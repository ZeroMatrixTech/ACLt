# SPDX-License-Identifier: Apache-2.0
"""Job messages over the existing length-prefixed LAN transport."""

import hashlib
import json
from pathlib import Path
import socket

from baseline import ARTIFACT_TAG, LIMITS, QUESTION_TAG, Answer, ask, solve, verify
from job import (
    BOUNDED_RULE, HEADER, JOB_TAG, RULE, STATS_RIR_ID, VALUE, Slice, merge_job, prepare_job,
    record_verdict, stats_gas_bound,
)
from tools.formal_migration.s2_transport import receive, send
from tools.verification_profile import codec

TIMEOUT = 90


def encode_answer(answer: Answer) -> dict:
    return {"question_id": answer.question_id, "outcome": answer.outcome}


def decode_answer(value: dict) -> Answer:
    codec.fields(value, ("question_id", "outcome"))
    codec.digest_bytes(value["question_id"])
    codec.need(type(value["outcome"]) is bytes, "expected outcome bytes")
    return Answer(value["question_id"], value["outcome"])


def request(action: str, plan: bytes, artifact: bytes, shard: Slice, answer: Answer | None = None) -> bytes:
    message = {"action": action, "plan": plan, "start": shard.start, "artifact": artifact,
               "question": shard.question, "data": shard.data}
    if answer is not None:
        message["answer"] = encode_answer(answer)
    return codec.encode(message)


def handle_request(raw: bytes, expected_action: str, executor: Path, *, prior_plan: bytes | None = None
                   ) -> tuple[bytes, bytes]:
    message = codec.decode(raw)
    required = ("action", "plan", "start", "artifact", "question", "data")
    if expected_action == "VERIFY":
        required += ("answer",)
    codec.fields(message, required)
    codec.need(message["action"] == expected_action, "unexpected LAN operation")
    plan = message["plan"]
    codec.need(prior_plan is None or plan == prior_plan, "LAN operation changed the plan")
    meta = codec.decode(plan)
    codec.fields(meta, ("rule", "artifact_digest", "input_digest", "chunk", "slices"), ("solve_budget",))
    codec.need(meta["rule"] in (RULE, BOUNDED_RULE) and meta["artifact_digest"] == STATS_RIR_ID,
               "unsupported LAN plan")
    codec.need(meta["rule"] == BOUNDED_RULE or "solve_budget" not in meta, "unexpected legacy solve budget")
    codec.digest_bytes(meta["input_digest"])
    codec.need(type(meta["slices"]) is list and len(meta["slices"]) == 2, "expected two planned positions")
    for planned in meta["slices"]:
        codec.fields(planned, ("start", "stop", "question_id"))
    slot = meta["slices"][1 if expected_action == "SOLVE" else 0]
    start = codec.uint(message["start"])
    codec.need(start == codec.uint(slot["start"]), "LAN slice position mismatch")
    count = codec.uint(slot["stop"]) - start
    artifact, question, data = (message[key] for key in ("artifact", "question", "data"))
    codec.need(type(artifact) is bytes and codec.domain_hash(ARTIFACT_TAG, artifact) == STATS_RIR_ID,
               "LAN artifact mismatch")
    codec.need(type(question) is bytes and codec.domain_hash(QUESTION_TAG, question) == slot["question_id"],
               "LAN question mismatch")
    chunk = codec.uint(meta["chunk"])
    codec.need(type(data) is bytes and count > 0 and len(data) == HEADER.size + count * VALUE.size
               and HEADER.unpack_from(data) == (chunk, count), "LAN slice shape mismatch")
    if meta["rule"] == BOUNDED_RULE:
        frozen = codec.decode(question)
        codec.fields(frozen, ("rule", "artifact_digest", "input_digest", "limits"))
        codec.fields(frozen["limits"], LIMITS)
        codec.need(codec.uint(frozen["limits"]["gas_limit"]) == stats_gas_bound(count, chunk),
                   "LAN gas allocation mismatch")
        if "solve_budget" in meta:
            required = sum(stats_gas_bound(codec.uint(s["stop"]) - codec.uint(s["start"]), chunk)
                           for s in meta["slices"])
            codec.need(codec.uint(meta["solve_budget"]) >= required, "insufficient LAN shard solve budget")
    if expected_action == "SOLVE":
        answer = solve(question, artifact, data)
        reply = {"job_id": codec.domain_hash(JOB_TAG, plan), "start": start, "answer": encode_answer(answer)}
    else:
        answer = decode_answer(message["answer"])
        reply = record_verdict(plan, start, answer, verify(question, artifact, data, answer, executor=executor))
    return plan, codec.encode(reply)


def serve(bind: str, executor: Path, output: Path) -> None:
    output.mkdir(mode=0o700)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((bind, 0))
        listener.listen(1)
        listener.settimeout(TIMEOUT)
        print(json.dumps({"port": listener.getsockname()[1]}), flush=True)
        connection, peer = listener.accept()
        with connection:
            codec.need(peer[0] != bind and not peer[0].startswith("127."), "expected a distinct LAN peer")
            connection.settimeout(TIMEOUT)
            plan = None
            for action in ("SOLVE", "VERIFY"):
                raw = receive(connection)
                (output / f"{action}-request.cbor").write_bytes(raw)
                plan, response = handle_request(raw, action, executor, prior_plan=plan)
                (output / f"{action}-response.cbor").write_bytes(response)
                send(connection, response)


def run_job(connection: socket.socket, artifact: bytes, data: bytes, limits: dict,
            executor: Path, output: Path, *, solve_budget: int | None = None) -> dict:
    plan, (a_slice, b_slice) = prepare_job(artifact, data, limits, allocate_gas=True, solve_budget=solve_budget)
    reference_question = ask(artifact, data, limits)
    job_id = codec.domain_hash(JOB_TAG, plan)
    (output / "plan.cbor").write_bytes(plan)
    (output / "original-input.bin").write_bytes(data)
    (output / "artifact.cbor").write_bytes(artifact)

    def exchange(action: str, raw: bytes) -> dict:
        (output / f"{action}-request.cbor").write_bytes(raw)
        send(connection, raw)
        response = receive(connection)
        (output / f"{action}-response.cbor").write_bytes(response)
        return codec.decode(response)

    b_response = exchange("SOLVE", request("SOLVE", plan, artifact, b_slice))
    codec.fields(b_response, ("job_id", "start", "answer"))
    codec.need(b_response["job_id"] == job_id and codec.uint(b_response["start"]) == b_slice.start,
               "LAN submission slot mismatch")
    b_answer = decode_answer(b_response["answer"])
    a_answer = solve(a_slice.question, artifact, a_slice.data)
    a_receipt = exchange("VERIFY", request("VERIFY", plan, artifact, a_slice, a_answer))
    b_receipt = record_verdict(
        plan, b_slice.start, b_answer, verify(b_slice.question, artifact, b_slice.data, b_answer, executor=executor),
    )
    (output / "A-verdict.cbor").write_bytes(codec.encode(b_receipt))
    submissions = [(a_answer, a_receipt), (b_answer, b_receipt)]
    combined = merge_job(plan, artifact, data, limits, submissions, allocate_gas=True,
                         solve_budget=solve_budget)

    # Acceptance reference runs only after composition from the verified slices.
    reversed_output = merge_job(plan, artifact, data, limits, submissions[::-1], allocate_gas=True,
                                solve_budget=solve_budget)
    reference = solve(reference_question, artifact, data)
    reference_outcome = codec.decode(reference.outcome)
    codec.need(reference_outcome["outcome"] == "OK", "reference execution did not return OK")
    (output / "reference-output.bin").write_bytes(reference_outcome["output"])
    codec.need(combined == reversed_output == reference_outcome["output"], "composition output mismatch")
    (output / "merged-output.bin").write_bytes(combined)

    return {
        "job_id": job_id.hex(),
        "output_sha256": hashlib.sha256(combined).hexdigest(),
        "output_bytes": len(combined),
        "reference_gas_used": reference_outcome["gas_used"],
        "solve_budget": solve_budget,
        "allocated_solve_gas": sum(codec.decode(shard.question)["limits"]["gas_limit"]
                                   for shard in (a_slice, b_slice)),
        "reverse_order_equal": True,
        "slices": [
            {"start": shard.start, "stop": shard.stop, "question_id": shard.question_id.hex(),
             "answer_digest": receipt["answer_digest"].hex(),
             "execution_host": worker, "verification_host": validator,
             "status": receipt["status"], "gas_limit": codec.decode(shard.question)["limits"]["gas_limit"],
             "gas_used": codec.decode(answer.outcome)["gas_used"]}
            for shard, (answer, receipt), worker, validator in zip(
                (a_slice, b_slice), submissions, ("A", "B"), ("B", "A"), strict=True)
        ],
    }
