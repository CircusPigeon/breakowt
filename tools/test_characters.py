"""Engine-free checks for dialogue choices, callbacks, and actual preparation help."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("character_agency", ROOT / "breakowt" / "characters.py")
characters = importlib.util.module_from_spec(spec)
spec.loader.exec_module(characters)


class Game:
    def __init__(self, answers=()):
        self.flags = {}
        self.stats = {}
        self.answers = iter(answers)
        self.lines = []
        self.choices = []
        self.visits = []
        self.in_dialogue = False
        self.cows = {key: SimpleNamespace(goto=lambda point, speed, key=key:
                                         self.visits.append((key, point, speed)))
                     for key in characters.INTRODUCTIONS}
        self.herd = [SimpleNamespace(idx=i, x=-40 + i, z=-20 - i) for i in range(8)]

    def talk(self, lines):
        self.in_dialogue = True
        self.lines.extend(lines)
        yield None
        self.end_talk()

    def say(self, who, text, choices):
        self.in_dialogue = True
        self.choices.append(list(choices))
        yield None
        return next(self.answers, 0)

    def end_talk(self):
        self.in_dialogue = False


class Story(characters.CharacterAgency):
    def __init__(self, answers=()):
        self.g = Game(answers)
        self.flags = self.g.flags
        self.cur = "d6_prep"
        self.day = 6
        self.saves = 0
        self.saved_flags = []
        self.actions = []
        self.supplied = False
        self.refreshes = 0
        self._prep_refresh = self.refresh

    def setf(self, key, value=True):
        self.flags[key] = value

    def done(self, key):
        return bool(self.flags.get(key))

    def save_progress(self):
        import copy
        self.saves += 1
        self.saved_flags.append(copy.deepcopy(self.flags))

    def puzzle_help(self, key):
        self.actions.append(key)
        return True

    def bridge_hint(self, stance):
        self.actions.append(("hint", stance))
        return "The unsupported end needs a bearer."

    def bridge_supply(self):
        if self.supplied:
            return False
        self.supplied = True
        self.actions.append("board")
        return True

    def refresh(self):
        self.refreshes += 1


def run(gen):
    while True:
        try:
            next(gen)
        except StopIteration as result:
            return result.value


class CharacterChecks(unittest.TestCase):
    def test_all_stances_keep_every_introduction_available(self):
        for key in characters.INTRODUCTIONS:
            for answer, stance in enumerate(characters.STANCES):
                with self.subTest(cow=key, stance=stance):
                    story = Story((answer, 0))
                    run(story.character_introduction(key))
                    self.assertEqual(story.flags[f"_stance_{key}"], stance)
                    self.assertIn((key, characters.REPLIES[key][stance]), story.g.lines)
                    self.assertFalse(story.done(f"_argument_{key}"))
                    self.assertLessEqual(len(story.g.lines), 4)
                    self.assertFalse(story.g.in_dialogue)

    def test_argument_optional_and_stance_never_repeated_after_reload(self):
        story = Story((2, 1))
        run(story.character_introduction("cowpernicus"))
        self.assertTrue(story.done("_argument_cowpernicus"))
        self.assertFalse(story.g.in_dialogue)
        self.assertEqual(story.flags["_stance_cowpernicus"], "evidence")
        n = len(story.g.choices)
        self.assertFalse(run(story.offer_discussion("cowpernicus")))
        self.assertEqual(len(story.g.choices), n)

    def test_reaction_survives_save_and_new_context_remains_available(self):
        story = Story()
        story.g.stats["caught"] = 2
        self.assertTrue(run(story.character_reaction("sirloin")))
        restored = Story()
        restored.flags.update(story.flags)
        restored.g.stats.update(story.g.stats)
        self.assertFalse(run(restored.character_reaction("sirloin")))
        restored.g.stats["faints"] = 2
        self.assertTrue(run(restored.character_reaction("sirloin")))
        self.assertIn("sirloin:faints", restored.flags["_character_reactions"])

    def test_quiet_success_requires_actual_milestone_and_no_catches(self):
        story = Story()
        self.assertFalse(run(story.character_reaction("moozart")))
        story.flags["d2_out"] = True
        story.g.stats["caught"] = 1
        self.assertFalse(run(story.character_reaction("moozart")))
        story.g.stats["caught"] = 0
        self.assertTrue(run(story.character_reaction("moozart")))

    def test_inspection_changes_hint_and_moves_cow_without_solving_layout(self):
        story = Story()
        story.flags["bridge_layout"] = [[0, 0, 90]]
        story.flags["_stance_cowpernicus"] = "evidence"
        run(story.character_support("cowpernicus"))
        self.assertIn(("hint", "evidence"), story.actions)
        self.assertEqual(story.flags["bridge_layout"], [[0, 0, 90]])
        self.assertEqual(story.g.visits[0][0], "cowpernicus")

    def test_supply_is_once_and_distraction_uses_farm_system(self):
        story = Story()
        run(story.character_support("mooriarty"))
        run(story.character_support("mooriarty"))
        self.assertEqual(story.actions.count("board"), 1)
        run(story.character_support("sirloin"))
        self.assertIn("distraction", story.actions)
        self.assertTrue(story.done("helper_distraction"))

    def test_rally_stance_and_favour_change_actual_assistance(self):
        for stance, photo, expected in (("practical", False, 2), ("evidence", False, 2),
                                        ("challenge", False, 1), ("challenge", True, 2)):
            with self.subTest(stance=stance, photo=photo):
                story = Story()
                story.flags["_stance_moomaw"] = stance
                story.flags["sq_photo"] = photo
                run(story.character_support("moomaw"))
                self.assertEqual(len(story.flags["rallied"]), expected)
                self.assertEqual(story.refreshes, expected)
                self.assertTrue(story.g.visits)
                run(story.character_support("moomaw"))
                self.assertEqual(len(story.flags["rallied"]), expected)

    def test_rally_does_not_count_existing_cows_twice_or_exceed_target(self):
        story = Story()
        story.flags["rallied"] = [0, 1, 2, 3]
        run(story.character_support("moomaw"))
        self.assertEqual(story.flags["rallied"], [0, 1, 2, 3, 4])

    def test_rally_resumes_exact_targets_after_first_recruit_checkpoint(self):
        story = Story()
        run(story.character_support("moomaw"))
        first_save = story.saved_flags[0]
        self.assertEqual(first_save["rallied"], [0])
        self.assertEqual(first_save["_helper_rally_targets"], [0, 1])
        self.assertNotIn("helper_rally", first_save)
        restored = Story()
        restored.flags.update(first_save)
        run(restored.character_support("moomaw"))
        self.assertEqual(restored.flags["rallied"], [0, 1])
        self.assertEqual(len(restored.g.visits), 1)
        self.assertTrue(restored.done("helper_rally"))
        run(restored.character_support("moomaw"))
        self.assertEqual(restored.flags["rallied"], [0, 1])

    def test_support_menu_can_fall_through_to_ordinary_conversation(self):
        story = Story((1,))
        self.assertFalse(run(story.character_talk("sirloin")))
        self.assertEqual(story.actions, [])
        story.flags["latch_kit_taken"] = True
        story.cur = "d5_emails"
        self.assertFalse(run(story.character_talk("sirloin")))

    def test_relevant_puzzle_help_is_available_before_saturday(self):
        for key, action in (("sirloin", "distraction"), ("cowpernicus", "weight")):
            with self.subTest(cow=key):
                story = Story((0,))
                story.day = 3
                story.cur = "d3_tractor"
                self.assertTrue(run(story.character_talk(key)))
                self.assertIn(action, story.actions)

    def test_evidence_stance_exposes_observation_route_first(self):
        story = Story((0,))
        story.day = 3
        story.cur = "d3_tractor"
        story.flags["_stance_sirloin"] = "evidence"
        self.assertTrue(run(story.character_talk("sirloin")))
        self.assertEqual(story.g.choices[0][0], "Ask what Moogenes observed")
        self.assertTrue(story.done("helper_maintenance_hint"))
        self.assertNotIn("distraction", story.actions)
        self.assertTrue(any("service hatch" in text for _, text in story.g.lines))

    def test_puzzle_help_is_not_offered_on_sunday_when_puzzles_are_closed(self):
        story = Story()
        story.day = 7
        story.cur = "d7_out"
        self.assertFalse(run(story.character_talk("sirloin")))
        self.assertFalse(run(story.character_talk("cowpernicus")))
        self.assertEqual(story.g.choices, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
