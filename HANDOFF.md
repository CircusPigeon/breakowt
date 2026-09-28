# Handoff notes (for a future Claude Code session)

Read `docs/DESIGN.md` first. It is the full story/mechanics spec. This file tracks build status.

## Stack
- Python 3.13, Ursina 8.3 (Panda3D 1.10.16), numpy, scipy, Pillow (`requirements.txt`; Ursina 8.3 needs
  Python 3.12+). `README.md` is the player-facing download/install/controls guide. Keep its controls table
  in step with `Game.input` when keys change.
- All audio, textures and fonts are generated procedurally on first run (about a minute, with a
  progress bar) into `Documents/My Games/BREAKOWT/generated/` (falls back to `~/.breakowt/`).
  Saves (`saves/`) and F12 screenshots (`screenshots/`) live next to it. Bump `TEX_VERSION` in
  `texgen.py` or `AUDIO_VERSION` in `synth.py` to force a regenerate.
- Windows at 200% display scaling: the process is made DPI-aware *before* `Ursina()` is created, and the
  window is opened at its final size (`breakowt/engine/boot.py`). Not testable in the Linux cloud
  container, so check it on the real machine.
- The player's machine: Windows 11 on a Snapdragon X (ARM64) laptop with a Qualcomm Adreno X1-85 GPU,
  2880x1920 panel at 200%. `python` is the Microsoft Store build (x64, runs under emulation). Graphics
  driver quirks here don't show up in the cloud's software renderer, so rendering changes need a run on
  this machine (see Testing).
- Private repo: github.com/CircusPigeon/cow_game. Work has happened both in a cloud session (branch
  `claude/upbeat-allen-m6ufzp`) and locally on `main`; they're linear, and `main` was fast-forwarded to
  the branch. Run `git fetch --all` and compare branches before starting.

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

### Latest round (player feedback)
- HUD: the stamina bar sits bottom-left (it used to collide with the hotbar on 3:2 / 16:10 screens), and
  `UI.relayout()` re-anchors edge-pinned HUD pieces when the window changes shape (fullscreen toggle).
- Chuck in bed: `BED_SLEEP` / `BED_GETUP` in `days.py`. The "sleep" pose lays him out along +z from his
  feet, 0.8 m up; boots to nightcap he's 2.7 m long lying down, so his feet go at z 45.1 to keep the cap
  off the headboard. The quilt over him (`World.fit_bed_covers`) is built the first time he lies down:
  a height field over the mattress lifted over each of his parts' bounding boxes with a soft fall-off,
  ending below the shoulders with a turned-down sheet. `Farmer.update` shows it while he's asleep in bed. Stirring uses the `sleep_look` pose (head turns
  on the pillow) instead of standing him up in the bed.
- Light sleeper (`farmer.py`: `_hear_asleep`, `_disturbance`, `get_up`, `back_to_bed`): noises inside the
  house add to `drowse`; a thrown item, a moo, the radio, the toilet or a gunshot wakes him outright,
  about three galloping strides do too, a door or the nightstand drawer just makes him stir (the drawer
  is silent if you're sneaking). Stirring, his eyes open after half a second. Fully awake he gets up at
  `BED_GETUP` with the flashlight and the bedroom/hall lights on, investigates, then walks back to bed
  (`tobed` state) and the lights go off. Only in bed with a `getup` spot; the porch nap only stirs.
- Doors left open (`Farmer._check_doors`): a door the player opened (`Door.player_opened`, set in
  `DayScripts._toggle_door`) that Chuck then sees while awake makes him suspicious (a line, the "?" and
  the meter at 0.45), and he walks over and shuts it. Doors opened by story scripts don't count.
- Cows glowing at night: the herd's merged far-LOD mesh (`_merged_copy` in `npc.py`) copied the part's
  whole net ShaderAttrib, which snapshots every scene-wide input (sun, ambient, fog, lamps). A copy made by
  day kept daylight after dark. It now takes just the shader plus the per-entity inputs.
- Boss fight (`ChuckBoss` in `combat.py`, `d7_boss` in `days.py`): Chuck has 6 HP and the bar empties
  exactly when he goes down (it used to hand over to the finale at 4 of 12, so the bar sat at a third);
  longer openings (windup 0.95 s, stuck 3.2 s, winded every 2 throws for 3.5 s). Still 3 hearts (the
  player asked to keep it at 3). Losing resets the whole fight (Chuck to full, your shells back).
- Ol' Bessie fires: Q with the shotgun selected (`Game.fire_shotgun`). Two shells (`flags["shells"]`, set
  when you take her from the cabinet and in the chapter-select preset). 3 damage and knocks Chuck flat
  whatever state he's in; a big noise (radius 60) anywhere else, so firing in the house wakes Chuck.
- Credits: hold Space/E/Enter/click to fast-forward. The roll used to read the "advance" latch that any
  earlier key press left on, so it flew past in seconds.
- Earlier this round: farmhouse furnished room by room; TV and ChuckOS screens; the moo-hole wire sags
  and is held up by the boot; grass/flowers no longer grow through floors; porch roof no longer pokes
  into the living room; hotbar deselect (press the selected number again); the held item follows removals.

### Windows-machine round (local session, after the cloud round above)
- Black screen after loading: Continue resumed past a day's opening step, and that step owns the fade-in,
  so the screen stayed black. Fixed in b4ddd90 (see its message); verified on the real machine: New game
  and Continue both fade in, and `--resume` passes for days 1-2.
- `gpuprobe` (signature `probe3`) now also fails a feature if the probe frame comes out black, not only if
  the child process crashes: a driver can break the offscreen path without crashing. This machine reads
  ~134/255, the cutoff is 2.
- `main.py` and the test harness set `sys.dont_write_bytecode`: the user doesn't want `__pycache__` in the
  project. Test screenshots go to `Documents/My Games/BREAKOWT/test_screenshots/` (override with
  `BREAKOWT_TEST_SHOTS`), not the repo. Tests save to a temp folder (`BREAKOWT_SAVE_DIR`), never over the
  player's save.
- Earlier on this machine: the title menu's click areas fill the gaps and the highlight follows the
  cursor (measured live in fullscreen); Continue only appears once a story step is done; the sound pass
  (mastered loudness per category, 36-100 s music, positional farm ambience, slide whistle/bonk) is
  waiting on the player's ears.

### Freeplay round: Moo-dals and a farm that answers back
- `moodals.py`: 25 achievements for freeplay (moo 50 times, make Chuck trip, knock over every prop, get the
  herd to moo back, a day without being caught, find the bathroom mirror, ...). Each pays Golden Clovers
  into the current run (Mooriarty's shop). Progress is a profile, `saves/moodals.json`, separate from the
  checkpoint save, so it carries across playthroughs and survives reloads. UI: banner on unlock
  (`UI.moodal_banner`, queued), list screen `UI.open_moodals` from the pause menu and the title screen,
  a count in the journal and a line plus a rank in the credits.
- `Game.event(name, **kw)` is the hook: the player (moo, hop, step), farmer (chuck_trip, dale), game
  (interact, knock, clover, caught, noise) and story (day_start, herd_talk) call it; `Moodals.on_event` and
  `Life.on_event` listen. It swallows exceptions from those two: decoration never breaks the story. To add
  a Moo-dal: a row in `MOODALS`, a `GOALS`/`SET_GOALS` entry or an `unlock()` in `on_event`.
- `life.py`: birds (8 spots, ground and perched; scatter when you come close, gallop or make a noise; only
  near the player and by day), butterflies by day, fireflies at night, water rings ahead of you when you
  wade (and around herd cows in the pond), dust when Chuck runs, hoofprints in the mud (fade after a
  minute). Moo and the herd moos back; after dark the frogs (near the pond) and the owl (north of the
  cowshed) answer; the frogs hush when you walk up. A thrown thing that hits Chuck makes him yelp and
  come looking (`Life.check_chuck_hit`, outside the boss fight); he rights knocked-over props he walks up
  to. Headbutting Cardboard Chuck spins him. Cost measured on this laptop: ~0.8 ms/frame by day,
  ~0.3 ms at night (fireflies and butterflies use Panda's `setPos`/`setH` directly; Ursina's property
  setters were the expensive part).
- Herd cows you lean on step sideways out of your path (`HerdCow.update`, `_shoved`). Two cows standing
  shoulder to shoulder used to wall off the escort route for the bot, and are annoying for a player too.
- Audio v9 adds `moodal`, `bird_flutter`, `frog_chorus`, `owl_hoot`.

### Verified
- Freeplay round, on the Windows machine: `--day 1 --to 7 --detect` passes; a scratch test mooed at the
  herd (answers), scattered a flock, hit Chuck with a rock (yelp, investigate, Moo-dal), watched him tidy a
  knocked prop, waded (rings), got the frogs to answer at night, and opened the Moo-dals screen.
- On the Windows machine (build 1a72578 + this round): `--day 1 --to 7 --detect` (passed, including a
  real catch and the shotgun hit), `--day 1 --to 2 --resume`, fullscreen title at 2880x1920, New game and
  Continue from the title.
- `--day 1 --to 7` (the boss plan fires the shotgun once and checks it lands), `--resume` for days 5-7,
  `--day 6 --to 6 --caught all --detect`. The bot sneaks for the nightstand drawer, and if it's caught for
  real (not on purpose) it waits for the catch to play out and restarts the step's plan.
- Boss: a scratch test shot him (6 -> 3 HP, knocked flat, 1 shell left), lost the fight, and got Chuck
  back at 6/6, phase 1, full hearts and 2 shells; the bar hits 0 exactly when he goes down.
- Credits with a stale key press: about 110 s including the epilogue (it used to be a few seconds).
- Chuck: rock in the living room -> gets up, investigates, back to bed under the quilt; galloping in the
  house wakes him after a few strides; a front door left open gets noticed and shut.
- Full `--day 1 --to 7 --caught all --detect` passed after the drawer fix.

## Run
```
python main.py            # fullscreen
python main.py --windowed # dev window
python main.py --day 3    # start on Wednesday (with the flags a normal run would have)
python main.py --debug    # F5 skip step, F6 next day, F7 teleport to objective, F8 toggle Chuck's eyes, F9 print position
```

Controls: WASD walk, mouse look, Shift gallop, C/Ctrl sneak, Space hop, E interact, left click headbutt,
right click kick, R throw, Q use selected item (fires Ol' Bessie), M moo, 1-9 / scroll wheel pick item (press its number again to put it away), Tab/J journal + map,
H hint, Esc pause, F11 fullscreen, F12 screenshot. In the tractor: W/S throttle, A/D steer.

Settings (title screen or pause menu) has volume sliders, mouse sensitivity, invert Y, fullscreen and
Graphics: Low / Medium (default) / High.

## Rendering and performance
- The 3D scene is drawn into an offscreen buffer (`engine/postfx.py`) and put on screen by one pass that
  does FXAA, plus a light sharpen when upscaling. The UI draws on top at full resolution. The Graphics
  preset (`QUALITY` in `game.py`) caps the scene's height: Low 720 px, Medium 1080 px, High native with
  4x MSAA. On a high-DPI laptop panel this is the biggest saving.
- Sun shadows: our own depth map (packed into an RGBA8 texture, compared by hand in the shader). No
  `sampler2DShadow` / `p3d_LightSource`, which crashed the Adreno driver on Windows on ARM. Low has none;
  Medium uses a 1024 map redrawn every other frame; High 2048, every frame.
- The main shader has no `discard` (alpha test): all world textures are opaque, and a discard turns off
  early depth rejection for everything using the shader, which costs a lot on tile-based mobile GPUs.
- Herd cows beyond `herd_lod` metres switch to a merged one-piece copy of their model (1 draw call instead
  of 8). Ursina's per-frame mouse picking is skipped while the cursor is locked.
- `engine/gpuprobe.py` checks once, in child processes, that shadows and the offscreen buffer render
  without crashing and without coming out black, and caches the answer in `gpu.json`
  (`Documents/My Games/BREAKOWT/gpu.json`; delete it to re-check). `BREAKOWT_SHADOWS=0/1` and
  `BREAKOWT_POSTFX=0/1` override the check. The probe opens a tiny real window for a second: offscreen
  buffers never reach the failing driver path, so an offscreen probe passes when the real game wouldn't.

## Code map
- `main.py` → `breakowt/app.py` (window, fonts, loading screen) → `game.py` (`Game`: state, input, update loop).
- `story.py`: title screen, day runner, step/hook system, checkpoints, conversations, shop, credits.
  Every story step is idempotent and records a flag; a checkpoint is the day plus flags plus inventory,
  and world state (doors, props, who's where) is rebuilt from flags at the start of each day
  (`apply_world_flags` in `days.py`).
- `days.py`: the seven days as generators, plus the in-game documents and idle chatter.
- `world.py`: terrain, buildings, props, colliders, zones, nav graph (`build_nav`, `find_path`).
  The farmhouse (`build_house`) is furnished room by room with small helpers (`_fbox`/`_fcyl` place parts
  in a piece of furniture's own frame, plus `_picture`, `_curtains`, `_baseboard`, `_chair`). MeshBuilder
  `rot=(a, 0, 0)` with a positive `a` tips the top of an upright part towards +z. Grass and flowers skip
  the footprints in `World.ROOFED`. The moo-hole's bottom wire is its own entity (`set_moohole_wire`).
  `Door.center()` / `Door.player_opened` feed Chuck's open-door check.
- `player.py`, `farmer.py`, `npc.py`, `combat.py`, `vehicle.py`, `models.py`, `ui.py`, `items.py`.
- `moodals.py` (achievements) and `life.py` (wildlife and reactions), both fed by `Game.event`.
- Any node that copies a render state (like the herd LOD) must not copy the net ShaderAttrib: scene-wide
  inputs live on `render` and are updated every frame, and a copied attrib freezes them.
- `engine/`: `shading.py` (GLSL, shadows, time of day), `postfx.py`, `gpuprobe.py`, `meshbuilder.py`, `physics.py`, `audio.py`, `script.py`, `assets.py`, `boot.py`.

## Testing
The tools run the real game at a fixed 30 fps clock. On Linux wrap them in Xvfb as below; on the Windows
machine run them directly (`python -B tools/walkthrough.py --day 1 --to 7 --detect`), which opens a small
game window. A full `--day 1 --to 7` takes about 2 minutes there.

Real fullscreen checks on Windows: a tool call's child processes are killed when the call returns, so
launch, capture and close inside one command. Find the game window by enumerating the process's windows
(`FindWindow(null, "BREAKOWT")` missed it), bring it forward before `CopyFromScreen`, and make the capture
process DPI-aware. Don't move the player's mouse or inject keys without asking first.
```
xvfb-run -a -s "-screen 0 1280x720x24" python tools/walkthrough.py --day 1 --to 7   # full playthrough bot
xvfb-run -a -s "-screen 0 1280x720x24" python tools/walkthrough.py --day 5 --to 5 --shots   # one day, screenshot per step
xvfb-run -a -s "-screen 0 1280x720x24" python tools/walkthrough.py --day 2 --to 2 --detect  # with Chuck's eyes on
xvfb-run -a -s "-screen 0 1280x720x24" python tools/walkthrough.py --day 1 --to 7 --caught all  # get caught once in every step
xvfb-run -a -s "-screen 0 1280x720x24" python tools/walkthrough.py --day 1 --to 7 --resume     # Continue from every checkpoint
xvfb-run -a -s "-screen 0 1280x720x24" python tools/uishots.py   # every UI screen
xvfb-run -a -s "-screen 0 1280x720x24" python tools/smoke.py     # boot + title + a few seconds of day 1
python tools/navcheck.py                                           # nav graph connectivity
```
Screenshots go to `Documents/My Games/BREAKOWT/test_screenshots/`. The walkthrough bot has one plan per story
step (`p_<step key>` in `tools/walkthrough.py`); a new step needs a new plan or the run fails with a
state dump when the step's time limit runs out.
