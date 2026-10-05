"""Collision regressions without a game window or third-party dependencies.

Run with: python -B tools/test_physics.py
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from breakowt.engine.physics import Physics  # noqa: E402


class CircleCollisionTests(unittest.TestCase):
    def make_circle(self, dynamic):
        phys = Physics()
        if dynamic:
            circle = phys.add_dynamic(0, 0, 0.5, owner=object())
        else:
            circle = phys.add_circle(0, 0, 0.5)
        return phys, circle

    def assert_bounded_push(self, start, result, max_push=1.0):
        self.assertTrue(all(math.isfinite(v) for v in result))
        displacement = math.hypot(result[0] - start[0], result[1] - start[1])
        self.assertGreater(displacement, 0)
        self.assertLessEqual(displacement, max_push + 1e-12)

    def test_coincident_static_centers_separate_by_radii(self):
        phys, _ = self.make_circle(dynamic=False)
        result = phys.resolve(0, 0, 0.5)
        self.assert_bounded_push((0, 0), result)
        self.assertAlmostEqual(math.hypot(*result), 1.0)

    def test_coincident_dynamic_centers_keep_soft_bounded_push(self):
        phys, _ = self.make_circle(dynamic=True)
        result = phys.resolve(0, 0, 0.5, iterations=1)
        self.assert_bounded_push((0, 0), result, max_push=0.6)
        self.assertAlmostEqual(math.hypot(*result), 0.6)
        for _ in range(10):
            result = phys.resolve(*result, 0.5)
            self.assertTrue(all(math.isfinite(v) for v in result))
            self.assertLessEqual(math.hypot(*result), 1.0 + 1e-12)
        self.assertAlmostEqual(math.hypot(*result), 1.0)

    def test_near_zero_centers_push_away_without_large_displacement(self):
        starts = ((1e-8, 0), (0, -1e-8), (-1e-8, 1e-8), (1e-150, -1e-150))
        for dynamic in (False, True):
            for start in starts:
                with self.subTest(dynamic=dynamic, start=start):
                    phys, _ = self.make_circle(dynamic)
                    result = phys.resolve(*start, 0.5, iterations=1)
                    self.assert_bounded_push(start, result)
                    self.assertGreater(math.hypot(*result), math.hypot(*start))
                    # Preserve the direction away from the obstacle, even below the old epsilon.
                    cross = result[0] * start[1] - result[1] * start[0]
                    self.assertAlmostEqual(cross / math.hypot(*start), 0.0)
                    self.assertGreater(result[0] * start[0] + result[1] * start[1], 0)
                    if not dynamic:
                        self.assertAlmostEqual(math.hypot(*result), 1.0)

    def test_normal_static_overlap_resolves_radially(self):
        phys, _ = self.make_circle(dynamic=False)
        result = phys.resolve(0.3, 0.4, 0.5, iterations=1)
        self.assertAlmostEqual(result[0], 0.6)
        self.assertAlmostEqual(result[1], 0.8)

    def test_normal_dynamic_overlap_retains_soft_push(self):
        phys, _ = self.make_circle(dynamic=True)
        result = phys.resolve(0.3, 0.4, 0.5, iterations=1)
        self.assertAlmostEqual(result[0], 0.48)
        self.assertAlmostEqual(result[1], 0.64)

    def test_touching_and_separated_circles_do_not_move(self):
        for dynamic in (False, True):
            phys, _ = self.make_circle(dynamic)
            for start in ((1.0, 0), (0, -2.0)):
                with self.subTest(dynamic=dynamic, start=start):
                    self.assertEqual(phys.resolve(*start, 0.5), start)

    def test_dynamic_without_owner_collides_with_default_ignore(self):
        phys = Physics()
        phys.add_dynamic(0, 0, 0.5)
        result = phys.resolve(0, 0, 0.5)
        self.assert_bounded_push((0, 0), result)

    def test_ignoring_circle_skips_only_that_shape(self):
        for dynamic in (False, True):
            with self.subTest(dynamic=dynamic):
                phys, circle = self.make_circle(dynamic)
                self.assertEqual(phys.resolve(0, 0, 0.5, ignore=circle), (0, 0))
                self.assert_bounded_push((0, 0), phys.resolve(0, 0, 0.5, ignore=object()))

    def test_ignoring_owner_skips_only_its_dynamic_circle(self):
        phys, circle = self.make_circle(dynamic=True)
        self.assertEqual(phys.resolve(0, 0, 0.5, ignore=circle.owner), (0, 0))
        other = phys.add_dynamic(0, 0, 0.5, owner=object())
        result = phys.resolve(0, 0, 0.5, ignore=circle.owner)
        self.assert_bounded_push((0, 0), result)
        self.assertIsNot(other.owner, circle.owner)

    def test_excluding_dynamic_circles_skips_overlap(self):
        phys, _ = self.make_circle(dynamic=True)
        self.assertEqual(phys.resolve(0, 0, 0.5, include_dynamic=False), (0, 0))

    def test_move_with_no_velocity_still_resolves_overlap_safely(self):
        for dynamic in (False, True):
            with self.subTest(dynamic=dynamic):
                phys, _ = self.make_circle(dynamic)
                self.assert_bounded_push((0, 0), phys.move(0, 0, 0, 0, 0.5))


if __name__ == "__main__":
    unittest.main()
