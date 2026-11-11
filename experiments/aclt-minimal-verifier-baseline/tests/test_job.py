# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from baseline import PROBE, Verdict, ask, solve, verify
from dualhost import fixture
from job import HEADER, ROW, VALUE, merge_job, prepare_job, record_verdict
from lan import decode_answer, handle_request, request, run_job
from test_baseline import build_executor
from tools.verification_profile import codec


class JobTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = TemporaryDirectory(prefix="aclt-minimal-verifier-job-test-")
        cls.addClassCleanup(temp.cleanup)
        cls.executor = Path(temp.name) / "executor"
        build_executor(PROBE / "src/independent_executor.rs", cls.executor)

    def setUp(self):
        self.artifact, self.data, self.limits = fixture()
        self.plan, self.slices = prepare_job(self.artifact, self.data, self.limits)

    def accepted(self, plan, shard):
        answer = solve(shard.question, self.artifact, shard.data)
        verdict = verify(shard.question, self.artifact, shard.data, answer, executor=self.executor)
        self.assertEqual(verdict, Verdict("ACCEPT"))
        return answer, record_verdict(plan, shard.start, answer, verdict)

    def merge(self, submissions):
        return merge_job(self.plan, self.artifact, self.data, self.limits, submissions)

    def test_job_plan_and_lan_messages_preserve_cross_verification(self):
        a, b = self.slices
        self.assertEqual([(a.start, a.stop), (b.start, b.stop)], [(0, 2), (2, 5)])
        self.assertEqual(a.data, HEADER.pack(2, 2) + VALUE.pack(3) + VALUE.pack(-1))
        self.assertEqual(b.data, HEADER.pack(2, 3) + VALUE.pack(5) + VALUE.pack(8) + VALUE.pack(-2))
        pinned, raw = handle_request(request("SOLVE", self.plan, self.artifact, b), "SOLVE", self.executor)
        b_answer = decode_answer(codec.decode(raw)["answer"])
        self.assertEqual(pinned, self.plan)
        a_answer = solve(a.question, self.artifact, a.data)
        _, raw = handle_request(request("VERIFY", self.plan, self.artifact, a, a_answer),
                                "VERIFY", self.executor, prior_plan=pinned)
        a_record = codec.decode(raw)
        self.assertEqual(a_record, record_verdict(self.plan, a.start, a_answer, Verdict("ACCEPT")))
        b_record = record_verdict(self.plan, b.start, b_answer,
                                  verify(b.question, self.artifact, b.data, b_answer, executor=self.executor))
        submissions = [(a_answer, a_record), (b_answer, b_record)]
        expected = [(0, 0, 2, 2, -1, 3), (1, 2, 2, 13, 5, 8), (2, 4, 1, -2, -2, -2)]
        reference = solve(ask(self.artifact, self.data, self.limits), self.artifact, self.data)
        self.assertEqual(self.merge(submissions), b"".join(ROW.pack(*row) for row in expected))
        self.assertEqual(self.merge(submissions[::-1]), codec.decode(reference.outcome)["output"])

    def test_coordinator_emits_output_after_both_verdicts(self):
        reply = b""
        pinned = None

        def local_message_handler(_connection, raw):
            nonlocal reply, pinned
            action = codec.decode(raw)["action"]
            pinned, reply = handle_request(raw, action, self.executor, prior_plan=pinned)

        with TemporaryDirectory() as directory:
            output = Path(directory)
            with patch("lan.send", side_effect=local_message_handler), patch("lan.receive", side_effect=lambda _: reply):
                summary = run_job(None, self.artifact, self.data, self.limits, self.executor, output)
            self.assertEqual((output / "merged-output.bin").read_bytes(), (output / "reference-output.bin").read_bytes())
            self.assertEqual(summary["output_bytes"], 144)
            self.assertEqual([item["gas_used"] for item in summary["slices"]], [8719, 9018])
            self.assertEqual(summary["reference_gas_used"], 9425)

    def test_incomplete_duplicate_and_wrongly_bound_results(self):
        first, second = [self.accepted(self.plan, shard) for shard in self.slices]
        bad_cases = (
            ([first], "missing slice position"),
            ([first, first], "duplicate slice position"),
            ([first, (first[0], second[1])], "slice question mismatch"),
            ([first, (second[0], dict(second[1], answer_digest=b"x" * 32))], "bound to its exact answer"),
            ([first, (second[0], dict(second[1], job_id=b"x" * 32))], "bound to its exact answer"),
            ([first, (second[0], dict(second[1], status="REJECT"))], "bound to its exact answer"),
        )
        for submissions, message in bad_cases:
            with self.subTest(message=message), self.assertRaisesRegex(codec.CodecError, message):
                self.merge(submissions)
        with self.assertRaisesRegex(codec.CodecError, "plan does not match"):
            merge_job(self.plan, self.artifact, self.data[:-8] + VALUE.pack(-3), self.limits, [first, second])

    def test_identical_questions_still_occupy_two_job_positions(self):
        data = HEADER.pack(2, 4) + (VALUE.pack(3) + VALUE.pack(-1)) * 2
        plan, slices = prepare_job(self.artifact, data, self.limits)
        self.assertEqual(slices[0].question_id, slices[1].question_id)
        submissions = [self.accepted(plan, shard) for shard in slices]
        rows = merge_job(plan, self.artifact, data, self.limits, submissions)
        self.assertEqual(list(ROW.iter_unpack(rows)), [(0, 0, 2, 2, -1, 3), (1, 2, 2, 2, -1, 3)])

    def test_lan_worker_rejects_a_request_for_the_wrong_position(self):
        with self.assertRaisesRegex(codec.CodecError, "LAN slice position mismatch"):
            handle_request(request("SOLVE", self.plan, self.artifact, self.slices[0]), "SOLVE", self.executor)
        wrong = replace(self.slices[1], question=self.slices[0].question)
        with self.assertRaisesRegex(codec.CodecError, "LAN question mismatch"):
            handle_request(request("SOLVE", self.plan, self.artifact, wrong), "SOLVE", self.executor)

    def test_accepted_slice_trap_cannot_be_merged_as_output(self):
        limits = dict(self.limits, gas_limit=8719)
        plan, slices = prepare_job(self.artifact, self.data, limits)
        submissions = [self.accepted(plan, shard) for shard in slices]
        self.assertEqual(codec.decode(submissions[1][0].outcome)["outcome"], "TRAP_GAS_EXHAUSTED")
        with self.assertRaisesRegex(codec.CodecError, "slice needs OK output"):
            merge_job(plan, self.artifact, self.data, limits, submissions)

    def test_common_gas_cap_can_pass_slices_and_fail_whole_job(self):
        limits = dict(self.limits, gas_limit=9018)
        plan, slices = prepare_job(self.artifact, self.data, limits)
        submissions = [self.accepted(plan, shard) for shard in slices]
        outcomes = [codec.decode(answer.outcome) for answer, _ in submissions]
        self.assertEqual(
            [(value["outcome"], value["gas_used"]) for value in outcomes],
            [("OK", 8719), ("OK", 9018)],
        )
        whole = solve(ask(self.artifact, self.data, limits), self.artifact, self.data)
        self.assertEqual(codec.decode(whole.outcome), {"outcome": "TRAP_GAS_EXHAUSTED", "gas_used": 9016})
        self.assertEqual(len(merge_job(plan, self.artifact, self.data, limits, submissions)), 144)
