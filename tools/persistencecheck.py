"""Exercise real shop callbacks, reloads, and partial story checkpoints.

Run like the other harness tools: python -B tools/persistencecheck.py
Uses an isolated temporary save folder unless BREAKOWT_SAVE_DIR is already set.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness  # noqa: E402
from walkthrough import Bot, FPS  # noqa: E402


class PersistenceCheck:
    def __init__(self, app, game):
        self.g = game
        args = SimpleNamespace(shots=False, caught="", detect=False, render=False, verbose=False, ending="auto")
        self.bot = Bot(app, game, args)
        self.check = unittest.TestCase()

    def tick(self):
        self.g.farmer.detect = False
        self.bot.tick()
        self.g.farmer.detect = False
        if self.bot.errors:
            raise AssertionError(f"Script errors: {self.bot.errors}")

    def wait(self, condition, label, seconds=120):
        for _ in range(seconds * FPS):
            if condition():
                return
            self.tick()
        raise AssertionError(f"Timed out waiting for {label}; current step={self.g.story.cur}")

    def run_plan(self, plan):
        for _ in range(120 * FPS):
            try:
                next(plan)
            except StopIteration:
                return
            self.tick()
        plan.close()
        raise AssertionError("Plan took more than 120 seconds of game time")

    def reach_step(self, day, target):
        self.g.story.new_game(day)
        self.wait(lambda: self.g.day == day and self.g.story.cur is None, "new day setup")
        last_key = None
        plan = None
        for _ in range(240 * FPS):
            key = self.g.story.cur
            if self.g.day == day and key == target and self.bot.ready():
                return
            if key != last_key:
                last_key = key
                plan = self.bot.plan_for(key) if key and key != target else None
            if plan is not None:
                try:
                    next(plan)
                except StopIteration:
                    plan = None
            self.tick()
        raise AssertionError(f"Did not reach {target}; current step={self.g.story.cur}")

    def reload(self, snapshot, target):
        self.g.story.load_from_save(copy.deepcopy(snapshot))
        # A restart first fades out while the old step can still be ready. Wait
        # for teardown before accepting the rebuilt step with the same key.
        self.wait(lambda: self.g.story.cur is None, "reload teardown")
        self.wait(lambda: self.g.story.cur == target and self.bot.ready(), f"reload at {target}")

    def buy(self, key, fail=False):
        """Intercept the real menu's callback, then invoke exactly what its button would."""
        g = self.g
        callbacks = {}
        original = g.ui.open_shop

        def capture(title, entries, clovers, on_buy, on_close):
            callbacks.update(buy=on_buy, close=on_close)
            return original(title, entries, clovers, on_buy, on_close)

        with patch.object(g.ui, "open_shop", side_effect=capture):
            if g.story.cur == "d6_prep":
                self.bot.choice_queue = [1]  # Browse the shop after the board-help offer.
            g.interact(g.ia.get("cow_mooriarty"))
            self.wait(lambda: "buy" in callbacks, "shop menu")
            before = {
                "clovers": g.clovers(), "inventory": g.inv.to_dict(),
                "profile": copy.deepcopy(g.moodals.data), "bought": g.stats.get("bought", 0),
                "applied": list(g.flags.get("_purchases", [])),
            }
            if fail:
                g._save_error_at = -100.0
                with patch("breakowt.moodals.write_json", side_effect=OSError("simulated full disk")), \
                        patch.object(g.ui, "toast", wraps=g.ui.toast) as toast:
                    callbacks["buy"](key)
                    self.check.assertTrue(any("Couldn't save" in str(call.args) for call in toast.call_args_list))
                self.check.assertEqual(g.clovers(), before["clovers"])
                self.check.assertEqual(g.inv.to_dict(), before["inventory"])
                self.check.assertEqual(g.moodals.data, before["profile"])
                self.check.assertEqual(g.stats.get("bought", 0), before["bought"])
                self.check.assertEqual(g.flags.get("_purchases", []), before["applied"])
            else:
                callbacks["buy"](key)
                price = 6 if key == "shells" else 2
                self.check.assertEqual(g.clovers(), before["clovers"] - price)
            callbacks["close"]()
        self.wait(self.bot.ready, "shop close")

    def purchases(self):
        g = self.g
        self.reach_step(6, "d6_prep")
        g.moodals.data["purse"]["found"] = 100
        self.check.assertTrue(g.moodals.save())
        old = copy.deepcopy(g.load_save())
        self.check.assertEqual(g.inv.count("shells"), 0)
        self.buy("shells")
        self.check.assertEqual(g.inv.count("shells"), 2)
        self.check.assertEqual(g.load_save()["inv"]["items"].get("shells", 0), 0)
        g.moodals.load()  # Receipts must survive reading the profile back from disk.
        self.reload(old, "d6_prep")
        self.check.assertEqual(g.inv.count("shells"), 2)
        self.buy("shells")
        self.check.assertEqual(g.inv.count("shells"), 4)
        self.reload(old, "d6_prep")
        self.check.assertEqual(g.inv.count("shells"), 4)
        self.check.assertEqual(len(g.flags["_purchases"]), 2)
        g.inv.remove("shells")
        self.check.assertTrue(g.save_checkpoint())
        consumed = copy.deepcopy(g.load_save())
        self.reload(consumed, "d6_prep")
        self.check.assertEqual(g.inv.count("shells"), 3)
        self.check.assertEqual(len(g.flags["_purchases"]), 2)
        print("OK: purchased shells survive old checkpoints and are delivered once", flush=True)

        before_coffee = copy.deepcopy(g.load_save())
        self.buy("coffee")
        self.check.assertTrue(g.flags.get("coffee"))
        self.reload(before_coffee, "d6_prep")
        self.check.assertTrue(g.flags.get("coffee"))
        self.check.assertEqual(g.flags.get("_coffee_day"), 6)
        self.check.assertTrue(g.save_checkpoint())
        self.reload(g.load_save(), "d6_prep")
        self.check.assertTrue(g.flags.get("coffee"))
        self.buy("shells", fail=True)
        print("OK: failed purchase preserves clovers, receipts, and inventory and shows a notice", flush=True)

        from breakowt.engine.assets import SAVE_DIR
        checkpoint_bytes = (SAVE_DIR / "save.json").read_bytes()
        g._save_error_at = -100.0
        with patch("breakowt.game.write_json", side_effect=OSError("simulated checkpoint failure")), \
                patch.object(g.ui, "toast", wraps=g.ui.toast) as toast:
            self.check.assertFalse(g.save_checkpoint())
            self.check.assertTrue(any("Couldn't save progress" in str(call.args) for call in toast.call_args_list))
        self.check.assertEqual((SAVE_DIR / "save.json").read_bytes(), checkpoint_bytes)
        print("OK: failed checkpoint keeps the previous save and shows a notice", flush=True)

        g.story.start_day(7)
        self.wait(lambda: g.day == 7, "next day")
        self.check.assertFalse(g.flags.get("coffee"))
        self.check.assertNotIn("_coffee_day", g.flags)
        self.reach_step(6, "d6_prep")
        self.check.assertEqual(g.inv.count("shells"), 0)
        self.check.assertFalse(g.flags.get("coffee"))
        print("OK: coffee survives same-day reloads, expires next day; consumables stay within their run", flush=True)

    def saturday_milestones(self):
        g = self.g
        self.run_plan(self.bot.interact("woodpile"))
        self.check.assertEqual(g.load_save()["flags"].get("pile_taken"), 1)
        self.check.assertEqual(g.load_save()["inv"]["items"].get("plank"), 1)
        self.run_plan(self.bot.interact("st_bridge_right_full", direct_ok=False))
        self.check.assertEqual(g.load_save()["flags"].get("planks_laid"), 1)
        self.check.assertEqual(g.load_save()["flags"]["bridge_layout"]["long"]["slot"], "right_full")
        self.run_plan(self.bot.interact("herd_0"))
        self.wait(self.bot.ready, "herd conversation")
        partial = copy.deepcopy(g.load_save())
        self.check.assertEqual(partial["flags"].get("rallied"), [0])
        self.check.assertFalse(partial["flags"].get("d6_prep"))
        self.reload(partial, "d6_prep")
        self.check.assertEqual(g.flags.get("pile_taken"), 1)
        self.check.assertEqual(g.flags.get("planks_laid"), 1)
        self.check.assertEqual(g.flags.get("rallied"), [0])
        self.check.assertEqual(g.inv.count("plank"), 0)
        self.check.assertTrue(any("1/3 planks" in o["text"] for o in g.objectives))
        self.check.assertTrue(any("1/5" in o["text"] for o in g.objectives))
        print("OK: Saturday's partial plank and herd milestones rebuild after reload", flush=True)

    def monday_milestone(self):
        g = self.g
        self.reach_step(1, "d1_crew")
        self.run_plan(self.bot.talk_to("moozart"))
        partial = copy.deepcopy(g.load_save())
        self.check.assertEqual(partial["flags"].get("d1_told"), ["moozart"])
        self.check.assertFalse(partial["flags"].get("d1_crew"))
        self.reload(partial, "d1_crew")
        self.check.assertEqual(g.flags.get("d1_told"), ["moozart"])
        self.check.assertTrue(g.is_done("t_moozart"))
        self.check.assertTrue(any("1/5" in o["text"] for o in g.objectives))
        print("OK: Monday's partial introductions rebuild after reload", flush=True)

    def recoverable_items(self):
        g = self.g
        self.reach_step(2, "d2_radio")
        self.check.assertTrue(g.inv.has("glasses"))
        self.check.assertTrue(g.inv.has("radio"))
        self.bot.place(-42, -35, 0)
        g.inv.select_key("radio")
        g.input("q")
        self.check.assertFalse(g.inv.has("radio"))
        self.check.assertIsNotNone(g.story.radio_on)
        self.check.assertIsNotNone(g.ia.get("st_radio_on"))
        self.run_plan(self.bot.talk_to("cowpernicus"))
        favor = copy.deepcopy(g.load_save())
        self.check.assertTrue(favor["flags"].get("sq_specs"))
        self.check.assertFalse(favor["flags"].get("d2_radio"))
        self.check.assertEqual(favor["inv"]["items"].get("radio"), 1)
        self.check.assertFalse(g.inv.has("radio"))  # Saving must not put it in two places during play.
        self.reload(favor, "d2_radio")
        self.check.assertEqual(g.inv.count("radio"), 1)
        self.check.assertIsNone(g.story.radio_on)
        self.check.assertIsNone(g.ia.get("st_radio_on"))
        self.run_plan(self.bot.p_d2_radio())
        self.wait(lambda: g.story.cur == "d2_ram" and self.bot.ready(), "restored radio puzzle finishes")
        print("OK: favor checkpoint recovers the placed radio and Tuesday's puzzle still finishes", flush=True)

        self.bot.place(-42, -35, 0)
        g.inv.select_key("cowbell")
        g.input("q")
        self.check.assertFalse(g.inv.has("cowbell"))
        self.check.assertTrue(any(p.alive and p.kind == "cowbell" for p in g.player.projectiles))
        self.check.assertTrue(g.save_checkpoint())
        airborne = copy.deepcopy(g.load_save())
        self.check.assertEqual(airborne["inv"]["items"].get("cowbell"), 1)
        self.check.assertFalse(g.inv.has("cowbell"))
        self.reload(airborne, "d2_ram")
        self.check.assertEqual(g.inv.count("cowbell"), 1)
        self.check.assertEqual(g.player.projectiles, [])
        self.check.assertNotIn("dropped_cowbell", g.world.items)

        self.bot.place(-42, -35, 0)
        g.inv.select_key("cowbell")
        g.input("q")
        self.wait(lambda: "dropped_cowbell" in g.world.items, "cowbell lands")
        self.check.assertFalse(g.inv.has("cowbell"))
        self.check.assertTrue(g.save_checkpoint())
        dropped = copy.deepcopy(g.load_save())
        self.check.assertEqual(dropped["inv"]["items"].get("cowbell"), 1)
        self.check.assertFalse(g.inv.has("cowbell"))
        self.reload(dropped, "d2_ram")
        for _ in range(3 * FPS):
            self.tick()
        self.check.assertEqual(g.inv.count("cowbell"), 1)
        self.check.assertNotIn("dropped_cowbell", g.world.items)
        self.check.assertEqual(g.player.projectiles, [])
        print("OK: airborne and dropped reusable items recover once; stale projectiles do not create duplicates", flush=True)

        self.bot.place(-42, -35, 0)
        g.inv.select_key("radio")
        g.input("q")
        g.inv.select_key("cowbell")
        g.input("q")
        self.wait(lambda: "dropped_cowbell" in g.world.items, "cowbell before sleep")
        self.check.assertFalse(g.inv.has("radio"))
        self.check.assertFalse(g.inv.has("cowbell"))
        self.run_plan(self.bot.p_d2_ram())
        self.wait(lambda: g.story.cur == "d2_sleep" and self.bot.ready(), "Tuesday sleep step")
        self.run_plan(self.bot.p_d2_sleep())
        self.wait(lambda: g.day == 3 and g.story.cur == "d3_moohole" and self.bot.ready(), "natural Wednesday transition")
        self.check.assertEqual(g.inv.count("radio"), 1)
        self.check.assertEqual(g.inv.count("cowbell"), 1)
        self.check.assertIsNone(g.story.radio_on)
        self.check.assertNotIn("dropped_cowbell", g.world.items)
        self.check.assertEqual(g.player.projectiles, [])
        print("OK: natural day transition recovers placed radio and dropped reusable items", flush=True)

        self.run_plan(self.bot.interact("st_boot"))
        self.check.assertTrue(g.inv.has("boot"))
        self.run_plan(self.bot.interact("moohole"))
        self.wait(lambda: g.story.cur == "d3_barn" and self.bot.ready(), "boot wedges the wire")
        consumed = copy.deepcopy(g.load_save())
        self.check.assertTrue(consumed["flags"].get("moohole_open"))
        self.check.assertFalse(consumed["inv"]["items"].get("boot"))
        self.reload(consumed, "d3_barn")
        self.check.assertFalse(g.inv.has("boot"))
        self.check.assertIsNone(g.ia.get("st_boot"))
        print("OK: a boot consumed by the fence puzzle is not recovered", flush=True)

        self.bot.place(-42, -35, 0)
        g.inv.select_key("radio")
        g.input("q")
        g.inv.select_key("cowbell")
        g.input("q")
        self.check.assertIsNotNone(g.story.radio_on)
        self.check.assertTrue(any(p.alive and p.kind == "cowbell" for p in g.player.projectiles))
        self.reach_step(1, "d1_crew")
        self.check.assertFalse(g.inv.has("radio"))
        self.check.assertFalse(g.inv.has("cowbell"))
        self.check.assertIsNone(g.story.radio_on)
        self.check.assertIsNone(g.ia.get("st_radio_on"))
        self.check.assertNotIn("dropped_cowbell", g.world.items)
        self.check.assertEqual(g.player.projectiles, [])
        print("OK: starting a new game does not inherit the previous run's world items", flush=True)


def main():
    with tempfile.TemporaryDirectory(prefix="breakowt-persistencecheck-") as folder:
        os.environ.setdefault("BREAKOWT_SAVE_DIR", folder)
        app, g = harness.boot(size=(640, 360))
        try:
            test = PersistenceCheck(app, g)
            test.purchases()
            test.saturday_milestones()
            test.monday_milestone()
            test.recoverable_items()
            print("OK: persistence checks passed", flush=True)
        finally:
            g.runner.stop_all()
            from ursina import application
            application.base.destroy()


if __name__ == "__main__":
    main()
