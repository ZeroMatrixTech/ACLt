#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the minimal-verifier job between QEMU guests on one physical host.

The guests have separate kernels, disks, and TCP stacks. They are still the same
physical machine, so host-level faults, memory, and the kernel image are shared.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
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
import coordination
import dualhost_multivm
import general_vm
import sort_contract
from dualhost import fixture, snapshot
from job import JOB_TAG, admit_stats_root, merge_job, prepare_job
from lan import decode_answer, handle_request, operations, request
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


def build_runtime(destination: Path, *, capacity_sort=False) -> Path:
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
    if capacity_sort:
        (root / "usr/sbin").mkdir()
        for name in ("mkfs.ext4", "debugfs", "dumpe2fs"):
            binary = shutil.which(name)
            if not binary:
                raise RunError(f"missing sort tool: {name}")
            shutil.copy2(binary, root / "usr/sbin" / name)
            libraries.update(ldd_closure(Path(binary)))
        config = Path("/etc/mke2fs.conf")
        if config.is_file():
            shutil.copy2(config, root / "etc" / config.name)
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
    job = fixture()
    admit_stats_root(*job)
    if recursive:
        _, slices = prepare_tree(*job, solve_budget=budget)
    else:
        _, slices = prepare_job(*job, allocate_gas=True, solve_budget=budget)
    return len(slices)


def boot_arguments(role: str, kernel: Path, initramfs: Path, disk: Path, log: Path,
                   accel: str, memory: int, link: int, commit: str, budget: int | None,
                   recursive: bool, leaves: int, links: dict[str, int] | None = None,
                   interrupt: tuple[str, str] | None = None, retry_solve: bool = False,
                   root_caps: dict | None = None, handoff: str | None = None,
                   general_options: tuple[str, ...] = (), coordination_port: int | None = None, lan_links: dict[str, str] | None = None) -> list[str]:
    lan_links = lan_links or {}
    ip = GUEST_A if role == "A" else GUEST_B
    peer = GUEST_B if role == "A" else GUEST_A
    if links is not None:
        ip = guest_ip(role)
    options = ["console=ttyS0", "panic=1", f"aclt_role={role}", f"aclt_ip={ip}/24",
               f"aclt_peer={peer}", f"aclt_port={JOB_PORT}", f"aclt_commit={commit}",
               f"aclt_leaves={leaves}"]
    if links is not None:
        options.append(f"aclt_guests={len(links) + 1}")
    options.extend(f"aclt_root_{name}={value}" for name, value in (root_caps or {}).items())
    if handoff is not None:
        options.append(f"aclt_handoff={handoff}")
    if retry_solve:
        options.append("aclt_retry_solve=1")
    if interrupt is not None:
        mode, operation = interrupt
        options.extend((f"aclt_interrupt={operation}", f"aclt_interrupt_mode={mode}"))
    if budget is not None:
        options.append(f"aclt_budget={budget}")
    if recursive:
        options.append("aclt_recursive=1")
    options.extend(general_options)
    netdev = (f"socket,id=n0,listen=127.0.0.1:{link}" if role == "B"
              else f"socket,id=n0,connect=127.0.0.1:{link}")
    commands = ["qemu-system-x86_64", "-accel", accel]
    commands += ["-cpu", "host"] if accel == "kvm" else ["-cpu", "max"]
    commands += ["-m", str(memory), "-smp", "2", "-display", "none", "-monitor", "none",
                 "-serial", f"file:{log}", "-no-reboot",
                 "-kernel", str(kernel), "-initrd", str(initramfs), "-append", " ".join(options),
                 "-drive", f"file={disk},format=raw,if=virtio"]
    device = "virtio-net-pci,netdev=n0"
    if handoff == "control":
        netdev = f"socket,id=n0,listen=127.0.0.1:{link}"
    if links is not None:
        device += f",mac=52:54:00:ac:17:{ord(role):02x}"
        if role == "A":
            netdev = "hubport,id=n0,hubid=0"
            for peer_role, port in links.items():
                backend = (f"stream,id=link{peer_role},server=off,addr.type=inet,"
                           f"addr.host={lan_links[peer_role]},addr.port={port}" if peer_role in lan_links else
                           f"socket,id=link{peer_role},connect=127.0.0.1:{port}")
                commands.extend(["-netdev", backend,
                                 "-netdev", f"hubport,id=hub{peer_role},hubid=0,netdev=link{peer_role}"])
        elif role in lan_links:
            netdev = f"stream,id=n0,server=on,addr.type=inet,addr.host={lan_links[role]},addr.port={links[role]}"
        else:
            netdev = f"socket,id=n0,listen=127.0.0.1:{links[role]}"
    if coordination_port is not None:
        commands.extend(["-device", "virtio-serial-pci",
                         "-chardev", f"socket,id=control,host=127.0.0.1,port={coordination_port}",
                         "-device", "virtserialport,chardev=control,name=aclt.coordination"])
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
            "accel": accel, "os": dualhost_multivm.os_release(), "kernel": platform.release(),
            "machine": platform.machine(), "kvm": dualhost_multivm.kvm_available()}


def utc_now() -> str:
    """A-side orchestration clock (R1 5.5): one UTC clock for locks, run window and observations."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def observe(record: dict, event: str, role: str | None = None, frame_sha256: str | None = None) -> None:
    record.setdefault("observations", []).append(
        {"event": event, "role": role, "frame_sha256": frame_sha256, "observed_at": utc_now()})


def check_topology(guests: dict, record: dict, *, incomplete=False) -> None:
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
        if incomplete and guest.get("transport_stopped") and guest["local_socket_ip"] is None:
            continue
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
                       retry_solve: bool = False, recovered: bool = False, account: bool = False,
                       root_caps: dict | None = None) -> dict:
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
                       retry_solve=retry_solve, account=account, root_caps=root_caps)


def check_handoff_checkpoint(roots: dict[str, Path], executor: Path, budget: int, root_caps: dict) -> None:
    artifact, data, limits = job_fixture(3, root_caps)
    plan, leaves = prepare_tree(artifact, data, limits, solve_budget=budget)
    shard = leaves[0]
    a, b = roots["A"], roots["B"]
    codec.need((a / "plan.cbor").read_bytes() == plan, "handoff plan differs")
    solve_request = request("SOLVE", plan, artifact, shard)
    codec.need((a / "SOLVE-0-request.cbor").read_bytes() == solve_request, "handoff solve request differs")
    answer_frame = codec.decode((a / "SOLVE-0-response.cbor").read_bytes())
    codec.fields(answer_frame, ("job_id", "start", "answer"))
    job_id = codec.domain_hash(JOB_TAG, plan)
    codec.need(answer_frame["job_id"] == job_id and answer_frame["start"] == shard.start,
               "handoff answer is for a different job or leaf")
    answer = decode_answer(answer_frame["answer"])
    verify_request = request("VERIFY", plan, artifact, shard, answer)
    _, receipt = handle_request(verify_request, "VERIFY", executor, leaf_index=0, leaf_count=3)
    codec.need(codec.decode(receipt)["status"] == "ACCEPT", "handoff answer was not accepted")
    for root in (a, b):
        codec.need((root / "VERIFY-0-request.cbor").read_bytes() == verify_request
                   and (root / "VERIFY-0-response.cbor").read_bytes() == receipt,
                   "handoff verification differs from replay")
    verify_frames = {"VERIFY-0-request.cbor", "VERIFY-0-response.cbor"}
    allowed = {"A": verify_frames | {"SOLVE-0-request.cbor", "SOLVE-0-response.cbor"},
               "B": verify_frames, "C": set()}
    for role, root in roots.items():
        frames = {path.name for pattern in ("*-request.cbor", "*-response.cbor") for path in root.glob(pattern)}
        codec.need(frames == allowed[role], f"unexpected dispatches before handoff on {role}")
        codec.need(not any((root / name).exists() for name in
                           ("result.json", "merged-output.bin", "flat-output.bin", "reference-output.bin")),
                   f"output published before handoff on {role}")
    outcome = codec.decode(answer.outcome)
    cap = codec.decode(shard.question)["limits"]["gas_limit"]
    codec.need(outcome["outcome"] == "OK" and outcome["gas_used"] == cap, "invalid handoff solve cost")
    expected = dict(solve_budget=budget, charged_gas=cap,
                    attempts=[dict(leaf_index=0, guest="A", attempt=1, gas_limit=cap, status="ANSWER",
                                   measured_gas=cap, charged_gas=cap)])
    codec.need(json.loads((a / "solve-attempts.json").read_bytes()) == expected, "handoff ledger differs")


def replay_handoff(before: dict[str, Path], after: dict[str, Path], executor: Path,
                   budget: int, root_caps: dict, scratch: Path) -> dict:
    check_handoff_checkpoint(before, executor, budget, root_caps)
    boot_ids = set()
    for phase, roots in (("before", before), ("after", after)):
        for root in roots.values():
            guest = json.loads((root / "guest.json").read_bytes())
            codec.need(guest.get("handoff_phase") == phase and guest["boot_id"] not in boot_ids,
                       f"unexpected guest identity in handoff phase: {phase}")
            boot_ids.add(guest["boot_id"])
    for name in ("SOLVE-0-request.cbor", "SOLVE-0-response.cbor", "VERIFY-0-request.cbor", "VERIFY-0-response.cbor",
                 "artifact.cbor", "original-input.bin", "plan.cbor", "root-question.cbor"):
        if (before["A"] / name).exists() or (after["A"] / name).exists():
            codec.need((before["A"] / name).read_bytes() == (after["A"] / name).read_bytes(),
                       f"handoff changed retained input {name}")
    for root in (after["B"], after["C"]):
        codec.need(not list(root.glob("*-0-*.cbor")), "accepted leaf was sent to a peer again")
    verification = scratch / "B"
    shutil.copytree(after["B"], verification)
    for path in before["B"].glob("VERIFY-0-*.cbor"):
        shutil.copyfile(path, verification / path.name)
    replay = scratch / "replay"
    replay.mkdir()
    return replay_many(after | {"B": verification}, 3, executor, replay, solve_budget=budget,
                       root_caps=root_caps, account=True)


def run_general(job, args, boot, executor, image, output, record, successor_image):
    is_sort = isinstance(job, sort_contract.SortJob)

    def check_sort_response(raw, response, root, unanswered):
        sort_contract.replay_response(job, raw, response, root, unanswered)

    if is_sort:
        control, serial = boot(output / "control", image, "control")
        if "GUEST_EXIT=0" not in serial["A"].splitlines() or "Traceback" in serial["A"]:
            raise RunError("capacity control guest failed")
        result = json.loads((control["A"] / "result.json").read_bytes())
        if result["status"] != "CAPACITY_EXHAUSTED":
            raise RunError("single guest did not demonstrate capacity exhaustion")
        record["single_guest_control"] = result

    scenario = getattr(args, "m9", None)
    suppressed_reply = bool(getattr(args, "general_inject", None)) and \
        general_vm.Injection.parse(args.general_inject).mode == "no_reply"
    authority = None
    if scenario in ("handoff", "overlap") or getattr(args, "coordinated", False):
        authority = coordination.Coordinator(job, output / "host-journal.cbor",
                                             output / "coordination.trace")

    def phase(directory, image, handoff=None, history=(), phase_job=job, source=None, guard=None):
        roots, serial = boot(directory, image, handoff, phase_job=phase_job, guard=guard)
        if any("GUEST_EXIT=0" not in log.splitlines() or "Traceback" in log for log in serial.values()):
            raise RunError("general job guest failed")
        guests = {role: json.loads((root / "guest.json").read_bytes()) for role, root in roots.items()}
        check_topology(guests, record)
        for role in sorted(guests):
            for hit in guests[role].get("injection", ()):
                observe(record, f"injected_{hit['mode']}", hit["role"], hit["request_sha256"])
            for row in guests[role].get("worker_exits", ()):
                if type(row) is dict:
                    observe(record, f"worker_exit_{row['exit_status']}", row["role"])
        for name in ("declaration", "plan", "execution"):
            if (roots["A"] / f"{name}.cbor").read_bytes() != getattr(phase_job, name):
                raise RunError(f"guest changed frozen {name}")
        journal = general_vm.replay(phase_job, roots, executor, history, source=source,
                                    check_response=check_sort_response if is_sort else None,
                                    suppressed_reply=suppressed_reply)
        if guard and guard.journal.events != journal.events:
            raise RunError("guest evidence differs from authoritative host journal")
        publication = roots["A"] / "publication.cbor"
        if journal.final is None:
            if publication.exists():
                raise RunError("incomplete run published an output")
        elif publication.read_bytes() != codec.encode(journal.final):
            raise RunError("publication differs from replay")
        return roots, guests, journal

    history = ()
    before_guests = None
    before = {}
    source = None
    mode = None
    if scenario == "reuse":
        source_job = general_vm.fixture(os.urandom(32), job.budget)
        source_guard = coordination.Coordinator(source_job, output / "source-journal.cbor",
                                                output / "source-coordination.trace")
        source_roots, _, source = phase(output / "source", image, phase_job=source_job,
                                        guard=source_guard)
        source_path = output / "source.cbor"
        shutil.copyfile(source_roots["A"] / "journal.cbor", source_path)
        image = successor_image(image, (source_path,))
        authority = coordination.Coordinator(job, output / "host-journal.cbor",
                                             output / "coordination.trace", source=source)
        mode = "reuse"
    if args.general_checkpoint:
        before, before_guests, journal = phase(output / "before", image, "before", guard=authority)
        if (before_guests["A"]["general_status"] != "CHECKPOINT"
                or len(journal.accepted) != args.general_checkpoint or journal.final is not None
                or journal.reserved):
            raise RunError("guest did not reach the requested quiescent checkpoint")
        history = journal.events
        files = [before["A"] / "journal.cbor"]
        if is_sort:
            owner, = (entry["worker"] for entry in journal.attempts.values()
                      if entry["state"] == "ACCEPTED")
            files.append(before[owner] / "delivery.img")
        image = successor_image(image, files)
        record["successor_initramfs_sha256"] = sha256(image)
    roots, guests, journal = phase(output / "after" if history else output, image,
                                   "after" if history else mode, history, source=source, guard=authority)
    if history and (journal.events[len(history)] != {"kind": "HANDOFF", "epoch": 1}
                    or {g["boot_id"] for g in guests.values()} & {g["boot_id"] for g in before_guests.values()}):
        raise RunError("successor did not take over after the checkpoint")
    result = guests["A"]["general_status"]
    expected = ("COORDINATION_PAUSED",) if scenario == "overlap" else ("PUBLISHED", "BUDGET_BLOCKED")
    if args.general_inject:
        expected += ("NO_REPLY",)
    if result not in expected or (result == "PUBLISHED") != (journal.final is not None):
        raise RunError(f"unexpected terminal state: {result}")
    if result == "BUDGET_BLOCKED":
        if not (args.general_drop or args.general_inject) or journal.charged + sum(
                cap for slot, cap in enumerate(job.caps) if slot not in journal.accepted) <= job.budget:
            raise RunError("guest reported a budget block with enough remaining gas")
    if is_sort:
        sort_contract.verify_retained(
            job, journal, lambda request: (before if history and request["epoch"] == 0 else roots)
            [sort_contract.PLACEMENT[request["slot"]][0]] / "delivery.img")
    overlap = scenario == "overlap"
    if overlap and (not authority.paused or journal.final is not None):
        raise RunError("overlap did not stop both dispatch and publication")
    if source is not None:
        if (job.declaration_id != source.job.declaration_id or job.plan_id == source.job.plan_id
                or journal.charged or journal.attempts or journal.final is None
                or journal.final["output"] != source.final["output"]):
            raise RunError("reused publication differs from its source or incurred solve costs")
        record["source_execution_id"] = source.job.execution_id.hex()
        record["source_charged_gas"] = source.charged
    return dict(status="PASS" if journal.final or overlap else "FAIL", general_status=result,
                declaration_id=job.declaration_id.hex(), plan_id=job.plan_id.hex(),
                execution_id=job.execution_id.hex(), **{job.charge_field: journal.charged},
                output=json.loads(json.dumps(journal.final["output"], default=bytes.hex))
                if journal.final else None,
                solve_order=[event["slot"] for event in journal.events if event["kind"] == "RESERVE"],
                acceptance_order=list(journal.accepted),
                handoff=bool(history), before_guests=before_guests, guests=guests,
                claim=("Guest-level trusted execution on two physical hosts of one operator; "
                       "the hosts are not independent failure domains"
                       if getattr(args, "dualhost_config", None) else
                       "Guest-level trusted execution on one physical host"))


def run(args: argparse.Namespace) -> dict:
    roles = guest_roles(args.guests)
    many = len(roles) > 2
    recursive = args.recursive or many
    root_caps = {name: value for name, value in (("gas_limit", args.root_gas_limit),
                                                ("output_limit", args.root_output_limit))
                 if value is not None}
    general = getattr(args, "general", False)
    general_six = bool(getattr(args, "general_six", False))
    general_inject = getattr(args, "general_inject", None)
    is_sort = getattr(args, "capacity_sort", False)
    job = None
    execution = None
    if general:
        if not many or args.handoff or args.interrupt or args.retry_solve or args.leaves or root_caps:
            raise RunError("general job requires at least three guests and its own fault and handoff options")
        if is_sort:
            if len(roles) != 3 or args.solve_budget is not None:
                raise RunError("capacity sort requires three guests and a frozen record budget")
            execution = sort_contract.SortJob(os.urandom(32))
            leaves = len(execution.tasks)
        else:
            leaves = len(general_vm.caps(general_six))
            default = general_vm.DEFAULT_BUDGET_SIX if general_six else general_vm.DEFAULT_BUDGET
            budget = args.solve_budget if args.solve_budget is not None else default
            args.solve_budget = budget
            nonce = os.urandom(32)
            if getattr(args, "general_nonce", None):
                try:
                    nonce = bytes.fromhex(args.general_nonce)
                except ValueError as error:
                    raise RunError("general nonce must be hexadecimal") from error
                if len(nonce) != 32:
                    raise RunError("general nonce must be 32 bytes")
            execution = general_vm.fixture(nonce, budget, flat=args.general_flat,
                                           six=general_six)
        if general_inject is not None:
            if args.general_drop or args.m9 or args.general_checkpoint:
                raise RunError("an injected fault cannot be combined with the drop, M9 or checkpoint scenarios")
            try:
                injection = general_vm.Injection.parse(general_inject)
            except ValueError as error:
                raise RunError(str(error)) from None
            if injection.slot >= leaves:
                raise RunError(f"injected slot must be below {leaves}")
    elif root_caps and not many:
        raise RunError("explicit whole-task limits require three or more guests")
    elif many:
        leaves = args.leaves if args.leaves is not None else len(roles)
        if not len(roles) <= leaves <= MAX_LEAVES:
            raise RunError(f"leaf count must be between the guest count and {MAX_LEAVES}")
        job = job_fixture(leaves, root_caps)
        admit_stats_root(*job)
        prepare_tree(*job, solve_budget=args.solve_budget)
    else:
        if args.leaves is not None:
            raise RunError("explicit leaf count requires three or more guests")
        leaves = planned_leaf_count(args.solve_budget, recursive)
    if args.retry_solve and (not many or args.solve_budget is None):
        raise RunError("solve retry requires three or more guests and an explicit solve budget")
    if args.handoff and (len(roles) != 3 or leaves != 3 or args.solve_budget is None
                         or args.interrupt is not None or args.retry_solve):
        raise RunError("handoff requires three guests, three leaves, a solve budget, and no other fault mode")
    target = None
    if args.interrupt is not None:
        if not many:
            raise RunError("interruption scenarios require three or more guests")
        target, _ = fault_target(roles, leaves, args.interrupt[1])
    settings = getattr(args, "dualhost_config", None)
    if settings and (not many or args.handoff):
        raise RunError("dual-host mode requires three or more guests and no nVM handoff mode")
    if bool(settings) != bool(getattr(args, "host_b_roles", None)):
        raise RunError("dual-host configuration and placement must be supplied together")
    output = args.output.resolve()
    if output.exists():
        raise RunError(f"output directory already exists: {output}")
    output.mkdir(mode=0o700)
    args.owns_output = True
    remote_roles = ()
    if settings:
        if settings.resolve().is_relative_to(ROOT):
            raise RunError("dual-host configuration must be kept outside the repository")
        settings, remote_roles = dualhost_multivm.config(settings, roles, args.host_b_roles)
    if many and not general and not args.handoff:
        write_json(output / "run-input.json", dict(schema="aclt.nvm-input/1", guests=len(roles), leaves=leaves,
                   budget=args.solve_budget, retry=bool(args.retry_solve), fault=args.interrupt,
                   host_b_roles=list(remote_roles), root_caps=root_caps))
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
    if args.executor is not None:
        shutil.copyfile(args.executor, executor)
    else:
        subprocess.run(COMPILE + [str(executor)], cwd=staging / "repo", check=True,
                       capture_output=True)
    executor.chmod(0o755)
    runtime = (args.runtime_root.resolve() if args.runtime_root
               else build_runtime(work / "runtime", capacity_sort=is_sort))
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
    if is_sort:
        record.update(solve_unit="records", solve_budget_records=execution.budget)
    links = guest_links(roles)
    record["planned_leaves"] = leaves
    if many:
        if job is not None:
            record["root_limits"] = job[2]
        record["topology"] = {"coordinator": "A", "guest_ips": {role: guest_ip(role) for role in roles},
                              "transport": "QEMU hub with host-loopback socket links"}
    session = None
    def boot(directory: Path, image: Path, handoff: str | None = None, *, phase_job=execution, guard=None):
        if settings:
            if session is not None:
                return boot_guests(directory, image, handoff, phase_job=phase_job,
                                   guard=guard, remote=session)
            with dualhost_multivm.experiment_lock(), dualhost_multivm.Remote(settings, remote_roles, output) as remote:
                return boot_guests(directory, image, handoff, phase_job=phase_job, guard=guard, remote=remote)
        return boot_guests(directory, image, handoff, phase_job=phase_job, guard=guard)

    def boot_guests(directory, image, handoff, *, phase_job, guard, remote=None):
        directory.mkdir(exist_ok=True)
        active = ("A",) if handoff == "control" else roles
        logs = {role: directory / f"{role}-serial.log" for role in active}
        disks = {role: work / f"{directory.name}-{role}.img" for role in active}
        for role in active:
            if role not in remote_roles:
                make_disk(disks[role])
        phase_links = dict(links)
        lan_links = {}
        if remote:
            hashes = remote.stage(kernel, image)
            phase_links.update(remote.call(action="ports"))
            lan_links = dict.fromkeys(remote_roles, settings["host_b_lan"])
            record["topology"].update(
                transport="QEMU hub with physical LAN and local socket links",
                placement={role: "B" if role in remote_roles else "A" for role in roles},
                host_b_environment=remote.environment, host_a_lock="held", host_b_boot_hashes=hashes)

        processes = {}
        started = time.monotonic()
        observe(record, f"{handoff or 'run'}_started", "A")
        general_options = ()
        if general:
            general_options = (
                f'aclt_execution_nonce={codec.decode(phase_job.execution)["nonce"].hex()}',
                f"aclt_capacity_sort={int(is_sort)}",
                f'aclt_general_order={args.general_order}',
                f'aclt_general_drop={int(args.general_drop)}',
                f'aclt_general_flat={int(not is_sort and codec.decode(phase_job.plan)["tree"] == list(range(leaves)))}',
                f'aclt_general_six={int(general_six)}',
                f'aclt_general_inject={args.general_inject or ""}',
                f'aclt_general_workers={getattr(args, "general_workers", None) or ""}',
                f'aclt_coordinated={int(guard is not None)}',
                f'aclt_general_checkpoint={args.general_checkpoint if handoff == "before" else 0}',
            )
        listener = pool = None
        try:
            if guard:
                listener = socket.create_server(("127.0.0.1", 0))
                listener.settimeout(30)
            for role in (*active[1:], active[0]):
                if role == active[0] and len(active) > 1:
                    if remote:
                        remote.wait_ready()
                    time.sleep(1)
                on_b = role in remote_roles
                argv = boot_arguments(
                    role, Path("kernel") if on_b else kernel, Path("guest.cpio.gz") if on_b else image,
                    Path(f"{role}.img") if on_b else disks[role],
                    Path(f"{role}-serial.log") if on_b else logs[role], accel, args.memory, phase_links[roles[1]],
                    commit, args.solve_budget, recursive, leaves, phase_links if len(active) > 1 and many else None,
                    args.interrupt if role == target else None, args.retry_solve, root_caps, handoff,
                    general_options, listener.getsockname()[1] if listener and role == "A" else None, lan_links)
                if on_b:
                    remote.call(action="launch", role=role, argv=argv, disk_size=DISK_BYTES)
                else:
                    processes[role] = launch(argv)
            if remote:
                record["topology"]["lan_links"] = remote.observe(
                    processes["A"], {role: phase_links[role] for role in remote_roles})
                write_json(output / f"host-topology-{handoff or 'run'}.json",
                           record["topology"])
            else:
                record["topology"].update(
                    placement={role: "A" for role in roles},
                    transport="QEMU hub with host-loopback socket links")
                write_json(output / f"host-topology-{handoff or 'run'}.json",
                           record["topology"])
            if guard:
                coordinator = processes["A"]
                guard.assign(coordinator)
                connection, _ = listener.accept()
                pool = ThreadPoolExecutor(max_workers=1)

                def admission():
                    with connection, connection.makefile("rb") as reader, connection.makefile("wb") as writer:
                        inject = None
                        intents = 0
                        if getattr(args, "m9", None) == "overlap":
                            def inject():
                                nonlocal intents
                                intents += 1
                                if intents == 5:
                                    coordination.conflicting_intent(guard, future=True)
                        coordination.serve(guard, coordinator, reader, writer, on_intent=inject)

                admission_result = pool.submit(admission)
            deadline = started + BOOT_TIMEOUT
            for role, process in processes.items():
                try:
                    process.wait(timeout=max(0, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    raise RunError(f"guest {role} did not finish within {BOOT_TIMEOUT}s")
                if process.returncode:
                    raise RunError(f"guest {role} exited {process.returncode}")
            if remote:
                for role in remote_roles:
                    remote.collect(role, disks[role], logs[role], deadline)
            if pool:
                admission_result.result(timeout=10)
        finally:
            for process in processes.values():
                terminate(process)
            if listener:
                listener.close()
            if pool:
                pool.shutdown()
        roots = {}
        for role in active:
            disk_root = directory / role
            extract(disks[role], disk_root)
            roots[role] = disk_root / role
        serial = {role: log.read_text(encoding="utf-8", errors="replace") for role, log in logs.items()}
        observe(record, f"{handoff or 'run'}_collected", "A")
        return roots, serial

    def successor_image(source: Path, files) -> Path:
        transfer = work / "transfer"
        checkpoint = transfer / "handoff"
        checkpoint.mkdir(parents=True)
        for path in files:
            shutil.copyfile(path, checkpoint / path.name)
        cpio = work / "handoff.cpio"
        write_cpio(transfer, cpio)
        successor = output / "successor.cpio.gz"
        shutil.copyfile(source, successor)
        with successor.open("ab") as raw, gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=1, mtime=0) as stream:
            stream.write(cpio.read_bytes())
        return successor

    started = time.monotonic()
    (output / "init").write_text(INIT, encoding="utf-8")
    if general:
        # R1 5.5: one A lock (and one B agent session) spans the whole run, every
        # phase included; lock states and the run window use the A-side UTC clock,
        # and B's lock state is confirmed over SSH when it is taken and released.
        locks = record["locks"] = []
        with dualhost_multivm.experiment_lock():
            locks.append({"host": "A", "phase": "run", "state": "held", "observed_at": utc_now()})
            if settings:
                with dualhost_multivm.Remote(settings, remote_roles, output) as remote:
                    if remote.environment.get("lock") != "held":
                        raise RunError("B agent did not report its experiment lock held")
                    locks.append({"host": "B", "phase": "run", "state": "held",
                                  "observed_at": utc_now()})
                    session = remote
                    record["started_at"] = utc_now()
                    record.update(run_general(execution, args, boot, executor, initramfs, output,
                                              record, successor_image))
                    record["ended_at"] = utc_now()
                    if remote.call(action="lock") != "held":
                        raise RunError("B agent lost its experiment lock")
                state = dualhost_multivm.probe_b_lock(settings)
                locks.append({"host": "B", "phase": "run", "state": state,
                              "observed_at": utc_now()})
                if state != "released":
                    raise RunError("B experiment lock was not released")
            else:
                record["started_at"] = utc_now()
                record.update(run_general(execution, args, boot, executor, initramfs, output,
                                          record, successor_image))
                record["ended_at"] = utc_now()
        locks.append({"host": "A", "phase": "run", "state": "released", "observed_at": utc_now()})
        record["seconds"] = round(time.monotonic() - started, 2)
        (output / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        if not args.keep_work:
            shutil.rmtree(work)
        return record
    if args.handoff:
        before, serial = boot(output / "before", initramfs, "before")
        if ("GUEST_HANDOFF accepted=1" not in serial["A"].splitlines()
                or "GUEST_EXIT=76" not in serial["A"].splitlines()
                or any("GUEST_EXIT=0" not in serial[role].splitlines() for role in roles[1:])):
            raise RunError("old guest did not stop at the handoff checkpoint")
        guests_before = {role: json.loads((root / "guest.json").read_bytes()) for role, root in before.items()}
        check_topology(guests_before, record)
        check_handoff_checkpoint(before, executor, args.solve_budget, root_caps)
        successor = successor_image(initramfs, (path for path in before["A"].iterdir()
                                                 if path.name != "guest.json"))
        roots, serial = boot(output / "after", successor, "after")
        guests_after = {role: json.loads((root / "guest.json").read_bytes()) for role, root in roots.items()}
        check_topology(guests_after, record)
        if any("GUEST_EXIT=0" not in log.splitlines() or "Traceback" in log for log in serial.values()):
            raise RunError("successor phase failed")
        with TemporaryDirectory(prefix="replay-", dir=work) as replay:
            record.update(replay_handoff(before, roots, executor, args.solve_budget, root_caps, Path(replay)))
        record.update(status="PASS", handoff=True, seconds=round(time.monotonic() - started, 2),
                      before_guests=guests_before, guests=guests_after, successor_initramfs_sha256=sha256(successor),
                      solve_accounting=json.loads((roots["A"] / "solve-attempts.json").read_bytes()))
        (output / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        if not args.keep_work:
            shutil.rmtree(work)
        return record
    roots, serial = boot(output, initramfs)
    record["seconds"] = round(time.monotonic() - started, 2)
    failure_path = roots["A"] / "failure.json"
    recovered = many and args.interrupt is not None and (roots["A"] / "result.json").is_file()
    if args.interrupt is not None:
        mode, operation = args.interrupt
        with TemporaryDirectory(prefix="replay-", dir=work) as replay:
            failure = check_interruption(roots, serial, executor, Path(replay), leaves, args.solve_budget,
                                         mode, operation, retry_solve=args.retry_solve,
                                         recovered=recovered, account=True, root_caps=root_caps)
        record.update(failure, fault_mode=mode, interrupted_transcript_replayed=True)
    elif many and failure_path.is_file():
        record.update(json.loads(failure_path.read_bytes()))
    ledger = roots["A"] / "solve-attempts.json"
    if many and ledger.is_file():
        record["solve_accounting"] = json.loads(ledger.read_bytes())
    if many and args.retry_solve and args.interrupt is None and record.get("status") != "FAIL":
        unanswered = [row for row in record["solve_accounting"]["attempts"] if row["status"] == "NO_REPLY"]
        if unanswered:
            if len(unanswered) != 1:
                raise RunError("expected at most one unanswered solve in a recovered job")
            operation = f"SOLVE-{unanswered[0]['leaf_index']}"
            target, _ = fault_target(roles, leaves, operation)
            recovered = True
            mode = None
            with TemporaryDirectory(prefix="replay-", dir=work) as replay:
                record.update(replay_many(roots, leaves, executor, Path(replay), solve_budget=args.solve_budget,
                                          interrupted=operation, retry_solve=True, account=True, root_caps=root_caps))
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
            response = roots[target] / f"{operation}-response.cbor"
            missing = None if response.is_file() else (target, operation)
            record["timings"] = read_timings(roots, leaves, retry=operation, missing_timing=missing)
        else:
            record["timings"] = read_timings(roots, leaves)
            with TemporaryDirectory(prefix="replay-", dir=work) as replay:
                record.update(replay_many(roots, leaves, executor, Path(replay), solve_budget=args.solve_budget,
                                          account=True, root_caps=root_caps))
    else:
        check_guests(guests["A"], guests["B"], commit=commit, executor_sha256=record["executor_sha256"],
                     source_manifest_sha256=source_manifest_sha256)
        record.update(check_run(roots["A"], roots["B"], leaf_count=leaves, recursive=recursive,
                                solve_budget=args.solve_budget))
    record["guests"] = guests
    record["status"] = "PASS"
    record["claim"] = (f"{len(roles)} guests, one physical host: guest-level protocol and role split only; "
                       "not physical host separation, not statistical independence")
    if settings:
        record["claim"] = "Two trusted physical hosts, QEMU guest traffic over the observed LAN links"
    (output / "result.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    if not args.keep_work:
        shutil.rmtree(work, ignore_errors=True)
    return record


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def replay_fixed(output, executor):
    """Recompute the fixed nVM case using only retained artifacts and the pinned executor."""
    inputs = json.loads((output / "run-input.json").read_bytes())
    codec.need(inputs["schema"] == "aclt.nvm-input/1", "unknown nVM evidence input")
    roles = guest_roles(inputs["guests"])
    roots = {role: output / role / role for role in roles}
    ledger_path = roots["A"] / "solve-attempts.json"
    report = output / "result.json"
    retained = json.loads((report if report.exists() else output / "failure.json").read_bytes())
    codec.need(sha256(executor) == retained["executor_sha256"], "replay executor digest differs")
    codec.need((output / "commit.txt").read_text().strip() == retained["commit"], "source revision differs")
    pins = json.loads((output / "source-sha256.json").read_bytes())
    manifest = "".join(f"{digest}  {name}\n" for name, digest in pins.items()).encode()
    codec.need(hashlib.sha256(manifest).hexdigest() == retained["source_manifest_sha256"],
               "source manifest digest differs")
    fault = inputs["fault"]
    recovered = (roots["A"] / "result.json").is_file()
    guests = {role: json.loads((root / "guest.json").read_bytes()) for role, root in roots.items()}
    check_topology(guests, retained, incomplete=not recovered)
    dualhost_multivm.check_lan(retained, roles, inputs["host_b_roles"])
    budget, root_caps = inputs["budget"], inputs["root_caps"]
    leaves = inputs["leaves"]
    with TemporaryDirectory(prefix="aclt-nvm-replay-") as scratch:
        if fault:
            logs = {role: (output / f"{role}-serial.log").read_text() for role in roles}
            replayed = check_interruption(roots, logs, executor, Path(scratch), leaves, budget, *fault,
                                          retry_solve=inputs["retry"], recovered=recovered,
                                          account=True, root_caps=root_caps)
        else:
            codec.need(recovered, "unplanned stop has no verified publication")
            replayed = replay_many(roots, leaves, executor, Path(scratch), solve_budget=budget,
                                   retry_solve=inputs["retry"], account=True, root_caps=root_caps)
    codec.need((replayed.get("status") != "FAIL") == recovered, "publication disagrees with replay")
    ledger = json.loads(ledger_path.read_bytes()) if ledger_path.exists() else None
    return dict(schema="aclt.nvm-outcome/1", status="PUBLISHED" if recovered else "SAFE_STOP",
                requested_fault=fault, triggered_fault=fault, output_published=recovered,
                accounting=ledger, job_id=replayed["job_id"], output_sha256=replayed.get("output_sha256"),
                evidence={"run_input": "run-input.json", "transcript_roots": {
                          role: f"{role}/{role}" for role in roles},
                          "report": "result.json" if recovered else "failure.json"})



def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    replay = command.add_parser("replay")
    replay.add_argument("--evidence", type=Path, required=True)
    replay.add_argument("--executor", type=Path, required=True)
    runner = command.add_parser("run")
    runner.add_argument("--dualhost-config", type=Path)
    runner.add_argument("--host-b-roles")
    runner.add_argument("--kernel", required=True, type=Path, help="guest bzImage")
    runner.add_argument("--output", required=True, type=Path, help="new evidence directory")
    runner.add_argument("--runtime-root", type=Path,
                        help="existing guest root with bin/busybox and usr/bin/python3")
    runner.add_argument("--solve-budget", type=int)
    runner.add_argument("--executor", type=Path, help="use a prebuilt guest executor")
    runner.add_argument("--recursive", action="store_true")
    runner.add_argument("--guests", type=int, default=2, help="guest count; three or more use a tree job")
    runner.add_argument("--accel", choices=("kvm", "tcg"), default="kvm")
    runner.add_argument("--leaves", type=int, help="stats blocks in a tree job with three or more guests")
    runner.add_argument("--root-gas-limit", type=int, help="whole-task gas cap for a three-or-more guest job")
    runner.add_argument("--root-output-limit", type=int, help="whole-task output bytes for a three-or-more guest job")
    runner.add_argument("--memory", type=int, default=1024)
    runner.add_argument("--handoff", action="store_true", help="replace the coordinator after the first accepted leaf")
    runner.add_argument("--keep-work", action="store_true")
    runner.add_argument("--m9", choices=("reuse", "handoff", "overlap"), help="run a contract closure scenario")
    runner.add_argument("--general", action="store_true", help="run the integer-vector contract fixture")
    runner.add_argument("--capacity-sort", action="store_true", help="run the fixed capacity-sort contract fixture")
    runner.add_argument("--general-order", choices=("0123", "3102", "1023", "012345", "543210", "01", "10"),
                        default="0123", help="priority by slot; dependencies always gate dispatch")
    runner.add_argument("--general-drop", action="store_true", help="drop B's first solve reply")
    runner.add_argument("--general-flat", action="store_true", help="use the alternative flat merge plan")
    runner.add_argument("--general-six", action="store_true", help="use the four-guest six-leaf contract fixture")
    runner.add_argument("--general-nonce", metavar="HEX", help="frozen 32-byte general execution nonce")
    runner.add_argument("--general-inject", metavar="MODE:SLOT:LOSS",
                        help="abort a remote SOLVE reply: no_reply, worker_exit or tcp_disconnect")
    runner.add_argument("--coordinated", action="store_true",
                        help="route every general-job journal write through the host arbitration entry")
    runner.add_argument("--general-workers", metavar="ROLES",
                        help="coordinator-only layout: the worker roles in rotation order, e.g. BCD")
    runner.add_argument("--general-checkpoint", choices=(0, 1, 2), type=int, default=0,
                        help="handoff after this many accepted slots")
    runner.add_argument("--retry-solve", action="store_true",
                        help="allow one budgeted coordinator retry of an eligible remote solve")
    runner.add_argument("--interrupt", nargs=2, metavar=("MODE", "OPERATION"),
                        help="inject worker-exit or disconnect after receiving SOLVE-i or VERIFY-i")
    args = parser.parse_args()
    if args.command == "replay":
        try:
            result = replay_fixed(args.evidence, args.executor)
        except (RuntimeError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
            print(json.dumps(dict(status="RUN_ERROR", reason=str(error))))
            raise SystemExit(2)
        print(json.dumps(result, indent=2))
        return
    if args.m9:
        if (args.capacity_sort or args.general_drop or args.general_flat or args.general_checkpoint
                or args.general_inject):
            runner.error("M9 scenarios choose their own family, plan and checkpoint")
        args.general = True
        args.general_flat = args.m9 == "reuse"
        args.general_checkpoint = int(args.m9 == "handoff")
    if args.capacity_sort:
        if args.general or args.general_flat or args.general_checkpoint > 1:
            runner.error("capacity sort has its own fixed plan and one-slot checkpoint")
        args.general = True
        if args.general_order == "0123":
            args.general_order = "10" if args.general_drop else "01"
        if args.general_order not in ("01", "10"):
            runner.error("capacity sort order must be 01 or 10")
    elif args.general_order in ("01", "10"):
        runner.error("two-slot order requires --capacity-sort")
    if not args.general and (args.general_drop or args.general_flat or args.general_checkpoint
                             or args.general_six or args.general_inject is not None
                             or args.general_order != "0123"):
        runner.error("general scenario options require --general")
    if args.general_six:
        if args.general_order in ("01", "10"):
            runner.error("six leaves require a general order, not the capacity-sort order")
        if len(args.general_order) != 6:
            runner.error("six leaves require a six-slot --general-order such as 012345")
    elif args.general_order in ("012345", "543210"):
        runner.error("a six-slot order requires --general-six")
    if args.general_inject is not None:
        try:
            general_vm.Injection.parse(args.general_inject)
        except ValueError as error:
            runner.error(str(error))
    if args.coordinated and not args.general:
        runner.error("--coordinated needs --general")
    if args.general_workers is not None:
        workers = args.general_workers
        if (not args.general or args.capacity_sort or len(workers) < 3 or len(set(workers)) != len(workers)
                or "A" in workers or not set(workers) <= set(guest_roles(args.guests))):
            runner.error("--general-workers needs --general and three distinct non-coordinator guest roles")
    if args.general_drop and args.general_checkpoint and not args.general_order.startswith("1"):
        runner.error("start with slot 1 to drop before handoff")
    if args.interrupt is not None and args.interrupt[0] not in ("worker-exit", "disconnect", "drop-reply"):
        runner.error("interruption mode must be worker-exit, disconnect, or drop-reply")
    try:
        record = run(args)
        if (args.output / "run-input.json").is_file():
            outcome = replay_fixed(args.output, args.output / "executor")
            write_json(args.output / "outcome.json", outcome)
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        if getattr(args, "owns_output", False) and args.guests >= 3 and not args.general and not args.handoff:
            write_json(args.output / "outcome.json", dict(schema="aclt.nvm-outcome/1", status="RUN_ERROR",
                       requested_fault=args.interrupt, triggered_fault=None, output_published=None,
                       reason=type(error).__name__))

        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2))
        raise SystemExit(2 if args.guests >= 3 and not args.general and not args.handoff else 1)
    if args.general:
        print(json.dumps({key: record[key] for key in ("status", "execution_id", "charged_records" if args.capacity_sort else "charged_gas",
                                                       "output", "seconds")}, indent=2))
        raise SystemExit(0 if record["status"] == "PASS" else 1)
    if record["status"] == "FAIL":
        print(json.dumps({key: record[key] for key in ("status", "reason", "operation", "guest",
                                                       "leaf_index", "output_published")}, indent=2))
        raise SystemExit(1)
    print(json.dumps({key: record[key] for key in ("status", "seconds", "guest_count", "slices", "job_id",
                                                   "output_sha256", "lan_transcript_equal",
                                                   "initramfs_sha256")}, indent=2))


if __name__ == "__main__":
    main()
