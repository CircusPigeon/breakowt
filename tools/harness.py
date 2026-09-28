"""Headless test harness: boot the game with a fixed-step clock, step frames, take screenshots.

Run under a virtual display on Linux, e.g.:
    xvfb-run -s "-screen 0 1280x720x24" python tools/harness.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHOTS = ROOT / "screenshots"


class Args:
    windowed = True
    day = 0
    debug = True
    size = None


def boot(size=(1280, 720), fps=30):
    from breakowt.engine.boot import create_app
    app = create_app(windowed=True, size=size)
    from panda3d.core import ClockObject
    from ursina import Text, application
    from breakowt.engine import assets
    clock = ClockObject.getGlobalClock()
    clock.setMode(ClockObject.MNonRealTime)
    clock.setFrameRate(fps)
    application.fonts_folder = assets.FONT_DIR
    for _ in assets.generation_steps():
        pass
    fonts = assets.setup_fonts()
    if fonts.get("body"):
        Text.default_font = fonts["body"]
    from breakowt.game import Game
    g = Game(Args(), fonts)
    return app, g


def step(app, n=1):
    for _ in range(n):
        app.step()


def shot(app, name):
    from breakowt.engine.boot import screenshot
    SHOTS.mkdir(exist_ok=True)
    p = SHOTS / f"{name}.png"
    app.step()
    screenshot(str(p))
    return p
