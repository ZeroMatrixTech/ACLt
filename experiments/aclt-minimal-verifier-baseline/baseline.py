# SPDX-License-Identifier: Apache-2.0
"""Experimental ask/solve/verify loop for the independent RIR stats core."""

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "experiments/aclt-rir-stats-probe"
sys.path[:0] = [str(ROOT), str(PROBE)]

from independent import CoreReject, execute, validate
from tools.verification_profile import codec

RULE = "aclt.exp.rir-stats-exact@1"
QUESTION_TAG = "ACLt/Experiment/MinimalVerifier/Question/1"
INPUT_TAG = "ACLt/Experiment/MinimalVerifier/Input/1"
CONTRACT = json.loads((PROBE / "independent-contract.json").read_text(encoding="utf-8"))
ARTIFACT_TAG = CONTRACT["artifact_digest_tag"]
SUPPORT = CONTRACT["support"]
LIMITS = ("gas_limit", "output_limit", "call_depth_limit", "memory_pages_limit")


class QuestionRejected(ValueError):
    """The question or its supplied bytes could not be bound."""


class ExecutionError(RuntimeError):
    """The local evaluator could not produce a task outcome."""


@dataclass(frozen=True)
class Answer:
    question_id: bytes
    outcome: bytes


@dataclass(frozen=True)
class Verdict:
    status: str
    reason: str | None = None


def _check_limits(limits: dict) -> None:
    codec.fields(limits, LIMITS)
    for value in limits.values():
        codec.uint(value)


def ask(artifact: bytes, data: bytes, limits: dict, *, rule: str = RULE) -> bytes:
    """Return the immutable, canonical CBOR question or raise QuestionRejected."""
    if rule != RULE:
        raise QuestionRejected("UNSUPPORTED_RULE")
    if (type(artifact) is not bytes or len(artifact) > SUPPORT["artifact_bytes_max"]
            or type(data) is not bytes or len(data) > SUPPORT["input_bytes_max"]):
        raise QuestionRejected("RIR_REJECT_LIMITS")
    try:
        codec.need(type(limits) is dict, "expected limits map")
        limits = limits.copy()
        _check_limits(limits)
        validate(artifact, limits)
    except CoreReject as exc:
        raise QuestionRejected(exc.code) from exc
    except codec.CodecError as exc:
        raise QuestionRejected("INVALID_LIMITS") from exc
    return codec.encode({
        "rule": rule,
        "artifact_digest": codec.domain_hash(ARTIFACT_TAG, artifact),
        "input_digest": codec.domain_hash(INPUT_TAG, data),
        "limits": limits,
    })


def _bind(question: bytes, artifact: bytes, data: bytes) -> tuple[bytes, dict, str]:
    try:
        value = codec.decode(question)
        codec.fields(value, ("rule", "artifact_digest", "input_digest", "limits"))
        codec.digest_bytes(value["artifact_digest"])
        codec.digest_bytes(value["input_digest"])
        _check_limits(value["limits"])
    except codec.CodecError as exc:
        raise QuestionRejected("INVALID_QUESTION") from exc
    if value["rule"] != RULE:
        raise QuestionRejected("UNSUPPORTED_RULE")
    if (type(artifact) is not bytes or len(artifact) > SUPPORT["artifact_bytes_max"]
            or codec.domain_hash(ARTIFACT_TAG, artifact) != value["artifact_digest"]):
        raise QuestionRejected("ARTIFACT_MISMATCH")
    if (type(data) is not bytes or len(data) > SUPPORT["input_bytes_max"]
            or codec.domain_hash(INPUT_TAG, data) != value["input_digest"]):
        raise QuestionRejected("INPUT_MISMATCH")
    return codec.domain_hash(QUESTION_TAG, question), value["limits"], value["artifact_digest"].hex()


def solve(question: bytes, artifact: bytes, data: bytes) -> Answer:
    question_id, limits, artifact_digest = _bind(question, artifact, data)
    # Every charged step costs at least one gas. Allow one extra attempted step.
    result = execute(artifact, data, dict(limits, max_steps=limits["gas_limit"] + 1), artifact_digest)
    if result["status"] != "TASK_OUTCOME":
        raise ExecutionError(result["code"])
    return Answer(question_id, bytes.fromhex(result["canonical_outcome_hex"]))


def verify(question: bytes, artifact: bytes, data: bytes, answer: Answer, *, executor: Path) -> Verdict:
    try:
        question_id, limits, artifact_digest = _bind(question, artifact, data)
    except QuestionRejected as exc:
        return Verdict("REJECT", str(exc))
    if (type(answer) is not Answer or type(answer.question_id) is not bytes
            or type(answer.outcome) is not bytes):
        return Verdict("REJECT", "INVALID_ANSWER")
    if answer.question_id != question_id:
        return Verdict("REJECT", "QUESTION_MISMATCH")

    outcome = _rust_outcome(executor, artifact, data, limits, artifact_digest)
    if answer.outcome != outcome:
        return Verdict("REJECT", "OUTCOME_MISMATCH")
    return Verdict("ACCEPT")


def _rust_outcome(executor: Path, artifact: bytes, data: bytes, limits: dict, artifact_digest: str) -> bytes:
    try:
        with TemporaryDirectory(prefix="aclt-minimal-verifier-") as directory:
            artifact_path = Path(directory) / "artifact.cbor"
            input_path = Path(directory) / "input.bin"
            artifact_path.write_bytes(artifact)
            input_path.write_bytes(data)
            result = subprocess.run(
                [str(executor.resolve()), "--artifact", str(artifact_path), str(input_path),
                 str(limits["gas_limit"]), str(limits["output_limit"]),
                 str(limits["call_depth_limit"]), str(limits["gas_limit"] + 1),
                 str(limits["memory_pages_limit"]), artifact_digest],
                capture_output=True, timeout=60,
            )
        report = json.loads(result.stdout)
        if type(report) is not dict:
            raise ExecutionError("Rust evaluator returned an invalid report")
        if result.returncode != 0 or report["status"] != "TASK_OUTCOME":
            raise ExecutionError(f'Rust evaluator: {report.get("code", "no task outcome")}')
        if report["rir_digest"] != artifact_digest:
            raise ExecutionError("Rust evaluator returned an unexpected artifact digest")
        outcome = bytes.fromhex(report["canonical_outcome_hex"])
        if not outcome:
            raise ExecutionError("Rust evaluator returned an empty outcome")
        return outcome
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, TypeError) as exc:
        raise ExecutionError("Rust evaluator could not produce a task outcome") from exc
