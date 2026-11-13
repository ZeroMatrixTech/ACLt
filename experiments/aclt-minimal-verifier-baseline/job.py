# SPDX-License-Identifier: Apache-2.0
"""Two deterministic slices and ordered composition of stats-int-v1 output."""

from dataclasses import dataclass
from struct import Struct

from baseline import ARTIFACT_TAG, INPUT_TAG, LIMITS, QUESTION_TAG, Answer, Verdict, ask
from tools.verification_profile import codec

RULE = "aclt.exp.stats-chunk-merge@1"
BOUNDED_RULE = "aclt.exp.stats-chunk-merge@2"
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


def stats_gas_bound(count: int, chunk: int) -> int:
    """Metered cost of the pinned stats artifact's valid-input OK path."""
    codec.need(1 <= codec.uint(count) <= 100000 and 1 <= codec.uint(chunk) <= 100000,
               "invalid stats count or chunk")
    blocks = (count + chunk - 1) // chunk
    return 8312 + 108 * count + 191 * blocks


def stats_input(artifact: bytes, data: bytes) -> tuple[int, int, memoryview]:
    codec.need(type(artifact) is bytes and codec.domain_hash(ARTIFACT_TAG, artifact) == STATS_RIR_ID,
               "unsupported stats artifact")
    codec.need(type(data) is bytes and len(data) >= HEADER.size, "invalid stats header")
    chunk, count = HEADER.unpack_from(data)
    codec.need(1 <= chunk <= 100000 and 1 <= count <= 100000
               and len(data) == HEADER.size + count * VALUE.size, "invalid stats length or chunk")
    values = memoryview(data)[HEADER.size:]
    codec.need(all(-10**9 <= value <= 10**9 for (value,) in VALUE.iter_unpack(values)),
               "invalid stats value")
    return chunk, count, values


def admit_stats_root(artifact: bytes, data: bytes, limits: dict) -> bytes:
    """Admit only the successful whole-task path of the pinned artifact."""
    chunk, count, _ = stats_input(artifact, data)
    question = ask(artifact, data, limits)
    required_gas = stats_gas_bound(count, chunk)
    required_output = ROW.size * ((count + chunk - 1) // chunk)
    codec.need(limits["gas_limit"] >= required_gas,
               f"whole-task gas limit needs at least {required_gas}")
    codec.need(limits["output_limit"] >= required_output,
               f"whole-task output limit needs at least {required_output} bytes")
    return question


def freeze_slice(artifact: bytes, values: memoryview, chunk: int, start: int, stop: int,
                 limits: dict, *, allocate_gas: bool) -> Slice:
    raw = HEADER.pack(chunk, stop - start) + values[start * VALUE.size:stop * VALUE.size].tobytes()
    shard_limits = dict(limits, gas_limit=stats_gas_bound(stop - start, chunk)) if allocate_gas else limits
    return Slice(start, stop, raw, ask(artifact, raw, shard_limits))


def prepare_job(artifact: bytes, data: bytes, limits: dict, *, allocate_gas: bool = False,
                solve_budget: int | None = None) -> tuple[bytes, tuple[Slice, Slice]]:
    """Bind a validated stats input to exactly two chunk-aligned positions."""
    chunk, count, values = stats_input(artifact, data)
    block_count = (count + chunk - 1) // chunk
    codec.need(block_count >= 2, "job needs at least two stats blocks")
    cut = (block_count // 2) * chunk
    bounded = allocate_gas or solve_budget is not None
    codec.fields(limits, LIMITS)
    for limit in limits.values():
        codec.uint(limit)
    if solve_budget is not None:
        required = stats_gas_bound(cut, chunk) + stats_gas_bound(count - cut, chunk)
        codec.need(codec.uint(solve_budget) >= required, "insufficient shard solve budget")

    slices = (
        freeze_slice(artifact, values, chunk, 0, cut, limits, allocate_gas=bounded),
        freeze_slice(artifact, values, chunk, cut, count, limits, allocate_gas=bounded),
    )
    plan = {
        "rule": BOUNDED_RULE if bounded else RULE,
        "artifact_digest": STATS_RIR_ID,
        "input_digest": codec.domain_hash(INPUT_TAG, data),
        "chunk": chunk,
        "slices": [{"start": s.start, "stop": s.stop, "question_id": s.question_id} for s in slices],
    }
    if solve_budget is not None:
        plan["solve_budget"] = solve_budget
    return codec.encode(plan), slices


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
              submissions: list[tuple[Answer, dict]], *, allocate_gas: bool = False,
              solve_budget: int | None = None) -> bytes:
    """Validate plan and receipt bindings, then compose accepted OK results."""
    expected_plan, slices = prepare_job(artifact, data, limits, allocate_gas=allocate_gas,
                                        solve_budget=solve_budget)
    codec.need(plan == expected_plan, "plan does not match original input and limits")
    chunk, count = HEADER.unpack_from(data)
    accepted = accepted_outputs(plan, slices, submissions)
    return compose_rows(0, count, chunk, [(shard.start, shard.stop, accepted[shard.start][0]) for shard in slices])


def accepted_outputs(plan: bytes, slices: tuple[Slice, ...],
                     submissions: list[tuple[Answer, dict]]) -> dict[int, tuple[bytes, int]]:
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

    outputs = {}
    for start, result in accepted.items():
        codec.need(type(result) is dict and result.get("outcome") == "OK", "slice needs OK output")
        codec.fields(result, ("outcome", "gas_used", "output"))
        codec.uint(result["gas_used"])
        codec.need(type(result["output"]) is bytes, "invalid slice output bytes")
        outputs[start] = (result["output"], result["gas_used"])
    return outputs


def compose_rows(parent_start: int, parent_stop: int, chunk: int,
                 children: list[tuple[int, int, bytes]]) -> bytes:
    """Compose child-local rows into coordinates relative to their parent."""
    output = bytearray()
    cursor = parent_start
    for start, stop, raw in children:
        delta = start - parent_start
        codec.need(start == cursor and delta % chunk == 0 and start < stop <= parent_stop,
                   "invalid child coverage")
        count = stop - start
        codec.need(len(raw) == ROW.size * ((count + chunk - 1) // chunk), "unexpected slice row count")
        for index, (row, offset, size, total, low, high) in enumerate(ROW.iter_unpack(raw)):
            codec.need(row == index and offset == index * chunk and size == min(chunk, count - offset),
                       "invalid slice row coordinates")
            output.extend(ROW.pack(row + delta // chunk, offset + delta, size, total, low, high))
        cursor = stop
    codec.need(cursor == parent_stop, "incomplete child coverage")
    return bytes(output)
