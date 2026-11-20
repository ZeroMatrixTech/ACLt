# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from baseline import (
    Answer, ExecutionError, LIMITS, PROBE, QuestionRejected, Verdict, ask, solve, verify,
)
from independent import validate
from tools.verification_profile import codec
from wasm import artifact as encode_artifact

VECTORS = {
    row["id"]: row
    for row in json.loads((PROBE / "tests/independent-vectors.json").read_text())["vectors"]
}


def fixture(name):
    row = VECTORS[name]
    return (
        bytes.fromhex(row["artifact_hex"]),
        bytes.fromhex(row["input_hex"]),
        {key: row["limits"][key] for key in LIMITS},
    )


def build_executor(source, executable):
    subprocess.run(
        [os.environ.get("RUSTC", "rustc"), "--edition=2021", "-D", "warnings",
         "-C", "overflow-checks=yes", "-O", str(source), "-o", str(executable)],
        check=True, timeout=90,
    )


def opcodes(nodes):
    for node in nodes:
        yield node["op"]
        yield from opcodes(node.get("body", ()))
        yield from opcodes(node.get("else", ()))


def emit_42_fixture():
    artifact, data, limits = fixture("divzero")
    module = validate(artifact, limits)
    # Push address/value, store i64, then call output_write(address, length).
    instructions = ((0x41, 0), (0x42, 42), (0x37, 3, 0), (0x41, 0), (0x41, 8), (0x10, 3))
    module.code[module.run - len(module.imports)] = (
        [], [{"op": op, "args": args} for op, *args in instructions],
    )
    return encode_artifact(module.canonical()), data, limits


def division_cost_mutant(root):
    # Keep the module layout for Rust path attributes; change only the temporary source.
    source = root / "experiments/aclt-rir-stats-probe/src"
    source.mkdir(parents=True)
    (root / "tools").symlink_to(PROBE.parents[1] / "tools", target_is_directory=True)
    (source / "core.rs").symlink_to(PROBE / "src/core.rs")
    original = (PROBE / "src/independent_executor.rs").read_text()
    anchor = "else if matches!(op,0x6d..=0x70|0x7f..=0x82){8}"
    if original.count(anchor) != 1:
        raise AssertionError("update the i64.div_s mutation anchor for the current executor")
    mutated = source / "independent_executor.rs"
    mutated.write_text(original.replace(anchor, "else if op==0x7f{7}" + anchor))
    executable = root / "executor"
    build_executor(mutated, executable)
    return executable


class MinimalVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = TemporaryDirectory(prefix="aclt-minimal-verifier-test-")
        cls.addClassCleanup(temp.cleanup)
        cls.executor = Path(temp.name) / "executor"
        build_executor(PROBE / "src/independent_executor.rs", cls.executor)

    def test_same_question_accepts_correct_answer_and_rejects_changed_output(self):
        artifact, data, limits = fixture("stats")
        question = ask(artifact, data, limits)
        answer = solve(question, artifact, data)
        self.assertEqual(question, ask(artifact, data, dict(reversed(limits.items()))))
        self.assertEqual(
            answer.question_id.hex(),
            "0cd47e58189ca2e31ebe724b2087cf2bc03ccbf1db9967c6518173dd0436d2d2",
        )
        self.assertEqual(answer.outcome.hex(), VECTORS["stats"]["expected"]["canonical_outcome_hex"])
        changed = codec.decode(answer.outcome)
        changed["output"] = bytes([changed["output"][0] ^ 1]) + changed["output"][1:]
        incorrect = Answer(answer.question_id, codec.encode(changed))
        self.assertEqual(verify(question, artifact, data, answer, executor=self.executor), Verdict("ACCEPT"))
        self.assertEqual(verify(question, artifact, data, incorrect, executor=self.executor),
                         Verdict("REJECT", "OUTCOME_MISMATCH"))

    def test_question_digest_is_recorded_without_rejecting_an_identical_outcome(self):
        artifact, data, limits = fixture("stats")
        question = ask(artifact, data, limits)
        other_question = ask(artifact, data, dict(limits, gas_limit=9126))
        answer = solve(question, artifact, data)
        other_answer = solve(other_question, artifact, data)
        self.assertEqual(answer.outcome, other_answer.outcome)
        self.assertNotEqual(answer.question_id, other_answer.question_id)
        self.assertEqual(verify(other_question, artifact, data, answer, executor=self.executor),
                         Verdict("ACCEPT"))
        self.assertEqual(verify(other_question, artifact, data, other_answer, executor=self.executor),
                         Verdict("ACCEPT"))

    def test_stats_instruction_inventory_matches_reviewed_subset(self):
        artifact, _, limits = fixture("stats")
        module = validate(artifact, limits)
        self.assertEqual(
            {op for _, nodes in module.code for op in opcodes(nodes)},
            {0x00, 0x02, 0x03, 0x0C, 0x0D, 0x0F, 0x10, 0x1B, 0x20, 0x21, 0x22,
             0x23, 0x24, 0x29, 0x37, 0x41, 0x42, 0x45, 0x47, 0x50, 0x52, 0x53,
             0x54, 0x55, 0x58, 0x5A, 0x6A, 0x6B, 0x7C, 0x7D, 0x86},
        )

    def test_hand_calculated_output_and_adjacent_gas_limits(self):
        division = fixture("divzero")
        cases = (
            ("emit-42", emit_42_fixture(), 8215, {
                "outcome": "OK", "gas_used": 8215, "output": bytes.fromhex("2a00000000000000"),
            }),
            ("division-exact", division, 8202, {
                "outcome": "TRAP_INTEGER_DIVIDE_BY_ZERO", "gas_used": 8202,
            }),
            ("division-short", division, 8201, {
                "outcome": "TRAP_GAS_EXHAUSTED", "gas_used": 8194,
            }),
        )
        question_ids = set()
        for name, (artifact, data, limits), gas_limit, expected in cases:
            with self.subTest(vector=name):
                question = ask(artifact, data, dict(limits, gas_limit=gas_limit))
                answer = solve(question, artifact, data)
                question_ids.add(answer.question_id)
                self.assertEqual(answer.outcome, codec.encode(expected))
                self.assertEqual(verify(question, artifact, data, answer, executor=self.executor),
                                 Verdict("ACCEPT"))
        self.assertEqual(len(question_ids), len(cases))

    def test_trap_reason_and_gas_are_compared_separately(self):
        artifact, data, limits = fixture("divzero")
        question = ask(artifact, data, dict(limits, gas_limit=8202))
        answer = solve(question, artifact, data)
        for field, value in (("outcome", "TRAP_GAS_EXHAUSTED"), ("gas_used", 8201)):
            with self.subTest(field=field):
                changed = dict(codec.decode(answer.outcome), **{field: value})
                incorrect = Answer(answer.question_id, codec.encode(changed))
                self.assertEqual(verify(question, artifact, data, incorrect, executor=self.executor),
                                 Verdict("REJECT", "OUTCOME_MISMATCH"))

    def test_single_sided_division_cost_mutation_is_detected(self):
        artifact, data, limits = fixture("divzero")
        question = ask(artifact, data, dict(limits, gas_limit=8201))
        correct = solve(question, artifact, data)
        self.assertEqual(verify(question, artifact, data, correct, executor=self.executor),
                         Verdict("ACCEPT"))
        with TemporaryDirectory(prefix="aclt-minimal-verifier-mutation-") as directory:
            mutant = division_cost_mutant(Path(directory))
            verdict = verify(question, artifact, data, correct, executor=mutant)
            self.assertEqual(verdict, Verdict("REJECT", "OUTCOME_MISMATCH"))
            # At 7 gas the mutant executes the divide. Confirm the exact divergent bytes.
            divergent = Answer(correct.question_id, codec.encode({
                "outcome": "TRAP_INTEGER_DIVIDE_BY_ZERO", "gas_used": 8201,
            }))
            self.assertEqual(verify(question, artifact, data, divergent, executor=mutant),
                             Verdict("ACCEPT"))
        print(json.dumps({
            "vector": "division-short",
            "gas_limit": 8201,
            "question_id": correct.question_id.hex(),
            "unmodified_outcome_hex": correct.outcome.hex(),
            "mutant_outcome_hex": divergent.outcome.hex(),
            "mutant_verdict_for_correct_answer": verdict.status,
            "reason": verdict.reason,
        }, sort_keys=True))

    def test_ask_rejects_unsupported_rule_or_artifact(self):
        artifact, data, limits = fixture("stats")
        with self.assertRaisesRegex(QuestionRejected, "^UNSUPPORTED_RULE$"):
            ask(artifact, data, limits, rule="unknown")
        with self.assertRaisesRegex(QuestionRejected, "^RIR_REJECT_UNSUPPORTED$"):
            ask(*fixture("field-rir_version"))

    def test_sha_binding_is_disabled_and_executor_io_failure_is_reported(self):
        artifact, data, limits = fixture("stats")
        question = ask(artifact, data, limits)
        answer = solve(question, artifact, data)
        missing_executor = self.executor.with_name("missing")
        for supplied_artifact, supplied_data in ((artifact + b"\x00", data), (artifact, data + b"\x00")):
            with self.assertRaises(ExecutionError):
                verify(question, supplied_artifact, supplied_data, answer, executor=missing_executor)
        with self.assertRaises(ExecutionError):
            verify(question, artifact, data, answer, executor=missing_executor)
