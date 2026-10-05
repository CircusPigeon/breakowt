# Handoff notes (for a future Claude Code session)

`docs/DESIGN.md` is the original story/mechanics spec; the cast and many scenes have changed since (see the
rounds below, newest first). This file tracks what the game is now.

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
- Repo: github.com/CircusPigeon/breakowt (public; renamed from cow_game, and GitHub redirects the
  old URL). The local checkout is Coding/Breakowt (it was Coding/Cow Game). Work has happened both in a
  cloud session (branch `claude/upbeat-allen-m6ufzp`) and locally on `main`; they're linear, and `main`
  was fast-forwarded to the branch. Run `git fetch --all` and compare branches before starting.

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
- [x] Combat (Cluckydides the rooster, Chuck boss), tractor driving (`combat.py`, `vehicle.py`)
- [x] Ending + epilogue cards (the player asked for no credits roll)
- [x] Automated walkthrough test: every day passes (`tools/walkthrough.py`)

### Character agency and physical puzzles round (latest, `main`)
- The final Chuck fight remains required. Optional preparation grants one player-triggered Moothagoras
  charge per fight attempt; it stuns Chuck briefly and leaves the player to finish the fight and verdict.
- `characters.py` supplies shorter Monday introductions, practical/challenge/evidence responses,
  optional philosophical arguments, and reactions to catches, fainting, favours and quiet escapes.
  Saturday helpers inspect the grid, supply a board, distract Chuck or recruit herd cows. Moothagoras
  can hold the weight plate from Wednesday onward. Helper recruitment saves exact targets for reloads.
- `puzzles.py` owns day-scoped props, colliders and interactions. The weight store opens for a cow,
  one heavy crate or two sacks; reset handles and an inside release prevent dead ends. The maintenance
  cabinet opens when Chuck fetches a wrench for a jammed hopper; distract him before taking the kit.
  Alternatively push the service crate to the high hatch and climb it.
- The Saturday grid uses one long board and two short boards on two hoof lanes with three yellow support
  lines. Aim at the physical pegs to place, turn or lift boards. Board count alone cannot finish the step.
  `engine/puzzle_rules.py` validates geometry; legacy plank-count checkpoints rebuild a valid layout.
- Thursday foreshadows Chuck substituting another cow for an empty truck. Reaching the loft earns the
  gate-post sketch on Archimoodes' plan; he returns the pencil. Existing completed loft saves earn the
  sketch too. `escape.py` combines the sketch, plant ledger/maintenance clipboard and both puzzle rewards
  into a gate release rig. Every Sunday story step and the existing endings remain in place.
- `tools/puzzlecheck.py` and `tools/fightprepcheck.py` exercise the new puzzles and optional combat assist
  in the real engine; `tools/test_characters.py`, `test_puzzles.py` and `test_fight_prep.py` cover the rules
  without rendering. The walkthrough now places boards at pegs and checks the supported crossing.
- Verified on this Windows machine with isolated offscreen saves: 55 rule/persistence/character checks,
  5 narrative checks, full seven-day campaign with detection, all 17 Saturday checkpoint resumes,
  the persistence harness, actual puzzle/helper interactions, and gate-assist defeat/retry plus verdicts.
  Puzzle and combat-assist screenshots were inspected for layout and readability.

### Reliability and comfort round (`main`)
- **Monday**: the pencil theft follows the planner, before the five introductions and sunset meeting.
  Moocrates introduces the stealth trick; Chuck returns to his daytime routine afterwards. Old saves
  with the meeting already done still resume correctly. Each introduction saves its reward and flag.
- **Final choice**: a loaded Ol' Bessie offers "Lower Ol' Bessie and leave" or "Shoot Chuck" after the
  boss. Mercy keeps ammunition; shooting consumes one shell and sets `chuck_shot`. An empty gun goes
  straight to the survival dialogue. `chuck_verdict` is the shared ending branch in `days.py`.
- **Persistence**: `engine/persistence.py` writes JSON through a flushed temporary file and atomic
  replacement, keeping the previous valid file as `.json.bak`. Progress, settings and Moo-dals use it;
  failed writes show a notice. Consumable purchases atomically store a debit and a receipt in the
  profile; `_run_id` and checkpoint `_purchases` prevent duplicate delivery while recovering purchases
  after rewinding. Coffee also records `_coffee_day` and lasts through same-day reloads. Permanent
  equipment retains the existing profile ownership. Checkpoints now include `Story.talk_i`.
  A placed radio and dropped/airborne reusable items return to inventory in a checkpoint; teardown clears
  their old entities so reload cannot duplicate or lose them. Natural day transitions recover them too.
- **Partial objectives**: Friday's clue chain and pickups, Saturday's spark plug, planks, herd rally,
  cabinet key and gun, plus completed favours save through `Story.save_progress`. Only reconstructable
  steps with `save=True` can save a milestone; Sunday's escape still replays as a sequence.
- **Comfort & reading**: Settings has two tabs. FOV 60–110, bob/roll/shake Off/Reduced/Full, optional
  sprint FOV and reading size 100/115/130% persist. Motion controls also apply while driving. Dialogue,
  documents, mail and the journal page at the selected size instead of shrinking or dropping text.
  Reading pages use arrows/Page Up/Page Down (wheel for documents/journal); dialogue uses Space.
  Measured wrapping uses Panda3D TextNode so literal `<` in story clues is not parsed as markup.
- **Physics**: coincident circle contacts use a unit separation direction instead of dividing by an
  epsilon; near-zero contacts preserve direction without huge displacement. Unowned dynamic circles
  participate in collisions when no owner is ignored.
- New checks: `python -B -m unittest discover -s tools -p 'test_*.py'` (persistence and physics),
  `tools/narrativecheck.py` (story branches), `tools/persistencecheck.py` (real purchase/reload APIs),
  `tools/comfortcheck.py [width height]` (layout and settings). Walkthrough supports
  `--ending spare|shoot|empty`, and `--resume` exercises partial checkpoints as well as step boundaries.
- Verified on Windows with offscreen rendering and isolated saves: 22 persistence/physics tests and
  5 narrative checks; seven-day walkthrough with detection and armed mercy; Sunday shoot and empty
  endings; Monday, Friday and Saturday checkpoint replay; purchase, item-recovery and failed-save
  integration checks; enlarged UI/settings/tractor checks at 1200x800, 1024x768 and 1280x720.

### Philosophers round (branch `wip/philosophers`, merged to `main`)
The player's long playtest list, all addressed. The design taste behind it is in the notes below and in
the player's own words: as humorous as it is a thought piece, puzzles you have to think about, no
hand-holding, no sentimentality.
- **Cast = ancient Greek philosophers** (display names only; internal keys unchanged): Moocrates
  (`cowleen`, Socratic questions), Archimoodes (`moozart`; was Moobius: Archimedes, who proves things in the
  sand by the pond: "don't step on my circles", the grains of sand vs Chuck losing count at forty), Moogenes
  (`sirloin`, Diogenes the Cynic: lives like a dog, wants a bucket to live in, "out of my sunlight"),
  Moothagoras (`cowpernicus`, Pythagoras: everything is number, refuses beans, the glasses), Epicowrus
  (`mooriarty`, Epicurus: "death is nothing to us", runs the shop, now called THE GARDEN), Heifercleitus
  (`moomaw`, Heraclitus: the river; widow of Ajax, the bull Chuck called "Big Ajax" after the floor cleaner),
  Cluckydides (the rooster, Thucydides: "the strong do what
  they can"). Display names live in `npc.FRIENDS`, `ui.SPEAKER_COLORS` and the dialogue.
- **The arc**: the herd starts out treating the truck as weather ("you don't argue with weather"), and
  wakes up over the week: Moocrates' question on Monday, the market report (Lemma Two), the first funeral
  ever held on the farm (Thursday), the "sold in bulk" emails (Friday), and optionally the ledger inside the
  plant. Archimoodes works out the trolley problem himself and walks onto the truck (no "moo to accept the
  axiom" any more; the loft scene is all dialogue). The funeral talks about mortality (Epicurus,
  transmigration, "you can't grieve the weather") with no "it's what he'd have wanted". Nobody does
  anything "for" him. The epilogue cards end on a short, dry thought piece (serif font) and branch on
  whether Chuck was shot, the side quests, and the ledger. Keep this register for new lines.
- **Less hand-holding**: objectives say what, not how ("Get into the tool shed", "Make the cattle grid
  safe for hooves", "Find the cabinet key"); far fewer map markers; clues live in the world (the tractor's
  taped notes and a feather on the fuel cap, the cattle grid's examine, chatter). Hints are tiered: a step's
  `hint=` can be a tuple, and each H press goes one level further (`Story.hint`, `hint_level`); the first
  level is a Socratic question. The toolbox rejects 300 with a joke (a perfect game isn't Chuck's perfect).
  The gnome is back to subtle (no rattle, no explicit popup; the headbutt prompt only once the note
  points at him).
- **Deer stand** (`World.build_deer_stand`, `DayScripts._deer_stand`) in the empty yard corner by the main
  gate (`DEER_STAND`): an ammo tin on the platform, a sign saying DO NOT SHAKE. Headbutting a leg sways the
  stand (noise 12) and slides the tin (a charge counts twice: `Game.last_charge`); it falls and opens to two
  shells. Rocks don't shift it. Moo-dal "Do Not Shake".
- **Shells are an item** (`shells`, stackable). Ol' Bessie comes out of the cabinet empty; Q with no shells
  clicks. Shells come from the deer stand or the shop (6 clovers for two). Before the boss, Q says "not
  yet". In the boss intro Chuck notices the cow has his shotgun and whether it's loaded. The finale needs
  a shell left to offer the shot ending (`chuck_shot` flag). The final choice and empty-gun dialogue were
  revised in the reliability and comfort round above.
- **Happy Acres** (`build_plant_inside`, `DayScripts._plant`): a staff door at the back (`plant_back`,
  `PLANT_BACK`) with a keypad and Chuck's sticky note ("the year of the best day of my life"). 2009 (Big
  Ajax's Best in Show: the photo, and Heifercleitus says it in chatter); 1998 (the bowling trophy) gets a
  joke. Inside: the hook rail, tables, drains, a safety board ("4,212 days without an incident"), and the
  intake ledger (`LEDGER`, shown with the new "ledger" document style). Reading it gives a Moo-dal, a
  conversation with Moocrates (`side_quest_talk`), and an epilogue line. `processing` is a room in
  `InteractionSystem.ROOMS`.
- **Golden Clovers on the map**: five in the strip of grass behind the plant (`_clover_patch`), found once
  per profile. The purse is now profile-level (`Moodals.purse/spend/find_clover/owned`, in moodals.json):
  Moo-dal rewards + found clovers - spent. **Purchases carry over** to later playthroughs
  (`Story.apply_owned` on new game and load); coffee and shells are consumables.
- **Sunday**: pulling the fuse kills the house power too, so Chuck gets up for his freezer
  (`chuck_sunday`, `SUNDAY_PATROL`: underwear, flashlight, dawn sight 26 m) and patrols the shed and yard
  while you get to the barn. Once you're driving he runs at the tractor with the pitchfork: at speed he
  dives out of the way and falls; stop next to him for a second and he drags you off (back to the pasture,
  tractor back in the barn, try again). No "climb in" prompt while driving.
- **Chuck**: sees and hears further (`SIGHT_*`, `HEARING` in `farmer.py`), roams more (extra yard legs and
  shorter waits in every day's routine). Dale is never caught; Chuck greets him, finds him odd up close, and
  a noise traced to Dale is "Oh. Just you, Dale."
- **UI**: dialogue box sizes to its text and popups move above it; journal in three measured columns;
  "[Tab] journal & map  [H] hint" on the HUD; documents in note/paper/screen/ledger styles; ChuckOS mail
  is an inbox (`open_mail`); fonts picked per role in `assets.FONT_CHOICES`; the keypad takes typed digits;
  cutscenes and the caught sequence can't be paused; Esc works in the title's Moo-dals screen.
- **World**: house windows are real openings with tinted glass; a barn window by the side door; the
  player's body is drawn in cutscenes (`Player.sync_body`); herd tags 1-50 (no #96); Archimoodes gets up the
  loft ramp (`World.ramp_ends`) and opens the side door himself.
- **No repeated conversations (latest)**: a friend's chatter for the day plays once per conversation
  (`Story.idle_talk` / `_next_chat`, counted per day in `talk_i["<day>:<key>"]`), then a short brush-off from
  `BRUSH_OFF` (days.py). On Monday a friend you've already told about the page gets their chatter, not the
  whole introduction again. Epicowrus' daily chatter now opens the shop (it was unreachable once you'd met
  him). Herd cows draw from one shuffled deck (`talk_i["herd_deck"]`, a separate one from Thursday on), skip
  lines that name themselves, and shrug (`HERD_SHRUGS`) once it's empty.
- **Look-before-you-smash, softlocks**: Friday has three gnomes in the flowerbed (`World.gnome_ents`
  fish / empty / lantern, `gnome_spots`, ias `gnome_0..2`), shuffled per playthrough (`flags.gnome_order`, set
  in `apply_world_flags`). Chuck's flowerpot note says the key is in Gary, "the fisherman who's never caught a
  thing": the bare hook. E offers a headbutt only after you've looked at that gnome (`gnome_seen`); a wrong one
  cracks open empty (`flags.gnomes_broken`, a list of kinds). Saturday's lumber pile has only two long planks
  (`flags.pile_taken`); the third is the shed board you knocked in on Tuesday, still on the shed floor (ia
  `shed_plank`, `flags.shed_plank_taken` removes the `board_fallen` prop). Monday's meeting lost a third; the
  cut lines (Moogenes on Chuck's face, Moothagoras' nice problem, Big Ajax's one-step plan) are Tuesday and
  Wednesday chatter. Radio: Q never sets it down through a fence or wall (raycast, plus a pasture-zone check),
  and on Tuesday you only count as back in the pasture with the radio in your mouth or set down inside, so
  the gate stays open (and Chuck's feed runs keep going) until you've fetched it.
- **Tuesday, Chuck, music**: the radio gets only static until it's set down against the electric
  fence (`near_fence`; the fence is the aerial), then Archimoodes comes to hear the farm report. Chuck can open
  the pasture gate himself (`OWN_DOORS`): without that, shutting it behind you while he was inside left him
  scraping along the fence (find_path falls back to a straight line when there's no route). Chuck's eyes are
  off during cutscenes and dialogue (a catch during the rooster's intro froze the fight). Archimoodes counting
  primes out loud on Thursday brings Chuck running, sure of himself. The fuse box's wall conduit moved to the
  far end (it sat by the FENCE fuse and the generator's fence cable, so the FENCE label looked right); the
  wiring can never match a label (asserted). The truck scene's lament (`sad_theme`, audio 11) is the ending's
  road tune slowed into B minor, from the moment Archimoodes walks out of the barn. The boss intro is a side-on
  two-shot (the camera was at your ear, hiding you), Moocrates stands beside you on the hill, and the epilogue is
  four cards. Tests are silent (`harness.boot` mutes; `BREAKOWT_TEST_SOUND=1` to hear them).
- **The schedule and the story (audit)**. The truck to Happy Acres comes every other Thursday (#12 this
  week); Sunday is different: Chuck is killing #47 himself for Dale's barbecue (the planner says so, and so does
  Moocrates on Monday), which is why he sharpens knives on Saturday. Everyone but Archimoodes and you treats the
  truck as routine at first, each for a real reason: Moocrates is Socrates in the *Crito* ("you can't take the
  grass for years and refuse the truck"), Epicowrus "death is nothing to us", Moothagoras "souls go round",
  Heifercleitus "the river runs one way", Moogenes "throw me over the fence for the crows". Archimoodes
  (Archimedes) is an engineer, not a theorem prover: "give me a lever and a place to stand" (the tractor is the
  lever); maths is only his hobby (trapping the circle between 96-gons, primes when he's nervous). No lemmas,
  proofs or QED anywhere. He hid his #12 under mud on Monday because he'd made his peace and didn't want the
  week to be about him; Moocrates' curiosity about the mud is the trough scene's hook. Only he calls you
  Moodysseus after the page; at the truck it's the trolley problem, and he's the one at the lever. The
  awakening starts at the funeral and is complete on Friday ("there isn't a bargain, there's a price list").
  The plan item (key `score`) is "Archimoodes' Plan". The epilogue: India, jobs, then the short serious note.
  Cast models: Moogenes wears Diogenes' lantern (not the old knight's cape), Epicowrus a Golden Clover behind
  the ear (not the fedora), Heifercleitus just the shawl (the bonnet read as a grey wig).
- **Mechanics in that round**: every item is on the hotbar and Q does everything (throw, fire, set down, put
  on; R still throws as a quiet alias); Ol' Bessie takes a third of Chuck's health; sight 60 m by day (rain 34,
  dawn 36, dark 18, torch 42) and Chuck makes up his mind faster at range; running into a bin knocks it over
  (noise 40); the fuse box can be solved with no pulls (the shed-light fuse's cable runs up to the ceiling
  lamp); the computer's sticky note is readable; the tractor is looked at, not climbed into; herd cows no longer
  buzz in place when blocked (a one-off sidestep waypoint, and a waypoint with no progress for two seconds is
  dropped); HUD objectives wrap and stack by measured height; the house windows' frames were solid plates
  covering the real openings; the paper texture lost its coffee ring and its own ruled lines; fonts are
  Candara / Candara Bold / Cooper Black / Segoe Print; the ending music is a new folk piece (`ending_theme`,
  audio version 10) instead of the composer-era symphony with the cow choir.
- **Polish pass after the crates** (player's notes): the letterbox bars were 0.12 tall and covered the
  bottom of the dialogue box (`UI.LB_H` 0.075, `DLG_BOTTOM` -0.405). Text that has to fit a box is now
  measured glyph by glyph (`ui.text_width`, `ui.wrap_to`; the old character-count guess was off by a third
  for capitals): toasts size to their text and wrap (a long "New favor" ran out of its box), and the
  journal wraps every column for real. Its inventory measures itself first: full descriptions if they fit,
  smaller text if that fits, else a two-column list with one-line descriptions, so it can't run off the
  screen; the HUD is hidden behind the journal. `MeshBuilder.cylinder` caps were wound inside-out (every
  cylinder and cone in the game): upright you couldn't tell, but a trash can knocked on its side looked open
  at the end; knocked props also tipped about their base and sank half into the ground (now lifted by
  `lie`). The tractor's steering wheel is a rim with spokes on a column (it was a solid disc blocking the
  driver's view); Moogenes' bucket sits upside down on his head between the horns (the old knight's-helm
  model had his horns through it, plus a plume); the held bucket has a handle and hangs below the snout.
  **Carry-over**: favour rewards are profile perks now too (`Moodals.add_perk/perks`): the hiding-spot map
  and the lucky horseshoe come with you into later playthroughs, like everything bought from Epicowrus.
- **Crates and hops** (the player's idea: nudging boxes and simple parkour). `world.Pushable`: a crate you
  headbutt (or E) one step along whichever of the four directions you're pushing it; blocked by walls, other
  crates, cows and Chuck; it can't leave its zone, falls off ledges, and goes back home if you leave its zone
  for two seconds (so a wedged crate never strands a puzzle). It has a floor on top. Physics: boxes tagged
  `"climb"` stop blocking a walker once their top is within `climb` of its feet (`Physics.resolve`), and the
  player passes `STEP_UP` (0.55); a hop (`HOP_VEL` 4.6, about half a metre) gets you onto a 0.85 m crate but
  not onto the 1.7 m tractor or over a fence. The three puzzles, in teaching order:
  Tuesday, Chuck's radio is on top of a tall cabinet in the shed (`RADIO_SPOT`): push the shed crate over and
  stand on it. Wednesday, the tractor key is tied to the hayloft rafter (`KEY_SPOT`, rocks just bounce off):
  push the loft crate under it, hop on, and hop again; at the top of the hop your head's by the key and you
  bite it off (`_rafter_grab`). Sunday, you can't climb into the tractor: break the rickety stretch of loft
  railing above it (`_loft_rail`, two headbutts or one at a gallop, loud: noise 22) and step off onto it
  (`on_tractor`, the tractor's top is a floor at `TRACTOR_TOP`). Landing on the tractor any other time slides
  you off the hood. The loft posts moved to clear the drop (16, 18.6, 25.4, 28).
- **The argument** (the player asked for real positions, not philosopher catchphrases). Monday, Moocrates
  asks why Chuck is allowed to do it, and each friend answers from their own philosophy; at the meeting she
  takes every answer apart: Heifercleitus' "the river only runs one way" (but everything flows), Epicowrus'
  "death is nothing to us" (then it's nothing to Chuck, so we could eat him), Moogenes' "natural" (a habit
  that forgot it was a choice), and the humans' old rule that nothing without reason is owed justice (the
  cows are reasoning, so by their own rule they're owed it). No argument moves a man who isn't listening,
  so they escape instead. The thread then runs through the week: a motive isn't a reason (Tue);
  Cluckydides' "the strong do what they can", and the weak can change what they can do (Wed); Moocrates
  asks whether a cow is the kind of thing that adds, and Archimoodes answers that he's only using Chuck's
  arithmetic (Wed, then the truck); Epicowrus notices his consolation works best for whoever holds the rope
  (funeral); custom did everyone's thinking (Fri); Chuck states the rule himself in the finale ("cows don't
  THINK, that's why it's okay") and you answer with it. Moothagoras has held the Pythagorean view (one soul,
  so eating any of us is eating family) all along. The herd's chatter switches from "it's like weather"
  (`HERD_LINES`) to the waking-up lines (`HERD_LINES_LATE`) after Thursday.
- **Your name is Moodysseus.** The herd stops saying a cow's name once she's on Chuck's list ("it makes
  Thursdays easier"), so from the planner page on you're Forty-Seven, and Moocrates catches herself doing
  the same to Archimoodes. At the funeral they notice they've said his name all night; on the hill at the
  end Moocrates says yours. The nameplate follows (`Game.player_name`, flags `on_list` / `renamed`).
  Archimoodes points out that Odysseus escaped the Cyclops as "Nobody".
- **All cow names are Greek** (the player's call): Moobius became Archimoodes, Big Earl became Big Ajax
  (password BIGAJAX), Clarabelle became Echo (who repeats whatever she heard last), and the whole herd
  (`npc.HERD_NAMES`, 42 names). A named herd cow's first line is her own (`story.HERD_SAYS`): Xenophanes on
  gods drawn by whoever holds the brush, Chrysippus on the "no reason, no justice" rule, Aristotle (the cow
  who's bought in), Plutarch, Porphyry, Homer's cattle of the Sun, and so on. Chuck only ever uses numbers.
- **Fuse box puzzle (Sunday)**: three fuses on the shed wall labelled FENCE, HOUSE and SHED LIGHT, and
  Chuck's note: "the electrician says every label is wrong". The true wiring is one of the two derangements
  (`flags["fuse_map"]`, picked once per run). The fuse marked HOUSE is always safe to pull first (fence or
  shed light), and what happens tells you the rest. Pulling the real house fuse kills the porch light and
  the freezer: Chuck gets up and walks into the shed (he has the shed key on Sunday: `door_keys`) to put it
  back (`_chuck_fixes_house`), then patrols. The fence fuse sets off the fence alarm, which also gets him up.
- **Not reproduced**: "headbutting in the shed opened the menu". 96 scripted headbutts in every direction
  inside the shed opened nothing; the likely culprit is the Moo-dal banner (knocking things over in there).
- Textures added since the last version bump are painted on launch (like sounds).

### Bed, doors and boss round
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
- Ol' Bessie fires: Q with the shotgun selected (`Game.fire_shotgun`), one `shells` item per shot (see the
  philosophers round for where shells come from). 3 damage and knocks Chuck flat whatever state he's in.
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
- `moodals.py`: 23 achievements for freeplay (moo 50 times, make Chuck trip, knock over every prop, get the
  herd to moo back, a day without being caught, find the bathroom mirror, ...). They are the only source of
  Golden Clovers (Mooriarty's shop currency): `Game.clovers()` = total Moo-dal payout minus
  `flags["clovers_spent"]`. (The player asked for no collectibles, so the 20 hidden clovers are gone.)
  Progress is a profile, `saves/moodals.json`, separate from the
  checkpoint save, so it carries across playthroughs and survives reloads. UI: banner on unlock
  (`UI.moodal_banner`, queued), list screen `UI.open_moodals` from the pause menu and the title screen,
  and a count in the journal.
- `Game.event(name, **kw)` is the hook: the player (moo, hop, step), farmer (chuck_trip, dale), game
  (interact, knock, caught, noise) and story (day_start, herd_talk) call it; `Moodals.on_event` and
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

### Player feedback round (playtest notes, all addressed)
- **Every item has a use.** Holdable = on the hotbar (Q use / R throw); the rest live in the journal and
  work by themselves (keys). Pencil: Moobius writes his proof with it. Pliers: needed to pull the live
  fuse on Sunday. Radio: [Q] sets it down playing, Chuck comes to switch it off (also the way to get him out
  of bed on Saturday night). Proof (item key still `score`): [Q] reads it out, the herd argues about it and
  Chuck stomps to the pasture gate to shush them (`score_use`, 45 s cooldown, sound `moo_herd_argue`, noise
  source `herd_hum`). Boot and tin can are throwables.
  The spare key stays in the front door once used; the tractor key is used on Sunday; no fuse item.
- **Hotbar has no cap** (it was silently 9, which hid late items like the spark plug): keys 1-9 and 0, scroll
  for the rest, the bar shrinks past ten slots.
- **Chuck handles doors** (`Farmer._doors_tick`, `OWN_DOORS`): pathfinding goes through his own doors
  (`find_path(through=...)`), he opens them when he reaches them and shuts them behind him. A door the
  player left open on his route gets a remark and he walks through it, instead of shutting it and opening
  it again (that was the Friday "open/close glitch"). Friday's routines no longer script the front door.
- **Sight** 30 m by day (was 24), 23 in rain, 9.5 in the dark, 27 in the torch beam; same 110° cone.
- **Asleep, walking wakes him** (`footfall` noise, only while he sleeps, only if not sneaking), faster up
  close and in the house; galloping is loud at any distance under 9 m.
- **Cameras** aim with `game.aim_camera` (yaw/pitch, zero roll). Ursina 8's `look_at` rotates the shortest
  way from the current orientation, so a cut facing the other way flipped the boss intro upside down.
- **Boss takes 8 hits**, one per landed blow whatever it was (shotgun included).
- **Truck tailgate** drops to a ramp, Moobius walks in over a temporary floor, a stand-in rides away.
- **Barn windows** (`wall_gaps` takes an optional sill: invisible pane, see-through both ways, trim via
  `_window_frame`): north at cow height, east south of the silo, east gable in the loft north of it.
- **Moozart is now Moobius**, a logician. Only the display name changed: the key is still `moozart`
  everywhere in code, sounds, flags and saves. He wears a bow tie and builds the Escape Theorem across the
  week: Lemma 1 (Chuck can't count past forty, Mon), Lemma 2 (the market report: a cow is worth more to
  Chuck stopped than walking, Tue), Lemma 3 (the rooster is on time, Wed); the ear tag shows he's #12. The
  cast was later recast as Greek philosophers (see the philosophers round).
- **Dialogue** rewritten for more jokes and less sentiment (the player's words: funnier, edgier, the puns
  are good but it was a bit innocent). Keep that register for new lines. The soft scenes were then rebuilt
  as comedy (the player's pick, plot unchanged, Moobius still goes on the truck): Thursday's vigil is
  Moobius's funeral going off the rails (Sir Loin's eulogy, a sad trombone, Mooriarty selling "signed"
  hoofprints); Saturday's stargazing is a dress rehearsal at the oak (Cluck's "quiet" practice crow, Chuck's
  light flicks on, you charge the oak); the ending is one exchange on the hill cut off mid-word by a hard cut
  to black, then short epilogue cards and straight back to the title. No credits roll.
- New sounds are generated on launch without a version bump (assets fill in missing files).

### Verified
- Crates and hops: `--day 1 --to 7 --caught all --detect`, `--day 2 --to 3 --resume` and `--day 7 --to 7
  --resume` pass. The bot does each puzzle for real (headbutt pushes from behind the crate, a real hop with W
  held, the hop-grab, two headbutts on the railing, walking off the loft edge). A drop onto the tractor on a
  weekday slides you off; navcheck is clean.
- Greek names + fuse box: `--day 1 --to 7 --detect` passes; the bot pulls the fuse marked HOUSE first and
  reasons from what happens. A scratch test pulled the real house fuse: Chuck got up, walked into the shed,
  put it back, carried on patrolling, and the fence fuse then ended the step.
- Philosophers round, on the Windows machine: `--day 1 --to 7 --detect` passes (the bot now also shakes the
  deer stand, opens the plant, reads the ledger, picks the clovers, fires one shell and keeps one for the
  shot ending). A scratch test stalled the tractor next to Chuck on Sunday: he drags you off, you're back
  in the pasture, he patrols again, and the tractor starts again. `tools/uishots.py` covers the new
  note/mail/ledger documents and the Moo-dals screen.
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
Graphics: Low / Medium (default) / High, plus the Comfort & reading controls described above.

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
- `story.py`: title screen, day runner, step/hook system, checkpoints, conversations, shop, epilogue cards.
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
