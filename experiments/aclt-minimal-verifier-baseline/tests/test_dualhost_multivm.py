# SPDX-License-Identifier: Apache-2.0
"""Dual-host placement, fail-closed transport setup and evidence checks."""

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dualhost_multivm as dual
import multivm


class DualHostTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.settings = dict(ssh_target="example.invalid", host_a_lan="192.0.2.1",
                             host_b_lan="192.0.2.2", remote_root="/tmp")
        self.roles = ("A", "B", "C", "D")

    def make_config(self, **changes):
        path = self.root / "config.json"
        path.write_text(json.dumps(self.settings | changes))
        return path

    def test_validate_config_and_placement(self):
        self.assertEqual(dual.config(self.make_config(), self.roles, "D,B")[1], ("B", "D"))
        for roles in ("A,B", "B,B", "E", ""):
            with self.subTest(roles=roles), self.assertRaises(dual.DualHostError):
                dual.config(self.make_config(), self.roles, roles)
        for changes in (dict(host_b_lan="127.0.0.1"), dict(host_b_lan="192.0.2.1"),
                        dict(ssh_target="-oProxyCommand=bad"), dict(remote_root="relative")):
            with self.subTest(changes=changes), self.assertRaises(dual.DualHostError):
                dual.config(self.make_config(**changes), self.roles, "B")

    def test_host_lock_excludes_second_acquisition_and_releases(self):
        path = self.root / "lock"
        with dual.experiment_lock(path):
            with self.assertRaisesRegex(dual.DualHostError, "lock busy"):
                with dual.experiment_lock(path):
                    self.fail("second acquisition succeeded")
        with dual.experiment_lock(path):
            pass

    def test_boot_backends_use_lan_only_for_remote_guests(self):
        def command(role):
            return multivm.boot_arguments(role, Path("kernel"), Path("guest"), Path("disk"), Path("log"),
                                          "tcg", 1024, 10200, "revision", None, True, 4,
                                          {"B": 10200, "C": 10201, "D": 10202},
                                          lan_links={"B": "192.0.2.2", "D": "192.0.2.2"})
        self.assertIn("stream,id=linkB,server=off,addr.type=inet,addr.host=192.0.2.2,addr.port=10200", command("A"))
        self.assertIn("socket,id=linkC,connect=127.0.0.1:10201", command("A"))
        self.assertIn("stream,id=n0,server=on,addr.type=inet,addr.host=192.0.2.2,addr.port=10202", command("D"))
        self.assertIn("socket,id=n0,listen=127.0.0.1:10201", command("C"))

    def test_missing_reversed_and_misplaced_lan_evidence(self):
        a = dict(local=["A-LAN", 65000], peer=["B-LAN", 50000])
        b = dict(local=a["peer"], peer=a["local"])
        topology = dict(placement={"A": "A", "B": "B", "C": "A"}, lan_links={"B": {"A": a, "B": b}},
                        host_a_lock="held", host_b_environment={"lock": "held"},
                        host_b_boot_hashes={"kernel": "k", "guest.cpio.gz": "i"})
        record = dict(topology=topology, kernel_sha256="k", initramfs_sha256="i")
        dual.check_lan(record, self.roles[:3], ("B",))
        with self.assertRaisesRegex(dual.DualHostError, "placement"):
            dual.check_lan(record, self.roles[:3], ("C",))
        b["peer"] = ["A-LAN", 65001]
        with self.assertRaisesRegex(dual.DualHostError, "observations"):
            dual.check_lan(record, self.roles[:3], ("B",))

    def test_staging_and_collection_errors_stop(self):
        remote = dual.Remote(self.settings, ("B",), self.root)
        file = self.make_config()
        with patch.object(remote, "call", return_value="unrelated"):
            remote.stage(file, file)  # boot image digest consistency DISABLED
        with patch.object(remote, "call", side_effect=DualFailure):
            with self.assertRaises(DualFailure):
                remote.collect("B", self.root / "disk", self.root / "log", float("inf"))
        self.assertFalse((self.root / "disk").exists())


class DualFailure(OSError):
    pass
