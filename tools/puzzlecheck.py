"""Exercise rendered farm puzzles, actual targeting/NPC movement, reloads and teardown.

Use the same isolated/offscreen boot wrapper as the walkthrough on desktop systems.
"""
from __future__ import annotations

import copy
import math
import os
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import harness
from persistencecheck import PersistenceCheck
from walkthrough import FPS


class PuzzleCheck(PersistenceCheck):
    def frames(self, n=2):
        for _ in range(n):
            self.tick()

    def fresh(self):
        self.reach_step(6, "d6_prep")
        self.g.farmer.trip_rate = 0
        self.bot.place(10,18,y=0)
        self.frames()
        return self.g.story.farm_puzzles

    def nudge(self, key, dx, dz, count):
        pb=self.g.world.pushables[key]
        for _ in range(count):
            self.check.assertTrue(pb.nudge(dx,dz), f"{key} could not move {dx},{dz} from {pb.x},{pb.z}")
            self.frames(12)

    def counterweight(self):
        g=self.g
        puzzles=self.fresh()
        self.bot.place(3,18,y=0)
        self.frames()
        self.check.assertTrue(puzzles.weight_gate.is_open)
        self.bot.place(10,18,y=0)
        self.frames()
        self.check.assertFalse(puzzles.weight_gate.is_open)
        self.nudge("st_weight_crate",0,1,7)
        self.check.assertTrue(puzzles.weight_gate.is_open)
        self.bot.place(7.5,14,y=0)
        self.bot.face((3,1,20))
        self.bot.shot("counterweight_overview")
        self.run_plan(self.bot.interact("st_weight_reset",direct_ok=False))
        self.check.assertFalse(puzzles.weight_gate.is_open)
        self.bot.place(10,18,y=0)
        self.nudge("st_weight_bag_a",1,0,6)
        self.check.assertFalse(puzzles.weight_gate.is_open)
        self.nudge("st_weight_bag_b",1,0,6)
        self.check.assertTrue(puzzles.weight_gate.is_open)
        puzzles.reset_weights()
        self.bot.place(10,18,y=0)
        self.frames()
        self.bot.choice_queue=[1]
        self.run_plan(self.bot.talk_to("cowpernicus"))
        self.bot.place(10,18,y=0)
        self.wait(lambda:puzzles.helper and math.hypot(puzzles.helper.x-3,puzzles.helper.z-18)<.9,
                  "Moothagoras actually walks onto the plate",seconds=180)
        self.frames()
        self.check.assertTrue(puzzles.weight_gate.is_open)
        self.bot.place(3,22,y=0)
        self.bot.face(g.ia.get("st_escape_rope").world_pos())
        self.frames(4)
        self.check.assertIs(g.target,g.ia.get("st_escape_rope"))
        g.input("e")
        self.frames()
        self.check.assertTrue(g.inv.has("escape_rope"))
        self.check.assertTrue(g.flags["escape_rope_taken"])
        self.check.assertFalse(puzzles.take_rope() if not g.ia.get("st_escape_rope").enabled else True)
        self.bot.shot("counterweight_store")
        print("OK: player, heavy crate, two sacks and a walking cow operate the actual counterweight gate",flush=True)
        snapshot=copy.deepcopy(g.load_save())
        self.reload(snapshot,"d6_prep")
        self.check.assertEqual(g.inv.count("escape_rope"),1)
        self.check.assertFalse(g.ia.get("st_escape_rope").enabled)

    def cabinet(self):
        g=self.g
        puzzles=self.fresh()
        g.farmer.teleport((26,0,17))
        g.farmer.set_routine([("wait",1000,"look")])
        self.check.assertFalse(puzzles.take_latch())
        self.run_plan(self.bot.interact("st_grain_hopper",direct_ok=False))
        self.bot.place(41,17,y=0)
        self.wait(lambda:puzzles.cabinet_open,"Chuck walks to and opens the cabinet",seconds=120)
        self.wait(lambda:g.farmer.tool=="wrench","Chuck enters and fetches the wrench",seconds=30)
        self.check.assertTrue(20 < g.farmer.z < 23.4)
        self.bot.place(39,16.3,y=0)
        self.bot.face((34,1.2,20))
        self.bot.shot("cabinet_overview")
        self.check.assertFalse(puzzles.take_latch())
        self.bot.choice_queue=[0]
        self.run_plan(self.bot.talk_to("sirloin"))
        self.check.assertTrue(g.flags.get("helper_distraction"))
        self.check.assertEqual(g.farmer.state,"investigate")
        self.check.assertIsNotNone(g.farmer.inv_target)
        self.check.assertAlmostEqual(g.farmer.inv_target[0],g.cows["sirloin"].x,places=1)
        self.check.assertTrue(g.inv.has("radio"))
        self.bot.place(42,19,y=0)
        self.check.assertTrue(g.story.radio_use("radio"))
        self.bot.place(35,19,y=0)
        self.wait(lambda:math.hypot(g.farmer.x-35,g.farmer.z-21.4)>=4.5,
                  "radio draws Chuck away from unlocked kit",seconds=45)
        self.check.assertTrue(puzzles.cabinet_open)
        self.bot.place(35,20.7,y=0)
        self.bot.face(g.ia.get("st_latch_kit").world_pos())
        self.frames(4)
        self.check.assertIs(g.target,g.ia.get("st_latch_kit"))
        g.input("e")
        self.frames()
        self.check.assertTrue(g.inv.has("latch_kit"))
        self.check.assertFalse(puzzles.take_latch())
        self.bot.shot("tool_cabinet")
        snapshot=copy.deepcopy(g.load_save())
        self.reload(snapshot,"d6_prep")
        self.check.assertEqual(g.inv.count("latch_kit"),1)
        self.check.assertFalse(g.ia.get("st_latch_kit").enabled)
        print("OK: Chuck unlocks and fetches a visible wrench; radio permits theft, receipt survives reload",flush=True)

        puzzles=self.fresh()
        self.bot.place(40,26,y=0)
        self.check.assertFalse(puzzles.take_latch(hatch=True))
        self.nudge("st_service_crate",0,-1,3)
        pb=g.world.pushables["st_service_crate"]
        self.bot.place(pb.x,pb.z,y=pb.h)
        self.bot.face(g.ia.get("st_service_hatch").world_pos())
        self.frames(4)
        self.check.assertIs(g.target,g.ia.get("st_service_hatch"))
        g.input("e")
        self.frames()
        self.check.assertTrue(g.inv.has("latch_kit"))
        self.check.assertFalse(puzzles.cabinet_open)
        print("OK: moving/climbing the real service crate reaches the alternate hatch",flush=True)

    def helpers(self):
        g=self.g
        self.fresh()
        self.bot.choice_queue=[0]
        self.run_plan(self.bot.talk_to("mooriarty"))
        self.check.assertEqual(g.inv.count("plank"),1)
        self.check.assertTrue(g.flags.get("helper_supply"))
        self.bot.choice_queue=[0]
        self.run_plan(self.bot.talk_to("mooriarty"))
        self.check.assertEqual(g.inv.count("plank"),1)
        self.bot.choice_queue=[0]
        self.run_plan(self.bot.talk_to("moomaw"))
        self.check.assertTrue(g.flags.get("helper_rally"))
        self.check.assertEqual(len(g.flags.get("rallied",[])),2)
        self.check.assertTrue(any("2/5" in objective["text"] for objective in g.objectives))
        self.bot.choice_queue=[0]
        self.run_plan(self.bot.talk_to("moomaw"))
        self.check.assertEqual(len(g.flags.get("rallied",[])),2)
        print("OK: real character menus supply one board once and rally two herd cows with objective feedback",flush=True)

    def bridge(self):
        g=self.g
        puzzles=self.fresh()
        g.inv.add("plank",3,silent=True)
        self.bot.place(0,78,y=0)
        # Initial board deliberately points at the wrong support; count cannot unlock the crossing.
        self.run_plan(self.bot.interact("st_bridge_right_south",direct_ok=False))
        self.check.assertFalse(g.story.bridge_finished())
        self.check.assertTrue(g.world.colliders["cattle_grid"].enabled)
        self.check.assertEqual(g.flags["planks_laid"],1)
        partial=copy.deepcopy(g.load_save())
        self.reload(partial,"d6_prep")
        self.check.assertEqual(g.flags["bridge_layout"]["long"]["slot"],"right_south")
        self.check.assertEqual(g.inv.count("plank"),2)
        self.check.assertTrue(g.world.colliders["cattle_grid"].enabled)
        self.bot.choice_queue=[1]
        self.run_plan(self.bot.interact("st_bridge_right_south",direct_ok=False))
        self.wait(self.bot.ready,"occupied peg lifts the misplaced long board")
        self.check.assertNotIn("long",g.flags["bridge_layout"])
        self.check.assertEqual(g.inv.count("plank"),3)
        for peg in ("st_bridge_right_full","st_bridge_left_south","st_bridge_left_north"):
            self.run_plan(self.bot.interact(peg,direct_ok=False))
            self.wait(self.bot.ready,"board placement at "+peg)
        self.check.assertTrue(g.story.bridge_finished())
        self.bot.choice_queue=[0]
        self.run_plan(self.bot.interact("st_bridge_left_north",direct_ok=False))
        self.wait(self.bot.ready,"occupied peg turns the north board sideways")
        self.check.assertTrue(g.flags["bridge_layout"]["short_b"]["turned"])
        self.check.assertEqual(g.flags["planks_laid"],3)
        self.check.assertFalse(g.story.bridge_finished())
        self.check.assertTrue(g.world.colliders["cattle_grid"].enabled)
        self.bot.choice_queue=[0]
        self.run_plan(self.bot.interact("st_bridge_left_north",direct_ok=False))
        self.wait(self.bot.ready,"occupied peg turns the board back toward the road")
        self.check.assertFalse(g.flags["bridge_layout"]["short_b"]["turned"])
        self.check.assertFalse(g.ui.choice_root.enabled)
        self.check.assertTrue(g.story.bridge_finished())
        self.check.assertFalse(g.world.colliders["cattle_grid"].enabled)
        self.bot.place(0,79,y=0)
        self.bot.face((0,.1,82.5))
        self.bot.shot("supported_bridge")
        snapshot=copy.deepcopy(g.load_save())
        self.reload(snapshot,"d6_prep")
        self.check.assertTrue(g.story.bridge_finished())
        self.check.assertFalse(g.world.colliders["cattle_grid"].enabled)
        g.story.farm_puzzles.reset_bridge()
        self.check.assertEqual(g.inv.count("plank"),3)
        self.check.assertFalse(g.story.bridge_finished())
        self.check.assertTrue(g.world.colliders["cattle_grid"].enabled)
        print("OK: unsupported and rotated boards fail; supported reversible layout survives reload",flush=True)

    def cleanup(self):
        g=self.g
        puzzles=g.story.farm_puzzles
        shapes=list(puzzles.colliders)+[pb.col for pb,weight in puzzles.pushables]
        floors=[pb.floor for pb,weight in puzzles.pushables]
        interactions=list(puzzles.interactions)
        g.story.clear_farm_puzzles()
        self.check.assertFalse(puzzles.alive)
        self.check.assertFalse(any(shape in g.phys.shapes for shape in shapes))
        self.check.assertFalse(any(floor in g.phys.floors for floor in floors))
        self.check.assertFalse(any(g.ia.get(key) is not None for key in interactions))
        self.check.assertFalse(any(key.startswith("st_puzzle_") for key in g.story.props))
        self.check.assertFalse(any(key.startswith("st_weight_") for key in g.world.pushables))
        print("OK: teardown removes puzzle colliders, floors, doors, props and interaction targets",flush=True)


def main():
    with tempfile.TemporaryDirectory(prefix="breakowt-puzzlecheck-") as folder:
        os.environ.setdefault("BREAKOWT_SAVE_DIR",folder)
        app,g=harness.boot(size=(1200,800))
        try:
            check=PuzzleCheck(app,g)
            check.counterweight()
            check.cabinet()
            check.helpers()
            check.bridge()
            check.cleanup()
            print("OK: puzzle integration checks passed",flush=True)
        finally:
            g.runner.stop_all()
            from ursina import application
            application.base.destroy()


if __name__=="__main__":
    main()
