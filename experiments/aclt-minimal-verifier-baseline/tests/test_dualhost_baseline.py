# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import shutil
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dualhost import PROBE, fixture, replay_baseline
from lan import handle_request, operations, run_job
from test_baseline import build_executor
from tools.formal_migration.s2_transport import MAX
from tools.verification_profile import codec


class InMemoryPeer:
    """Implement the same byte exchange without allocating network resources."""

    def __init__(self, schedule, executor, root):
        self.schedule = iter(schedule)
        self.executor = executor
        self.root = root
        self.reply = b""
        self.plan = None

    def sendall(self, frame):
        action, index, label = next(self.schedule)
        raw = frame[4:]
        if int.from_bytes(frame[:4], "big") != len(raw) or len(raw) > MAX:
            raise ValueError("bad fixture frame")
        self.plan, reply = handle_request(raw, action, self.executor, prior_plan=self.plan, leaf_index=index)
        (self.root / f"{label}-request.cbor").write_bytes(raw)
        (self.root / f"{label}-response.cbor").write_bytes(reply)
        self.reply = len(reply).to_bytes(4, "big") + reply

    def recv(self, size):
        chunk, self.reply = self.reply[:size], self.reply[size:]
        return chunk


class BaselineAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.executor = Path(temporary.name) / "executor"
        build_executor(PROBE / "src/independent_executor.rs", cls.executor)

    def run_fixture(self, root, *, reverse=False):
        for role in ("A", "B"):
            (root / role).mkdir(parents=True)
        schedule = operations(2)
        if reverse:
            schedule.reverse()
        connection = InMemoryPeer(schedule, self.executor, root / "B")
        run_job(connection, *fixture(), self.executor, root / "A", reverse_schedule=reverse)

    def test_actual_order_and_replayed_negative_inputs(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            outputs = []
            for reverse, order in ((False, [2, 0]), (True, [0, 2])):
                job = root / str(reverse)
                self.run_fixture(job, reverse=reverse)
                result = replay_baseline(job, self.executor, job / "replay", reverse_schedule=reverse)
                self.assertEqual(result["accepted_order"], order)
                self.assertEqual(result["negatives"]["missing"]["reason"], "missing slice position")
                self.assertEqual(result["negatives"]["misbound"]["reason"], "slice question mismatch")
                for case in result["negatives"]:
                    self.assertEqual(list((job / "replay" / case).glob("*.bin")), [])
                outputs.append(result["output_sha256"])
            self.assertEqual(outputs[0], outputs[1])

    def test_replay_rejects_wrong_order_and_copied_modified_frame(self):
        with TemporaryDirectory() as temp:
            job = Path(temp)
            self.run_fixture(job)
            with self.assertRaisesRegex(codec.CodecError, "recorded acceptance order differs"):
                replay_baseline(job, self.executor, job / "order", reverse_schedule=True)
            frame = job / "A" / "SOLVE-request.cbor"
            request = codec.decode(frame.read_bytes())
            request["data"] = b"incorrect"
            frame.write_bytes(codec.encode(request))
            shutil.copyfile(frame, job / "B" / frame.name)
            with self.assertRaisesRegex(codec.CodecError, "differs from frozen plan"):
                replay_baseline(job, self.executor, job / "frame")
