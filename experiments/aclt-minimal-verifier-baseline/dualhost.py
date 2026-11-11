#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run one stats job on two trusted physical hosts; SSH controls deployment."""

import argparse
import hashlib
import io
from ipaddress import IPv4Address
import json
from pathlib import Path
import platform
import re
import selectors
import shlex
import socket
import subprocess
import sys
import tarfile
import unicodedata

from baseline import LIMITS, PROBE, ROOT
from job import HEADER, VALUE
from lan import TIMEOUT, run_job, serve

HERE = Path(__file__).resolve().parent
SOURCE_PATHS = (
    str(HERE.relative_to(ROOT)), str(PROBE.relative_to(ROOT)), "tools/verification_profile",
    "tools/formal_migration/__init__.py", "tools/formal_migration/s2_transport.py",
)
COMPILE = ["rustc", "--edition=2021", "-D", "warnings", "-C", "overflow-checks=yes", "-O",
           str((PROBE / "src/independent_executor.rs").relative_to(ROOT)), "-o"]
TRANSCRIPT = tuple(f"{action}-{direction}.cbor" for action in ("SOLVE", "VERIFY")
                   for direction in ("request", "response"))


def environment() -> dict:
    return {
        "hostname": socket.gethostname(),
        "system": platform.platform(),
        "python": platform.python_version(),
        "unicode": unicodedata.unidata_version,
        "rustc": subprocess.check_output(["rustc", "--version"], text=True, timeout=15).strip(),
    }


def snapshot() -> tuple[str, bytes, dict]:
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain", "--", *SOURCE_PATHS], cwd=ROOT):
        raise RuntimeError("commit the experiment sources before capturing evidence")
    tracked = subprocess.check_output(["git", "ls-files", "-z", "--", *SOURCE_PATHS], cwd=ROOT)
    names = [name.decode() for name in tracked.split(b"\x00") if name]
    files = {name: (ROOT / name).read_bytes() for name in names}
    pins = {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}
    files["SOURCE-SHA256SUMS"] = "".join(f"{digest}  {name}\n" for name, digest in pins.items()).encode()
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode="w") as bundle:
        for name, raw in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(raw)
            member.mode = 0o600
            bundle.addfile(member, io.BytesIO(raw))
    return commit, archive.getvalue(), pins


def fixture() -> tuple[bytes, bytes, dict]:
    vectors = json.loads((PROBE / "tests/independent-vectors.json").read_text())["vectors"]
    stats = next(row for row in vectors if row["id"] == "stats")
    values = (3, -1, 5, 8, -2)
    data = HEADER.pack(2, len(values)) + b"".join(VALUE.pack(value) for value in values)
    return bytes.fromhex(stats["artifact_hex"]), data, {key: stats["limits"][key] for key in LIMITS}


def run(peer: str, address: str, remote_root: str, output: Path) -> None:
    output = output.resolve()
    output.mkdir(mode=0o700)
    commit, archive, pins = snapshot()
    (output / "source-sha256.json").write_text(json.dumps(pins, indent=2) + "\n")
    (output / "commit.txt").write_text(commit + "\n")
    a_env = environment()
    (output / "A-environment.json").write_text(json.dumps(a_env, indent=2) + "\n")

    ssh = ["ssh", "-F", "/dev/null", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes",
           "-o", "ConnectTimeout=10", peer]
    remote_dir = shlex.quote(remote_root)
    entry = str(Path(__file__).resolve().relative_to(ROOT))

    def capture(command: list[str], label: str, *, data: bytes | None = None) -> bytes:
        result = subprocess.run(command, input=data, capture_output=True, cwd=ROOT, timeout=120)
        (output / f"{label}.log").write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"{label} exited {result.returncode}; see run log")
        return result.stdout

    def remote(command: list[str]) -> list[str]:
        return ssh + [f"cd {remote_dir} && {shlex.join(command)}"]

    capture(ssh + [f"umask 077; mkdir -- {remote_dir} && tar -xf - -C {remote_dir}"],
            "B-deploy", data=archive)
    capture(remote(["sha256sum", "--check", "SOURCE-SHA256SUMS"]), "B-source-check")
    b_env = json.loads(capture(remote(["python3", "-B", entry, "environment"]), "B-environment"))
    if a_env["hostname"] == b_env["hostname"]:
        raise RuntimeError("SSH peer reports the local hostname")

    executor = output / "executor"
    capture(COMPILE + [str(executor)], "A-build")
    capture(remote(COMPILE + ["executor"]), "B-build")
    a_binary_sha = hashlib.sha256(executor.read_bytes()).hexdigest()
    b_binary_sha = capture(remote(["sha256sum", "executor"]), "B-executor-sha256").decode().split()[0]
    a_wire = output / "A"
    a_wire.mkdir()
    args = ["python3", "-B", entry, "serve", address, "executor", "B"]
    with (output / "B-serve.log").open("wb") as error_log:
        worker = subprocess.Popen(remote(args), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=error_log)
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(worker.stdout, selectors.EVENT_READ)
                if not selector.select(timeout=20):
                    raise RuntimeError("B did not announce a listener")
            ready = worker.stdout.readline(4096)
            (output / "B-ready.json").write_bytes(ready)
            if not ready:
                raise RuntimeError("B exited before announcing a listener; see B-serve.log")
            port = json.loads(ready)["port"]
            with socket.create_connection((address, port), timeout=10) as connection:
                local_ip, peer_ip = connection.getsockname()[0], connection.getpeername()[0]
                if peer_ip != address or local_ip == peer_ip or IPv4Address(local_ip).is_loopback:
                    raise RuntimeError("expected an actual LAN connection between A and B")
                connection.settimeout(TIMEOUT)
                summary = run_job(connection, *fixture(), executor, a_wire)
            if worker.wait(timeout=15):
                raise RuntimeError("B worker failed; see B-serve.log")
        finally:
            if worker.poll() is None:
                worker.terminate()
                try:
                    worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=5)
            worker.stdout.close()

    archive = capture(remote(["tar", "-cf", "-", "-C", "B", *TRANSCRIPT]), "B-transcript.tar")
    b_wire = output / "B"
    b_wire.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as transcript:
        if transcript.getnames() != list(TRANSCRIPT):
            raise RuntimeError("unexpected B transcript inventory")
        for name in TRANSCRIPT:
            file = transcript.extractfile(name)
            if file is None or not transcript.getmember(name).isfile():
                raise RuntimeError("invalid B transcript member")
            raw = file.read()
            (b_wire / name).write_bytes(raw)
            if raw != (a_wire / name).read_bytes():
                raise RuntimeError(f"A/B transcript mismatch for {name}")
    if any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest for name, digest in pins.items()):
        raise RuntimeError("A sources changed during the run")
    summary.update(status="PASS", source_commit=commit, lan_transcript_equal=True,
                   executor_sha256={"A": a_binary_sha, "B": b_binary_sha})
    (output / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    driver = commands.add_parser("run")
    driver.add_argument("--peer", required=True, help="B SSH destination user@IPv4")
    driver.add_argument("--remote-root", required=True, help="new B directory /tmp/aclt-verifier-*")
    driver.add_argument("--output", required=True, type=Path)
    worker = commands.add_parser("serve")
    worker.add_argument("address")
    worker.add_argument("executor", type=Path)
    worker.add_argument("output", type=Path)
    commands.add_parser("environment")
    args = parser.parse_args()
    if args.command == "environment":
        print(json.dumps(environment()))
        return
    if args.command == "serve":
        serve(args.address, args.executor, args.output)
        return
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*@[0-9.]+", args.peer):
        parser.error("--peer must be user@IPv4")
    try:
        address = IPv4Address(args.peer.rsplit("@", 1)[1])
    except ValueError:
        parser.error("--peer must be user@IPv4")
    if address.is_loopback or address.is_unspecified or address.is_multicast:
        parser.error("--peer must name B's LAN address")
    if not re.fullmatch(r"/tmp/aclt-verifier-[A-Za-z0-9_.-]+", args.remote_root):
        parser.error("--remote-root must be a new /tmp/aclt-verifier-* directory")
    run(args.peer, str(address), args.remote_root, args.output)


if __name__ == "__main__":
    main()
