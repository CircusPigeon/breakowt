"""Renderer-free regression checks for physical puzzle rules."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from breakowt.engine.puzzle_rules import (BOARD_LENGTHS, bridge_status, cabinet_access, clean_layout,
                                         legacy_layout, plate_load)


class BridgeTests(unittest.TestCase):
    def test_three_boards_need_correct_positions(self):
        layout = legacy_layout(3)
        self.assertTrue(bridge_status(layout)[0])
        layout["short_b"]["slot"] = "right_north"
        self.assertFalse(bridge_status(layout)[0])

    def test_swapping_rails_is_also_valid(self):
        layout = {board: {"slot": slot, "turned": False} for board, slot in
                  (("long", "left_full"), ("short_a", "right_north"), ("short_b", "right_south"))}
        self.assertTrue(bridge_status(layout)[0])

    def test_turning_and_unsupported_end_are_distinct_failures(self):
        layout = legacy_layout(3)
        layout["long"]["turned"] = True
        self.assertIn("sideways", bridge_status(layout)[1])
        layout["long"] = {"slot": "right_south"}
        self.assertIn("end hangs", bridge_status(layout)[1])

    def test_middle_short_board_cannot_float(self):
        layout = legacy_layout(3)
        layout["short_a"]["slot"] = "left_full"
        self.assertFalse(bridge_status(layout)[0])

    def test_partial_and_legacy_layouts(self):
        for count in range(3):
            self.assertEqual(len(legacy_layout(count)), count)
            self.assertFalse(bridge_status(legacy_layout(count))[0])
        self.assertTrue(bridge_status(legacy_layout(9))[0])
        self.assertEqual(legacy_layout("broken"), {})

    def test_corrupt_layout_cannot_duplicate_or_invent_boards(self):
        self.assertEqual(clean_layout(None), {})
        result = clean_layout({"long": {"slot": "left_full"}, "short_a": {"slot": "left_full"},
                               "short_b": {"slot": "missing"}, "fourth": {"slot": "right_full"}})
        self.assertEqual(set(result), {"long"})
        self.assertEqual(set(BOARD_LENGTHS), {"long", "short_a", "short_b"})


class WeightAndCabinetTests(unittest.TestCase):
    def test_player_opens_gate_but_it_closes_when_they_leave(self):
        self.assertEqual(plate_load([(3, 0, 18, 3)]), 3)
        self.assertEqual(plate_load([(3, 0, 20, 3)]), 0)

    def test_heavy_crate_or_two_small_weights_work(self):
        self.assertEqual(plate_load([(3, 0, 18, 3)]), 3)
        self.assertEqual(plate_load([(2.4, 0, 18, 1.5), (3.6, 0, 18, 1.5)]), 3)
        self.assertLess(plate_load([(3, 0, 18, 1.5)]), 3)

    def test_jump_and_nonfinite_positions_do_not_hold_gate(self):
        self.assertEqual(plate_load([(3, 1, 18, 3), (float("nan"), 0, 18, 99)]), 0)

    def test_door_requires_unlock_and_distraction(self):
        self.assertFalse(cabinet_access(False, 20))
        self.assertFalse(cabinet_access(True, 2))
        self.assertTrue(cabinet_access(True, 4.5))
        self.assertTrue(cabinet_access(False, 0, elevated_hatch=True))


if __name__ == "__main__":
    unittest.main()
