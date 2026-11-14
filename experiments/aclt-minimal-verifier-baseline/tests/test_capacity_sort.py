# SPDX-License-Identifier: Apache-2.0
"""Local regressions for the fixed-capacity two-partition delivery experiment."""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import capacity_sort
from tools.verification_profile import codec


TOOLS = ("mkfs.ext4", "debugfs", "dumpe2fs")
MISSING = tuple(tool for tool in TOOLS if shutil.which(tool) is None)

IMAGE_BYTES = 1 << 20
RECORDS = 1 << 16
PARTITION_BYTES = RECORDS // 2 * capacity_sort.RECORD.size
CHUNK_BYTES = 16 << 10
NONCE = bytes(range(32))


def scaled_declaration():
    return codec.encode(dict(rule="aclt.exp.partition-sort@1", fixture="alternating-range-v1",
                             records=RECORDS, encoding="u64be-key/u64be-ordinal",
                             order=["key", "ordinal"], output_bytes=RECORDS * capacity_sort.RECORD.size))


def scaled_plan():
    return codec.encode(dict(rule="aclt.exp.partition-sort@1", owners=["A", "B"],
                             keys=[0, 1 << 63], shard_records=RECORDS // 2))


@unittest.skipIf(MISSING, f"e2fsprogs tools missing: {', '.join(MISSING)}")
class CapacitySortRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.saved = {name: getattr(capacity_sort, name) for name in
                     ("IMAGE_BYTES", "RECORDS", "PARTITION_BYTES", "CHUNK_BYTES",
                      "DECLARATION", "PLAN")}
        cls.addClassCleanup(cls.restore)
        capacity_sort.IMAGE_BYTES = IMAGE_BYTES
        capacity_sort.RECORDS = RECORDS
        capacity_sort.PARTITION_BYTES = PARTITION_BYTES
        capacity_sort.CHUNK_BYTES = CHUNK_BYTES
        capacity_sort.DECLARATION = scaled_declaration()
        capacity_sort.PLAN = scaled_plan()

    @classmethod
    def restore(cls):
        for name, value in cls.saved.items():
            setattr(capacity_sort, name, value)

    def setUp(self):
        temporary = TemporaryDirectory(prefix="aclt-capacity-sort-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def run_pair(self):
        a, b = self.root / "a", self.root / "b"
        a.mkdir()
        b.mkdir()
        left, right = socket.socketpair()
        left.settimeout(15)
        right.settimeout(15)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (
                pool.submit(capacity_sort.distributed, left, "A", a, NONCE),
                pool.submit(capacity_sort.distributed, right, "B", b, NONCE),
            )
            try:
                for future in futures:
                    future.result(timeout=60)
            finally:
                left.close()
                right.close()
        return a, b

    def debugfs(self, image, command, write=False):
        arguments = ["debugfs"] + (["-w"] if write else []) + ["-R", command, str(image)]
        return subprocess.run(arguments, check=True, capture_output=True, text=True,
                              env=os.environ | {"LC_ALL": "C"})

    def assert_scaled_capacity(self, usable):
        self.assertGreaterEqual(usable, PARTITION_BYTES)
        self.assertLess(usable, 2 * PARTITION_BYTES)

    def test_scaled_two_party_round_trip_and_replay(self):
        a, b = self.run_pair()
        self.assertTrue((a / "publication.cbor").is_file())
        self.assertFalse((b / "publication.cbor").exists())
        for root, role in ((a, "A"), (b, "B")):
            result = json.loads((root / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["role"], role)
            self.assertEqual(result["capacity_bytes"], IMAGE_BYTES)
            self.assert_scaled_capacity(result["usable_bytes"])
            self.assertEqual(result["submitted_bytes"], PARTITION_BYTES)
            self.assertEqual(result["verified_bytes"], PARTITION_BYTES)
            self.assertEqual(result["payload_sent"], PARTITION_BYTES + PARTITION_BYTES // 2)
            self.assertEqual(result["payload_received"], PARTITION_BYTES + PARTITION_BYTES // 2)
            self.assertEqual((root / "declaration.cbor").read_bytes(), capacity_sort.DECLARATION)
            self.assertEqual((root / "plan.cbor").read_bytes(), capacity_sort.PLAN)
            self.assertEqual((root / "delivery.img").stat().st_size, IMAGE_BYTES)

        replay = capacity_sort.replay(a, b)
        self.assertEqual(replay["status"], "PASS")
        self.assertEqual(replay["verified_records"], RECORDS)
        self.assertEqual(replay["delivered_bytes"], 2 * PARTITION_BYTES)
        self.assertEqual(len(replay["partitions"]), 2)
        for value in replay["partitions"]:
            self.assertRegex(value, r"^[0-9a-f]{64}$")
        self.assertRegex(replay["execution_id"], r"^[0-9a-f]{64}$")

    def test_replay_rejects_missing_b_partition(self):
        a, b = self.run_pair()
        self.debugfs(b / "delivery.img", "rm /partition-1", write=True)
        with self.assertRaisesRegex(ValueError, "^missing or truncated stored partition$"):
            capacity_sort.replay(a, b)

    def test_replay_rejects_changed_b_partition(self):
        a, b = self.run_pair()
        image = b / "delivery.img"
        original = self.root / "b-partition-1.bin"
        self.debugfs(image, f"dump /partition-1 {original}")
        data = bytearray(original.read_bytes())
        self.assertEqual(len(data), PARTITION_BYTES)
        data[0] ^= 1
        changed = self.root / "b-partition-1-changed.bin"
        changed.write_bytes(data)
        self.debugfs(image, "rm /partition-1", write=True)
        self.debugfs(image, f"write {changed} /partition-1", write=True)
        with self.assertRaisesRegex(ValueError, "^record differs from frozen source or range$"):
            capacity_sort.replay(a, b)

    def test_single_node_reports_capacity_exhausted(self):
        output = self.root / "single"
        output.mkdir()
        capacity_sort.single(output)
        result = json.loads((output / "result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "CAPACITY_EXHAUSTED")
        self.assertEqual(result["capacity_bytes"], IMAGE_BYTES)
        self.assertEqual(result["required_bytes"], 2 * PARTITION_BYTES)
        self.assert_scaled_capacity(result["usable_bytes"])
        self.assertEqual(result["second_apparent_bytes"], PARTITION_BYTES)
        self.assertTrue(result["rejection"])
        self.assertEqual((output / "delivery.img").stat().st_size, IMAGE_BYTES)
