# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import multivm
from multivm_job import assignments, guest_roles, replay_many
from test_baseline import build_executor
from tools.verification_profile import codec


class TopologyTests(unittest.TestCase):
    def test_role_rotation_wraps_when_leaves_outnumber_guests(self):
        roles = guest_roles(4)
        self.assertEqual(assignments(roles, 6),
                         (("A", "B"), ("B", "C"), ("C", "D"), ("D", "A"), ("A", "B"), ("B", "C")))

    def test_distinct_hub_ports_and_macs(self):
        links = {"B": 17701, "C": 17702}
        commands = {role: multivm.boot_arguments(role, Path("kernel"), Path("initramfs"), Path("disk"),
                                                 Path("log"), "tcg", 1024, 17701, "commit", None,
                                                 True, 3, links) for role in guest_roles(3)}
        self.assertIn("hubport,id=hubC,hubid=0,netdev=linkC", commands["A"])
        self.assertIn("socket,id=n0,listen=127.0.0.1:17702", commands["C"])
        self.assertEqual(len({commands[role][-1] for role in commands}), 3)


class RetainedTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        work = TemporaryDirectory(prefix="aclt-nvm-evidence-")
        cls.addClassCleanup(work.cleanup)
        cls.base = Path(work.name)
        cls.executor = cls.base / "executor"
        build_executor(multivm.ROOT / multivm.EXECUTOR_SOURCE, cls.executor)
        for name in ("MULTIVM-N-20261112", "MULTIVM-ROOT-LIMITS"):
            archive = multivm.ROOT / "docs/testing/public-evidence" / f"{name}-public-evidence.tar.gz"
            with tarfile.open(archive, "r:gz") as bundle:
                bundle.extractall(cls.base, filter="data")

    def evidence(self, scenario):
        base = self.base / scenario
        record = json.loads((base / "result.json").read_bytes())
        roots = {role: base / role / role for role in guest_roles(record["guest_count"])}
        return record, roots

    def test_replays_three_and_four_guest_runs(self):
        for scenario, count, leaves in (("three", 3, 3), ("four", 4, 6)):
            with self.subTest(scenario=scenario), TemporaryDirectory() as scratch:
                record, roots = self.evidence(scenario)
                self.assertEqual(len(roots), count)
                self.assertEqual(record["planned_leaves"], leaves)
                guests = {role: json.loads((root / "guest.json").read_bytes()) for role, root in roots.items()}
                multivm.check_topology(guests, record)
                self.assertEqual(multivm.read_timings(roots, leaves), record["timings"])
                replay = replay_many(roots, leaves, self.executor, Path(scratch), solve_budget=record["solve_budget"])
                self.assertEqual(replay, {key: record[key] for key in replay})

    def test_replays_whole_task_exact_limits_and_rejects_changed_root_question(self):
        record, roots = self.evidence("exact")
        caps = {name: record["root_limits"][name] for name in ("gas_limit", "output_limit")}
        self.assertEqual(caps, dict(gas_limit=9425, output_limit=144))
        with TemporaryDirectory() as scratch:
            replay = replay_many(roots, 3, self.executor, Path(scratch), solve_budget=record["solve_budget"],
                                 root_caps=caps, account=True)
        self.assertEqual(replay, {key: record[key] for key in replay})
        # A higher root gas limit leaves leaf questions and result bytes unchanged.
        # Replaying the frozen root question still catches the cap change.
        with TemporaryDirectory() as scratch, self.assertRaisesRegex(codec.CodecError, "root-question.cbor"):
            replay_many(roots, 3, self.executor, Path(scratch), solve_budget=record["solve_budget"],
                        root_caps=dict(caps, gas_limit=9426), account=True)

    def test_copied_modified_frames_fail_even_when_both_guests_agree(self):
        record, roots = self.evidence("three")
        paths = [roots[role] / "SOLVE-1-response.cbor" for role in ("A", "B")]
        original = paths[0].read_bytes()
        changed = codec.decode(original)
        answer = codec.decode(changed["answer"]["outcome"])
        answer["gas_used"] -= 1
        changed["answer"]["outcome"] = codec.encode(answer)
        try:
            for path in paths:
                path.write_bytes(codec.encode(changed))
            with TemporaryDirectory() as scratch, self.assertRaisesRegex(codec.CodecError, "differs from replay"):
                replay_many(roots, 3, self.executor, Path(scratch), solve_budget=record["solve_budget"])
        finally:
            for path in paths:
                path.write_bytes(original)
