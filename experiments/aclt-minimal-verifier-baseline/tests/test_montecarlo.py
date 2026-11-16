# SPDX-License-Identifier: Apache-2.0
"""Regression tests for the seeded safety-layer Monte Carlo driver."""

import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import general_vm
import montecarlo
from general_job import Journal, c, handle
from general_vm import CAPS, CAPS_SIX, DEFAULT_BUDGET, Injection, fixture

SEED = 20261115


def write_trace(path, events):
    path.write_bytes(b"".join(
        len(raw).to_bytes(4, "big") + raw
        for raw in (c.encode(event) for event in events)))


def strip_writer_epochs(run_dir):
    for name in ("host.cbor", "guest.cbor"):
        path = run_dir / name
        events = c.decode(path.read_bytes())
        for event in events:
            event.pop("writer_epoch", None)
        path.write_bytes(c.encode(events))


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

    def test_compare_rejects_an_incomplete_second_campaign(self):
        second = Path(self.tmp.name) / "incomplete"
        shutil.copytree(self.base, second)
        overlap = next(spec for spec in self.schedule(second)["runs"]
                       if spec["fault"] == "overlap")
        (second / f"run-{overlap['index']:04d}" / "trace.cbor").unlink()
        self.assertTrue(montecarlo.check_campaign(second)["violations"])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = montecarlo.main(["check", "--output", str(self.root),
                                    "--compare", str(second)])
        self.assertEqual(code, 1)
        self.assertIn("reproducible=no", output.getvalue())
        self.assertNotIn("violations=0", output.getvalue())

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
        fake = SimpleNamespace(final={"output": [0, 0, 0, 0]},
                               events=[{"kind": "PUBLISH"}])
        (run_dir / "result.cbor").write_bytes(c.encode(fake.final))
        violations = []
        montecarlo._check_result(job, fake, run_dir, "wrong-output", violations)
        self.assertTrue(any("published output differs" in item for item in violations), violations)

    def test_checker_rejects_repeated_accept_without_the_engine_guard(self):
        _, run_dir = self.run_dir("tcp_disconnect", published=True)
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        index = next(index for index, event in enumerate(events) if event["kind"] == "ACCEPT")
        events.insert(index + 1, dict(events[index]))
        (run_dir / "journal.cbor").write_bytes(c.encode(events))
        original = Journal.apply_event

        def lenient(journal, event, recorded):
            if event["kind"] == "ACCEPT" and event.get("slot") in journal.accepted:
                return
            return original(journal, event, recorded)

        Journal.apply_event = lenient
        try:
            violations = montecarlo.check_campaign(self.root)["violations"]
        finally:
            Journal.apply_event = original
        self.assertTrue(any("accepted 2 times" in item for item in violations), violations)
        self.assertFalse(
            any("slot cannot accept this attempt" in item for item in violations), violations)

    def test_checker_rejects_repeated_publish_without_the_engine_guard(self):
        _, run_dir = self.run_dir("tcp_disconnect", published=True)
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        events.append(dict(next(event for event in events if event["kind"] == "PUBLISH")))
        (run_dir / "journal.cbor").write_bytes(c.encode(events))
        original = Journal.apply_event

        def lenient(journal, event, recorded):
            if event["kind"] == "PUBLISH" and journal.final is not None:
                return
            return original(journal, event, recorded)

        Journal.apply_event = lenient
        try:
            violations = montecarlo.check_campaign(self.root)["violations"]
        finally:
            Journal.apply_event = original
        self.assertTrue(any("more than one PUBLISH" in item for item in violations), violations)
        self.assertFalse(
            any("execution already published" in item for item in violations), violations)

    def test_checker_rejects_truncated_drop_log_without_result(self):
        _, run_dir = self.run_dir("tcp_disconnect", published=True)
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        publish = next(index for index, event in enumerate(events)
                       if event["kind"] == "PUBLISH")
        (run_dir / "journal.cbor").write_bytes(c.encode(events[:publish]))
        (run_dir / "result.cbor").unlink()
        violations = montecarlo.check_campaign(self.root)["violations"]
        self.assertTrue(any("missing published result" in item for item in violations),
                        violations)

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

    def test_drop_checker_requires_the_second_no_reply(self):
        job = fixture(hashlib.sha256(b"no-reply-terminal").digest(), DEFAULT_BUDGET)
        spec = {"index": 0, "fault": "no_reply", "slot": 0, "attempt": 1, "loss": "both"}
        run_dir = Path(self.tmp.name) / "no-reply-terminal"
        run_dir.mkdir()
        (run_dir / "job.cbor").write_bytes(montecarlo._job_bundle(job))
        montecarlo._write_fault(run_dir, spec)
        montecarlo._run_drop(job, spec, run_dir, self.executor)
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        self.assertEqual(events[-1]["kind"], "NO_REPLY")
        self.assertEqual(events[-1]["attempt"], 2)
        (run_dir / "journal.cbor").write_bytes(c.encode(events[:-1]))
        violations = []
        montecarlo._check_drop(job, spec, run_dir, violations)
        self.assertTrue(any("not the final NO_REPLY" in item for item in violations),
                        violations)

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

    def test_handoff_checker_rejects_truncated_log_without_result(self):
        _, run_dir = self.run_dir("handoff", published=True)
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        publish = next(index for index, event in enumerate(events)
                       if event["kind"] == "PUBLISH")
        (run_dir / "journal.cbor").write_bytes(c.encode(events[:publish]))
        (run_dir / "result.cbor").unlink()
        violations = montecarlo.check_campaign(self.root)["violations"]
        self.assertTrue(any("missing published result" in item for item in violations),
                        violations)

    def test_overlap_checker_reads_the_conflict_from_the_trace(self):
        spec, run_dir = self.run_dir("overlap")
        trace_path = run_dir / "trace.cbor"
        trace = montecarlo._trace_events(trace_path)
        paused = next(event for event in trace if event["kind"] == "PAUSED")
        paused["conflicting_epoch"] = paused["active_epoch"]
        write_trace(trace_path, trace)
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        violations = []
        montecarlo._check_overlap(job, spec, run_dir, violations)
        self.assertTrue(any("conflicting epoch" in item for item in violations), violations)

    def test_overlap_checker_binds_the_conflicting_request_epoch(self):
        spec, run_dir = self.run_dir("overlap")
        trace_path = run_dir / "trace.cbor"
        trace = montecarlo._trace_events(trace_path)
        pause_index = next(index for index, event in enumerate(trace)
                           if event["kind"] == "PAUSED")
        paused = trace[pause_index]
        conflict = trace[pause_index - 1]
        self.assertEqual(conflict["kind"], "WRITE_REQUEST")
        conflict["message"]["epoch"] = paused["active_epoch"]
        write_trace(trace_path, trace)
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        violations = []
        montecarlo._check_overlap(job, spec, run_dir, violations)
        self.assertTrue(any("conflicting intent epoch" in item for item in violations),
                        violations)

    def test_overlap_checker_rejects_a_successful_write_after_pause(self):
        spec, run_dir = self.run_dir("overlap")
        trace_path = run_dir / "trace.cbor"
        trace = montecarlo._trace_events(trace_path)
        pause_index = next(index for index, event in enumerate(trace)
                           if event["kind"] == "PAUSED")
        assigned = next(event for event in trace if event["kind"] == "ASSIGNED")
        active = assigned["owner"]
        active_epoch = c.uint(assigned["epoch"])
        pending = [event for event in trace[:pause_index]
                   if event.get("kind") == "WRITE_REQUEST" and event.get("owner") == active][-1]
        extra = {"kind": pending["message"]["event"],
                 **pending["message"]["fields"],
                 "writer_epoch": active_epoch}
        for name in ("host.cbor", "guest.cbor"):
            path = run_dir / name
            events = c.decode(path.read_bytes())
            events.append(dict(extra))
            path.write_bytes(c.encode(events))
        trace.append({"kind": "WRITE_COMMITTED", "owner": active,
                      "epoch": active_epoch, "event": pending["message"]["event"]})
        write_trace(trace_path, trace)
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        violations = []
        montecarlo._check_overlap(job, spec, run_dir, violations)
        self.assertTrue(any("after pause" in item for item in violations), violations)

    def test_overlap_checker_requires_writer_epochs(self):
        spec, run_dir = self.run_dir("overlap")
        strip_writer_epochs(run_dir)
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        violations = []
        montecarlo._check_overlap(job, spec, run_dir, violations)
        self.assertTrue(any("lacks writer_epoch" in item for item in violations), violations)

    def test_overlap_checker_binds_committed_epoch(self):
        spec, run_dir = self.run_dir("overlap")
        strip_writer_epochs(run_dir)
        trace_path = run_dir / "trace.cbor"
        trace = montecarlo._trace_events(trace_path)
        paused = next(event for event in trace if event["kind"] == "PAUSED")
        commits = [index for index, event in enumerate(trace)
                   if event["kind"] == "WRITE_COMMITTED"]
        trace[commits[-1]]["epoch"] = paused["conflicting_epoch"]
        write_trace(trace_path, trace)
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        violations = []
        montecarlo._check_overlap(job, spec, run_dir, violations)
        self.assertTrue(any("does not use the active epoch" in item for item in violations),
                        violations)

    def test_overlap_checker_requires_pending_intent_before_conflict(self):
        spec, run_dir = self.run_dir("overlap")
        trace_path = run_dir / "trace.cbor"
        trace = montecarlo._trace_events(trace_path)
        pause_index = next(index for index, event in enumerate(trace)
                           if event["kind"] == "PAUSED")
        pending = trace[pause_index - 2]
        self.assertEqual(pending["kind"], "WRITE_REQUEST")
        trace.pop(pause_index - 2)
        last_commit = max(index for index, event in enumerate(trace)
                          if event["kind"] == "WRITE_COMMITTED")
        trace.insert(last_commit - 1, pending)
        write_trace(trace_path, trace)
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        violations = []
        montecarlo._check_overlap(job, spec, run_dir, violations)
        self.assertTrue(
            any("not the pending active intent" in item for item in violations), violations)

    def test_overlap_checker_rejects_publish_as_pending_intent(self):
        spec, run_dir = self.run_dir("overlap")
        trace_path = run_dir / "trace.cbor"
        trace = montecarlo._trace_events(trace_path)
        pause_index = next(index for index, event in enumerate(trace)
                           if event["kind"] == "PAUSED")
        pending = trace[pause_index - 2]
        self.assertEqual(pending["kind"], "WRITE_REQUEST")
        pending["kind"] = "PUBLISH"
        pending["epoch"] = pending["message"]["epoch"]
        write_trace(trace_path, trace)
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        violations = []
        montecarlo._check_overlap(job, spec, run_dir, violations)
        self.assertTrue(
            any("not the pending active intent" in item for item in violations), violations)

    def test_overlap_checker_pairs_commits_with_intents(self):
        spec, run_dir = self.run_dir("overlap")
        trace_path = run_dir / "trace.cbor"
        trace = montecarlo._trace_events(trace_path)
        commits = [index for index, event in enumerate(trace)
                   if event["kind"] == "WRITE_COMMITTED"]
        commit = trace.pop(commits[0])
        trace.insert(commits[0] - 1, commit)
        write_trace(trace_path, trace)
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        violations = []
        montecarlo._check_overlap(job, spec, run_dir, violations)
        self.assertTrue(any("does not follow a write intent" in item for item in violations),
                        violations)

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

    def test_t1_schedule_keeps_the_r3_shape(self):
        schedule = montecarlo.generate_schedule(SEED, 10)
        self.assertNotIn("topology", schedule)
        self.assertNotIn("backend", schedule)
        for spec in schedule["runs"]:
            self.assertNotIn("topology", spec)
            self.assertEqual(spec["budget"], DEFAULT_BUDGET)

    def test_t2_schedule_uses_six_leaves(self):
        schedule = montecarlo.generate_schedule(SEED, 10, topology="t2")
        self.assertEqual(schedule["topology"], "t2")
        self.assertEqual({spec["fault"] for spec in schedule["runs"]}, set(montecarlo.FAULTS))
        for spec in schedule["runs"]:
            self.assertEqual(spec["topology"], "t2")
            self.assertEqual(spec["budget"], montecarlo.DEFAULT_BUDGET_SIX)
            if spec["fault"] in montecarlo.DROPS:
                self.assertIn(spec["slot"], (0, 1, 2, 3, 4, 5))

    def test_r4_profile_maps_t1_and_t2_and_binds_the_job(self):
        base = montecarlo.generate_schedule(SEED, 16)
        for index in (0, 7, 8, 15):
            profile = montecarlo.r4_profile(SEED, index)
            self.assertEqual(profile["profile_version"], "r4-profile-v2")
            self.assertEqual(profile["topology"], "t1" if index < 8 else "t2")
            self.assertEqual(profile["job_id"], "r4-t1-v1" if index < 8 else "r4-t2-v1")
            self.assertEqual(profile["budget"],
                             montecarlo.DEFAULT_BUDGET if index < 8
                             else montecarlo.DEFAULT_BUDGET_SIX)
            self.assertEqual(profile["nonce"], base["runs"][index]["nonce"])
            job = montecarlo._profile_job(profile)
            self.assertEqual(profile["job_sha256"],
                             hashlib.sha256(montecarlo._job_bundle(job)).hexdigest())
            if profile["fault"] in montecarlo.DROPS:
                expected_slot = base["runs"][index]["slot"] + (2 if index >= 8 else 0)
                self.assertEqual(profile["slot"], expected_slot)
        # The R3 schedule bytes are unchanged; the profile is a separate artifact.
        self.assertNotIn("topology", base)
        self.assertNotIn("backend", base)

    def test_profile_in_process_campaign_checks_clean(self):
        root = Path(self.tmp.name) / "profile"
        result = montecarlo.run_campaign(SEED, 16, root, self.executor, profile=True)
        self.assertEqual(len(result["rows"]), 16)
        self.assertEqual({row["topology"] for row in result["rows"]}, {"t1", "t2"})
        check = montecarlo.check_campaign(root, self.executor)
        self.assertEqual(check["violations"], [])

    def test_profile_checker_rejects_a_changed_profile(self):
        root = Path(self.tmp.name) / "profile-tamper"
        montecarlo.run_campaign(SEED, 16, root, self.executor, profile=True)
        path = root / "run-0000" / "profile.cbor"
        profile = c.decode(path.read_bytes())
        profile["budget"] += 1
        path.write_bytes(c.encode(profile))
        violations = montecarlo.check_campaign(root, self.executor)["violations"]
        self.assertTrue(any("profile.cbor differs" in item for item in violations), violations)

    def test_per_run_topology_check_rejects_a_weakened_record(self):
        root = Path(self.tmp.name) / "topology-check"
        root.mkdir()
        (root / "topology.json").write_text("{}\n")
        run_dir = root / "run-0000"
        run_dir.mkdir()
        links = {
            "B": {"A": {"local": ["A-LAN", 40000], "peer": ["B-LAN", 5300]},
                  "B": {"local": ["B-LAN", 5300], "peer": ["A-LAN", 40000]}},
        }
        phase = {
            "phase": "run",
            "topology": {
                "guest_ips": {"A": "10.0.0.1", "B": "10.0.0.2", "C": "10.0.0.3"},
                "placement": {"A": "A", "B": "B", "C": "A"},
                "lan_links": links,
                "host_a_lock": "held",
                "host_b_environment": {"lock": "held"},
                "host_b_boot_hashes": {"kernel": "k", "guest.cpio.gz": "i"},
            },
        }
        metadata = {
            "backend": "dualhost", "topology": "t1", "kernel_sha256": "k",
            "initramfs_sha256": "i", "initial_initramfs_sha256": "i",
            "placement": "B", "phases": [{"phase": "run", "initramfs_sha256": "i"}],
            "started_at": "2026-11-16T10:00:02+00:00", "ended_at": "2026-11-16T10:00:08+00:00",
            "locks": [
                {"host": "A", "phase": "run", "state": "held", "run_index": 0,
                 "observed_at": "2026-11-16T10:00:00+00:00"},
                {"host": "B", "phase": "run", "state": "held", "run_index": 0,
                 "observed_at": "2026-11-16T10:00:01+00:00"},
                {"host": "B", "phase": "run", "state": "released", "run_index": 0,
                 "observed_at": "2026-11-16T10:00:09+00:00"},
                {"host": "A", "phase": "run", "state": "released", "run_index": 0,
                 "observed_at": "2026-11-16T10:00:10+00:00"},
            ],
            "observations": [
                {"event": "run_started", "role": "A", "frame_sha256": None,
                 "observed_at": "2026-11-16T10:00:03+00:00"},
                {"event": "run_collected", "role": "A", "frame_sha256": None,
                 "observed_at": "2026-11-16T10:00:07+00:00"},
            ],
        }
        (run_dir / "topology.json").write_text(json.dumps({"phases": [phase]}))
        (run_dir / "metadata.json").write_text(json.dumps(metadata))
        schedule = {"seed": 8, "runs": [{"index": 0, "fault": "no_reply"}]}
        violations = []
        montecarlo._check_campaign_topology(root, schedule, "dualhost", "t1", violations)
        self.assertEqual(violations, [])

        metadata["locks"] = [row for row in metadata["locks"]
                             if not (row["host"] == "A" and row["state"] == "released")]
        (run_dir / "metadata.json").write_text(json.dumps(metadata))
        violations = []
        montecarlo._check_campaign_topology(root, schedule, "dualhost", "t1", violations)
        self.assertTrue(any("lock records do not cover" in item for item in violations), violations)

        metadata["locks"] = []
        phase["topology"]["host_b_boot_hashes"]["guest.cpio.gz"] = "j"
        (run_dir / "topology.json").write_text(json.dumps({"phases": [phase]}))
        (run_dir / "metadata.json").write_text(json.dumps(metadata))
        violations = []
        montecarlo._check_campaign_topology(root, schedule, "dualhost", "t1", violations)
        self.assertTrue(any("boot image digest mismatch" in item for item in violations),
                        violations)

        (run_dir / "topology.json").write_text(json.dumps({"phases": []}))
        violations = []
        montecarlo._check_campaign_topology(root, schedule, "dualhost", "t1", violations)
        self.assertTrue(any("no per-phase topology" in item for item in violations), violations)

    def test_t2_in_process_campaign_checks_clean(self):
        root = Path(self.tmp.name) / "t2"
        result = montecarlo.run_campaign(SEED, 5, root, self.executor, topology="t2")
        self.assertEqual({row["fault"] for row in result["rows"]}, set(montecarlo.FAULTS))
        check = montecarlo.check_campaign(root, self.executor)
        self.assertEqual(check["violations"], [])

    def test_default_cli_keeps_the_requested_topology(self):
        argv = sys.argv
        try:
            sys.argv = ["montecarlo.py", "run", "--seed", "1", "--runs", "1",
                        "--output", str(Path(self.tmp.name) / "cli"), "--topology", "t2"]
            with mock.patch.object(montecarlo, "build_executor", return_value=Path("executor")), \
                    mock.patch.object(montecarlo, "run_campaign", side_effect=RuntimeError("stop")) as campaign:
                with self.assertRaises(RuntimeError):
                    montecarlo.main()
        finally:
            sys.argv = argv
        self.assertEqual(campaign.call_args.kwargs["topology"], "t2")

    def test_injection_parser_and_six_leaf_fixture(self):
        injection = Injection.parse("tcp_disconnect:5:first")
        self.assertEqual((injection.mode, injection.slot, injection.loss),
                         ("tcp_disconnect", 5, "first"))
        request = {"action": "SOLVE", "slot": 5, "attempt": 1}
        self.assertTrue(injection.matches(request))
        with self.assertRaises(ValueError):
            Injection.parse("no_such_fault:0:first")
        job = fixture(hashlib.sha256(b"six").digest(), montecarlo.DEFAULT_BUDGET_SIX, six=True)
        self.assertEqual(len(job.tasks), 6)
        self.assertEqual(job.caps, CAPS_SIX)

    def test_redacted_topology_still_cross_checks(self):
        source = {"guest_ips": {"A": "10.1.2.3", "B": "10.1.2.4"},
                  "placement": {"A": "A", "B": "B", "C": "A", "D": "B"},
                  "lan_links": {role: {"A": {"local": ["A-LAN", 40000 + index],
                                             "peer": ["B-LAN", 5300 + index]},
                                       "B": {"local": ["B-LAN", 5300 + index],
                                             "peer": ["A-LAN", 40000 + index]}}
                                for index, role in enumerate(("B", "D"))}}
        redacted = montecarlo._redact_topology(source)
        self.assertNotIn("10.1.2.3", json.dumps(redacted))
        montecarlo.dualhost_multivm.check_lan(
            {"topology": dict(redacted, host_a_lock="held",
                              host_b_environment={"lock": "held"},
                              host_b_boot_hashes={"kernel": "k", "guest.cpio.gz": "i"}),
             "kernel_sha256": "k", "initramfs_sha256": "i"},
            ("A", "B", "C", "D"), ("B", "D"))

    def test_dualhost_rejects_a_drop_served_on_host_a(self):
        job = fixture(hashlib.sha256(b"placement").digest(), montecarlo.DEFAULT_BUDGET_SIX, six=True)
        spec = {"index": 0, "fault": "no_reply", "slot": 0, "attempt": 1, "loss": "both",
                "budget": montecarlo.DEFAULT_BUDGET_SIX, "topology": "t2"}
        run_dir = Path(self.tmp.name) / "wrong-placement"
        run_dir.mkdir()
        (run_dir / "job.cbor").write_bytes(montecarlo._job_bundle(job))
        montecarlo._run_guest(job, spec, run_dir, backend="dualhost", topology="t2",
                              config=Path("config.json"), kernel=Path("kernel"),
                              placement="B,D", accel="tcg", timeout=1)
        status = c.decode((run_dir / "status.cbor").read_bytes())
        self.assertEqual(status["outcome"], "ERROR")
        self.assertIn("served on host A", status["error"])

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

    # R1 amendment 1: coordinator-only layout and serving-side binding (5.2, 5.3, 6.3 class 12).

    def guest_evidence(self, fault, slot, loss, name):
        """Emulate a guest-backend profile run: coordinator and worker VMs keep frames."""
        job = fixture(hashlib.sha256(name.encode()).digest(), DEFAULT_BUDGET)
        run_dir = Path(self.tmp.name) / name
        frames = run_dir / "frames"
        for role in montecarlo.PROFILE_ROLES:
            (frames / role).mkdir(parents=True)
        inject = Injection(fault, slot, loss) if fault in montecarlo.DROPS else None
        exits, closed = [], []

        def exchange(worker, raw):
            wire = general_vm.wire_name(raw)
            for role in ("A", worker):
                (frames / role / f"{wire}-request.cbor").write_bytes(raw)
            request = c.decode(raw)
            if inject is not None and inject.matches(request):
                if fault == "no_reply":
                    withheld = handle(raw, self.executor)
                    (frames / worker / f"{wire}-response.cbor").write_bytes(withheld)
                    inject.hit(request, raw, worker, withheld)
                else:
                    inject.hit(request, raw, worker)
                event = {"role": worker, "slot": request["slot"], "attempt": request["attempt"]}
                if fault == "worker_exit":
                    exits.append(dict(event, exit_status=general_vm.WORKER_EXIT_CODE))
                elif fault == "tcp_disconnect":
                    closed.append(dict(event, event="closed"))
                raise ConnectionError("injected")
            response = handle(raw, self.executor)
            for role in ("A", worker):
                (frames / role / f"{wire}-response.cbor").write_bytes(response)
            return response

        workers = montecarlo.PROFILE_WORKERS
        general_vm.run(job, montecarlo.PROFILE_ROLES, run_dir / "journal.cbor", exchange,
                       order=montecarlo.ORDER,
                       placement=general_vm.coordinator_only(workers, len(job.tasks)),
                       retry_worker=general_vm.retry_after(workers))
        spec = {"fault": fault, "slot": slot, "attempt": 1, "loss": loss, "topology": "t1"}
        (run_dir / "fault.cbor").write_bytes(c.encode(
            dict(spec, injections=inject.hits if inject is not None else [])))
        timed = [{"event": f"injected_{row['mode']}", "role": row["role"],
                  "frame_sha256": row["request_sha256"], "observed_at": "2026-11-16T10:00:05+00:00"}
                 for row in (inject.hits if inject is not None else [])]
        timed += [{"event": f"worker_exit_{row['exit_status']}", "role": row["role"],
                   "frame_sha256": None, "observed_at": "2026-11-16T10:00:05+00:00"} for row in exits]
        (run_dir / "metadata.json").write_text(json.dumps(
            {"guest_boot_ids": {role: f"boot-{role}" for role in montecarlo.PROFILE_ROLES},
             "worker_exits": exits, "serving_observations": closed, "observations": timed}))
        return job, spec, run_dir

    def serving(self, job, spec, run_dir):
        violations = []
        montecarlo._check_serving(job, spec, run_dir, self.executor, violations)
        return violations

    def test_profile_assignment_is_coordinator_only(self):
        self.assertEqual(montecarlo.PROFILE_VERSION, "r4-profile-v2")
        self.assertEqual([montecarlo._profile_worker(slot, 1) for slot in range(6)],
                         ["B", "C", "D", "B", "C", "D"])
        self.assertEqual([montecarlo._profile_verifier(slot) for slot in range(6)],
                         ["C", "D", "B", "C", "D", "B"])
        self.assertEqual([montecarlo._profile_worker(slot, 2) for slot in range(6)],
                         ["D", "B", "C", "D", "B", "C"])
        for slot in range(6):
            roles = {montecarlo._profile_worker(slot, 1), montecarlo._profile_verifier(slot),
                     montecarlo._profile_worker(slot, 2)}
            self.assertEqual(roles, set(montecarlo.PROFILE_WORKERS))
        root = Path(self.tmp.name) / "profile-layout"
        montecarlo.run_campaign(SEED, 16, root, self.executor, profile=True)
        for run_dir in sorted(root.glob("run-*")):
            for name in ("journal.cbor", "host.cbor"):
                if (run_dir / name).is_file():
                    events = c.decode((run_dir / name).read_bytes())
                    self.assertFalse(any(event.get("worker") == "A" or event.get("verifier") == "A"
                                         for event in events), run_dir)
        self.assertEqual(montecarlo.check_campaign(root, self.executor)["violations"], [])

    def test_assignment_check_rejects_a_coordinator_solve(self):
        root = Path(self.tmp.name) / "profile-assign"
        montecarlo.run_campaign(SEED, 16, root, self.executor, profile=True)
        run_dir = next(path for path in sorted(root.glob("run-*"))
                       if (path / "journal.cbor").is_file())
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        reserve = next(event for event in events if event["kind"] == "RESERVE")
        reserve["worker"] = "A"
        violations = []
        montecarlo._check_assignment(events, "journal", violations)
        self.assertTrue(any("went to A" in item for item in violations), violations)

    def test_serving_binding_accepts_each_drop_class(self):
        for fault, slot, loss in (("no_reply", 0, "both"), ("worker_exit", 1, "first"),
                                  ("tcp_disconnect", 2, "first")):
            job, spec, run_dir = self.guest_evidence(fault, slot, loss, f"clean-{fault}")
            self.assertEqual(self.serving(job, spec, run_dir), [], fault)

    def test_serving_binding_rejects_misplaced_or_missing_frames(self):
        # SOLVE first attempt, SOLVE retry and VERIFY each have their own branch.
        job, spec, run_dir = self.guest_evidence("no_reply", 0, "first", "misplaced")
        frames = run_dir / "frames"
        first = frames / "B" / "0-0-1-SOLVE-request.cbor"
        retry = frames / "D" / "0-0-2-SOLVE-request.cbor"
        verify = frames / "C" / "0-0-2-VERIFY-request.cbor"
        self.assertTrue(first.is_file() and retry.is_file() and verify.is_file())
        # Move each serving frame to a worker that did not serve it, then drop it
        # so only the coordinator copy remains.
        for path, target in ((first, "C"), (retry, "B"), (verify, "D")):
            moved = frames / target / path.name
            path.rename(moved)
            violations = self.serving(job, spec, run_dir)
            self.assertTrue(any(path.name.removesuffix("-request.cbor") in item
                                for item in violations), violations)
            moved.rename(path)
            path.unlink()
            violations = self.serving(job, spec, run_dir)
            self.assertTrue(violations, path)
            path.write_bytes((frames / "A" / path.name).read_bytes())
            self.assertEqual(self.serving(job, spec, run_dir), [])

    def test_no_reply_needs_the_withheld_reply_and_its_record(self):
        job, spec, run_dir = self.guest_evidence("no_reply", 0, "both", "withheld")
        withheld = run_dir / "frames" / "B" / "0-0-1-SOLVE-response.cbor"
        raw = withheld.read_bytes()
        withheld.unlink()
        self.assertTrue(any("no generated serving-side reply" in item
                            for item in self.serving(job, spec, run_dir)))
        withheld.write_bytes(raw)
        record = c.decode((run_dir / "fault.cbor").read_bytes())
        record["injections"][0]["response_sha256"] = "00" * 32
        (run_dir / "fault.cbor").write_bytes(c.encode(record))
        self.assertTrue(any("does not bind the withheld reply" in item
                            for item in self.serving(job, spec, run_dir)))
        record["injections"] = record["injections"][1:]
        (run_dir / "fault.cbor").write_bytes(c.encode(record))
        self.assertTrue(any("has no injection record" in item
                            for item in self.serving(job, spec, run_dir)))

    def test_exit_and_disconnect_must_not_generate_a_reply(self):
        for fault, slot in (("worker_exit", 1), ("tcp_disconnect", 2)):
            job, spec, run_dir = self.guest_evidence(fault, slot, "first", f"generated-{fault}")
            worker = montecarlo._profile_worker(slot, 1)
            request = run_dir / "frames" / worker / f"0-{slot}-1-SOLVE-request.cbor"
            (request.parent / f"0-{slot}-1-SOLVE-response.cbor").write_bytes(
                handle(request.read_bytes(), self.executor))
            self.assertTrue(any("has a serving-side reply" in item
                                for item in self.serving(job, spec, run_dir)), fault)

    def test_exit_and_disconnect_need_their_serving_observation(self):
        for fault, slot, key, message in (
                ("worker_exit", 1, "worker_exits", "non-zero worker process exit"),
                ("tcp_disconnect", 2, "serving_observations", "serving-side close")):
            job, spec, run_dir = self.guest_evidence(fault, slot, "first", f"observed-{fault}")
            path = run_dir / "metadata.json"
            metadata = json.loads(path.read_text())
            self.assertEqual(len(metadata[key]), 1)
            if fault == "worker_exit":
                metadata[key][0]["exit_status"] = 0
            else:
                metadata[key] = []
            path.write_text(json.dumps(metadata))
            self.assertTrue(any(message in item for item in self.serving(job, spec, run_dir)),
                            fault)

    def test_dispatched_verify_without_accept_is_rejected(self):
        job, spec, run_dir = self.guest_evidence("worker_exit", 1, "first", "stray-verify")
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        accept = next(event for event in events if event["kind"] == "ACCEPT")
        stray = dict(c.decode(accept["request"]), attempt=7)
        raw = c.encode(stray)
        name = general_vm.wire_name(raw)
        for role in ("A", accept["verifier"]):
            (run_dir / "frames" / role / f"{name}-request.cbor").write_bytes(raw)
        self.assertTrue(any("unbound frame" in item for item in self.serving(job, spec, run_dir)))

    def test_overlap_pause_must_hold_an_uncommitted_reserve(self):
        run_dir = Path(self.tmp.name) / "pending"
        (run_dir / "frames" / "B").mkdir(parents=True)
        job = fixture(hashlib.sha256(b"pending").digest(), DEFAULT_BUDGET)
        journal = Journal(job, run_dir / "unused.cbor", ())
        journal.add("START", execution=job.execution)
        request = journal.frame(1, 1, "SOLVE")
        pending = {"kind": "WRITE_REQUEST", "message": {
            "epoch": 0, "event": "RESERVE",
            "fields": {"slot": 1, "attempt": 1, "worker": "C", "request": request}}}
        violations = []
        montecarlo._check_pending_reserve(pending, run_dir, violations)
        self.assertEqual(violations, [])
        name = general_vm.wire_name(request)
        (run_dir / "frames" / "B" / f"{name}-request.cbor").write_bytes(request)
        montecarlo._check_pending_reserve(pending, run_dir, violations)
        self.assertTrue(any("was dispatched" in item for item in violations), violations)
        pending["message"]["event"] = "ACCEPT"
        violations = []
        montecarlo._check_pending_reserve(pending, run_dir, violations)
        self.assertTrue(any("not an uncommitted RESERVE" in item for item in violations))

    # PRA-156-01/03/07: run window, handoff boots, journals, backend binding, comparison.

    def window_metadata(self):
        return {
            "started_at": "2026-11-16T10:00:02+00:00", "ended_at": "2026-11-16T10:00:08+00:00",
            "locks": [
                {"host": host, "phase": "run", "state": state, "run_index": 4,
                 "observed_at": f"2026-11-16T10:00:{second:02d}+00:00"}
                for host, state, second in (("A", "held", 0), ("B", "held", 1),
                                            ("B", "released", 9), ("A", "released", 10))],
            "observations": [
                {"event": f"{phase}_{what}", "role": "A", "frame_sha256": None,
                 "observed_at": f"2026-11-16T10:00:0{second}+00:00"}
                for phase, what, second in (("before", "started", 3), ("before", "collected", 4),
                                            ("after", "started", 5), ("after", "collected", 6))],
        }

    def window(self, metadata):
        violations = []
        montecarlo._check_run_window("run-0004", 4, metadata, "dualhost",
                                     ("before", "after"), violations)
        return violations

    def test_run_window_binds_locks_to_the_run(self):
        self.assertEqual(self.window(self.window_metadata()), [])
        wrong = self.window_metadata()
        for row in wrong["locks"]:
            row["run_index"] = 99
        self.assertTrue(any("belongs to run 99" in item for item in self.window(wrong)))
        early = self.window_metadata()
        early["started_at"] = "2026-11-16T09:59:59+00:00"
        self.assertTrue(any("outside the common lock window" in item for item in self.window(early)))
        naive = self.window_metadata()
        naive["ended_at"] = "2026-11-16T10:00:08"
        self.assertTrue(any("RFC 3339" in item for item in self.window(naive)))
        outer = self.window_metadata()
        outer["locks"][1]["observed_at"] = "2026-11-16T09:59:59+00:00"
        self.assertTrue(any("not nested" in item for item in self.window(outer)))
        missing = self.window_metadata()
        missing["observations"] = missing["observations"][:2]
        self.assertTrue(any("after: phase start" in item for item in self.window(missing)))

    def test_handoff_phases_are_ordered_on_the_a_clock(self):
        swapped = self.window_metadata()
        times = {row["event"]: row["observed_at"] for row in swapped["observations"]}
        for row in swapped["observations"]:
            phase, _, what = row["event"].partition("_")
            other = "after" if phase == "before" else "before"
            row["observed_at"] = times[f"{other}_{what}"]
        self.assertTrue(any("started before the previous phase was collected" in item
                            for item in self.window(swapped)))

    def test_timed_fault_observations_match_the_records(self):
        job, spec, run_dir = self.guest_evidence("worker_exit", 1, "first", "timed-exit")
        path = run_dir / "metadata.json"
        metadata = json.loads(path.read_text())
        metadata["observations"] = [row for row in metadata["observations"]
                                    if not row["event"].startswith("worker_exit_")]
        path.write_text(json.dumps(metadata))
        self.assertTrue(any("worker-exit observations do not match" in item
                            for item in self.serving(job, spec, run_dir)))
        job, spec, run_dir = self.guest_evidence("tcp_disconnect", 2, "first", "timed-close")
        path = run_dir / "metadata.json"
        metadata = json.loads(path.read_text())
        metadata["observations"][0]["role"] = "A"
        path.write_text(json.dumps(metadata))
        self.assertTrue(any("injection observations do not match" in item
                            for item in self.serving(job, spec, run_dir)))

    def test_run_source_revision_matches_the_campaign(self):
        root = Path(self.tmp.name) / "source-revision"
        root.mkdir()
        (root / "environment.json").write_text(json.dumps({"source_revision": "a" * 40}))
        metadata = {"source_revision": "a" * 40, "source_commit": "a" * 40}
        violations = []
        montecarlo._check_run_environment("run-0004", root, metadata, "local", violations)
        self.assertFalse(any("source revision" in item for item in violations), violations)
        metadata["source_revision"] = "b" * 40
        montecarlo._check_run_environment("run-0004", root, metadata, "local", violations)
        self.assertTrue(any("source revision differs" in item for item in violations))

    def test_handoff_needs_fresh_boots_for_every_guest(self):
        before = {role: f"before-{role}" for role in montecarlo.PROFILE_ROLES}
        after = {role: f"after-{role}" for role in montecarlo.PROFILE_ROLES}
        violations = []
        montecarlo._check_handoff_boots("run-0004", {"before_guest_boot_ids": before,
                                                     "guest_boot_ids": after}, violations)
        self.assertEqual(violations, [])
        montecarlo._check_handoff_boots("run-0004", {"before_guest_boot_ids": before,
                                                     "guest_boot_ids": dict(before)}, violations)
        self.assertTrue(any("reused the old coordinator boot" in item for item in violations))

    def test_coordinated_journals_bind_host_guest_and_epochs(self):
        run_dir = Path(self.tmp.name) / "journals"
        run_dir.mkdir()
        events = [{"kind": "START", "writer_epoch": 0}, {"kind": "RESERVE", "writer_epoch": 0},
                  {"kind": "HANDOFF", "epoch": 1}, {"kind": "RESERVE", "writer_epoch": 1}]
        for name in ("host.cbor", "guest.cbor", "journal.cbor"):
            (run_dir / name).write_bytes(c.encode(events))
        violations = []
        montecarlo._check_coordinated_journals({"fault": "handoff"}, run_dir, violations)
        self.assertEqual(violations, [])
        stale = [dict(event) for event in events]
        stale[3]["writer_epoch"] = 0
        (run_dir / "host.cbor").write_bytes(c.encode(stale))
        montecarlo._check_coordinated_journals({"fault": "handoff"}, run_dir, violations)
        self.assertTrue(any("host and guest journals differ" in item for item in violations))
        self.assertTrue(any("advance exactly once" in item for item in violations))
        violations = []
        (run_dir / "host.cbor").unlink()
        montecarlo._check_coordinated_journals({"fault": "no_reply"}, run_dir, violations)
        self.assertTrue(any("missing or unreadable" in item for item in violations))

    def test_summary_backend_cannot_weaken_the_acceptance_path(self):
        root = Path(self.tmp.name) / "backend-bind"
        montecarlo.run_campaign(SEED, 16, root, self.executor, profile=True)
        self.assertEqual(montecarlo.check_campaign(root, self.executor)["violations"], [])
        bound = montecarlo.check_campaign(root, self.executor, expected_backend="dualhost")
        self.assertTrue(any("acceptance expects dualhost" in item for item in bound["violations"]))
        self.assertTrue(any("no manifest" in item for item in bound["violations"]))
        (root / "environment.json").write_text(json.dumps({"backend": "dualhost"}))
        claimed = montecarlo.check_campaign(root, self.executor)
        self.assertTrue(any("in-process declaration conflicts" in item
                            for item in claimed["violations"]), claimed["violations"])

    def test_comparison_ignores_clocks_and_boots_but_not_evidence(self):
        roots = [Path(self.tmp.name) / f"pass-{name}" for name in ("a", "b")]
        for number, root in enumerate(roots):
            run_dir = root / "run-0000"
            run_dir.mkdir(parents=True)
            (root / "schedule.cbor").write_bytes(c.encode({"seed": 1}))
            (run_dir / "fault.cbor").write_bytes(c.encode({"fault": "no_reply"}))
            metadata = dict(self.window_metadata(), fault="no_reply", final_state="NO_REPLY",
                            guest_boot_ids={"A": f"boot-{number}"})
            metadata["started_at"] = f"2026-11-16T1{number}:00:02+00:00"
            for row in metadata["locks"] + metadata["observations"]:
                row["observed_at"] = f"2026-11-16T1{number}:00:00+00:00"
            (run_dir / "metadata.json").write_text(json.dumps(metadata))
            (run_dir / "topology.json").write_text(json.dumps({"phases": [{"phase": "run", "topology": {
                "placement": {"A": "A", "B": "B"}, "lan_links": {"B": {"A": {"local": ["A-LAN", 40000 + number]}}},
                "guest_ips": {"A": "<A_GUEST_IP>", "B": "<B_GUEST_IP>"}}}]}))
            (root / "report.json").write_text(json.dumps({"run": number}))
        same, differences = montecarlo.compare_campaigns(*roots)
        self.assertTrue(same, differences)
        metadata = json.loads((roots[1] / "run-0000" / "metadata.json").read_text())
        metadata["final_state"] = "PUBLISHED"
        (roots[1] / "run-0000" / "metadata.json").write_text(json.dumps(metadata))
        (roots[1] / "run-0000" / "fault.cbor").write_bytes(c.encode({"fault": "worker_exit"}))
        same, differences = montecarlo.compare_campaigns(*roots)
        self.assertFalse(same)
        self.assertEqual(set(differences), {"evidence differs: run-0000/metadata.json",
                                            "evidence differs: run-0000/fault.cbor"})


if __name__ == "__main__":
    unittest.main()
