# SPDX-License-Identifier: Apache-2.0
"""Local multi-VM acceptance for the experimental integer-vector job family."""

from contextlib import closing
import json
import socket
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
TIMEOUT = 30


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

    def hit(self, request):
        self.hits.append({"mode": self.mode, "slot": request["slot"],
                          "attempt": request["attempt"], "loss": self.loss})


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


def run(job, roles, path, exchange, *, order, checkpoint=0, previous=None,
        placement=None, retry_worker=None, retry_remote=False, source=None, reuse=None,
        journal_factory=Journal):
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
                if retry_worker is not None:
                    worker = retry_worker(worker)
                elif retry_remote:
                    candidates = [role for role in roles[1:] if role not in (worker, verifier)]
                    worker = candidates[0] if candidates else next(
                        role for role in roles if role not in (worker, verifier))
                else:
                    worker = next(role for role in roles if role not in (worker, verifier))
                continue
            journal.add("ANSWER", slot=slot, attempt=attempt, response=response)
            answer = journal.attempts[slot, attempt]["answer"]
            request = journal.frame(slot, attempt, "VERIFY", answer)
            response = exchange(verifier, request)
            journal.add("ACCEPT", slot=slot, attempt=attempt, verifier=verifier, request=request, response=response)
            break
        if len(journal.accepted) == checkpoint:
            return journal, "CHECKPOINT"
    journal.add("PUBLISH")
    return journal, "PUBLISHED"


def wire_name(raw):
    value = c.decode(raw)
    return f'{value["epoch"]}-{value["slot"]}-{value["attempt"]}-{value["action"]}'


def serve(role, port, executor, output, *, drop_first_b, sort_job=None, inject=None):
    """Serve the authenticated-by-topology peer in this trusted VM experiment."""
    seen = set()
    with closing(socket.create_server((guest_ip(role), port))) as listener:
        listener.settimeout(120)
        while True:
            connection, address = listener.accept()
            with connection:
                connection.settimeout(TIMEOUT)
                c.need(address[0] == guest_ip("A"), "unexpected coordinator address")
                raw = receive(connection)
                if raw == STOP:
                    return dict(local_socket_ip=connection.getsockname()[0], peer_socket_ip=address[0])
                request = c.decode(raw)
                key = (request["execution_id"], request["slot"], request["attempt"], request["action"])
                c.need(key not in seen, "duplicate attempt request")
                seen.add(key)
                name = wire_name(raw)
                (output / f"{name}-request.cbor").write_bytes(raw)
                if inject is not None and inject.matches(request):
                    inject.hit(request)
                    if inject.mode == "worker_exit":
                        raise WorkerExit(role, name, connection.getsockname()[0], address[0])
                    if inject.mode == "tcp_disconnect":
                        try:
                            connection.shutdown(socket.SHUT_RDWR)
                        except OSError:
                            pass
                    continue
                drop = drop_first_b and name == "0-1-1-SOLVE"
                response_path = output / f"{name}-response.cbor"
                if sort_job is None:
                    response = handle(raw, executor)
                    response_path.write_bytes(response)
                    if not drop:
                        send(connection, response)
                else:
                    from sort_contract import respond
                    respond(sort_job, raw, connection, response_path, drop=drop)


def replay(job, roots, executor, previous=(), *, check_response=None, source=None,
           journal_path=None):
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
