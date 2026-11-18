# SPDX-License-Identifier: Apache-2.0
"""Local multi-VM acceptance for the experimental integer-vector job family."""

from contextlib import closing
import hashlib
import json
import os
import socket
import sys
from pathlib import Path

from baseline import ARTIFACT_TAG, PROBE, QUESTION_TAG, ask, solve, validate
from general_job import BudgetError, FAMILY, INT, Job, Journal, digest, handle
from multivm_job import assignments, guest_ip
from tools.formal_migration.s2_transport import receive, send
from tools.verification_profile import codec as c
from wasm import artifact as encode_artifact

CAPS = [8232, 8232, 8242, 8232]
CAPS_SIX = [8232, 8232, 8242, 8232, 8232, 8242]
DEFAULT_BUDGET = sum(CAPS) + CAPS[1]
DEFAULT_BUDGET_SIX = sum(CAPS_SIX) + CAPS_SIX[1]
TASKS = [{"literal": 2}, {"literal": 3}, {"double": 0}, {"literal": 11}]
TASKS_SIX = TASKS + [{"literal": 2}, {"double": 4}]
DROP_MODES = ("no_reply", "worker_exit", "tcp_disconnect")
STOP = c.encode({"action": "STOP"})
WORKER_EXIT_CODE = 7
TIMEOUT = 30
BOOT_FIELDS = ("action", "epoch", "dispatch")


class DispatchUnavailable(RuntimeError):
    """No serving boot could be activated before a dispatch; no attempt was made."""


def _record(path, row):
    """Append one durable record so it survives a serving process exit."""
    append_record(path, row)


class ServingBoot:
    """One serving process's boot identity, admission rules and observations.

    The boot is generated once per process start.  Every frozen request carries the
    boot it was dispatched for, so a request dispatched before a restart is refused
    without relying on process memory being retained.  The execution and rejection
    records are observations for evidence; they never admit a request.
    """

    def __init__(self, role, output, *, restart=False):
        self.role = role
        self.output = Path(output)
        self.boot = os.urandom(32)
        self.seen = set()
        self.epoch = None
        self.restart_enabled = restart
        self.activations = self.output / "activations.jsonl"
        self.executions = self.output / "executions.jsonl"
        self.rejections = self.output / "rejections.jsonl"
        self.restarts = self.output / "restarts.jsonl"
        _record(self.output / "boots.jsonl",
                dict(event="boot", role=role, boot=self.boot.hex()))

    def activate(self, raw):
        """Accept one BOOT frame; return its reply and epoch, or None and a reason."""
        request = c.decode(raw)
        c.fields(request, BOOT_FIELDS)
        c.need(request["action"] == "BOOT", "not a boot frame")
        epoch, dispatch = c.uint(request["epoch"]), c.uint(request["dispatch"])
        if self.epoch is not None and epoch < self.epoch:
            _record(self.activations, dict(event="activation", dispatch=dispatch, epoch=epoch,
                                           boot=self.boot.hex(), accepted=False,
                                           reason="stale-epoch", request_bytes=len(raw)))
            return None, "stale-epoch"
        self.epoch = epoch
        reply = c.encode(dict(boot=self.boot, epoch=epoch, dispatch=dispatch))
        _record(self.activations, dict(event="activation", dispatch=dispatch, epoch=epoch,
                                       boot=self.boot.hex(), accepted=True,
                                       request_bytes=len(raw), response_bytes=len(reply)))
        return reply, epoch

    def admit(self, request, activation):
        """Return the rejection reason for a request on an activated connection."""
        if activation is None:
            return "unactivated"
        if request.get("epoch") != activation:
            return "epoch-mismatch"
        boot = request.get("boot")
        if type(boot) is not bytes or boot != self.boot:
            return "boot-mismatch"
        key = (request.get("execution_id"), request.get("slot"),
               request.get("attempt"), request.get("action"))
        if key in self.seen:
            return "duplicate"
        self.seen.add(key)
        return None

    def reject(self, reason, *, kind=None, raw=None, request=None, activation=None):
        request = request or {}
        boot = request.get("boot")
        _record(self.rejections, dict(
            event="reject", boot=self.boot.hex(), kind=kind or request.get("action"),
            reason=reason,
            execution_id=request["execution_id"].hex() if type(request.get("execution_id")) is bytes else None,
            slot=request.get("slot"), attempt=request.get("attempt"),
            request_sha256=hashlib.sha256(raw).hexdigest() if raw is not None else None,
            request_bytes=len(raw) if raw is not None else None,
            request_boot=boot.hex() if type(boot) is bytes else None,
            request_epoch=request.get("epoch"), activation_epoch=activation))

    def execute(self, raw, executor):
        """Execute one admitted request, recording both sides of the actual call."""
        request = c.decode(raw)
        row = dict(boot=self.boot.hex(), execution_id=bytes(request["execution_id"]).hex(),
                   slot=request["slot"], attempt=request["attempt"], action=request["action"],
                   request_sha256=hashlib.sha256(raw).hexdigest(), request_bytes=len(raw))
        _record(self.executions, dict(event="execute-begin", **row))
        response = handle(raw, executor)
        _record(self.executions, dict(event="execute-end", response_bytes=len(response),
                                      response_sha256=hashlib.sha256(response).hexdigest(), **row))
        return response

    def withhold(self, raw, response):
        """Record a reply that was generated but deliberately not sent."""
        request = c.decode(raw)
        _record(self.output / "withheld.jsonl", dict(
            event="withhold", boot=self.boot.hex(),
            execution_id=bytes(request["execution_id"]).hex(),
            slot=request["slot"], attempt=request["attempt"], action=request["action"],
            request_sha256=hashlib.sha256(raw).hexdigest(),
            response_sha256=hashlib.sha256(response).hexdigest(),
            response_bytes=len(response)))

    def restart(self, request_bytes):
        _record(self.restarts, dict(event="restart", role=self.role, boot=self.boot.hex(),
                                    request_bytes=request_bytes))
        self.control("restart", request_bytes)

    def control(self, event, request_bytes):
        _record(self.output / "controls.jsonl",
                dict(event=event, role=self.role, request_bytes=request_bytes))


def caps(six=False):
    return list(CAPS_SIX if six else CAPS)


class WorkerExit(RuntimeError):
    """The serving worker aborted after reading a request; the guest remains up."""

    def __init__(self, role, name, local, peer):
        super().__init__(f"worker {role} exited after {name}")
        self.role = role
        self.name = name
        self.local = local
        self.peer = peer


class Injection:
    """One seeded remote-worker failure, applied at the TCP request boundary."""

    def __init__(self, mode, slot, loss):
        self.mode = mode
        self.slot = slot
        self.loss = loss
        self.hits = []
        self.log_path = None
        self.observation_path = None

    @classmethod
    def parse(cls, value):
        if not value:
            return None
        parts = value.split(":")
        if len(parts) != 3:
            raise ValueError("injection must be MODE:SLOT:LOSS")
        mode, slot, loss = parts
        if mode not in DROP_MODES:
            raise ValueError("injection mode must be no_reply, worker_exit or tcp_disconnect")
        if loss not in ("first", "both"):
            raise ValueError("injection loss must be first or both")
        try:
            slot = int(slot)
        except ValueError:
            raise ValueError("injection slot must be an integer") from None
        if slot < 0:
            raise ValueError("injection slot must be non-negative")
        return cls(mode, slot, loss)

    def matches(self, request):
        if request["action"] != "SOLVE" or request["slot"] != self.slot:
            return False
        return self.loss == "both" or request["attempt"] == 1

    def hit(self, request, raw, role, response=None):
        """Record one injection before it is applied (R1 5.3, per-attempt record).

        The record binds the execution, slot, attempt, serving role, fault class and
        request digest; a suppressed ``no_reply`` also binds the reply it withheld.
        It carries no wall clock, endpoint, PID or path.
        """
        row = {"mode": self.mode, "slot": request["slot"], "attempt": request["attempt"],
               "loss": self.loss, "role": role,
               "execution_id": bytes(request["execution_id"]).hex(),
               "request_sha256": hashlib.sha256(raw).hexdigest()}
        if response is not None:
            row["response_sha256"] = hashlib.sha256(response).hexdigest()
        self.hits.append(row)
        append_record(self.log_path, row)

    def observe(self, request, role, event):
        """Record what the serving side did after the injection (closed, ...)."""
        append_record(self.observation_path, {"event": event, "role": role,
                                             "slot": request["slot"], "attempt": request["attempt"]})


def append_record(path, row):
    """Persist one record durably so it survives a worker process exit."""
    if path is None:
        return
    with open(path, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_lines(path):
    path = Path(path)
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def coordinator_only(workers, leaf_count):
    """R1 5.2 placement: the coordinator serves nothing; workers rotate by slot."""
    workers = tuple(workers)
    c.need(len(workers) >= 3 and len(set(workers)) == len(workers),
           "coordinator-only placement needs three distinct workers")
    return tuple((workers[slot % len(workers)], workers[(slot + 1) % len(workers)])
                 for slot in range(leaf_count))


def retry_after(workers):
    """R1 5.2 retry: the unique worker that neither solved nor verifies the slot."""
    workers = tuple(workers)

    def choose(worker):
        return workers[(workers.index(worker) + 2) % len(workers)]
    return choose


def artifact_module():
    row = next(row for row in json.loads((PROBE / "tests/independent-vectors.json").read_bytes())["vectors"]
               if row["id"] == "divzero")
    return validate(bytes.fromhex(row["artifact_hex"]), row["limits"])


def program(module, instructions):
    module.code[module.run - len(module.imports)] = (
        [], [dict(op=code, args=args) for code, *args in instructions],
    )
    return encode_artifact(module.canonical())


def fixture(nonce, budget, *, flat=False, six=False):
    module = artifact_module()
    read = [(0x41, 0), (0x42, 0), (0x41, 0), (0x41, 8), (0x10, 2)]
    double = [(0x41, 0), (0x41, 0), (0x29, 3, 0), (0x42, 2), (0x7e,), (0x37, 3, 0)]
    write = [(0x41, 0), (0x41, 8), (0x10, 3)]
    artifacts = {op: program(module, read + middle + write)
                 for op, middle in (("copy", []), ("double", double))}
    tasks = TASKS_SIX if six else TASKS
    tree = ([[0, 1], [2, 3], [4, 5]] if six else [[0, 1], [2, 3]])
    declaration = c.encode(dict(family=FAMILY, tasks=tasks))
    plan = c.encode(dict(family=FAMILY,
                         tree=list(range(len(tasks))) if flat else tree,
                         dependencies={2: 0, 5: 4} if six else {2: 0}, caps=caps(six),
                         artifacts={op: c.domain_hash(ARTIFACT_TAG, raw) for op, raw in artifacts.items()}))
    execution = c.encode(dict(declaration_id=digest("Declaration", declaration), plan_id=digest("Plan", plan),
                              nonce=nonce, budget=budget))
    return Job(declaration, plan, execution, artifacts)


def standalone_probe(job, gas_limit):
    """Run the same whole problem as an external single-machine control."""
    tasks = job.tasks
    if len(tasks) == 6:
        c.need(tasks[2] == {"double": 0} and tasks[5] == {"double": 4},
               "unexpected standalone fixture dependency")
        values = []
        for task in tasks:
            if "literal" in task:
                values.append(task["literal"])
            else:
                c.need(task["double"] < len(values), "standalone dependency is not earlier")
                values.append(2 * values[task["double"]])
        return {"outcome": "OK", "output": b"".join(INT.pack(value) for value in values)}
    c.need(tasks[2] == {"double": 0}, "unexpected standalone fixture dependency")
    data = b"".join(INT.pack(tasks[slot]["literal"]) for slot in (0, 1, 3))
    artifact = program(artifact_module(), [
        (0x41, 0), (0x42, 0), (0x41, 0), (0x41, 24), (0x10, 2),
        (0x41, 24), (0x41, 16), (0x29, 3, 0), (0x37, 3, 0),
        (0x41, 16), (0x41, 0), (0x29, 3, 0), (0x42, 2), (0x7e,), (0x37, 3, 0),
        (0x41, 0), (0x41, 32), (0x10, 3),
    ])
    limits = dict(gas_limit=gas_limit, output_limit=32, memory_pages_limit=2, call_depth_limit=8)
    return c.decode(solve(ask(artifact, data, limits), artifact, data).outcome)


def next_worker(worker, verifier, roles, retry_worker, retry_remote):
    """Select the next serving role after a failed dispatch (R1 5.2 retry rules)."""
    if retry_worker is not None:
        return retry_worker(worker)
    if retry_remote:
        candidates = [role for role in roles[1:] if role not in (worker, verifier)]
        return candidates[0] if candidates else next(
            role for role in roles if role not in (worker, verifier))
    return next(role for role in roles if role not in (worker, verifier))


def activate(dispatch, worker, verifier, roles, epoch, *, slot, attempt, action,
             retry_worker, retry_remote):
    """Activate one serving boot before a dispatch, or None when no candidate answers.

    A failed activation is a pre-dispatch failure: no request was sent and no journal
    attempt exists yet, so the caller can either try another candidate role or stop
    with DISPATCH_UNAVAILABLE without charging the execution budget.
    """
    candidate = worker
    tried = set()
    while candidate is not None and candidate not in tried:
        tried.add(candidate)
        if candidate == verifier:
            # The frozen verification role is part of the placement.  Dispatching the
            # solve to it would leave an illegal solver/verifier combination and a
            # reserved attempt behind, so treat it as no legitimate candidate.
            candidate = next_worker(candidate, verifier, roles, retry_worker, retry_remote)
            continue
        try:
            boot, session = dispatch.open(candidate, epoch, slot=slot, attempt=attempt,
                                          action=action)
        except OSError:
            candidate = next_worker(candidate, verifier, roles, retry_worker, retry_remote)
        else:
            return candidate, boot, session
    return None


def run(job, roles, path, exchange=None, *, order, checkpoint=0, previous=None,
        placement=None, retry_worker=None, retry_remote=False, source=None, reuse=None,
        journal_factory=Journal, dispatch=None):
    """Drive one execution in the trusted-host experiment.

    With a dispatch object every SOLVE and VERIFY is frozen for the serving boot that
    was just activated in the same exchange, so a request dispatched before a worker
    restart cannot be executed after it.  The legacy exchange callable keeps the
    pre-C1 request shape for replay models and for archived evidence.
    """
    c.need(dispatch is not None or exchange is not None, "run needs an exchange or a dispatch")
    c.need(reuse is None or source is not None, "reuse needs verified source evidence")
    history = c.decode(previous.read_bytes()) if previous else ()
    journal = journal_factory(job, path, history, source=source)
    if previous:
        journal.add("HANDOFF", epoch=journal.epoch + 1)
    else:
        journal.add("START", execution=job.execution)
    if placement is None:
        placement = assignments(roles, len(job.tasks))
    while journal.ready():
        slot = next(slot for slot in order if slot in journal.ready())
        if reuse is not None and slot in reuse:
            source_slot = reuse[slot]
            receipt = source.accepted.get(source_slot)
            c.need(receipt is not None, "missing source acceptance")
            question = job.question(slot, journal.accepted)["question"]
            journal.add("REUSE", slot=slot, source_execution=source.job.execution_id,
                        source_slot=source_slot, source_evidence=receipt["evidence"],
                        question_id=c.domain_hash(QUESTION_TAG, question))
            if len(journal.accepted) == checkpoint:
                return journal, "CHECKPOINT"
            continue
        worker, verifier = placement[slot]
        attempt = 1
        while True:
            if dispatch is None:
                request = journal.frame(slot, attempt, "SOLVE")
                try:
                    journal.add("RESERVE", slot=slot, attempt=attempt, worker=worker, request=request)
                except BudgetError:
                    return journal, "BUDGET_BLOCKED"
                try:
                    response = exchange(worker, request)
                except OSError:
                    journal.add("NO_REPLY", slot=slot, attempt=attempt)
                    if attempt == 2:
                        return journal, "NO_REPLY"
                    attempt += 1
                    worker = next_worker(worker, verifier, roles, retry_worker, retry_remote)
                    continue
            else:
                opened = activate(dispatch, worker, verifier, roles, journal.epoch,
                                  slot=slot, attempt=attempt, action="SOLVE",
                                  retry_worker=retry_worker, retry_remote=retry_remote)
                if opened is None:
                    return journal, "DISPATCH_UNAVAILABLE"
                worker, boot, session = opened
                request = journal.frame(slot, attempt, "SOLVE", boot=boot)
                try:
                    journal.add("RESERVE", slot=slot, attempt=attempt, worker=worker,
                                request=request, boot=boot)
                except BudgetError:
                    session.close()
                    return journal, "BUDGET_BLOCKED"
                except BaseException:
                    session.close()
                    raise
                try:
                    response = session.request(request)
                except OSError:
                    session.close()
                    journal.add("NO_REPLY", slot=slot, attempt=attempt)
                    if attempt == 2:
                        return journal, "NO_REPLY"
                    attempt += 1
                    worker = next_worker(worker, verifier, roles, retry_worker, retry_remote)
                    continue
                except BaseException:
                    session.close()
                    raise
                session.close()
            journal.add("ANSWER", slot=slot, attempt=attempt, response=response)
            answer = journal.attempts[slot, attempt]["answer"]
            if dispatch is None:
                request = journal.frame(slot, attempt, "VERIFY", answer)
                response = exchange(verifier, request)
                journal.add("ACCEPT", slot=slot, attempt=attempt, verifier=verifier,
                            request=request, response=response)
            else:
                boot, session = dispatch.open(verifier, journal.epoch, slot=slot,
                                              attempt=attempt, action="VERIFY")
                request = journal.frame(slot, attempt, "VERIFY", answer, boot=boot)
                try:
                    response = session.request(request)
                finally:
                    session.close()
                journal.add("ACCEPT", slot=slot, attempt=attempt, verifier=verifier,
                            request=request, response=response, boot=boot)
            break
        if len(journal.accepted) == checkpoint:
            return journal, "CHECKPOINT"
    journal.add("PUBLISH")
    return journal, "PUBLISHED"


def wire_name(raw):
    value = c.decode(raw)
    return f'{value["epoch"]}-{value["slot"]}-{value["attempt"]}-{value["action"]}'


def serve(role, port, executor, output, *, drop_first_b, sort_job=None, inject=None,
          exit_on_fault=False, restart=False, address=None, peer=None):
    """Serve the authenticated-by-topology peer in this trusted VM experiment.

    Each connection opens with one BOOT frame that binds this serving boot and the
    epoch to the request that follows.  A request that cannot be bound to this boot
    is recorded and refused without executing it; the serving process stays up.
    """
    worker = ServingBoot(role, output, restart=restart)
    host = guest_ip(role) if address is None else address
    coordinator = guest_ip("A") if peer is None else peer
    with closing(socket.create_server((host, port))) as listener:
        listener.settimeout(120)
        while True:
            connection, address = listener.accept()
            with connection:
                connection.settimeout(TIMEOUT)
                c.need(address[0] == coordinator, "unexpected coordinator address")
                bounds = dict(local_socket_ip=connection.getsockname()[0],
                              peer_socket_ip=address[0])
                try:
                    raw = receive(connection)
                except OSError:
                    # A readiness probe may connect and close without a frame; it must not
                    # stop the service or count as an attempt.
                    continue
                if raw == STOP:
                    worker.control("stop", len(raw))
                    return bounds
                request = c.decode(raw)
                action = request.get("action")
                if action == "RESTART":
                    if not worker.restart_enabled:
                        worker.reject("unknown-action", kind="RESTART", raw=raw, request=request)
                        continue
                    worker.restart(len(raw))
                    if exit_on_fault:
                        # A real non-zero exit; the in-guest supervisor starts a new serving
                        # process, so later requests can only be bound to a new boot.
                        sys.stdout.flush()
                        os._exit(WORKER_EXIT_CODE)
                    raise WorkerExit(role, "RESTART", bounds["local_socket_ip"], bounds["peer_socket_ip"])
                if action != "BOOT":
                    worker.reject("unactivated", raw=raw, request=request)
                    continue
                reply, activation = worker.activate(raw)
                if reply is None:
                    continue
                send(connection, reply)
                try:
                    raw = receive(connection)
                except OSError:
                    continue
                if raw == STOP:
                    worker.control("stop", len(raw))
                    return bounds
                request = c.decode(raw)
                reason = worker.admit(request, activation)
                if reason is not None:
                    worker.reject(reason, raw=raw, request=request, activation=activation)
                    continue
                name = wire_name(raw)
                (output / f"{name}-request.cbor").write_bytes(raw)
                if inject is not None and inject.matches(request):
                    if inject.mode == "no_reply":
                        # Generate and keep the reply, record the suppression, never send it.
                        response = worker.execute(raw, executor)
                        (output / f"{name}-response.cbor").write_bytes(response)
                        worker.withhold(raw, response)
                        inject.hit(request, raw, role, response)
                        continue
                    inject.hit(request, raw, role)
                    if inject.mode == "worker_exit":
                        if exit_on_fault:
                            # A real non-zero exit of the worker process (R1 section 4); the
                            # kernel closes its sockets and the supervisor observes the status.
                            sys.stdout.flush()
                            os._exit(WORKER_EXIT_CODE)
                        raise WorkerExit(role, name, bounds["local_socket_ip"], bounds["peer_socket_ip"])
                    if inject.mode == "tcp_disconnect":
                        try:
                            connection.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                        connection.close()
                        inject.observe(request, role, "closed")
                    continue
                drop = drop_first_b and name == "0-1-1-SOLVE"
                response_path = output / f"{name}-response.cbor"
                if sort_job is None:
                    response = worker.execute(raw, executor)
                    response_path.write_bytes(response)
                    if drop:
                        worker.withhold(raw, response)
                    else:
                        send(connection, response)
                else:
                    from sort_contract import respond
                    respond(sort_job, raw, connection, response_path, drop=drop)


def replay(job, roots, executor, previous=(), *, check_response=None, source=None,
           journal_path=None, suppressed_reply=False):
    """Check all requests and recompute the retained peer responses before replaying."""
    journal_path = Path(journal_path) if journal_path is not None else roots["A"] / "journal.cbor"
    events = c.decode(journal_path.read_bytes())
    c.need(events[:len(previous)] == list(previous), "successor changed retained history")
    journal = Journal(job, journal_path, events, source=source)
    expected = {role: set() for role in roots}
    for event in events[len(previous):]:
        kind = event["kind"]
        if kind not in ("RESERVE", "ACCEPT"):
            continue
        role = event["worker" if kind == "RESERVE" else "verifier"]
        raw = event["request"]
        name = wire_name(raw)
        request_file = f"{name}-request.cbor"
        response_file = f"{name}-response.cbor"
        expected["A"].add(request_file)
        for endpoint in {role, "A"}:
            c.need((roots[endpoint] / request_file).read_bytes() == raw, "peer request differs")
        received = event["response"] if kind == "ACCEPT" else None
        if kind == "RESERVE":
            outcome = [e for e in events if e["kind"] in ("ANSWER", "NO_REPLY")
                       and (e["slot"], e["attempt"]) == (event["slot"], event["attempt"])]
            c.need(len(outcome) == 1, "attempt has no unique disposition")
            if outcome[0]["kind"] == "ANSWER":
                received = outcome[0]["response"]
            else:
                expected[role].add(request_file)
                c.need(not (roots["A"] / response_file).exists(),
                       "coordinator retained a reply it did not receive")
                if suppressed_reply and role != "A":
                    # no_reply or drop: the worker generated the reply and withheld it.
                    expected[role].add(response_file)
                    c.need((roots[role] / response_file).is_file(),
                           "suppressed reply was not retained by the worker")
                    withheld = (roots[role] / response_file).read_bytes()
                    if check_response is None:
                        c.need(withheld == handle(raw, executor),
                               "suppressed reply differs from the recomputed reply")
                    else:
                        # The sort family needs its own retained-image check here.
                        check_response(raw, withheld, roots[role], True)
                else:
                    c.need(not (roots[role] / response_file).exists(),
                           "missing reply has a response frame")
                continue
        expected[role].update((request_file, response_file))
        response = (roots[role] / response_file).read_bytes()
        if check_response is None:
            c.need(response == handle(raw, executor), "peer response differs")
        else:
            check_response(raw, response, roots[role], received is None)
        if received is not None:
            expected["A"].add(response_file)
            c.need(received == response == (roots["A"] / response_file).read_bytes(),
                   "journal reply differs from coordinator or worker frame")
    for role, root in roots.items():
        actual = {path.name for path in root.glob("*-*.cbor")}
        c.need(actual == expected[role], "peer frame inventory differs")
    return journal


def source_journal(job, path, executor):
    events = c.decode(path.read_bytes())
    source = Journal(job, path, events)
    c.need(source.final is not None, "source execution did not publish")
    for event in source.events:
        if event["kind"] == "ACCEPT":
            c.need(handle(event["request"], executor) == event["response"], "source verification differs")
    return source


def _frame_records(root):
    """Return the retained request/response frames of one endpoint with sizes."""
    rows = []
    for path in sorted(Path(root).glob("*-*.cbor")):
        name = path.name
        if name.endswith("-request.cbor"):
            action = name[: -len("-request.cbor")].rsplit("-", 1)[-1]
            direction = "request"
        elif name.endswith("-response.cbor"):
            action = name[: -len("-response.cbor")].rsplit("-", 1)[-1]
            direction = "response"
        else:
            continue
        rows.append(dict(direction=direction, action=action, bytes=path.stat().st_size,
                         sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return rows


def _payload_bytes(path):
    """Application payload carried by one retained request frame (derived value)."""
    try:
        value = c.decode(path.read_bytes())
    except Exception:
        return 0
    total = 0
    for key in ("artifact", "data", "dependency", "answer"):
        item = value.get(key)
        if type(item) is bytes:
            total += len(item)
    return total


def check_restart_resend(roots, journal, executor, *, scenario, target=(1, 1)):
    """Check one recorded C1 run and return its split observation summary.

    The checks bind every frozen request to the serving boot that was activated
    immediately before it, require at most one execution per (execution, slot,
    attempt, action), and require every recorded resend to be refused without an
    execution.  Execution counts and refusal reasons come from the workers' durable
    records, never from the coordinator's accounting.
    """
    c.need(scenario in ("restart", "duplicate", "stale"), "unknown C1 scenario")
    roles = tuple(roots)
    c.need("A" in roles and len(roles) >= 3, "C1 evidence needs the coordinator and two workers")
    boots = {}
    for role in roles:
        rows = read_lines(Path(roots[role]) / "boots.jsonl")
        boots[role] = [row["boot"] for row in rows]
        if role != "A":
            c.need(boots[role], f"{role} recorded no serving boot")
        c.need(len(set(boots[role])) == len(boots[role]), f"{role} repeated a boot identifier")

    activations = {}
    for role in roles:
        if role == "A":
            continue
        for row in read_lines(Path(roots[role]) / "activations.jsonl"):
            if not row.get("accepted"):
                continue
            key = row["dispatch"]
            c.need(key not in activations, f"dispatch {key} was activated twice")
            activations[key] = dict(role=role, epoch=row["epoch"], boot=row["boot"])

    dispatches = read_lines(Path(roots["A"]) / "dispatch.jsonl")
    activated = {}
    for row in dispatches:
        if row.get("event") != "activation":
            continue
        sequence = row["sequence"]
        if row["role"] == "A":
            continue
        c.need(sequence in activations, f"A dispatched {sequence} that no worker activated")
        worker = activations[sequence]
        c.need(worker["role"] == row["role"] and worker["epoch"] == row["epoch"]
               and worker["boot"] == row["boot"],
               f"dispatch {sequence} binding differs between A and {row['role']}")
        activated[(row["role"], row["slot"], row["attempt"], row["action"])] = row["boot"]

    handoff = next((index for index, event in enumerate(journal.events)
                    if event["kind"] == "HANDOFF"), None)
    for index, event in enumerate(journal.events):
        if handoff is not None and index < handoff:
            # Retained history belongs to the previous coordinator phase and its own
            # dispatch records; only the current phase is bound to this evidence root.
            continue
        if event["kind"] == "RESERVE":
            key = (event["worker"], event["slot"], event["attempt"], "SOLVE")
        elif event["kind"] == "ACCEPT":
            key = (event["verifier"], event["slot"], event["attempt"], "VERIFY")
        else:
            continue
        c.need("boot" in event, f"{key} has no serving boot")
        c.need(event["boot"].hex() == activated.get(key),
               f"{key} boot differs from the activation that preceded it")

    executions = []
    for role in roles:
        if role == "A":
            continue
        for row in read_lines(Path(roots[role]) / "executions.jsonl"):
            c.need(row["event"] in ("execute-begin", "execute-end"), "unknown execution record")
            executions.append(row)
    begins = [row for row in executions if row["event"] == "execute-begin"]
    key_fields = ("boot", "execution_id", "slot", "attempt", "action")
    keys = [tuple(row[field] for field in key_fields) for row in begins]
    c.need(len(keys) == len(set(keys)), "one boot executed the same attempt twice")
    frames_by_boot = [(row["boot"], row["request_sha256"]) for row in begins]
    c.need(len(frames_by_boot) == len(set(frames_by_boot)),
           "one boot executed the same frozen request twice")
    attempt_keys = [(row["execution_id"], row["slot"], row["attempt"], row["action"])
                    for row in begins]
    c.need(len(attempt_keys) == len(set(attempt_keys)),
           "one attempt and action executed on more than one boot")
    for row in begins:
        ends = [other for other in executions
                if other["event"] == "execute-end"
                and all(other[field] == row[field] for field in key_fields)]
        c.need(len(ends) == 1, "an execution has no unique completion record")

    # Every execution the journal and the retained frames require must have both
    # records, bound to the same attempt, boot, request and reply.  Missing, orphaned
    # or misbound records are refused; recomputing a frame cannot replace them.
    expected = []
    for index, event in enumerate(journal.events):
        if handoff is not None and index < handoff:
            continue
        if event["kind"] == "RESERVE":
            role, action = event["worker"], "SOLVE"
            disposition = [other for other in journal.events
                           if other["kind"] in ("ANSWER", "NO_REPLY")
                           and (other["slot"], other["attempt"]) == (event["slot"], event["attempt"])]
            c.need(len(disposition) == 1, "an attempt has no unique disposition")
            path = Path(roots[role]) / f"{wire_name(event['request'])}-response.cbor"
            if disposition[0]["kind"] == "ANSWER":
                c.need(path.is_file(), "an answered solve retained no reply")
            if not path.is_file():
                # No retained reply means the serving side never wrote one, so no
                # execution record may exist for it either.
                continue
        elif event["kind"] == "ACCEPT":
            role, action = event["verifier"], "VERIFY"
            path = Path(roots[role]) / f"{wire_name(event['request'])}-response.cbor"
            c.need(path.is_file(), "an accepted verification retained no reply")
        else:
            continue
        expected.append((role, event["boot"].hex(), action, event["slot"], event["attempt"],
                         event["request"], path))
    c.need(all(role != "A" for role, *_ in expected),
           "the C1 evidence expects no coordinator-side execution")
    by_key = {}
    for row in begins:
        by_key.setdefault((row["boot"], row["request_sha256"]), []).append(row)
    for role, boot, action, slot, attempt, raw, path in expected:
        request_sha = hashlib.sha256(raw).hexdigest()
        records = by_key.get((boot, request_sha), [])
        c.need(len(records) == 1,
               f"{action} {request_sha[:12]} has no unique execution record")
        record = records[0]
        c.need((record["action"], record["slot"], record["attempt"]) == (action, slot, attempt),
               f"{action} {request_sha[:12]} execution record is bound to another attempt")
        c.need(record.get("request_bytes") == len(raw),
               f"{action} {request_sha[:12]} execution record has another request size")
        ends = [other for other in executions
                if other["event"] == "execute-end"
                and all(other[field] == record[field] for field in key_fields)]
        c.need(len(ends) == 1,
               f"{action} {request_sha[:12]} has no unique completion record")
        reply = path.read_bytes()
        c.need(ends[0]["response_sha256"] == hashlib.sha256(reply).hexdigest(),
               f"{action} {request_sha[:12]} completion record binds another reply")
        c.need(ends[0].get("response_bytes") == len(reply),
               f"{action} {request_sha[:12]} completion record has another reply size")
    expected_keys = {(boot, hashlib.sha256(raw).hexdigest())
                     for role, boot, action, slot, attempt, raw, path in expected}
    c.need({(row["boot"], row["request_sha256"]) for row in begins} == expected_keys,
           "execution records do not match the retained dispatches")

    rejections = []
    for role in roles:
        if role == "A":
            continue
        for row in read_lines(Path(roots[role]) / "rejections.jsonl"):
            rejections.append((role, row))
            c.need(row.get("reason") in ("unactivated", "epoch-mismatch", "boot-mismatch",
                                         "duplicate", "stale-epoch", "unknown-action"),
                   "unknown refusal reason")
            if row.get("reason") in ("boot-mismatch", "epoch-mismatch") \
                    and row.get("request_sha256"):
                # A frame for another boot or epoch may never execute where it was refused.
                same = [begin for begin in begins
                        if begin["boot"] == row["boot"]
                        and begin["request_sha256"] == row["request_sha256"]]
                c.need(not same, "a refused foreign-boot or stale-epoch frame was executed")

    probes = read_lines(Path(roots["A"]) / "resends.jsonl")
    if scenario in ("restart", "duplicate"):
        reserve = next((event for event in journal.events
                        if event["kind"] == "RESERVE"
                        and (event["slot"], event["attempt"]) == target), None)
        c.need(reserve is not None, "the dropped attempt has no reservation")
        c.need(journal.attempts[target]["state"] == "NO_REPLY",
               "the dropped attempt is not recorded as unanswered")
        old_boot, old_sha = reserve["boot"].hex(), hashlib.sha256(reserve["request"]).hexdigest()
        retries = [event for event in journal.events
                   if event["kind"] == "RESERVE"
                   and (event["slot"], event["attempt"]) == (target[0], target[1] + 1)]
        c.need(len(retries) == 1 and retries[0]["boot"].hex() != old_boot,
               "the retry did not use a different serving boot")
        executed = [row for row in begins if row["boot"] == old_boot
                    and row["request_sha256"] == old_sha]
        c.need(len(executed) == 1, "the dropped attempt did not execute exactly once")
        expected = "boot-mismatch" if scenario == "restart" else "duplicate"
        for kind, reason in (("bare", "unactivated"), ("boot", expected)):
            rows = [row for row in probes
                    if row.get("probe") == kind and row.get("request_sha256") == old_sha]
            c.need(len(rows) == 1 and rows[0]["outcome"] == "refused",
                   f"{kind} resend was not refused")
            c.need(any(row.get("request_sha256") == old_sha and row.get("reason") == reason
                       for _, row in rejections),
                   f"{kind} resend has no {reason} refusal record")
        if scenario == "restart":
            restarts = [row for row in probes if row.get("event") == "restart"]
            c.need(len(restarts) == 1 and restarts[0]["previous_boot"] == old_boot
                   and restarts[0]["boot"] != old_boot,
                   "the restart record does not separate the two serving boots")
        c.need(not [row for row in begins if row["request_sha256"] == old_sha
                    and row["boot"] != old_boot],
               "a resent frame executed on another boot")
    else:
        c.need(handoff is not None, "the stale scenario has no handoff")
        prefix = journal.events[:handoff]
        stale = [(event["worker"], event["request"]) for event in prefix
                 if event["kind"] == "RESERVE"]
        stale += [(event["verifier"], event["request"]) for event in prefix
                  if event["kind"] == "ACCEPT"]
        c.need(stale, "the stale scenario retained no pre-handoff request")
        for role, raw in stale:
            sha = hashlib.sha256(raw).hexdigest()
            epoch = c.decode(raw)["epoch"]
            rows = {kind: [row for row in probes
                           if row.get("probe") == kind and row.get("request_sha256") == sha]
                    for kind in ("bare", "old-boot", "boot")}
            c.need(len(rows["bare"]) == 1 and rows["bare"][0]["outcome"] == "refused",
                   "the stale frame was not refused when replayed alone")
            c.need(len(rows["old-boot"]) == 1
                   and rows["old-boot"][0]["outcome"] == "activation-refused",
                   "the stale activation was not refused")
            c.need(len(rows["boot"]) == 1 and rows["boot"][0]["outcome"] == "refused",
                   "the stale frame was not refused after a current activation")
            c.need(any(row.get("request_sha256") == sha and row.get("reason") == "unactivated"
                       for _, row in rejections), "the stale frame has no unactivated refusal")
            c.need(any(row.get("request_sha256") == sha and row.get("reason") == "epoch-mismatch"
                       for _, row in rejections), "the stale frame has no epoch-mismatch refusal")
            c.need(any(row.get("epoch") == epoch and row.get("accepted") is False
                       and row.get("reason") == "stale-epoch"
                       for other in roles if other != "A"
                       for row in read_lines(Path(roots[other]) / "activations.jsonl")),
                   "the stale epoch has no stale-epoch activation refusal")
            c.need(not [row for row in begins if row["request_sha256"] == sha],
                   "a stale frame executed after the handoff")

    # Frames actually sent and received, taken from each side's own records.  Retained
    # frame files are reported apart: a retained reply may never have been sent, and a
    # repeated probe send leaves no extra file.
    def add(store, cls, count, size):
        if not count:
            return
        entry = store.setdefault(cls, dict(count=0, bytes=0))
        entry["count"] += count
        entry["bytes"] += size

    coordinator_sent, coordinator_received = {}, {}
    worker_sent, worker_received = {}, {}
    for row in dispatches:
        if row.get("event") == "activation":
            add(coordinator_sent, "BOOT", 1, row["request_bytes"])
            if row.get("response_bytes") is not None:
                add(coordinator_received, "BOOT", 1, row["response_bytes"])
        elif row.get("event") == "outcome":
            add(coordinator_sent, row["action"], 1, row["request_bytes"])
            if row.get("response_bytes") is not None:
                add(coordinator_received, row["action"], 1, row["response_bytes"])
        elif row.get("event") == "stop" and row.get("sent_bytes"):
            add(coordinator_sent, "STOP", 1, row["sent_bytes"])
    for row in probes:
        event = row.get("event")
        if event == "probe":
            if row.get("boot_bytes"):
                add(coordinator_sent, "BOOT", 1, row["boot_bytes"])
            if row.get("boot_reply_bytes"):
                add(coordinator_received, "BOOT", 1, row["boot_reply_bytes"])
            if row.get("raw_sent_bytes"):
                add(coordinator_sent, row["request_action"], 1, row["raw_sent_bytes"])
            if row.get("reply_bytes"):
                add(coordinator_received, row["request_action"], 1, row["reply_bytes"])
        elif event == "wait_boot":
            if row.get("sent_bytes"):
                add(coordinator_sent, "BOOT", row.get("attempts") or 0, row["sent_bytes"])
            if row.get("received_bytes"):
                add(coordinator_received, "BOOT", row.get("replies") or 0,
                    row["received_bytes"])
        elif event == "restart_sent" and row.get("sent_bytes"):
            add(coordinator_sent, "RESTART", 1, row["sent_bytes"])
    worker_withheld, withheld_keys = {}, set()
    for role in roles:
        if role == "A":
            continue
        for row in read_lines(Path(roots[role]) / "withheld.jsonl"):
            add(worker_withheld, row["action"], 1, row["response_bytes"])
            withheld_keys.add((row["boot"], row["execution_id"], row["slot"],
                               row["attempt"], row["action"]))
    for role in roles:
        if role == "A":
            continue
        for row in read_lines(Path(roots[role]) / "activations.jsonl"):
            add(worker_received, "BOOT", 1, row["request_bytes"])
            if row.get("accepted"):
                add(worker_sent, "BOOT", 1, row["response_bytes"])
        for row in read_lines(Path(roots[role]) / "executions.jsonl"):
            if row["event"] == "execute-begin":
                add(worker_received, row["action"], 1, row["request_bytes"])
                continue
            key = (row["boot"], row["execution_id"], row["slot"], row["attempt"], row["action"])
            if key in withheld_keys:
                continue
            add(worker_sent, row["action"], 1, row["response_bytes"])
        for row in read_lines(Path(roots[role]) / "rejections.jsonl"):
            if row.get("request_bytes"):
                add(worker_received, row.get("kind") or "UNKNOWN", 1, row["request_bytes"])
        for row in read_lines(Path(roots[role]) / "controls.jsonl"):
            add(worker_received, row["event"].upper(), 1, row["request_bytes"])
    zero = dict(count=0, bytes=0)
    in_flight = {}
    for sent, received, label in ((coordinator_sent, worker_received, "coordinator to worker"),
                                  (worker_sent, coordinator_received, "worker to coordinator")):
        difference = {}
        for cls in sorted(set(sent) | set(received)):
            sent_row, received_row = sent.get(cls, zero), received.get(cls, zero)
            c.need(received_row["count"] <= sent_row["count"]
                   and received_row["bytes"] <= sent_row["bytes"],
                   f"{label} {cls} frames were received but not recorded as sent")
            if sent_row != received_row:
                difference[cls] = dict(count=sent_row["count"] - received_row["count"],
                                       bytes=sent_row["bytes"] - received_row["bytes"])
        in_flight[label] = difference
    if scenario != "restart":
        # Without a serving-process restart no frame may be lost in flight, so both
        # sides must agree exactly.
        for label, difference in in_flight.items():
            c.need(not difference,
                   f"{label} frames differ between the sending and receiving records: {difference}")

    def totals_by_action(rows):
        result = {}
        for row in rows:
            entry = result.setdefault(row["action"], dict(count=0, bytes=0))
            entry["count"] += 1
            entry["bytes"] += row["bytes"]
        return dict(sorted(result.items()))

    worker_request_files, worker_response_files = [], []
    for role in roles:
        if role == "A":
            continue
        for row in _frame_records(roots[role]):
            (worker_request_files if row["direction"] == "request"
             else worker_response_files).append(row)
    retained = {
        "coordinator_requests": totals_by_action(
            [row for row in _frame_records(roots["A"]) if row["direction"] == "request"]),
        "coordinator_responses": totals_by_action(
            [row for row in _frame_records(roots["A"]) if row["direction"] == "response"]),
        "worker_requests": totals_by_action(worker_request_files),
        "worker_responses": totals_by_action(worker_response_files),
    }
    payload = {}
    for path in Path(roots["A"]).glob("*-request.cbor"):
        name = path.name[: -len("-request.cbor")]
        action = name.rsplit("-", 1)[-1]
        entry = payload.setdefault(action, dict(count=0, bytes=0))
        entry["count"] += 1
        entry["bytes"] += _payload_bytes(path)
    reasons = {}
    for _, row in rejections:
        reasons[row["reason"]] = reasons.get(row["reason"], 0) + 1
    executions_by_action = {}
    for row in begins:
        executions_by_action[row["action"]] = executions_by_action.get(row["action"], 0) + 1
    return dict(
        scenario=scenario,
        boots={role: len(boots[role]) for role in roles},
        executions=executions_by_action,
        execution_keys=len(begins),
        rejections=reasons,
        frames=dict(coordinator_sent=coordinator_sent, coordinator_received=coordinator_received,
                    worker_sent=worker_sent, worker_received=worker_received,
                    worker_withheld=worker_withheld, in_flight=in_flight, retained=retained),
        payload=dict(sorted(payload.items())),
        probes=len(probes),
        charged=journal.charged,
        reserved=journal.reserved,
        accepted=sorted(journal.accepted),
        merge_ns=json.loads((Path(roots["A"]) / "guest.json").read_text()).get("merge_ns"),
    )