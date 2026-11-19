# SPDX-License-Identifier: Apache-2.0
"""C1: a restarted serving boot refuses every request dispatched before it.

The tests exercise the same admission, execution and refusal code as the guest
worker.  Execution counts come from the durable records written around the actual
call, never from the coordinator's accounting.
"""
import hashlib
import os
from pathlib import Path
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from baseline import PROBE
from general_job import Journal, c
from general_vm import (
    DEFAULT_BUDGET, ServingBoot, coordinator_only, fixture, read_lines, retry_after, run,
)
from test_baseline import build_executor
from tools.formal_migration.s2_transport import receive, send

ROLES = ("A", "B", "C", "D")
WORKERS = ("B", "C", "D")


class MemorySession:
    """One in-process dispatch: activation then request, like the guest transport."""

    def __init__(self, worker, activation, executor, *, drop=False):
        self.worker = worker
        self.activation = activation
        self.executor = executor
        self.drop = drop

    def request(self, raw):
        request = c.decode(raw)
        reason = self.worker.admit(request, self.activation)
        if reason is not None:
            self.worker.reject(reason, raw=raw, request=request, activation=self.activation)
            raise ConnectionError(reason)
        response = self.worker.execute(raw, self.executor)
        if self.drop:
            raise ConnectionError("simulated missing reply")
        return response

    def close(self):
        return None


class MemoryDispatch:
    """Dispatch object for local tests; one ServingBoot per worker role."""

    def __init__(self, workers, executor, *, drops=()):
        self.workers = workers
        self.executor = executor
        self.drops = set(drops)
        self.sequence = 0

    def open(self, role, epoch, *, slot, attempt, action):
        self.sequence += 1
        worker = self.workers[role]
        frame = c.encode(dict(action="BOOT", epoch=epoch, dispatch=self.sequence))
        reply, activation = worker.activate(frame)
        if reply is None:
            raise ConnectionError("activation refused")
        return worker.boot, MemorySession(worker, activation, self.executor,
                                          drop=(slot, attempt, action) in self.drops)


class ServedBootTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        work = TemporaryDirectory()
        cls.addClassCleanup(work.cleanup)
        cls.work = Path(work.name)
        cls.executor = cls.work / "executor"
        build_executor(PROBE / "src/independent_executor.rs", cls.executor)

    def setUp(self):
        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.job = fixture(bytes(32), DEFAULT_BUDGET)
        self.out = self.root / "serving"
        self.out.mkdir()
        self.worker = ServingBoot("C", self.out)
        self.request = Journal(self.job, self.root / "frame.cbor").frame(
            0, 1, "SOLVE", boot=self.worker.boot)

    def boot_frame(self, epoch, dispatch=1):
        return c.encode(dict(action="BOOT", epoch=epoch, dispatch=dispatch))

    def test_request_is_bound_to_the_boot_that_activated_it(self):
        reply, activation = self.worker.activate(self.boot_frame(0))
        self.assertEqual(activation, 0)
        self.assertEqual(c.decode(reply)["boot"], self.worker.boot)
        self.assertIsNone(self.worker.admit(c.decode(self.request), activation))
        response = self.worker.execute(self.request, self.executor)
        self.assertTrue(response)
        begins = [row for row in read_lines(self.out / "executions.jsonl")
                  if row["event"] == "execute-begin"]
        ends = [row for row in read_lines(self.out / "executions.jsonl")
                if row["event"] == "execute-end"]
        self.assertEqual(len(begins), len(ends))
        self.assertEqual(begins[0]["boot"], self.worker.boot.hex())

    def test_same_boot_repeat_is_refused_without_executing(self):
        self.worker.activate(self.boot_frame(0))
        reply, activation = self.worker.activate(self.boot_frame(0, dispatch=2))
        self.assertIsNone(self.worker.admit(c.decode(self.request), activation))
        self.worker.execute(self.request, self.executor)
        reply, activation = self.worker.activate(self.boot_frame(0, dispatch=3))
        self.assertEqual(self.worker.admit(c.decode(self.request), activation), "duplicate")
        self.worker.reject("duplicate", raw=self.request,
                           request=c.decode(self.request), activation=activation)
        refusals = read_lines(self.out / "rejections.jsonl")
        self.assertEqual([row["reason"] for row in refusals], ["duplicate"])
        begins = [row for row in read_lines(self.out / "executions.jsonl")
                  if row["event"] == "execute-begin"]
        self.assertEqual(len(begins), 1)

    def test_restarted_boot_refuses_an_old_request(self):
        self.worker.activate(self.boot_frame(0))
        self.worker.execute(self.request, self.executor)
        restarted = ServingBoot("C", self.out)
        self.assertNotEqual(restarted.boot, self.worker.boot)
        reply, activation = restarted.activate(self.boot_frame(0, dispatch=2))
        self.assertEqual(restarted.admit(c.decode(self.request), activation), "boot-mismatch")
        restarted.reject("boot-mismatch", raw=self.request,
                         request=c.decode(self.request), activation=activation)
        self.assertEqual([row["reason"] for row in read_lines(self.out / "rejections.jsonl")],
                         ["boot-mismatch"])
        self.assertEqual([row["boot"] for row in read_lines(self.out / "executions.jsonl")
                          if row["event"] == "execute-begin"], [self.worker.boot.hex()])
        self.assertEqual([row["boot"] for row in read_lines(self.out / "boots.jsonl")],
                         [self.worker.boot.hex(), restarted.boot.hex()])

    def test_bare_request_is_refused_and_the_server_stays_up(self):
        self.assertEqual(self.worker.admit(c.decode(self.request), None), "unactivated")
        self.worker.reject("unactivated", raw=self.request, request=c.decode(self.request))
        self.worker.activate(self.boot_frame(0))
        self.worker.execute(self.request, self.executor)
        self.assertEqual(len([row for row in read_lines(self.out / "executions.jsonl")
                              if row["event"] == "execute-begin"]), 1)

    def test_stale_epoch_activation_is_refused_after_a_current_one(self):
        self.worker.activate(self.boot_frame(1, dispatch=1))
        reply, reason = self.worker.activate(self.boot_frame(0, dispatch=2))
        self.assertIsNone(reply)
        self.assertEqual(reason, "stale-epoch")
        rows = read_lines(self.out / "activations.jsonl")
        self.assertEqual([(row["accepted"], row.get("reason")) for row in rows],
                         [(True, None), (False, "stale-epoch")])

    def test_epoch_mismatch_and_boot_mismatch_reasons(self):
        reply, activation = self.worker.activate(self.boot_frame(1))
        old = Journal(self.job, self.root / "old.cbor").frame(0, 1, "SOLVE",
                                                              boot=self.worker.boot)
        self.assertEqual(self.worker.admit(c.decode(old), activation), "epoch-mismatch")
        fresh = Journal(self.job, self.root / "fresh.cbor")
        fresh.epoch = 1
        self.assertEqual(self.worker.admit(c.decode(fresh.frame(
            0, 1, "SOLVE", boot=os.urandom(32))), activation), "boot-mismatch")


class DispatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        work = TemporaryDirectory()
        cls.addClassCleanup(work.cleanup)
        cls.work = Path(work.name)
        cls.executor = cls.work / "executor"
        build_executor(PROBE / "src/independent_executor.rs", cls.executor)

    def setUp(self):
        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.job = fixture(bytes(32), DEFAULT_BUDGET)
        self.journal = self.root / "journal.cbor"
        self.outs = {}
        for role in WORKERS:
            path = self.root / role
            path.mkdir()
            self.outs[role] = path
        self.workers = {role: ServingBoot(role, path) for role, path in self.outs.items()}
        self.placement = coordinator_only(WORKERS, len(self.job.tasks))
        self.retry = retry_after(WORKERS)

    def dispatch(self, *, drops=(), workers=None):
        return MemoryDispatch(workers or self.workers, self.executor, drops=drops)

    def play(self, *, drops=(), workers=None, order=(1, 0, 2, 3), previous=None):
        return run(self.job, ROLES, self.journal, order=order, previous=previous,
                   placement=self.placement, retry_worker=self.retry,
                   dispatch=self.dispatch(drops=drops, workers=workers))

    def test_drop_then_retry_executes_each_attempt_once(self):
        journal, status = self.play(drops={(1, 1, "SOLVE")})
        self.assertEqual(status, "PUBLISHED")
        self.assertEqual(journal.attempts[1, 1]["state"], "NO_REPLY")
        self.assertEqual(journal.attempts[1, 2]["state"], "ACCEPTED")
        self.assertEqual(journal.charged, DEFAULT_BUDGET)
        begins = [row for path in self.outs.values() for row in read_lines(path / "executions.jsonl")
                  if row["event"] == "execute-begin"]
        keys = [(row["execution_id"], row["slot"], row["attempt"], row["action"]) for row in begins]
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(len([key for key in keys if key[1:3] == (1, 1)]), 1)

    def test_restart_refuses_the_old_frame_and_the_retry_uses_a_new_boot(self):
        journal, status = self.play(drops={(1, 1, "SOLVE")})
        self.assertEqual(status, "PUBLISHED")
        reserve = next(event for event in journal.events
                       if event["kind"] == "RESERVE" and (event["slot"], event["attempt"]) == (1, 1))
        old_boot, raw = reserve["boot"], reserve["request"]
        retry = next(event for event in journal.events
                     if event["kind"] == "RESERVE" and (event["slot"], event["attempt"]) == (1, 2))
        self.assertNotEqual(retry["boot"], old_boot)
        restarted = ServingBoot(reserve["worker"], self.outs[reserve["worker"]])
        self.assertEqual(restarted.admit(c.decode(raw), None), "unactivated")
        restarted.reject("unactivated", raw=raw, request=c.decode(raw))
        reply, activation = restarted.activate(c.encode(dict(action="BOOT", epoch=0, dispatch=1)))
        self.assertEqual(restarted.admit(c.decode(raw), activation), "boot-mismatch")
        restarted.reject("boot-mismatch", raw=raw, request=c.decode(raw), activation=activation)
        self.assertEqual([row["reason"] for row in
                          read_lines(self.outs[reserve["worker"]] / "rejections.jsonl")],
                         ["unactivated", "boot-mismatch"])
        retried = [row for row in read_lines(self.outs[retry["worker"]] / "executions.jsonl")
                   if row["event"] == "execute-begin" and row["attempt"] == 2]
        self.assertEqual(len(retried), 1)

    def test_duplicate_resend_keeps_one_execution(self):
        journal, _ = self.play(drops={(1, 1, "SOLVE")})
        reserve = next(event for event in journal.events
                       if event["kind"] == "RESERVE" and (event["slot"], event["attempt"]) == (1, 1))
        raw, worker = reserve["request"], self.workers[reserve["worker"]]
        reply, activation = worker.activate(c.encode(dict(action="BOOT", epoch=0, dispatch=99)))
        self.assertEqual(worker.admit(c.decode(raw), activation), "duplicate")
        worker.reject("duplicate", raw=raw, request=c.decode(raw), activation=activation)
        self.assertEqual([row["reason"] for row in
                          read_lines(self.outs[reserve["worker"]] / "rejections.jsonl")],
                         ["duplicate"])

    def test_stale_epoch_frame_is_refused_after_the_handoff(self):
        checkpoint, status = run(self.job, ROLES, self.root / "before.cbor", order=(1, 0, 2, 3),
                                 checkpoint=1, placement=self.placement,
                                 retry_worker=self.retry,
                                 dispatch=self.dispatch(drops={(1, 1, "SOLVE")}))
        self.assertEqual(status, "CHECKPOINT")
        opened = [event for event in checkpoint.events
                  if event["kind"] in ("RESERVE", "ACCEPT")]
        self.assertTrue(opened)
        after_boots = {role: ServingBoot(role, path) for role, path in self.outs.items()}
        journal, status = run(self.job, ROLES, self.journal, order=(1, 0, 2, 3),
                              previous=self.root / "before.cbor", placement=self.placement,
                              retry_worker=self.retry,
                              dispatch=self.dispatch(workers=after_boots))
        self.assertEqual(status, "PUBLISHED")
        self.assertEqual(journal.epoch, 1)
        for event in opened:
            raw = event["request"]
            epoch = c.decode(raw)["epoch"]
            role = event["worker"] if event["kind"] == "RESERVE" else event["verifier"]
            worker = after_boots[role]
            self.assertEqual(worker.admit(c.decode(raw), None), "unactivated")
            reply, activation = worker.activate(c.encode(dict(action="BOOT", epoch=1,
                                                              dispatch=1000 + epoch)))
            self.assertEqual(worker.admit(c.decode(raw), activation), "epoch-mismatch")
            reply, reason = worker.activate(c.encode(dict(action="BOOT", epoch=epoch,
                                                           dispatch=2000 + epoch)))
            self.assertIsNone(reply)
            self.assertEqual(reason, "stale-epoch")
        digests = {hashlib.sha256(event["request"]).hexdigest() for event in opened}
        boots = {worker.boot.hex() for worker in after_boots.values()}
        after = [row for path in self.outs.values()
                 for row in read_lines(path / "executions.jsonl")
                 if row["event"] == "execute-begin" and row["boot"] in boots]
        self.assertEqual([row for row in after if row["request_sha256"] in digests], [])

    def test_dispatch_unavailable_stops_without_an_attempt(self):
        class Unreachable:
            def open(self, role, epoch, *, slot, attempt, action):
                raise ConnectionError("worker is down")

        journal, status = run(self.job, ROLES, self.journal, order=(1, 0, 2, 3),
                              placement=self.placement, retry_worker=self.retry,
                              dispatch=Unreachable())
        self.assertEqual(status, "DISPATCH_UNAVAILABLE")
        self.assertFalse(journal.attempts)
        self.assertEqual((journal.charged, journal.reserved), (0, 0))

    def test_partial_unreachability_never_uses_the_frozen_verifier_as_solver(self):
        # Slot 0 freezes (solver C, verifier B).  Only B answers the boot exchange, so
        # the fallback chain B -> D -> C reaches the verifier; it must be refused rather
        # than dispatched as the solver.
        class Partial:
            def __init__(self, workers, reachable):
                self.workers = workers
                self.reachable = reachable
                self.opened = []

            def open(self, role, epoch, *, slot, attempt, action):
                self.opened.append((role, slot, attempt, action))
                if role not in self.reachable:
                    raise ConnectionError("worker is down")
                worker = self.workers[role]
                frame = c.encode(dict(action="BOOT", epoch=epoch, dispatch=len(self.opened)))
                reply, activation = worker.activate(frame)
                if reply is None:
                    raise ConnectionError("activation refused")
                return worker.boot, MemorySession(worker, activation, self.executor)

        dispatch = Partial(self.workers, {"B"})
        journal, status = run(self.job, ROLES, self.root / "partial.cbor", order=(0,),
                              placement=(("C", "B"), ("C", "B"), ("C", "B"), ("C", "B")),
                              retry_worker=self.retry, dispatch=dispatch)
        self.assertEqual(status, "DISPATCH_UNAVAILABLE")
        self.assertFalse(journal.attempts)
        self.assertEqual((journal.charged, journal.reserved), (0, 0))
        self.assertNotIn(("B", 0, 1, "SOLVE"), dispatch.opened)
        self.assertEqual([event["kind"] for event in journal.events], ["START"])


class ServedProcessTests(unittest.TestCase):
    """A real serving process: a restart changes the boot and keeps the records."""

    @classmethod
    def setUpClass(cls):
        work = TemporaryDirectory()
        cls.addClassCleanup(work.cleanup)
        cls.work = Path(work.name)
        cls.executor = cls.work / "executor"
        build_executor(PROBE / "src/independent_executor.rs", cls.executor)

    def setUp(self):
        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.job = fixture(bytes(32), DEFAULT_BUDGET)
        self.out = self.root / "worker"
        self.out.mkdir()
        self.port = self.free_port()

    def free_port(self):
        listener = socket.socket()
        try:
            listener.bind(("127.0.0.1", 0))
            return listener.getsockname()[1]
        finally:
            listener.close()

    def start(self, *, restart=False, exit_on_fault=False):
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(PROBE.parents[1])
        return subprocess.Popen(
            [sys.executable, "-c",
             "import sys; from pathlib import Path; from general_vm import serve; "
             "serve('C', int(sys.argv[1]), Path(sys.argv[3]), Path(sys.argv[2]), "
             "drop_first_b=False, address='127.0.0.1', peer='127.0.0.1', "
             "restart=sys.argv[4] == '1', exit_on_fault=sys.argv[5] == '1')",
             str(self.port), str(self.out), str(self.executor),
             "1" if restart else "0", "1" if exit_on_fault else "0"],
            cwd=PROBE.parents[1] / "experiments/aclt-minimal-verifier-baseline",
            env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def exchange(self, frames):
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as connection:
            connection.settimeout(5)
            replies = []
            for raw in frames:
                send(connection, raw)
                replies.append(receive(connection))
            return replies

    def wait_ready(self):
        deadline = time.monotonic() + 15
        while True:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=5):
                    return
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

    def test_process_restart_changes_the_boot_and_refuses_the_old_frame(self):
        worker = self.start()
        self.addCleanup(lambda: worker.poll() is None and worker.kill())
        self.wait_ready()
        boot = c.decode(self.exchange([c.encode(dict(action="BOOT", epoch=0,
                                                     dispatch=1))])[0])["boot"]
        request = Journal(self.job, self.root / "frozen.cbor").frame(0, 1, "SOLVE", boot=boot)
        replies = self.exchange([c.encode(dict(action="BOOT", epoch=0, dispatch=2)), request])
        self.assertTrue(replies[-1])
        worker.terminate()
        worker.wait(10)
        restarted = self.start()
        self.addCleanup(lambda: restarted.poll() is None and restarted.kill())
        self.wait_ready()
        new_boot = c.decode(self.exchange([c.encode(dict(action="BOOT", epoch=0,
                                                         dispatch=2))])[0])["boot"]
        self.assertNotEqual(new_boot, boot)
        with self.assertRaises(OSError):
            self.exchange([c.encode(dict(action="BOOT", epoch=0, dispatch=3)), request])
        self.assertEqual([row["reason"] for row in read_lines(self.out / "rejections.jsonl")],
                         ["boot-mismatch"])
        self.assertEqual([row["boot"] for row in read_lines(self.out / "boots.jsonl")],
                         [boot.hex(), new_boot.hex()])
        self.assertEqual(len([row for row in read_lines(self.out / "executions.jsonl")
                              if row["event"] == "execute-begin"]), 1)
        restarted.terminate()
        restarted.wait(10)
        if worker.poll() is None:
            worker.terminate()
            worker.wait(10)

    def test_restart_control_is_an_unknown_action_when_not_enabled(self):
        worker = self.start()
        try:
            self.wait_ready()
            with self.assertRaises(OSError):
                self.exchange([c.encode({"action": "RESTART"})])
            self.assertIsNone(worker.poll())
            self.assertEqual([(row["kind"], row["reason"]) for row in
                              read_lines(self.out / "rejections.jsonl")],
                             [("RESTART", "unknown-action")])
            boot = c.decode(self.exchange([c.encode(dict(action="BOOT", epoch=0,
                                                         dispatch=1))])[0])["boot"]
            self.assertTrue(boot)
        finally:
            if worker.poll() is None:
                worker.terminate()
                worker.wait(10)

    def test_restart_control_exits_with_the_worker_status(self):
        worker = self.start(restart=True, exit_on_fault=True)
        try:
            self.wait_ready()
            with self.assertRaises(OSError):
                self.exchange([c.encode({"action": "RESTART"})])
            self.assertEqual(worker.wait(10), 7)
        finally:
            if worker.poll() is None:
                worker.terminate()
                worker.wait(10)
        self.assertEqual([row["event"] for row in read_lines(self.out / "restarts.jsonl")],
                         ["restart"])



class GuestDispatchTests(unittest.TestCase):
    """The guest-side dispatch and probe driver against a real serving process."""

    @classmethod
    def setUpClass(cls):
        work = TemporaryDirectory()
        cls.addClassCleanup(work.cleanup)
        cls.work = Path(work.name)
        cls.executor = cls.work / "executor"
        build_executor(PROBE / "src/independent_executor.rs", cls.executor)

    def setUp(self):
        root = TemporaryDirectory()
        self.addCleanup(root.cleanup)
        self.root = Path(root.name)
        self.job = fixture(bytes(32), DEFAULT_BUDGET)
        self.worker_out = self.root / "worker"
        self.coord_out = self.root / "A"
        self.worker_out.mkdir()
        self.coord_out.mkdir()
        self.port = self.free_port()
        self.worker = self.start()
        self.addCleanup(self.stop)
        self.wait_ready()

    def free_port(self):
        listener = socket.socket()
        try:
            listener.bind(("127.0.0.1", 0))
            return listener.getsockname()[1]
        finally:
            listener.close()

    def start(self):
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(PROBE.parents[1])
        return subprocess.Popen(
            [sys.executable, "-c",
             "import sys; from pathlib import Path; from general_vm import serve; "
             "serve('C', int(sys.argv[1]), Path(sys.argv[3]), Path(sys.argv[2]), "
             "drop_first_b=False, address='127.0.0.1', peer='127.0.0.1')",
             str(self.port), str(self.worker_out), str(self.executor)],
            cwd=PROBE.parents[1] / "experiments/aclt-minimal-verifier-baseline",
            env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def stop(self):
        if self.worker.poll() is None:
            self.worker.terminate()
            self.worker.wait(10)

    def wait_ready(self):
        deadline = time.monotonic() + 15
        while True:
            try:
                with socket.create_connection(("127.0.0.1", self.port), timeout=5):
                    return
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

    def connect(self, owner):
        return socket.create_connection(("127.0.0.1", self.port), timeout=5)

    def dispatch(self):
        import guest_multivm
        return guest_multivm.C1Dispatch(self.connect, self.coord_out, "A")

    def test_dispatch_round_trip_records_the_binding(self):
        dispatch = self.dispatch()
        boot, session = dispatch.open("C", 0, slot=1, attempt=1, action="SOLVE")
        request = Journal(self.job, self.root / "frame.cbor").frame(1, 1, "SOLVE", boot=boot)
        response = session.request(request)
        session.close()
        self.assertTrue(response)
        rows = read_lines(self.coord_out / "dispatch.jsonl")
        self.assertEqual([row["event"] for row in rows], ["activation", "outcome"])
        self.assertEqual(rows[0]["boot"], boot.hex())
        self.assertEqual(rows[1]["outcome"], "answered")
        begins = [row for row in read_lines(self.worker_out / "executions.jsonl")
                  if row["event"] == "execute-begin"]
        self.assertEqual([row["boot"] for row in begins], [boot.hex()])

    def test_duplicate_probes_are_refused_without_another_execution(self):
        import guest_multivm
        dispatch = self.dispatch()
        driver = guest_multivm.C1Driver("duplicate", connect_peer=self.connect,
                                        output=self.coord_out)
        boot, session = dispatch.open("C", 0, slot=1, attempt=1, action="SOLVE")
        request = Journal(self.job, self.root / "frame.cbor").frame(1, 1, "SOLVE", boot=boot)
        session.request(request)
        driver.after_failure(session, request)
        session.close()
        probes = read_lines(self.coord_out / "resends.jsonl")
        self.assertEqual([row["probe"] for row in probes], ["bare", "boot"])
        self.assertEqual([row["outcome"] for row in probes], ["refused", "refused"])
        refusals = read_lines(self.worker_out / "rejections.jsonl")
        self.assertEqual([row["reason"] for row in refusals], ["unactivated", "duplicate"])
        begins = [row for row in read_lines(self.worker_out / "executions.jsonl")
                  if row["event"] == "execute-begin"]
        self.assertEqual(len(begins), 1)


if __name__ == "__main__":
    unittest.main()
