# SPDX-License-Identifier: Apache-2.0
"""Trusted experimental distributed job records and deterministic replay."""

from dataclasses import dataclass
from pathlib import Path
import os
import struct
from threading import RLock

from baseline import ARTIFACT_TAG, QUESTION_TAG, ask, solve, verify
from lan import decode_answer, encode_answer
from tools.verification_profile import codec as c

PREFIX = "ACLt/Experiment/DistributedJob/1/"
FAMILY = "integer-vector/1"
INT = struct.Struct("<q")


class BudgetError(c.CodecError):
    """The required reservation exceeds the execution budget."""


def digest(kind, raw):
    return c.domain_hash(PREFIX + kind, raw)


def leaves(tree):
    if type(tree) is int:
        return [c.uint(tree)]
    c.need(type(tree) is list and len(tree) >= 2, "invalid merge node")
    return [slot for child in tree for slot in leaves(child)]


def merge(tree, outputs):
    if type(tree) is int:
        return [INT.unpack(outputs[tree])[0]]
    return [value for child in tree for value in merge(child, outputs)]


@dataclass(frozen=True)
class Job:
    declaration: bytes
    plan: bytes
    execution: bytes
    artifacts: dict

    def __post_init__(self):
        declaration = c.decode(self.declaration)
        plan = c.decode(self.plan)
        execution = c.decode(self.execution)
        c.fields(declaration, ("family", "tasks"))
        c.fields(plan, ("family", "tree", "dependencies", "caps", "artifacts"))
        c.fields(execution, ("declaration_id", "plan_id", "nonce", "budget"))
        c.need(declaration["family"] == plan["family"] == FAMILY, "unsupported task family")
        tasks = declaration["tasks"]
        c.need(type(tasks) is list and 1 <= len(tasks) <= 16, "unsupported task count")
        c.need(leaves(plan["tree"]) == list(range(len(tasks))), "tree must cover slots in declaration order")
        c.need(type(plan["caps"]) is list and len(plan["caps"]) == len(tasks), "caps must cover slots")
        for cap in plan["caps"]:
            c.need(c.uint(cap) > 0, "empty attempt cap")
        c.fields(plan["artifacts"], ("copy", "double"))
        c.need(plan["artifacts"] == {op: c.domain_hash(ARTIFACT_TAG, raw)
                                    for op, raw in self.artifacts.items()}, "plan artifact mismatch")
        # Any acyclic path has at most len(tasks) - 1 doublings.
        literal_limit = (2**63 - 1) >> (len(tasks) - 1)
        for task in tasks:
            if type(task) is dict and "literal" in task:
                c.fields(task, ("literal",))
                c.need(type(task["literal"]) is int and abs(task["literal"]) <= literal_limit,
                       "literal exceeds the task family's safe i64 bound")
            else:
                c.fields(task, ("double",))
                c.need(c.uint(task["double"]) < len(tasks), "unknown dependency")
        expected_dependencies = {slot: task["double"] for slot, task in enumerate(tasks) if "double" in task}
        c.need(type(plan["dependencies"]) is dict, "dependencies must be a map")
        for slot, dependency in plan["dependencies"].items():
            c.uint(slot)
            c.uint(dependency)
        c.need(plan["dependencies"] == expected_dependencies, "plan changes declared dependencies")
        # All open events precede dispatch and merges depend only on their children.
        # In this family only leaf-to-leaf edges can complete an event cycle.
        unresolved = set(range(len(tasks)))
        while unresolved:
            ready = {slot for slot in unresolved if expected_dependencies.get(slot) not in unresolved}
            c.need(ready, "cyclic dependency")
            unresolved.difference_update(ready)
        c.need(execution["declaration_id"] == self.declaration_id
               and execution["plan_id"] == self.plan_id, "execution binding mismatch")
        c.digest_bytes(execution["nonce"])
        c.need(c.uint(execution["budget"]) >= sum(plan["caps"]), "first attempts exceed budget")

    @property
    def declaration_id(self):
        return digest("Declaration", self.declaration)

    @property
    def plan_id(self):
        return digest("Plan", self.plan)

    @property
    def execution_id(self):
        return digest("Execution", self.execution)

    @property
    def tasks(self):
        return c.decode(self.declaration)["tasks"]

    @property
    def dependencies(self):
        return c.decode(self.plan)["dependencies"]

    @property
    def caps(self):
        return c.decode(self.plan)["caps"]

    @property
    def budget(self):
        return c.decode(self.execution)["budget"]

    def question(self, slot, accepted):
        task = self.tasks[slot]
        dependency = b""
        if "literal" in task:
            artifact, data = self.artifacts["copy"], INT.pack(task["literal"])
        else:
            prior = accepted[self.dependencies[slot]]
            dependency = prior["evidence"]
            artifact, data = self.artifacts["double"], prior["output"]
        limits = dict(gas_limit=self.caps[slot], output_limit=8, memory_pages_limit=2, call_depth_limit=8)
        return dict(question=ask(artifact, data, limits), artifact=artifact, data=data, dependency=dependency)


def handle(raw, executor):
    """Execute a bounded request from the trusted coordinator."""
    request = c.decode(raw)
    action = request["action"]
    c.need(action in ("SOLVE", "VERIFY"), "unknown job action")
    c.fields(request, ("action", "execution_id", "slot", "attempt", "epoch",
                       "question", "artifact", "data", "dependency") + (("answer",) if action == "VERIFY" else ()))
    c.digest_bytes(request["execution_id"])
    if request["dependency"] != b"":
        c.digest_bytes(request["dependency"])
    for field in ("slot", "attempt", "epoch"):
        c.uint(request[field])
    args = [request[key] for key in ("question", "artifact", "data")]
    response = {"request": digest("Request", raw)}
    if action == "SOLVE":
        response["answer"] = encode_answer(solve(*args))
    else:
        response["verdict"] = verify(*args, decode_answer(request["answer"]), executor=executor).status
    return c.encode(response)


def response_for(raw, response, field):
    value = c.decode(response)
    c.fields(value, ("request", field))
    c.need(value["request"] == digest("Request", raw), "reply bound to different request")
    return value[field]


class Journal:
    """One trusted writer, with a durable transition before dispatch."""

    def __init__(self, job, path: Path, events=()):
        self.job = job
        self.path = path
        self.lock = RLock()
        self.events = []
        self.epoch = 0
        self.attempts = {}
        self.accepted = {}
        self.charged = 0
        self.reserved = 0
        self.final = None
        for event in events:
            self.apply(event)
            self.events.append(event)

    def ready(self):
        dependencies = self.job.dependencies
        return {slot for slot in range(len(self.job.tasks)) if slot not in self.accepted
                and (slot not in dependencies or dependencies[slot] in self.accepted)}

    def frame(self, slot, attempt, action, answer=None):
        fields = self.job.question(slot, self.accepted)
        fields.update(action=action, execution_id=self.job.execution_id, slot=slot,
                      attempt=attempt, epoch=self.epoch)
        if answer is not None:
            fields["answer"] = answer
        return c.encode(fields)

    def apply(self, event):
        kind = event["kind"]
        c.need(self.final is None, "execution already published")
        if kind == "START":
            c.fields(event, ("kind", "execution"))
            c.need(not self.events and event["execution"] == self.job.execution, "wrong start binding")
            return
        c.need(self.events and self.events[0]["kind"] == "START", "missing execution start")
        if kind == "HANDOFF":
            c.fields(event, ("kind", "epoch"))
            c.need(event["epoch"] == self.epoch + 1 and not self.reserved
                   and all(a["state"] in ("NO_REPLY", "ACCEPTED") for a in self.attempts.values()),
                   "handoff needs a quiescent journal")
            self.epoch += 1
            return
        if kind == "PUBLISH":
            c.fields(event, ("kind",))
            c.need(len(self.accepted) == len(self.job.tasks) and not self.reserved, "incomplete evidence")
            output = merge(c.decode(self.job.plan)["tree"], {k: v["output"] for k, v in self.accepted.items()})
            evidence = [self.accepted[i]["evidence"] for i in range(len(output))]
            self.final = dict(execution_id=self.job.execution_id, declaration_id=self.job.declaration_id,
                              plan_id=self.job.plan_id, charged_gas=self.charged, output=output,
                              output_digest=digest("Output", c.encode(output)), evidence=evidence,
                              journal_digest=digest("Journal", c.encode([*self.events, event])))
            return

        slot = c.uint(event["slot"])
        number = c.uint(event["attempt"])
        c.need(slot < len(self.job.tasks), "unknown slot")
        cap = self.job.caps[slot]
        key = (slot, number)
        attempt = self.attempts.get(key)
        if kind == "RESERVE":
            c.fields(event, ("kind", "slot", "attempt", "worker", "request"))
            c.need(slot in self.ready() and number in (1, 2) and attempt is None, "attempt not ready")
            first = self.attempts.get((slot, 1))
            c.need(number == 1 or first and first["state"] == "NO_REPLY", "retry requires unanswered first attempt")
            c.need(number == 1 or all(n == 1 for _, n in self.attempts), "execution already used its one retry")
            future = sum(cap for i, cap in enumerate(self.job.caps) if (i, 1) not in self.attempts)
            required = cap if number == 1 else cap + future
            if self.charged + self.reserved + required > self.job.budget:
                raise BudgetError("insufficient solve budget")
            c.need(event["request"] == self.frame(slot, number, "SOLVE"), "wrong frozen solve request")
            self.reserved += cap
            self.attempts[key] = dict(state="RESERVED", request=event["request"], worker=event["worker"])
        elif kind == "NO_REPLY":
            c.fields(event, ("kind", "slot", "attempt"))
            c.need(attempt and attempt["state"] == "RESERVED", "no outstanding attempt")
            self.reserved -= cap
            self.charged += cap
            attempt["state"] = "NO_REPLY"
        elif kind == "ANSWER":
            c.fields(event, ("kind", "slot", "attempt", "response"))
            c.need(attempt and attempt["state"] == "RESERVED", "answer is late or unsolicited")
            answer = response_for(attempt["request"], event["response"], "answer")
            parsed = decode_answer(answer)
            frozen = c.decode(attempt["request"])["question"]
            c.need(parsed.question_id == c.domain_hash(QUESTION_TAG, frozen), "answer is for another question")
            outcome = c.decode(parsed.outcome)
            c.fields(outcome, ("outcome", "gas_used"), ("output",))
            gas = c.uint(outcome["gas_used"])
            c.need(gas <= cap, "invalid reported gas")
            # The cap stays reserved until the independent verifier validates the outcome.
            attempt.update(state="ANSWER", answer=answer, outcome=outcome)
        elif kind == "ACCEPT":
            c.fields(event, ("kind", "slot", "attempt", "verifier", "request", "response"))
            c.need(attempt and attempt["state"] == "ANSWER" and slot not in self.accepted,
                   "slot cannot accept this attempt")
            c.need(event["verifier"] != attempt["worker"], "verification must use a distinct role")
            c.need(event["request"] == self.frame(slot, number, "VERIFY", attempt["answer"]),
                   "wrong frozen verify request")
            c.need(response_for(event["request"], event["response"], "verdict") == "ACCEPT", "not verified")
            outcome = attempt["outcome"]
            c.need(outcome["outcome"] == "OK" and type(outcome.get("output")) is bytes
                   and len(outcome["output"]) == INT.size, "task did not return a composable value")
            task = self.job.tasks[slot]
            expected = (task["literal"] if "literal" in task
                        else 2 * INT.unpack(self.accepted[task["double"]]["output"])[0])
            c.need(outcome["output"] == INT.pack(expected), "output violates task family")
            self.reserved -= cap
            self.charged += outcome["gas_used"]
            attempt["state"] = "ACCEPTED"
            self.accepted[slot] = dict(output=outcome["output"], evidence=digest("Acceptance", c.encode(event)))
        else:
            raise c.CodecError("unknown journal transition")
        c.need(self.charged + self.reserved <= self.job.budget, "budget invariant violated")

    def add(self, kind, **fields):
        event = dict(kind=kind, **fields)
        with self.lock:
            if kind == "PUBLISH" and self.final is not None:
                return self.final
            if kind == "ACCEPT" and event in self.events:
                return None
            # Validate on a replay before updating the live state or allowing any dispatch.
            updated = Journal(self.job, self.path, [*self.events, event])
            pending = self.path.with_suffix(".pending")
            with pending.open("wb") as stream:
                stream.write(c.encode(updated.events))
                stream.flush()
                os.fsync(stream.fileno())
            pending.replace(self.path)
            directory = os.open(self.path.parent, os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
            for name in ("events", "epoch", "attempts", "accepted", "charged", "reserved", "final"):
                setattr(self, name, getattr(updated, name))
            return self.final
