#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Guest entry for the minimal-verifier VM run; reads its role from the kernel command line."""

from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import sys
import time

sys.path[:0] = ["/repo", "/repo/experiments/aclt-minimal-verifier-baseline"]

from dualhost import fixture
from lan import TIMEOUT, handle_request, run_job, serve
from multivm_job import IncompleteExchange, guest_ip, guest_roles, label, peer_operations, run_many
from tools.formal_migration.s2_transport import receive, send

EVIDENCE = Path("/evidence")
EXECUTOR = Path("/executor")
CONNECT_TIMEOUT = 60
FAULT_EXIT = 75


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


def run_topology(role: str, pairs: dict, port: int, budget: int | None, leaves: int, report: dict) -> int:
    roles = guest_roles(int(pairs["aclt_guests"]))
    output = EVIDENCE / role
    coordinator = roles[0]
    operations_ns = {}
    elapsed_ns = {}
    if role != coordinator:
        target = pairs.get("aclt_interrupt")
        mode = pairs.get("aclt_interrupt_mode")

        def interrupt(operation: str, connection: socket.socket) -> None:
            if operation != target:
                return
            print(f"GUEST_INTERRUPT role={role} operation={operation} mode={mode}", flush=True)
            if mode == "worker-exit":
                os._exit(FAULT_EXIT)
            connection.shutdown(socket.SHUT_RDWR)
            raise InjectedDisconnect

        try:
            bounds = serve(guest_ip(role), EXECUTOR, output, leaf_count=leaves, port=port,
                           schedule=peer_operations(roles, leaves, role), expected_peer=guest_ip(coordinator),
                           elapsed_ns=operations_ns, on_request=interrupt if target else None)
        except InjectedDisconnect:
            return 0
        except OSError as error:
            print(f"GUEST_TRANSPORT_STOP role={role} reason={error}", flush=True)
            return 1
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

            def exchange(owner, action, index, raw):
                nonlocal local_plan
                if owner == coordinator:
                    started = time.monotonic_ns()
                    local_plan, result = handle_request(raw, action, EXECUTOR, prior_plan=local_plan,
                                                        leaf_index=index, leaf_count=leaves)
                    operations_ns[label(action, index)] = time.monotonic_ns() - started
                    return result
                connection = connections[owner]
                send(connection, raw)
                return receive(connection)

            try:
                summary = run_many(roles, leaves, output, exchange, solve_budget=budget, elapsed_ns=elapsed_ns)
            except IncompleteExchange as error:
                print(f"GUEST_JOB_INCOMPLETE operation={error}", flush=True)
                return 1
            print(f"GUEST_RESULT slices={len(summary['slices'])}", flush=True)
    (output / "timings.json").write_text(json.dumps(dict(operations_ns=operations_ns, **elapsed_ns), indent=2)
                                         + "\n", encoding="utf-8")
    (output / "guest.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
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
