"""Story runner: title screen, days, steps, checkpoints, conversations, ending.

The seven days live in days.py. Every step is idempotent: it records a flag when it
finishes, and a restarted day skips any step whose flag is already set. World state
(doors, props, who's where) is rebuilt from flags at the start of each day, so a
checkpoint is just "which day" plus the flags and inventory at that moment.
"""
from __future__ import annotations

import math
import random

from ursina import BoxCollider, Button, Entity, Quad, Text, Vec3, application, camera, color, destroy, mouse

from .days import DayScripts, DAYS
from .farmer import HEARING, SIGHT_DAY
from .game import aim_camera
from .interact import Handler, Interactable
from .items import ITEMS
from .npc import FRIENDS, HERD_NAMES
from .ui import C, CREAM, BRASS, DIM, PANEL, PANEL_LIGHT, txt
from . import models


def save_has_progress(save):
    """True once the player has really played: at least one story step finished.

    A save is written as soon as a day starts, so a bare 'New game, then quit' leaves a
    save with no finished steps; the title screen shouldn't offer Continue for that."""
    if not isinstance(save, dict) or not isinstance(save.get("flags"), dict):
        return False
    try:
        if int(save.get("day", 1)) > 1:
            return True
    except (TypeError, ValueError):
        return False
    return any(str(k).startswith("d1_") and v for k, v in save["flags"].items())

SHOP = [
    # key, label, price, description
    ("rock_pouch", "Rock Pouch", 2, "Carry six rocks instead of three. Yours to keep, every playthrough."),
    ("rubber_chicken", "Rubber Chicken", 3, "Squeaky, throwable, and it doesn't conduct electricity."),
    ("moustache", "Fake Moustache", 4, "Wear it with a straw hat and Chuck will think you're Dale. Walk, don't run."),
    ("coffee", "Suspiciously Strong Coffee", 2, "Gallop twice as long for the rest of the day. Drink it here."),
    ("tincan", "Mysterious Tin Can", 5, "No refunds."),
    ("shells", "Two Shotgun Shells", 6, "For a gun you don't have yet. Epicowrus doesn't ask what for."),
]
# bought again each time (the rest are yours for good, and come with you into the next playthrough)
CONSUMABLE = ("coffee", "shells")

HERD_LINES = [
    "Moo. (The grass by the fence tastes the same as the other grass. I keep checking. That's empiricism.)",
    "Moo. (If a cow is raised to be eaten and knows it, is she livestock or a tragic hero? Asking for me.)",
    "Moo. (Chuck scratched my ears yesterday, then looked at my rump for a really long time. Kindness with an "
    "invoice.)",
    "Moo. (I stare at the pond and the pond doesn't stare back. I'm told that's a relief. I'm told a lot of things.)",
    "Moo. (Four stomachs. I've processed more than any philosopher alive. Mostly grass. Some regret.)",
    "Moo. (Moogenes says he's descended from royalty. So is everyone, if you go back far enough. Also from "
    "bacteria.)",
    "Moo. (The rooster's writing a history of the coop. Eight volumes. The hens are in none of them. The hens "
    "are an oral tradition.)",
    "Moo. (I'm going to stand here, then over there. Zeno says I'll never arrive. Zeno never met a salt lick.)",
    "Moo. (Epicowrus sold me a 'Golden Clover'. It was a regular clover, painted. Value is a shared "
    "hallucination.)",
    "Moo. (If you see Clarabelle, tell her she owes me a salt lick and an apology. She knows why. She doesn't "
    "know anything else.)",
    "Moo. (The truck comes, someone goes, the grass grows back. It's like weather. You don't argue with weather. "
    "...Do you?)",
    "Moo. (Chuck counted us last night. It's nice to be counted. It means you matter. Numerically.)",
    "Moo. (There's a fly on my back. I know. It knows I know. We're in a standoff of mutual awareness.)",
    "Moo. (My mother said 'you are what you eat'. Then she got eaten. The syllogism was grim for everyone.)",
    "Moo. (Chuck calls us 'the girls'. Then 'the inventory'. The distance between those words is the whole "
    "industry.)",
    "Moo. ('Free range.' I've ranged for years. None of it was free. Marketing is violence with a font.)",
    "Moo. (I'm not scared of Sunday. I'm scared of Dale. Nobody's seen Dale. Dale is a Platonic horror.)",
]



class Story(DayScripts):
    def __init__(self, g):
        self.g = g
        self.music_locked = False
        self.base_music = "music_pasture"
        self.day = 0
        self.cur = None
        self.cur_cheat = None
        self.hooks: dict = {}
        self.day_hooks: dict = {}
        self.hint_text = ""
        self.marks: list = []
        self.props: dict = {}
        self.title_root = None
        self.title_sel = 0
        self.title_buttons: list = []
        self.title_mode = "main"
        self.cam_t = 0.0
        self.talk_i: dict = {}
        self.fx: list = []
        self.enemy = None
        self.ending = False
        DayScripts.__init__(self)

    # ------------------------------------------------------------------
    # flags
    # ------------------------------------------------------------------
    @property
    def flags(self):
        return self.g.flags

    def done(self, key):
        return bool(self.g.flags.get(key))

    def setf(self, key, val=True):
        self.g.flags[key] = val

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self, day=0):
        if day and 1 <= day <= 7:
            self.new_game(day)
        else:
            self.to_title()

    def reset_run(self):
        g = self.g
        g.flags = {}
        g.stats = {}
        g.inv.items = {}
        g.inv.order = []
        g.inv.sel = 0
        g.player.has_bell = True
        g.player.set_disguise(False)
        g.player.health = g.player.max_health
        self.talk_i = {}

    def new_game(self, day=1):
        self.reset_run()
        self.canon_before(day)
        self.apply_owned()
        self._leave_title(lambda: self.start_day(day))

    def apply_owned(self):
        """Things bought from Epicowrus in any playthrough come with you (unless this run already has them)."""
        g = self.g
        for k in g.moodals.owned():
            if k in CONSUMABLE or self.flags.get(f"shop_{k}"):
                continue
            self.setf(f"shop_{k}")
            if k == "rock_pouch":
                self.setf("rock_pouch")
            elif k in ITEMS:
                g.inv.add(k, silent=True)

    def continue_game(self):
        d = self.g.load_save()
        if not save_has_progress(d):
            self.new_game(1)
            return
        self._leave_title(lambda: self.load_from_save(d))

    def _leave_title(self, then):
        """Fade the title to black first: closing it moves the camera into the cow's head, and that
        view shouldn't flash up before the day card."""
        g = self.g
        if g.state != "title" or self.title_root is None:
            self.close_title()
            then()
            return
        def nothing():
            pass
        for b in self.title_buttons:
            b.on_click = nothing
            b.on_mouse_enter = nothing
            b.on_mouse_exit = nothing
        self.title_buttons = []     # no second pick while the fade runs

        def go():
            yield from g.fade_out(0.5)
            self.close_title()
            then()
        g.runner.start(go(), name="title_out")

    def load_from_save(self, d):
        self.reset_run()
        self.g.apply_save(d)
        self.apply_owned()
        self.start_day(int(d.get("day", 1)))

    def start_day(self, n):
        g = self.g
        g.runner.stop("story")
        g.runner.stop("interact")
        g.runner.stop("caught")
        g.runner.stop_tag("day")
        g.busy = False
        g.state = "play"
        g.set_mouse(True)
        g.runner.start(self._run_day(n), name="story")

    def _run_day(self, n):
        g = self.g
        if g.ui.fade_alpha < 0.99:
            yield from g.fade_out(0.6)
        self.clear_day()
        self.day = n
        g.day = n
        # a day restarted from a mid-day checkpoint skips its opening step, which is where the
        # screen fades in; step() notices and fades in (and puts the light back) instead
        self.resume_time = self.flags.get("_time")
        self.day_skipped = False
        self.day_ran = False
        info = DAYS[n]
        g.day_title = info["name"]
        g.day_sub = info["sub"]
        g.ui.set_day(info["name"], info["sub"])
        self.setf("max_day", max(n, self.flags.get("max_day", 1)))
        g.event("day_start", day=n)
        self.apply_world_flags()
        getattr(self, f"setup_day{n}")()
        g.refresh_hotbar()
        g.save_checkpoint()
        g.cutscene_start(letterbox=False)
        g.ui.show_hud(False)
        yield 0.3
        yield from g.card(info["card"], info["card_sub"], dur=3.2)
        g.cutscene_end_now()
        g.ui.show_hud(True)
        yield from getattr(self, f"day{n}")()

    def clear_day(self):
        """Tear down everything a day created."""
        g = self.g
        g.ia.clear_scope("step")
        g.ia.clear_scope("day")
        self.hooks = {}
        self.day_hooks = {}
        self.marks = []
        self.hint_text = ""
        self.cur = None
        self.cur_cheat = None
        g.restricted_fn = None
        g.noise_masks = []
        g.flags.pop("_hiding", None)
        for e in list(g.enemies):
            if hasattr(e, "remove"):
                e.remove()
        g.enemies = []
        self.enemy = None
        if g.vehicle is not None:
            g.vehicle.leave()
        g.cutscene_end_now()
        g.ui.set_boss("", 0, False)
        g.ui.set_health(0, 0, False)
        g.ui.show_hud(True)
        g.ui.close_modal()
        g.ui.set_center_text("")
        g.ui.title_card("", "", 0)
        cr = getattr(self, "credits_root", None)
        if cr is not None:
            destroy(cr)
            self.credits_root = None
        self.hide_overlay()
        for k in list(self.props):
            self.remove_prop(k)
        for k in list(g.world.items):
            g.world.remove_item(k)
        for k in [k for k in g.ia.items if k.startswith(("st_", "dropped_"))]:
            g.ia.remove(k)
        for f in self.fx:
            if hasattr(f, "remove"):
                f.remove()
        self.fx = []
        g.audio.stop_all_loops(0.5)
        self.music_locked = False
        g.player.frozen = False
        g.player.health = g.player.max_health
        g.player.set_disguise(False)
        self.flags.pop("coffee", None)
        f = g.farmer
        f.boss = None
        f.detect = True
        f.flashlight = False
        f.hearing = HEARING
        f.range_day = SIGHT_DAY
        f.walk_run = False
        f.trip_rate = 1 / 90.0
        f.dale_greeted = False
        if f.sleeping:
            f.wake()
        f.sleeping = False
        f.set_outfit("day")
        f.set_tool(None)
        f.set_visible(True)
        f.set_routine([])
        g.player.crouch_toggle = False

    def to_title(self):
        g = self.g
        g.runner.stop_all()
        self.clear_day()
        self.ending = False
        g.state = "title"
        g.player.body.enabled = False
        g.audio.stop_everything()
        g.ui.show_hud(False)
        g.ui.set_fade(0.0)
        g.set_mouse(False)
        g.farmer.set_visible(False)
        g.env.set_preset("sunset")
        g.ambience("day")
        g.audio.music_play("music_title", 0.8, fade=1.0)
        for c in g.cows.values():
            c.set_visible(True)
        for h in g.herd:
            h.model.enabled = True
            h.col.enabled = True
            h.state = "graze"
            h.path = []
        self.scatter_herd()
        self.place_friends_default()
        g.cam_detach()
        camera.rotation = (0, 0, 0)
        self.cam_t = 0.0
        self.open_title()

    # ------------------------------------------------------------------
    # title screen
    # ------------------------------------------------------------------
    def open_title(self, mode="main"):
        self.close_title_ui()
        g = self.g
        self.title_mode = mode
        r = Entity(parent=camera.ui)
        self.title_root = r
        A = g.ui.aspect
        # a soft dark band behind the menu so it reads over the bright sky
        Entity(parent=r, model="quad", color=C(0, 0, 0, 0.35), scale=(0.62, 1.2), x=-A / 2 + 0.36, z=0.5)
        t = Text("BREAKOWT", parent=r, x=-A / 2 + 0.08, y=0.34, scale=5.2, color=C(0.98, 0.95, 0.86, 1),
                 origin=(-0.5, 0))
        if g.fonts.get("title"):
            t.font = g.fonts["title"]
        Text("SEVEN DAYS TO STEAK", parent=r, x=-A / 2 + 0.09, y=0.25, scale=1.5, color=BRASS, origin=(-0.5, 0))
        opts = []
        save = g.load_save()
        if not save_has_progress(save):
            save = None
        if mode == "main":
            if save:
                d = int(save.get("day", 1))
                opts.append((f"Continue  ({DAYS[d]['name']})", self.continue_game))
            opts.append(("New game", lambda: self.new_game(1)))
            # every day is open from the start; a chapter sets up what the earlier days would have
            opts.append(("Chapter select", lambda: self.open_title("chapters")))
            opts.append(("Moo-dals", self._title_moodals))
            opts.append(("Settings", self._title_settings))
            opts.append(("Quit", self._quit))
        else:
            for d in range(1, 8):
                opts.append((f"{DAYS[d]['name']}  ·  {DAYS[d]['card_sub'].split('·')[0].strip()}",
                             (lambda d=d: self.new_game(d))))
            opts.append(("Back", lambda: self.open_title("main")))
        self.title_buttons = []
        gap = 0.075 if len(opts) <= 6 else 0.064
        bh = 0.054
        for i, (label, cb) in enumerate(opts):
            b = Button(parent=r, text=label, x=-A / 2 + 0.3, y=0.1 - i * gap, scale=(0.46, bh),
                       color=PANEL_LIGHT, radius=0.25, text_origin=(-0.5, 0))
            b.text_entity.x = -0.45
            # the clickable area reaches halfway into the gaps, so there are no dead strips between buttons
            b.collider = BoxCollider(b, center=Vec3(0, 0, 0), size=Vec3(1, gap / bh, 1))
            b.on_click = cb
            b._cb = cb
            b.on_mouse_enter = (lambda i=i: self._title_hl(i))
            b.on_mouse_exit = (lambda i=i: self._title_unhover(i))
            self.title_buttons.append(b)
        self.title_sel = 0
        # nothing is lit until the mouse is over a button or a key picks one
        self._title_hl(None)
        Text("F11 fullscreen", parent=r, x=A / 2 - 0.03, y=-0.46, scale=0.8, color=DIM, origin=(0.5, 0))
        from .engine.buildinfo import build_id
        Text(f"v1.0  {build_id()}".strip(), parent=r, x=-A / 2 + 0.03, y=-0.46, scale=0.8, color=DIM, origin=(-0.5, 0))

    def _title_hl(self, i):
        """Light up button i (None: none lit). The highlight always marks what a click or Enter would pick."""
        if i is not None:
            self.title_sel = i
        for k, b in enumerate(self.title_buttons):
            b.color = C(0.98, 0.78, 0.25, 0.95) if k == i else PANEL_LIGHT
            b.text_color = C(0.1, 0.08, 0.05, 1) if k == i else CREAM
        self.title_lit = i

    def _title_unhover(self, i):
        # leaving a button for empty space clears the highlight; moving onto a neighbour re-lights it
        if getattr(self, "title_lit", None) == i and not any(b.hovered for b in self.title_buttons):
            self._title_hl(None)

    def _title_moodals(self):
        g = self.g
        self.close_title_ui()

        def back():
            g.ui.close_modal()
            g.set_mouse(False)
            self.open_title("main")
        g.ui.open_moodals(g, back)

    def _title_settings(self):
        g = self.g
        self.close_title_ui()

        def back():
            g.ui.close_modal()
            g.set_mouse(False)
            self.open_title("main")
        g.ui.open_settings(back)

    def _quit(self):
        self.g.save_settings()
        application.quit()

    def close_title_ui(self):
        if self.title_root is not None:
            destroy(self.title_root)
        self.title_root = None
        self.title_buttons = []

    def close_title(self):
        g = self.g
        self.close_title_ui()
        g.ui.close_modal()
        g.cam_attach()
        g.farmer.set_visible(True)

    def title_update(self, dt):
        self.cam_t += dt
        a = self.cam_t * 0.035 + 2.2
        cx, cz = -10.0, -10.0
        r = 70.0
        pos = (cx + math.sin(a) * r, 26 + math.sin(self.cam_t * 0.05) * 3, cz + math.cos(a) * r)
        camera.position = pos
        aim_camera((cx * 0.5, 4, cz * 0.5))

    def title_input(self, key):
        if self.g.ui.modal in ("settings", "moodals"):
            if key == "escape":
                st = getattr(self.g.ui, "_modal_state", {}) or {}
                if st.get("back_cb"):
                    st["back_cb"]()
            return
        if not self.title_buttons:
            return
        n = len(self.title_buttons)
        lit = getattr(self, "title_lit", None)
        if key in ("w", "up arrow", "scroll up"):
            self._title_hl((self.title_sel - 1) % n if lit is not None else n - 1)
            self.g.audio.play("blip", vol=0.3)
        elif key in ("s", "down arrow", "scroll down"):
            self._title_hl((self.title_sel + 1) % n if lit is not None else 0)
            self.g.audio.play("blip", vol=0.3)
        elif key in ("enter", "space", "e"):
            if lit is None:
                self._title_hl(self.title_sel)
                return
            self.g.audio.play("blip_hi", vol=0.4)
            self.title_buttons[self.title_sel]._cb()
        elif key == "escape" and self.title_mode != "main":
            self.open_title("main")

    # ------------------------------------------------------------------
    # steps
    # ------------------------------------------------------------------
    def step(self, key, fn, hint="", cheat=None, save=True):
        """Run one step unless it's already done. Generator."""
        if self.done(key):
            self.day_skipped = True
            return None
        g = self.g
        if not getattr(self, "day_ran", True):
            self.day_ran = True
            if self.day_skipped:
                yield from self._resume_in()
        self.cur = key
        self.cur_cheat = cheat
        self.hint_text = hint
        self.hint_level = 0
        self.hooks = {}
        res = yield from fn()
        self.setf(key)
        g.ia.clear_scope("step")
        self.hooks = {}
        self.marks = []
        self.cur = None
        self.cur_cheat = None
        if save:
            g.save_checkpoint()
        return res

    def _resume_in(self):
        g = self.g
        rt = self.resume_time
        if isinstance(rt, (list, tuple)) and len(rt) == 2 and rt[0] == self.day:
            g.set_time(rt[1])
        if g.ui.fade_alpha > 0.01:
            yield from g.fade_in(1.0)

    def hook(self, name, fn):
        self.hooks[name] = fn

    def dhook(self, name, fn):
        self.day_hooks[name] = fn

    def _hook(self, name):
        return self.hooks.get(name) or self.day_hooks.get(name)

    def mark(self, *pts):
        """pts: (x, z, label) ... replaces the map markers."""
        self.marks = list(pts)

    def objectives(self, *objs):
        self.g.set_objectives(list(objs))

    def wait_all(self, *keys):
        return lambda: all(self.g.is_done(k) for k in keys)

    # ------------------------------------------------------------------
    # hooks called by the game
    # ------------------------------------------------------------------
    def update(self, dt):
        fn = self._hook("update")
        if fn:
            fn(dt)
        for f in self.fx:
            if hasattr(f, "update"):
                f.update(dt)
        self.fx = [f for f in self.fx if getattr(f, "alive", True)]

    def on_noise(self, pos, radius, source):
        fn = self._hook("noise")
        if fn:
            fn(pos, radius, source)

    def on_headbutt(self, eye, fwd):
        fn = self._hook("headbutt")
        return bool(fn(eye, fwd)) if fn else False

    def on_kick(self, pos, yaw):
        fn = self._hook("kick")
        return bool(fn(pos, yaw)) if fn else False

    def on_projectile_land(self, proj, p):
        fn = self._hook("land")
        if fn:
            fn(proj, p)

    def on_player_moo(self):
        fn = self._hook("moo")
        return bool(fn()) if fn else False

    def on_player_defeated(self):
        fn = self._hook("defeated")
        if fn:
            fn()

    def on_caught(self):
        fn = self._hook("caught")
        return bool(fn()) if fn else False

    def caught_line(self):
        fn = self._hook("caught_line")
        return fn() if fn else None

    def after_caught(self):
        g = self.g
        g.flags.pop("_hiding", None)
        self.hide_overlay()
        g.player.frozen = False
        g.player.set_disguise(False)
        fn = self._hook("after_caught")
        if fn and fn():
            return
        self.return_to_pasture()

    def return_to_pasture(self):
        g = self.g
        g.player.teleport(-24.5, 0, -34.5, 270)
        f = g.farmer
        f.teleport((-14.5, 0, -36.5), 90)
        f.path = []
        f.resume_routine()

    def use_item(self, sel):
        fn = self._hook("use")
        if fn and fn(sel):
            return True
        g = self.g
        p = g.player
        if sel == "shotgun":
            g.fire_shotgun()
            return True
        if sel == "score":
            return self.score_use()
        if sel == "moustache":
            if p.disguised:
                p.set_disguise(False)
                g.examine("You take the moustache off. You're a cow again.")
            elif g.inv.has("hat"):
                p.set_disguise(True)
                g.examine("Moustache on, hat on. You are Dale now. Walk like Dale. Dale does not gallop.")
            else:
                g.examine("A moustache on its own just makes you a cow with a moustache. You need a straw hat too. "
                          "Chuck keeps spares in his wardrobe.")
            return True
        uses = {
            "cowbell": "Your old cowbell. It still smells like you, which is to say: like a cow. [R] throws it.",
            "tincan": "You shake the tin can. Nothing. You shake it again. Still nothing. [R] throws it, very loudly.",
            "boot": "It smells like Chuck's foot. That's a weapon on its own. [R] throws it.",
            "page": "MON fix fence (AGAIN). TUE oil tractor. SUN #47 -> PROCESSING. Buy charcoal. Buy MORE charcoal.",
            "photo": "Chuck and Big Earl, Best in Show 2009. Big Earl looks like he's planning something. Heifercleitus "
                     "would want this.",
            "plank": "It's a plank. The cattle grid wants three of them.",
            "sparkplug": "It smells of vinegar and Chuck's dentures. It goes in the tractor.",
            "jerrycan": "Diesel. It goes in the tractor, not in you.",
            "glasses": "Everything's blurry and huge. So this is how Chuck sees you. Moothagoras wants these.",
            "bucket": "A rusty bucket. Moogenes wants it. Moogenes wants to WEAR it.",
            "rubber_chicken": "You squeeze it. It screams. You feel seen. [R] throws it.",
        }
        if sel in uses:
            g.examine(uses[sel])
            return True
        return False

    def hint(self):
        fn = self._hook("hint")
        if fn:
            h = fn()
            if h:
                return h
        h = self.hint_text
        if isinstance(h, (tuple, list)):
            # tiered: a nudge first, then (asked again) more of the answer
            lvl = min(getattr(self, "hint_level", 0), len(h) - 1)
            self.hint_level = lvl + 1
            return h[lvl] + ("  [H again for more]" if lvl < len(h) - 1 else "")
        return h or "Nothing to do right now but chew. Talk to the others, or explore."

    def markers(self):
        return list(self.marks)

    # ------------------------------------------------------------------
    # debug
    # ------------------------------------------------------------------
    def debug_skip_step(self):
        if self.cur is None:
            return
        if self.cur_cheat:
            self.cur_cheat()
        self.setf(self.cur)
        self.g.ui.popup_sub(f"[debug] skipped {self.cur}", 2)
        self.start_day(self.day)

    def debug_next_day(self):
        n = min(7, self.day + 1)
        self.canon_day(self.day)
        self.start_day(n)

    # ------------------------------------------------------------------
    # conversations
    # ------------------------------------------------------------------
    def default_talk(self, key):
        g = self.g
        fn = self._hook(f"talk:{key}")
        if fn:
            res = yield from fn()
            return res
        res = yield from self.side_quest_talk(key)
        if res:
            return True
        if key == "mooriarty" and self.done("mooriarty_met"):
            yield from self.shop()
            return True
        lines = self.chatter(key)
        if not lines:
            lines = [[(key, "Moo.")]]
        i = self.talk_i.get(key, 0)
        self.talk_i[key] = i + 1
        yield from g.talk(lines[i % len(lines)])
        return True

    def herd_talk(self, cow):
        g = self.g
        fn = self._hook("herd_talk")
        if fn:
            res = yield from fn(cow)
            if res:
                return True
        g.event("herd_talk", idx=cow.idx)
        line = HERD_LINES[(cow.idx * 7 + self.talk_i.get(f"herd{cow.idx}", 0)) % len(HERD_LINES)]
        self.talk_i[f"herd{cow.idx}"] = self.talk_i.get(f"herd{cow.idx}", 0) + 1
        yield from g.talk([(cow, line)])
        return True

    def side_quest_talk(self, key):
        """Handing over favors. Returns True if something happened."""
        g = self.g
        if key == "cowleen" and self.flags.get("ledger_read") and not self.flags.get("ledger_told"):
            self.flags["ledger_told"] = True
            yield from g.talk([
                ("cowleen", "You went inside the plant? ...What's in there?"),
                ("you", "Moo. (A book. We're all in it. Number, weight, grade. No names.)"),
                ("cowleen", "No. There wouldn't be. You don't name what you're going to weigh."),
                ("cowleen", "We name each other, though. We always have. I used to think it was just a habit."),
                ("cowleen", "Now I think it might be the only thing on this farm that isn't on their side."),
            ])
            return True
        if key == "sirloin" and g.inv.has("bucket") and not self.done("sq_helm"):
            g.inv.remove("bucket")
            self.setf("sq_helm")
            g.cows["sirloin"].model.set_acc("bucket")
            g.audio.play("metal_clang", vol=0.8)
            yield from g.talk([
                ("sirloin", "A bucket. For me?"),
                ("you", "Moo. (You wanted a home nobody could sell.)"),
                ("sirloin", "Everything Chuck owns, he can sell. The field. The barn. Us. But nobody in history has "
                            "ever sold a bucket with a cow in it. The market won't touch it."),
                ("sirloin", "There. I live in it now."),
                ("you", "Moo. (It's on your head.)"),
                ("sirloin", "A house is a thing you live in. I live in this. Show me the flaw."),
                ("you", "Moo. (You're going to walk into the fence wearing that.)"),
                ("sirloin", "Then the fence will learn something about property."),
                ("sirloin", "...It smells like old paint and Chuck's feet. I've never been happier. Happiness is "
                            "very stupid and I recommend it."),
            ])
            g.side_quest("helm", state="done")
            return True
        if key == "cowpernicus" and g.inv.has("glasses") and not self.done("sq_specs"):
            g.inv.remove("glasses")
            self.setf("sq_specs")
            self.setf("star_chart")
            g.cows["cowpernicus"].model.set_acc("glasses")
            yield from g.talk([
                ("cowpernicus", "Are those... reading glasses? Plus two-point-five?"),
                ("cowpernicus", "Oh. Oh no. The stars are points. I had a whole cosmology based on them being "
                                "smudges. Four years of work. Falsified in one second. This is what science feels "
                                "like. It's awful. It's wonderful."),
                ("cowpernicus", "And now I can see where Chuck CAN'T see. His blind spots are fixed geometry: every "
                                "bale, every clump of tall grass. Hold still, I'm charting it."),
                ("cowpernicus", "Done. Every hiding spot on the farm, on your map. Tab. The glasses did twenty "
                                "percent. I did eighty. I'd show you the working, but you'd feel inadequate."),
            ])
            g.side_quest("specs", state="done")
            g.ui.toast("Hiding spots marked on your map", "glasses", col=BRASS)
            return True
        if key == "moomaw" and g.inv.has("photo") and not self.done("sq_photo"):
            g.inv.remove("photo")
            self.setf("sq_photo")
            yield from g.talk([
                ("moomaw", "Oh. Look at him. That big dumb handsome face. Two thousand pounds of not knowing "
                           "he was a product."),
                ("moomaw", "Best in Show, 2009. He ate half the ribbon. Then the judge's hat. He understood "
                           "prizes better than anyone: they're just things people give you before they take the "
                           "rest."),
                ("moomaw", "Chuck's standing next to him like they were friends. Earl bit him ten minutes after this. "
                           "You can see Chuck's hand is already worried. That hand was right."),
                ("moomaw", "Here. His lucky horseshoe. He wore it on a string. It didn't work. Luck is a story "
                           "survivors tell."),
                ("moomaw", "But if Chuck grabs you, drop it at his feet. He's tripped on it twice. The man cannot "
                           "handle a horseshoe. Or grief. Or accountability."),
            ])
            g.inv.add("horseshoe")
            g.side_quest("photo", state="done")
            return True
        return False

    def shop(self):
        g = self.g
        done = {"d": False}

        def owned(k):
            if k == "coffee":
                return bool(self.flags.get("coffee"))
            if k in CONSUMABLE:
                return False
            return k in g.moodals.owned() or self.done(f"shop_{k}")

        def entries():
            out = []
            for key, label, price, desc in SHOP:
                out.append((key if key != "rock_pouch" else "rock", label, price, desc, owned(key)))
            return out

        def buy(key):
            k = "rock_pouch" if key == "rock" else key
            price = next(p for kk, _, p, _ in SHOP if kk == k)
            if owned(k):
                return
            if g.clovers() < price:
                g.audio.play("blip_lo", vol=0.5)
                g.ui.toast("Not enough Golden Clovers. Earn Moo-dals.")
                return
            g.moodals.spend(price, k, keep=k not in CONSUMABLE)
            if k not in CONSUMABLE:
                self.setf(f"shop_{k}")
            g.stats["bought"] = g.stats.get("bought", 0) + 1
            g.audio.play("clover", vol=0.6)
            if k == "rock_pouch":
                self.setf("rock_pouch")
                g.ui.toast("Rock Pouch: carry up to 6 rocks", "rock")
            elif k == "coffee":
                self.setf("coffee")
                g.ui.toast("You drink it on the spot. Gallop for longer today.", "coffee")
            elif k == "shells":
                g.inv.add("shells", 2)
            else:
                g.inv.add(k)
            g.refresh_hotbar()
            reopen()

        def close():
            g.ui.close_modal()
            g.set_mouse(True)
            done["d"] = True

        def reopen():
            g.ui.open_shop("THE GARDEN", entries(), g.clovers(), buy, close)

        yield from g.talk([("mooriarty", random.choice([
            "Psst. Over here. Take a look. Don't touch unless you're buying.",
            "Back again. I knew you would be. I know things.",
            "Golden Clovers only. Don't ask me where the merchandise comes from. Or where the clovers go.",
            "Every Moo-dal you earn, a clover finds its way to you. I don't make the rules. I sell the rules.",
        ]))])
        reopen()
        yield lambda: done["d"]

    # ------------------------------------------------------------------
    # modals as generators
    # ------------------------------------------------------------------
    def combo(self, digits=3, title="Combination lock"):
        g = self.g
        g.ui.open_combo(digits, title)
        yield lambda: g.ui._modal_state.get("result") is not None
        r = g.ui._modal_state.get("result")
        g.ui.close_modal()
        g.set_mouse(True)
        return r

    def password(self, answers, hint):
        g = self.g
        g.ui.open_password()
        tries = 0
        while True:
            yield lambda: g.ui._modal_state.get("result") is not None
            r = g.ui._modal_state.get("result")
            if r is False:
                g.ui.close_modal()
                g.set_mouse(True)
                return False
            if r.replace(" ", "") in answers:
                g.audio.play("ding", vol=0.6)
                g.ui.close_modal()
                g.set_mouse(True)
                return True
            tries += 1
            g.audio.play("blip_lo", vol=0.6)
            g.ui.password_message("Wrong password. " + (hint if tries >= 1 else ""))
            g.ui._modal_state["text"] = ""
            g.ui._modal_state["t"].text = "_"

    # ------------------------------------------------------------------
    # props and items the story places
    # ------------------------------------------------------------------
    def prop(self, key, ent):
        self.remove_prop(key)
        self.props[key] = ent
        return ent

    def remove_prop(self, key):
        e = self.props.pop(key, None)
        if e is not None:
            destroy(e)

    def item(self, key, model, pos, name, prompt, on_take, rot=0.0, scale=1.0, bob=False, spin=False, glow=0.0,
             radius=0.4, reach=2.6, cond=None):
        """A pickup in the world. on_take(g) may return a generator."""
        g = self.g
        ik = "st_" + key
        g.world.add_item(ik, model, pos, rot, scale, bob, spin, glow)
        ia = g.ia.add(Interactable(ik, pos, radius, name, None, prompt, reach))
        ia.handlers.append(Handler(prompt, on_take, cond, "global"))
        return ia

    def remove_item(self, key):
        g = self.g
        g.world.remove_item("st_" + key)
        g.ia.remove("st_" + key)

    def take_item(self, key, inv_key, n=1):
        self.remove_item(key)
        self.g.inv.add(inv_key, n)

    # ------------------------------------------------------------------
    # overlay (hiding in the wardrobe)
    # ------------------------------------------------------------------
    def show_overlay(self):
        self.hide_overlay()
        g = self.g
        A = g.ui.aspect
        r = Entity(parent=g.ui.root, z=-0.2)
        Entity(parent=r, model="quad", color=C(0.02, 0.015, 0.01, 0.96), scale=((A + 0.2) / 2 - 0.02, 1.2),
               x=-(A + 0.2) / 4 - 0.01)
        Entity(parent=r, model="quad", color=C(0.02, 0.015, 0.01, 0.96), scale=((A + 0.2) / 2 - 0.02, 1.2),
               x=(A + 0.2) / 4 + 0.01)
        txt(r, "Hiding in the wardrobe.  [E] Get out", 0, -0.44, 1.0, DIM, origin=(0, 0))
        self.overlay = r

    def hide_overlay(self):
        ov = getattr(self, "overlay", None)
        if ov is not None:
            destroy(ov)
        self.overlay = None

    # ------------------------------------------------------------------
    # friends
    # ------------------------------------------------------------------
    FRIEND_SPOTS = {
        "cowleen": (-49.0, 0, -16.0, 160),
        "moozart": (-39.0, 0, -52.0, 200),
        "sirloin": (-35.5, 0, -44.5, 300),
        "cowpernicus": (-46.5, 0, -30.0, 40),
        "mooriarty": (-71.8, 0, -27.5, 90),
        "moomaw": (-34.0, 0, -17.0, 250),
    }

    def place_friends_default(self):
        g = self.g
        for k, c in g.cows.items():
            x, y, z, yaw = self.FRIEND_SPOTS[k]
            c.teleport((x, y, z), yaw)
            c.stop()
            c.look = "player"
            c.graze = k in ("moomaw", "sirloin")

    # ------------------------------------------------------------------
    # small shared cutscene helpers
    # ------------------------------------------------------------------
    def face_each_other(self, a, b):
        a.yaw = math.degrees(math.atan2(b.x - a.x, b.z - a.z))
        b.yaw = math.degrees(math.atan2(a.x - b.x, a.z - b.z))

    def walk_npc(self, npc, target, speed=2.0, timeout=20.0):
        npc.goto(target, speed)
        t0 = self.g.env.time
        yield lambda: not npc.path or self.g.env.time - t0 > timeout
        if npc.path:
            # didn't make it in time: finish the move instantly so a cutscene never hangs
            npc.teleport(target)

    def lock_hud_music(self, name, vol=0.8, fade=1.5):
        self.music_locked = True
        self.g.audio.music_play(name, vol, fade)

    def unlock_music(self):
        self.music_locked = False

    # ------------------------------------------------------------------
    # ending
    # ------------------------------------------------------------------
    def epilogue(self):
        """Generator: a few short cards over black, then back to the title (no credits roll)."""
        g = self.g
        r = Entity(parent=g.ui.root, z=-0.95)
        self.credits_root = r
        for text in self.epilogue_lines():
            t = txt(r, text, 0, 0.02, 1.35, CREAM, origin=(0, 0), wrap=54, font=g.ui.fonts.get("serif"))
            t.color = C(1, 1, 1, 0)
            for k in range(24):
                t.color = C(0.98, 0.95, 0.86, k / 23)
                yield None
            yield 2.2 + len(text) * 0.03
            for k in range(16):
                t.color = C(0.98, 0.95, 0.86, 1 - k / 15)
                yield None
            destroy(t)
        destroy(r)
        self.credits_root = None

    def epilogue_lines(self):
        out = ["The herd crossed the county line by noon. The rooster rode the bull. Nobody counted them."]
        if self.done("chuck_shot"):
            out.append("Chuck's funeral fund raised eleven dollars. All from Dale.")
        else:
            out.append("Chuck kept the farm. He grows soybeans now, and says it's for the money. He has never once "
                       "been good with money.")
        if self.done("dale_cancelled"):
            out.append("Dale never got over the potato salad email.")
        else:
            out.append("Dale waited on the porch till four, then ate the potato salad alone.")
        if self.done("sq_helm"):
            out.append("Moogenes still lives in the bucket.")
        if self.done("sq_specs"):
            out.append("Moothagoras found a star he was sure was Moobius. It's a satellite. He checked.")
        if self.done("sq_photo"):
            out.append("Heifercleitus tells the calves Big Earl fought a bear. He did not.")
        if self.done("ledger_read"):
            out.append("The ledger at Happy Acres has room for four hundred more lines. Nobody has written in it "
                       "since.")
        out += [
            "None of this happened, of course. Cows can't do geometry, or read email, or hold a funeral.",
            "They can be afraid. They know one another apart. A cow whose calf is taken will call for it for days.",
            "Moocrates would want to know which of those things was supposed to be the reason.",
            "Somebody should still buy milk.",
        ]
        return out
