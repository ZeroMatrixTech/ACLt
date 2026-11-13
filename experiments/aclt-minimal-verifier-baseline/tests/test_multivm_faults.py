# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import multivm
from multivm_job import fault_target, guest_roles
from test_baseline import build_executor
from tools.verification_profile import codec


class InterruptionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        workspace = TemporaryDirectory(prefix="aclt-nvm-interruption-")
        cls.addClassCleanup(workspace.cleanup)
        cls.base = Path(workspace.name)
        cls.executor = cls.base / "executor"
        build_executor(multivm.ROOT / multivm.EXECUTOR_SOURCE, cls.executor)
        archive = multivm.ROOT / "docs/testing/public-evidence/MULTIVM-N-FAULTS-public-evidence.tar.gz"
        with tarfile.open(archive, "r:gz") as bundle:
            bundle.extractall(cls.base, filter="data")

    def replay(self, mode, operation, alter=None):
        base = self.base / mode
        record = json.loads((base / "failure.json").read_bytes())
        roles = guest_roles(record["guest_count"])
        roots = {role: base / role / role for role in roles}
        logs = {role: (base / f"{role}-serial.log").read_text(errors="replace") for role in roles}
        if alter is not None:
            alter(roots, logs)
        with TemporaryDirectory() as scratch:
            failure = multivm.check_interruption(roots, logs, self.executor, Path(scratch),
                                                 record["planned_leaves"], record["solve_budget"], mode, operation)
        self.assertEqual(failure, {key: record[key] for key in failure})
        return failure

    def test_worker_exit_and_disconnect_preserve_only_the_accepted_prefix(self):
        for mode, operation, role in (("worker-exit", "SOLVE-1", "B"), ("disconnect", "VERIFY-1", "C")):
            with self.subTest(mode=mode):
                failure = self.replay(mode, operation)
                self.assertEqual(failure["guest"], role)
                self.assertEqual((failure["start"], failure["stop"]), (2, 4))
                self.assertEqual(failure["accepted_leaf_indices"], [0])
                self.assertEqual(failure["unaccepted_leaf_indices"], [1, 2])
                self.assertIs(failure["output_published"], False)

    def test_wrong_fault_marker_does_not_count_as_evidence(self):
        def alter(roots, logs):
            logs["B"] = logs["B"].replace("mode=worker-exit", "mode=disconnect")

        with self.assertRaisesRegex(multivm.RunError, "failure marker"):
            self.replay("worker-exit", "SOLVE-1", alter)

    def test_replay_rejects_a_partial_result_marked_for_publication(self):
        def alter(roots, logs):
            path = roots["A"] / "merged-output.bin"
            path.write_bytes(b"partial result")
            self.addCleanup(path.unlink)

        with self.assertRaisesRegex(codec.CodecError, "published merged-output"):
            self.replay("worker-exit", "SOLVE-1", alter)

    def test_missing_request_is_not_a_replayable_interruption(self):
        def alter(roots, logs):
            for role in ("A", "B"):
                path = roots[role] / "SOLVE-1-request.cbor"
                self.addCleanup(path.write_bytes, path.read_bytes())
                path.unlink()

        with self.assertRaisesRegex(codec.CodecError, "cannot read retained frame"):
            self.replay("worker-exit", "SOLVE-1", alter)

    def test_fault_target_must_be_remote_and_planned(self):
        for target in ("SOLVE-0", "VERIFY-3", "VERIFY-01"):
            with self.subTest(target=target), self.assertRaises(ValueError):
                fault_target(guest_roles(3), 3, target)
