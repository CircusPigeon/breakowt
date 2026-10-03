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

sys.dont_write_bytecode = True
# test screenshots live with the game's other generated files, not in the repo
SHOTS = Path(os.environ.get("BREAKOWT_TEST_SHOTS", "")) if os.environ.get("BREAKOWT_TEST_SHOTS") else None


class Args:
    windowed = True
    day = 0
    debug = True
    size = None


def boot(size=(1280, 720), fps=30):
    # keep test runs away from the player's real save and settings
    import tempfile
    os.environ.setdefault("BREAKOWT_SAVE_DIR", str(Path(tempfile.gettempdir()) / "breakowt_test_saves"))
    from breakowt.engine import gpuprobe
    from breakowt.engine.boot import create_app
    app = create_app(windowed=True, size=size, msaa=gpuprobe.cached("postfx") is not True)
    gpuprobe.configure()
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
    # tests are silent: nobody wants a farm playing at them while a bot runs it (BREAKOWT_TEST_SOUND=1 to hear it)
    if not os.environ.get("BREAKOWT_TEST_SOUND"):
        g.audio.volumes["master"] = 0.0
        application.base.disableAllAudio()
    return app, g


def step(app, n=1):
    for _ in range(n):
        app.step()


def shots_dir():
    global SHOTS
    if SHOTS is None:
        from breakowt.engine.assets import USER
        SHOTS = USER / "test_screenshots"
    return SHOTS


def shot(app, name):
    from breakowt.engine.boot import screenshot
    shots = shots_dir()
    shots.mkdir(parents=True, exist_ok=True)
    p = shots / f"{name}.png"
    app.step()
    screenshot(str(p))
    return p
