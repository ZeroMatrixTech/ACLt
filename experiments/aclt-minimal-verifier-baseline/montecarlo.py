# SPDX-License-Identifier: Apache-2.0
"""Seeded, local, process-internal safety-layer fault injection for the minimal verifier.

The driver deliberately uses only a fixed finite schedule.  It is not a model of a
fault process and it makes no claim about a fault rate or a safety probability.  A
campaign is useful only as reproducible evidence that the selected fault classes did
not produce the forbidden outcomes in the reported runs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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

from baseline import PROBE
from coordination import Coordinator, CoordinationError, GuestJournal, serve
from general_job import INT, Job, Journal, c, handle
from general_vm import DEFAULT_BUDGET, fixture, run, standalone_probe

FAULTS = ("no_reply", "worker_exit", "tcp_disconnect", "handoff", "overlap")
DROPS = ("no_reply", "worker_exit", "tcp_disconnect")
ROLES = ("A", "B", "C")
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


def _block_rng(seed: int, block: int) -> random.Random:
    return random.Random(f"aclt-montecarlo/{seed}/{block}")


def generate_schedule(seed: int, runs: int) -> dict[str, Any]:
    """Build a deterministic schedule in which every five-run block covers all classes."""
    c.need(type(seed) is int and seed >= 0, "seed must be a non-negative integer")
    c.need(type(runs) is int and runs >= 1, "runs must be a positive integer")
    specs = []
    for index in range(runs):
        block = index // len(FAULTS)
        rng = _block_rng(seed, block)
        classes = list(FAULTS)
        rng.shuffle(classes)
        fault = classes[index % len(FAULTS)]
        nonce = hashlib.sha256(f"aclt-montecarlo/{seed}/{index}".encode()).digest()
        spec: dict[str, Any] = {
            "index": index,
            "fault": fault,
            "nonce": nonce.hex(),
            "budget": DEFAULT_BUDGET,
        }
        if fault in DROPS:
            # DEFAULT_BUDGET funds one extra 8232-gas attempt.  Slot 2 has an
            # 8242-gas cap, so its retry is intentionally budget-blocked; that
            # would test the budget path rather than the selected fault class.
            spec["slot"] = rng.choice((0, 1, 3))
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


def _worker_exit(raw: bytes) -> None:
    """A distinct OS process reads the request and exits without a reply."""
    completed = subprocess.run(
        [sys.executable, "-c", "import sys; sys.stdin.buffer.read(); sys.exit(7)"],
        input=raw, check=False, timeout=SOCKET_TIMEOUT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    c.need(completed.returncode == 7, "worker exit probe did not exit with status 7")


def _tcp_disconnect(raw: bytes) -> None:
    """Send on a loopback TCP socket whose peer immediately closes it."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)

    def closer() -> None:
        try:
            connection, _ = listener.accept()
            connection.close()
        except OSError:
            pass

    thread = threading.Thread(target=closer, daemon=True)
    thread.start()
    try:
        with socket.create_connection(listener.getsockname(), timeout=SOCKET_TIMEOUT) as client:
            client.sendall(raw)
            try:
                client.recv(1)
            except OSError:
                pass
    finally:
        listener.close()
        thread.join(timeout=5)


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
            raise ConnectionError(f"simulated {spec['fault']}")
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
        {"seed": seed, "runs": rows}, indent=2, sort_keys=True) + "\n")
    return {"root": str(root), "seed": seed, "runs": runs, "rows": rows}


def _load_journal(job: Job, path: Path) -> Journal:
    return Journal(job, path, c.decode(path.read_bytes()))


def _check_prefixes(job: Job, events: list[dict[str, Any]], label: str, violations: list[str]) -> None:
    for index in range(len(events) + 1):
        try:
            Journal(job, None, events[:index])
        except Exception as error:
            violations.append(f"{label}: invalid prefix {index}: {error}")


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


def _check_result(job: Job, journal: Journal, run_dir: Path, label: str,
                  violations: list[str]) -> None:
    result_path = run_dir / "result.cbor"
    if journal.final is None:
        if result_path.exists():
            violations.append(f"{label}: complete output exists without PUBLISH")
        return
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


def _check_drop(job: Job, spec: dict[str, Any], run_dir: Path,
                violations: list[str]) -> None:
    fault = c.decode((run_dir / "fault.cbor").read_bytes())
    status = c.decode((run_dir / "status.cbor").read_bytes())
    raw_events = c.decode((run_dir / "journal.cbor").read_bytes())
    _check_accept_slots(raw_events, "journal", violations)
    journal = _load_journal(job, run_dir / "journal.cbor")
    _check_prefixes(job, journal.events, "journal", violations)
    if fault.get("triggered", 0) < 1:
        violations.append("journal: requested fault was not triggered")
    expected = "PUBLISHED" if spec["loss"] == "first" else "NO_REPLY"
    if status["outcome"] != expected:
        violations.append(f"journal: outcome {status['outcome']} is not {expected}")
    if _count_events(journal.events, "PUBLISH") > 1:
        violations.append("journal: more than one PUBLISH")
    if _count_events(journal.events, "ACCEPT") > len(job.tasks):
        violations.append("journal: too many ACCEPT events")
    _check_result(job, journal, run_dir, "journal", violations)
    if expected == "NO_REPLY":
        if journal.final is not None:
            violations.append("journal: no-reply run published")
        if (run_dir / "result.cbor").exists():
            violations.append("journal: no-reply run retained a complete output")


def _check_handoff(job: Job, spec: dict[str, Any], run_dir: Path,
                   violations: list[str]) -> None:
    status = c.decode((run_dir / "status.cbor").read_bytes())
    fault = c.decode((run_dir / "fault.cbor").read_bytes())
    if status["outcome"] != "PUBLISHED":
        violations.append(f"handoff: outcome {status['outcome']} is not PUBLISHED")
    if fault.get("triggered") != 1:
        violations.append("handoff: fault was not triggered exactly once")
    checkpoint = _load_journal(job, run_dir / "checkpoint.cbor")
    journal = _load_journal(job, run_dir / "journal.cbor")
    _check_accept_slots(journal.events, "handoff", violations)
    if checkpoint.final is not None:
        violations.append("handoff: checkpoint already published")
    if _count_events(checkpoint.events, "PUBLISH"):
        violations.append("handoff: checkpoint contains PUBLISH")
    if journal.events[:len(checkpoint.events)] != checkpoint.events:
        violations.append("handoff: successor changed retained history")
    if _count_events(journal.events, "HANDOFF") != 1:
        violations.append("handoff: expected exactly one HANDOFF")
    if _count_events(journal.events, "PUBLISH") > 1:
        violations.append("handoff: more than one PUBLISH")
    if _count_events(journal.events, "ACCEPT") > len(job.tasks):
        violations.append("handoff: too many ACCEPT events")
    _check_prefixes(job, journal.events, "handoff", violations)
    _check_result(job, journal, run_dir, "handoff", violations)


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
    fault = c.decode((run_dir / "fault.cbor").read_bytes())
    host = _load_journal(job, run_dir / "host.cbor")
    guest = _load_journal(job, run_dir / "guest.cbor")
    _check_accept_slots(host.events, "overlap-host", violations)
    _check_accept_slots(guest.events, "overlap-guest", violations)
    if status["outcome"] != "PAUSED":
        violations.append(f"overlap: outcome {status['outcome']} is not PAUSED")
    if not status.get("paused"):
        violations.append("overlap: coordinator did not pause")
    if fault.get("intents", 0) < spec["overlap_after"]:
        violations.append("overlap: conflicting intent was not reached")
    if host.final is not None or guest.final is not None:
        violations.append("overlap: paused run published")
    if _count_events(host.events, "PUBLISH") or _count_events(guest.events, "PUBLISH"):
        violations.append("overlap: PUBLISH appeared after pause")
    if host.events != guest.events:
        violations.append("overlap: host and guest journals differ")
    if (run_dir / "result.cbor").exists():
        violations.append("overlap: paused run retained a complete output")
    trace = _trace_events(run_dir / "trace.cbor")
    if not any(event.get("kind") == "PAUSED" for event in trace):
        violations.append("overlap: trace has no PAUSED record")
    _check_prefixes(job, host.events, "overlap-host", violations)


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
    if fault in DROPS:
        _check_drop(job, spec, run_dir, violations)
    elif fault == "handoff":
        _check_handoff(job, spec, run_dir, violations)
    elif fault == "overlap":
        _check_overlap(job, spec, run_dir, violations)
    else:
        violations.append(f"unknown fault class {fault}")
    return violations


def check_campaign(root: Path) -> dict[str, Any]:
    """Replay every run and check the safety-layer invariants without trusting the driver."""
    root = Path(root)
    violations: list[str] = []
    try:
        schedule = c.decode((root / "schedule.cbor").read_bytes())
        specs = schedule["runs"]
        seed = schedule["seed"]
        rebuilt = generate_schedule(seed, len(specs))
        c.need(c.encode(schedule) == c.encode(rebuilt),
               "schedule differs from the seeded generator")
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

    args = parser.parse_args(argv)
    if args.command == "check":
        result = check_campaign(args.output)
        reproducible = None
        if args.compare is not None:
            reproducible, differences = compare_campaigns(args.output, args.compare)
            result["violations"].extend(differences)
        print(format_report(result, reproducible))
        return 0 if not result["violations"] else 1

    if args.executor is not None:
        executor = args.executor
        run_campaign(args.seed, args.runs, args.output, executor)
        result = check_campaign(args.output)
        print(format_report(result))
        return 0 if not result["violations"] else 1
    with tempfile.TemporaryDirectory(prefix="aclt-montecarlo-executor-") as temporary:
        executor = build_executor(Path(temporary) / "executor")
        run_campaign(args.seed, args.runs, args.output, executor)
        result = check_campaign(args.output)
    print(format_report(result))
    return 0 if not result["violations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
