"""Check once whether this GPU driver can run the shadow-mapped shader.

Panda3D's shadow maps reach the shader as a `sampler2DShadow` inside the
`p3d_LightSource` struct. Some drivers (seen: Qualcomm Adreno X1-85 on Windows
on ARM) crash natively with an illegal instruction on the first frame that
uses it, which can't be caught in-process. So the check renders a few frames
in a child process and reads its exit status. The answer is cached per
machine in the saves folder.
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
    return f"{platform.system()}|{platform.machine()}|{platform.processor()}|probe1"


def _cache_path():
    from .assets import USER
    return USER / "gpu.json"


def shadows_supported(force=False):
    """True if the shadow shader renders without crashing (cached)."""
    env = os.environ.get("BREAKOWT_SHADOWS")
    if env in ("0", "1"):
        return env == "1"
    p = _cache_path()
    sig = _signature()
    if not force:
        try:
            d = json.loads(p.read_text())
            if d.get("signature") == sig and "shadows" in d:
                return bool(d["shadows"])
        except (OSError, ValueError):
            pass
    ok = _run_probe()
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"signature": sig, "shadows": ok}, indent=1))
    except OSError:
        pass
    return ok


def _run_probe():
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        r = subprocess.run([sys.executable, "-B", "-m", "breakowt.engine.gpuprobe"], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=60, creationflags=flags)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return r.returncode == 0 and "PROBE-OK" in r.stdout


def configure():
    """Pick the shader variant before any entity uses FARM_SHADER."""
    from . import shading
    ok = shadows_supported()
    shading.set_shadow_support(ok)
    if not ok:
        print("[breakowt] this GPU can't run shadow maps; using the shadow-free shader", flush=True)
    return ok


def _probe_main():
    sys.dont_write_bytecode = True
    from .boot import create_app
    app = create_app(windowed=True, size=(320, 200))
    from ursina import Entity, camera
    from . import shading
    from .meshbuilder import MeshBuilder
    env = shading.Environment(shadows=True)
    Entity(model=MeshBuilder().box((0, 0, 5), (2, 2, 2)).build(), shader=shading.FARM_SHADER)
    camera.position = (0, 0, 0)
    for _ in range(6):
        env.update(1 / 60)
        app.step()
    print("PROBE-OK", flush=True)
    os._exit(0)


if __name__ == "__main__":
    _probe_main()
