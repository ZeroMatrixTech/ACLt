# SPDX-License-Identifier: Apache-2.0
"""Two deterministic slices and ordered composition of stats-int-v1 output."""

from dataclasses import dataclass
from struct import Struct

from baseline import ARTIFACT_TAG, INPUT_TAG, QUESTION_TAG, Answer, Verdict, ask
from tools.verification_profile import codec

RULE = "aclt.exp.stats-chunk-merge@1"
JOB_TAG = "ACLt/Experiment/MinimalVerifier/Job/1"
ANSWER_TAG = "ACLt/Experiment/MinimalVerifier/Answer/1"
STATS_RIR_ID = bytes.fromhex("7077c1ac21677dc89040c65a95a3008c43b0292c9e3763a67a4e44055c8a2879")
HEADER = Struct("<QQ")
VALUE = Struct("<q")
ROW = Struct("<QQQqqq")


@dataclass(frozen=True)
class Slice:
    start: int
    stop: int
    data: bytes
    question: bytes

    @property
    def question_id(self) -> bytes:
        return codec.domain_hash(QUESTION_TAG, self.question)


def prepare_job(artifact: bytes, data: bytes, limits: dict) -> tuple[bytes, tuple[Slice, Slice]]:
    """Bind a validated stats input to exactly two chunk-aligned positions."""
    codec.need(type(artifact) is bytes and codec.domain_hash(ARTIFACT_TAG, artifact) == STATS_RIR_ID,
               "unsupported stats artifact")
    codec.need(type(data) is bytes and len(data) >= HEADER.size, "invalid stats header")
    chunk, count = HEADER.unpack_from(data)
    codec.need(1 <= chunk <= 100000 and 1 <= count <= 100000
               and len(data) == HEADER.size + count * VALUE.size, "invalid stats length or chunk")
    values = memoryview(data)[HEADER.size:]
    codec.need(all(-10**9 <= value <= 10**9 for (value,) in VALUE.iter_unpack(values)),
               "invalid stats value")
    block_count = (count + chunk - 1) // chunk
    codec.need(block_count >= 2, "job needs at least two stats blocks")
    cut = (block_count // 2) * chunk

    def freeze(start: int, stop: int) -> Slice:
        raw = HEADER.pack(chunk, stop - start) + values[start * VALUE.size:stop * VALUE.size].tobytes()
        return Slice(start, stop, raw, ask(artifact, raw, limits))

    slices = (freeze(0, cut), freeze(cut, count))
    plan = codec.encode({
        "rule": RULE,
        "artifact_digest": STATS_RIR_ID,
        "input_digest": codec.domain_hash(INPUT_TAG, data),
        "chunk": chunk,
        "slices": [{"start": s.start, "stop": s.stop, "question_id": s.question_id} for s in slices],
    })
    return plan, slices


def answer_digest(answer: Answer) -> bytes:
    # A fixed 32-byte question ID makes the digest preimage unambiguous.
    codec.digest_bytes(answer.question_id)
    codec.need(type(answer.outcome) is bytes, "expected outcome bytes")
    return codec.domain_hash(ANSWER_TAG, answer.question_id + answer.outcome)


def record_verdict(plan: bytes, start: int, answer: Answer, verdict: Verdict) -> dict:
    receipt = {
        "job_id": codec.domain_hash(JOB_TAG, plan),
        "start": start,
        "question_id": answer.question_id,
        "answer_digest": answer_digest(answer),
        "status": verdict.status,
    }
    if verdict.reason is not None:
        receipt["reason"] = verdict.reason
    return receipt


def merge_job(plan: bytes, artifact: bytes, data: bytes, limits: dict,
              submissions: list[tuple[Answer, dict]]) -> bytes:
    """Validate plan and receipt bindings, then compose accepted OK results."""
    expected_plan, slices = prepare_job(artifact, data, limits)
    codec.need(plan == expected_plan, "plan does not match original input and limits")
    expected = {s.start: s for s in slices}
    accepted = {}
    for answer, receipt in submissions:
        codec.fields(receipt, ("job_id", "start", "question_id", "answer_digest", "status"), ("reason",))
        start = codec.uint(receipt["start"])
        codec.need(start in expected, "unexpected slice position")
        codec.need(start not in accepted, "duplicate slice position")
        codec.need(answer.question_id == expected[start].question_id, "slice question mismatch")
        codec.need(receipt == record_verdict(plan, start, answer, Verdict("ACCEPT")),
                   "slice needs an ACCEPT bound to its exact answer")
        accepted[start] = codec.decode(answer.outcome)
    codec.need(accepted.keys() == expected.keys(), "missing slice position")

    chunk, _ = HEADER.unpack_from(data)
    output = bytearray()
    for start, shard in expected.items():
        result = accepted[start]
        codec.need(type(result) is dict and result.get("outcome") == "OK", "slice needs OK output")
        codec.fields(result, ("outcome", "gas_used", "output"))
        codec.uint(result["gas_used"])
        codec.need(type(result["output"]) is bytes, "invalid slice output bytes")
        count = shard.stop - start
        codec.need(len(result["output"]) == ROW.size * ((count + chunk - 1) // chunk),
                   "unexpected slice row count")
        for index, (row, offset, size, total, low, high) in enumerate(ROW.iter_unpack(result["output"])):
            codec.need(row == index and offset == index * chunk and size == min(chunk, count - offset),
                       "invalid slice row coordinates")
            output.extend(ROW.pack(row + start // chunk, offset + start, size, total, low, high))
    return bytes(output)
