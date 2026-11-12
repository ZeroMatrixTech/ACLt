#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the minimal-verifier job between two QEMU guests on one physical host.

The guests have separate kernels, disks, and TCP stacks. They are still the same
physical machine, so host-level faults, memory, and the kernel image are shared.
"""

import argparse
import gzip
import hashlib
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
import time

from baseline import ROOT
from dualhost import SOURCE_PATHS, fixture, snapshot
from job import JOB_TAG
from lan import operations
from tools.verification_profile import codec

HERE = Path(__file__).resolve().parent
PROBE = ROOT / "experiments/aclt-rir-stats-probe"
EXECUTOR_SOURCE = PROBE / "src/independent_executor.rs"
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
python3 /repo/guest_multivm.py
echo "GUEST_EXIT=$?"
sync
poweroff -f
"""


class RunError(RuntimeError):
    """The two-guest run did not produce comparable evidence."""


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
            name = entry.relative_to(root).as_posix()
            info = entry.lstat()
            if stat.S_ISLNK(info.st_mode):
                mode, body = stat.S_IFLNK | 0o777, os.readlink(entry).encode()
            elif stat.S_ISDIR(info.st_mode):
                mode, body = stat.S_IFDIR | (info.st_mode & 0o777), b""
            else:
                mode = stat.S_IFREG | (0o755 if info.st_mode & 0o111 else 0o644)
                body = entry.read_bytes()
            fields = (0, mode, 0, 0, 2 if stat.S_ISDIR(info.st_mode) else 1, 0,
                      len(body), 0, 0, 0, 0, len(name) + 1, 0)
            stream.write(b"070701" + "".join(f"{value:08x}" for value in fields).encode())
            stream.write(name.encode() + b"\0")
            pad(stream, 110 + len(name) + 1)
            stream.write(body)
            pad(stream, len(body))
        trailer = (0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, len("TRAILER!!!") + 1, 0)
        stream.write(b"070701" + "".join(f"{value:08x}" for value in trailer).encode())
        stream.write(b"TRAILER!!!\0")
        pad(stream, 110 + len("TRAILER!!!") + 1)


def pack_guest(work: Path, commit: str, pins: dict, executor: Path) -> Path:
    staging = work / "guest"
    (staging / "repo").mkdir(parents=True)
    for name in pins:
        target = staging / "repo" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, target)
    for name, mode in (("tmp", 0o1777), ("evidence", 0o700), ("proc", 0o755), ("sys", 0o755),
                       ("dev", 0o755)):
        directory = staging / name
        directory.mkdir(parents=True, exist_ok=True)
        directory.chmod(mode)
    shutil.copy2(executor, staging / "executor")
    (staging / "executor").chmod(0o755)
    (staging / "init").write_text(INIT, encoding="utf-8")
    (staging / "init").chmod(0o755)
    archive = work / "guest.cpio"
    write_cpio(staging, archive)
    return archive


def make_disk(path: Path) -> None:
    with path.open("wb") as stream:
        stream.truncate(DISK_BYTES)
    subprocess.run(["mkfs.ext4", "-q", "-F", "-L", "evidence", str(path)], check=True)


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def boot_arguments(role: str, kernel: Path, initramfs: Path, disk: Path, log: Path,
                   accel: str, memory: int, link: int, commit: str, budget: int | None,
                   recursive: bool) -> list[str]:
    ip = GUEST_A if role == "A" else GUEST_B
    peer = GUEST_B if role == "A" else GUEST_A
    options = ["console=ttyS0", "panic=1", f"aclt_role={role}", f"aclt_ip={ip}/24",
               f"aclt_peer={peer}", f"aclt_port={JOB_PORT}", f"aclt_commit={commit}"]
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
                 "-drive", f"file={disk},format=raw,if=virtio",
                 "-netdev", netdev, "-device", "virtio-net-pci,netdev=n0"]
    return commands


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
    return {f"{label}-{direction}.cbor": (root / f"{label}-{direction}.cbor").read_bytes()
            for _, _, label in operations(leaf_count)
            for direction in ("request", "response")}


def check_guests(a: dict, b: dict) -> None:
    if a["boot_id"] == b["boot_id"]:
        raise RunError("both guests report the same boot id")
    if a["role"] != "A" or b["role"] != "B":
        raise RunError("guest roles are not A and B")
    for report, expected_local, expected_peer in ((a, GUEST_A, GUEST_B), (b, GUEST_B, GUEST_A)):
        if report["local_socket_ip"] != expected_local or report["peer_socket_ip"] != expected_peer:
            raise RunError(f"role {report['role']} did not use its own address over TCP")
    if a["source_commit"] != b["source_commit"]:
        raise RunError("guests disagree on the source commit")
    if a["executor_sha256"] != b["executor_sha256"]:
        raise RunError("guests ran different executor binaries")


def check_summary(summary: dict, root: Path) -> None:
    required = ("job_id", "output_sha256", "output_bytes", "reference_gas_used", "solve_budget",
                "allocated_solve_gas", "reverse_order_equal", "slices")
    missing = [key for key in required if key not in summary]
    if missing:
        raise RunError(f"summary is missing {missing}")
    plan = (root / "plan.cbor").read_bytes()
    if summary["job_id"] != codec.domain_hash(JOB_TAG, plan).hex():
        raise RunError("summary job id does not match the recorded plan")
    merged = (root / "merged-output.bin").read_bytes()
    if summary["output_sha256"] != hashlib.sha256(merged).hexdigest():
        raise RunError("summary output digest does not match the merged output")
    if summary["output_bytes"] != len(merged):
        raise RunError("summary output length does not match the merged output")
    if summary["reverse_order_equal"] is not True:
        raise RunError("reverse-order composition did not agree")
    if summary["allocated_solve_gas"] != sum(slice_["gas_limit"] for slice_ in summary["slices"]):
        raise RunError("allocated gas is not the sum of the shard limits")
    for index, entry in enumerate(summary["slices"]):
        worker, validator = ("B", "A") if index % 2 else ("A", "B")
        if entry["execution_host"] != worker or entry["verification_host"] != validator:
            raise RunError("slice did not use the expected compute/verify split")
        if entry["status"] != "ACCEPT":
            raise RunError(f"slice {entry['start']} was not accepted")


def check_run(a_root: Path, b_root: Path, *, leaf_count: int, recursive: bool) -> dict:
    frames = transcript(a_root, leaf_count)
    peer_frames = transcript(b_root, leaf_count)
    if sorted(frames) != sorted(peer_frames):
        raise RunError("the two guests captured different transcript inventories")
    for name, raw in frames.items():
        if raw != peer_frames[name]:
            raise RunError(f"A/B transcript mismatch for {name}")
    summary = json.loads((a_root / "result.json").read_text(encoding="utf-8"))
    check_summary(summary, a_root)
    report = {"lan_transcript_equal": True, "slices": len(summary["slices"]),
              "job_id": summary["job_id"], "output_sha256": summary["output_sha256"],
              "reference_gas_used": summary["reference_gas_used"],
              "allocated_solve_gas": summary["allocated_solve_gas"],
              "recursive": recursive}
    return report


def environment(accel: str) -> dict:
    return {"host": platform.platform(), "python": platform.python_version(),
            "qemu": subprocess.run(["qemu-system-x86_64", "--version"], check=True,
                                   capture_output=True, text=True).stdout.splitlines()[0],
            "accel": accel}


def run(args: argparse.Namespace) -> dict:
    output = args.output.resolve()
    if output.exists():
        raise RunError(f"output directory already exists: {output}")
    output.mkdir(mode=0o700)
    commit, _, pins = snapshot()
    (output / "commit.txt").write_text(commit + "\n", encoding="utf-8")
    (output / "source-sha256.json").write_text(json.dumps(pins, indent=2) + "\n", encoding="utf-8")
    work = output / "work"
    work.mkdir(mode=0o700)
    kernel = args.kernel.resolve()
    if not kernel.is_file():
        raise RunError(f"kernel image not found: {kernel}")
    executor = output / "executor"
    subprocess.run(COMPILE + [str(executor)], check=True, capture_output=True)
    executor.chmod(0o755)
    runtime = (args.runtime_root.resolve() if args.runtime_root
               else build_runtime(work / "runtime"))
    runtime_archive = work / "runtime.cpio"
    write_cpio(runtime, runtime_archive)
    guest_archive = pack_guest(work, commit, pins, executor)
    initramfs = output / "guest.cpio.gz"
    with gzip.open(initramfs, "wb", compresslevel=1) as stream:
        stream.write(runtime_archive.read_bytes())
        stream.write(guest_archive.read_bytes())
    accel = args.accel
    if accel == "kvm" and not os.access("/dev/kvm", os.R_OK | os.W_OK):
        accel = "tcg"
    record = {"commit": commit, "kernel": str(kernel), "kernel_sha256": sha256(kernel),
              "initramfs_sha256": sha256(initramfs), "executor_sha256": sha256(executor),
              "runtime_root": None if args.runtime_root else "host build",
              "runtime_files": sum(1 for _ in runtime.rglob("*")),
              "environment": environment(accel), "solve_budget": args.solve_budget,
              "recursive": args.recursive}
    link = free_port()
    logs = {"A": output / "A-serial.log", "B": output / "B-serial.log"}
    disks = {"A": work / "A.img", "B": work / "B.img"}
    for role in ("A", "B"):
        make_disk(disks[role])
    processes = {}
    started = time.monotonic()
    try:
        processes["B"] = launch(boot_arguments("B", kernel, initramfs, disks["B"], logs["B"],
                                               accel, args.memory, link, commit,
                                               args.solve_budget, args.recursive))
        time.sleep(1)
        processes["A"] = launch(boot_arguments("A", kernel, initramfs, disks["A"], logs["A"],
                                               accel, args.memory, link, commit,
                                               args.solve_budget, args.recursive))
        for role, process in processes.items():
            try:
                process.wait(timeout=BOOT_TIMEOUT)
            except subprocess.TimeoutExpired:
                raise RunError(f"guest {role} did not finish within {BOOT_TIMEOUT}s")
            if process.returncode:
                raise RunError(f"guest {role} exited {process.returncode}")
    finally:
        for process in processes.values():
            terminate(process)
    record["seconds"] = round(time.monotonic() - started, 2)
    for role in ("A", "B"):
        log = logs[role].read_text(encoding="utf-8", errors="replace")
        (output / f"{role}-serial.log").write_text(log, encoding="utf-8")
        if "GUEST_EXIT=0" not in log:
            raise RunError(f"guest {role} did not report a clean exit")
        if "Traceback" in log:
            raise RunError(f"guest {role} raised an exception")
    (output / "init").write_text(INIT, encoding="utf-8")
    roots = {}
    for role in ("A", "B"):
        roots[role] = output / role
        extract(disks[role], roots[role])
    guests = {role: json.loads((roots[role] / "guest.json").read_text(encoding="utf-8"))
              for role in ("A", "B")}
    check_guests(guests["A"], guests["B"])
    leaf_count = len(json.loads((roots["A"] / "result.json").read_text())["slices"])
    record.update(check_run(roots["A"], roots["B"], leaf_count=leaf_count, recursive=args.recursive))
    record["guests"] = guests
    record["status"] = "PASS"
    record["claim"] = ("two guests, one physical host: guest-level protocol and role split only; "
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
    runner.add_argument("--accel", choices=("kvm", "tcg"), default="kvm")
    runner.add_argument("--memory", type=int, default=1024)
    runner.add_argument("--keep-work", action="store_true")
    args = parser.parse_args()
    try:
        record = run(args)
    except (RunError, RuntimeError, subprocess.CalledProcessError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2))
        raise SystemExit(1)
    print(json.dumps({key: record[key] for key in ("status", "seconds", "slices", "job_id",
                                                   "output_sha256", "lan_transcript_equal",
                                                   "initramfs_sha256")}, indent=2))


if __name__ == "__main__":
    main()
