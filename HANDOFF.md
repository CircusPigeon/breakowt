# Handoff notes (for a future Claude Code session)

Read `docs/DESIGN.md` first — it is the full story/mechanics spec. This file tracks build status.

## Stack
- Python 3.13, Ursina 8.3 (Panda3D 1.10.16), numpy, scipy, Pillow (all already installed on this machine).
- All audio and textures are generated procedurally on first run into `assets/generated/` (gitignored).
- Windows at 200% display scaling: the process must be DPI-aware *before* `Ursina()` is created, and the
  window must be opened at its final size (see `breakowt/app.py`). Same fix as the Rush Hour project.
- Private repo: github.com/CircusPigeon/cow_game (push after each milestone).

## Status
- [ ] Audio synthesis (`breakowt/synth.py`)
- [ ] Texture generation (`breakowt/texgen.py`)
- [ ] Engine core: shader, mesh builder, physics, audio manager, script runner
- [ ] World + models
- [ ] Player controller, interaction, inventory
- [ ] Farmer AI (patrol, vision, noise, caught)
- [ ] NPC cows (friends + herd, escort)
- [ ] UI (HUD, dialogue, menus, documents, keypad, password, map)
- [ ] Story days 1–7, side quests
- [ ] Combat (rooster, boss), tractor driving
- [ ] Ending + credits
- [ ] Automated walkthrough test

## Run
```
python main.py            # fullscreen
python main.py --windowed # dev window
python main.py --day 3    # debug: start on Wednesday
```
