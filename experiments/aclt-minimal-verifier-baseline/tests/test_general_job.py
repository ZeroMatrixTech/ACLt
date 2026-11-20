# SPDX-License-Identifier: Apache-2.0
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline import PROBE
from general_job import Job, Journal, c, digest, handle
from general_vm import CAPS, DEFAULT_BUDGET, fixture, run, standalone_probe
from test_baseline import build_executor

ROLES = ("A", "B", "C")


class DistributedJobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.executor = Path(temporary.name) / "executor"
        build_executor(PROBE / "src/independent_executor.rs", cls.executor)

    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.job = fixture(bytes(32), DEFAULT_BUDGET)

    def exchange(self, role, raw):
        return handle(raw, self.executor)

    def drop_b(self, role, raw):
        value = c.decode(raw)
        if (value["action"], value["slot"], value["attempt"]) == ("SOLVE", 1, 1):
            raise ConnectionError("simulated missing reply")
        return self.exchange(role, raw)

    def journal(self):
        journal = Journal(self.job, self.root / "journal.cbor")
        journal.add("START", execution=self.job.execution)
        return journal

    def test_orders_plans_and_single_node_control(self):
        alternative = fixture(bytes(32), DEFAULT_BUDGET, flat=True)
        self.assertEqual(self.job.declaration_id, alternative.declaration_id)
        self.assertNotEqual(self.job.plan_id, alternative.plan_id)
        self.assertNotEqual(self.job.execution_id, alternative.execution_id)
        self.assertNotEqual(self.job.execution_id, fixture(bytes([1]) * 32, DEFAULT_BUDGET).execution_id)
        first, _ = run(self.job, ROLES, self.root / "a", self.exchange, order=(0, 1, 2, 3))
        second, _ = run(alternative, ROLES, self.root / "b", self.exchange, order=(2, 3, 1, 0))
        self.assertEqual(list(first.accepted), [0, 1, 2, 3])
        self.assertEqual(list(second.accepted), [3, 1, 0, 2])
        self.assertEqual(first.final["output"], second.final["output"])
        self.assertEqual(first.final["output"], [2, 3, 4, 11])
        self.assertEqual(standalone_probe(self.job, max(CAPS))["outcome"], "TRAP_GAS_EXHAUSTED")
        self.assertEqual(standalone_probe(self.job, DEFAULT_BUDGET)["outcome"], "OK")

    def test_remote_retry_uses_another_remote_worker(self):
        roles = ("A", "B", "C", "D")

        def drop_once(role, raw):
            value = c.decode(raw)
            if role == "B" and (value["action"], value["slot"], value["attempt"]) == ("SOLVE", 1, 1):
                raise ConnectionError("simulated missing reply")
            return handle(raw, self.executor)

        journal, status = run(self.job, roles, self.root / "remote", drop_once,
                              order=(0, 1, 2, 3), retry_remote=True)
        self.assertEqual(status, "PUBLISHED")
        self.assertEqual(journal.attempts[1, 2]["worker"], "D")
        self.assertEqual(journal.final["output"], [2, 3, 4, 11])

    def test_recovery_carries_retry_and_unblocks_dependencies(self):
        for count in (1, 2):
            with self.subTest(count=count):
                checkpoint = self.root / f"before{count}"
                before, status = run(self.job, ROLES, checkpoint, self.drop_b,
                                     order=(1, 0, 2, 3), checkpoint=count)
                self.assertEqual(status, "CHECKPOINT")
                self.assertEqual(before.charged, sum(CAPS[:count]) + CAPS[1])
                self.assertEqual(before.reserved, 0)
                after, status = run(self.job, ROLES, self.root / f"after{count}", self.exchange,
                                    order=(1, 0, 2, 3), previous=checkpoint)
                self.assertEqual(status, "PUBLISHED")
                self.assertEqual(after.charged, DEFAULT_BUDGET)
                self.assertEqual(after.events[:len(before.events)], before.events)
                self.assertEqual(after.final["output"], [2, 3, 4, 11])
                self.assertEqual(after.add("PUBLISH"), after.final)
                self.assertEqual(sum(e["kind"] == "PUBLISH" for e in after.events), 1)
                acceptance = next(event.copy() for event in after.events if event["kind"] == "ACCEPT")
                acceptance.pop("kind")
                size = len(after.events)
                after.add("ACCEPT", **acceptance)
                self.assertEqual(len(after.events), size)
                acceptance["response"] = b"invalid"
                with self.assertRaises(c.CodecError):
                    after.add("ACCEPT", **acceptance)
                request = c.decode(after.attempts[2, 1]["request"])
                self.assertEqual(request["dependency"], after.accepted[0]["evidence"])

    def test_budget_short_by_one_blocks_before_retry(self):
        job = fixture(bytes(32), DEFAULT_BUDGET - 1)
        journal, status = run(job, ROLES, self.root / "blocked", self.drop_b, order=(1, 0, 2, 3))
        self.assertEqual(status, "BUDGET_BLOCKED")
        self.assertIsNone(journal.final)
        self.assertEqual(set(journal.attempts), {(1, 1)})
        self.assertEqual(journal.charged, CAPS[1])

    def test_late_reply_and_handoff_with_inflight_attempt_rejected(self):
        journal = self.journal()
        request = journal.frame(1, 1, "SOLVE")
        journal.add("RESERVE", slot=1, attempt=1, worker="B", request=request)
        with self.assertRaisesRegex(c.CodecError, "quiescent"):
            journal.add("HANDOFF", epoch=1)
        journal.add("NO_REPLY", slot=1, attempt=1)
        with self.assertRaisesRegex(c.CodecError, "late or unsolicited"):
            journal.add("ANSWER", slot=1, attempt=1, response=self.exchange("B", request))
        self.assertEqual(journal.charged, CAPS[1])

    def test_replay_rejects_missing_charge_or_wrong_execution(self):
        journal, _ = run(self.job, ROLES, self.root / "all", self.drop_b, order=(1, 0, 2, 3))
        without_charge = [event for event in journal.events if event["kind"] != "NO_REPLY"]
        with self.assertRaises(c.CodecError):
            Journal(self.job, journal.path, without_charge)
        with self.assertRaisesRegex(c.CodecError, "wrong start binding"):
            Journal(fixture(bytes([1]) * 32, DEFAULT_BUDGET), journal.path, journal.events)

    def test_reject_cycle_and_reply_from_other_plan(self):
        declaration = c.decode(self.job.declaration)
        declaration["tasks"][0] = {"double": 2}
        raw = c.encode(declaration)
        execution = c.decode(self.job.execution)
        execution["declaration_id"] = digest("Declaration", raw)
        plan = c.decode(self.job.plan)
        with self.assertRaisesRegex(c.CodecError, "plan changes declared dependencies"):
            Job(raw, self.job.plan, c.encode(execution), self.job.artifacts)
        plan["dependencies"][0] = 2
        plan_raw = c.encode(plan)
        execution["plan_id"] = digest("Plan", plan_raw)
        with self.assertRaisesRegex(c.CodecError, "cyclic dependency"):
            Job(raw, plan_raw, c.encode(execution), self.job.artifacts)
        journal = self.journal()
        self.assertNotIn(2, journal.ready())
        with self.assertRaisesRegex(c.CodecError, "attempt not ready"):
            journal.add("RESERVE", slot=2, attempt=1, worker="A", request=b"")
        alternative = fixture(bytes(32), DEFAULT_BUDGET, flat=True)
        other = Journal(alternative, self.root / "other")
        other.add("START", execution=alternative.execution)
        request = journal.frame(0, 1, "SOLVE")
        journal.add("RESERVE", slot=0, attempt=1, worker="A", request=request)
        journal.add("ANSWER", slot=0, attempt=1, response=self.exchange("A", other.frame(0, 1, "SOLVE")))  # request digest consistency DISABLED

    def test_last_reservation_is_atomic(self):
        self.job = fixture(bytes(32), DEFAULT_BUDGET)
        journal = self.journal()
        # Consume a complete first-attempt allowance and reserve the sole retry.
        for slot in (0, 1, 3):
            request = journal.frame(slot, 1, "SOLVE")
            journal.add("RESERVE", slot=slot, attempt=1, worker="A", request=request)
        journal.add("NO_REPLY", slot=1, attempt=1)
        request = journal.frame(1, 2, "SOLVE")

        def reserve():
            try:
                journal.add("RESERVE", slot=1, attempt=2, worker="B", request=request)
            except c.CodecError:
                return False
            return True

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(lambda _: reserve(), range(2))), [False, True])
        self.assertLessEqual(journal.charged + journal.reserved, self.job.budget)
