"""Check once whether this GPU driver can run the shadow-mapped shader and the offscreen scene buffer.

Panda3D's own shadow maps reached the shader as a `sampler2DShadow` inside the
`p3d_LightSource` struct, and some drivers (seen: Qualcomm Adreno X1-85 on
Windows on ARM) crashed natively with an illegal instruction on the first frame
that used it, which can't be caught in-process. Shadows now use a plain packed
depth texture instead, but a driver crash is still possible in principle, so each
feature renders a few frames in a child process and the exit status decides.
The answers are cached per machine in the saves folder.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _signature():
    # probe2: shadows moved off Panda's sampler2DShadow light struct onto our own packed-depth map,
    # and the scene now renders through an offscreen buffer; machines that failed probe1 get re-tested
    # probe3: a feature also fails if the frame comes out black (a driver can fail without crashing)
    return f"{platform.system()}|{platform.machine()}|{platform.processor()}|probe3"


def _cache_path():
    from .assets import USER
    return USER / "gpu.json"


FEATURES = ("shadows", "postfx")
POSTFX_OK = True    # set by configure(): may the scene render through the offscreen post buffer?


def supported(feature, force=False):
    """True if `feature` ("shadows" or "postfx") renders without crashing (cached).
    BREAKOWT_SHADOWS / BREAKOWT_POSTFX = 0 or 1 skips the check."""
    env = os.environ.get(f"BREAKOWT_{feature.upper()}")
    if env in ("0", "1"):
        return env == "1"
    p = _cache_path()
    sig = _signature()
    d = {}
    try:
        d = json.loads(p.read_text())
        if d.get("signature") != sig:
            d = {}
    except (OSError, ValueError):
        d = {}
    if not force and feature in d:
        return bool(d[feature])
    ok = _run_probe(feature)
    d.update({"signature": sig, feature: ok})
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d, indent=1))
    except OSError:
        pass
    return ok


def cached(feature):
    """The stored answer for `feature` without running a probe (None if there isn't one yet)."""
    env = os.environ.get(f"BREAKOWT_{feature.upper()}")
    if env in ("0", "1"):
        return env == "1"
    try:
        d = json.loads(_cache_path().read_text())
    except (OSError, ValueError):
        return None
    if d.get("signature") != _signature() or feature not in d:
        return None
    return bool(d[feature])


def shadows_supported(force=False):
    """True if the shadow shader renders without crashing (cached)."""
    return supported("shadows", force)


def _run_probe(feature):
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run([sys.executable, "-B", "-m", "breakowt.engine.gpuprobe", feature], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=60, creationflags=flags)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and "PROBE-OK" in r.stdout


def configure():
    """Pick the shader variant and render path before any entity uses FARM_SHADER."""
    global POSTFX_OK
    from . import shading
    ok = shadows_supported()
    shading.set_shadow_support(ok)
    if not ok:
        print("[breakowt] this GPU can't run shadow maps; using the shadow-free shader", flush=True)
    POSTFX_OK = supported("postfx")
    if not POSTFX_OK:
        print("[breakowt] this GPU can't render the scene offscreen; drawing it straight to the window",
              flush=True)
    return ok


def _probe_main(feature):
    sys.dont_write_bytecode = True
    from .boot import create_app
    app = create_app(windowed=True, size=(320, 200))
    from ursina import Entity, application, camera
    from . import shading
    from .meshbuilder import MeshBuilder
    env = shading.Environment(shadows=feature == "shadows")
    if feature == "postfx":
        from .postfx import PostFX
        fx = PostFX(application.base)
        if not fx.apply(0.75, msaa=4):
            print("PROBE-FAIL", flush=True)
            os._exit(1)
    Entity(model=MeshBuilder().box((0, 0, 5), (2, 2, 2)).build(), shader=shading.FARM_SHADER)
    camera.position = (0, 0, 0)
    for _ in range(6):
        env.update(1 / 60)
        app.step()
    # not crashing isn't enough: a broken path can also just draw nothing
    level = _frame_brightness(application.base)
    print(f"PROBE-BRIGHTNESS {level:.1f}", flush=True)
    if level < 2.0:
        print("PROBE-FAIL black frame", flush=True)
        os._exit(1)
    print("PROBE-OK", flush=True)
    os._exit(0)


def _frame_brightness(base):
    """Mean 0-255 brightness of what the window shows (the sky alone is far above 2)."""
    base.graphicsEngine.renderFrame()
    tex = base.win.getScreenshot()
    if tex is None:
        return 0.0
    data = bytes(tex.getRamImageAs("RGB"))
    if not data:
        return 0.0
    return sum(data[::97]) / len(data[::97])


if __name__ == "__main__":
    _probe_main(sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in FEATURES else "shadows")
