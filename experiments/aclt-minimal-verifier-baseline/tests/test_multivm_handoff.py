# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import multivm
from test_baseline import build_executor
from tools.verification_profile import codec


class HandoffEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        work = TemporaryDirectory(prefix="aclt-handoff-test-")
        cls.addClassCleanup(work.cleanup)
        cls.directory = Path(work.name)
        cls.executor = cls.directory / "executor"
        build_executor(multivm.ROOT / multivm.EXECUTOR_SOURCE, cls.executor)
        evidence = multivm.ROOT / "docs/testing/public-evidence/MULTIVM-HANDOFF-public-evidence.tar.gz"
        with tarfile.open(evidence, "r:gz") as archive:
            archive.extractall(cls.directory, filter="data")
        cls.record = json.loads((cls.directory / "result.json").read_bytes())
        cls.before, cls.after = ({role: cls.directory / phase / role / role for role in "ABC"}
                                 for phase in ("before", "after"))

    def replay(self):
        caps = {name: self.record["root_limits"][name] for name in ("gas_limit", "output_limit")}
        with TemporaryDirectory() as scratch:
            return multivm.replay_handoff(self.before, self.after, self.executor, self.record["solve_budget"],
                                          caps, Path(scratch))

    def test_resumes_same_job_and_charges_each_leaf_once(self):
        result = self.replay()
        self.assertEqual(result, {key: self.record[key] for key in result})
        ledger = self.record["solve_accounting"]
        self.assertEqual(ledger["charged_gas"], 26049)
        self.assertEqual([(row["leaf_index"], row["attempt"]) for row in ledger["attempts"]],
                         [(0, 1), (1, 1), (2, 1)])

    def test_rejects_checkpoint_with_unaccounted_dispatch(self):
        frame = self.before["A"] / "SOLVE-1-request.cbor"
        frame.write_bytes(b"unexpected dispatch")
        try:
            with self.assertRaisesRegex(codec.CodecError, "unexpected dispatches"):
                self.replay()
        finally:
            frame.unlink()

    def test_rejects_checkpoint_with_reduced_gas_charge(self):
        path = self.before["A"] / "solve-attempts.json"
        original = path.read_bytes()
        ledger = json.loads(original)
        ledger["charged_gas"] -= 1
        path.write_text(json.dumps(ledger))
        try:
            with self.assertRaisesRegex(codec.CodecError, "handoff ledger differs"):
                self.replay()
        finally:
            path.write_bytes(original)
