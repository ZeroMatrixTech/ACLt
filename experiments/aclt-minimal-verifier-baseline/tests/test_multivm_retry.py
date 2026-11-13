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


class RetryEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        work = TemporaryDirectory(prefix="aclt-nvm-retry-")
        cls.addClassCleanup(work.cleanup)
        cls.base = Path(work.name)
        cls.executor = cls.base / "executor"
        build_executor(multivm.ROOT / multivm.EXECUTOR_SOURCE, cls.executor)
        archive = multivm.ROOT / "docs/testing/public-evidence/MULTIVM-N-RETRY-public-evidence.tar.gz"
        with tarfile.open(archive, "r:gz") as bundle:
            bundle.extractall(cls.base, filter="data")

    def replay(self, mode, budget, *, recovered, alter=None):
        directory = self.base / f"{mode}-{budget}"
        record = json.loads((directory / ("result.json" if recovered else "failure.json")).read_bytes())
        roots = {role: directory / role / role for role in "ABC"}
        logs = {role: (directory / f"{role}-serial.log").read_text() for role in roots}
        ledger_path = roots["A"] / "solve-attempts.json"
        original = ledger_path.read_bytes()
        self.assertEqual(json.loads(original), record["solve_accounting"])
        try:
            if alter is not None:
                ledger = json.loads(original)
                alter(ledger)
                ledger_path.write_text(json.dumps(ledger))
            with TemporaryDirectory() as scratch:
                result = multivm.check_interruption(roots, logs, self.executor, Path(scratch), 3, budget,
                                                    mode, "SOLVE-1", retry_solve=True,
                                                    recovered=recovered, account=True)
        finally:
            if alter is not None:
                ledger_path.write_bytes(original)
        self.assertEqual(result, {key: record[key] for key in result})
        return record

    def test_pre_execution_exit_and_lost_reply_have_same_charge(self):
        for mode in ("worker-exit", "drop-reply"):
            with self.subTest(mode=mode):
                record = self.replay(mode, 34768, recovered=True)
                self.assertEqual(record["leaf_solve_gas_used"], 26049)
                self.assertEqual(record["output_sha256"],
                                 "1216b67718f016f305a97cc465db4f34fb268c348fde0f1e75befbf49a347d56")
                ledger = record["solve_accounting"]
                self.assertEqual(ledger["charged_gas"], 34768)
                self.assertEqual(ledger["attempts"][1],
                                 dict(leaf_index=1, guest="B", attempt=1, gas_limit=8719,
                                      status="NO_REPLY", measured_gas=None, charged_gas=8719))
                self.assertEqual(ledger["attempts"][2],
                                 dict(leaf_index=1, guest="A", attempt=2, gas_limit=8719,
                                      status="ANSWER", measured_gas=8719, charged_gas=8719))

    def test_budget_one_short_stops_before_retry(self):
        record = self.replay("drop-reply", 34767, recovered=False)
        self.assertIs(record["output_published"], False)
        self.assertEqual(record["solve_accounting"]["charged_gas"], 17438)
        self.assertEqual(len(record["solve_accounting"]["attempts"]), 2)

    def test_replay_rejects_credit_for_unanswered_attempt(self):
        def undercharge(ledger):
            ledger["attempts"][1]["charged_gas"] = 0

        with self.assertRaisesRegex(codec.CodecError, "solve-attempts.json differs"):
            self.replay("drop-reply", 34768, recovered=True, alter=undercharge)
