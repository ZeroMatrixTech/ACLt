# SPDX-License-Identifier: Apache-2.0
"""Trusted round-robin tree jobs and evidence replay for three or more guests."""

from collections.abc import Callable
import hashlib
import json
from pathlib import Path
import time

from baseline import Verdict, ask, solve
from dualhost import fixture
from job import HEADER, JOB_TAG, VALUE, record_verdict
from lan import decode_answer, handle_request, request
from tools.verification_profile import codec
from tree import merge_tree, prepare_tree

MAX_GUESTS = 16
MAX_LEAVES = 32
Exchange = Callable[[str, str, int, bytes], bytes]


def guest_roles(count: int) -> tuple[str, ...]:
    if not 2 <= count <= MAX_GUESTS:
        raise ValueError(f"guest count must be between 2 and {MAX_GUESTS}")
    return tuple(chr(ord("A") + index) for index in range(count))


def guest_ip(role: str) -> str:
    return f"10.0.3.{ord(role) - ord('A') + 1}"


def job_fixture(leaf_count: int) -> tuple[bytes, bytes, dict]:
    artifact, data, limits = fixture()
    if leaf_count > 3:
        # Preserve the original three-leaf fixture. For larger topologies, use
        # deterministic two-element blocks, with a short last block.
        values = range(1 - leaf_count, leaf_count)
        data = HEADER.pack(2, len(values)) + b"".join(VALUE.pack(value) for value in values)
    return artifact, data, limits


def assignments(roles: tuple[str, ...], leaf_count: int):
    return tuple((roles[index % len(roles)], roles[(index + 1) % len(roles)])
                 for index in range(leaf_count))


def peer_operations(roles: tuple[str, ...], leaf_count: int, role: str):
    return [(action, index, label(action, index))
            for index, (solver, verifier) in enumerate(assignments(roles, leaf_count))
            for action, owner in (("SOLVE", solver), ("VERIFY", verifier)) if role == owner]


def label(action: str, index: int) -> str:
    return f"{action}-{index}"


class IncompleteExchange(RuntimeError):
    """A remote exchange ended without a complete response."""


def fault_target(roles: tuple[str, ...], leaf_count: int, value: str) -> tuple[str, int]:
    action, separator, index = value.partition("-")
    if separator != "-" or action not in ("SOLVE", "VERIFY") or not index.isascii() or not index.isdecimal():
        raise ValueError("fault target must be SOLVE-INDEX or VERIFY-INDEX")
    index = int(index)
    if not 0 <= index < leaf_count or label(action, index) != value:
        raise ValueError("fault target must identify a planned operation")
    owner = assignments(roles, leaf_count)[index][action == "VERIFY"]
    if owner == roles[0]:
        raise ValueError("fault target must be assigned to a remote guest")
    return owner, index


def run_many(roles: tuple[str, ...], leaf_count: int, output: Path, exchange: Exchange, *,
             solve_budget: int | None, elapsed_ns: dict[str, int] | None = None) -> dict:
    started = time.monotonic_ns()
    artifact, data, limits = job_fixture(leaf_count)
    plan, leaves = prepare_tree(artifact, data, limits, solve_budget=solve_budget)
    job_id = codec.domain_hash(JOB_TAG, plan)
    (output / "plan.cbor").write_bytes(plan)
    (output / "original-input.bin").write_bytes(data)
    (output / "artifact.cbor").write_bytes(artifact)
    submissions = []
    reports = []
    wire_bytes = 0

    def dispatch(role, action, index, shard, raw):
        nonlocal wire_bytes
        name = label(action, index)
        (output / f"{name}-request.cbor").write_bytes(raw)
        try:
            response = exchange(role, action, index, raw)
        except OSError as error:
            if role == roles[0]:
                raise
            failure = dict(status="FAIL", job_id=job_id.hex(), reason="EXCHANGE_INCOMPLETE",
                           operation=name, guest=role, leaf_index=index, start=shard.start, stop=shard.stop,
                           accepted_leaf_indices=list(range(len(submissions))),
                           unaccepted_leaf_indices=list(range(len(submissions), len(leaves))),
                           output_published=False)
            (output / "failure.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
            raise IncompleteExchange(name) from error
        (output / f"{name}-response.cbor").write_bytes(response)
        if role != roles[0]:
            wire_bytes += len(raw) + len(response)
        return codec.decode(response)

    for index, (shard, (worker, verifier)) in enumerate(zip(leaves, assignments(roles, len(leaves)), strict=True)):
        result = dispatch(worker, "SOLVE", index, shard, request("SOLVE", plan, artifact, shard))
        codec.fields(result, ("job_id", "start", "answer"))
        codec.need(result["job_id"] == job_id and codec.uint(result["start"]) == shard.start,
                   "SOLVE response is for a different job or position")
        answer = decode_answer(result["answer"])
        receipt = dispatch(verifier, "VERIFY", index, shard, request("VERIFY", plan, artifact, shard, answer))
        codec.need(receipt == record_verdict(plan, shard.start, answer, Verdict("ACCEPT")),
                   "slice needs an ACCEPT bound to its exact answer")
        outcome = codec.decode(answer.outcome)
        gas_limit = codec.decode(shard.question)["limits"]["gas_limit"]
        codec.need(outcome.get("outcome") == "OK" and codec.uint(outcome["gas_used"]) == gas_limit,
                   "shard outcome or gas differs from the planned successful path")
        submissions.append((answer, receipt))
        reports.append(dict(start=shard.start, stop=shard.stop, question_id=shard.question_id.hex(),
                            execution_host=worker, verification_host=verifier, status=receipt["status"],
                            gas_limit=gas_limit, gas_used=outcome["gas_used"]))

    merge_started = time.monotonic_ns()
    tree = merge_tree(plan, artifact, data, limits, submissions, solve_budget=solve_budget)
    merge_ns = time.monotonic_ns() - merge_started
    reverse = merge_tree(plan, artifact, data, limits, submissions[::-1], solve_budget=solve_budget)
    reference_started = time.monotonic_ns()
    reference = codec.decode(solve(ask(artifact, data, limits), artifact, data).outcome)
    reference_ns = time.monotonic_ns() - reference_started
    codec.need(reference["outcome"] == "OK"
               and tree.output == reverse.output == tree.flat_output == reverse.flat_output == reference["output"],
               "composition differs from the successful whole-task reference")
    (output / "reference-output.bin").write_bytes(reference["output"])
    (output / "merged-output.bin").write_bytes(tree.output)
    (output / "flat-output.bin").write_bytes(tree.flat_output)
    summary = dict(job_id=job_id.hex(), output_sha256=hashlib.sha256(tree.output).hexdigest(),
                   output_bytes=len(tree.output), slices=reports, solve_budget=solve_budget,
                   reference_gas_used=reference["gas_used"], leaf_solve_gas_used=tree.leaf_gas_used,
                   lan_payload_bytes=wire_bytes, tree_merge_order=[list(pair) for pair in tree.merge_order])
    (output / "result.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    if elapsed_ns is not None:
        elapsed_ns.update(merge_ns=merge_ns, reference_ns=reference_ns, job_ns=time.monotonic_ns() - started)
    return summary


def replay_many(roots: dict[str, Path], leaf_count: int, executor: Path, scratch: Path, *,
                solve_budget: int | None, interrupted: str | None = None) -> dict:
    roles = guest_roles(len(roots))
    codec.need(set(roots) == set(roles), "unexpected guest roles")
    coordinator = roots[roles[0]]
    _, leaves = prepare_tree(*job_fixture(leaf_count), solve_budget=solve_budget)
    plans = {}
    expected_files = {role: set() for role in roles}

    def retained_frame(root: Path, name: str) -> bytes:
        try:
            return (root / name).read_bytes()
        except OSError as error:
            raise codec.CodecError(f"cannot read retained frame {name}") from error

    def exchange(role, action, index, raw):
        name = label(action, index)
        req, rep = f"{name}-request.cbor", f"{name}-response.cbor"
        for root in {coordinator, roots[role]}:
            codec.need(retained_frame(root, req) == raw, f"{role} {name} request differs from replay")
        expected_files[roles[0]].add(req)
        expected_files[role].add(req)
        if name == interrupted:
            raise ConnectionError("replay of incomplete exchange")
        expected_files[roles[0]].add(rep)
        expected_files[role].add(rep)
        plans[role], response = handle_request(raw, action, executor, prior_plan=plans.get(role),
                                               leaf_index=index, leaf_count=len(leaves))
        for root in {coordinator, roots[role]}:
            codec.need(retained_frame(root, rep) == response, f"{role} {name} response differs from replay")
        return response

    try:
        summary = run_many(roles, leaf_count, scratch, exchange, solve_budget=solve_budget)
    except IncompleteExchange:
        if interrupted is None:
            raise
        summary = None
    else:
        codec.need(interrupted is None, "expected exchange to be interrupted")
    for role, root in roots.items():
        actual = {file.name for pattern in ("*-request.cbor", "*-response.cbor") for file in root.glob(pattern)}
        codec.need(actual == expected_files[role], f"{role} has unexpected transcript inventory")
    for path in scratch.iterdir():
        codec.need(path.read_bytes() == (coordinator / path.name).read_bytes(),
                   f"coordinator {path.name} differs from replay")
    if summary is None:
        for root in roots.values():
            for name in ("result.json", "merged-output.bin", "flat-output.bin", "reference-output.bin"):
                codec.need(not (root / name).exists(), f"interrupted run published {name}")
        return json.loads((scratch / "failure.json").read_bytes())
    return dict(slices=len(leaves), job_id=summary["job_id"], output_sha256=summary["output_sha256"],
                lan_transcript_equal=True, leaf_solve_gas_used=summary["leaf_solve_gas_used"],
                lan_payload_bytes=summary["lan_payload_bytes"])
