"""Story runner: title screen, days, steps, checkpoints, conversations, ending.

The seven days live in days.py. Every step is idempotent: it records a flag when it
finishes, and a restarted day skips any step whose flag is already set. World state
(doors, props, who's where) is rebuilt from flags at the start of each day, so a
checkpoint is just "which day" plus the flags and inventory at that moment.
"""
from __future__ import annotations

import math
import random

import time

from ursina import BoxCollider, Button, Entity, Quad, Text, Vec3, application, camera, color, destroy, mouse

from .days import DayScripts, DAYS
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
    ("rock_pouch", "Rock Pouch", 2, "Carry six rocks instead of three."),
    ("rubber_chicken", "Rubber Chicken", 3, "Squeaky, throwable, and it doesn't conduct electricity."),
    ("moustache", "Fake Moustache", 4, "Wear it with a straw hat and Chuck will think you're Dale. Walk, don't run."),
    ("coffee", "Suspiciously Strong Coffee", 2, "Gallop twice as long for the rest of the day. Drink it here."),
    ("tincan", "Mysterious Tin Can", 5, "No refunds."),
]

HERD_LINES = [
    "Moo. (Have you tried the grass by the fence? Same as the other grass.)",
    "Moo. (I'm lying down because it might rain. It might not. I'm covered either way.)",
    "Moo. (Chuck scratched my ears yesterday. I'm still thinking about it.)",
    "Moo. (Do you ever look at the pond and think about the pond?)",
    "Moo. (I've been chewing this since Tuesday. Last Tuesday.)",
    "Moo. (Sir Loin told me he's descended from royalty. He told the fence post the same thing.)",
    "Moo. (The hens say the rooster has a black belt. I don't know what that is.)",
    "Moo. (I'm going to stand here. Then maybe over there. Big day.)",
    "Moo. (Mooriarty sold me a Golden Clover. It was a regular clover. Painted.)",
    "Moo. (If you see Clarabelle, tell her she still owes me a salt lick.)",
    "Moo. (I heard the truck on Thursday. I didn't like it.)",
    "Moo. (There's a fly on my back. Don't tell it I know.)",
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
        self._leave_title(lambda: self.start_day(day))

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
            if not k.startswith("clover_"):
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
        f.hearing = 1.0
        f.range_day = 24.0
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
        camera.rotation = (0, 0, 0)
        camera.look_at((cx * 0.5, 4, cz * 0.5))
        camera.rotation_z = 0

    def title_input(self, key):
        if self.g.ui.modal == "settings":
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
            "cowbell": "Your old cowbell. It still smells a bit like you. [R] throws it.",
            "tincan": "You shake the tin can. Nothing. You shake it again. Still nothing. Mysterious.",
            "pencil": "You chew the pencil for a while. It's a good pencil.",
            "pliers": "You click the pliers at nothing. Snip snip.",
            "tractor_key": "WORLD'S OKAYEST FARMER, says the keychain. Sunday, then.",
            "score": "Symphony No. 1 in Moo Major. For Forty-Seven. You can hear it when you look at it.",
            "page": "MON fix fence (AGAIN). TUE oil tractor. SUN #47 -> PROCESSING. Buy milk.",
            "photo": "Chuck and Big Earl, Best in Show 2009. Moomaw would want this.",
            "shotgun": "Ol' Bessie. You hold her very carefully. Your tongue stays well away from the trigger.",
            "plank": "It's a plank. The cattle grid wants three of them.",
            "house_key": "The spare key. It came out of a gnome.",
            "sparkplug": "It smells of vinegar. It goes in the tractor.",
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
        return self.hint_text or "Nothing to do right now but chew. Talk to the others, or explore."

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
        line = HERD_LINES[(cow.idx * 7 + self.talk_i.get(f"herd{cow.idx}", 0)) % len(HERD_LINES)]
        self.talk_i[f"herd{cow.idx}"] = self.talk_i.get(f"herd{cow.idx}", 0) + 1
        yield from g.talk([(cow, line)])
        return True

    def side_quest_talk(self, key):
        """Handing over favors. Returns True if something happened."""
        g = self.g
        if key == "sirloin" and g.inv.has("bucket") and not self.done("sq_helm"):
            g.inv.remove("bucket")
            self.setf("sq_helm")
            g.cows["sirloin"].model.set_acc("bucket")
            g.audio.play("metal_clang", vol=0.8)
            yield from g.talk([
                ("sirloin", "Is that... a helm? For me?"),
                ("sirloin", "It fits. Of course it fits. It was always meant to fit."),
                ("sirloin", "Kneel, Forty-Seven. Well. Stand, since you're a cow. We're all standing."),
                ("sirloin", "I dub thee Dame Forty-Seven of the Pasture. When the fighting starts, I ride at your side."),
                ("you", "Moo. (You're going to walk into the fence wearing that.)"),
                ("sirloin", "A knight does not walk into fences. A knight is walked into BY fences."),
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
                ("cowpernicus", "Oh. Oh, the sky has EDGES. I thought stars were blurry on purpose."),
                ("cowpernicus", "Give me a second. I've been meaning to chart every Golden Clover on the farm by their glint."),
                ("cowpernicus", "Done. They're on your map now. Tab to look. Don't tell Mooriarty I did this."),
            ])
            g.side_quest("specs", state="done")
            g.ui.toast("Golden Clovers marked on your map", "clover", col=BRASS)
            return True
        if key == "moomaw" and g.inv.has("photo") and not self.done("sq_photo"):
            g.inv.remove("photo")
            self.setf("sq_photo")
            yield from g.talk([
                ("moomaw", "Oh. Oh, look at him. Look at that big dumb handsome face."),
                ("moomaw", "Best in Show, 2009. He hated that ribbon. He ate half of it."),
                ("moomaw", "Thank you, sweetheart. Here. This was his. He found it by the gate the spring you were born."),
                ("moomaw", "If Chuck ever gets his hands on you, drop it. He's tripped on it before. Twice."),
            ])
            g.inv.add("horseshoe")
            g.side_quest("photo", state="done")
            return True
        return False

    def shop(self):
        g = self.g
        done = {"d": False}

        def entries():
            out = []
            for key, label, price, desc in SHOP:
                owned = self.done(f"shop_{key}")
                out.append((key if key != "rock_pouch" else "rock", label, price, desc, owned))
            return out

        def buy(key):
            k = "rock_pouch" if key == "rock" else key
            price = next(p for kk, _, p, _ in SHOP if kk == k)
            if self.done(f"shop_{k}"):
                return
            if g.flags.get("clovers", 0) < price:
                g.audio.play("blip_lo", vol=0.5)
                g.ui.toast("Not enough Golden Clovers")
                return
            g.flags["clovers"] -= price
            self.setf(f"shop_{k}")
            g.stats["bought"] = g.stats.get("bought", 0) + 1
            g.audio.play("clover", vol=0.6)
            if k == "rock_pouch":
                self.setf("rock_pouch")
                g.ui.toast("Rock Pouch: carry up to 6 rocks", "rock")
            elif k == "coffee":
                self.setf("coffee")
                g.ui.toast("You drink it on the spot. Gallop for longer today.", "coffee")
            else:
                g.inv.add(k)
            g.refresh_hotbar()
            reopen()

        def close():
            g.ui.close_modal()
            g.set_mouse(True)
            done["d"] = True

        def reopen():
            g.ui.open_shop("MOORIARTY'S", entries(), g.flags.get("clovers", 0), buy, close)

        yield from g.talk([("mooriarty", random.choice([
            "Psst. Over here. Take a look. Don't touch unless you're buying.",
            "Back again. I knew you would be. I know things.",
            "Golden Clovers only. Don't ask me where the merchandise comes from.",
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
    def credits(self):
        """Generator: epilogue, credits and the post-credits line."""
        g = self.g
        st = g.stats
        caught = st.get("caught", 0)
        lines_epi = self.epilogue_lines()
        r = Entity(parent=g.ui.root, z=-0.95)
        self.credits_root = r
        for text in lines_epi:
            t = txt(r, text, 0, 0.02, 1.35, CREAM, origin=(0, 0), wrap=54)
            t.color = C(1, 1, 1, 0)
            for k in range(30):
                t.color = C(0.98, 0.95, 0.86, k / 29)
                yield None
            yield 3.2 + len(text) * 0.03
            for k in range(20):
                t.color = C(0.98, 0.95, 0.86, 1 - k / 19)
                yield None
            destroy(t)
        yield 0.6
        roll = [
            ("BREAKOWT", "title"),
            ("Seven Days to Steak", "sub"),
            ("", ""),
            ("A game by Ethan Mader", "head"),
            ("with Claude", "small"),
            ("", ""),
            ("Cast", "head"),
            ("Forty-Seven .......... you", "small"),
            ("Cowleen .......... herself", "small"),
            ("Moozart .......... #12", "small"),
            ("Sir Loin .......... a knight, he says", "small"),
            ("Cowpernicus .......... the brains", "small"),
            ("Mooriarty .......... no comment", "small"),
            ("Moomaw .......... in memory of Big Earl", "small"),
            ("Cluck Norris .......... himself", "small"),
            ("Chuck .......... Charles Rumpley", "small"),
            ("Dale .......... never seen", "small"),
            ("", ""),
            ("Music", "head"),
            ("Symphony No. 1 in Moo Major, by Moozart", "small"),
            ("finished by Forty-Seven", "small"),
            ("", ""),
            ("Your week", "head"),
            (f"Times caught: {caught}", "small"),
            (f"Golden Clovers found: {self.flags.get('clovers_total', 0)} of {len(g.world.clover_spots)}", "small"),
            (f"Rocks thrown: {st.get('thrown', 0)}", "small"),
            (f"Moos: {st.get('moos', 0)}", "small"),
            (f"Pathetic hops: {st.get('hops', 0)}", "small"),
            (f"Times Chuck fell over: {st.get('chuck_trips', 0)}", "small"),
            (f"Things knocked over: {st.get('knocked', 0)}", "small"),
            (f"Favors done: {sum(1 for k in ('sq_helm', 'sq_specs', 'sq_photo') if self.done(k))} of 3", "small"),
            ("", ""),
            ("No cows were harmed in the making of this game.", "small"),
            ("One farmer was.", "small"),
        ]
        col = Entity(parent=r)
        y = -0.62
        for text, kind in roll:
            if kind == "title":
                t = txt(col, text, 0, y, 3.4, CREAM, origin=(0, 0), font=g.fonts.get("title"))
                y -= 0.11
            elif kind == "sub":
                txt(col, text, 0, y, 1.4, BRASS, origin=(0, 0))
                y -= 0.07
            elif kind == "head":
                txt(col, text, 0, y, 1.3, BRASS, origin=(0, 0))
                y -= 0.055
            elif kind == "small":
                txt(col, text, 0, y, 1.0, CREAM, origin=(0, 0))
                y -= 0.045
            else:
                y -= 0.04
        total = -y + 0.62
        speed = 0.055
        t = 0.0
        while col.y < total + 0.1:
            col.y += speed * min(0.05, time.dt)
            if g._advance:
                col.y += 0.02
            yield None
        g._advance = False
        destroy(col)
        yield 1.0
        t = txt(r, "Also, somebody should buy milk.", 0, 0, 1.4, CREAM, origin=(0, 0))
        g.audio.play("ding", vol=0.4)
        yield 4.0
        destroy(t)
        destroy(r)
        self.credits_root = None

    def epilogue_lines(self):
        out = [
            "The herd crossed the county line a little after noon. Forty-seven cows, one bull, and a rooster riding on the bull.",
        ]
        if self.done("dale_cancelled"):
            out.append("Dale got an email saying Chuck had gone vegetarian. He still brings it up at bowling.")
        else:
            out.append("Dale showed up at one o'clock with the good potato salad. He waited on the porch until four.")
        out.append("Cluck Norris runs the coop at an animal sanctuary two counties over. The hens there have a curfew.")
        if self.done("sq_specs"):
            out.append("Cowpernicus named a star after Moozart. He says the paperwork is pending.")
        if self.done("sq_helm"):
            out.append("Sir Loin still wears the bucket. He has asked to be buried in it. He is four.")
        if self.done("sq_photo"):
            out.append("Moomaw keeps the photo of Big Earl under a flat rock by the new pond.")
        out.append("Mooriarty sold the tractor. Nobody knows who to.")
        out.append("Every evening at sunset, the whole herd moos Moozart's symphony. Badly, and all the way through.")
        out.append("Happy Acres Family Farm is closed. The sign is still up.")
        return out
