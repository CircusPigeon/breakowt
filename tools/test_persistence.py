"""Save and purchase regressions without third-party dependencies.

Run with: python -B tools/test_persistence.py
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from breakowt.engine.persistence import pending_purchases, read_json, record_purchase, write_json  # noqa: E402


class SaveTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="breakowt-save-test-")
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "save.json"
        self.backup = self.path.with_suffix(".json.bak")

    def test_latest_save_and_previous_backup_are_readable(self):
        first = {"day": 1, "flags": {"d1_page": True}}
        latest = {"day": 2, "flags": {"bell_off": True}}
        write_json(self.path, first)
        write_json(self.path, latest)
        self.assertEqual(read_json(self.path), latest)
        self.assertEqual(read_json(self.backup), first)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_corrupt_primary_recovers_previous_good_save(self):
        first = {"day": 1}
        write_json(self.path, first)
        write_json(self.path, {"day": 2})
        self.path.write_text('{"day":', encoding="utf-8")
        self.assertEqual(read_json(self.path), first)

    def test_saving_over_corrupt_primary_preserves_good_backup(self):
        first = {"day": 1}
        write_json(self.path, first)
        write_json(self.path, {"day": 2})
        self.path.write_text("truncated", encoding="utf-8")
        write_json(self.path, {"day": 3})
        self.assertEqual(read_json(self.path), {"day": 3})
        self.assertEqual(read_json(self.backup), first)

    def test_failed_primary_replace_keeps_original_and_cleans_temp(self):
        original = {"day": 4, "inv": {"items": {"shells": 2}}}
        write_json(self.path, original)
        original_bytes = self.path.read_bytes()
        real_replace = os.replace

        def fail_primary(source, destination):
            if Path(destination) == self.path:
                raise OSError("simulated replacement failure")
            return real_replace(source, destination)

        with patch("breakowt.engine.persistence.os.replace", side_effect=fail_primary):
            with self.assertRaises(OSError):
                write_json(self.path, {"day": 5})
        self.assertEqual(self.path.read_bytes(), original_bytes)
        self.assertEqual(read_json(self.path), original)
        self.assertEqual(read_json(self.backup), original)
        self.assertEqual(list(self.path.parent.glob("*.tmp")), [])

    def test_failed_first_save_leaves_no_partial_files(self):
        with patch("breakowt.engine.persistence.os.replace", side_effect=OSError("full disk")):
            with self.assertRaises(OSError):
                write_json(self.path, {"day": 1})
        self.assertFalse(self.path.exists())
        self.assertEqual(list(self.path.parent.iterdir()), [])

    def test_non_dict_primary_json_falls_back_to_good_backup(self):
        good = {"day": 2}
        write_json(self.path, good)
        write_json(self.path, {"day": 3})
        for invalid in ([], "save", 3, None, True):
            with self.subTest(primary=invalid):
                self.path.write_text(json.dumps(invalid), encoding="utf-8")
                self.assertEqual(read_json(self.path), good)

    def test_missing_or_invalid_files_return_none(self):
        self.assertIsNone(read_json(self.path))
        self.path.write_text("invalid", encoding="utf-8")
        self.backup.write_text("[]", encoding="utf-8")
        self.assertIsNone(read_json(self.path))


class PurchaseTests(unittest.TestCase):
    def test_debit_and_delivery_receipt_are_saved_in_one_profile(self):
        with tempfile.TemporaryDirectory(prefix="breakowt-purchase-test-") as folder:
            path = Path(folder) / "moodals.json"
            data = {"purse": {"found": 10, "spent": 1}}
            receipt = record_purchase(data, 6, "shells", keep=False, run_id="run-a", day=6)
            write_json(path, data)
            saved = read_json(path)
            self.assertEqual(saved["purse"]["spent"], 7)
            self.assertEqual(saved["purse"]["purchases"], [receipt])
            self.assertEqual(receipt["run"], "run-a")
            self.assertEqual(receipt["day"], 6)
            self.assertEqual(receipt["key"], "shells")
            self.assertTrue(receipt["id"])
            self.assertNotIn("shells", saved["purse"].get("owned", []))
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_pending_receipts_filter_run_applied_ids_and_invalid_entries(self):
        data = {"purse": {}}
        applied = record_purchase(data, 6, "shells", False, "run-a", 6)
        pending = record_purchase(data, 2, "coffee", False, "run-a", 6)
        record_purchase(data, 6, "shells", False, "run-b", 6)
        data["purse"]["purchases"].extend([
            None, "bad", {"id": 42, "run": "run-a", "key": "shells"},
            {"id": "unknown-item", "run": "run-a", "key": "tractor"},
        ])
        flags = {"_run_id": "run-a", "_purchases": [applied["id"]]}
        self.assertEqual(pending_purchases(data, flags), [pending])

    def test_multiple_purchases_replay_only_after_the_restored_snapshot(self):
        data = {"purse": {}}
        old_flags = {"_run_id": "run-a", "_purchases": []}
        first = record_purchase(data, 6, "shells", False, "run-a", 6)
        checkpoint_flags = copy.deepcopy(old_flags)
        checkpoint_flags["_purchases"].append(first["id"])
        second = record_purchase(data, 6, "shells", False, "run-a", 6)
        coffee = record_purchase(data, 2, "coffee", False, "run-a", 6)
        self.assertEqual(pending_purchases(data, old_flags), [first, second, coffee])
        self.assertEqual(pending_purchases(data, checkpoint_flags), [second, coffee])
        self.assertEqual(data["purse"]["spent"], 14)
        self.assertEqual(len({r["id"] for r in data["purse"]["purchases"]}), 3)
        latest_flags = {"_run_id": "run-a", "_purchases": [first["id"], second["id"], coffee["id"]]}
        self.assertEqual(pending_purchases(data, latest_flags), [])

    def test_permanent_purchase_records_ownership_without_consumable_receipt(self):
        data = {"purse": {}}
        self.assertIsNone(record_purchase(data, 3, "rubber_chicken", True, "run-a", 3))
        self.assertEqual(data["purse"]["owned"], ["rubber_chicken"])
        self.assertEqual(data["purse"]["spent"], 3)
        self.assertEqual(pending_purchases(data, {"_run_id": "run-a"}), [])


if __name__ == "__main__":
    unittest.main()
