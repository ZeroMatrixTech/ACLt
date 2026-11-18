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
from tools.verification_profile import codec as c
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


class DispatchSession:
    """One dispatch: the frozen request follows the activation on the same connection."""

    def __init__(self, dispatch, connection, sequence, epoch, owner, slot, attempt, action, boot):
        self.dispatch = dispatch
        self.connection = connection
        self.sequence = sequence
        self.epoch = epoch
        self.owner = owner
        self.slot = slot
        self.attempt = attempt
        self.action = action
        self.boot = boot
        self.closed = False

    def request(self, raw):
        name = general_vm.wire_name(raw)
        request_sha = hashlib.sha256(raw).hexdigest()
        (self.dispatch.output / f"{name}-request.cbor").write_bytes(raw)
        try:
            if self.dispatch.relay is None:
                send(self.connection, raw)
                response = receive(self.connection)
            else:
                response = sort_contract.exchange_payload(self.connection, raw, self.dispatch.relay)
        except OSError as error:
            self.dispatch.record_outcome(self, request_sha, len(raw), "no_reply",
                                         error=type(error).__name__)
            if self.dispatch.driver is not None:
                self.dispatch.driver.after_failure(self, raw)
            raise
        (self.dispatch.output / f"{name}-response.cbor").write_bytes(response)
        self.dispatch.record_outcome(self, request_sha, len(raw), "answered",
                                     response=response)
        return response

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.connection.close()
            except OSError:
                pass


class LocalSession:
    """The coordinator's own serving slot: same admission and records, no socket."""

    def __init__(self, dispatch, sequence, epoch, owner, slot, attempt, action, activation):
        self.dispatch = dispatch
        self.sequence = sequence
        self.epoch = epoch
        self.owner = owner
        self.slot = slot
        self.attempt = attempt
        self.action = action
        self.activation = activation
        self.boot = dispatch.local.boot

    def request(self, raw):
        request = c.decode(raw)
        name = general_vm.wire_name(raw)
        request_sha = hashlib.sha256(raw).hexdigest()
        (self.dispatch.output / f"{name}-request.cbor").write_bytes(raw)
        reason = self.dispatch.local.admit(request, self.activation)
        if reason is not None:
            self.dispatch.local.reject(reason, raw=raw, request=request,
                                       activation=self.activation)
            self.dispatch.record_outcome(self, request_sha, len(raw), "refused", reason=reason)
            raise ConnectionError("local serving refused the request")
        if self.dispatch.inject is not None and self.dispatch.inject.matches(request):
            self.dispatch.inject.hit(request, raw, self.owner)
            self.dispatch.record_outcome(self, request_sha, len(raw), "no_reply", error="injected")
            raise ConnectionError("injected local serving fault")
        response = self.dispatch.local.execute(raw, EXECUTOR)
        (self.dispatch.output / f"{name}-response.cbor").write_bytes(response)
        self.dispatch.record_outcome(self, request_sha, len(raw), "answered", response=response)
        return response

    def close(self):
        pass


class C1Dispatch:
    """Bridge between general_vm.run and the serving boots (C-03 request binding)."""

    def __init__(self, connect_peer, output, coordinator, *, inject=None):
        self.connect_peer = connect_peer
        self.output = output
        self.coordinator = coordinator
        self.inject = inject
        self.relay = None
        self.driver = None
        self.sequence = 0
        self.trace = output / "dispatch.jsonl"
        self.local = None

    def record(self, row):
        general_vm.append_record(self.trace, row)

    def record_outcome(self, session, request_sha, request_bytes, outcome, *, response=None,
                       reason=None, error=None):
        row = dict(event="outcome", sequence=session.sequence, epoch=session.epoch,
                   role=session.owner, slot=session.slot, attempt=session.attempt,
                   action=session.action, boot=session.boot.hex(),
                   request_sha256=request_sha, request_bytes=request_bytes, outcome=outcome)
        if response is not None:
            row.update(response_sha256=hashlib.sha256(response).hexdigest(),
                       response_bytes=len(response))
        if reason is not None:
            row["reason"] = reason
        if error is not None:
            row["error"] = error
        self.record(row)

    def activation(self, sequence, epoch, owner, slot, attempt, action, boot,
                   request_bytes, response_bytes):
        self.record(dict(event="activation", sequence=sequence, epoch=epoch, role=owner,
                         slot=slot, attempt=attempt, action=action, boot=boot.hex(),
                         request_bytes=request_bytes, response_bytes=response_bytes))

    def open(self, owner, epoch, *, slot, attempt, action):
        self.sequence += 1
        sequence = self.sequence
        boot_frame = c.encode(dict(action="BOOT", epoch=epoch, dispatch=sequence))
        if owner == self.coordinator:
            if self.local is None:
                self.local = general_vm.ServingBoot(owner, self.output)
            reply, activation = self.local.activate(boot_frame)
            c.need(reply is not None, "local serving refused the activation")
            boot = self.local.boot
            self.activation(sequence, epoch, owner, slot, attempt, action, boot,
                            len(boot_frame), len(reply))
            return boot, LocalSession(self, sequence, epoch, owner, slot, attempt, action,
                                      activation)
        connection = self.connect_peer(owner)
        try:
            send(connection, boot_frame)
            raw = receive(connection)
        except BaseException:
            connection.close()
            raise
        reply = c.decode(raw)
        c.fields(reply, ("boot", "epoch", "dispatch"))
        boot = c.digest_bytes(reply["boot"])
        c.need(c.uint(reply["epoch"]) == epoch and c.uint(reply["dispatch"]) == sequence,
               "activation reply differs from the dispatch")
        self.activation(sequence, epoch, owner, slot, attempt, action, boot,
                        len(boot_frame), len(raw))
        return boot, DispatchSession(self, connection, sequence, epoch, owner, slot, attempt,
                                     action, boot)

    def stop(self, owner):
        try:
            connection = self.connect_peer(owner)
        except OSError:
            self.record(dict(event="stop", role=owner, sent_bytes=0, outcome="unreachable"))
            return
        sent = 0
        try:
            send(connection, general_vm.STOP)
            sent = len(general_vm.STOP)
        except OSError:
            pass
        finally:
            connection.close()
        self.record(dict(event="stop", role=owner, sent_bytes=sent,
                         outcome="sent" if sent else "failed"))


class C1Driver:
    """Deliver the C-03 probes: restarts, resent frames and stale-epoch frames.

    Each probe records what was sent and what answered.  The refusing side records
    the reason, so this driver never claims one.
    """

    def __init__(self, scenario, *, connect_peer, output, previous=None, target=(1, 1)):
        self.scenario = scenario
        self.connect_peer = connect_peer
        self.output = output
        self.previous = previous
        self.target = target
        self.trace = output / "resends.jsonl"
        self.sequence = 1000000

    def record(self, row):
        general_vm.append_record(self.trace, row)

    def probe_sequence(self):
        self.sequence += 1
        return self.sequence

    def send_frames(self, owner, frames):
        sent, replies, sent_bytes, received_bytes = 0, [], 0, 0
        connection = self.connect_peer(owner)
        try:
            for raw in frames:
                send(connection, raw)
                sent += 1
                sent_bytes += len(raw)
                reply = receive(connection)
                replies.append(reply)
                received_bytes += len(reply)
        except OSError:
            pass
        finally:
            connection.close()
        return sent, replies, sent_bytes, received_bytes

    def probe(self, owner, raw, *, kind, epoch):
        boot_frame = None if kind == "bare" else c.encode(
            dict(action="BOOT", epoch=epoch, dispatch=self.probe_sequence()))
        frames = [] if boot_frame is None else [boot_frame]
        frames.append(raw)
        sent, replies, sent_bytes, received_bytes = self.send_frames(owner, frames)
        answered = len(replies) == len(frames)
        if kind == "bare":
            outcome = "answered" if answered else "refused"
        elif not replies:
            outcome = "activation-refused"
        else:
            outcome = "answered" if answered else "refused"
        activation_boot = None
        if boot_frame is not None and replies:
            reply = c.decode(replies[0])
            boot = reply.get("boot")
            activation_boot = boot.hex() if type(boot) is bytes else None
        raw_sent = sent == len(frames)
        self.record(dict(event="probe", scenario=self.scenario, probe=kind, role=owner,
                         epoch=epoch, request_sha256=hashlib.sha256(raw).hexdigest(),
                         request_action=codec.decode(raw)["action"],
                         request_bytes=len(raw), frames=len(frames), sent=sent,
                         sent_bytes=sent_bytes, replies=len(replies),
                         received_bytes=received_bytes, outcome=outcome,
                         boot_bytes=len(boot_frame) if (boot_frame is not None and sent >= 1) else 0,
                         boot_reply_bytes=(len(replies[0]) if (boot_frame is not None and replies) else 0),
                         raw_sent_bytes=len(raw) if raw_sent else 0,
                         reply_bytes=len(replies[-1]) if answered else 0,
                         activation_boot=activation_boot))

    def restart(self, owner):
        frame = c.encode({"action": "RESTART"})
        sent = 0
        connection = self.connect_peer(owner)
        try:
            send(connection, frame)
            sent = len(frame)
        except OSError:
            pass
        finally:
            connection.close()
        self.record(dict(event="restart_sent", role=owner, sent_bytes=sent,
                         outcome="sent" if sent else "failed"))

    def wait_boot(self, owner, epoch, previous_boot):
        deadline = time.monotonic() + CONNECT_TIMEOUT
        attempts, sent_bytes, received_bytes = 0, 0, 0
        while True:
            frame = c.encode(dict(action="BOOT", epoch=epoch,
                                  dispatch=self.probe_sequence()))
            try:
                connection = self.connect_peer(owner)
            except OSError:
                if time.monotonic() >= deadline:
                    self.record(dict(event="wait_boot", role=owner, epoch=epoch,
                                     attempts=attempts, sent_bytes=sent_bytes,
                                     received_bytes=received_bytes, outcome="failed"))
                    raise
                time.sleep(0.2)
                continue
            try:
                send(connection, frame)
                attempts += 1
                sent_bytes += len(frame)
                raw = receive(connection)
                received_bytes += len(raw)
            except OSError:
                if time.monotonic() >= deadline:
                    self.record(dict(event="wait_boot", role=owner, epoch=epoch,
                                     attempts=attempts, sent_bytes=sent_bytes,
                                     received_bytes=received_bytes, outcome="failed"))
                    raise
                time.sleep(0.2)
                continue
            finally:
                connection.close()
            boot = c.digest_bytes(c.decode(raw)["boot"])
            if boot != previous_boot:
                self.record(dict(event="wait_boot", role=owner, epoch=epoch,
                                 attempts=attempts, sent_bytes=sent_bytes,
                                 received_bytes=received_bytes, outcome="changed",
                                 boot=boot.hex()))
                return boot
            if time.monotonic() >= deadline:
                raise RuntimeError("serving boot did not change after the restart")
            time.sleep(0.2)

    def after_failure(self, session, raw):
        if self.scenario not in ("restart", "duplicate"):
            return
        if (session.slot, session.attempt, session.action) != (*self.target, "SOLVE"):
            return
        owner = session.owner
        if self.scenario == "restart":
            self.restart(owner)
            boot = self.wait_boot(owner, session.epoch, session.boot)
            self.record(dict(event="restart", scenario=self.scenario, role=owner,
                             epoch=session.epoch, previous_boot=session.boot.hex(),
                             boot=boot.hex(),
                             request_sha256=hashlib.sha256(raw).hexdigest()))
        self.probe(owner, raw, kind="bare", epoch=session.epoch)
        self.probe(owner, raw, kind="boot", epoch=session.epoch)

    def after_run(self, journal):
        if self.scenario != "stale" or self.previous is None:
            return
        events = codec.decode(self.previous.read_bytes())
        probes = [(event["worker"], event["request"]) for event in events
                  if event["kind"] == "RESERVE"]
        probes += [(event["verifier"], event["request"]) for event in events
                   if event["kind"] == "ACCEPT"]
        for owner, raw in probes:
            epoch = c.decode(raw)["epoch"]
            self.probe(owner, raw, kind="bare", epoch=epoch)
            self.probe(owner, raw, kind="old-boot", epoch=epoch)
            self.probe(owner, raw, kind="boot", epoch=journal.epoch)


def run_general(role, port, budget, report, pairs):
    output = EVIDENCE / role
    output.mkdir(mode=0o700)
    drop = pairs.get("aclt_general_drop") == "1"
    six = pairs.get("aclt_general_six") == "1"
    inject = general_vm.Injection.parse(pairs.get("aclt_general_inject"))
    nonce = bytes.fromhex(pairs["aclt_execution_nonce"])
    sort_job = sort_contract.SortJob(nonce) if pairs.get("aclt_capacity_sort") == "1" else None
    scenario = pairs.get("aclt_c1") or None
    if sort_job is not None and scenario is not None:
        raise RuntimeError("the C1 restart scenarios do not apply to the sort family")
    if sort_job is not None:
        if pairs.get("aclt_handoff") == "control":
            capacity_sort.single(output)
            report["general_status"] = "CAPACITY_EXHAUSTED"
            (output / "guest.json").write_text(json.dumps(report) + "\n", encoding="utf-8")
            return 0
    if role != "A":
        # The worker serves in a child process so that worker_exit is a real non-zero
        # process exit (R1 section 4).  Injection records, restart records and serving
        # observations are written durably before the child acts; the supervisor restarts it.
        hits_path = output / "injection.jsonl"
        observed_path = output / "observations.jsonl"
        restarts_path = output / "restarts.jsonl"
        bounds_path = output / "serve-bounds.json"
        if inject is not None:
            inject.log_path = hits_path
            inject.observation_path = observed_path
        while True:
            seen = len(general_vm.read_lines(hits_path))
            restarted = len(general_vm.read_lines(restarts_path))
            child = os.fork()
            if child == 0:
                code = 0
                try:
                    bounds = general_vm.serve(role, port, EXECUTOR, output, drop_first_b=drop,
                                              sort_job=sort_job, inject=inject, exit_on_fault=True,
                                              restart=scenario == "restart")
                    bounds_path.write_text(json.dumps(bounds) + "\n", encoding="utf-8")
                except BaseException:
                    import traceback
                    traceback.print_exc()
                    code = 1
                finally:
                    sys.stdout.flush()
                    sys.stderr.flush()
                    os._exit(code)
            _, status = os.waitpid(child, 0)
            code = os.waitstatus_to_exitcode(status)
            if code == general_vm.WORKER_EXIT_CODE:
                hits = general_vm.read_lines(hits_path)
                restarts = general_vm.read_lines(restarts_path)
                if len(hits) == seen + 1 and hits[-1]["mode"] == "worker_exit":
                    last = hits[-1]
                    row = {"role": role, "reason": "worker_exit", "slot": last["slot"],
                           "attempt": last["attempt"], "exit_status": code}
                elif len(restarts) == restarted + 1 and restarts[-1].get("event") == "restart":
                    row = {"role": role, "reason": "restart", "exit_status": code,
                           "boot": restarts[-1].get("boot")}
                else:
                    raise RuntimeError("worker exited without exactly one injection or restart record")
                report.setdefault("worker_exits", []).append(row)
                print(f"GUEST_WORKER_EXIT role={role} status={code}", flush=True)
                continue
            if code != 0:
                raise RuntimeError(f"worker process failed with status {code}")
            break
        report.update(json.loads(bounds_path.read_text(encoding="utf-8")))
        hits = general_vm.read_lines(hits_path)
        report["fault_triggered"] = len(hits)
        if scenario is not None:
            report["c1_scenario"] = scenario
        if inject is not None:
            report["injection"] = hits
            report["observations"] = general_vm.read_lines(observed_path)
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

        def connect_peer(owner):
            connection = connect(guest_ip(owner), port)
            connection.settimeout(general_vm.TIMEOUT)
            report["connections"][owner] = dict(local_ip=connection.getsockname()[0],
                                                peer_ip=connection.getpeername()[0])
            return connection

        dispatch = C1Dispatch(connect_peer, output, role, inject=inject)
        if scenario is not None:
            dispatch.driver = C1Driver(scenario, connect_peer=connect_peer, output=output,
                                       previous=previous)

        # Finish the operation stream even on a blocked budget or checkpoint.
        try:
            checkpoint = int(pairs.get("aclt_general_checkpoint", "0"))
            with ExitStack() as resources:
                placement = retry_worker = None
                if workers := tuple(pairs.get("aclt_general_workers", "")):
                    placement = general_vm.coordinator_only(workers, len(job.tasks))
                    retry_worker = general_vm.retry_after(workers)
                if sort_job is not None:
                    stored = resources.enter_context(capacity_sort.memory_file())
                    dispatch.relay = stored
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
                        job, roles, output / "journal.cbor", order=order, previous=previous,
                        checkpoint=checkpoint, placement=placement, retry_worker=retry_worker,
                        retry_remote=inject is not None and not workers, source=source,
                        reuse=reuse, journal_factory=journal_factory, dispatch=dispatch,
                    )
                except coordination.CoordinationError:
                    path = output / "journal.cbor"
                    events = codec.decode(path.read_bytes()) if path.is_file() else ()
                    journal = general_vm.Journal(job, path, events)
                    if not path.is_file():
                        path.write_bytes(codec.encode(events))
                    status = "COORDINATION_PAUSED"
                if dispatch.driver is not None and status != "COORDINATION_PAUSED":
                    dispatch.driver.after_run(journal)
        finally:
            for peer in roles[1:]:
                dispatch.stop(peer)
        (output / "declaration.cbor").write_bytes(job.declaration)
        (output / "plan.cbor").write_bytes(job.plan)
        (output / "execution.cbor").write_bytes(job.execution)
        if journal.final is not None:
            (output / "publication.cbor").write_bytes(codec.encode(journal.final))
        report["general_status"] = status
        report["merge_ns"] = getattr(journal, "merge_ns", None)
        if scenario is not None:
            report["c1_scenario"] = scenario
        if inject is not None:
            report["fault_triggered"] = len(inject.hits)
            report["injection"] = inject.hits
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
