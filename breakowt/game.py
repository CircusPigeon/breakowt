"""The game: owns every system and exposes the scripting API used by the story."""
from __future__ import annotations

import json
import math
import random
import sys
import time as _time

from ursina import Button, Entity, Text, application, camera, color, destroy, mouse, scene, window
import time

from .engine.assets import SAVE_DIR, SHOT_DIR, tex, FONT_DIR
from .engine.audio import AudioManager
from .engine.physics import Physics
from .engine.script import ScriptRunner
from .engine.shading import Environment, FARM_SHADER
from .engine.meshbuilder import MeshBuilder
from .interact import Handler, InteractionSystem, Interactable
from .items import ITEMS, Inventory
from .npc import FRIENDS, HerdCow, Hen, NPCCow
from .farmer import Farmer
from .player import Player, THROWABLE
from .ui import UI, C, CREAM, BRASS, DIM
from .world import World, PASTURE, in_pond
from . import models

MOO_BUBBLES = {
    "sirloin": ["MOOOO.", "MOO!", "Moo, forsooth."],
    "moomaw": ["Mooo-oo", "Moo, dear.", "Mooo..."],
    "mooriarty": ["psst. moo.", "moo.", "...moo."],
    "cowpernicus": ["Moo (technically).", "Moo.", "Moo?"],
    "moozart": ["Mooo-oo", "Moo.", "Mooo..."],
    "cowleen": ["Moo.", "Moo!", "Moo?"],
}

CAUGHT_LINES = [
    "HEY! How'd you get out here?!",
    "Well, well, well. A cow. Out here. Doin' cow crimes.",
    "Oh no you don't. Back to the pasture, missy.",
    "Now how in the heck did you get through the fence? Again?",
    "Forty-seven! You're supposed to be relaxing! You got a big Sunday!",
    "Don't make me get the good rope.",
    "What are you, a cat? Get back in there.",
]
CAUGHT_AFTER = [
    "Chuck marched you back to the pasture. He's added 'fix fence' to his to-do list. Again.",
    "Chuck escorted you home with a long lecture about 'boundaries'. You understood every word.",
    "Back in the pasture. Chuck is counting fence posts, suspiciously.",
    "Chuck returned you to the pasture and gave you a little pat. You hated it.",
]


class Game(Entity):
    def __init__(self, args, fonts):
        super().__init__()
        self.args = args
        self.debug = getattr(args, "debug", False)
        self.fonts = fonts
        self.env = Environment()
        self.audio = AudioManager()
        self.phys = Physics()
        self.ia = InteractionSystem(self)
        self.runner = ScriptRunner()
        self.runner.on_error = self._script_error
        self.flags: dict = {}
        self.stats: dict = {}
        self.inv = Inventory(self)
        self.state = "loading"
        self.in_dialogue = False
        self.cutscene = False
        self.busy = False           # an interaction script is running
        self._advance = False
        self.noise_masks: list = []
        self.day = 0
        self.step_i = 0
        self.day_title = ""
        self.day_sub = ""
        self.objectives: list = []
        self.side_quests: dict = {}
        self.target = None
        self.cam_free = False
        self.enemies: list = []
        self.knockables: list = []
        self.vehicle = None
        self.hint_text = ""
        self.restricted_fn = None
        self.carrying = None
        self.herd_t = 0.0
        self.herd_i = 0
        self.clover_items: dict = {}
        self.music_zone = None
        self.fullscreen = not getattr(args, "windowed", False)
        self.ui = UI(self, fonts)
        self.world = World(self)
        self.player = Player(self)
        self.farmer = Farmer(self)
        self.cows = {k: NPCCow(self, k, (0, 0, 0)) for k in FRIENDS}
        self.herd: list[HerdCow] = []
        rnd = random.Random(47)
        for i in range(42):
            x0, x1, z0, z1 = PASTURE
            for _ in range(50):
                x, z = rnd.uniform(x0 + 3, x1 - 3), rnd.uniform(z0 + 3, z1 - 16)
                if not in_pond(x, z, 2) and not self.phys.blocked_at(x, z, 1.2) and math.hypot(x + 50, z + 35) > 4:
                    break
            self.herd.append(HerdCow(self, i, (x, z), rnd.uniform(0, 360)))
        self.hens = [Hen(self, (rnd.uniform(38, 46), rnd.uniform(-40, -34))) for _ in range(4)]
        self._build_knockables()
        from .story import Story
        self.story = Story(self)
        self.load_settings()
        self.refresh_hotbar()
        self.set_mouse(True)

    # ------------------------------------------------------------------
    # errors
    # ------------------------------------------------------------------
    def _script_error(self, s):
        print("SCRIPT ERROR in", s.name, "\n", s.error, file=sys.stderr)
        if self.debug:
            self.ui.popup_sub("Script error: see console", 5)
        self.in_dialogue = False
        self.ui.dlg_hide()
        if s.name == "story":
            # never leave the player stuck: release controls
            self.cutscene_end_now()

    # ------------------------------------------------------------------
    # knockable props (distractions)
    # ------------------------------------------------------------------
    def _build_knockables(self):
        spots = [("buckets", (-2.6, -26.5), "Stack of buckets"), ("milkcans", (14.5, -12.5), "Milk cans"),
                 ("feedbin", (33, -24.5), "Feed bin"), ("trashcan", (63.2, 29.0), "Trash can"),
                 ("milkcans2", (-15.5, -40), "Milk cans"), ("buckets2", (36.5, 3), "Stack of buckets"),
                 ("trashcan2", (70.5, 43), "Trash can")]
        for key, (x, z), name in spots:
            ent = Entity(position=(x, 0, z))
            mb = MeshBuilder()
            if "bucket" in key:
                for k in range(4):
                    mb.cylinder((0, k * 0.28, 0), 0.22, 0.3, color=models.METAL, segs=10, radius_top=0.26)
            elif "milk" in key:
                for k, (ox, oz) in enumerate([(0, 0), (0.45, 0.1), (0.2, 0.45)]):
                    mb.cylinder((ox, 0, oz), 0.2, 0.7, color=(0.8, 0.82, 0.85, 1), segs=10)
                    mb.cylinder((ox, 0.7, oz), 0.12, 0.15, color=(0.8, 0.82, 0.85, 1), segs=8)
            elif "trash" in key:
                mb.cylinder((0, 0, 0), 0.32, 0.9, color=(0.4, 0.45, 0.4, 1), segs=10)
                mb.cylinder((0, 0.9, 0), 0.35, 0.06, color=(0.35, 0.4, 0.35, 1), segs=10)
            else:
                mb.box((0, 0.45, 0), (0.9, 0.9, 0.7), color=(0.6, 0.5, 0.3, 1), uv_rect=models.WHITE)
            Entity(parent=ent, model=mb.build(solid_rect=models.WHITE), texture=tex("atlas"), shader=FARM_SHADER)
            col = self.phys.add_circle(x, z, 0.45, 0, 1.0, sight=False)
            ia = self.ia.add(Interactable(f"knock_{key}", (x, 0.6, z), 0.6, name, None, "Knock over", 2.4))
            k = {"key": key, "ent": ent, "col": col, "ia": ia, "down": False, "t": 0.0, "x": x, "z": z}
            ia.handlers.append(Handler("Knock over (noisy!)", lambda g, k=k: g.knock(k), lambda g, k=k: not k["down"],
                                       scope="global"))
            ia.on_headbutt = lambda g, k=k: g.knock(k)
            ia.on_rock = lambda g, p, k=k: g.knock(k)
            self.knockables.append(k)

    def knock(self, k):
        if k["down"]:
            return
        k["down"] = True
        k["t"] = 45.0
        k["ent"].animate_rotation((0, random.uniform(0, 360), 88), duration=0.35)
        self.audio.play("crash", vol=1.0, pos=(k["x"], 0.5, k["z"]), rng=60)
        self.noise((k["x"], 0.5, k["z"]), 22, source="crash")
        self.stats["knocked"] = self.stats.get("knocked", 0) + 1

    def _update_knockables(self, dt):
        for k in self.knockables:
            if k["down"]:
                k["t"] -= dt
                if k["t"] <= 0:
                    d = math.hypot(self.player.x - k["x"], self.player.z - k["z"])
                    if d > 12:
                        k["down"] = False
                        k["ent"].rotation = (0, 0, 0)

    # ------------------------------------------------------------------
    # mouse / window
    # ------------------------------------------------------------------
    def set_mouse(self, locked):
        mouse.locked = locked
        mouse.visible = not locked

    def controls_enabled(self):
        return (self.state == "play" and not self.in_dialogue and not self.cutscene and self.ui.modal is None
                and not self.cam_free)

    def toggle_fullscreen(self):
        from .engine.boot import screen_size
        from panda3d.core import WindowProperties
        self.fullscreen = not self.fullscreen
        sw, sh = screen_size()
        props = WindowProperties()
        if self.fullscreen:
            props.setUndecorated(True)
            props.setSize(sw, sh)
            props.setOrigin(0, 0)
        else:
            w, h = int(sw * 0.75), int(sh * 0.75)
            props.setUndecorated(False)
            props.setSize(w, h)
            props.setOrigin((sw - w) // 2, (sh - h) // 2)
        application.base.win.requestProperties(props)

    def screenshot(self):
        from .engine.boot import screenshot
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        p = SHOT_DIR / f"breakowt_{_time.strftime('%Y%m%d_%H%M%S')}.png"
        screenshot(str(p))
        self.ui.toast("Screenshot saved")

    # ------------------------------------------------------------------
    # settings / saves
    # ------------------------------------------------------------------
    def save_settings(self):
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            d = {"volumes": self.audio.volumes, "sens": self.player.sensitivity, "invert": self.player.invert_y,
                 "shadows": self.env.shadows}
            (SAVE_DIR / "settings.json").write_text(json.dumps(d, indent=1))
        except OSError:
            pass

    def load_settings(self):
        try:
            d = json.loads((SAVE_DIR / "settings.json").read_text())
            self.audio.volumes.update(d.get("volumes", {}))
            self.player.sensitivity = d.get("sens", 1.0)
            self.player.invert_y = d.get("invert", False)
            if not d.get("shadows", True):
                self.env.set_shadows(False)
        except (OSError, ValueError):
            pass

    def save_checkpoint(self):
        prev = self.load_save() or {}
        d = {"day": self.day, "step": self.step_i, "flags": self.flags, "stats": self.stats,
             "inv": self.inv.to_dict(), "bell": self.player.has_bell,
             "max_day": max(self.day, prev.get("max_day", 1))}
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            (SAVE_DIR / "save.json").write_text(json.dumps(d, indent=1, default=list))
        except OSError:
            pass

    def load_save(self):
        try:
            return json.loads((SAVE_DIR / "save.json").read_text())
        except (OSError, ValueError):
            return None

    def apply_save(self, d):
        self.flags = dict(d.get("flags", {}))
        self.stats = dict(d.get("stats", {}))
        self.inv.from_dict(d.get("inv", {}))
        self.player.has_bell = d.get("bell", True)
        self.refresh_hotbar()

    # ------------------------------------------------------------------
    # queries used by AI
    # ------------------------------------------------------------------
    def player_restricted(self):
        p = self.player
        if self.restricted_fn is not None:
            r = self.restricted_fn(self)
            if r is not None:
                return r
        if self.phys.in_zone("pasture", p.x, p.z):
            return False
        return True

    def player_hidden(self):
        p = self.player
        if self.flags.get("_hiding"):
            return True
        for zn in self.phys.zones:
            if zn.name == "hide" and zn.contains(p.x, p.z, p.y):
                if zn.data.get("kind") == "hay":
                    return True
                return p.crouching
        return False

    def player_lit(self):
        p = self.player
        for L in self.world.lamps.values():
            if L["on"]:
                lx, ly, lz = L["pos"]
                if math.dist((lx, lz), (p.x, p.z)) < L["radius"] * 0.6 and abs(ly - p.y) < 5:
                    return True
        return False

    def noise(self, pos, radius, source="misc"):
        if self.farmer is not None:
            self.farmer.hear(pos, radius, source)
        self.story.on_noise(pos, radius, source)

    def mask_noise(self, key, pos, radius, until_fn):
        self.noise_masks = [m for m in self.noise_masks if m[0] != key]
        self.noise_masks.append((key, pos, radius, until_fn))

    def noise_masked(self, pos):
        for key, mp, r, fn in self.noise_masks:
            try:
                if fn() and math.dist((mp[0], mp[2]), (pos[0], pos[2])) < r:
                    return True
            except Exception:
                pass
        return False

    def carry_slow(self):
        if self.inv.selected() == "plank":
            return 0.8
        return 1.0

    # ------------------------------------------------------------------
    # inventory / HUD
    # ------------------------------------------------------------------
    def refresh_hotbar(self):
        keys = self.inv.hotbar_keys()
        entries = [(k, ITEMS[k][2], self.inv.count(k), ITEMS[k][0]) for k in keys]
        self.ui.set_hotbar(entries, self.inv.sel if keys else -1, self.flags.get("clovers", 0))
        sel = self.inv.selected()
        self.player.hold(sel)

    def objective_lines(self):
        return [(o["text"], o["done"]) for o in self.objectives]

    def side_quest_lines(self):
        return [(q["text"], q["state"]) for q in self.side_quests.values() if q["state"] != "hidden"]

    def inventory_lines(self):
        return [(k, ITEMS[k][0], self.inv.count(k), ITEMS[k][1]) for k in self.inv.order if k in ITEMS]

    def map_markers(self):
        out = list(self.story.markers())
        if self.flags.get("star_chart"):
            for i, it in self.clover_items.items():
                if it is not None:
                    p = self.world.clover_spots[i]
                    out.append((p[0], p[2], "clover"))
        return out

    def set_objectives(self, objs):
        self.objectives = [{"key": k, "text": t, "done": False} for k, t in objs]
        self.ui.set_objectives(self.objective_lines())

    def add_objective(self, key, text):
        self.objectives.append({"key": key, "text": text, "done": False})
        self.ui.set_objectives(self.objective_lines())

    def complete(self, key, sound=True):
        for o in self.objectives:
            if o["key"] == key and not o["done"]:
                o["done"] = True
                if sound:
                    self.audio.play("ding", vol=0.6)
        self.ui.set_objectives(self.objective_lines())

    def is_done(self, key):
        return any(o["key"] == key and o["done"] for o in self.objectives)

    def side_quest(self, key, text=None, state=None):
        q = self.side_quests.setdefault(key, {"text": text or key, "state": "hidden"})
        if text:
            q["text"] = text
        if state:
            old = q["state"]
            q["state"] = state
            if state == "active" and old == "hidden":
                self.ui.toast("New favor: " + q["text"], col=BRASS)
            if state == "done" and old != "done":
                self.ui.toast("Favor complete!", col=C(0.5, 0.9, 0.45, 1))
                self.audio.play("ding", vol=0.6)
        self.flags.setdefault("_sq", {})[key] = q

    def notify(self, text, icon=None):
        self.ui.toast(text, icon)

    def examine(self, text):
        self.ui.popup_sub(text)

    # ------------------------------------------------------------------
    # interaction handlers
    # ------------------------------------------------------------------
    def on(self, key, prompt, action, cond=None, scope="step"):
        ia = self.ia.get(key)
        if ia is None:
            print("WARN: no interactable", key, file=sys.stderr)
            return
        ia.handlers.append(Handler(prompt, action, cond, scope))

    def interact(self, ia):
        h = ia.active_handler(self)
        if h is not None:
            res = h.action(self)
            if hasattr(res, "__next__"):
                self.busy = True
                s = self.runner.start(self._wrap_busy(res), name="interact")
            return
        if ia.key.startswith("cow_"):
            self.busy = True
            self.runner.start(self._wrap_busy(self.story.default_talk(ia.key[4:])), name="interact")
            return
        if ia.key.startswith("herd_"):
            idx = int(ia.key.split("_")[1])
            self.busy = True
            self.runner.start(self._wrap_busy(self.story.herd_talk(self.herd[idx])), name="interact")
            return
        if ia.key.startswith("rockpile"):
            self.take_rock()
            return
        if ia.key.startswith("clover_"):
            self.pick_clover(int(ia.key.split("_")[1]))
            return
        if ia.text:
            lines = ia.text if isinstance(ia.text, list) else [ia.text]
            self.examine(lines[ia.text_i % len(lines)])
            ia.text_i += 1
            return
        self.examine(f"It's a {ia.name.lower()}. You stare at it, as cows do.")

    def _wrap_busy(self, gen):
        try:
            result = yield from gen
        finally:
            self.busy = False
        return result

    def take_rock(self):
        cap = 6 if self.flags.get("rock_pouch") else 3
        if self.inv.count("rock") >= cap:
            self.examine(f"You can only carry {cap} rocks in your mouth. It's a big mouth, but still.")
            return
        self.inv.add("rock", 1, silent=True)
        self.inv.select_key("rock")
        self.audio.play("rock_land", vol=0.5, pitch=1.3)
        self.ui.toast(f"Rock ({self.inv.count('rock')}/{cap}) - [R] to throw", "rock")

    def place_clovers(self):
        got = set(self.flags.get("clover_got", []))
        for i, p in enumerate(self.world.clover_spots):
            key = f"clover_{i}"
            if i in got:
                self.clover_items[i] = None
                continue
            if key not in self.world.items:
                self.world.add_item(key, "clover", p, bob=True, spin=True, glow=0.6)
                self.ia.add(Interactable(key, p, 0.5, "Golden Clover", None, "Take the Golden Clover", 2.6))
            self.clover_items[i] = self.world.items[key]

    def pick_clover(self, i):
        got = set(self.flags.get("clover_got", []))
        got.add(i)
        self.flags["clover_got"] = sorted(got)
        self.flags["clovers"] = self.flags.get("clovers", 0) + 1
        self.flags["clovers_total"] = self.flags.get("clovers_total", 0) + 1
        self.world.remove_item(f"clover_{i}")
        self.ia.remove(f"clover_{i}")
        self.clover_items[i] = None
        self.audio.play("clover", vol=0.8)
        n = self.flags["clovers_total"]
        self.ui.toast(f"Golden Clover! ({n}/{len(self.world.clover_spots)})", "clover", col=BRASS)
        self.refresh_hotbar()

    def drop_item_at(self, kind, p):
        key = f"dropped_{kind}"
        gh, _ = self.phys.ground(p[0], p[2], p[1] + 0.5)
        pos = (p[0], gh + 0.12, p[2])
        self.world.add_item(key, kind, pos)
        ia = self.ia.get(key)
        if ia is None:
            ia = self.ia.add(Interactable(key, pos, 0.5, ITEMS[kind][0], None, "Pick up", 2.5))
            ia.handlers.append(Handler(f"Pick up {ITEMS[kind][0]}", lambda g, k=kind: g._pickup_dropped(k), scope="global"))
        ia.pos = pos
        ia.enabled = True

    def _pickup_dropped(self, kind):
        key = f"dropped_{kind}"
        self.world.remove_item(key)
        ia = self.ia.get(key)
        if ia:
            ia.enabled = False
        self.inv.add(kind, 1, silent=True)
        self.audio.play("blip", vol=0.5)

    # ------------------------------------------------------------------
    # combat hooks
    # ------------------------------------------------------------------
    def on_headbutt(self, eye, fwd, charge):
        hit = False
        for e in list(self.enemies):
            if e.alive and e.in_front(eye, fwd, 2.4):
                e.take_hit(2 if charge else 1, "headbutt", self.player.pos)
                hit = True
        if hit:
            self.audio.play("bonk", vol=0.8, pitch=random.uniform(0.9, 1.1))
            return True
        t = self.ia.find_target(eye, fwd)
        if t is not None and t.on_headbutt is not None:
            t.on_headbutt(self)
            return True
        res = self.story.on_headbutt(eye, fwd)
        if res:
            return True
        # walls
        p1 = (eye[0] + fwd[0] * 1.6, eye[1] + fwd[1] * 1.6, eye[2] + fwd[2] * 1.6)
        if self.phys.raycast(eye, p1, sight_only=False) is not None:
            self.noise(self.player.pos, 6, "headbutt")
            return True
        return False

    def on_kick(self, pos, yaw):
        hit = False
        for e in list(self.enemies):
            if e.alive and e.behind(pos, yaw, 2.8):
                e.take_hit(2, "kick", pos)
                hit = True
        return hit

    def on_projectile_move(self, proj, p0, p1):
        for e in list(self.enemies):
            if e.alive and e.segment_hit(p0, p1):
                e.take_hit(1, "rock", p0)
                return True
        for ia in self.ia.items.values():
            if ia.on_rock is not None and ia.enabled:
                px, py, pz = ia.world_pos()
                # distance from segment to point
                dx, dy, dz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
                L2 = dx * dx + dy * dy + dz * dz
                if L2 < 1e-9:
                    continue
                t = max(0, min(1, ((px - p0[0]) * dx + (py - p0[1]) * dy + (pz - p0[2]) * dz) / L2))
                cx, cy, cz = p0[0] + dx * t, p0[1] + dy * t, p0[2] + dz * t
                if (cx - px) ** 2 + (cy - py) ** 2 + (cz - pz) ** 2 < (ia.radius + 0.15) ** 2:
                    ia.on_rock(self, (cx, cy, cz))
                    return True
        return False

    def on_projectile_land(self, proj, p):
        self.story.on_projectile_land(proj, p)

    def on_player_moo(self):
        return self.story.on_player_moo()

    def on_player_defeated(self):
        self.story.on_player_defeated()

    def on_farmer_trip(self):
        pass

    # ------------------------------------------------------------------
    # caught
    # ------------------------------------------------------------------
    def on_caught(self, farmer):
        if self.runner.running("caught"):
            return
        if self.story.on_caught():
            return
        self.runner.start(self._caught_seq(farmer), name="caught")

    def _caught_seq(self, f):
        p = self.player
        if self.inv.has("horseshoe") and not self.flags.get("horseshoe_used"):
            self.flags["horseshoe_used"] = True
            self.inv.remove("horseshoe")
            self.audio.play("alert", vol=0.8)
            yield 0.5
            f.susp = 0.0
            f.set_marker("")
            f.state = "routine"
            f.trip()
            f.fall_timer = 5.0
            self.examine("Chuck lunges... and trips on Big Earl's lucky horseshoe! RUN!")
            return
        self.stats["caught"] = self.stats.get("caught", 0) + 1
        self.cutscene = True
        p.frozen = True
        self.audio.play("alert", vol=1.0)
        self.ui.flash((1, 0.2, 0.1), 0.5)
        f.face_target = (p.x, p.z)
        f.pose = "point"
        yield 0.4
        p.look_at_point((f.x, f.y + 1.6, f.z))
        line = self.story.caught_line() or random.choice(CAUGHT_LINES)
        f.say(line, force=True)
        yield 2.2
        yield from self.fade_out(0.8)
        self.audio.play("sad_trombone", vol=0.9)
        self.ui.set_center_text("CAUGHT", 1.0, (0.95, 0.35, 0.3))
        yield 2.4
        self.ui.set_center_text("")
        self.story.after_caught()
        f.susp = 0.0
        f.set_marker("")
        self.in_dialogue = False
        p.frozen = False
        self.cutscene = False
        yield from self.fade_in(0.8)
        self.examine(random.choice(CAUGHT_AFTER) + f"  (Caught: {self.stats['caught']})")

    # ------------------------------------------------------------------
    # scripting API (generators)
    # ------------------------------------------------------------------
    def wait(self, t):
        yield t

    def until(self, cond):
        yield cond

    def speaker(self, who):
        if who in self.cows:
            c = self.cows[who]
            return c.name, who, c
        if isinstance(who, HerdCow):
            return who.name, None, who
        if who in ("you", "player"):
            return "Forty-Seven", "player", None
        if who == "chuck":
            return "Chuck", "chuck", self.farmer
        if who == "cluck":
            return "Cluck Norris", "cluck", None
        if who == "narrator":
            return "", None, None
        return str(who), None, None

    def _voice(self, key, ent, text):
        kind = "question" if text.rstrip().endswith("?") else "exclaim" if text.rstrip().endswith("!") else (
            "short" if len(text) < 30 else "medium" if len(text) < 80 else "long")
        if key == "chuck":
            fk = "question" if kind == "question" else ("angry" if kind == "exclaim" else
                                                        "short" if kind == "short" else "medium" if kind == "medium" else "long")
            self.audio.play(f"farmer_{fk}_{random.randrange(2)}", vol=1.0, group="voice",
                            pitch=random.uniform(0.96, 1.04))
            return
        if key == "cluck":
            self.audio.play(random.choice(["cluck_0", "cluck_1", "squawk"]), vol=0.9, group="voice")
            return
        if key == "player":
            self.audio.play(f"moo_player_{kind}_{random.randrange(2)}", vol=0.85, group="voice",
                            pitch=random.uniform(0.95, 1.05))
            return
        if isinstance(ent, HerdCow):
            self.audio.play(ent.voice, vol=0.9, pitch=ent.pitch, group="voice")
            ent.bubble(random.choice(["Moo.", "Moo?", "Mooo."]) if kind != "exclaim" else "MOO!")
            return
        if key in FRIENDS:
            sad = "..." in text and kind != "exclaim"
            k2 = "sad" if (sad and key in ("moozart", "moomaw", "cowleen") and random.random() < 0.5) else kind
            self.audio.play(f"moo_{key}_{k2}_{random.randrange(2)}", vol=0.95, group="voice",
                            pitch=random.uniform(0.95, 1.05))
            b = random.choice(MOO_BUBBLES.get(key, ["Moo."]))
            if kind == "question":
                b = "Moo?"
            elif kind == "exclaim":
                b = "MOO!" if key != "sirloin" else "MOOOOO!"
            ent.bubble(b)

    def say(self, who, text, choices=None, auto=None, look=True):
        """Show one line. Returns the chosen index if choices are given."""
        name, vkey, ent = self.speaker(who)
        self.in_dialogue = True
        self._advance = False
        p = self.player
        if ent is not None and look and not self.cam_free:
            hx = ent.x
            hz = ent.z
            hy = (ent.y if hasattr(ent, "y") else 0) + (1.6 if who == "chuck" else 1.35)
            dx, dz = hx - p.x, hz - p.z
            want_yaw = math.degrees(math.atan2(dx, dz))
            want_pitch = -math.degrees(math.atan2(hy - (p.y + p.cam_y), max(0.5, math.hypot(dx, dz))))
            self._look_goal = (want_yaw, want_pitch)
        else:
            self._look_goal = None
        if ent is not None and hasattr(ent, "look"):
            ent.look = "player"
        self.ui.dlg_show(name, text)
        if vkey:
            self._voice(vkey, ent, text)
        if choices:
            yield lambda: self.ui.dlg_revealed()
            self.ui.show_choices(choices)
            self.set_mouse(False)
            yield lambda: self.ui.choice_result is not None
            res = self.ui.choice_result
            self.ui.clear_choices()
            self.set_mouse(True)
            self._advance = False
            return res
        if auto is not None:
            t0 = self.env.time
            yield lambda: self.ui.dlg_revealed() and (self._advance or self.env.time - t0 > auto + len(text) / 55)
        else:
            yield lambda: self._advance and self.ui.dlg_revealed()
        self._advance = False
        return None

    def talk(self, lines):
        """lines: list of (who, text) tuples. Returns the result of the last choice."""
        res = None
        for ln in lines:
            if ln is None:
                continue
            who, text = ln[0], ln[1]
            choices = ln[2] if len(ln) > 2 else None
            res = yield from self.say(who, text, choices)
        self.end_talk()
        return res

    def end_talk(self):
        self.in_dialogue = False
        self.ui.dlg_hide()
        self._look_goal = None

    def fade_out(self, dur=1.0, col=(0, 0, 0)):
        a0 = self.ui.fade_alpha
        t = 0.0
        while t < dur:
            t += time.dt
            self.ui.set_fade(a0 + (1 - a0) * min(1, t / dur), col)
            yield None
        self.ui.set_fade(1.0, col)

    def fade_in(self, dur=1.0):
        a0 = self.ui.fade_alpha
        col = self.ui.fade_col
        t = 0.0
        while t < dur:
            t += time.dt
            self.ui.set_fade(a0 * (1 - min(1, t / dur)), col)
            yield None
        self.ui.set_fade(0.0, col)

    def card(self, big, small="", dur=3.0, sting=True):
        if sting:
            self.audio.play("dun_dun", vol=0.9)
        t = 0.0
        while t < dur:
            t += time.dt
            a = min(1.0, t / 0.4, (dur - t) / 0.5)
            self.ui.title_card(big, small, max(0.0, a))
            yield None
        self.ui.title_card("", "", 0)

    def cutscene_start(self, letterbox=True):
        self.cutscene = True
        self.player.frozen = True
        self.ui.letterbox(letterbox)
        self.ui.show_hud(False)
        self.ui.set_prompt(None)

    def cutscene_end(self):
        self.cutscene_end_now()
        yield None

    def cutscene_end_now(self):
        self.cam_attach()
        self.cutscene = False
        self.player.frozen = False
        self.ui.letterbox(False)
        self.ui.show_hud(True)
        self.in_dialogue = False
        self.ui.dlg_hide()

    def cam_detach(self):
        if not self.cam_free:
            self.cam_free = True
            wp = camera.world_position
            wr = camera.world_rotation
            camera.parent = scene
            camera.position = wp
            camera.rotation = wr
            self.player.snout.enabled = False
            if self.player.held:
                self.player.held.enabled = False

    def cam_attach(self):
        if self.cam_free:
            self.cam_free = False
            camera.parent = self.player.head
            camera.position = (0, 0, 0)
            camera.rotation = (0, 0, 0)
            self.player.snout.enabled = True
            if self.player.held:
                self.player.held.enabled = True
            camera.fov = self.player.fov_base

    def cam_set(self, pos, look):
        self.cam_detach()
        camera.position = pos
        camera.look_at(look)

    def cam_move(self, pos, look, dur=2.0, look_to=None, ease=True):
        self.cam_detach()
        p0 = camera.position
        la0 = look
        la1 = look_to or look
        t = 0.0
        while t < dur:
            t += time.dt
            k = min(1.0, t / dur)
            if ease:
                k = k * k * (3 - 2 * k)
            camera.position = (p0[0] + (pos[0] - p0[0]) * k, p0[1] + (pos[1] - p0[1]) * k, p0[2] + (pos[2] - p0[2]) * k)
            camera.look_at((la0[0] + (la1[0] - la0[0]) * k, la0[1] + (la1[1] - la0[1]) * k, la0[2] + (la1[2] - la0[2]) * k))
            yield None

    def set_time(self, preset, dur=0.0):
        self.env.set_preset(preset, dur)

    def music(self, name, vol=1.0, fade=2.0):
        self.audio.music_play(name, vol, fade)

    def ambience(self, preset):
        a = self.audio
        if preset == "day":
            a.loop("amb", "loop_birds", 0.35)
            a.loop("wind", "loop_wind", 0.15)
            a.stop_loop("rain")
        elif preset == "night":
            a.loop("amb", "loop_crickets", 0.4)
            a.loop("wind", "loop_wind", 0.12)
            a.stop_loop("rain")
        elif preset == "rain":
            a.loop("amb", "loop_wind", 0.3)
            a.loop("rain", "loop_rain", 0.5)
            a.stop_loop("wind")
        elif preset == "none":
            a.stop_loop("amb")
            a.stop_loop("wind")
            a.stop_loop("rain")
        self.farm_ambience(preset)

    # places on the farm that make their own noise (positional, so they also help you find your way)
    EMITTERS = {
        # key: (sound, position, audible range, volume by preset {day, night, rain})
        "env_frogs": ("loop_frogs", (-45, 0.3, -60), 28, {"day": 0.25, "night": 0.6, "rain": 0.5}),
        "env_windmill": ("loop_windmill", (6, 9, 32), 40, {"day": 0.5, "night": 0.35, "rain": 0.55}),
        "env_chickens": ("loop_chickens", (42, 1, -33), 30, {"day": 0.6, "rain": 0.35}),
        "env_flies": ("loop_flies", (-30, 1, -22), 8, {"day": 0.45}),
        "env_pigeons": ("loop_pigeons", (20, 5.5, 10), 16, {"day": 0.5, "rain": 0.4}),
        "env_owl": ("loop_owl", (-62, 9, 30), 110, {"night": 0.4}),
        "env_clock": ("loop_clock", (45.2, 2.2, 36), 9, {"day": 0.4, "night": 0.45, "rain": 0.4}),
        "env_fridge": ("loop_fridge", (67, 1.3, 38.6), 6, {"day": 0.35, "night": 0.35, "rain": 0.35}),
    }

    def farm_ambience(self, preset):
        a = self.audio
        for key, (snd, pos, rng, vols) in self.EMITTERS.items():
            v = vols.get(preset)
            if preset != "none" and v:
                a.loop(key, snd, v, pos=pos, rng=rng, group="ambient", fade=2.0)
            else:
                a.stop_loop(key, 1.5)

    def teleport_player(self, spawn):
        sp = self.world.spawns.get(spawn, spawn) if isinstance(spawn, str) else spawn
        self.player.teleport(sp)

    # ------------------------------------------------------------------
    # main loop
    # ------------------------------------------------------------------
    def prune_entity_updates(self):
        """Ursina visits every entity each frame looking for update()/input(). Most of ours are
        static meshes; flag those so the engine skips them."""
        for e in scene.entities:
            if e.ignore or isinstance(e, Button):
                continue
            if hasattr(e, "update") or hasattr(e, "input") or getattr(e, "scripts", None):
                continue
            e.ignore = True

    def update(self):
        dt = min(time.dt, 0.05)
        self._prune_t = getattr(self, "_prune_t", 0.0) - dt
        if self._prune_t <= 0:
            self._prune_t = 1.5
            self.prune_entity_updates()
        if self.state == "loading":
            return
        self.ui.update(dt)
        self.audio.talk_duck_target = 0.55 if self.in_dialogue else 1.0
        if self.state == "title":
            self.story.title_update(dt)
            self.env.update(dt)
            self.world.update(dt)
            self._update_herd(dt)
            self.audio.update(dt, camera.world_position, camera.world_rotation_y)
            self.runner.update(dt)
            return
        if self.state == "paused":
            self.audio.update(0, (self.player.x, self.player.y + 1.4, self.player.z), self.player.yaw)
            return
        self.env.update(dt)
        self.world.update(dt)
        # smooth look at speaker during dialogue
        if getattr(self, "_look_goal", None) and not self.cam_free:
            wy, wp = self._look_goal
            p = self.player
            p.yaw += ((wy - p.yaw + 180) % 360 - 180) * min(1, dt * 5)
            p.pitch += (wp - p.pitch) * min(1, dt * 5)
        self.player.update(dt)
        if self.vehicle is not None:
            self.vehicle.update(dt)
        self.farmer.update(dt)
        if not (self.farmer.flashlight and self.env.is_dark):
            self.env.flash = None
        for c in self.cows.values():
            c.update(dt)
        self._update_herd(dt)
        for h in self.hens:
            h.update(dt)
        for e in list(self.enemies):
            e.update(dt)
        self._update_knockables(dt)
        self.runner.update(dt)
        self.story.update(dt)
        p = self.player
        lis = camera.world_position
        self.audio.update(dt, (lis.x, lis.y, lis.z), p.yaw if not self.cam_free else camera.world_rotation_y)
        # interaction target
        if self.controls_enabled() and not self.busy:
            self.target = self.ia.find_target(p.eye_pos, p.forward())
            if self.target is not None:
                h = self.target.active_handler(self)
                if h is not None:
                    prompt = h.prompt(self) if callable(h.prompt) else h.prompt
                else:
                    prompt = self.target.prompt if not self.target.key.startswith(("cow_", "herd_")) else self.target.prompt
                    if not self.target.key.startswith(("cow_", "herd_", "clover_", "rockpile")):
                        prompt = f"Examine {self.target.name}"
                self.ui.set_prompt(f"[E] {prompt}" if prompt else None)
            else:
                self.ui.set_prompt(None)
        else:
            self.target = None
            if not self.in_dialogue:
                self.ui.set_prompt(None)
        # meters
        self.ui.set_stamina(p.stamina, self.controls_enabled())
        f = self.farmer
        state = f.marker_state
        self.ui.set_suspicion(f.susp if f.visible else 0.0, state if f.visible else "")
        self._music_logic()

    def _update_herd(self, dt):
        cam = camera.world_position
        # update a third of the herd each frame (staggered), everyone moves
        for i, h in enumerate(self.herd):
            h.update(dt, cam.x, cam.z)

    def _music_logic(self):
        """Stealth music when Chuck is near and the player is somewhere they shouldn't be."""
        if self.story.music_locked or self.cutscene:
            return
        p = self.player
        f = self.farmer
        tense = f.visible and self.player_restricted() and math.hypot(f.x - p.x, f.z - p.z) < 40 and \
            f.state not in ("sleep", "disabled", "scripted")
        want = "music_stealth" if tense else self.story.base_music
        if want != self.audio.music_name:
            self.audio.music_play(want, 0.8 if want == "music_stealth" else 0.7, fade=2.5)

    # ------------------------------------------------------------------
    # input
    # ------------------------------------------------------------------
    def input(self, key):
        if key == "f11":
            self.toggle_fullscreen()
            return
        if key == "f12":
            self.screenshot()
            return
        if self.state == "title":
            self.story.title_input(key)
            return
        ui = self.ui
        if ui.modal is not None:
            self._modal_input(key)
            return
        if self.state != "play":
            return
        if self.in_dialogue:
            if ui.choice_root.enabled:
                ui.choice_input(key)
                return
            if key in ("space", "e", "left mouse down", "enter"):
                if not ui.dlg_revealed():
                    ui.dlg_complete()
                else:
                    self._advance = True
            if key == "escape":
                self.open_pause()
            return
        if key == "escape":
            self.open_pause()
            return
        if self.debug and self._debug_input(key):
            return
        if self.vehicle is not None and self.vehicle.input(key):
            return
        if not self.controls_enabled():
            if self.cutscene and key in ("space", "e", "left mouse down", "enter"):
                self._advance = True
            return
        p = self.player
        if key == "e":
            if self.target is not None and not self.busy:
                self.interact(self.target)
        elif key == "left mouse down":
            p.headbutt()
        elif key == "right mouse down":
            p.kick()
        elif key == "r":
            sel = self.inv.selected()
            if sel in THROWABLE:
                if p.throw(sel):
                    self.inv.remove(sel)
            elif self.inv.has("rock"):
                if p.throw("rock"):
                    self.inv.remove("rock")
            else:
                self.examine("Nothing to throw. Rock piles are dotted around the farm.")
        elif key == "m":
            p.moo()
        elif key == "space":
            p.hop()
        elif key == "c":
            p.crouch_toggle = not p.crouch_toggle
        elif key in ("tab", "j"):
            self.ui.open_journal(self)
        elif key == "h":
            self.show_hint()
        elif key in "123456789" and len(key) == 1:
            keys = self.inv.hotbar_keys()
            i = int(key) - 1
            if i < len(keys):
                self.inv.sel = i
                self.refresh_hotbar()
        elif key == "scroll up":
            self.inv.cycle(-1)
        elif key == "scroll down":
            self.inv.cycle(1)
        elif key == "q":
            self.use_selected()

    def use_selected(self):
        sel = self.inv.selected()
        if not sel:
            return
        if not self.story.use_item(sel):
            self.examine(f"You hold the {ITEMS[sel][0].lower()} thoughtfully in your mouth. Nothing happens.")

    def show_hint(self):
        h = self.story.hint()
        if h:
            self.audio.play(f"moo_cowleen_short_{random.randrange(2)}", vol=0.5, group="voice")
            self.ui.popup_sub("Cowleen's voice in your head: " + h, 7)

    def _modal_input(self, key):
        ui = self.ui
        m = ui.modal
        if m == "document":
            if key in ("e", "space", "escape", "enter", "left mouse down"):
                ui.close_modal()
                self.set_mouse(True)
                self._doc_closed = True
        elif m == "combo":
            ui.combo_input(key)
        elif m == "password":
            ui.password_input(key)
        elif m == "journal":
            if key in ("tab", "j", "escape"):
                ui.close_modal()
                self.set_mouse(True)
        elif m in ("pause", "settings", "shop", "menu"):
            if key == "escape":
                st = getattr(ui, "_modal_state", {}) or {}
                if st.get("back_cb"):
                    st["back_cb"]()
                elif m == "pause":
                    self.close_pause()

    def show_document(self, title, body, paper=True):
        """Generator: show a document and wait until it is closed."""
        self._doc_closed = False
        self.ui.show_document(title, body, paper=paper)
        yield lambda: self._doc_closed

    # ------------------------------------------------------------------
    # pause
    # ------------------------------------------------------------------
    def open_pause(self):
        if self.state != "play":
            return
        self.state = "paused"
        application.paused = False
        self.audio.music_duck = 0.4
        self.ui.open_menu("PAUSED", [
            ("Resume", self.close_pause),
            ("Settings", lambda: self.ui.open_settings(self._back_to_pause)),
            ("Restart checkpoint", self._restart_checkpoint),
            ("Quit to title", self._quit_to_title),
            ("Quit game", self._quit_game),
        ], subtitle=f"{self.day_title}  ·  {self.day_sub}", name="pause")

    def _back_to_pause(self):
        self.ui.close_modal()
        self.state = "play"
        self.open_pause()

    def close_pause(self):
        self.ui.close_modal()
        self.state = "play"
        self.audio.music_duck = 1.0
        self.set_mouse(True)

    def _restart_checkpoint(self):
        self.close_pause()
        d = self.load_save()
        if d:
            self.story.load_from_save(d)

    def _quit_to_title(self):
        self.close_pause()
        self.story.to_title()

    def _quit_game(self):
        self.save_settings()
        application.quit()

    # ------------------------------------------------------------------
    # debug
    # ------------------------------------------------------------------
    def _debug_input(self, key):
        if key == "f5":
            self.story.debug_skip_step()
            return True
        if key == "f6":
            self.story.debug_next_day()
            return True
        if key == "f7":
            m = list(self.story.markers())
            if m:
                x, z, _ = m[0]
                gh, _ = self.phys.ground(x, z, 5)
                self.player.teleport(x - 2, gh, z - 2)
            return True
        if key == "f8":
            self.farmer.detect = not self.farmer.detect
            self.examine(f"[debug] farmer detection {'on' if self.farmer.detect else 'off'}")
            return True
        if key == "f9":
            p = self.player
            print(f"pos=({p.x:.2f}, {p.y:.2f}, {p.z:.2f}) yaw={p.yaw:.1f} day={self.day} step={self.step_i}")
            self.examine(f"({p.x:.1f}, {p.y:.1f}, {p.z:.1f}) yaw {p.yaw:.0f}")
            return True
        return False
