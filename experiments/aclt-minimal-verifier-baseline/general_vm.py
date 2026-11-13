# SPDX-License-Identifier: Apache-2.0
"""Local multi-VM acceptance for the experimental integer-vector job family."""

from contextlib import closing
import json
import socket

from baseline import ARTIFACT_TAG, PROBE, ask, solve, validate
from general_job import BudgetError, FAMILY, INT, Job, Journal, digest, handle
from multivm_job import assignments, guest_ip
from tools.formal_migration.s2_transport import receive, send
from tools.verification_profile import codec as c
from wasm import artifact as encode_artifact

CAPS = [8232, 8232, 8242, 8232]
DEFAULT_BUDGET = sum(CAPS) + CAPS[1]
STOP = c.encode({"action": "STOP"})
TIMEOUT = 30


def artifact_module():
    row = next(row for row in json.loads((PROBE / "tests/independent-vectors.json").read_bytes())["vectors"]
               if row["id"] == "divzero")
    return validate(bytes.fromhex(row["artifact_hex"]), row["limits"])


def program(module, instructions):
    module.code[module.run - len(module.imports)] = (
        [], [dict(op=code, args=args) for code, *args in instructions],
    )
    return encode_artifact(module.canonical())


def fixture(nonce, budget, *, flat=False):
    module = artifact_module()
    read = [(0x41, 0), (0x42, 0), (0x41, 0), (0x41, 8), (0x10, 2)]
    double = [(0x41, 0), (0x41, 0), (0x29, 3, 0), (0x42, 2), (0x7e,), (0x37, 3, 0)]
    write = [(0x41, 0), (0x41, 8), (0x10, 3)]
    artifacts = {op: program(module, read + middle + write)
                 for op, middle in (("copy", []), ("double", double))}
    declaration = c.encode(dict(family=FAMILY, tasks=[{"literal": 2}, {"literal": 3},
                                                     {"double": 0}, {"literal": 11}]))
    plan = c.encode(dict(family=FAMILY, tree=[0, 1, 2, 3] if flat else [[0, 1], [2, 3]],
                         dependencies={2: 0}, caps=CAPS,
                         artifacts={op: c.domain_hash(ARTIFACT_TAG, raw) for op, raw in artifacts.items()}))
    execution = c.encode(dict(declaration_id=digest("Declaration", declaration), plan_id=digest("Plan", plan),
                              nonce=nonce, budget=budget))
    return Job(declaration, plan, execution, artifacts)


def standalone_probe(job, gas_limit):
    """Run the same whole problem as an external single-machine control."""
    tasks = job.tasks
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


def run(job, roles, path, exchange, *, order, checkpoint=0, previous=None):
    history = c.decode(previous.read_bytes()) if previous else ()
    journal = Journal(job, path, history)
    if previous:
        journal.add("HANDOFF", epoch=journal.epoch + 1)
    else:
        journal.add("START", execution=job.execution)
    while journal.ready():
        slot = next(slot for slot in order if slot in journal.ready())
        worker, verifier = assignments(roles, len(job.tasks))[slot]
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


def serve(role, port, executor, output, *, drop_first_b):
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
                response = handle(raw, executor)
                (output / f"{name}-response.cbor").write_bytes(response)
                if not (drop_first_b and name == "0-1-1-SOLVE"):
                    send(connection, response)


def replay(job, roots, executor, previous=()):
    """Check all requests and recompute the retained peer responses before replaying."""
    journal_path = roots["A"] / "journal.cbor"
    events = c.decode(journal_path.read_bytes())
    c.need(events[:len(previous)] == list(previous), "successor changed retained history")
    journal = Journal(job, journal_path, events)
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
        expected[role].update((request_file, response_file))
        expected["A"].add(request_file)
        for endpoint in {role, "A"}:
            c.need((roots[endpoint] / request_file).read_bytes() == raw, "peer request differs")
        response = handle(raw, executor)
        c.need((roots[role] / response_file).read_bytes() == response, "peer response differs")
        received = event["response"] if kind == "ACCEPT" else None
        if kind == "RESERVE":
            outcome = [e for e in events if e["kind"] in ("ANSWER", "NO_REPLY")
                       and (e["slot"], e["attempt"]) == (event["slot"], event["attempt"])]
            c.need(len(outcome) == 1, "attempt has no unique disposition")
            if outcome[0]["kind"] == "ANSWER":
                received = outcome[0]["response"]
            else:
                c.need(name == "0-1-1-SOLVE" and role == "B", "unexpected missing reply")
        if received is not None:
            expected["A"].add(response_file)
            c.need(received == response == (roots["A"] / response_file).read_bytes(),
                   "journal reply differs from coordinator or worker frame")
    for role, root in roots.items():
        actual = {path.name for path in root.glob("*-*.cbor")}
        c.need(actual == expected[role], "peer frame inventory differs")
    return journal
