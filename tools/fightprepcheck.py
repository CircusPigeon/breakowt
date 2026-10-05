"""Exercise gate preparation, reloads and a real optional assist in Sunday's boss.

    python -B tools/fightprepcheck.py

Uses the standard harness and an isolated save folder. No player input is sent
to the desktop; Bot operates the game's interaction and control APIs.
"""
from __future__ import annotations

import copy
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness
from persistencecheck import PersistenceCheck
from walkthrough import FPS


class FightPrepCheck(PersistenceCheck):
    def preparation(self):
        g, bot = self.g, self.bot
        self.reach_step(6, "d6_prep")
        self.check.assertTrue(g.flags.get("escort_route_sketch"))
        self.check.assertFalse(g.story.prep_ready())
        self.run_plan(bot.interact("prep_gate_rig", direct_ok=False))
        self.check.assertFalse(g.flags.get("gate_rigged"))

        self.run_plan(bot.interact("ledger", direct_ok=False))
        self.wait(bot.ready, "intake ledger read")
        self.check.assertTrue(g.flags.get("ledger_read"))
        self.run_plan(bot.interact("prep_clipboard", direct_ok=False))
        self.wait(bot.ready, "maintenance clipboard read")
        self.check.assertTrue(g.flags.get("gate_rig_clue"))
        g.inv.add("escape_rope", silent=True)
        self.run_plan(bot.interact("prep_gate_rig", direct_ok=False))
        self.check.assertFalse(g.flags.get("gate_rigged"))
        self.check.assertEqual(g.inv.count("escape_rope"), 1)
        g.inv.add("latch_kit", silent=True)
        self.run_plan(bot.interact("prep_gate_rig", direct_ok=False))
        self.check.assertTrue(g.flags.get("gate_rigged"))
        self.check.assertEqual(g.inv.count("escape_rope"), 0)
        self.check.assertEqual(g.inv.count("latch_kit"), 0)
        snapshot = copy.deepcopy(g.load_save())
        self.check.assertTrue(snapshot["flags"].get("gate_rigged"))
        self.reload(snapshot, "d6_prep")
        self.check.assertTrue(g.story.prep_ready())
        self.check.assertIn("prep_gate_rig_prop", g.story.props)
        self.check.assertTrue(g.ia.get("prep_gate_rig").enabled)
        self.check.assertEqual(g.inv.count("escape_rope"), 0)
        self.check.assertEqual(g.inv.count("latch_kit"), 0)
        self.run_plan(bot.interact("prep_gate_rig", direct_ok=False))
        self.check.assertEqual(g.inv.count("escape_rope"), 0)
        print("OK: plant investigation and Thursday sketch unlock the rig; both rewards are consumed once and reload rebuilds it",
              flush=True)

    def reach_boss(self):
        g, bot = self.g, self.bot
        g.story.canon_day(6)
        bot.ending = "spare"
        g.story.start_day(7)
        self.wait(lambda: g.day == 7 and g.story.cur is None, "Sunday setup")
        plan, last = None, None
        for _ in range(400 * FPS):
            key = g.story.cur
            if key == "d7_boss" and bot.ready() and g.story.enemy is not None:
                return
            if key != last:
                last = key
                plan = bot.plan_for(key) if key and key != "d7_boss" else None
            if plan is not None:
                try:
                    next(plan)
                except StopIteration:
                    plan = None
            self.tick()
        raise AssertionError(f"Sunday did not reach the final fight; step={g.story.cur}")

    def assist(self):
        g, bot = self.g, self.bot
        boss = g.story.enemy
        self.check.assertIsNotNone(g.story._fight_prep)
        self.check.assertEqual(boss.hp, boss.MAX_HP)
        self.check.assertFalse(boss.finished)
        instructions = " ".join(str(g.ui.popup.text).split())
        self.check.assertIn("headbutt", instructions)
        self.check.assertIn("Gate rig", instructions)
        home = g.story._fight_prep["home"]
        g.farmer.teleport((-4.5, 0, 74.5), 270)
        boss.state, boss.t = "winded", 15
        g.cam_set((-11.5, 2.6, 79), (-7.0, 0.9, 74.5))
        bot.shot("fightprep_ready")
        g.cam_attach()
        hp, shells = boss.hp, g.inv.count("shells")
        assists = g.stats.get("gate_assists", 0)
        self.run_plan(bot.interact("prep_gate_rig", direct_ok=False))
        self.wait(lambda: g.cows["cowpernicus"].x > -10, "cow starts its charge", seconds=5)
        g.cam_set((-11.5, 2.6, 79), (-7.0, 0.9, 74.5))
        bot.shot("fightprep_charge")
        g.cam_attach()
        self.wait(lambda: g.stats.get("gate_assists", 0) == assists + 1, "the actual cow charge", seconds=10)
        self.check.assertEqual(boss.hp, hp)
        self.check.assertEqual(boss.state, "stunned")
        self.check.assertFalse(boss.finished)
        self.check.assertEqual(g.story.cur, "d7_boss")
        self.check.assertEqual(g.inv.count("shells"), shells)
        self.check.assertTrue(g.story._fight_prep["used"])
        self.run_plan(bot.interact("prep_gate_rig", direct_ok=False))
        self.check.assertEqual(g.stats.get("gate_assists", 0), assists + 1)

        # Use the real defeat callback, then verify its cleanup and restart.
        g.player.invuln = 0
        g.player.damage(g.player.max_health)
        self.wait(lambda: g.story._fight_prep is None, "defeat cleans up the assist", seconds=10)
        c = g.cows["cowpernicus"]
        self.check.assertAlmostEqual(c.x, home[0], delta=0.1)
        self.check.assertAlmostEqual(c.z, home[2], delta=0.1)
        self.wait(lambda: g.story._fight_prep is not None and bot.ready(), "fight restarts with an armed rig", seconds=15)
        self.check.assertFalse(g.story._fight_prep["used"])
        self.check.assertEqual(boss.hp, boss.MAX_HP)
        self.check.assertEqual(g.player.health, g.player.max_health)
        self.check.assertIn("Gate rig", " ".join(str(g.ui.popup.text).split()))
        h = g.ia.get("prep_gate_rig").active_handler(g)
        self.check.assertIn("charge", h.prompt)
        print("OK: E releases a visible cow charge for a brief stun, leaves boss HP unchanged, and defeat resets the support",
              flush=True)

        bot.run(7)
        self.check.assertTrue(g.flags.get("d7_fuse"))
        self.check.assertTrue(g.flags.get("d7_tractor"))
        self.check.assertTrue(g.flags.get("d7_boss"))
        self.check.assertTrue(g.flags.get("game_finished"))
        self.check.assertFalse(g.flags.get("chuck_shot"))
        self.check.assertIsNone(g.story._fight_prep)
        self.check.assertEqual(bot.ending_choice, 0)
        print("OK: the full final fight and original armed mercy choice still complete after preparation", flush=True)

        # The shooting choice uses the same real verdict generator. The full
        # walkthrough separately covers its post-fight epilogue.
        bot.ending = "shoot"
        bot.ending_choice = None
        before = g.inv.count("shells")
        self.check.assertGreater(before, 0)
        g.runner.start(g.story.chuck_verdict(), name="verdict_check")
        self.wait(lambda: not g.runner.running("verdict_check"), "original shooting verdict", seconds=30)
        self.check.assertEqual(bot.ending_choice, 1)
        self.check.assertTrue(g.flags.get("chuck_shot"))
        self.check.assertEqual(g.inv.count("shells"), before - 1)
        print("OK: the original shooting option remains available and spends exactly one shell", flush=True)


def main():
    with tempfile.TemporaryDirectory(prefix="breakowt-fightprepcheck-") as folder:
        os.environ.setdefault("BREAKOWT_SAVE_DIR", folder)
        app, g = harness.boot(size=(960, 540))
        try:
            test = FightPrepCheck(app, g)
            test.preparation()
            test.reach_boss()
            test.assist()
            print("OK: fight preparation checks passed", flush=True)
        finally:
            g.runner.stop_all()
            from ursina import application
            application.base.destroy()


if __name__ == "__main__":
    main()
