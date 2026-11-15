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

import montecarlo
from general_job import Journal, c
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
            self.assertEqual(profile["profile_version"], "r4-profile-v1")
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


if __name__ == "__main__":
    unittest.main()
