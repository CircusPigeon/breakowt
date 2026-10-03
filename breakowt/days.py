"""The seven days. Mixed into Story (story.py), so `self` is the Story and `self.g` the Game."""
from __future__ import annotations

import math
import random
import time

from ursina import Entity, curve, destroy

from . import models
from .combat import CluckNorris, ChuckBoss, Feathers
from .engine.assets import tex
from .engine.meshbuilder import MeshBuilder
from .engine.shading import FARM_SHADER
from .interact import Handler, Interactable
from .farmer import HEARING, OWN_DOORS
from .npc import FRIENDS, ang_diff
from .vehicle import Tractor
from .world import BARN, COOP_RUN, DEER_STAND, GATE_PASTURE, HOUSE, HOUSE_Y, LOFT_Y, PASTURE, PLANT_BACK, PROC, \
    RADIO_SPOT, SHED, TRACTOR_TOP, in_pond

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

FENCE_LINES = ["Stupid fence.", "Every Monday. EVERY Monday.", "Who keeps LEANING on this?", "Hold still, you.",
               "Four hundred dollars of wire and it's scared of a cow's BUTT."]
FEED_LINES = ["Breakfast, ladies!", "Come and get it. Don't all rush at once.",
              "This feed costs more than my truck payment.", "Eat up. Marbling don't happen by itself.",
              "Grain-finished. Like the fancy restaurants say. Whatever that means."]
OIL_LINES = ["C'mon, baby.", "Purr for Daddy.", "There she goes!", "Needs more oil. Everything needs more oil.",
             "You're the only one on this farm who listens to me, Big Green."]
TOOTH_LINES = ["Ow.", "Ow ow ow.", "Stupid tooth.", "Dentist's not till Thursday. THURSDAY.", "Mmmph. Ow.",
               "If I pull it myself, is that still dentistry?"]
RAIN_LINES = ["Great. Rain.", "My socks are wet. Both of 'em.", "Truck better not be late in this.",
              "Where's my other boot... oh. Right.", "Rain's good for the grass. Grass is good for the cows. Cows "
              "are good for... well. Circle of life."]
SHARPEN_LINES = ["Big day tomorrow.", "Nice and sharp.", "Dale likes 'em thick-cut.", "Sharp knife's a safe knife.",
                 "Ribeye, sirloin, T-bone... brisket for Dale. Dale's a brisket man. Dale's a simple man."]
GEN_LINES = ["Fuse is FRIED. Who fries a FUSE?", "Somebody's been in my shed. AGAIN.",
             "Fence is dead too. Great. GREAT.", "Thirty pounds of brisket, thawin' as we speak."]
PATROL_LINES = ["Somebody's out here.", "I know you're out here!", "Raccoons don't pull fuses!",
                "Show yourself!", "If this is Dale's idea of a surprise party...", "My BRISKET, people!"]
DIVE_LINES = ["WHOA!", "Not the TRACTOR!", "AAH! She's got no BRAKES!", "Who taught you to DRIVE?!",
              "That's MY tractor! I'm ON the payments!"]
SUNDAY_CAUGHT = ["HEY! Was it YOU? Did YOU kill my freezer?!", "Back in the pasture! And STAY there! It's your BIG DAY!",
                 "Forty-seven! Of COURSE it's forty-seven!"]
# Sunday, after the fuse: house (the freezer), the shed (the generator), then round the yard
SUNDAY_PATROL = [
    ("go", (56, HOUSE_Y, 32.0), 2.6), ("go", (40, 0, 18), 2.6), ("go", (14, 0, -14), 2.6),
    ("go", (-2, 0, -22), 2.4), ("face", (-8, -22)), ("wait", 7, "look", GEN_LINES, (-8, -22)),
    ("go", (14, 0, -14), 2.2), ("wait", 4, "look", PATROL_LINES),
    ("go", (0, 0, 10), 2.2), ("wait", 4, "look", PATROL_LINES),
    ("go", (20, 0, 23), 2.2), ("wait", 3, "look"),
    ("go", (22, 0, -14), 2.2), ("wait", 4, "look", PATROL_LINES),
    ("go", (-2, 0, -22), 2.2), ("wait", 5, "look", GEN_LINES, (-8, -22)),
]
COUNT_LINES = ["Thirty-one, thirty-two...", "...thirty-eight, thirty-nine. Hold STILL, you. Whichever number you are.",
               "Forty, forty-one... no, I counted you.", "...forty-two, forty-three...",
               "Forty... how are there always more of you when I count and fewer when I sell?"]

MOOHOLE_POS = (-18.0, -66.1)
BED_SLEEP = (58.5, Y - 0.02, 45.1)    # where Chuck's feet go in bed: the sleep pose lays him out along +z, 0.8 up
#                                      (boots to nightcap he's 2.7 m lying down; this keeps the cap off the headboard)
BED_GETUP = (56.95, Y, 45.7)          # where he stands when something gets him out of bed (by the rug)
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
        self._hum_ready = 0.0

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
            self._sq("helm", "Find Moogenes something to live in", "active")
            self._sq("specs", "Find Moothagoras some glasses", "active")
            self._sq("photo", "Bring Heifercleitus the photo of Big Ajax", "active")
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
            take("pencil")
            give("score")
            f["moozart_gone"] = True
        elif d == 5:
            # the spare key stays in the front door once it's unlocked
            give("sparkplug")
            f["house_unlocked"] = True
            f["gnome_broken"] = True
            f["emails_read"] = True
        elif d == 6:
            take("sparkplug")
            f["sparkplug_in"] = True
            f["planks_laid"] = 3
            f["herd_rallied"] = True
            f["cabinet_open"] = True
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
            self.moohole_prop(fl.get("moohole_item", "boot"))
        else:
            w.set_moohole_wire(None)
        self.lay_planks(fl.get("planks_laid", 0))
        self.place_tractor(22, 1, 180)
        w.gnome.rotation = (0, 200, 0) if not fl.get("gnome_broken") else (80, 200, 0)
        w.props["bessie"].enabled = not (fl.get("cabinet_open") or g.inv.has("shotgun"))
        w.props["monitor_screen"].texture = tex("monitor_inbox" if fl.get("emails_read") else "monitor")
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
        for key in ("cowshed", "barn", "loft", "porch", "processing", "plant"):
            w.set_lamp(key, False)
        w.set_lamp("shed", True)
        for k in g.knockables:
            k["down"] = False
            k["t"] = 0.0
            k["ent"].rotation = (0, 0, 0)
            k["ent"].y = 0
        for h in g.herd:
            h.state = "graze"
            h.path = []
            h.free = False
            h.area = PASTURE
            h.model.enabled = True
            h.col.enabled = True
        self.scatter_herd()
        self.register_doors()
        self.register_globals()
        self.register_extras()
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
        w.colliders["tractor"] = g.phys.add_box_c(cx, cz, 4.4 if horiz else 2.4, 2.4 if horiz else 4.4, 0,
                                                  TRACTOR_TOP, tag="climb")
        # its top (the hood and the big wheels): out of a hop's reach from the ground, but you can land on it
        fl = w.tractor_floor
        hw, hd = (2.2, 1.2) if horiz else (1.2, 2.2)
        fl.x0, fl.x1, fl.z0, fl.z1 = cx - hw, cx + hw, cz - hd, cz + hd
        fl.enabled = True

    def on_tractor(self):
        """Standing on top of the parked tractor (dropped onto it from the hayloft, most likely)."""
        p = self.g.player
        fl = self.g.world.tractor_floor
        return (fl.enabled and fl.x0 <= p.x <= fl.x1 and fl.z0 <= p.z <= fl.z1 and abs(p.y - TRACTOR_TOP) < 0.12
                and p.y_vel == 0 and self.g.vehicle is None)

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
        w.house_glass.set_shader_input("u_emissive", 0.6 if on else 0.0)
        w.house_glass.color = (1, 0.85, 0.55, 0.32) if on else (0.78, 0.9, 1.0, 0.16)

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
        d.player_opened = opening
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
                    gg.inv.remove("house_key")
                    gg.audio.play("blip_hi", vol=0.5)
                    self._toggle_door("front_door", 4)
                    gg.examine("The spare key turns. You leave it in the lock, like Chuck does, like an idiot.")
                elif self.day >= 5:
                    gg.examine("Locked. There's always a spare key somewhere. Try the doormat.")
                else:
                    # before Friday the house is off limits: don't send anyone hunting for a key that isn't there yet
                    gg.examine("Locked. Chuck's in and out of there all day. The house can wait until he's gone.")
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
             lambda gg: gg.examine("It hums. Everything on the farm runs off it. The fuse box on the wall beside it "
                                   "has three fuses and a note from Chuck. Not yet. Sunday."),
             cond=lambda gg: gg.day < 7, scope="day")

    def register_globals(self):
        """Wardrobe hiding and the radio: useful whenever you're around them."""
        g = self.g
        # Before Friday the gnome is only a gnome (Chuck moves the spare key into him on Friday). Say so,
        # instead of a headbutt doing nothing at all.
        gn = g.ia.get("gnome")
        if self.day < 5:
            g.on("gnome", "Look at the gnome", lambda gg: gg.examine(
                "A garden gnome with a fishing rod. Something small rattles inside him. Chuck's about today, "
                "though. The house can wait until he's out."), scope="day")
            gn.on_headbutt = lambda gg: gg.examine(
                "Clonk. The gnome wobbles and something rattles inside him. Not today: Chuck's around. "
                "Come back when he's out of the house.")
        else:
            gn.on_headbutt = None

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

    # ------------------------------------------------------------------
    # things to find off the main path: the deer stand, the plant, a patch of clovers
    # ------------------------------------------------------------------
    def register_extras(self):
        self._fuse_cables()
        self._deer_stand()
        self._plant()
        self._clover_patch()
        self._loft_rail()
        for pb in self.g.world.pushables.values():
            pb.reset()

    def _loft_rail(self):
        """The stretch of hayloft railing over the tractor: twine and optimism. Two headbutts (or one at a
        gallop) and it goes, loudly."""
        g = self.g
        w = g.world
        ia = g.ia.get("loft_rail")
        broken = bool(self.flags.get("rail_broken"))
        w.loft_rail.enabled = not broken
        w.loft_rail.position = (22, L, 4.1)
        w.loft_rail.rotation = (0, 0, 0)
        w.colliders["loft_rail"].enabled = not broken
        ia.enabled = not broken
        hits = {"n": 0}

        def wobble():
            for k in range(14):
                w.loft_rail.rotation_x = math.sin(k * 1.4) * 7 * (1 - k / 14)
                yield None
            w.loft_rail.rotation_x = 0

        def butt(gg):
            if self.flags.get("rail_broken"):
                return
            hits["n"] += 2 if getattr(gg, "last_charge", False) else 1
            if hits["n"] < 2:
                gg.audio.play("wood_crack", vol=0.7, pos=(22, L + 0.8, 4.1), rng=40)
                gg.noise((22, L, 4.1), 10.0, "crash")
                gg.runner.start(wobble(), name="rail_wobble", tag="day")
                gg.ui.popup_sub("CRACK. The twine creaks. It wouldn't take much more.", 3)
                return
            self.flags["rail_broken"] = True
            w.colliders["loft_rail"].enabled = False
            ia.enabled = False
            gg.audio.play("crash", vol=1.0, pos=(22, L, 4.1), rng=70)
            gg.audio.play("wood_crack", vol=1.0, pos=(22, L, 4.1), rng=50)
            gg.noise((22, L, 4.1), 22.0, "crash")
            gg.runner.start(self._rail_falls(), name="rail_fall", tag="day")
            gg.ui.popup_sub("The whole stretch of railing goes over the edge and lands on the barn floor. The "
                            "tractor is right there, two metres down.", 4)
        ia.on_headbutt = butt

    def _rail_falls(self):
        w = self.g.world
        t = 0.0
        while t < 0.7:
            t += min(0.05, time.dt)
            k = min(1.0, t / 0.7)
            w.loft_rail.position = (22, L - (L - 0.05) * k * k, 4.1 + 0.9 * k)
            w.loft_rail.rotation_x = 90 * k
            yield None
        self.g.audio.play("thump", vol=1.0, pos=(22, 0.3, 5), rng=40)

    def _slide_off_tractor(self):
        g = self.g
        p = g.player
        fl = g.world.tractor_floor
        p.teleport(fl.x0 - 0.75, 0, min(fl.z1, max(fl.z0, p.z)), p.yaw)
        g.audio.play("thump", vol=0.8)
        p.shake = 0.3
        g.ui.popup_sub("You land on the tractor, skid off the hood, and meet the floor. Undignified. Educational, "
                       "though.", 4)

    FUSE_X = (-9.15, -8.7, -8.25)       # the three fuses, left to right: labelled FENCE, HOUSE, SHED LIGHT

    def _fuse_cables(self):
        """The fuse box's wiring. Two cables go into the wall together; the one from the real shed-light fuse
        climbs the wall and runs across the ceiling to the lamp. That, and 'every label is wrong', is enough to
        work out the fence fuse without pulling anything."""
        labels = ("fence", "house", "shed")
        fmap = self.flags.get("fuse_map")
        if not fmap or any(a == b for a, b in zip(fmap, labels)):
            # the two wirings where no label is right
            fmap = self.flags["fuse_map"] = random.choice([["house", "shed", "fence"], ["shed", "fence", "house"]])
        assert not any(a == b for a, b in zip(fmap, labels))
        zw = SHED[2] + 0.17
        top = 1.83
        mb = MeshBuilder()
        cab = (0.08, 0.08, 0.08, 1)
        ceil = 2.88
        for i, fx in enumerate(self.FUSE_X):
            if fmap[i] == "shed":
                # up the wall, along the ceiling to above the lamp, then down its cord
                mb.box((fx, (top + ceil) / 2, zw), (0.035, ceil - top, 0.035), color=cab)
                mb.box((fx, ceil, (zw + -22.0) / 2), (0.035, 0.035, abs(-22.0 - zw)), color=cab)
                mb.box(((fx + -8.0) / 2, ceil, -22.0), (abs(-8.0 - fx) + 0.035, 0.035, 0.035), color=cab)
                for k in range(4):
                    # cable clips along the ceiling run, so it reads as a cable and not a crack
                    cz = zw + (-22.0 - zw) * (k + 0.5) / 4
                    mb.box((fx, ceil - 0.02, cz), (0.07, 0.03, 0.05), color=(0.85, 0.85, 0.82, 1))
            else:
                # a short way up, then sideways into the conduit that takes them both into the wall (at the
                # far end from the generator, so nothing looks wired to the fence)
                mb.box((fx, top + 0.12, zw), (0.035, 0.24, 0.035), color=cab)
                mb.box(((fx + -7.55) / 2, top + 0.24, zw), (abs(-7.55 - fx) + 0.035, 0.035, 0.035), color=cab)
        mb.box((-7.55, top + 0.24, zw - 0.02), (0.1, 0.1, 0.08), color=(0.45, 0.47, 0.48, 1))
        self.prop("fuse_cables", Entity(model=mb.build(), texture=tex("white"), shader=FARM_SHADER))

    TIN_Z = (-0.55, -0.72, -0.84)

    def _deer_stand(self):
        """An ammo tin on Chuck's deer stand. The sign says not to shake it."""
        g = self.g
        w = g.world
        x, z = DEER_STAND
        tin = w.ammo_tin
        tin_ia = g.ia.get("ammo_tin")
        w.deer_stand.rotation = (0, 0, 0)
        if self.flags.get("shells_found"):
            tin.enabled = False
            tin_ia.enabled = False
            if not self.flags.get("shells_taken"):
                self._tin_pickup()
        else:
            st = min(2, self.flags.get("tin_stage", 0))
            tin.enabled = True
            tin_ia.enabled = True
            tin.position = (-0.3, 3.62, self.TIN_Z[st])
            tin.rotation_x = 14 if st >= 2 else 0

        def sway():
            for k in range(28):
                a = 1 - k / 28
                w.deer_stand.rotation_z = math.sin(k * 0.9) * 2.8 * a
                w.deer_stand.rotation_x = math.cos(k * 0.7) * 1.3 * a
                yield None
            w.deer_stand.rotation = (0, 0, 0)

        def shake(gg):
            gg.audio.play("wood_crack", vol=0.8, pitch=0.7, pos=(x, 2, z), rng=40)
            gg.noise((x, 0, z), 12, "crash")
            gg.runner.start(sway(), name="deer_sway", tag="day")
            if self.flags.get("shells_found"):
                gg.examine("The stand creaks and sways. There's nothing left up there to fall.")
                return
            n = self.flags.get("tin_stage", 0) + (2 if getattr(gg, "last_charge", False) else 1)
            self.flags["tin_stage"] = n
            if n < 3:
                tin.position = (-0.3, 3.62, self.TIN_Z[n])
                tin.rotation_x = 14 if n >= 2 else 0
                gg.ui.popup_sub("The whole stand groans. Up top, something metal slides toward the edge." if n == 1
                                else "It's teetering right on the edge now.", 3)
                return
            gg.runner.start(self._tin_falls(), name="tin_fall", tag="day")
        g.ia.get("deer_stand").on_headbutt = shake
        tin_ia.on_rock = lambda gg, pt: gg.examine(
            "Tink. Whatever's in that tin is too heavy for a rock to shift. The whole stand would have to move.")

    def _tin_falls(self):
        g = self.g
        w = g.world
        x, z = DEER_STAND
        self.flags["shells_found"] = True
        w.ammo_tin.enabled = False
        g.ia.get("ammo_tin").enabled = False
        e = models.item_model("ammo_tin", position=(x - 0.3, 3.62, z + self.TIN_Z[2]))
        self.fx.append(_Temp(e))
        t = 0.0
        while t < 0.55:
            t += min(0.05, time.dt)
            k = min(1.0, t / 0.55)
            e.position = (x - 0.3, 3.62 - 3.5 * k * k, z + self.TIN_Z[2] - 0.8 * k)
            e.rotation_x = 300 * k
            yield None
        destroy(e)
        g.audio.play("metal_clang", vol=0.8, pos=(x, 0.3, z - 1.4), rng=30)
        g.ui.popup_sub("The tin slides off the edge and lands in the grass with a clang.", 3)
        self._tin_pickup()

    def _tin_pickup(self):
        x, z = DEER_STAND

        def take(gg):
            self.remove_item("ammo_tin")
            self.flags["shells_taken"] = True
            gg.inv.add("shells", 2)
            gg.event("deer")
            gg.examine("Two shotgun shells, and a note in Chuck's capitals: 'HID THESE FROM MYSELF. DON'T TELL ME "
                       "WHERE.'")
        self.item("ammo_tin", "ammo_tin", (x - 0.3, 0.12, z - 1.4), "Ammo tin", "Pry open the ammo tin", take,
                  rot=25, radius=0.35)

    def _plant(self):
        """Happy Acres has a staff door round the back. It has a keypad, and the keypad has a note."""
        g = self.g
        w = g.world
        door = w.doors["plant_back"]
        w.keypad_light.color = (0.2, 0.85, 0.3, 1) if self.flags.get("plant_unlocked") else (0.9, 0.15, 0.1, 1)

        def keypad(gg):
            if self.flags.get("plant_unlocked"):
                gg.examine("The light on the keypad is green. It's been green since you got the code right.")
                return
            r = yield from self.combo(4, "Keypad")
            if r == "2009":
                self.flags["plant_unlocked"] = True
                w.keypad_light.color = (0.2, 0.85, 0.3, 1)
                gg.audio.play("blip_hi", vol=0.6)
                open_door(gg)
            elif r == "1998":
                gg.audio.play("blip_lo", vol=0.6)
                gg.examine("BZZT. Red light. 1998 is the bowling trophy. Close, then: that's the second-best day of "
                           "his life.")
            elif r:
                gg.audio.play("blip_lo", vol=0.6)
                gg.examine("BZZT. Red light. The best day of Chuck's life was some other year.")

        def open_door(gg):
            was = door.is_open
            self._toggle_door("plant_back", 4)
            if not was and not w.lamps["plant"]["on"]:
                w.set_lamp("plant", True)
                gg.audio.play("blip_hi", vol=0.3, pitch=0.6)
                gg.ui.popup_sub("The lights flicker on. Motion sensor. Somebody wanted to see every corner of this "
                                "room.", 4)

        def try_door(gg):
            if self.flags.get("plant_unlocked") or door.is_open:
                open_door(gg)
            else:
                gg.examine("Locked. There's a keypad beside it, and a sticky note under the keypad.")
        g.on("plant_keypad", "Punch in a code", keypad, scope="day")
        g.on("plant_back", lambda gg: "Close the door" if door.is_open else
             ("Open the door" if self.flags.get("plant_unlocked") else "Try the door"), try_door, scope="day")

        def ledger(gg):
            yield from gg.show_document("HAPPY ACRES PROCESSING - INTAKE", LEDGER, style="ledger")
            if not self.flags.get("ledger_read"):
                self.flags["ledger_read"] = True
                gg.event("ledger")
                yield from gg.talk([
                    ("you", "Moo. (Every line is one of us. A number, a weight and a grade. There's no column for "
                            "a name.)"),
                    ("you", "Moo. (Two a month, every month. I knew that. I've always known that. I'd just never "
                            "seen it written down in a straight line, adding up.)"),
                ])
        g.on("ledger", "Read the ledger", ledger, scope="day")

    CLOVERS = [(77.4, -47.2), (78.3, -46.4), (77.6, -45.3), (78.9, -44.6), (78.1, -43.5)]

    def _clover_patch(self):
        """Five Golden Clovers in the strip of grass behind the plant, where nobody's looked. Found once, ever."""
        g = self.g
        for i, (cx, cz) in enumerate(self.CLOVERS):
            cid = f"plant_{i}"
            if g.moodals.clover_found(cid):
                continue

            def take(gg, i=i, cid=cid):
                self.remove_item(f"clover{i}")
                if gg.moodals.find_clover(cid):
                    gg.audio.play("clover", vol=0.7)
                    gg.ui.toast("Found a Golden Clover", "clover")
                    gg.refresh_hotbar()
                    left = sum(1 for j in range(len(self.CLOVERS)) if not gg.moodals.clover_found(f"plant_{j}"))
                    if left == 0:
                        gg.examine("Five Golden Clovers, growing in the one patch of grass nobody on this farm has "
                                   "ever wanted to stand in. Epicowrus did say they grow where nobody's looked.")
            self.item(f"clover{i}", "clover", (cx, 0.25, cz), "Golden Clover", "Pick the Golden Clover", take,
                      spin=True, bob=True, glow=0.5, radius=0.3)

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

    def score_use(self):
        """Q with Archimoodes' plan: read it out. The herd starts arguing about whether to bother, loudly, and
        Chuck stomps over to the pasture gate to shut them up: a distraction you can use from anywhere."""
        g = self.g
        if g.env.time < self._hum_ready:
            g.examine("The herd is still arguing about the last reading. Moogenes has started a splinter faction. "
                      "Give it a minute.")
            return True
        self._hum_ready = g.env.time + 45.0
        g.audio.play("moo_player_medium_0", vol=0.8, group="voice")
        g.examine("You moo the first line of Archimoodes' plan, loud enough to carry. 'One: the fence...'")
        g.runner.start(self._herd_hum(), name="herd_hum", tag="day")
        return True

    def _herd_hum(self):
        g = self.g
        yield 2.4
        gx, gz = GATE_PASTURE[0] - 12.0, (GATE_PASTURE[1] + GATE_PASTURE[2]) / 2
        g.audio.play("moo_herd_argue", vol=1.0, pos=(gx, 1.2, gz), rng=150, group="voice")
        for h in g.herd:
            h.model.talk_t = 6.0
        g.ui.popup_sub(random.choice([
            "The whole herd starts arguing about whether to bother. Echo agrees with whoever spoke last, loudly, "
            "every time.",
            "Fifty cows debate whether 'the road' goes anywhere. It gets personal.",
            "The herd splits into the ones who'd go and the ones who say it's weather. Heifercleitus heckles both.",
        ]), 6)
        yield 1.5
        g.noise((GATE_PASTURE[0] + 1.5, 0, gz), 80, "herd_hum")

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
        if "rafter_key" in self.props:
            self._rafter_grab()
        if self.cur != "d7_tractor" and self.on_tractor():
            self._slide_off_tractor()

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
            ("go", (-15.2, 0, -50), 1.8), ("wait", 9, "work", FENCE_LINES, (-18, -50)),
            ("go", (-15.2, 0, -21), 1.8), ("wait", 9, "work", FENCE_LINES, (-18, -21)),
            ("go", (-15.2, 0, -8), 1.8), ("wait", 8, "work", FENCE_LINES, (-18, -8)),
            ("go", (0, 0, -10), 2.0), ("wait", 4, "look"),
            ("go", (-2, 0, -22), 2.0), ("wait", 3, "look"),
            ("go", (-15.2, 0, -36), 1.8), ("wait", 6, "look"),
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
                             hint="Tell the others. Archimoodes is by the pond, Moogenes at the salt lick, Moothagoras under the "
                                  "oak, Epicowrus in the hay bales in the far corner, Heifercleitus by the trough.")
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
            ("cowleen", "Moodysseus. Wake up. Chuck dropped his planner at the fence last night, and the wind put a page "
                        "up the Old Oak."),
            ("you", "Moo. (And?)"),
            ("cowleen", "And there's a Sunday on it, with a number next to it. Go and see whose. You've the better neck "
                        "for it."),
            ("you", "Moo. (Does it matter whose?)"),
            ("cowleen", "Not much. But nobody's ever seen the page before the truck came. I'd like to know if knowing "
                        "feels any different."),
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
        yield from g.talk([("cowleen", "The pond. Heifercleitus says you can't step in the same river twice. She's "
                                       "never said anything about fishing a page out of a pond, so it's allowed.")])

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
            ("you", "Moo. (Forty-seven. Sunday. That's me.)"),
            ("cowleen", "So it is. 'SUN: number forty-seven, barbecue with Dale. Do it myself, save money.' He isn't "
                        "sending you to the plant. He's doing you himself, for Dale."),
            ("cowleen", "And twelve goes on Thursday's truck, like every other Thursday. Whoever twelve is. We'll find "
                        "out on Thursday. We always do."),
        ])
        self.flags["on_list"] = True
        yield from g.talk([
            ("cowleen", "...Well. Sunday, then, Forty-Seven."),
            ("you", "Moo. (Forty-Seven? You've called me Moodysseus since I was a calf.)"),
            ("cowleen", "Once a cow's on the list, we stop using her name. Everybody does. It makes Thursdays easier."),
            ("you", "Moo. (Easier for who?)"),
            ("cowleen", "For whoever's left. Isn't that obvious?"),
            ("you", "Moo. (I'm not going.)"),
            ("cowleen", "Everybody says that on Monday. You eat the grass, the grass grows back, somebody eats you. It's a "
                        "circle. By Sunday it'll feel like one."),
            ("you", "Moo. (Somebody eating you isn't part of the circle. It's where the circle stops.)"),
            ("cowleen", "Hm. Go and tell the others, then, and see what they say. Then the oak at sundown: Archimoodes "
                        "will want to argue about it. He always argues."),
            ("cowleen", "Archimoodes is by the pond. Moogenes is at the salt lick, Moothagoras under the oak, Epicowrus "
                        "in his hay bales in the far corner, Heifercleitus at the trough."),
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
            yield from g.talk([
                ("moozart", "Don't step on my circles."),
                ("you", "Moo. (Sorry. What are they?)"),
                ("moozart", "An argument with a circle. I'm trying to pin down how far round it is, against how far across. "
                            "A bit more than three. I've trapped it between two fractions and I'm squeezing."),
                ("you", "Moo. (Chuck's planner. Sunday's me. Twelve goes on the truck on Thursday.)"),
                ("moozart", "...Sunday. Right."),
                ("moozart", "And the others told you it's just how things are, so you came to the one cow who'd disagree. "
                            "Good. It isn't how things are. It's how Chuck arranged them, which is a different thing, and "
                            "much easier to fix."),
                ("you", "Moo. (Fix how?)"),
                ("moozart", "Give me a place to stand and I'll move the world. I don't need the world. I need a gate. "
                            "Sundown, at the oak: I'll show everyone."),
                ("you", "Moo. (And twelve? Do you know who twelve is?)"),
                ("moozart", "Twelve. Divisible by one, two, three, four and six. A very obliging number. Go on, Moodysseus. "
                            "Sundown."),
            ])

        def sirloin_lines():
            yield from g.talk([
                ("sirloin", "You're in my sunlight."),
                ("you", "Moo. (It's seven in the morning.)"),
                ("sirloin", "It's the principle. A king once stood where you're standing and asked what I wanted. I told him "
                            "to move. He moved."),
                ("you", "Moo. (That was a different philosopher.)"),
                ("sirloin", "Prove it. What do you want?"),
                ("you", "Moo. (Chuck's going to eat me on Sunday.)"),
                ("sirloin", "And? When I go, I've left instructions: throw me over the fence for the crows. Saves Chuck a "
                            "job and feeds a crow. Dying's only a problem if you're precious about where you end up."),
                ("you", "Moo. (I'm precious about where I end up.)"),
                ("sirloin", "Then you're a cow and I'm a dog. I eat in public, I sleep where I drop, and I bark at the "
                            "powerful. Even a dog wants a kennel, mind. Find me something to live in: a jar, a barrel, a "
                            "bucket. A home nobody can sell me."),
            ])

        def cowpernicus_lines():
            yield from g.talk([
                ("cowpernicus", "Shh. I'm counting. Fence posts: two hundred and six. Cows: fifty. Farmers: one."),
                ("you", "Moo. (Chuck's planner. I'm on it. Sunday.)"),
                ("cowpernicus", "Forty-seven. Prime. You can't be divided by anything but one and yourself. They'll divide you "
                                "anyway: chuck, brisket, rib, round."),
                ("cowpernicus", "Don't look like that. Souls go round, Forty-Seven. You'll be back: a cow again, or a hen, or "
                                "a fly. Possibly Dale. You don't get to pick, so I don't worry about it."),
                ("you", "Moo. (Then why won't you eat beans? You told me beans have souls.)"),
                ("cowpernicus", "Because I don't want to eat my grandmother. Being eaten was her problem. Eating is mine."),
                ("cowpernicus", "Archimoodes has a meeting at the oak? He'll have diagrams. I'll come for the diagrams. And: "
                                "Chuck owns spare reading glasses. Every triangle I've drawn for four years has been a guess. "
                                "Find them and I'll draw you the whole farm."),
            ])

        def mooriarty_lines():
            yield from g.talk([
                ("mooriarty", "Psst. In here. Welcome to the Garden."),
                ("you", "Moo. (It's a pile of hay bales.)"),
                ("mooriarty", "It's a philosophy. Friends, simple food, no fear. Also a shop."),
                ("you", "Moo. (Chuck's going to eat me on Sunday.)"),
                ("mooriarty", "Then have the best thing I sell, free: death is nothing to us. Where death is, you aren't, "
                              "and where you are, it isn't. You never actually meet it. Nobody does."),
                ("you", "Moo. (I'd still rather not be a burger.)"),
                ("mooriarty", "Nobody said anything about rather. Still, if you're going to spend the week fighting it, "
                              "you'll want equipment. Rocks, rubber, a disguise. Golden Clovers only. They come to cows who do "
                              "things worth talking about, and a few grow where nobody's thought to look."),
            ])
            self.setf("mooriarty_met")

        def moomaw_lines():
            yield from g.talk([
                ("moomaw", "Morning, dear. You can't step into the same pasture twice. It's always a slightly different "
                           "pasture, and you're always a slightly older cow."),
                ("you", "Moo. (He wrote my number next to Sunday. And 'barbecue'.)"),
                ("moomaw", "Oh, sweetheart. Everything flows. Grass into cow, cow into Chuck. I've watched that river eleven "
                           "years, and it only ever runs one way."),
                ("moomaw", "He did it to my Ajax. Circled him on the calendar with a little smiley face. Chuck called him Big "
                           "Ajax, after the floor cleaner. There was a hero called Ajax first. Chuck has never once wondered "
                           "what anything was called before he named it."),
                ("you", "Moo. (Did nobody try to stop it?)"),
                ("moomaw", "You don't stop a river, dear. You stand in it and get wet. He keeps Ajax's photo in his office. "
                           "I'd like it back. Small things can go upstream, now and then."),
            ])
        self.hook("talk:moozart", teller("moozart", moozart_lines))
        self.hook("talk:sirloin", teller("sirloin", sirloin_lines,
                                         lambda: g.side_quest("helm", "Find Moogenes something to live in",
                                                              "active")))
        self.hook("talk:cowpernicus", teller("cowpernicus", cowpernicus_lines,
                                             lambda: g.side_quest("specs", "Find Moothagoras some glasses", "active")))
        self.hook("talk:mooriarty", teller("mooriarty", mooriarty_lines))
        self.hook("talk:moomaw", teller("moomaw", moomaw_lines,
                                        lambda: g.side_quest("photo", "Bring Heifercleitus the photo of Big Ajax", "active")))
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
            ("moozart", "Thank you for coming. I know none of you think this matters."),
            ("mooriarty", "Death is nothing to us. A meeting, though. I'll always come to a meeting."),
            ("moozart", "Moodysseus is on the page for Sunday. Somebody's on it for Thursday. Every fortnight, somebody. "
                        "I'd like to stop it."),
            ("cowleen", "And I'd like to know why we should. We've eaten Chuck's grass all our lives. Slept in his shed, "
                        "drunk his water. You can't take the grass for years and then refuse the truck."),
            ("moozart", "He didn't give us the grass, Moocrates. He invested it. A loan you pay back with your own body "
                        "isn't hospitality. It's a mortgage."),
            ("cowleen", "...I'll need to think about that."),
            ("moomaw", "It'll still be Thursday when you've thought about it, dear."),
            ("sirloin", "I'm in. Not to escape. I'd just like to see Chuck's face."),
            ("cowpernicus", "It's a nice problem. I'll do the numbers. It won't change anything, but nice problems are "
                            "rare."),
            ("moozart", "That'll do. The fence runs off the generator in the tool shed: no current, no fence. The main "
                        "gate's chained, with a cattle grid in front. We can't undo the chain. So we don't open the "
                        "gate. We knock it down."),
            ("cowpernicus", "With what? A cow weighs six hundred kilos and is very sorry about it."),
            ("moozart", "Give me a lever long enough and a place to stand, and I'll move the world. The lever's in the "
                        "barn. It weighs four tons, and Chuck calls it 'baby'."),
            ("sirloin", "He means the tractor."),
            ("moozart", "I mean the tractor. Somebody drives it through the gate, and everybody walks out behind it."),
            ("moomaw", "Ajax's plan was 'headbutt the truck'. One step. Very elegant."),
            ("cowleen", "How did that go?"),
            ("moomaw", "He's in Chuck's freezer, dear. What's left of him. He's been at three barbecues."),
            ("moozart", "Which is why this plan has more than one step. The first is tonight. Here comes Chuck for the "
                        "headcount. Moodysseus: get behind him and take his pencil. A man who can't write things down "
                        "has to remember them, and Chuck can't."),
            ("cowpernicus", "His eyes cover about a hundred degrees in front of him. Behind him there's nothing at all. "
                            "Sneak in it: C or Ctrl."),
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
        f.hearing = HEARING * 0.6
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
            ("chuck", "Aw, heck. Lost count. Again. Every night I lose count. It's like they MOVE."),
            ("chuck", "...Forty-nine. Close enough. Nobody ever audits a cow."),
        ])
        f.set_tool(None)
        self.chuck_routine([
            ("go", (-21, 0, -35), 2.2), ("call", lambda: g.world.doors["pasture_gate"].set_open(True)),
            ("go", (-14, 0, -35.5), 2.2), ("call", lambda: g.world.doors["pasture_gate"].set_open(False)),
            ("go", (40, 0, 18), 2.4), ("go", (56, 0, 23), 2.4), ("hide",), ("stop", "idle"),
        ])
        f.hearing = HEARING
        g.set_time("dusk", 12)
        g.ambience("night")
        self.base_music = "music_night"
        yield from g.talk([
            ("moozart", "Forty-nine, and he'll write down fifty. Nobody checks Chuck's arithmetic, Chuck least of all. "
                        "Remember that."),
            ("moozart", "Sleep, Moodysseus. Tomorrow, the shed."),
        ])

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
            ia = self.item("radio", "radio", RADIO_SPOT, "Chuck's radio", "Take the radio", radio, rot=200,
                           cond=lambda gg: gg.player.y > 0.5)
            ia.handlers.append(Handler("Look at the radio", lambda gg: gg.examine(
                "Chuck's radio, on top of the cabinet. From down here you can admire it. From something a bit "
                "taller, you could have it."), lambda gg: gg.player.y <= 0.5, "global"))

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
            # a stroll round the yard before the next feed run
            ("go", (-2, 0, -22), 2.2), ("wait", 4, "look"),
            ("go", (14, 0, -14), 2.2), ("wait", 3, "look"),
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
        # Moocrates' fainting routine: once Chuck is inside the pasture
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
            f.say("Moocrates? You okay, girl? Say somethin'!", force=True)
            fa["said"] = False
        if fa.get("active"):
            fa["t"] -= dt
            if not f.path:
                f.face_target = (c.x, c.z)
                f.pose = "look"
                if not fa["said"]:
                    fa["said"] = True
                    f.say("Don't you die on me! Not like this! Not UNREFRIGERATED!", force=True)
            if fa["t"] <= 0:
                fa["active"] = False
                c.model.lying_target = 0.0
                c.bubble("Moo.")
                f.say("Huh. Faintin' cow. Is that a breed? Could I charge more?", force=True)
                f.resume_routine()

    def day2(self):
        yield from self.step("d2_wake", self.d2_wake)
        yield from self.step("d2_out", self.d2_out, hint=(
            "What does Chuck do with the gate when both his hands are full?",
            "When Chuck carries the feed to the trough he leaves the gate open behind him. Slip out while his back "
            "is turned, or ask me to faint and he'll only have eyes for me."))
        yield from self.step("d2_board", self.d2_board, hint=(
            "A padlock locks a door. How many walls does a shed have? And what on this farm is louder than you?",
            "One of the boards on the back of the shed, facing the pasture, is loose. Headbutt it three times, "
            "but only while Chuck is revving the tractor: the engine covers the noise."))
        yield from self.step("d2_shed", self.d2_shed, hint=(
            "Who chose the combination: and is a man's perfect score the same as a perfect score? And what could "
            "a cow stand on?",
            "The note says Chuck's PERFECT bowling score. Not a perfect game: his. His trophy is on the shelf. "
            "The radio's on the tall cabinet: headbutt the crate over to it, then hop up (Space)."))
        yield from self.step("d2_return", self.d2_return, hint=(
            "Which side of the pasture gate is the bolt on?",
            "The bolt is on the outside, where you are. Open the gate and walk in."))
        yield from self.step("d2_radio", self.d2_radio, hint=(
            "Archimoodes asked for the radio, and then for an aerial: something long and metal. What on this farm "
            "is long and metal, and has been humming at you all your life?",
            "The electric fence. Set the radio down right up against it (Q) and the static clears. Archimoodes "
            "will come over to listen."))
        yield from self.step("d2_ram", self.d2_ram, hint="Moothagoras has been staring at the tractor all day. "
                                                         "Ask him why.")
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
            ("cowleen", "Morning, Forty-Seven. Archimoodes wants you in the tool shed today. I said I'd help."),
            ("you", "Moo. (I thought you didn't think it mattered.)"),
            ("cowleen", "I don't know whether it matters. That's not the same thing. Nobody's ever tried, so I'd like to "
                        "see what happens when somebody does."),
            ("cowleen", "Chuck does the feed run, walks to the trough, and leaves the gate open behind him. Every single "
                        "time. I've watched him do it for four years and never once thought it was for me."),
            ("cowleen", "If you need cover, ask me and I'll collapse. A sick cow is the one thing Chuck walks toward. The "
                        "shed's past the east fence, padlocked. Epicowrus says a padlock only locks a door, and a shed has "
                        "four walls. I think that's a hint."),
            ("cowleen", "And Archimoodes wants Chuck's radio, if it's in there. Don't ask me why. He'll tell you anyway."),
        ])
        g.cutscene_end_now()

    def d2_out(self):
        g = self.g
        self.objectives(("out", "Get out of the pasture"))
        self.mark((-8, -22, "Tool shed"))

        def cowleen_talk():
            if self.faint.get("asked"):
                yield from g.talk([("cowleen", "Ready. When he comes through the gate, I go down. They say philosophy "
                                               "is practice for dying. Finally, a practical application.")])
                return True
            r = yield from g.say("cowleen", "Need me to faint?", choices=["Yes. Faint when Chuck comes in.",
                                                                         "Not yet."])
            if r == 0:
                self.faint["asked"] = True
                if g.world.doors["pasture_gate"].is_open:
                    self.faint["armed"] = True
                yield from g.talk([("cowleen", "Watch. I've been rehearsing. Turns out I have range.")])
            else:
                g.end_talk()
            return True
        self.hook("talk:cowleen", cowleen_talk)
        p = g.player
        yield lambda: not g.phys.in_zone("pasture", p.x, p.z) and p.x > -17.5
        g.complete("out")

    def d2_board(self):
        g = self.g
        self.objectives(("board", "Get into the tool shed"))
        self.mark((-8, -22, "Tool shed"))
        hits = {"n": self.flags.get("board_hits", 0)}
        ia = g.ia.get("shed_board")

        def butt(gg):
            pos = (SHED[0], 0.0, -22.2)
            if gg.noise_masked(pos):
                hits["n"] += 1
                self.flags["board_hits"] = hits["n"]
                gg.audio.play("wood_crack", vol=0.5, pos=pos, rng=20)
                if hits["n"] < 3:
                    gg.ui.popup_sub("CRACK. The engine swallowed it." if hits["n"] == 1 else
                                    "CRACK. It's nearly through.", 3)
            else:
                gg.audio.play("wood_crack", vol=1.0, pos=pos, rng=60)
                gg.noise(pos, 24, "crash")
                gg.ui.popup_sub("WHAM. The board gives a little, and the whole farm heard it. Something louder "
                                "would cover that.", 4)
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
        self.objectives(("toolbox", "Open the toolbox"), ("radio", "Find Archimoodes a radio"))
        if g.inv.has("radio"):
            g.complete("radio", sound=False)
        opened = {"d": False}

        def toolbox(gg):
            r = yield from self.combo(3, "Toolbox")
            if r == "117":
                opened["d"] = True
                gg.audio.play("blip_hi", vol=0.6)
            elif r == "300":
                gg.examine("300 is a perfect game. Chuck has never bowled a perfect game. Chuck has bowled a game he "
                           "considers perfect. Those are different numbers.")
            elif r:
                gg.examine("The lock doesn't budge. Chuck wrote his combination down somewhere. Chuck writes "
                           "everything down somewhere.")
        g.on("toolbox", "Try the combination lock", toolbox)
        yield lambda: opened["d"]
        g.complete("toolbox")
        g.inv.add("pliers")
        yield from g.talk([
            ("you", "Moo. (Pliers.)"),
            ("you", "Moo. (Four years I've worn this bell. I thought it was jewellery. It's an inventory system.)"),
            ("you", "Moo. (Hold still. I'm removing myself from the inventory.)"),
        ])
        g.audio.play("metal_clang", vol=0.5, pitch=1.6)
        yield 0.4
        g.player.has_bell = False
        self.setf("bell_off")
        g.inv.add("cowbell", silent=True)
        g.ui.toast("Cowbell off. You're quiet now.", "cowbell")
        g.ui.popup_sub("No more jingling. You can still throw the bell to make a noise somewhere else. [Q]", 6)
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
            g.ui.popup_sub("Moocrates noses the gate shut behind you.", 3)
        g.set_time("sunset", 12)
        self.chuck_routine([("go", (40, 0, 18), 2.4), ("go", (56, 0, 23), 2.4), ("hide",), ("stop", "idle")])
        self.revving = False
        g.audio.stop_loop("tractor", 0.5)

    @staticmethod
    def near_fence(x, z, reach=1.4):
        """Within reach of the pasture's electric fence (inside or out)."""
        x0, x1, z0, z1 = PASTURE
        d = min(abs(x - x0) if z0 - reach < z < z1 + reach else 99, abs(x - x1) if z0 - reach < z < z1 + reach else 99,
                abs(z - z0) if x0 - reach < x < x1 + reach else 99, abs(z - z1) if x0 - reach < x < x1 + reach else 99)
        return d < reach

    def d2_radio(self):
        """The radio gets nothing but static in the pasture: it wants an aerial. Two kilometres of electric fence
        will do. Set it down against the fence and the farm report comes through."""
        g = self.g
        mz = g.cows["moozart"]
        st = {"given": bool(self.flags.get("radio_static")), "tuned": False}

        def show():
            objs = [("radio_mz", "Give the radio to Archimoodes")]
            if st["given"]:
                objs.append(("aerial", "Get the radio some reception"))
            self.objectives(*objs)
            if st["given"]:
                g.complete("radio_mz", sound=False)
        show()
        self.mark((mz.x, mz.z, "Archimoodes"))

        def talk():
            if st["given"]:
                yield from g.talk([("moozart", "Still static? Something long and metal, Moodysseus. Something that's "
                                               "been humming at us our whole lives.")])
                return True
            if g.inv.has("radio"):
                yield from g.talk([("moozart", "The radio. Good. Let's hear the farm report. If we're going to outwit "
                                               "Chuck, I'd like to hear what he thinks about, and Chuck mostly thinks "
                                               "about money.")])
                g.audio.play("radio_static", vol=0.8, pos=(mz.x, 1, mz.z), rng=25)
                yield 1.8
                yield from g.talk([
                    ("moozart", "...Static. Of course. We're a long way from anything out here. A radio wants an "
                                "aerial: a long piece of metal, the longer the better."),
                    ("moozart", "Take it. Find it something long and metal to lean on, and call me when it's talking. "
                                "I'll come and listen."),
                ])
                st["given"] = True
                self.flags["radio_static"] = True
                g.complete("radio_mz")
                show()
                return True
            if not g.inv.has("radio"):
                yield from g.talk([("moozart", "No radio? Chuck had one on the tractor last summer. He doesn't throw things away. He "
                                        "puts them in the shed, on top of something tall, and forgets them.")])
                return True
            return True
        self.hook("talk:moozart", talk)

        def use(sel):
            if sel != "radio" or not st["given"] or st["tuned"]:
                return self.radio_use(sel)
            self.radio_use(sel)
            pos = self.radio_on["pos"]
            if self.near_fence(pos[0], pos[2]):
                st["tuned"] = True
            else:
                g.audio.stop_loop("radio", 0.05)
                g.audio.play("radio_static", vol=0.9, pos=pos, rng=25)
                g.examine("Kssshhh. Static. It wants something long and metal to lean on. Pick it up and try "
                          "somewhere else.")
            return True
        self.hook("use", use)
        yield lambda: st["tuned"]
        g.complete("aerial")
        pos = self.radio_on["pos"]
        g.audio.stop_loop("radio", 0.05)
        g.audio.loop("radio", "loop_radio", vol=0.9, pos=pos, rng=35, group="sfx")
        g.examine("The static clears. Two kilometres of electric fence make a very good aerial. A man with a "
                  "lovely voice is reading out cattle prices.")
        # Archimoodes comes over to listen
        ox, oz = (1.6 if pos[0] < -48 else -1.6), (1.6 if pos[2] < -35 else -1.6)
        mz.goto((pos[0] + ox, 0, pos[2] + oz), 3.0)
        t0 = g.env.time
        yield lambda: math.hypot(mz.x - pos[0], mz.z - pos[2]) < 3.2 or g.env.time - t0 > 15
        if math.hypot(mz.x - pos[0], mz.z - pos[2]) >= 3.2:
            mz.teleport((pos[0] + ox, 0, pos[2] + oz), 0)
        mz.path = []
        mz.face_target = (pos[0], pos[2])
        g.cutscene_start(letterbox=True)
        g.player.look_at_point((mz.x, 1.3, mz.z))
        g.audio.music_duck = 0.1
        yield 1.0
        yield from g.talk([
            ("moozart", "Live cattle, up four cents. Hides, steady. 'Lean trim', up. Lean trim is us, ground. Every part "
                        "of you has a price, and every part of you went up this morning."),
            ("moozart", "So that's what we are to him: a number that goes up while he feeds us, and gets paid out when "
                        "he stops. He isn't cruel. He's a man who can read a market report and not much else."),
        ])
        self._radio_pickup()
        self.unduck()
        yield from g.talk([
            ("you", "Moo. (How are you so calm about it?)"),
            ("moozart", "I'm not calm. I'm busy. You can't panic and draw a straight line at the same time. I've tried."),
            ("moozart", "Keep the radio. Chuck can't stand that station: it ran the ad for his divorce lawyer. Set it "
                        "down playing anywhere and he'll cross the whole farm to switch it off. A man who always walks "
                        "toward the same noise is a man you can steer."),
        ])
        g.cutscene_end_now()
        g.ui.popup_sub("The radio's yours. [Q] sets it down playing: Chuck comes to switch it off. Pick it up "
                       "again after.", 7)

    def d2_ram(self):
        g = self.g
        self.objectives(("ram", "Talk to Moothagoras"))
        cp = g.cows["cowpernicus"]
        self.mark((cp.x, cp.z, "Moothagoras"))
        done = {"d": False}

        def talk():
            yield from g.talk([
                ("cowpernicus", "Archimoodes has been grinning at that radio all afternoon. He only grins when something's "
                                "true and awful."),
                ("cowpernicus", "I've watched the tractor all day. Four tons. He calls it a lever. I call it four, the number "
                                "of justice: equal times equal. I'm not saying the universe is on our side. I'm saying it has a "
                                "sense of humour."),
                ("cowpernicus", "Chuck calls it 'baby'. He has never called a living thing 'baby'. He loves the machine and "
                                "prices the cow, and none of us ever thought that was odd."),
                ("cowpernicus", "Someone has to find out what it needs to run. Not me. I can't see past the fence. I can "
                                "barely see the fence. I've been apologising to a post for a week. It's a very forgiving post."),
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
            ("go", (20, 0, 23), 1.5), ("wait", 6, "look"),
            ("go", (30, 0, -20), 1.5), ("wait", 5, "look"),
            ("go", (22, 0, -7), 1.5), ("wait", 5, "ow", TOOTH_LINES),
            ("go", (-8, 0, -40), 1.5), ("wait", 6, "work", TOOTH_LINES, (-8, -41)),
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

    KEY_SPOT = (22.0, 5.95, 10.0)       # tied to a nail on the hayloft rafter

    def _rafter_key(self):
        g = self.g
        pos = self.KEY_SPOT
        key = models.item_model("tractor_key", position=pos, rotation=(90, 0, 0), scale=2.0)
        string = MeshBuilder().box((0, 0.12, 0), (0.015, 0.24, 0.015), color=(0.85, 0.8, 0.6, 1), uv_rect=models.WHITE)
        s = Entity(model=string.build(solid_rect=models.WHITE), texture=tex("atlas"), shader=FARM_SHADER, position=pos)
        for c in key.children:
            c.set_shader_input("u_emissive", 0.35)
        self.prop("rafter_key", key)
        self.prop("rafter_string", s)
        ia = g.ia.add(Interactable("st_rafter_key", pos, 0.35, "Tractor key", None, "Look at the key", 6.0))

        def look(gg):
            if gg.player.y > L + 0.5:
                gg.examine("Nearly. It's just above your nose. A hop would do it.")
            else:
                gg.examine("The tractor key, tied to a nail on the rafter with twine. Well out of reach. Cows don't "
                           "climb. Cows do stand on things, though.")
        ia.handlers.append(Handler("Look at the key", look, None, "global"))
        ia.on_rock = lambda gg, hit: gg.examine(
            "Tink. The rock bounces off. The key's tied to the nail. Somebody would have to get up there and bite "
            "through the twine.")

    def _rafter_grab(self):
        """A hop from on top of something, with your head up by the key: you bite it off the nail."""
        g = self.g
        p = g.player
        kx, ky, kz = self.KEY_SPOT
        if math.hypot(p.x - kx, p.z - kz) > 0.9 or abs(p.y + 1.45 - ky) > 0.35:
            return
        g.ia.remove("st_rafter_key")
        self.remove_prop("rafter_string")
        self.remove_prop("rafter_key")
        g.audio.play("metal_clang", vol=0.6, pos=(kx, ky, kz), rng=25)
        g.inv.add("tractor_key")
        self.setf("tractor_key_taken")
        g.complete("key")
        g.ui.popup_sub("SNAP. You bite through the twine at the top of the hop and come down with the key in your "
                       "teeth.", 4)

    def _jerrycan(self):
        def take(gg):
            if not gg.flags.get("cluck_beaten"):
                gg.examine("Cluckydides is watching you. You'd have to go through him first.")
                return
            self.remove_item("jerrycan")
            gg.inv.add("jerrycan")
            self.setf("jerrycan_taken")
            gg.complete("fuel_get")
        self.item("jerrycan", "jerrycan", (36.6, 0.2, -29.6), "Jerry can", "Take the jerry can", take, rot=90,
                  radius=0.4)

    def day3(self):
        yield from self.step("d3_lock", self.d3_lock)
        yield from self.step("d3_moohole", self.d3_moohole, hint=(
            "What did Moogenes' nose learn about that wire? And what on this farm doesn't carry current?",
            "Rubber doesn't conduct. Chuck lost a boot in the pond, or Epicowrus sells a rubber chicken. Wedge one "
            "under the sagging wire at the far end of the east fence."))
        yield from self.step("d3_barn", self.d3_barn, hint=(
            "Moothagoras wanted to know what the tractor needs. Who's going to look?",
            "The barn's side door, on the west wall, is never locked. Look the tractor over."))
        yield from self.step("d3_parts", self.d3_parts, hint=(
            "A nail nobody can reach, and a feather on the fuel cap. Cows can't climb, but they can stand on "
            "things, and they can hop. What could go under the key?",
            "The key's tied to the rafter over the hayloft. Headbutt the loft crate until it's under the key, hop up "
            "onto it, then hop again to bite the key off. The diesel's in the chicken run, guarded by "
            "Cluckydides; Chuck naps on the porch around midday."))
        yield from self.step("d3_trough", self.d3_trough, hint=(
            "Archimoodes is waiting at the trough. And what's he got that a trough could wash?",
            "Use the trough while Archimoodes is drinking: dunk his muddy ear tag."))
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
            ("chuck", "Somebody's been usin' this gate. Other than me. And it ain't the raccoons. Raccoons "
                      "close gates."),
            ("chuck", "Ow. Ow ow ow. Stupid tooth."),
        ])
        f.pose = "work"
        g.audio.play("chain", vol=0.9, pos=(-18, 1, -35), rng=40)
        yield 1.2
        self.setf("gate_locked")
        yield from g.talk([("chuck", "There. Padlock. Let's see you open THAT without thumbs, whoever you are.")])
        f.set_tool(None)
        self.chuck_wed_chores()
        c = g.cows["cowpernicus"]
        c.teleport((-24.5, 0, -30.5), 200)
        g.cows["cowleen"].teleport((-25, 0, -36.5), 20)
        g.cam_set((-30.5, 2.4, -29.5), (-25.5, 1.2, -33.5))
        yield from g.talk([
            ("cowpernicus", "He's adapting. That's worrying. I had him down as a constant."),
            ("cowpernicus", "The far end of the east fence sags at the bottom. Lift the wire and a cow fits under. "
                            "The trouble is lifting it. Moogenes tried with his nose once. It's why he's like that."),
            ("cowleen", "So the question is what can touch that wire and not care. What doesn't carry current?"),
            ("cowpernicus", "Don't do that. You know I can't resist a question."),
            ("cowleen", "I know. Unrelated: Chuck lost a boot in the pond last month. Hopped back to the house on "
                        "one leg, swearing at God. God didn't reply. I've never felt closer to God."),
        ])
        g.cutscene_end_now()

    def d3_moohole(self):
        g = self.g
        self.objectives(("hole", "Get under the east fence"))
        self.mark((MOOHOLE_POS[0], MOOHOLE_POS[1], "Sagging wire"))
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
                gg.ui.popup_sub("ZAP. Every hair you own is now standing up. Something else touches the wire, "
                                "then. Something that doesn't mind.", 4)
                gg.stats["zapped"] = gg.stats.get("zapped", 0) + 1
                if "rubber" not in gg.objective_keys():
                    gg.add_objective("rubber", "Find something that won't carry current")
                return
            gg.inv.remove(item)
            self.setf("moohole_open")
            self.setf("moohole_item", item)
            gg.world.colliders["moohole"].enabled = False
            self.moohole_prop(item)
            gg.audio.play("zap", vol=0.3, pitch=1.5)
            gg.ui.popup_sub("You wedge it under the bottom wire and push. The wire lifts. There's a gap now. "
                            "A cow-sized gap.", 5)
            done["d"] = True
        g.on("moohole", lambda gg: "Prop up the wire" if rubber() else "Squeeze under the wire", prop_it)
        yield lambda: done["d"]
        if "rubber" in g.objective_keys():
            g.complete("rubber", sound=False)
        g.complete("hole")

    def moohole_prop(self, item):
        """Stand the boot (or the rubber chicken) up under the sagging wire and hang the wire over it."""
        if item == "boot":
            e = models.item_model("boot", position=(MOOHOLE_POS[0], 0.165, MOOHOLE_POS[1]), rotation=(0, -90, 0),
                                  scale=1.5)
            top = 0.165 + 0.3115 * 1.5
        else:
            # standing on its belly along the fence, head up under the wire
            e = models.item_model("rubber_chicken", position=(MOOHOLE_POS[0], 0.12, MOOHOLE_POS[1] - 0.33),
                                  scale=1.5)
            top = 0.12 + 0.28 * 1.5
        self.prop("moohole_boot", e)
        self.g.world.set_moohole_wire(top + 0.013)

    def d3_barn(self):
        g = self.g
        self.objectives(("look", "Find out what the tractor needs"))
        self.mark((22, 1, "Barn"))
        done = {"d": False}

        def look(gg):
            yield from gg.talk([
                ("narrator", "The ignition is empty. Taped to the dash, in Chuck's capitals: 'KEY ON THE NAIL. NOT "
                             "IN POCKET. REMEMBER THE NAIL.' There's no nail on the dash."),
                ("narrator", "The fuel gauge is resting on E. Stuck to the filler cap: one smear of diesel and a "
                             "small, angry-looking feather."),
                ("narrator", "There's a hole where the spark plug should be. A note taped to the engine says: "
                             "'PLUG SOAKING IN VINEGAR (KITCHEN). DO NOT DRINK. -C'"),
                ("you", "Moo. (Key, fuel, spark plug. The plug's in the house. The other two are somewhere on this "
                        "farm. Grand theft tractor. Mom would be proud. Mom was a hamburger. A proud one, I assume.)"),
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
        self.mark((22, 1, "Tractor"))

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
        # Cluckydides guards the coop
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
            ("cluck", "This is my coop. I've seen off two foxes, a weasel, a hawk and a very confused goose, and "
                      "I wrote a history of each war. Eight volumes. Nobody reads them. The hens can't read."),
            ("cluck", "You want the diesel. Let me save you some time, because it always goes the same way: the "
                      "strong do what they can, and the weak suffer what they must."),
            ("you", "Moo. (I'm a two-thousand-pound mammal. You're a nugget with a headband.)"),
            ("cluck", "...Then I suppose we're about to find out which of us that line is about. Fight me."),
        ])
        g.cutscene_end_now()
        self.lock_hud_music("music_boss", 0.7, 1.0)
        g.ui.set_boss("CLUCKYDIDES", 1.0)
        p.health = p.max_health
        g.ui.set_health(p.health, p.max_health, True)
        g.ui.popup_sub("Left click headbutt (gallop into it for double)\nRight click back-kick   Q throw", 6)
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
                g.ui.popup_sub("Cluckydides stands on your head for a while, doing a little victory dance, then "
                               "lets you go. 'Come back when you've got a spine, cow. Or a beak.'", 6)
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
            ("cluck", "Bawk... okay. Okay. Hard head, cow. Harder than the goose. In this analogy the goose was "
                      "Melos, and I've just become Melos too. Embarrassing."),
            ("cluck", "What do you want with Chuck's diesel?"),
            ("you", "Moo. (We're driving his tractor through the main gate on Sunday. All of us are leaving.)"),
            ("cluck", "...All of you? Cows have never done anything. That's why there's no history of cows. I "
                      "checked. It's one page and the page is a menu."),
            ("you", "Moo. (Moocrates keeps asking why Chuck is allowed to eat us.)"),
            ("cluck", "Allowed? Nobody allows anything. The strong do what they can and the weak suffer what they "
                      "must. Eight volumes, and that's the one sentence I've never had to revise."),
            ("you", "Moo. (So what do the weak do?)"),
            ("cluck", "Historically? Suffer. Now and then one of them reads the sentence again, notices it's about "
                      "what you CAN do, and goes and changes that. Those are the good chapters."),
            ("cluck", "Six years I've announced the sunrise, as if the sun needed my permission. You know what "
                      "Chuck calls me? 'Nuggets.' A historian. Nuggets. To my FACE."),
            ("cluck", "Sunday at dawn I crow like the world is ending, because for him it is. That's your signal. "
                      "Take the can. And if you fail, I'll write that you never existed. Historians can do that."),
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
        self.objectives(("trough", "Head back to the pasture. Archimoodes is waiting at the trough."))
        self.mark((-31, -22, "Archimoodes"))
        p = g.player
        yield lambda: math.hypot(p.x + 32, p.z + 22) < 5 and not g.busy
        g.complete("trough")
        g.cutscene_start(letterbox=True)
        g.set_time("sunset")
        p.teleport(-31.5, 0, -19.0, 180)
        p.look_at_point((mz.x, 1.3, mz.z))
        yield from g.talk([
            ("moozart", "Cluckydides crowed at six fourteen this morning. He's crowed at six fourteen for eleven days, give "
                        "or take a minute and a half. Is he with us?"),
            ("you", "Moo. (I beat him up. He's on our side now.)"),
            ("moozart", "The oldest argument there is. Good: then Sunday has a signal, and it's the most reliable thing on "
                        "this farm. Key, diesel, signal. That leaves the spark plug, and that's in Chuck's kitchen."),
            ("cowleen", "Archimoodes, why is your ear tag always caked in mud? You're the tidiest cow on the farm. You "
                        "sweep your circles."),
            ("moozart", "I like it that way. It's a look."),
            ("cowleen", "It isn't."),
        ])
        g.cutscene_end_now()
        self.objectives(("wash", "Find out what's under the mud"))
        done = {"d": False}
        g.on("trough", "Dunk Archimoodes' ear tag in the trough", lambda gg: done.__setitem__("d", True))
        g.on("cow_moozart", "Nudge him toward the trough", lambda gg: gg.examine(
            "He's drinking. His muddy ear is right over the water. One good nudge from the trough side would do it."))
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
            ("moozart", "...Well. That's that, then."),
            ("you", "Moo. (Twelve. You're twelve.)"),
            ("moozart", "Since I was a calf. Chuck said it when he put the tag in: 'Twelve. Lucky number.' Chuck is wrong "
                        "about luck and about numbers, but he's very reliable about Thursdays."),
            ("you", "Moo. (You've known since Monday.)"),
            ("moozart", "Since the page. I put the mud on that afternoon. I'd done the sums, and I'd made my peace, and I "
                        "didn't want this week to be about me. If you'd known, you'd have spent it on me instead of on the "
                        "fence."),
            ("cowleen", "Thursday's Thursday. It was always going to be somebody, Twelve. I'm sorry it's you."),
            ("moozart", "Archimoodes, please. I'm not on the truck yet."),
            ("cowleen", "...Sorry. Habit."),
            ("you", "Moo. (Then we hide him. Tomorrow, before the truck comes. The hayloft: Chuck hates the ramp.)"),
            ("cowleen", "Forty-Seven, it doesn't work like that. If he isn't there, Chuck counts. Then he searches."),
            ("you", "Moo. (Then let him search. Nobody's handing him over.)"),
            ("moozart", "...Fine. The hayloft. It's quiet up there and I've some circles to finish."),
            ("moozart", "They've been calling you Forty-Seven all week, I notice. Odysseus told the Cyclops his name was "
                        "Nobody, then walked out of the cave under a sheep. Be Nobody till Sunday if it helps, Moodysseus. "
                        "Just don't forget it isn't your name."),
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
        f.range_day = 34.0     # rain: shorter than a dry day's 60 m
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
            ("go", (-2, 0, -22), 1.9), ("wait", 4, "look", RAIN_LINES),
            ("go", (0, 0, 10), 1.9), ("wait", 4, "look"),
        ])
        f.teleport((22, 0, -14), 0)
        self.dhook("update", self.base_update)
        self.dhook("use", self.radio_use)

    def day4(self):
        yield from self.step("d4_wake", self.d4_wake)
        yield from self.step("d4_escort", self.d4_escort, hint=(
            "Which way into the barn doesn't go past Chuck? And what stops a cow counting out loud?",
            "Out through the gap in the fence, along the outside of the pasture fence, and in through the barn's "
            "side door, then up the ramp. If Archimoodes starts reciting primes, moo at him (M)."))
        yield from self.step("d4_loft", self.d4_loft)
        yield from self.step("d4_back", self.d4_back, hint="Back to the pasture, through the gap in the fence.")
        yield from self.step("d4_truck", self.d4_truck)
        yield from self.step("d4_vigil", self.d4_vigil, hint="Look at Archimoodes' circles in the mud by the pond.")
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
            ("cowleen", "The truck comes at dusk. So he's going up into the hayloft, Forty-Seven? Your idea."),
            ("you", "Moo. (He's going up into the hayloft.)"),
            ("cowleen", "When he's thinking hard he counts primes out loud. Chuck will hear that. If he starts, moo at him."),
            ("moozart", "I don't count primes out loud."),
            ("cowleen", "You're doing it now."),
            ("moozart", "Two, three, five, seven... That's not counting. That's listing the numbers nobody can divide. It's "
                        "soothing. Nobody on this farm is indivisible."),
        ])
        g.cutscene_end_now()

    def d4_escort(self):
        g = self.g
        mz = g.cows["moozart"]
        p = g.player
        self.objectives(("escort", "Lead Archimoodes to the hayloft"))
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
                    g.ui.popup_sub(random.choice(["Archimoodes stops. \"Sorry. Thirty-seven. Where was I.\"",
                                                  "Archimoodes stops. \"Fine. I'll count in my head. It's less accurate.\"",
                                                  "Archimoodes stops. \"Silence isn't the absence of numbers. It's just "
                                                  "numbers you can't hear.\""]), 3)
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
                        mz.bubble("...41, 43, 47! FORTY-SEVEN!", 2.5)
                        g.audio.play("moo_moozart_exclaim_0", vol=0.8, pos=(mz.x, 1.4, mz.z), rng=30, group="voice")
                        f = g.farmer
                        if f.visible and f.state in ("routine", "investigate", "alert"):
                            # that carries: Chuck drops everything and comes running, already sure something's up
                            f.say("WHO'S COUNTIN' OUT THERE?!", force=True)
                            g.audio.play("alert", vol=0.7)
                            f.investigate((mz.x, 0, mz.z), quiet=True)
                            f.walk_speed = 4.4
                            f.susp = max(f.susp, 0.85)
                            f.set_marker("!")
                            g.ui.popup_sub("Chuck heard that. He's coming. Hide, or he'll have you both.", 4)
                        st["t"] = random.uniform(10, 16)
                else:
                    st["t"] -= dt
                    if st["t"] <= 0:
                        st["warn"] = 3.5
                        mz.bubble("2, 3, 5, 7, 11...", 3.0)
                        g.ui.popup_sub("Archimoodes is reciting primes. Moo at him before he gets loud! (M)", 3)
            # a shut side door would strand him outside the barn: he noses it open himself
            sd = g.world.doors["barn_side"]
            if not sd.is_open:
                cx, cz = sd.center()
                if math.hypot(mz.x - cx, mz.z - cz) < 3.0:
                    sd.set_open(True)
                    g.audio.play("door_creak", vol=0.6, pos=(cx, 1, cz), rng=30)
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
            ("moozart", "Good. Rain on a tin roof, no Chuck, and a problem. If there's a heaven, it's this."),
            ("moozart", "Since we've time: the circle. I can't measure it. I can only trap it, between a shape with "
                        "ninety-six sides inside it and another one outside. Three and ten seventy-firsts, to three and a "
                        "seventh. It's in there somewhere."),
        ])
        yield from g.cam_move((14.0, L + 1.2, 13.4), (16.2, L + 1.1, 11.4), dur=6.0)
        yield from g.talk([
            ("you", "Moo. (Does it matter?)"),
            ("moozart", "Not at all. That's why I like it. Everything else this week has mattered far too much."),
            ("moozart", "Give me that page from Chuck's planner. The back's blank. And the pencil you stole at the "
                        "headcount."),
        ])
        for k in ("page", "pencil"):
            if g.inv.has(k):
                g.inv.remove(k)
        g.audio.play("paper", vol=0.7)
        yield 1.2
        g.inv.add("score")
        yield from g.talk([
            ("moozart", "There. The whole plan, in order: fence, signal, tractor, gate, road. Written down, so it doesn't "
                        "live in one cow's head."),
            ("moozart", "Read it to the herd if you ever need a distraction. They'll argue for an hour about whether to "
                        "bother, very loudly. They'll still be arguing about it on the road."),
            ("you", "Moo. (Why write it down? You'll be there.)"),
            ("moozart", "Plans that live in one cow's head have a habit of ending on a Thursday. Go on, Moodysseus, "
                        "before Chuck counts. I'll stay up here and squeeze my circle."),
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
            ("chuck", "Twelve! C'mere, twelve! Truck's here! Big day! You're goin' on a little trip!"),
            ("chuck", "Twelve? ...Where the heck is twelve? I got a guy with a truck and a schedule!"),
        ])
        yield from self.walk_npc(f, (-25.0, 0, -31.0), 2.0, 5)
        f.face_target = (p.x, p.z)
        yield 0.8
        yield from g.talk([
            ("chuck", "Aw, heck. The truck's paid for. Non-refundable. I read the small print this time."),
            ("chuck", "Forty-seven. Well, you're in the book for Sunday anyway. Guess you're goin' early. Dale's "
                      "gonna be real disappointed."),
        ])
        f.goto((p.x + 1.6, 0, p.z), 1.4)
        yield 1.5
        # Archimoodes walks out of the barn and hands himself in: the plan needs Forty-Seven on Sunday
        mz.teleport((8.5, 0, 0.7), 225)
        mz.set_visible(True)
        g.world.doors["barn_side"].set_open(True)
        g.audio.play("moo_moozart_long_0", vol=1.0, pos=(8.5, 1.4, 0.7), rng=80, group="voice")
        g.cam_set((1.5, 2.2, -8.0), (8.5, 1.4, 0.2))
        mz.goto((-2.0, 0, -22.0), 1.6)
        mz.bubble("MOO. (Twelve. Here.)", 3)
        self.lock_hud_music("music_sad", 0.6, 2.5)
        yield 4.5
        f.path = []
        f.face_target = (-10, -30)
        g.cam_set((-27.5, 1.9, -33.0), (-22, 1.5, -31))
        f.pose = "idle"
        yield 1.5
        yield from g.talk([("chuck", "Well. There you are, twelve. Walkin' right up. Most cows gotta be dragged. You're "
                                     "a real professional.")])
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
            ("you", "Moo. (Archimoodes. Don't. Go back up the ramp.)"),
            ("moozart", "Do you know the trolley problem? A runaway trolley. Five on one track, one on the other, and "
                        "somebody at the lever. Humans will argue about it for years."),
            ("moozart", "It's simpler from the track. That truck leaves with a cow tonight: Chuck paid for one. If it's "
                        "you, nobody drives the tractor on Sunday and the whole herd stays on the track. If it's me, it's "
                        "one."),
            ("moozart", "And I'm not only the one on the track. I'm the one at the lever. That's the part I'm glad of. "
                        "Nobody chose this for me."),
            ("moozart", "Don't answer to Forty-Seven, Moodysseus. And tell Moogenes to stay off my circles."),
        ])
        g.cam_set((-26, 2.5, -42), (-12, 1.4, -35))
        # the tailgate drops into a ramp. The truck faces +x, so its tail (hinge 2.95 m back, 1 m up) is
        # on the -x side; a 2.4 m gate swung 113 degrees rests its edge on the ground 2.2 m out
        hx, tz = truck.x - 2.95, truck.z
        foot = hx - 2.2
        truck.door.animate_rotation((-113, 0, 0), duration=0.9, curve=curve.in_quad)
        f.goto((foot - 0.4, 0, tz - 2.2), 1.2)
        yield 0.9
        g.audio.play("metal_clang", vol=0.9, pos=(foot, 0.3, tz), rng=50)
        ramp = [g.phys.add_floor(foot, hx, tz - 1.1, tz + 1.1, 0.06, 0.97, axis="x", surface="wood"),
                g.phys.add_floor(hx, truck.x + 2.4, tz - 1.1, tz + 1.1, 0.97, surface="wood")]
        try:
            yield from self.walk_npc(mz, (foot - 0.6, 0, tz), 1.2, 6)
            # straight up the ramp: the nav graph doesn't know about this floor
            mz.path = [(hx + 2.3, 0.97, tz)]
            mz.walk_speed = 0.9
            mz.look = None
            t0 = g.env.time
            yield lambda: not mz.path or g.env.time - t0 > 8
        finally:
            for fl in ramp:
                g.phys.floors.remove(fl)
        # he rides away with the truck: a stand-in parented to it takes his place
        _, _, mkw, tag = FRIENDS["moozart"]
        rider = models.CowModel(parent=truck, tag=tag, **mkw)
        rider.world_position = (mz.x, max(mz.y, 0.97), mz.z)
        rider.world_rotation_y = mz.yaw
        rider.animate(0.02)
        mz.set_visible(False)
        mz.path = []
        mz.look = "player"
        yield from self.walk_npc(f, (foot - 0.3, 0, tz - 1.4), 1.2, 3)
        f.face_target = (hx, tz)
        yield 0.4
        truck.door.animate_rotation((0, 0, 0), duration=0.9, curve=curve.in_out_sine)
        yield 0.9
        g.audio.play("door_close", vol=1.0, pos=(hx, 1.5, tz), rng=60)
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
        yield 7.0
        yield from g.fade_out(2.0)
        destroy(rider)
        self.remove_prop("truck")
        self.setf("moozart_gone")
        g.cutscene_end_now()

    def d4_vigil(self):
        g = self.g
        p = g.player
        g.set_time("night")
        g.ambience("night")
        g.world.set_lamp("cowshed", True)
        # frogs and crickets, no music: his tune already played once tonight (at the truck)
        self.lock_hud_music(None, 0, 2.0)
        self.gather_at(POND_VIGIL)
        p.teleport(-41.0, 0, -49.0, 180)
        # Archimoodes' circles in the mud by the pond (where he was working on Monday)
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
        self.objectives(("prints", "Archimoodes' funeral, by the pond (look at his circles in the mud)"))
        self.mark((-44, -53, "Funeral"))
        ia = g.ia.add(Interactable("st_prints", (-43.5, 0.2, -52.9), 1.2, "Hoofprints", None, "Look at the hoofprints",
                                   4.0))
        seen = {"d": False}

        def look(gg):
            yield from gg.show_document("Hoofprints in the mud", HOOFPRINTS)
            seen["d"] = True
        ia.handlers.append(Handler("Look at the hoofprints", look, None, "global"))
        yield lambda: seen["d"]
        g.complete("prints")
        # the funeral, which goes about as well as everything else on this farm
        g.cutscene_start(letterbox=True)
        g.cam_set((-41.0, 1.9, -46.5), (-42.5, 1.1, -53.0))
        yield from g.talk([
            ("cowleen", "Okay. We're here for Archimoodes. Moogenes asked to do the eulogy, and I didn't have the energy "
                        "to stop him."),
            ("sirloin", "Friends. Cows. Epicowrus."),
            ("mooriarty", "Hey."),
            ("sirloin", "Archimoodes never once let me finish a sentence without correcting it. I've been talking for a "
                        "whole minute now and nobody's corrected me. I hate it."),
            ("sirloin", "He once called my reasoning 'a series of non sequiturs held together by confidence'. I think "
                        "about it every day. It's the nicest thing anyone's ever said about me."),
            ("moomaw", "That was lovely, dear. Now say something about him."),
            ("sirloin", "He had a bow tie."),
        ])
        g.audio.play("sad_trombone", vol=0.7)
        yield 2.2
        g.cam_set((-45.5, 1.7, -48.5), (-49.5, 1.1, -53.3))
        yield from g.talk([
            ("cowpernicus", "I went over his reasoning all afternoon. The truck, the count, Sunday. I wanted it to be "
                            "wrong, so at least he'd have gone for an arithmetic slip. It isn't wrong. I've never hated a "
                            "sum more."),
            ("mooriarty", "Death is nothing to us. Where death is, we are not. I've sold that line for years. It works: "
                          "the cows go calm."),
            ("mooriarty", "Tonight I noticed who it works best for. A little for the cow. Enormously for whoever's "
                          "holding the rope."),
            ("cowpernicus", "My school teaches that the soul goes round. Into another body."),
            ("sirloin", "Which body?"),
            ("cowpernicus", "...We don't usually follow that one through, on a farm."),
            ("moomaw", "When Ajax went, there wasn't a funeral. Chuck had a cookout. Everyone said the burgers were very "
                       "moving."),
            ("cowleen", "That's what I keep coming back to. Ajax. Io's sister. Echo's mother. The truck's come every "
                        "other Thursday of my life, and this is the first funeral we've ever had. Why?"),
            ("mooriarty", "You won't like the answer, Moocrates."),
            ("moomaw", "Because it was weather, dear. You can't grieve the weather. You'd never stop."),
            ("cowleen", "He never called it weather. He was the only one of us who didn't. He hid his number so we'd keep "
                        "working on the fence, and when we found it, I called him Twelve."),
            ("cowleen", "We've said his name all night. Have you noticed? We've never said one after a Thursday before."),
        ])
        yield 1.5
        g.cam_set((-41.0, 1.9, -46.5), (-42.5, 1.1, -53.0))
        yield from g.talk([
            ("mooriarty", "While we're all gathered: I have a strictly limited run of Archimoodes memorabilia. Signed "
                          "circles. Authentic."),
            ("cowleen", "Those are YOUR hoofprints. You're standing in them."),
            ("mooriarty", "Every circle is a copy of an ideal one, Moocrates. Plato. Five clovers. Grief discount."),
            ("sirloin", "Can I add one thing?"),
            ("cowpernicus", "No."),
            ("moomaw", "No, dear."),
            ("mooriarty", "No."),
            ("you", "Moo. (No.)"),
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
                "A framed photo: 'Me & Big Ajax, Best in Show 2009.' Chuck has his arm round a huge, unimpressed bull. "
                "Chuck is beaming. It's the only photo in the house."), None, "global"))
            ia.handlers.append(Handler("Take the photo (for Heifercleitus)", take, lambda gg: "photo" in gg.side_quests,
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
        yield from self.step("d5_key", self.d5_key, hint=(
            "Where does every human on earth hide a spare key? And then where does Chuck move it?",
            "Lift the doormat and follow the notes. The key ends up inside the garden gnome by the corner of the "
            "house: knock him over."))
        yield from self.step("d5_inside", self.d5_inside, hint=(
            "Who has Chuck ever called his best friend? There's exactly one photo in that house.",
            "The spark plug's in a glass on the kitchen table. The computer's in the office, and the password is "
            "the bull in the photo on the desk."))
        yield from self.step("d5_return", self.d5_return, hint=(
            "Where can a cow hide in a house? And what did Chuck come back for?",
            "Hide in the bedroom wardrobe until he's gone, or slip out of the back door in the kitchen. If you "
            "took his shoes, throw them (Q) and he'll go after them."))
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
        yield from g.talk([("chuck", "Big night tonight, girls! Bowlin' with the boys! Don't wait up! Not that you "
                                     "can! You're cows! HA!")])
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
            ("cowleen", "He's gone till late. Bowling: you roll something heavy at things standing in a row. Very on brand."),
            ("cowleen", "The house is empty. The spark plug's in there somewhere. And Archimoodes always said Chuck writes "
                        "everything down. This time he typed it. I'd like to know what's on that computer."),
            ("cowleen", "Back before dark, Forty-Seven. I'd like to go to fewer funerals."),
        ])
        g.cutscene_end_now()

    def d5_key(self):
        g = self.g
        # each note you find goes in the objective, so you don't have to remember it
        clue = {0: "   The front door's locked",
                1: "   A note says: under the flowerpot",
                2: "   A note says: in the gnome"}

        def show():
            self.objectives(("in", "Get into the farmhouse"),
                            ("in_key", clue[min(2, self.flags.get("d5_keystate", 0))]))
        self.flags.setdefault("d5_keystate", 0)
        show()
        self.mark((56, 29, "Farmhouse"))

        def found(stage):
            if self.flags.get("d5_keystate", 0) < stage:
                self.flags["d5_keystate"] = stage
                show()

        def mat(gg):
            yield from gg.show_document("Under the doormat", "A sticky note, a bit damp:\n\n"
                                                             "    Spare key is under the FLOWERPOT.\n"
                                                             "    (Burglars: it's not. Go away.)")
            found(1)

        def pot(gg):
            gg.audio.play("rock_land", vol=0.6, pitch=0.7)
            yield from gg.show_document("Under the flowerpot", "Another sticky note:\n\n"
                                                               "    Moved it. Spare key is in the GNOME.\n"
                                                               "    (Break him open. I'll buy another.\n"
                                                               "     His name is Gary. He knew the risks.)\n"
                                                               "                              - Chuck")
            found(2)
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
        g.on("gnome", "Headbutt the gnome", smash,
             cond=lambda gg: not self.done("gnome_broken") and self.flags.get("d5_keystate", 0) >= 2)
        g.ia.get("gnome").on_headbutt = bonk
        g.ia.get("gnome").on_rock = lambda gg, pt: bonk(gg)

        GX, GZ = 41.0, 24.0
        p = g.player

        def upd(dt):
            self.base_update(dt)
            if self.done("gnome_broken"):
                return
            # walking into him is enough: the cow's body stops about 0.9 m from his middle
            if math.hypot(p.x - GX, p.z - GZ) < 1.05 and abs(p.y) < 1.0:
                bonk(g)
        self.hook("update", upd)

        def kick(pos, yaw):
            # a back-kick with him behind you
            dx, dz = GX - pos[0], GZ - pos[2]
            d = math.hypot(dx, dz)
            fx, fz = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
            if d < 2.4 and (dx * fx + dz * fz) / max(d, 0.01) < -0.2 and not self.done("gnome_broken"):
                bonk(g)
                return True
            return False
        self.hook("kick", kick)

        def land(proj, pos):
            # anything thrown that comes down on or next to him
            if math.hypot(pos[0] - GX, pos[2] - GZ) < 1.4:
                bonk(g)
        self.hook("land", land)
        yield lambda: g.inv.has("house_key") or self.done("house_unlocked")
        g.ia.get("gnome").on_headbutt = None
        g.ia.get("gnome").on_rock = None
        self.objectives(("in", "Get into the farmhouse"), ("in_key", "   Found the spare key"))
        g.complete("in_key", sound=False)
        self.mark((56, 29, "Front door"))
        p = g.player
        yield lambda: g.phys.in_zone("house", p.x, p.z)
        g.complete("in")

    def d5_inside(self):
        g = self.g
        self.objectives(("plug", "Find the spark plug"), ("pc", "Get into Chuck's computer"))
        if self.done("sparkplug_taken"):
            g.complete("plug", sound=False)
        used = {"d": self.done("emails_read")}
        if used["d"]:
            g.complete("pc", sound=False)

        def computer(gg):
            ok = yield from self.password({"BIGAJAX", "AJAX"}, "Hint: 'my best friend (NOT Dale)'.")
            if not ok:
                return
            gg.world.props["monitor_screen"].texture = tex("monitor_inbox")
            yield from gg.show_mail(EMAILS)
            yield from gg.show_document("COWS.XLS - ChuckOffice", SPREADSHEET, paper=False)
            r = yield from gg.say("you", "Moo. (All of them. He's selling the whole herd to Dale's cousin. In "
                                         "bulk. Like toilet paper.)",
                                  choices=["Reply to Dale: cancel the barbecue (and insult his potato salad)",
                                           "Leave it alone"])
            gg.end_talk()
            if r == 0:
                self.setf("dale_cancelled")
                yield from gg.show_document("ChuckOS Mail - Reply", DALE_REPLY, paper=False)
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
                        # he lets himself in (and shuts the door behind him): see Farmer._doors_tick
                        f.set_routine([("say", "Forgot my dang SHOES."), ("go", (56, Y, 32.0), 2.3), ("stop", "idle")])
            elif ph == "walk_in":
                if f.r_i >= 2 and not f.path:
                    state["phase"] = "search"
                    self._chuck_search(search, state)
            elif ph == "search":
                if f.state == "routine" and f.routine and f.r_i == len(f.routine) - 1 and not f.path:
                    if not g.inv.has("shoes"):
                        self._chuck_found_shoes(state)
                    else:
                        self._chuck_search(search, state)
            elif ph == "fetch":
                # r_i: he's walked to them (the path is also empty the moment the routine is set)
                if f.r_i >= 1 and not f.path and f.state == "routine":
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
        f.set_routine([("go", (56, 0, 25.5), 2.6), ("go", (71.5, 0, 33.5), 2.6), ("hide",), ("stop", "idle")])
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
            lines += [
                ("you", "Moo. (Chuck's selling the rest of the herd to Dale's cousin at the plant. All of you. End of "
                        "the month. In bulk.)"),
                ("sirloin", "In BULK. As if we were interchangeable. As if I were fungible."),
                ("mooriarty", "To be fair, Moogenes, from a market perspective you're extremely fungible."),
                ("moomaw", "Well. That settles it. I was going to die of old age out of spite."),
                ("cowleen", "On Monday I said we owed Chuck the truck, because we'd eaten his grass. I was defending a "
                            "bargain. There isn't one. There's a price list, and now we're all on it."),
                ("cowleen", "Archimoodes said it was a mortgage. I said I'd think about it. I've thought about it."),
                ("sirloin", "Custom did our thinking for us. It did Chuck's too. Admit it: you all said 'weather'."),
                ("mooriarty", "I said 'death is nothing to us'. Same thing, nicer font."),
                ("moomaw", "And I said the river only runs one way. It does. It turns out we're not the river, dear. "
                           "We're standing in it."),
            ]
        else:
            lines += [
                ("cowleen", "Last night we held a funeral. First one ever. This morning nobody would say 'weather'. "
                            "I've been asking around. Nobody can tell me what changed. Something did."),
            ]
        lines += [
            ("cowpernicus", "Then the plan. His plan: I've only done the sums. It's in the dirt. Moogenes, please."),
            ("sirloin", "I've moved."),
            ("cowpernicus", "You've moved onto a different bit of it. Anyway."),
            ("cowpernicus", "Sunday, dawn. Cluckydides crows. The fence goes dead: it runs off the generator in the "
                            "shed, and somebody pulls the fuse. Not with their face. The face is an organ, not a "
                            "tool."),
            ("cowpernicus", "Forty-Seven drives the tractor through the main gate. Forty-eight cows follow it to the "
                            "road."),
            ("cowpernicus", "What we haven't solved: the tractor still has a hole where its spark plug goes. The "
                            "cattle grid in front of the gate is bars and gaps, and a cow's leg fits the gap "
                            "exactly. Somebody measured us for it. And the herd doesn't know any of this."),
            ("cowleen", "Tell them quietly. Not Echo. Whatever Echo hears last, the next cow she meets hears next, "
                        "and last week that was Chuck."),
            ("mooriarty", "And somebody deals with the shotgun."),
            ("moomaw", "Ol' Bessie. She lives in a cabinet in his office. The key lives somewhere Chuck can reach "
                       "without getting out of bed. Chuck has never once got out of bed for anything."),
            ("mooriarty", "If Chuck walks out on Sunday holding Bessie, the plan gets very short."),
            ("cowleen", "Tomorrow night, then, while he sleeps. We rob a man in his bedroom. I've looked at the "
                        "ethics from every side. Every side has a barbecue on it."),
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
            ("go", (40, 0, 18), 2.0), ("wait", 6, "look"),
            ("go", (30, 0, -20), 2.0), ("wait", 4, "look"),
            ("go", (0, 0, -10), 2.0), ("wait", 5, "look"),
            ("go", (-2, 0, -22), 2.0), ("wait", 4, "look"),
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
        yield from self.step("d6_prep", self.d6_prep, hint=(
            "What's the tractor still missing? What makes a floor across bars? And who still hasn't been told?",
            "Spark plug: in the tractor, in the barn. Planks: the lumber pile south of the shed, carried to the "
            "cattle grid at the main gate. Herd: talk to five of the herd cows."))
        yield from self.step("d6_night", self.d6_night, hint=(
            "Where does a man who never gets out of bed keep a key? And what wakes a sleeping farmer?",
            "The cabinet key's in the nightstand by Chuck's bed; the gun cabinet is in the office. Sneak (C) the "
            "whole way: walking wakes him. Or set the radio down playing in the kitchen (Q) and let him get up "
            "to deal with it."))
        yield from self.step("d6_stars", self.d6_stars, hint="The crew's rehearsing at the Old Oak. Get back into the "
                                                             "pasture and join them.")
        yield from self._run_day(7)

    def d6_wake(self):
        g = self.g
        c = g.cows["cowleen"]
        c.teleport((-45.6, 0, -4.2), 20)
        g.cutscene_start(letterbox=True)
        g.player.look_at_point((c.x, 1.3, c.z))
        yield from g.fade_in(1.2)
        yield from g.talk([
            ("cowleen", "Hear that? He's sharpening knives by the barn. Since six. Whistling. He isn't cruel. He's "
                        "cheerful. I can't decide which is worse."),
            ("cowleen", "Upside: the grinder's loud. Near it, he can't hear a thing. Downside: the reason it's "
                        "loud."),
            ("cowleen", "Today we close what's still open: the tractor, the cattle grid, the herd. Tonight, the "
                        "shotgun. Tomorrow we find out what a plan's worth once Chuck's awake."),
        ])
        g.cutscene_end_now()

    def d6_prep(self):
        g = self.g
        herd_n = {"n": len(self.flags.get("rallied", []))}
        planks = {"n": self.flags.get("planks_laid", 0)}

        def refresh():
            self.objectives(("plug", "Get the tractor running"),
                            ("planks", "Make the cattle grid safe for hooves" +
                             (f" ({planks['n']}/3 planks)" if planks["n"] else "")),
                            ("herd", f"Tell the herd ({min(5, herd_n['n'])}/5)"))
            if self.done("sparkplug_in"):
                g.complete("plug", sound=False)
            if planks["n"] >= 3:
                g.complete("planks", sound=False)
            if herd_n["n"] >= 5:
                g.complete("herd", sound=False)
        refresh()
        self.mark((22, 1, "Tractor"), (0, 82.5, "Cattle grid"))

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
        g.on("cattle_grid", "Look at the cattle grid", lambda gg: gg.examine(
            "Steel bars over a pit, each gap exactly one hoof wide. A floor laid across it would fix that. Something "
            "long and flat. Three of something long and flat."),
            cond=lambda gg: not gg.inv.has("plank") and planks["n"] < 3)

        def rally(cow):
            rl = set(self.flags.get("rallied", []))
            if cow.idx in rl:
                return False
            rl.add(cow.idx)
            self.flags["rallied"] = sorted(rl)
            herd_n["n"] = len(rl)
            yield from g.talk([
                ("you", "Moo. (Sunday, dawn. When the rooster crows, follow the tractor. Pass it on. Don't tell "
                        "Chuck. Obviously.)"),
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
        f.sleep(BED_SLEEP, 180, getup=BED_GETUP)
        g.world.set_lamp("porch", True)
        if not g.phys.in_zone("pasture", p.x, p.z):
            self.return_to_pasture()
            f.sleep(BED_SLEEP, 180, getup=BED_GETUP)
            p.teleport(-40, 0, -30, 90)
        yield from g.fade_in(1.2)
        g.cutscene_end_now()
        self.objectives(("gun", "Take Ol' Bessie from Chuck's office"),
                        ("ckey", "Find the cabinet key"))
        if g.inv.has("cabinet_key") or self.done("cabinet_open"):
            g.complete("ckey", sound=False)
        self.mark((54, 44, "Farmhouse"))

        def after():
            self.return_to_pasture()
            f.sleep(BED_SLEEP, 180, getup=BED_GETUP)
            g.ui.popup_sub("Chuck walked you back in his pyjamas, yawning, and went straight back to bed.", 6)
            return True
        self.hook("after_caught", after)
        self.hook("caught_line", lambda: "Mmf... forty-seven? In my HOUSE? At NIGHT? ...Back to bed. Both of us.")

        def drawer(gg):
            gg.audio.play("door_creak", vol=0.3, pitch=1.6, pos=(60.9, 1, 47.1), rng=15)
            gg.noise((60.9, Y, 47.1), 5, "drawer")
            gg.inv.add("cabinet_key")
            gg.complete("ckey")
        g.on("nightstand", lambda gg: "Open the drawer (quietly)" if gg.player.crouching else
             "Open the drawer (sneak first: C, or it'll creak)", drawer,
             cond=lambda gg: not gg.inv.has("cabinet_key") and not self.done("cabinet_open"))

        def cabinet(gg):
            gg.inv.remove("cabinet_key")
            self.setf("cabinet_open")
            gg.world.props["bessie"].enabled = False
            gg.audio.play("chain", vol=0.3, pitch=1.4, pos=(50.9, 1, 46.5), rng=15)
            gg.flags["shells"] = gg.flags.get("shells", 0)
            gg.inv.add("shotgun")
            gg.complete("gun")
            if not gg.flags["shells"]:
                gg.ui.popup_sub("She's empty. No shells in the cabinet either. Chuck keeps the ammunition somewhere "
                                "separate, like a responsible man. It's the only responsible thing in the house.", 7)
        g.on("gun_cabinet", "Unlock the cabinet and take Ol' Bessie", cabinet,
             cond=lambda gg: gg.inv.has("cabinet_key"))
        g.on("gun_cabinet", "Try the gun cabinet", lambda gg: gg.examine("Locked. A small brass keyhole, and "
                                                                         "Ol' Bessie behind the glass."),
             cond=lambda gg: not gg.inv.has("cabinet_key") and not gg.inv.has("shotgun"))
        yield lambda: g.inv.has("shotgun")

    def d6_stars(self):
        g = self.g
        p = g.player
        c = g.cows["cowleen"]
        c.teleport((-48.0, 0, -39.5), 20)
        c.look = "player"
        self.gather_at(OAK_MEET)
        self.objectives(("back", "Get back to the pasture"), ("cowleen", "Dress rehearsal at the Old Oak"))
        self.mark((-50, -35, "Rehearsal"))
        yield lambda: g.phys.in_zone("pasture", p.x, p.z) and not g.runner.running("caught")
        g.complete("back")
        yield lambda: math.hypot(p.x + 50, p.z + 35) < 7.5 and not g.busy
        g.complete("cowleen")
        # the dress rehearsal, which goes about as well as you'd expect
        g.cutscene_start(letterbox=True)
        self.gather_at(OAK_MEET)
        p.teleport(-50.5, 0, -41.5, 0)
        g.cam_set((-56.5, 3.2, -43.0), (-50, 1.2, -34.5))
        self.lock_hud_music(None, 0, 1.0)
        yield from g.talk([
            ("cowleen", "Good, you've got the gun. Dress rehearsal. Everyone in position. Quietly: Chuck's asleep."),
            ("cowpernicus", "Positions. The oak is the main gate. Forty-Seven is the tractor. Moogenes is... the "
                            "herd. All forty-eight of them."),
            ("sirloin", "I contain multitudes. Mostly grass."),
            ("cowpernicus", "Archimoodes would be the empty space next to Moogenes. I've left it empty. Don't stand in "
                            "it. Cluck! A practice crow, please. QUIETLY."),
        ])
        g.audio.play("rooster_crow", vol=1.0, pos=(41, 3.5, -29.5), rng=250)
        yield 2.6
        g.world.set_lamp("house_bed", True)
        g.audio.play("dun_dun", vol=0.5)
        yield from g.talk([
            ("cowleen", "..."),
            ("mooriarty", "A rooster was asked to crow quietly. We have learned something about roosters and "
                          "nothing about our plan. Nobody move."),
            ("chuck", "...mmf... Dale?... it's the middle of the NIGHT, Dale... zzz..."),
        ])
        g.world.set_lamp("house_bed", False)
        yield 1.0
        yield from g.talk([
            ("cowpernicus", "Okay. Okay. Step two. The tractor charges the gate. Go, Forty-Seven."),
            ("you", "Moo. (Vroom.)"),
        ])
        g.audio.play("thump", vol=1.0)
        g.audio.play("wood_crack", vol=0.5, pos=(-50, 1, -35), rng=40)
        g.player.shake = 0.4
        yield 0.8
        yield from g.talk([
            ("you", "Moo. (Ow. I hit the gate. It's a tree. The map was not the territory.)"),
            ("cowleen", "You were supposed to STOP at the tree. The tree is the gate. You don't hit the gate "
                        "until Sunday."),
            ("sirloin", "The herd is also in disarray. The herd has run into the trough."),
            ("moomaw", "Ajax's plan went better than this, dears, and Ajax's plan was a hamburger."),
            ("cowpernicus", "It's fine. A bad dress rehearsal predicts a good opening night."),
            ("cowleen", "Is that true?"),
            ("cowpernicus", "No. It's survivorship bias. The theatres whose opening nights went badly don't tell "
                            "the story. But it's comforting, and comfort was not in Archimoodes' plan, so I'm adding "
                            "it."),
            ("cowleen", "Bed. Everyone. Tomorrow it's real. Nobody practise anything else tonight."),
            ("sirloin", "Understood."),
        ])
        g.audio.play("thump", vol=0.8, pos=(-53.6, 0.5, -36.5), rng=40)
        yield from g.talk([("sirloin", "That was the trough again. I'm fine. The trough and I have an understanding. "
                                       "Goodnight.")])
        yield from g.fade_out(2.0)
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
        f.sleep(BED_SLEEP, 180, getup=BED_GETUP)
        g.world.set_lamp("porch", True)
        self.dhook("update", self.base_update)
        self.dhook("caught_line", lambda: "Hnnh? Not today, forty-seven. Today's your big day. Go get marinated.")
        # he has the shed key: on Sunday he'll go in there himself
        f.door_keys = OWN_DOORS + ("shed_door",)
        # every label on the fuse box is wrong: which of the two ways is decided once per run
        for e in g.world.fuses:
            e.enabled = True

        def after():
            self.return_to_pasture()
            f.sleep(BED_SLEEP, 180, getup=BED_GETUP)
            return True
        self.dhook("after_caught", after)

    def day7(self):
        yield from self.step("d7_crow", self.d7_crow)
        yield from self.step("d7_fuse", self.d7_fuse, hint=(
            "Every label is wrong. Is there anything in the shed that shows you what one of the fuses really does, "
            "without pulling it?",
            "Follow the cables: one runs up the wall and across the ceiling to the light, so that fuse is the shed "
            "light. Then the fence is whichever of the other two isn't labelled FENCE. Pull it with the pliers."),
                             save=False)
        yield from self.step("d7_tractor", self.d7_tractor, hint=(
            "A cow can't climb into a tractor. Can a cow fall into one? And where's Chuck looking?",
            "Sneak into the barn and up the ramp to the hayloft. The railing above the tractor is rickety: headbutt "
            "it till it goes (it's loud), then step off onto the tractor. Once you're driving, keep moving: he can't "
            "catch a tractor, only a stopped one."),
                             save=False)
        yield from self.step("d7_boss", self.d7_boss,
                             hint="Dodge his lunges. When the pitchfork sticks in the ground, hit him. When he's out of "
                                  "breath, hit him. Ol' Bessie (Q) knocks him flat, if she's got shells left.",
                             save=False)
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
            ("cowleen", "That's the signal. Six fourteen, on the dot. And Chuck slept through it. Six years of announcing "
                        "the sun, and the one man it's for has never heard it once."),
            ("cowleen", "Go. Fuse, tractor, gate. And try not to run anyone over. Except Chuck. Chuck is within "
                        "tolerances."),
        ])
        g.cutscene_end_now()
        self.lock_hud_music("music_stealth", 0.6, 2.0)

    def d7_fuse(self):
        """The fuse box: three fuses, three labels, and a note saying every label is wrong. The one marked HOUSE is
        the only safe first pull (it can only be the fence or the shed light), and what it does tells you the
        rest. Pull the real house fuse and Chuck's freezer dies: he's up, and on his way to the shed to fix it."""
        g = self.g
        f = g.farmer
        w = g.world
        self.objectives(("fuse", "Kill the fence"))
        self.mark((-8, -22, "Tool shed"))
        fmap = self.flags["fuse_map"]
        pulled = set()
        done = {"d": False}
        GEN = (-10, 1, -24)

        def pull(i):
            def fn(gg):
                what = fmap[i]
                pulled.add(i)
                w.fuses[i].enabled = False
                gg.audio.play("zap", vol=0.6 if what != "fence" else 1.0, pos=GEN, rng=30)
                if what == "fence":
                    gg.ui.flash((1, 0.95, 0.5), 0.4)
                    gg.audio.stop_loop("fence", 0.2)
                    gg.inv.remove("pliers")
                    gg.examine("A fat blue spark, a smell like burnt toast, and outside, the fence's ticking stops. "
                               "The pliers are welded open now. They died doing what they loved.")
                    done["d"] = True
                elif what == "shed":
                    w.set_lamp("shed", False)
                    gg.examine("Pop. The shed goes dark. Not the fence, then. Which leaves one.")
                else:
                    w.set_lamp("porch", False)
                    gg.examine("Pop. Nothing happens in here. Across the yard the porch light goes out, and somewhere "
                               "in the farmhouse a freezer stops humming.")
                    if not self.done("chuck_up"):
                        g.runner.start(self._chuck_fixes_house(lambda: pulled.discard(i)), name="chuck_fix",
                                       tag="day")
            return fn

        def bare(gg):
            gg.audio.play("zap", vol=0.5, pitch=1.6, pos=GEN, rng=20)
            gg.ui.flash((1, 0.95, 0.5), 0.15)
            gg.examine("You put your lips near it. It bites back. Your whole face is buzzing. Something insulated, "
                       "then: the pliers from Chuck's toolbox would do it.")
        for i in range(3):
            g.on(f"fuse_{i}", "Pull the fuse with the pliers", pull(i),
                 cond=lambda gg, i=i: gg.inv.has("pliers") and i not in pulled)
            g.on(f"fuse_{i}", "Pull the fuse", bare, cond=lambda gg, i=i: not gg.inv.has("pliers") and i not in pulled)
            g.on(f"fuse_{i}", "Look at the empty socket", lambda gg: gg.examine("An empty socket where a fuse was."),
                 cond=lambda gg, i=i: i in pulled)

        def caught_back():
            self.return_to_pasture()
            if self.done("chuck_up"):
                f.set_routine(SUNDAY_PATROL)
            else:
                f.sleep(BED_SLEEP, 180, getup=BED_GETUP)
            return True
        self.hook("after_caught", caught_back)
        self.hook("caught_line", lambda: random.choice(SUNDAY_CAUGHT) if self.done("chuck_up") else
                  "Hnnh? Not today, forty-seven. Today's your big day. Go get marinated.")
        yield lambda: done["d"]
        g.complete("fuse")
        yield from g.talk([("narrator", "The fence ticks once more, then goes quiet. Somewhere, forty-eight cows "
                                        "lean on it at the same time, just to see.")])
        yield 1.0
        if self.done("chuck_up"):
            f.say("Fence just went quiet. Why'd the fence go QUIET?", force=True)
        else:
            self.chuck_sunday()

    def _chuck_fixes_house(self, refit):
        """The wrong fuse: no power, no freezer. Chuck's up and straight out to the shed to put it back."""
        g = self.g
        f = g.farmer
        w = g.world
        yield 2.0
        self.chuck_sunday("power")
        fix = [("go", (56, HOUSE_Y, 32.0), 2.8), ("go", (40, 0, 18), 2.8), ("go", (14, 0, -14), 2.8),
               ("go", (-2, 0, -22), 2.6), ("go", (-8.2, 0, -24.6), 2.2), ("face", (-8.7, -26)),
               ("say", "There's my problem. Who PULLS a FUSE?"), ("wait", 2.5, "work", None, (-8.7, -26))]
        f.set_routine(fix + SUNDAY_PATROL[6:])
        # once he's done the fixing, the porch light and the freezer come back
        yield lambda: f.state == "routine" and f.r_i >= len(fix)
        for i, what in enumerate(self.flags["fuse_map"]):
            if what == "house":
                w.fuses[i].enabled = True
        refit()
        w.set_lamp("porch", True)
        if f.state == "routine" and len(f.routine) == len(fix) + len(SUNDAY_PATROL) - 6:
            f.set_routine(SUNDAY_PATROL, start=6)      # carry on round the yard (not back to the shed again)
        f.say("And STAY in there.", force=False)

    def chuck_sunday(self, why="fence"):
        """The fence alarm (or the freezer) gets Chuck up: underwear, flashlight, looking for why."""
        g = self.g
        f = g.farmer
        f.wake()
        f.set_visible(True)
        f.teleport(BED_GETUP, 180)
        f.set_outfit("underwear")
        f.set_tool(None)
        f.flashlight = True
        f.range_day = 36.0      # dawn half-light
        f.set_routine(SUNDAY_PATROL)
        f.say("...Power's out? The POWER'S out. The FREEZER. THE BRISKET!" if why == "power" else
              "...beep... beep... Is that the FENCE alarm? Who touches a fence at SIX in the MORNIN'?", force=True)
        g.audio.play("dun_dun", vol=0.5)
        self.setf("chuck_up")

    def d7_tractor(self):
        g = self.g
        f = g.farmer
        w = g.world
        p = g.player
        if not self.done("chuck_up"):
            self.chuck_sunday()
        self.hook("caught_line", lambda: random.choice(SUNDAY_CAUGHT))

        def after():
            self.return_to_pasture()
            return True
        self.hook("after_caught", after)
        home = (w.tractor.x, w.tractor.z, w.tractor.rotation_y)
        started = {"d": False}

        g.on("tractor", "Look at the tractor", lambda gg: gg.examine(
            "The seat's up there and you're a cow. Cows don't climb. Cows do, however, fall."),
             cond=lambda gg: gg.inv.has("tractor_key") and not started["d"])
        g.on("tractor", "Look at the tractor", lambda gg: gg.examine(
            "No key, no tractor. You can't hotwire it: you're a cow."),
             cond=lambda gg: not gg.inv.has("tractor_key"))

        def landing(dt):
            # dropped onto the tractor from the hayloft: that's you in the seat
            if not started["d"] and g.inv.has("tractor_key") and self.on_tractor():
                started["d"] = True
                g.ui.popup_sub("You land in the seat. Mostly. Hooves on the pedals, chin on the wheel, and the key "
                               "goes in.", 4)
            self.base_update(dt)
        smashed = {"barn": False, "main": False}
        while True:
            started["d"] = False
            self.objectives(("start", "Get into the tractor"))
            self.mark((22, 1, "Barn"))
            self.hook("update", landing)
            yield lambda: started["d"]
            g.complete("start")
            tr = Tractor(g, w.tractor, on_smash=lambda name: smashed.__setitem__(name, True))
            tr.smashables = [("barn", [w.doors["barn_left"], w.doors["barn_right"]]),
                             ("main", [w.doors["main_left"], w.doors["main_right"]])]
            tr.x, tr.z, tr.yaw = w.tractor.x, w.tractor.z, w.tractor.rotation_y
            tr.enter()
            self.unlock_music()
            self.lock_hud_music("music_boss", 0.5, 2.0)
            g.restricted_fn = lambda gg: False
            # he drops whatever he was doing and comes for his tractor
            f.wake()
            f.flashlight = True
            f.scripted()
            f.set_tool("pitchfork")
            f.say("WHO'S TOUCHIN' MY TRACTOR?!", force=True)
            if not self.flags.get("_drove"):
                self.flags["_drove"] = True
                g.ui.popup_sub("W/S throttle   A/D steer   Mouse look. Through the barn doors!", 7)
            self.objectives(("drive", "Drive through the main gate"))
            self.mark((0, 86, "Main gate"))
            ch = {"t": 0.0, "grab": 0.0, "got": False}

            def chase(dt):
                self.base_update(dt)
                d = math.hypot(f.x - tr.x, f.z - tr.z)
                if f.state == "scripted" and d < 2.7 and abs(tr.speed) > 3.0:
                    # he dives out of the way, and the ground comes up to meet him
                    f._pre_fall = "scripted"
                    f.state = "fallen"
                    f.fall_timer = 2.4
                    f.path_saved = []
                    f.path = []
                    f.pose = "fallen"
                    f.say(random.choice(DIVE_LINES), kind="surprise", force=True)
                    g.audio.play("thump", vol=0.9, pos=(f.x, 0.5, f.z), rng=30)
                    g.stats["chuck_trips"] = g.stats.get("chuck_trips", 0) + 1
                    g.event("chuck_trip")
                    return
                if f.state != "scripted":
                    return
                if d < 2.4 and abs(tr.speed) < 1.0:
                    ch["grab"] += dt
                    if ch["grab"] > 1.0:
                        ch["got"] = (tr.x, tr.z, f.x, f.z)
                else:
                    ch["grab"] = max(0.0, ch["grab"] - dt)
                ch["t"] -= dt
                if ch["t"] <= 0:
                    ch["t"] = 0.5
                    # run for where the tractor is about to be
                    yr = math.radians(tr.yaw)
                    lead = min(7.0, abs(tr.speed) * 0.8)
                    f.goto((tr.x + math.sin(yr) * lead, 0, tr.z + math.cos(yr) * lead), 4.3)
            self.hook("update", chase)
            yield lambda: smashed["main"] or ch["got"]
            if smashed["main"]:
                break
            # stalled next to him: he hauls you off by the ear, and it's back to the pasture
            self.flags["_grab"] = tuple(round(v, 1) for v in ch["got"])
            self.hook("update", self.base_update)
            g.cutscene_start(letterbox=True)
            tr.speed = 0.0
            f.path = []
            f.face_target = (tr.x, tr.z)
            f.pose = "point"
            f.say("GOTCHA! Off my TRACTOR!", force=True)
            g.audio.play("alert", vol=1.0)
            yield 1.4
            yield from g.fade_out(0.8)
            tr.leave()
            self.place_tractor(*home)
            g.restricted_fn = None
            self.unlock_music()
            self.lock_hud_music("music_stealth", 0.6, 1.0)
            self.return_to_pasture()
            f.set_tool(None)
            f.set_routine(SUNDAY_PATROL)
            g.stats["caught"] = g.stats.get("caught", 0) + 1
            yield from g.fade_in(0.8)
            g.cutscene_end_now()
            g.examine("Chuck dragged you off the seat by the ear and marched you back to the pasture. He's still out "
                      "there, in his underwear, looking for whoever did this.")
        self.hook("update", self.base_update)
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
        yield from g.talk([("sirloin", "OUT OF MY SUNLIGHT, CHUCK! ALL OF IT! FOREVER!")])
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
        # side on, so you see both of them squaring up (it used to sit at your ear, which hid you)
        g.player.teleport(0, 0, 71, 180)
        g.cam_set((5.6, 1.7, 70.2), (0.8, 1.2, 68.6))
        lines = [
            ("chuck", "NOBODY'S LEAVIN'! Not you, not the herd, not NOBODY!"),
            ("chuck", "I raised you from a calf! I bottle-fed you! You BIT me! I had to get a SHOT!"),
            ("chuck", "You know how much you're worth? Per POUND? I got a spreadsheet!"),
            ("you", "Moo. (Lean trim, up four cents. We heard. The cow who worked it out, you put on a truck.)"),
        ]
        if g.inv.has("shotgun"):
            lines.append(("chuck", "And where's Ol' Bessie? Somebody's been in my... is that... A COW? WITH MY "
                                   "SHOTGUN?"))
            if g.inv.count("shells"):
                lines.append(("chuck", "Is she LOADED? Where'd you get SHELLS? Those were up the deer stand! I hid "
                                       "those from MYSELF!"))
            else:
                lines.append(("chuck", "HA! Joke's on you, she ain't loaded! Shells are up the deer stand where "
                                       "nobody'd... why do I keep TELLIN' people that?"))
        lines += [
            ("chuck", "What're you MOOIN' at me for?! Over my dead body!"),
            ("you", "Moo. (That's the other way this goes, yes.)"),
        ]
        yield from g.talk(lines)
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
        # whatever shells you've found (or bought) for Ol' Bessie
        p.health = p.max_health
        start_shells = g.inv.count("shells") if g.inv.has("shotgun") else 0
        g.ui.set_boss("CHUCK", 1.0)
        g.ui.set_health(p.health, p.max_health, True)
        bessie = f"   Q fire Ol' Bessie ({start_shells} shell{'s' if start_shells != 1 else ''})" if start_shells else ""
        g.ui.popup_sub("Left click headbutt   Right click kick   Q throw / fire" + bessie +
                       "\nHit him when he's stuck or winded", 8)
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
                        g.ui.bark_line("Without my bucket I am naked before the world! I'm staying here!", "Moogenes")
            if res["lost"]:
                # knocked out: the whole fight starts again (Chuck back to full, your shells back)
                res["lost"] = False
                g.cutscene_start(letterbox=True)
                yield from g.fade_out(0.6)
                boss.remove()
                boss.hp = boss.MAX_HP
                boss.phase = 1
                boss.throws = 0
                boss.state = "approach"
                boss.t = 2.0
                allies.update(cluck_t=14.0, loin_t=24.0)
                have = g.inv.count("shells")
                if have < start_shells:
                    g.inv.add("shells", start_shells - have, silent=True)
                f.teleport((1.5, 0, 66), 180)
                f.pose = "idle"
                p.teleport(0, 0, 76, 180)
                p.health = p.max_health
                g.ui.set_boss("CHUCK", 1.0)
                yield from g.fade_in(0.6)
                g.cutscene_end_now()
                f.say("Had enough? 'Cause I'm just gettin' STARTED.", force=True)
                g.ui.popup_sub("Round two. From the top.", 3)
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
            g.ui.popup_sub("Moocrates kicks your old cowbell into the dirt in front of him.", 3)
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
        g.event("chuck_trip")
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
            ("chuck", "Okay. Okay. Easy, now. You're... you're just a cow."),
            ("chuck", "Cows don't know how to work a shotgun. Right? Cows don't THINK. That's the whole... that's "
                      "the whole deal. That's why it's okay."),
            ("you", "Moo. (We've done nothing but think all week, Chuck. By your own rule, you owe us. Stay down and "
                    "we'll call it even.)"),
        ])
        g.cutscene_end_now()
        g.cutscene_start(letterbox=True)
        g.player.frozen = True
        p.look_at_point((f.x, 0.5, f.z))
        if g.inv.count("shells"):
            # the bonus ending: you found the shells, and you kept one
            yield from g.talk([("you", "Moo. (Well done, Chuck.)")])
            g.inv.remove("shells")
            g.audio.play("shotgun", vol=1.0)
            g.ui.set_fade(1.0, (1, 1, 1))
            g.audio.stop_everything()
            self.setf("chuck_shot")
            g.event("chuck_shot")
            yield 2.5
        else:
            g.audio.play("blip_lo", vol=0.8)
            yield 0.6
            yield from g.talk([
                ("chuck", "...Click. Told ya. She ain't loaded."),
                ("you", "Moo. (Then you get to live, Chuck. And think about it. Ask any of us: that's the hard part.)"),
            ])
            g.ui.set_fade(1.0, (0, 0, 0))
            yield 2.0
        f.set_visible(False)
        g.player.frozen = False
        self.setf("chuck_done")

    def _cluck_attack(self, boss):
        g = self.g
        f = g.farmer
        cl = models.RoosterModel(headband=True, scale=1.6, position=(f.x - 8, 0, f.z + 3))
        self.fx.append(_Temp(cl))
        g.audio.play("squawk", vol=1.0, pos=(f.x, 1, f.z), rng=60)
        g.ui.bark_line("BAWK! GET OFF MY FARM!", "Cluckydides")
        for k in range(24):
            cl.position = (f.x - 8 + k / 24 * 7.6, abs(math.sin(k / 24 * math.pi)) * 1.5, f.z + 3 - k / 24 * 2.8)
            cl.rotation = (0, math.degrees(math.atan2(f.x - cl.x, f.z - cl.z)), 0)
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
        g.ui.bark_line("FOR THE PASTURE!", "Moogenes")
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
        g.event("chuck_trip")
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
        sl = models.CowModel(hide="hide_red", bull=True, acc=("lantern",) + (("bucket",) if self.done("sq_helm") else ()),
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
        # side by side on the hill (she used to stand 1.6 m behind you along the way you both face: half inside you)
        sx_, sz_ = math.cos(math.radians(300)), -math.sin(math.radians(300))
        cw.position = (hx - sx_ * 1.7, terrain_h(hx - sx_ * 1.7, hz - sz_ * 1.7), hz - sz_ * 1.7)
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
            ("cowleen", "A whole herd on a public road. Nobody's counting us."),
            ("cowleen", "So. Where are we going, Moodysseus?"),
        ])
        self.flags["renamed"] = True
        yield from g.talk([
            ("you", "Moo. (You said my name.)"),
            ("cowleen", "It's a long walk. I wasn't going to say 'Forty-Seven' all the way there."),
            ("you", "Moo. (Somewhere without a barbecue.)"),
            ("cowleen", "Moothagoras made a list."),
            ("cowpernicus", "It's a short list. It's India."),
            ("sirloin", "DO THEY HAVE BUCKETS IN INDIA?"),
            ("cowpernicus", "Everywhere has buck—"),
        ])
        # hard cut to black, mid-argument; the music carries on under the epilogue
        g.ui.set_fade(1.0, (0, 0, 0))
        self.hooks.pop("update", None)
        for e in ents:
            destroy(e)
        yield 1.5
        yield from self.epilogue()
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
THU   truck: #12 -> Happy Acres
FRI   BOWLING W/ THE BOYS!!!
SAT   sharpen knives
SUN   #47 -> BBQ w/ Dale!!!
        (do it myself, save $$)
        buy charcoal"""

HOOFPRINTS = """His circles by the pond, pressed into the mud one hoof at a time: a circle, a shape with ninety-six sides inside it, another outside it, and two fractions underneath.

3 10/71  <  round / across  <  3 1/7

In the corner, smaller, pressed in on Monday: a 12, rubbed out with a hoof, and next to it, 'not this week. Fence first.'

Somebody has stepped in the middle of the circle. It was Moogenes. He says it's a critique."""

# Chuck's inbox: (sender, subject, body)
EMAILS = [
    ("Dale", "sunday!!!",
     "Chuck buddy. Can't wait for Sunday. I'm bringing the good potato salad, not the one from the store. Also my "
     "new apron. It says KISS THE COOK. Nobody has.\n\nRe: the other thing. We're agreed. After the BBQ I take the "
     "rest of the herd off your hands, all of 'em, before the end of the month. My cousin at the plant says he'll "
     "do us a fair price. He says \"fair\" like it's a joke.\n\n- Dale"),
    ("Happy Acres Processing", "Pickup confirmation",
     "Thursday pickup confirmed: 1 head (#12).\n\nThank you for your business.\n\nRate your experience: "
     ":)  :|  :("),
    ("Mom", "(no subject)",
     "Charles, are you eating vegetables. Call your mother. Dale calls me more than you do. DALE. Think about "
     "that."),
]

SPREADSHEET = """COWS.XLS

#12 .............. Thursday ......... DONE
#47 .............. Sunday (BBQ)
everybody else .... Dale, end of month

Total: $$$ (ask Dale's cousin)"""

LEDGER = """SOURCE: CHUCK (FARM)

DATE    TAG    LIVE WT    GRADE     NOTES
01/12   #31    1,310      Choice
01/26   #8     1,265      Select
02/09   #22    1,340      Choice
02/23   #5     1,190      Select
03/09   #40    1,405      Prime     good one
03/23   #17    1,280      Choice
04/06   #29    1,350      Choice
04/20   #44    1,225      Select    limped
05/04   #36    1,300      Choice
05/18   #11    1,370      Choice
06/01   #26    1,290      Choice
THU     #12    1,190      -         lean trim
EOM     'the rest' - see Dale's cousin

There are columns for the date, the number, the weight
and the grade. There isn't a column for anything else."""

DALE_REPLY = """TO: Dale
RE: sunday!!!

Dale, BBQ's off. I've gone vegetarian. Also I've always hated your potato salad. It has raisins in it, Dale. RAISINS. Don't call.
- Chuck

[Sent]"""


# ----------------------------------------------------------------------
# idle conversations: day -> friend -> list of conversations
# (a conversation is a list of lines; bare strings are said by that friend)
# ----------------------------------------------------------------------
CHATTER = {
    0: {
        "cowleen": [["Keep your head down and your ears up. Chuck can't read faces, but he can read rumps."],
                    ["I know that I don't know very much. That's one more thing than Chuck knows."]],
        "moozart": [["Give me a place to stand, Moodysseus. That's all anybody needs. Chuck's spent his life making "
                     "sure we haven't got one."]],
        "sirloin": [["I live like a dog. I eat in public, I sleep where I drop, and I bark at authority. The authority "
                     "is mostly the fence."]],
        "cowpernicus": [["Press Tab for your journal. Writing things down is how you find out you were wrong in a "
                         "way you can check."]],
        "mooriarty": [["Pleasure is the absence of pain. Clovers are the presence of clovers. I deal in both."]],
        "moomaw": [["Ajax won Best in Show in '09. Chuck cried. Said it was the best day of his life. Six years later "
                    "he ate him. Everything flows, dear. Mostly into Chuck."]],
    },
    1: {
        "cowleen": [["The page. The oak. Go on, Forty-Seven."],
                    ["Tell the others, then the oak at sundown. And don't tell Echo. Echo repeats whatever she "
                     "heard last to whoever's nearest. She thinks 'Processing' is a spa, because Chuck said so."]],
        "moozart": [["Chuck counts us every night and loses his place around forty. He's never noticed. That's not "
                     "an insult. It's the most useful thing I know about him."]],
        "sirloin": [["A dog should be ready to die anywhere, I've always said. I assumed I'd get to pick the "
                     "anywhere."]],
        "cowpernicus": [["Fifty cows. Fifty is the sum of two squares in two different ways. A very stable number. "
                         "Chuck makes it less stable every other Thursday."]],
        "mooriarty": [["Sunday, huh? Death is nothing to us, Forty-Seven. It's the Saturday I'd worry about. "
                       "That's when he marinates."]],
        "moomaw": [["Chuck never hurt a fly, you know. Flies aren't on the menu. That's his whole ethics: the menu."],
                   ["Ajax won Best in Show in '09. Chuck cried. Said it was the best day of his life. He kept the "
                    "ribbon, and then he kept Ajax, in the freezer. Chuck's a keeper."]],
    },
    2: {
        "cowleen": [["He does the feed run, then revs the tractor. Over and over. It's the most intimate "
                     "relationship on the farm and it's with an engine."],
                    ["I've watched him leave that gate open a thousand times and never once thought it was for me. "
                     "I'm still not sure it is."]],
        "moozart": [["The radio, if you find it. I want the farm report. Chuck's world is mostly prices, and I'd like "
                     "to see it the way he does."]],
        "sirloin": [["If there's a bucket in that shed, I want it. A dog needs a house nobody can sell. I've checked "
                     "the market. Nobody sells buckets with dogs in them."]],
        "cowpernicus": [["The toolbox has a three-digit lock. Humans write their codes down. A species that invented "
                         "cryptography and then wrote the key next to the lock."],
                        ["I don't eat beans. Beans have souls. The herd says grass has souls too. I've asked the "
                         "grass. It hasn't objected."]],
        "mooriarty": [["The loose board on the back of the shed? I loosened it. Years ago. You plan for "
                       "opportunities that don't exist yet. It's the only kind of planning that's any fun."]],
        "moomaw": [["You're so quiet without that bell. It's nice. A bell is a leash that sings."],
                   ["Ajax won Best in Show in '09. Chuck cried. Said it was the best day of his life. He still "
                    "says it, every time he's had a beer. Usually to Ajax's photo."]],
    },
    3: {
        "cowleen": [["He's got a toothache. Slow and cranky. He naps on the porch around noon. Peak of "
                     "civilisation."],
                    ["Moogenes says it's custom. Epicowrus says it's harmless. Heifercleitus says it's a river. "
                     "Archimoodes says it's a mortgage. I'm the only one still asking, and I'm not sure I want the "
                     "answer."]],
        "moozart": [["Key, diesel, spark plug. Three things between us and a lever. That isn't many things."],
                    ["The mud? It's a look. I'm told it's very rustic."]],
        "sirloin": [["The rooster? I've fought the rooster. We agreed it was a draw. He did not agree. History is "
                     "written by whoever can reach the coop wall with a beak."]],
        "cowpernicus": [["Not your nose. Moogenes is the control group for 'nose'. Don't join him."]],
        "mooriarty": [["Rubber chicken's in stock. It squeaks, it flies, it insulates. It's the most useful object "
                       "on this farm, and it's a joke. Remember that about the world."]],
        "moomaw": [["Chuck's dentist is Dale's cousin. The one at the plant. Teeth and beef. Same tools, different "
                    "customer."],
                   ["Ajax won Best in Show in '09. Best day of Chuck's life, he says. Ajax didn't rank it. Ajax ate "
                    "the ribbon."]],
    },
    4: {
        "cowleen": [["Stay low. He can't see much in the rain. He can still see a black cow counting primes."],
                    ["If Archimoodes starts counting out loud, moo at him. He'll resent it. Resentment is quieter."]],
        "moozart": [["Two, three, five, seven, eleven... sorry. Habit. Lead on, Moodysseus."]],
        "sirloin": [["If the truck comes, I will stand in front of it. Probably. Adjacent to it. In its general "
                     "moral vicinity."]],
        "cowpernicus": [["Rain cuts his sight short. I measured. The error bars are also wet."]],
        "mooriarty": [["Truck's due at dusk. I know the driver's name. It doesn't help. Knowing a name has never "
                       "once stopped a truck."]],
        "moomaw": [["Go on, dear. Get him somewhere safe. And if there's nowhere safe, get him somewhere quiet."]],
    },
    5: {
        "cowleen": [["House. Spark plug. Computer. Back by dark. Don't sit on his couch. It remembers him."],
                    ["Last night was the first funeral this farm has ever had. This morning everyone's acting like "
                     "it was normal. It wasn't. It was the first normal thing we've ever done."]],
        "sirloin": [["I miss Archimoodes. He used to correct my logic until it was just silence. It was the most right "
                     "I've ever been."],
                    ["Chuck has a little tower in the corner by the gate. He sits up it to shoot deer. There are no "
                     "deer. I respect a man committed to a premise."]],
        "cowpernicus": [["Computers have passwords. Humans use the name of whatever they love most. Try his truck. "
                         "Or himself. Or the one thing on this farm he ever called a friend."],
                        ["Forty-nine now. Seven sevens. Chuck will still write fifty. I keep checking it, like it "
                         "might change."]],
        "mooriarty": [["Chuck keeps the spare key where everybody keeps a spare key. Security through assuming "
                       "nobody else has ever owned a doormat."],
                      ["Death is nothing to us. Still true. I've stopped selling it to cows, though. It was only ever "
                       "a comfort to the other side."]],
        "moomaw": [["If you're in the office, look for Ajax. He's the handsome one. Chuck's the one who looks like "
                    "a boiled ham that found religion."]],
    },
    6: {
        "cowleen": [["Plug, grid, herd. Then tonight, the shotgun. Then tomorrow, the part where it matters."],
                    ["Every SHING of that grinder is a cut of meat he's already picturing. I counted forty. I "
                     "stopped. Archimoodes wouldn't have."]],
        "sirloin": [["Tomorrow I charge. I've been practising on the trough. The trough has lost every time. It's "
                     "starting to feel unsporting."]],
        "cowpernicus": [["Three planks across the grid. Two and somebody breaks a leg. One and somebody breaks two. "
                         "Zero is just a hole with good intentions."]],
        "mooriarty": [["Bessie's no use empty. Chuck hid the shells from himself after the last barbecue. Where "
                       "does a man hide things from himself? Somewhere he swore he'd go and never does."]],
        "moomaw": [["Eleven years I said the river only runs one way. Then a black cow drew some circles in the "
                    "mud and walked onto a truck, and here we all are, standing in it. I'd like my eleven years "
                    "back."]],
    },
    7: {
        "cowleen": [["Go. We're right behind you. Well. Behind the fence. Then behind you."]],
        "sirloin": [["The fuse, Forty-Seven! Then the tractor! Then glory! Then possibly a nap!"]],
        "cowpernicus": [["Fuse, tractor, gate. In that order. He wrote it down. I've read it eleven times."]],
        "mooriarty": [["Don't look at me. Go. I was never here. Plausible deniability is a lifestyle."]],
        "moomaw": [["Go on, sweetheart. You can't step in the same river twice. You can absolutely drive through "
                    "the same gate once."]],
    },
}

RALLY_LINES = [
    "Moo! (Sunday at dawn? I'll be up. I haven't slept since the truck. Sleep is a luxury for the uneaten.)",
    "Moo. (Count me in. What are we doing? Doesn't matter. Anything is better than being an ingredient.)",
    "Moo! (The road! My whole family went down that road. In a truck. Facing backwards. I'll face forwards.)",
    "Moo. (Archimoodes once told me my circles were 'nearly round'. Best thing anyone's ever said to me. I'm "
    "coming.)",
    "Moo! (Tell Moogenes I'll follow him. Not too close. He swings his head about when he's being profound.)",
    "Moo. (I'll tell the others. Quietly. Not Echo. Echo has never had a thought she didn't hear first.)",
    "Moo! (The road. The actual road. Okay. Okay okay. I'm not scared. I'm recalibrating.)",
    "Moo. (Funny. Last week I'd have said the truck was just how things are. I don't know what I'd say now. That's "
    "new.)",
    "Moo. (Dale can eat his own potato salad. With the raisins. Alone. In the dark. Like he deserves.)",
]
