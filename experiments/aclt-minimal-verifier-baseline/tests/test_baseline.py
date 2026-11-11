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
from tools.verification_profile import codec

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


class MinimalVerifierTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temp = TemporaryDirectory(prefix="aclt-minimal-verifier-test-")
        cls.addClassCleanup(temp.cleanup)
        cls.executor = Path(temp.name) / "executor"
        subprocess.run(
            [os.environ.get("RUSTC", "rustc"), "--edition=2021", "-D", "warnings",
             "-C", "overflow-checks=yes", "-O", str(PROBE / "src/independent_executor.rs"),
             "-o", str(cls.executor)],
            check=True, timeout=90,
        )

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

    def test_an_identical_outcome_cannot_be_submitted_under_a_different_question(self):
        artifact, data, limits = fixture("stats")
        question = ask(artifact, data, limits)
        other_question = ask(artifact, data, dict(limits, gas_limit=9126))
        answer = solve(question, artifact, data)
        other_answer = solve(other_question, artifact, data)
        self.assertEqual(answer.outcome, other_answer.outcome)
        self.assertNotEqual(answer.question_id, other_answer.question_id)
        self.assertEqual(verify(other_question, artifact, data, answer, executor=self.executor),
                         Verdict("REJECT", "QUESTION_MISMATCH"))
        self.assertEqual(verify(other_question, artifact, data, other_answer, executor=self.executor),
                         Verdict("ACCEPT"))

    def test_a_deterministic_trap_is_an_outcome(self):
        artifact, data, limits = fixture("divzero")
        question = ask(artifact, data, limits)
        answer = solve(question, artifact, data)
        self.assertEqual(answer.outcome.hex(), VECTORS["divzero"]["expected"]["canonical_outcome_hex"])
        self.assertEqual(verify(question, artifact, data, answer, executor=self.executor), Verdict("ACCEPT"))

    def test_ask_rejects_unsupported_rule_or_artifact(self):
        artifact, data, limits = fixture("stats")
        with self.assertRaisesRegex(QuestionRejected, "^UNSUPPORTED_RULE$"):
            ask(artifact, data, limits, rule="unknown")
        with self.assertRaisesRegex(QuestionRejected, "^RIR_REJECT_UNSUPPORTED$"):
            ask(*fixture("field-rir_version"))

    def test_binding_is_checked_before_starting_the_executor(self):
        artifact, data, limits = fixture("stats")
        question = ask(artifact, data, limits)
        answer = solve(question, artifact, data)
        missing_executor = self.executor.with_name("missing")
        self.assertEqual(verify(question, artifact + b"\x00", data, answer, executor=missing_executor),
                         Verdict("REJECT", "ARTIFACT_MISMATCH"))
        self.assertEqual(verify(question, artifact, data + b"\x00", answer, executor=missing_executor),
                         Verdict("REJECT", "INPUT_MISMATCH"))
        with self.assertRaises(ExecutionError):
            verify(question, artifact, data, answer, executor=missing_executor)
