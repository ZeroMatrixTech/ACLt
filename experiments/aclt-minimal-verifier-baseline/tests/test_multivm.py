# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import multivm
from job import JOB_TAG
from lan import operations
from tools.verification_profile import codec


def guest(role, local, peer, boot="boot"):
    return {"role": role, "boot_id": boot, "local_socket_ip": local, "peer_socket_ip": peer,
            "source_commit": "c0ffee", "executor_sha256": "ab" * 32}


def summary(plan, merged, slices):
    return {"job_id": codec.domain_hash(JOB_TAG, plan).hex(),
            "output_sha256": hashlib.sha256(merged).hexdigest(), "output_bytes": len(merged),
            "reference_gas_used": 9425, "solve_budget": None,
            "allocated_solve_gas": sum(entry["gas_limit"] for entry in slices),
            "reverse_order_equal": True, "slices": slices}


def sliced(worker, validator, gas_limit=100):
    return {"start": 0, "stop": 1, "status": "ACCEPT", "execution_host": worker,
            "verification_host": validator, "gas_limit": gas_limit}


class GuestReportTests(unittest.TestCase):
    def test_distinct_guests_pass(self):
        multivm.check_guests(guest("A", multivm.GUEST_A, multivm.GUEST_B, "a"),
                             guest("B", multivm.GUEST_B, multivm.GUEST_A, "b"))

    def test_same_boot_id_is_rejected(self):
        with self.assertRaises(multivm.RunError):
            multivm.check_guests(guest("A", multivm.GUEST_A, multivm.GUEST_B, "same"),
                                 guest("B", multivm.GUEST_B, multivm.GUEST_A, "same"))

    def test_loopback_peer_is_rejected(self):
        with self.assertRaises(multivm.RunError):
            multivm.check_guests(guest("A", multivm.GUEST_A, "127.0.0.1", "a"),
                                 guest("B", multivm.GUEST_B, multivm.GUEST_A, "b"))

    def test_swapped_roles_are_rejected(self):
        with self.assertRaises(multivm.RunError):
            multivm.check_guests(guest("B", multivm.GUEST_A, multivm.GUEST_B, "a"),
                                 guest("A", multivm.GUEST_B, multivm.GUEST_A, "b"))

    def test_different_executor_is_rejected(self):
        other = guest("B", multivm.GUEST_B, multivm.GUEST_A, "b")
        other["executor_sha256"] = "cd" * 32
        with self.assertRaises(multivm.RunError):
            multivm.check_guests(guest("A", multivm.GUEST_A, multivm.GUEST_B, "a"), other)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.plan, self.merged = b"plan-bytes", b"merged-output"
        (self.root / "plan.cbor").write_bytes(self.plan)
        (self.root / "merged-output.bin").write_bytes(self.merged)

    def tearDown(self):
        self.directory.cleanup()

    def test_expected_split_passes(self):
        entries = [sliced("A", "B"), sliced("B", "A")]
        multivm.check_summary(summary(self.plan, self.merged, entries), self.root)

    def test_single_host_slices_are_rejected(self):
        entries = [sliced("A", "B"), sliced("A", "B")]
        with self.assertRaises(multivm.RunError):
            multivm.check_summary(summary(self.plan, self.merged, entries), self.root)

    def test_rejected_slice_is_refused(self):
        entries = [sliced("A", "B"), sliced("B", "A")]
        entries[1]["status"] = "REJECT"
        with self.assertRaises(multivm.RunError):
            multivm.check_summary(summary(self.plan, self.merged, entries), self.root)

    def test_digest_mismatch_is_refused(self):
        entries = [sliced("A", "B"), sliced("B", "A")]
        record = summary(self.plan, self.merged, entries)
        record["output_sha256"] = "00" * 32
        with self.assertRaises(multivm.RunError):
            multivm.check_summary(record, self.root)

    def test_gas_sum_must_match_allocations(self):
        entries = [sliced("A", "B"), sliced("B", "A")]
        record = summary(self.plan, self.merged, entries)
        record["allocated_solve_gas"] += 1
        with self.assertRaises(multivm.RunError):
            multivm.check_summary(record, self.root)


class TranscriptTests(unittest.TestCase):
    def populate(self, root, leaf_count, salt=b""):
        root.mkdir(parents=True, exist_ok=True)
        for _, _, label in operations(leaf_count):
            for direction in ("request", "response"):
                (root / f"{label}-{direction}.cbor").write_bytes(label.encode() + salt)

    def test_identical_transcripts_pass(self):
        with TemporaryDirectory() as directory:
            a, b = Path(directory) / "A", Path(directory) / "B"
            self.populate(a, 2)
            self.populate(b, 2)
            for _, _, label in operations(2):
                for direction in ("request", "response"):
                    (b / f"{label}-{direction}.cbor").write_bytes((a / f"{label}-{direction}.cbor").read_bytes())
            (a / "result.json").write_text(json.dumps(summary(b"p", b"m", [sliced("A", "B"), sliced("B", "A")])))
            (a / "plan.cbor").write_bytes(b"p")
            (a / "merged-output.bin").write_bytes(b"m")
            record = multivm.check_run(a, b, leaf_count=2, recursive=False)
            self.assertTrue(record["lan_transcript_equal"])
            self.assertEqual(record["slices"], 2)

    def test_divergent_frame_is_refused(self):
        with TemporaryDirectory() as directory:
            a, b = Path(directory) / "A", Path(directory) / "B"
            self.populate(a, 2)
            self.populate(b, 2, b"-tampered")
            with self.assertRaises(multivm.RunError):
                multivm.check_run(a, b, leaf_count=2, recursive=False)


class BootArgumentTests(unittest.TestCase):
    def arguments(self, role, budget=None, leaves=2):
        return multivm.boot_arguments(role, Path("/k"), Path("/i"), Path("/d"), Path("/l"),
                                      "kvm", 1024, 5555, "c0ffee", budget, False, leaves)

    def test_guests_join_opposite_link_ends(self):
        b, a = self.arguments("B"), self.arguments("A")
        self.assertIn("socket,id=n0,listen=127.0.0.1:5555", b)
        self.assertIn("socket,id=n0,connect=127.0.0.1:5555", a)
        self.assertNotIn("socket,id=n0,listen=127.0.0.1:5555", a)

    def test_command_line_carries_role_and_addresses(self):
        append = self.arguments("A")[self.arguments("A").index("-append") + 1]
        self.assertIn("aclt_role=A", append)
        self.assertIn(f"aclt_ip={multivm.GUEST_A}/24", append)
        self.assertIn(f"aclt_peer={multivm.GUEST_B}", append)
        self.assertNotIn("aclt_budget=", append)

    def test_budget_is_forwarded_when_given(self):
        append = self.arguments("B", 17737)[self.arguments("B", 17737).index("-append") + 1]
        self.assertIn("aclt_budget=17737", append)

    def test_planned_leaf_count_reaches_both_guests(self):
        for role in ("A", "B"):
            append = self.arguments(role, leaves=4)[self.arguments(role, leaves=4).index("-append") + 1]
            self.assertIn("aclt_leaves=4", append)

    def test_flat_and_tree_plans_agree_on_their_shape(self):
        self.assertEqual(multivm.planned_leaf_count(None, False), 2)
        self.assertGreater(multivm.planned_leaf_count(None, True), 1)


@unittest.skipUnless(shutil.which("cpio"), "cpio is needed to inspect the archive")
class ArchiveTests(unittest.TestCase):
    def test_archive_carries_guest_entry_points(self):
        with TemporaryDirectory() as directory:
            root = Path(directory) / "root"
            (root / "bin").mkdir(parents=True)
            (root / "bin/busybox").write_bytes(b"\x7fELF")
            (root / "bin/sh").symlink_to("busybox")
            (root / "init").write_text("#!/bin/sh\n")
            archive = Path(directory) / "guest.cpio"
            multivm.write_cpio(root, archive)
            listing = subprocess.run(["cpio", "-it"], stdin=archive.open("rb"), check=True,
                                     capture_output=True, text=True).stdout.split()
            self.assertEqual(listing[1:], ["bin", "bin/busybox", "bin/sh", "init"])

    def test_init_runs_the_packed_entry_point(self):
        entry = "experiments/aclt-minimal-verifier-baseline/guest_multivm.py"
        self.assertIn(f"python3 /repo/{entry}", multivm.INIT)
        self.assertTrue((multivm.ROOT / entry).is_file())


if __name__ == "__main__":
    unittest.main()
