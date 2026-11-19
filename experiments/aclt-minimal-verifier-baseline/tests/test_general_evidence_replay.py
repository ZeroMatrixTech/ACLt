# SPDX-License-Identifier: Apache-2.0
"""Replay the retained general-job and capacity-sort evidence under current code.

These packages were previously replayed by hand.  Keeping the procedure here means
any request or journal format change that breaks an old retained run fails the
local suite instead of slipping through as an unverified claim."""
from pathlib import Path
import tarfile
from tempfile import TemporaryDirectory
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline import PROBE, ROOT
import general_vm
import sort_contract
from test_baseline import build_executor
from tools.verification_profile import codec as c

EVIDENCE = ROOT / "docs/testing/public-evidence"
PACKAGES = ("MULTIVM-GENERAL-JOB", "MULTIVM-CONTRACT-CLOSURE", "MULTIVM-SORT-CONTRACT")


def roots_of(base, roles="ABC"):
    return {role: Path(base) / role / role for role in roles}


def general_job(base, six=False):
    """Rebuild the job from its frozen execution and plan bytes."""
    execution = c.decode((Path(base) / "A/A/execution.cbor").read_bytes())
    plan = c.decode((Path(base) / "A/A/plan.cbor").read_bytes())
    flat = plan["tree"] == list(range(len(plan["caps"])))
    return general_vm.fixture(execution["nonce"], execution["budget"], flat=flat, six=six)


class GeneralEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        work = TemporaryDirectory()
        cls.addClassCleanup(work.cleanup)
        cls.base = Path(work.name)
        cls.executor = cls.base / "executor"
        build_executor(PROBE / "src/independent_executor.rs", cls.executor)
        for name in PACKAGES:
            with tarfile.open(EVIDENCE / f"{name}-public-evidence.tar.gz") as archive:
                archive.extractall(cls.base / name, filter="data")

    def test_general_job_five_scenarios_still_replay(self):
        package = self.base / "MULTIVM-GENERAL-JOB"
        expected = {"tree": 32938, "flat": 32938}
        for name, charged in expected.items():
            with self.subTest(scenario=name):
                journal = general_vm.replay(general_job(package / name), roots_of(package / name),
                                            self.executor)
                self.assertTrue(journal.final is not None)
                self.assertEqual(journal.charged, charged)
                self.assertEqual(sorted(journal.accepted), [0, 1, 2, 3])
        # The drop scenarios keep the generated reply at the worker, like no_reply.
        for name, before, total in (("one", 16464, 41170), ("two", 24696, 41170)):
            with self.subTest(scenario=name):
                job = general_job(package / name / "after")
                first = general_vm.replay(job, roots_of(package / name / "before"), self.executor,
                                          suppressed_reply=True)
                second = general_vm.replay(job, roots_of(package / name / "after"), self.executor,
                                           first.events, suppressed_reply=True)
                self.assertTrue(second.final is not None)
                self.assertEqual((first.charged, second.charged), (before, total))
        with self.subTest(scenario="budget"):
            journal = general_vm.replay(general_job(package / "budget"),
                                        roots_of(package / "budget"), self.executor,
                                        suppressed_reply=True)
            self.assertIsNone(journal.final)
            self.assertEqual(journal.charged, 8232)

    def test_contract_closure_phases_still_replay(self):
        package = self.base / "MULTIVM-CONTRACT-CLOSURE"
        source = general_vm.replay(general_job(package / "reuse/source"),
                                   roots_of(package / "reuse/source"), self.executor)
        retained = general_vm.source_journal(general_job(package / "reuse/source"),
                                             source.path, self.executor)
        self.assertTrue(retained.final is not None)
        reuse = general_vm.replay(general_job(package / "reuse"), roots_of(package / "reuse"),
                                  self.executor, source=retained)
        self.assertTrue(reuse.final is not None)
        self.assertEqual((reuse.charged, sorted(reuse.accepted)), (0, [0, 1, 2, 3]))
        for name, charged in (("handoff", 32938), ("overlap", 8232)):
            with self.subTest(scenario=name):
                job = general_job(package / name / "after")
                first = general_vm.replay(job, roots_of(package / name / "before"), self.executor)
                second = general_vm.replay(job, roots_of(package / name / "after"), self.executor,
                                           first.events)
                self.assertEqual((first.charged, second.charged), (8232, charged))
                if name == "handoff":
                    self.assertTrue(second.final is not None)
                else:
                    self.assertIsNone(second.final)
                    self.assertEqual(second.reserved, 0)
                    self.assertEqual(len(second.events), 5)

    def test_capacity_sort_two_phases_still_replay(self):
        package = self.base / "MULTIVM-SORT-CONTRACT"
        nonce = c.decode((package / "before/A/A/execution.cbor").read_bytes())["nonce"]
        job = sort_contract.SortJob(nonce)

        def check(raw, response, root, unanswered):
            return sort_contract.replay_response(job, raw, response, root, unanswered)

        before = general_vm.replay(job, roots_of(package / "before"), self.executor,
                                   check_response=check, suppressed_reply=True)
        after = general_vm.replay(job, roots_of(package / "after"), self.executor,
                                  before.events, check_response=check, suppressed_reply=True)
        self.assertTrue(after.final is not None)
        placements = sort_contract.PLACEMENT
        images = {}
        for phase, journal in (("before", before), ("after", after)):
            for slot in journal.accepted:
                role = placements[slot][0]
                images[(phase, role)] = package / phase / role / role / "delivery.img"
        sort_contract.verify_retained(
            job, after, lambda request: images[
                ("before" if request["epoch"] == 0 else "after",
                 placements[request["slot"]][0])])


if __name__ == "__main__":
    unittest.main()
