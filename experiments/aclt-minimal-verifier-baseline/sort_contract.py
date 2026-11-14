# SPDX-License-Identifier: Apache-2.0
"""Frozen declaration, questions and output evidence for the capacity-sort fixture."""

from dataclasses import dataclass

import capacity_sort as sort
from tools.formal_migration.s2_transport import receive, send
from general_job import digest
from tools.verification_profile import codec as c

FAMILY = "capacity-sort/1"
DECLARATION = c.encode(dict(family=FAMILY, input=sort.DECLARATION,
                            delivery_image_bytes=sort.IMAGE_BYTES))
SLOTS = (0, 1)
PLACEMENT = (("C", "B"), ("B", "C"))
CAPS = (sort.RECORDS // 2,) * len(SLOTS)
BUDGET = sum(CAPS) + max(CAPS)
PLAN = c.encode(dict(family=FAMILY, tree=list(SLOTS), dependencies={},
                     keys=c.decode(sort.PLAN)["keys"], caps=list(CAPS), solve_unit="records"))


def question(execution_id, slot):
    """Bind the fixed input, ordered range and slot to the caller's execution."""
    c.digest_bytes(execution_id)
    c.need(c.uint(slot) < 2, "unknown sort slot")
    return c.encode(dict(declaration_id=digest("Declaration", DECLARATION),
                         plan_id=digest("Plan", PLAN), execution_id=execution_id, slot=slot))


def check_descriptor(slot, descriptor):
    c.fields(descriptor, ("partition", "bytes", "records", "sha256"))
    c.need(c.uint(descriptor["partition"]) == slot, "sort descriptor is for a different slot")
    c.need(c.uint(descriptor["bytes"]) == sort.PARTITION_BYTES
           and c.uint(descriptor["records"]) == sort.RECORDS // 2, "incomplete sort partition")
    c.digest_bytes(descriptor["sha256"])


def verify_delivery(execution_id, slot, frozen_question, descriptor, image):
    """Re-read and validate the partition in the designated ext4 delivery image."""
    c.need(frozen_question == question(execution_id, slot), "wrong frozen sort question")
    check_descriptor(slot, descriptor)
    c.need(image.stat().st_size == sort.IMAGE_BYTES, "wrong delivery image capacity")
    with sort.memory_file() as stored:
        sort.read_partition(image, stored, slot, [])
        verified = sort.verify_partition(stored, slot)
    c.need(verified == descriptor, "sort descriptor does not match delivered partition")
    return verified


def merge_verified(partitions):
    """Return the range-ordered index of independently verified partitions."""
    slots = c.decode(PLAN)["tree"]
    c.need(set(partitions) == set(slots), "incomplete sort evidence")
    for slot in slots:
        check_descriptor(slot, partitions[slot])
    return [partitions[slot] for slot in slots]


@dataclass(frozen=True)
class SortJob:
    nonce: bytes
    declaration = DECLARATION
    plan = PLAN
    tasks = SLOTS
    caps = CAPS
    budget = BUDGET
    charge_field = "charged_records"

    def __post_init__(self):
        c.digest_bytes(self.nonce)

    @property
    def dependencies(self):
        return {}

    @property
    def declaration_id(self):
        return digest("Declaration", self.declaration)

    @property
    def plan_id(self):
        return digest("Plan", self.plan)

    @property
    def execution(self):
        return c.encode(dict(declaration_id=self.declaration_id, plan_id=self.plan_id,
                             nonce=self.nonce, budget=self.budget))

    @property
    def execution_id(self):
        return digest("Execution", self.execution)

    def question(self, slot, accepted):
        return {"question": question(self.execution_id, slot)}

    def decode_outcome(self, slot, frozen, answer):
        parsed = c.decode(answer)
        c.fields(parsed, ("question", "output"))
        c.need(parsed["question"] == frozen, "answer is for another question")
        return parsed

    def check_answer(self, slot, outcome):
        check_descriptor(slot, outcome["output"])

    def check_output(self, slot, outcome, accepted):
        check_descriptor(slot, outcome["output"])

    def check_verdict(self, slot, outcome, verdict):
        check_descriptor(slot, verdict)
        c.need(verdict == outcome["output"], "verifier checked a different partition")
        return verdict["records"]

    def merge_output(self, accepted):
        return merge_verified({slot: row["output"] for slot, row in accepted.items()})


def checked_request(job, raw):
    request = c.decode(raw)
    action = request["action"]
    c.need(action in ("SOLVE", "VERIFY"), "unknown job action")
    c.fields(request, ("action", "execution_id", "slot", "attempt", "epoch", "question")
             + (("answer",) if action == "VERIFY" else ()))
    slot = c.uint(request["slot"])
    c.need(request["execution_id"] == job.execution_id
           and request["question"] == question(job.execution_id, slot), "wrong frozen sort question")
    c.need(c.uint(request["attempt"]) in (1, 2), "unknown sort attempt")
    c.uint(request["epoch"])
    if action == "VERIFY":
        job.check_answer(slot, job.decode_outcome(slot, request["question"], request["answer"]))
    return request


def solve_delivery(request, output, stored):
    slot = request["slot"]
    image = output / "delivery.img"
    if image.exists():
        c.need(request["attempt"] == 2, "delivery image already exists")
        image.unlink()
    usable = sort.new_image(image)
    log = []
    with sort.memory_file() as raw, sort.memory_file() as ordered:
        sort.generate(0, sort.RECORDS, slot, raw)
        sort.sorted_partition((raw,), ordered)
        descriptor = sort.capture_partition(image, slot, ordered, stored, log)
    sort.save_json(output / "delivery.json", dict(slot=slot, attempt=request["attempt"],
                   usable_bytes=usable, operations=log))
    return c.encode(dict(question=request["question"], output=descriptor))


def respond(job, raw, connection, response_path, *, drop=False):
    request = checked_request(job, raw)
    slot = request["slot"]
    response = {"request": digest("Request", raw)}
    with sort.memory_file() as stored:
        if request["action"] == "SOLVE":
            response["answer"] = solve_delivery(request, response_path.parent, stored)
        else:
            sort.move_in(connection, stored, sort.PARTITION_BYTES)
            verdict = sort.verify_partition(stored, slot)
            outcome = job.decode_outcome(slot, request["question"], request["answer"])
            job.check_verdict(slot, outcome, verdict)
            response["verdict"] = verdict
        encoded = c.encode(response)
        response_path.write_bytes(encoded)
        if not drop:
            send(connection, encoded)
            if request["action"] == "SOLVE":
                sort.move_out(connection, stored, sort.PARTITION_BYTES)


def exchange_payload(connection, raw, stored):
    """Relay one partition at a time through volatile storage."""
    request = c.decode(raw)
    send(connection, raw)
    if request["action"] == "VERIFY":
        sort.move_out(connection, stored, sort.PARTITION_BYTES)
    response = receive(connection)
    if request["action"] == "SOLVE":
        stored.seek(0)
        stored.truncate()
        sort.move_in(connection, stored, sort.PARTITION_BYTES)
    return response


def verify_retained(job, journal, find_image):
    """Bind accepted evidence to the original delivery images after handoff or offline."""
    for slot, row in journal.accepted.items():
        number, = (number for (index, number), entry in journal.attempts.items()
                   if index == slot and entry["state"] == "ACCEPTED")
        attempt = journal.attempts[slot, number]
        request = c.decode(attempt["request"])
        verify_delivery(job.execution_id, slot, request["question"], row["output"], find_image(request))


def retry_on_same_worker(worker):
    return worker


def replay_response(job, raw, encoded_response, root, unanswered):
    request = checked_request(job, raw)
    response = c.decode(encoded_response)
    slot = request["slot"]
    if request["action"] == "SOLVE":
        c.fields(response, ("request", "answer"))
        outcome = job.decode_outcome(slot, request["question"], response["answer"])
        if unanswered:
            # The retry reuses the single delivery image. Replay the dropped answer
            # from frozen input, without treating it as an accepted delivery.
            with sort.memory_file() as source, sort.memory_file() as ordered:
                sort.generate(0, sort.RECORDS, slot, source)
                sort.sorted_partition((source,), ordered)
                c.need(sort.verify_partition(ordered, slot) == outcome["output"],
                       "dropped answer differs from frozen sort result")
        else:
            verify_delivery(job.execution_id, slot, request["question"], outcome["output"],
                            root / "delivery.img")
    else:
        c.fields(response, ("request", "verdict"))
        outcome = job.decode_outcome(slot, request["question"], request["answer"])
        job.check_verdict(slot, outcome, response["verdict"])
    c.need(response["request"] == digest("Request", raw), "reply bound to different request")
