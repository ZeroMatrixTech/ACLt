#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Guest entry for the two-VM minimal-verifier run; reads its role from the kernel command line."""

import hashlib
import json
from pathlib import Path
import platform
import socket
import sys
import time

sys.path[:0] = ["/repo", "/repo/experiments/aclt-minimal-verifier-baseline"]

from dualhost import fixture
from lan import run_job, serve

EVIDENCE = Path("/evidence")
EXECUTOR = Path("/executor")
CONNECT_TIMEOUT = 60


def options() -> dict:
    pairs = {}
    for word in Path("/proc/cmdline").read_text(encoding="utf-8").split():
        if "=" in word:
            key, value = word.split("=", 1)
            pairs[key] = value
    return pairs


def identity(role: str, pairs: dict) -> dict:
    report = {
        "role": role,
        "kernel": Path("/proc/version").read_text(encoding="utf-8").strip(),
        "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip(),
        "python": platform.python_version(),
        "ip": pairs["aclt_ip"].split("/")[0],
        "peer": pairs["aclt_peer"],
        "source_commit": pairs["aclt_commit"],
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


def main() -> int:
    pairs = options()
    role = pairs["aclt_role"]
    port = int(pairs["aclt_port"])
    budget = int(pairs["aclt_budget"]) if "aclt_budget" in pairs else None
    recursive = pairs.get("aclt_recursive") == "1"
    print(f"GUEST_CONF role={role} port={port}", flush=True)
    if role == "B":
        bounds = serve(pairs["aclt_ip"].split("/")[0], EXECUTOR, EVIDENCE / "B", port=port)
        report = identity(role, pairs)
        report.update(local_socket_ip=bounds["local_ip"], peer_socket_ip=bounds["peer_ip"])
    else:
        artifact, data, limits = fixture()
        with connect(pairs["aclt_peer"], port) as connection:
            output = EVIDENCE / "A"
            output.mkdir(mode=0o700)
            report = identity(role, pairs)
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
