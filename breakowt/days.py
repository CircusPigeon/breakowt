"""The seven days. Mixed into Story (story.py), so `self` is the Story and `self.g` the Game."""
from __future__ import annotations

import math
import random
import time

from ursina import Entity, destroy

from . import models
from .combat import CluckNorris, ChuckBoss, Feathers
from .engine.assets import tex
from .engine.meshbuilder import MeshBuilder
from .engine.shading import FARM_SHADER
from .interact import Handler, Interactable
from .npc import FRIENDS, ang_diff
from .vehicle import Tractor
from .world import BARN, COOP_RUN, HOUSE, HOUSE_Y, LOFT_Y, PASTURE, SHED, in_pond

Y = HOUSE_Y
L = LOFT_Y

DAYS = {
    1: dict(name="Monday", sub="6 days until steak", card="MONDAY", card_sub="Moo-nday  ·  6 days until steak"),
    2: dict(name="Tuesday", sub="5 days until steak", card="TUESDAY", card_sub="Chews-day  ·  5 days until steak"),
    3: dict(name="Wednesday", sub="4 days until steak", card="WEDNESDAY", card_sub="Hump Day  ·  4 days until steak"),
    4: dict(name="Thursday", sub="3 days until steak", card="THURSDAY", card_sub="The Truck  ·  3 days until steak"),
    5: dict(name="Friday", sub="2 days until steak", card="FRIDAY", card_sub="Fry-day  ·  2 days until steak"),
    6: dict(name="Saturday", sub="1 day until steak", card="SATURDAY", card_sub="Sharpen Stuff  ·  1 day until steak"),
    7: dict(name="Sunday", sub="Steak day", card="SUNDAY", card_sub="Moo-ving Day"),
}

FENCE_LINES = ["Stupid fence.", "Every Monday. EVERY Monday.", "Who keeps LEANING on this?", "Hold still, you."]
FEED_LINES = ["Breakfast, ladies!", "Come and get it. Don't all rush at once.",
              "This feed costs more than my truck payment.", "Eat up. Big week."]
OIL_LINES = ["C'mon, baby.", "Purr for Daddy.", "There she goes!", "Needs more oil. Everything needs more oil."]
TOOTH_LINES = ["Ow.", "Ow ow ow.", "Stupid tooth.", "Dentist's not till Thursday. THURSDAY.", "Mmmph. Ow."]
RAIN_LINES = ["Great. Rain.", "My socks are wet. Both of 'em.", "Truck better not be late in this.",
              "Where's my other boot... oh. Right."]
SHARPEN_LINES = ["Big day tomorrow.", "Nice and sharp.", "Dale likes 'em thick-cut.", "Sharp knife's a safe knife."]
COUNT_LINES = ["Thirty-one, thirty-two...", "...thirty-eight, thirty-nine. Hold STILL, Buttercup.",
               "Forty, forty-one... no, I counted you.", "...forty-two, forty-three..."]

MOOHOLE_POS = (-18.0, -66.1)
OAK_MEET = {
    "cowpernicus": (-46.8, 0, -35.2, 270), "cowleen": (-50.0, 0, -39.5, 0), "sirloin": (-53.6, 0, -36.5, 70),
    "moozart": (-53.0, 0, -31.8, 140), "mooriarty": (-49.8, 0, -30.8, 180), "moomaw": (-46.9, 0, -38.8, 310),
}
POND_VIGIL = {
    "cowleen": (-38.5, 0, -52.0, 220), "sirloin": (-43.0, 0, -51.2, 190), "moomaw": (-35.2, 0, -56.0, 250),
    "cowpernicus": (-47.5, 0, -51.8, 160), "mooriarty": (-51.0, 0, -53.5, 140),
}


class DayScripts:
    def __init__(self):
        self.revving = False
        self.radio_on = None

    # ==================================================================
    # canonical progress: what finishing each day leaves you with
    # ==================================================================
    def canon_before(self, day):
        for d in range(1, day):
            self.canon_day(d)

    def _sq(self, key, text, state):
        g = self.g
        q = {"text": text, "state": state}
        g.side_quests[key] = q
        g.flags.setdefault("_sq", {})[key] = q

    def canon_day(self, d):
        g = self.g
        inv = g.inv
        f = g.flags

        def give(k, n=1):
            if not inv.has(k):
                inv.add(k, n, silent=True)

        def take(k):
            while inv.has(k):
                inv.remove(k)
        if d == 1:
            give("page")
            give("pencil")
            f["mooriarty_met"] = True
            self._sq("helm", "Find Sir Loin a helm", "active")
            self._sq("specs", "Find Cowpernicus some glasses", "active")
            self._sq("photo", "Bring Moomaw the photo of Big Earl", "active")
        elif d == 2:
            give("pliers")
            give("cowbell")
            give("radio")
            f["board_broken"] = True
            f["bell_off"] = True
            g.player.has_bell = False
        elif d == 3:
            f["gate_locked"] = True
            f["moohole_open"] = True
            give("tractor_key")
            f["tractor_key_taken"] = True
            f["tractor_fueled"] = True
            f["jerrycan_taken"] = True
            f["cluck_beaten"] = True
            f["moozart_tag_clean"] = True
            f["tractor_inspected"] = True
        elif d == 4:
            take("page")
            give("score")
            f["moozart_gone"] = True
        elif d == 5:
            give("house_key")
            give("sparkplug")
            f["house_unlocked"] = True
            f["gnome_broken"] = True
            f["emails_read"] = True
        elif d == 6:
            take("sparkplug")
            f["sparkplug_in"] = True
            f["planks_laid"] = 3
            f["herd_rallied"] = True
            give("shotgun")
        g.refresh_hotbar()

    # ==================================================================
    # world state from flags
    # ==================================================================
    def apply_world_flags(self):
        g = self.g
        w = g.world
        fl = g.flags
        g.side_quests = {k: dict(v) for k, v in fl.get("_sq", {}).items()}
        for d in w.doors.values():
            d.set_open(False, instant=True)
        board = bool(fl.get("board_broken"))
        w.colliders["shed_board"].enabled = not board
        w.shed_board.enabled = not board
        if board:
            self.fallen_board()
        mh = bool(fl.get("moohole_open"))
        w.colliders["moohole"].enabled = not mh
        if mh:
            self.prop("moohole_boot", models.item_model(
                "boot" if fl.get("moohole_item", "boot") == "boot" else "rubber_chicken",
                position=(MOOHOLE_POS[0], 0.55, MOOHOLE_POS[1]), rotation=(0, 0, 90), scale=1.2))
        self.lay_planks(fl.get("planks_laid", 0))
        self.place_tractor(22, 1, 180)
        w.gnome.rotation = (0, 200, 0) if not fl.get("gnome_broken") else (80, 200, 0)
        w.chain.enabled = True
        w.pickup.position = (74, 0, 36)
        w.pickup.rotation = (0, 180, 0)
        w.pickup.enabled = True
        w.colliders["pickup"].enabled = True
        g.player.has_bell = not fl.get("bell_off")
        mz = g.cows["moozart"]
        mz.set_visible(not fl.get("moozart_gone"))
        if fl.get("moozart_tag_clean") and mz.model.tag != "tag_12":
            mz.model.set_tag("tag_12")
        sl = g.cows["sirloin"].model
        if bool(fl.get("sq_helm")) != ("bucket" in sl.acc):
            sl.set_acc("bucket", bool(fl.get("sq_helm")))
        cp = g.cows["cowpernicus"].model
        if bool(fl.get("sq_specs")) != ("glasses" in cp.acc):
            cp.set_acc("glasses", bool(fl.get("sq_specs")))
        self.house_lights(False)
        for key in ("cowshed", "barn", "loft", "porch", "processing"):
            w.set_lamp(key, False)
        w.set_lamp("shed", True)
        for k in g.knockables:
            k["down"] = False
            k["t"] = 0.0
            k["ent"].rotation = (0, 0, 0)
        for h in g.herd:
            h.state = "graze"
            h.path = []
            h.free = False
            h.area = PASTURE
            h.model.enabled = True
            h.col.enabled = True
        self.scatter_herd()
        g.place_clovers()
        self.register_doors()
        self.register_globals()
        self.place_friends_default()
        g.farmer.teleport((22, 0, -20), 0)
        g.farmer.set_visible(True)

    def scatter_herd(self):
        g = self.g
        rnd = random.Random(47 + self.day)
        x0, x1, z0, z1 = PASTURE
        for h in g.herd:
            for _ in range(40):
                x, z = rnd.uniform(x0 + 3, x1 - 3), rnd.uniform(z0 + 3, z1 - 16)
                if not in_pond(x, z, 2) and not g.phys.blocked_at(x, z, 1.2) and math.hypot(x + 50, z + 35) > 4 \
                        and not (-66 < x < -38 and -12 < z < 3):
                    break
            h.x, h.z = x, z
            h.yaw = rnd.uniform(0, 360)
            h._apply()

    def fallen_board(self):
        mb = MeshBuilder()
        for k in range(3):
            mb.box((SHED[0] + 1.1, 0.06 + k * 0.02, -22.7 + k * 0.52), (2.0, 0.04, 0.48), color=(0.95 - k * 0.05, 0.9, 0.85, 1),
                   rot=(0, 4 - k * 3, 0), uv_density=0.6)
        self.prop("board_fallen", Entity(model=mb.build(), texture=tex("wood"), shader=FARM_SHADER))

    def place_tractor(self, x, z, yaw):
        g = self.g
        w = g.world
        w.tractor.position = (x, 0, z)
        w.tractor.rotation = (0, yaw, 0)
        old = w.colliders.get("tractor")
        if old is not None:
            g.phys.remove(old)
        # the tractor's footprint, rotated with it (only 0/90/180/270 are used)
        horiz = abs(math.sin(math.radians(yaw))) > 0.7
        fx, fz = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
        cx, cz = x + fx * 0.2, z + fz * 0.2
        w.colliders["tractor"] = g.phys.add_box_c(cx, cz, 4.4 if horiz else 2.4, 2.4 if horiz else 4.4, 0, 2.6)

    def lay_planks(self, n):
        g = self.g
        for i in range(3):
            self.remove_prop(f"plank{i}")
        for i in range(n):
            mb = MeshBuilder()
            mb.box((-1.2 + i * 1.2, 0.05, 82.5), (0.5, 0.08, 4.6), color=(0.72, 0.55, 0.35, 1), uv_density=0.6)
            self.prop(f"plank{i}", Entity(model=mb.build(), texture=tex("wood"), shader=FARM_SHADER))
        g.world.colliders["cattle_grid"].enabled = n < 3

    def house_lights(self, on):
        w = self.g.world
        for k in ("house_living", "house_kitchen", "house_hall", "house_office", "house_bed", "house_bath"):
            w.set_lamp(k, on)
        w.house_glass.set_shader_input("u_emissive", 0.9 if on else 0.0)
        w.house_glass.color = (1, 0.85, 0.55, 1) if on else (1, 1, 1, 1)

    # ------------------------------------------------------------------
    # doors the player can use, and other always-on interactions
    # ------------------------------------------------------------------
    def _toggle_door(self, key, noise=5.0):
        g = self.g
        d = g.world.doors[key]
        opening = not d.is_open
        p = g.player
        # swing away from the player
        d.set_open(opening)
        g.audio.play("door_creak" if opening else "door_close", vol=0.7, pos=(p.x, 1, p.z), rng=25)
        if noise:
            g.noise(p.pos, noise, "door")

    def register_doors(self):
        g = self.g
        fl = g.flags

        def door_prompt(key, what):
            return lambda gg: (f"Close the {what}" if gg.world.doors[key].is_open else f"Open the {what}")
        g.on("barn_side", door_prompt("barn_side", "side door"), lambda gg: self._toggle_door("barn_side"), scope="day")
        g.on("coop_gate", door_prompt("coop_gate", "gate"), lambda gg: self._toggle_door("coop_gate"), scope="day")

        # pasture gate: the bolt is on the outside
        def outside_pasture(gg):
            return gg.player.x > -18
        g.on("pasture_gate", "Slide the bolt and open the gate",
             lambda gg: self._toggle_door("pasture_gate", 8),
             cond=lambda gg: outside_pasture(gg) and not gg.flags.get("gate_locked") and
             not gg.world.doors["pasture_gate"].is_open, scope="day")
        g.on("pasture_gate", "Close the gate", lambda gg: self._toggle_door("pasture_gate", 8),
             cond=lambda gg: gg.world.doors["pasture_gate"].is_open, scope="day")
        g.on("pasture_gate", "Examine the gate",
             lambda gg: gg.examine("Padlocked now. Chuck's learning."),
             cond=lambda gg: gg.flags.get("gate_locked") and not gg.world.doors["pasture_gate"].is_open, scope="day")

        # the farmhouse
        def front(gg):
            if not gg.flags.get("house_unlocked"):
                if gg.inv.has("house_key"):
                    gg.flags["house_unlocked"] = True
                    gg.audio.play("blip_hi", vol=0.5)
                    self._toggle_door("front_door", 4)
                    gg.examine("The spare key turns. You're in.")
                else:
                    gg.examine("Locked. There's always a spare key somewhere.")
                return
            self._toggle_door("front_door", 4)
        g.on("front_door", lambda gg: ("Close the front door" if gg.world.doors["front_door"].is_open else
                                        ("Open the front door" if gg.flags.get("house_unlocked") else
                                         ("Unlock the door with the spare key" if gg.inv.has("house_key")
                                          else "Try the front door"))), front, scope="day")

        def back(gg):
            if gg.player.x < HOUSE[1] or gg.world.doors["back_door"].is_open:
                self._toggle_door("back_door", 4)
            else:
                gg.examine("Locked from the inside.")
        g.on("back_door", lambda gg: ("Close the back door" if gg.world.doors["back_door"].is_open else
                                       ("Open the back door" if gg.player.x < HOUSE[1] else "Try the back door")),
             back, scope="day")
        g.on("barn_door", "Push the barn doors",
             lambda gg: gg.examine("The big doors are barred from the inside. The side door, though, never is."),
             scope="day")
        g.on("shed_door", "Try the shed door",
             lambda gg: gg.examine("Padlocked. The back of the shed might be another story."),
             cond=lambda gg: not gg.flags.get("board_broken"), scope="day")
        g.on("main_gate", "Push the main gate",
             lambda gg: gg.examine("Chained and padlocked. It rattles. It does not open. Something big and green could fix that."),
             scope="day")
        g.on("generator", "Look at the generator",
             lambda gg: gg.examine("It hums. The label on the fuse says 'MAIN FUSE: PULL TO KILL FENCE (DON'T)'. "
                                   "Not yet. Sunday."), cond=lambda gg: gg.day < 7, scope="day")

    def register_globals(self):
        """Wardrobe hiding and the radio: useful whenever you're around them."""
        g = self.g

        def hide(gg):
            gg.flags["_hiding"] = True
            p = gg.player
            p.teleport(53.9, Y, 45.4, 90)
            p.frozen = True
            p.crouch_toggle = False
            self.show_overlay()
            gg.audio.play("door_creak", vol=0.4)

        def unhide(gg):
            gg.flags.pop("_hiding", None)
            gg.player.frozen = False
            self.hide_overlay()
            gg.audio.play("door_close", vol=0.4)
        def hat(gg):
            gg.inv.add("hat")
            gg.examine("A spare straw hat. With a moustache, you'd pass for Dale. From a distance. In bad light.")
        g.on("wardrobe", "Hide in the wardrobe", hide, cond=lambda gg: not gg.flags.get("_hiding"), scope="day")
        g.on("wardrobe", "Borrow a spare straw hat", hat,
             cond=lambda gg: gg.inv.has("moustache") and not gg.inv.has("hat") and not gg.flags.get("_hiding"),
             scope="day")
        g.on("wardrobe", "Get out of the wardrobe", unhide, cond=lambda gg: gg.flags.get("_hiding"), scope="day")
        g.on("toilet", "Flush it (loud!)", lambda gg: self.flush(), scope="day")

    def flush(self):
        g = self.g
        g.audio.play("flush", vol=1.0, pos=(66.8, 1, 47), rng=40)
        g.noise((66.8, Y, 47.0), 24, "flush")
        g.examine("WHOOSH. Very satisfying. Very loud.")

    def radio_use(self, sel):
        """Q with the radio: set it down playing. Chuck can't resist checking on it."""
        g = self.g
        if sel != "radio":
            return False
        p = g.player
        f = p.forward()
        pos = (p.x + f[0] * 1.2, 0.0, p.z + f[2] * 1.2)
        gh, _ = g.phys.ground(pos[0], pos[2], p.y + 0.5)
        pos = (pos[0], gh + 0.13, pos[2])
        g.inv.remove("radio")
        ia = self.item("radio_on", "radio", pos, "Chuck's radio (playing)", "Turn it off and pick it up",
                       lambda gg: self._radio_pickup(), radius=0.4)
        self.radio_on = {"pos": pos, "t": 0.5}
        g.audio.loop("radio", "loop_radio", vol=0.8, pos=pos, rng=35, group="sfx")
        g.examine("You nose the radio on. Country music, loud. Someone's going to come and see about that.")
        return True

    def _radio_pickup(self):
        g = self.g
        self.remove_item("radio_on")
        g.audio.stop_loop("radio", 0.3)
        self.radio_on = None
        g.inv.add("radio", silent=True)
        g.audio.play("blip", vol=0.5)

    def radio_tick(self, dt):
        r = self.radio_on
        if not r:
            return
        r["t"] -= dt
        if r["t"] <= 0:
            r["t"] = 7.0
            self.g.noise(r["pos"], 20, "radio")

    # ------------------------------------------------------------------
    # common bits
    # ------------------------------------------------------------------
    def base_update(self, dt):
        self.radio_tick(dt)

    def morning(self, preset="morning", music="music_pasture", amb="day"):
        g = self.g
        g.set_time(preset)
        g.ambience(amb)
        self.base_music = music
        g.audio.loop("fence", "loop_fence", vol=0.12, pos=(-18, 1, -40), rng=14, group="ambient")

    def wake_in_stall(self):
        self.g.teleport_player("bed47")

    def chuck(self):
        return self.g.farmer

    def chuck_routine(self, steps):
        f = self.g.farmer
        f.set_visible(True)
        f.set_routine(steps)

    def sleep_step(self, text="Go to sleep in stall 47"):
        """Generator: objective to go to bed, then fade out."""
        g = self.g
        self.objectives(("sleep", text))
        self.mark((-43.5, 0.7, "Your stall"))
        done = {"d": False}

        def sleep(gg):
            done["d"] = True
        g.on("bed47", "Sleep", sleep)
        yield lambda: done["d"]
        g.complete("sleep")
        g.player.frozen = True
        yield from g.fade_out(1.6)
        g.player.frozen = False

    def gather_at(self, spots):
        g = self.g
        for k, (x, y, z, yaw) in spots.items():
            c = g.cows[k]
            if c.visible:
                c.teleport((x, y, z), yaw)
                c.look = "player"
                c.graze = False

    def moo_music(self, name, npc=None, dur=None):
        """Play a Moozart piece over the music (ducked)."""
        g = self.g
        g.audio.music_duck = 0.15
        pos = (npc.x, 1.5, npc.z) if npc is not None else None
        g.audio.play(name, vol=1.0, pos=pos, rng=60, group="voice")
        if npc is not None:
            npc.bubble("Mooo-oo", life=3.0)
        return dur

    def unduck(self):
        self.g.audio.music_duck = 1.0

    def chuck_ia(self, prompt, action, cond=None, reach=2.2):
        """An interactable that follows Chuck around."""
        g = self.g
        f = g.farmer
        ia = g.ia.add(Interactable("st_chuck", (0, 0, 0), 0.6, "Chuck", None, prompt, reach,
                                   follow=lambda: (f.x, f.y + 1.3, f.z)))
        ia.handlers.append(Handler(prompt, action, cond, "global"))
        return ia

    def behind_chuck(self):
        g = self.g
        f = g.farmer
        p = g.player
        bearing = math.degrees(math.atan2(p.x - f.x, p.z - f.z))
        return abs(ang_diff(bearing, f.facing())) > 100

    def friends_follow_off(self):
        for c in self.g.cows.values():
            c.trail_fn = None
            c.path = []

    # ==================================================================
    # per-day chatter when there's nothing specific to say
    # ==================================================================
    def chatter(self, key):
        d = self.day
        C = CHATTER.get(d, {}).get(key) or CHATTER[0].get(key) or []
        return [[(key, line) if isinstance(line, str) else line for line in conv] for conv in C]

    # ==================================================================
    # MONDAY
    # ==================================================================
    def setup_day1(self):
        g = self.g
        self.morning()
        self.wake_in_stall()
        self.chuck_routine([
            ("tool", "hammer"),
            ("go", (-15.2, 0, -50), 1.8), ("wait", 12, "work", FENCE_LINES, (-18, -50)),
            ("go", (-15.2, 0, -21), 1.8), ("wait", 12, "work", FENCE_LINES, (-18, -21)),
            ("go", (-15.2, 0, -8), 1.8), ("wait", 10, "work", FENCE_LINES, (-18, -8)),
            ("go", (-15.2, 0, -36), 1.8), ("wait", 8, "look"),
        ])
        g.farmer.teleport((-15.2, 0, -44), 0)
        if not self.done("d1_oak"):
            self.prop("page_tree", models.item_model("page", position=(-49.2, 6.2, -34.1), rotation=(20, 40, 10)))
        self.dhook("update", self.base_update)
        self.dhook("use", self.radio_use)

    def day1(self):
        yield from self.step("d1_wake", self.d1_wake)
        yield from self.step("d1_oak", self.d1_oak,
                             hint="The page is stuck up in the Old Oak. Stand next to the trunk and headbutt it (left click).")
        yield from self.step("d1_page", self.d1_page,
                             hint="The page landed in the pond. Walk into the water and pick it up with E.")
        yield from self.step("d1_crew", self.d1_crew,
                             hint="Tell the others. Moozart's by the pond, Sir Loin at the salt lick, Cowpernicus under the "
                                  "oak, Mooriarty in the hay bales in the far corner, Moomaw by the trough.")
        yield from self.step("d1_meeting", self.d1_meeting, hint="Everyone's meeting under the Old Oak.")
        yield from self.step("d1_pencil", self.d1_pencil,
                             hint="Get behind Chuck while he counts (crouch with C or Ctrl) and press E to take the "
                                  "pencil. If he spots you close up he'll shoo you off, no harm done.")
        yield from self.step("d1_sleep", self.sleep_step, hint="Bed. Stall 47, in the cowshed.")
        yield from self._run_day(2)

    def d1_wake(self):
        g = self.g
        c = g.cows["cowleen"]
        c.teleport((-45.6, 0, -4.2), 20)
        g.cutscene_start(letterbox=True)
        g.player.look_at_point((c.x, 1.3, c.z))
        yield from g.fade_in(1.4)
        yield from g.talk([
            ("cowleen", "Forty-Seven. Wake up. You'll want to see this."),
            ("you", "Moo. (It's barely light out.)"),
            ("cowleen", "Chuck was out at the fence at dawn, yelling at it again. His planner fell out of his overalls."),
            ("cowleen", "The wind took a page. It's caught up in the Old Oak."),
            ("cowleen", "I could see the word 'Sunday' on it, and a number. I'd like to know which number."),
            ("you", "Moo. (Let's go and look.)"),
        ])
        g.cutscene_end_now()
        c.follow(lambda: g.player.pos, 3.5, 3.4)
        g.ui.popup_sub("WASD walk   Mouse look   Shift gallop   C sneak\n"
                       "E interact   Left click headbutt   Tab journal   H hint", 12)

    def d1_oak(self):
        g = self.g
        self.objectives(("oak", "Knock the page out of the Old Oak"))
        self.mark((-50, -35, "Old Oak"))
        hit = {"d": False}

        def headbutt(eye, fwd):
            p = g.player
            if math.hypot(p.x + 50, p.z + 35) < 3.4:
                hit["d"] = True
                return True
            return False
        self.hook("headbutt", headbutt)
        g.on("oak", "Look up at the page",
             lambda gg: gg.examine("The page is snagged way up in the branches. A good headbutt to the trunk might "
                                   "shake it loose. (Left click)"))
        yield lambda: hit["d"]
        g.complete("oak")
        g.audio.play("headbutt", vol=1.0)
        g.audio.play("wood_crack", vol=0.4)
        g.cutscene_start(letterbox=True)
        g.cam_set((-40, 4.5, -44), (-47, 3, -45))
        page = self.props.pop("page_tree", None) or models.item_model("page", position=(-49.2, 6.2, -34.1))
        self.props["page_fall"] = page
        start = (-49.2, 6.2, -34.1)
        end = (-44.0, 0.09, -57.0)
        t, T = 0.0, 4.5
        while t < T:
            t += min(0.05, time.dt)
            k = t / T
            x = start[0] + (end[0] - start[0]) * k + math.sin(k * 9) * 1.2 * (1 - k)
            z = start[2] + (end[2] - start[2]) * k
            y = start[1] + (end[1] - start[1]) * (k ** 0.8) + math.sin(k * 14) * 0.25 * (1 - k)
            page.position = (x, max(end[1], y), z)
            page.rotation = (math.sin(k * 12) * 50, k * 400, math.cos(k * 10) * 40)
            if k < 0.35:
                g.cam_set((-40, 4.5, -44), (x, y, z))
            yield None
        page.rotation = (90, 30, 0)
        g.audio.play("splash", vol=0.6, pos=end, rng=40)
        yield 0.6
        g.cutscene_end_now()
        yield from g.talk([("cowleen", "Of course. Of course it went in the pond.")])

    def d1_page(self):
        g = self.g
        self.remove_prop("page_fall")
        self.objectives(("page", "Fish the page out of the pond"))
        self.mark((-44, -57, "Page"))
        got = {"d": False}

        def take(gg):
            self.remove_item("page")
            gg.inv.add("page")
            got["d"] = True
        self.item("page", "page", (-44.0, 0.09, -57.0), "Soggy page", "Pick up the page", take, rot=30, bob=True,
                  radius=0.5, reach=3.0)
        yield lambda: got["d"]
        g.complete("page")
        yield from g.show_document("Chuck's planner", PLANNER)
        c = g.cows["cowleen"]
        c.trail_fn = None
        if math.hypot(c.x - g.player.x, c.z - g.player.z) > 6:
            p = g.player
            c.teleport((p.x + 2.5, 0, p.z + 2.5))
        yield from g.talk([
            ("you", "Moo. (Forty-seven.)"),
            ("cowleen", "Yeah."),
            ("you", "Moo. (That's me. On Sunday. Next to 'barbecue'.)"),
            ("cowleen", "And somebody called twelve goes on Thursday. I don't know who twelve is. Half the tags on "
                        "this farm are too muddy to read."),
            ("cowleen", "You're not going to be anybody's barbecue. Go and tell the others."),
            ("cowleen", "Moozart's by the pond. Sir Loin's at the salt lick, Cowpernicus is under the oak, "
                        "Mooriarty's in his hay bales in the far corner, and Moomaw's by the trough."),
            ("cowleen", "Then we meet at the oak at sundown. Cowpernicus will want to make a plan. He always does."),
        ])
        c.look = "player"

    CREW = ["moozart", "sirloin", "cowpernicus", "mooriarty", "moomaw"]

    def d1_crew(self):
        g = self.g
        told = set(self.flags.get("d1_told", []))

        def refresh():
            n = len(told)
            objs = [("crew", f"Tell the others ({n}/5)")]
            for k in self.CREW:
                objs.append((f"t_{k}", "   " + FRIENDS[k][0]))
            self.objectives(*objs)
            for k in told:
                g.complete(f"t_{k}", sound=False)
            self.mark(*[(self.FRIEND_SPOTS[k][0], self.FRIEND_SPOTS[k][2], FRIENDS[k][0]) for k in self.CREW
                        if k not in told])

        def teller(key, lines, after=None):
            def fn():
                res = yield from lines()
                if key not in told:
                    told.add(key)
                    self.flags["d1_told"] = sorted(told)
                    g.audio.play("ding", vol=0.5)
                    if after:
                        after()
                    refresh()
                return res
            return fn

        def moozart_lines():
            mz = g.cows["moozart"]
            yield from g.talk([("moozart", "Shh. Listen. I've got the first four bars.")])
            self.moo_music("moozart_4", mz)
            yield 11.0
            self.unduck()
            yield from g.talk([
                ("moozart", "That's all of it. I've had those four bars since spring. The fifth one won't come."),
                ("you", "Moo. (Chuck's planner says I'm going to Processing on Sunday.)"),
                ("moozart", "..."),
                ("moozart", "Then I'd better finish this before Sunday. You should hear how it ends."),
                ("moozart", "Is anyone else on the list?"),
                ("you", "Moo. (Number twelve. Thursday.)"),
                ("moozart", "Twelve. Poor thing. I don't even know who that is."),
            ])

        def sirloin_lines():
            yield from g.talk([
                ("sirloin", "HALT! Who approaches the Salt Lick of Sir Loin?"),
                ("you", "Moo. (Me. We see each other every day.)"),
                ("sirloin", "Forty-Seven. What news?"),
                ("you", "Moo. (Chuck's planning to eat me on Sunday.)"),
                ("sirloin", "Then he'll have to get through me first. And I am very large. Look at me."),
                ("sirloin", "A knight should have a helm, though. Every knight in the old stories wears one. I have never "
                            "had one."),
                ("sirloin", "If you find a helm, or anything shaped like a helm, bring it to me."),
            ])

        def cowpernicus_lines():
            yield from g.talk([
                ("cowpernicus", "Oh, hi. I'm working out where the sun goes at night. I'm eighty percent sure it's "
                                "behind the silo."),
                ("you", "Moo. (Sunday. Processing. Me.)"),
                ("cowpernicus", "Oh. Okay. Okay, that's a problem with a deadline. I'm good with deadlines."),
                ("cowpernicus", "Give me until sundown. Meet me under the oak and I'll have a plan with numbered steps."),
                ("cowpernicus", "Also, unrelated: Chuck owns spare reading glasses. If you ever find them, I would "
                                "like to see things."),
            ])

        def mooriarty_lines():
            yield from g.talk([
                ("mooriarty", "Psst. Forty-Seven. In here."),
                ("mooriarty", "I heard about Sunday. Bad business. I'm sorry."),
                ("mooriarty", "Now, I sell things that could help. More rocks than you can fit in your mouth. Rubber "
                              "goods. A disguise."),
                ("mooriarty", "I only take Golden Clovers. There are twenty of them on this farm, if you know where to "
                              "look. I know. I'm not telling."),
                ("mooriarty", "Come back when you've found a few."),
            ])
            self.setf("mooriarty_met")

        def moomaw_lines():
            yield from g.talk([
                ("moomaw", "Morning, dear. You look like you've seen the inside of Chuck's house."),
                ("you", "Moo. (He wrote my number next to Sunday. And 'barbecue'.)"),
                ("moomaw", "Oh, sweetheart."),
                ("moomaw", "He did the same thing to my Earl. Big Earl. Eleven years ago. He wrote it on the calendar "
                           "in the kitchen and drew a circle round it."),
                ("moomaw", "Chuck keeps a photo of Earl in his office, of all places. With the ribbon. As if they were "
                           "friends."),
                ("moomaw", "If you're ever in that house, I'd like that picture back. It's the only one there is."),
            ])
        self.hook("talk:moozart", teller("moozart", moozart_lines))
        self.hook("talk:sirloin", teller("sirloin", sirloin_lines,
                                         lambda: g.side_quest("helm", "Find Sir Loin a helm", "active")))
        self.hook("talk:cowpernicus", teller("cowpernicus", cowpernicus_lines,
                                             lambda: g.side_quest("specs", "Find Cowpernicus some glasses", "active")))
        self.hook("talk:mooriarty", teller("mooriarty", mooriarty_lines))
        self.hook("talk:moomaw", teller("moomaw", moomaw_lines,
                                        lambda: g.side_quest("photo", "Bring Moomaw the photo of Big Earl", "active")))
        refresh()
        yield lambda: len(told) >= 5 and not g.busy
        g.complete("crew")
        yield 1.0

    def walk_friends_to(self, spots):
        g = self.g
        for k, (x, y, z, yaw) in spots.items():
            c = g.cows[k]
            if c.visible:
                c.trail_fn = None
                c.goto((x, y, z), 2.2)

    def d1_meeting(self):
        g = self.g
        g.set_time("sunset", 10)
        self.walk_friends_to(OAK_MEET)
        g.cows["cowleen"].trail_fn = None
        self.objectives(("meet", "Crew meeting at the Old Oak"))
        self.mark((-50, -35, "Meeting"))
        yield lambda: math.hypot(g.player.x + 50, g.player.z + 35) < 7.5 and not g.busy
        g.complete("meet")
        g.cutscene_start(letterbox=True)
        self.gather_at(OAK_MEET)
        g.player.teleport(-50.5, 0, -41.5, 0)
        g.cam_set((-56.5, 3.2, -43.0), (-50, 1.2, -34.5))
        yield from g.talk([
            ("cowpernicus", "Okay. Thanks for coming, everyone. I drew a diagram."),
            ("cowpernicus", "I drew it in the dirt. Sir Loin, you're standing on it."),
            ("sirloin", "I am guarding it."),
            ("cowpernicus", "Step one. The fence runs off a generator in Chuck's tool shed. No generator, no zap."),
            ("cowpernicus", "Step two. The main gate's chained shut, and there's a cattle grid in front of it. We need "
                            "something big enough to go through both."),
            ("mooriarty", "And step three?"),
            ("cowpernicus", "Step three is everybody runs. I'm still working out the details of step three."),
            ("moomaw", "It's a lovely plan, dear. It has steps."),
            ("cowleen", "We start with the shed. Tomorrow."),
            ("moozart", "..."),
            ("cowleen", "Moozart?"),
            ("moozart", "Sorry. I was thinking about the fifth bar."),
            ("cowleen", "Here comes Chuck for the headcount. Forty-Seven, practise for tomorrow. Get behind him and "
                        "take his pencil."),
            ("cowpernicus", "He sees about a hundred degrees in front of him and nothing behind. Crouch to stay "
                            "quiet. C or Ctrl."),
        ])
        g.cutscene_end_now()

    def d1_pencil(self):
        g = self.g
        f = g.farmer
        f.teleport((-24, 0, -35), 270)
        f.set_tool("clipboard")
        self.chuck_routine([
            ("tool", "clipboard"),
            ("go", (-33, 0, -32), 1.6), ("wait", 11, "count", COUNT_LINES, (-44, -26)),
            ("go", (-42, 0, -22), 1.6), ("wait", 11, "count", COUNT_LINES, (-52, -30)),
            ("go", (-40, 0, -45), 1.6), ("wait", 11, "count", COUNT_LINES, (-45, -58)),
            ("go", (-28, 0, -40), 1.6), ("wait", 9, "count", COUNT_LINES, (-26, -55)),
            ("say", "Dang it. Lost count. From the top."),
        ])
        f.hearing = 0.6
        self.objectives(("pencil", "Steal Chuck's pencil during the headcount"))
        self.hook("hint", lambda: None)
        g.restricted_fn = lambda gg: True if math.hypot(gg.player.x - f.x, gg.player.z - f.z) < 7 else None

        def shooed():
            p = g.player
            f.say("Forty-seven, quit crowdin' me. Go stand with the others.", force=True)
            dx, dz = p.x - f.x, p.z - f.z
            d = math.hypot(dx, dz) or 1
            p.teleport(f.x + dx / d * 10, 0, f.z + dz / d * 10, p.yaw)
            f.susp = 0.0
            f.set_marker("")
            f.resume_routine()
            g.ui.popup_sub("He saw you coming. Circle round behind him and crouch.")
            return True
        self.hook("caught", shooed)
        got = {"d": False}

        def steal(gg):
            if not self.behind_chuck():
                gg.examine("Not from the front. He'd see you. Circle round behind him.")
                return
            got["d"] = True
        self.chuck_ia("Take his pencil", steal)
        self.mark((f.x, f.z, "Chuck"))

        def upd(dt):
            self.base_update(dt)
            self.marks = [(f.x, f.z, "Chuck")]
        self.hook("update", upd)
        yield lambda: got["d"]
        g.ia.remove("st_chuck")
        g.restricted_fn = None
        g.inv.add("pencil")
        g.complete("pencil")
        f.scripted()
        f.pose = "count"
        yield from g.talk([
            ("chuck", "Forty-four, forty-five, forty-f... hey. Where'd my pencil go?"),
            ("chuck", "Aw, heck. Lost count."),
            ("chuck", "...Forty-nine. Close enough."),
        ])
        f.set_tool(None)
        self.chuck_routine([
            ("go", (-21, 0, -35), 2.2), ("call", lambda: g.world.doors["pasture_gate"].set_open(True)),
            ("go", (-14, 0, -35.5), 2.2), ("call", lambda: g.world.doors["pasture_gate"].set_open(False)),
            ("go", (40, 0, 18), 2.4), ("go", (56, 0, 23), 2.4), ("hide",), ("stop", "idle"),
        ])
        f.hearing = 1.0
        g.set_time("dusk", 12)
        g.ambience("night")
        self.base_music = "music_night"
        yield from g.talk([("cowleen", "Nicely done. Get some sleep. Tomorrow's the shed.")])

    # ==================================================================
    # TUESDAY
    # ==================================================================
    def setup_day2(self):
        g = self.g
        self.morning()
        self.wake_in_stall()
        self.place_tractor(5, -21, 0)
        self.revving = False
        g.mask_noise("tractor", (5, 0, -21), 27, lambda: self.revving)
        if not self.done("d2_shed"):
            self._shed_items()
        self.chuck_tuesday()
        self.dhook("update", self.tue_update)
        self.dhook("use", self.radio_use)
        self.dhook("caught_line", lambda: random.choice([
            "Hey! How'd you get out here?", "Well, look who's out for a walk. Back you go.",
            "Forty-seven! Pasture! Now!"]))
        self.faint = {"armed": False, "t": 0.0}

    def _shed_items(self):
        g = self.g

        def radio(gg):
            self.remove_item("radio")
            gg.inv.add("radio")
            gg.complete("radio")
        if not g.inv.has("radio") and not self.done("radio_taken"):
            self.item("radio", "radio", (-7.4, 1.08, -18.62), "Chuck's radio", "Take the radio", radio, rot=10)

        def glasses(gg):
            self.remove_item("glasses")
            gg.inv.add("glasses")
            self.setf("glasses_taken")
        if not self.done("glasses_taken"):
            self.item("glasses", "glasses", (-6.6, 1.06, -25.55), "Spare reading glasses", "Take the glasses", glasses)

        def bucket(gg):
            self.remove_item("bucket")
            gg.inv.add("bucket")
            self.setf("bucket_taken")
        if not self.done("bucket_taken"):
            self.item("bucket", "bucket", (-4.8, 0.16, -24.8), "Rusty bucket", "Take the bucket", bucket, radius=0.35)

    def chuck_tuesday(self):
        g = self.g
        gate = g.world.doors["pasture_gate"]

        def rev(on):
            def fn():
                self.revving = on
                if on:
                    g.audio.loop("tractor", "loop_tractor", vol=1.0, pos=(5, 1.5, -21), rng=70, group="sfx")
                else:
                    g.audio.stop_loop("tractor", 0.4)
            return fn

        def open_gate():
            gate.set_open(True)
            g.audio.play("door_creak", vol=0.8, pos=(-18, 1, -35), rng=40)
            self.faint["armed"] = self.faint.get("asked", False)

        def close_gate():
            # tue_update shuts it as soon as nobody's standing in the gateway
            self.faint["close_pending"] = True
        self.chuck_routine([
            ("call", rev(False)), ("tool", "bucket"),
            ("go", (-14.8, 0, -35.6), 2.2), ("call", open_gate),
            ("go", (-28.4, 0, -22.0), 2.0), ("face", (-30, -22)),
            ("wait", 11, "work", FEED_LINES, (-30, -22)),
            ("go", (-14.6, 0, -36.2), 2.2), ("call", close_gate),
            ("tool", "oilcan"),
            ("go", (3.2, 0, -19.4), 2.2), ("face", (5, -21)),
            ("call", rev(True)), ("wait", 8, "work", OIL_LINES, (5, -21)),
            ("call", rev(False)), ("wait", 6, "work", None, (5, -21)),
            ("call", rev(True)), ("wait", 8, "work", OIL_LINES, (5, -21)),
            ("call", rev(False)), ("wait", 5, "work", None, (5, -21)),
            ("call", rev(True)), ("wait", 8, "work", OIL_LINES, (5, -21)),
            ("call", rev(False)), ("wait", 3, "look"),
        ])
        g.farmer.teleport((0, 0, -30), 0)

    def tue_update(self, dt):
        self.base_update(dt)
        g = self.g
        if self.faint.get("close_pending"):
            p = g.player
            gate = g.world.doors["pasture_gate"]
            if not (abs(p.x + 18) < 1.5 and -38.6 < p.z < -31.4):
                self.faint["close_pending"] = False
                if gate.is_open:
                    gate.set_open(False)
                    g.audio.play("door_close", vol=0.8, pos=(-18, 1, -35), rng=40)
        if self.revving:
            self.faint.setdefault("puff", 0.0)
            self.faint["puff"] -= dt
            if self.faint["puff"] <= 0:
                self.faint["puff"] = 0.3
                from .vehicle import Puff
                self.fx.append(Puff((5.3, 2.7, -19.7)))
        # Cowleen's fainting routine: once Chuck is inside the pasture
        fa = self.faint
        f = g.farmer
        c = g.cows["cowleen"]
        if fa.get("armed") and f.state == "routine" and g.phys.in_zone("pasture", f.x, f.z) and not fa.get("active"):
            fa["armed"] = False
            fa["asked"] = False
            fa["active"] = True
            fa["t"] = 11.0
            c.model.lying_target = 1.0
            c.bubble("MOOOoooo...", 2.5)
            g.audio.play("moo_cowleen_long_0", vol=1.0, pos=(c.x, 1, c.z), rng=50, group="voice")
            f.scripted()
            f.goto((c.x + 1.6, 0, c.z + 0.4), 3.2)
            f.say("Cowleen? You okay, girl? Say somethin'!", force=True)
            fa["said"] = False
        if fa.get("active"):
            fa["t"] -= dt
            if not f.path:
                f.face_target = (c.x, c.z)
                f.pose = "look"
                if not fa["said"]:
                    fa["said"] = True
                    f.say("Is it the heat? It's not even hot. Breathe, girl.", force=True)
            if fa["t"] <= 0:
                fa["active"] = False
                c.model.lying_target = 0.0
                c.bubble("Moo.")
                f.say("Huh. Faintin' cow. I'll look it up.", force=True)
                f.resume_routine()

    def day2(self):
        yield from self.step("d2_wake", self.d2_wake)
        yield from self.step("d2_out", self.d2_out,
                             hint="When Chuck carries the feed to the trough he leaves the gate open behind him. Slip "
                                  "out while his back is turned, or ask Cowleen to faint.")
        yield from self.step("d2_board", self.d2_board,
                             hint="The loose board is on the back of the shed, facing the pasture. Headbutt it three "
                                  "times, but only while Chuck is revving the tractor. The engine covers the noise.")
        yield from self.step("d2_shed", self.d2_shed,
                             hint="The sticky note says the combination is Chuck's perfect bowling score. His trophy is "
                                  "on the shelf.")
        yield from self.step("d2_return", self.d2_return,
                             hint="The pasture gate's bolt is on the outside, where you are. Open it and walk in.")
        yield from self.step("d2_radio", self.d2_radio, hint="Take the radio to Moozart by the pond.")
        yield from self.step("d2_ram", self.d2_ram, hint="Cowpernicus is under the Old Oak.")
        yield from self.step("d2_sleep", self.sleep_step, hint="Bed. Stall 47.")
        yield from self._run_day(3)

    def d2_wake(self):
        g = self.g
        c = g.cows["cowleen"]
        c.teleport((-45.6, 0, -4.2), 20)
        g.cutscene_start(letterbox=True)
        g.player.look_at_point((c.x, 1.3, c.z))
        yield from g.fade_in(1.2)
        yield from g.talk([
            ("cowleen", "Morning. Chuck brings the feed out soon. He opens the gate, walks to the trough and leaves "
                        "the gate open behind him. Every single time."),
            ("cowleen", "While he's at the trough, go. If you want a distraction, ask me. I'm a very good fainter."),
            ("cowleen", "The tool shed's just past the east fence. It's padlocked, but Mooriarty says there's a loose "
                        "board round the back."),
        ])
        g.cutscene_end_now()

    def d2_out(self):
        g = self.g
        self.objectives(("out", "Slip out of the pasture while Chuck brings the feed"))
        self.mark((-18, -35, "Pasture gate"), (-8, -22, "Tool shed"))

        def cowleen_talk():
            if self.faint.get("asked"):
                yield from g.talk([("cowleen", "I'm ready. When he comes through the gate, I go down.")])
                return True
            r = yield from g.say("cowleen", "Need me to faint?", choices=["Yes. Faint when Chuck comes in.",
                                                                         "Not yet."])
            if r == 0:
                self.faint["asked"] = True
                if g.world.doors["pasture_gate"].is_open:
                    self.faint["armed"] = True
                yield from g.talk([("cowleen", "Watch this. I've been practising on Moomaw.")])
            else:
                g.end_talk()
            return True
        self.hook("talk:cowleen", cowleen_talk)
        p = g.player
        yield lambda: not g.phys.in_zone("pasture", p.x, p.z) and p.x > -17.5
        g.complete("out")

    def d2_board(self):
        g = self.g
        self.objectives(("board", "Get into the tool shed (there's a loose board round the back)"))
        self.mark((-12, -22, "Loose board"))
        hits = {"n": self.flags.get("board_hits", 0)}
        ia = g.ia.get("shed_board")

        def butt(gg):
            pos = (SHED[0], 0.0, -22.2)
            if gg.noise_masked(pos):
                hits["n"] += 1
                self.flags["board_hits"] = hits["n"]
                gg.audio.play("wood_crack", vol=0.5, pos=pos, rng=20)
                if hits["n"] < 3:
                    gg.ui.popup_sub(f"CRACK. The tractor covered that. ({hits['n']}/3)", 3)
            else:
                gg.audio.play("wood_crack", vol=1.0, pos=pos, rng=60)
                gg.noise(pos, 24, "crash")
                gg.ui.popup_sub("WHAM. Much too loud. Wait until Chuck's revving the tractor.", 4)
        ia.on_headbutt = butt
        yield lambda: hits["n"] >= 3
        ia.on_headbutt = None
        self.setf("board_broken")
        g.world.colliders["shed_board"].enabled = False
        g.world.shed_board.enabled = False
        self.fallen_board()
        g.audio.play("thump", vol=0.6, pos=(SHED[0], 0.5, -22), rng=30)
        g.ui.popup_sub("The board falls in. You're through.", 3)
        p = g.player
        yield lambda: g.phys.in_zone("shed", p.x, p.z)
        g.complete("board")

    def d2_shed(self):
        g = self.g
        self.objectives(("toolbox", "Open the toolbox"), ("radio", "Take Chuck's radio"))
        if g.inv.has("radio"):
            g.complete("radio", sound=False)
        self.mark((-9.3, -18.6, "Toolbox"), (-7.4, -18.6, "Radio"))
        opened = {"d": False}

        def toolbox(gg):
            r = yield from self.combo(3, "Toolbox")
            if r == "117":
                opened["d"] = True
                gg.audio.play("blip_hi", vol=0.6)
            elif r:
                gg.examine("The lock doesn't budge. The sticky note on the wall had a hint.")
        g.on("toolbox", "Try the combination lock", toolbox)
        yield lambda: opened["d"]
        g.complete("toolbox")
        g.inv.add("pliers")
        yield from g.talk([
            ("you", "Moo. (Pliers.)"),
            ("you", "Moo. (Hold still, bell.)"),
        ])
        g.audio.play("metal_clang", vol=0.5, pitch=1.6)
        yield 0.4
        g.player.has_bell = False
        self.setf("bell_off")
        g.inv.add("cowbell", silent=True)
        g.ui.toast("Cowbell off. You're quiet now.", "cowbell")
        g.ui.popup_sub("No more jingling. You can still throw the bell to make a noise somewhere else. [R]", 6)
        yield lambda: g.inv.has("radio")
        self.setf("radio_taken")

    def d2_return(self):
        g = self.g
        self.objectives(("back", "Get back into the pasture"))
        self.mark((-18, -35, "Pasture gate"))

        def back():
            self.return_to_pasture()
            return True
        self.hook("after_caught", back)
        p = g.player
        yield lambda: g.phys.in_zone("pasture", p.x, p.z) and not g.runner.running("caught")
        g.complete("back")
        yield 1.5
        gate = g.world.doors["pasture_gate"]
        if gate.is_open:
            gate.set_open(False)
            g.audio.play("door_close", vol=0.6, pos=(-18, 1, -35), rng=30)
            g.ui.popup_sub("Cowleen noses the gate shut behind you.", 3)
        g.set_time("sunset", 12)
        self.chuck_routine([("go", (40, 0, 18), 2.4), ("go", (56, 0, 23), 2.4), ("hide",), ("stop", "idle")])
        self.revving = False
        g.audio.stop_loop("tractor", 0.5)

    def d2_radio(self):
        g = self.g
        self.objectives(("radio_mz", "Give the radio to Moozart"))
        mz = g.cows["moozart"]
        self.mark((mz.x, mz.z, "Moozart"))
        done = {"d": False}

        def talk():
            if not g.inv.has("radio"):
                yield from g.talk([("moozart", "Did you find anything in the shed? Anything with music in it?")])
                return True
            yield from g.talk([("moozart", "Is that Chuck's radio? Turn it on. I've heard it through the barn wall "
                                           "for years.")])
            g.audio.loop("radio", "loop_radio", vol=0.9, pos=(mz.x, 1, mz.z), rng=30, group="sfx")
            g.audio.music_duck = 0.1
            yield 7.0
            yield from g.talk([
                ("moozart", "It's a song about a man whose truck breaks down, and then his dog leaves, and then it "
                            "starts to rain."),
                ("moozart", "It's a terrible song. But listen to what it does in the middle. It goes down when you "
                            "expect it to go up."),
                ("moozart", "Oh. Oh, that's my fifth bar. And the sixth. Turn it off, turn it off."),
            ])
            g.audio.stop_loop("radio", 0.3)
            self.moo_music("moozart_8", mz)
            yield 20.0
            self.unduck()
            yield from g.talk([
                ("moozart", "Eight bars. I have eight bars."),
                ("moozart", "Keep that radio away from me. If I hear the rest of the song I'll write a sad one."),
            ])
            done["d"] = True
            return True
        self.hook("talk:moozart", talk)
        yield lambda: done["d"]
        g.complete("radio_mz")

    def d2_ram(self):
        g = self.g
        self.objectives(("ram", "Talk to Cowpernicus"))
        cp = g.cows["cowpernicus"]
        self.mark((cp.x, cp.z, "Cowpernicus"))
        done = {"d": False}

        def talk():
            yield from g.talk([
                ("cowpernicus", "Moozart's smiling. That's never happened. What did you do?"),
                ("cowpernicus", "Anyway. News. I've been watching the tractor all afternoon."),
                ("cowpernicus", "It's the only thing on this farm heavier than the main gate. That's step two. The "
                                "tractor is our battering ram."),
                ("cowpernicus", "Tomorrow somebody should look at what it needs to run. I would, but I can't see "
                                "past the fence."),
            ])
            done["d"] = True
            return True
        self.hook("talk:cowpernicus", talk)
        yield lambda: done["d"]
        g.complete("ram")
        g.set_time("dusk", 10)
        g.ambience("night")
        self.base_music = "music_night"

    # ==================================================================
    # WEDNESDAY
    # ==================================================================
    def setup_day3(self):
        g = self.g
        self.morning()
        self.wake_in_stall()
        f = g.farmer
        f.trip_rate = 1 / 50.0
        self.chuck_wed_chores()
        if not self.done("tractor_key_taken"):
            self._rafter_key()
        if not self.done("jerrycan_taken"):
            self._jerrycan()
        if not self.done("boot_taken") and not self.done("moohole_open"):
            def boot(gg):
                self.remove_item("boot")
                gg.inv.add("boot")
                self.setf("boot_taken")
            self.item("boot", "boot", (-37.0, 0.12, -61.8), "Chuck's rubber boot", "Pull the boot out of the mud",
                      boot, rot=60, radius=0.45, reach=3.0)
        self.dhook("update", self.wed_update)
        self.dhook("use", self.radio_use)
        self.dhook("caught_line", lambda: random.choice([
            "Ow. OW. Don't make me chase you, my tooth can't take it.", "Hey! Mmph. Back in the pasture.",
            "I'm in no mood, forty-seven. None."]))
        self.wed = {"phase": "chores", "t": 95.0}

    def chuck_wed_chores(self):
        self.chuck_routine([
            ("go", (-2, 0, -24), 1.5), ("wait", 10, "ow", TOOTH_LINES),
            ("go", (14, 0, -14), 1.5), ("wait", 8, "work", TOOTH_LINES, (14.5, -12.5)),
            ("go", (0, 0, 10), 1.5), ("wait", 6, "ow", TOOTH_LINES),
            ("go", (20, 0, 23), 1.5), ("wait", 8, "look"),
            ("go", (-8, 0, -40), 1.5), ("wait", 8, "work", TOOTH_LINES, (-8, -41)),
        ])

    def wed_update(self, dt):
        self.base_update(dt)
        g = self.g
        f = g.farmer
        w = self.wed
        if not self.done("d3_lock") or self.enemy is not None:
            return
        w["t"] -= dt
        if w["phase"] == "chores" and w["t"] <= 0 and f.state == "routine":
            w["phase"] = "to_nap"
            f.set_routine([("say", "That's it. I'm takin' a nap. Stupid tooth."), ("go", (54.5, Y, 27.3), 1.6),
                           ("stop", "idle")])
        elif w["phase"] == "to_nap" and f.state == "routine" and not f.path and f.r_i >= 2:
            w["phase"] = "nap"
            w["t"] = 150.0
            f.sleep((54.5, Y, 27.3), 180, pose="nap", outfit=None)
            self.prop("chair", self._chair((54.5, Y, 27.3), 180))
        elif w["phase"] == "nap" and w["t"] <= 0 and f.state == "sleep":
            w["phase"] = "chores"
            w["t"] = 95.0
            f.wake()
            f.sleeping = False
            f.say("Hnnk. Who... right. Chores.", force=False)
            self.chuck_wed_chores()

    def _chair(self, pos, yaw):
        mb = MeshBuilder()
        mb.box((0, 0.42, 0), (0.7, 0.08, 0.6), uv_density=1)
        mb.box((0, 0.85, -0.3), (0.7, 0.8, 0.06), uv_density=1, rot=(-10, 0, 0))
        for sx in (-0.3, 0.3):
            for sz in (-0.25, 0.25):
                mb.box((sx, 0.2, sz), (0.05, 0.42, 0.05), uv_density=1)
        return Entity(model=mb.build(), texture=tex("wood"), shader=FARM_SHADER, position=(pos[0], pos[1], pos[2]),
                      rotation_y=yaw)

    def _rafter_key(self):
        g = self.g
        pos = (20.0, 5.55, 10.0)
        key = models.item_model("tractor_key", position=pos, rotation=(90, 0, 0), scale=2.0)
        string = MeshBuilder().box((0, 0.35, 0), (0.015, 0.7, 0.015), color=(0.85, 0.8, 0.6, 1), uv_rect=models.WHITE)
        s = Entity(model=string.build(solid_rect=models.WHITE), texture=tex("atlas"), shader=FARM_SHADER, position=pos)
        for c in key.children:
            c.set_shader_input("u_emissive", 0.35)
        self.prop("rafter_key", key)
        self.prop("rafter_string", s)
        ia = g.ia.add(Interactable("st_rafter_key", pos, 0.35, "Tractor key", None, "Look at the key", 6.0))
        ia.handlers.append(Handler("Look at the key", lambda gg: gg.examine(
            "The tractor key, hanging off a nail on the rafter. Much too high. Something thrown could knock it down."),
            None, "global"))
        ia.on_rock = lambda gg, hit: self._key_falls()

    def _key_falls(self):
        g = self.g
        g.ia.remove("st_rafter_key")
        self.remove_prop("rafter_string")
        k = self.props.pop("rafter_key", None)
        if k:
            destroy(k)
        g.audio.play("metal_clang", vol=0.7, pos=(20, 4, 10), rng=30)
        land = (20.0, L + 0.06, 10.0)

        def take(gg):
            self.remove_item("tractor_key")
            gg.inv.add("tractor_key")
            self.setf("tractor_key_taken")
            gg.complete("key")
        self.item("tractor_key", "tractor_key", land, "Tractor key", "Take the tractor key", take, scale=2.0,
                  glow=0.4, radius=0.35)
        g.ui.popup_sub("Clink. The key drops onto the hayloft floor.", 3)

    def _jerrycan(self):
        def take(gg):
            if not gg.flags.get("cluck_beaten"):
                gg.examine("Cluck Norris is watching you. You'd have to go through him first.")
                return
            self.remove_item("jerrycan")
            gg.inv.add("jerrycan")
            self.setf("jerrycan_taken")
            gg.complete("fuel_get")
        self.item("jerrycan", "jerrycan", (36.6, 0.2, -29.6), "Jerry can", "Take the jerry can", take, rot=90,
                  radius=0.4)

    def day3(self):
        yield from self.step("d3_lock", self.d3_lock)
        yield from self.step("d3_moohole", self.d3_moohole,
                             hint="Rubber doesn't conduct. Chuck lost a boot in the pond. Or Mooriarty sells a rubber "
                                  "chicken. Take it to the sagging wire at the far end of the east fence.")
        yield from self.step("d3_barn", self.d3_barn,
                             hint="The barn's side door (west wall) is never locked. Have a look at the tractor.")
        yield from self.step("d3_parts", self.d3_parts,
                             hint="The key hangs from a rafter over the hayloft: go up the ramp and throw a rock at it. "
                                  "The diesel's in the chicken run, guarded by Cluck Norris. Chuck naps on the porch "
                                  "around midday.")
        yield from self.step("d3_trough", self.d3_trough, hint="Moozart's waiting at the trough.")
        yield from self.step("d3_sleep", self.sleep_step, hint="Bed. Stall 47.")
        yield from self._run_day(4)

    def d3_lock(self):
        g = self.g
        f = g.farmer
        g.cutscene_start(letterbox=True)
        f.set_routine([])
        f.scripted()
        f.teleport((-14.8, 0, -35.2), 270)
        f.set_tool("wrench")
        g.player.teleport(-27, 0, -33, 90)
        g.cam_set((-22.5, 2.2, -31.5), (-16, 1.2, -35.3))
        yield from g.fade_in(1.2)
        f.pose = "ow"
        yield from g.talk([
            ("chuck", "Somebody's been usin' this gate. Other than me."),
            ("chuck", "Ow. Ow ow ow. Stupid tooth."),
        ])
        f.pose = "work"
        g.audio.play("chain", vol=0.9, pos=(-18, 1, -35), rng=40)
        yield 1.2
        self.setf("gate_locked")
        yield from g.talk([("chuck", "There. Padlock. Let's see you open THAT, whoever you are.")])
        f.set_tool(None)
        self.chuck_wed_chores()
        c = g.cows["cowpernicus"]
        c.teleport((-24.5, 0, -30.5), 200)
        g.cows["cowleen"].teleport((-25, 0, -36.5), 20)
        g.cam_set((-30.5, 2.4, -29.5), (-25.5, 1.2, -33.5))
        yield from g.talk([
            ("cowpernicus", "Okay, new problem. But I've been looking at the far end of the east fence. The bottom "
                            "wire sags. You could fit under it if something held it up."),
            ("cowpernicus", "Something rubber. Rubber doesn't conduct electricity. Please don't try it with your nose."),
            ("cowleen", "Chuck lost a boot in the pond last month. He hopped all the way back to the house. Best day "
                        "of my life."),
        ])
        g.cutscene_end_now()

    def d3_moohole(self):
        g = self.g
        self.objectives(("rubber", "Find something rubber"), ("hole", "Prop up the sagging wire at the far end "
                                                                      "of the east fence"))
        self.mark((-37, -61.8, "Boot?"), (MOOHOLE_POS[0], MOOHOLE_POS[1], "Sagging wire"))
        done = {"d": False}

        def rubber():
            return "boot" if g.inv.has("boot") else ("rubber_chicken" if g.inv.has("rubber_chicken") else None)

        def prop_it(gg):
            item = rubber()
            if not item:
                gg.audio.play("zap", vol=0.9)
                gg.ui.flash((1, 0.95, 0.4), 0.3)
                gg.player.shake = 0.5
                gg.player.vx -= 6
                gg.ui.popup_sub("ZAP. Right. Rubber first.", 3)
                gg.stats["zapped"] = gg.stats.get("zapped", 0) + 1
                return
            gg.inv.remove(item)
            self.setf("moohole_open")
            self.setf("moohole_item", item)
            gg.world.colliders["moohole"].enabled = False
            self.prop("moohole_boot", models.item_model(item, position=(MOOHOLE_POS[0], 0.55, MOOHOLE_POS[1]),
                                                        rotation=(0, 0, 90), scale=1.2))
            gg.audio.play("zap", vol=0.3, pitch=1.5)
            gg.ui.popup_sub("You wedge it under the bottom wire and push. The wire lifts. There's a gap now. "
                            "A cow-sized gap.", 5)
            done["d"] = True
        g.on("moohole", lambda gg: "Prop up the wire" if rubber() else "Squeeze under the wire", prop_it)
        yield lambda: rubber() is not None or done["d"]
        g.complete("rubber")
        yield lambda: done["d"]
        g.complete("hole")

    def d3_barn(self):
        g = self.g
        self.objectives(("look", "Look over the tractor in the barn"))
        self.mark((22, 1, "Tractor"), (10, 0.7, "Side door"))
        done = {"d": False}

        def look(gg):
            yield from gg.talk([
                ("narrator", "The ignition is empty. No key."),
                ("narrator", "The fuel gauge is resting on E."),
                ("narrator", "There's a hole where the spark plug should be. A note taped to the engine says: "
                             "'PLUG SOAKING IN VINEGAR (KITCHEN). -C'"),
                ("you", "Moo. (Key, fuel, spark plug. The plug's in the house. The other two I can find today.)"),
            ])
            done["d"] = True
        g.on("tractor", "Look the tractor over", look)
        yield lambda: done["d"]
        g.complete("look")
        self.setf("tractor_inspected")

    def d3_parts(self):
        g = self.g
        self.objectives(("key", "Find the tractor key"), ("fuel_get", "Find some diesel"),
                        ("fuel", "Fuel the tractor"))
        for k, fl in (("key", "tractor_key_taken"), ("fuel_get", "jerrycan_taken"), ("fuel", "tractor_fueled")):
            if self.done(fl):
                g.complete(k, sound=False)
        self.mark((20, 10, "Key"), (41, -34, "Coop"), (22, 1, "Tractor"))

        def fuel(gg):
            gg.inv.remove("jerrycan")
            self.setf("tractor_fueled")
            gg.audio.play("splash", vol=0.6, pitch=0.6)
            gg.complete("fuel")
            gg.examine("Glug glug glug. The needle wobbles up to F.")
        g.on("tractor", "Pour in the diesel", fuel, cond=lambda gg: gg.inv.has("jerrycan"))
        g.on("tractor", "Look at the tractor",
             lambda gg: gg.examine("Still needs: " + ", ".join(
                 [n for n, fl in (("the key", "tractor_key_taken"), ("diesel", "tractor_fueled")) if not self.done(fl)]
                 + ["the spark plug (it's in Chuck's kitchen)"])),
             cond=lambda gg: not gg.inv.has("jerrycan"))
        # Cluck Norris guards the coop
        if not self.done("cluck_beaten"):
            self.hook("update", self.cluck_watch)
        yield lambda: self.done("tractor_key_taken") and self.done("tractor_fueled")
        g.set_time("sunset", 12)

    def cluck_watch(self, dt):
        self.wed_update(dt)
        g = self.g
        p = g.player
        x0, x1, z0, z1 = COOP_RUN
        if self.enemy is None and not self.done("cluck_beaten") and x0 + 0.5 < p.x < x1 and z0 < p.z < z1 \
                and not g.runner.running("cluck"):
            g.runner.start(self.cluck_fight(), name="cluck", tag="day")

    def cluck_fight(self):
        g = self.g
        p = g.player
        g.cutscene_start(letterbox=True)
        boss = CluckNorris(g, (44.0, 0, -35.0), (COOP_RUN[0] + 0.3, COOP_RUN[1] - 0.3, COOP_RUN[2] + 0.3,
                                                  COOP_RUN[3] - 0.3))
        boss.active = False
        boss.yaw = math.degrees(math.atan2(p.x - 44, p.z + 35))
        boss._apply()
        self.enemy = boss
        g.cam_set((p.x + (44 - p.x) * 0.35, 1.6, p.z + (-35 - p.z) * 0.35 - 0.1), (44, 0.8, -35))
        g.audio.play("squawk", vol=1.0)
        yield from g.talk([
            ("cluck", "BAWK. Stop right there, cow."),
            ("cluck", "This is my coop. I've seen off two foxes, a weasel and a very confused goose."),
            ("cluck", "Nobody comes in. Turn around or get plucked."),
            ("you", "Moo. (Cows can't be plucked.)"),
            ("cluck", "We'll find out."),
        ])
        g.cutscene_end_now()
        self.lock_hud_music("music_boss", 0.7, 1.0)
        g.ui.set_boss("CLUCK NORRIS", 1.0)
        p.health = p.max_health
        g.ui.set_health(p.health, p.max_health, True)
        g.ui.popup_sub("Left click headbutt (gallop into it for double)\nRight click back-kick   R throw", 6)
        g.enemies.append(boss)
        boss.active = True
        result = {"r": None}
        boss.on_defeat = lambda: result.__setitem__("r", "win")
        self.hook("defeated", lambda: result.__setitem__("r", "lose"))
        while result["r"] is None:
            g.ui.set_health(p.health, p.max_health, True)
            x0, x1, z0, z1 = COOP_RUN
            if not (x0 - 1 < p.x < x1 + 1 and z0 - 1 < p.z < z1 + 1):
                result["r"] = "fled"
            yield None
        self.hooks.pop("defeated", None)
        g.ui.set_boss("", 0, False)
        g.ui.set_health(0, 0, False)
        self.unlock_music()
        if result["r"] != "win":
            if boss in g.enemies:
                g.enemies.remove(boss)
            boss.remove()
            self.enemy = None
            p.health = p.max_health
            if result["r"] == "lose":
                g.cutscene_start(letterbox=True)
                yield from g.fade_out(0.6)
                p.teleport(31.5, 0, -35, 270)
                yield from g.fade_in(0.6)
                g.cutscene_end_now()
                g.ui.popup_sub("Cluck Norris stands on your head for a while, then lets you go. "
                               "'Come back when you're ready.'", 6)
            return
        g.stats["cluck_beaten"] = 1
        yield 1.0
        g.cutscene_start(letterbox=True)
        boss.state = "idle"
        boss.model.rig.rotation_z = 0
        boss.active = False
        g.enemies.remove(boss)
        g.cam_set((p.x + (boss.x - p.x) * 0.4, 1.5, p.z + (boss.z - p.z) * 0.4 - 0.2), (boss.x, 0.8, boss.z))
        yield from g.talk([
            ("cluck", "Bawk... okay. Okay. You've got a hard head, cow."),
            ("cluck", "What do you want with Chuck's diesel?"),
            ("you", "Moo. (We're driving his tractor through the main gate on Sunday. All of us are leaving.)"),
            ("cluck", "...All of you?"),
            ("cluck", "I've crowed at that sunrise every morning for six years. Not one thank you."),
            ("cluck", "Sunday morning, I'll crow louder than I've ever crowed. That's your signal. Take the can."),
        ])
        g.audio.play("rooster_crow", vol=1.0, pos=(boss.x, 1, boss.z), rng=120)
        yield 2.5
        g.cutscene_end_now()
        self.setf("cluck_beaten")
        boss.remove()
        self.enemy = None
        self.prop("cluck_friend", models.RoosterModel(headband=True, scale=1.6, position=(41.5, 0, -33.0),
                                                     rotation_y=260))
        self.hook("update", self.wed_update)

    def d3_trough(self):
        g = self.g
        mz = g.cows["moozart"]
        mz.teleport((-32.3, 0, -21.4), 90)
        mz.look = "player"
        g.cows["cowleen"].teleport((-33.5, 0, -24.8), 40)
        self.objectives(("trough", "Head back to the pasture. Moozart's waiting at the trough."))
        self.mark((-31, -22, "Moozart"))
        p = g.player
        yield lambda: math.hypot(p.x + 32, p.z + 22) < 5 and not g.busy
        g.complete("trough")
        g.cutscene_start(letterbox=True)
        g.set_time("sunset")
        p.teleport(-31.5, 0, -19.0, 180)
        p.look_at_point((mz.x, 1.3, mz.z))
        yield from g.talk([
            ("moozart", "Was that the rooster this morning? The big one. I heard it through the fence."),
            ("you", "Moo. (Cluck Norris. He's on our side now.)"),
            ("moozart", "It went up at the end. Up and up, and it never came down. Listen."),
        ])
        self.moo_music("moozart_12", mz)
        yield 29.0
        self.unduck()
        yield from g.talk([
            ("moozart", "Twelve bars. Four more and it's finished."),
            ("moozart", "Could you do something for me? My ear tag's been itching for weeks. It's caked in mud. "
                        "Dunk it in the trough?"),
        ])
        g.cutscene_end_now()
        self.objectives(("wash", "Wash Moozart's ear tag in the trough"))
        done = {"d": False}
        g.on("trough", "Wash Moozart's ear tag", lambda gg: done.__setitem__("d", True))
        yield lambda: done["d"]
        g.complete("wash")
        g.cutscene_start(letterbox=True)
        g.audio.play("splash", vol=0.8)
        mz.model.set_tag("tag_12")
        self.setf("moozart_tag_clean")
        hd = mz.model.head
        tag = hd.world_position + hd.right * 0.44 + hd.forward * 0.24 + hd.up * 0.06
        g.cam_set(tag + hd.right * 1.0 + hd.forward * 0.35 + hd.up * 0.15, tag)
        yield 2.0
        yield from g.talk([
            ("moozart", "What does it say?"),
            ("you", "Moo. (Twelve.)"),
            ("moozart", "I know."),
            ("moozart", "Chuck said it when he put the tag in. 'Twelve. Lucky number.' I was a calf. I remembered."),
            ("you", "Moo. (Why didn't you tell anyone?)"),
            ("moozart", "Because then you'd all look at me the way you're looking at me now, and I'd never finish the "
                        "symphony."),
            ("cowleen", "Then we hide him. Tomorrow, before the truck comes. The hayloft's full of hay, and Chuck "
                        "hates the ramp. He says it's too steep for a man his age."),
            ("moozart", "I'd like to finish it first. Wherever I end up."),
        ])
        g.cutscene_end_now()
        g.set_time("dusk", 10)
        g.ambience("night")
        self.base_music = "music_night"

    # ==================================================================
    # THURSDAY
    # ==================================================================
    def setup_day4(self):
        g = self.g
        self.morning(preset="rain", amb="rain")
        self.wake_in_stall()
        f = g.farmer
        f.range_day = 17.0
        if not self.done("d4_truck"):
            mz = g.cows["moozart"]
            if self.done("d4_escort"):
                mz.teleport((16.2, L, 11.4), 250)
            else:
                mz.teleport((-44.5, 0, -6.0), 180)
        self.chuck_routine([
            ("go", (0, 0, -30), 1.9), ("wait", 6, "look", RAIN_LINES),
            ("go", (22, 0, -14), 1.9), ("wait", 6, "look", RAIN_LINES),
            ("go", (40, 0, -12), 1.9), ("wait", 5, "look"),
            ("go", (32, 0, -35), 1.9), ("wait", 5, "look", RAIN_LINES),
            ("go", (8, 0, -40), 1.9), ("wait", 5, "look"),
        ])
        f.teleport((22, 0, -14), 0)
        self.dhook("update", self.base_update)
        self.dhook("use", self.radio_use)

    def day4(self):
        yield from self.step("d4_wake", self.d4_wake)
        yield from self.step("d4_escort", self.d4_escort,
                             hint="Out through the gap in the fence, then along the east side of the pasture fence, "
                                  "and in through the barn's side door. Up the ramp. If Moozart starts humming, moo "
                                  "at him (M).")
        yield from self.step("d4_loft", self.d4_loft, hint="Moo when he stops (M).")
        yield from self.step("d4_back", self.d4_back, hint="Back to the pasture, through the gap in the fence.")
        yield from self.step("d4_truck", self.d4_truck)
        yield from self.step("d4_vigil", self.d4_vigil, hint="Look at the hoofprints by the pond.")
        yield from self._run_day(5)

    def d4_wake(self):
        g = self.g
        c = g.cows["cowleen"]
        mz = g.cows["moozart"]
        c.teleport((-45.6, 0, -4.2), 20)
        g.cutscene_start(letterbox=True)
        g.player.look_at_point((c.x, 1.3, c.z))
        yield from g.fade_in(1.2)
        yield from g.talk([
            ("cowleen", "The truck comes at dusk. We get Moozart up into the hayloft before then."),
            ("cowleen", "He'll follow you. He's slow, and he hums when he's scared. If he starts, moo at him and "
                        "he'll stop."),
            ("moozart", "I don't hum."),
            ("cowleen", "You're humming right now."),
            ("moozart", "That's the rain."),
        ])
        g.cutscene_end_now()

    def d4_escort(self):
        g = self.g
        mz = g.cows["moozart"]
        p = g.player
        self.objectives(("escort", "Lead Moozart to the hayloft"))
        self.mark((MOOHOLE_POS[0], MOOHOLE_POS[1], "Gap"), (10, 0.7, "Side door"), (17, 11, "Hayloft"))
        mz.follow(lambda: p.pos, 2.6, 2.7)
        mz.look = "player"
        st = {"t": random.uniform(12, 18), "warn": 0.0, "far_t": 0.0}

        def moo():
            if math.hypot(p.x - mz.x, p.z - mz.z) < 10:
                if st["warn"] > 0:
                    st["warn"] = 0.0
                    st["t"] = random.uniform(14, 22)
                    mz.bubble("...")
                    g.ui.popup_sub("Moozart stops humming. \"Sorry. Nerves.\"", 3)
                else:
                    mz.bubble("?")
                return True
            return False
        self.hook("moo", moo)

        def upd(dt):
            self.base_update(dt)
            outside = not g.phys.in_zone("pasture", mz.x, mz.z)
            if outside and not g.cutscene:
                if st["warn"] > 0:
                    st["warn"] -= dt
                    if st["warn"] <= 0:
                        mz.bubble("Hmm-hmm-hmmm", 2.5)
                        g.audio.play("moo_moozart_long_0", vol=0.8, pos=(mz.x, 1.4, mz.z), rng=30, group="voice")
                        g.noise((mz.x, 0, mz.z), 15, "hum")
                        st["t"] = random.uniform(10, 16)
                else:
                    st["t"] -= dt
                    if st["t"] <= 0:
                        st["warn"] = 3.5
                        mz.bubble("hm... hm...", 3.0)
                        g.ui.popup_sub("Moozart's starting to hum. Moo at him! (M)", 3)
            # if he falls far behind (stuck on something), bring him along quietly
            d = math.hypot(p.x - mz.x, p.z - mz.z)
            st["far_t"] = st["far_t"] + dt if d > 22 else 0.0
            if st["far_t"] > 4.0:
                st["far_t"] = 0.0
                f = p.forward()
                bx, bz = p.x - f[0] * 3.5, p.z - f[2] * 3.5
                bx, bz = g.phys.resolve(bx, bz, 0.9, p.y, 1.5)
                mz.teleport((bx, p.y, bz), p.yaw)
                mz.follow(lambda: p.pos, 2.6, 2.7)
        self.hook("update", upd)

        def caught_back():
            self.return_to_pasture()
            mz.teleport((p.x - 2.0, 0, p.z + 1.5), 90)
            mz.follow(lambda: p.pos, 2.6, 2.7)
            return True
        self.hook("after_caught", caught_back)
        self.hook("caught_line", lambda: random.choice(["Two of you? What is this, a union?",
                                                        "Twelve AND forty-seven? In the rain? Back you go."]))
        yield lambda: p.y > L - 0.3 and 12 < p.x < 22 and 7 < p.z < 13.8 and mz.y > L - 0.4 and \
            math.hypot(p.x - mz.x, p.z - mz.z) < 5
        g.complete("escort")
        mz.trail_fn = None
        mz.path = []

    def d4_loft(self):
        g = self.g
        mz = g.cows["moozart"]
        p = g.player
        g.cutscene_start(letterbox=True)
        mz.teleport((16.2, L, 11.4), 250)
        p.teleport(13.0, L, 9.2, 60)
        g.cam_set((12.2, L + 1.5, 8.4), (16.2, L + 1.2, 11.4))
        self.lock_hud_music(None, 0, 1.0)
        yield from g.talk([
            ("moozart", "It's nice up here. Listen to the rain on the roof. It's in three-four time."),
            ("moozart", "I'll play you what I've got. Fifteen bars. That's as far as I get."),
        ])
        self.moo_music("moozart_15", mz)
        yield 2.0
        yield from g.cam_move((14.0, L + 1.2, 13.4), (16.2, L + 1.1, 11.4), dur=33.0)
        self.unduck()
        yield from g.talk([
            ("moozart", "That's where I get stuck. The last note has to come from somewhere else."),
            ("moozart", "I've tried every moo I have, and they're all mine. It needs to be somebody else's."),
            ("moozart", "Would you? Just the one. Moo for me."),
        ])
        g.cutscene_end_now()
        p.frozen = True
        self.objectives(("moo", "Moo for Moozart (M)"))
        mooed = {"d": False}

        def moo():
            mooed["d"] = True
            return True
        self.hook("moo", moo)
        yield lambda: mooed["d"]
        g.complete("moo")
        g.audio.play("final_note", vol=1.0, group="voice")
        g.cutscene_start(letterbox=True)
        g.cam_set((12.2, L + 1.5, 8.4), (16.2, L + 1.2, 11.4))
        yield 4.5
        g.ui.toast("Symphony No. 1 in Moo Major: complete", "score")
        yield from g.talk([
            ("moozart", "..."),
            ("moozart", "That's it. That's the one."),
            ("moozart", "Give me that page from Chuck's planner. The back's blank."),
        ])
        if g.inv.has("page"):
            g.inv.remove("page")
        g.audio.play("paper", vol=0.7)
        yield 1.2
        g.inv.add("score")
        yield from g.talk([
            ("moozart", "There. Symphony Number One in Moo Major. For Forty-Seven."),
            ("moozart", "Now go back before Chuck notices you're gone. I'll stay up here and be quiet. I'm good at "
                        "quiet when it matters."),
        ])
        p.frozen = False
        g.cutscene_end_now()
        self.unlock_music()
        self.lock_hud_music("music_night", 0.5, 2.0)

    def d4_back(self):
        g = self.g
        p = g.player
        self.objectives(("back", "Get back to the pasture before the headcount"))
        self.mark((MOOHOLE_POS[0], MOOHOLE_POS[1], "Gap"))
        self.unlock_music()
        yield lambda: g.phys.in_zone("pasture", p.x, p.z) and not g.runner.running("caught")
        g.complete("back")

    def d4_truck(self):
        g = self.g
        f = g.farmer
        p = g.player
        mz = g.cows["moozart"]
        w = g.world
        g.cutscene_start(letterbox=True)
        self.lock_hud_music(None, 0, 2.0)
        yield from g.fade_out(0.8)
        g.set_time("dusk")
        g.ambience("rain")
        p.teleport(-30, 0, -34, 90)
        for k, c in g.cows.items():
            if k != "moozart":
                c.trail_fn = None
        g.cows["cowleen"].teleport((-31.5, 0, -31.8), 120)
        truck = self.prop("truck", models.cattle_truck_model(position=(0, 0, 70), rotation_y=180))
        f.set_routine([])
        f.scripted()
        f.set_visible(False)
        g.cam_set((-24, 2.0, -38.5), (-12, 1.5, -35))
        yield from g.fade_in(1.0)
        g.audio.loop("truck", "loop_truck", vol=1.0, pos=(0, 1, 70), rng=120, group="sfx")
        # the truck comes down the drive and round to the pasture gate
        # down the drive, then reverse up to the pasture gate so the loading door faces it
        path = [(0, 0, 70), (0, 0, -12), (-1.5, 0, -27), (-11.5, 0, -35)]
        yaws = [180, 180, 185, 90]
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            d = math.dist(a, b)
            T = d / 9.0
            t = 0.0
            while t < T:
                t += min(0.05, time.dt)
                k = min(1.0, t / T)
                truck.position = (a[0] + (b[0] - a[0]) * k, 0, a[2] + (b[2] - a[2]) * k)
                truck.rotation_y = yaws[i] + ang_diff(yaws[i + 1], yaws[i]) * k
                g.audio.set_loop("truck", pos=(truck.x, 1, truck.z))
                if i == 0 and k > 0.6:
                    g.cam_set((-24, 2.0, -38.5), (truck.x, 1.5, truck.z))
                yield None
        truck.rotation_y = 90
        g.audio.stop_loop("truck", 1.5)
        yield 1.0
        f.set_visible(True)
        f.set_outfit("day")
        f.teleport((-13.5, 0, -38.5), 270)
        f.set_tool("rope")
        g.world.doors["pasture_gate"].set_open(True)
        g.audio.play("door_creak", vol=0.8, pos=(-18, 1, -35), rng=40)
        yield from self.walk_npc(f, (-21.5, 0, -35.0), 2.2, 6)
        g.cam_set((-33, 2.2, -36.5), (-22, 1.4, -34))
        yield from g.talk([
            ("chuck", "Twelve! C'mere, twelve! Truck's here!"),
            ("chuck", "Twelve? ...Where the heck is twelve?"),
        ])
        yield from self.walk_npc(f, (-25.0, 0, -31.0), 2.0, 5)
        f.face_target = (p.x, p.z)
        yield 0.8
        yield from g.talk([
            ("chuck", "Aw, heck. The truck's paid for."),
            ("chuck", "Forty-seven. Guess you're goin' early."),
        ])
        f.goto((p.x + 1.6, 0, p.z), 1.4)
        yield 1.5
        # Moozart walks out of the barn, singing
        mz.teleport((8.5, 0, 0.7), 225)
        mz.set_visible(True)
        g.world.doors["barn_side"].set_open(True)
        g.audio.play("moozart_walk", vol=1.0, group="voice")
        g.cam_set((1.5, 2.2, -8.0), (8.5, 1.4, 0.2))
        mz.goto((-2.0, 0, -22.0), 1.6)
        mz.bubble("Mooo-oo", 3)
        yield 4.5
        f.path = []
        f.face_target = (-10, -30)
        g.cam_set((-27.5, 1.9, -33.0), (-22, 1.5, -31))
        f.pose = "idle"
        yield 1.5
        yield from g.talk([("chuck", "Well. There you are, twelve.")])
        mz.teleport((-15.5, 0, -31.5), 250)
        mz.path = []
        yield from self.walk_npc(mz, (-19.5, 0, -34.2), 1.4, 6)
        mz.yaw = 270
        mz.look = "player"
        f.teleport((-20.5, 0, -36.8), 0)
        f.face_target = (mz.x, mz.z)
        g.cam_set((-25.5, 1.8, -35.0), (-19.5, 1.5, -34.2))
        yield 1.0
        yield from g.talk([
            ("moozart", "Sixteen bars, Forty-Seven. All of them."),
            ("moozart", "Tell Cowpernicus to redo his numbers. One fewer."),
        ])
        g.cam_set((-26, 2.5, -42), (-12, 1.4, -35))
        mz.goto((-15.2, 0, -35.0), 1.2)
        f.goto((-16.0, 0, -37.2), 1.2)
        yield 5.5
        mz.set_visible(False)
        mz.path = []
        truck.door.animate_rotation((-80, 0, 0), duration=0.8)
        g.audio.play("door_close", vol=1.0, pos=(-13, 1, -35), rng=60)
        yield 1.2
        f.set_visible(False)
        g.world.doors["pasture_gate"].set_open(False)
        g.audio.loop("truck", "loop_truck", vol=1.0, pos=(truck.x, 1, truck.z), rng=120, group="sfx")
        # round the south side of the chicken run to the processing door
        path = [(-11.5, 0, -35), (18, 0, -40), (30, 0, -46.5), (47, 0, -46.5), (52.5, 0, -41)]
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            T = math.dist(a, b) / 6.0
            t = 0.0
            yaw = math.degrees(math.atan2(b[0] - a[0], b[2] - a[2]))
            while t < T:
                t += min(0.05, time.dt)
                k = min(1.0, t / T)
                truck.position = (a[0] + (b[0] - a[0]) * k, 0, a[2] + (b[2] - a[2]) * k)
                truck.rotation_y += ang_diff(yaw, truck.rotation_y) * min(1, 0.1)
                g.audio.set_loop("truck", pos=(truck.x, 1, truck.z))
                yield None
        g.audio.stop_loop("truck", 2.0)
        yield 1.0
        # smoke from the chimney
        g.cam_set((20, 6, -20), (70, 11, -44))
        smoke = Smoke((73, 13.2, -46))
        self.fx.append(smoke)
        self.lock_hud_music("music_sad", 0.6, 3.0)
        yield 7.0
        yield from g.fade_out(2.0)
        self.remove_prop("truck")
        self.setf("moozart_gone")
        g.cutscene_end_now()

    def d4_vigil(self):
        g = self.g
        p = g.player
        g.set_time("night")
        g.ambience("night")
        g.world.set_lamp("cowshed", True)
        self.lock_hud_music("music_sad", 0.45, 2.0)
        self.gather_at(POND_VIGIL)
        p.teleport(-41.0, 0, -49.0, 180)
        # Moozart's symphony, pressed into the mud in hoofprints
        mb = MeshBuilder()
        rnd = random.Random(12)
        for bar in range(16):
            for k in range(3):
                x = -48.6 + bar * 0.62 + k * 0.18
                z = -52.9 + rnd.uniform(-0.25, 0.25)
                for sx in (-0.03, 0.03):
                    mb.disk((x + sx, 0.035, z), 0.035, 0.05, color=(0.22, 0.16, 0.1, 1), segs=8, uv_rect=models.WHITE)
        mb.disk((-48.6 + 16 * 0.62 + 0.1, 0.036, -52.9), 0.08, 0.11, color=(0.15, 0.1, 0.06, 1), segs=10,
                uv_rect=models.WHITE)
        self.prop("hoofprints", Entity(model=mb.build(), texture=tex("atlas"), shader=FARM_SHADER))
        yield from g.fade_in(2.0)
        self.objectives(("prints", "Look at the hoofprints by the pond"))
        self.mark((-44, -53, "Hoofprints"))
        ia = g.ia.add(Interactable("st_prints", (-43.5, 0.2, -52.9), 1.2, "Hoofprints", None, "Look at the hoofprints",
                                   4.0))
        seen = {"d": False}

        def look(gg):
            yield from gg.show_document("Hoofprints in the mud", HOOFPRINTS)
            seen["d"] = True
        ia.handlers.append(Handler("Look at the hoofprints", look, None, "global"))
        yield lambda: seen["d"]
        g.complete("prints")
        g.cutscene_start(letterbox=True)
        g.cam_set((-41.0, 1.9, -46.5), (-42.5, 1.1, -53.0))
        yield from g.talk([
            ("cowleen", "He heard it finished. That's something."),
            ("sirloin", "He was braver than me. I'm the knight, and he was braver than me."),
            ("moomaw", "Earl would have liked him. Earl liked anybody who sang."),
            ("cowpernicus", "I did the numbers for Sunday. It works. It's tight, but it works."),
            ("mooriarty", "Whatever you need from me. No charge."),
            ("cowleen", "We get everyone out. All forty-eight of us."),
        ])
        g.cutscene_end_now()
        yield from g.fade_out(2.0)
        self.unlock_music()

    # ==================================================================
    # FRIDAY
    # ==================================================================
    def setup_day5(self):
        g = self.g
        self.morning()
        self.wake_in_stall()
        f = g.farmer
        f.set_routine([])
        f.set_visible(False)
        if not self.done("d5_return"):
            self._house_items()
        self.dhook("update", self.base_update)
        self.dhook("use", self.radio_use)
        self.dhook("caught_line", lambda: "What in the... a COW? In my HOUSE?")

    def _house_items(self):
        g = self.g
        if not self.done("sparkplug_taken"):
            self.prop("vinegar", self._glass((60.35, Y + 0.79, 34.25)))

            def plug(gg):
                self.remove_item("sparkplug")
                self.remove_prop("vinegar")
                gg.inv.add("sparkplug")
                self.setf("sparkplug_taken")
                gg.complete("plug")
            self.item("sparkplug", "sparkplug", (60.35, Y + 0.93, 34.25), "Spark plug (in vinegar)",
                      "Fish the spark plug out of the vinegar", plug, radius=0.25, reach=2.4)
        if not self.done("photo_taken"):
            ph = MeshBuilder().quad((0, 0, 0), (0.34, 0.27), uv_rect=(0, 0, 1, 1))
            frame = Entity(model=ph.build(), texture=tex("photo_earl"), shader=FARM_SHADER,
                           position=(46.75, Y + 0.97, 46.75), rotation=(-12, 200, 0))
            fr = MeshBuilder().box((0, 0, 0.012), (0.38, 0.31, 0.02), color=(0.35, 0.22, 0.12, 1), uv_rect=models.WHITE)
            Entity(parent=frame, model=fr.build(solid_rect=models.WHITE), texture=tex("atlas"), shader=FARM_SHADER)
            self.prop("photo", frame)
            ia = g.ia.add(Interactable("st_photo", (46.75, Y + 0.97, 46.75), 0.25, "Framed photo", None,
                                       "Look at the photo", 2.4))

            def take(gg):
                self.remove_prop("photo")
                gg.ia.remove("st_photo")
                gg.inv.add("photo")
                self.setf("photo_taken")
            ia.handlers.append(Handler("Look at the photo", lambda gg: gg.examine(
                "A framed photo: 'Me & Big Earl, Best in Show 2009.' Chuck has his arm round a huge, unimpressed bull. "
                "The computer password hint says 'my best friend'."), None, "global"))
            ia.handlers.append(Handler("Take the photo (for Moomaw)", take, lambda gg: "photo" in gg.side_quests,
                                       "global"))
        if not self.done("shoes_taken") and not self.done("d5_return"):
            def shoes(gg):
                self.remove_item("shoes")
                gg.inv.add("shoes")
                self.setf("shoes_taken")
            self.item("shoes", "shoes", (45.8, Y + 0.05, 37.4), "Bowling shoes", "Take the bowling shoes", shoes,
                      rot=30, radius=0.3)

    def _glass(self, pos):
        mb = MeshBuilder()
        mb.cylinder((0, 0, 0), 0.055, 0.16, color=(0.85, 0.92, 0.95, 1), segs=10)
        mb.cylinder((0, 0.005, 0), 0.05, 0.12, color=(0.9, 0.85, 0.6, 1), segs=10)
        return Entity(model=mb.build(), texture=tex("white"), shader=FARM_SHADER, position=pos)

    def day5(self):
        yield from self.step("d5_leave", self.d5_leave)
        yield from self.step("d5_key", self.d5_key,
                             hint="Chuck's spare key is hidden by the front door. Lift the doormat and follow the "
                                  "notes: it ends up inside the garden gnome by the corner of the house. Headbutt him.")
        yield from self.step("d5_inside", self.d5_inside,
                             hint="The spark plug's in a glass on the kitchen table. The computer's in the office; the "
                                  "password hint says 'my best friend', and there's a photo on the desk.")
        yield from self.step("d5_return", self.d5_return,
                             hint="Hide in the bedroom wardrobe until he's gone, or slip out of the back door in the "
                                  "kitchen. If you took his shoes, throw them (R) and he'll go after them.")
        yield from self.step("d5_meeting", self.d5_meeting, hint="The crew's at the Old Oak.")
        yield from self.step("d5_sleep", self.sleep_step, hint="Bed. Stall 47.")
        yield from self._run_day(6)

    def d5_leave(self):
        g = self.g
        f = g.farmer
        w = g.world
        g.cutscene_start(letterbox=True)
        g.set_time("morning")
        f.set_visible(True)
        f.scripted()
        f.set_tool("bowling_ball")
        f.teleport((56, Y, 29), 180)
        g.cam_set((62, 2.4, 16), (60, 1.2, 30))
        yield from g.fade_in(1.0)
        yield from g.talk([("chuck", "Big night tonight, girls! Bowlin' with the boys! Don't wait up!")])
        yield from self.walk_npc(f, (71.0, 0, 33.0), 2.6, 7)
        f.set_visible(False)
        pk = w.pickup
        w.colliders["pickup"].enabled = False
        g.audio.play("tractor_start", vol=0.6, pitch=1.4, pos=(74, 1, 36), rng=60)
        g.audio.loop("pickup", "loop_truck", vol=0.8, pos=(74, 1, 36), rng=80, group="sfx", pitch=1.3)
        path = [(74, 0, 36), (74, 0, 24), (60, 0, 23), (4, 0, 23), (0, 0, 30), (0, 0, 84), (0, 0, 120)]
        w.doors["main_left"].set_open(True)
        w.doors["main_right"].set_open(True)
        w.chain.enabled = False
        for i in range(len(path) - 1):
            a, b = path[i], path[i + 1]
            T = math.dist(a, b) / 11.0
            t = 0.0
            yaw = math.degrees(math.atan2(b[0] - a[0], b[2] - a[2]))
            while t < T:
                t += min(0.05, time.dt)
                k = min(1.0, t / T)
                pk.position = (a[0] + (b[0] - a[0]) * k, 0, a[2] + (b[2] - a[2]) * k)
                pk.rotation_y += ang_diff(yaw, pk.rotation_y) * 0.15
                g.audio.set_loop("pickup", pos=(pk.x, 1, pk.z))
                if i >= 3:
                    g.cam_set((10, 3, 62), (pk.x, 1, pk.z))
                yield None
        g.audio.stop_loop("pickup", 1.0)
        pk.enabled = False
        w.doors["main_left"].set_open(False)
        w.doors["main_right"].set_open(False)
        w.chain.enabled = True
        yield from g.fade_out(0.8)
        self.wake_in_stall()
        c = g.cows["cowleen"]
        c.teleport((-45.6, 0, -4.2), 20)
        g.player.look_at_point((c.x, 1.3, c.z))
        yield from g.fade_in(0.8)
        yield from g.talk([
            ("cowleen", "He's gone till late. The house is empty."),
            ("cowleen", "Spark plug's in the kitchen. And Cowpernicus wants to know what's on Chuck's computer."),
            ("cowleen", "Go out through the gap. Be back before dark."),
        ])
        g.cutscene_end_now()

    def d5_key(self):
        g = self.g
        # the objective spells out each clue as it's found, so there's always a next thing to try
        clue = {0: "   Find Chuck's spare key (try the doormat)",
                1: "   The note says: under the flowerpot",
                2: "   It's inside the garden gnome: headbutt him to break him open"}

        def show():
            self.objectives(("in", "Get into the farmhouse"),
                            ("in_key", clue[min(2, self.flags.get("d5_keystate", 0))]))
        self.flags.setdefault("d5_keystate", 0)
        show()
        self.mark((56, 29, "Doormat"))

        def found(stage, mark):
            if self.flags.get("d5_keystate", 0) < stage:
                self.flags["d5_keystate"] = stage
                show()
                self.mark(mark)

        def mat(gg):
            yield from gg.show_document("Under the doormat", "A sticky note, a bit damp:\n\n"
                                                             "    Spare key is under the FLOWERPOT.")
            found(1, (60.6, 28.6, "Flowerpot"))

        def pot(gg):
            gg.audio.play("rock_land", vol=0.6, pitch=0.7)
            yield from gg.show_document("Under the flowerpot", "Another sticky note:\n\n"
                                                               "    Moved it. Spare key is in the GNOME.\n"
                                                               "    (Break him open. I'll buy another.)\n"
                                                               "                              - Chuck")
            found(2, (41, 24, "Gnome"))
            gg.ui.popup_sub("The gnome's in the flowerbed by the corner of the house. Walk up to him and headbutt "
                            "him (left click or E).", 8)
        g.on("doormat", "Lift the doormat", mat)
        g.on("flowerpot", "Tip the flowerpot", pot)

        if self.done("gnome_broken") and not g.inv.has("house_key") and not self.done("house_unlocked"):
            # broken in an earlier try (the old version dropped the key in the flowerbed): hand it over
            g.inv.add("house_key", silent=True)

        def bonk(gg):
            # works whether or not you've read the notes: the key is in the gnome either way
            if self.done("gnome_broken") or gg.inv.has("house_key"):
                return
            self.setf("gnome_broken")
            gg.world.gnome.animate_rotation((80, 200, 0), duration=0.3)
            gg.audio.play("crash", vol=0.8, pos=(41, 0.4, 24), rng=30)
            gg.inv.add("house_key")
            gg.ui.popup_sub("The gnome topples over and cracks open. The spare key falls out. You pick it up in "
                            "your teeth.", 5)
        def smash(gg):
            # E does the same as a left click here: the prompt tells you what's going to happen
            p = gg.player
            p.lunge = 1.0
            p.shake = 0.3
            gg.audio.play("headbutt", vol=0.9)
            bonk(gg)
        g.on("gnome", "Headbutt the gnome", smash, cond=lambda gg: not self.done("gnome_broken"))
        g.ia.get("gnome").on_headbutt = bonk

        gn = g.world.gnome
        wob = {"next": 0.5, "t": 0.0}

        def upd(dt):
            self.base_update(dt)
            if self.done("gnome_broken") or self.flags.get("d5_keystate", 0) < 2:
                return
            # once the note points at him, the gnome rattles every few seconds: a shake and a jingle of keys
            wob["next"] -= dt
            if wob["next"] <= 0:
                wob["next"] = 2.5
                wob["t"] = 0.5
                g.audio.play("cowbell_1", vol=0.4, pitch=2.4, pos=(41, 0.8, 24), rng=20)
            if wob["t"] > 0:
                wob["t"] = max(0.0, wob["t"] - dt)
                gn.rotation_z = math.sin(wob["t"] * 45) * 9 * (wob["t"] / 0.5)
            else:
                gn.rotation_z = 0
        self.hook("update", upd)
        yield lambda: g.inv.has("house_key") or self.done("house_unlocked")
        g.ia.get("gnome").on_headbutt = None
        self.objectives(("in", "Get into the farmhouse"), ("in_key", "   Found the spare key"))
        g.complete("in_key", sound=False)
        self.mark((56, 29, "Front door"))
        p = g.player
        yield lambda: g.phys.in_zone("house", p.x, p.z)
        g.complete("in")

    def d5_inside(self):
        g = self.g
        self.objectives(("plug", "Get the spark plug (kitchen)"), ("pc", "Look at Chuck's computer (office)"))
        if self.done("sparkplug_taken"):
            g.complete("plug", sound=False)
        self.mark((60.4, 34.3, "Spark plug"), (47.5, 46.8, "Computer"))
        used = {"d": self.done("emails_read")}
        if used["d"]:
            g.complete("pc", sound=False)

        def computer(gg):
            ok = yield from self.password({"BIGEARL", "EARL"}, "Hint: 'my best friend (NOT Dale)'. There's a photo "
                                                                "on the desk.")
            if not ok:
                return
            yield from gg.show_document("ChuckOS Mail: Inbox (3)", EMAILS, paper=False)
            yield from gg.show_document("COWS.XLS", SPREADSHEET, paper=False)
            r = yield from gg.say("you", "Moo. (All of them. He's selling every last one of them to Dale.)",
                                  choices=["Reply to Dale: cancel the barbecue", "Leave it alone"])
            gg.end_talk()
            if r == 0:
                self.setf("dale_cancelled")
                yield from gg.show_document("ChuckOS Mail: Reply", DALE_REPLY, paper=False)
            self.setf("emails_read")
            used["d"] = True
            gg.complete("pc")
        g.on("computer", "Use the computer", computer, cond=lambda gg: not used["d"])
        yield lambda: self.done("sparkplug_taken") and used["d"] and not g.busy

    def d5_return(self):
        g = self.g
        f = g.farmer
        w = g.world
        p = g.player
        g.ui.popup_sub("Tyres on the gravel. Chuck's pickup is coming back up the drive.", 5)
        g.audio.loop("pickup", "loop_truck", vol=0.8, pos=(0, 1, 90), rng=90, group="sfx", pitch=1.3)
        self.objectives(("escape", "Get out of the house without being seen"))
        self.mark((53.4, 46.4, "Wardrobe"), (68, 41, "Back door"))
        pk = w.pickup
        pk.enabled = True
        pk.position = (0, 0, 110)
        path = [(0, 0, 110), (0, 0, 30), (4, 0, 23), (60, 0, 23), (74, 0, 24), (74, 0, 36)]
        mv = {"i": 0, "t": 0.0}
        state = {"phase": "drive", "t": 0.0, "found": False, "shoes_pos": None}
        search = [(50, Y, 35.5, "Shoes... shoes... where'd I put my shoes..."),
                  (62, Y, 35, "Not in the kitchen. Why would they be in the kitchen."),
                  (56.4, Y, 43.9, "Bedroom. They're always in the bedroom. ...They're not in the bedroom."),
                  (48, Y, 44.8, "Office? Who keeps shoes in an office."),
                  (46.4, Y, 37.0, None)]
        w.doors["main_left"].set_open(True)
        w.doors["main_right"].set_open(True)
        w.chain.enabled = False
        self.hook("caught_line", lambda: "What in the... a COW? In my HOUSE? In my HALLWAY?")

        def after():
            self.return_to_pasture()
            state["phase"] = "gone"
            f.set_visible(False)
            g.audio.stop_loop("pickup", 0.5)
            pk.enabled = True
            pk.position = (74, 0, 36)
            g.ui.popup_sub("Chuck marched you back to the pasture, found his shoes, and drove off to bowling, late "
                           "and muttering.", 7)
            return True
        self.hook("after_caught", after)

        def land(proj, pos):
            if proj.kind == "shoes":
                state["shoes_pos"] = (pos[0], pos[1], pos[2])
                self.prop("shoes_thrown", models.item_model("shoes", position=pos, rotation_y=random.uniform(0, 360)))
                if state["phase"] == "search":
                    f.say("Huh? What was... hey! My SHOES!", force=True)
                    f.set_routine([("go", (pos[0], Y, pos[2]), 2.6), ("stop", "look")])
                    state["phase"] = "fetch"
        self.hook("land", land)

        def upd(dt):
            self.base_update(dt)
            ph = state["phase"]
            if ph == "drive":
                a, b = path[mv["i"]], path[mv["i"] + 1]
                T = math.dist(a, b) / 11.0
                mv["t"] += dt
                k = min(1.0, mv["t"] / T)
                pk.position = (a[0] + (b[0] - a[0]) * k, 0, a[2] + (b[2] - a[2]) * k)
                yaw = math.degrees(math.atan2(b[0] - a[0], b[2] - a[2]))
                pk.rotation_y += ang_diff(yaw, pk.rotation_y) * min(1, dt * 6)
                g.audio.set_loop("pickup", pos=(pk.x, 1, pk.z))
                if k >= 1.0:
                    mv["i"] += 1
                    mv["t"] = 0.0
                    if mv["i"] >= len(path) - 1:
                        state["phase"] = "walk_in"
                        g.audio.stop_loop("pickup", 0.5)
                        pk.rotation_y = 180
                        w.doors["main_left"].set_open(False)
                        w.doors["main_right"].set_open(False)
                        w.chain.enabled = True
                        f.set_visible(True)
                        f.set_outfit("day")
                        f.set_tool(None)
                        f.teleport((71.5, 0, 33.5), 250)
                        f.set_routine([("say", "Forgot my dang SHOES."), ("go", (56, 0, 25.5), 2.4),
                                       ("call", lambda: (w.doors["front_door"].set_open(True),
                                                         g.audio.play("door_creak", vol=0.8, pos=(56, 1, 30), rng=40))),
                                       ("go", (56, Y, 32.0), 2.2), ("stop", "idle")])
            elif ph == "walk_in":
                if f.r_i >= 4 and not f.path:
                    state["phase"] = "search"
                    self._chuck_search(search, state)
            elif ph == "search":
                if f.state == "routine" and f.routine and f.r_i == len(f.routine) - 1 and not f.path:
                    if not g.inv.has("shoes"):
                        self._chuck_found_shoes(state)
                    else:
                        self._chuck_search(search, state)
            elif ph == "fetch":
                if not f.path and f.state == "routine":
                    self.remove_prop("shoes_thrown")
                    self._chuck_found_shoes(state)
            elif ph == "leaving":
                if f.r_i >= 3 and not f.path and f.visible is False:
                    state["phase"] = "drive_off"
                    mv["i"] = 0
                    mv["t"] = 0.0
                    g.audio.loop("pickup", "loop_truck", vol=0.8, pos=(74, 1, 36), rng=90, group="sfx", pitch=1.3)
                    w.doors["main_left"].set_open(True)
                    w.doors["main_right"].set_open(True)
                    w.chain.enabled = False
            elif ph == "drive_off":
                back = [(74, 0, 36), (74, 0, 24), (60, 0, 23), (4, 0, 23), (0, 0, 30), (0, 0, 120)]
                a, b = back[mv["i"]], back[mv["i"] + 1]
                T = math.dist(a, b) / 11.0
                mv["t"] += dt
                k = min(1.0, mv["t"] / T)
                pk.position = (a[0] + (b[0] - a[0]) * k, 0, a[2] + (b[2] - a[2]) * k)
                yaw = math.degrees(math.atan2(b[0] - a[0], b[2] - a[2]))
                pk.rotation_y += ang_diff(yaw, pk.rotation_y) * min(1, dt * 6)
                g.audio.set_loop("pickup", pos=(pk.x, 1, pk.z))
                if k >= 1.0:
                    mv["i"] += 1
                    mv["t"] = 0.0
                    if mv["i"] >= len(back) - 1:
                        state["phase"] = "gone"
                        g.audio.stop_loop("pickup", 1.0)
                        pk.enabled = False
                        w.doors["main_left"].set_open(False)
                        w.doors["main_right"].set_open(False)
                        w.chain.enabled = True
        self.hook("update", upd)
        # done once you're out of the house and he's either gone or still inside hunting
        yield lambda: (not g.phys.in_zone("house", p.x, p.z) and not g.phys.in_zone("porch", p.x, p.z)
                       and not g.flags.get("_hiding") and state["phase"] in ("search", "fetch", "leaving",
                                                                            "drive_off", "gone")
                       and not g.runner.running("caught"))
        g.complete("escape")
        # he finishes leaving in the background
        self.day_hooks["update"] = upd

    def _chuck_search(self, spots, state):
        f = self.g.farmer
        steps = []
        for x, y, z, line in spots:
            steps.append(("go", (x, y, z), 1.8))
            steps.append(("wait", 3.5, "look", [line] if line else None))
        steps.append(("say", "Where did I PUT them?"))
        steps.append(("stop", "look"))
        f.set_routine(steps)
        f.walk_run = False

    def _chuck_found_shoes(self, state):
        g = self.g
        f = g.farmer
        if state.get("found"):
            return True
        state["found"] = True
        self.remove_item("shoes")
        f.say("THERE they are! Okay. Bowlin'. Bowlin' bowlin' bowlin'.", force=True)
        f.set_tool(None)
        w = g.world
        f.set_routine([("go", (56, Y, 32), 2.6), ("go", (56, 0, 25.5), 2.6),
                       ("call", lambda: w.doors["front_door"].set_open(False)),
                       ("go", (71.5, 0, 33.5), 2.6), ("hide",), ("stop", "idle")])
        state["phase"] = "leaving"
        return True

    def d5_meeting(self):
        g = self.g
        g.set_time("sunset", 12)
        yield 0.5
        self.walk_friends_to(OAK_MEET)
        self.objectives(("meet", "Crew meeting at the Old Oak"))
        self.mark((-50, -35, "Meeting"))
        p = g.player
        yield lambda: math.hypot(p.x + 50, p.z + 35) < 7.5 and not g.busy
        g.complete("meet")
        g.cutscene_start(letterbox=True)
        self.gather_at(OAK_MEET)
        p.teleport(-50.5, 0, -41.5, 0)
        g.cam_set((-56.5, 3.2, -43.0), (-50, 1.2, -34.5))
        lines = []
        if self.done("emails_read"):
            lines.append(("you", "Moo. (Chuck's selling the rest of the herd to Dale. All of you. Next month.)"))
            lines.append(("moomaw", "Well. That settles it, then."))
        lines += [
            ("cowpernicus", "Okay. The plan, final version. I've drawn it again. Sir Loin, please."),
            ("sirloin", "I've moved."),
            ("cowpernicus", "Sunday, dawn. Cluck crows. Forty-Seven pulls the main fuse in the shed and the fence dies."),
            ("cowpernicus", "Forty-Seven starts the tractor and drives it through the main gate. Everybody runs for "
                            "the road."),
            ("cowpernicus", "Tomorrow we get ready. The spark plug goes in the tractor. Somebody lays planks over the "
                            "cattle grid so nobody breaks a leg."),
            ("cowleen", "And somebody tells the herd. Quietly."),
            ("mooriarty", "And somebody deals with the shotgun."),
            ("moomaw", "Ol' Bessie. He keeps her in a cabinet in his office. The key's in the drawer by his bed."),
            ("mooriarty", "If Chuck walks out on Sunday with Bessie, step three gets very short."),
            ("cowleen", "Tomorrow night, then. While he's asleep."),
        ]
        yield from g.talk(lines)
        g.cutscene_end_now()
        g.set_time("dusk", 10)
        g.ambience("night")
        self.base_music = "music_night"

    # ==================================================================
    # SATURDAY
    # ==================================================================
    def setup_day6(self):
        g = self.g
        self.morning()
        self.wake_in_stall()
        self.prop("grinder", self._grinder((26, 0, -14.6)))
        self.chuck_saturday()
        self.dhook("update", self.sat_update)
        self.dhook("use", self.radio_use)
        self.dhook("caught_line", lambda: random.choice([
            "Hey! You're s'posed to be restin' up!", "Tomorrow's a big day, forty-seven. Back in the pasture.",
            "Out for a stroll, huh? Not today."]))
        self.grind = {"on": False, "t": 0.0}

    def _grinder(self, pos):
        mb = MeshBuilder()
        mb.box((0, 0.4, 0), (0.5, 0.8, 0.4), color=(0.3, 0.32, 0.35, 1), uv_rect=models.WHITE)
        mb.cylinder((0, 0.95, 0), 0.28, 0.08, color=(0.6, 0.58, 0.55, 1), segs=16, rot=(0, 0, 90))
        mb.box((0, 0.85, 0), (0.1, 0.12, 0.1), color=(0.2, 0.2, 0.2, 1), uv_rect=models.WHITE)
        e = Entity(model=mb.build(solid_rect=models.WHITE), texture=tex("atlas"), shader=FARM_SHADER, position=pos)
        return e

    def chuck_saturday(self):
        g = self.g

        def grind(on):
            def fn():
                self.grind["on"] = on
                if on:
                    g.audio.loop("grinder", "loop_grinder", vol=0.9, pos=(26, 1, -14.6), rng=45, group="sfx")
                else:
                    g.audio.stop_loop("grinder", 0.3)
            return fn
        self.chuck_routine([
            ("tool", "knife"), ("go", (26, 0, -16.1), 2.0), ("face", (26, -14.6)),
            ("call", grind(True)), ("wait", 28, "sharpen", SHARPEN_LINES, (26, -14.6)), ("call", grind(False)),
            ("go", (40, 0, 18), 2.0), ("wait", 8, "look"),
            ("go", (0, 0, -10), 2.0), ("wait", 6, "look"),
            ("go", (26, 0, -16.1), 2.0), ("face", (26, -14.6)),
            ("call", grind(True)), ("wait", 28, "sharpen", SHARPEN_LINES, (26, -14.6)), ("call", grind(False)),
            ("go", (-14, 0, -35), 2.0), ("wait", 6, "look"),
        ])
        g.farmer.teleport((26, 0, -16.1), 0)
        g.mask_noise("grinder", (26, 0, -14.6), 11, lambda: self.grind["on"])

    def sat_update(self, dt):
        self.base_update(dt)
        if self.grind.get("on"):
            self.grind["t"] -= dt
            if self.grind["t"] <= 0:
                self.grind["t"] = random.uniform(1.5, 3.0)
                self.g.audio.play("metal_clang", vol=0.25, pitch=2.2, pos=(26, 1, -14.6), rng=40)

    def day6(self):
        yield from self.step("d6_wake", self.d6_wake)
        yield from self.step("d6_prep", self.d6_prep,
                             hint="Plug: tractor, in the barn. Planks: the lumber pile south of the shed, carried to "
                                  "the cattle grid at the main gate. Herd: talk to any five herd cows.")
        yield from self.step("d6_night", self.d6_night,
                             hint="Chuck's asleep. The cabinet key's in the nightstand by his bed; the gun cabinet is "
                                  "in the office. Walk softly.")
        yield from self.step("d6_stars", self.d6_stars, hint="Cowleen's by the Old Oak.")
        yield from self._run_day(7)

    def d6_wake(self):
        g = self.g
        c = g.cows["cowleen"]
        c.teleport((-45.6, 0, -4.2), 20)
        g.cutscene_start(letterbox=True)
        g.player.look_at_point((c.x, 1.3, c.z))
        yield from g.fade_in(1.2)
        yield from g.talk([
            ("cowleen", "Hear that? He's sharpening knives by the barn. SHING. SHING. Since six o'clock."),
            ("cowleen", "The grinder's loud, though. Near it, he won't hear a thing."),
            ("cowleen", "Three jobs today: spark plug, planks, and the herd. Then tonight, the shotgun."),
        ])
        g.cutscene_end_now()

    def d6_prep(self):
        g = self.g
        herd_n = {"n": len(self.flags.get("rallied", []))}
        planks = {"n": self.flags.get("planks_laid", 0)}

        def refresh():
            self.objectives(("plug", "Put the spark plug in the tractor"),
                            ("planks", f"Lay planks over the cattle grid ({planks['n']}/3)"),
                            ("herd", f"Rally the herd ({min(5, herd_n['n'])}/5)"))
            if self.done("sparkplug_in"):
                g.complete("plug", sound=False)
            if planks["n"] >= 3:
                g.complete("planks", sound=False)
            if herd_n["n"] >= 5:
                g.complete("herd", sound=False)
        refresh()
        self.mark((22, 1, "Tractor"), (-8, -40, "Lumber"), (0, 82.5, "Cattle grid"), (-45, -40, "Herd"))

        def plug(gg):
            gg.inv.remove("sparkplug")
            self.setf("sparkplug_in")
            gg.audio.play("metal_clang", vol=0.4, pitch=1.8)
            gg.examine("You screw the spark plug in with your teeth. It tastes like vinegar.")
            gg.complete("plug")
        g.on("tractor", "Screw in the spark plug", plug, cond=lambda gg: gg.inv.has("sparkplug"))
        g.on("tractor", "Look at the tractor",
             lambda gg: gg.examine("Key: you have it. Diesel: full. Spark plug: in. Ready for tomorrow."),
             cond=lambda gg: gg.flags.get("sparkplug_in"))

        def take_plank(gg):
            carrying = gg.inv.count("plank")
            if carrying + planks["n"] >= 3:
                gg.examine("That's enough planks.")
                return
            gg.inv.add("plank", 1, silent=True)
            gg.inv.select_key("plank")
            gg.audio.play("wood_crack", vol=0.3, pitch=1.5)
            gg.ui.toast(f"Plank ({gg.inv.count('plank')} in your mouth)", "plank")
        g.on("woodpile", "Take a plank", take_plank, cond=lambda gg: planks["n"] < 3)

        def lay(gg):
            gg.inv.remove("plank")
            planks["n"] += 1
            self.flags["planks_laid"] = planks["n"]
            self.lay_planks(planks["n"])
            gg.audio.play("thump", vol=0.7, pos=(0, 0.3, 82.5), rng=30)
            gg.noise((0, 0, 82.5), 8, "plank")
            refresh()
            if planks["n"] >= 3:
                gg.audio.play("ding", vol=0.6)
        g.on("cattle_grid", "Lay a plank across the grid", lay, cond=lambda gg: gg.inv.has("plank"))

        def rally(cow):
            rl = set(self.flags.get("rallied", []))
            if cow.idx in rl:
                return False
            rl.add(cow.idx)
            self.flags["rallied"] = sorted(rl)
            herd_n["n"] = len(rl)
            yield from g.talk([
                ("you", "Moo. (Sunday, at dawn. When the rooster crows, follow the tractor. Pass it on.)"),
                (cow, RALLY_LINES[cow.idx % len(RALLY_LINES)]),
            ])
            refresh()
            if herd_n["n"] == 5:
                g.audio.play("ding", vol=0.6)
            return True
        self.hook("herd_talk", rally)
        yield lambda: self.done("sparkplug_in") and planks["n"] >= 3 and herd_n["n"] >= 5 and not g.busy
        self.setf("herd_rallied")

    def d6_night(self):
        g = self.g
        f = g.farmer
        p = g.player
        g.cutscene_start(letterbox=False)
        yield from g.fade_out(1.2)
        g.audio.stop_loop("grinder", 0.2)
        self.grind["on"] = False
        self.remove_prop("grinder")
        g.set_time("night")
        g.ambience("night")
        self.base_music = "music_night"
        f.set_routine([])
        f.sleep((58.5, Y + 0.62, 46.3), 180)
        g.world.set_lamp("porch", True)
        if not g.phys.in_zone("pasture", p.x, p.z):
            self.return_to_pasture()
            f.sleep((58.5, Y + 0.62, 46.3), 180)
            p.teleport(-40, 0, -30, 90)
        yield from g.fade_in(1.2)
        g.cutscene_end_now()
        self.objectives(("ckey", "Take the cabinet key from Chuck's nightstand"),
                        ("gun", "Take Ol' Bessie from the gun cabinet (office)"))
        if g.inv.has("cabinet_key") or self.done("cabinet_open"):
            g.complete("ckey", sound=False)
        self.mark((60.9, 47.1, "Nightstand"), (50.9, 46.5, "Gun cabinet"))

        def after():
            self.return_to_pasture()
            f.sleep((58.5, Y + 0.62, 46.3), 180)
            g.ui.popup_sub("Chuck walked you back in his pyjamas, yawning, and went straight back to bed.", 6)
            return True
        self.hook("after_caught", after)
        self.hook("caught_line", lambda: "Mmf... forty-seven? In my HOUSE? At NIGHT? ...Back to bed. Both of us.")

        def drawer(gg):
            gg.audio.play("door_creak", vol=0.3, pitch=1.6, pos=(60.9, 1, 47.1), rng=15)
            gg.noise((60.9, Y, 47.1), 5, "drawer")
            gg.inv.add("cabinet_key")
            gg.complete("ckey")
        g.on("nightstand", "Open the drawer (quietly)", drawer,
             cond=lambda gg: not gg.inv.has("cabinet_key") and not self.done("cabinet_open"))

        def cabinet(gg):
            gg.inv.remove("cabinet_key")
            self.setf("cabinet_open")
            gg.audio.play("chain", vol=0.3, pitch=1.4, pos=(50.9, 1, 46.5), rng=15)
            gg.inv.add("shotgun")
            gg.complete("gun")
        g.on("gun_cabinet", "Unlock the cabinet and take Ol' Bessie", cabinet,
             cond=lambda gg: gg.inv.has("cabinet_key"))
        g.on("gun_cabinet", "Try the gun cabinet", lambda gg: gg.examine("Locked. The key's in the nightstand by "
                                                                         "Chuck's bed."),
             cond=lambda gg: not gg.inv.has("cabinet_key") and not gg.inv.has("shotgun"))
        yield lambda: g.inv.has("shotgun")

    def d6_stars(self):
        g = self.g
        p = g.player
        c = g.cows["cowleen"]
        c.teleport((-48.0, 0, -39.5), 20)
        c.look = "player"
        self.objectives(("back", "Get back to the pasture"), ("cowleen", "Find Cowleen"))
        self.mark((-48, -39.5, "Cowleen"))
        yield lambda: g.phys.in_zone("pasture", p.x, p.z) and not g.runner.running("caught")
        g.complete("back")
        yield lambda: math.hypot(p.x - c.x, p.z - c.z) < 4.5 and not g.busy
        g.complete("cowleen")
        g.cutscene_start(letterbox=True)
        p.teleport(-46.5, 0, -41.0, 330)
        g.cam_set((-44.5, 1.2, -44.5), (-47.5, 2.8, -38.0))
        self.lock_hud_music("music_night", 0.5, 2.0)
        yield from g.talk([
            ("cowleen", "Can't sleep either?"),
            ("you", "Moo. (No.)"),
            ("cowleen", "When we were calves you told me the stars were holes in the barn roof. You said the sky was "
                        "just a bigger barn."),
            ("you", "Moo. (It still might be.)"),
            ("cowleen", "Tomorrow we find out how big."),
            ("cowleen", "Forty-Seven. Whatever happens at that gate, you don't stop. You keep going till you hit the "
                        "road, and then you keep going."),
            ("you", "Moo. (You too.)"),
            ("cowleen", "Obviously. I'm very fast when I want to be. You've just never seen me want to."),
        ])
        g.runner.start(g.cam_move((-44.5, 3.0, -44.5), (-47.5, 12, -32.0), dur=4.0), name="cam", tag="day")
        yield from g.fade_out(4.0)
        g.cutscene_end_now()
        self.unlock_music()

    # ==================================================================
    # SUNDAY
    # ==================================================================
    def setup_day7(self):
        g = self.g
        self.morning(preset="predawn", music="music_night", amb="night")
        self.wake_in_stall()
        f = g.farmer
        f.set_routine([])
        f.sleep((58.5, Y + 0.62, 46.3), 180)
        g.world.set_lamp("porch", True)
        self.dhook("update", self.base_update)
        self.dhook("caught_line", lambda: "Hnnh? Not today, forty-seven. Not TODAY.")

        def after():
            self.return_to_pasture()
            f.sleep((58.5, Y + 0.62, 46.3), 180)
            return True
        self.dhook("after_caught", after)

    def day7(self):
        yield from self.step("d7_crow", self.d7_crow)
        yield from self.step("d7_fuse", self.d7_fuse, hint="The main fuse is on the generator in the tool shed. In "
                                                          "through the back.", save=False)
        yield from self.step("d7_tractor", self.d7_tractor,
                             hint="Tractor's in the barn. Drive it through the barn doors, down the drive and through "
                                  "the main gate. W/S throttle, A/D steer.", save=False)
        yield from self.step("d7_boss", self.d7_boss,
                             hint="Dodge his lunges. When the pitchfork sticks in the ground, hit him. When he's out of "
                                  "breath, hit him.", save=False)
        yield from self.play_ending()

    def d7_crow(self):
        g = self.g
        p = g.player
        g.cutscene_start(letterbox=True)
        cl = self.prop("cluck_roof", models.RoosterModel(headband=True, scale=1.6, position=(41, 3.35, -29.5),
                                                          rotation_y=250))
        g.cam_set((33.5, 2.2, -31.5), (41, 3.6, -29.5))
        yield from g.fade_in(1.5)
        yield 1.0
        g.set_time("dawn", 60)
        g.audio.play("rooster_crow", vol=1.0, pos=(41, 3.5, -29.5), rng=200)
        cl.head.rotation_x = -40
        yield 2.8
        cl.head.rotation_x = 0
        g.audio.play("rooster_crow", vol=1.0, pitch=0.95, pos=(41, 3.5, -29.5), rng=200)
        yield 2.5
        g.cam_set((-44, 1.5, -6.5), (-45.6, 1.3, -4.2))
        c = g.cows["cowleen"]
        c.teleport((-45.6, 0, -4.2), 20)
        yield from g.talk([
            ("cowleen", "That's him. That's the signal."),
            ("cowleen", "Go. We'll be ready when you come through."),
        ])
        g.cutscene_end_now()
        self.lock_hud_music("music_stealth", 0.6, 2.0)

    def d7_fuse(self):
        g = self.g
        self.objectives(("fuse", "Pull the main fuse in the tool shed"))
        self.mark((-10, -24.3, "Generator"))
        done = {"d": False}

        def pull(gg):
            gg.audio.play("zap", vol=1.0, pos=(-10, 1, -24), rng=40)
            gg.ui.flash((1, 0.95, 0.5), 0.4)
            gg.audio.stop_loop("fence", 0.2)
            gg.inv.add("fuse")
            gg.world.set_lamp("shed", False)
            done["d"] = True
        g.on("fuse", "Pull the main fuse", pull)
        g.on("generator", "Pull the main fuse", pull)
        yield lambda: done["d"]
        g.complete("fuse")
        yield from g.talk([("narrator", "The fence ticks once more, then goes quiet.")])

    def d7_tractor(self):
        g = self.g
        f = g.farmer
        w = g.world
        self.objectives(("start", "Start the tractor (barn)"))
        self.mark((22, 1, "Tractor"))
        started = {"d": False}

        def start(gg):
            started["d"] = True
        g.on("tractor", "Climb in and start her up", start)
        yield lambda: started["d"]
        g.complete("start")
        smashed = {"barn": False, "main": False}
        tr = Tractor(g, w.tractor, on_smash=lambda name: smashed.__setitem__(name, True))
        tr.smashables = [("barn", [w.doors["barn_left"], w.doors["barn_right"]]),
                         ("main", [w.doors["main_left"], w.doors["main_right"]])]
        tr.x, tr.z, tr.yaw = w.tractor.x, w.tractor.z, w.tractor.rotation_y
        tr.enter()
        self.unlock_music()
        self.lock_hud_music("music_boss", 0.5, 2.0)
        g.restricted_fn = lambda gg: False
        self.house_lights(True)
        f.wake()
        f.say("WHO'S TOUCHIN' MY TRACTOR?!", force=True)
        g.ui.popup_sub("W/S throttle   A/D steer   Mouse look. Go through the barn doors!", 7)
        self.objectives(("drive", "Drive through the main gate"))
        self.mark((22, -10, "Barn doors"), (0, 86, "Main gate"))
        yield lambda: smashed["barn"] or smashed["main"]
        if not smashed["main"]:
            self.mark((0, 86, "Main gate"))
        yield lambda: smashed["main"]
        w.chain.enabled = False
        g.complete("drive")
        g.stats["gate_smashed"] = 1
        yield 0.8
        # everyone goes
        tr.speed = 0
        g.cutscene_start(letterbox=True)
        tr.leave()
        g.vehicle = None
        self.place_tractor(tr.x, tr.z, tr.yaw)
        g.player.teleport(0, 0, 74, 0)
        g.cam_set((-12, 4.5, -25.5), (-20, 1.5, -35))
        yield 0.5
        sl = g.cows["sirloin"]
        sl.teleport((-29, 0, -35), 90)
        sl.goto((-15, 0, -35), 6.0)
        yield 0.7
        g.world.doors["pasture_gate"].set_open(True)
        self.stampede()
        g.audio.play("gate_smash", vol=1.0, pos=(-18, 1, -35), rng=80)
        sl.bubble("MOOOOO!", 3)
        g.audio.play("moo_sirloin_exclaim_0", vol=1.0, group="voice")
        yield from g.talk([("sirloin", "FOR MOOZART!")])
        g.audio.loop("herd", "loop_herd", vol=0.8, pos=(-10, 1, -30), rng=150, group="sfx")
        g.runner.start(g.cam_move((0, 5, 20), (0, 1, -10), dur=3.0), name="cam", tag="day")
        yield 3.2
        # Chuck, running out in his underwear
        f.set_visible(True)
        f.sleeping = False
        f.set_outfit("underwear")
        f.set_tool("pitchfork")
        f.teleport((6, 0, 58), 200)
        f.scripted()
        g.cam_set((3, 2.0, 70), (5, 1.5, 60))
        f.goto((1.5, 0, 66), 4.0)
        yield 2.2
        g.cam_set((0.5, 1.4, 72.5), (1.5, 1.6, 66))
        g.player.teleport(0, 0, 72, 180)
        yield from g.talk([
            ("chuck", "NOBODY'S LEAVIN'! Not you, not the herd, not NOBODY!"),
            ("chuck", "I raised you from a calf! I bottle-fed you! You BIT me!"),
            ("you", "Moo. (Move.)"),
            ("chuck", "Over my dead body!"),
        ])
        g.cutscene_end_now()

    def stampede(self):
        g = self.g
        rnd = random.Random(7)
        for i, h in enumerate(g.herd):
            h.free = True
            h.lie = False
            h.model.lying_target = 0.0
            tx, tz = rnd.uniform(-10, 10), rnd.uniform(30, 52)
            h.path = g.world.find_path((h.x, 0, h.z), (tx, 0, tz))
            h.walk_speed = rnd.uniform(3.2, 4.5)
            h.state = "stampede"
        for k, c in g.cows.items():
            if c.visible and k != "sirloin":
                c.goto((rnd.uniform(-6, 6), 0, rnd.uniform(40, 50)), 3.6)

    def d7_boss(self):
        g = self.g
        f = g.farmer
        p = g.player
        arena = (-9.0, 9.0, 58.0, 80.0)
        self.objectives(("boss", "Get past Chuck"))
        self.mark()
        res = {"phase3": False, "lost": False}
        boss = ChuckBoss(g, arena, on_phase3=lambda: res.__setitem__("phase3", True))
        f.boss = boss
        f.state = "boss"
        f.set_tool("pitchfork")
        g.enemies.append(boss)
        self.enemy = boss
        p.health = p.max_health
        g.ui.set_boss("CHUCK", 1.0)
        g.ui.set_health(p.health, p.max_health, True)
        g.ui.popup_sub("Left click headbutt   Right click kick   R throw\nHit him when he's stuck or winded", 7)
        self.hook("defeated", lambda: res.__setitem__("lost", True))
        allies = {"cluck_t": 14.0, "loin_t": 24.0, "cluck": None}
        while not res["phase3"]:
            g.ui.set_health(p.health, p.max_health, True)
            # keep the fight near the gate
            x0, x1, z0, z1 = arena
            p.x = min(x1 + 2, max(x0 - 2, p.x))
            p.z = min(z1 + 3, max(z0 - 3, p.z))
            p.col.x, p.col.z = p.x, p.z
            if boss.phase >= 2:
                allies["cluck_t"] -= time.dt
                allies["loin_t"] -= time.dt
                if allies["cluck_t"] <= 0 and boss.state in ("approach", "retreat", "throw_windup"):
                    allies["cluck_t"] = 16.0
                    g.runner.start(self._cluck_attack(boss), name="ally_cluck", tag="day")
                if allies["loin_t"] <= 0 and boss.state in ("approach", "retreat", "throw_windup"):
                    allies["loin_t"] = 22.0
                    if self.done("sq_helm"):
                        g.runner.start(self._loin_charge(boss), name="ally_loin", tag="day")
                    else:
                        g.cows["sirloin"].bubble("MOO!")
                        g.ui.bark_line("If I had a helm I'd be in there!", "Sir Loin")
            if res["lost"]:
                res["lost"] = False
                g.cutscene_start(letterbox=True)
                yield from g.fade_out(0.6)
                boss.remove()
                boss.hp = max(boss.hp, 8)
                boss.phase = 1 if boss.hp > 8 else 2
                boss.state = "approach"
                boss.t = 2.0
                f.teleport((1.5, 0, 66), 180)
                p.teleport(0, 0, 76, 180)
                p.health = p.max_health
                g.ui.set_boss("CHUCK", boss.hp / boss.MAX_HP)
                yield from g.fade_in(0.6)
                g.cutscene_end_now()
                f.say("Had enough? 'Cause I'm just gettin' STARTED.", force=True)
            yield None
        self.hooks.pop("defeated", None)
        # the cowbell
        g.cutscene_start(letterbox=True)
        boss.remove()
        g.enemies.remove(boss)
        g.ui.set_boss("", 0, False)
        g.ui.set_health(0, 0, False)
        f.boss = None
        f.scripted()
        f.teleport((f.x, 0, f.z), f.yaw)
        f.pose = "windup"
        p.teleport(0, 0, min(79, f.z + 5.5), 180)
        p.look_at_point((f.x, 1.2, f.z))
        g.cam_set((f.x + 4.5, 1.6, (f.z + p.z) / 2), ((f.x + p.x) / 2, 1.0, (f.z + p.z) / 2))
        yield from g.talk([("chuck", "RRRRAAAAAGH!")])
        bx, bz = (f.x + p.x) / 2, (f.z + p.z) / 2
        bell = self.prop("bell", models.item_model("cowbell", position=(bx - 3, 0.9, bz), scale=1.4))
        if g.inv.has("cowbell"):
            g.inv.remove("cowbell")
            g.ui.popup_sub("You toss your old cowbell into the dirt.", 3)
        else:
            g.ui.popup_sub("Cowleen kicks your old cowbell into the dirt in front of him.", 3)
        for k in range(12):
            bell.position = (bx - 3 + k * 0.25, 0.9 - k * 0.07, bz)
            yield None
        bell.position = (bx, 0.1, bz)
        g.audio.play("cowbell_drop", vol=1.0)
        f.goto((bx, 0, bz), 5.0)
        yield lambda: math.hypot(f.x - bx, f.z - bz) < 0.6 or not f.path
        f.path = []
        f.set_tool(None)
        f.state = "scripted"
        f.pose = "fallen"
        g.audio.play("thump", vol=1.0)
        g.audio.play("cowbell_0", vol=1.0)
        g.stats["chuck_trips"] = g.stats.get("chuck_trips", 0) + 1
        self.unlock_music()
        self.lock_hud_music(None, 0, 1.0)
        yield 1.5
        p.teleport(f.x + 0.2, 0, f.z + 2.4, 180)
        p.look_at_point((f.x, 0.4, f.z))
        g.inv.select_key("shotgun")
        g.refresh_hotbar()
        p.hold("shotgun")
        g.cam_set((f.x - 2.5, 0.9, f.z + 2.5), (f.x + 0.3, 0.5, f.z + 0.6))
        yield from g.talk([
            ("chuck", "You're... you're just a cow."),
        ])
        g.cutscene_end_now()
        g.cutscene_start(letterbox=True)
        g.player.frozen = True
        p.look_at_point((f.x, 0.5, f.z))
        yield from g.talk([("you", "Moo. (My name is Forty-Seven.)")])
        g.audio.play("shotgun", vol=1.0)
        g.ui.set_fade(1.0, (1, 1, 1))
        g.audio.stop_everything()
        yield 2.5
        f.set_visible(False)
        g.player.frozen = False
        self.setf("chuck_done")

    def _cluck_attack(self, boss):
        g = self.g
        f = g.farmer
        cl = models.RoosterModel(headband=True, scale=1.6, position=(f.x - 8, 0, f.z + 3))
        self.fx.append(_Temp(cl))
        g.audio.play("squawk", vol=1.0, pos=(f.x, 1, f.z), rng=60)
        g.ui.bark_line("BAWK! GET OFF MY FARM!", "Cluck Norris")
        for k in range(24):
            cl.position = (f.x - 8 + k / 24 * 7.6, abs(math.sin(k / 24 * math.pi)) * 1.5, f.z + 3 - k / 24 * 2.8)
            cl.look_at((f.x, 0.5, f.z))
            cl.rotation_x = 0
            cl.animate(0.03, 6, False)
            yield None
        if boss.finished:
            destroy(cl)
            return
        boss.stun(3.2, "cluck", "ow")
        f.say(random.choice(["AAH! GET IT OFF!", "Not the FACE!", "Ow ow OW! Bad chicken!"]), force=True)
        g.audio.play("squawk", vol=1.0)
        for k in range(60):
            cl.position = (f.x + math.sin(k * 0.6) * 0.4, 1.7 + abs(math.sin(k * 0.8)) * 0.2, f.z + math.cos(k * 0.6) * 0.4)
            cl.animate(0.03, 0, True)
            if k % 12 == 0:
                boss.fx.append(Feathers((f.x, 1.8, f.z), n=4))
            yield None
        for k in range(20):
            cl.position = (f.x - k * 0.4, 1.7 + k * 0.1, f.z + k * 0.2)
            yield None
        destroy(cl)

    def _loin_charge(self, boss):
        g = self.g
        f = g.farmer
        sl = g.cows["sirloin"]
        sx, sz = f.x - 12, f.z - 4
        sl.teleport((sx, 0, sz), 70)
        sl.path = []
        g.ui.bark_line("FOR THE PASTURE!", "Sir Loin")
        g.audio.play("moo_sirloin_exclaim_1", vol=1.0, pos=(sx, 1.4, sz), rng=60, group="voice")
        t = 0.0
        while t < 1.3:
            t += time.dt
            k = min(1.0, t / 1.3)
            sl.x = sx + (f.x - 0.8 - sx) * k
            sl.z = sz + (f.z - 0.3 - sz) * k
            sl.yaw = math.degrees(math.atan2(f.x - sx, f.z - sz))
            sl._apply()
            sl.model.animate(0.03, 7.0, None)
            yield None
        if boss.finished:
            return
        g.audio.play("punch", vol=1.0)
        g.audio.play("thump", vol=1.0)
        boss.state = "fallen"
        boss.t = 3.5
        f.pose = "fallen"
        f.say("OOF!", kind="ow", force=True)
        g.stats["chuck_trips"] = g.stats.get("chuck_trips", 0) + 1
        yield 1.0
        sl.goto((6, 0, 50), 3.0)

    def play_ending(self):
        g = self.g
        g.cutscene_start(letterbox=True)
        g.ui.show_hud(False)
        self.ending_active = True
        for e in list(g.enemies):
            if hasattr(e, "remove"):
                e.remove()
        g.enemies = []
        g.farmer.set_visible(False)
        for c in g.cows.values():
            c.set_visible(False)
        for h in g.herd:
            h.model.enabled = False
            h.col.enabled = False
        for k in list(self.props):
            self.remove_prop(k)
        g.set_time("sunrise")
        g.ambience("day")
        from .world import terrain_h
        # the herd walking down the road, and the two of you on the hill
        walkers = []
        rnd = random.Random(3)
        hides = ["hide_bw", "hide_bw", "hide_brown", "hide_black", "hide_gray", "hide_red", "hide_dun"]
        for i in range(40):
            m = models.CowModel(hide=rnd.choice(hides), bell=False, tag="tag_blank", horns=rnd.random() < 0.2)
            x = rnd.uniform(-2.4, 2.4)
            z = 96 + i * 3.1 + rnd.uniform(-0.8, 0.8)
            m.position = (x, 0, z)
            m.rotation_y = rnd.uniform(-8, 8)
            walkers.append([m, x, z, rnd.uniform(1.2, 1.5)])
        sl = models.CowModel(hide="hide_red", bull=True, acc=("cape",) + (("bucket",) if self.done("sq_helm") else ()),
                             tag="tag_blank")
        sl.position = (0.5, 0, 92)
        cl = models.RoosterModel(headband=True, scale=1.4, parent=sl, position=(0, 1.55, 0))
        walkers.append([sl, 0.5, 92.0, 1.3])
        hx, hz = 16.0, 124.0
        hy = terrain_h(hx, hz)
        me = models.CowModel(hide="hide_brown", bell=False, tag="tag_47", pupils=[(0, 0), (0, 0)])
        me.position = (hx, hy, hz)
        me.rotation_y = 300
        cw = models.CowModel(hide="hide_brown", bell=False, acc=("daisy",), tag="tag_blank")
        cw.position = (hx - 1.6, terrain_h(hx - 1.6, hz + 0.6), hz + 0.6)
        cw.rotation_y = 300
        ents = [w[0] for w in walkers] + [me, cw]
        g.audio.music_play("music_ending", 0.9, fade=0.5)
        self.music_locked = True
        g.cam_set((hx + 5.5, hy + 2.4, hz - 6.0), (hx - 8, hy + 1.2, hz + 10))
        yield from g.fade_in(3.0)
        T = 0.0

        def walk(dt):
            for w_ in walkers:
                m, x, z, s = w_
                w_[2] = z + s * dt
                m.position = (x, 0, w_[2])
                m.animate(dt, s, None)
            me.animate(dt, 0, None)
            cw.animate(dt, 0, None)
        self.hook("update", walk)
        g.runner.start(g.cam_move((hx + 3.5, hy + 1.8, hz - 4.0), (hx - 10, hy + 1.0, hz + 16), dur=12.0),
                       name="cam", tag="day")
        yield 12.5
        yield from g.talk([
            ("cowleen", "He'd have written something about this."),
            ("you", "Moo. (He did.)"),
        ])
        g.runner.start(g.cam_move((hx - 2, hy + 7, hz - 14), (0, 2, hz + 40), dur=14.0), name="cam", tag="day")
        yield 10.0
        yield from g.fade_out(4.0)
        self.hooks.pop("update", None)
        for e in ents:
            destroy(e)
        g.ui.set_fade(1.0, (0, 0, 0))
        yield from self.credits()
        self.setf("game_finished")
        g.save_checkpoint()
        self.to_title()


class _Temp:
    """Wraps an entity so it gets cleaned up with the day."""

    def __init__(self, e):
        self.e = e
        self.alive = True

    def update(self, dt):
        if not self.e:
            self.alive = False

    def remove(self):
        if self.e:
            destroy(self.e)


class Smoke:
    def __init__(self, pos):
        self.pos = pos
        self.puffs = []
        self.t = 0.0
        self.alive = True
        self.spawn = 0.0

    def update(self, dt):
        self.t += dt
        self.spawn -= dt
        if self.spawn <= 0 and self.t < 60:
            self.spawn = 0.35
            mb = MeshBuilder().sphere((0, 0, 0), 0.5, color=(0.35, 0.35, 0.37, 1), segs=7, rings=5)
            e = Entity(model=mb.build(), texture=tex("white"), shader=FARM_SHADER, position=self.pos)
            self.puffs.append([e, 0.0])
        keep = []
        for pf in self.puffs:
            e, a = pf
            pf[1] = a + dt
            e.y += dt * 1.3
            e.x += dt * 0.6
            e.scale = 1 + pf[1] * 0.9
            if pf[1] > 7:
                destroy(e)
            else:
                keep.append(pf)
        self.puffs = keep

    def remove(self):
        for e, _ in self.puffs:
            destroy(e)
        self.puffs = []
        self.alive = False


# ----------------------------------------------------------------------
# documents
# ----------------------------------------------------------------------
PLANNER = """MON   fix fence (AGAIN)
TUE   oil tractor
WED   dentist??
THU   truck pickup #12 -> Processing
FRI   BOWLING W/ THE BOYS!!!
SAT   sharpen stuff
SUN   #47 -> PROCESSING
        BBQ w/ Dale!!!
        buy milk"""

HOOFPRINTS = """Sixteen bars, pressed into the mud one hoof at a time. Three to a bar.

The rain has softened the edges, but you can still read it. The first four bars are the ones he played you on Monday. The next four came from Chuck's radio. Then Cluck Norris's crow, going up and up.

The last hoofprint is set apart from the others and pressed in deeper.

That one's yours."""

EMAILS = """FROM: Dale
RE: sunday!!!
Chuck buddy. Can't wait for Sunday. I'm bringing the good potato salad, not the one from the store.
Re: the other thing. We're agreed. After the BBQ I take the rest of the herd off your hands, all 47 head, before the end of the month. My cousin at the plant says he'll do us a fair price.
- Dale

FROM: Happy Acres Processing
RE: Pickup confirmation
Thursday pickup confirmed: 1 head (#12). Thank you for your business.

FROM: Mom
RE: (no subject)
Charles, are you eating vegetables. Call your mother."""

SPREADSHEET = """COWS.XLS

#12 .............. Thursday ......... DONE
#47 .............. Sunday (BBQ)
everybody else .... Dale, end of month

Total: $$$ (ask Dale's cousin)"""

DALE_REPLY = """TO: Dale
RE: sunday!!!

Dale, BBQ's off. I've gone vegetarian. Don't call.
- Chuck

[Sent]"""


# ----------------------------------------------------------------------
# idle conversations: day -> friend -> list of conversations
# (a conversation is a list of lines; bare strings are said by that friend)
# ----------------------------------------------------------------------
CHATTER = {
    0: {
        "cowleen": [["Keep your head down and your ears up."], ["If you get caught, Chuck just walks you back. He "
                                                               "doesn't know what we're doing. Yet."]],
        "moozart": [["I'm listening to the fence tick. It's slightly out of time."]],
        "sirloin": [["I stand guard. Over what, I'm not sure. But I stand."]],
        "cowpernicus": [["Press Tab for your journal. I'd kill for a journal. I've got a patch of mud."]],
        "mooriarty": [["Clovers. Bring me clovers. I've got the goods."]],
        "moomaw": [["Earl used to say you can't hurry grass. He was talking about grass."]],
    },
    1: {
        "cowleen": [["The page. The oak. Go on."], ["Tell the others, then the oak at sundown."]],
        "moozart": [["Four bars. Just four. They're good bars, though."]],
        "sirloin": [["A knight without a helm is just a large cow with opinions."]],
        "cowpernicus": [["I'm drafting. Come back at sundown."]],
        "moomaw": [["Chuck never hurt a fly, you know. Flies aren't on the menu."]],
    },
    2: {
        "cowleen": [["He does the feed run, then plays with the tractor. Over and over. Then he does it again."],
                    ["Watch when he revs the engine. You won't hear yourself think."]],
        "moozart": [["The radio. I can hear it through the barn wall sometimes. Terrible songs. Good bits in them."]],
        "sirloin": [["If you find a helm in that shed, it is MINE. By right of being a knight."]],
        "cowpernicus": [["The toolbox has a three-digit combination. Chuck writes his passwords on sticky notes. "
                         "Statistically, so does everyone."]],
        "mooriarty": [["The board on the back of the shed? I loosened it. Years ago. You're welcome."]],
        "moomaw": [["You're so quiet without that bell. It's nice. Earl hated his too."]],
    },
    3: {
        "cowleen": [["He's got a toothache. He's slow, and he's cross. He'll nap on the porch around noon."],
                    ["The key's up in the rafters and the diesel's in the coop? This farm."]],
        "moozart": [["Twelve bars would be good. I'd settle for twelve bars."]],
        "sirloin": [["The rooster? I have fought the rooster. We agreed it was a draw. He did not agree."]],
        "cowpernicus": [["Rubber, not your nose. I can't stress that enough."]],
        "mooriarty": [["Rubber chicken's in stock. Just saying."]],
        "moomaw": [["Chuck's dentist is Dale's cousin. The one at the plant. He does both."]],
    },
    4: {
        "cowleen": [["Stay low. He can't see much in the rain, but he can see a black cow in a wig."]],
        "sirloin": [["If the truck comes, I will stand in front of it. Probably."]],
        "cowpernicus": [["Rain cuts his sight to about seventeen metres. I measured. Roughly."]],
        "mooriarty": [["Truck's due at dusk. I know the driver's name. It doesn't help."]],
        "moomaw": [["Go on, dear. Get him somewhere safe."]],
    },
    5: {
        "cowleen": [["House. Spark plug. Computer. Back by dark."]],
        "sirloin": [["I miss him. Moozart. He used to hum when I got my head stuck in the fence."]],
        "cowpernicus": [["Computers have passwords. People use the name of whoever they love most. So, probably "
                         "his truck."]],
        "mooriarty": [["Chuck keeps a spare key where everybody keeps a spare key. Start at the doormat."]],
        "moomaw": [["If you're in the office, look for Earl. He's the handsome one."]],
    },
    6: {
        "cowleen": [["Plug, planks, herd. Then tonight."]],
        "sirloin": [["Tomorrow I charge. I have been practising on the trough."]],
        "cowpernicus": [["Three planks across the grid. Two and somebody breaks a leg. Three."]],
        "mooriarty": [["Dale's potato salad has raisins in it. I've heard. That's reason enough to leave."]],
        "moomaw": [["Earl got out once. Made it as far as the mailbox. He said it was worth it."]],
    },
    7: {
        "cowleen": [["Go. We're right behind you."]],
        "sirloin": [["The fuse, Forty-Seven! The FUSE!"]],
        "cowpernicus": [["Fuse, tractor, gate. In that order. Please."]],
        "mooriarty": [["Don't look at me. Go."]],
        "moomaw": [["Go on, sweetheart."]],
    },
}

RALLY_LINES = [
    "Moo! (Sunday at dawn? I'll be up. I'm always up. I'm a cow.)",
    "Moo. (Count me in. What are we doing? Doesn't matter. In.)",
    "Moo! (I've wanted to see the road since I was a calf. Is it nice? It looks nice.)",
    "Moo. (For Moozart. He hummed at me once. It was a good hum.)",
    "Moo! (Tell Sir Loin I'll follow him. Not too close. He swings his head about.)",
    "Moo. (I'll tell the others. Quietly. I'm very good at quiet.)",
    "Moo! (The road. The actual road. Okay. Okay okay okay.)",
    "Moo. (Dale's potato salad can wait for somebody else.)",
]
