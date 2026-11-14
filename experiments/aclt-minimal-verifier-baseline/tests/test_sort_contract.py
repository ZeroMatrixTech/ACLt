# SPDX-License-Identifier: Apache-2.0
"""Exercise fixed sort artifact binding independently of solve accounting."""

from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import capacity_sort as sort
from general_job import digest
import sort_contract as contract
from tools.verification_profile import codec as c

EXECUTION = b"e" * 32
TOOLS = ("mkfs.ext4", "debugfs", "dumpe2fs")


class SortBindingTests(unittest.TestCase):
    def test_question_binds_execution_and_slot(self):
        bound = contract.question(EXECUTION, 0)
        self.assertEqual(c.decode(bound), dict(
            execution_id=EXECUTION, slot=0,
            declaration_id=digest("Declaration", contract.DECLARATION),
            plan_id=digest("Plan", contract.PLAN)))
        self.assertNotEqual(bound, contract.question(EXECUTION, 1))
        self.assertNotEqual(bound, contract.question(b"f" * 32, 0))
        with self.assertRaisesRegex(ValueError, "unknown sort slot"):
            contract.question(EXECUTION, 2)


@unittest.skipUnless(all(shutil.which(tool) for tool in TOOLS), "e2fsprogs tools required")
class SortDeliveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = TemporaryDirectory(prefix="aclt-sort-contract-")
        cls.addClassCleanup(temporary.cleanup)
        cls.root = Path(temporary.name)
        cls.images, cls.descriptors = {}, {}
        for slot in (0, 1):
            image = cls.root / f"partition-{slot}.img"
            sort.new_image(image)
            with sort.memory_file() as raw, sort.memory_file() as ordered, sort.memory_file() as stored:
                sort.generate(0, sort.RECORDS, slot, raw)
                sort.sorted_partition((raw,), ordered)
                cls.descriptors[slot] = sort.capture_partition(image, slot, ordered, stored, [])
            cls.images[slot] = image

    def verify(self, slot, *, question=None, descriptor=None, image=None):
        return contract.verify_delivery(
            EXECUTION, slot,
            contract.question(EXECUTION, slot) if question is None else question,
            self.descriptors[slot] if descriptor is None else descriptor,
            self.images[slot] if image is None else image)

    def test_reversed_arrival_merges_in_frozen_order(self):
        verified = {slot: self.verify(slot) for slot in (1, 0)}
        self.assertEqual(contract.merge_verified(verified), [self.descriptors[0], self.descriptors[1]])
        with self.assertRaisesRegex(ValueError, "incomplete sort evidence"):
            contract.merge_verified({1: verified[1]})
        with self.assertRaisesRegex(ValueError, "different slot"):
            contract.merge_verified({0: verified[1], 1: verified[0]})

    def test_rejects_wrong_execution_slot_and_digest(self):
        for question in (contract.question(b"f" * 32, 0), contract.question(EXECUTION, 1)):
            with self.assertRaisesRegex(ValueError, "wrong frozen sort question"):
                self.verify(0, question=question)
        with self.assertRaisesRegex(ValueError, "different slot"):
            self.verify(0, descriptor=self.descriptors[1])
        with self.assertRaisesRegex(ValueError, "does not match delivered partition"):
            self.verify(0, descriptor=self.descriptors[0] | {"sha256": b"x" * 32})

    def test_rejects_missing_partition_and_modified_record(self):
        with self.assertRaisesRegex(ValueError, "missing or truncated stored partition"):
            self.verify(0, image=self.images[1])

        altered = self.root / "altered.img"
        sort.new_image(altered)
        with sort.memory_file() as raw, sort.memory_file() as ordered:
            sort.generate(0, sort.RECORDS, 0, raw)
            sort.sorted_partition((raw,), ordered)
            first = ordered.read(1)
            ordered.seek(0)
            ordered.write(bytes([first[0] ^ 1]))
            sort.image_command(altered, "write", ordered, 0, [])
        with self.assertRaisesRegex(ValueError, "record differs from frozen source or range"):
            self.verify(0, image=altered)
