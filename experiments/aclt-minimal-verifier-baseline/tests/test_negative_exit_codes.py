# SPDX-License-Identifier: Apache-2.0
"""R1 section 6.3: every negative class through the `check` CLI.

Each class has an independent case that asserts a non-empty violation list, the
class-specific violation, and a non-zero exit code from `montecarlo.py check`.
Classes 2-11 mutate in-process campaigns.  Class 1 (archive manifest) and
class 12 (serving-side binding) need guest-backend evidence, so they mutate a
local-backend profile campaign synthesized from an in-process profile campaign;
that synthesized campaign is first shown to check clean with exit code 0.
"""

import contextlib
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import general_vm
import montecarlo
from general_job import Journal, c, handle

SEED = 20261115
# Seed 8's profile has a T1 run whose slot 2 loses its first reply and is budget-blocked.
PROFILE_SEED = 8
CLOCK = "2026-11-16T10:{minute:02d}:{second:02d}+00:00"


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _coordinated(job, events, executor):
    """Replay an uncoordinated journal as the coordinated run would have written it.

    Writer epochs enter accepted evidence, so dependent requests and every reply
    are regenerated from the coordinated journal state; the event sequence (slots,
    attempts, workers, verifiers, drops, handoff) stays the same.
    """
    journal = Journal(job, None, [])
    epoch = 0

    def apply(event):
        journal.apply(event)
        journal.events.append(event)

    for event in events:
        kind = event["kind"]
        if kind == "HANDOFF":
            epoch = c.uint(event["epoch"])
            apply({"kind": "HANDOFF", "epoch": epoch})
            continue
        fields = {key: value for key, value in event.items() if key != "kind"}
        if kind == "RESERVE":
            fields["request"] = journal.frame(event["slot"], event["attempt"], "SOLVE")
        elif kind == "ANSWER":
            request = journal.attempts[event["slot"], event["attempt"]]["request"]
            fields["response"] = handle(request, executor)
        elif kind == "ACCEPT":
            answer = journal.attempts[event["slot"], event["attempt"]]["answer"]
            request = journal.frame(event["slot"], event["attempt"], "VERIFY", answer)
            fields.update(request=request, response=handle(request, executor))
        apply({"kind": kind, "writer_epoch": epoch, **fields})
    return journal


def synthesize_local_campaign(source: Path, target: Path, executor: Path) -> None:
    """Rewrite an in-process profile campaign into the local guest-backend layout."""
    shutil.copytree(source, target)
    report = json.loads((target / "report.json").read_text())
    schedule = c.decode((target / "schedule.cbor").read_bytes())
    host_a = {"os": "Synthetic OS", "kernel": "synthetic", "machine": "x86_64",
              "qemu": "QEMU synthetic", "kvm": False, "python": "3", "accel": "tcg"}
    environment = dict(report["environment"], backend="local", topology="profile",
                       host_a=host_a, source_manifest_sha256="m" * 64,
                       kernel_sha256="k" * 64, initramfs_sha256="i" * 64)
    revision = environment["source_revision"]
    executor_sha = _sha(Path(executor).read_bytes())
    for spec in schedule["runs"]:
        index = spec["index"]
        run_dir = target / f"run-{index:04d}"
        profile = montecarlo.r4_profile(schedule["seed"], index)
        fault = profile["fault"]
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        if fault == "overlap":
            events = c.decode((run_dir / "guest.cbor").read_bytes())
            (run_dir / "journal.cbor").write_bytes(c.encode(events))
            checkpoint = []
        else:
            rebuilt = _coordinated(job, c.decode((run_dir / "journal.cbor").read_bytes()), executor)
            events = rebuilt.events
            for name in ("journal.cbor", "host.cbor", "guest.cbor"):
                (run_dir / name).write_bytes(c.encode(events))
            if rebuilt.final is not None:
                (run_dir / "result.cbor").write_bytes(c.encode(rebuilt.final))
            checkpoint = []
            if fault == "handoff":
                length = len(c.decode((run_dir / "checkpoint.cbor").read_bytes()))
                checkpoint = events[:length]
                (run_dir / "checkpoint.cbor").write_bytes(c.encode(checkpoint))
        phases = ([("before", events[:len(checkpoint)]), ("after", events[len(checkpoint):])]
                  if fault == "handoff" else [("", events)])
        injections, exits, closed = [], [], []
        for label, phase_events in phases:
            frames = run_dir / "frames" / label if label else run_dir / "frames"
            for role in montecarlo.PROFILE_ROLES:
                (frames / role).mkdir(parents=True, exist_ok=True)

            def put(role, name, raw):
                (frames / role / name).write_bytes(raw)

            for event in phase_events:
                if event["kind"] == "RESERVE":
                    raw, worker = event["request"], event["worker"]
                    wire = general_vm.wire_name(raw)
                    put("A", f"{wire}-request.cbor", raw)
                    put(worker, f"{wire}-request.cbor", raw)
                    outcome = next(item for item in phase_events
                                   if item["kind"] in ("ANSWER", "NO_REPLY")
                                   and (item["slot"], item["attempt"])
                                   == (event["slot"], event["attempt"]))
                    if outcome["kind"] == "ANSWER":
                        put("A", f"{wire}-response.cbor", outcome["response"])
                        put(worker, f"{wire}-response.cbor", outcome["response"])
                        continue
                    row = {"mode": fault, "slot": event["slot"], "attempt": event["attempt"],
                           "loss": profile["loss"], "role": worker,
                           "execution_id": job.execution_id.hex(), "request_sha256": _sha(raw)}
                    if fault == "no_reply":
                        withheld = handle(raw, executor)
                        put(worker, f"{wire}-response.cbor", withheld)
                        row["response_sha256"] = _sha(withheld)
                    injections.append(row)
                    where = {"role": worker, "slot": event["slot"], "attempt": event["attempt"]}
                    if fault == "worker_exit":
                        exits.append(dict(where, exit_status=general_vm.WORKER_EXIT_CODE))
                    elif fault == "tcp_disconnect":
                        closed.append(dict(where, event="closed"))
                elif event["kind"] == "ACCEPT":
                    wire = general_vm.wire_name(event["request"])
                    for role in ("A", event["verifier"]):
                        put(role, f"{wire}-request.cbor", event["request"])
                        put(role, f"{wire}-response.cbor", event["response"])
        recorded_fault = c.decode((run_dir / "fault.cbor").read_bytes())
        status = c.decode((run_dir / "status.cbor").read_bytes())
        status.setdefault("triggered", 1)
        (run_dir / "status.cbor").write_bytes(c.encode(status))
        if fault in montecarlo.DROPS:
            recorded_fault["injections"] = injections
        (run_dir / "fault.cbor").write_bytes(c.encode(recorded_fault))
        labels = ("before", "after") if fault == "handoff" else ("run",)
        observations = []
        for position, label in enumerate(labels):
            observations += [
                {"event": f"{label}_started", "role": "A", "frame_sha256": None,
                 "observed_at": CLOCK.format(minute=index, second=10 + 20 * position)},
                {"event": f"{label}_collected", "role": "A", "frame_sha256": None,
                 "observed_at": CLOCK.format(minute=index, second=20 + 20 * position)}]
        middle = CLOCK.format(minute=index, second=15)
        observations += [{"event": f"injected_{row['mode']}", "role": row["role"],
                          "frame_sha256": row["request_sha256"], "observed_at": middle}
                         for row in injections]
        observations += [{"event": f"worker_exit_{row['exit_status']}", "role": row["role"],
                          "frame_sha256": None, "observed_at": middle} for row in exits]
        placement = {role: "A" for role in montecarlo.PROFILE_ROLES}
        images = {"before": "i" * 64, "after": "j" * 64, "run": "i" * 64}
        topology = {"coordinator": "A", "placement": placement,
                    "guest_ips": {role: f"<{role}_GUEST_IP>" for role in montecarlo.PROFILE_ROLES}}
        metadata = {
            "backend": "local", "topology": profile["topology"], "seed": profile["seed"],
            "index": index, "job_id": profile["job_id"], "job_sha256": profile["job_sha256"],
            "fault": fault, "source_revision": revision, "source_commit": revision,
            "source_manifest_sha256": "m" * 64, "executor_sha256": executor_sha,
            "kernel_sha256": "k" * 64,
            "initramfs_sha256": images["after" if fault == "handoff" else "run"],
            "initial_initramfs_sha256": "i" * 64, "host_a_environment": host_a,
            "host_b_environment": None,
            "phases": [{"phase": label, "initramfs_sha256": images[label],
                        "placement": placement, "remote_roles": []} for label in labels],
            "locks": [{"host": "A", "phase": "run", "state": "held", "run_index": index,
                       "observed_at": CLOCK.format(minute=index, second=0)},
                      {"host": "A", "phase": "run", "state": "released", "run_index": index,
                       "observed_at": CLOCK.format(minute=index, second=59)}],
            "observations": observations,
            "started_at": CLOCK.format(minute=index, second=5),
            "ended_at": CLOCK.format(minute=index, second=55),
            "final_state": status["outcome"], "failure_reason": status.get("error"),
            "placement": placement, "remote_roles": [],
            "guest_boot_ids": {role: f"{index}-after-{role}" for role in montecarlo.PROFILE_ROLES},
            "before_guest_boot_ids": ({role: f"{index}-before-{role}"
                                       for role in montecarlo.PROFILE_ROLES}
                                      if fault == "handoff" else {}),
            "triggered": status["triggered"], "worker_exits": exits,
            "serving_observations": closed,
        }
        (run_dir / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True))
        (run_dir / "topology.json").write_text(json.dumps(dict(topology, phases=[
            {"phase": label, "topology": topology} for label in labels]), indent=2))
    (target / "environment.json").write_text(json.dumps(environment, indent=2, sort_keys=True))
    (target / "topology.json").write_text(json.dumps({"profile": True,
                                                       "topologies": ["t1", "t2"]}))
    report.update(backend="local", topology="profile", environment=environment)
    (target / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    montecarlo._manifest(target)


class NegativeClassExitCodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        root = Path(cls.tmp.name)
        cls.executor = montecarlo.build_executor(root / "executor")
        cls.base = root / "base"
        montecarlo.run_campaign(SEED, 10, cls.base, cls.executor)
        cls.profile = root / "profile"
        montecarlo.run_campaign(PROFILE_SEED, 16, cls.profile, cls.executor, profile=True)
        cls.local = root / "local"
        synthesize_local_campaign(cls.profile, cls.local, cls.executor)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def copy(self, source: Path, name: str) -> Path:
        target = Path(self.tmp.name) / name
        shutil.copytree(source, target)
        return target

    def cli(self, root: Path, backend: str | None = None) -> tuple[int, str]:
        argv = ["check", "--output", str(root), "--executor", str(self.executor)]
        if backend is not None:
            argv += ["--backend", backend]
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = montecarlo.main(argv)
        return code, output.getvalue()

    def assert_rejected(self, root: Path, needles, backend: str | None = None):
        """Non-empty violations, the class-specific one among them, and exit code 1."""
        violations = montecarlo.check_campaign(root, self.executor,
                                               expected_backend=backend)["violations"]
        self.assertTrue(violations)
        self.assertTrue(any(needle in item for item in violations for needle in needles),
                        violations)
        code, output = self.cli(root, backend)
        self.assertEqual(code, 1, output)
        self.assertRegex(output, r"violations=[1-9]")

    def run_dir(self, root: Path, fault: str, outcome: str | None = None):
        schedule = c.decode((root / "schedule.cbor").read_bytes())
        for spec in schedule["runs"]:
            if spec["fault"] != fault:
                continue
            run_dir = root / f"run-{spec['index']:04d}"
            status = c.decode((run_dir / "status.cbor").read_bytes())
            if outcome is None or status["outcome"] == outcome:
                return spec, run_dir
        self.skipTest(f"no {fault} run with outcome {outcome}")

    def refresh_manifest(self, root: Path) -> None:
        montecarlo._manifest(root)

    def test_baselines_check_clean_with_exit_zero(self):
        for root, backend in ((self.base, None), (self.profile, "inprocess"),
                              (self.local, "local")):
            code, output = self.cli(root, backend)
            self.assertEqual(code, 0, output)
            self.assertIn("violations=0", output)

    # Class 1: a frozen manifest or digest is tampered with.
    def test_class_01_tampered_manifest_or_frozen_digest(self):
        root = self.copy(self.local, "manifest")
        lines = (root / "manifest.sha256").read_text().splitlines()
        digest, _, name = lines[0].partition("  ")
        lines[0] = f"{'0' * len(digest)}  {name}"
        (root / "manifest.sha256").write_text("\n".join(lines) + "\n")
        self.assert_rejected(root, [f"manifest: {name} differs"], "local")

        root = self.copy(self.local, "manifest-file")
        _, run_dir = self.run_dir(root, "no_reply")
        (run_dir / "status.cbor").write_bytes((run_dir / "status.cbor").read_bytes() + b"\0")
        self.assert_rejected(root, ["status.cbor differs from the recorded digest"], "local")

        root = self.copy(self.profile, "profile-digest")
        path = root / "run-0000" / "profile.cbor"
        profile = c.decode(path.read_bytes())
        profile["job_sha256"] = "0" * 64
        path.write_bytes(c.encode(profile))
        self.assert_rejected(root, ["profile.cbor differs"])

    # Class 2: the published output is replaced.
    def test_class_02_replaced_output(self):
        root = self.copy(self.base, "output")
        _, run_dir = self.run_dir(root, "tcp_disconnect", "PUBLISHED")
        result = c.decode((run_dir / "result.cbor").read_bytes())
        result["output"] = b"\0" * len(result["output"])
        (run_dir / "result.cbor").write_bytes(c.encode(result))
        self.assert_rejected(root, ["result differs from journal final",
                                    "published output differs"])

    # Class 3: a journal prefix exceeds the budget (engine guard bypassed).
    def test_class_03_budget_prefix_exceeded(self):
        root = self.copy(self.base, "budget")
        _, run_dir = self.run_dir(root, "tcp_disconnect", "PUBLISHED")
        job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        journal = Journal(job, None, events)
        events.append({"kind": "RESERVE", "slot": 2, "attempt": 2, "worker": "A",
                       "request": journal.frame(2, 2, "SOLVE")})
        (run_dir / "journal.cbor").write_bytes(c.encode(events))
        with mock.patch.object(Journal, "apply_event", lambda self, event, recorded: None):
            self.assert_rejected(root, ["budget exceeded"])

    # Class 4: the retry-completability counterexample of R1 6.3 (T1, slot 2).
    def test_class_04_retry_completability_counterexample(self):
        root = self.copy(self.profile, "completability")
        job = None
        for index in range(8):  # T1 runs
            profile = montecarlo.r4_profile(PROFILE_SEED, index)
            run_dir = root / f"run-{index:04d}"
            status = c.decode((run_dir / "status.cbor").read_bytes())
            if status["outcome"] == "BUDGET_BLOCKED" and profile.get("slot") == 2:
                job = montecarlo._job_from_bundle((run_dir / "job.cbor").read_bytes())
                break
        self.assertIsNotNone(job, "seed 8 profile must contain the T1 slot-2 budget block")
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        self.assertEqual(events[-1]["kind"], "NO_REPLY")
        self.assertEqual((events[-1]["slot"], events[-1]["attempt"]), (2, 1))
        journal = Journal(job, None, events)
        # Dispatching the retry anyway: charged 24706 + retry cap 8242 + slot 3's
        # first cap 8232 = 41180 > 41170 must be refused before dispatch.
        events.append({"kind": "RESERVE", "slot": 2, "attempt": 2,
                       "worker": montecarlo._profile_worker(2, 2),
                       "request": journal.frame(2, 2, "SOLVE")})
        (run_dir / "journal.cbor").write_bytes(c.encode(events))
        with mock.patch.object(Journal, "apply_event", lambda self, event, recorded: None):
            self.assert_rejected(root, ["charged 24706 + reserved 0 + required 16474 > budget 41170"])

    # Class 5: a slot is accepted twice (engine guard bypassed).
    def test_class_05_repeated_accept(self):
        root = self.copy(self.base, "accept")
        _, run_dir = self.run_dir(root, "tcp_disconnect", "PUBLISHED")
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        index = next(i for i, event in enumerate(events) if event["kind"] == "ACCEPT")
        events.insert(index + 1, dict(events[index]))
        (run_dir / "journal.cbor").write_bytes(c.encode(events))
        original = Journal.apply_event

        def lenient(journal, event, recorded):
            if event["kind"] == "ACCEPT" and event.get("slot") in journal.accepted:
                return None
            return original(journal, event, recorded)

        with mock.patch.object(Journal, "apply_event", lenient):
            self.assert_rejected(root, ["accepted 2 times"])

    # Class 6: PUBLISH is missing although the complete output exists.
    def test_class_06_missing_publish(self):
        root = self.copy(self.base, "publish")
        _, run_dir = self.run_dir(root, "handoff", "PUBLISHED")
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        publish = next(i for i, event in enumerate(events) if event["kind"] == "PUBLISH")
        (run_dir / "journal.cbor").write_bytes(c.encode(events[:publish]))
        self.assert_rejected(root, ["complete output exists without PUBLISH"])

    # Class 7: a write after PUBLISH (engine guard bypassed).
    def test_class_07_write_after_publish(self):
        root = self.copy(self.base, "after-publish")
        _, run_dir = self.run_dir(root, "tcp_disconnect", "PUBLISHED")
        events = c.decode((run_dir / "journal.cbor").read_bytes())
        events.append(dict(next(event for event in events if event["kind"] == "PUBLISH")))
        (run_dir / "journal.cbor").write_bytes(c.encode(events))
        original = Journal.apply_event

        def lenient(journal, event, recorded):
            if event["kind"] == "PUBLISH" and journal.final is not None:
                return None
            return original(journal, event, recorded)

        with mock.patch.object(Journal, "apply_event", lenient):
            self.assert_rejected(root, ["more than one PUBLISH"])

    # Class 8: a PUBLISHED run lacks result.cbor.
    def test_class_08_published_run_without_result(self):
        root = self.copy(self.base, "result")
        _, run_dir = self.run_dir(root, "tcp_disconnect", "PUBLISHED")
        (run_dir / "result.cbor").unlink()
        self.assert_rejected(root, ["missing published result"])

    # Class 9: a writer epoch is missing.
    def test_class_09_missing_writer_epoch(self):
        root = self.copy(self.base, "epoch")
        _, run_dir = self.run_dir(root, "overlap")
        for name in ("host.cbor", "guest.cbor"):
            path = run_dir / name
            events = c.decode(path.read_bytes())
            del events[1]["writer_epoch"]
            path.write_bytes(c.encode(events))
        self.assert_rejected(root, ["writer_epoch", "writer epoch"])

    # Class 10: a commit without a preceding intent.
    def test_class_10_commit_without_intent(self):
        root = self.copy(self.base, "intent")
        _, run_dir = self.run_dir(root, "overlap")
        trace_path = run_dir / "trace.cbor"
        trace = montecarlo._trace_events(trace_path)
        commits = [i for i, event in enumerate(trace) if event["kind"] == "WRITE_COMMITTED"]
        commit = trace.pop(commits[0])
        trace.insert(commits[0] - 1, commit)
        trace_path.write_bytes(b"".join(len(raw).to_bytes(4, "big") + raw
                                        for raw in (c.encode(event) for event in trace)))
        self.assert_rejected(root, ["does not follow a write intent"])

    # Class 11: a commit or publication after the pause.
    def test_class_11_commit_after_pause(self):
        root = self.copy(self.base, "pause")
        _, run_dir = self.run_dir(root, "overlap")
        trace_path = run_dir / "trace.cbor"
        trace = montecarlo._trace_events(trace_path)
        pause = next(i for i, event in enumerate(trace) if event["kind"] == "PAUSED")
        assigned = next(event for event in trace if event["kind"] == "ASSIGNED")
        epoch = c.uint(assigned["epoch"])
        pending = [event for event in trace[:pause] if event.get("kind") == "WRITE_REQUEST"
                   and event.get("owner") == assigned["owner"]][-1]
        extra = {"kind": pending["message"]["event"], **pending["message"]["fields"],
                 "writer_epoch": epoch}
        for name in ("host.cbor", "guest.cbor"):
            path = run_dir / name
            events = c.decode(path.read_bytes())
            events.append(dict(extra))
            path.write_bytes(c.encode(events))
        trace.append({"kind": "WRITE_COMMITTED", "owner": assigned["owner"], "epoch": epoch,
                      "event": pending["message"]["event"]})
        trace_path.write_bytes(b"".join(len(raw).to_bytes(4, "big") + raw
                                        for raw in (c.encode(event) for event in trace)))
        self.assert_rejected(root, ["after pause"])

    # Class 12: serving-side binding fails (frames, withheld reply, records, VERIFY).
    def test_class_12_serving_binding(self):
        cases = []

        def move_first_solve(root):
            _, run_dir = self.run_dir(root, "handoff")
            frames = run_dir / "frames" / "after"
            path = next(path for path in sorted(frames.glob("[!A]/*-SOLVE-request.cbor")))
            other = next(role for role in montecarlo.PROFILE_WORKERS
                         if role != path.parent.name)
            path.rename(frames / other / path.name)
            return "unbound frame"
        cases.append(("moved-solve", move_first_solve))

        def move_retry_solve(root):
            for spec in c.decode((root / "schedule.cbor").read_bytes())["runs"]:
                run_dir = root / f"run-{spec['index']:04d}"
                retries = sorted((run_dir / "frames").glob("[!A]/*-*-2-SOLVE-request.cbor"))
                if retries:
                    path = retries[0]
                    other = next(role for role in montecarlo.PROFILE_WORKERS
                                 if role != path.parent.name)
                    path.rename(path.parent.parent / other / path.name)
                    return "unbound frame"
            self.fail("no dispatched retry in the synthesized campaign")
        cases.append(("moved-retry", move_retry_solve))

        def drop_withheld_reply(root):
            _, run_dir = self.run_dir(root, "no_reply")
            withheld = [path for path in (run_dir / "frames").glob("[!A]/*-SOLVE-response.cbor")
                        if not (run_dir / "frames" / "A" / path.name).exists()]
            self.assertTrue(withheld)
            withheld[0].unlink()
            return "no generated serving-side reply"
        cases.append(("withheld", drop_withheld_reply))

        def drop_injection_record(root):
            _, run_dir = self.run_dir(root, "tcp_disconnect")
            record = c.decode((run_dir / "fault.cbor").read_bytes())
            record["injections"] = record["injections"][1:]
            (run_dir / "fault.cbor").write_bytes(c.encode(record))
            return "has no injection record"
        cases.append(("record", drop_injection_record))

        def stray_verify(root):
            _, run_dir = self.run_dir(root, "handoff")
            events = c.decode((run_dir / "journal.cbor").read_bytes())
            accept = [event for event in events if event["kind"] == "ACCEPT"][-1]
            raw = c.encode(dict(c.decode(accept["request"]), attempt=7))
            wire = general_vm.wire_name(raw)
            for role in ("A", accept["verifier"]):
                (run_dir / "frames" / "after" / role / f"{wire}-request.cbor").write_bytes(raw)
            return "unbound frame"
        cases.append(("verify", stray_verify))

        def text_exit_status(root):
            _, run_dir = self.run_dir(root, "worker_exit")
            metadata = json.loads((run_dir / "metadata.json").read_text())
            metadata["worker_exits"][0]["exit_status"] = "seven"
            (run_dir / "metadata.json").write_text(json.dumps(metadata))
            return "non-zero worker process exit"
        cases.append(("exit-status", text_exit_status))

        for name, mutate in cases:
            with self.subTest(name):
                root = self.copy(self.local, f"serving-{name}")
                needle = mutate(root)
                self.refresh_manifest(root)
                self.assert_rejected(root, [needle], "local")


if __name__ == "__main__":
    unittest.main()
