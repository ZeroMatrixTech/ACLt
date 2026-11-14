# SPDX-License-Identifier: Apache-2.0
"""Trusted host admission for a single experimental execution."""

import os
import subprocess
import sys
import time
from threading import RLock

from general_job import Journal
from tools.verification_profile import codec as c


class CoordinationError(c.CodecError):
    """A coordinator failed an authority or write admission check."""


class Coordinator:
    """Own the live journal and serialize all coordinator write intents on one host."""

    def __init__(self, job, path, trace, *, source=None):
        self.journal = Journal(job, path, source=source)
        self.trace = trace
        self.lock = RLock()
        self.owner = None
        self.epoch = 0
        self.pending = None
        self.paused = False

    def record(self, kind, **fields):
        with self.trace.open("ab") as stream:
            raw = c.encode(dict(kind=kind, **fields))
            stream.write(len(raw).to_bytes(4, "big") + raw)
            stream.flush()
            os.fsync(stream.fileno())

    def assign(self, process):
        with self.lock:
            if self.paused or self.pending or process.poll() is not None:
                raise CoordinationError("coordination unavailable")
            if self.owner is not None:
                if self.owner.poll() is None:
                    self.record("ASSIGN_REJECTED", owner=self.owner.pid, candidate=process.pid, epoch=self.epoch)
                    raise CoordinationError("old coordinator still running")
                history = c.decode(self.journal.path.read_bytes())
                replay = Journal(self.journal.job, self.journal.path, history, source=self.journal.source)
                if replay.events != self.journal.events or replay.final is not None:
                    raise CoordinationError("checkpoint differs or execution is final")
                replay.add("HANDOFF", epoch=self.epoch + 1)
                self.journal = replay
                self.epoch += 1
            self.owner = process
            self.record("ASSIGNED", owner=process.pid, epoch=self.epoch,
                        execution=self.journal.job.execution_id)
            return self.epoch

    def begin(self, process, message):
        """Register an intent before mutating the journal or releasing a dispatch."""
        with self.lock:
            c.fields(message, ("epoch", "event", "fields"))
            epoch = c.uint(message["epoch"])
            self.record("WRITE_REQUEST", owner=process.pid, message=message)
            if self.paused:
                raise CoordinationError("dispatch and publication paused")
            if self.pending is not None:
                active, pending = self.pending
                if active is not process and pending["epoch"] != epoch:
                    self.paused = True
                    self.pending = None
                    self.record("PAUSED", active=active.pid, active_epoch=pending["epoch"],
                                conflicting=process.pid, conflicting_epoch=epoch)
                    raise CoordinationError("overlapping coordinator epochs")
                raise CoordinationError("a write is already in progress")
            if process is not self.owner or process.poll() is not None or epoch != self.epoch:
                self.record("WRITE_REJECTED", owner=process.pid, epoch=epoch, reason="not current coordinator")
                raise CoordinationError("not current coordinator")
            if message["event"] == "HANDOFF":
                raise CoordinationError("handoff requires host reassignment")
            self.pending = process, message

    def commit(self, process):
        with self.lock:
            if self.paused:
                raise CoordinationError("dispatch and publication paused")
            if self.pending is None or self.pending[0] is not process:
                raise CoordinationError("no matching write intent")
            _, message = self.pending
            self.pending = None
            if process is not self.owner or process.poll() is not None or message["epoch"] != self.epoch:
                raise CoordinationError("not current coordinator")
            result = self.journal.add(message["event"], writer_epoch=self.epoch, **message["fields"])
            self.record("WRITE_COMMITTED", owner=process.pid, epoch=self.epoch, event=message["event"])
            return result

def receive(stream, *, guest=False):
    def exact(size):
        data = bytearray()
        deadline = time.monotonic() + 10 if guest else None
        while len(data) < size:
            block = stream.read(size - len(data))
            if block:
                data.extend(block)
            elif deadline is None or time.monotonic() >= deadline:
                raise CoordinationError("coordination host response incomplete")
            else:
                time.sleep(0.02)
        return bytes(data)

    header = exact(4)
    length = int.from_bytes(header, "big")
    c.need(0 < length <= 900000, f"invalid coordination frame header {header.hex()}")
    return c.decode(exact(length))


def send(stream, message):
    raw = c.encode(message)
    frame = memoryview(len(raw).to_bytes(4, "big") + raw)
    while frame:
        written = stream.write(frame)
        if not written:
            raise CoordinationError("coordination frame write incomplete")
        frame = frame[written:]
    stream.flush()


class GuestJournal(Journal):
    """A guest mirror that waits for the host before it can dispatch or publish."""

    def __init__(self, job, path, events, *, source, reader, writer):
        super().__init__(job, path, events, source=source)
        self.reader = reader
        self.writer = writer

    def add(self, kind, **fields):
        epoch = fields["epoch"] if kind == "HANDOFF" else self.epoch
        send(self.writer, dict(epoch=epoch, event=kind, fields=fields))
        response = receive(self.reader, guest=True)
        if "error" in response:
            raise CoordinationError(response["error"])
        result = super().add(kind, **fields) if kind == "HANDOFF" else super().add(kind, writer_epoch=epoch, **fields)
        c.need(result == response["result"], "host and guest journals differ")
        return result


def serve(authority, process, reader, writer, *, on_intent=None):
    while True:
        header = reader.peek(1)
        if not header:
            return
        message = receive(reader)
        try:
            if message["event"] == "HANDOFF":
                # Assignment already replayed the journal and wrote the handoff.
                c.need(not authority.paused and authority.owner is process and process.poll() is None
                       and message == dict(epoch=authority.epoch, event="HANDOFF",
                                           fields={"epoch": authority.epoch})
                       and authority.journal.events[-1] == {"kind": "HANDOFF", "epoch": authority.epoch},
                       "handoff is not the current host assignment")
                result = None
            else:
                authority.begin(process, message)
                if on_intent is not None:
                    on_intent()
                result = authority.commit(process)
        except c.CodecError as error:
            send(writer, {"error": str(error)})
        else:
            send(writer, {"result": result})


def conflicting_intent(authority):
    """Test-only stale coordinator process with a separate write request."""
    script = ("import signal, sys; "
              "sys.stdout.buffer.write(sys.stdin.buffer.read()); sys.stdout.flush(); signal.pause()")
    message = dict(epoch=authority.epoch - 1, event="PUBLISH", fields={})
    with subprocess.Popen([sys.executable, "-c", script], stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE) as stale:
        send(stale.stdin, message)
        stale.stdin.close()
        try:
            authority.begin(stale, receive(stale.stdout))
        except CoordinationError as error:
            c.need(authority.paused, str(error))
        else:
            raise CoordinationError("conflicting writer was not stopped")
        finally:
            stale.terminate()
