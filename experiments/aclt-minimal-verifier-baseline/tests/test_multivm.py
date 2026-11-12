# SPDX-License-Identifier: Apache-2.0
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import multivm
from tools.verification_profile import codec


HOST_IDS = {"commit": "c0ffee", "executor_sha256": "ab" * 32, "source_manifest_sha256": "34" * 32}


def guest(role, local, peer, boot):
    return {"role": role, "boot_id": boot, "local_socket_ip": local, "peer_socket_ip": peer,
            "source_commit": HOST_IDS["commit"], "executor_sha256": HOST_IDS["executor_sha256"],
            "source_manifest_sha256": HOST_IDS["source_manifest_sha256"]}


class GuestReportTests(unittest.TestCase):
    def setUp(self):
        self.a = guest("A", multivm.GUEST_A, multivm.GUEST_B, "a")
        self.b = guest("B", multivm.GUEST_B, multivm.GUEST_A, "b")

    def test_distinct_guests_pass(self):
        multivm.check_guests(self.a, self.b, **HOST_IDS)

    def test_same_boot_id_is_rejected(self):
        with self.assertRaisesRegex(multivm.RunError, "same boot id"):
            multivm.check_guests(self.a, dict(self.b, boot_id="a"), **HOST_IDS)

    def test_loopback_peer_is_rejected(self):
        with self.assertRaisesRegex(multivm.RunError, "TCP addresses"):
            multivm.check_guests(self.a, dict(self.b, peer_socket_ip="127.0.0.1"), **HOST_IDS)

    def test_swapped_roles_are_rejected(self):
        with self.assertRaisesRegex(multivm.RunError, "assigned role"):
            multivm.check_guests(self.b, self.a, **HOST_IDS)

    def test_guest_ids_must_match_host_even_when_guests_agree(self):
        for field in ("source_commit", "executor_sha256", "source_manifest_sha256"):
            with self.subTest(field=field), self.assertRaisesRegex(multivm.RunError, field):
                multivm.check_guests(dict(self.a, **{field: "00"}), dict(self.b, **{field: "00"}), **HOST_IDS)


class SnapshotTests(unittest.TestCase):
    def archive(self, content, digest):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w") as bundle:
            for name, data in (("test.py", content), ("SOURCE-SHA256SUMS", f"{digest}  test.py\n".encode())):
                member = tarfile.TarInfo(name)
                member.size = len(data)
                bundle.addfile(member, io.BytesIO(data))
        return stream.getvalue()

    def test_stages_the_frozen_commit(self):
        content = b"committed source"
        digest = hashlib.sha256(content).hexdigest()
        with TemporaryDirectory() as directory, patch("multivm.subprocess.check_output", return_value=content):
            path = Path(directory) / "repo"
            actual = multivm.stage_sources(path, "commit", self.archive(content, digest), {"test.py": digest})
            self.assertEqual((path / "test.py").read_bytes(), content)
            self.assertEqual(actual, multivm.sha256(path / "SOURCE-SHA256SUMS"))

    def test_rejects_archive_whose_pin_differs_from_git(self):
        content = b"changed source"
        digest = hashlib.sha256(content).hexdigest()
        with TemporaryDirectory() as directory, patch("multivm.subprocess.check_output", return_value=b"commit"):
            with self.assertRaisesRegex(multivm.RunError, "frozen source does not match"):
                multivm.stage_sources(Path(directory) / "repo", "commit", self.archive(content, digest),
                                      {"test.py": digest})


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.a, self.b = (Path(directory.name) / role for role in ("A", "B"))
        archive = (multivm.ROOT / "docs/testing/public-evidence/MULTIVM-20261112-public-evidence.tar.gz")
        with tarfile.open(archive, "r:gz") as bundle:
            for role, destination in (("A", self.a), ("B", self.b)):
                destination.mkdir()
                prefix = f"./mv-tree/{role}-disk/{role}/"
                for member in bundle.getmembers():
                    if member.isfile() and member.name.startswith(prefix):
                        with bundle.extractfile(member) as source:
                            (destination / Path(member.name).name).write_bytes(source.read())

    def check(self, *, budget=None):
        return multivm.check_run(self.a, self.b, leaf_count=3, recursive=True, solve_budget=budget)

    def test_replays_retained_tree_evidence(self):
        report = self.check()
        self.assertTrue(report["lan_transcript_equal"])
        self.assertEqual(report["slices"], 3)
        self.assertEqual(report["leaf_solve_gas_used"], 26049)

    def test_summary_fields_must_match_replay(self):
        path = self.a / "result.json"
        original = path.read_text()
        for field, update in (("slices", {"gas_used": 0}), ("slices", {"status": "REJECT"}),
                              ("slices", {"execution_host": "B"}), ("allocated_solve_gas", 0),
                              ("output_sha256", "00" * 32)):
            with self.subTest(field=field, update=update):
                report = json.loads(original)
                if field == "slices":
                    report["slices"][0].update(update)
                else:
                    report[field] = update
                path.write_text(json.dumps(report))
                with self.assertRaisesRegex(multivm.RunError, field):
                    self.check()

    def test_requested_budget_must_match_plan(self):
        with self.assertRaisesRegex(multivm.RunError, "differs from the host plan"):
            self.check(budget=26049)

    def test_saved_outputs_must_match_replay(self):
        for name in ("reference-output.bin", "merged-output.bin", "flat-output.bin"):
            with self.subTest(name=name):
                path = self.a / name
                original = path.read_bytes()
                path.write_bytes(b"inconsistent output")
                with self.assertRaisesRegex(multivm.RunError, "output"):
                    self.check()
                path.write_bytes(original)

    def test_identically_copied_frames_still_need_correct_gas(self):
        filename = "SOLVE-response.cbor"
        frame = codec.decode((self.a / filename).read_bytes())
        outcome = codec.decode(frame["answer"]["outcome"])
        outcome["gas_used"] -= 1
        frame["answer"]["outcome"] = codec.encode(outcome)
        for role in (self.a, self.b):
            (role / filename).write_bytes(codec.encode(frame))
        with self.assertRaisesRegex(multivm.RunError, "metered gas differs"):
            self.check()

    def test_divergent_frame_is_refused(self):
        (self.b / "SOLVE-response.cbor").write_bytes(b"divergent frame")
        with self.assertRaisesRegex(multivm.RunError, "A/B transcript mismatch"):
            self.check()


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
            (root / "数据.txt").write_text("guest payload")
            archive = Path(directory) / "guest.cpio"
            multivm.write_cpio(root, archive)
            with archive.open("rb") as source:
                listing = subprocess.run(["cpio", "-it"], stdin=source, check=True,
                                         capture_output=True, text=True).stdout.splitlines()
            self.assertEqual(listing[1:], ["bin", "bin/busybox", "bin/sh", "init", "数据.txt"])

    def test_init_runs_the_packed_entry_point(self):
        entry = "experiments/aclt-minimal-verifier-baseline/guest_multivm.py"
        self.assertIn(f"python3 /repo/{entry}", multivm.INIT)
        self.assertTrue((multivm.ROOT / entry).is_file())


if __name__ == "__main__":
    unittest.main()
