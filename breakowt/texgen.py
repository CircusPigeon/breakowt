"""Procedural textures for BREAKOWT (Pillow + numpy).

Written to assets/generated/textures/*.png on first run.
"""
from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

TEX_VERSION = "13"
_rng = np.random.default_rng(1987)

FONT_DIRS = [r"C:\Windows\Fonts", "/usr/share/fonts/truetype/dejavu", "/Library/Fonts"]


def font(names, size):
    if isinstance(names, str):
        names = [names]
    for n in names:
        for d in FONT_DIRS:
            p = os.path.join(d, n)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, size)
                except OSError:
                    pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


IMPACT = ["impact.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"]
BOLD = ["arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf"]
HAND = ["segoepr.ttf", "comic.ttf", "DejaVuSans.ttf"]
HANDB = ["segoeprb.ttf", "comicbd.ttf", "DejaVuSans-Bold.ttf"]
SERIF = ["georgiab.ttf", "timesbd.ttf", "DejaVuSerif-Bold.ttf"]


# --------------------------------------------------------------------------
# noise helpers
# --------------------------------------------------------------------------

def tile_noise(size=256, beta=2.0, seed=None):
    r = np.random.default_rng(seed) if seed is not None else _rng
    w = r.standard_normal((size, size))
    F = np.fft.fft2(w)
    fx = np.fft.fftfreq(size)[:, None]
    fy = np.fft.fftfreq(size)[None, :]
    f = np.sqrt(fx ** 2 + fy ** 2)
    f[0, 0] = 1
    F = F / f ** (beta / 2)
    F[0, 0] = 0
    x = np.real(np.fft.ifft2(F))
    x = (x - x.min()) / (x.max() - x.min() + 1e-9)
    return x


def colorize(n, c0, c1):
    c0 = np.array(c0, dtype=float)
    c1 = np.array(c1, dtype=float)
    return (c0[None, None, :] * (1 - n[..., None]) + c1[None, None, :] * n[..., None])


def to_img(a):
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def wrap_draw(img: Image.Image, draw_fn):
    """Draw a shape at 9 offsets so it tiles seamlessly."""
    w, h = img.size
    d = ImageDraw.Draw(img)
    for ox in (-w, 0, w):
        for oy in (-h, 0, h):
            draw_fn(d, ox, oy)


# --------------------------------------------------------------------------
# tileable surfaces
# --------------------------------------------------------------------------

def tex_grass():
    n = tile_noise(256, 2.2) * 0.6 + tile_noise(256, 0.8) * 0.4
    a = colorize(n, (70, 120, 40), (125, 175, 70))
    img = to_img(a)
    d = ImageDraw.Draw(img)
    for _ in range(900):
        x, y = _rng.uniform(0, 256, 2)
        l = _rng.uniform(3, 8)
        ang = _rng.uniform(-0.5, 0.5) - math.pi / 2
        c = tuple(int(v) for v in _rng.choice([(60, 110, 35), (140, 190, 80), (95, 150, 50)]))
        for ox in (-256, 0, 256):
            for oy in (-256, 0, 256):
                d.line([(x + ox, y + oy), (x + ox + math.cos(ang) * l, y + oy + math.sin(ang) * l)], fill=c, width=1)
    return img


def tex_dirt():
    n = tile_noise(256, 2.0) * 0.7 + tile_noise(256, 0.5) * 0.3
    img = to_img(colorize(n, (105, 78, 50), (150, 115, 78)))
    d = ImageDraw.Draw(img)
    for _ in range(160):
        x, y = _rng.uniform(0, 256, 2)
        r = _rng.uniform(0.8, 2.6)
        v = _rng.uniform(85, 165)
        c = (int(v), int(v * 0.86), int(v * 0.7))
        sh = (int(v * 0.55), int(v * 0.45), int(v * 0.35))
        for ox in (-256, 0, 256):
            for oy in (-256, 0, 256):
                d.ellipse([x + ox - r + 0.6, y + oy - r + 0.8, x + ox + r + 0.6, y + oy + r + 0.8], fill=sh)
                d.ellipse([x + ox - r, y + oy - r, x + ox + r, y + oy + r], fill=c)
    return img


def tex_mud():
    n = tile_noise(256, 2.5)
    return to_img(colorize(n, (70, 50, 30), (105, 78, 48)))


def tex_gravel():
    n = tile_noise(256, 0.3)
    img = to_img(colorize(n, (120, 115, 105), (175, 168, 155)))
    d = ImageDraw.Draw(img)
    for _ in range(500):
        x, y = _rng.uniform(0, 256, 2)
        r = _rng.uniform(1, 3.5)
        g = int(_rng.uniform(90, 200))
        for ox in (-256, 0, 256):
            for oy in (-256, 0, 256):
                d.ellipse([x + ox - r, y + oy - r, x + ox + r, y + oy + r], fill=(g, g - 5, g - 12))
    return img


def _boards(size, n_boards, base, var, vertical=True, gap_color=None, knots=True, seed=None):
    r = np.random.default_rng(seed)
    grain = tile_noise(size, 2.8, seed=seed)
    # stretch grain along boards
    img = np.zeros((size, size, 3))
    bw = size / n_boards
    for i in range(n_boards):
        shade = r.uniform(1 - var, 1 + var)
        c = np.array(base) * shade
        a, b = int(i * bw), int((i + 1) * bw)
        g = grain[:, a:b] if vertical else grain[a:b, :]
        streak = (np.sin(np.linspace(0, r.uniform(20, 40), size))[:, None] * 0.5 + 0.5) if vertical else \
            (np.sin(np.linspace(0, r.uniform(20, 40), size))[None, :] * 0.5 + 0.5)
        tone = 0.82 + 0.18 * (0.6 * g + 0.4 * (streak if vertical else streak))
        if vertical:
            img[:, a:b] = c[None, None, :] * tone[..., None]
        else:
            img[a:b, :] = c[None, None, :] * tone[..., None]
    im = to_img(img)
    d = ImageDraw.Draw(im)
    gc = gap_color or tuple(int(v * 0.45) for v in base)
    for i in range(n_boards + 1):
        p = int(i * bw)
        if vertical:
            d.line([(p, 0), (p, size)], fill=gc, width=2)
        else:
            d.line([(0, p), (size, p)], fill=gc, width=2)
    if knots:
        for _ in range(n_boards):
            x, y = r.uniform(0, size, 2)
            rr = r.uniform(2, 5)
            kc = tuple(int(v * 0.6) for v in base)
            d.ellipse([x - rr, y - rr * 1.6, x + rr, y + rr * 1.6], outline=kc, width=2)
    return im


def tex_wood():
    return _boards(256, 4, (165, 125, 80), 0.1, seed=3)


def tex_wood_dark():
    return _boards(256, 4, (100, 72, 48), 0.12, seed=4)


def tex_barn_red():
    return _boards(256, 5, (160, 38, 30), 0.08, seed=5)


def tex_floorboards():
    return _boards(256, 6, (150, 105, 65), 0.12, vertical=False, seed=6)


def tex_siding():
    return _boards(256, 8, (228, 218, 190), 0.03, vertical=False, knots=False, seed=7,
                   gap_color=(150, 140, 120))


def tex_fence_wood():
    return _boards(128, 2, (140, 110, 80), 0.1, seed=8)


def tex_hay():
    n = tile_noise(256, 1.5)
    img = to_img(colorize(n, (200, 165, 70), (235, 205, 110)))
    d = ImageDraw.Draw(img)
    for _ in range(1400):
        x, y = _rng.uniform(0, 256, 2)
        l = _rng.uniform(6, 22)
        ang = _rng.normal(0, 0.35)
        c = tuple(int(v) for v in _rng.choice([(180, 140, 50), (245, 220, 130), (215, 180, 80), (160, 120, 40)]))
        for ox in (-256, 0, 256):
            for oy in (-256, 0, 256):
                d.line([(x + ox, y + oy), (x + ox + math.cos(ang) * l, y + oy + math.sin(ang) * l)], fill=c, width=1)
    return img


def tex_cowhide(spot=(25, 22, 22), base=(245, 242, 235), n_spots=9, seed=None):
    size = 256
    r = np.random.default_rng(seed)
    img = Image.new("RGB", (size, size), base)
    for _ in range(n_spots):
        cx, cy = r.uniform(0, size, 2)
        blobs = [(cx + r.normal(0, 18), cy + r.normal(0, 18), r.uniform(14, 34)) for _ in range(5)]
        def fn(d, ox, oy, blobs=blobs):
            for bx, by, br in blobs:
                d.ellipse([bx + ox - br, by + oy - br * 0.85, bx + ox + br, by + oy + br * 0.85], fill=spot)
        wrap_draw(img, fn)
    img = img.filter(ImageFilter.GaussianBlur(1.2))
    # subtle fur noise
    a = np.asarray(img).astype(float)
    a *= (0.93 + 0.07 * tile_noise(size, 0.5, seed=seed))[..., None]
    return to_img(a)


def tex_concrete():
    n = tile_noise(256, 1.2) * 0.5 + tile_noise(256, 3.0) * 0.5
    img = to_img(colorize(n, (125, 125, 122), (170, 170, 165)))
    d = ImageDraw.Draw(img)
    for _ in range(6):
        x, y = _rng.uniform(0, 256, 2)
        pts = [(x, y)]
        for _ in range(6):
            x += _rng.uniform(-15, 15)
            y += _rng.uniform(5, 18)
            pts.append((x, y))
        d.line(pts, fill=(100, 100, 98), width=1)
    return img


def tex_metal():
    size = 256
    x = np.arange(size)
    ridge = (np.sin(x / size * 2 * math.pi * 12) * 0.5 + 0.5)[None, :]
    n = tile_noise(size, 2.0)
    v = 0.65 * ridge + 0.35 * n
    return to_img(colorize(v, (120, 125, 130), (190, 195, 200)))


def tex_metal_rust():
    size = 256
    x = np.arange(size)
    ridge = (np.sin(x / size * 2 * math.pi * 12) * 0.5 + 0.5)[None, :]
    rust = tile_noise(size, 2.2)
    base = colorize(0.6 * ridge + 0.4 * tile_noise(size, 1.0), (110, 110, 112), (175, 175, 178))
    rustc = colorize(rust, (120, 60, 30), (170, 90, 45))
    m = np.clip((rust - 0.45) * 3, 0, 1)[..., None]
    return to_img(base * (1 - m) + rustc * m)


def tex_shingles():
    size = 256
    img = Image.new("RGB", (size, size), (70, 60, 58))
    d = ImageDraw.Draw(img)
    rows = 8
    rh = size / rows
    for r in range(rows):
        off = (r % 2) * 16
        for c in range(-1, 9):
            x0 = c * 32 + off
            shade = int(_rng.uniform(55, 95))
            d.rectangle([x0 + 1, r * rh + 1, x0 + 31, (r + 1) * rh - 1], fill=(shade + 15, shade, shade - 5))
            d.line([(x0 + 1, (r + 1) * rh - 2), (x0 + 31, (r + 1) * rh - 2)], fill=(40, 34, 32), width=2)
    return img


def tex_stone():
    size = 256
    img = Image.new("RGB", (size, size), (90, 88, 84))
    d = ImageDraw.Draw(img)
    for r in range(8):
        off = (r % 2) * 20
        for c in range(-1, 7):
            x0 = c * 40 + off
            g = int(_rng.uniform(120, 170))
            d.rounded_rectangle([x0 + 2, r * 32 + 2, x0 + 38, r * 32 + 30], radius=6, fill=(g, g - 3, g - 8))
    return img


def tex_wallpaper():
    """Floral wallpaper... with tiny cows on it. Chuck, why."""
    size = 256
    img = Image.new("RGB", (size, size), (222, 208, 170))
    d = ImageDraw.Draw(img)
    for i in range(0, size, 32):
        d.line([(i, 0), (i, size)], fill=(208, 190, 150), width=6)
    for gx in range(4):
        for gy in range(4):
            cx = gx * 64 + (32 if gy % 2 else 0)
            cy = gy * 64 + 32
            if (gx + gy) % 3 == 0:
                # a tiny cow
                d.ellipse([cx - 12, cy - 6, cx + 10, cy + 8], fill=(250, 250, 245), outline=(80, 60, 50))
                d.ellipse([cx - 6, cy - 3, cx, cy + 2], fill=(40, 40, 40))
                d.ellipse([cx + 7, cy - 9, cx + 16, cy + 1], fill=(250, 250, 245), outline=(80, 60, 50))
                for lx in (-8, -3, 3, 7):
                    d.line([(cx + lx, cy + 7), (cx + lx, cy + 13)], fill=(80, 60, 50), width=2)
            else:
                for k in range(5):
                    a = k / 5 * 2 * math.pi
                    px, py = cx + math.cos(a) * 7, cy + math.sin(a) * 7
                    d.ellipse([px - 5, py - 5, px + 5, py + 5], fill=(190, 90, 100))
                d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(240, 200, 90))
    return img


def tex_tiles():
    size = 256
    img = Image.new("RGB", (size, size), (240, 240, 235))
    d = ImageDraw.Draw(img)
    s = 32
    for x in range(8):
        for y in range(8):
            if (x + y) % 2:
                d.rectangle([x * s, y * s, x * s + s, y * s + s], fill=(60, 60, 70))
    for i in range(9):
        d.line([(i * s, 0), (i * s, size)], fill=(150, 150, 150), width=2)
        d.line([(0, i * s), (size, i * s)], fill=(150, 150, 150), width=2)
    return img


def tex_carpet():
    n = tile_noise(256, 0.2)
    return to_img(colorize(n, (95, 110, 60), (120, 140, 75)))


def tex_water():
    n = tile_noise(256, 3.0) * 0.6 + tile_noise(256, 1.4) * 0.4
    a = colorize(n, (40, 90, 120), (90, 160, 185))
    ridge = np.clip((n - 0.62) * 8, 0, 1)
    a = a * (1 - ridge[..., None] * 0.5) + np.array([220, 240, 245])[None, None, :] * ridge[..., None] * 0.5
    return to_img(a)


def tex_plaid():
    size = 128
    a = np.zeros((size, size, 3))
    a[:] = (170, 30, 35)
    x = np.arange(size)
    band = ((x % 32) < 10).astype(float)
    thin = ((x % 32) == 20).astype(float)
    a *= (1 - 0.45 * band[None, :, None]) * (1 - 0.45 * band[:, None, None])
    a += 60 * thin[None, :, None] + 60 * thin[:, None, None]
    a *= (0.92 + 0.08 * tile_noise(size, 0.2))[..., None]
    return to_img(a)


def tex_denim():
    n = tile_noise(128, 0.1)
    a = colorize(n, (45, 70, 120), (70, 100, 155))
    x = np.arange(128)
    diag = ((x[:, None] + x[None, :]) % 4 < 2).astype(float)
    a *= (0.9 + 0.1 * diag)[..., None]
    return to_img(a)


def tex_straw():
    size = 128
    img = Image.new("RGB", (size, size), (215, 185, 110))
    d = ImageDraw.Draw(img)
    for y in range(0, size, 8):
        for x in range(0, size, 8):
            c = (200, 165, 90) if ((x // 8 + y // 8) % 2) else (230, 200, 125)
            d.rectangle([x, y, x + 7, y + 7], fill=c)
    return img


def tex_white():
    return Image.new("RGB", (8, 8), (255, 255, 255))


def tex_paper():
    size = 512
    n = tile_noise(size, 1.0)
    img = to_img(colorize(n, (238, 230, 205), (250, 246, 230)))
    d = ImageDraw.Draw(img)
    for y in range(60, size, 28):
        d.line([(0, y), (size, y)], fill=(170, 195, 225), width=2)
    d.line([(52, 0), (52, size)], fill=(225, 140, 140), width=2)
    # coffee ring
    d.ellipse([360, 380, 470, 490], outline=(185, 150, 110), width=5)
    return img


def tex_blob_shadow():
    size = 64
    y, x = np.mgrid[0:size, 0:size]
    r = np.sqrt((x - size / 2 + 0.5) ** 2 + (y - size / 2 + 0.5) ** 2) / (size / 2)
    a = np.clip(1 - r ** 2.2, 0, 1) ** 1.3
    img = np.zeros((size, size, 4))
    img[..., 3] = a * 255
    return Image.fromarray(img.astype(np.uint8), "RGBA")


def tex_vignette():
    size = 256
    y, x = np.mgrid[0:size, 0:size]
    r = np.sqrt(((x - size / 2 + 0.5) / (size / 2)) ** 2 + ((y - size / 2 + 0.5) / (size / 2)) ** 2)
    t = np.clip((r - 0.62) / 0.75, 0, 1)
    a = t * t * (3 - 2 * t) * 0.5
    img = np.zeros((size, size, 4))
    img[..., 3] = a * 255
    return Image.fromarray(img.astype(np.uint8), "RGBA")


def tex_soft_circle():
    size = 64
    y, x = np.mgrid[0:size, 0:size]
    r = np.sqrt((x - size / 2 + 0.5) ** 2 + (y - size / 2 + 0.5) ** 2) / (size / 2)
    a = np.clip(1 - r, 0, 1) ** 2
    img = np.full((size, size, 4), 255.0)
    img[..., 3] = a * 255
    return Image.fromarray(img.astype(np.uint8), "RGBA")


def tex_leaves():
    n = tile_noise(128, 1.0)
    img = to_img(colorize(n, (45, 95, 35), (95, 150, 55)))
    d = ImageDraw.Draw(img)
    for _ in range(120):
        x, y = _rng.uniform(0, 128, 2)
        c = tuple(int(v) for v in _rng.choice([(40, 85, 30), (110, 165, 60)]))
        d.ellipse([x - 3, y - 2, x + 3, y + 2], fill=c)
    return img


def tex_bark():
    size = 128
    n = tile_noise(size, 2.5)
    a = colorize(n, (70, 50, 35), (115, 85, 60))
    x = np.arange(size)
    grooves = np.sin(x / size * 2 * math.pi * 6) * 0.5 + 0.5
    a *= (0.75 + 0.25 * grooves)[None, :, None]
    return to_img(a)


# --------------------------------------------------------------------------
# signs & props
# --------------------------------------------------------------------------

def centered(d, box, text, fnt, fill, spacing=4):
    x0, y0, x1, y1 = box
    bb = d.multiline_textbbox((0, 0), text, font=fnt, spacing=spacing, align="center")
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.multiline_text(((x0 + x1 - w) / 2 - bb[0], (y0 + y1 - h) / 2 - bb[1]), text, font=fnt, fill=fill,
                     spacing=spacing, align="center")


def sign_board(w, h, bg, border, lines, fonts_sizes, colors, wood=True):
    img = _boards(max(w, h), 3, bg, 0.05, vertical=False, knots=False).resize((w, h)) if wood else Image.new("RGB", (w, h), bg)
    d = ImageDraw.Draw(img)
    d.rectangle([4, 4, w - 5, h - 5], outline=border, width=8)
    total = len(lines)
    for i, (txt, (fn, sz), col) in enumerate(zip(lines, fonts_sizes, colors)):
        top = 10 + (h - 20) * i / total
        bot = 10 + (h - 20) * (i + 1) / total
        centered(d, (10, top, w - 10, bot), txt, font(fn, sz), col)
    return img


def tex_sign_farm():
    return sign_board(1024, 384, (240, 230, 200), (140, 30, 25),
                      ["HAPPY ACRES", "FAMILY FARM  ·  Est. 1987", "\u201cWhere Every Cow Is Family\u201d"],
                      [(SERIF, 130), (BOLD, 54), (HAND, 50)],
                      [(160, 35, 30), (60, 50, 40), (60, 50, 40)])


def smiling_cow(d, cx, cy, s, wink=True):
    d.ellipse([cx - s, cy - s * 0.85, cx + s, cy + s * 0.85], fill=(250, 250, 250), outline=(30, 30, 30), width=6)
    d.ellipse([cx - s * 0.7, cy - s * 0.8, cx - s * 0.1, cy - s * 0.2], fill=(30, 30, 30))
    d.ellipse([cx - s * 0.55, cy + s * 0.15, cx + s * 0.55, cy + s * 0.75], fill=(245, 170, 175), outline=(30, 30, 30), width=5)
    d.ellipse([cx - s * 0.3, cy + s * 0.35, cx - s * 0.15, cy + s * 0.5], fill=(30, 30, 30))
    d.ellipse([cx + s * 0.15, cy + s * 0.35, cx + s * 0.3, cy + s * 0.5], fill=(30, 30, 30))
    # eyes
    d.ellipse([cx - s * 0.45, cy - s * 0.35, cx - s * 0.2, cy - s * 0.05], fill=(255, 255, 255), outline=(30, 30, 30), width=4)
    d.ellipse([cx - s * 0.36, cy - s * 0.25, cx - s * 0.26, cy - s * 0.12], fill=(30, 30, 30))
    if wink:
        d.arc([cx + s * 0.18, cy - s * 0.3, cx + s * 0.45, cy - s * 0.05], 200, 340, fill=(30, 30, 30), width=6)
    else:
        d.ellipse([cx + s * 0.2, cy - s * 0.35, cx + s * 0.45, cy - s * 0.05], fill=(255, 255, 255), outline=(30, 30, 30), width=4)
    # horns & ears
    d.polygon([(cx - s * 0.6, cy - s * 0.75), (cx - s * 0.75, cy - s * 1.25), (cx - s * 0.4, cy - s * 0.8)], fill=(235, 220, 180), outline=(30, 30, 30))
    d.polygon([(cx + s * 0.6, cy - s * 0.75), (cx + s * 0.75, cy - s * 1.25), (cx + s * 0.4, cy - s * 0.8)], fill=(235, 220, 180), outline=(30, 30, 30))
    # grin
    d.arc([cx - s * 0.35, cy + s * 0.45, cx + s * 0.35, cy + s * 0.85], 20, 160, fill=(30, 30, 30), width=5)


def tex_sign_processing():
    w, h = 1024, 512
    img = Image.new("RGB", (w, h), (235, 235, 225))
    d = ImageDraw.Draw(img)
    d.rectangle([6, 6, w - 7, h - 7], outline=(200, 40, 40), width=12)
    smiling_cow(d, 190, 250, 130)
    centered(d, (340, 40, w - 30, 200), "HAPPY ACRES\nPROCESSING", font(IMPACT, 92), (200, 40, 40), spacing=0)
    centered(d, (340, 230, w - 30, 360), "\u201cHappy Cows Come\nFrom Happy Acres!\u201d", font(HANDB, 50), (40, 40, 40))
    centered(d, (340, 380, w - 30, 470), "NO COWS BEYOND THIS POINT (except today)", font(BOLD, 26), (120, 120, 120))
    return img


def tex_sign_cowshed():
    return sign_board(512, 160, (230, 215, 170), (90, 60, 40), ["COWSHED"], [(IMPACT, 110)], [(90, 60, 40)])


def tex_sign_47():
    img = Image.new("RGB", (256, 256), (240, 200, 40))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 247, 247], outline=(40, 40, 40), width=10)
    centered(d, (0, 0, 256, 256), "47", font(IMPACT, 170), (30, 30, 30))
    return img


def tex_eartag(num):
    img = Image.new("RGB", (128, 128), (245, 205, 40))
    d = ImageDraw.Draw(img)
    centered(d, (0, 0, 128, 128), str(num), font(IMPACT, 80 if len(str(num)) < 3 else 60), (20, 20, 20))
    return img


def tex_eartag_mud():
    img = tex_eartag(12)
    a = np.asarray(img).astype(float)
    n = tile_noise(128, 2.0)
    m = np.clip((n - 0.2) * 3, 0, 1)[..., None]
    mud = np.array([95, 70, 40])[None, None, :]
    return to_img(a * (1 - m) + mud * m)


def tex_john_steer():
    img = Image.new("RGB", (512, 128), (40, 110, 45))
    d = ImageDraw.Draw(img)
    centered(d, (0, 0, 512, 128), "JOHN STEER", font(IMPACT, 90), (250, 215, 40))
    return img


def tex_do_not_touch():
    img = Image.new("RGB", (512, 256), (250, 220, 40))
    d = ImageDraw.Draw(img)
    for i in range(-10, 40):
        d.polygon([(i * 30, 0), (i * 30 + 15, 0), (i * 30 - 35, 256), (i * 30 - 50, 256)], fill=(30, 30, 30))
    d.rectangle([30, 40, 482, 216], fill=(250, 250, 245))
    centered(d, (30, 40, 482, 216), "DANGER\nDO NOT TOUCH\n(SERIOUSLY)", font(IMPACT, 50), (200, 30, 30), spacing=2)
    return img


def tex_sticky(text, color=(255, 240, 120), size=256, fsize=23):
    img = Image.new("RGB", (size, size), color)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, size, 26], fill=tuple(int(c * 0.92) for c in color))
    centered(d, (10, 30, size - 10, size - 10), text, font(HANDB, fsize), (40, 40, 90))
    return img


def tex_trophy_plaque():
    img = Image.new("RGB", (256, 128), (60, 45, 30))
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 246, 118], fill=(210, 175, 70), outline=(120, 90, 30), width=4)
    centered(d, (10, 10, 246, 118), "CHUCK \u00b7 1998\nHIGH SCORE: 117", font(BOLD, 26), (60, 40, 10))
    return img


def tex_poster_employee():
    img = Image.new("RGB", (256, 360), (245, 245, 235))
    d = ImageDraw.Draw(img)
    d.rectangle([4, 4, 251, 355], outline=(30, 60, 140), width=6)
    centered(d, (10, 10, 246, 90), "EMPLOYEE\nOF THE MONTH", font(IMPACT, 38), (30, 60, 140), spacing=0)
    # crude portrait of Chuck
    d.ellipse([78, 110, 178, 220], fill=(235, 190, 160), outline=(40, 40, 40), width=3)
    d.rectangle([70, 100, 186, 120], fill=(220, 190, 110))
    d.ellipse([60, 108, 196, 126], fill=(220, 190, 110))
    d.polygon([(95, 180), (128, 172), (161, 180), (150, 192), (106, 192)], fill=(110, 70, 40))
    d.ellipse([103, 145, 113, 155], fill=(30, 30, 30))
    d.ellipse([143, 145, 153, 155], fill=(30, 30, 30))
    centered(d, (10, 235, 246, 350), "CHUCK\n(every month\nsince 1987)", font(BOLD, 20), (40, 40, 40))
    return img


def tex_photo_earl():
    img = Image.new("RGB", (320, 256), (90, 60, 40))
    d = ImageDraw.Draw(img)
    d.rectangle([14, 14, 306, 242], fill=(190, 215, 235))
    d.rectangle([14, 170, 306, 242], fill=(110, 160, 80))
    # Big Earl the bull
    d.ellipse([60, 110, 200, 190], fill=(60, 45, 35))
    d.ellipse([170, 95, 230, 150], fill=(60, 45, 35))
    d.polygon([(175, 100), (160, 70), (185, 95)], fill=(235, 225, 190))
    d.polygon([(225, 100), (245, 70), (215, 95)], fill=(235, 225, 190))
    for lx in (75, 100, 150, 175):
        d.rectangle([lx, 180, lx + 12, 215], fill=(50, 38, 30))
    d.ellipse([200, 115, 208, 123], fill=(255, 255, 255))
    # Chuck (younger, thinner mustache)
    d.rectangle([240, 120, 280, 210], fill=(60, 90, 150))
    d.ellipse([242, 80, 278, 120], fill=(235, 190, 160))
    d.rectangle([236, 74, 284, 84], fill=(220, 190, 110))
    d.rectangle([252, 104, 268, 110], fill=(110, 70, 40))
    # ribbon
    d.ellipse([120, 60, 150, 90], fill=(40, 80, 200))
    d.polygon([(128, 88), (122, 110), (135, 100), (142, 110), (142, 88)], fill=(40, 80, 200))
    centered(d, (14, 214, 306, 242), "Me & Big Earl, Best in Show 2009", font(HAND, 14), (30, 30, 30))
    return img


# ---------------------------------------------------------------------------
# Chuck's house: one finish per room, fabrics, screens
# ---------------------------------------------------------------------------

def _noise_img(c0, c1, beta=2.0, seed=None, size=256):
    return to_img(colorize(tile_noise(size, beta, seed=seed), c0, c1))


def tex_wall_living():
    """Warm cream with narrow tan pinstripes: the living room and hall."""
    img = _noise_img((226, 212, 180), (236, 224, 196), 1.6, seed=31)
    d = ImageDraw.Draw(img)
    for x in range(0, 256, 32):
        d.line([(x + 4, 0), (x + 4, 256)], fill=(196, 172, 128), width=2)
        d.line([(x + 9, 0), (x + 9, 256)], fill=(208, 188, 148), width=1)
    return img


def tex_wall_kitchen():
    """Buttery yellow paint over plaster."""
    return _noise_img((236, 214, 150), (246, 228, 170), 2.4, seed=32)


def tex_wall_bath():
    """Pale mint gloss paint (the tiles go halfway up)."""
    return _noise_img((200, 224, 212), (214, 236, 224), 2.4, seed=36)


def tex_wall_office():
    """Knotty pine panelling, the kind every den had."""
    n = tile_noise(256, 3.0, seed=33)
    img = to_img(colorize(n, (150, 104, 62), (178, 128, 80)))
    d = ImageDraw.Draw(img)
    for x in range(0, 256, 42):
        d.line([(x, 0), (x, 256)], fill=(96, 62, 36), width=3)
        d.line([(x + 3, 0), (x + 3, 256)], fill=(190, 140, 92), width=1)
    rng = np.random.default_rng(34)
    for _ in range(9):
        cx, cy = int(rng.uniform(0, 256)), int(rng.uniform(0, 256))
        d.ellipse([cx - 5, cy - 3, cx + 5, cy + 3], fill=(110, 70, 40))
    return img


def tex_wall_bedroom():
    """Dusty blue with a thin white stripe."""
    img = _noise_img((150, 170, 186), (162, 182, 198), 1.8, seed=35)
    d = ImageDraw.Draw(img)
    for x in range(0, 256, 64):
        d.line([(x + 20, 0), (x + 20, 256)], fill=(214, 222, 228), width=3)
    return img


def tex_tiles_kitchen():
    """Cream and terracotta squares with soft grout."""
    size = 256
    img = Image.new("RGB", (size, size), (220, 206, 186))
    d = ImageDraw.Draw(img)
    s = 64
    for x in range(4):
        for y in range(4):
            c = (184, 102, 70) if (x + y) % 2 else (232, 220, 196)
            d.rectangle([x * s + 2, y * s + 2, x * s + s - 2, y * s + s - 2], fill=c)
    return img.filter(ImageFilter.GaussianBlur(0.6))


def tex_tiles_bath():
    """Small white wall-and-floor tiles, a few pale blue ones."""
    size = 256
    img = Image.new("RGB", (size, size), (176, 180, 184))
    d = ImageDraw.Draw(img)
    s = 32
    rng = np.random.default_rng(36)
    for x in range(8):
        for y in range(8):
            c = (170, 205, 225) if rng.random() < 0.12 else (238, 240, 240)
            d.rectangle([x * s + 1, y * s + 1, x * s + s - 2, y * s + s - 2], fill=c)
    return img


def tex_carpet_house():
    """Oatmeal carpet (it used to be grass green, which looked like a lawn indoors)."""
    return _noise_img((168, 146, 116), (186, 164, 132), 0.6, seed=37)


def tex_quilt():
    """Patchwork quilt with stitched seams."""
    size = 256
    img = Image.new("RGB", (size, size), (230, 220, 200))
    d = ImageDraw.Draw(img)
    cols = [(170, 60, 55), (60, 90, 140), (228, 214, 186), (90, 120, 70), (200, 150, 70), (130, 70, 90)]
    rng = np.random.default_rng(38)
    s = 64
    for x in range(4):
        for y in range(4):
            c = cols[int(rng.integers(0, len(cols)))]
            d.rectangle([x * s, y * s, x * s + s, y * s + s], fill=c)
            if (x + y) % 2:
                d.polygon([(x * s, y * s), (x * s + s, y * s), (x * s, y * s + s)],
                          fill=tuple(min(255, v + 25) for v in c))
    for i in range(0, size, s):
        for k in range(0, size, 8):
            d.line([(i + 1, k), (i + 1, k + 4)], fill=(245, 240, 225), width=1)
            d.line([(k, i + 1), (k + 4, i + 1)], fill=(245, 240, 225), width=1)
    return img


def tex_upholstery():
    """A mustard corduroy for the sofa and armchair."""
    n = tile_noise(256, 1.2, seed=39)
    a = colorize(n, (150, 112, 40), (170, 130, 52))
    a[:, ::4, :] *= 0.86                      # the cords
    return to_img(a)


def tex_books():
    """Rows of book spines for the shelves."""
    img = Image.new("RGB", (256, 256), (60, 40, 25))
    d = ImageDraw.Draw(img)
    rng = np.random.default_rng(40)
    cols = [(120, 30, 30), (30, 60, 110), (40, 90, 50), (150, 120, 60), (90, 60, 100), (180, 160, 120), (60, 50, 40)]
    for row in range(4):
        y0, y1 = row * 64 + 6, row * 64 + 62
        x = 0
        while x < 256:
            w = int(rng.integers(8, 18))
            top = y0 + int(rng.integers(0, 12))
            c = cols[int(rng.integers(0, len(cols)))]
            d.rectangle([x, top, x + w - 1, y1], fill=c)
            d.line([(x + 2, top + 8), (x + w - 3, top + 8)], fill=(220, 200, 140), width=1)
            d.line([(x + 2, y1 - 10), (x + w - 3, y1 - 10)], fill=(220, 200, 140), width=1)
            x += w + 1
    return img


def tex_keyboard():
    """A beige keyboard seen from above."""
    img = Image.new("RGB", (512, 160), (206, 198, 176))
    d = ImageDraw.Draw(img)
    for r in range(5):
        y = 12 + r * 28
        x = 12 + (r % 2) * 8
        while x < 380:
            w = 26 if not (r == 4 and 120 < x < 260) else 150
            d.rounded_rectangle([x, y, x + w - 3, y + 24], radius=3, fill=(232, 226, 208), outline=(160, 152, 132))
            x += w
    for r in range(4):
        for c in range(4):
            x, y = 400 + c * 27, 12 + r * 28
            d.rounded_rectangle([x, y, x + 24, y + 24], radius=3, fill=(232, 226, 208), outline=(160, 152, 132))
    return img


def tex_painting_barn():
    """A little oil painting of a red barn under a big sky (Chuck's mother painted it)."""
    img = Image.new("RGB", (256, 192), (120, 170, 210))
    d = ImageDraw.Draw(img)
    for y in range(0, 110):
        k = y / 110
        d.line([(0, y), (256, y)], fill=(int(110 + 90 * k), int(160 + 60 * k), int(210 + 20 * k)))
    d.ellipse([190, 20, 226, 56], fill=(250, 230, 160))
    d.polygon([(0, 120), (60, 92), (130, 112), (200, 90), (256, 108), (256, 192), (0, 192)], fill=(92, 140, 70))
    d.polygon([(0, 150), (256, 132), (256, 192), (0, 192)], fill=(110, 158, 78))
    d.rectangle([70, 100, 130, 150], fill=(160, 40, 35))
    d.polygon([(64, 102), (100, 76), (136, 102)], fill=(90, 40, 35))
    d.rectangle([92, 122, 108, 150], fill=(230, 220, 200))
    d.rectangle([150, 112, 162, 150], fill=(200, 200, 205))
    d.ellipse([150, 104, 162, 116], fill=(200, 200, 205))
    return img.filter(ImageFilter.GaussianBlur(0.8))


def _crt(img):
    """Scanlines, a soft glow and a darker rim: an old tube screen."""
    a = np.asarray(img).astype(float)
    a[::3, :, :] *= 0.82
    h, w = a.shape[:2]
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.sqrt(((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2)
    a *= np.clip(1.15 - 0.35 * r ** 2, 0.55, 1.0)[..., None]
    return to_img(a).filter(ImageFilter.GaussianBlur(0.7))


def tex_tv():
    """Channel 4's cooking show: Carl, a grill, a steak, and a caption nobody here wants to read."""
    img = Image.new("RGB", (512, 384), (70, 50, 40))
    d = ImageDraw.Draw(img)
    # studio: warm back wall with a window flat, a counter, a grill
    d.rectangle([0, 0, 512, 250], fill=(176, 120, 76))
    d.rectangle([40, 30, 190, 150], fill=(150, 200, 230), outline=(250, 240, 220), width=6)
    d.line([(115, 30), (115, 150)], fill=(250, 240, 220), width=5)
    d.line([(40, 90), (190, 90)], fill=(250, 240, 220), width=5)
    d.rectangle([0, 250, 512, 384], fill=(96, 70, 50))
    d.rectangle([0, 238, 512, 262], fill=(220, 214, 200))
    # Carl: chef's whites, a tall hat, a very big grin
    d.rectangle([300, 120, 400, 250], fill=(245, 245, 240))
    d.ellipse([318, 60, 382, 124], fill=(236, 190, 160))
    d.rectangle([322, 12, 378, 66], fill=(250, 250, 250))
    d.ellipse([314, 0, 386, 36], fill=(250, 250, 250))
    d.ellipse([332, 84, 342, 94], fill=(40, 30, 30))
    d.ellipse([358, 84, 368, 94], fill=(40, 30, 30))
    d.arc([334, 92, 366, 116], 10, 170, fill=(120, 40, 40), width=4)
    d.line([(400, 150), (450, 110)], fill=(245, 245, 240), width=16)
    d.line([(446, 112), (470, 70)], fill=(160, 160, 170), width=5)                 # the tongs
    # the grill and the steak
    d.rectangle([180, 196, 330, 244], fill=(40, 40, 42))
    for x in range(186, 326, 12):
        d.line([(x, 196), (x, 208)], fill=(90, 90, 95), width=3)
    d.ellipse([210, 176, 300, 212], fill=(120, 50, 36), outline=(70, 26, 20), width=3)
    for k in range(3):
        d.line([(222 + k * 22, 184), (238 + k * 22, 204)], fill=(60, 24, 18), width=3)
    # lower third caption and the channel bug
    d.rectangle([0, 292, 512, 356], fill=(180, 30, 30))
    d.rectangle([0, 292, 512, 298], fill=(250, 210, 80))
    centered(d, (0, 298, 512, 356), "BEEF TONIGHT!", font(IMPACT, 44), (255, 250, 230))
    d.ellipse([446, 16, 494, 64], fill=(250, 250, 250))
    centered(d, (446, 16, 494, 64), "4", font(IMPACT, 34), (180, 30, 30))
    centered(d, (0, 356, 512, 384), "Cooking with Carl  ·  weeknights at 6", font(BOLD, 18), (240, 230, 210))
    return _crt(img)


def _os_frame(title):
    """A ChuckOS 95 desktop with one window open; returns (img, draw, window box)."""
    img = Image.new("RGB", (512, 384), (32, 120, 120))
    d = ImageDraw.Draw(img)
    # desktop icons
    for i, label in enumerate(["My Cows", "Taxes", "Solitaire"]):
        y = 16 + i * 64
        d.rectangle([18, y, 50, y + 30], fill=(240, 230, 150), outline=(20, 20, 20))
        centered(d, (0, y + 32, 70, y + 50), label, font(BOLD, 11), (255, 255, 255))
    # taskbar
    d.rectangle([0, 352, 512, 384], fill=(192, 192, 192))
    d.line([(0, 353), (512, 353)], fill=(255, 255, 255), width=2)
    d.rectangle([4, 357, 74, 380], fill=(200, 200, 200), outline=(40, 40, 40))
    centered(d, (4, 357, 74, 380), "Start", font(BOLD, 14), (10, 10, 10))
    d.rectangle([440, 357, 508, 380], fill=(200, 200, 200), outline=(128, 128, 128))
    centered(d, (440, 357, 508, 380), "4:52 PM", font(BOLD, 12), (10, 10, 10))
    # the window
    box = (96, 52, 480, 330)
    d.rectangle(box, fill=(212, 208, 200), outline=(20, 20, 20), width=2)
    d.rectangle([box[0] + 3, box[1] + 3, box[2] - 3, box[1] + 26], fill=(20, 40, 140))
    d.text((box[0] + 10, box[1] + 6), title, font=font(BOLD, 14), fill=(255, 255, 255))
    for i, c in enumerate("_□x"):
        x = box[2] - 70 + i * 22
        d.rectangle([x, box[1] + 6, x + 18, box[1] + 23], fill=(200, 200, 200), outline=(40, 40, 40))
    return img, d, box


def tex_monitor_login():
    img, d, (x0, y0, x1, y1) = _os_frame("Welcome to ChuckOS 95")
    smiling_cow(d, x0 + 64, y0 + 110, 34, wink=False)
    d.text((x0 + 120, y0 + 50), "Type your password to", font=font(BOLD, 15), fill=(20, 20, 20))
    d.text((x0 + 120, y0 + 70), "log on to ChuckOS.", font=font(BOLD, 15), fill=(20, 20, 20))
    d.text((x0 + 120, y0 + 112), "User name:", font=font(BOLD, 14), fill=(20, 20, 20))
    d.rectangle([x0 + 210, y0 + 108, x1 - 20, y0 + 130], fill=(255, 255, 255), outline=(60, 60, 60))
    d.text((x0 + 216, y0 + 111), "CHUCK", font=font(BOLD, 14), fill=(10, 10, 10))
    d.text((x0 + 120, y0 + 146), "Password:", font=font(BOLD, 14), fill=(20, 20, 20))
    d.rectangle([x0 + 210, y0 + 142, x1 - 20, y0 + 164], fill=(255, 255, 255), outline=(60, 60, 60))
    d.line([(x0 + 216, y0 + 146), (x0 + 216, y0 + 160)], fill=(10, 10, 10), width=2)
    for i, label in enumerate(["OK", "Cancel"]):
        bx = x0 + 150 + i * 100
        d.rectangle([bx, y0 + 200, bx + 84, y0 + 228], fill=(212, 208, 200), outline=(20, 20, 20), width=2)
        centered(d, (bx, y0 + 200, bx + 84, y0 + 228), label, font(BOLD, 14), (10, 10, 10))
    d.text((x0 + 20, y0 + 244), "Hint: my best friend (NOT Dale)", font=font(BOLD, 12), fill=(90, 20, 20))
    return _crt(img)


def tex_monitor_inbox():
    img, d, (x0, y0, x1, y1) = _os_frame("ChuckOS Mail - Inbox (3)")
    rows = [("Dale", "RE: sunday!!!"), ("Happy Acres Processing", "RE: Pickup confirmation"), ("Mom", "(no subject)")]
    d.rectangle([x0 + 8, y0 + 34, x1 - 8, y0 + 56], fill=(180, 176, 168))
    d.text((x0 + 14, y0 + 38), "From", font=font(BOLD, 13), fill=(10, 10, 10))
    d.text((x0 + 240, y0 + 38), "Subject", font=font(BOLD, 13), fill=(10, 10, 10))
    for i, (who, subj) in enumerate(rows):
        y = y0 + 60 + i * 30
        if i == 0:
            d.rectangle([x0 + 8, y - 2, x1 - 8, y + 24], fill=(20, 40, 140))
        col = (255, 255, 255) if i == 0 else (10, 10, 10)
        d.text((x0 + 14, y + 3), who, font=font(BOLD, 13), fill=col)
        f13 = font(BOLD, 13)
        room = x1 - 14 - (x0 + 240)
        while f13.getlength(subj) > room and len(subj) > 4:
            subj = subj[:-2].rstrip() + "…"
        d.text((x0 + 240, y + 3), subj, font=f13, fill=col)
    d.rectangle([x0 + 8, y0 + 160, x1 - 8, y1 - 10], fill=(255, 255, 255), outline=(90, 90, 90))
    for i, line in enumerate(["Chuck buddy. Can't wait for Sunday.", "I'm bringing the good potato salad.",
                              "Re: the other thing. We're agreed..."]):
        d.text((x0 + 16, y0 + 168 + i * 20), line, font=font(BOLD, 13), fill=(20, 20, 20))
    return _crt(img)


def tex_calendar():
    img = Image.new("RGB", (256, 320), (250, 250, 245))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 256, 120], fill=(120, 170, 90))
    smiling_cow(d, 128, 62, 42, wink=False)
    centered(d, (0, 122, 256, 150), "MOO-VEMBER", font(IMPACT, 26), (40, 40, 40))
    for r in range(5):
        for c in range(7):
            x, y = 12 + c * 33, 160 + r * 30
            d.rectangle([x, y, x + 30, y + 27], outline=(150, 150, 150))
            n = r * 7 + c + 1
            if n <= 30:
                d.text((x + 3, y + 2), str(n), font=font(BOLD, 12), fill=(60, 60, 60))
    d.line([(12 + 6 * 33, 160 + 2 * 30), (12 + 6 * 33 + 30, 160 + 2 * 30 + 27)], fill=(220, 30, 30), width=4)
    d.line([(12 + 6 * 33 + 30, 160 + 2 * 30), (12 + 6 * 33, 160 + 2 * 30 + 27)], fill=(220, 30, 30), width=4)
    return img


def tex_cookbook():
    img = Image.new("RGB", (200, 280), (170, 40, 35))
    d = ImageDraw.Draw(img)
    centered(d, (10, 20, 190, 260), "101\nWAYS\nTO COOK\nA COW", font(IMPACT, 40), (250, 230, 190), spacing=2)
    return img


def tex_window():
    """Window glass: sky reflection, two highlight streaks and a white mullion cross."""
    w = h = 128
    y = np.linspace(0, 1, h)[:, None]
    top = np.array([150, 175, 200], dtype=float)
    bot = np.array([45, 60, 80], dtype=float)
    a = top[None, None, :] * (1 - y[..., None]) + bot[None, None, :] * y[..., None]
    a = np.repeat(a, w, axis=1)
    xx = np.arange(w)[None, :]
    yy = np.arange(h)[:, None]
    for off, wid, k in ((20, 14, 0.35), (58, 6, 0.25)):
        band = np.abs((xx + yy * 0.8) - (off + 40)) < wid
        a = np.where(band[..., None], a + (255 - a) * k, a)
    img = to_img(a)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w - 1, h - 1], outline=(245, 245, 240), width=7)
    d.rectangle([w // 2 - 3, 0, w // 2 + 3, h], fill=(245, 245, 240))
    d.rectangle([0, h // 2 - 3, w, h // 2 + 3], fill=(245, 245, 240))
    return img


def tex_welcome_mat():
    img = Image.new("RGB", (384, 192), (150, 110, 60))
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 374, 182], outline=(90, 60, 30), width=6)
    centered(d, (10, 10, 374, 182), "WELCOME", font(IMPACT, 80), (90, 60, 30))
    return img


def tex_road_sign_steak():
    img = Image.new("RGB", (512, 256), (30, 110, 60))
    d = ImageDraw.Draw(img)
    d.rectangle([8, 8, 503, 247], outline=(255, 255, 255), width=6)
    centered(d, (10, 10, 502, 246), "\u2191 FREEDOM  12\n\u2193 HAPPY ACRES  0", font(BOLD, 44), (255, 255, 255))
    return img


# --------------------------------------------------------------------------
# item icons (64x64 RGBA, crude on purpose)
# --------------------------------------------------------------------------

def _icon():
    img = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


OUT = (30, 25, 20, 255)


def icon_rock():
    img, d = _icon()
    d.polygon([(18, 60), (26, 34), (50, 24), (74, 36), (80, 62), (58, 76), (30, 74)], fill=(140, 138, 132), outline=OUT, width=4)
    d.line([(40, 40), (56, 50)], fill=(100, 100, 95), width=3)
    return img


def icon_page():
    img, d = _icon()
    d.polygon([(22, 12), (70, 12), (78, 22), (76, 86), (20, 84)], fill=(235, 228, 200), outline=OUT, width=3)
    for y in range(28, 80, 10):
        d.line([(28, y), (68, y)], fill=(90, 110, 160), width=2)
    d.ellipse([48, 56, 76, 84], fill=(160, 130, 90, 180))
    return img


def icon_pliers():
    img, d = _icon()
    d.line([(20, 80), (50, 44)], fill=(200, 40, 40), width=10)
    d.line([(76, 80), (46, 44)], fill=(200, 40, 40), width=10)
    d.polygon([(44, 48), (40, 14), (50, 14), (52, 44)], fill=(150, 150, 160), outline=OUT)
    d.polygon([(52, 48), (56, 14), (46, 14), (44, 44)], fill=(170, 170, 180), outline=OUT)
    d.ellipse([42, 40, 54, 52], fill=(120, 120, 130), outline=OUT)
    return img


def icon_radio():
    img, d = _icon()
    d.rounded_rectangle([12, 30, 84, 80], radius=8, fill=(170, 60, 50), outline=OUT, width=4)
    d.ellipse([20, 40, 50, 70], fill=(60, 50, 45), outline=OUT, width=2)
    d.rectangle([56, 42, 78, 52], fill=(240, 230, 190))
    d.line([(70, 30), (84, 8)], fill=OUT, width=3)
    return img


def icon_cowbell():
    img, d = _icon()
    d.polygon([(30, 20), (66, 20), (80, 74), (16, 74)], fill=(200, 170, 70), outline=OUT, width=4)
    d.ellipse([40, 68, 56, 84], fill=(90, 80, 60), outline=OUT, width=2)
    d.rectangle([40, 8, 56, 22], fill=(120, 80, 50), outline=OUT, width=2)
    return img


def icon_key(color=(220, 190, 60)):
    img, d = _icon()
    d.ellipse([10, 30, 42, 62], fill=color, outline=OUT, width=4)
    d.ellipse([20, 40, 32, 52], fill=(0, 0, 0, 0))
    d.rectangle([40, 42, 86, 50], fill=color, outline=OUT, width=2)
    d.rectangle([70, 50, 76, 62], fill=color, outline=OUT, width=2)
    d.rectangle([80, 50, 86, 58], fill=color, outline=OUT, width=2)
    return img


def icon_jerrycan():
    img, d = _icon()
    d.rounded_rectangle([18, 22, 78, 86], radius=6, fill=(200, 40, 35), outline=OUT, width=4)
    d.line([(24, 30), (72, 78)], fill=(150, 25, 25), width=4)
    d.line([(72, 30), (24, 78)], fill=(150, 25, 25), width=4)
    d.rectangle([28, 10, 50, 22], fill=(60, 60, 60), outline=OUT, width=2)
    return img


def icon_sparkplug():
    img, d = _icon()
    d.rectangle([40, 8, 56, 40], fill=(240, 240, 240), outline=OUT, width=3)
    d.polygon([(34, 40), (62, 40), (62, 58), (34, 58)], fill=(150, 150, 160), outline=OUT)
    d.rectangle([42, 58, 54, 80], fill=(170, 170, 170), outline=OUT, width=2)
    d.line([(54, 82), (46, 88)], fill=OUT, width=3)
    return img


def icon_score():
    img, d = _icon()
    d.rectangle([14, 10, 82, 86], fill=(245, 240, 225), outline=OUT, width=3)
    for y in (26, 46, 66):
        for k in range(5):
            d.line([(20, y + k * 3), (76, y + k * 3)], fill=(60, 60, 60), width=1)
    for x, y in [(26, 30), (38, 27), (52, 33), (64, 29), (30, 52), (48, 49), (62, 55)]:
        d.ellipse([x - 4, y - 3, x + 4, y + 3], fill=(40, 30, 20))
        d.line([(x + 3, y), (x + 3, y - 12)], fill=(40, 30, 20), width=2)
    return img


def icon_photo():
    img, d = _icon()
    d.rectangle([10, 16, 86, 80], fill=(110, 75, 45), outline=OUT, width=3)
    d.rectangle([18, 24, 78, 72], fill=(190, 215, 235))
    d.ellipse([26, 44, 56, 66], fill=(60, 45, 35))
    d.ellipse([50, 38, 64, 52], fill=(60, 45, 35))
    return img


def icon_glasses():
    img, d = _icon()
    d.ellipse([10, 34, 44, 62], outline=OUT, width=5)
    d.ellipse([52, 34, 86, 62], outline=OUT, width=5)
    d.line([(44, 44), (52, 44)], fill=OUT, width=4)
    return img


def icon_bucket():
    img, d = _icon()
    d.polygon([(18, 28), (78, 28), (70, 84), (26, 84)], fill=(150, 150, 155), outline=OUT, width=4)
    d.arc([18, 6, 78, 50], 180, 360, fill=OUT, width=4)
    d.ellipse([18, 22, 78, 34], fill=(120, 120, 125), outline=OUT, width=2)
    return img


def icon_boot():
    img, d = _icon()
    d.polygon([(30, 10), (54, 10), (56, 60), (82, 66), (82, 84), (26, 84)], fill=(40, 110, 50), outline=OUT, width=4)
    return img


def icon_rubber_chicken():
    img, d = _icon()
    d.ellipse([18, 36, 66, 70], fill=(250, 220, 60), outline=OUT, width=3)
    d.line([(62, 44), (80, 18)], fill=(250, 220, 60), width=10)
    d.ellipse([72, 8, 90, 26], fill=(250, 220, 60), outline=OUT, width=3)
    d.polygon([(88, 16), (96, 20), (88, 22)], fill=(240, 120, 30))
    d.polygon([(76, 6), (80, 0), (84, 8)], fill=(220, 30, 30))
    d.line([(30, 68), (26, 88)], fill=(240, 120, 30), width=4)
    d.line([(46, 68), (50, 88)], fill=(240, 120, 30), width=4)
    return img


def icon_moustache():
    img, d = _icon()
    d.chord([10, 30, 50, 70], 0, 180, fill=(80, 50, 30), outline=OUT, width=3)
    d.chord([46, 30, 86, 70], 0, 180, fill=(80, 50, 30), outline=OUT, width=3)
    return img


def icon_shotgun():
    img, d = _icon()
    d.polygon([(6, 60), (30, 50), (40, 60), (14, 76)], fill=(120, 75, 40), outline=OUT, width=3)
    d.rectangle([30, 48, 90, 56], fill=(70, 70, 75), outline=OUT, width=2)
    d.rectangle([30, 56, 80, 62], fill=(60, 60, 65), outline=OUT, width=2)
    return img


def icon_plank():
    img, d = _icon()
    d.polygon([(8, 70), (76, 12), (88, 24), (20, 82)], fill=(170, 130, 80), outline=OUT, width=3)
    return img


def icon_fuse():
    img, d = _icon()
    d.rectangle([26, 36, 70, 60], fill=(240, 240, 230), outline=OUT, width=3)
    d.rectangle([14, 40, 26, 56], fill=(200, 170, 70), outline=OUT, width=2)
    d.rectangle([70, 40, 82, 56], fill=(200, 170, 70), outline=OUT, width=2)
    d.line([(34, 48), (62, 48)], fill=(200, 40, 40), width=3)
    return img


def icon_clover():
    img, d = _icon()
    g = (240, 200, 40)
    for cx, cy in [(48, 26), (30, 48), (66, 48)]:
        d.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=g, outline=OUT, width=3)
    d.line([(48, 52), (56, 88)], fill=(150, 120, 20), width=5)
    return img


def icon_heart(full=True):
    img, d = _icon()
    col = (220, 50, 50) if full else (60, 40, 40)
    d.ellipse([12, 18, 50, 56], fill=col, outline=OUT, width=4)
    d.ellipse([46, 18, 84, 56], fill=col, outline=OUT, width=4)
    d.polygon([(15, 46), (48, 84), (81, 46)], fill=col, outline=OUT)
    d.line([(15, 46), (48, 84), (81, 46)], fill=OUT, width=4)
    d.rectangle([22, 36, 74, 50], fill=col)
    if full:
        d.ellipse([22, 26, 34, 38], fill=(255, 160, 150))
    return img


def icon_egg():
    img, d = _icon()
    d.ellipse([26, 14, 70, 84], fill=(250, 245, 230), outline=OUT, width=4)
    return img


def icon_pencil():
    img, d = _icon()
    d.polygon([(14, 80), (22, 64), (74, 12), (84, 22), (32, 74)], fill=(250, 200, 50), outline=OUT, width=3)
    d.polygon([(14, 80), (22, 64), (32, 74)], fill=(230, 190, 150))
    return img


def icon_horseshoe():
    img, d = _icon()
    d.arc([16, 14, 80, 78], 150, 390, fill=(140, 140, 150), width=14)
    d.arc([16, 14, 80, 78], 150, 390, fill=OUT, width=2)
    return img


def icon_coffee():
    img, d = _icon()
    d.rectangle([22, 26, 64, 82], fill=(240, 240, 240), outline=OUT, width=4)
    d.arc([56, 38, 80, 64], 270, 90, fill=OUT, width=5)
    d.rectangle([26, 30, 60, 40], fill=(90, 50, 20))
    for x in (32, 44, 56):
        d.arc([x - 6, 4, x + 6, 24], 90, 270, fill=(180, 180, 180), width=2)
    return img


def icon_tincan():
    img, d = _icon()
    d.rectangle([26, 20, 70, 80], fill=(180, 180, 190), outline=OUT, width=4)
    d.ellipse([26, 12, 70, 28], fill=(200, 200, 210), outline=OUT, width=3)
    d.rectangle([28, 40, 68, 62], fill=(200, 60, 60))
    return img


def icon_shoes():
    img, d = _icon()
    d.polygon([(10, 60), (20, 44), (46, 44), (50, 60), (48, 70), (12, 70)], fill=(200, 40, 40), outline=OUT, width=3)
    d.polygon([(46, 70), (56, 54), (82, 54), (86, 70), (84, 80), (48, 80)], fill=(40, 120, 200), outline=OUT, width=3)
    return img


def icon_hat():
    img, d = _icon()
    d.ellipse([6, 52, 90, 74], fill=(220, 190, 110), outline=OUT, width=3)
    d.rounded_rectangle([26, 26, 70, 62], radius=10, fill=(230, 200, 120), outline=OUT, width=3)
    d.rectangle([26, 50, 70, 58], fill=(160, 40, 35))
    return img


def icon_generic(color=(200, 200, 200)):
    img, d = _icon()
    d.ellipse([16, 16, 80, 80], fill=color, outline=OUT, width=4)
    return img


def icon_wrench():
    img, d = _icon()
    d.line([(20, 78), (64, 34)], fill=(160, 160, 170), width=12)
    d.ellipse([56, 12, 88, 44], fill=(160, 160, 170), outline=OUT, width=3)
    d.rectangle([66, 14, 78, 30], fill=(0, 0, 0, 0))
    return img


def icon_chimes():
    img, d = _icon()
    d.ellipse([24, 6, 72, 18], fill=(120, 80, 50), outline=OUT, width=2)
    for i, x in enumerate([30, 40, 50, 60, 68]):
        d.line([(x, 14), (x, 30)], fill=OUT, width=1)
        d.rectangle([x - 3, 30, x + 3, 60 + i * 5], fill=(200, 200, 210), outline=OUT, width=1)
    return img


def icon_gnome_key():
    return icon_key((200, 200, 210))


def icon_cabinet_key():
    return icon_key((150, 110, 60))


def icon_tractor_key():
    return icon_key((60, 150, 60))


ICONS = {
    "rock": icon_rock, "page": icon_page, "pliers": icon_pliers, "radio": icon_radio, "cowbell": icon_cowbell,
    "key": icon_key, "tractor_key": icon_tractor_key, "house_key": icon_gnome_key, "cabinet_key": icon_cabinet_key,
    "jerrycan": icon_jerrycan, "sparkplug": icon_sparkplug, "score": icon_score, "photo": icon_photo,
    "glasses": icon_glasses, "bucket": icon_bucket, "boot": icon_boot, "rubber_chicken": icon_rubber_chicken,
    "moustache": icon_moustache, "shotgun": icon_shotgun, "plank": icon_plank, "fuse": icon_fuse,
    "clover": icon_clover, "egg": icon_egg, "pencil": icon_pencil, "horseshoe": icon_horseshoe,
    "coffee": icon_coffee, "tincan": icon_tincan, "shoes": icon_shoes, "hat": icon_hat, "wrench": icon_wrench,
    "chimes": icon_chimes, "heart": icon_heart, "heart_empty": lambda: icon_heart(False),
}


# character atlas: (x0, y0, x1, y1) in pixels, y measured from the top
ATLAS_W, ATLAS_H = 1024, 512
ATLAS = {
    "hide_bw": (0, 0, 256, 256), "hide_brown": (256, 0, 512, 256), "hide_black": (512, 0, 768, 256),
    "hide_gray": (768, 0, 1024, 256), "hide_red": (0, 256, 256, 512), "hide_dun": (256, 256, 512, 512),
    "plaid": (512, 256, 640, 384), "denim": (640, 256, 768, 384), "straw": (768, 256, 896, 384),
    "white": (896, 256, 1024, 384), "tag_47": (512, 384, 576, 448), "tag_12": (576, 384, 640, 448),
    "tag_12_mud": (640, 384, 704, 448), "tag_blank": (704, 384, 768, 448), "bark": (768, 384, 896, 512),
    "hay": (896, 384, 1024, 512),
}


def tex_atlas():
    img = Image.new("RGB", (ATLAS_W, ATLAS_H), (255, 255, 255))
    parts = {
        "hide_bw": lambda: tex_cowhide(seed=21), "hide_brown": lambda: tex_cowhide(spot=(120, 70, 40), seed=22),
        "hide_black": lambda: tex_cowhide(spot=(245, 242, 235), base=(28, 25, 25), n_spots=3, seed=23),
        "hide_gray": lambda: tex_cowhide(spot=(90, 88, 88), base=(190, 188, 185), n_spots=7, seed=24),
        "hide_red": lambda: tex_cowhide(spot=(245, 242, 235), base=(130, 55, 35), n_spots=5, seed=25),
        "hide_dun": lambda: tex_cowhide(spot=(245, 240, 225), base=(185, 150, 100), n_spots=6, seed=26),
        "plaid": tex_plaid, "denim": tex_denim, "straw": tex_straw, "white": tex_white,
        "tag_47": lambda: tex_eartag(47), "tag_12": lambda: tex_eartag(12), "tag_12_mud": tex_eartag_mud,
        "tag_blank": lambda: tex_eartag(""), "bark": tex_bark, "hay": tex_hay,
    }
    for k, (x0, y0, x1, y1) in ATLAS.items():
        im = parts[k]().convert("RGB").resize((x1 - x0, y1 - y0))
        img.paste(im, (x0, y0))
    return img


def all_textures():
    t = {
        "grass": tex_grass, "dirt": tex_dirt, "mud": tex_mud, "gravel": tex_gravel, "wood": tex_wood,
        "wood_dark": tex_wood_dark, "barn_red": tex_barn_red, "floorboards": tex_floorboards, "siding": tex_siding,
        "fence_wood": tex_fence_wood, "hay": tex_hay, "concrete": tex_concrete, "metal": tex_metal,
        "metal_rust": tex_metal_rust, "shingles": tex_shingles, "stone": tex_stone, "wallpaper": tex_wallpaper,
        "tiles": tex_tiles, "carpet": tex_carpet, "water": tex_water, "plaid": tex_plaid, "denim": tex_denim,
        "straw": tex_straw, "white": tex_white, "paper": tex_paper, "blob_shadow": tex_blob_shadow, "vignette": tex_vignette,
        "soft_circle": tex_soft_circle, "leaves": tex_leaves, "bark": tex_bark,
        "cowhide": lambda: tex_cowhide(seed=11),
        "cowhide_brown": lambda: tex_cowhide(spot=(120, 70, 40), seed=12),
        "cowhide_black": lambda: tex_cowhide(spot=(245, 242, 235), base=(28, 25, 25), n_spots=4, seed=13),
        "cowhide_gray": lambda: tex_cowhide(spot=(90, 88, 88), base=(190, 188, 185), n_spots=7, seed=14),
        "cowhide_red": lambda: tex_cowhide(spot=(245, 242, 235), base=(130, 55, 35), n_spots=5, seed=15),
        "cowhide_dun": lambda: tex_cowhide(spot=(245, 240, 225), base=(185, 150, 100), n_spots=6, seed=16),
        "sign_farm": tex_sign_farm, "sign_processing": tex_sign_processing, "sign_cowshed": tex_sign_cowshed,
        "sign_47": tex_sign_47, "tag_47": lambda: tex_eartag(47), "tag_12_mud": tex_eartag_mud, "tag_12": lambda: tex_eartag(12),
        "tag_blank": lambda: tex_eartag(""),
        "john_steer": tex_john_steer, "do_not_touch": tex_do_not_touch,
        "sticky_combo": lambda: tex_sticky("TOOLBOX COMBO =\nmy PERFECT\nbowling score!!!\n(don't forget)"),
        "sticky_password": lambda: tex_sticky("PASSWORD HINT:\nmy best friend\n(NOT Dale)", (255, 200, 220)),
        "sticky_mat": lambda: tex_sticky("Spare key is\nunder the\nFLOWERPOT", (200, 240, 255)),
        "sticky_pot": lambda: tex_sticky("Moved it.\nSpare key is in\nthe GNOME.\n-Chuck", (200, 255, 200)),
        "trophy_plaque": tex_trophy_plaque, "poster_employee": tex_poster_employee, "photo_earl": tex_photo_earl,
        "tv": tex_tv, "monitor": tex_monitor_login, "monitor_inbox": tex_monitor_inbox, "calendar": tex_calendar,
        "cookbook": tex_cookbook, "wall_living": tex_wall_living, "wall_kitchen": tex_wall_kitchen,
        "wall_office": tex_wall_office, "wall_bedroom": tex_wall_bedroom, "tiles_kitchen": tex_tiles_kitchen,
        "tiles_bath": tex_tiles_bath, "wall_bath": tex_wall_bath, "carpet_house": tex_carpet_house, "quilt": tex_quilt,
        "upholstery": tex_upholstery, "books": tex_books, "keyboard": tex_keyboard,
        "painting_barn": tex_painting_barn,
        "welcome_mat": tex_welcome_mat, "window": tex_window, "road_sign": tex_road_sign_steak, "atlas": tex_atlas,
    }
    for name, fn in ICONS.items():
        t["icon_" + name] = fn
    return t


def generate_all(out_dir: str, progress=None):
    os.makedirs(out_dir, exist_ok=True)
    ver_path = os.path.join(out_dir, ".version")
    if os.path.exists(ver_path):
        with open(ver_path) as f:
            if f.read().strip() == TEX_VERSION:
                return False
    tex = all_textures()
    for i, (name, fn) in enumerate(tex.items()):
        img = fn()
        img.save(os.path.join(out_dir, name + ".png"))
        if progress:
            progress(i + 1, len(tex), name)
    with open(ver_path, "w") as f:
        f.write(TEX_VERSION)
    return True


if __name__ == "__main__":
    import time
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from breakowt.engine.assets import TEX_DIR
    out = str(TEX_DIR)
    vp = os.path.join(out, ".version")
    if os.path.exists(vp):
        os.remove(vp)
    t0 = time.time()
    generate_all(out)
    print(f"done in {time.time() - t0:.1f}s")
