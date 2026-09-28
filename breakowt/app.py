"""Start-up: window, first-run asset generation (with a progress screen), then the game."""
from __future__ import annotations

import sys
import traceback


def _size_arg(args):
    s = getattr(args, "size", None)
    if not s:
        return None
    try:
        w, h = s.lower().split("x")
        return int(w), int(h)
    except ValueError:
        return None


class Loader:
    """Runs asset generation one step per frame so the window stays responsive."""

    def __init__(self, fonts, on_done):
        from ursina import Entity, Text, camera, color, window
        from .engine import assets
        self.on_done = on_done
        self.gen = assets.generation_steps()
        self.root = Entity(parent=camera.ui)
        A = window.aspect_ratio
        Entity(parent=self.root, model="quad", color=color.rgba(0.07, 0.06, 0.05, 1), scale=(A + 0.2, 1.2), z=1)
        t = Text("BREAKOWT", parent=self.root, origin=(0, 0), y=0.12, scale=5, color=color.rgba(0.98, 0.95, 0.86, 1))
        if fonts.get("title"):
            t.font = fonts["title"]
        Text("Seven Days to Steak", parent=self.root, origin=(0, 0), y=0.03, scale=1.6,
             color=color.rgba(0.98, 0.78, 0.25, 1))
        self.bar_bg = Entity(parent=self.root, model="quad", color=color.rgba(1, 1, 1, 0.12), scale=(0.6, 0.012), y=-0.1)
        self.bar = Entity(parent=self.root, model="quad", color=color.rgba(0.98, 0.78, 0.25, 1), scale=(0, 0.012),
                          x=-0.3, y=-0.1, origin=(-0.5, 0))
        self.label = Text("", parent=self.root, origin=(0, 0), y=-0.15, scale=1.0, color=color.rgba(0.75, 0.72, 0.65, 1))
        self.note = Text("First launch: making the sounds and pictures. This only happens once.", parent=self.root,
                         origin=(0, 0), y=-0.22, scale=0.85, color=color.rgba(0.55, 0.52, 0.47, 1), enabled=False)
        self.frames = 0
        self.finished = False
        self.upd = Entity(parent=self.root)
        self.upd.update = self.update

    def update(self):
        if self.finished:
            return
        self.frames += 1
        if self.frames < 3:
            return
        try:
            label, frac = next(self.gen)
        except StopIteration:
            label, frac = "Done", 1.0
        if frac < 1.0:
            self.note.enabled = True
        self.bar.scale_x = 0.6 * frac
        self.label.text = label + "..." if frac < 1.0 else "Building the farm..."
        if label == "Done" or frac >= 1.0:
            self.finished = True
            # let one frame render "Building the farm..." before the heavy world build
            from ursina import invoke
            invoke(self._finish, delay=0.05)

    def _finish(self):
        from ursina import destroy
        destroy(self.root)
        self.on_done()


def run(args):
    from .engine import gpuprobe
    from .engine.boot import create_app
    # the scene's post pass does the anti-aliasing when this machine is known to support it
    app = create_app(windowed=args.windowed, size=_size_arg(args), msaa=gpuprobe.cached("postfx") is not True)
    gpuprobe.configure()
    from ursina import Text, application
    from .engine import assets
    application.fonts_folder = assets.FONT_DIR
    fonts = assets.setup_fonts()
    if fonts.get("body"):
        Text.default_font = fonts["body"]
    holder = {}

    def start():
        try:
            from .game import Game
            g = Game(args, fonts)
            holder["game"] = g
            g.story.start(args.day)
        except Exception:
            traceback.print_exc()
            sys.exit(1)

    Loader(fonts, start)
    app.run(info=False)
