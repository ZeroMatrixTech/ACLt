# SPDX-License-Identifier: Apache-2.0
"""Trusted dual-host QEMU lifecycle. Only the virtual network uses physical LAN."""

import argparse
import base64
from contextlib import ExitStack, contextmanager
import fcntl
import gzip
import hashlib
import ipaddress
import io
import json
import os
from pathlib import Path
import platform
import selectors
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time

SSH_OPTIONS = ("ssh", "-F", "/dev/null", "-o", "BatchMode=yes",
               "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=10",
               "-o", "ServerAliveInterval=10", "-o", "ServerAliveCountMax=3")


class DualHostError(RuntimeError):
    pass


def config(path, roles, placement):
    value = json.loads(path.read_text())
    fields = {"ssh_target", "host_a_lan", "host_b_lan", "remote_root"}
    if not isinstance(value, dict) or value.keys() != fields:
        raise DualHostError("invalid dual-host configuration fields")
    if any(not isinstance(value[key], str) or not value[key] for key in fields):
        raise DualHostError("dual-host configuration requires nonempty strings")
    for key in ("host_a_lan", "host_b_lan"):
        ip = ipaddress.IPv4Address(value[key])
        if ip.is_loopback or ip.is_unspecified or ip.is_multicast:
            raise DualHostError("physical LAN requires unicast non-loopback addresses")
    if value["host_a_lan"] == value["host_b_lan"]:
        raise DualHostError("physical hosts need distinct addresses")
    if value["ssh_target"].startswith("-") or any(ch.isspace() for ch in value["ssh_target"]):
        raise DualHostError("invalid SSH target")
    if not Path(value["remote_root"]).is_absolute():
        raise DualHostError("remote_root must be an absolute private run parent")
    remote = placement.split(",")
    if not remote or len(set(remote)) != len(remote) or set(remote) - set(roles[1:]):
        raise DualHostError("B placement must list distinct non-coordinator roles")
    return value, tuple(role for role in roles if role in remote)


@contextmanager
def experiment_lock(path=None):
    path = path or Path(os.environ.get("XDG_RUNTIME_DIR") or "/tmp") / "aclt-experiment.lock"
    with path.open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise DualHostError("host experiment lock busy") from error
        yield


def identity():
    return hashlib.sha256(Path("/etc/machine-id").read_bytes()).hexdigest()


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sockets(pid, local, remote):
    rows = subprocess.check_output(["ss", "-4Htnp", "state", "established"], text=True)
    result = []
    for line in rows.splitlines():
        parts = line.split()
        if len(parts) < 5 or f"pid={pid}," not in line:
            continue
        source, destination = parts[-3:-1]
        if source.startswith(local + ":") and destination.startswith(remote + ":"):
            result.append((int(source.rsplit(":", 1)[1]), int(destination.rsplit(":", 1)[1])))
    return result


def check_lan(record, roles, remote_roles):
    topology = record["topology"]
    if not remote_roles:
        if "lan_links" in topology:
            raise DualHostError("unexpected physical links in local run")
        return
    placement = {role: "B" if role in remote_roles else "A" for role in roles}
    links = topology["lan_links"]
    if topology["placement"] != placement or set(links) != set(remote_roles):
        raise DualHostError("physical topology differs from requested placement")
    if topology["host_a_lock"] != "held" or topology["host_b_environment"]["lock"] != "held":
        raise DualHostError("missing host lock record")
    if topology["host_b_boot_hashes"] != {"kernel": record["kernel_sha256"],
                                          "guest.cpio.gz": record["initramfs_sha256"]}:
        raise DualHostError("B boot image digest mismatch")
    for link in links.values():
        left, right = link["A"], link["B"]
        if (left["local"] != right["peer"] or left["peer"] != right["local"]
                or left["local"][0] != "A-LAN" or right["local"][0] != "B-LAN"
                or not all(type(port) is int and 0 < port < 65536
                           for port in (left["local"][1], right["local"][1]))):
            raise DualHostError("LAN endpoint observations do not match")


def stop(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def agent(parent, lan, roles):
    # The SSH stdin lifetime owns the B lock and the QEMU processes.
    with experiment_lock(), tempfile.TemporaryDirectory(prefix="aclt-r2-", dir=parent) as name:
        root = Path(name)
        children = {}
        with socket.socket() as endpoint:
            endpoint.bind((lan, 0))
        print(json.dumps(dict(identity=identity(), kernel=platform.release(), machine=platform.machine(),
                              qemu=subprocess.check_output(["qemu-system-x86_64", "--version"],
                                                           text=True).splitlines()[0],
                              lock="held")), flush=True)
        try:
            for line in sys.stdin:
                request = json.loads(line)
                action = request["action"]
                if action == "ports":
                    with reserved_ports(lan, roles) as ports:
                        response = ports
                elif action == "stage":
                    filename = request["name"]
                    if filename not in ("kernel", "guest.cpio.gz"):
                        raise DualHostError("unknown staging object")
                    path = root / filename
                    with path.open("xb") as stream:
                        stream.write(base64.b64decode(request["data"], validate=True))
                    response = sha(path)
                elif action == "launch":
                    role = request["role"]
                    if role not in roles or role in children:
                        raise DualHostError("invalid remote launch role")
                    disk = root / f"{role}.img"
                    with disk.open("xb") as stream:
                        stream.truncate(request["disk_size"])
                    subprocess.run(["mkfs.ext4", "-q", "-F", "-L", "evidence", str(disk)], check=True)
                    with (root / f"{role}-qemu.log").open("wb") as log:
                        children[role] = subprocess.Popen(request["argv"], cwd=root, stdin=subprocess.DEVNULL,
                                                          stdout=log, stderr=subprocess.STDOUT)
                    response = None
                elif action == "ready":
                    active = subprocess.check_output(["ss", "-4Hltnp"], text=True)
                    response = [role for role, proc in children.items()
                                if proc.poll() is None and f"pid={proc.pid}," in active]
                elif action == "observe":
                    response = {role: sockets(proc.pid, lan, request["peer"])
                                for role, proc in children.items()}
                elif action in ("collect", "diagnostics"):
                    role = request["role"]
                    returncode = children[role].poll()
                    response = None
                    if returncode is not None or action == "diagnostics":
                        log = root / f"{role}-serial.log"
                        response = dict(exit=returncode, serial=log.read_text(errors="replace") if log.exists() else "",
                                        qemu=(root / f"{role}-qemu.log").read_text(errors="replace"))
                        if action == "collect" and returncode == 0:
                            response["disk"] = base64.b64encode(
                                gzip.compress((root / f"{role}.img").read_bytes(), compresslevel=1)).decode()
                else:
                    raise DualHostError("unknown remote action")
                print(json.dumps({"result": response}), flush=True)
        finally:
            for process in children.values():
                stop(process)


@contextmanager
def reserved_ports(address, roles):
    with ExitStack() as stack:
        reserved = {}
        for role in roles:
            listener = stack.enter_context(socket.socket())
            listener.bind((address, 0))
            reserved[role] = listener.getsockname()[1]
        yield reserved


class Remote:
    def __init__(self, settings, roles, output):
        self.settings = settings
        self.roles = roles
        self.output = output

    def __enter__(self):
        command = ["python3", "-B", "-u", "-c", Path(__file__).read_text(),
                   self.settings["remote_root"], self.settings["host_b_lan"], *self.roles]
        self.error_log = (self.output / "B-ssh.log").open("wb")
        try:
            self.process = subprocess.Popen(
                [*SSH_OPTIONS, self.settings["ssh_target"], shlex.join(command)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.error_log)
            ready = self.read()
            if ready.pop("identity") == identity() or ready["machine"] != platform.machine():
                raise DualHostError("B has local machine identity or incompatible architecture")
            self.environment = ready
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        try:
            if hasattr(self, "process"):
                self.process.stdin.close()
                try:
                    self.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    stop(self.process)
                finally:
                    self.process.stdout.close()
        finally:
            self.error_log.close()

    def read(self):
        with selectors.DefaultSelector() as selector:
            selector.register(self.process.stdout, selectors.EVENT_READ)
            if not selector.select(timeout=90):
                raise DualHostError("B control response timed out")
        data = self.process.stdout.readline()
        if not data:
            raise DualHostError("B control channel closed; see B-ssh.log")
        return json.loads(data)

    def call(self, **request):
        self.process.stdin.write(json.dumps(request).encode() + b"\n")
        self.process.stdin.flush()
        return self.read()["result"]

    def stage(self, kernel, initramfs):
        observed = {}
        for name, path in (("kernel", kernel), ("guest.cpio.gz", initramfs)):
            blob = base64.b64encode(path.read_bytes()).decode()
            recorded = self.call(action="stage", name=name, data=blob)
            if recorded != sha(path):
                raise DualHostError("B boot image digest mismatch")
            observed[name] = recorded
        return observed

    def wait_ready(self):
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if set(self.call(action="ready")) == set(self.roles):
                return
            time.sleep(0.2)
        raise DualHostError("B QEMU listeners did not become ready")

    def observe(self, coordinator, ports):
        address_a = self.settings["host_a_lan"]
        address_b = self.settings["host_b_lan"]
        deadline = time.monotonic() + 20
        while coordinator.poll() is None and time.monotonic() < deadline:
            a = sockets(coordinator.pid, address_a, address_b)
            b = self.call(action="observe", peer=address_a)
            matches = {}
            for role, listen in ports.items():
                paired = [(source, port) for source, port in a if port == listen
                          and [port, source] in b.get(role, ())]
                if len(paired) == 1:
                    source, port = paired[0]
                    matches[role] = {"A": {"local": ["A-LAN", source], "peer": ["B-LAN", port]},
                                     "B": {"local": ["B-LAN", port], "peer": ["A-LAN", source]}}
            if matches.keys() == ports.keys():
                return matches
            time.sleep(0.2)
        raise DualHostError("cross-host QEMU endpoints did not agree")

    def collect(self, role, disk, serial, deadline):
        while time.monotonic() < deadline:
            result = self.call(action="collect", role=role)
            if result is not None:
                serial.write_text(result["serial"])
                (self.output / f"{role}-qemu.log").write_text(result["qemu"])
                if result["exit"] != 0:
                    raise DualHostError(f"remote guest {role} exited {result['exit']}")
                with gzip.GzipFile(fileobj=io.BytesIO(base64.b64decode(result["disk"]))) as source:
                    with disk.open("xb") as target:
                        shutil.copyfileobj(source, target)
                return
            time.sleep(0.2)
        raise DualHostError(f"remote guest {role} did not finish")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("parent")
    parser.add_argument("lan")
    parser.add_argument("roles", nargs="+")
    args = parser.parse_args()
    agent(args.parent, args.lan, args.roles)
