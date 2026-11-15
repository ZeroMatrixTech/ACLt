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
import shutil
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
import dualhost_multivm
from coordination import Coordinator, CoordinationError, GuestJournal, serve
from general_job import INT, Job, Journal, c, handle, response_for
import general_vm
from general_vm import DEFAULT_BUDGET, DEFAULT_BUDGET_SIX, fixture, run, standalone_probe
from multivm_job import assignments
from lan import decode_answer
from tools.formal_migration.s2_transport import receive as s2_receive, send as s2_send

FAULTS = ("no_reply", "worker_exit", "tcp_disconnect", "handoff", "overlap")
DROPS = ("no_reply", "worker_exit", "tcp_disconnect")
ROLES = ("A", "B", "C")
ROLES_SIX = ("A", "B", "C", "D")
ORDER = (0, 1, 2, 3)
ORDER_SIX = (0, 1, 2, 3, 4, 5)
TOPOLOGIES = {
    "t1": {"guests": 3, "leaves": 4, "roles": ROLES, "order": ORDER,
           "budget": DEFAULT_BUDGET},
    "t2": {"guests": 4, "leaves": 6, "roles": ROLES_SIX, "order": ORDER_SIX,
           "budget": DEFAULT_BUDGET_SIX},
}
BACKENDS = ("inprocess", "local", "dualhost")
DEFAULT_SEED = 20261115
DEFAULT_RUNS = 32
SOCKET_TIMEOUT = 15


def build_executor(destination: Path, *, static: bool = False) -> Path:
    """Build the independent Rust executor used by the in-process peers.

    The cross-host harness compiles a statically linked executor from the same source,
    so a static build keeps the campaign environment digest comparable with the guest.
    """
    source = PROBE / "src/independent_executor.rs"
    destination = Path(destination)
    options = ["-C", "target-feature=+crt-static"] if static else []
    subprocess.run(
        [os.environ.get("RUSTC") or "rustc", "--edition=2021", "-D", "warnings",
         "-C", "overflow-checks=yes", "-O", *options, str(source), "-o", str(destination)],
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


def generate_schedule(seed: int, runs: int, *, topology: str = "t1") -> dict[str, Any]:
    """Build a deterministic schedule in which every five-run block covers all classes."""
    c.need(type(seed) is int and seed >= 0, "seed must be a non-negative integer")
    c.need(type(runs) is int and runs >= 1, "runs must be a positive integer")
    c.need(topology in TOPOLOGIES, f"unknown topology {topology}")
    shape = TOPOLOGIES[topology]
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
            "budget": shape["budget"],
        }
        if fault in DROPS:
            spec["slot"] = rng.choice(shape["order"])
            spec["attempt"] = 1
            spec["loss"] = rng.choice(("first", "both"))
        elif fault == "handoff":
            spec["checkpoint"] = rng.choice((1, 2))
        else:
            spec["overlap_after"] = 5
        specs.append(spec)
    schedule = {"version": 1, "seed": seed, "runs": specs}
    if topology != "t1":
        schedule["topology"] = topology
        for spec in specs:
            spec["topology"] = topology
    return schedule


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


def _run_drop(job: Job, spec: dict[str, Any], run_dir: Path, executor: Path, *,
              roles: tuple[str, ...] = ROLES, order: tuple[int, ...] = ORDER) -> None:
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
        journal, outcome = run(job, roles, run_dir / "journal.cbor", exchange, order=order)
        _write_status(run_dir, spec, outcome, triggered=triggered,
                      accepted=len(journal.accepted), final=journal.final is not None)
        _write_fault(run_dir, spec, triggered=triggered)
        _write_result(run_dir, journal.final)
    except Exception as error:  # Keep the campaign inspectable; the checker records the violation.
        _write_status(run_dir, spec, "ERROR", triggered=triggered, error=repr(error))
        _write_fault(run_dir, spec, triggered=triggered)


def _run_handoff(job: Job, spec: dict[str, Any], run_dir: Path, executor: Path, *,
                 roles: tuple[str, ...] = ROLES, order: tuple[int, ...] = ORDER) -> None:
    checkpoint = spec["checkpoint"]

    def exchange(worker: str, raw: bytes) -> bytes:
        return handle(raw, executor)

    try:
        checkpoint_journal, checkpoint_outcome = run(
            job, roles, run_dir / "checkpoint.cbor", exchange,
            order=order, checkpoint=checkpoint,
        )
        if checkpoint_outcome != "CHECKPOINT":
            _write_status(run_dir, spec, "ERROR", checkpoint=checkpoint,
                          error=f"checkpoint stopped at {checkpoint_outcome}")
            _write_fault(run_dir, spec, triggered=0)
            return
        journal, outcome = run(
            job, roles, run_dir / "journal.cbor", exchange,
            order=order, previous=run_dir / "checkpoint.cbor",
        )
        _write_status(run_dir, spec, outcome, checkpoint=checkpoint,
                      checkpoint_events=len(checkpoint_journal.events),
                      accepted=len(journal.accepted), final=journal.final is not None)
        _write_fault(run_dir, spec, triggered=1)
        _write_result(run_dir, journal.final)
    except Exception as error:
        _write_status(run_dir, spec, "ERROR", checkpoint=checkpoint, error=repr(error))
        _write_fault(run_dir, spec, triggered=0)


def _run_overlap(job: Job, spec: dict[str, Any], run_dir: Path, executor: Path, *,
                 roles: tuple[str, ...] = ROLES, order: tuple[int, ...] = ORDER) -> None:
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
                _, outcome = run(job, roles, run_dir / "guest.cbor", exchange,
                                 order=order, journal_factory=factory)
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


def _run_one(job: Job, spec: dict[str, Any], run_dir: Path, executor: Path, *,
             topology: str = "t1") -> None:
    shape = TOPOLOGIES[topology]
    roles, order = shape["roles"], shape["order"]
    if spec["fault"] in DROPS:
        _run_drop(job, spec, run_dir, executor, roles=roles, order=order)
    elif spec["fault"] == "handoff":
        _run_handoff(job, spec, run_dir, executor, roles=roles, order=order)
    elif spec["fault"] == "overlap":
        _run_overlap(job, spec, run_dir, executor, roles=roles, order=order)
    else:
        raise c.CodecError(f"unknown fault class {spec['fault']}")


def _topology_for(spec: dict[str, Any], default: str) -> str:
    return spec.get("topology", default)


def _phase_root(raw: Path, phase: str = "") -> Path:
    root = raw / phase if phase else raw
    return root / "A" / "A"


def _copy(source: Path, destination: Path) -> None:
    c.need(source.is_file(), f"missing guest evidence {source.name}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(source.read_bytes())


def _redact_topology(topology: dict[str, Any]) -> dict[str, Any]:
    """Record the observed shape without the operator's physical addresses.

    The link records hold only the fixed A-LAN/B-LAN labels and TCP ports, which
    the cross-check needs.  Guest addresses are synthesized by the QEMU user
    network, but are still replaced so that a future configuration cannot leak a
    host address through the evidence tree.
    """
    value = json.loads(json.dumps(topology))
    for role in value.get("guest_ips", {}):
        value["guest_ips"][role] = f"<{role}_GUEST_IP>"
    return value


def _normalize_guest_run(job: Job, spec: dict[str, Any], run_dir: Path, raw: Path,
                         result: dict[str, Any], *, backend: str, topology: str) -> None:
    """Turn one multivm evidence tree into the R3 checker's per-run layout."""
    fault = spec["fault"]
    handoff = fault == "handoff"
    overlap = fault == "overlap"
    phase = "after" if (raw / "after").is_dir() else ""
    root = _phase_root(raw, phase)
    journal = _load_journal(job, root / "journal.cbor")
    _copy(root / "journal.cbor", run_dir / "journal.cbor")
    guest = result.get("guests", {})
    triggered = 1 if handoff or overlap else sum(int(row.get("fault_triggered", 0))
                                                 for row in guest.values())
    worker_exits = sum(len(row.get("worker_exits", ())) for row in guest.values())
    extra: dict[str, Any] = {}
    if fault in DROPS:
        extra = {"triggered": triggered, "accepted": len(journal.accepted),
                 "final": journal.final is not None}
    elif handoff:
        before_root = _phase_root(raw, "before")
        checkpoint = _load_journal(job, before_root / "journal.cbor")
        _copy(before_root / "journal.cbor", run_dir / "checkpoint.cbor")
        extra = {"triggered": 1, "checkpoint": spec["checkpoint"],
                 "checkpoint_events": len(checkpoint.events),
                 "accepted": len(journal.accepted),
                 "final": journal.final is not None}
    else:
        _copy(raw / "host-journal.cbor", run_dir / "host.cbor")
        _copy(raw / "coordination.trace", run_dir / "trace.cbor")
        _copy(root / "journal.cbor", run_dir / "guest.cbor")
        extra = {"triggered": 1, "paused": True, "intents": spec["overlap_after"],
                 "error": "overlapping coordinator epochs"}
    outcome = "PAUSED" if overlap else result["general_status"]
    _write_status(run_dir, spec, outcome, **extra)
    _write_fault(run_dir, spec, triggered=triggered)
    if journal.final is not None:
        _copy(root / "publication.cbor", run_dir / "result.cbor")
    observed = result.get("topology", {})
    if not observed.get("placement"):
        observed = dict(observed, placement={role: "A" for role in guest})
    _copy_json(run_dir / "topology.json", _redact_topology(observed))
    frames = run_dir / "frames"
    phases = ([("before", result.get("before_guests", {})), ("after", guest)]
              if handoff else [("after", guest)] if phase else [("", guest)])
    for label, rows in phases:
        for role in rows:
            source = (raw / label / role / role) if label else (raw / role / role)
            if not source.is_dir():
                continue
            destination = frames / label / role if label else frames / role
            for path in sorted(source.glob("*-*.cbor")):
                _copy(path, destination / path.name)
    initial_image = result.get("initramfs_sha256")
    boot_image = (result.get("successor_initramfs_sha256") if handoff else None) or initial_image
    metadata = {
        "backend": backend,
        "topology": topology,
        "source_commit": result.get("commit"),
        "source_manifest_sha256": result.get("source_manifest_sha256"),
        "executor_sha256": result.get("executor_sha256"),
        "kernel_sha256": result.get("kernel_sha256"),
        "initramfs_sha256": boot_image,
        "initial_initramfs_sha256": initial_image,
        "placement": _redact_topology(observed).get("placement"),
        "remote_roles": sorted(observed.get("lan_links", {})),
        "guest_boot_ids": {role: row.get("boot_id") for role, row in guest.items()},
        "before_guest_boot_ids": ({role: row.get("boot_id")
                                   for role, row in result.get("before_guests", {}).items()}
                                  if handoff else {}),
        "triggered": triggered,
        "worker_exits": worker_exits,
    }
    _copy_json(run_dir / "metadata.json", metadata)


def _check_frames(job: Job, spec: dict[str, Any], run_dir: Path, executor: Path | None,
                  violations: list[str]) -> None:
    """Replay the retained raw frames, not just the journals derived from them."""
    frames = run_dir / "frames"
    if not frames.is_dir():
        violations.append("frames: run retained no request/response frames")
        return
    topology = spec.get("topology", "t1")
    roles = TOPOLOGIES[topology]["roles"]
    try:
        if spec["fault"] == "handoff":
            general_vm.replay(
                job, {role: frames / "before" / role for role in roles}, executor,
                journal_path=run_dir / "checkpoint.cbor")
            checkpoint = c.decode((run_dir / "checkpoint.cbor").read_bytes())
            general_vm.replay(
                job, {role: frames / "after" / role for role in roles}, executor,
                previous=checkpoint, journal_path=run_dir / "journal.cbor")
        else:
            general_vm.replay(
                job, {role: frames / role for role in roles}, executor,
                journal_path=run_dir / "journal.cbor")
    except Exception as error:
        violations.append(f"frames: {error}")


def _copy_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _run_guest(job: Job, spec: dict[str, Any], run_dir: Path, *, backend: str,
               topology: str, config: Path | None, kernel: Path, placement: str | None,
               accel: str, timeout: int, executor: Path | None = None) -> None:
    shape = TOPOLOGIES[topology]
    remote_roles = tuple(role for role in (placement or "").split(",") if role)
    roles = shape["roles"]
    if spec["fault"] in DROPS and backend == "dualhost":
        worker, _ = assignments(roles, len(job.tasks))[spec["slot"]]
        if worker not in remote_roles:
            _write_status(run_dir, spec, "ERROR",
                          error=f"injected slot {spec['slot']} is served on host A")
            _write_fault(run_dir, spec, triggered=0)
            return
    raw = run_dir / "raw"
    order = "".join(str(slot) for slot in shape["order"])
    command = [sys.executable, "-B", str(Path(__file__).with_name("multivm.py")), "run",
               "--general", "--guests", str(shape["guests"]), "--kernel", str(kernel),
               "--output", str(raw), "--solve-budget", str(spec["budget"]),
               "--general-order", order, "--general-nonce", spec["nonce"],
               "--accel", accel]
    if executor is not None:
        command += ["--executor", str(executor)]
    if topology == "t2":
        command.append("--general-six")
    if backend == "dualhost":
        c.need(config is not None and placement, "dual-host campaign needs config and placement")
        command += ["--dualhost-config", str(config), "--host-b-roles", placement]
    if spec["fault"] in DROPS:
        command += ["--general-inject",
                    f"{spec['fault']}:{spec['slot']}:{spec['loss']}"]
    elif spec["fault"] == "handoff":
        command += ["--general-checkpoint", str(spec["checkpoint"])]
    else:
        command += ["--m9", "overlap"]
    try:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True,
                                   timeout=timeout)
    except subprocess.TimeoutExpired:
        _write_status(run_dir, spec, "ERROR", error=f"guest harness exceeded {timeout}s")
        _write_fault(run_dir, spec, triggered=0)
        return
    (raw / "multivm.log").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    result_path = raw / "result.json"
    if not result_path.is_file():
        _write_status(run_dir, spec, "ERROR",
                      error=(completed.stderr.strip().splitlines() or ["guest harness failed"])[-1][:300])
        _write_fault(run_dir, spec, triggered=0)
        return
    result = json.loads(result_path.read_text())
    if backend == "dualhost":
        expected_placement = {role: "B" if role in remote_roles else "A" for role in roles}
        c.need(result.get("topology", {}).get("placement") == expected_placement,
               "guest harness recorded a different placement")
    if completed.returncode != 0:
        safe = ("BUDGET_BLOCKED", "NO_REPLY", "COORDINATION_PAUSED")
        if completed.returncode != 1 or result.get("general_status") not in safe:
            _write_status(run_dir, spec, "ERROR",
                          error=(completed.stderr.strip().splitlines() or ["guest harness failed"])[-1][:300])
            _write_fault(run_dir, spec, triggered=0)
            return
    _normalize_guest_run(job, spec, run_dir, raw, result, backend=backend, topology=topology)
    shutil.rmtree(raw, ignore_errors=True)


def _manifest(root: Path) -> None:
    """Cover every retained evidence file; only the manifest itself is excluded."""
    rows = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == "manifest.sha256":
            continue
        rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {relative}")
    (root / "manifest.sha256").write_text("\n".join(rows) + "\n", encoding="utf-8")


def run_campaign(seed: int, runs: int, root: Path, executor: Path | None = None, *,
                 backend: str = "inprocess", topology: str = "t1",
                 config: Path | None = None, kernel: Path | None = None,
                 placement: str | None = None, accel: str = "kvm",
                 timeout: int = 1800) -> dict[str, Any]:
    """Execute one deterministic campaign and retain inspectable per-run evidence."""
    c.need(backend in BACKENDS, f"unknown backend {backend}")
    c.need(topology in TOPOLOGIES, f"unknown topology {topology}")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    c.need(not any(root.iterdir()), "campaign output directory must be empty")
    if backend != "inprocess":
        c.need(kernel is not None and Path(kernel).is_file(), "cross-host campaign needs a kernel")
        if backend == "dualhost":
            c.need(config is not None, "dual-host campaign needs a placement file")
            c.need(placement, "dual-host campaign needs a B placement")
        if executor is None:
            executor = build_executor(root / "executor", static=True)
    c.need(executor is not None, "in-process campaign needs an executor")
    schedule = generate_schedule(seed, runs, topology=topology)
    environment = _environment(Path(executor))
    if backend != "inprocess":
        environment = dict(environment, backend=backend, topology=topology)
        schedule["backend"] = backend
    schedule["environment"] = environment
    (root / "schedule.cbor").write_bytes(c.encode(schedule))
    if backend != "inprocess":
        (root / "environment.json").write_text(
            json.dumps(environment, indent=2, sort_keys=True) + "\n")
    rows = []
    for spec in schedule["runs"]:
        run_dir = root / f"run-{spec['index']:04d}"
        run_dir.mkdir()
        spec_topology = _topology_for(spec, topology)
        job = fixture(bytes.fromhex(spec["nonce"]), spec["budget"],
                      six=spec_topology == "t2")
        (run_dir / "job.cbor").write_bytes(_job_bundle(job))
        _write_fault(run_dir, spec)
        if backend == "inprocess":
            _run_one(job, spec, run_dir, Path(executor), topology=spec_topology)
        else:
            _run_guest(job, spec, run_dir, backend=backend, topology=spec_topology,
                       config=config, kernel=Path(kernel), placement=placement,
                       accel=accel, timeout=timeout, executor=Path(executor))
        status = c.decode((run_dir / "status.cbor").read_bytes())
        row = {"index": spec["index"], "fault": spec["fault"], "outcome": status["outcome"]}
        if backend != "inprocess":
            row["topology"] = spec_topology
            row["triggered"] = int(status.get("triggered", 0))
        rows.append(row)
    report = {"seed": seed, "runs": rows, "environment": environment}
    if backend != "inprocess":
        report.update(backend=backend, topology=topology)
        first_spec = next((spec for spec in schedule["runs"] if spec["fault"] != "handoff"),
                          schedule["runs"][0])
        first = root / f"run-{first_spec['index']:04d}"
        if (first / "metadata.json").is_file():
            meta = json.loads((first / "metadata.json").read_text())
            topology_record = json.loads((first / "topology.json").read_text())
            topology_record.update(kernel_sha256=meta.get("kernel_sha256"),
                                   initramfs_sha256=meta.get("initial_initramfs_sha256")
                                   or meta.get("initramfs_sha256"))
            _copy_json(root / "topology.json", topology_record)
    (root / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if backend != "inprocess":
        _manifest(root)
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
                           order: tuple[int, ...] = ORDER,
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
        return [slot for slot in order if slot not in accepted
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
                violations: list[str], *, order: tuple[int, ...] = ORDER) -> None:
    raw_events = c.decode((run_dir / "journal.cbor").read_bytes())
    _check_budget(job, raw_events, "journal", violations)
    _check_accept_slots(raw_events, "journal", violations)
    expected, drops, accepted_count = _expected_drop_outcome(job, spec, tuple(raw_events), order)
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
        if pauses[0] < 2:
            violations.append("overlap: no pending active intent before the conflict")
        else:
            pending = trace[pauses[0] - 2]
            if pending.get("kind") != "WRITE_REQUEST" or pending.get("owner") != active:
                violations.append(
                    f"overlap: trace event {pauses[0] - 2} is not the pending active intent")
            elif c.uint(pending.get("message", {}).get("epoch", -1)) != active_epoch:
                violations.append("overlap: pending active intent used a different epoch")
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
                try:
                    writer_epoch = c.uint(recorded.get("writer_epoch", -1))
                except c.CodecError:
                    violations.append(
                        f"overlap: successful write {position} has an invalid writer epoch")
                    continue
                if c.uint(event.get("epoch", -1)) != writer_epoch:
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


def _check_run(spec: dict[str, Any], run_dir: Path, *, executor: Path | None = None,
               backend: str = "inprocess") -> list[str]:
    violations: list[str] = []
    for name in ("job.cbor", "status.cbor", "fault.cbor"):
        if not (run_dir / name).exists():
            violations.append(f"missing {name}")
    if violations:
        return violations
    topology = spec.get("topology", "t1")
    shape = TOPOLOGIES[topology]
    raw = (run_dir / "job.cbor").read_bytes()
    expected = _job_bundle(fixture(bytes.fromhex(spec["nonce"]), spec["budget"],
                                  six=topology == "t2"))
    if raw != expected:
        return ["job differs from the seeded schedule"]
    job = _job_from_bundle(raw)
    if backend != "inprocess":
        metadata_path = run_dir / "metadata.json"
        if not metadata_path.is_file():
            violations.append("missing per-run metadata")
        else:
            metadata = json.loads(metadata_path.read_text())
            if metadata.get("backend") != backend:
                violations.append(f"metadata: backend {metadata.get('backend')} is not {backend}")
            if metadata.get("topology") != topology:
                violations.append(
                    f"metadata: topology {metadata.get('topology')} is not {topology}")
            status = c.decode((run_dir / "status.cbor").read_bytes())
            if c.uint(metadata.get("triggered", -1)) != c.uint(status.get("triggered", -1)):
                violations.append("metadata: triggered count differs from status")
            if executor is not None:
                digest = hashlib.sha256(Path(executor).read_bytes()).hexdigest()
                if metadata.get("executor_sha256") != digest:
                    violations.append("metadata: guest executor differs from campaign executor")
    if backend != "inprocess":
        _check_frames(job, spec, run_dir, executor, violations)
    fault = spec["fault"]
    try:
        if fault in DROPS:
            _check_drop(job, spec, run_dir, violations, order=shape["order"])
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


def _check_campaign_topology(root: Path, schedule: dict[str, Any], backend: str,
                             topology: str, violations: list[str]) -> None:
    path = root / "topology.json"
    if not path.is_file():
        violations.append("topology: campaign has no topology record")
        return
    record = json.loads(path.read_text())
    roles = TOPOLOGIES[topology]["roles"]
    if backend == "local":
        if "lan_links" in record:
            violations.append("topology: local campaign recorded physical links")
        return
    placement = record.get("placement")
    if type(placement) is not dict:
        violations.append("topology: missing guest placement")
        return
    remote = tuple(role for role, host in placement.items() if host == "B")
    if not remote:
        violations.append("topology: dual-host campaign placed no guest on B")
        return
    try:
        dualhost_multivm.check_lan(
            {"topology": record, "kernel_sha256": record.get("kernel_sha256"),
             "initramfs_sha256": record.get("initramfs_sha256")},
            roles, remote)
    except Exception as error:
        violations.append(f"topology: {error}")
    for spec in schedule["runs"]:
        metadata_path = root / f"run-{spec['index']:04d}" / "metadata.json"
        if not metadata_path.is_file():
            continue
        metadata = json.loads(metadata_path.read_text())
        if metadata.get("kernel_sha256") != record.get("kernel_sha256"):
            violations.append(f"run-{spec['index']:04d}: kernel digest differs from topology")
        run_topology = json.loads((root / f"run-{spec['index']:04d}" / "topology.json").read_text())
        boot = run_topology.get("host_b_boot_hashes", {}).get("guest.cpio.gz")
        if boot is not None and metadata.get("initramfs_sha256") != boot:
            violations.append(f"run-{spec['index']:04d}: initramfs digest differs from topology")


def _check_manifest(root: Path, violations: list[str]) -> None:
    path = root / "manifest.sha256"
    if not path.is_file():
        violations.append("manifest: campaign has no evidence manifest")
        return
    recorded = {}
    for line in path.read_text().splitlines():
        if not line:
            continue
        digest, _, name = line.partition("  ")
        recorded[name] = digest
    expected = {}
    for file in sorted(root.rglob("*")):
        if not file.is_file():
            continue
        relative = file.relative_to(root).as_posix()
        if relative == "manifest.sha256":
            continue
        expected[relative] = hashlib.sha256(file.read_bytes()).hexdigest()
    if recorded != expected:
        for name in sorted(set(recorded) | set(expected)):
            if recorded.get(name) != expected.get(name):
                violations.append(f"manifest: {name} differs from the recorded digest")


def check_campaign(root: Path, executor: Path | None = None) -> dict[str, Any]:
    """Replay every run and check the safety-layer invariants without trusting the driver."""
    root = Path(root)
    violations: list[str] = []
    try:
        schedule = c.decode((root / "schedule.cbor").read_bytes())
        specs = schedule["runs"]
        seed = schedule["seed"]
        backend = schedule.get("backend", "inprocess")
        topology = schedule.get("topology", "t1")
        c.need(backend in BACKENDS, f"unknown backend {backend}")
        c.need(topology in TOPOLOGIES, f"unknown topology {topology}")
        rebuilt = generate_schedule(seed, len(specs), topology=topology)
        for key in ("version", "seed", "runs"):
            c.need(schedule.get(key) == rebuilt.get(key),
                   f"schedule {key} differs from the seeded generator")
        report = json.loads((root / "report.json").read_text())
        c.need(type(report) is dict, "report is not an object")
        if executor is None and (root / "executor").is_file():
            executor = root / "executor"
        _check_environment(schedule, report, executor, violations)
        if backend != "inprocess":
            _check_campaign_topology(root, schedule, backend, topology, violations)
            _check_manifest(root, violations)
    except Exception as error:
        return {"runs": 0, "seed": None, "violations": [f"schedule: {error}"]}
    for spec in specs:
        run_dir = root / f"run-{spec['index']:04d}"
        if not run_dir.is_dir():
            violations.append(f"run-{spec['index']:04d}: missing directory")
            continue
        try:
            violations.extend(_check_run(spec, run_dir, executor=executor, backend=backend))
        except Exception as error:
            violations.append(f"run-{spec['index']:04d}: {error}")
    return {"runs": len(specs), "seed": seed, "violations": violations}


def _evidence_hashes(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if (relative in ("report.json", "manifest.sha256")
                or relative.endswith("trace.cbor") or relative.startswith("raw/")
                or "/raw/" in relative):
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
    run_parser.add_argument("--backend", choices=BACKENDS, default="inprocess")
    run_parser.add_argument("--topology", choices=tuple(TOPOLOGIES), default="t1")
    run_parser.add_argument("--config", type=Path)
    run_parser.add_argument("--kernel", type=Path)
    run_parser.add_argument("--placement")
    run_parser.add_argument("--accel", choices=("kvm", "tcg"), default="kvm")
    run_parser.add_argument("--timeout", type=int, default=1800)

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

    if args.backend != "inprocess" or args.executor is not None:
        run_campaign(args.seed, args.runs, args.output, args.executor,
                     backend=args.backend, topology=args.topology, config=args.config,
                     kernel=args.kernel, placement=args.placement, accel=args.accel,
                     timeout=args.timeout)
        result = check_campaign(args.output, args.executor)
        print(format_report(result))
        return 0 if not result["violations"] else 1
    with tempfile.TemporaryDirectory(prefix="aclt-montecarlo-executor-") as temporary:
        executor = build_executor(Path(temporary) / "executor")
        run_campaign(args.seed, args.runs, args.output, executor,
                     backend=args.backend, topology=args.topology, config=args.config,
                     kernel=args.kernel, placement=args.placement, accel=args.accel,
                     timeout=args.timeout)
        result = check_campaign(args.output, executor)
    print(format_report(result))
    return 0 if not result["violations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())