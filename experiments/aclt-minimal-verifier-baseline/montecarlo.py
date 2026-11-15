# SPDX-License-Identifier: Apache-2.0
"""Seeded, local, process-internal safety-layer fault injection for the minimal verifier.

The driver deliberately uses only a fixed finite schedule.  It is not a model of a
fault process and it makes no claim about a fault rate or a safety probability.  A
campaign is useful only as reproducible evidence that the selected fault classes did
not produce the forbidden outcomes in the reported runs.

The no_reply, worker_exit, and tcp_disconnect classes are injected at the peer
exchange boundary.  worker_exit and tcp_disconnect use real loopback S2 frames;
no_reply omits the reply.  They do not exercise the full guest_multivm remote path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import random
import socket
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Any

from baseline import PROBE, ROOT
from coordination import Coordinator, CoordinationError, GuestJournal, serve
from general_job import INT, Job, Journal, c, handle, response_for
from general_vm import DEFAULT_BUDGET, fixture, run, standalone_probe
from lan import decode_answer
from tools.formal_migration.s2_transport import receive as s2_receive, send as s2_send

FAULTS = ("no_reply", "worker_exit", "tcp_disconnect", "handoff", "overlap")
DROPS = ("no_reply", "worker_exit", "tcp_disconnect")
ROLES = ("A", "B", "C")
ORDER = (0, 1, 2, 3)
DEFAULT_SEED = 20261115
DEFAULT_RUNS = 32
SOCKET_TIMEOUT = 15


def build_executor(destination: Path) -> Path:
    """Build the independent Rust executor used by the in-process peers."""
    source = PROBE / "src/independent_executor.rs"
    destination = Path(destination)
    subprocess.run(
        [os.environ.get("RUSTC") or "rustc", "--edition=2021", "-D", "warnings",
         "-C", "overflow-checks=yes", "-O", str(source), "-o", str(destination)],
        check=True, timeout=90, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    return destination


def _git(*args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def _environment(executor: Path | None = None) -> dict[str, Any]:
    """Describe the source, toolchain, and executor that produced a campaign."""
    rustc = os.environ.get("RUSTC") or "rustc"
    try:
        completed = subprocess.run(
            [rustc, "--version"], capture_output=True, text=True, check=False, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        completed = None
    revision = _git("rev-parse", "HEAD")
    status = _git("status", "--porcelain")
    return {
        "source_revision": revision or "unavailable",
        "source_dirty": bool(status),
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
        },
        "rustc": (completed.stdout.strip()
                  if completed is not None and completed.returncode == 0 else "unavailable"),
        "executor_sha256": (hashlib.sha256(Path(executor).read_bytes()).hexdigest()
                            if executor is not None else None),
    }


def _block_rng(seed: int, block: int) -> random.Random:
    """Return the RNG that chooses the class order for one five-run block."""
    return random.Random(f"aclt-montecarlo/{seed}/{block}/classes")


def _parameter_rng(seed: int, index: int) -> random.Random:
    """Return an independent RNG for one run's fault parameters."""
    return random.Random(f"aclt-montecarlo/{seed}/{index}/parameters")


def generate_schedule(seed: int, runs: int) -> dict[str, Any]:
    """Build a deterministic schedule in which every five-run block covers all classes."""
    c.need(type(seed) is int and seed >= 0, "seed must be a non-negative integer")
    c.need(type(runs) is int and runs >= 1, "runs must be a positive integer")
    specs = []
    for index in range(runs):
        block = index // len(FAULTS)
        classes = list(FAULTS)
        _block_rng(seed, block).shuffle(classes)
        fault = classes[index % len(FAULTS)]
        rng = _parameter_rng(seed, index)
        nonce = hashlib.sha256(f"aclt-montecarlo/{seed}/{index}".encode()).digest()
        spec: dict[str, Any] = {
            "index": index,
            "fault": fault,
            "nonce": nonce.hex(),
            "budget": DEFAULT_BUDGET,
        }
        if fault in DROPS:
            spec["slot"] = rng.choice(ORDER)
            spec["attempt"] = 1
            spec["loss"] = rng.choice(("first", "both"))
        elif fault == "handoff":
            spec["checkpoint"] = rng.choice((1, 2))
        else:
            spec["overlap_after"] = 5
        specs.append(spec)
    return {"version": 1, "seed": seed, "runs": specs}


def _job_bundle(job: Job) -> bytes:
    return c.encode({
        "declaration": job.declaration,
        "plan": job.plan,
        "execution": job.execution,
        "artifacts": job.artifacts,
    })


def _job_from_bundle(raw: bytes) -> Job:
    value = c.decode(raw)
    return Job(value["declaration"], value["plan"], value["execution"], value["artifacts"])


def _write_status(run_dir: Path, spec: dict[str, Any], outcome: str, **extra: Any) -> None:
    row = {"fault": spec["fault"], "outcome": outcome, **extra}
    (run_dir / "status.cbor").write_bytes(c.encode(row))


def _write_fault(run_dir: Path, spec: dict[str, Any], **extra: Any) -> None:
    row = {"fault": spec["fault"], **{key: value for key, value in spec.items()
                                         if key not in ("nonce", "budget", "index")}, **extra}
    (run_dir / "fault.cbor").write_bytes(c.encode(row))


def _write_result(run_dir: Path, final: dict[str, Any] | None) -> None:
    if final is not None:
        (run_dir / "result.cbor").write_bytes(c.encode(final))


def _spawn_idle() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-c", "import signal; signal.pause()"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


_WORKER_EXIT_SCRIPT = """
import socket
import sys
from tools.formal_migration.s2_transport import receive
client = socket.create_connection((sys.argv[1], int(sys.argv[2])), timeout=15)
receive(client)
client.close()
sys.exit(7)
"""


def _worker_exit(raw: bytes) -> None:
    """Send one S2 frame to a real worker that reads it and exits with status 7."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(SOCKET_TIMEOUT)
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT) + (
        os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    process = subprocess.Popen(
        [sys.executable, "-c", _WORKER_EXIT_SCRIPT, "127.0.0.1",
         str(listener.getsockname()[1])],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        env=environment,
    )
    error: OSError | None = None
    try:
        with listener:
            connection, _ = listener.accept()
            with connection:
                connection.settimeout(SOCKET_TIMEOUT)
                s2_send(connection, raw)
                try:
                    s2_receive(connection)
                except OSError as exc:
                    error = exc
    finally:
        try:
            process.wait(timeout=SOCKET_TIMEOUT)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
    c.need(process.returncode == 7, "worker exit probe did not exit with status 7")
    c.need(error is not None, "worker exit probe returned a reply")
    raise error


def _tcp_disconnect(raw: bytes) -> None:
    """Send one real S2 frame over a loopback connection whose peer closes it."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    listener.settimeout(SOCKET_TIMEOUT)

    def closer() -> None:
        try:
            connection, _ = listener.accept()
            connection.close()
        except OSError:
            pass

    thread = threading.Thread(target=closer, daemon=True)
    thread.start()
    error: OSError | None = None
    try:
        with socket.create_connection(listener.getsockname(), timeout=SOCKET_TIMEOUT) as client:
            client.settimeout(SOCKET_TIMEOUT)
            try:
                s2_send(client, raw)
                s2_receive(client)
            except OSError as exc:
                error = exc
    finally:
        listener.close()
        thread.join(timeout=5)
    c.need(error is not None, "tcp disconnect probe returned a reply")
    raise error


def _should_drop(raw: bytes, spec: dict[str, Any]) -> bool:
    request = c.decode(raw)
    if request.get("action") != "SOLVE" or request.get("slot") != spec["slot"]:
        return False
    attempt = request.get("attempt")
    if spec["loss"] == "first":
        return attempt == 1
    return attempt in (1, 2)


def _run_drop(job: Job, spec: dict[str, Any], run_dir: Path, executor: Path) -> None:
    triggered = 0

    def exchange(worker: str, raw: bytes) -> bytes:
        nonlocal triggered
        drop = _should_drop(raw, spec)
        if spec["fault"] == "no_reply":
            response = handle(raw, executor)
            if drop:
                triggered += 1
                raise ConnectionError("simulated missing reply")
            return response
        if drop:
            triggered += 1
            if spec["fault"] == "worker_exit":
                _worker_exit(raw)
            else:
                _tcp_disconnect(raw)
            raise ConnectionError("transport probe returned without a reply")
        return handle(raw, executor)

    try:
        journal, outcome = run(job, ROLES, run_dir / "journal.cbor", exchange,
                               order=(0, 1, 2, 3))
        _write_status(run_dir, spec, outcome, triggered=triggered,
                      accepted=len(journal.accepted), final=journal.final is not None)
        _write_fault(run_dir, spec, triggered=triggered)
        _write_result(run_dir, journal.final)
    except Exception as error:  # Keep the campaign inspectable; the checker records the violation.
        _write_status(run_dir, spec, "ERROR", triggered=triggered, error=repr(error))
        _write_fault(run_dir, spec, triggered=triggered)


def _run_handoff(job: Job, spec: dict[str, Any], run_dir: Path, executor: Path) -> None:
    checkpoint = spec["checkpoint"]

    def exchange(worker: str, raw: bytes) -> bytes:
        return handle(raw, executor)

    try:
        checkpoint_journal, checkpoint_outcome = run(
            job, ROLES, run_dir / "checkpoint.cbor", exchange,
            order=(0, 1, 2, 3), checkpoint=checkpoint,
        )
        if checkpoint_outcome != "CHECKPOINT":
            _write_status(run_dir, spec, "ERROR", checkpoint=checkpoint,
                          error=f"checkpoint stopped at {checkpoint_outcome}")
            _write_fault(run_dir, spec, triggered=0)
            return
        journal, outcome = run(
            job, ROLES, run_dir / "journal.cbor", exchange,
            order=(0, 1, 2, 3), previous=run_dir / "checkpoint.cbor",
        )
        _write_status(run_dir, spec, outcome, checkpoint=checkpoint,
                      checkpoint_events=len(checkpoint_journal.events),
                      accepted=len(journal.accepted), final=journal.final is not None)
        _write_fault(run_dir, spec, triggered=1)
        _write_result(run_dir, journal.final)
    except Exception as error:
        _write_status(run_dir, spec, "ERROR", checkpoint=checkpoint, error=repr(error))
        _write_fault(run_dir, spec, triggered=0)


def _run_overlap(job: Job, spec: dict[str, Any], run_dir: Path, executor: Path) -> None:
    authority = Coordinator(job, run_dir / "host.cbor", run_dir / "trace.cbor")
    owner = _spawn_idle()
    conflicting = _spawn_idle()
    host, guest = socket.socketpair()
    host.settimeout(SOCKET_TIMEOUT)
    guest.settimeout(SOCKET_TIMEOUT)
    host_reader = host.makefile("rb")
    host_writer = host.makefile("wb")
    guest_reader = guest.makefile("rb")
    guest_writer = guest.makefile("wb")
    intents = 0
    error: str | None = None
    outcome: str | None = None

    def on_intent() -> None:
        nonlocal intents
        intents += 1
        if intents == spec["overlap_after"]:
            authority.begin(conflicting, {"epoch": authority.epoch + 1,
                                          "event": "PUBLISH", "fields": {}})

    def exchange(worker: str, raw: bytes) -> bytes:
        return handle(raw, executor)

    factory = partial(GuestJournal, reader=guest_reader, writer=guest_writer)
    try:
        authority.assign(owner)
        with ThreadPoolExecutor(max_workers=1) as pool:
            serving = pool.submit(serve, authority, owner, host_reader, host_writer,
                                  on_intent=on_intent)
            try:
                _, outcome = run(job, ROLES, run_dir / "guest.cbor", exchange,
                                 order=(0, 1, 2, 3), journal_factory=factory)
            except CoordinationError as exc:
                error = str(exc)
            finally:
                try:
                    guest.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
            serving.result(timeout=SOCKET_TIMEOUT + 5)
    finally:
        _terminate(owner)
        _terminate(conflicting)
        for stream in (host_reader, host_writer, guest_reader, guest_writer):
            try:
                stream.close()
            except OSError:
                pass
        host.close()
        guest.close()

    _write_status(run_dir, spec, outcome or "PAUSED", paused=authority.paused,
                  intents=intents, error=error)
    _write_fault(run_dir, spec, triggered=1 if authority.paused else 0, intents=intents)


def _run_one(job: Job, spec: dict[str, Any], run_dir: Path, executor: Path) -> None:
    if spec["fault"] in DROPS:
        _run_drop(job, spec, run_dir, executor)
    elif spec["fault"] == "handoff":
        _run_handoff(job, spec, run_dir, executor)
    elif spec["fault"] == "overlap":
        _run_overlap(job, spec, run_dir, executor)
    else:
        raise c.CodecError(f"unknown fault class {spec['fault']}")


def run_campaign(seed: int, runs: int, root: Path, executor: Path) -> dict[str, Any]:
    """Execute one deterministic campaign and retain inspectable per-run evidence."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    c.need(not any(root.iterdir()), "campaign output directory must be empty")
    schedule = generate_schedule(seed, runs)
    environment = _environment(Path(executor))
    schedule["environment"] = environment
    (root / "schedule.cbor").write_bytes(c.encode(schedule))
    rows = []
    for spec in schedule["runs"]:
        run_dir = root / f"run-{spec['index']:04d}"
        run_dir.mkdir()
        job = fixture(bytes.fromhex(spec["nonce"]), spec["budget"])
        (run_dir / "job.cbor").write_bytes(_job_bundle(job))
        _write_fault(run_dir, spec)
        _run_one(job, spec, run_dir, Path(executor))
        status = c.decode((run_dir / "status.cbor").read_bytes())
        rows.append({"index": spec["index"], "fault": spec["fault"],
                     "outcome": status["outcome"]})
    (root / "report.json").write_text(json.dumps(
        {"seed": seed, "runs": rows, "environment": environment},
        indent=2, sort_keys=True) + "\n")
    return {"root": str(root), "seed": seed, "runs": runs, "rows": rows}


def _load_journal(job: Job, path: Path) -> Journal:
    return Journal(job, path, c.decode(path.read_bytes()))


def _check_budget(job: Job, events: list[dict[str, Any]], label: str,
                  violations: list[str]) -> None:
    """Recompute the solve budget from raw transitions without trusting Journal."""
    caps = job.caps
    budget = job.budget
    charged = 0
    reserved = 0
    attempts: dict[tuple[int, int], dict[str, Any]] = {}
    accepted: set[int] = set()

    def report(index: int, required: int) -> None:
        if charged + reserved + required > budget:
            violations.append(
                f"{label}: budget exceeded at event {index}: charged {charged} + "
                f"reserved {reserved} + required {required} > budget {budget}")

    for index, event in enumerate(events):
        kind = event.get("kind")
        if kind in ("RESERVE", "NO_REPLY", "ANSWER", "ACCEPT"):
            slot = c.uint(event["slot"])
            number = c.uint(event["attempt"])
            cap = caps[slot]
            key = (slot, number)
            if kind == "RESERVE":
                future = sum(cap for i, cap in enumerate(caps)
                             if (i, 1) not in attempts and i not in accepted)
                required = cap if number == 1 else cap + future
                report(index, required)
                reserved += cap
                attempts[key] = {"state": "RESERVED", "cap": cap,
                                 "request": event["request"]}
            elif kind == "NO_REPLY":
                if key not in attempts or attempts[key]["state"] != "RESERVED":
                    violations.append(f"{label}: no-reply without a reservation at event {index}")
                    continue
                reserved -= cap
                charged += cap
                attempts[key]["state"] = "NO_REPLY"
            elif kind == "ANSWER":
                attempt = attempts.get(key)
                if attempt is None or attempt["state"] != "RESERVED":
                    violations.append(f"{label}: answer without a reservation at event {index}")
                    continue
                answer = response_for(attempt["request"], event["response"], "answer")
                outcome = c.decode(decode_answer(answer).outcome)
                used = c.uint(outcome["gas_used"])
                if used > cap:
                    violations.append(
                        f"{label}: reported gas {used} exceeds cap {cap} at event {index}")
                attempt.update(state="ANSWER", gas_used=used)
            else:
                attempt = attempts.get(key)
                if attempt is None or attempt["state"] != "ANSWER" or slot in accepted:
                    violations.append(f"{label}: accept without an answer at event {index}")
                    continue
                reserved -= cap
                charged += attempt["gas_used"]
                accepted.add(slot)
                attempt["state"] = "ACCEPTED"
        if charged + reserved > budget:
            violations.append(
                f"{label}: budget invariant violated at event {index}: "
                f"charged {charged} + reserved {reserved} > budget {budget}")


def _expected_drop_outcome(job: Job, spec: dict[str, Any],
                           events: tuple[dict[str, Any], ...] = (),
                           ) -> tuple[str, list[tuple[int, int]], int]:
    """Derive the drop outcome from caps and recorded answer charges."""
    caps = job.caps
    budget = job.budget
    dependencies = job.dependencies
    attempts: dict[tuple[int, int], str] = {}
    accepted: set[int] = set()
    charged = 0
    reserved = 0
    drops: list[tuple[int, int]] = []
    requests: dict[tuple[int, int], bytes] = {}
    gas: dict[tuple[int, int], int] = {}
    for event in events:
        kind = event.get("kind")
        key = (c.uint(event.get("slot", 0)), c.uint(event.get("attempt", 0)))
        if kind == "RESERVE":
            requests[key] = event["request"]
        elif kind == "ANSWER" and key in requests:
            answer = response_for(requests[key], event["response"], "answer")
            outcome = c.decode(decode_answer(answer).outcome)
            gas[key] = c.uint(outcome["gas_used"])

    def ready() -> list[int]:
        return [slot for slot in ORDER if slot not in accepted
                and (slot not in dependencies or dependencies[slot] in accepted)]

    def reserve(slot: int, number: int) -> bool:
        nonlocal reserved
        cap = caps[slot]
        future = sum(cap for i, cap in enumerate(caps)
                     if (i, 1) not in attempts and i not in accepted)
        required = cap if number == 1 else cap + future
        if charged + reserved + required > budget:
            return False
        reserved += cap
        attempts[(slot, number)] = "RESERVED"
        return True

    while ready():
        slot = ready()[0]
        number = 1 if (slot, 1) not in attempts else 2
        cap = caps[slot]
        if not reserve(slot, number):
            return "BUDGET_BLOCKED", drops, len(accepted)
        drop = slot == spec["slot"] and (spec["loss"] == "both" or number == 1)
        if drop:
            drops.append((slot, number))
            reserved -= cap
            charged += cap
            attempts[(slot, number)] = "NO_REPLY"
            if number == 2:
                return "NO_REPLY", drops, len(accepted)
            continue
        reserved -= cap
        charged += gas.get((slot, number), cap)
        attempts[(slot, number)] = "ACCEPTED"
        accepted.add(slot)
    return "PUBLISHED", drops, len(accepted)


def _count_events(events: list[dict[str, Any]], kind: str) -> int:
    return sum(1 for event in events if event.get("kind") == kind)


def _check_accept_slots(events: list[dict[str, Any]], label: str,
                        violations: list[str]) -> None:
    counts: dict[Any, int] = {}
    for event in events:
        if event.get("kind") == "ACCEPT":
            slot = event.get("slot")
            counts[slot] = counts.get(slot, 0) + 1
    for slot, count in counts.items():
        if count > 1:
            violations.append(f"{label}: slot {slot} accepted {count} times")


def _last_event(journal: Journal) -> dict[str, Any] | None:
    if not journal.events:
        return None
    return journal.events[-1]


def _check_result(job: Job, journal: Journal, run_dir: Path, label: str,
                  violations: list[str], expected: str = "PUBLISHED",
                  drops: tuple[tuple[int, int], ...] = ()) -> None:
    result_path = run_dir / "result.cbor"
    last = _last_event(journal)
    if expected == "PUBLISHED":
        if journal.final is None:
            if result_path.exists():
                violations.append(f"{label}: complete output exists without PUBLISH")
            else:
                violations.append(f"{label}: missing published result (journal ends before PUBLISH)")
            return
        if last is None or last.get("kind") != "PUBLISH":
            kind = "empty journal" if last is None else str(last.get("kind"))
            violations.append(f"{label}: journal ends with {kind}, not PUBLISH")
        if not result_path.exists():
            violations.append(f"{label}: missing published result")
            return
        if result_path.read_bytes() != c.encode(journal.final):
            violations.append(f"{label}: result differs from journal final")
        reference = standalone_probe(job, job.budget)
        if reference.get("outcome") != "OK":
            violations.append(f"{label}: standalone reference did not succeed")
            return
        output = b"".join(INT.pack(value) for value in journal.final["output"])
        if output != reference["output"]:
            violations.append(f"{label}: published output differs from standalone reference")
        return
    if journal.final is not None:
        violations.append(f"{label}: {expected} run published")
    if result_path.exists():
        violations.append(f"{label}: {expected} run retained a complete output")
    if expected == "NO_REPLY":
        if not drops:
            violations.append(f"{label}: no seeded drop for a NO_REPLY run")
            return
        slot, attempt = drops[-1]
        if last is None or last.get("kind") != "NO_REPLY":
            kind = "empty journal" if last is None else str(last.get("kind"))
            violations.append(f"{label}: journal ends with {kind}, not the final NO_REPLY")
        elif (c.uint(last.get("slot")), c.uint(last.get("attempt"))) != (slot, attempt):
            violations.append(
                f"{label}: final NO_REPLY is slot {last.get('slot')} "
                f"attempt {last.get('attempt')}, not {slot}/{attempt}")
    elif expected == "BUDGET_BLOCKED":
        if not drops:
            violations.append(f"{label}: no seeded drop for a blocked run")
            return
        slot, attempt = drops[-1]
        if last is None or last.get("kind") != "NO_REPLY":
            kind = "empty journal" if last is None else str(last.get("kind"))
            violations.append(f"{label}: journal ends with {kind}, not the blocking NO_REPLY")
        elif (c.uint(last.get("slot")), c.uint(last.get("attempt"))) != (slot, attempt):
            violations.append(
                f"{label}: blocking NO_REPLY is slot {last.get('slot')} "
                f"attempt {last.get('attempt')}, not {slot}/{attempt}")
    else:
        violations.append(f"{label}: unknown terminal state {expected}")


def _check_drop(job: Job, spec: dict[str, Any], run_dir: Path,
                violations: list[str]) -> None:
    raw_events = c.decode((run_dir / "journal.cbor").read_bytes())
    _check_budget(job, raw_events, "journal", violations)
    _check_accept_slots(raw_events, "journal", violations)
    expected, drops, accepted_count = _expected_drop_outcome(job, spec, tuple(raw_events))
    actual_drops = [(c.uint(event["slot"]), c.uint(event["attempt"]))
                    for event in raw_events if event.get("kind") == "NO_REPLY"]
    if actual_drops != drops:
        violations.append(
            f"journal: no-reply events {actual_drops} do not match seeded drops {drops}")
    journal = _load_journal(job, run_dir / "journal.cbor")
    if len(journal.accepted) != accepted_count:
        violations.append(
            f"journal: accepted {len(journal.accepted)} slots but expected {accepted_count}")
    if _count_events(journal.events, "PUBLISH") > 1:
        violations.append("journal: more than one PUBLISH")
    if _count_events(journal.events, "ACCEPT") > len(job.tasks):
        violations.append("journal: too many ACCEPT events")
    _check_result(job, journal, run_dir, "journal", violations,
                  expected, tuple(drops))


def _check_handoff(job: Job, spec: dict[str, Any], run_dir: Path,
                   violations: list[str]) -> None:
    checkpoint_raw = c.decode((run_dir / "checkpoint.cbor").read_bytes())
    journal_raw = c.decode((run_dir / "journal.cbor").read_bytes())
    _check_budget(job, checkpoint_raw, "handoff-checkpoint", violations)
    _check_budget(job, journal_raw, "handoff", violations)
    _check_accept_slots(journal_raw, "handoff", violations)
    checkpoint = _load_journal(job, run_dir / "checkpoint.cbor")
    journal = _load_journal(job, run_dir / "journal.cbor")
    if len(checkpoint.accepted) != spec["checkpoint"]:
        violations.append(
            f"handoff: checkpoint accepted {len(checkpoint.accepted)} slots, "
            f"not {spec['checkpoint']}")
    if checkpoint.final is not None:
        violations.append("handoff: checkpoint already published")
    if _count_events(checkpoint.events, "PUBLISH"):
        violations.append("handoff: checkpoint contains PUBLISH")
    if journal.events[:len(checkpoint.events)] != checkpoint.events:
        violations.append("handoff: successor changed retained history")
    handoffs = [index for index, event in enumerate(journal.events)
                if event.get("kind") == "HANDOFF"]
    if handoffs != [len(checkpoint.events)]:
        violations.append(
            f"handoff: handoff records {handoffs} do not follow the checkpoint")
    if journal.epoch != checkpoint.epoch + 1:
        violations.append("handoff: successor epoch did not advance exactly once")
    if _count_events(journal.events, "PUBLISH") > 1:
        violations.append("handoff: more than one PUBLISH")
    if _count_events(journal.events, "ACCEPT") > len(job.tasks):
        violations.append("handoff: too many ACCEPT events")
    _check_result(job, journal, run_dir, "handoff", violations, "PUBLISHED")


def _trace_events(path: Path) -> list[dict[str, Any]]:
    data = path.read_bytes()
    offset = 0
    events = []
    while offset < len(data):
        if offset + 4 > len(data):
            raise c.CodecError("truncated coordination trace header")
        length = int.from_bytes(data[offset:offset + 4], "big")
        offset += 4
        if length <= 0 or offset + length > len(data):
            raise c.CodecError("truncated coordination trace frame")
        events.append(c.decode(data[offset:offset + length]))
        offset += length
    return events


def _check_overlap(job: Job, spec: dict[str, Any], run_dir: Path,
                   violations: list[str]) -> None:
    status = c.decode((run_dir / "status.cbor").read_bytes())
    host_raw = c.decode((run_dir / "host.cbor").read_bytes())
    guest_raw = c.decode((run_dir / "guest.cbor").read_bytes())
    _check_budget(job, host_raw, "overlap-host", violations)
    _check_budget(job, guest_raw, "overlap-guest", violations)
    _check_accept_slots(host_raw, "overlap-host", violations)
    _check_accept_slots(guest_raw, "overlap-guest", violations)
    host = _load_journal(job, run_dir / "host.cbor")
    guest = _load_journal(job, run_dir / "guest.cbor")
    for label, events in (("host", host_raw), ("guest", guest_raw)):
        missing = [index for index, event in enumerate(events)
                   if event.get("kind") != "HANDOFF" and "writer_epoch" not in event]
        if missing:
            violations.append(
                f"overlap: {label} journal lacks writer_epoch at events {missing}")

    trace = _trace_events(run_dir / "trace.cbor")
    assigned = [event for event in trace if event.get("kind") == "ASSIGNED"]
    pauses = [index for index, event in enumerate(trace) if event.get("kind") == "PAUSED"]
    if len(assigned) != 1:
        violations.append(f"overlap: trace has {len(assigned)} ASSIGNED records")
    if len(pauses) != 1:
        violations.append(f"overlap: trace has {len(pauses)} PAUSED records")
    if len(assigned) == 1 and len(pauses) == 1:
        active = assigned[0]["owner"]
        active_epoch = c.uint(assigned[0]["epoch"])
        paused = trace[pauses[0]]
        if paused.get("active") != active:
            violations.append("overlap: pause names a different active owner")
        if c.uint(paused.get("active_epoch", -1)) != active_epoch:
            violations.append("overlap: pause names a different active epoch")
        conflicting = paused.get("conflicting")
        if conflicting == active:
            violations.append("overlap: pause names the active owner as conflicting")
        if c.uint(paused.get("conflicting_epoch", -1)) != active_epoch + 1:
            violations.append("overlap: conflicting epoch did not advance exactly once")
        requests = [event for event in trace[:pauses[0]]
                    if event.get("kind") == "WRITE_REQUEST" and event.get("owner") == active]
        if len(requests) != spec["overlap_after"]:
            violations.append(
                f"overlap: active owner issued {len(requests)} intents, "
                f"not {spec['overlap_after']}")
        if any(c.uint(event.get("message", {}).get("epoch", -1)) != active_epoch
               for event in requests):
            violations.append("overlap: active owner intent used a different epoch")
        prior = trace[pauses[0] - 1] if pauses[0] else {}
        if prior.get("kind") != "WRITE_REQUEST" or prior.get("owner") != conflicting:
            violations.append("overlap: conflict did not immediately precede the pause")
        elif c.uint(prior.get("message", {}).get("epoch", -1)) != c.uint(
                paused.get("conflicting_epoch", -1)):
            violations.append("overlap: conflicting intent epoch does not match the pause")
        committed = [(index, event) for index, event in enumerate(trace)
                     if event.get("kind") == "WRITE_COMMITTED"]
        expected_commits = len(requests) - 1
        if len(committed) != expected_commits:
            violations.append(
                f"overlap: trace records {len(committed)} successful writes, "
                f"not {expected_commits}")
        after_pause = [index for index, _ in committed if index > pauses[0]]
        if after_pause:
            violations.append(
                f"overlap: successful write after pause at trace events {after_pause}")
        for index, event in committed:
            if event.get("owner") != active:
                violations.append(
                    f"overlap: successful write at trace event {index} has another owner")
            if c.uint(event.get("epoch", -1)) != active_epoch:
                violations.append(
                    f"overlap: successful write at trace event {index} "
                    f"does not use the active epoch")
            if index == 0 or trace[index - 1].get("kind") != "WRITE_REQUEST":
                violations.append(
                    f"overlap: successful write at trace event {index} "
                    f"does not follow a write intent")
                continue
            intent = trace[index - 1]
            if intent.get("owner") != event.get("owner"):
                violations.append(
                    f"overlap: successful write at trace event {index} "
                    f"follows another owner's intent")
            message = intent.get("message", {})
            if message.get("event") != event.get("event"):
                violations.append(
                    f"overlap: successful write at trace event {index} "
                    f"follows a different write intent")
            if c.uint(message.get("epoch", -1)) != c.uint(event.get("epoch", -1)):
                violations.append(
                    f"overlap: successful write at trace event {index} "
                    f"follows an intent for a different epoch")
        if len(committed) != len(host.events):
            violations.append(
                f"overlap: {len(committed)} successful writes but "
                f"{len(host.events)} journal events")
        else:
            for position, (commit, recorded) in enumerate(zip(committed, host.events)):
                index, event = commit
                if event.get("event") != recorded.get("kind"):
                    violations.append(
                        f"overlap: successful write {position} is {event.get('event')}, "
                        f"not {recorded.get('kind')}")
                if event.get("epoch") != recorded.get("writer_epoch"):
                    violations.append(
                        f"overlap: successful write {position} used a different epoch")
    if status["outcome"] != "PAUSED":
        violations.append(f"overlap: outcome {status['outcome']} is not PAUSED")
    if not status.get("paused"):
        violations.append("overlap: coordinator did not pause")
    if status.get("error") != "overlapping coordinator epochs":
        violations.append("overlap: pause was not caused by overlapping epochs")
    if host.final is not None or guest.final is not None:
        violations.append("overlap: paused run published")
    if _count_events(host.events, "PUBLISH") or _count_events(guest.events, "PUBLISH"):
        violations.append("overlap: PUBLISH appeared after pause")
    if host.events != guest.events:
        violations.append("overlap: host and guest journals differ")
    if (run_dir / "result.cbor").exists():
        violations.append("overlap: paused run retained a complete output")


def _check_run(spec: dict[str, Any], run_dir: Path) -> list[str]:
    violations: list[str] = []
    for name in ("job.cbor", "status.cbor", "fault.cbor"):
        if not (run_dir / name).exists():
            violations.append(f"missing {name}")
    if violations:
        return violations
    raw = (run_dir / "job.cbor").read_bytes()
    expected = _job_bundle(fixture(bytes.fromhex(spec["nonce"]), spec["budget"]))
    if raw != expected:
        return ["job differs from the seeded schedule"]
    job = _job_from_bundle(raw)
    fault = spec["fault"]
    try:
        if fault in DROPS:
            _check_drop(job, spec, run_dir, violations)
        elif fault == "handoff":
            _check_handoff(job, spec, run_dir, violations)
        elif fault == "overlap":
            _check_overlap(job, spec, run_dir, violations)
        else:
            violations.append(f"unknown fault class {fault}")
    except Exception as error:
        violations.append(f"{fault}: {error}")
    return violations


def _check_environment(schedule: dict[str, Any], report: dict[str, Any],
                      executor: Path | None, violations: list[str]) -> None:
    recorded = schedule.get("environment")
    if type(recorded) is not dict:
        violations.append("environment: schedule has no environment record")
        return
    if report.get("environment") != recorded:
        violations.append("environment: report and schedule records differ")
    current = _environment(executor)
    if recorded.get("python") != current["python"]:
        violations.append(
            f"environment: Python {current['python']} differs from recorded "
            f"{recorded.get('python')}")
    if recorded.get("rustc") != current["rustc"]:
        violations.append(
            f"environment: rustc {current['rustc']} differs from recorded "
            f"{recorded.get('rustc')}")
    if executor is not None and recorded.get("executor_sha256") != current["executor_sha256"]:
        violations.append("environment: executor digest differs from the recorded executor")
    if not isinstance(recorded.get("source_revision"), str):
        violations.append("environment: source revision is not recorded")


def check_campaign(root: Path, executor: Path | None = None) -> dict[str, Any]:
    """Replay every run and check the safety-layer invariants without trusting the driver."""
    root = Path(root)
    violations: list[str] = []
    try:
        schedule = c.decode((root / "schedule.cbor").read_bytes())
        specs = schedule["runs"]
        seed = schedule["seed"]
        rebuilt = generate_schedule(seed, len(specs))
        for key in ("version", "seed", "runs"):
            c.need(schedule.get(key) == rebuilt.get(key),
                   f"schedule {key} differs from the seeded generator")
        report = json.loads((root / "report.json").read_text())
        c.need(type(report) is dict, "report is not an object")
        _check_environment(schedule, report, executor, violations)
    except Exception as error:
        return {"runs": 0, "seed": None, "violations": [f"schedule: {error}"]}
    for spec in specs:
        run_dir = root / f"run-{spec['index']:04d}"
        if not run_dir.is_dir():
            violations.append(f"run-{spec['index']:04d}: missing directory")
            continue
        try:
            violations.extend(_check_run(spec, run_dir))
        except Exception as error:
            violations.append(f"run-{spec['index']:04d}: {error}")
    return {"runs": len(specs), "seed": seed, "violations": violations}


def _evidence_hashes(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative in ("report.json",) or relative.endswith("trace.cbor"):
            continue
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def compare_campaigns(first: Path, second: Path) -> tuple[bool, list[str]]:
    """Compare the deterministic evidence of two independent campaigns."""
    first, second = Path(first), Path(second)
    differences = []
    try:
        if (first / "schedule.cbor").read_bytes() != (second / "schedule.cbor").read_bytes():
            differences.append("schedule differs")
    except OSError as error:
        return False, [f"schedule comparison failed: {error}"]
    left, right = _evidence_hashes(first), _evidence_hashes(second)
    for name in sorted(set(left) | set(right)):
        if left.get(name) != right.get(name):
            differences.append(f"evidence differs: {name}")
    return not differences, differences


def format_report(result: dict[str, Any], reproducible: bool | None = None) -> str:
    suffix = "" if reproducible is None else \
        f" reproducible={'yes' if reproducible else 'no'}"
    return (f"runs={result['runs']} seed={result['seed']} "
            f"violations={len(result['violations'])}{suffix}")


def run_crash_probe(root: Path) -> dict[str, Any]:
    """Test-only probe: a new assignment after an in-flight owner crash must fail closed."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    job = fixture(hashlib.sha256(b"aclt-montecarlo/crash").digest(), DEFAULT_BUDGET)
    (root / "job.cbor").write_bytes(_job_bundle(job))
    authority = Coordinator(job, root / "crash.cbor", root / "trace.cbor")
    owner = _spawn_idle()
    successor = _spawn_idle()
    error: str | None = None
    try:
        authority.assign(owner)

        def commit(event: str, fields: dict[str, Any]) -> None:
            message = {"epoch": authority.epoch, "event": event, "fields": fields}
            authority.begin(owner, message)
            authority.commit(owner)

        commit("START", {"execution": job.execution})
        commit("RESERVE", {
            "slot": 0, "attempt": 1, "worker": "A",
            "request": authority.journal.frame(0, 1, "SOLVE"),
        })
        _terminate(owner)
        try:
            authority.assign(successor)
        except c.CodecError as exc:
            error = str(exc)
        else:
            error = "successor assignment unexpectedly succeeded"
    finally:
        _terminate(owner)
        _terminate(successor)
    passed = (error == "handoff needs a quiescent journal"
              and authority.journal.final is None
              and _count_events(authority.journal.events, "PUBLISH") == 0)
    (root / "status.cbor").write_bytes(c.encode({
        "fault": "crash", "outcome": "CRASH_FAIL_CLOSED" if passed else "UNEXPECTED",
        "error": error, "paused": authority.paused,
        "final": authority.journal.final is not None,
    }))
    (root / "fault.cbor").write_bytes(c.encode({"fault": "crash", "triggered": 1}))
    return {"outcome": "CRASH_FAIL_CLOSED" if passed else "UNEXPECTED", "error": error}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="execute one seeded campaign")
    run_parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    run_parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    run_parser.add_argument("--output", type=Path, required=True)
    run_parser.add_argument("--executor", type=Path)

    check_parser = subparsers.add_parser("check", help="replay and check one campaign")
    check_parser.add_argument("--output", type=Path, required=True)
    check_parser.add_argument("--compare", type=Path)
    check_parser.add_argument("--executor", type=Path)

    args = parser.parse_args(argv)
    if args.command == "check":
        result = check_campaign(args.output, args.executor)
        reproducible = None
        if args.compare is not None:
            second = check_campaign(args.compare, args.executor)
            result["violations"].extend(
                f"compare campaign: {item}" for item in second["violations"])
            reproducible, differences = compare_campaigns(args.output, args.compare)
            result["violations"].extend(differences)
            if result["violations"]:
                reproducible = False
        print(format_report(result, reproducible))
        return 0 if not result["violations"] else 1

    if args.executor is not None:
        executor = args.executor
        run_campaign(args.seed, args.runs, args.output, executor)
        result = check_campaign(args.output, executor)
        print(format_report(result))
        return 0 if not result["violations"] else 1
    with tempfile.TemporaryDirectory(prefix="aclt-montecarlo-executor-") as temporary:
        executor = build_executor(Path(temporary) / "executor")
        run_campaign(args.seed, args.runs, args.output, executor)
        result = check_campaign(args.output, executor)
    print(format_report(result))
    return 0 if not result["violations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())