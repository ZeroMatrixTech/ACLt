# SPDX-License-Identifier: Apache-2.0
"""C1 evidence checker: the recorded runs pass, and missing or misbound records fail.

The checker must require real execution records, not only frame re-derivation: a
deleted, orphaned or misbound begin/end record has to fail the run.
"""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline import PROBE, ROOT
import general_vm
from test_baseline import build_executor
from tools.verification_profile import codec as c

ARCHIVE = ROOT / "docs/testing/public-evidence/C1-RESTART-RESEND-public-evidence.tar.gz"
ROLES = ("A", "B", "C", "D")


def job_for(base):
    execution = c.decode((Path(base) / "A/A/execution.cbor").read_bytes())
    plan = c.decode((Path(base) / "A/A/plan.cbor").read_bytes())
    flat = plan["tree"] == list(range(len(plan["caps"])))
    return general_vm.fixture(execution["nonce"], execution["budget"], flat=flat)


def roots_of(base):
    base = Path(base)
    return {role: base / role / role for role in ROLES
            if (base / role / role).is_dir()}


def workers_of(base):
    return {role: root for role, root in roots_of(base).items() if role != "A"}


class RecordedRunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        work = TemporaryDirectory()
        cls.addClassCleanup(work.cleanup)
        cls.work = Path(work.name)
        cls.executor = cls.work / "executor"
        build_executor(PROBE / "src/independent_executor.rs", cls.executor)
        with tarfile.open(ARCHIVE) as archive:
            archive.extractall(cls.work / "evidence", filter="data")
        cls.root = cls.work / "evidence/C1-RESTART-RESEND"

    def copy(self, scenario):
        temporary = TemporaryDirectory(dir=self.work)
        self.addCleanup(temporary.cleanup)
        target = Path(temporary.name) / scenario
        shutil.copytree(self.root / scenario, target)
        return target

    def replay(self, base, scenario):
        base = Path(base)
        if scenario == "stale":
            before, after = base / "before", base / "after"
            job = job_for(after)
            first = general_vm.replay(job, roots_of(before), self.executor)
            return general_vm.replay(job, roots_of(after), self.executor, first.events), after
        job = job_for(base)
        return general_vm.replay(job, roots_of(base), self.executor,
                                  suppressed_reply=True), base

    def check(self, base, scenario):
        journal, phase = self.replay(base, scenario)
        return general_vm.check_restart_resend(roots_of(phase), journal, self.executor,
                                               scenario=scenario)

    def test_recorded_scenarios_pass_and_report_split_observations(self):
        expected = {"restart": (5, 4), "duplicate": (5, 4), "stale": (3, 3)}
        for scenario, (solves, verifies) in expected.items():
            with self.subTest(scenario=scenario):
                summary = self.check(self.root / scenario, scenario)
                self.assertEqual(summary["executions"], {"SOLVE": solves, "VERIFY": verifies})
                self.assertEqual(summary["scenario"], scenario)
                frames = summary["frames"]
                self.assertTrue(frames["retained"]["coordinator_requests"]["SOLVE"]["count"])
                self.assertEqual(frames["worker_sent"]["VERIFY"]["count"], verifies)
                self.assertTrue(frames["coordinator_sent"]["STOP"]["count"])

    def test_missing_verify_records_fail(self):
        for mutate in ("all", "one"):
            with self.subTest(mutation=mutate):
                base = self.copy("restart")
                for root in workers_of(base).values():
                    path = root / "executions.jsonl"
                    rows = [json.loads(line) for line in path.read_text().splitlines() if line]
                    keep = []
                    removed = False
                    for row in rows:
                        if row["action"] != "VERIFY":
                            keep.append(row)
                            continue
                        if mutate == "all":
                            continue
                        if not removed:
                            removed = True
                            continue
                        keep.append(row)
                    path.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                             for row in keep))
                with self.assertRaisesRegex(c.CodecError, "execution record|do not pair"):
                    self.check(base, "restart")

    def test_misbound_verify_completion_fails(self):
        base = self.copy("restart")
        changed = False
        for root in workers_of(base).values():
            path = root / "executions.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines() if line]
            for row in rows:
                if (not changed and row["event"] == "execute-end"
                        and row["action"] == "VERIFY"):
                    row["response_sha256"] = hashlib.sha256(b"other").hexdigest()
                    changed = True
            path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        self.assertTrue(changed)
        with self.assertRaisesRegex(c.CodecError, "completion record"):
            self.check(base, "restart")

    def test_orphan_execution_record_fails(self):
        base = self.copy("restart")
        root = base / "C/C"
        path = root / "executions.jsonl"
        begin = dict(event="execute-begin", boot="00" * 32, execution_id="11" * 32,
                     slot=9, attempt=1, action="SOLVE", request_sha256="22" * 32,
                     request_bytes=1)
        end = dict(begin, event="execute-end", response_sha256="33" * 32, response_bytes=1)
        with path.open("a") as stream:
            stream.write(json.dumps(begin, sort_keys=True) + "\n")
            stream.write(json.dumps(end, sort_keys=True) + "\n")
        with self.assertRaisesRegex(c.CodecError, "execution records do not match"):
            self.check(base, "restart")


    def test_wrong_execution_id_fails(self):
        base = self.copy("restart")
        changed = False
        for root in workers_of(base).values():
            path = root / "executions.jsonl"
            rows = [json.loads(line) for line in path.read_text().splitlines() if line]
            for row in rows:
                if row["action"] == "VERIFY":
                    row["execution_id"] = "44" * 32
                    changed = True
            path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        self.assertTrue(changed)
        with self.assertRaisesRegex(c.CodecError, "no unique execution record"):
            self.check(base, "restart")

    def test_records_moved_to_another_role_fail(self):
        base = self.copy("restart")
        source = base / "C/C" / "executions.jsonl"
        target = base / "B/B" / "executions.jsonl"
        rows = [json.loads(line) for line in source.read_text().splitlines() if line]
        moved = [row for row in rows if row["action"] == "VERIFY"]
        self.assertTrue(moved)
        source.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows
                                 if row["action"] != "VERIFY"))
        with target.open("a") as stream:
            for row in moved:
                stream.write(json.dumps(row, sort_keys=True) + "\n")
        with self.assertRaisesRegex(c.CodecError, "no unique execution record"):
            self.check(base, "restart")

    def test_orphan_completion_record_fails(self):
        base = self.copy("restart")
        path = base / "C/C" / "executions.jsonl"
        end = dict(event="execute-end", boot="00" * 32, execution_id="55" * 32,
                   slot=9, attempt=1, action="VERIFY", request_sha256="66" * 32,
                   request_bytes=1, response_sha256="77" * 32, response_bytes=1)
        with path.open("a") as stream:
            stream.write(json.dumps(end, sort_keys=True) + "\n")
        with self.assertRaisesRegex(c.CodecError, "do not pair one to one"):
            self.check(base, "restart")


if __name__ == "__main__":
    unittest.main()
