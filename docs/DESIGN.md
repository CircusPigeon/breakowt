# BREAKOWT: Seven Days to Steak — Design Document

A first-person, absurd, satirical stealth / puzzle / combat game in 3D (Python + Ursina/Panda3D).
You are **Cow #47** ("Forty-Seven") on *Happy Acres Family Farm* ("Where Every Cow Is Family").
On Monday you learn you're scheduled for "PROCESSING" on Sunday ("BBQ w/ Dale!!! Buy milk.").
Escape before then, without being caught by **Farmer Chuck** (Charles "Chuck" Rumpley) —
clumsy, lonely, the only human on the farm. The game ends with you killing him and
leading the herd out at sunrise while the melody composed by your late friend Moozart plays.

## Tone
- Cows are strikingly intelligent; they only make moo sounds. A literal "MOO" floats over the
  speaker's head in the world while a subtitle shows what they actually mean.
- The farmer speaks in a muted-trombone "wah-wah" voice with English subtitles.
- Sound design leans absurd: kazoo fanfare for item pickups, sad trombone when caught,
  808 cowbell "ding" on objective completion, a tuba "DUN DUN DUNNN" for day title cards.
- The ending is sincere: music box + strings + a cow choir mooing Moozart's melody.

## Cast
| Name | Who | Look | Role |
|---|---|---|---|
| **Forty-Seven** (#47) | the player | brown/white; only the pink snout is visible in first person | protagonist |
| **Cowleen** | best friend since calfhood, dry & practical | brown-and-white, daisy behind ear | co-conspirator, distraction partner, final scene |
| **Moozart** (#12) | melancholy composer | black cow, powdered white wig | composing "Symphony for Grass and Sorrow"; dies Thursday (sacrifice) |
| **Sir Loin** | pompous bull who thinks he's a knight | big horns, bucket helm (side quest) | comic relief, charges farmer in finale |
| **Cowpernicus** | nerdy planner/astronomer | bow tie, glasses (side quest), paper-tube telescope | the brains; explains fence/generator/tractor plan |
| **Mooriarty** | shady black-market dealer | fedora, hides behind hay bales | shop: trades Golden Clovers for items |
| **Moomaw** | elder cow, widow of Big Earl | gray, knitted shawl + bonnet | lore, hints; photo side quest |
| **Cluck Norris** | rooster, self-appointed coop guard | — | Wednesday mini-boss; later the dawn signal |
| **Farmer Chuck** | owner, clumsy antagonist | overalls, plaid, straw hat, huge mustache | patrols, investigates noises, trips over things |
| **Dale** | off-screen neighbor | — | BBQ guest; plans to buy the other 48 cows for slaughter |

## Farm layout (meters; x east, z north)
- **Pasture** (electric fence) SW quadrant: cowshed (sleeping barn) on north edge, Old Oak,
  pond, trough, salt lick, Mooriarty's hay-bale hideout, "Cardboard Chuck" scarecrow.
  Pasture gate on east fence. "Moo-hole" (Wednesday) under the sagging wire by the pond.
- **Farmyard** center: tool shed (next to pasture), tractor spot, windmill, woodpile.
- **Big Red Barn**: tractor (brand "JOHN STEER"), ramp up to hayloft, rafters.
- **Chicken coop** with run (Cluck Norris).
- **Farmhouse** NE: porch (wind chimes, gnome, flowerpot, doormat), living room (TV, couch,
  Big Earl cowhide rug — dark joke), kitchen (key hook, fridge, spark plug in vinegar),
  office (computer, gun cabinet, Big Earl photo), bedroom (bed, nightstand w/ cabinet key,
  wardrobe hide spot), bathroom (toilet flush = distraction).
- **Processing building** E: ominous concrete, smiling-cow sign "Happy Cows Come From Happy Acres!", chimney.
- **Main gate** N: chained gate + cattle grid, road beyond.

## Core mechanics
- **Movement**: WASD, mouse look, Shift = gallop (stamina), Ctrl/C = sneak (lower, quieter,
  harder to see), Space = pathetic hop. E = interact (look-at targeting), M = moo,
  R = throw rock (ballistic, makes noise where it lands), LMB = headbutt, RMB = back-kick (combat),
  1-9/scroll = select item, Tab = inventory/journal/map, Esc = pause.
- **Cowbell**: until removed (Tuesday, pliers) it jingles when moving fast → noise.
- **Zones**: pasture is "legal" (you're just a cow). Everywhere else is restricted: if Chuck sees you,
  a suspicion meter fills ("?" → investigates, "!" → caught). Vision cone + line of sight
  (buildings, hay, other cows occlude). Sneaking, distance, darkness reduce visibility.
- **Noise/distractions**: rocks, knocking over buckets/milk cans, radio, toilet, cowbell, mooing.
  Chuck walks to the noise, looks around, mutters, returns to routine.
- **Caught**: sad trombone, Chuck marches you back to the pasture (you keep items). Stat tracked.
- **Clumsy**: Chuck randomly trips (3 s window).
- **Golden Clovers**: hidden collectibles, currency for Mooriarty's shop.
- **Combat**: headbutt, gallop-charge, back-kick, rocks; player health only matters in fights.
- **Tractor driving** on Sunday.

## Story (7 days, one chapter each)

### MONDAY — "Moo-nday" (6 days until steak)
1. Wake in cowshed; Cowleen: a page flew out of Chuck's planner into the Old Oak.
2. Headbutt the oak → page flutters into the pond → wade in and grab it.
3. Read the **planner page**: MON fix fence (AGAIN) · TUE oil tractor · WED dentist?? · THU truck pickup #12 → Processing ·
   FRI bowling w/ the boys!!! · SAT sharpen stuff · SUN #47 → PROCESSING. BBQ w/ Dale!!! Buy milk.
4. Tell the crew (5 conversations, any order) — each introduces a side quest / hint.
5. Crew meeting at the Old Oak at sunset: the plan (fence → generator in tool shed; gate; "step three").
6. Stealth tutorial: steal Chuck's pencil during evening headcount (he loses count).
7. Sleep in stall #47.

### TUESDAY — "Chews-day" (5 days)
1. Chuck brings feed through the pasture gate; slip out (ask Cowleen to faint dramatically, throw a rock, or time it).
2. Tool shed is padlocked; loose board at the back. Headbutt it 3× **only while the tractor engine is roaring** (noise masking).
3. Inside: generator (fuse — "not yet"), toolbox with combo lock (sticky note: "combo = my perfect bowling score";
   trophy: "HIGH SCORE: 117"). Get **pliers** (remove cowbell → silent; cowbell becomes a throwable noisemaker),
   **radio**. Optional: spare glasses (Cowpernicus), rusty bucket (Sir Loin's helm).
4. Return to the pasture (gate bolt is on the outside) before the headcount.
5. Radio → Moozart's inspiration #1 → melody bars 5–8. Cowpernicus: the tractor is our battering ram.

### WEDNESDAY — "Hump Day" (4 days)
Chuck has a toothache (rescheduled dentist): slower, grumpy, naps on porch at noon.
1. Gate padlocked now. Lift the sagging bottom wire by the pond with something rubber (Chuck's lost
   **rubber boot** in the pond, or Mooriarty's **rubber chicken**) → permanent "Moo-hole".
2. Scout the Big Barn: tractor needs **key** (hung from a rafter in the hayloft → knock it down with a rock),
   **fuel** (jerry can in the chicken coop), **spark plug** (Chuck took it to the house).
3. Chicken coop: **Cluck Norris** mini-boss (combat tutorial). Defeated, he crows → inspiration #2 → bars 9–12,
   and he pledges to crow as the signal on Sunday.
4. Fuel the tractor.
5. Evening: wash Moozart's muddy ear tag in the trough → **#12**. He already knew.
   Plan: hide him in the hayloft tomorrow.

### THURSDAY — "The Truck" (3 days)
Gray, rainy.
1. Escort Moozart (follows your trail; slow, hums when nervous — moo to shush him) through the Moo-hole to the hayloft.
2. Hayloft: Moozart plays bars 1–15; "Moo for me" → the player's moo is the final note. Symphony complete.
   He gives you the **score**.
3. Dusk: the truck arrives. Chuck can't find #12: "Aw heck, truck's paid for. I'll take forty-seven early."
   He walks toward you with a rope. Moozart walks out of the barn mooing his symphony: "There you are, twelve."
   Looks back: "Finish it for me. Not the song — the song's done. The escape." Truck drives to Processing. Chimney smoke.
4. Night vigil by the pond; hoofprint notation in the mud. Cowleen: "We get everyone out. All forty-nine."

### FRIDAY — "Fry-day" (2 days)
1. Watch Chuck leave for bowling (pickup drives out the main gate).
2. Get into the farmhouse: doormat → note → flowerpot → note → garden gnome → headbutt gnome → **spare key**.
3. Inside: **spark plug** (kitchen, in vinegar next to dentures), computer (password hint "my best friend (not Dale)",
   photo "Me and Big Earl ♥" → password BIGEARL): emails reveal Dale will buy the other 48 cows next month.
   Spreadsheet: "#12 — done ✓". Optional: email Dale to cancel the BBQ. Optional: Big Earl photo (Moomaw).
4. Chuck returns early (forgot bowling shoes) → stealth escape from the house (hide in wardrobe, lead him with the shoes).
5. Crew meeting: Everyone escapes, Sunday at dawn.

### SATURDAY — "Sharpen Stuff" (1 day)
Chuck sharpens knives at the grinding wheel (SHING). Checklist in any order:
- Install the spark plug in the tractor.
- Lay 3 **planks** over the cattle grid at the main gate.
- Rally the herd (talk to herd cows).
- Night: sneak into the bedroom while Chuck snores (sleep-talks about Dale's potato salad), take the gun-cabinet key
  from the nightstand, take the **shotgun** from the office.
- Quiet night scene with Cowleen under the stars.

### SUNDAY — "Moo-ving Day"
1. Cluck Norris crows. Pull the generator fuse → fence dies.
2. Start the tractor (lights come on in the house) → drive through the main gate.
3. Herd pours out; Sir Loin: "FOR MOOZART!"
4. **Boss fight** — Chuck in underwear + boots with a pitchfork. Phase 1: pitchfork lunges stick in the ground → hit him.
   Phase 2: he throws things; allies help (Sir Loin charge, Cluck Norris). Phase 3: he trips over your old cowbell.
   "You're... you're just a cow." — "Moo." (*My name is Forty-Seven.*) — BANG. Cut to white.
5. **Ending**: sunrise, herd walking down the road; Cowleen and you on the hill.
   "He'd have written something about this." — "He already did." Moozart's symphony plays in full.
   Epilogue cards; credits with stats; post-credits: "Also, somebody should buy milk."

## Side quests
- **Sir Loin's Helm** (bucket) → he knights you and joins the boss fight.
- **Cowpernicus' Spectacles** (spare glasses, tool shed) → star chart marks all Golden Clovers on the map.
- **Moomaw's Photo** (farmhouse office) → Big Earl's Lucky Horseshoe (one free escape when caught).
- **Mooriarty's Clovers** → shop items (rock pouch, rubber chicken, fake moustache disguise, coffee, "mysterious tin can").
- Named herd cows with one-liners.

## Moozart's melody (F major, 3/4, ~76 bpm)
Chords: F | C/E | Dm | Bb | F/A | Gm7 | C | C7 | Dm | Am | Bb | F | Bb | Bbm | F/C–C7 | F
Melody: A4 C5 | G4 E4 | F4 A4 D5 | D5 C5 | C5 A4 | Bb4 A4 G4 | E4 G4 C5 | Bb4 | A4 F4 | E4 C5 | D5 C5 Bb4 | A4 |
F5 D5 | Db5 Bb4 | A4 C5 G4 | F4 (the last note is the player's moo).
Mon: bars 1–4 · Tue (radio): 5–8 · Wed (rooster): 9–12 · Thu (your moo): 13–16.
