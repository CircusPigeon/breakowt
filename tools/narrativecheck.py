"""Engine-free narrative regression checks; the full walkthrough covers in-game integration.

    python tools/narrativecheck.py

Extract the actual generators from days.py so these checks need neither a window nor Ursina.
"""
from __future__ import annotations

import ast
import copy
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
CREW = ("moozart", "sirloin", "cowpernicus", "mooriarty", "moomaw")
source = ast.parse((ROOT / "breakowt" / "days.py").read_text(encoding="utf-8"))
scripts = next(n for n in source.body if isinstance(n, ast.ClassDef) and n.name == "DayScripts")
namespace = {"FRIENDS": {key: (key,) for key in CREW}}
methods = ast.Module(body=[n for n in scripts.body if isinstance(n, ast.FunctionDef)
                          and n.name in ("day1", "d1_crew", "chuck_verdict")], type_ignores=[])
exec(compile(methods, str(ROOT / "breakowt" / "days.py"), "exec"), namespace)


class Inventory:
    def __init__(self, shells=0):
        self.items = {"shells": shells}

    def count(self, key):
        return self.items.get(key, 0)

    def remove(self, key):
        self.items[key] -= 1


class Game:
    def __init__(self, shells=0, choice=0, flags=None):
        self.flags = copy.deepcopy(flags or {})
        self.inv = Inventory(shells)
        self.choice = choice
        self.choices = []
        self.lines = []
        self.events = []
        self.sounds = []
        self.busy = False
        self.audio = SimpleNamespace(play=lambda name, **kw: self.sounds.append(name), stop_everything=lambda: None)
        self.ui = SimpleNamespace(set_fade=lambda *args: None)
        self.player = SimpleNamespace(hold=lambda name: None)

    def say(self, who, text, choices=None, **kw):
        self.lines.append(text)
        self.choices.append(choices)
        yield None
        return self.choice

    def talk(self, lines):
        self.lines.extend(text for _, text in lines)
        yield None

    def end_talk(self):
        pass

    def event(self, name):
        self.events.append(name)

    def side_quest(self, key, text, state):
        self.flags.setdefault("_sq", {})[key] = {"text": text, "state": state}

    def complete(self, *args, **kw):
        pass


class CrewStory:
    CREW = CREW
    FRIEND_SPOTS = {key: (0, 0, 0) for key in CREW}

    def __init__(self, flags=None):
        self.g = Game(flags=flags)
        self.flags = self.g.flags
        self.hooks = {}
        self.saves = []
        self.idle = []

    def objectives(self, *args):
        pass

    def mark(self, *args):
        pass

    def hook(self, key, fn):
        self.hooks[key] = fn

    def setf(self, key, value=True):
        self.flags[key] = value

    def save_progress(self):
        self.saves.append(copy.deepcopy(self.flags))

    def idle_talk(self, key):
        self.idle.append(key)
        yield None

    def character_introduction(self, key):
        yield from self.g.talk([(key, "An introduction, with optional discussion.")])


class NarrativeChecks(unittest.TestCase):
    def verdict(self, shells, choice):
        g = Game(shells, choice)
        story = SimpleNamespace(g=g, setf=lambda key: g.flags.__setitem__(key, True))
        list(namespace["chuck_verdict"](story))
        return g

    def test_loaded_mercy_keeps_shells(self):
        g = self.verdict(2, 0)
        self.assertEqual(g.choices, [["Lower Ol' Bessie and leave", "Shoot Chuck"]])
        self.assertFalse(g.flags.get("chuck_shot"))
        self.assertEqual(g.inv.count("shells"), 2)
        self.assertNotIn("shotgun", g.sounds)
        self.assertTrue(any("Stay down and we'll call it even" in line for line in g.lines))

    def test_shoot_requires_choice_and_consumes_one_shell(self):
        g = self.verdict(2, 1)
        self.assertTrue(g.flags.get("chuck_shot"))
        self.assertEqual(g.inv.count("shells"), 1)
        self.assertEqual(g.events, ["chuck_shot"])
        self.assertEqual(g.sounds.count("shotgun"), 1)

    def test_empty_gun_cannot_offer_or_fire_a_shot(self):
        g = self.verdict(0, 1)
        self.assertEqual(g.choices, [])
        self.assertFalse(g.flags.get("chuck_shot"))
        self.assertEqual(g.inv.count("shells"), 0)
        self.assertNotIn("shotgun", g.sounds)

    def test_monday_stealth_precedes_introductions(self):
        order = []

        def step(key, *args, **kw):
            order.append(key)
            yield None

        story = SimpleNamespace(step=step, _run_day=lambda day: iter(()))
        for name in ("d1_wake", "d1_oak", "d1_page", "d1_pencil", "d1_crew", "d1_meeting", "sleep_step"):
            setattr(story, name, lambda: None)
        list(namespace["day1"](story))
        self.assertEqual(order, ["d1_wake", "d1_oak", "d1_page", "d1_pencil", "d1_crew", "d1_meeting", "d1_sleep"])

    def test_partial_introductions_save_rewards_and_resume_without_repeating(self):
        story = CrewStory()
        day = namespace["d1_crew"](story)
        next(day)
        list(story.hooks["talk:sirloin"]())
        list(story.hooks["talk:mooriarty"]())
        self.assertEqual(len(story.saves), 2)
        saved = story.saves[-1]
        self.assertEqual(saved["d1_told"], ["mooriarty", "sirloin"])
        self.assertEqual(saved["_sq"]["helm"]["state"], "active")
        self.assertTrue(saved["mooriarty_met"])
        self.assertFalse(saved.get("d1_crew"))
        day.close()

        resumed = CrewStory(saved)
        day = namespace["d1_crew"](resumed)
        next(day)
        list(resumed.hooks["talk:sirloin"]())
        self.assertEqual(resumed.idle, ["sirloin"])
        self.assertEqual(resumed.saves, [])
        day.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
