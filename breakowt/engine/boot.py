"""Window creation. Must run before anything touches Panda3D.

This machine runs Windows at 200% display scaling: the process has to be
DPI-aware *before* the window exists, and the window must be opened at its
final size (resizing at startup leaves the GL drawable stuck small).
"""
from __future__ import annotations

import sys


def _dpi_aware():
    if sys.platform != "win32":
        return
    import ctypes
    for attempt in (
        lambda: ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)),
        lambda: ctypes.windll.shcore.SetProcessDpiAwareness(2),
        lambda: ctypes.windll.user32.SetProcessDPIAware(),
    ):
        try:
            attempt()
            return
        except Exception:
            continue


def screen_size():
    if sys.platform == "win32":
        try:
            import ctypes
            u = ctypes.windll.user32
            return u.GetSystemMetrics(0), u.GetSystemMetrics(1)
        except Exception:
            pass
    return 1920, 1080


def create_app(windowed=False, offscreen=False, size=None):
    _dpi_aware()
    from panda3d.core import loadPrcFileData
    loadPrcFileData("", "dpi-aware #t")
    loadPrcFileData("", "framebuffer-multisample 1")
    loadPrcFileData("", "multisamples 4")
    loadPrcFileData("", "sync-video #t")
    loadPrcFileData("", "audio-library-name p3openal_audio")
    loadPrcFileData("", "notify-level-audio error")
    from ursina import Ursina, application, window
    application.development_mode = False
    sw, sh = screen_size()
    if offscreen:
        app = Ursina(title="BREAKOWT", window_type="offscreen", size=size or (1280, 800),
                     borderless=False, fullscreen=False, development_mode=False, editor_ui_enabled=False)
    elif windowed:
        w, h = size or (int(sw * 0.75), int(sh * 0.75))
        app = Ursina(title="BREAKOWT", borderless=False, fullscreen=False, size=(w, h),
                     development_mode=False, editor_ui_enabled=False)
    else:
        app = Ursina(title="BREAKOWT", borderless=True, fullscreen=True, development_mode=False,
                     editor_ui_enabled=False)
    for name in ("entity_counter", "fps_counter", "collider_counter", "exit_button", "cog_button"):
        ov = getattr(window, name, None)
        if ov is not None:
            ov.enabled = False
    ie = getattr(window, "input_entity", None)
    if ie is not None:
        ie.enabled = False
    try:
        from panda3d.core import AntialiasAttrib
        application.base.render.setAntialias(AntialiasAttrib.MMultisample)
    except Exception:
        pass
    window.color = (0, 0, 0, 1)
    application.base.setBackgroundColor(0, 0, 0, 1)
    return app


def screenshot(path: str):
    from panda3d.core import Filename
    from ursina import application
    application.base.graphicsEngine.renderFrame()
    img = application.base.win.getScreenshot()
    if img is not None:
        img.write(Filename.fromOsSpecific(path))
        return True
    return False
