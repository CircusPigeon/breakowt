"""Asset paths, lazy generation and caching."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _user_dir():
    # Documents/My Games is the conventional home for game data on Windows and,
    # unlike AppData, is not virtualized for Microsoft Store Python.
    docs = Path.home() / "Documents"
    if docs.is_dir():
        return docs / "My Games" / "BREAKOWT"
    return Path.home() / ".breakowt"


# generated assets, saves and screenshots live outside the project folder
USER = _user_dir()
GEN = USER / "generated"
AUDIO_DIR = GEN / "audio"
TEX_DIR = GEN / "textures"
FONT_DIR = GEN / "fonts"
# tests point this elsewhere so they never overwrite the player's save
SAVE_DIR = Path(os.environ["BREAKOWT_SAVE_DIR"]) if os.environ.get("BREAKOWT_SAVE_DIR") else USER / "saves"
SHOT_DIR = USER / "screenshots"

_tex_cache: dict = {}

# first one found wins. The first picks ship with Windows/Office; the last ones are the DejaVu set Linux has
FONT_CHOICES = {
    "ui": ["BRLNSDB.TTF", "seguisb.ttf", "segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"],     # names, buttons
    "body": ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"],
    "title": ["ROCKEB.TTF", "COOPBL.TTF", "georgiab.ttf", "impact.ttf", "DejaVuSerif-Bold.ttf",
              "DejaVuSans-Bold.ttf"],                                                             # farm-sign slab
    "hand": ["Inkfree.ttf", "segoepr.ttf", "comic.ttf", "DejaVuSans.ttf"],                       # Chuck's notes
    "mono": ["consola.ttf", "lucon.ttf", "cour.ttf", "DejaVuSansMono.ttf"],                      # ChuckOS
    "serif": ["georgia.ttf", "pala.ttf", "times.ttf", "DejaVuSerif.ttf"],
    "serif_i": ["georgiai.ttf", "palai.ttf", "timesi.ttf", "DejaVuSerif-Italic.ttf", "DejaVuSerif.ttf"],
}
FONT_SEARCH = [r"C:\Windows\Fonts", os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Windows\Fonts"),
               "/usr/share/fonts/truetype/dejavu", "/Library/Fonts"]


def generation_steps():
    """Yield (label, fraction) while generating whatever is missing."""
    from .. import synth, texgen

    done = {"n": 0}

    def need(dir_, ver):
        vp = dir_ / ".version"
        return not (vp.exists() and vp.read_text().strip() == ver)

    if need(TEX_DIR, texgen.TEX_VERSION):
        TEX_DIR.mkdir(parents=True, exist_ok=True)
        tex = texgen.all_textures()
        for i, (name, fn) in enumerate(tex.items()):
            fn().save(TEX_DIR / f"{name}.png")
            yield f"Painting {name.replace('_', ' ')}", 0.1 * (i + 1) / len(tex)
        (TEX_DIR / ".version").write_text(texgen.TEX_VERSION)
    if need(AUDIO_DIR, synth.AUDIO_VERSION):
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)
        cat = synth.catalog()
        names = list(cat)
        for i, name in enumerate(names):
            synth.write_wav(str(AUDIO_DIR / f"{name}.wav"), cat[name](), name=name)
            yield f"Teaching cows to {name.split('_')[0]}", 0.1 + 0.9 * (i + 1) / len(names)
        (AUDIO_DIR / ".version").write_text(synth.AUDIO_VERSION)
    else:
        # same version, but sounds added since: make just those
        cat = synth.catalog()
        missing = [n for n in cat if not (AUDIO_DIR / f"{n}.wav").exists()]
        for i, name in enumerate(missing):
            synth.write_wav(str(AUDIO_DIR / f"{name}.wav"), cat[name](), name=name)
            yield f"Teaching cows to {name.split('_')[0]}", 0.1 + 0.9 * (i + 1) / len(missing)
    yield "Done", 1.0


def setup_fonts() -> dict:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    out = {}
    for role, names in FONT_CHOICES.items():
        for n in names:
            src = None
            for d in FONT_SEARCH:
                p = os.path.join(d, n)
                if os.path.exists(p):
                    src = p
                    break
            if src:
                dst = FONT_DIR / n
                if not dst.exists():
                    try:
                        shutil.copyfile(src, dst)
                    except OSError:
                        continue
                out[role] = n
                break
    try:
        # Ursina rasterises glyphs at 54 px per unit by default, which is soft on a tall (or high-DPI) window
        from ursina import Text, window
        Text.default_resolution = int(min(140, max(54, window.size[1] * Text.size * 2)))
    except Exception:
        pass
    return out


def tex(name: str):
    if name in _tex_cache:
        return _tex_cache[name]
    from ursina import Texture
    p = TEX_DIR / f"{name}.png"
    t = Texture(p) if p.exists() else None
    if t is not None:
        t.filtering = "mipmap"
    _tex_cache[name] = t
    return t
