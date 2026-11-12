# SPDX-License-Identifier: Apache-2.0
"""Breadth-first partition and child-ready composition for the pinned stats job."""

from dataclasses import dataclass

from baseline import INPUT_TAG, LIMITS, Answer
from job import STATS_RIR_ID, Slice, accepted_outputs, compose_rows, freeze_slice, stats_gas_bound, stats_input
from tools.verification_profile import codec

TREE_RULE = "aclt.exp.stats-chunk-tree@1"


@dataclass(frozen=True)
class TreeResult:
    output: bytes
    flat_output: bytes
    leaf_gas_used: int
    flat_gas_used: int
    merge_order: tuple[tuple[int, int], ...]


def layout(count: int, chunk: int) -> list[dict]:
    """Number nodes breadth first; split until each leaf holds one original block."""
    stats_gas_bound(count, chunk)
    intervals = [(0, count)]
    nodes = []
    for start, stop in intervals:
        node = {"start": start, "stop": stop}
        blocks = (stop - start + chunk - 1) // chunk
        if blocks > 1:
            cut = start + (blocks // 2) * chunk
            first = len(intervals)
            node["children"] = [first, first + 1]
            intervals.extend(((start, cut), (cut, stop)))
        nodes.append(node)
    return nodes


def tree_slots(meta: dict) -> list[dict]:
    """Check canonical breadth-first shape and extract ordered leaf positions."""
    nodes = meta["nodes"]
    codec.need(type(nodes) is list and bool(nodes), "missing tree nodes")
    codec.fields(nodes[0], ("start", "stop"), ("children", "question_id"))
    shape = layout(codec.uint(nodes[0]["stop"]), codec.uint(meta["chunk"]))
    codec.need(len(shape) == len(nodes), "invalid BFS node inventory")
    leaves = []
    for actual, expected in zip(nodes, shape, strict=True):
        if "children" not in expected:
            codec.fields(actual, ("start", "stop", "question_id"))
            expected["question_id"] = codec.digest_bytes(actual["question_id"])
            leaves.append(actual)
        codec.need(codec.encode(actual) == codec.encode(expected), "invalid BFS node shape")
    return sorted(leaves, key=lambda node: node["start"])


def prepare_tree(artifact: bytes, data: bytes, limits: dict, *,
                 solve_budget: int | None = None) -> tuple[bytes, tuple[Slice, ...]]:
    chunk, count, values = stats_input(artifact, data)
    nodes = layout(count, chunk)
    codec.fields(limits, LIMITS)
    for limit in limits.values():
        codec.uint(limit)
    leaf_nodes = sorted((node for node in nodes if "children" not in node), key=lambda node: node["start"])
    required = sum(stats_gas_bound(node["stop"] - node["start"], chunk) for node in leaf_nodes)
    if solve_budget is not None:
        codec.need(codec.uint(solve_budget) >= required, "insufficient leaf solve budget")
    slices = tuple(freeze_slice(artifact, values, chunk, node["start"], node["stop"], limits, allocate_gas=True)
                   for node in leaf_nodes)
    for node, shard in zip(leaf_nodes, slices, strict=True):
        node["question_id"] = shard.question_id
    plan = {
        "rule": TREE_RULE,
        "artifact_digest": STATS_RIR_ID,
        "input_digest": codec.domain_hash(INPUT_TAG, data),
        "chunk": chunk,
        "nodes": nodes,
    }
    if solve_budget is not None:
        plan["solve_budget"] = solve_budget
    return codec.encode(plan), slices


def merge_tree(plan: bytes, artifact: bytes, data: bytes, limits: dict,
               submissions: list[tuple[Answer, dict]], *, solve_budget: int | None = None
               ) -> TreeResult:
    """Consume leaf receipts in arrival order and check flat and recursive results."""
    expected, slices = prepare_tree(artifact, data, limits, solve_budget=solve_budget)
    codec.need(plan == expected, "tree plan does not match original input and limits")
    outputs = accepted_outputs(plan, slices, submissions)
    meta = codec.decode(plan)
    chunk, nodes = meta["chunk"], meta["nodes"]
    parents = {child: index for index, node in enumerate(nodes) for child in node.get("children", ())}
    leaf_ids = {node["start"]: index for index, node in enumerate(nodes) if "children" not in node}
    ready = {}
    merged = []
    for start, output in outputs.items():
        index = leaf_ids[start]
        ready[index] = output
        while index in parents:
            index = parents[index]
            parent = nodes[index]
            if any(child not in ready for child in parent["children"]):
                break
            children = []
            gas = 0
            for child in parent["children"]:
                child_output, child_gas = ready.pop(child)
                children.append((nodes[child]["start"], nodes[child]["stop"], child_output))
                gas += child_gas
            ready[index] = (compose_rows(parent["start"], parent["stop"], chunk, children), gas)
            merged.append((index, start))

    flat = compose_rows(0, nodes[0]["stop"], chunk,
                        [(shard.start, shard.stop, outputs[shard.start][0]) for shard in slices])
    output, gas = ready[0]
    return TreeResult(output, flat, gas, sum(leaf_gas for _, leaf_gas in outputs.values()), tuple(merged))
