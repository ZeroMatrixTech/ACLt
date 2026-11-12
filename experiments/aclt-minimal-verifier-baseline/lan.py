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
from tree import TREE_RULE, merge_tree, prepare_tree, tree_slots

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


def operations(leaf_count: int) -> list[tuple[str, int, str]]:
    """Keep the original two-leaf transcript names and index later exchanges."""
    return [(action, index, action if index == first else f"{action}-{index}")
            for action, first in (("SOLVE", 1), ("VERIFY", 0))
            for index in range(first, leaf_count, 2)]


def handle_request(raw: bytes, expected_action: str, executor: Path, *, prior_plan: bytes | None = None,
                   leaf_index: int | None = None, leaf_count: int = 2) -> tuple[bytes, bytes]:
    message = codec.decode(raw)
    required = ("action", "plan", "start", "artifact", "question", "data")
    if expected_action == "VERIFY":
        required += ("answer",)
    codec.fields(message, required)
    codec.need(message["action"] == expected_action, "unexpected LAN operation")
    plan = message["plan"]
    codec.need(prior_plan is None or plan == prior_plan, "LAN operation changed the plan")
    meta = codec.decode(plan)
    codec.fields(meta, ("rule", "artifact_digest", "input_digest", "chunk"),
                 ("solve_budget", "slices", "nodes"))
    rule = meta["rule"]
    codec.need(rule in (RULE, BOUNDED_RULE, TREE_RULE) and meta["artifact_digest"] == STATS_RIR_ID,
               "unsupported LAN plan")
    codec.need(rule != RULE or "solve_budget" not in meta, "unexpected legacy solve budget")
    codec.digest_bytes(meta["input_digest"])
    if rule == TREE_RULE:
        codec.need("nodes" in meta and "slices" not in meta, "expected tree nodes")
        slots = tree_slots(meta)
    else:
        codec.need("nodes" not in meta and type(meta.get("slices")) is list, "expected flat positions")
        slots = meta["slices"]
        codec.need(len(slots) == 2, "expected two planned positions")
        for planned in slots:
            codec.fields(planned, ("start", "stop", "question_id"))
    codec.need(len(slots) == leaf_count, "unexpected LAN leaf count")
    index = (1 if expected_action == "SOLVE" else 0) if leaf_index is None else leaf_index
    slot = slots[index]
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
    if rule in (BOUNDED_RULE, TREE_RULE):
        frozen = codec.decode(question)
        codec.fields(frozen, ("rule", "artifact_digest", "input_digest", "limits"))
        codec.fields(frozen["limits"], LIMITS)
        codec.need(codec.uint(frozen["limits"]["gas_limit"]) == stats_gas_bound(count, chunk),
                   "LAN gas allocation mismatch")
        if "solve_budget" in meta:
            required = sum(stats_gas_bound(codec.uint(s["stop"]) - codec.uint(s["start"]), chunk)
                           for s in slots)
            codec.need(codec.uint(meta["solve_budget"]) >= required, "insufficient LAN shard solve budget")
    if expected_action == "SOLVE":
        answer = solve(question, artifact, data)
        reply = {"job_id": codec.domain_hash(JOB_TAG, plan), "start": start, "answer": encode_answer(answer)}
    else:
        answer = decode_answer(message["answer"])
        reply = record_verdict(plan, start, answer, verify(question, artifact, data, answer, executor=executor))
    return plan, codec.encode(reply)


def serve(bind: str, executor: Path, output: Path, *, leaf_count: int = 2, port: int = 0,
          schedule: list[tuple[str, int, str]] | None = None, expected_peer: str | None = None) -> dict:
    output.mkdir(mode=0o700)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((bind, port))
        listener.listen(1)
        listener.settimeout(TIMEOUT)
        local_port = listener.getsockname()[1]
        print(json.dumps({"port": local_port}), flush=True)
        connection, peer = listener.accept()
        with connection:
            codec.need(peer[0] != bind and not peer[0].startswith("127."), "expected a distinct LAN peer")
            codec.need(expected_peer is None or peer[0] == expected_peer, "unexpected LAN peer")
            connection.settimeout(TIMEOUT)
            plan = None
            for action, index, label in operations(leaf_count) if schedule is None else schedule:
                raw = receive(connection)
                (output / f"{label}-request.cbor").write_bytes(raw)
                plan, response = handle_request(raw, action, executor, prior_plan=plan,
                                                leaf_index=index, leaf_count=leaf_count)
                (output / f"{label}-response.cbor").write_bytes(response)
                send(connection, response)
    return {"port": local_port, "local_ip": bind, "peer_ip": peer[0]}


def run_job(connection: socket.socket, artifact: bytes, data: bytes, limits: dict,
            executor: Path, output: Path, *, solve_budget: int | None = None,
            recursive: bool = False) -> dict:
    if recursive:
        plan, slices = prepare_tree(artifact, data, limits, solve_budget=solve_budget)
    else:
        plan, slices = prepare_job(artifact, data, limits, allocate_gas=True, solve_budget=solve_budget)
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

    submissions = []
    for action, index, label in operations(len(slices)):
        shard = slices[index]
        if action == "SOLVE":
            response = exchange(label, request(action, plan, artifact, shard))
            codec.fields(response, ("job_id", "start", "answer"))
            codec.need(response["job_id"] == job_id and codec.uint(response["start"]) == shard.start,
                       "LAN submission slot mismatch")
            answer = decode_answer(response["answer"])
            verdict = verify(shard.question, artifact, shard.data, answer, executor=executor)
            receipt = record_verdict(plan, shard.start, answer, verdict)
            name = "A-verdict" if index == 1 else f"A-verdict-{index}"
            (output / f"{name}.cbor").write_bytes(codec.encode(receipt))
        else:
            answer = solve(shard.question, artifact, shard.data)
            receipt = exchange(label, request(action, plan, artifact, shard, answer))
            codec.need(type(receipt) is dict and receipt.get("start") == shard.start, "LAN verdict slot mismatch")
        submissions.append((answer, receipt))

    if recursive:
        tree = merge_tree(plan, artifact, data, limits, submissions, solve_budget=solve_budget)
        reverse = merge_tree(plan, artifact, data, limits, submissions[::-1], solve_budget=solve_budget)
        combined, reversed_output = tree.output, reverse.output
        codec.need(combined == tree.flat_output == reverse.flat_output, "flat and recursive outputs differ")
        codec.need(tree.leaf_gas_used == tree.flat_gas_used == reverse.leaf_gas_used,
                   "flat and recursive leaf gas differ")
        (output / "flat-output.bin").write_bytes(tree.flat_output)
        (output / "tree-merge-order.json").write_text(json.dumps(tree.merge_order) + "\n")
    else:
        combined = merge_job(plan, artifact, data, limits, submissions, allocate_gas=True,
                             solve_budget=solve_budget)
        reversed_output = merge_job(plan, artifact, data, limits, submissions[::-1], allocate_gas=True,
                                    solve_budget=solve_budget)

    # Acceptance reference runs only after composition from the verified slices.
    reference = solve(reference_question, artifact, data)
    reference_outcome = codec.decode(reference.outcome)
    codec.need(reference_outcome["outcome"] == "OK", "reference execution did not return OK")
    (output / "reference-output.bin").write_bytes(reference_outcome["output"])
    codec.need(combined == reversed_output == reference_outcome["output"], "composition output mismatch")
    (output / "merged-output.bin").write_bytes(combined)

    ordered = {receipt["start"]: (answer, receipt) for answer, receipt in submissions}
    reports = []
    for index, shard in enumerate(slices):
        answer, receipt = ordered[shard.start]
        worker, validator = ("B", "A") if index % 2 else ("A", "B")
        reports.append({
            "start": shard.start, "stop": shard.stop, "question_id": shard.question_id.hex(),
            "answer_digest": receipt["answer_digest"].hex(), "execution_host": worker,
            "verification_host": validator, "status": receipt["status"],
            "gas_limit": codec.decode(shard.question)["limits"]["gas_limit"],
            "gas_used": codec.decode(answer.outcome)["gas_used"],
        })
    summary = {
        "job_id": job_id.hex(),
        "output_sha256": hashlib.sha256(combined).hexdigest(),
        "output_bytes": len(combined),
        "reference_gas_used": reference_outcome["gas_used"],
        "solve_budget": solve_budget,
        "allocated_solve_gas": sum(shard["gas_limit"] for shard in reports),
        "reverse_order_equal": True,
        "slices": reports,
    }
    if recursive:
        summary["flat_output_equal"] = True
        summary["tree_merge_order"] = tree.merge_order
        summary["leaf_solve_gas_used"] = tree.leaf_gas_used
        summary["flat_leaf_solve_gas_used"] = tree.flat_gas_used
    return summary
