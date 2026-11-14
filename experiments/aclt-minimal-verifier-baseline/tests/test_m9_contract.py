# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for frozen-question reuse and trusted host coordination."""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline import PROBE, QUESTION_TAG
from coordination import Coordinator, CoordinationError, conflicting_intent
from general_job import Job, Journal, c, digest, handle
from general_vm import DEFAULT_BUDGET, fixture, run, source_journal
from test_baseline import build_executor

ROLES = ("A", "B", "C")


def change(job, *, nonce, tasks=None, caps=None):
    declaration, plan = c.decode(job.declaration), c.decode(job.plan)
    if tasks is not None:
        declaration["tasks"] = tasks
    if caps is not None:
        plan["caps"] = caps
    declaration, plan = c.encode(declaration), c.encode(plan)
    execution = c.encode(dict(declaration_id=digest("Declaration", declaration),
                              plan_id=digest("Plan", plan), nonce=nonce, budget=job.budget))
    return Job(declaration, plan, execution, job.artifacts)


class ReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        executor_dir = TemporaryDirectory()
        cls.addClassCleanup(executor_dir.cleanup)
        cls.executor = Path(executor_dir.name) / "executor"
        build_executor(PROBE / "src/independent_executor.rs", cls.executor)

    def setUp(self):
        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.job = fixture(bytes(32), DEFAULT_BUDGET)
        self.tasks = [{"literal": 2}, {"literal": 2}, {"double": 0}, {"literal": 11}]
        self.old = change(self.job, nonce=b"a" * 32, tasks=self.tasks)
        original, _ = run(self.old, ROLES, self.root / "source.cbor",
                          lambda role, raw: handle(raw, self.executor), order=(0, 1, 2, 3))
        self.source = source_journal(self.old, original.path, self.executor)
        self.target = change(fixture(bytes(32), DEFAULT_BUDGET, flat=True),
                             nonce=b"b" * 32, tasks=self.tasks)

    def reuse(self, journal, slot, source_slot, /, **overrides):
        question = journal.job.question(slot, journal.accepted)["question"]
        fields = dict(slot=slot, source_execution=self.old.execution_id, source_slot=source_slot,
                      source_evidence=self.source.accepted[source_slot]["evidence"],
                      question_id=c.domain_hash(QUESTION_TAG, question))
        journal.add("REUSE", **(fields | overrides))

    def test_plan_change_reuses_another_slot_and_dependency(self):
        target, status = run(self.target, ROLES, self.root / "new.cbor",
                             lambda *_: self.fail("reused slot dispatched work"),
                             order=(2, 0, 1, 3), source=self.source, reuse={0: 1, 1: 0, 2: 2, 3: 3})
        self.assertEqual(status, "PUBLISHED")
        self.assertEqual(self.target.declaration_id, self.old.declaration_id)
        self.assertNotEqual(self.target.plan_id, self.old.plan_id)
        self.assertEqual(target.final["output"], [2, 2, 4, 11])
        self.assertEqual(target.charged, 0)
        self.assertEqual(self.source.charged, sum(self.old.caps))
        self.assertFalse(target.attempts)
        self.assertNotEqual(target.accepted[0]["evidence"], self.source.accepted[1]["evidence"])
        self.assertEqual(Journal(self.target, target.path, target.events, source=self.source).final, target.final)

    def test_changed_cap_and_dependency_input_reject(self):
        capped = change(self.target, nonce=b"c" * 32, caps=[8233, *self.target.caps[1:]])
        journal = Journal(capped, self.root / "cap.cbor", source=self.source)
        journal.add("START", execution=capped.execution)
        with self.assertRaisesRegex(ValueError, "frozen question mismatch"):
            self.reuse(journal, 0, 0)

        changed = change(self.target, nonce=b"d" * 32, tasks=[{"literal": 3}, *self.tasks[1:]])
        journal, _ = run(changed, ROLES, self.root / "dep.cbor",
                         lambda role, raw: handle(raw, self.executor), order=(0, 1, 2, 3),
                         checkpoint=1, source=self.source)
        with self.assertRaisesRegex(ValueError, "frozen question mismatch"):
            self.reuse(journal, 2, 2)

    def test_missing_misbound_and_duplicate_acceptance(self):
        journal = Journal(self.target, self.root / "reject.cbor", source=self.source)
        journal.add("START", execution=self.target.execution)
        with self.assertRaisesRegex(ValueError, "wrong source execution"):
            self.reuse(journal, 0, 0, source_execution=b"x" * 32)
        with self.assertRaisesRegex(ValueError, "missing or wrong source acceptance"):
            self.reuse(journal, 0, 0, source_slot=99)
        with self.assertRaisesRegex(ValueError, "missing or wrong source acceptance"):
            self.reuse(journal, 0, 0, source_evidence=b"x" * 32)
        self.reuse(journal, 0, 0)
        self.reuse(journal, 0, 0)
        self.assertEqual(len(journal.events), 2)
        with self.assertRaisesRegex(ValueError, "cannot accept"):
            self.reuse(journal, 0, 1)


class CoordinationTests(unittest.TestCase):
    def test_live_owner_reassignment_stale_write_and_overlap(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            job = fixture(bytes(32), DEFAULT_BUDGET)
            guard = Coordinator(job, root / "journal.cbor", root / "trace")
            code = "import signal; signal.pause()"
            with subprocess.Popen([sys.executable, "-c", code]) as old, \
                 subprocess.Popen([sys.executable, "-c", code]) as new:
                try:
                    self.assertEqual(guard.assign(old), 0)
                    start = {"epoch": 0, "event": "START", "fields": {"execution": job.execution}}
                    guard.begin(old, start)
                    guard.commit(old)
                    with self.assertRaisesRegex(CoordinationError, "still running"):
                        guard.assign(new)
                    old.terminate()
                    old.wait(5)
                    self.assertEqual(guard.assign(new), 1)
                    with self.assertRaisesRegex(CoordinationError, "not current"):
                        guard.begin(old, start)
                    self.assertFalse(guard.paused)
                    path_bytes = guard.journal.path.read_bytes()
                    guard.begin(new, {"epoch": 1, "event": "PUBLISH", "fields": {}})
                    conflicting_intent(guard)
                    with self.assertRaisesRegex(CoordinationError, "paused"):
                        guard.commit(new)
                    with self.assertRaisesRegex(CoordinationError, "paused"):
                        guard.begin(new, {"epoch": 1, "event": "PUBLISH", "fields": {}})
                    self.assertEqual(guard.journal.path.read_bytes(), path_bytes)
                    self.assertIsNone(guard.journal.final)
                finally:
                    for process in (old, new):
                        if process.poll() is None:
                            process.terminate()
