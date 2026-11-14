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

from baseline import LIMITS, PROBE, ROOT, Verdict, solve, verify
from job import HEADER, VALUE, admit_stats_root, merge_job, prepare_job, record_verdict
from lan import TIMEOUT, decode_answer, handle_request, operations, request, run_job, serve
from tools.verification_profile import codec
from tree import prepare_tree

HERE = Path(__file__).resolve().parent
SOURCE_PATHS = (
    str(HERE.relative_to(ROOT)), str(PROBE.relative_to(ROOT)), "tools/verification_profile",
    "tools/formal_migration/__init__.py", "tools/formal_migration/s2_transport.py",
)
COMPILE = ["rustc", "--edition=2021", "-D", "warnings", "-C", "overflow-checks=yes", "-O",
           str((PROBE / "src/independent_executor.rs").relative_to(ROOT)), "-o"]


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


def run(peer: str, address: str, remote_root: str, output: Path, *, solve_budget: int | None = None,
        recursive: bool = False, reverse_schedule: bool = False) -> None:
    job = fixture()
    admit_stats_root(*job)
    if recursive:
        _, slices = prepare_tree(*job, solve_budget=solve_budget)
    else:
        _, slices = prepare_job(*job, allocate_gas=True, solve_budget=solve_budget)
    leaf_count = len(slices)
    transcript_names = tuple(f"{label}-{direction}.cbor" for _, _, label in operations(leaf_count)
                             for direction in ("request", "response"))
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
    args = ["python3", "-B", entry, "serve", address, "executor", "B", "--leaf-count", str(leaf_count)]
    if reverse_schedule:
        args.append("--reverse-schedule")
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
                summary = run_job(connection, *job, executor, a_wire, solve_budget=solve_budget,
                                  recursive=recursive, reverse_schedule=reverse_schedule)
                local_endpoint, peer_endpoint = connection.getsockname(), connection.getpeername()
            if worker.wait(timeout=15):
                raise RuntimeError("B worker failed; see B-serve.log")
            finished = worker.stdout.readline(4096)
        finally:
            if worker.poll() is None:
                worker.terminate()
                try:
                    worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    worker.kill()
                    worker.wait(timeout=5)
            worker.stdout.close()

    observed = json.loads(finished)
    if (observed["port"], observed["local_ip"], observed["peer_ip"]) != (
            peer_endpoint[1], peer_endpoint[0], local_endpoint[0]):
        raise RuntimeError("A/B LAN endpoint records disagree")
    (output / "topology.json").write_text(json.dumps(
        {"A": {"local": local_endpoint, "peer": peer_endpoint}, "B": observed}, indent=2) + "\n")
    archive = capture(remote(["tar", "-cf", "-", "-C", "B", *transcript_names]), "B-transcript.tar")
    b_wire = output / "B"
    b_wire.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as transcript:
        if transcript.getnames() != list(transcript_names):
            raise RuntimeError("unexpected B transcript inventory")
        for name in transcript_names:
            file = transcript.extractfile(name)
            if file is None or not transcript.getmember(name).isfile():
                raise RuntimeError("invalid B transcript member")
            raw = file.read()
            (b_wire / name).write_bytes(raw)
            if raw != (a_wire / name).read_bytes():
                raise RuntimeError(f"A/B transcript mismatch for {name}")
    if any(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest for name, digest in pins.items()):
        raise RuntimeError("A sources changed during the run")
    if not recursive:
        summary["accepted_order"] = json.loads((a_wire / "accepted-order.json").read_text())
    summary.update(status="PASS", source_commit=commit, lan_transcript_equal=True,
                   executor_sha256={"A": a_binary_sha, "B": b_binary_sha})
    (output / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


def replay_baseline(evidence: Path, executor: Path, output: Path, *, reverse_schedule: bool = False) -> dict:
    """Check both endpoints and exercise the production merge guard with saved submissions."""
    output.mkdir(mode=0o700)
    artifact, data, limits = fixture()
    plan, slices = prepare_job(artifact, data, limits, allocate_gas=True)
    a = evidence / "A"
    b = evidence / "B"
    for name, expected in (("plan.cbor", plan), ("artifact.cbor", artifact), ("original-input.bin", data)):
        codec.need((a / name).read_bytes() == expected, f"{name} differs from the baseline fixture")
    schedule = operations(len(slices))
    if reverse_schedule:
        schedule.reverse()
    accepted = []
    for action, index, label in schedule:
        shard = slices[index]
        raw = (a / f"{label}-request.cbor").read_bytes()
        reply = (a / f"{label}-response.cbor").read_bytes()
        codec.need(raw == (b / f"{label}-request.cbor").read_bytes()
                   and reply == (b / f"{label}-response.cbor").read_bytes(),
                   f"{label} transcripts differ")
        data_from_request = codec.decode(raw)
        answer = decode_answer(codec.decode(reply)["answer"] if action == "SOLVE" else data_from_request["answer"])
        expected_request = request(action, plan, artifact, shard, answer if action == "VERIFY" else None)
        codec.need(raw == expected_request, f"{label} request differs from frozen plan")
        _, recomputed = handle_request(raw, action, executor, prior_plan=plan, leaf_index=index,
                                      leaf_count=len(slices))
        codec.need(reply == recomputed, f"{label} reply differs from replay")
        if action == "SOLVE":
            receipt = codec.decode((a / "A-verdict.cbor").read_bytes())
            vote = verify(shard.question, artifact, shard.data, answer, executor=executor)
            codec.need(vote == Verdict("ACCEPT") and receipt == record_verdict(plan, shard.start, answer, vote),
                       "local verdict differs from replay")
        else:
            receipt = codec.decode(reply)
        accepted.append((answer, receipt))
    observed = json.loads((a / "accepted-order.json").read_text())
    codec.need(observed == [receipt["start"] for _, receipt in accepted], "recorded acceptance order differs")

    def compose(submissions):
        return merge_job(plan, artifact, data, limits, submissions, allocate_gas=True)

    combined = compose(accepted)
    reference = solve(admit_stats_root(artifact, data, limits), artifact, data)
    outcome = codec.decode(reference.outcome)
    codec.need(outcome["outcome"] == "OK" and combined == outcome["output"]
               == (a / "merged-output.bin").read_bytes() == (a / "reference-output.bin").read_bytes(),
               "replayed output differs from retained output or single-machine reference")
    (output / "merged-output.bin").write_bytes(combined)
    first, second = accepted
    cases = {
        "missing": (accepted[:-1], "missing slice position"),
        "misbound": ([(first[0], second[1]), second], "slice question mismatch"),
    }
    negatives = {}
    for case, (submissions, expected) in cases.items():
        directory = output / case
        directory.mkdir()
        # Store the actual mutated inputs to the production merge function.
        raw = codec.encode([{"answer": {"question_id": answer.question_id, "outcome": answer.outcome},
                             "receipt": receipt} for answer, receipt in submissions])
        (directory / "submissions.cbor").write_bytes(raw)
        try:
            candidate = compose(submissions)
        except codec.CodecError as error:
            codec.need(str(error) == expected, f"{case} reached a different refusal: {error}")
            negatives[case] = {"status": "REJECT", "reason": str(error), "merged_output": False}
        else:
            (directory / "unexpected-output.bin").write_bytes(candidate)
            raise RuntimeError(f"{case} unexpectedly produced merged output")
        (directory / "result.json").write_text(json.dumps(negatives[case], indent=2) + "\n")
    return {"status": "PASS", "accepted_order": observed, "output_bytes": len(combined),
            "output_sha256": hashlib.sha256(combined).hexdigest(), "negatives": negatives}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    driver = commands.add_parser("run")
    driver.add_argument("--peer", required=True, help="B SSH destination user@IPv4")
    driver.add_argument("--remote-root", required=True, help="new B directory /tmp/aclt-verifier-*")
    driver.add_argument("--output", required=True, type=Path)
    driver.add_argument("--solve-budget", type=int, help="optional total gas cap for the leaf solves")
    driver.add_argument("--reverse-schedule", action="store_true", help="reverse the order of LAN operations")
    driver.add_argument("--recursive", action="store_true", help="use the BFS tree with one leaf per block")
    worker = commands.add_parser("serve")
    worker.add_argument("address")
    worker.add_argument("executor", type=Path)
    worker.add_argument("output", type=Path)
    worker.add_argument("--leaf-count", type=int, default=2)
    worker.add_argument("--reverse-schedule", action="store_true")
    replay = commands.add_parser("replay-baseline", help="replay saved two-slice LAN frames offline")
    replay.add_argument("evidence", type=Path)
    replay.add_argument("executor", type=Path)
    replay.add_argument("output", type=Path)
    replay.add_argument("--reverse-schedule", action="store_true")
    commands.add_parser("environment")
    args = parser.parse_args()
    if args.command == "environment":
        print(json.dumps(environment()))
        return
    if args.command == "serve":
        schedule = operations(args.leaf_count)[::-1] if args.reverse_schedule else None
        observed = serve(args.address, args.executor, args.output, leaf_count=args.leaf_count, schedule=schedule)
        print(json.dumps(observed), flush=True)
        return
    if args.command == "replay-baseline":
        print(json.dumps(replay_baseline(args.evidence, args.executor, args.output,
                                         reverse_schedule=args.reverse_schedule), indent=2))
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
    run(args.peer, str(address), args.remote_root, args.output, solve_budget=args.solve_budget,
        recursive=args.recursive, reverse_schedule=args.reverse_schedule)


if __name__ == "__main__":
    main()
