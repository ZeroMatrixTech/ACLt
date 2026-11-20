# SPDX-License-Identifier: Apache-2.0
"""Exercise fixed sort delivery, evidence replay and solve accounting."""

from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import capacity_sort as sort
from general_job import Journal, digest
from general_vm import run
import sort_contract as contract
from tools.verification_profile import codec as c

EXECUTION = b"e" * 32
TOOLS = ("mkfs.ext4", "debugfs", "dumpe2fs")


def descriptor(slot):
    return dict(partition=slot, bytes=sort.PARTITION_BYTES,
                records=contract.CAPS[slot], sha256=bytes([slot]) * 32)


def response(raw, **payload):
    return c.encode(dict(request=digest("Request", raw), **payload))


def solve_response(raw, output):
    return response(raw, answer=c.encode(dict(question=c.decode(raw)["question"], output=output)))


def reserve(journal, slot, attempt):
    request = journal.frame(slot, attempt, "SOLVE")
    journal.add("RESERVE", slot=slot, attempt=attempt, worker="B", request=request)
    return request


class SortBindingTests(unittest.TestCase):
    def test_caps_match_frozen_range_populations(self):
        populations = [0, 0]
        for ordinal in range(sort.RECORDS):
            populations[sort.key(ordinal) >> 63] += 1
        self.assertEqual(tuple(populations), contract.CAPS)

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
        cls.job = contract.SortJob(EXECUTION)
        cls.images, cls.descriptors, cls.responses = {}, {}, {}
        cls.journal = Journal(cls.job, cls.root / "journal.cbor")
        cls.journal.add("START", execution=cls.job.execution)
        for slot in (0, 1):
            root = cls.root / str(slot)
            root.mkdir()
            raw = reserve(cls.journal, slot, 1)
            response_path = root / "solve.cbor"
            contract.respond(cls.job, raw, None, response_path, drop=True)
            encoded = response_path.read_bytes()
            answer = c.decode(encoded)["answer"]
            cls.images[slot] = root / "delivery.img"
            cls.descriptors[slot] = c.decode(answer)["output"]
            cls.responses[slot] = raw, encoded
            cls.journal.add("ANSWER", slot=slot, attempt=1, response=encoded)
            verify = cls.journal.frame(slot, 1, "VERIFY", answer)
            cls.journal.add("ACCEPT", slot=slot, attempt=1, verifier="C", request=verify,
                            response=response(verify, verdict=cls.descriptors[slot]))

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
        self.verify(0, descriptor=self.descriptors[0] | {"sha256": b"x" * 32})  # SHA consistency DISABLED; actual partition is still verified.

    def test_replay_and_retained_reject_missing_changed_and_wrong_slot(self):
        raw, encoded = self.responses[0]
        contract.replay_response(self.job, raw, encoded, self.images[0].parent, False)
        contract.replay_response(self.job, raw, encoded, self.root, True)
        contract.verify_retained(self.job, self.journal, lambda req: self.images[req["slot"]])

        missing = self.root / "missing"
        missing.mkdir()
        altered = self.root / "altered"
        altered.mkdir()
        image = altered / "delivery.img"
        sort.new_image(image)
        with sort.memory_file() as raw_records, sort.memory_file() as ordered:
            sort.generate(0, sort.RECORDS, 0, raw_records)
            sort.sorted_partition((raw_records,), ordered)
            first = ordered.read(1)
            ordered.seek(0)
            ordered.write(bytes([first[0] ^ 1]))
            sort.image_command(image, "write", ordered, 0, [])

        cases = (
            (missing, FileNotFoundError, "delivery.img"),
            (altered, ValueError, "record differs from frozen source or range"),
            (self.images[1].parent, ValueError, "missing or truncated stored partition"),
        )
        for root, error, detail in cases:
            with self.subTest(image=root.name):
                with self.assertRaisesRegex(error, detail):
                    contract.replay_response(self.job, raw, encoded, root, False)
                with self.assertRaisesRegex(error, detail):
                    contract.verify_retained(self.job, self.journal, lambda req: root / "delivery.img")
        with self.assertRaisesRegex(ValueError, "answer is for another question"):
            contract.replay_response(self.job, raw, self.responses[1][1], self.images[0].parent, False)


class SortLedgerTests(unittest.TestCase):
    def test_accounting_retry_and_handoff(self):
        job = contract.SortJob(EXECUTION)
        executions = []

        def exchange(owner, raw):
            request = contract.checked_request(job, raw)
            slot, number, action = (request[key] for key in ("slot", "attempt", "action"))
            executions.append((owner, slot, number, action))
            if (slot, number, action) == (1, 1, "SOLVE"):
                raise ConnectionError("dropped")
            output = descriptor(slot)
            if action == "SOLVE":
                return solve_response(raw, output)
            return response(raw, verdict=output)

        self.assertEqual(job.budget, 786432)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            before, status = run(job, ("A", "B", "C"), root / "before.cbor", exchange,
                                 order=(1, 0), checkpoint=1, placement=contract.PLACEMENT,
                                 retry_worker=contract.retry_on_same_worker)
            self.assertEqual((status, before.charged, before.reserved), ("CHECKPOINT", 524288, 0))
            self.assertEqual(before.attempts[1, 1]["state"], "NO_REPLY")
            after, status = run(job, ("A", "B", "C"), root / "after.cbor", exchange,
                                order=(1, 0), previous=before.path, placement=contract.PLACEMENT,
                                retry_worker=contract.retry_on_same_worker)
            self.assertEqual((status, after.final["charged_records"]), ("PUBLISHED", 786432))
            self.assertNotIn("charged_gas", after.final)
            self.assertEqual(after.events[:len(before.events)], before.events)
            self.assertEqual(after.accepted[1], before.accepted[1])
            self.assertEqual([item["partition"] for item in after.final["output"]], [0, 1])
            self.assertEqual([item[:3] for item in executions if item[3] == "SOLVE"],
                             [("B", 1, 1), ("B", 1, 2), ("C", 0, 1)])
            self.assertEqual(Journal(job, after.path, after.events).final, after.final)

    def test_verified_count_must_match_frozen_count(self):
        job = contract.SortJob(EXECUTION)
        descriptor = dict(partition=0, bytes=sort.PARTITION_BYTES,
                          records=contract.CAPS[0], sha256=b"x" * 32)
        with self.assertRaisesRegex(ValueError, "incomplete sort partition"):
            job.check_verdict(0, {"output": descriptor}, descriptor | {"records": descriptor["records"] - 1})


    def test_late_answer_conflicting_acceptance_and_second_retry_leave_ledger_intact(self):
        job = contract.SortJob(EXECUTION)
        with TemporaryDirectory() as directory:
            journal = Journal(job, Path(directory) / "journal.cbor")
            journal.add("START", execution=job.execution)
            first = reserve(journal, 0, 1)
            journal.add("NO_REPLY", slot=0, attempt=1)
            retry = reserve(journal, 0, 2)
            before = journal.path.read_bytes()
            with self.assertRaisesRegex(ValueError, "answer is late or unsolicited"):
                journal.add("ANSWER", slot=0, attempt=1, response=solve_response(first, descriptor(0)))
            self.assertEqual(journal.path.read_bytes(), before)

            solved = c.decode(solve_response(retry, descriptor(0)))
            journal.add("ANSWER", slot=0, attempt=2, response=c.encode(solved))
            verify = journal.frame(0, 2, "VERIFY", solved["answer"])
            accepted = dict(slot=0, attempt=2, verifier="C", request=verify,
                            response=response(verify, verdict=descriptor(0)))
            journal.add("ACCEPT", **accepted)
            before = journal.path.read_bytes()
            with self.assertRaisesRegex(ValueError, "slot cannot accept this attempt"):
                journal.add("ACCEPT", **(accepted | {"verifier": "A"}))
            self.assertEqual(journal.path.read_bytes(), before)
            self.assertEqual(journal.charged, 2 * contract.CAPS[0])

            reserve(journal, 1, 1)
            journal.add("NO_REPLY", slot=1, attempt=1)
            before = journal.path.read_bytes()
            with self.assertRaisesRegex(ValueError, "execution already used its one retry"):
                reserve(journal, 1, 2)
            self.assertEqual(journal.path.read_bytes(), before)
            self.assertEqual((journal.charged, journal.reserved), (job.budget, 0))
