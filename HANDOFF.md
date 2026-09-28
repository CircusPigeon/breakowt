# Handoff notes (for a future Claude Code session)

Read `docs/DESIGN.md` first. It is the full story/mechanics spec. This file tracks build status.

## Stack
- Python 3.13, Ursina 8.3 (Panda3D 1.10.16), numpy, scipy, Pillow.
- All audio, textures and fonts are generated procedurally on first run (about a minute, with a
  progress bar) into `Documents/My Games/BREAKOWT/generated/` (falls back to `~/.breakowt/`).
  Saves (`saves/`) and F12 screenshots (`screenshots/`) live next to it. Bump `TEX_VERSION` in
  `texgen.py` or `AUDIO_VERSION` in `synth.py` to force a regenerate.
- Windows at 200% display scaling: the process is made DPI-aware *before* `Ursina()` is created, and the
  window is opened at its final size (`breakowt/engine/boot.py`). Not testable in the Linux cloud
  container, so check it on the real machine.
- Private repo: github.com/CircusPigeon/cow_game.

## Status
- [x] Audio synthesis (`breakowt/synth.py`)
- [x] Texture generation (`breakowt/texgen.py`)
- [x] Engine core: shader (wind sway, AO, water, shadow-mapped sun, tonemap), mesh builder, physics,
      audio manager, script runner
- [x] World + models
- [x] Player controller, interaction, inventory
- [x] Farmer AI (patrol, vision, noise, caught)
- [x] NPC cows (friends + herd, escort)
- [x] UI (HUD, dialogue, menus, documents, keypad, password, map, shop, settings)
- [x] Story days 1–7 (`days.py`), side quests, shop (`story.py`)
- [x] Combat (Cluck Norris, Chuck boss), tractor driving (`combat.py`, `vehicle.py`)
- [x] Ending + credits
- [x] Automated walkthrough test: every day passes (`tools/walkthrough.py`)

## Run
```
python main.py            # fullscreen
python main.py --windowed # dev window
python main.py --day 3    # start on Wednesday (with the flags a normal run would have)
python main.py --debug    # F5 skip step, F6 next day, F7 teleport to objective, F8 toggle Chuck's eyes, F9 print position
```

Controls: WASD walk, mouse look, Shift gallop, C/Ctrl sneak, Space hop, E interact, left click headbutt,
right click kick, R throw, Q use selected item, M moo, 1-9 / scroll wheel pick item, Tab/J journal + map,
H hint, Esc pause, F11 fullscreen, F12 screenshot. In the tractor: W/S throttle, A/D steer.

Settings (title screen or pause menu) has volume sliders, mouse sensitivity, invert Y, fullscreen and a
Shadows toggle (turn shadows off on weak GPUs).

## Code map
- `main.py` → `breakowt/app.py` (window, fonts, loading screen) → `game.py` (`Game`: state, input, update loop).
- `story.py`: title screen, day runner, step/hook system, checkpoints, conversations, shop, credits.
  Every story step is idempotent and records a flag; a checkpoint is the day plus flags plus inventory,
  and world state (doors, props, who's where) is rebuilt from flags at the start of each day
  (`apply_world_flags` in `days.py`).
- `days.py`: the seven days as generators, plus the in-game documents and idle chatter.
- `world.py`: terrain, buildings, props, colliders, zones, nav graph (`build_nav`, `find_path`).
- `player.py`, `farmer.py`, `npc.py`, `combat.py`, `vehicle.py`, `models.py`, `ui.py`, `items.py`.
- `engine/`: `shading.py` (GLSL), `meshbuilder.py`, `physics.py`, `audio.py`, `script.py`, `assets.py`, `boot.py`.

## Testing (headless, Linux)
The tools run the real game under Xvfb at a fixed 30 fps clock.
```
xvfb-run -a -s "-screen 0 1280x720x24" python tools/walkthrough.py --day 1 --to 7   # full playthrough bot
xvfb-run -a -s "-screen 0 1280x720x24" python tools/walkthrough.py --day 5 --to 5 --shots   # one day, screenshot per step
xvfb-run -a -s "-screen 0 1280x720x24" python tools/walkthrough.py --day 2 --to 2 --detect  # with Chuck's eyes on
xvfb-run -a -s "-screen 0 1280x720x24" python tools/walkthrough.py --day 1 --to 7 --caught all  # get caught once in every step
xvfb-run -a -s "-screen 0 1280x720x24" python tools/uishots.py   # every UI screen
xvfb-run -a -s "-screen 0 1280x720x24" python tools/smoke.py     # boot + title + a few seconds of day 1
python tools/navcheck.py                                           # nav graph connectivity
```
Screenshots go to `screenshots/` in the repo (gitignored). The walkthrough bot has one plan per story
step (`p_<step key>` in `tools/walkthrough.py`); a new step needs a new plan or the run fails with a
state dump when the step's time limit runs out.
