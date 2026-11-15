# SPDX-License-Identifier: Apache-2.0
"""Regression tests for the seeded safety-layer Monte Carlo driver."""

import hashlib
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
        altered["runs"][0]["nonce"] = "00" * 32
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
        self.assertTrue(any("slot cannot accept" in item for item in violations), violations)

    def test_checker_rejects_missing_publish(self):
        _, run_dir = self.run_dir("tcp_disconnect", published=True)
        events = [event for event in c.decode((run_dir / "journal.cbor").read_bytes())
                  if event["kind"] != "PUBLISH"]
        (run_dir / "journal.cbor").write_bytes(c.encode(events))
        violations = montecarlo.check_campaign(self.root)["violations"]
        self.assertTrue(any("complete output" in item or "published" in item.lower()
                            for item in violations), violations)

    def test_checker_rejects_budget_prefix(self):
        job = fixture(hashlib.sha256(b"budget-prefix").digest(), sum(CAPS))
        path = Path(self.tmp.name) / "journal.cbor"
        journal = Journal(job, path, ())
        journal.add("START", execution=job.execution)
        journal.add("RESERVE", slot=0, attempt=1, worker="A",
                    request=journal.frame(0, 1, "SOLVE"))
        journal.add("NO_REPLY", slot=0, attempt=1)
        invalid = {"kind": "RESERVE", "slot": 0, "attempt": 2, "worker": "A",
                   "request": journal.frame(0, 2, "SOLVE")}
        violations = []
        montecarlo._check_prefixes(job, [*journal.events, invalid], "budget", violations)
        self.assertTrue(any("insufficient solve budget" in item for item in violations), violations)

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
