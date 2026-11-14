# SPDX-License-Identifier: Apache-2.0
"""Frozen declaration, questions and output evidence for the capacity-sort fixture."""

import capacity_sort as sort
from general_job import digest
from tools.verification_profile import codec as c

FAMILY = "capacity-sort/1"
DECLARATION = c.encode(dict(family=FAMILY, input=sort.DECLARATION,
                            delivery_image_bytes=sort.IMAGE_BYTES))
PLAN = c.encode(dict(family=FAMILY, tree=[0, 1], dependencies={},
                     keys=c.decode(sort.PLAN)["keys"]))


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
