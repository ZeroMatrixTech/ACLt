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
from datetime import datetime, timezone
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
PROFILE_VERSION = "r4-profile-v2"
# R1 amendment 1 (5.2): guest A only coordinates; workers rotate in this order.
PROFILE_ROLES = ("A", "B", "C", "D")
PROFILE_WORKERS = ("B", "C", "D")
PROFILE_RUNS = 16
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


def r4_profile(seed: int, index: int) -> dict[str, Any]:
    """Return the frozen R4 profile for one (seed, index) pair.

    This is the only topology/job selector shared by the runner and the checker.
    The R3 schedule remains the source of the fault class and nonce; the profile
    adds the fixed T1/T2 mapping and the T2 slot offset.
    """
    c.need(type(seed) is int and seed >= 0, "seed must be a non-negative integer")
    c.need(type(index) is int and 0 <= index < PROFILE_RUNS,
           "profile index must be in 0..15")
    base = generate_schedule(seed, PROFILE_RUNS)["runs"][index]
    topology = "t1" if index < 8 else "t2"
    budget = TOPOLOGIES[topology]["budget"]
    fault = base["fault"]
    profile: dict[str, Any] = {
        "profile_version": PROFILE_VERSION,
        "seed": seed,
        "index": index,
        "topology": topology,
        "job_id": "r4-t1-v1" if topology == "t1" else "r4-t2-v1",
        "budget": budget,
        "fault": fault,
        "nonce": base["nonce"],
    }
    if fault in DROPS:
        profile.update(attempt=base["attempt"], loss=base["loss"],
                       slot=base["slot"] + (2 if topology == "t2" else 0))
    elif fault == "handoff":
        profile["checkpoint"] = base["checkpoint"]
    else:
        profile["overlap_after"] = base["overlap_after"]
    job = _profile_job(profile)
    profile["job_sha256"] = hashlib.sha256(_job_bundle(job)).hexdigest()
    return profile


def _profile_job(profile: dict[str, Any]) -> Job:
    return fixture(bytes.fromhex(profile["nonce"]), profile["budget"],
                   six=profile["topology"] == "t2")


def _profile_spec(base: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """Overlay the frozen profile on the R3 schedule record for execution/checking."""
    merged = dict(base)
    for key in ("index", "topology", "budget", "fault", "nonce"):
        merged[key] = profile[key]
    for key in ("attempt", "loss", "slot", "checkpoint", "overlap_after"):
        if key in profile:
            merged[key] = profile[key]
    return merged


def _profile_placement(topology: str) -> str:
    """Both profile topologies keep coordinator A on host A and B, C, D on host B."""
    c.need(topology in TOPOLOGIES, f"unknown topology {topology}")
    return ",".join(PROFILE_WORKERS)


def _profile_worker(slot: int, attempt: int) -> str:
    """R1 5.2: first solve W[i], retry W[i+2] (the verifier is W[i+1])."""
    return PROFILE_WORKERS[(slot + (0 if attempt == 1 else 2)) % len(PROFILE_WORKERS)]


def _profile_verifier(slot: int) -> str:
    return PROFILE_WORKERS[(slot + 1) % len(PROFILE_WORKERS)]


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
              roles: tuple[str, ...] = ROLES, order: tuple[int, ...] = ORDER,
              layout: dict[str, Any] | None = None) -> None:
    layout = layout or {}
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
        journal, outcome = run(job, roles, run_dir / "journal.cbor", exchange, order=order,
                               **layout)
        _write_status(run_dir, spec, outcome, triggered=triggered,
                      accepted=len(journal.accepted), final=journal.final is not None)
        _write_fault(run_dir, spec, triggered=triggered)
        _write_result(run_dir, journal.final)
    except Exception as error:  # Keep the campaign inspectable; the checker records the violation.
        _write_status(run_dir, spec, "ERROR", triggered=triggered, error=repr(error))
        _write_fault(run_dir, spec, triggered=triggered)


def _run_handoff(job: Job, spec: dict[str, Any], run_dir: Path, executor: Path, *,
                 roles: tuple[str, ...] = ROLES, order: tuple[int, ...] = ORDER,
                 layout: dict[str, Any] | None = None) -> None:
    layout = layout or {}
    checkpoint = spec["checkpoint"]

    def exchange(worker: str, raw: bytes) -> bytes:
        return handle(raw, executor)

    try:
        checkpoint_journal, checkpoint_outcome = run(
            job, roles, run_dir / "checkpoint.cbor", exchange,
            order=order, checkpoint=checkpoint, **layout,
        )
        if checkpoint_outcome != "CHECKPOINT":
            _write_status(run_dir, spec, "ERROR", checkpoint=checkpoint,
                          error=f"checkpoint stopped at {checkpoint_outcome}")
            _write_fault(run_dir, spec, triggered=0)
            return
        journal, outcome = run(
            job, roles, run_dir / "journal.cbor", exchange,
            order=order, previous=run_dir / "checkpoint.cbor", **layout,
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
                 roles: tuple[str, ...] = ROLES, order: tuple[int, ...] = ORDER,
                 layout: dict[str, Any] | None = None) -> None:
    layout = layout or {}
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
                                 order=order, journal_factory=factory, **layout)
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
             topology: str = "t1", profile: bool = False) -> None:
    shape = TOPOLOGIES[topology]
    roles, order = shape["roles"], shape["order"]
    layout = None
    if profile:
        roles = PROFILE_ROLES
        layout = {"placement": general_vm.coordinator_only(PROFILE_WORKERS, len(job.tasks)),
                  "retry_worker": general_vm.retry_after(PROFILE_WORKERS)}
    if spec["fault"] in DROPS:
        _run_drop(job, spec, run_dir, executor, roles=roles, order=order, layout=layout)
    elif spec["fault"] == "handoff":
        _run_handoff(job, spec, run_dir, executor, roles=roles, order=order, layout=layout)
    elif spec["fault"] == "overlap":
        _run_overlap(job, spec, run_dir, executor, roles=roles, order=order, layout=layout)
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


def _phase_topologies(raw: Path, fallback: dict[str, Any]) -> list[dict[str, Any]]:
    """Read every per-phase topology record the dual-host harness retained."""
    records = []
    for label in ("before", "after", "run"):
        path = raw / f"host-topology-{label}.json"
        if path.is_file():
            records.append({"phase": label,
                            "topology": _redact_topology(json.loads(path.read_text()))})
    if not records and fallback:
        records.append({"phase": "run", "topology": _redact_topology(fallback)})
    return records


def _normalize_guest_run(job: Job, spec: dict[str, Any], run_dir: Path, raw: Path,
                         result: dict[str, Any], *, backend: str, topology: str,
                         profile: dict[str, Any] | None = None) -> None:
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
    worker_exits = sorted((dict(row) for item in guest.values() for row in item.get("worker_exits", ())
                           if type(row) is dict),
                          key=lambda row: (row["slot"], row["attempt"], row["role"]))
    serving_observations = sorted(
        (dict(row) for item in guest.values() for row in item.get("observations", ())),
        key=lambda row: (row["slot"], row["attempt"], row["role"], row["event"]))
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
        _copy(raw / "coordination.trace", run_dir / "trace.cbor")
        extra = {"triggered": 1, "paused": True, "intents": spec["overlap_after"],
                 "error": "overlapping coordinator epochs"}
    if overlap or (raw / "host-journal.cbor").is_file():
        # R1 5.4: host.cbor is the authoritative journal, guest.cbor the coordinator's copy.
        _copy(raw / "host-journal.cbor", run_dir / "host.cbor")
        _copy(root / "journal.cbor", run_dir / "guest.cbor")
    outcome = "PAUSED" if overlap else result["general_status"]
    _write_status(run_dir, spec, outcome, **extra)
    if fault in DROPS:
        injections = sorted((dict(row) for item in guest.values() for row in item.get("injection", ())),
                            key=lambda row: (row["slot"], row["attempt"], row["role"]))
        _write_fault(run_dir, spec, triggered=triggered, injections=injections)
    else:
        _write_fault(run_dir, spec, triggered=triggered)
    if journal.final is not None:
        _copy(root / "publication.cbor", run_dir / "result.cbor")
    phase_records = _phase_topologies(raw, result.get("topology", {}))
    observed = phase_records[-1]["topology"]
    topology_doc = dict(observed)
    topology_doc["phases"] = phase_records
    _copy_json(run_dir / "topology.json", topology_doc)
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
    phase_images = {"before": initial_image, "after": boot_image, "run": boot_image}
    phase_meta = []
    for record in phase_records:
        item = record["topology"]
        phase_meta.append({
            "phase": record["phase"],
            "initramfs_sha256": phase_images.get(record["phase"]),
            "placement": item.get("placement"),
            "remote_roles": sorted(item.get("lan_links", {})),
        })
    # Lock records and the run window come from the harness's A-side UTC clock (R1 5.5).
    locks = [dict(row, run_index=spec["index"]) for row in result.get("locks", ())]
    observations = [dict(row) for row in result.get("observations", ())]
    metadata = {
        "backend": backend,
        "topology": topology,
        "seed": profile.get("seed") if profile else None,
        "index": spec["index"],
        "job_id": profile.get("job_id") if profile else None,
        "job_sha256": profile.get("job_sha256") if profile else None,
        "fault": fault,
        "source_revision": result.get("commit"),
        "source_commit": result.get("commit"),
        "source_manifest_sha256": result.get("source_manifest_sha256"),
        "executor_sha256": result.get("executor_sha256"),
        "kernel_sha256": result.get("kernel_sha256"),
        "initramfs_sha256": boot_image,
        "initial_initramfs_sha256": initial_image,
        "host_a_environment": result.get("environment"),
        "host_b_environment": observed.get("host_b_environment"),
        "phases": phase_meta,
        "locks": locks,
        "observations": observations,
        "final_state": outcome,
        "failure_reason": extra.get("error"),
        "started_at": result.get("started_at"),
        "ended_at": result.get("ended_at"),
        "placement": observed.get("placement"),
        "remote_roles": sorted(observed.get("lan_links", {})),
        "guest_boot_ids": {role: row.get("boot_id") for role, row in guest.items()},
        "before_guest_boot_ids": ({role: row.get("boot_id")
                                   for role, row in result.get("before_guests", {}).items()}
                                  if handoff else {}),
        "triggered": triggered,
        "worker_exits": worker_exits,
        "serving_observations": serving_observations,
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
                journal_path=run_dir / "journal.cbor",
                suppressed_reply=spec["fault"] == "no_reply")
    except Exception as error:
        violations.append(f"frames: {error}")


def _check_assignment(events: list[dict[str, Any]], label: str,
                      violations: list[str]) -> None:
    """R1 5.2/5.3: rebuild the coordinator-only assignment and compare each slot."""
    for position, event in enumerate(events):
        kind = event.get("kind")
        if kind == "RESERVE":
            expected = _profile_worker(c.uint(event["slot"]), c.uint(event["attempt"]))
            if event.get("worker") != expected:
                violations.append(
                    f"{label}: event {position} solve slot {event['slot']} attempt "
                    f"{event['attempt']} went to {event.get('worker')}, not {expected}")
        elif kind == "ACCEPT":
            expected = _profile_verifier(c.uint(event["slot"]))
            if event.get("verifier") != expected:
                violations.append(
                    f"{label}: event {position} verify slot {event['slot']} went to "
                    f"{event.get('verifier')}, not {expected}")


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _check_serving(job: Job, spec: dict[str, Any], run_dir: Path, executor: Path | None,
                   violations: list[str]) -> None:
    """R1 5.3 serving-side binding for profile evidence from a guest backend.

    Every dispatched SOLVE (first and retry) and VERIFY is bound by
    (run, slot, attempt, action) to the raw frames retained by the coordinator and
    by the serving worker VM; replies are split into generated, sent and received.
    """
    fault = spec["fault"]
    frames = run_dir / "frames"
    if not frames.is_dir():
        violations.append("serving: run retained no request/response frames")
        return
    metadata_path = run_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.is_file() else {}
    try:
        journal_events = c.decode((run_dir / "journal.cbor").read_bytes())
    except Exception as error:
        violations.append(f"serving: unreadable journal: {error}")
        return
    if fault == "handoff":
        try:
            checkpoint_events = c.decode((run_dir / "checkpoint.cbor").read_bytes())
        except Exception as error:
            violations.append(f"serving: unreadable checkpoint: {error}")
            return
        phases = [("before", checkpoint_events, 0, metadata.get("before_guest_boot_ids")),
                  ("after", journal_events, len(checkpoint_events),
                   metadata.get("guest_boot_ids"))]
    else:
        phases = [("", journal_events, 0, metadata.get("guest_boot_ids"))]
    injections = []
    try:
        recorded_fault = c.decode((run_dir / "fault.cbor").read_bytes())
        injections = recorded_fault.get("injections", [])
    except Exception as error:
        violations.append(f"serving: unreadable fault record: {error}")
    if type(injections) is not list:
        violations.append("serving: fault injections are not a list")
        injections = []
    no_replies: dict[tuple[int, int], dict[str, Any]] = {}
    for label, events, prefix, boot_ids in phases:
        where = f"serving/{label}" if label else "serving"
        root = frames / label if label else frames
        present: dict[str, set[str]] = {}
        if root.is_dir():
            for child in root.iterdir():
                if child.is_dir():
                    present[child.name] = {path.name for path in child.glob("*")}
                else:
                    violations.append(f"{where}: unexpected frame file {child.name}")
        for role in sorted(set(present) - set(PROFILE_ROLES)):
            violations.append(f"{where}: frames for unknown role {role}")
        expected: dict[str, set[str]] = {role: set() for role in PROFILE_ROLES}
        boot_ids = boot_ids if type(boot_ids) is dict else {}

        def frame(role: str, name: str) -> bytes | None:
            path = root / role / name
            return path.read_bytes() if path.is_file() else None

        def bind(role: str, name: str, raw: bytes, what: str) -> None:
            if role == "A" or role not in PROFILE_WORKERS:
                violations.append(f"{where}: {what} {name} was served by {role}, not a worker")
                return
            if not isinstance(boot_ids.get(role), str) or not boot_ids.get(role):
                violations.append(f"{where}: serving role {role} has no boot identifier")
            for endpoint in ("A", role):
                expected[endpoint].add(f"{name}-request.cbor")
                if frame(endpoint, f"{name}-request.cbor") != raw:
                    violations.append(
                        f"{where}: {what} {name} request frame at {endpoint} is missing or differs")

        later = events[prefix:]
        for position, event in enumerate(later, start=prefix):
            kind = event.get("kind")
            if kind == "RESERVE":
                slot, attempt = c.uint(event["slot"]), c.uint(event["attempt"])
                raw, worker = event["request"], event.get("worker")
                name = general_vm.wire_name(raw)
                bind(worker, name, raw, "solve")
                outcome = [item for item in later if item.get("kind") in ("ANSWER", "NO_REPLY")
                           and (c.uint(item["slot"]), c.uint(item["attempt"])) == (slot, attempt)]
                if len(outcome) != 1:
                    violations.append(f"{where}: dispatched solve {name} has no unique disposition")
                    continue
                response_name = f"{name}-response.cbor"
                if outcome[0]["kind"] == "ANSWER":
                    response = outcome[0]["response"]
                    for endpoint in ("A", worker):
                        expected[endpoint].add(response_name)
                        if frame(endpoint, response_name) != response:
                            violations.append(
                                f"{where}: solve {name} reply at {endpoint} is missing or differs")
                    if executor is not None and handle(raw, executor) != response:
                        violations.append(f"{where}: solve {name} reply differs from recomputation")
                    continue
                if frame("A", response_name) is not None:
                    violations.append(
                        f"{where}: coordinator holds a reply for undelivered solve {name}")
                served = frame(worker, response_name)
                if fault == "no_reply":
                    expected[worker].add(response_name)
                    if served is None:
                        violations.append(
                            f"{where}: no_reply solve {name} has no generated serving-side reply")
                    elif executor is not None and handle(raw, executor) != served:
                        violations.append(
                            f"{where}: withheld reply for {name} differs from recomputation")
                elif served is not None:
                    violations.append(
                        f"{where}: {fault} solve {name} has a serving-side reply")
                no_replies[(slot, attempt)] = {"worker": worker, "request": raw,
                                               "response": served}
            elif kind == "ACCEPT":
                raw, verifier = event["request"], event.get("verifier")
                name = general_vm.wire_name(raw)
                bind(verifier, name, raw, "verify")
                response_name = f"{name}-response.cbor"
                for endpoint in ("A", verifier):
                    expected.setdefault(endpoint, set()).add(response_name)
                    if frame(endpoint, response_name) != event["response"]:
                        violations.append(
                            f"{where}: verify {name} reply at {endpoint} is missing or differs")
                if executor is not None and handle(raw, executor) != event["response"]:
                    violations.append(f"{where}: verify {name} reply differs from recomputation")
        for role in PROFILE_ROLES:
            actual = present.get(role, set())
            for name in sorted(actual - expected[role]):
                violations.append(f"{where}: unbound frame {role}/{name}")
            for name in sorted(expected[role] - actual):
                if not any(name in item for item in violations):
                    violations.append(f"{where}: missing frame {role}/{name}")
    if fault not in DROPS:
        if injections:
            violations.append(f"serving: {fault} run recorded drop injections")
        return
    matched: set[tuple[int, int]] = set()
    for row in injections:
        if type(row) is not dict:
            violations.append("serving: injection record is not a map")
            continue
        try:
            key = (c.uint(row.get("slot", -1)), c.uint(row.get("attempt", -1)))
        except c.CodecError:
            violations.append("serving: injection record has no slot/attempt")
            continue
        if key in matched:
            violations.append(f"serving: duplicate injection record for slot/attempt {key}")
            continue
        matched.add(key)
        disposition = no_replies.get(key)
        if disposition is None:
            violations.append(f"serving: injection record {key} has no NO_REPLY attempt")
            continue
        if row.get("mode") != fault:
            violations.append(f"serving: injection record {key} is {row.get('mode')}, not {fault}")
        if row.get("role") != disposition["worker"]:
            violations.append(f"serving: injection record {key} names {row.get('role')}, "
                              f"not the serving worker {disposition['worker']}")
        if row.get("execution_id") != job.execution_id.hex():
            violations.append(f"serving: injection record {key} names another execution")
        if row.get("request_sha256") != _sha256(disposition["request"]):
            violations.append(f"serving: injection record {key} request digest differs")
        if fault == "no_reply":
            served = disposition["response"]
            if served is None or row.get("response_sha256") != _sha256(served):
                violations.append(
                    f"serving: no_reply record {key} does not bind the withheld reply")
        elif "response_sha256" in row:
            violations.append(f"serving: {fault} record {key} claims a generated reply")
        target = {"role": disposition["worker"], "slot": key[0], "attempt": key[1]}
        if fault == "worker_exit":
            exits = [item for item in metadata.get("worker_exits", ())
                     if type(item) is dict and all(item.get(k) == v for k, v in target.items())]
            if len(exits) != 1 or exits[0].get("exit_status") in (None, 0):
                violations.append(
                    f"serving: worker_exit {key} has no non-zero worker process exit observation")
        elif fault == "tcp_disconnect":
            closed = [item for item in metadata.get("serving_observations", ())
                      if type(item) is dict and item.get("event") == "closed"
                      and all(item.get(k) == v for k, v in target.items())]
            if len(closed) != 1:
                violations.append(
                    f"serving: tcp_disconnect {key} has no serving-side close observation")
    for key in sorted(set(no_replies) - matched):
        violations.append(f"serving: NO_REPLY at slot/attempt {key} has no injection record")
    # Host-timed observations (A-side collection time, R1 5.5) must match the
    # per-attempt records: one injected_<mode> per record with its serving role and
    # request-frame digest, and one worker_exit_<status> per observed worker exit.
    timed = [row for row in metadata.get("observations", ()) if type(row) is dict]
    expected_injected = sorted((row.get("role"), row.get("request_sha256"))
                               for row in injections if type(row) is dict)
    observed_injected = sorted((row.get("role"), row.get("frame_sha256")) for row in timed
                               if row.get("event") == f"injected_{fault}")
    if observed_injected != expected_injected or any(
            str(row.get("event", "")).startswith("injected_") and row.get("event") != f"injected_{fault}"
            for row in timed):
        violations.append("serving: host injection observations do not match the injection records")
    if fault == "worker_exit":
        expected_exits = sorted((row.get("role"), f"worker_exit_{row.get('exit_status')}")
                                for row in metadata.get("worker_exits", ()) if type(row) is dict)
        observed_exits = sorted((row.get("role"), row.get("event")) for row in timed
                                if str(row.get("event", "")).startswith("worker_exit_"))
        if observed_exits != expected_exits:
            violations.append("serving: host worker-exit observations do not match the worker exits")


def _copy_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _run_guest(job: Job, spec: dict[str, Any], run_dir: Path, *, backend: str,
               topology: str, config: Path | None, kernel: Path, placement: str | None,
               accel: str, timeout: int, executor: Path | None = None,
               profile: bool = False, profile_record: dict[str, Any] | None = None) -> None:
    shape = TOPOLOGIES[topology]
    remote_roles = tuple(role for role in (placement or "").split(",") if role)
    roles = PROFILE_ROLES if profile else shape["roles"]
    if spec["fault"] in DROPS and backend == "dualhost":
        worker = (_profile_worker(spec["slot"], 1) if profile
                  else assignments(roles, len(job.tasks))[spec["slot"]][0])
        if worker not in remote_roles:
            _write_status(run_dir, spec, "ERROR",
                          error=f"injected slot {spec['slot']} is served on host A")
            _write_fault(run_dir, spec, triggered=0)
            return
    raw = run_dir / "raw"
    order = "".join(str(slot) for slot in shape["order"])
    command = [sys.executable, "-B", str(Path(__file__).with_name("multivm.py")), "run",
               "--general", "--guests", str(len(roles)), "--kernel", str(kernel),
               "--output", str(raw), "--solve-budget", str(spec["budget"]),
               "--general-order", order, "--general-nonce", spec["nonce"],
               "--accel", accel]
    if executor is not None:
        command += ["--executor", str(executor)]
    if topology == "t2":
        command.append("--general-six")
    if profile:
        command += ["--general-workers", "".join(PROFILE_WORKERS), "--coordinated"]
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
    _normalize_guest_run(job, spec, run_dir, raw, result, backend=backend, topology=topology,
                         profile=profile_record)
    shutil.rmtree(raw, ignore_errors=True)


def _host_environment(metadata: dict[str, Any], backend: str) -> dict[str, Any]:
    host_a = metadata.get("host_a_environment") or {}
    record: dict[str, Any] = {
        "host_a": {key: host_a.get(key) for key in
                   ("os", "kernel", "machine", "qemu", "kvm", "python", "accel")},
        "source_manifest_sha256": metadata.get("source_manifest_sha256"),
        "kernel_sha256": metadata.get("kernel_sha256"),
        "initramfs_sha256": metadata.get("initial_initramfs_sha256")
        or metadata.get("initramfs_sha256"),
    }
    if backend == "dualhost":
        host_b = metadata.get("host_b_environment") or {}
        record["host_b"] = dict({key: host_b.get(key) for key in
                                 ("os", "kernel", "machine", "qemu", "kvm", "python")},
                                rustc=None)  # B runs the static executor built on A.
    return record


def _profile_environment(root: Path, environment: dict[str, Any],
                         backend: str) -> dict[str, Any]:
    first = next((path for path in sorted(root.glob("run-*/metadata.json"))), None)
    if first is None:
        return dict(environment)
    return dict(environment, **_host_environment(json.loads(first.read_text()), backend))


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
                 backend: str = "inprocess", topology: str | None = "t1",
                 profile: bool = False,
                 config: Path | None = None, kernel: Path | None = None,
                 placement: str | None = None, accel: str = "kvm",
                 timeout: int = 1800) -> dict[str, Any]:
    """Execute one deterministic campaign and retain inspectable per-run evidence."""
    c.need(backend in BACKENDS, f"unknown backend {backend}")
    if profile:
        c.need(topology in (None, "t1"), "profile mode derives T1/T2 from the run index")
        topology = None
        c.need(runs == PROFILE_RUNS, f"profile campaign needs {PROFILE_RUNS} runs")
    else:
        c.need(topology in TOPOLOGIES, f"unknown topology {topology}")
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    c.need(not any(root.iterdir()), "campaign output directory must be empty")
    if backend != "inprocess":
        c.need(kernel is not None and Path(kernel).is_file(), "cross-host campaign needs a kernel")
        if backend == "dualhost":
            c.need(config is not None, "dual-host campaign needs a placement file")
            if not profile:
                c.need(placement, "dual-host campaign needs a B placement")
        if executor is None:
            executor = build_executor(root / "executor", static=True)
    c.need(executor is not None, "in-process campaign needs an executor")
    schedule = (generate_schedule(seed, PROFILE_RUNS) if profile
                else generate_schedule(seed, runs, topology=topology))
    environment = _environment(Path(executor))
    if backend != "inprocess":
        environment = dict(environment, backend=backend,
                           topology="profile" if profile else topology)
        if not profile:
            schedule["backend"] = backend
    if not profile:
        schedule["environment"] = environment
    (root / "schedule.cbor").write_bytes(c.encode(schedule))
    if backend != "inprocess" and not profile:
        (root / "environment.json").write_text(
            json.dumps(environment, indent=2, sort_keys=True) + "\n")
    rows = []
    for base_spec in schedule["runs"]:
        spec = _profile_spec(base_spec, r4_profile(seed, base_spec["index"])) if profile else base_spec
        run_dir = root / f"run-{spec['index']:04d}"
        run_dir.mkdir()
        spec_topology = _topology_for(spec, topology or "t1")
        job = fixture(bytes.fromhex(spec["nonce"]), spec["budget"],
                      six=spec_topology == "t2")
        (run_dir / "job.cbor").write_bytes(_job_bundle(job))
        if profile:
            (run_dir / "profile.cbor").write_bytes(c.encode(r4_profile(seed, spec["index"])))
        _write_fault(run_dir, spec)
        if backend == "inprocess":
            _run_one(job, spec, run_dir, Path(executor), topology=spec_topology, profile=profile)
        else:
            run_placement = (_profile_placement(spec_topology) if profile else placement)
            _run_guest(job, spec, run_dir, backend=backend, topology=spec_topology,
                       config=config, kernel=Path(kernel), placement=run_placement,
                       accel=accel, timeout=timeout, executor=Path(executor), profile=profile,
                       profile_record=r4_profile(seed, spec["index"]) if profile else None)
        status = c.decode((run_dir / "status.cbor").read_bytes())
        row = {"index": spec["index"], "fault": spec["fault"], "outcome": status["outcome"]}
        if backend != "inprocess" or profile:
            row["topology"] = spec_topology
        if backend != "inprocess":
            row["triggered"] = int(status.get("triggered", 0))
        rows.append(row)
    if backend != "inprocess" and profile:
        # R1 5.4: both hosts' OS, kernel, QEMU, KVM, Python, Rust, executor and source
        # digests, and B's boot images; no clock values or transient endpoints.
        environment = _profile_environment(root, environment, backend)
        (root / "environment.json").write_text(
            json.dumps(environment, indent=2, sort_keys=True) + "\n")
    report = {"seed": seed, "runs": rows, "environment": environment}
    if profile:
        report["profile"] = True
    if backend != "inprocess":
        report.update(backend=backend, topology="profile" if profile else topology)
        if profile:
            _copy_json(root / "topology.json", {
                "profile": True,
                "topologies": ["t1", "t2"],
                "profile_version": PROFILE_VERSION,
                "roles": list(PROFILE_ROLES),
                "workers": list(PROFILE_WORKERS),
                "placements": {name: _profile_placement(name) for name in ("t1", "t2")},
                "run_count": len(rows),
            })
        else:
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
                   violations: list[str], *, profile: bool = False) -> None:
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
            elif profile:
                _check_pending_reserve(pending, run_dir, violations)
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


def _check_pending_reserve(pending: dict[str, Any], run_dir: Path,
                           violations: list[str]) -> None:
    """R1 5.3: the paused intent is the uncommitted RESERVE, never dispatched."""
    message = pending.get("message", {})
    if message.get("event") != "RESERVE":
        violations.append(
            f"overlap: paused intent is {message.get('event')}, not an uncommitted RESERVE")
        return
    request = (message.get("fields") or {}).get("request")
    if not isinstance(request, bytes):
        violations.append("overlap: paused RESERVE carries no request")
        return
    name = general_vm.wire_name(request)
    frames = run_dir / "frames"
    if frames.is_dir() and any(path.name.startswith(f"{name}-") for path in frames.rglob("*")):
        violations.append(f"overlap: paused RESERVE {name} was dispatched")


def _check_run(spec: dict[str, Any], run_dir: Path, *, executor: Path | None = None,
               backend: str = "inprocess", profile: dict[str, Any] | None = None) -> list[str]:
    violations: list[str] = []
    for name in ("job.cbor", "status.cbor", "fault.cbor"):
        if not (run_dir / name).exists():
            violations.append(f"missing {name}")
    if violations:
        return violations
    if profile is not None:
        profile_path = run_dir / "profile.cbor"
        if not profile_path.is_file():
            return ["profile: run has no profile.cbor"]
        if profile_path.read_bytes() != c.encode(profile):
            return ["profile: profile.cbor differs from the rebuilt profile"]
        spec = _profile_spec(spec, profile)
    topology = spec.get("topology", "t1")
    shape = TOPOLOGIES[topology]
    raw = (run_dir / "job.cbor").read_bytes()
    expected_job = _profile_job(profile) if profile is not None else fixture(
        bytes.fromhex(spec["nonce"]), spec["budget"], six=topology == "t2")
    expected = _job_bundle(expected_job)
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
        if profile is not None:
            _check_coordinated_journals(spec, run_dir, violations)
            metadata_path = run_dir / "metadata.json"
            if metadata_path.is_file():
                metadata = json.loads(metadata_path.read_text())
                for key in ("seed", "index", "job_id", "job_sha256", "fault"):
                    expected = spec["fault"] if key == "fault" else profile[key]
                    if metadata.get(key) != expected:
                        violations.append(f"metadata: {key} differs from the rebuilt profile")
            _check_serving(job, spec, run_dir, executor, violations)
        else:
            _check_frames(job, spec, run_dir, executor, violations)
    fault = spec["fault"]
    if profile is not None:
        for name in ("journal.cbor", "checkpoint.cbor", "host.cbor"):
            if (run_dir / name).is_file():
                try:
                    _check_assignment(c.decode((run_dir / name).read_bytes()),
                                      f"assignment/{name}", violations)
                except Exception as error:
                    violations.append(f"assignment/{name}: {error}")
    try:
        if fault in DROPS:
            _check_drop(job, spec, run_dir, violations, order=shape["order"])
        elif fault == "handoff":
            _check_handoff(job, spec, run_dir, violations)
        elif fault == "overlap":
            _check_overlap(job, spec, run_dir, violations, profile=profile is not None)
        else:
            violations.append(f"unknown fault class {fault}")
    except Exception as error:
        violations.append(f"{fault}: {error}")
    return violations


def _check_environment(schedule: dict[str, Any], report: dict[str, Any],
                      executor: Path | None, violations: list[str]) -> None:
    recorded = schedule.get("environment") or report.get("environment")
    if type(recorded) is not dict:
        violations.append("environment: no environment record")
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
                             topology: str | None, violations: list[str],
                             *, profile: bool = False) -> None:
    """Check every run and every handoff phase, not only the campaign summary."""
    path = root / "topology.json"
    if not path.is_file():
        violations.append("topology: campaign has no topology record")
        return
    for spec in schedule["runs"]:
        index = spec["index"]
        label = f"run-{index:04d}"
        run_dir = root / label
        metadata_path = run_dir / "metadata.json"
        if not metadata_path.is_file():
            violations.append(f"{label}: missing per-run metadata")
            continue
        metadata = json.loads(metadata_path.read_text())
        expected_topology = (r4_profile(schedule["seed"], index)["topology"]
                             if profile else topology)
        if not expected_topology:
            violations.append(f"{label}: no topology selected")
            continue
        if metadata.get("topology") != expected_topology:
            violations.append(f"{label}: metadata topology is not {expected_topology}")
        topology_path = run_dir / "topology.json"
        if not topology_path.is_file():
            violations.append(f"{label}: missing per-run topology")
            continue
        document = json.loads(topology_path.read_text())
        records = document.get("phases")
        if type(records) is not list or not records:
            violations.append(f"{label}: no per-phase topology records")
            continue
        phases = {}
        for item in records:
            if type(item) is dict and type(item.get("phase")) is str:
                phases[item["phase"]] = item
        expected_phases = (("before", "after") if spec["fault"] == "handoff"
                           else ("run",))
        if set(phases) != set(expected_phases):
            violations.append(
                f"{label}: phases {sorted(phases)} are not {sorted(expected_phases)}")
            continue
        meta_phases = {item.get("phase"): item
                       for item in metadata.get("phases", []) if type(item) is dict}
        for phase in expected_phases:
            item = phases[phase].get("topology")
            if type(item) is not dict:
                violations.append(f"{label}/{phase}: topology is not an object")
                continue
            if backend == "local":
                if "lan_links" in item:
                    violations.append(f"{label}/{phase}: local run recorded physical links")
                continue
            placement = item.get("placement")
            if type(placement) is not dict:
                violations.append(f"{label}/{phase}: missing guest placement")
                continue
            remote = tuple(sorted(role for role, host in placement.items() if host == "B"))
            if profile:
                expected = _profile_placement(expected_topology)
            else:
                expected = metadata.get("placement")
            if tuple(sorted(role for role in (expected or "").split(",") if role)) != remote:
                violations.append(f"{label}/{phase}: B placement differs from the campaign")
                continue
            phase_meta = meta_phases.get(phase, {})
            image = phase_meta.get("initramfs_sha256")
            if not isinstance(image, str):
                violations.append(f"{label}/{phase}: no boot image digest in metadata")
                continue
            try:
                dualhost_multivm.check_lan(
                    {"topology": item, "kernel_sha256": metadata.get("kernel_sha256"),
                     "initramfs_sha256": image},
                    PROFILE_ROLES if profile else TOPOLOGIES[expected_topology]["roles"], remote)
            except Exception as error:
                violations.append(f"{label}/{phase}: {error}")
        _check_run_window(label, index, metadata, backend, expected_phases, violations)
        if profile:
            _check_run_environment(label, root, metadata, backend, violations)
            if spec["fault"] == "handoff":
                _check_handoff_boots(label, metadata, violations)
        if spec["fault"] == "handoff":
            before = meta_phases.get("before", {}).get("initramfs_sha256")
            after = meta_phases.get("after", {}).get("initramfs_sha256")
            if metadata.get("initial_initramfs_sha256") != before:
                violations.append(f"{label}: initial image differs from the before phase")
            if metadata.get("initramfs_sha256") != after:
                violations.append(f"{label}: final image differs from the after phase")
        else:
            run_image = meta_phases.get("run", {}).get("initramfs_sha256")
            if metadata.get("initramfs_sha256") != run_image:
                violations.append(f"{label}: image differs from the run phase")


def _instant(value: Any) -> datetime | None:
    """Parse an RFC 3339 timestamp that carries a time zone; None if it does not."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _check_run_window(label: str, index: int, metadata: dict[str, Any], backend: str,
                      phases: tuple[str, ...], violations: list[str]) -> None:
    """R1 5.5: locks belong to this run and enclose its window on the A-side clock."""
    hosts = ("A", "B") if backend == "dualhost" else ("A",)
    started, ended = _instant(metadata.get("started_at")), _instant(metadata.get("ended_at"))
    if started is None or ended is None:
        violations.append(f"{label}: started_at/ended_at are not RFC 3339 times with a zone")
        return
    if started > ended:
        violations.append(f"{label}: started_at is after ended_at")
    locks = metadata.get("locks")
    if type(locks) is not list:
        violations.append(f"{label}: no lock records")
        return
    window: dict[tuple[str, str], datetime] = {}
    for row in locks:
        if type(row) is not dict:
            violations.append(f"{label}: lock record is not a map")
            continue
        if row.get("run_index") != index:
            violations.append(f"{label}: lock record belongs to run {row.get('run_index')}")
        if row.get("host") not in hosts or row.get("phase") != "run" \
                or row.get("state") not in ("held", "released"):
            violations.append(f"{label}: unexpected lock record {row.get('host')}/"
                              f"{row.get('phase')}/{row.get('state')}")
            continue
        key = (row["host"], row["state"])
        moment = _instant(row.get("observed_at"))
        if key in window:
            violations.append(f"{label}: duplicate {row['host']} {row['state']} lock record")
        elif moment is None:
            violations.append(f"{label}: {row['host']} {row['state']} lock has no observed time")
        else:
            window[key] = moment
    if any((host, state) not in window for host in hosts for state in ("held", "released")):
        violations.append(f"{label}: lock records do not cover hosts {', '.join(hosts)} "
                          f"held and released")
        return
    held = max(window[(host, "held")] for host in hosts)
    released = min(window[(host, "released")] for host in hosts)
    if backend == "dualhost" and not (window[("A", "held")] <= window[("B", "held")]
                                      and window[("B", "released")] <= window[("A", "released")]):
        violations.append(f"{label}: B lock is not nested inside the A lock")
    if not held <= started <= ended <= released:
        violations.append(f"{label}: run window is outside the common lock window")
    observations = metadata.get("observations")
    if type(observations) is not list:
        violations.append(f"{label}: no host observations")
        return
    events = {}
    for row in observations:
        moment = _instant(row.get("observed_at")) if type(row) is dict else None
        if moment is None:
            violations.append(f"{label}: host observation has no observed time")
            continue
        if not started <= moment <= ended:
            violations.append(f"{label}: host observation {row.get('event')} is outside the run window")
        events.setdefault(row.get("event"), []).append(moment)
    previous_done = None
    for phase in phases:
        begin, done = events.get(f"{phase}_started"), events.get(f"{phase}_collected")
        if not begin or not done or len(begin) != 1 or len(done) != 1 or begin[0] > done[0]:
            violations.append(f"{label}/{phase}: phase start/collection observations are missing")
            previous_done = None
            continue
        # Phases are sequential on the one A clock: a successor starts only after the
        # previous phase has been collected.
        if previous_done is not None and begin[0] < previous_done:
            violations.append(f"{label}/{phase}: phase started before the previous phase was collected")
        previous_done = done[0]


def _check_run_environment(label: str, root: Path, metadata: dict[str, Any], backend: str,
                           violations: list[str]) -> None:
    path = root / "environment.json"
    if not path.is_file():
        violations.append(f"{label}: campaign has no environment.json")
        return
    recorded = json.loads(path.read_text())
    frozen = recorded.get("source_revision")
    if not isinstance(frozen, str) or metadata.get("source_revision") != frozen \
            or metadata.get("source_commit") != frozen:
        violations.append(f"{label}: source revision differs from the campaign's frozen revision")
    for key, value in _host_environment(metadata, backend).items():
        if recorded.get(key) != value:
            violations.append(f"{label}: {key} differs from environment.json")


def _check_handoff_boots(label: str, metadata: dict[str, Any], violations: list[str]) -> None:
    """The successor phase is a fresh boot of every guest, coordinator included."""
    before, after = metadata.get("before_guest_boot_ids"), metadata.get("guest_boot_ids")
    if type(before) is not dict or type(after) is not dict or set(before) != set(after) \
            or set(after) != set(PROFILE_ROLES):
        violations.append(f"{label}: handoff boot identifiers do not cover both phases")
        return
    values = [*before.values(), *after.values()]
    if not all(isinstance(value, str) and value for value in values):
        violations.append(f"{label}: handoff boot identifier is empty")
        return
    if before["A"] == after["A"]:
        violations.append(f"{label}: successor coordinator reused the old coordinator boot")
    if set(before.values()) & set(after.values()) or len(set(values)) != len(values):
        violations.append(f"{label}: handoff phases share a guest boot identifier")


def _check_coordinated_journals(spec: dict[str, Any], run_dir: Path,
                                violations: list[str]) -> None:
    """R1 5.4: host.cbor is authoritative and guest.cbor its copy; epochs per writer."""
    try:
        host = c.decode((run_dir / "host.cbor").read_bytes())
        guest = c.decode((run_dir / "guest.cbor").read_bytes())
    except Exception as error:
        violations.append(f"journals: missing or unreadable host/guest journal: {error}")
        return
    if host != guest:
        violations.append("journals: host and guest journals differ")
    if spec["fault"] != "overlap" and (run_dir / "journal.cbor").is_file():
        if c.decode((run_dir / "journal.cbor").read_bytes()) != guest:
            violations.append("journals: journal.cbor is not the coordinator's journal")
    epochs = []
    for position, event in enumerate(host):
        if event.get("kind") == "HANDOFF":
            continue
        try:
            epochs.append((position, c.uint(event["writer_epoch"])))
        except (KeyError, c.CodecError):
            violations.append(f"journals: host event {position} has no valid writer_epoch")
    handoffs = [position for position, event in enumerate(host) if event.get("kind") == "HANDOFF"]
    if spec["fault"] == "handoff":
        if len(handoffs) != 1:
            violations.append(f"journals: handoff host journal has {len(handoffs)} HANDOFF records")
            return
        at = handoffs[0]
        try:
            new_epoch = c.uint(host[at]["epoch"])
        except (KeyError, c.CodecError):
            violations.append("journals: HANDOFF has no valid epoch")
            return
        before = {epoch for position, epoch in epochs if position < at}
        after = {epoch for position, epoch in epochs if position > at}
        if len(before) != 1 or after != {new_epoch} or new_epoch != next(iter(before)) + 1:
            violations.append("journals: writer epochs do not advance exactly once at the HANDOFF")
    elif handoffs or len({epoch for _, epoch in epochs}) > 1:
        violations.append("journals: a run without handoff changed writer epoch")


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


def _bind_backend(root: Path, declared: str, expected: str | None,
                  violations: list[str]) -> str:
    """Decide which backend's checks apply; summaries never weaken the acceptance path.

    An explicit expected backend wins over every declaration.  Without one, an
    in-process declaration is rejected whenever guest-backend evidence is present.
    """
    environment_path = root / "environment.json"
    recorded = None
    if environment_path.is_file():
        try:
            recorded = json.loads(environment_path.read_text()).get("backend")
        except Exception:
            violations.append("backend: environment.json is unreadable")
    guest_evidence = [name for name, present in (
        ("environment.json", environment_path.is_file()),
        ("manifest.sha256", (root / "manifest.sha256").is_file()),
        ("run metadata", any(root.glob("run-*/metadata.json"))),
        ("frames", any(root.glob("run-*/frames")))) if present]
    backend = expected or declared
    if expected is not None and declared != expected:
        violations.append(f"backend: report declares {declared}, acceptance expects {expected}")
    if backend == "inprocess":
        if guest_evidence:
            violations.append("backend: in-process declaration conflicts with guest-backend "
                              f"evidence ({', '.join(guest_evidence)})")
    else:
        if recorded != backend:
            violations.append(f"backend: environment.json records {recorded}, not {backend}")
        if not (root / "manifest.sha256").is_file():
            violations.append("backend: guest-backend campaign has no manifest")
    return backend


def check_campaign(root: Path, executor: Path | None = None, *,
                   expected_backend: str | None = None) -> dict[str, Any]:
    """Replay every run and check the safety-layer invariants without trusting the driver."""
    root = Path(root)
    violations: list[str] = []
    try:
        schedule = c.decode((root / "schedule.cbor").read_bytes())
        specs = schedule["runs"]
        seed = schedule["seed"]
        report = json.loads((root / "report.json").read_text())
        c.need(type(report) is dict, "report is not an object")
        profile_mode = bool(report.get("profile"))
        if profile_mode:
            c.need(len(specs) == PROFILE_RUNS,
                   f"profile campaign needs {PROFILE_RUNS} runs")
            backend = report.get("backend", "inprocess")
            topology = None
        else:
            backend = schedule.get("backend", "inprocess")
            topology = schedule.get("topology", "t1")
            c.need(topology in TOPOLOGIES, f"unknown topology {topology}")
        c.need(backend in BACKENDS, f"unknown backend {backend}")
        c.need(expected_backend in (None, *BACKENDS), f"unknown backend {expected_backend}")
        backend = _bind_backend(root, backend, expected_backend, violations)
        rebuilt = (generate_schedule(seed, PROFILE_RUNS) if profile_mode
                   else generate_schedule(seed, len(specs), topology=topology))
        for key in ("version", "seed", "runs"):
            c.need(schedule.get(key) == rebuilt.get(key),
                   f"schedule {key} differs from the seeded generator")
        if executor is None and (root / "executor").is_file():
            executor = root / "executor"
        _check_environment(schedule, report, executor, violations)
        if backend != "inprocess":
            _check_campaign_topology(root, schedule, backend, topology, violations,
                                     profile=profile_mode)
            _check_manifest(root, violations)
    except Exception as error:
        return {"runs": 0, "seed": None, "violations": [f"schedule: {error}"]}
    for spec in specs:
        run_dir = root / f"run-{spec['index']:04d}"
        if not run_dir.is_dir():
            violations.append(f"run-{spec['index']:04d}: missing directory")
            continue
        try:
            profile = r4_profile(seed, spec["index"]) if profile_mode else None
            violations.extend(_check_run(spec, run_dir, executor=executor,
                                         backend=backend, profile=profile))
        except Exception as error:
            violations.append(f"run-{spec['index']:04d}: {error}")
    return {"runs": len(specs), "seed": seed, "violations": violations}


# R1 5.5: fields of metadata.json that take part in cross-pass comparison.
METADATA_PROJECTION = ("seed", "index", "source_revision", "source_manifest_sha256",
                       "executor_sha256", "topology", "job_id", "job_sha256", "fault",
                       "triggered", "final_state", "failure_reason", "placement",
                       "remote_roles", "kernel_sha256", "initramfs_sha256",
                       "initial_initramfs_sha256")
EXCLUDED_FROM_COMPARE = ("report.json", "pass-report.json", "manifest.sha256")


def _metadata_projection(value: dict[str, Any]) -> dict[str, Any]:
    projected = {key: value.get(key) for key in METADATA_PROJECTION}
    projected["locks"] = [{key: row.get(key) for key in ("host", "phase", "state", "run_index")}
                          for row in value.get("locks", ()) if type(row) is dict]
    projected["observations"] = [{key: row.get(key) for key in ("event", "role", "frame_sha256")}
                                 for row in value.get("observations", ()) if type(row) is dict]
    return projected


def _topology_projection(value: dict[str, Any]) -> dict[str, Any]:
    """Stable topology: roles, placement and B images; never endpoints, ports or paths."""
    def stable(item: dict[str, Any]) -> dict[str, Any]:
        return {"coordinator": item.get("coordinator"), "placement": item.get("placement"),
                "roles": sorted(item.get("guest_ips", {})),
                "remote_roles": sorted(item.get("lan_links", {})),
                "host_b_boot_hashes": item.get("host_b_boot_hashes")}
    if "phases" not in value:  # campaign root record
        return value
    return {"run": stable(value), "phases": [
        {"phase": record.get("phase"), **stable(record.get("topology") or {})}
        for record in value.get("phases", ()) if type(record) is dict]}


def _comparable(root: Path) -> dict[str, Any]:
    """Map each evidence path to its deterministic comparison value (R1 5.5)."""
    values: dict[str, Any] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if (relative in EXCLUDED_FROM_COMPARE or relative.endswith("trace.cbor")
                or relative.startswith("raw/") or "/raw/" in relative):
            continue
        if relative.endswith("metadata.json"):
            values[relative] = _metadata_projection(json.loads(path.read_text()))
        elif relative.endswith("topology.json"):
            values[relative] = _topology_projection(json.loads(path.read_text()))
        else:
            values[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return values


def compare_campaigns(first: Path, second: Path) -> tuple[bool, list[str]]:
    """Compare the deterministic projection of two independent campaigns (R1 5.5).

    Wall-clock fields, lock and observation times, boot identifiers, transient
    endpoints, the summary report and the coordination trace are not compared.
    """
    first, second = Path(first), Path(second)
    differences = []
    try:
        if (first / "schedule.cbor").read_bytes() != (second / "schedule.cbor").read_bytes():
            differences.append("schedule differs")
        left, right = _comparable(first), _comparable(second)
    except (OSError, ValueError) as error:
        return False, [f"comparison failed: {error}"]
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
    run_parser.add_argument("--profile", action="store_true",
                            help="use the frozen R4 16-run T1/T2 profile")
    run_parser.add_argument("--config", type=Path)
    run_parser.add_argument("--kernel", type=Path)
    run_parser.add_argument("--placement")
    run_parser.add_argument("--accel", choices=("kvm", "tcg"), default="kvm")
    run_parser.add_argument("--timeout", type=int, default=1800)

    check_parser = subparsers.add_parser("check", help="replay and check one campaign")
    check_parser.add_argument("--output", type=Path, required=True)
    check_parser.add_argument("--compare", type=Path)
    check_parser.add_argument("--executor", type=Path)
    check_parser.add_argument("--backend", choices=BACKENDS,
                              help="bind the acceptance path to this backend (R4: dualhost)")

    args = parser.parse_args(argv)
    if args.command == "check":
        result = check_campaign(args.output, args.executor, expected_backend=args.backend)
        reproducible = None
        if args.compare is not None:
            second = check_campaign(args.compare, args.executor, expected_backend=args.backend)
            result["violations"].extend(
                f"compare campaign: {item}" for item in second["violations"])
            reproducible, differences = compare_campaigns(args.output, args.compare)
            result["violations"].extend(differences)
            if result["violations"]:
                reproducible = False
        print(format_report(result, reproducible))
        return 0 if not result["violations"] else 1

    topology = None if args.profile else args.topology
    if args.backend != "inprocess" or args.executor is not None:
        run_campaign(args.seed, args.runs, args.output, args.executor,
                     backend=args.backend, topology=topology, profile=args.profile,
                     config=args.config, kernel=args.kernel,
                     placement=args.placement, accel=args.accel, timeout=args.timeout)
        result = check_campaign(args.output, args.executor)
        print(format_report(result))
        return 0 if not result["violations"] else 1
    with tempfile.TemporaryDirectory(prefix="aclt-montecarlo-executor-") as temporary:
        executor = build_executor(Path(temporary) / "executor")
        run_campaign(args.seed, args.runs, args.output, executor,
                     backend=args.backend, topology=topology, profile=args.profile,
                     config=args.config, kernel=args.kernel,
                     placement=args.placement, accel=args.accel, timeout=args.timeout)
        result = check_campaign(args.output, executor)
    print(format_report(result))
    return 0 if not result["violations"] else 1


if __name__ == "__main__":
    raise SystemExit(main())