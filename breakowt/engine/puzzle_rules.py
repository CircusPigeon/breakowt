"""Geometry and access rules for the farm's physical puzzles (no renderer needed)."""
from __future__ import annotations

import math

SUPPORTS = (80.4, 82.5, 84.6)
BOARD_LENGTHS = {"long": 4.7, "short_a": 2.6, "short_b": 2.6}
SLOTS = {f"{side}_{section}": (x, z) for side, x in (("left", -0.5), ("right", 0.5))
         for section, z in (("south", 81.45), ("north", 83.55), ("full", 82.5))}
LEGACY_LAYOUT = (("long", "right_full"), ("short_a", "left_south"), ("short_b", "left_north"))


def clean_layout(layout):
    """A save can only contain the three authored boards, each in one physical slot."""
    if not isinstance(layout, dict):
        return {}
    result, occupied = {}, set()
    for board in BOARD_LENGTHS:
        placement = layout.get(board)
        if not isinstance(placement, dict) or placement.get("slot") not in SLOTS:
            continue
        slot = placement["slot"]
        if slot in occupied:
            continue
        result[board] = {"slot": slot, "turned": bool(placement.get("turned", False))}
        occupied.add(slot)
    return result


def legacy_layout(count):
    try:
        count = max(0, min(3, int(count)))
    except (ValueError, TypeError):
        count = 0
    return {board: {"slot": slot, "turned": False} for board, slot in LEGACY_LAYOUT[:count]}


def board_supported(board, placement):
    """Both ends must rest on a painted support, rather than on open bars."""
    if board not in BOARD_LENGTHS or placement.get("slot") not in SLOTS or placement.get("turned"):
        return False
    _, z = SLOTS[placement["slot"]]
    ends = (z - BOARD_LENGTHS[board] / 2, z + BOARD_LENGTHS[board] / 2)
    return all(min(abs(end - support) for support in SUPPORTS) <= 0.3 + 1e-8 for end in ends)


def bridge_status(layout):
    """Check supported, continuous coverage on both hoof lanes; count alone is insufficient."""
    layout = clean_layout(layout)
    for board, placement in layout.items():
        if placement["turned"]:
            return False, "A board lies sideways. Its grain should point toward the road. Turn that board."
        if not board_supported(board, placement):
            return False, "A board end hangs over open bars. Both ends need a yellow support line beneath them."
    for side in ("left", "right"):
        spans = []
        for board, placement in layout.items():
            if placement["slot"].startswith(side + "_"):
                _, z = SLOTS[placement["slot"]]
                spans.append((z - BOARD_LENGTHS[board] / 2, z + BOARD_LENGTHS[board] / 2))
        covered = SUPPORTS[0]
        for start, end in sorted(spans):
            if start > covered + 0.05:
                break
            covered = max(covered, end)
        if covered < SUPPORTS[-1]:
            return False, f"The {side} hoof lane has a gap. One long board spans the pit; two short boards meet at the middle support."
    return True, "Both hoof lanes are supported from grass to road. Moothagoras approves the arithmetic."


def on_plate(x, y, z):
    return math.isfinite(x) and math.isfinite(y) and math.isfinite(z) and abs(x - 3) <= 1.15 and abs(z - 18) <= 0.95 and -0.1 <= y <= 0.35


def plate_load(weights):
    """Each entry is (x, feet_y, z, weight); jumping and standing beside it do not count."""
    return sum(weight for x, y, z, weight in weights if on_plate(x, y, z) and weight > 0)


def cabinet_access(is_open, farmer_distance, elevated_hatch=False):
    """The unlocked door still requires getting Chuck away; the high hatch bypasses the lock."""
    return bool(elevated_hatch or (is_open and farmer_distance >= 4.5))
