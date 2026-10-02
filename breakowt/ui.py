"""HUD, dialogue box, menus and modal screens."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw
from ursina import Button, Entity, Quad, Text, Texture, camera, color, destroy, window

from .engine.assets import tex
from . import texgen

C = color.rgba
PANEL = C(0.08, 0.07, 0.06, 0.78)
PANEL_LIGHT = C(0.16, 0.14, 0.12, 0.9)
CREAM = C(0.98, 0.95, 0.86, 1)
BRASS = C(0.98, 0.78, 0.25, 1)
DIM = C(0.75, 0.72, 0.65, 1)
RED = C(0.95, 0.3, 0.25, 1)
DLG_WRAP = 74
GREEN = C(0.5, 0.9, 0.45, 1)

SPEAKER_COLORS = {
    "Moocrates": C(0.98, 0.7, 0.45, 1),
    "Moobius": C(0.8, 0.8, 1.0, 1),
    "Moogenes": C(1.0, 0.45, 0.4, 1),
    "Moothagoras": C(0.5, 0.85, 1.0, 1),
    "Epicowrus": C(0.75, 0.75, 0.75, 1),
    "Heifercleitus": C(0.9, 0.65, 0.95, 1),
    "Chuck": C(0.95, 0.85, 0.35, 1),
    "Cluckydides": C(1.0, 0.55, 0.2, 1),
    "You": C(1.0, 0.95, 0.9, 1),
    "Forty-Seven": C(1.0, 0.95, 0.9, 1),
}


def panel(parent, x, y, w, h, col=PANEL, radius=0.02, origin=(0, 0), z=0):
    return Entity(parent=parent, model=Quad(radius=radius, aspect=w / h if h else 1), scale=(w, h),
                  position=(x, y, z), color=col, origin=origin)


def wrap_str(s, width):
    """Greedy word wrap by character count (keeps existing line breaks)."""
    if not width or not s:
        return s
    out = []
    for line in s.split("\n"):
        indent = line[:len(line) - len(line.lstrip(" "))]
        cur = indent
        for word in line.lstrip(" ").split(" "):
            if cur.strip() and len(cur) + 1 + len(word) > width:
                out.append(cur)
                cur = indent + word
            else:
                cur = f"{cur} {word}" if cur.strip() else cur + word
        out.append(cur)
    return "\n".join(out)


class WText(Text):
    """Text that re-wraps every time it is set (Ursina's wordwrap only applies once)."""
    _wrap_chars = None

    def _set_wrapped(self, value):
        Text.text_setter(self, wrap_str(value, self._wrap_chars) if self._wrap_chars else value)

    text = property(Text.text_getter, _set_wrapped)


def txt(parent, s, x, y, scale=1.0, col=CREAM, origin=(-0.5, 0.5), wrap=None, font=None, z=-0.01, tags=False):
    t = WText("", parent=parent, position=(x, y, z), scale=scale, color=col, origin=origin, use_tags=tags)
    if font:
        t.font = font
    t._wrap_chars = wrap
    if s:
        t.text = s
    return t


class UI:
    def __init__(self, g, fonts):
        self.g = g
        self.fonts = fonts
        self.aspect = window.aspect_ratio
        A = self.aspect
        self.L = -A / 2
        self.R = A / 2
        self.root = Entity(parent=camera.ui)
        self.vignette = Entity(parent=self.root, model="quad", texture=tex("vignette"), scale=(A + 0.02, 1.02), z=1,
                               color=C(1, 1, 1, 1))
        self.hud = Entity(parent=self.root)
        self.modal = None
        self.modal_root = None
        self.toasts = []
        self.popup_t = 0.0
        self.bark_t = 0.0
        self.flash_t = 0.0
        self.flash_dur = 0.0
        self.title_t = 0.0

        # --- day header + objectives (top-left)
        self.day_text = txt(self.hud, "", self.L + 0.03, 0.47, 1.35, BRASS, font=fonts.get("title"))
        self.day_sub = txt(self.hud, "", self.L + 0.03, 0.425, 0.85, DIM)
        self.obj_texts = [txt(self.hud, "", self.L + 0.03, 0.38 - i * 0.034, 0.95, CREAM, wrap=52) for i in range(7)]

        # --- crosshair + prompt
        self.cross = Entity(parent=self.hud, model=Quad(radius=0.5), scale=0.006, color=C(1, 1, 1, 0.6))
        self.prompt_bg = Entity(parent=self.hud, model=Quad(radius=0.3), color=C(0, 0, 0, 0.55), y=-0.12, scale=(0.3, 0.045),
                                enabled=False)
        self.prompt = txt(self.hud, "", 0, -0.12, 1.05, CREAM, origin=(0, 0))

        # --- popup subtitle (examine text, moo thoughts)
        self.popup_bg = Entity(parent=self.hud, model=Quad(radius=0.3), color=C(0, 0, 0, 0.5), y=-0.3, scale=(0.9, 0.06),
                               enabled=False)
        self.popup = txt(self.hud, "", 0, -0.3, 1.05, C(1, 1, 0.92, 1), origin=(0, 0), wrap=70)

        # --- bark line (farmer mutterings heard at a distance)
        self.bark_bg = Entity(parent=self.hud, model=Quad(radius=0.3), color=C(0, 0, 0, 0.45), y=0.34, scale=(0.9, 0.05),
                              enabled=False)
        self.bark = txt(self.hud, "", 0, 0.34, 1.05, SPEAKER_COLORS["Chuck"], origin=(0, 0), wrap=70)

        # --- meters (bottom-left: the hotbar grows leftwards from the bottom-right corner, so keep clear of it)
        self.stam_bg = Entity(parent=self.hud, model="quad", color=C(0, 0, 0, 0.5), position=(self.L + 0.13, -0.465),
                              scale=(0.2, 0.01))
        self.stam = Entity(parent=self.hud, model="quad", color=C(0.95, 0.85, 0.5, 0.9), position=(self.L + 0.03, -0.465),
                           scale=(0.2, 0.01), origin=(-0.5, 0))
        self.susp_icon = txt(self.hud, "", 0, 0.415, 2.4, BRASS, origin=(0, 0), font=fonts.get("title"))
        self.susp_bg = Entity(parent=self.hud, model="quad", color=C(0, 0, 0, 0.5), position=(0, 0.375), scale=(0.24, 0.012))
        self.susp = Entity(parent=self.hud, model="quad", color=BRASS, position=(-0.12, 0.375), scale=(0, 0.012), origin=(-0.5, 0))
        self.hearts = txt(self.hud, "", self.L + 0.03, -0.38, 1.6, RED)
        # a standing reminder of where the journal, the map and hints live
        self.keys_hint = txt(self.hud, "[Tab] journal & map    [H] hint", self.L + 0.03, -0.432, 0.78,
                             C(0.85, 0.82, 0.75, 0.75))
        self.boss_name = txt(self.hud, "", 0, 0.46, 1.1, CREAM, origin=(0, 0))
        self.boss_bg = Entity(parent=self.hud, model="quad", color=C(0, 0, 0, 0.6), position=(0, 0.43), scale=(0.7, 0.018))
        self.boss_bar = Entity(parent=self.hud, model="quad", color=RED, position=(-0.35, 0.43), scale=(0.7, 0.018), origin=(-0.5, 0))
        for e in (self.susp_bg, self.susp, self.boss_bg, self.boss_bar):
            e.enabled = False

        # --- hotbar (bottom-right)
        self.hot_root = Entity(parent=self.hud)
        self.hot_slots = []
        self.clover_text = txt(self.hud, "", self.R - 0.03, 0.47, 1.0, BRASS, origin=(0.5, 0.5))

        # --- toasts (top-right)
        self.toast_root = Entity(parent=self.hud)

        # --- dialogue box (grows upward with the number of lines; see dlg_show)
        self.dlg = Entity(parent=self.root, enabled=False)
        self.dlg_bg = Entity(parent=self.dlg, model=Quad(radius=0.02, aspect=1.25 / 0.2), scale=(1.25, 0.2), position=(0, -0.36),
                             color=PANEL)
        self.dlg_name = txt(self.dlg, "", -0.6, -0.27, 1.25, BRASS, font=fonts.get("ui"))
        self.dlg_text = txt(self.dlg, "", -0.6, -0.31, 1.18, CREAM, font=fonts.get("body"))
        self.dlg_hint = txt(self.dlg, "[Space]", 0.6, -0.44, 0.8, DIM, origin=(0.5, 0))
        self.dlg_top = -0.26
        self._dlg_quads = {}
        self.dlg_full = ""
        self.dlg_shown = 0.0
        self.dlg_speed = 55.0
        self.choice_root = Entity(parent=self.root, enabled=False)
        self.choice_items = []
        self.choice_sel = 0
        self.choice_result = None

        # --- cutscene letterbox, fader, flash, title cards
        self.lb_top = Entity(parent=self.root, model="quad", color=C(0, 0, 0, 1), scale=(A + 0.2, 0.12), y=0.56, z=-0.5)
        self.lb_bot = Entity(parent=self.root, model="quad", color=C(0, 0, 0, 1), scale=(A + 0.2, 0.12), y=-0.56, z=-0.5)
        self.lb = 0.0
        self.lb_target = 0.0
        self.flash_q = Entity(parent=self.root, model="quad", color=C(1, 0, 0, 0), scale=(A + 0.2, 1.2), z=-0.6)
        self.fader = Entity(parent=self.root, model="quad", color=C(0, 0, 0, 0), scale=(A + 0.2, 1.2), z=-0.8)
        self.fade_alpha = 0.0
        self.fade_col = (0, 0, 0)
        self.card_big = txt(self.root, "", 0, 0.04, 4.0, CREAM, origin=(0, 0), font=fonts.get("title"), z=-0.9)
        self.card_small = txt(self.root, "", 0, -0.06, 1.5, BRASS, origin=(0, 0), z=-0.9)
        self.card_alpha = 0.0
        self.center_text = txt(self.root, "", 0, 0.0, 1.4, CREAM, origin=(0, 0), wrap=60, z=-0.95)
        self.hud_visible = True
        self.map_tex = None

    # ------------------------------------------------------------------
    # HUD setters
    # ------------------------------------------------------------------
    def set_day(self, title, sub):
        self.day_text.text = title
        self.day_sub.text = sub

    def set_objectives(self, lines):
        for i, t in enumerate(self.obj_texts):
            if i < len(lines):
                text, done = lines[i]
                t.text = ("[x] " if done else "- ") + text
                t.color = DIM if done else CREAM
            else:
                t.text = ""

    def set_prompt(self, text):
        if text:
            self.prompt.text = text
            w = max(0.22, len(text) * 0.0125 + 0.05)
            self.prompt_bg.scale = (w, 0.045)
            self.prompt_bg.enabled = True
            self.cross.color = BRASS
            self.cross.scale = 0.01
        else:
            self.prompt.text = ""
            self.prompt_bg.enabled = False
            self.cross.color = C(1, 1, 1, 0.55)
            self.cross.scale = 0.006

    def popup_sub(self, text, dur=None):
        self.popup.text = text
        n = len(text)
        lines = wrap_str(text, 70).split("\n")
        w = max(len(ln) for ln in lines)
        self.popup_bg.scale = (min(1.3, max(0.3, w * 0.0135 + 0.06)), 0.045 * len(lines) + 0.02)
        self.popup_bg.enabled = True
        self.popup_t = dur if dur else max(3.0, 1.5 + n * 0.045)

    def bark_line(self, text, speaker="Chuck", dur=None):
        self.bark.text = f"{speaker}: {text}"
        self.bark.color = SPEAKER_COLORS.get(speaker, CREAM)
        lines = wrap_str(f"{speaker}: {text}", 70).split("\n")
        self.bark_bg.scale = (max(len(ln) for ln in lines) * 0.0135 + 0.06, 0.045 * len(lines) + 0.02)
        self.bark_bg.enabled = True
        self.bark_t = dur if dur else max(2.5, 1.2 + len(text) * 0.05)

    def toast(self, text, icon=None, col=None):
        e = Entity(parent=self.toast_root, position=(self.R - 0.03, 0.40 - len(self.toasts) * 0.06))
        w = min(0.55, len(text) * 0.0125 + 0.09)
        Entity(parent=e, model=Quad(radius=0.3), color=PANEL, scale=(w, 0.05), origin=(0.5, 0))
        if icon and tex("icon_" + icon):
            Entity(parent=e, model="quad", texture=tex("icon_" + icon), scale=0.045, x=-w + 0.03, z=-0.01)
        txt(e, text, -0.015, 0.0, 1.0, col or CREAM, origin=(0.5, 0))
        self.toasts.append([e, 3.5])

    def relayout(self):
        """The window changed shape (fullscreen toggle, resize): move everything pinned to the left or right edge."""
        A = window.aspect_ratio
        if abs(A - self.aspect) < 1e-3:
            return
        self.aspect, self.L, self.R = A, -A / 2, A / 2
        self.vignette.scale = (A + 0.02, 1.02)
        for e in [self.day_text, self.day_sub, self.hearts, self.keys_hint] + self.obj_texts:
            e.x = self.L + 0.03
        self.stam_bg.x, self.stam.x = self.L + 0.13, self.L + 0.03
        self.clover_text.x = self.R - 0.03
        for t in self.toasts:
            t[0].x = self.R - 0.03
        for e in (self.lb_top, self.lb_bot):
            e.scale_x = A + 0.2
        for e in (self.flash_q, self.fader):
            e.scale_x = A + 0.2
        k, self._hearts_key = getattr(self, "_hearts_key", None), None
        if k:
            self.set_health(*k)
        self.g.refresh_hotbar()

    def set_stamina(self, v, visible=True):
        self.stam.scale_x = 0.2 * max(0, v)
        self.stam.enabled = self.stam_bg.enabled = visible and v < 0.99

    def set_suspicion(self, v, state=""):
        on = v > 0.01 or state == "!"
        self.susp.enabled = self.susp_bg.enabled = on and state != "!"
        self.susp.scale_x = 0.24 * min(1.0, v)
        self.susp.color = RED if v > 0.7 else BRASS
        self.susp_icon.text = state if on else ""
        self.susp_icon.color = RED if state == "!" else BRASS

    def set_health(self, n, mx, visible):
        key = (n, mx, visible)
        if getattr(self, "_hearts_key", None) == key:
            return
        self._hearts_key = key
        for e in getattr(self, "_heart_ents", []):
            destroy(e)
        self._heart_ents = []
        if not visible:
            return
        for i in range(mx):
            t = tex("icon_heart" if i < n else "icon_heart_empty")
            e = Entity(parent=self.hud, model="quad", texture=t, scale=0.055, position=(self.L + 0.06 + i * 0.062, -0.4))
            self._heart_ents.append(e)

    def set_boss(self, name, frac, visible=True):
        for e in (self.boss_bg, self.boss_bar):
            e.enabled = visible
        self.boss_name.text = name if visible else ""
        self.boss_bar.scale_x = 0.7 * max(0.0, frac)

    def set_hotbar(self, entries, selected, clovers):
        for s in self.hot_slots:
            destroy(s)
        self.hot_slots = []
        n = len(entries)
        # past ten slots the bar shrinks to keep within the right half of the screen
        k = min(1.0, 10 / max(n, 1))
        step = 0.085 * k
        for i, (key, icon, count, label) in enumerate(entries):
            x = self.R - 0.06 - (n - 1 - i) * step
            e = Entity(parent=self.hot_root, position=(x, -0.43), scale=k)
            sel = i == selected
            Entity(parent=e, model=Quad(radius=0.15), color=C(0.98, 0.78, 0.25, 0.85) if sel else PANEL, scale=0.075)
            if tex("icon_" + icon):
                Entity(parent=e, model="quad", texture=tex("icon_" + icon), scale=0.064, z=-0.01)
            if count and count > 1:
                txt(e, str(count), 0.034, -0.02, 0.9, CREAM, origin=(0.5, 0))
            if i < 10:
                txt(e, "1234567890"[i], -0.034, 0.034, 0.7, DIM if not sel else C(0.1, 0.1, 0.1, 1))
            if sel:
                # keep the label on screen for the right-most slots
                lab_w = len(label) * 0.0105 * k
                lx = min(0.0, (self.R - 0.02 - lab_w / 2) - x) / k
                txt(e, label, lx, 0.058, 0.85, CREAM, origin=(0, 0))
            self.hot_slots.append(e)
        self.clover_text.text = f"Golden Clovers: {clovers}" if clovers else ""

    def flash(self, col, dur=0.3):
        self.flash_q.color = C(col[0], col[1], col[2], 0.45)
        self.flash_t = dur
        self.flash_dur = dur

    def letterbox(self, on):
        self.lb_target = 1.0 if on else 0.0

    def show_hud(self, on):
        self.hud_visible = on
        self.hud.enabled = on

    def set_fade(self, a, col=(0, 0, 0)):
        self.fade_alpha = a
        self.fade_col = col
        self.fader.color = C(col[0], col[1], col[2], a)

    def title_card(self, big, small="", alpha=1.0):
        self.card_big.text = big
        self.card_small.text = small
        self.card_alpha = alpha
        self.card_big.color = C(0.98, 0.95, 0.86, alpha)
        self.card_small.color = C(0.98, 0.78, 0.25, alpha)

    def set_center_text(self, s, alpha=1.0, col=(0.98, 0.95, 0.86)):
        self.center_text.text = s
        self.center_text.color = C(col[0], col[1], col[2], alpha)

    # ------------------------------------------------------------------
    # dialogue
    # ------------------------------------------------------------------
    DLG_BOTTOM = -0.43      # just above the cutscene letterbox (which covers y < -0.44)
    DLG_LINE = 0.032        # one line of body text at scale 1.18

    def dlg_show(self, name, text):
        self.dlg.enabled = True
        self.dlg_name.text = name
        self.dlg_name.color = SPEAKER_COLORS.get(name, CREAM)
        self.dlg_full = wrap_str(text, DLG_WRAP)
        self.dlg_shown = 0.0
        self.dlg_text.text = ""
        self.dlg_hint.enabled = False
        # size the box to the text, growing upward from a fixed bottom edge, so a long line never runs off
        # the bottom of the screen (or under the letterbox)
        n = self.dlg_full.count("\n") + 1
        h = 0.09 + n * self.DLG_LINE + (0.0 if name else -0.035)
        bottom = self.DLG_BOTTOM
        top = bottom + h
        qk = (n, bool(name))
        if qk not in self._dlg_quads:
            self._dlg_quads[qk] = Quad(radius=0.02, aspect=1.25 / h)
        self.dlg_bg.model = self._dlg_quads[qk]
        self.dlg_bg.scale = (1.25, h)
        self.dlg_bg.y = bottom + h / 2
        self.dlg_name.y = top - 0.012
        self.dlg_text.y = top - (0.05 if name else 0.018)
        self.dlg_hint.y = bottom + 0.018
        self.dlg_top = top

    def dlg_hide(self):
        self.dlg.enabled = False
        self.choice_root.enabled = False

    def dlg_revealed(self):
        return self.dlg_shown >= len(self.dlg_full)

    def dlg_complete(self):
        self.dlg_shown = len(self.dlg_full)
        self.dlg_text.text = self.dlg_full

    def show_choices(self, options):
        for c in self.choice_items:
            destroy(c)
        self.choice_items = []
        self.choice_root.enabled = True
        self.choice_sel = 0
        self.choice_result = None
        n = len(options)
        for i, opt in enumerate(options):
            y = -0.2 + (n - 1 - i) * 0.055
            b = Button(parent=self.choice_root, text=f"{i + 1}.  {opt}", position=(0, y), scale=(0.9, 0.048),
                       color=PANEL_LIGHT, text_origin=(-0.5, 0), radius=0.25)
            b.text_entity.x = -0.47
            b.text_entity.scale *= 0.9
            b.on_click = (lambda i=i: self._pick(i))
            self.choice_items.append(b)
        self._hl()

    def _pick(self, i):
        self.choice_result = i
        self.g.audio.play("blip", vol=0.5)

    def _hl(self):
        for i, b in enumerate(self.choice_items):
            b.color = C(0.98, 0.78, 0.25, 0.95) if i == self.choice_sel else PANEL_LIGHT
            b.text_color = C(0.1, 0.08, 0.05, 1) if i == self.choice_sel else CREAM

    def choice_input(self, key):
        if not self.choice_items:
            return
        if key in ("w", "up arrow", "scroll up"):
            self.choice_sel = (self.choice_sel - 1) % len(self.choice_items)
            self._hl()
        elif key in ("s", "down arrow", "scroll down"):
            self.choice_sel = (self.choice_sel + 1) % len(self.choice_items)
            self._hl()
        elif key in ("enter", "space", "e"):
            self._pick(self.choice_sel)
        elif key in "123456" and len(key) == 1 and key.isdigit():
            i = int(key) - 1
            if i < len(self.choice_items):
                self._pick(i)

    def clear_choices(self):
        for c in self.choice_items:
            destroy(c)
        self.choice_items = []
        self.choice_root.enabled = False

    # ------------------------------------------------------------------
    # modal screens
    # ------------------------------------------------------------------
    def open_modal(self, name):
        self.close_modal()
        self.modal = name
        self.modal_root = Entity(parent=self.root, z=-0.3)
        self.g.set_mouse(False)
        return self.modal_root

    def close_modal(self):
        if self.modal_root is not None:
            destroy(self.modal_root)
        self.modal_root = None
        self.modal = None
        self._modal_state = {}

    def _fit(self, body, width, height, scale, lead=1.25, min_scale=0.7):
        """Largest text scale (from `scale` down) at which `body` wrapped to `width` fits in `height`."""
        s = scale
        while True:
            w = self._wrap_for(width, s)
            lines = wrap_str(body, w).count("\n") + 1
            if lines * 0.025 * s * lead <= height or s <= min_scale:
                return s, w
            s -= 0.04

    def show_document(self, title, body, footer="[E] / [Space] to close", paper=True, style=None):
        """style: 'note' (a sticky note: short scraps), 'paper' (ruled paper: the planner, letters) or
        'screen' (ChuckOS). Text is fitted to the sheet, so long documents shrink instead of spilling off."""
        style = style or (("note" if len(body) < 200 and body.count("\n") < 8 else "paper") if paper else "screen")
        r = self.open_modal("document")
        Entity(parent=r, model="quad", color=C(0, 0, 0, 0.6), scale=(3, 2), z=0.1)
        hand, body_f = self.fonts.get("hand"), self.fonts.get("body")
        if style == "note":
            w = h = 0.66
            sheet = Entity(parent=r, rotation_z=-2.5)
            Entity(parent=sheet, model="quad", color=C(0, 0, 0, 0.35), scale=(w, h), position=(0.012, -0.014, 0.06))
            Entity(parent=sheet, model="quad", color=C(0.99, 0.92, 0.5, 1), scale=(w, h), z=0.05)
            Entity(parent=sheet, model="quad", color=C(0.96, 0.86, 0.38, 1), scale=(w, 0.07), y=h / 2 - 0.035, z=0.045)
            Entity(parent=sheet, model="quad", color=C(1, 1, 1, 0.5), scale=(0.2, 0.05), y=h / 2 + 0.005,
                   rotation_z=4, z=0.04)
            ink = C(0.1, 0.12, 0.3, 1)
            txt(sheet, title, -w / 2 + 0.05, h / 2 - 0.09, 1.25, C(0.45, 0.35, 0.15, 1), font=hand)
            s, wr = self._fit(body, w - 0.1, h - 0.2, 1.55)
            txt(sheet, body, -w / 2 + 0.05, h / 2 - 0.16, s, ink, wrap=wr, font=hand)
            foot_col = C(0.85, 0.82, 0.75, 1)
            foot_y = -h / 2 - 0.05
        elif style == "paper":
            w, h = 0.98, 0.88
            sheet = Entity(parent=r, rotation_z=-1.0)
            Entity(parent=sheet, model="quad", color=C(0, 0, 0, 0.35), scale=(w, h), position=(0.014, -0.016, 0.06))
            Entity(parent=sheet, model="quad", texture=tex("paper"), scale=(w, h), color=C(1, 1, 1, 1), z=0.05)
            # ruled lines and the red margin
            for k in range(1, 22):
                Entity(parent=sheet, model="quad", color=C(0.45, 0.6, 0.85, 0.35), scale=(w - 0.04, 0.0025),
                       y=h / 2 - 0.12 - k * 0.034, z=0.045)
            Entity(parent=sheet, model="quad", color=C(0.85, 0.3, 0.3, 0.5), scale=(0.003, h - 0.02),
                   x=-w / 2 + 0.085, z=0.044)
            ink = C(0.12, 0.13, 0.32, 1)
            txt(sheet, title, -w / 2 + 0.11, h / 2 - 0.05, 1.7, ink, font=hand)
            s, wr = self._fit(body, w - 0.17, h - 0.2, 1.25)
            txt(sheet, body, -w / 2 + 0.11, h / 2 - 0.135, s, ink, wrap=wr, font=hand)
            foot_col = C(0.85, 0.82, 0.75, 1)
            foot_y = -h / 2 - 0.04
        else:
            w, h = 1.05, 0.84
            Entity(parent=r, model=Quad(radius=0.012, aspect=w / h), scale=(w + 0.012, h + 0.012),
                   color=C(0.55, 0.57, 0.6, 1), z=0.06)
            Entity(parent=r, model="quad", color=C(0.94, 0.95, 0.97, 1), scale=(w, h), z=0.05)
            Entity(parent=r, model="quad", color=C(0.12, 0.3, 0.62, 1), scale=(w, 0.055), y=h / 2 - 0.0275, z=0.045)
            txt(r, title, -w / 2 + 0.02, h / 2 - 0.012, 1.0, C(1, 1, 1, 1), font=self.fonts.get("ui"))
            txt(r, "_  []  x", w / 2 - 0.02, h / 2 - 0.012, 0.9, C(1, 1, 1, 0.8), origin=(0.5, 0.5))
            s, wr = self._fit(body, w - 0.08, h - 0.13, 1.05)
            txt(r, body, -w / 2 + 0.04, h / 2 - 0.085, s, C(0.08, 0.08, 0.12, 1), wrap=wr,
                font=self.fonts.get("mono") or body_f)
            foot_col = DIM
            foot_y = -h / 2 - 0.035
        txt(r, footer, 0, foot_y, 0.85, foot_col, origin=(0, 0))
        self.g.audio.play("paper" if style != "screen" else "type", vol=0.7)

    # --- ChuckOS Mail -----------------------------------------------------
    def open_mail(self, messages, title="ChuckOS Mail"):
        """An inbox: the message list on the left, the open message on the right. messages: list of
        (sender, subject, body). W/S or click to pick a message; E / Space / Esc to close."""
        r = self.open_modal("mail")
        Entity(parent=r, model="quad", color=C(0, 0, 0, 0.6), scale=(3, 2), z=0.1)
        w, h = 1.3, 0.84
        lw = 0.4
        Entity(parent=r, model=Quad(radius=0.012, aspect=w / h), scale=(w + 0.012, h + 0.012),
               color=C(0.55, 0.57, 0.6, 1), z=0.06)
        Entity(parent=r, model="quad", color=C(0.96, 0.96, 0.97, 1), scale=(w, h), z=0.05)
        Entity(parent=r, model="quad", color=C(0.12, 0.3, 0.62, 1), scale=(w, 0.055), y=h / 2 - 0.0275, z=0.045)
        txt(r, f"{title}  -  Inbox ({len(messages)})", -w / 2 + 0.02, h / 2 - 0.012, 1.0, C(1, 1, 1, 1),
            font=self.fonts.get("ui"))
        Entity(parent=r, model="quad", color=C(0.88, 0.9, 0.93, 1), scale=(lw, h - 0.055),
               position=(-w / 2 + lw / 2, -0.0275, 0.044))
        st = {"msgs": messages, "sel": 0, "rows": [], "pane": None, "w": w, "h": h, "lw": lw, "root": r}
        for i, (frm, subj, _body) in enumerate(messages):
            y = h / 2 - 0.09 - i * 0.085
            row = Button(parent=r, z=-0.01, model="quad", color=C(0, 0, 0, 0), scale=(lw - 0.01, 0.08),
                         position=(-w / 2 + lw / 2, y - 0.025), highlight_color=C(0.12, 0.3, 0.62, 0.12))
            row.on_click = (lambda i=i: self._mail_pick(i))
            txt(r, frm, -w / 2 + 0.02, y, 0.95, C(0.08, 0.08, 0.12, 1), font=self.fonts.get("ui"))
            txt(r, subj, -w / 2 + 0.02, y - 0.03, 0.8, C(0.3, 0.32, 0.38, 1), wrap=self._wrap_for(lw - 0.04, 0.8))
            st["rows"].append(row)
        txt(r, "W/S or click: pick a message     E / Space: close", 0, -h / 2 - 0.035, 0.85,
            C(0.85, 0.82, 0.75, 1), origin=(0, 0))
        self._modal_state = st
        self._mail_pick(0)
        self.g.audio.play("type", vol=0.6)

    def _mail_pick(self, i):
        st = self._modal_state
        if not st or "msgs" not in st:
            return
        st["sel"] = i % len(st["msgs"])
        for k, row in enumerate(st["rows"]):
            row.color = C(0.12, 0.3, 0.62, 0.22) if k == st["sel"] else C(0, 0, 0, 0)
        if st["pane"] is not None:
            destroy(st["pane"])
        w, h, lw, r = st["w"], st["h"], st["lw"], st["root"]
        pane = Entity(parent=r)
        st["pane"] = pane
        frm, subj, body = st["msgs"][st["sel"]]
        x0 = -w / 2 + lw + 0.03
        pw = w - lw - 0.06
        ink = C(0.08, 0.08, 0.12, 1)
        txt(pane, subj, x0, h / 2 - 0.08, 1.25, ink, font=self.fonts.get("ui"), wrap=self._wrap_for(pw, 1.25))
        txt(pane, f"From: {frm}", x0, h / 2 - 0.135, 0.85, C(0.35, 0.37, 0.42, 1))
        Entity(parent=pane, model="quad", color=C(0.75, 0.77, 0.8, 1), scale=(pw, 0.003),
               position=(x0 + pw / 2, h / 2 - 0.165, -0.005))
        s, wr = self._fit(body, pw, h - 0.25, 1.0)
        txt(pane, body, x0, h / 2 - 0.19, s, ink, wrap=wr)

    def mail_input(self, key):
        st = self._modal_state
        if key in ("w", "up arrow", "scroll up"):
            self._mail_pick(st["sel"] - 1)
            self.g.audio.play("blip", vol=0.3)
        elif key in ("s", "down arrow", "scroll down"):
            self._mail_pick(st["sel"] + 1)
            self.g.audio.play("blip", vol=0.3)
        elif key in ("e", "space", "escape", "enter"):
            st["closed"] = True

    def open_combo(self, digits=3, title="Combination lock"):
        r = self.open_modal("combo")
        Entity(parent=r, model="quad", color=C(0, 0, 0, 0.6), scale=(3, 2), z=0.1)
        Entity(parent=r, model=Quad(radius=0.03, aspect=0.8 / 0.5), scale=(0.8, 0.5), color=C(0.55, 0.08, 0.08, 0.97), z=0.05)
        txt(r, title, 0, 0.2, 1.4, CREAM, origin=(0, 0))
        st = {"vals": [0] * digits, "sel": 0, "texts": [], "result": None, "frames": []}
        for i in range(digits):
            x = (i - (digits - 1) / 2) * 0.16
            f = Entity(parent=r, model=Quad(radius=0.2), scale=(0.12, 0.16), position=(x, 0, -0.005),
                       color=C(0.9, 0.88, 0.8, 1))
            t = txt(r, "0", x, 0, 3.0, C(0.1, 0.1, 0.1, 1), origin=(0, 0), font=self.fonts.get("title"))
            st["texts"].append(t)
            st["frames"].append(f)
        txt(r, "A/D select   W/S change   Enter open   Esc back", 0, -0.18, 0.9, CREAM, origin=(0, 0))
        self._modal_state = st
        self._combo_hl()

    def _combo_hl(self):
        st = self._modal_state
        for i, f in enumerate(st["frames"]):
            f.color = C(0.98, 0.78, 0.25, 1) if i == st["sel"] else C(0.9, 0.88, 0.8, 1)
            st["texts"][i].text = str(st["vals"][i])

    def combo_input(self, key):
        st = self._modal_state
        if key in ("a", "left arrow"):
            st["sel"] = (st["sel"] - 1) % len(st["vals"])
        elif key in ("d", "right arrow"):
            st["sel"] = (st["sel"] + 1) % len(st["vals"])
        elif key in ("w", "up arrow", "scroll up"):
            st["vals"][st["sel"]] = (st["vals"][st["sel"]] + 1) % 10
            self.g.audio.play("type", vol=0.6)
        elif key in ("s", "down arrow", "scroll down"):
            st["vals"][st["sel"]] = (st["vals"][st["sel"]] - 1) % 10
            self.g.audio.play("type", vol=0.6)
        elif key.isdigit() and len(key) == 1:
            st["vals"][st["sel"]] = int(key)
            st["sel"] = min(len(st["vals"]) - 1, st["sel"] + 1)
            self.g.audio.play("type", vol=0.6)
        elif key in ("enter", "e", "space"):
            st["result"] = "".join(str(v) for v in st["vals"])
        elif key == "escape":
            st["result"] = False
        self._combo_hl()

    def open_password(self, title="ChuckOS 95", prompt="Password:"):
        r = self.open_modal("password")
        Entity(parent=r, model="quad", color=C(0, 0, 0, 0.6), scale=(3, 2), z=0.1)
        Entity(parent=r, model=Quad(radius=0.02, aspect=1.0 / 0.6), scale=(1.0, 0.6), color=C(0.16, 0.36, 0.66, 0.98), z=0.05)
        txt(r, title, 0, 0.22, 2.2, CREAM, origin=(0, 0), font=self.fonts.get("title"))
        txt(r, prompt, -0.3, 0.07, 1.2, CREAM, origin=(-0.5, 0))
        Entity(parent=r, model="quad", color=C(1, 1, 1, 1), scale=(0.6, 0.06), y=0.0, z=-0.005)
        t = txt(r, "", -0.29, 0.0, 1.3, C(0.05, 0.05, 0.05, 1), origin=(-0.5, 0), font=self.fonts.get("body"))
        msg = txt(r, "(You type with your nose. Slowly. Carefully.)", 0, -0.1, 0.9, CREAM, origin=(0, 0))
        txt(r, "Enter to log in   Esc to give up", 0, -0.22, 0.85, DIM, origin=(0, 0))
        self._modal_state = {"text": "", "t": t, "msg": msg, "result": None}

    def password_input(self, key):
        st = self._modal_state
        if key == "backspace":
            st["text"] = st["text"][:-1]
        elif key == "enter":
            st["result"] = st["text"]
        elif key == "escape":
            st["result"] = False
        elif key == "space":
            st["text"] += " "
        elif len(key) == 1 and (key.isalnum()):
            if len(st["text"]) < 22:
                st["text"] += key.upper()
                self.g.audio.play("type", vol=0.5)
        st["t"].text = st["text"] + "_"

    def password_message(self, s):
        if self._modal_state.get("msg"):
            self._modal_state["msg"].text = s
            self._modal_state["result"] = None

    def open_menu(self, title, options, subtitle="", name="menu", back=True):
        """Generic vertical menu. options: list of (label, callback)."""
        r = self.open_modal(name)
        Entity(parent=r, model="quad", color=C(0, 0, 0, 0.55), scale=(3, 2), z=0.1)
        h = 0.2 + len(options) * 0.07
        Entity(parent=r, model=Quad(radius=0.02, aspect=0.7 / h), scale=(0.7, h), color=PANEL, z=0.05)
        txt(r, title, 0, h / 2 - 0.04, 1.8, BRASS, origin=(0, 0.5), font=self.fonts.get("title"))
        if subtitle:
            txt(r, subtitle, 0, h / 2 - 0.11, 0.9, DIM, origin=(0, 0.5))
        for i, (label, cb) in enumerate(options):
            y = h / 2 - 0.17 - i * 0.07
            b = Button(parent=r, z=-0.02, text=label, position=(0, y), scale=(0.5, 0.055), color=PANEL_LIGHT, radius=0.25)
            b.on_click = cb
        self._modal_state = {"back": back}

    # ------------------------------------------------------------------
    # Moo-dals
    # ------------------------------------------------------------------
    def moodal_banner(self, name, desc, reward):
        """A banner under the day header: queued so two unlocks don't overlap."""
        q = getattr(self, "_banner_q", None)
        if q is None:
            q = self._banner_q = []
        q.append((name, desc, reward))
        if getattr(self, "_banner", None) is None:
            self._next_banner()

    def _next_banner(self):
        q = self._banner_q
        if not q:
            self._banner = None
            return
        name, desc, reward = q.pop(0)
        e = Entity(parent=self.root, position=(0, 0.2, -0.05))
        w = 0.78
        Entity(parent=e, model=Quad(radius=0.02, aspect=w / 0.13), scale=(w, 0.13), color=C(0.1, 0.08, 0.05, 0.9))
        Entity(parent=e, model=Quad(radius=0.02, aspect=w / 0.13), scale=(w + 0.008, 0.138), color=BRASS, z=0.01)
        txt(e, "MOO-DAL EARNED", 0, 0.045, 0.85, BRASS, origin=(0, 0))
        txt(e, name, 0, 0.012, 1.45, CREAM, origin=(0, 0), font=self.fonts.get("ui"))
        txt(e, desc, 0, -0.025, 0.78, DIM, origin=(0, 0), wrap=90)
        if reward:
            txt(e, f"+{reward} Golden Clover{'s' if reward > 1 else ''}", 0, -0.052, 0.8, BRASS, origin=(0, 0))
        self._banner = [e, 4.2]

    def _update_banner(self, dt):
        b = getattr(self, "_banner", None)
        if not b:
            return
        b[1] -= dt
        e = b[0]
        e.y = 0.2 + max(0.0, b[1] - 3.9) * 0.4
        e.enabled = self.modal is None
        if b[1] <= 0:
            destroy(e)
            self._next_banner()

    def open_moodals(self, g, on_close):
        from . import moodals as M
        r = self.open_modal("moodals")
        Entity(parent=r, model="quad", color=C(0, 0, 0, 0.78), scale=(3, 2), z=0.1)
        md = g.moodals
        n = md.count_unlocked()
        txt(r, "MOO-DALS", 0, 0.47, 2.0, BRASS, origin=(0, 0.5), font=self.fonts.get("title"))
        txt(r, f"{n} of {len(M.MOODALS)}  ·  rank: {md.rank()}  ·  they carry over between playthroughs",
            0, 0.395, 0.95, DIM, origin=(0, 0.5))
        cols = 2
        per = (len(M.MOODALS) + cols - 1) // cols
        colw = 0.66
        for i, (mid, name, desc, reward, hidden) in enumerate(M.MOODALS):
            c, row = divmod(i, per)
            x = (c - (cols - 1) / 2) * (colw + 0.04) - colw / 2
            y = 0.33 - row * 0.061
            got = md.unlocked(mid)
            if hidden and not got:
                name, desc = "???", "A secret. Moo at things. Look at things. Live a little."
            Entity(parent=r, model=Quad(radius=0.2), scale=0.022, position=(x + 0.012, y - 0.013),
                   color=BRASS if got else C(0.3, 0.28, 0.25, 1))
            txt(r, name, x + 0.035, y, 0.95, CREAM if got else DIM, origin=(-0.5, 0.5))
            prog = md.progress(mid)
            right = f"+{reward}" if got else (f"{prog[0]}/{prog[1]}" if prog else "")
            txt(r, right, x + colw, y, 0.8, BRASS if got else DIM, origin=(0.5, 0.5))
            txt(r, desc, x + 0.035, y - 0.025, 0.68, DIM, origin=(-0.5, 0.5))
        txt(r, "[Esc] back", 0, -0.47, 0.9, DIM, origin=(0, 0))
        self._modal_state = {"back_cb": on_close}

    def open_settings(self, on_close):
        r = self.open_modal("settings")
        from ursina import Slider
        g = self.g
        Entity(parent=r, model="quad", color=C(0, 0, 0, 0.6), scale=(3, 2), z=0.1)
        Entity(parent=r, model=Quad(radius=0.02, aspect=0.9 / 0.8), scale=(0.9, 0.8), color=PANEL, z=0.05)
        txt(r, "Settings", 0, 0.36, 1.8, BRASS, origin=(0, 0.5), font=self.fonts.get("title"))
        rows = [("Master volume", "master"), ("Music", "music"), ("Sound effects", "sfx"), ("Voices (moos)", "voice"),
                ("Ambience", "ambient")]
        for i, (label, key) in enumerate(rows):
            y = 0.24 - i * 0.07
            txt(r, label, -0.4, y, 1.0, CREAM, origin=(-0.5, 0))
            s = Slider(0, 1, default=g.audio.volumes[key], step=0.05, parent=r, z=-0.02, x=0.0, y=y, scale=0.7, dynamic=True)
            s.knob.color = BRASS

            def _set(s=s, key=key):
                g.audio.volumes[key] = s.value
            s.on_value_changed = _set
        y = 0.24 - len(rows) * 0.07
        txt(r, "Mouse sensitivity", -0.4, y, 1.0, CREAM, origin=(-0.5, 0))
        s2 = Slider(0.2, 3.0, default=g.player.sensitivity, step=0.05, parent=r, z=-0.02, x=0.0, y=y, scale=0.7, dynamic=True)

        def _sens():
            g.player.sensitivity = s2.value
        s2.on_value_changed = _sens
        y -= 0.08
        b = Button(parent=r, z=-0.02, text=f"Invert Y: {'On' if g.player.invert_y else 'Off'}", position=(-0.2, y), scale=(0.3, 0.05),
                   color=PANEL_LIGHT, radius=0.25)

        def _inv():
            g.player.invert_y = not g.player.invert_y
            b.text = f"Invert Y: {'On' if g.player.invert_y else 'Off'}"
        b.on_click = _inv
        from .game import QUALITY_NAMES
        from .engine import shading as _sh

        def q_label():
            extra = "  (no shadows)" if not _sh.SHADOWS_SUPPORTED and g.quality != "low" else ""
            return f"Graphics: {QUALITY_NAMES[g.quality]}{extra}"
        b3 = Button(parent=r, z=-0.02, text=q_label(), position=(0.2, y), scale=(0.3, 0.05), color=PANEL_LIGHT,
                    radius=0.25)

        def _quality():
            g.cycle_quality()
            b3.text = q_label()
        b3.on_click = _quality
        y -= 0.065
        b2 = Button(parent=r, z=-0.02, text="Toggle fullscreen (F11)", position=(0, y), scale=(0.34, 0.05), color=PANEL_LIGHT, radius=0.25)
        b2.on_click = g.toggle_fullscreen
        bb = Button(parent=r, z=-0.02, text="Back", position=(0, -0.345), scale=(0.3, 0.055), color=PANEL_LIGHT, radius=0.25)

        def _back():
            g.save_settings()
            on_close()
        bb.on_click = _back
        self._modal_state = {"back_cb": _back}

    def open_shop(self, title, entries, clovers, on_buy, on_close):
        """entries: list of (key, label, price, desc, owned)."""
        r = self.open_modal("shop")
        Entity(parent=r, model="quad", color=C(0, 0, 0, 0.6), scale=(3, 2), z=0.1)
        h = 0.3 + len(entries) * 0.085
        Entity(parent=r, model=Quad(radius=0.02, aspect=1.2 / h), scale=(1.2, h), color=PANEL, z=0.05)
        txt(r, title, 0, h / 2 - 0.04, 1.7, BRASS, origin=(0, 0.5), font=self.fonts.get("title"))
        txt(r, f"Your Golden Clovers: {clovers}", 0, h / 2 - 0.11, 1.0, CREAM, origin=(0, 0.5))
        for i, (key, label, price, desc, owned) in enumerate(entries):
            y = h / 2 - 0.19 - i * 0.085
            if tex("icon_" + key):
                Entity(parent=r, model="quad", texture=tex("icon_" + key), scale=0.06, position=(-0.54, y))
            txt(r, label, -0.49, y + 0.018, 1.05, CREAM, origin=(-0.5, 0))
            txt(r, desc, -0.49, y - 0.018, 0.8, DIM, origin=(-0.5, 0), wrap=62)
            if owned:
                txt(r, "SOLD", 0.46, y, 1.0, GREEN, origin=(0, 0))
            else:
                b = Button(parent=r, z=-0.02, text=f"Buy  {price}", position=(0.45, y), scale=(0.15, 0.05),
                           color=PANEL_LIGHT if clovers >= price else C(0.3, 0.1, 0.1, 0.9), radius=0.25)
                b.text_entity.x = -0.12
                b.on_click = (lambda key=key: on_buy(key))
                if tex("icon_clover"):
                    Entity(parent=r, model="quad", texture=tex("icon_clover"), scale=0.036, position=(0.495, y, -0.02))
        bb = Button(parent=r, z=-0.02, text="Leave", position=(0, -h / 2 + 0.05), scale=(0.25, 0.05), color=PANEL_LIGHT, radius=0.25)
        bb.on_click = on_close
        self._modal_state = {"back_cb": on_close}

    CHAR_W = 0.0122         # average glyph width per unit of text scale, for wrapping to a column width

    def _wrap_for(self, width, scale):
        return max(16, int(width / (self.CHAR_W * scale)))

    def open_journal(self, g):
        """Three columns sized from the window's aspect: objectives and favours, inventory, map. Every block
        is wrapped to its column and advances by the number of lines it actually took, so nothing overlaps
        (the old fixed offsets ran together on a 3:2 screen)."""
        r = self.open_modal("journal")
        A = self.aspect
        Entity(parent=r, model="quad", color=C(0, 0, 0, 0.78), scale=(3, 2), z=0.1)
        margin, gap = 0.05, 0.05
        W = A - 2 * margin
        mw = min(0.62, W * 0.34)
        colw = (W - mw - 2 * gap) / 2
        x1 = self.L + margin
        x2 = x1 + colw + gap
        txt(r, "JOURNAL", x1, 0.47, 1.8, BRASS, font=self.fonts.get("title"))
        txt(r, g.day_title + "  ·  " + g.day_sub, x1, 0.405, 1.0, DIM)
        floor = -0.43

        def block(x, y, text, scale, col, lh, width=colw):
            w = self._wrap_for(width, scale)
            txt(r, text, x, y, scale, col, wrap=w)
            return y - lh * (wrap_str(text, w).count("\n") + 1)

        y = 0.34
        txt(r, "OBJECTIVES", x1, y, 1.05, BRASS, font=self.fonts.get("ui"))
        y -= 0.045
        for text, done in g.objective_lines():
            if y < floor:
                break
            y = block(x1, y, ("[x] " if done else "- ") + text.strip(), 0.92, DIM if done else CREAM, 0.03) - 0.006
        y -= 0.025
        side = g.side_quest_lines()
        if side and y > floor + 0.08:
            txt(r, "FAVOURS", x1, y, 1.05, BRASS, font=self.fonts.get("ui"))
            y -= 0.045
            for text, state in side:
                if y < floor:
                    break
                y = block(x1, y, ("[x] " if state == "done" else "- ") + text, 0.88,
                          GREEN if state == "done" else CREAM, 0.029) - 0.006
        # inventory: icon, name, and its description wrapped to the column
        yy = 0.34
        txt(r, "INVENTORY", x2, yy, 1.05, BRASS, font=self.fonts.get("ui"))
        yy -= 0.05
        items = g.inventory_lines()
        if not items:
            txt(r, "Nothing. You are a cow.", x2, yy, 0.85, DIM)
        for i, (key, label, count, desc) in enumerate(items):
            if yy < floor + 0.05:
                txt(r, f"...and {len(items) - i} more", x2 + 0.06, yy, 0.8, DIM)
                break
            if tex("icon_" + key):
                Entity(parent=r, model="quad", texture=tex("icon_" + key), scale=0.045, position=(x2 + 0.022, yy - 0.016))
            yy = block(x2 + 0.055, yy, label + (f" x{count}" if count > 1 else ""), 0.92, CREAM, 0.03,
                       colw - 0.055)
            yy = block(x2 + 0.055, yy + 0.004, desc, 0.72, DIM, 0.024, colw - 0.055) - 0.016
        # map
        if self.map_tex is None:
            self.map_tex = Texture(build_map_image())
        mx = self.R - margin - mw / 2
        my = 0.05
        Entity(parent=r, model="quad", texture=self.map_tex, scale=(mw, mw * MAP_H / MAP_W), position=(mx, my))
        txt(r, "MAP", mx - mw / 2, my + mw * MAP_H / MAP_W / 2 + 0.05, 1.1, BRASS)
        # markers
        def to_map(x, z):
            u = (x - MAP_X0) / (MAP_X1 - MAP_X0)
            v = (z - MAP_Z0) / (MAP_Z1 - MAP_Z0)
            return mx - mw / 2 + u * mw, my - mw * MAP_H / MAP_W / 2 + v * mw * MAP_H / MAP_W
        hide_col = C(0.45, 0.8, 0.4, 1)
        for (x, z, label) in g.map_markers():
            px, py = to_map(x, z)
            Entity(parent=r, model=Quad(radius=0.5), color=BRASS if label != "hide" else hide_col,
                   scale=0.014 if label != "hide" else 0.011, position=(px, py, -0.01))
            if label != "hide":
                txt(r, label, px + 0.012, py + 0.01, 0.7, BRASS)
        map_bottom = my - mw * MAP_H / MAP_W / 2
        if g.flags.get("star_chart"):
            txt(r, "green: hiding spots", mx - mw / 2, map_bottom - 0.02, 0.72, hide_col)
        px, py = to_map(g.player.x, g.player.z)
        Entity(parent=r, model=Quad(radius=0.1), color=RED, scale=(0.012, 0.03), position=(px, py, -0.02),
               rotation_z=g.player.yaw)
        txt(r, "You", px + 0.012, py - 0.012, 0.7, RED)
        txt(r, "[Tab] close", 0, -0.47, 0.9, DIM, origin=(0, 0))
        st = g.stats
        stats = (f"Caught: {st.get('caught', 0)}    Moos: {st.get('moos', 0)}    "
                 f"Moo-dals: {g.moodals.count_unlocked()} (pause menu)")
        txt(r, stats, mx - mw / 2, map_bottom - 0.065, 0.76, DIM, wrap=self._wrap_for(mw, 0.76))

    # ------------------------------------------------------------------
    def update(self, dt):
        self._update_banner(dt)
        # dialogue typewriter
        if self.dlg.enabled and self.dlg_shown < len(self.dlg_full):
            before = int(self.dlg_shown)
            self.dlg_shown = min(len(self.dlg_full), self.dlg_shown + dt * self.dlg_speed)
            n = int(self.dlg_shown)
            if n != before:
                self.dlg_text.text = self.dlg_full[:n]
                if n % 3 == 0:
                    self.g.audio.play("type", vol=0.08, pitch=1.4)
        if self.dlg.enabled:
            self.dlg_hint.enabled = self.dlg_revealed() and not self.choice_root.enabled
        # popup: above the dialogue box while one is up (they used to print over each other)
        py = (self.dlg_top + 0.02 + self.popup_bg.scale_y / 2) if self.dlg.enabled else -0.3
        if abs(self.popup.y - py) > 1e-4:
            self.popup.y = self.popup_bg.y = py
        if self.popup_t > 0:
            self.popup_t -= dt
            if self.popup_t <= 0:
                self.popup.text = ""
                self.popup_bg.enabled = False
        if self.bark_t > 0:
            self.bark_t -= dt
            if self.bark_t <= 0:
                self.bark.text = ""
                self.bark_bg.enabled = False
            else:
                # menus and documents draw over the HUD; keep the bark from showing through them
                self.bark.enabled = self.bark_bg.enabled = self.modal is None
        # toasts
        alive = []
        for i, t in enumerate(self.toasts):
            t[1] -= dt
            e = t[0]
            e.y += ((0.40 - i * 0.06) - e.y) * min(1, dt * 8)
            if t[1] <= 0:
                destroy(e)
            else:
                alive.append(t)
        self.toasts = alive
        # flash
        if self.flash_t > 0:
            self.flash_t -= dt
            c = self.flash_q.color
            self.flash_q.color = C(c[0], c[1], c[2], 0.45 * max(0, self.flash_t / self.flash_dur))
        # letterbox
        self.lb += (self.lb_target - self.lb) * min(1, dt * 3)
        self.lb_top.y = 0.56 - 0.12 * self.lb
        self.lb_bot.y = -0.56 + 0.12 * self.lb


# ---------------------------------------------------------------------------
# map image
# ---------------------------------------------------------------------------
MAP_X0, MAP_X1, MAP_Z0, MAP_Z1 = -84, 84, -82, 92
MAP_W = 600
MAP_H = int(MAP_W * (MAP_Z1 - MAP_Z0) / (MAP_X1 - MAP_X0))


def build_map_image():
    from . import world as W
    img = Image.new("RGB", (MAP_W, MAP_H), (120, 165, 85))
    d = ImageDraw.Draw(img)

    def P(x, z):
        return ((x - MAP_X0) / (MAP_X1 - MAP_X0) * MAP_W, (1 - (z - MAP_Z0) / (MAP_Z1 - MAP_Z0)) * MAP_H)

    def rect(r, fill, outline=None, width=2):
        x0, x1, z0, z1 = r
        a, b = P(x0, z1), P(x1, z0)
        d.rectangle([a[0], a[1], b[0], b[1]], fill=fill, outline=outline, width=width)

    rect((-3.5, 3.5, 30, 92), (160, 125, 85))
    rect((3.5, 58, 20, 26), (160, 125, 85))
    rect((-16, 40, -46, -12), (160, 125, 85))
    rect((-3.5, 3.5, -12, 30), (160, 125, 85))
    rect((68, 78, 24, 44), (160, 125, 85))
    rect(W.PASTURE, (100, 150, 70), (240, 220, 80), 2)
    cx, cz, rx, rz = W.POND
    a, b = P(cx - rx, cz + rz), P(cx + rx, cz - rz)
    d.ellipse([a[0], a[1], b[0], b[1]], fill=(70, 130, 170))
    for r, col in [(W.COWSHED, (150, 50, 40)), (W.SHED, (130, 95, 60)), (W.BARN, (170, 45, 35)),
                   (W.COOP_HUT, (130, 95, 60)), (W.HOUSE, (225, 215, 185)), (W.PROC, (140, 140, 140))]:
        rect(r, col, (40, 30, 25), 2)
    rect(W.COOP_RUN, None, (90, 70, 50), 1)
    sx, sz = W.SILO
    a, b = P(sx - 3.5, sz + 3.5), P(sx + 3.5, sz - 3.5)
    d.ellipse([a[0], a[1], b[0], b[1]], fill=(180, 180, 185), outline=(40, 40, 40))
    ox, oz = W.OAK
    a, b = P(ox - 4, oz + 4), P(ox + 4, oz - 4)
    d.ellipse([a[0], a[1], b[0], b[1]], fill=(50, 110, 40))
    rect(W.FARM, None, (90, 60, 30), 3)
    rect((-4.3, 4.3, 80.6, 84.4), (60, 60, 60))
    f = texgen.font(texgen.BOLD, 14)
    for label, (x, z) in [("Cowshed", (-52, -4)), ("Pasture", (-60, -45)), ("Shed", (-8, -30)), ("Barn", (22, 2)),
                          ("Coop", (43, -38)), ("House", (56, 39)), ("Processing", (66, -41)), ("Silo", (42, 14)),
                          ("Main gate", (0, 89)), ("Pond", (-45, -60)), ("Oak", (-50, -41))]:
        px, py = P(x, z)
        bb = d.textbbox((0, 0), label, font=f)
        d.text((px - (bb[2] - bb[0]) / 2, py - 7), label, font=f, fill=(20, 20, 20))
    return img
