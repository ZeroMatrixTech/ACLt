# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from itertools import permutations
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from baseline import PROBE, QUESTION_TAG, Verdict, ask, solve, verify
from dualhost import fixture
from job import (
    BOUNDED_RULE, HEADER, ROW, VALUE, admit_stats_root, merge_job, prepare_job, record_verdict, stats_gas_bound,
)
from lan import decode_answer, handle_request, operations, request, run_job
from tree import TREE_RULE, merge_tree, prepare_tree, tree_slots
from independent import validate
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
                summary = run_job(None, self.artifact, self.data, self.limits, self.executor, output, solve_budget=17737)
            self.assertEqual((output / "merged-output.bin").read_bytes(), (output / "reference-output.bin").read_bytes())
            self.assertEqual(summary["output_bytes"], 144)
            self.assertEqual([item["gas_used"] for item in summary["slices"]], [8719, 9018])
            self.assertEqual([item["gas_limit"] for item in summary["slices"]], [8719, 9018])
            self.assertEqual(summary["allocated_solve_gas"], 17737)
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

    def test_whole_task_resource_boundary_precedes_dispatch(self):
        exact = dict(self.limits, gas_limit=9425, output_limit=144, call_depth_limit=1)
        question = admit_stats_root(self.artifact, self.data, exact)
        answer = solve(question, self.artifact, self.data)
        outcome = codec.decode(answer.outcome)
        self.assertEqual((outcome["outcome"], outcome["gas_used"], len(outcome["output"])),
                         ("OK", 9425, 144))
        self.assertEqual(verify(question, self.artifact, self.data, answer, executor=self.executor),
                         Verdict("ACCEPT"))
        for field, expected_trap, message in (
            ("gas_limit", "TRAP_GAS_EXHAUSTED", "whole-task gas limit needs at least 9425"),
            ("output_limit", "TRAP_OUTPUT_LIMIT", "whole-task output limit needs at least 144 bytes"),
        ):
            short = dict(exact, **{field: exact[field] - 1})
            question = ask(self.artifact, self.data, short)
            answer = solve(question, self.artifact, self.data)
            self.assertEqual(codec.decode(answer.outcome)["outcome"], expected_trap)
            self.assertEqual(verify(question, self.artifact, self.data, answer, executor=self.executor),
                             Verdict("ACCEPT"))
            for recursive in (False, True):
                with self.subTest(field=field, recursive=recursive), TemporaryDirectory() as directory:
                    output = Path(directory)
                    with patch("lan.send") as send, patch("lan.solve") as execute:
                        with self.assertRaisesRegex(codec.CodecError, message):
                            run_job(None, self.artifact, self.data, short, self.executor, output,
                                    recursive=recursive)
                    send.assert_not_called()
                    execute.assert_not_called()
                    self.assertEqual(list(output.iterdir()), [])

    def test_static_metering_coefficients_from_pinned_wasm_paths(self):
        module = validate(self.artifact, self.limits)

        def preorder(nodes):
            for node in nodes:
                yield node
                yield from preorder(node.get("body", ()))
                yield from preorder(node.get("else", ()))

        nodes = list(preorder(module.code[module.run - len(module.imports)][1]))

        def span_cost(start, stop):
            costs = {0x29: 2, 0x37: 2}
            host = {0: 4, 1: 4, 2: 17, 3: 17}
            return sum(host[n["args"][0]] if n["op"] == 0x10 else costs.get(n["op"], 1)
                       for n in nodes[start - 1:stop])

        fixed = 8192 + span_cost(1, 69) + span_cost(103, 106) + span_cost(245, 249)
        validate_value = span_cost(70, 88) + span_cost(92, 102)
        accumulate_value = span_cost(144, 185)
        block = span_cost(107, 122) + span_cost(130, 143) + span_cost(186, 244)
        self.assertEqual((fixed, validate_value, accumulate_value, block), (8312, 48, 60, 191))

    def test_exact_bound_varies_by_elements_and_blocks_on_both_executors(self):
        for chunk, count in ((1, 1), (1, 8), (2, 3), (3, 6), (7, 15), (100000, 11)):
            for values in ((-10**9, 0, 10**9), (10**9, -10**9, -10**9)):
                with self.subTest(chunk=chunk, count=count, values=values):
                    data = HEADER.pack(chunk, count) + b"".join(VALUE.pack(values[i % 3]) for i in range(count))
                    gas = stats_gas_bound(count, chunk)
                    question = ask(self.artifact, data, dict(self.limits, gas_limit=gas))
                    answer = solve(question, self.artifact, data)
                    outcome = codec.decode(answer.outcome)
                    self.assertEqual((outcome["outcome"], outcome["gas_used"]), ("OK", gas))
                    self.assertEqual(verify(question, self.artifact, data, answer, executor=self.executor),
                                     Verdict("ACCEPT"))
                    short = ask(self.artifact, data, dict(self.limits, gas_limit=gas - 1))
                    answer = solve(short, self.artifact, data)
                    self.assertEqual(codec.decode(answer.outcome)["outcome"], "TRAP_GAS_EXHAUSTED")
                    self.assertEqual(verify(short, self.artifact, data, answer, executor=self.executor),
                                     Verdict("ACCEPT"))
        self.assertEqual(stats_gas_bound(100000, 1), 29908312)

    def test_solve_budget_rejects_before_dispatch_and_binds_plan(self):
        with TemporaryDirectory() as directory, patch("lan.send") as send:
            output = Path(directory)
            with self.assertRaisesRegex(codec.CodecError, "insufficient shard solve budget"):
                run_job(None, self.artifact, self.data, self.limits, self.executor, output, solve_budget=17736)
            send.assert_not_called()
            self.assertEqual(list(output.iterdir()), [])
        plan, slices = prepare_job(self.artifact, self.data, self.limits, solve_budget=17737)
        decoded = codec.decode(plan)
        self.assertEqual(decoded["rule"], BOUNDED_RULE)
        self.assertEqual(decoded["solve_budget"], 17737)
        submissions = [self.accepted(plan, s) for s in slices]
        with self.assertRaisesRegex(codec.CodecError, "plan does not match"):
            merge_job(plan, self.artifact, self.data, self.limits, submissions, solve_budget=17738)

    def test_peer_rejects_self_consistent_question_with_wrong_gas_cap(self):
        plan, (_, shard) = prepare_job(self.artifact, self.data, self.limits, allocate_gas=True)
        wrong = ask(self.artifact, shard.data, dict(self.limits, gas_limit=9019))
        record = codec.decode(plan)
        record["slices"][1]["question_id"] = codec.domain_hash(QUESTION_TAG, wrong)
        message = request("SOLVE", codec.encode(record), self.artifact, replace(shard, question=wrong))
        with self.assertRaisesRegex(codec.CodecError, "LAN gas allocation mismatch"):
            handle_request(message, "SOLVE", self.executor)

        insufficient = codec.decode(plan)
        insufficient["solve_budget"] = 17736
        message = request("SOLVE", codec.encode(insufficient), self.artifact, shard)
        with self.assertRaisesRegex(codec.CodecError, "insufficient LAN shard solve budget"):
            handle_request(message, "SOLVE", self.executor)

    def test_breadth_first_tree_composes_same_leaves_in_any_arrival_order(self):
        plan, slices = prepare_tree(self.artifact, self.data, self.limits, solve_budget=26049)
        meta = codec.decode(plan)
        self.assertEqual(meta["rule"], TREE_RULE)
        self.assertEqual(
            [(node["start"], node["stop"], node.get("children")) for node in meta["nodes"]],
            [(0, 5, [1, 2]), (0, 2, None), (2, 5, [3, 4]), (2, 4, None), (4, 5, None)],
        )
        self.assertEqual([slot["start"] for slot in tree_slots(meta)], [0, 2, 4])
        submissions = [self.accepted(plan, shard) for shard in slices]
        reference = solve(ask(self.artifact, self.data, self.limits), self.artifact, self.data)
        outcome = codec.decode(reference.outcome)
        for ordering in permutations(submissions):
            result = merge_tree(plan, self.artifact, self.data, self.limits, list(ordering), solve_budget=26049)
            self.assertEqual(result.output, outcome["output"])
            self.assertEqual(result.output, result.flat_output)
            self.assertEqual(result.leaf_gas_used, outcome["gas_used"] + 2 * 8312)
            self.assertEqual(result.leaf_gas_used, result.flat_gas_used)
            self.assertEqual([index for index, _ in result.merge_order], [2, 0])
        ready_right = merge_tree(plan, self.artifact, self.data, self.limits,
                                 submissions[1:] + submissions[:1], solve_budget=26049)
        self.assertEqual(ready_right.merge_order, ((2, 4), (0, 0)))

    def test_tree_rejects_missing_duplicate_and_malformed_children(self):
        plan, slices = prepare_tree(self.artifact, self.data, self.limits)
        submissions = [self.accepted(plan, shard) for shard in slices]
        for bad, error in ((submissions[:-1], "missing"), (submissions + submissions[:1], "duplicate")):
            with self.assertRaisesRegex(codec.CodecError, error):
                merge_tree(plan, self.artifact, self.data, self.limits, bad)
        meta = codec.decode(plan)
        meta["nodes"][2]["children"] = [3, 3]
        with self.assertRaisesRegex(codec.CodecError, "invalid BFS node shape"):
            handle_request(request("SOLVE", codec.encode(meta), self.artifact, slices[1]),
                           "SOLVE", self.executor, leaf_count=3)

    def test_tree_lan_coordinator_and_budget(self):
        plan = None
        reply = b""
        schedule = iter(operations(3))

        def local_message_handler(_connection, raw):
            nonlocal reply, plan
            action, index, _ = next(schedule)
            plan, reply = handle_request(raw, action, self.executor, prior_plan=plan,
                                         leaf_index=index, leaf_count=3)

        with TemporaryDirectory() as directory:
            output = Path(directory)
            with patch("lan.send", side_effect=local_message_handler) as send, patch("lan.receive", side_effect=lambda _: reply):
                with self.assertRaisesRegex(codec.CodecError, "insufficient leaf solve budget"):
                    run_job(None, self.artifact, self.data, self.limits, self.executor, output,
                            solve_budget=26048, recursive=True)
                send.assert_not_called()
                self.assertEqual(list(output.iterdir()), [])
                summary = run_job(None, self.artifact, self.data, self.limits, self.executor, output,
                                  solve_budget=26049, recursive=True)
            self.assertEqual(summary["leaf_solve_gas_used"], 26049)
            self.assertEqual(summary["flat_leaf_solve_gas_used"], 26049)
            self.assertTrue(summary["flat_output_equal"])
            self.assertEqual(summary["tree_merge_order"], ((2, 4), (0, 4)))
            self.assertEqual([part["execution_host"] for part in summary["slices"]], ["A", "B", "A"])
            self.assertTrue((output / "VERIFY-2-response.cbor").is_file())
