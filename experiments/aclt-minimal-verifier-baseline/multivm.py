#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the minimal-verifier job between QEMU guests on one physical host.

The guests have separate kernels, disks, and TCP stacks. They are still the same
physical machine, so host-level faults, memory, and the kernel image are shared.
"""

import argparse
from contextlib import ExitStack
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import socket
import stat
import subprocess
import sysconfig
import sys
import tarfile
from tempfile import TemporaryDirectory
import time

from baseline import ROOT, ask, solve
from dualhost import fixture, snapshot
from job import JOB_TAG, merge_job, prepare_job
from lan import decode_answer, operations, request
from multivm_job import MAX_LEAVES, fault_target, guest_ip, guest_roles, job_fixture, peer_operations, replay_many
from tools.verification_profile import codec
from tree import merge_tree, prepare_tree

HERE = Path(__file__).resolve().parent
PROBE = ROOT / "experiments/aclt-rir-stats-probe"
EXECUTOR_SOURCE = (PROBE / "src/independent_executor.rs").relative_to(ROOT)
COMPILE = ["rustc", "--edition=2021", "-D", "warnings", "-C", "overflow-checks=yes", "-O",
           "-C", "target-feature=+crt-static", str(EXECUTOR_SOURCE), "-o"]
GUEST_A = "10.0.3.1"
GUEST_B = "10.0.3.2"
JOB_PORT = 7400
DISK_BYTES = 64 * 1024 * 1024
BOOT_TIMEOUT = 300
APPLETS = ("sh", "mount", "ip", "cat", "echo", "poweroff", "sync", "sleep", "mkdir", "chmod",
           "ls", "dmesg", "grep", "sha256sum", "cmp", "dd", "df", "umount", "id", "kill", "rm")
INIT = """#!/bin/sh
export PATH=/bin:/usr/bin:/usr/sbin
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
chmod 1777 /tmp
IP=
for word in $(cat /proc/cmdline); do
    case "$word" in
        aclt_ip=*) IP=${word#aclt_ip=} ;;
    esac
done
[ -n "$IP" ] || { echo GUEST_CONFIG_MISSING; poweroff -f; }
mount -t ext4 /dev/vda /evidence || { echo EVIDENCE_MOUNT_FAILED; poweroff -f; }
busybox ip link set eth0 up || { echo NIC_LINK_FAILED; poweroff -f; }
busybox ip addr add "$IP" dev eth0 || { echo NIC_ADDR_FAILED; poweroff -f; }
echo "GUEST_START ip=$IP kernel=$(cat /proc/version)"
python3 /repo/experiments/aclt-minimal-verifier-baseline/guest_multivm.py
echo "GUEST_EXIT=$?"
sync
poweroff -f
"""


class RunError(RuntimeError):
    """The guest run did not produce comparable evidence."""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ldd_closure(binary: Path) -> list[Path]:
    """Paths of every shared object the binary needs, keeping the loader's own name."""
    try:
        output = subprocess.run(["ldd", str(binary)], check=True, capture_output=True, text=True).stdout
    except subprocess.CalledProcessError:
        return []
    paths = set()
    for line in output.splitlines():
        for word in line.split():
            if word.startswith("/") and Path(word).is_file():
                # keep the soname path the loader asks for instead of resolving it
                paths.add(Path(word))
    return sorted(paths)


def build_runtime(destination: Path) -> Path:
    """Assemble a minimal guest root from the host toolchain."""
    busybox = shutil.which("busybox")
    python = shutil.which("python3")
    if not busybox or not python:
        raise RunError("need busybox and python3 on the host to build the guest runtime")
    for tool in ("cpio", "mkfs.ext4", "debugfs", "qemu-system-x86_64"):
        if not shutil.which(tool):
            raise RunError(f"missing host tool: {tool}")
    root = destination
    (root / "bin").mkdir(parents=True)
    (root / "usr/bin").mkdir(parents=True)
    (root / "usr/lib").mkdir(parents=True)
    (root / "etc").mkdir()
    for name in ("proc", "sys", "dev", "tmp", "evidence"):
        (root / name).mkdir()
    (root / "tmp").chmod(0o1777)
    shutil.copy2(busybox, root / "bin/busybox")
    (root / "bin/busybox").chmod(0o755)
    for applet in APPLETS:
        link = root / "bin" / applet
        if not link.exists():
            link.symlink_to("busybox")
    interpreter = Path(python).resolve()
    shutil.copy2(interpreter, root / "usr/bin/python3")
    shutil.copy2(interpreter, root / "usr/bin" / interpreter.name)
    libraries = set(ldd_closure(interpreter))
    for module in sorted(Path(sysconfig.get_paths()["stdlib"]).glob("lib-dynload/*.so")):
        libraries.update(ldd_closure(module))
    for library in sorted(libraries):
        target = root / library.relative_to("/")
        if target.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(library, target)
    stdlib = Path(sysconfig.get_paths()["stdlib"])
    shutil.copytree(stdlib, root / f"usr/lib/python{sys.version_info.major}.{sys.version_info.minor}",
                    ignore=shutil.ignore_patterns("test", "idlelib", "tkinter", "turtledemo",
                                                  "ensurepip", "lib2to3", "site-packages",
                                                  "__pycache__", "*.pyc"))
    (root / "etc/passwd").write_text("root:x:0:0:root:/:/bin/sh\n", encoding="utf-8")
    (root / "etc/group").write_text("root:x:0:\n", encoding="utf-8")
    return root


def write_cpio(root: Path, destination: Path) -> None:
    """Write a newc archive with deterministic ordering."""
    def pad(stream, size: int) -> None:
        stream.write(b"\0" * (-size % 4))

    entries = [root, *sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix())]
    with destination.open("wb") as stream:
        for entry in entries:
            name = os.fsencode(entry.relative_to(root).as_posix())
            info = entry.lstat()
            if stat.S_ISLNK(info.st_mode):
                mode, body = stat.S_IFLNK | 0o777, os.fsencode(os.readlink(entry))
            elif stat.S_ISDIR(info.st_mode):
                mode, body = stat.S_IFDIR | (info.st_mode & 0o777), b""
            else:
                mode = stat.S_IFREG | (0o755 if info.st_mode & 0o111 else 0o644)
                body = entry.read_bytes()
            fields = (0, mode, 0, 0, 2 if stat.S_ISDIR(info.st_mode) else 1, 0,
                      len(body), 0, 0, 0, 0, len(name) + 1, 0)
            stream.write(b"070701" + "".join(f"{value:08x}" for value in fields).encode())
            stream.write(name + b"\0")
            pad(stream, 110 + len(name) + 1)
            stream.write(body)
            pad(stream, len(body))
        trailer = (0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, len("TRAILER!!!") + 1, 0)
        stream.write(b"070701" + "".join(f"{value:08x}" for value in trailer).encode())
        stream.write(b"TRAILER!!!\0")
        pad(stream, 110 + len("TRAILER!!!") + 1)


def stage_sources(destination: Path, commit: str, archive: bytes, pins: dict) -> str:
    destination.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        bundle.extractall(destination, filter="data")
    manifest = destination / "SOURCE-SHA256SUMS"
    expected = "".join(f"{digest}  {name}\n" for name, digest in pins.items()).encode()
    if manifest.read_bytes() != expected:
        raise RunError("source manifest does not match the host pins")
    for name, digest in pins.items():
        committed = subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)
        if sha256(destination / name) != digest or hashlib.sha256(committed).hexdigest() != digest:
            raise RunError(f"frozen source does not match {commit}: {name}")
    return sha256(manifest)


def pack_guest(staging: Path, executor: Path) -> Path:
    for name, mode in (("tmp", 0o1777), ("evidence", 0o700), ("proc", 0o755), ("sys", 0o755),
                       ("dev", 0o755)):
        directory = staging / name
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(mode)
    shutil.copy2(executor, staging / "executor")
    (staging / "executor").chmod(0o755)
    (staging / "init").write_text(INIT, encoding="utf-8")
    (staging / "init").chmod(0o755)
    archive = staging.parent / "guest.cpio"
    write_cpio(staging, archive)
    return archive


def make_disk(path: Path) -> None:
    with path.open("wb") as stream:
        stream.truncate(DISK_BYTES)
    subprocess.run(["mkfs.ext4", "-q", "-F", "-L", "evidence", str(path)], check=True)


def planned_leaf_count(budget: int | None, recursive: bool) -> int:
    """Plan the job on the host so both guests agree on its shape before boot."""
    if recursive:
        _, slices = prepare_tree(*fixture(), solve_budget=budget)
    else:
        _, slices = prepare_job(*fixture(), allocate_gas=True, solve_budget=budget)
    return len(slices)


def boot_arguments(role: str, kernel: Path, initramfs: Path, disk: Path, log: Path,
                   accel: str, memory: int, link: int, commit: str, budget: int | None,
                   recursive: bool, leaves: int, links: dict[str, int] | None = None,
                   interrupt: tuple[str, str] | None = None, retry_solve: bool = False) -> list[str]:
    ip = GUEST_A if role == "A" else GUEST_B
    peer = GUEST_B if role == "A" else GUEST_A
    if links is not None:
        ip = guest_ip(role)
    options = ["console=ttyS0", "panic=1", f"aclt_role={role}", f"aclt_ip={ip}/24",
               f"aclt_peer={peer}", f"aclt_port={JOB_PORT}", f"aclt_commit={commit}",
               f"aclt_leaves={leaves}"]
    if links is not None:
        options.append(f"aclt_guests={len(links) + 1}")
    if retry_solve:
        options.append("aclt_retry_solve=1")
    if interrupt is not None:
        mode, operation = interrupt
        options.extend((f"aclt_interrupt={operation}", f"aclt_interrupt_mode={mode}"))
    if budget is not None:
        options.append(f"aclt_budget={budget}")
    if recursive:
        options.append("aclt_recursive=1")
    netdev = (f"socket,id=n0,listen=127.0.0.1:{link}" if role == "B"
              else f"socket,id=n0,connect=127.0.0.1:{link}")
    commands = ["qemu-system-x86_64", "-accel", accel]
    commands += ["-cpu", "host"] if accel == "kvm" else ["-cpu", "max"]
    commands += ["-m", str(memory), "-smp", "2", "-display", "none", "-monitor", "none",
                 "-serial", f"file:{log}", "-no-reboot",
                 "-kernel", str(kernel), "-initrd", str(initramfs), "-append", " ".join(options),
                 "-drive", f"file={disk},format=raw,if=virtio"]
    device = "virtio-net-pci,netdev=n0"
    if links is not None:
        device += f",mac=52:54:00:ac:17:{ord(role):02x}"
        if role == "A":
            netdev = "hubport,id=n0,hubid=0"
            for peer_role, port in links.items():
                commands.extend(["-netdev", f"socket,id=link{peer_role},connect=127.0.0.1:{port}",
                                 "-netdev", f"hubport,id=hub{peer_role},hubid=0,netdev=link{peer_role}"])
        else:
            netdev = f"socket,id=n0,listen=127.0.0.1:{links[role]}"
    return commands + ["-netdev", netdev, "-device", device]


def terminate(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def launch(commands: list[str]) -> subprocess.Popen:
    return subprocess.Popen(commands, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.STDOUT)


def extract(image: Path, destination: Path) -> None:
    destination.mkdir(mode=0o700)
    subprocess.run(["debugfs", "-R", f"rdump / {destination}", str(image)], check=True,
                   capture_output=True)


def transcript(root: Path, leaf_count: int) -> dict[str, bytes]:
    expected = {f"{label}-{direction}.cbor" for _, _, label in operations(leaf_count)
                for direction in ("request", "response")}
    files = {path.name for pattern in ("*-request.cbor", "*-response.cbor") for path in root.glob(pattern)}
    if files != expected:
        raise RunError("unexpected guest transcript inventory")
    return {name: (root / name).read_bytes() for name in sorted(expected)}


def check_guests(a: dict, b: dict, *, commit: str, executor_sha256: str, source_manifest_sha256: str) -> None:
    if a["boot_id"] == b["boot_id"]:
        raise RunError("both guests report the same boot id")
    for report, role, local, peer in ((a, "A", GUEST_A, GUEST_B), (b, "B", GUEST_B, GUEST_A)):
        if report["role"] != role or report["local_socket_ip"] != local or report["peer_socket_ip"] != peer:
            raise RunError(f"guest {role} did not use its assigned role and TCP addresses")
        for field, expected in (("source_commit", commit), ("executor_sha256", executor_sha256),
                                ("source_manifest_sha256", source_manifest_sha256)):
            if report.get(field) != expected:
                raise RunError(f"guest {role} {field} differs from the host snapshot")


def check_run(a_root: Path, b_root: Path, *, leaf_count: int, recursive: bool,
              solve_budget: int | None = None) -> dict:
    frames = transcript(a_root, leaf_count)
    peer_frames = transcript(b_root, leaf_count)
    for name, raw in frames.items():
        if raw != peer_frames[name]:
            raise RunError(f"A/B transcript mismatch for {name}")

    artifact, data, limits = fixture()
    if recursive:
        plan, shards = prepare_tree(artifact, data, limits, solve_budget=solve_budget)
    else:
        plan, shards = prepare_job(artifact, data, limits, allocate_gas=True, solve_budget=solve_budget)
    if (len(shards) != leaf_count or (a_root / "plan.cbor").read_bytes() != plan
            or (a_root / "artifact.cbor").read_bytes() != artifact
            or (a_root / "original-input.bin").read_bytes() != data):
        raise RunError("guest input or plan differs from the host plan")
    job_id = codec.domain_hash(JOB_TAG, plan)
    submissions = []
    slices = {}
    for action, index, label in operations(leaf_count):
        shard = shards[index]
        request_bytes = frames[f"{label}-request.cbor"]
        response = codec.decode(frames[f"{label}-response.cbor"])
        if action == "SOLVE":
            codec.fields(response, ("job_id", "start", "answer"))
            if response["job_id"] != job_id or codec.uint(response["start"]) != shard.start:
                raise RunError("SOLVE response is for a different job or position")
            answer = decode_answer(response["answer"])
            name = "A-verdict" if index == 1 else f"A-verdict-{index}"
            receipt = codec.decode((a_root / f"{name}.cbor").read_bytes())
            expected_request = request(action, plan, artifact, shard)
            worker, verifier = "B", "A"
        else:
            answer = decode_answer(codec.decode(request_bytes)["answer"])
            receipt = response
            expected_request = request(action, plan, artifact, shard, answer)
            worker, verifier = "A", "B"
        if request_bytes != expected_request:
            raise RunError(f"{label} request differs from its frozen shard")
        submissions.append((answer, receipt))
        outcome = codec.decode(answer.outcome)
        gas_limit = codec.decode(shard.question)["limits"]["gas_limit"]
        if codec.uint(outcome["gas_used"]) != gas_limit:
            raise RunError(f"{label} metered gas differs from the planned cost")
        slices[index] = {
            "start": shard.start, "stop": shard.stop, "question_id": shard.question_id.hex(),
            "answer_digest": receipt["answer_digest"].hex(), "execution_host": worker,
            "verification_host": verifier, "status": receipt["status"], "gas_limit": gas_limit,
            "gas_used": outcome["gas_used"],
        }

    ordered = [slices[i] for i in range(leaf_count)]
    reference = codec.decode(solve(ask(artifact, data, limits), artifact, data).outcome)
    expected = {
        "job_id": job_id.hex(), "solve_budget": solve_budget, "slices": ordered,
        "reference_gas_used": reference["gas_used"],
        "allocated_solve_gas": sum(entry["gas_limit"] for entry in ordered),
        "reverse_order_equal": True,
    }
    if recursive:
        tree = merge_tree(plan, artifact, data, limits, submissions, solve_budget=solve_budget)
        reverse = merge_tree(plan, artifact, data, limits, submissions[::-1], solve_budget=solve_budget)
        output, reversed_output = tree.output, reverse.output
        if (tree.flat_output != output or reverse.flat_output != output
                or (a_root / "flat-output.bin").read_bytes() != output):
            raise RunError("flat output differs from the replayed tree output")
        merge_order = [list(pair) for pair in tree.merge_order]
        if json.loads((a_root / "tree-merge-order.json").read_text()) != merge_order:
            raise RunError("guest merge order differs from the replay")
        expected.update(flat_output_equal=True, tree_merge_order=merge_order,
                        leaf_solve_gas_used=tree.leaf_gas_used, flat_leaf_solve_gas_used=tree.flat_gas_used)
    else:
        output = merge_job(plan, artifact, data, limits, submissions, solve_budget=solve_budget, allocate_gas=True)
        reversed_output = merge_job(plan, artifact, data, limits, submissions[::-1],
                                    solve_budget=solve_budget, allocate_gas=True)
    if (reference["outcome"] != "OK" or output != reversed_output or output != reference["output"]
            or output != (a_root / "merged-output.bin").read_bytes()
            or output != (a_root / "reference-output.bin").read_bytes()):
        raise RunError("guest outputs differ from the host replay or reference")
    expected.update(output_sha256=hashlib.sha256(output).hexdigest(), output_bytes=len(output))
    summary = json.loads((a_root / "result.json").read_text(encoding="utf-8"))
    for key, value in expected.items():
        if key not in summary or summary[key] != value:
            raise RunError(f"guest summary {key} differs from the host replay")
    return {
        "lan_transcript_equal": True, "slices": leaf_count, "job_id": expected["job_id"],
        "output_sha256": expected["output_sha256"], "reference_gas_used": expected["reference_gas_used"],
        "allocated_solve_gas": expected["allocated_solve_gas"],
        "leaf_solve_gas_used": sum(entry["gas_used"] for entry in ordered), "recursive": recursive,
    }


def environment(accel: str) -> dict:
    return {"host": platform.platform(), "python": platform.python_version(),
            "qemu": subprocess.run(["qemu-system-x86_64", "--version"], check=True,
                                   capture_output=True, text=True).stdout.splitlines()[0],
            "accel": accel}


def check_topology(guests: dict, record: dict) -> None:
    roles = guest_roles(len(guests))
    if set(guests) != set(roles):
        raise RunError("unexpected guest identity inventory")
    boot_ids = set()
    for role in roles:
        guest = guests[role]
        if guest["role"] != role or guest["ip"] != guest_ip(role):
            raise RunError(f"guest {role} identity differs from the topology")
        if not guest["boot_id"] or guest["boot_id"] in boot_ids:
            raise RunError(f"guest {role} did not report a distinct boot id")
        boot_ids.add(guest["boot_id"])
        for field, expected in (("source_commit", record["commit"]),
                                ("executor_sha256", record["executor_sha256"]),
                                ("source_manifest_sha256", record["source_manifest_sha256"])):
            if guest[field] != expected:
                raise RunError(f"guest {role} {field} differs from the host snapshot")
    for peer in roles[1:]:
        guest = guests[peer]
        if (guest["local_socket_ip"], guest["peer_socket_ip"]) != (guest_ip(peer), guest_ip("A")):
            raise RunError(f"guest {peer} reported unexpected TCP addresses")
    expected = {peer: dict(local_ip=guest_ip("A"), peer_ip=guest_ip(peer)) for peer in roles[1:]}
    if guests["A"]["connections"] != expected:
        raise RunError("coordinator reported unexpected TCP addresses")


def read_timings(roots: dict[str, Path], leaves: int, *, retry: str | None = None,
                 missing_timing: tuple[str, str] | None = None) -> dict:
    roles = tuple(roots)
    timings = {}
    for role, root in roots.items():
        report = json.loads((root / "timings.json").read_text(encoding="utf-8"))
        required = ("operations_ns", "merge_ns", "reference_ns", "job_ns") if role == "A" else ("operations_ns",)
        codec.fields(report, required)
        operations_ns = report["operations_ns"]
        names = [name for _, _, name in peer_operations(roles, leaves, role) if (role, name) != missing_timing]
        if role == "A" and retry is not None:
            names.append(f"{retry}-retry")
        codec.fields(operations_ns, tuple(names))
        for duration in operations_ns.values():
            codec.uint(duration)
        for name in required[1:]:
            codec.uint(report[name])
        timings[role] = report
    return timings


def guest_links(roles: tuple[str, ...]) -> dict[str, int]:
    # Hold all reservations until the list is complete to prevent duplicate ports.
    with ExitStack() as stack:
        links = {}
        for role in roles[1:]:
            listener = stack.enter_context(socket.socket())
            listener.bind(("127.0.0.1", 0))
            links[role] = listener.getsockname()[1]
        return links


def check_interruption(roots: dict[str, Path], logs: dict[str, str], executor: Path, scratch: Path,
                       leaves: int, budget: int | None, mode: str, operation: str, *,
                       retry_solve: bool = False, recovered: bool = False, account: bool = False) -> dict:
    roles = guest_roles(len(roots))
    owner, _ = fault_target(roles, leaves, operation)
    marker = f"GUEST_INTERRUPT role={owner} operation={operation} mode={mode}"
    owner_exit = "GUEST_EXIT=75" if mode == "worker-exit" else "GUEST_EXIT=0"
    if mode == "drop-reply" and not (roots[owner] / f"{operation}-response.cbor").is_file():
        raise RunError("dropped reply was not retained by its worker")
    coordinator_exit = "GUEST_EXIT=0" if recovered else "GUEST_EXIT=1"
    if ([line for line in logs[owner].splitlines() if line.startswith("GUEST_INTERRUPT ")] != [marker]
            or owner_exit not in logs[owner].splitlines()
            or coordinator_exit not in logs["A"].splitlines()
            or (not recovered and f"GUEST_JOB_INCOMPLETE operation={operation}" not in logs["A"].splitlines())):
        raise RunError("expected interruption or coordinator failure marker is missing")
    return replay_many(roots, leaves, executor, scratch, solve_budget=budget, interrupted=operation,
                       retry_solve=retry_solve, account=account)


def run(args: argparse.Namespace) -> dict:
    roles = guest_roles(args.guests)
    many = len(roles) > 2
    recursive = args.recursive or many
    if many:
        leaves = args.leaves if args.leaves is not None else len(roles)
        if not len(roles) <= leaves <= MAX_LEAVES:
            raise RunError(f"leaf count must be between the guest count and {MAX_LEAVES}")
        prepare_tree(*job_fixture(leaves), solve_budget=args.solve_budget)
    else:
        if args.leaves is not None:
            raise RunError("explicit leaf count requires three or more guests")
        leaves = planned_leaf_count(args.solve_budget, recursive)
    if args.retry_solve and (not many or args.solve_budget is None):
        raise RunError("solve retry requires three or more guests and an explicit solve budget")
    target = None
    if args.interrupt is not None:
        if not many:
            raise RunError("interruption scenarios require three or more guests")
        target, _ = fault_target(roles, leaves, args.interrupt[1])
    output = args.output.resolve()
    if output.exists():
        raise RunError(f"output directory already exists: {output}")
    output.mkdir(mode=0o700)
    commit, archive, pins = snapshot()
    (output / "commit.txt").write_text(commit + "\n", encoding="utf-8")
    (output / "source-sha256.json").write_text(json.dumps(pins, indent=2) + "\n", encoding="utf-8")
    work = output / "work"
    work.mkdir(mode=0o700)
    kernel = args.kernel.resolve()
    if not kernel.is_file():
        raise RunError(f"kernel image not found: {kernel}")
    staging = work / "guest"
    source_manifest_sha256 = stage_sources(staging / "repo", commit, archive, pins)
    executor = output / "executor"
    subprocess.run(COMPILE + [str(executor)], cwd=staging / "repo", check=True, capture_output=True)
    executor.chmod(0o755)
    runtime = (args.runtime_root.resolve() if args.runtime_root
               else build_runtime(work / "runtime"))
    runtime_archive = work / "runtime.cpio"
    write_cpio(runtime, runtime_archive)
    guest_archive = pack_guest(staging, executor)
    initramfs = output / "guest.cpio.gz"
    with initramfs.open("wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=1,
                                                    mtime=0) as stream:
        stream.write(runtime_archive.read_bytes())
        stream.write(guest_archive.read_bytes())
    accel = args.accel
    if accel == "kvm" and not os.access("/dev/kvm", os.R_OK | os.W_OK):
        accel = "tcg"
    record = {"commit": commit, "kernel": str(kernel), "kernel_sha256": sha256(kernel),
              "initramfs_sha256": sha256(initramfs), "executor_sha256": sha256(executor),
              "source_manifest_sha256": source_manifest_sha256,
              "runtime_root": None if args.runtime_root else "host build",
              "runtime_files": sum(1 for _ in runtime.rglob("*")),
              "environment": environment(accel), "solve_budget": args.solve_budget,
              "recursive": recursive, "guest_count": len(roles)}
    links = guest_links(roles)
    record["planned_leaves"] = leaves
    if many:
        record["topology"] = {"coordinator": "A", "guest_ips": {role: guest_ip(role) for role in roles},
                              "transport": "QEMU hub with host-loopback socket links"}
    logs = {role: output / f"{role}-serial.log" for role in roles}
    disks = {role: work / f"{role}.img" for role in roles}
    for disk in disks.values():
        make_disk(disk)
    processes = {}
    started = time.monotonic()
    try:
        for role in (*roles[1:], roles[0]):
            if role == roles[0]:
                time.sleep(1)
            processes[role] = launch(boot_arguments(
                role, kernel, initramfs, disks[role], logs[role], accel, args.memory, links[roles[1]],
                commit, args.solve_budget, recursive, leaves, links if many else None,
                args.interrupt if role == target else None, args.retry_solve))
        deadline = started + BOOT_TIMEOUT
        for role, process in processes.items():
            try:
                process.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                raise RunError(f"guest {role} did not finish within {BOOT_TIMEOUT}s")
            if process.returncode:
                raise RunError(f"guest {role} exited {process.returncode}")
    finally:
        for process in processes.values():
            terminate(process)
    record["seconds"] = round(time.monotonic() - started, 2)
    serial = {role: log.read_text(encoding="utf-8", errors="replace") for role, log in logs.items()}
    (output / "init").write_text(INIT, encoding="utf-8")
    roots = {}
    for role in roles:
        # The guest mounts its disk at /evidence and writes /evidence/<role>.
        disk_root = output / role
        extract(disks[role], disk_root)
        roots[role] = disk_root / role
    failure_path = roots["A"] / "failure.json"
    recovered = many and args.interrupt is not None and (roots["A"] / "result.json").is_file()
    if args.interrupt is not None:
        mode, operation = args.interrupt
        with TemporaryDirectory(prefix="replay-", dir=work) as replay:
            failure = check_interruption(roots, serial, executor, Path(replay), leaves, args.solve_budget,
                                         mode, operation, retry_solve=args.retry_solve,
                                         recovered=recovered, account=True)
        record.update(failure, fault_mode=mode, interrupted_transcript_replayed=True)
    elif many and failure_path.is_file():
        record.update(json.loads(failure_path.read_bytes()))
    if many and (roots["A"] / "solve-attempts.json").is_file():
        record["solve_accounting"] = json.loads((roots["A"] / "solve-attempts.json").read_bytes())
    if record.get("status") == "FAIL":
        (output / "failure.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        return record
    for role, log in serial.items():
        expected_exit = "GUEST_EXIT=75" if recovered and role == target and mode == "worker-exit" else "GUEST_EXIT=0"
        if expected_exit not in log.splitlines() or "Traceback" in log:
            raise RunError(f"guest {role} did not report a clean exit")
    for role in roles:
        if not (roots[role] / "guest.json").is_file():
            raise RunError(f"guest {role} left no guest.json on its evidence disk")
    guests = {role: json.loads((roots[role] / "guest.json").read_text(encoding="utf-8")) for role in roles}
    if many:
        check_topology(guests, record)
        if recovered:
            missing = (target, operation) if mode != "drop-reply" else None
            record["timings"] = read_timings(roots, leaves, retry=operation, missing_timing=missing)
        else:
            record["timings"] = read_timings(roots, leaves)
            with TemporaryDirectory(prefix="replay-", dir=work) as replay:
                record.update(replay_many(roots, leaves, executor, Path(replay), solve_budget=args.solve_budget,
                                          account=True))
    else:
        check_guests(guests["A"], guests["B"], commit=commit, executor_sha256=record["executor_sha256"],
                     source_manifest_sha256=source_manifest_sha256)
        record.update(check_run(roots["A"], roots["B"], leaf_count=leaves, recursive=recursive,
                                solve_budget=args.solve_budget))
    record["guests"] = guests
    record["status"] = "PASS"
    record["claim"] = (f"{len(roles)} guests, one physical host: guest-level protocol and role split only; "
                       "not physical host separation, not statistical independence")
    (output / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if not args.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    return record


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    runner = command.add_parser("run")
    runner.add_argument("--kernel", required=True, type=Path, help="guest bzImage")
    runner.add_argument("--output", required=True, type=Path, help="new evidence directory")
    runner.add_argument("--runtime-root", type=Path,
                        help="existing guest root with bin/busybox and usr/bin/python3")
    runner.add_argument("--solve-budget", type=int)
    runner.add_argument("--recursive", action="store_true")
    runner.add_argument("--guests", type=int, default=2, help="guest count; three or more use a tree job")
    runner.add_argument("--accel", choices=("kvm", "tcg"), default="kvm")
    runner.add_argument("--leaves", type=int, help="stats blocks in a tree job with three or more guests")
    runner.add_argument("--memory", type=int, default=1024)
    runner.add_argument("--keep-work", action="store_true")
    runner.add_argument("--retry-solve", action="store_true",
                        help="allow one budgeted coordinator retry of an eligible remote solve")
    runner.add_argument("--interrupt", nargs=2, metavar=("MODE", "OPERATION"),
                        help="inject worker-exit or disconnect after receiving SOLVE-i or VERIFY-i")
    args = parser.parse_args()
    if args.interrupt is not None and args.interrupt[0] not in ("worker-exit", "disconnect", "drop-reply"):
        runner.error("interruption mode must be worker-exit, disconnect, or drop-reply")
    try:
        record = run(args)
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2))
        raise SystemExit(1)
    if record["status"] == "FAIL":
        print(json.dumps({key: record[key] for key in ("status", "reason", "operation", "guest",
                                                       "leaf_index", "output_published")}, indent=2))
        raise SystemExit(1)
    print(json.dumps({key: record[key] for key in ("status", "seconds", "guest_count", "slices", "job_id",
                                                   "output_sha256", "lan_transcript_equal",
                                                   "initramfs_sha256")}, indent=2))


if __name__ == "__main__":
    main()
