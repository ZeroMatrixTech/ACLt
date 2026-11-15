#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Guest entry for the minimal-verifier VM run; reads its role from the kernel command line."""

from contextlib import ExitStack
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import sys
import time

sys.path[:0] = ["/repo", "/repo/experiments/aclt-minimal-verifier-baseline"]

import capacity_sort
import coordination
from dualhost import fixture
import sort_contract
import general_vm
from lan import TIMEOUT, handle_request, run_job, serve
from multivm_job import IncompleteExchange, assignments, guest_ip, guest_roles, label, peer_operations, run_many
from tools.formal_migration.s2_transport import receive, send
from tools.verification_profile import codec

EVIDENCE = Path("/evidence")
EXECUTOR = Path("/executor")
CONNECT_TIMEOUT = 60
FAULT_EXIT = 75
HANDOFF_EXIT = 76
HANDOFF_INPUT = Path("/handoff")


def options() -> dict:
    pairs = {}
    for word in Path("/proc/cmdline").read_text(encoding="utf-8").split():
        if "=" in word:
            key, value = word.split("=", 1)
            pairs[key] = value
    return pairs


def identity(role: str, pairs: dict) -> dict:
    root = Path("/repo")
    manifest = (root / "SOURCE-SHA256SUMS").read_bytes()
    for line in manifest.decode("utf-8").splitlines():
        digest, name = line.split("  ", 1)
        if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"guest source hash mismatch: {name}")
    report = {
        "role": role,
        "kernel": Path("/proc/version").read_text(encoding="utf-8").strip(),
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip(),
        "python": platform.python_version(),
        "ip": pairs["aclt_ip"].split("/")[0],
        "peer": pairs["aclt_peer"],
        "source_commit": pairs["aclt_commit"],
        "source_manifest_sha256": hashlib.sha256(manifest).hexdigest(),
        "executor_sha256": hashlib.sha256(EXECUTOR.read_bytes()).hexdigest(),
        "local_socket_ip": None,
        "peer_socket_ip": None,
    }
    return report


def connect(peer: str, port: int) -> socket.socket:
    deadline = time.monotonic() + CONNECT_TIMEOUT
    while True:
        try:
            return socket.create_connection((peer, port), timeout=10)
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(0.2)


class InjectedDisconnect(RuntimeError):
    """The experiment intentionally closed the worker's TCP connection."""


class HandoffCheckpoint(RuntimeError):
    """Stop after accepting the first leaf and before the next dispatch."""


def check_handoff_prefix(previous: Path, current: Path) -> None:
    for name in ("plan.cbor", "original-input.bin", "artifact.cbor", "solve-attempts.json",
                 "root-question.cbor"):
        if name == "root-question.cbor" and not ((previous / name).exists() or (current / name).exists()):
            continue
        codec.need((previous / name).read_bytes() == (current / name).read_bytes(),
                   f"handoff checkpoint differs: {name}")


def retained_exchange(previous: Path, name: str, raw: bytes) -> bytes:
    codec.need((previous / f"{name}-request.cbor").read_bytes() == raw,
               f"handoff request differs: {name}")
    return (previous / f"{name}-response.cbor").read_bytes()


def run_topology(role: str, pairs: dict, port: int, budget: int | None, leaves: int, report: dict) -> int:
    roles = guest_roles(int(pairs["aclt_guests"]))
    output = EVIDENCE / role
    coordinator = roles[0]
    operations_ns = {}
    elapsed_ns = {}
    handoff = pairs.get("aclt_handoff")
    if handoff:
        report["handoff_phase"] = handoff
    schedule = peer_operations(roles, leaves, role)
    if handoff:
        schedule = [op for op in schedule if (op[1] == 0) == (handoff == "before")]
    if role != coordinator:
        target = pairs.get("aclt_interrupt")
        mode = pairs.get("aclt_interrupt_mode")

        def interrupt(operation: str, connection: socket.socket) -> None:
            if operation != target:
                return
            report.update(local_socket_ip=connection.getsockname()[0], peer_socket_ip=connection.getpeername()[0])
            print(f"GUEST_INTERRUPT role={role} operation={operation} mode={mode}", flush=True)
            if mode == "worker-exit":
                (output / "timings.json").write_text(json.dumps(dict(operations_ns=operations_ns)) + "\n")
                (output / "guest.json").write_text(json.dumps(report) + "\n")
                os._exit(FAULT_EXIT)
            connection.shutdown(socket.SHUT_RDWR)
            raise InjectedDisconnect

        try:
            bounds = serve(guest_ip(role), EXECUTOR, output, leaf_count=leaves, port=port,
                           schedule=schedule, expected_peer=guest_ip(coordinator),
                           elapsed_ns=operations_ns, on_request=interrupt if target and mode != "drop-reply" else None,
                           before_send=interrupt if target and mode == "drop-reply" else None)
        except InjectedDisconnect:
            pass
        except OSError as error:
            report["transport_stopped"] = True
            (output / "guest.json").write_text(json.dumps(report, indent=2) + "\n")
            print(f"GUEST_TRANSPORT_STOP role={role} reason={error}", flush=True)
            return 1
        else:
            report.update(local_socket_ip=bounds["local_ip"], peer_socket_ip=bounds["peer_ip"])
    else:
        output.mkdir(mode=0o700)
        with ExitStack() as stack:
            connections = {peer: stack.enter_context(connect(guest_ip(peer), port)) for peer in roles[1:]}
            for connection in connections.values():
                connection.settimeout(TIMEOUT)
            report["connections"] = {
                peer: dict(local_ip=connection.getsockname()[0], peer_ip=connection.getpeername()[0])
                for peer, connection in connections.items()
            }
            local_plan = None
            scheduled = assignments(roles, leaves)

            def exchange(owner, action, index, raw):
                nonlocal local_plan
                if handoff == "after" and index == 0:
                    return retained_exchange(HANDOFF_INPUT, label(action, index), raw)
                if owner == coordinator:
                    started = time.monotonic_ns()
                    local_plan, result = handle_request(raw, action, EXECUTOR, prior_plan=local_plan,
                                                        leaf_index=index, leaf_count=leaves)
                    name = label(action, index)
                    if action == "SOLVE" and scheduled[index][0] != coordinator:
                        name += "-retry"
                    operations_ns[name] = time.monotonic_ns() - started
                    return result
                connection = connections[owner]
                send(connection, raw)
                return receive(connection)

            root_caps = {name: int(pairs[f"aclt_root_{name}"])
                         for name in ("gas_limit", "output_limit") if f"aclt_root_{name}" in pairs}
            def checkpoint(accepted: int) -> None:
                if accepted != 1:
                    return
                if handoff == "before":
                    raise HandoffCheckpoint
                check_handoff_prefix(HANDOFF_INPUT, output)

            try:
                summary = run_many(roles, leaves, output, exchange, solve_budget=budget, elapsed_ns=elapsed_ns,
                                   retry_solve=pairs.get("aclt_retry_solve") == "1", account=True, root_caps=root_caps,
                                   after_accept=checkpoint if handoff else None)
            except HandoffCheckpoint:
                (output / "guest.json").write_text(json.dumps(report) + "\n")
                print("GUEST_HANDOFF accepted=1", flush=True)
                return HANDOFF_EXIT
            except IncompleteExchange as error:
                (output / "guest.json").write_text(json.dumps(report, indent=2) + "\n")
                print(f"GUEST_JOB_INCOMPLETE operation={error}", flush=True)
                return 1
            print(f"GUEST_RESULT slices={len(summary['slices'])}", flush=True)
    (output / "timings.json").write_text(json.dumps(dict(operations_ns=operations_ns, **elapsed_ns), indent=2)
                                         + "\n", encoding="utf-8")
    (output / "guest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


def run_general(role, port, budget, report, pairs):
    output = EVIDENCE / role
    output.mkdir(mode=0o700)
    drop = pairs.get("aclt_general_drop") == "1"
    six = pairs.get("aclt_general_six") == "1"
    inject = general_vm.Injection.parse(pairs.get("aclt_general_inject"))
    nonce = bytes.fromhex(pairs["aclt_execution_nonce"])
    sort_job = sort_contract.SortJob(nonce) if pairs.get("aclt_capacity_sort") == "1" else None
    if sort_job is not None:
        if pairs.get("aclt_handoff") == "control":
            capacity_sort.single(output)
            report["general_status"] = "CAPACITY_EXHAUSTED"
            (output / "guest.json").write_text(json.dumps(report) + "\n", encoding="utf-8")
            return 0
    if role != "A":
        while True:
            try:
                report.update(general_vm.serve(role, port, EXECUTOR, output, drop_first_b=drop,
                                               sort_job=sort_job, inject=inject))
                break
            except general_vm.WorkerExit as exc:
                # The worker aborted after reading one request.  The guest supervisor keeps
                # serving so the coordinator sees a real remote EOF and can retry elsewhere.
                report.setdefault("worker_exits", []).append(exc.name)
                report.update(local_socket_ip=exc.local, peer_socket_ip=exc.peer)
                print(f"GUEST_WORKER_EXIT role={role} request={exc.name}", flush=True)
        report["fault_triggered"] = len(inject.hits) if inject is not None else 0
        if inject is not None:
            report["injection"] = inject.hits
    else:
        roles = guest_roles(int(pairs["aclt_guests"]))
        job = sort_job or general_vm.fixture(nonce, budget,
                                 flat=pairs.get("aclt_general_flat") == "1", six=six)
        reuse = None
        source = None
        if pairs.get("aclt_handoff") == "reuse":
            source_path = HANDOFF_INPUT / "source.cbor"
            source_execution = codec.decode(codec.decode(source_path.read_bytes())[0]["execution"])
            source_job = general_vm.fixture(source_execution["nonce"], source_execution["budget"],
                                            six=six)
            source = general_vm.source_journal(source_job, source_path, EXECUTOR)
            reuse = {slot: slot for slot in range(len(job.tasks))}
        order = tuple(int(slot) for slot in pairs["aclt_general_order"])
        previous = HANDOFF_INPUT / "journal.cbor" if pairs.get("aclt_handoff") == "after" else None

        report["connections"] = {}

        def remote(owner, raw, *, reply=True, stored=None):
            with connect(guest_ip(owner), port) as connection:
                connection.settimeout(general_vm.TIMEOUT)
                report["connections"][owner] = dict(local_ip=connection.getsockname()[0],
                                                     peer_ip=connection.getpeername()[0])
                if stored is not None:
                    return sort_contract.exchange_payload(connection, raw, stored)
                send(connection, raw)
                if reply:
                    return receive(connection)

        def exchange(owner, raw):
            name = general_vm.wire_name(raw)
            (output / f"{name}-request.cbor").write_bytes(raw)
            if sort_job is None:
                result = general_vm.handle(raw, EXECUTOR) if owner == role else remote(owner, raw)
            else:
                result = remote(owner, raw, stored=stored)
            (output / f"{name}-response.cbor").write_bytes(result)
            return result

        # Finish the operation stream even on a blocked budget or checkpoint.
        try:
            checkpoint = int(pairs.get("aclt_general_checkpoint", "0"))
            with ExitStack() as resources:
                placement = retry_worker = None
                if sort_job is not None:
                    stored = resources.enter_context(capacity_sort.memory_file())
                    placement = sort_contract.PLACEMENT
                    retry_worker = sort_contract.retry_on_same_worker
                    if previous:
                        retained = general_vm.Journal(job, previous, codec.decode(previous.read_bytes()))
                        sort_contract.verify_retained(
                            job, retained, lambda request: HANDOFF_INPUT / "delivery.img")
                journal_factory = general_vm.Journal
                if pairs.get("aclt_coordinated") == "1":
                    # Minimal initramfs has devtmpfs but no udev symlink rules.
                    device, = (entry.name for entry in Path("/sys/class/virtio-ports").iterdir()
                               if (entry / "name").read_text().strip() == "aclt.coordination")
                    port_path = f"/dev/{device}"
                    device = resources.enter_context(open(port_path, "r+b", buffering=0))
                    journal_factory = partial(coordination.GuestJournal, reader=device, writer=device)
                try:
                    journal, status = general_vm.run(
                        job, roles, output / "journal.cbor", exchange, order=order, previous=previous,
                        checkpoint=checkpoint, placement=placement, retry_worker=retry_worker,
                        retry_remote=inject is not None, source=source, reuse=reuse,
                        journal_factory=journal_factory,
                    )
                except coordination.CoordinationError:
                    path = output / "journal.cbor"
                    events = codec.decode(path.read_bytes()) if path.is_file() else ()
                    journal = general_vm.Journal(job, path, events)
                    if not path.is_file():
                        path.write_bytes(codec.encode(events))
                    status = "COORDINATION_PAUSED"
        finally:
            for peer in roles[1:]:
                remote(peer, general_vm.STOP, reply=False)
        (output / "declaration.cbor").write_bytes(job.declaration)
        (output / "plan.cbor").write_bytes(job.plan)
        (output / "execution.cbor").write_bytes(job.execution)
        if journal.final is not None:
            (output / "publication.cbor").write_bytes(codec.encode(journal.final))
        report["general_status"] = status
    (output / "guest.json").write_text(json.dumps(report) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    pairs = options()
    role = pairs["aclt_role"]
    port = int(pairs["aclt_port"])
    budget = int(pairs["aclt_budget"]) if "aclt_budget" in pairs else None
    recursive = pairs.get("aclt_recursive") == "1"
    leaves = int(pairs.get("aclt_leaves", "2"))
    print(f"GUEST_CONF role={role} port={port} leaves={leaves}", flush=True)
    report = identity(role, pairs)
    if "aclt_execution_nonce" in pairs:
        return run_general(role, port, budget, report, pairs)
    if "aclt_guests" in pairs:
        return run_topology(role, pairs, port, budget, leaves, report)
    if role == "B":
        bounds = serve(pairs["aclt_ip"].split("/")[0], EXECUTOR, EVIDENCE / "B", leaf_count=leaves,
                       port=port)
        report.update(local_socket_ip=bounds["local_ip"], peer_socket_ip=bounds["peer_ip"])
    else:
        artifact, data, limits = fixture()
        with connect(pairs["aclt_peer"], port) as connection:
            output = EVIDENCE / "A"
            output.mkdir(mode=0o700)
            report.update(local_socket_ip=connection.getsockname()[0],
                          peer_socket_ip=connection.getpeername()[0])
            (output / "guest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            summary = run_job(connection, artifact, data, limits, EXECUTOR, output,
                              solve_budget=budget, recursive=recursive)
        (output / "result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"GUEST_RESULT slices={len(summary['slices'])}", flush=True)
        return 0
    (EVIDENCE / "B" / "guest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
