"""Headless checks for optional gate preparation and its bounded combat support.

    python tools/test_fight_prep.py
"""
from __future__ import annotations

import ast
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from breakowt.escape import FightPreparation, RIG_HANDLE


class Inventory:
    def __init__(self, *items):
        self.items = {key: 1 for key in items}

    def has(self, key):
        return self.items.get(key, 0) > 0

    def remove(self, key):
        self.items[key] -= 1


class Cow:
    def __init__(self):
        self.x, self.y, self.z, self.yaw = (4, 0, 48, 20)
        self.visible = True
        self.path = []
        self.model = SimpleNamespace(animate=lambda *args: None)
        self.destination = None

    def teleport(self, pos, yaw=None):
        self.x, self.y, self.z = pos[:3]
        if yaw is not None or len(pos) == 4:
            self.yaw = yaw if yaw is not None else pos[3]
        self.path = []

    def set_visible(self, value):
        self.visible = value

    def bubble(self, *args):
        pass

    def _apply(self):
        pass

    def goto(self, pos, speed):
        self.destination = pos


class Boss:
    def __init__(self):
        self.hp = 8
        self.finished = False
        self.stuns = []

    def stun(self, *args):
        self.stuns.append(args)


class Story(FightPreparation):
    def __init__(self, flags=None, items=()):
        self.flags = copy.deepcopy(flags or {})
        self.saves = []
        self.builds = 0
        self.started = []
        self.stopped = []
        self.lines = []
        self.handlers = []
        self.rig = SimpleNamespace(handlers=[])
        self.quests = {}
        self.g = SimpleNamespace(
            inv=Inventory(*items),
            cows={"cowpernicus": Cow()},
            farmer=SimpleNamespace(x=-4, z=74, say=lambda *args, **kw: None),
            stats={},
            ui=SimpleNamespace(popup_sub=lambda *args: None, bark_line=lambda *args: None),
            audio=SimpleNamespace(play=lambda *args, **kw: None),
            runner=SimpleNamespace(start=lambda gen, **kw: self.started.append((gen, kw)),
                                   stop=lambda name: self.stopped.append(name)),
            examine=lambda text: self.lines.append(text),
            side_quest=lambda key, text, state: self.quests.__setitem__(key, state),
            on=self.on,
            ia=SimpleNamespace(get=lambda key: self.rig if key == "prep_gate_rig" else None),
            show_document=self.document,
            talk=self.talk,
        )

    def document(self, *args, **kw):
        yield None

    def on(self, *args, **kw):
        self.handlers.append((args, kw))
        self.rig.handlers.append(SimpleNamespace(scope=kw.get("scope", "step")))

    def talk(self, lines):
        self.lines.extend(text for _, text in lines)
        yield None

    def setf(self, key, value=True):
        self.flags[key] = value

    def save_progress(self):
        self.saves.append((copy.deepcopy(self.flags), copy.deepcopy(self.g.inv.items)))

    def _build_fight_prep(self):
        self.builds += 1


class FightPrepTests(unittest.TestCase):
    def test_investigation_requires_the_intake_ledger(self):
        s = Story()
        list(s._read_fight_prep(s.g))
        self.assertFalse(s.flags.get("gate_rig_clue"))
        self.assertFalse(s.saves)
        s.flags["ledger_read"] = True
        list(s._read_fight_prep(s.g))
        self.assertTrue(s.flags["gate_rig_clue"])
        self.assertEqual(s.quests["gate_support"], "active")
        self.assertEqual(len(s.saves), 1)
        list(s._read_fight_prep(s.g))
        self.assertEqual(len(s.saves), 1)

    def test_installation_needs_discovery_sketch_and_both_items(self):
        requirements = {"gate_rig_clue": True, "escort_route_sketch": True}
        for flags, items in (({}, ("escape_rope", "latch_kit")),
                             ({"gate_rig_clue": True}, ("escape_rope", "latch_kit")),
                             (requirements, ("escape_rope",)),
                             (requirements, ("latch_kit",))):
            with self.subTest(flags=flags, items=items):
                s = Story(flags, items)
                before = dict(s.g.inv.items)
                s._fit_gate_rig(s.g)
                self.assertFalse(s.prep_ready())
                self.assertEqual(s.g.inv.items, before)
                self.assertFalse(s.saves)

    def test_installed_rig_saves_consumption_and_cannot_charge_twice(self):
        s = Story({"gate_rig_clue": True, "escort_route_sketch": True}, ("escape_rope", "latch_kit"))
        s._fit_gate_rig(s.g)
        self.assertTrue(s.prep_ready())
        self.assertEqual(s.saves[0][1], {"escape_rope": 0, "latch_kit": 0})
        self.assertEqual(s.quests["gate_support"], "done")
        s._fit_gate_rig(s.g)
        self.assertEqual(len(s.saves), 1)
        s.begin_fight_prep(Boss())
        s._release_prep_charge(s.g)
        s._release_prep_charge(s.g)
        self.assertEqual(len(s.started), 1)

    def test_far_chuck_does_not_consume_the_charge(self):
        s = Story({"gate_rigged": True})
        s.begin_fight_prep(Boss())
        s.g.farmer.x, s.g.farmer.z = (8, 59)
        s._release_prep_charge(s.g)
        self.assertFalse(s._fight_prep["used"])
        self.assertFalse(s.started)

    def test_charge_visibly_moves_cow_then_gives_a_short_stun_without_damage(self):
        s, boss = Story({"gate_rigged": True}), Boss()
        s.begin_fight_prep(boss)
        c = s.g.cows["cowpernicus"]
        start = (c.x, c.z)
        fake_ursina = SimpleNamespace(time=SimpleNamespace(dt=0.125))
        with patch.dict(sys.modules, {"ursina": fake_ursina}):
            list(s._prep_charge(s._fight_prep))
        self.assertNotEqual((c.x, c.z), start)
        self.assertEqual(boss.stuns, [(2.4, "gate_charge", "ow")])
        self.assertEqual(boss.hp, 8)
        self.assertFalse(boss.finished)
        self.assertEqual(s.g.stats["gate_assists"], 1)

    def test_moving_clear_can_evade_charge(self):
        s, boss = Story({"gate_rigged": True}), Boss()
        s.begin_fight_prep(boss)
        fake_ursina = SimpleNamespace(time=SimpleNamespace(dt=0.125))
        with patch.dict(sys.modules, {"ursina": fake_ursina}):
            gen = s._prep_charge(s._fight_prep)
            next(gen)
            s.g.farmer.x, s.g.farmer.z = (8, 59)
            list(gen)
        self.assertFalse(boss.stuns)
        self.assertEqual(boss.hp, 8)

    def test_fight_restart_rearms_and_restores_cow(self):
        s = Story({"gate_rigged": True})
        c = s.g.cows["cowpernicus"]
        home = (c.x, c.y, c.z, c.yaw)
        boss = Boss()
        s.begin_fight_prep(boss)
        s._release_prep_charge(s.g)
        self.assertTrue(s._fight_prep["used"])
        s.end_fight_prep()
        self.assertEqual((c.x, c.y, c.z, c.yaw), home)
        self.assertIsNone(s._fight_prep)
        self.assertIn("prep_charge", s.stopped)
        s.begin_fight_prep(boss)
        self.assertFalse(s._fight_prep["used"])

    def test_finished_fight_cannot_activate_support(self):
        s, boss = Story({"gate_rigged": True}), Boss()
        s.begin_fight_prep(boss)
        boss.finished = True
        s._release_prep_charge(s.g)
        self.assertFalse(s.started)

    def test_retries_replace_combat_handler_and_preserve_inspection(self):
        s = Story({"gate_rigged": True})
        s.rig.handlers.append(SimpleNamespace(scope="day"))
        for _ in range(20):
            s.begin_fight_prep(Boss())
            self.assertEqual([h.scope for h in s.rig.handlers], ["day", "step"])
        s.end_fight_prep()
        self.assertEqual([h.scope for h in s.rig.handlers], ["day"])

    def test_sunday_keeps_fuse_tractor_and_boss_in_order(self):
        tree = ast.parse((ROOT / "breakowt" / "days.py").read_text(encoding="utf-8"))
        scripts = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DayScripts")
        day7 = next(n for n in scripts.body if isinstance(n, ast.FunctionDef) and n.name == "day7")
        ns = {}
        exec(compile(ast.Module(body=[day7], type_ignores=[]), "day7", "exec"), ns)
        order = []

        def step(key, *args, **kw):
            order.append(key)
            yield None

        dummy = SimpleNamespace(step=step, play_ending=lambda: iter(()))
        for name in ("d7_crow", "d7_fuse", "d7_tractor", "d7_boss"):
            setattr(dummy, name, lambda: None)
        list(ns["day7"](dummy))
        self.assertEqual(order, ["d7_crow", "d7_fuse", "d7_tractor", "d7_boss"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
