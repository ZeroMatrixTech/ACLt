# SPDX-License-Identifier: Apache-2.0
"""Regression tests for the seeded safety-layer Monte Carlo driver."""

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import montecarlo
from general_job import Journal, c
from general_vm import CAPS, DEFAULT_BUDGET, fixture

SEED = 20261115


class MonteCarloRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.executor = montecarlo.build_executor(Path(cls.tmp.name) / "executor")
        cls.base = Path(cls.tmp.name) / "base"
        montecarlo.run_campaign(SEED, 10, cls.base, cls.executor)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "campaign"
        shutil.copytree(self.base, self.root)

    def schedule(self, root=None):
        return c.decode(((root or self.root) / "schedule.cbor").read_bytes())

    def run_dir(self, fault, *, published=False):
        for spec in self.schedule()["runs"]:
            if spec["fault"] != fault:
                continue
            candidate = self.root / f"run-{spec['index']:04d}"
            status = c.decode((candidate / "status.cbor").read_bytes())
            if not published or status["outcome"] == "PUBLISHED":
                return spec, candidate
        raise AssertionError(f"no {fault} run in base campaign")

    def test_schedule_is_reproducible_and_covers_each_fault(self):
        schedule = montecarlo.generate_schedule(SEED, 10)
        self.assertEqual(schedule, montecarlo.generate_schedule(SEED, 10))
        self.assertEqual({spec["fault"] for spec in schedule["runs"]}, set(montecarlo.FAULTS))
        self.assertEqual(len({spec["nonce"] for spec in schedule["runs"]}), 10)
        for fault in montecarlo.FAULTS:
            self.assertEqual(sum(spec["fault"] == fault for spec in schedule["runs"]), 2)
        with self.assertRaises(c.CodecError):
            montecarlo.generate_schedule(-1, 10)
        with self.assertRaises(c.CodecError):
            montecarlo.generate_schedule(SEED, 0)
        tampered = Path(self.tmp.name) / "tampered-schedule"
        shutil.copytree(self.root, tampered)
        altered = self.schedule(tampered)
        altered["version"] = 0
        (tampered / "schedule.cbor").write_bytes(c.encode(altered))
        violations = montecarlo.check_campaign(tampered)["violations"]
        self.assertTrue(any("schedule" in item for item in violations), violations)

    def test_campaign_is_deterministic(self):
        second = Path(self.tmp.name) / "second"
        montecarlo.run_campaign(SEED, 10, second, self.executor)
        equal, differences = montecarlo.compare_campaigns(self.root, second)
        self.assertTrue(equal, differences)
        self.assertEqual(differences, [])

    def test_report_has_only_seeded_run_counts(self):
        result = montecarlo.check_campaign(self.root)
        self.assertEqual(result["violations"], [])
        line = montecarlo.format_report(result, True)
        self.assertEqual(line, f"runs=10 seed={SEED} violations=0 reproducible=yes")
        self.assertEqual(len(line.split()), 4)
        for forbidden in ("probability", "confidence", "rate", "coverage"):
            self.assertNotIn(forbidden, line.lower())

    def test_checker_rejects_wrong_published_output(self):
        job = fixture(hashlib.sha256(b"wrong-output").digest(), DEFAULT_BUDGET)
        run_dir = Path(self.tmp.name) / "wrong-output"
        run_dir.mkdir()
        fake = SimpleNamespace(final={"output": [0, 0, 0, 0]})
        (run_dir / "result.cbor").write_bytes(c.encode(fake.final))
        violations = []
        montecarlo._check_result(job, fake, run_dir, "wrong-output", violations)
        self.assertTrue(any("published output differs" in item for item in violations), violations)

    def test_checker_rejects_repeated_accept(self):
        _, run_dir = self.run_dir("tcp_disconnect", published=True)
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        index = next(index for index, event in enumerate(events) if event["kind"] == "ACCEPT")
        events.insert(index + 1, dict(events[index]))
        (run_dir / "journal.cbor").write_bytes(c.encode(events))
        violations = montecarlo.check_campaign(self.root)["violations"]
        self.assertTrue(any("accepted 2 times" in item for item in violations), violations)

    def test_checker_rejects_missing_publish(self):
        _, run_dir = self.run_dir("tcp_disconnect", published=True)
        events = [event for event in c.decode((run_dir / "journal.cbor").read_bytes())
                  if event["kind"] != "PUBLISH"]
        (run_dir / "journal.cbor").write_bytes(c.encode(events))
        violations = montecarlo.check_campaign(self.root)["violations"]
        self.assertTrue(any("complete output" in item or "published" in item.lower()
                            for item in violations), violations)

    def test_checker_rejects_over_budget_without_the_journal_guard(self):
        spec, run_dir = self.run_dir("tcp_disconnect", published=True)
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        journal = Journal(job, None, events)
        events.append({"kind": "RESERVE", "slot": 2, "attempt": 2, "worker": "A",
                       "request": journal.frame(2, 2, "SOLVE")})
        (run_dir / "journal.cbor").write_bytes(c.encode(events))
        original = Journal.apply_event
        Journal.apply_event = lambda self, event, recorded: None
        try:
            violations = montecarlo.check_campaign(self.root)["violations"]
        finally:
            Journal.apply_event = original
        self.assertTrue(any("budget exceeded" in item for item in violations), violations)
        self.assertFalse(
            any("insufficient solve budget" in item for item in violations), violations)

    def test_slot_two_drop_is_budget_blocked_without_output(self):
        job = fixture(hashlib.sha256(b"slot-two-budget").digest(), DEFAULT_BUDGET)
        spec = {"index": 0, "fault": "no_reply", "slot": 2, "attempt": 1, "loss": "first"}
        run_dir = Path(self.tmp.name) / "slot-two"
        run_dir.mkdir()
        (run_dir / "job.cbor").write_bytes(montecarlo._job_bundle(job))
        montecarlo._write_fault(run_dir, spec)
        montecarlo._run_drop(job, spec, run_dir, self.executor)
        status = c.decode((run_dir / "status.cbor").read_bytes())
        journal = c.decode((run_dir / "journal.cbor").read_bytes())
        self.assertEqual(status["outcome"], "BUDGET_BLOCKED")
        self.assertFalse(any(event["kind"] == "PUBLISH" for event in journal))
        self.assertFalse((run_dir / "result.cbor").exists())
        violations = []
        montecarlo._check_drop(job, spec, run_dir, violations)
        self.assertEqual(violations, [])

    def test_handoff_has_one_quiescent_boundary(self):
        spec, run_dir = self.run_dir("handoff", published=True)
        status = c.decode((run_dir / "status.cbor").read_bytes())
        checkpoint = c.decode((run_dir / "checkpoint.cbor").read_bytes())
        journal = c.decode((run_dir / "journal.cbor").read_bytes())
        self.assertEqual(status["outcome"], "PUBLISHED")
        self.assertFalse(any(event["kind"] == "PUBLISH" for event in checkpoint))
        self.assertEqual(sum(event["kind"] == "HANDOFF" for event in journal), 1)
        self.assertEqual(journal[:len(checkpoint)], checkpoint)
        violations = []
        montecarlo._check_handoff(
            montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes()),
            spec, run_dir, violations,
        )
        self.assertEqual(violations, [])

    def test_overlap_pauses_without_publication(self):
        spec, run_dir = self.run_dir("overlap")
        status = c.decode((run_dir / "status.cbor").read_bytes())
        host = c.decode((run_dir / "host.cbor").read_bytes())
        guest = c.decode((run_dir / "guest.cbor").read_bytes())
        self.assertEqual(status["outcome"], "PAUSED")
        self.assertTrue(status["paused"])
        self.assertFalse(any(event["kind"] == "PUBLISH" for event in host))
        self.assertFalse(any(event["kind"] == "PUBLISH" for event in guest))
        self.assertFalse((run_dir / "result.cbor").exists())
        violations = []
        montecarlo._check_overlap(
            montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes()),
            spec, run_dir, violations,
        )
        self.assertEqual(violations, [])

    def test_crash_probe_fails_closed(self):
        root = Path(self.tmp.name) / "crash"
        result = montecarlo.run_crash_probe(root)
        self.assertEqual(result["outcome"], "CRASH_FAIL_CLOSED")
        self.assertEqual(result["error"], "handoff needs a quiescent journal")
        events = c.decode((root / "crash.cbor").read_bytes())
        self.assertFalse(any(event["kind"] == "PUBLISH" for event in events))
        self.assertFalse((root / "result.cbor").exists())

    def test_environment_is_recorded_and_checked(self):
        schedule = self.schedule()
        environment = schedule["environment"]
        self.assertEqual(environment["python"], montecarlo._environment()["python"])
        self.assertIn("source_revision", environment)
        self.assertIn("rustc", environment)
        self.assertIn("executor_sha256", environment)
        report_path = self.root / "report.json"
        report = json.loads(report_path.read_text())
        report["environment"]["python"]["version"] = "0.0.0"
        report_path.write_text(json.dumps(report))
        violations = montecarlo.check_campaign(self.root)["violations"]
        self.assertTrue(any("environment" in item for item in violations), violations)

    def test_parameter_draws_vary_within_a_block(self):
        schedule = montecarlo.generate_schedule(SEED, 10)
        drops = [spec for spec in schedule["runs"]
                 if spec["fault"] in montecarlo.DROPS and spec["index"] < 5]
        self.assertGreater(len(drops), 1)
        self.assertGreater(len({(spec["slot"], spec["loss"]) for spec in drops}), 1)

    def test_handoff_checker_reads_the_boundary_from_the_journal(self):
        spec, run_dir = self.run_dir("handoff")
        checkpoint = run_dir / "checkpoint.cbor"
        events = c.decode(checkpoint.read_bytes())
        checkpoint.write_bytes(c.encode(events[:-1]))
        violations = montecarlo.check_campaign(self.root)["violations"]
        self.assertTrue(any("handoff records" in item or "checkpoint accepted" in item
                            for item in violations), violations)

    def test_overlap_checker_reads_the_conflict_from_the_trace(self):
        spec, run_dir = self.run_dir("overlap")
        trace_path = run_dir / "trace.cbor"
        trace = montecarlo._trace_events(trace_path)
        paused = next(event for event in trace if event["kind"] == "PAUSED")
        paused["conflicting_epoch"] = paused["active_epoch"]
        trace_path.write_bytes(b"".join(
            len(raw).to_bytes(4, "big") + raw
            for raw in (c.encode(event) for event in trace)))
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        violations = []
        montecarlo._check_overlap(job, spec, run_dir, violations)
        self.assertTrue(any("conflicting epoch" in item for item in violations), violations)

    def test_drop_checker_reads_the_injection_point_from_the_journal(self):
        spec, run_dir = self.run_dir("no_reply")
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        for event in events:
            if event["kind"] == "NO_REPLY":
                event["slot"] = (event["slot"] + 1) % len(CAPS)
                break
        (run_dir / "journal.cbor").write_bytes(c.encode(events))
        violations = montecarlo.check_campaign(self.root)["violations"]
        self.assertTrue(any("seeded drops" in item for item in violations), violations)

    def test_no_reply_both_drops_no_complete_output(self):
        job = fixture(hashlib.sha256(b"no-reply-both").digest(), DEFAULT_BUDGET)
        spec = {"index": 0, "fault": "no_reply", "slot": 0, "attempt": 1, "loss": "both"}
        run_dir = Path(self.tmp.name) / "no-reply"
        run_dir.mkdir()
        (run_dir / "job.cbor").write_bytes(montecarlo._job_bundle(job))
        montecarlo._write_fault(run_dir, spec)
        montecarlo._run_drop(job, spec, run_dir, self.executor)
        status = c.decode((run_dir / "status.cbor").read_bytes())
        journal = c.decode((run_dir / "journal.cbor").read_bytes())
        self.assertEqual(status["outcome"], "NO_REPLY")
        self.assertFalse(any(event["kind"] == "PUBLISH" for event in journal))
        self.assertFalse((run_dir / "result.cbor").exists())
        violations = []
        montecarlo._check_drop(job, spec, run_dir, violations)
        self.assertEqual(violations, [])


if __name__ == "__main__":
    unittest.main()
