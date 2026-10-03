"""Procedural audio for BREAKOWT.

Every sound in the game — moos, the farmer's trombone mumbling, sound effects,
ambience and music — is synthesized here with numpy/scipy and written to
assets/generated/audio/*.wav the first time the game runs.
"""
from __future__ import annotations

import os
import wave

import numpy as np
from scipy import signal

SR = 44100
AUDIO_VERSION = "11"

_rng = np.random.default_rng(47)


# --------------------------------------------------------------------------
# basic helpers
# --------------------------------------------------------------------------

def tt(dur: float) -> np.ndarray:
    return np.arange(int(round(dur * SR))) / SR


def write_wav(path: str, x: np.ndarray, peak: float = 0.89, name: str | None = None):
    x = np.asarray(x, dtype=np.float64)
    if name is not None:
        x = master(name, x)  # loudness by category (see LOUDNESS)
    else:
        m = float(np.max(np.abs(x))) if x.size else 0.0
        if m > 1e-9:
            x = x * (peak / m)
    x = np.clip(x, -1.0, 1.0)
    data = (x * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(data.tobytes())


def env_adsr(n: int, a=0.01, d=0.05, s=0.7, r=0.1) -> np.ndarray:
    a_n, d_n, r_n = int(a * SR), int(d * SR), int(r * SR)
    a_n = max(a_n, 1)
    s_n = max(n - a_n - d_n - r_n, 0)
    e = np.concatenate([
        np.linspace(0, 1, a_n, endpoint=False),
        np.linspace(1, s, d_n, endpoint=False),
        np.full(s_n, s),
        np.linspace(s, 0, r_n),
    ])
    if len(e) < n:
        e = np.pad(e, (0, n - len(e)))
    return e[:n]


def fade_edges(x: np.ndarray, fin=0.005, fout=0.02) -> np.ndarray:
    x = x.copy()
    a, b = int(fin * SR), int(fout * SR)
    if a > 0:
        x[:a] *= np.linspace(0, 1, a)
    if b > 0:
        x[-b:] *= np.linspace(1, 0, b)
    return x


def mix(*parts) -> np.ndarray:
    """Sum arrays of different lengths. Each part is an array or (array, gain)."""
    arrs = [(p, 1.0) if isinstance(p, np.ndarray) else p for p in parts]
    n = max(len(a) for a, _ in arrs)
    out = np.zeros(n)
    for a, g in arrs:
        out[:len(a)] += a * g
    return out


def noise(n: int) -> np.ndarray:
    return _rng.standard_normal(n)


def bandpass(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def lowpass(x, fc, order=2):
    sos = signal.butter(order, fc, btype="low", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def highpass(x, fc, order=2):
    sos = signal.butter(order, fc, btype="high", fs=SR, output="sos")
    return signal.sosfilt(sos, x)


def fft_filter_periodic(x: np.ndarray, gain_fn) -> np.ndarray:
    """Filter in the frequency domain — the result loops seamlessly."""
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(X * gain_fn(f), n=len(x))


def reverb(x: np.ndarray, decay=1.6, wet=0.3, predelay=0.02, tone=4000) -> np.ndarray:
    n_ir = int(decay * SR)
    t = np.arange(n_ir) / SR
    ir = noise(n_ir) * np.exp(-t * 6.9 / decay)
    ir = lowpass(ir, tone)
    ir[: int(predelay * SR)] = 0
    ir /= np.sqrt(np.sum(ir ** 2)) + 1e-9
    y = signal.fftconvolve(x, ir)[: len(x) + n_ir]
    dry = np.pad(x, (0, len(y) - len(x)))
    return dry * (1 - wet) + y * wet * 0.9


class Track:
    """Simple mix buffer."""

    def __init__(self, dur: float):
        self.buf = np.zeros(int(dur * SR) + SR * 4)
        self.length = int(dur * SR)

    def add(self, t0: float, x: np.ndarray, gain=1.0):
        i = int(t0 * SR)
        if i < 0:
            x = x[-i:]
            i = 0
        j = min(i + len(x), len(self.buf))
        self.buf[i:j] += x[: j - i] * gain

    def add_wrapped(self, t0: float, x: np.ndarray, gain=1.0):
        """Add with wrap-around so the first `length` samples loop seamlessly."""
        i = int(t0 * SR) % self.length
        n = len(x)
        pos = 0
        while pos < n:
            take = min(n - pos, self.length - i)
            self.buf[i:i + take] += x[pos:pos + take] * gain
            pos += take
            i = 0

    def loop(self) -> np.ndarray:
        return self.buf[: self.length]

    def out(self, tail=2.0) -> np.ndarray:
        return self.buf[: self.length + int(tail * SR)]


def midi(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def nm(name: str) -> int:
    """'Bb4' -> midi number."""
    letter = name[0]
    rest = name[1:]
    acc = 0
    while rest and rest[0] in "b#":
        acc += -1 if rest[0] == "b" else 1
        rest = rest[1:]
    return 12 * (int(rest) + 1) + NOTE[letter] + acc


# --------------------------------------------------------------------------
# voice synthesis (additive, time-varying formants)
# --------------------------------------------------------------------------

def formant_gain(f: np.ndarray, formants) -> np.ndarray:
    g = np.full_like(f, 0.012)
    for F, B, A in formants:
        g = g + A / (1.0 + ((f - F) / B) ** 2)
    return g


def interp_formants(sets, times, t_norm):
    """sets: list of [(F,B,A)...]; times: keyframes in 0..1; returns per-sample arrays."""
    nf = len(sets[0])
    out = []
    for i in range(nf):
        F = np.interp(t_norm, times, [s[i][0] for s in sets])
        B = np.interp(t_norm, times, [s[i][1] for s in sets])
        A = np.interp(t_norm, times, [s[i][2] for s in sets])
        out.append((F, B, A))
    return out


def additive_voice(f0: np.ndarray, formants, tilt=1.1, max_h=64, rough=0.0,
                   breath=0.0, amp: np.ndarray | None = None) -> np.ndarray:
    n = len(f0)
    phase = 2 * np.pi * np.cumsum(f0) / SR
    out = np.zeros(n)
    for k in range(1, max_h + 1):
        fk = f0 * k
        if np.min(fk) > SR * 0.45:
            break
        a = formant_gain(fk, formants) / (k ** tilt)
        a = a * (fk < SR * 0.45)
        out += a * np.sin(k * phase + _rng.uniform(0, 6.28))
    if rough > 0:
        # subharmonic growl: modulate at f0/2
        out *= 1.0 + rough * np.sin(phase * 0.5)
    if breath > 0:
        nb = bandpass(noise(n), 300, 3500) * breath * 0.08
        out += nb
    if amp is not None:
        out *= amp
    return out


def contour(n, points):
    """points: list of (t_norm, value)."""
    t = np.linspace(0, 1, n)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return np.interp(t, xs, ys)


MOO_M = [(260, 70, 1.0), (900, 200, 0.04), (2400, 300, 0.01)]
MOO_OO = [(340, 90, 1.0), (780, 120, 0.45), (2300, 250, 0.08)]
MOO_OA = [(560, 110, 1.0), (980, 140, 0.55), (2450, 260, 0.1)]

VOICES = {
    # name: f0, brightness(tilt), rough, breath, vibrato depth, vibrato rate, formant scale
    "player": dict(f0=112, tilt=1.05, rough=0.15, breath=0.15, vib=0.012, vr=5.0, fs=1.0),
    "cowleen": dict(f0=150, tilt=0.95, rough=0.05, breath=0.2, vib=0.015, vr=5.5, fs=1.08),
    "moozart": dict(f0=128, tilt=1.0, rough=0.05, breath=0.1, vib=0.03, vr=5.2, fs=1.02),
    "sirloin": dict(f0=84, tilt=1.1, rough=0.45, breath=0.1, vib=0.01, vr=4.0, fs=0.9),
    "cowpernicus": dict(f0=168, tilt=0.9, rough=0.0, breath=0.1, vib=0.01, vr=6.0, fs=1.15),
    "mooriarty": dict(f0=100, tilt=1.15, rough=0.2, breath=0.6, vib=0.008, vr=4.5, fs=0.95),
    "moomaw": dict(f0=136, tilt=1.0, rough=0.3, breath=0.3, vib=0.05, vr=6.5, fs=1.0),
}

MOO_KINDS = {
    # kind: duration, pitch contour, formant keyframes
    "short": (0.55, [(0, 0.9), (0.3, 1.04), (1, 0.82)], [MOO_M, MOO_OO, MOO_OO], [0, 0.25, 1]),
    "medium": (0.95, [(0, 0.88), (0.25, 1.05), (0.6, 1.0), (1, 0.78)], [MOO_M, MOO_OO, MOO_OA, MOO_OO], [0, 0.2, 0.55, 1]),
    "long": (1.5, [(0, 0.86), (0.2, 1.05), (0.5, 1.02), (0.8, 0.92), (1, 0.75)], [MOO_M, MOO_OO, MOO_OA, MOO_OA, MOO_OO], [0, 0.15, 0.4, 0.7, 1]),
    "question": (0.9, [(0, 0.92), (0.35, 0.86), (0.75, 1.1), (1, 1.28)], [MOO_M, MOO_OO, MOO_OA], [0, 0.25, 1]),
    "exclaim": (0.8, [(0, 1.1), (0.15, 1.32), (0.6, 1.1), (1, 0.85)], [MOO_M, MOO_OA, MOO_OA, MOO_OO], [0, 0.12, 0.6, 1]),
    "sad": (1.4, [(0, 1.0), (0.3, 0.95), (1, 0.68)], [MOO_M, MOO_OO, MOO_OO], [0, 0.25, 1]),
}


def formant_noise(n, forms, nper=1024, hop=256):
    """White noise shaped by the time-varying formants: breath through the vocal tract."""
    f, ft, Z = signal.stft(noise(n), SR, nperseg=nper, noverlap=nper - hop, boundary="even")
    idx = np.clip((ft * SR).astype(int), 0, n - 1)
    G = np.full((len(f), len(ft)), 0.01)
    for F, B, A in forms:
        Fv = np.asarray(F)[idx] if np.ndim(F) else np.full(len(ft), float(F))
        Bv = np.asarray(B)[idx] if np.ndim(B) else np.full(len(ft), float(B))
        Av = np.asarray(A)[idx] if np.ndim(A) else np.full(len(ft), float(A))
        G += Av[None, :] / (1.0 + ((f[:, None] - Fv[None, :]) / (Bv[None, :] * 1.6)) ** 2)
    _, y = signal.istft(Z * G, SR, nperseg=nper, noverlap=nper - hop, boundary=True)
    y = y[:n]
    if len(y) < n:
        y = np.pad(y, (0, n - len(y)))
    return y / (np.sqrt(np.mean(y ** 2)) + 1e-9)


def room(x, wet=0.1, size=0.55):
    """A pasture, not a vacuum: a few reflections off a barn wall and a short open-air tail."""
    y = np.concatenate([x, np.zeros(int(0.06 * SR))])
    soft = lowpass(x, 2800)
    for d, g in ((0.019, 0.22), (0.031, 0.16), (0.047, 0.1)):
        k = int(d * SR)
        y[k:k + len(x)] += soft * g * wet * 3.5
    return reverb(y, decay=size, wet=wet, tone=3000)


def moo(f0=120, kind="medium", tilt=1.0, rough=0.1, breath=0.2, vib=0.015, vr=5.0, fs=1.0,
        dur=None) -> np.ndarray:
    d, pc, fsets, ftimes = MOO_KINDS[kind]
    if dur is not None:
        d = dur
    d *= _rng.uniform(0.9, 1.1)
    n = int(d * SR)
    t = np.arange(n) / SR
    base = contour(n, pc) * f0 * _rng.uniform(0.97, 1.03)
    # slow wandering pitch (a cow is not a synthesizer) plus fast jitter
    drift = lowpass(noise(n), 3) * 6
    jitter = lowpass(noise(n), 40) * 2
    vib_env = np.clip((t - 0.15) / 0.3, 0, 1)
    f0c = base * (1 + vib * np.sin(2 * np.pi * vr * t + _rng.uniform(0, 6)) * vib_env) \
        * (1 + 0.012 * drift + 0.006 * jitter)
    sets = [[(F * fs * _rng.uniform(0.96, 1.04), B, A) for (F, B, A) in s] for s in fsets]
    forms = interp_formants(sets, ftimes, np.linspace(0, 1, n))
    amp = contour(n, [(0, 0), (0.07, 0.35), (0.2, 0.75), (0.32, 1.0), (0.72, 0.85), (1, 0)])
    amp = amp ** 1.2
    shimmer = 1 + 0.08 * lowpass(noise(n), 12) * 4
    voiced = additive_voice(f0c, forms, tilt=tilt + 0.15, rough=rough, breath=0.0, amp=amp * shimmer)
    # breath: noise through the same formants, strongest at the onset and in the fading tail
    br_env = amp * (0.6 + 0.8 * contour(n, [(0, 1), (0.25, 0.3), (0.7, 0.35), (1, 1)]))
    asp = formant_noise(n, forms) * br_env
    level = np.sqrt(np.mean(voiced ** 2)) + 1e-9
    x = voiced + asp * level * (0.18 + 0.55 * breath)
    # the nasal 'mm' onset is darker than the open 'oo'
    x = lowpass(x, 3800)
    return room(fade_edges(x), wet=0.09, size=0.5)


def sung_moo(freq: float, dur: float, voice="moozart", open_=0.5, fs=1.0) -> np.ndarray:
    """A moo held on a musical pitch (used by Archimoodes and the cow choir)."""
    v = VOICES.get(voice, VOICES["moozart"])
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.018 * np.sin(2 * np.pi * 5.2 * t + _rng.uniform(0, 6)) * np.clip((t - 0.15) / 0.3, 0, 1)
    scoop = 1 - 0.04 * np.exp(-t / 0.06)
    f0c = freq * vib * scoop * (1 + 0.004 * lowpass(noise(n), 5) * 5)
    mid = [(F * (1 - open_) + G * open_, B, A) for (F, B, A), (G, _, _) in zip(MOO_OO, MOO_OA)]
    mid = [(F * fs * v["fs"], B, A) for F, B, A in mid]
    mset = [(F * fs, B, A) for F, B, A in MOO_M]
    kt = min(0.12 / max(dur, 0.2), 0.4)
    forms = interp_formants([mset, mid, mid], [0, kt, 1], np.linspace(0, 1, n))
    rel = min(0.25, dur * 0.3)
    amp = np.minimum(1, t / 0.06) * np.clip((dur - t) / rel, 0, 1)
    amp = amp * (0.55 + 0.45 * np.clip(t / 0.12, 0, 1))
    voiced = additive_voice(f0c, forms, tilt=v["tilt"] + 0.1, rough=v["rough"] * 0.3, breath=0.0, amp=amp)
    level = np.sqrt(np.mean(voiced ** 2)) + 1e-9
    x = voiced + formant_noise(n, forms) * amp * level * (0.12 + 0.3 * v["breath"])
    return lowpass(x, 4200)


def trombone_voice(syllables, base=120.0, mute=True, speed=1.0) -> np.ndarray:
    """'Wah-wah' adult-from-a-cartoon speech. syllables: list of (dur, pitch_ratio)."""
    parts = []
    for dur, pr in syllables:
        dur /= speed
        n = int(dur * SR)
        t = np.linspace(0, 1, n)
        f0 = base * pr * (1 + 0.06 * np.sin(np.pi * t)) * (1 + 0.01 * np.sin(2 * np.pi * 6 * t * dur))
        F1 = 320 + 480 * np.sin(np.pi * np.clip(t * 1.3, 0, 1)) ** 1.5
        F2 = 820 + 520 * np.sin(np.pi * np.clip(t * 1.3, 0, 1)) ** 1.5
        forms = [(F1, 110, 1.0), (F2, 160, 0.7), (np.full(n, 1500.0), 300, 0.35 if mute else 0.1)]
        amp = np.minimum(1, t * dur / 0.03) * np.clip((1 - t) * dur / 0.06, 0, 1)
        x = additive_voice(f0, forms, tilt=0.7, rough=0.05, breath=0.05, amp=amp)
        parts.append(x)
        parts.append(np.zeros(int(0.03 * SR / speed)))
    return fade_edges(np.concatenate(parts))


# --------------------------------------------------------------------------
# instruments
# --------------------------------------------------------------------------

def music_box(freq, dur=1.6, vel=1.0):
    t = tt(dur)
    x = (np.sin(2 * np.pi * freq * t) * np.exp(-t / 1.1)
         + 0.35 * np.sin(2 * np.pi * freq * 2.0 * t) * np.exp(-t / 0.35)
         + 0.18 * np.sin(2 * np.pi * freq * 5.93 * t) * np.exp(-t / 0.12)
         + 0.08 * np.sin(2 * np.pi * freq * 9.2 * t) * np.exp(-t / 0.05))
    click = noise(len(t)) * np.exp(-t / 0.003) * 0.15
    return fade_edges((x + click) * vel, 0.001, 0.05)


def piano(freq, dur=2.0, vel=1.0):
    t = tt(dur + 0.4)
    x = np.zeros_like(t)
    B = 0.0004
    for k in range(1, 14):
        fk = freq * k * np.sqrt(1 + B * k * k)
        if fk > SR * 0.45:
            break
        tau = 1.8 / (1 + 0.35 * k) * (220 / max(freq, 80)) ** 0.3
        x += (1 / k ** 1.3) * np.sin(2 * np.pi * fk * t + _rng.uniform(0, 6)) * np.exp(-t / tau)
    x *= np.minimum(1, t / 0.004)
    rel = np.clip((dur + 0.4 - t) / 0.4, 0, 1)
    return fade_edges(x * rel * vel, 0.001, 0.05)


def strings(freq, dur, vel=1.0, attack=0.35, release=0.5, voices=3):
    t = tt(dur + release)
    x = np.zeros_like(t)
    for v in range(voices):
        det = 1 + (v - (voices - 1) / 2) * 0.004
        vib = 1 + 0.004 * np.sin(2 * np.pi * (5 + v * 0.3) * t + v)
        f = freq * det * vib
        ph = 2 * np.pi * np.cumsum(f) / SR
        for k in range(1, 12):
            if freq * k > 9000:
                break
            x += (1 / k ** 1.4) * np.sin(k * ph + _rng.uniform(0, 6))
    env = np.minimum(1, t / attack) * np.clip((dur + release - t) / release, 0, 1)
    return lowpass(x * env, 3500) * vel / voices


def pad(freq, dur, vel=1.0):
    return strings(freq, dur, vel, attack=0.8, release=1.2, voices=4)


def tuba(freq, dur, vel=1.0):
    t = tt(dur + 0.08)
    scoop = 1 - 0.06 * np.exp(-t / 0.03)
    f = freq * scoop
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.zeros_like(t)
    bright = np.minimum(1, t / 0.05) * np.exp(-t / 0.4) * 0.6 + 0.4
    for k in range(1, 16):
        amp = (1 / k ** 1.1) * (1.0 if k < 4 else bright)
        x += amp * np.sin(k * ph)
    env = np.minimum(1, t / 0.025) * np.clip((dur + 0.08 - t) / 0.08, 0, 1)
    return lowpass(x * env, 1800) * vel


def kazoo(freq, dur, vel=1.0, vib=0.02):
    t = tt(dur + 0.04)
    f = freq * (1 + vib * np.sin(2 * np.pi * 6 * t) * np.clip(t / 0.15, 0, 1)) * (1 - 0.05 * np.exp(-t / 0.04))
    n = len(t)
    forms = [(np.full(n, 700.0), 200, 1.0), (np.full(n, 1600.0), 250, 0.9), (np.full(n, 3000.0), 400, 0.5)]
    x = additive_voice(f, forms, tilt=0.35, breath=0.4)
    buzz = 1 + 0.25 * np.sign(np.sin(2 * np.pi * f * t))
    env = np.minimum(1, t / 0.02) * np.clip((dur + 0.04 - t) / 0.04, 0, 1)
    return np.tanh(x * buzz * env * 2) * vel


def flute(freq, dur, vel=1.0):
    t = tt(dur + 0.1)
    f = freq * (1 + 0.006 * np.sin(2 * np.pi * 5 * t) * np.clip(t / 0.3, 0, 1))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph)
    x += bandpass(noise(len(t)), freq, min(freq * 3, 9000)) * 0.08
    env = np.minimum(1, t / 0.07) * np.clip((dur + 0.1 - t) / 0.1, 0, 1)
    return x * env * vel


def pluck(freq, dur=1.5, vel=1.0, bright=0.5, decay=0.996):
    """Karplus-Strong, computed block-wise so numpy does the work."""
    n = int(dur * SR)
    N = max(int(SR / freq), 2)
    buf = noise(N) * vel
    if bright < 1:
        buf = lowpass(buf, 800 + 6000 * bright)
    out = np.zeros(n + N)
    out[:N] = buf
    pos = N
    while pos < n + N:
        prev = out[pos - N: pos]
        nxt = 0.5 * (prev + np.concatenate([prev[1:], out[pos:pos + 1] if pos < len(out) else prev[:1]])) * decay
        take = min(N, n + N - pos)
        out[pos:pos + take] = nxt[:take]
        pos += take
    return fade_edges(out[N:N + n], 0.001, 0.05)


def kick(dur=0.35, vel=1.0):
    t = tt(dur)
    f = 45 + 120 * np.exp(-t / 0.04)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t / 0.12) * vel


def snare(dur=0.25, vel=1.0):
    t = tt(dur)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    nz = bandpass(noise(len(t)), 1200, 8000) * np.exp(-t / 0.07)
    return (tone * 0.5 + nz) * vel


def hat(dur=0.08, vel=1.0):
    t = tt(dur)
    return highpass(noise(len(t)), 7000) * np.exp(-t / 0.02) * vel


def bell808(dur=0.5, vel=1.0, f1=587, f2=845):
    t = tt(dur)
    sq = np.sign(np.sin(2 * np.pi * f1 * t)) + np.sign(np.sin(2 * np.pi * f2 * t))
    x = bandpass(sq, 700, 3500)
    env = 0.65 * np.exp(-t / 0.03) + 0.35 * np.exp(-t / 0.22)
    return x * env * vel


def metal_hit(dur=0.9, base=420, vel=1.0):
    t = tt(dur)
    x = np.zeros_like(t)
    for r, a, tau in [(1, 1, 0.35), (1.59, 0.7, 0.3), (2.14, 0.5, 0.22), (2.9, 0.45, 0.15),
                      (3.7, 0.3, 0.1), (5.1, 0.25, 0.06)]:
        x += a * np.sin(2 * np.pi * base * r * t * _rng.uniform(0.98, 1.02)) * np.exp(-t / tau)
    x += bandpass(noise(len(t)), 2000, 9000) * np.exp(-t / 0.01) * 0.6
    return x * vel


# --------------------------------------------------------------------------
# sound effects
# --------------------------------------------------------------------------

def sfx_step(kind="grass"):
    t = tt(0.16)
    n = len(t)
    if kind == "grass":
        thud = np.sin(2 * np.pi * (90 + 60 * np.exp(-t / 0.01)) * t) * np.exp(-t / 0.03)
        rustle = bandpass(noise(n), 1500, 6000) * np.exp(-t / 0.03) * 0.35
        return thud * 0.7 + rustle
    if kind == "wood":
        k = np.sin(2 * np.pi * 820 * t) * np.exp(-t / 0.018) + 0.6 * np.sin(2 * np.pi * 2350 * t) * np.exp(-t / 0.008)
        thud = np.sin(2 * np.pi * 140 * t) * np.exp(-t / 0.04)
        return k * 0.6 + thud
    if kind == "hay":
        return bandpass(noise(n), 800, 7000) * np.exp(-t / 0.05)
    if kind == "water":
        s = bandpass(noise(n), 400, 3000) * np.exp(-t / 0.06)
        bl = np.sin(2 * np.pi * (500 + 900 * t / 0.16) * t) * np.exp(-t / 0.05) * 0.4
        return s + bl
    # gravel/dirt
    return bandpass(noise(n), 900, 5000) * np.exp(-t / 0.035) + np.sin(2 * np.pi * 110 * t) * np.exp(-t / 0.03) * 0.5


def sfx_whoosh(dur=0.35):
    t = tt(dur)
    n = len(t)
    x = noise(n)
    out = np.zeros(n)
    segs = 16
    for i in range(segs):
        a, b = i * n // segs, (i + 1) * n // segs
        fc = 500 + 3000 * (i / segs)
        out[a:b] = bandpass(x, fc * 0.7, fc * 1.3)[a:b]
    env = np.sin(np.pi * t / dur) ** 2
    return out * env


def sfx_thump(dur=0.4, low=55):
    t = tt(dur)
    f = low + 90 * np.exp(-t / 0.03)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t / 0.1) + bandpass(noise(len(t)), 200, 2000) * np.exp(-t / 0.02) * 0.5


def sfx_wood_crack(dur=0.9):
    t = tt(dur)
    n = len(t)
    x = sfx_thump(dur) * 0.8
    for _ in range(14):
        i = int(_rng.uniform(0, 0.45) * SR)
        m = int(0.03 * SR)
        if i + m < n:
            x[i:i + m] += bandpass(noise(m), 1500, 7000) * np.exp(-np.arange(m) / (0.006 * SR)) * _rng.uniform(0.3, 1.0)
    return x


def sfx_rock_land():
    t = tt(0.3)
    click = np.sin(2 * np.pi * 1900 * t) * np.exp(-t / 0.01) + np.sin(2 * np.pi * 3100 * t) * np.exp(-t / 0.006)
    thud = np.sin(2 * np.pi * 160 * t) * np.exp(-t / 0.04)
    return click * 0.5 + thud * 0.7 + bandpass(noise(len(t)), 1000, 6000) * np.exp(-t / 0.02) * 0.4


def sfx_crash():
    tr = Track(1.8)
    for i in range(5):
        tr.add(i * 0.07 + _rng.uniform(0, 0.03), metal_hit(1.2, base=_rng.uniform(300, 700), vel=_rng.uniform(0.5, 1)))
    return tr.out(0.2)


def sfx_kazoo_fanfare():
    tr = Track(1.3)
    notes = [(0, "C5", 0.13), (0.15, "E5", 0.13), (0.3, "G5", 0.13), (0.45, "C6", 0.6)]
    for t0, n, d in notes:
        tr.add(t0, kazoo(midi(nm(n)), d, 0.8))
    return tr.out(0.2)


def sfx_sad_trombone():
    tr = Track(3.2)
    seq = [("Bb3", 0.0, 0.45), ("A3", 0.55, 0.45), ("Ab3", 1.1, 0.45), ("G3", 1.65, 1.3)]
    for name, t0, d in seq:
        f = midi(nm(name))
        n = int(d * SR)
        t = np.arange(n) / SR
        vib = 1 + (0.03 * np.sin(2 * np.pi * 6 * t) * np.clip((t - 0.3) / 0.3, 0, 1) if d > 1 else 0.004 * np.sin(2 * np.pi * 5 * t))
        f0 = f * vib * (1 - 0.03 * np.exp(-t / 0.04))
        forms = [(np.full(n, 520.0), 150, 1.0), (np.full(n, 1100.0), 250, 0.8), (np.full(n, 2300.0), 400, 0.25)]
        wah = 0.55 + 0.45 * np.sin(np.pi * np.clip(t / d, 0, 1))
        amp = np.minimum(1, t / 0.04) * np.clip((d - t) / 0.1, 0, 1) * wah
        tr.add(t0, additive_voice(f0, forms, tilt=0.6, amp=amp))
    return reverb(tr.out(0.5), 1.2, 0.2)


def sfx_alert():
    """The '!' sting (a stealth-game parody)."""
    t = tt(1.2)
    x = np.zeros_like(t)
    for f in [midi(nm("C5")), midi(nm("F#5")), midi(nm("C6")), midi(nm("C4"))]:
        ph = 2 * np.pi * f * t
        for k in range(1, 10):
            x += np.sin(k * ph) / k
    env = np.exp(-t / 0.25) * np.minimum(1, t / 0.005)
    x = x * env + np.sin(2 * np.pi * 70 * t) * np.exp(-t / 0.2) * 2
    return reverb(x, 1.4, 0.25)


def sfx_question():
    tr = Track(0.6)
    tr.add(0, music_box(midi(nm("E5")), 0.5, 0.8))
    tr.add(0.14, music_box(midi(nm("A5")), 0.5, 0.8))
    return tr.out(0.1)


def sfx_ding():
    tr = Track(1.0)
    tr.add(0, bell808(0.6, 1.0))
    tr.add(0.16, bell808(0.8, 1.0))
    return tr.out(0.2)


def sfx_cowbell_jingle(vel=1.0):
    return bell808(0.35, vel, f1=_rng.uniform(560, 610), f2=_rng.uniform(820, 870))


def sfx_door_creak(dur=0.9):
    t = tt(dur)
    f = 380 + 160 * np.sin(2 * np.pi * 1.7 * t) + 40 * lowpass(noise(len(t)), 20) * 20
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.zeros_like(t)
    for k in range(1, 8):
        x += np.sin(k * ph) / k
    # stick-slip grain
    grain = (np.sin(2 * np.pi * 30 * t) > 0.3).astype(float) * 0.6 + 0.4
    env = np.sin(np.pi * t / dur) ** 0.5
    return bandpass(x * grain * env, 300, 4000)


def sfx_door_close():
    return mix(sfx_thump(0.4, 70), (sfx_rock_land(), 0.4))


def sfx_chain_rattle():
    tr = Track(0.8)
    for i in range(10):
        tr.add(_rng.uniform(0, 0.5), metal_hit(0.25, base=_rng.uniform(1500, 2600), vel=_rng.uniform(0.2, 0.6)))
    return tr.out(0.1)


def sfx_zap():
    t = tt(0.8)
    buzz = np.sign(np.sin(2 * np.pi * 120 * t)) * 0.5 + np.sign(np.sin(2 * np.pi * 183 * t)) * 0.3
    crack = (noise(len(t)) * (_rng.random(len(t)) < 0.08)) * 1.5
    return (buzz + bandpass(crack, 1500, 9000)) * np.exp(-t / 0.35)


def sfx_splash():
    t = tt(0.8)
    x = bandpass(noise(len(t)), 300, 5000) * np.exp(-t / 0.18)
    for _ in range(8):
        i = int(_rng.uniform(0.02, 0.5) * SR)
        m = int(0.06 * SR)
        if i + m < len(t):
            tt_ = np.arange(m) / SR
            x[i:i + m] += np.sin(2 * np.pi * (600 + 1800 * tt_ / 0.06) * tt_) * np.exp(-tt_ / 0.02) * 0.4
    return x


def sfx_flush():
    t = tt(3.0)
    swirl = bandpass(noise(len(t)), 200, 3000) * (0.5 + 0.5 * np.sin(2 * np.pi * 2.5 * t))
    env = np.minimum(1, t / 0.3) * np.clip((3.0 - t) / 1.4, 0, 1)
    gurgle = np.sin(2 * np.pi * (200 + 120 * np.sin(2 * np.pi * 7 * t)) * t) * 0.3
    return (swirl + gurgle) * env


def sfx_paper():
    t = tt(0.45)
    x = bandpass(noise(len(t)), 2000, 9000)
    am = (lowpass(np.abs(noise(len(t))), 40) * 4)
    return x * am * np.sin(np.pi * t / 0.45)


def sfx_munch():
    tr = Track(0.9)
    for i in range(4):
        m = int(0.07 * SR)
        x = bandpass(noise(m), 1200, 7000) * np.exp(-np.arange(m) / (0.02 * SR))
        tr.add(i * 0.2 + _rng.uniform(0, 0.03), x, 0.8)
    return tr.out(0.1)


def sfx_clover():
    tr = Track(0.9)
    for i, n in enumerate(["E6", "G6", "B6", "E7"]):
        tr.add(i * 0.06, music_box(midi(nm(n)), 0.6, 0.6))
    return tr.out(0.2)


def sfx_ui_blip(f=880):
    t = tt(0.07)
    return np.sin(2 * np.pi * f * t) * np.exp(-t / 0.02)


def sfx_type_blip():
    t = tt(0.03)
    return np.sin(2 * np.pi * 1300 * t) * np.exp(-t / 0.008)


def sfx_shotgun():
    t = tt(2.5)
    blast = noise(len(t)) * np.exp(-t / 0.08)
    blast = lowpass(blast, 5000) + lowpass(noise(len(t)), 300) * np.exp(-t / 0.3) * 1.2
    boom = np.sin(2 * np.pi * (40 + 60 * np.exp(-t / 0.05)) * t) * np.exp(-t / 0.4) * 1.5
    return reverb(np.tanh((blast + boom) * 2), 2.4, 0.4, tone=2500)


def sfx_punch():
    t = tt(0.35)
    return mix(sfx_thump(0.35, 60), (bandpass(noise(len(t)), 300, 3000) * np.exp(-t / 0.03), 0.5))


def sfx_boing():
    t = tt(0.6)
    f = 180 + 260 * np.exp(-t / 0.15) * (1 + 0.5 * np.sin(2 * np.pi * 14 * t))
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) + 0.3 * np.sin(2 * ph)) * np.exp(-t / 0.25)


def sfx_gate_smash():
    tr = Track(2.5)
    tr.add(0, sfx_wood_crack(1.2), 1.2)
    tr.add(0.02, sfx_crash(), 0.9)
    tr.add(0.05, sfx_thump(0.6, 45), 1.4)
    return reverb(tr.out(0.5), 1.8, 0.3)


def sfx_tractor_start():
    tr = Track(2.2)
    # starter motor whine
    t = tt(1.0)
    whine = np.sin(2 * np.pi * (180 + 40 * np.sin(2 * np.pi * 9 * t)) * t) * 0.3
    tr.add(0, bandpass(whine + noise(len(t)) * 0.1, 100, 2000))
    # catch
    pulses = tractor_pulses(1.2, rate=9, low=48)
    tr.add(0.9, pulses * np.linspace(1.5, 1.0, len(pulses)))
    return tr.out(0.2)


def tractor_pulses(dur, rate=11.0, low=55):
    tr = Track(dur)
    n_p = int(dur * rate)
    for i in range(n_p):
        m = int(0.09 * SR)
        tm = np.arange(m) / SR
        p = np.sin(2 * np.pi * (low + 30 * np.exp(-tm / 0.01)) * tm) * np.exp(-tm / 0.03)
        p += bandpass(noise(m), 150, 1200) * np.exp(-tm / 0.02) * 0.6
        tr.add_wrapped(i / rate, p, _rng.uniform(0.8, 1.0))
    return tr.loop()


def loop_tractor():
    x = tractor_pulses(2.0, rate=11, low=55)
    x += fft_filter_periodic(noise(len(x)), lambda f: (f > 60) * (f < 400) * 1.0) * 0.08
    return x


def loop_truck():
    x = tractor_pulses(2.0, rate=8, low=40)
    x += fft_filter_periodic(noise(len(x)), lambda f: (f > 40) * (f < 250) * 1.0) * 0.12
    return x


def loop_generator():
    dur = 2.0
    t = tt(dur)
    x = np.zeros_like(t)
    for k, a in [(1, 1), (2, 0.6), (3, 0.3), (4, 0.25), (6, 0.1), (8, 0.06)]:
        x += a * np.sin(2 * np.pi * 60 * k * t)
    x *= 1 + 0.15 * np.sin(2 * np.pi * 3 * t)
    x += fft_filter_periodic(noise(len(t)), lambda f: (f > 100) * (f < 1500) * 1.0) * 0.1
    return x


def loop_fence_hum():
    dur = 2.0
    t = tt(dur)
    x = np.sin(2 * np.pi * 120 * t) * 0.5 + np.sin(2 * np.pi * 240 * t) * 0.3
    tick = np.zeros_like(t)
    for i in range(2):  # electric fence 'tick' once per second
        j = int(i * SR)
        m = int(0.02 * SR)
        tick[j:j + m] += noise(m) * np.exp(-np.arange(m) / (0.004 * SR))
    return x * 0.3 + highpass(tick, 2000) * 2


def loop_grinder():
    dur = 2.4
    tr = Track(dur)
    t = tt(dur)
    hiss = fft_filter_periodic(noise(len(t)), lambda f: (f > 2500) * (f < 9000) * 1.0)
    stroke = (np.sin(np.pi * ((t % 1.2) / 1.2)) ** 3)
    tr.add(0, hiss * stroke * 0.6)
    ring = np.zeros_like(t)
    for r in [1, 2.7, 4.1]:
        ring += np.sin(2 * np.pi * 1240 * r * t) / r
    tr.add(0, ring * stroke * 0.15)
    tr.add(0, np.sin(2 * np.pi * 95 * t) * 0.15)
    return tr.loop()


def loop_wind(dur=12.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = fft_filter_periodic(noise(n), lambda f: 1 / (1 + (f / 400) ** 2) * (f > 30))
    mod = 0.6 + 0.4 * np.sin(2 * np.pi * t / dur * 2) * np.sin(2 * np.pi * t / dur * 3 + 1)
    return x * mod


def loop_rain(dur=10.0):
    n = int(dur * SR)
    tr = Track(dur)
    base = fft_filter_periodic(noise(n), lambda f: (f > 400) * 1 / (1 + (f / 6000) ** 2))
    tr.add(0, base * 0.5)
    for _ in range(int(dur * 60)):
        m = int(0.012 * SR)
        d = bandpass(noise(m), 2000, 9000) * np.exp(-np.arange(m) / (0.002 * SR))
        tr.add_wrapped(_rng.uniform(0, dur), d, _rng.uniform(0.1, 0.5))
    return tr.loop()


def loop_birds(dur=16.0):
    tr = Track(dur)
    for _ in range(int(dur * 1.4)):
        t0 = _rng.uniform(0, dur)
        kind = _rng.integers(0, 3)
        base = _rng.uniform(2200, 4200)
        if kind == 0:  # trill
            for j in range(_rng.integers(3, 8)):
                d = 0.05
                t = tt(d)
                f = base * (1 + 0.15 * np.sin(np.pi * t / d))
                tr.add_wrapped(t0 + j * 0.065, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d), 0.3)
        elif kind == 1:  # sweep
            d = _rng.uniform(0.12, 0.3)
            t = tt(d)
            f = base * (1 + 0.5 * t / d)
            tr.add_wrapped(t0, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d), 0.35)
        else:  # two-tone
            for j, r in enumerate([1.0, 0.8]):
                d = 0.14
                t = tt(d)
                tr.add_wrapped(t0 + j * 0.18, np.sin(2 * np.pi * base * r * t) * np.sin(np.pi * t / d), 0.3)
    return tr.loop()


def loop_crickets(dur=10.0):
    tr = Track(dur)
    for c in range(5):
        f = _rng.uniform(4200, 5200)
        period = _rng.uniform(0.6, 1.1)
        t0 = _rng.uniform(0, period)
        gain = _rng.uniform(0.2, 0.5)
        k = 0
        while t0 + k * period < dur:
            d = 0.12
            t = tt(d)
            chirp = np.sin(2 * np.pi * f * t) * (np.sin(2 * np.pi * 45 * t) > 0) * np.sin(np.pi * t / d)
            tr.add_wrapped(t0 + k * period, chirp, gain)
            k += 1
    return tr.loop()


def loop_snore(dur=4.0):
    tr = Track(dur)
    t = tt(1.6)
    rattle = (np.sin(2 * np.pi * 28 * t) > 0).astype(float)
    inh = bandpass(noise(len(t)), 150, 1200) * rattle * np.sin(np.pi * t / 1.6) ** 2
    inh += np.sin(2 * np.pi * 70 * t) * rattle * 0.4 * np.sin(np.pi * t / 1.6)
    tr.add_wrapped(0.2, inh, 1.0)
    t2 = tt(1.4)
    exh = bandpass(noise(len(t2)), 1500, 6000) * np.sin(np.pi * t2 / 1.4) ** 2 * 0.4
    tr.add_wrapped(2.2, exh, 1.0)
    return tr.loop()


def loop_hum_crowd(dur=8.0):
    """Distant herd murmur (low moos) for the pasture."""
    tr = Track(dur)
    for _ in range(5):
        v = dict(VOICES["player"])
        v["f0"] = _rng.uniform(90, 160)
        x = moo(kind=_rng.choice(["short", "medium", "long"]), **v)
        x = lowpass(x, 1500)
        tr.add_wrapped(_rng.uniform(0, dur), x, _rng.uniform(0.1, 0.3))
    return tr.loop()


def rooster_crow():
    sylls = [(0.14, 720, 1.0), (0.1, 640, 0.8), (0.22, 860, 1.0), (0.16, 800, 0.9), (0.75, 900, 1.0)]
    parts = []
    for i, (d, f, a) in enumerate(sylls):
        n = int(d * SR)
        t = np.linspace(0, 1, n)
        if i == 4:
            f0 = f * (1 + 0.12 * np.sin(np.pi * t * 0.8) - 0.18 * t ** 3)
        else:
            f0 = f * (1 + 0.1 * np.sin(np.pi * t))
        forms = [(np.full(n, 1400.0), 350, 1.0), (np.full(n, 2600.0), 450, 0.6), (np.full(n, 3800.0), 500, 0.3)]
        amp = np.minimum(1, t * d / 0.02) * np.clip((1 - t) * d / 0.05, 0, 1) * a
        x = additive_voice(f0, forms, tilt=0.5, rough=0.6, breath=0.8, amp=amp)
        parts.append(x)
        parts.append(np.zeros(int(0.025 * SR)))
    return reverb(np.tanh(np.concatenate(parts) * 3), 1.0, 0.15)


def chicken_cluck(n=3):
    parts = []
    for i in range(n):
        d = _rng.uniform(0.07, 0.12) if i < n - 1 else 0.3
        m = int(d * SR)
        t = np.linspace(0, 1, m)
        f0 = _rng.uniform(420, 560) * (1 + (0.4 * t if i == n - 1 else 0.1 * np.sin(np.pi * t)))
        forms = [(np.full(m, 1300.0), 300, 1.0), (np.full(m, 2500.0), 400, 0.5)]
        amp = np.minimum(1, t * d / 0.01) * np.clip((1 - t) * d / 0.03, 0, 1)
        parts.append(additive_voice(f0, forms, tilt=0.6, rough=0.4, breath=0.5, amp=amp))
        parts.append(np.zeros(int(_rng.uniform(0.05, 0.12) * SR)))
    return np.tanh(np.concatenate(parts) * 2)


def squawk():
    d = 0.4
    m = int(d * SR)
    t = np.linspace(0, 1, m)
    f0 = 700 * (1 + 0.5 * np.sin(np.pi * t)) * (1 + 0.05 * noise(m))
    forms = [(np.full(m, 1600.0), 400, 1.0), (np.full(m, 3000.0), 500, 0.6)]
    amp = np.minimum(1, t * d / 0.01) * np.clip((1 - t) * d / 0.08, 0, 1)
    return np.tanh(additive_voice(f0, forms, tilt=0.4, rough=0.8, breath=1.2, amp=amp) * 3)


def dun_dun_dunnn():
    """Day title-card sting: dramatic, but on tuba."""
    tr = Track(3.2)
    for t0, n, d in [(0.0, "G2", 0.3), (0.4, "G2", 0.3), (0.8, "Db3", 1.6)]:
        tr.add(t0, tuba(midi(nm(n)), d, 1.0))
        tr.add(t0, tuba(midi(nm(n) - 12), d, 0.6))
        tr.add(t0, strings(midi(nm(n) + 12), d, 0.25, attack=0.02, release=0.4))
    tr.add(0.8, sfx_thump(0.8, 40), 0.6)
    return reverb(tr.out(0.6), 2.0, 0.25)


# --------------------------------------------------------------------------
# music
# --------------------------------------------------------------------------

# Archimoodes' melody: (note, beats). 3/4, 16 bars.
MELODY = [
    [("A4", 2), ("C5", 1)], [("G4", 2), ("E4", 1)], [("F4", 1), ("A4", 1), ("D5", 1)], [("D5", 2), ("C5", 1)],
    [("C5", 2), ("A4", 1)], [("Bb4", 1), ("A4", 1), ("G4", 1)], [("E4", 1), ("G4", 1), ("C5", 1)], [("Bb4", 3)],
    [("A4", 2), ("F4", 1)], [("E4", 2), ("C5", 1)], [("D5", 1), ("C5", 1), ("Bb4", 1)], [("A4", 3)],
    [("F5", 2), ("D5", 1)], [("Db5", 2), ("Bb4", 1)], [("A4", 1), ("C5", 1), ("G4", 1)], [("F4", 3)],
]
# chord per bar: (bass note, chord tones)
CHORDS = [
    ("F2", ["F3", "A3", "C4"]), ("E2", ["C3", "G3", "E4"]), ("D2", ["D3", "F3", "A3"]), ("Bb1", ["Bb2", "D3", "F3"]),
    ("A1", ["F3", "A3", "C4"]), ("G2", ["G3", "Bb3", "F4"]), ("C2", ["C3", "E3", "G3"]), ("C2", ["E3", "G3", "Bb3"]),
    ("D2", ["D3", "F3", "A3"]), ("A1", ["A2", "C3", "E3"]), ("Bb1", ["Bb2", "D3", "F3"]), ("F2", ["F3", "A3", "C4"]),
    ("Bb1", ["Bb2", "D3", "F3"]), ("Bb1", ["Bb2", "Db3", "F3"]), ("C2", ["F3", "A3", "C4"]), ("F2", ["F3", "A3", "C4"]),
]
# a harmony line a third/sixth under the melody for the choir
HARMONY = [
    [("F4", 2), ("A4", 1)], [("E4", 2), ("C4", 1)], [("D4", 1), ("F4", 1), ("A4", 1)], [("Bb4", 2), ("A4", 1)],
    [("A4", 2), ("F4", 1)], [("G4", 1), ("F4", 1), ("E4", 1)], [("C4", 1), ("E4", 1), ("G4", 1)], [("G4", 3)],
    [("F4", 2), ("D4", 1)], [("C4", 2), ("A4", 1)], [("Bb4", 1), ("A4", 1), ("F4", 1)], [("F4", 3)],
    [("D5", 2), ("Bb4", 1)], [("Bb4", 2), ("F4", 1)], [("F4", 1), ("A4", 1), ("E4", 1)], [("C4", 3)],
]
BPM = 76.0
BEAT = 60.0 / BPM
BAR = 3 * BEAT


def melody_events(bars=range(16), transpose=0):
    ev = []
    for bi in bars:
        t = bi * BAR
        for n, b in MELODY[bi]:
            ev.append((t, nm(n) + transpose, b * BEAT))
            t += b * BEAT
    return ev


def harmony_events(bars=range(16), transpose=0):
    ev = []
    for bi in bars:
        t = bi * BAR
        for n, b in HARMONY[bi]:
            ev.append((t, nm(n) + transpose, b * BEAT))
            t += b * BEAT
    return ev


def herd_argue() -> np.ndarray:
    """The whole herd arguing about a proof: overlapping moos, questions and objections, rising, then one
    cow who has to have the last word."""
    rng = np.random.default_rng(31)
    dur = 7.5
    tr = Track(dur)
    voices = ["cowleen", "sirloin", "cowpernicus", "mooriarty", "moomaw", "player"]
    kinds = ["short", "medium", "question", "exclaim", "question", "short"]
    t = 0.0
    k = 0
    while t < 6.0:
        v = VOICES[voices[k % len(voices)]]
        kind = kinds[rng.integers(len(kinds))]
        gain = 0.25 + 0.3 * min(1.0, t / 4.0)          # it escalates
        tr.add(t, moo(kind=kind, **dict(v, f0=v["f0"] * rng.uniform(0.9, 1.12))), gain)
        t += rng.uniform(0.12, 0.45)
        k += 1
    tr.add(6.4, moo(kind="exclaim", **VOICES["sirloin"]), 0.6)
    return reverb(tr.out(0.8), 1.6, 0.25)


def music_box_theme(tempo_scale=1.25, bars=range(16), sparse=False) -> np.ndarray:
    """Slow, lonely music-box version (Thursday)."""
    beat = BEAT * tempo_scale
    bar = 3 * beat
    nb = len(list(bars))
    tr = Track(nb * bar + 2)
    for i, bi in enumerate(bars):
        t = i * bar
        for n, b in MELODY[bi]:
            if not (sparse and _rng.random() < 0.12):
                tr.add(t, music_box(midi(nm(n) + 12), 2.2, 0.7))
            t += b * beat
        bass, tones = CHORDS[bi]
        tr.add(i * bar, music_box(midi(nm(bass) + 24), 2.2, 0.3))
    return reverb(tr.out(1.5), 2.6, 0.35)


D_CHORDS = {
    "D": ("D2", ["D3", "F#3", "A3", "D4"]), "A": ("A1", ["A2", "C#3", "E3", "A3"]),
    "Bm": ("B1", ["B2", "D3", "F#3", "B3"]), "G": ("G1", ["G2", "B2", "D3", "G3"]),
    "Em": ("E2", ["E3", "G3", "B3", "E4"]),
}
ROAD_A = [
    [("F#4", 1), ("A4", 1), ("D5", 1.5), ("C#5", 0.5)], [("E5", 2), ("C#5", 1), ("A4", 1)],
    [("B4", 1), ("D5", 1), ("F#5", 1.5), ("E5", 0.5)], [("D5", 3), ("R", 1)],
    [("F#4", 1), ("A4", 1), ("D5", 1), ("E5", 1)], [("F#5", 2), ("E5", 1), ("C#5", 1)],
    [("B4", 1), ("D5", 1), ("C#5", 1), ("B4", 1)], [("A4", 3), ("R", 1)],
]
ROAD_A_END = ROAD_A[:6] + [[("B4", 1), ("D5", 1), ("E5", 1), ("C#5", 1)], [("D5", 3), ("R", 1)]]
ROAD_B = [
    [("B4", 2), ("A4", 1), ("G4", 1)], [("F#4", 2), ("A4", 2)],
    [("G4", 1), ("B4", 1), ("E5", 1.5), ("D5", 0.5)], [("C#5", 3), ("R", 1)],
    [("B4", 2), ("D5", 1), ("B4", 1)], [("A4", 2), ("F#4", 1), ("A4", 1)],
    [("B4", 1), ("C#5", 1), ("D5", 1), ("F#5", 1)], [("E5", 3), ("R", 1)],
]


def ending_theme() -> np.ndarray:
    """The road out: about two minutes of something warm and unhurried for the hill and the epilogue cards.
    Plucked arpeggios, an upright bass, a simple tune on the piano, then flute and strings. No mooing."""
    bpm = 80
    beat = 60 / bpm
    bar = 4 * beat
    A = ["D", "A", "Bm", "G", "D", "A", "G", "A"]
    A_end = ["D", "A", "Bm", "G", "D", "A", "G", "D"]
    B = ["G", "D", "Em", "A", "G", "D", "Bm", "A"]
    prog = ["D", "A", "Bm", "G"] + A + B + A + B + A_end + ["G", "D", "D"]
    tr = Track(len(prog) * bar + 4)
    for i, c in enumerate(prog):
        root, tones = D_CHORDS[c]
        tb = i * bar
        last = i == len(prog) - 1
        # a soft bed of strings under everything, a touch brighter in the middle
        sv = 0.1 if i < 4 or last else (0.17 if 12 <= i < 20 or 28 <= i < 36 else 0.13)
        for tn in tones[1:]:
            tr.add(tb, strings(midi(nm(tn) + 12), bar * (2.0 if last else 1.02), sv, attack=0.6, release=0.9))
        if last:
            tr.add(tb, piano(midi(nm(root) + 12), bar * 2, 0.4))
            tr.add(tb, pluck(midi(nm(tones[0]) + 12), 3.0, 0.5, bright=0.35), 0.3)
            break
        if i >= 4:
            tr.add(tb, upright_bass(midi(nm(root) + 12), beat * 1.8, 0.75))
            tr.add(tb + 2 * beat, upright_bass(midi(nm(root) + 19), beat * 1.8, 0.55))
        pat = [0, 1, 2, 3, 2, 1, 2, 3] if i % 2 == 0 else [0, 2, 1, 3, 2, 1, 3, 2]
        for j, p in enumerate(pat):
            tr.add(tb + j * beat / 2, pluck(midi(nm(tones[p]) + 12), 1.6, 0.5, bright=0.4), 0.26 if j % 2 else 0.32)
        if 12 <= i < 20 or 28 <= i < 44:
            tr.add(tb + beat, brush(), 0.1)
            tr.add(tb + 3 * beat, brush(), 0.1)
    t = 4 * bar
    for b in ROAD_A:
        t = seq(tr, t, beat, b, piano, 0.42, wrap=False)
    for b in ROAD_B:
        t = seq(tr, t, beat, b, flute, 0.26, wrap=False)
    t2 = t
    for b in ROAD_A:
        t = seq(tr, t, beat, b, piano, 0.4, wrap=False)
    for b in ROAD_A:
        t2 = seq(tr, t2, beat, b, flute, 0.12, transpose=12, wrap=False)
    for b in ROAD_B:
        t = seq(tr, t, beat, b, piano, 0.36, wrap=False)
    t2 = t
    for b in ROAD_A_END:
        t = seq(tr, t, beat, b, piano, 0.42, wrap=False)
    for b in ROAD_A_END:
        t2 = seq(tr, t2, beat, b, flute, 0.18, wrap=False)
    x = tr.out(tail=3.0)
    return reverb(x, decay=1.6, wet=0.16, tone=5000)[: len(x)]


def harmonica(freq, dur, vel=1.0):
    t = tt(dur + 0.08)
    n = len(t)
    wob = 1 + 0.011 * np.sin(2 * np.pi * 5.5 * t) * np.clip((t - 0.2) / 0.3, 0, 1)
    f = freq * wob * (1 - 0.025 * np.exp(-t / 0.03))
    forms = [(np.full(n, 1150.0), 420, 1.0), (np.full(n, 2600.0), 650, 0.45)]
    x = additive_voice(f, forms, tilt=0.6, breath=0.0)
    x += bandpass(noise(n), 1500, 5500) * 0.03
    env = np.minimum(1, t / 0.035) * np.clip((dur + 0.08 - t) / 0.08, 0, 1)
    env *= 0.88 + 0.12 * np.sin(2 * np.pi * 5.5 * t)
    return lowpass(x * env, 5000) * vel


def fiddle(freq, dur, vel=1.0):
    t = tt(dur + 0.15)
    vib = 1 + 0.009 * np.sin(2 * np.pi * 5.8 * t + 1.0) * np.clip((t - 0.12) / 0.25, 0, 1)
    ph = 2 * np.pi * np.cumsum(freq * vib) / SR
    x = np.zeros_like(t)
    for k in range(1, 16):
        if freq * k > 9000:
            break
        x += (1 / k ** 1.05) * (1.35 if k in (2, 3) else 1.0) * np.sin(k * ph + _rng.uniform(0, 6))
    bow = bandpass(noise(len(t)), 2200, 7000) * 0.05
    env = np.minimum(1, t / 0.07) * np.clip((dur + 0.15 - t) / 0.15, 0, 1)
    return lowpass((x * 0.45 + bow) * env, 5200) * vel


def upright_bass(freq, dur, vel=1.0):
    t = tt(dur + 0.1)
    body = np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.7) + 0.3 * np.sin(4 * np.pi * freq * t) * np.exp(-t / 0.3)
    thump = np.sin(2 * np.pi * freq * 0.5 * t) * np.exp(-t / 0.05) * 0.3
    env = np.minimum(1, t / 0.006) * np.clip((dur + 0.1 - t) / 0.1, 0, 1)
    pl = pluck(freq, dur + 0.1, 0.5, bright=0.12, decay=0.995)
    pl = np.pad(pl, (0, max(0, len(t) - len(pl))))[:len(t)]
    return lowpass((body + thump) * env + pl * 0.4, 1600) * vel


def clarinet(freq, dur, vel=1.0):
    t = tt(dur + 0.07)
    f = freq * (1 + 0.004 * np.sin(2 * np.pi * 5 * t) * np.clip((t - 0.2) / 0.3, 0, 1))
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.zeros_like(t)
    for k in range(1, 16, 2):
        if freq * k > 8000:
            break
        x += (1 / k ** 0.9) * np.sin(k * ph)
    x += 0.1 * np.sin(2 * ph)
    x += bandpass(noise(len(t)), 1000, 4000) * 0.02
    env = np.minimum(1, t / 0.05) * np.clip((dur + 0.07 - t) / 0.07, 0, 1)
    return lowpass(x * env, 3200) * vel * 0.6


def muted_trumpet(freq, dur, vel=1.0):
    t = tt(dur + 0.05)
    n = len(t)
    f = freq * (1 - 0.03 * np.exp(-t / 0.03))
    op = np.clip(t / max(dur * 0.55, 0.05), 0, 1)
    forms = [(500 + 700 * op, 150, 1.0), (1300 + 900 * op, 260, 0.8), (np.full(n, 3000.0), 400, 0.3)]
    x = additive_voice(f, forms, tilt=0.5)
    env = np.minimum(1, t / 0.02) * np.clip((dur + 0.05 - t) / 0.05, 0, 1)
    return x * env * vel


def organ(freq, dur, vel=1.0):
    t = tt(dur + 0.04)
    x = np.zeros_like(t)
    for k, a in ((1, 1.0), (2, 0.7), (3, 0.45), (4, 0.3), (6, 0.15), (8, 0.12)):
        if freq * k < 9000:
            x += a * np.sin(2 * np.pi * freq * k * t)
    env = np.minimum(1, t / 0.008) * np.clip((dur + 0.04 - t) / 0.04, 0, 1)
    return x * env * vel * 0.4


def woodblock(pitch=900.0, vel=1.0):
    t = tt(0.14)
    x = np.sin(2 * np.pi * pitch * t) * np.exp(-t / 0.022) + 0.45 * np.sin(2 * np.pi * pitch * 2.41 * t) * np.exp(-t / 0.01)
    x += bandpass(noise(len(t)), 1500, 6000) * np.exp(-t / 0.003) * 0.4
    return x * vel


def brush(vel=1.0):
    t = tt(0.22)
    env = np.minimum(1, t / 0.012) * np.exp(-t / 0.08)
    return bandpass(noise(len(t)), 2200, 9000) * env * vel


def slide_whistle(f0, f1, dur, vel=1.0):
    t = tt(dur)
    k = np.clip(t / dur, 0, 1)
    f = f0 * (f1 / f0) ** (k * k * (3 - 2 * k))
    f *= 1 + 0.015 * np.sin(2 * np.pi * 6.5 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    x = np.sin(ph) + 0.12 * np.sin(2 * ph) + bandpass(noise(len(t)), 800, 5000) * 0.05
    env = np.minimum(1, t / 0.03) * np.clip((dur - t) / 0.06, 0, 1)
    return x * env * vel


def seq(tr, t0, beat, notes, inst, vel=1.0, transpose=0, gate=0.92, wrap=True):
    """Lay a list of (note, beats) into a track; 'R' is a rest. Returns the end time."""
    t = t0
    for n, b in notes:
        if n != "R":
            x = inst(midi(nm(n) + transpose), b * beat * gate, vel)
            (tr.add_wrapped if wrap else tr.add)(t, x)
        t += b * beat
    return t


def stereoless_space(x, wet=0.16, size=1.4):
    """Music gets a little hall so it doesn't sound like it's coming out of a tin can."""
    n = len(x)
    y = reverb(x, decay=size, wet=wet, tone=5000)
    # fold the reverb tail back onto the start so the loop stays seamless
    out = y[:n].copy()
    tail = y[n:]
    k = min(len(tail), n)
    out[:k] += tail[:k]
    return out


# --------------------------------------------------------------------------
# music (longer arrangements with real sections, so the loops don't grate)
# --------------------------------------------------------------------------

G_CHORDS = {
    "G": ("G2", ["G3", "B3", "D4"]), "C": ("C3", ["C4", "E4", "G4"]), "D": ("D2", ["D3", "F#3", "A3"]),
    "Em": ("E2", ["E3", "G3", "B3"]), "Bm": ("B1", ["B2", "D3", "F#3"]), "Am7": ("A1", ["A2", "C3", "E3", "G3"]),
    "D7": ("D2", ["D3", "F#3", "C4"]),
}
PASTURE_A = [
    [("B4", 1), ("D5", 1), ("G5", 1.5), ("F#5", 0.5)], [("E5", 2), ("C5", 1), ("E5", 1)],
    [("D5", 1.5), ("B4", 0.5), ("G4", 1), ("B4", 1)], [("A4", 3), ("R", 1)],
    [("B4", 1), ("E5", 1), ("G5", 1), ("E5", 1)], [("E5", 1.5), ("D5", 0.5), ("C5", 1), ("E5", 1)],
    [("D5", 1), ("A4", 1), ("B4", 1), ("C5", 1)], [("B4", 3), ("R", 1)],
]
PASTURE_B = [
    [("G5", 2), ("E5", 1), ("C5", 1)], [("F#5", 2), ("D5", 1), ("A4", 1)],
    [("B4", 1), ("D5", 1), ("F#5", 1), ("D5", 1)], [("E5", 3), ("B4", 1)],
    [("C5", 1), ("E5", 1), ("G5", 1), ("C6", 1)], [("B5", 1.5), ("A5", 0.5), ("F#5", 2)],
    [("E5", 1), ("G5", 1), ("C5", 1), ("E5", 1)], [("D5", 2), ("F#5", 1), ("A5", 1)],
]


def pasture_theme() -> np.ndarray:
    """~100 s of pastoral: intro, A (harmonica), A' (flute), B (fiddle), A'' (both), outro."""
    bpm = 92
    beat = 60 / bpm
    bar = 4 * beat
    A = ["G", "C", "G", "D", "Em", "C", "D", "G"]
    B = ["C", "D", "Bm", "Em", "C", "D", "Am7", "D7"]
    prog = ["G", "G", "C", "D"] + A + A + B + A + ["G", "G"]
    tr = Track(len(prog) * bar)
    for i, c in enumerate(prog):
        root, tones = G_CHORDS[c]
        tb = i * bar
        tr.add_wrapped(tb, upright_bass(midi(nm(root)), beat * 1.7, 0.85))
        tr.add_wrapped(tb + 2 * beat, upright_bass(midi(nm(root) + 7), beat * 1.7, 0.65))
        pat = [0, 1, 2, 1, 0, 1, 2, 1] if i % 2 == 0 else [0, 2, 1, 2, 0, 2, 1, 2]
        for j, p in enumerate(pat):
            tr.add_wrapped(tb + j * beat / 2, pluck(midi(nm(tones[p % len(tones)])), 1.4, 0.55, bright=0.45),
                           0.3 if j % 2 else 0.36)
        if 20 <= i < 36:
            tr.add_wrapped(tb + beat, brush(), 0.16)
            tr.add_wrapped(tb + 3 * beat, brush(), 0.16)
    t = 4 * bar
    for b in PASTURE_A:
        t = seq(tr, t, beat, b, harmonica, 0.34)
    for b in PASTURE_A:
        t = seq(tr, t, beat, b, flute, 0.3)
    for b in PASTURE_B:
        t = seq(tr, t, beat, b, fiddle, 0.4)
    t2 = t
    for b in PASTURE_A:
        t = seq(tr, t, beat, b, harmonica, 0.3)
    for b in PASTURE_A:
        t2 = seq(tr, t2, beat, b, flute, 0.16, transpose=12)
    seq(tr, t, beat, [("G4", 4), ("R", 4)], harmonica, 0.3)
    return stereoless_space(tr.loop(), wet=0.14, size=1.2)


def stealth_theme() -> np.ndarray:
    """~38 s sneaking music that builds in layers: bass & ticks, pizzicato, clarinet, trumpet stabs."""
    bpm = 100
    beat = 60 / bpm
    bar = 4 * beat
    n_bars = 16
    tr = Track(n_bars * bar)
    ost = [("D2", 1), ("R", 1), ("F2", 1), ("R", 1), ("E2", 1), ("R", 1), ("A1", 1), ("R", 1)]
    for k in range(n_bars // 2):
        seq(tr, k * 2 * bar, beat, ost, tuba, 0.6, gate=0.35)
        seq(tr, k * 2 * bar, beat, ost, upright_bass, 0.5, gate=0.4)
    for i in range(n_bars * 4):
        tr.add_wrapped(i * beat + beat / 2, woodblock(950 if i % 2 == 0 else 720), 0.22)
    harm = [["D4", "F4", "A4"], ["C#4", "E4", "A4"]]
    for bi in range(4, n_bars):
        tones = harm[bi % 2]
        for j in range(8):
            tr.add_wrapped(bi * bar + j * beat / 2, pluck(midi(nm(tones[[0, 1, 2, 1][j % 4]])), 0.35, 0.45,
                                                           bright=0.3, decay=0.99), 0.4)
    mel = [
        [("A3", 0.5), ("R", 0.5), ("A3", 0.5), ("Bb3", 0.5), ("A3", 1), ("R", 1)],
        [("F3", 0.5), ("R", 0.5), ("G3", 0.5), ("G#3", 0.5), ("A3", 2)],
        [("D4", 0.5), ("R", 0.5), ("C#4", 0.5), ("R", 0.5), ("C4", 0.5), ("R", 0.5), ("B3", 0.5), ("Bb3", 0.5)],
        [("A3", 1.5), ("R", 0.5), ("E3", 1), ("R", 1)],
        [("D4", 0.5), ("R", 0.5), ("D4", 0.5), ("Eb4", 0.5), ("D4", 1), ("R", 1)],
        [("Bb3", 0.5), ("R", 0.5), ("C4", 0.5), ("C#4", 0.5), ("D4", 2)],
        [("D4", 0.5), ("E4", 0.5), ("F4", 0.5), ("E4", 0.5), ("D4", 0.5), ("C#4", 0.5), ("D4", 1)],
        [("A3", 2), ("R", 2)],
    ]
    t = 8 * bar
    for b in mel:
        t = seq(tr, t, beat, b, clarinet, 0.5)
    for bi in range(12, n_bars):
        tr.add_wrapped(bi * bar + 3 * beat, muted_trumpet(midi(nm("D5")), beat * 0.45, 0.3))
        tr.add_wrapped(bi * bar + 3.5 * beat, muted_trumpet(midi(nm("C#5")), beat * 0.4, 0.25))
    for bi in range(8, n_bars):
        tr.add_wrapped(bi * bar + beat, brush(), 0.14)
        tr.add_wrapped(bi * bar + 3 * beat, brush(), 0.14)
    return stereoless_space(tr.loop(), wet=0.12, size=0.9)


E_CHORDS = {"Em": "E2", "C": "C2", "D": "D2", "B": "B1", "Am": "A1"}
E_TONES = {"Em": ["E4", "G4", "B4"], "C": ["C4", "E4", "G4"], "D": ["D4", "F#4", "A4"], "B": ["B3", "D#4", "F#4"],
           "Am": ["A3", "C4", "E4"]}


def boss_theme() -> np.ndarray:
    """~46 s of polka-metal: riff, cowbell breakdown, kazoo shred, riff again."""
    bpm = 168
    beat = 60 / bpm
    bar = 4 * beat
    A = ["Em", "Em", "C", "D"] * 2
    B = ["Am", "Am", "Em", "Em", "C", "C", "B", "B"]
    Cc = ["Em", "C", "D", "B"] * 2
    prog = A + B + Cc + A
    tr = Track(len(prog) * bar)
    for i, c in enumerate(prog):
        tb = i * bar
        r = nm(E_CHORDS[c])
        sec = "B" if 8 <= i < 16 else ("C" if 16 <= i < 24 else "A")
        for k in range(4):
            if k % 2 == 0:
                tr.add_wrapped(tb + k * beat, np.tanh(tuba(midi(r + (7 if k == 2 else 0)), beat * 0.45, 1.0) * 4), 0.35)
            else:
                for tn in E_TONES[c]:
                    tr.add_wrapped(tb + k * beat, organ(midi(nm(tn)), beat * 0.35, 0.5), 0.3)
        if sec == "B":
            tr.add_wrapped(tb, kick(0.3, 1.0))
            tr.add_wrapped(tb + 2 * beat, snare(0.25, 0.9))
            for k in range(4):
                tr.add_wrapped(tb + k * beat, bell808(0.3, 0.6))
        else:
            tr.add_wrapped(tb, kick(0.3, 1.0))
            tr.add_wrapped(tb + 1.5 * beat, kick(0.3, 0.6))
            tr.add_wrapped(tb + 2 * beat, kick(0.3, 0.9))
            tr.add_wrapped(tb + beat, snare(0.2, 0.8))
            tr.add_wrapped(tb + 3 * beat, snare(0.2, 0.8))
            step = 0.25 if sec == "C" else 0.5
            for k in range(int(4 / step)):
                tr.add_wrapped(tb + k * step * beat, hat(0.05, 0.22 if k % 2 == 0 else 0.14))
        if i in (0, 8, 16, 24):
            tr.add_wrapped(tb, highpass(noise(int(1.2 * SR)), 5000) * np.exp(-tt(1.2) / 0.35), 0.35)
    riff = [("E5", .5), ("G5", .5), ("B5", .5), ("G5", .5), ("E5", .5), ("F#5", .5), ("G5", 1),
            ("C6", .5), ("B5", .5), ("A5", .5), ("G5", .5), ("F#5", .5), ("G5", .5), ("A5", 1)]
    for rep in (0, 2, 4, 6, 24, 26, 28, 30):
        seq(tr, rep * bar, beat, riff, kazoo, 0.36)
    longs = [("A4", 4), ("C5", 4), ("B4", 4), ("G4", 4), ("E5", 4), ("G5", 4), ("F#5", 8)]
    seq(tr, 8 * bar, beat, longs, muted_trumpet, 0.3)
    seq(tr, 8 * bar, beat, longs, kazoo, 0.18, transpose=-12)
    for i, c in enumerate(Cc):
        tones = E_TONES[c]
        up = [tones[0], tones[1], tones[2], tones[1]] * 4
        seq(tr, (16 + i) * bar, beat, [(n, 0.25) for n in up], kazoo, 0.26, transpose=12 if i % 2 else 0)
    tr.add_wrapped(len(prog) * bar - 2 * beat, slide_whistle(400, 1500, 2 * beat), 0.35)
    return stereoless_space(tr.loop(), wet=0.1, size=0.8)


def title_theme() -> np.ndarray:
    """A tuba-and-kazoo polka with a verse, a chorus and a clarinet bridge (~36 s)."""
    bpm = 132
    beat = 60 / bpm
    bar = 2 * beat
    verse_prog = ["C3", "C3", "G2", "G2", "F2", "C3", "G2", "C3"] * 2
    chorus_prog = ["C3", "C3", "F2", "F2", "G2", "G2", "C3", "C3"] * 2
    bridge_prog = ["F2", "F2", "C3", "C3", "G2", "G2", "C3", "G2"]
    prog = verse_prog + chorus_prog + bridge_prog
    chord = {"C3": ["E4", "G4", "C5"], "G2": ["D4", "G4", "B4"], "F2": ["F4", "A4", "C5"]}
    tr = Track(len(prog) * bar)
    for i, root in enumerate(prog):
        tb = i * bar
        tr.add_wrapped(tb, tuba(midi(nm(root)), beat * 0.6, 0.9))
        tr.add_wrapped(tb + beat, tuba(midi(nm(root) + 7 - 12), beat * 0.6, 0.8))
        for off in (0.5, 1.5):
            for cn in chord[root]:
                tr.add_wrapped(tb + off * beat, strings(midi(nm(cn)), beat * 0.32, 0.12, attack=0.01, release=0.05,
                                                        voices=2))
        tr.add_wrapped(tb, kick(0.25, 0.5))
        tr.add_wrapped(tb + beat, snare(0.2, 0.3))
    verse = [
        ("E5", .5), ("G5", .5), ("G5", .5), ("E5", .5), ("D5", .5), ("F5", .5), ("F5", 1),
        ("D5", .5), ("F5", .5), ("B4", .5), ("D5", .5), ("C5", .5), ("E5", .5), ("E5", 1),
        ("A5", .5), ("A5", .5), ("G5", .5), ("E5", .5), ("F5", .5), ("D5", .5), ("E5", .5), ("C5", .5),
        ("D5", .5), ("E5", .25), ("D5", .25), ("B4", .5), ("G4", .5), ("C5", 1), ("R", 1),
    ]
    t = seq(tr, 0, beat, verse, kazoo, 0.5)
    seq(tr, t, beat, verse, kazoo, 0.5)
    chorus = [
        ("G4", 1), ("E4", .5), ("G4", .5), ("C5", .5), ("B4", .5), ("A4", .5), ("G4", .5),
        ("A4", 1), ("F4", .5), ("A4", .5), ("C5", .5), ("A4", .5), ("F4", 1),
        ("B4", 1), ("G4", .5), ("B4", .5), ("D5", .5), ("C5", .5), ("B4", .5), ("A4", .5),
        ("G4", .5), ("E4", .5), ("C4", .5), ("E4", .5), ("G4", 1.5), ("R", .5),
        ("E5", .5), ("D5", .5), ("C5", .5), ("D5", .5), ("E5", 1), ("C5", 1),
        ("F5", .5), ("E5", .5), ("D5", .5), ("C5", .5), ("A4", 1), ("F4", 1),
        ("G4", .5), ("A4", .5), ("B4", .5), ("C5", .5), ("D5", 1), ("B4", 1),
        ("C5", .5), ("G4", .5), ("E4", .5), ("G4", .5), ("C5", 1.5), ("R", .5),
    ]
    t0 = 16 * bar
    seq(tr, t0, beat, chorus, tuba, 0.55, transpose=-12)
    seq(tr, t0, beat, chorus, kazoo, 0.4)
    bridge = [("A4", 1), ("C5", 1), ("F5", 2), ("E5", 1), ("D5", .5), ("C5", .5), ("G4", 2),
              ("B4", 1), ("D5", 1), ("G5", 1), ("F5", 1), ("E5", .5), ("D5", .5), ("C5", 1), ("D5", 1), ("B4", 1)]
    seq(tr, 32 * bar, beat, bridge, clarinet, 0.7)
    tr.add_wrapped(len(prog) * bar - beat, slide_whistle(500, 1300, beat * 0.9), 0.3)
    return stereoless_space(tr.loop(), wet=0.1, size=0.9)


def night_theme() -> np.ndarray:
    """64 s of soft night: pads, a music box wandering, a far-off flute twice."""
    total = 64.0
    tr = Track(total)
    chords = [["F3", "A3", "C4"], ["D3", "F3", "A3"], ["Bb2", "D3", "F3"], ["C3", "E3", "G3"],
              ["A2", "C3", "E3"], ["D3", "F3", "A3"], ["G2", "Bb2", "F3"], ["C3", "E3", "Bb3"]]
    for i, ch in enumerate(chords):
        for n in ch:
            tr.add_wrapped(i * 8, pad(midi(nm(n)), 8.6, 0.15))
        tr.add_wrapped(i * 8, upright_bass(midi(nm(ch[0]) - 12), 3.0, 0.35))
    r = np.random.default_rng(12)
    scale = ["F5", "G5", "A5", "C6", "D6", "F6", "A5", "C6"]
    for i in range(22):
        t = i * 2.9 + r.uniform(0, 0.8)
        tr.add_wrapped(t, music_box(midi(nm(scale[r.integers(0, len(scale))])), 2.5, 0.28))
    phrase = [("C5", 2), ("A4", 1), ("F4", 1), ("G4", 3), ("R", 1)]
    seq(tr, 16, 0.75, phrase, flute, 0.18)
    seq(tr, 48, 0.75, [("A4", 2), ("C5", 1), ("D5", 1), ("C5", 3), ("R", 1)], flute, 0.18)
    return stereoless_space(tr.loop(), wet=0.22, size=2.2)


# --------------------------------------------------------------------------
# a livelier farm: positional ambience loops and comic stingers
# --------------------------------------------------------------------------

def loop_frogs(dur=12.0):
    tr = Track(dur)
    r = np.random.default_rng(3)
    for frog in range(4):
        base = r.uniform(170, 280)
        t0 = r.uniform(0, dur)
        for call in range(int(dur / r.uniform(2.5, 4.0))):
            tc = t0 + call * r.uniform(2.6, 4.2)
            for p in range(r.integers(2, 4)):
                d = r.uniform(0.12, 0.2)
                t = tt(d)
                f = base * (1 + 0.15 * np.sin(np.pi * t / d))
                ph = 2 * np.pi * np.cumsum(f) / SR
                x = (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.3 * np.sin(3 * ph)) * (np.sin(2 * np.pi * 38 * t) > -0.2)
                x = bandpass(x, 150, 1500) * np.sin(np.pi * t / d)
                tr.add_wrapped(tc + p * (d + 0.05), x, r.uniform(0.3, 0.6))
    return tr.loop()


def loop_chickens(dur=14.0):
    tr = Track(dur)
    r = np.random.default_rng(5)
    for _ in range(9):
        x = lowpass(chicken_cluck(int(r.integers(2, 5))), 3500)
        tr.add_wrapped(r.uniform(0, dur), x, r.uniform(0.3, 0.7))
    return tr.loop()


def loop_windmill(dur=9.0):
    """The rotor turns every 9 s; the bearing complains twice a turn."""
    tr = Track(dur)
    for t0 in (0.4, 4.9):
        cr = sfx_door_creak(1.3)
        tr.add_wrapped(t0, lowpass(cr, 2500), 0.6)
    t = tt(dur)
    rattle = np.zeros_like(t)
    for k in range(18):
        i = int((k * dur / 18) * SR)
        m = int(0.02 * SR)
        rattle[i:i + m] += noise(m) * np.exp(-np.arange(m) / (0.004 * SR))
    tr.add_wrapped(0, bandpass(rattle, 1500, 5000), 0.2)
    tr.add_wrapped(0, fft_filter_periodic(noise(len(t)), lambda f: 1 / (1 + (f / 300) ** 2) * (f > 30)), 0.12)
    return tr.loop()


def loop_flies(dur=8.0):
    tr = Track(dur)
    r = np.random.default_rng(9)
    for _ in range(5):
        d = r.uniform(0.8, 2.0)
        t = tt(d)
        f = r.uniform(180, 240) * (1 + 0.08 * lowpass(noise(len(t)), 6) * 5)
        ph = 2 * np.pi * np.cumsum(f) / SR
        x = sum(np.sin(k * ph) / k for k in range(1, 12))
        x = bandpass(x, 180, 2500) * np.sin(np.pi * t / d) ** 2
        tr.add_wrapped(r.uniform(0, dur), x, r.uniform(0.3, 0.6))
    return tr.loop()


def loop_owl(dur=18.0):
    tr = Track(dur)
    for t0, pat in ((3.0, (0.35, 0.35, 0.9)), (11.5, (0.3, 0.8))):
        tc = t0
        for d in pat:
            t = tt(d)
            f = 390 * (1 - 0.06 * t / d)
            x = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.15 * np.sin(4 * np.pi * np.cumsum(f) / SR)
            x *= np.sin(np.pi * t / d) ** 1.5
            tr.add_wrapped(tc, x, 0.5)
            tc += d + 0.25
    return reverb(tr.loop(), 1.8, 0.3)[: int(dur * SR)]


def loop_pigeons(dur=10.0):
    tr = Track(dur)
    r = np.random.default_rng(21)
    for _ in range(4):
        tc = r.uniform(0, dur)
        for p, d in enumerate((0.25, 0.5)):
            t = tt(d)
            f = r.uniform(300, 360) * (1 - 0.1 * t / d)
            x = np.sin(2 * np.pi * np.cumsum(f) / SR) * (0.75 + 0.25 * np.sin(2 * np.pi * 22 * t))
            x *= np.sin(np.pi * t / d)
            tr.add_wrapped(tc + p * 0.3, lowpass(x, 1500), 0.4)
    return tr.loop()


def loop_clock(dur=2.0):
    tr = Track(dur)
    tr.add_wrapped(0.0, woodblock(2600, 1.0) * 0.5)
    tr.add_wrapped(1.0, woodblock(2100, 1.0) * 0.45)
    return tr.loop()


def loop_fridge(dur=4.0):
    t = tt(dur)
    x = 0.6 * np.sin(2 * np.pi * 60 * t) + 0.3 * np.sin(2 * np.pi * 120 * t) + 0.1 * np.sin(2 * np.pi * 180 * t)
    x *= 1 + 0.05 * np.sin(2 * np.pi * 0.5 * t)
    x += fft_filter_periodic(noise(len(t)), lambda f: (f > 80) * (f < 900) * 1.0) * 0.05
    return x


def sfx_moodal():
    """Achievement jingle: two cowbell dings and a proud little kazoo run."""
    tr = Track(1.8)
    tr.add(0.0, bell808(0.5, 0.9))
    tr.add(0.12, bell808(0.6, 0.9, f1=660, f2=950))
    for i, (n, d) in enumerate((("G5", 0.11), ("C6", 0.11), ("E6", 0.11), ("G6", 0.55))):
        tr.add(0.26 + i * 0.12, kazoo(midi(nm(n)), d, 0.65))
    return tr.out(0.3)


def sfx_bird_flutter():
    """A small flock taking off: a burst of wingbeats that thins out, and a couple of alarm chirps."""
    tr = Track(1.2)
    r = np.random.default_rng(31)
    for b in range(5):
        t0 = r.uniform(0, 0.12)
        rate = r.uniform(13, 18)
        for k in range(int(0.8 * rate)):
            m = int(0.018 * SR)
            x = bandpass(noise(m), 400, 3000) * np.exp(-np.arange(m) / (0.005 * SR))
            tr.add(t0 + k / rate, x, 0.6 * (1 - k / (0.8 * rate)))
    for c in range(2):
        d = 0.08
        t = tt(d)
        f = r.uniform(3000, 4200) * (1 + 0.2 * t / d)
        tr.add(0.05 + c * 0.14, np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * t / d), 0.3)
    return tr.out(0.2)


def sfx_frog_chorus():
    x = loop_frogs(3.0)
    n = len(x)
    return x * np.clip(np.linspace(3.0, 0.0, n), 0, 1) * np.minimum(1, np.arange(n) / (0.05 * SR))


def sfx_owl_hoot():
    tr = Track(2.2)
    tc = 0.0
    for d in (0.3, 0.3, 0.85):
        t = tt(d)
        f = 385 * (1 - 0.06 * t / d)
        ph = 2 * np.pi * np.cumsum(f) / SR
        tr.add(tc, (np.sin(ph) + 0.15 * np.sin(2 * ph)) * np.sin(np.pi * t / d) ** 1.5, 0.6)
        tc += d + 0.22
    return reverb(tr.out(0.2), 1.6, 0.28)


def sfx_bonk():
    return mix(woodblock(560, 1.0), (sfx_thump(0.35, 70), 0.5))


# --------------------------------------------------------------------------
# mastering: every sound gets a loudness that fits its job, not the same peak
# --------------------------------------------------------------------------

LOUDNESS = {  # dBFS: loudest 400 ms for one-shots, average for loops and music
    "music": -17.0, "loop": -19.0, "voice": -12.0, "foley": -17.0, "ui": -15.0, "big": -10.0, "sfx": -13.0,
}
UI_SOUNDS = {"blip", "blip_hi", "blip_lo", "type", "ding", "question", "clover", "fanfare", "paper", "moodal"}
BIG_SOUNDS = {"shotgun", "gate_smash", "crash", "alert", "dun_dun", "sad_trombone"}


def sound_category(name):
    if name.startswith(("music_", "moozart_")) or name == "final_note":
        return "music"
    if name.startswith("loop_"):
        return "loop"
    if name.startswith(("moo_", "farmer_", "cluck")) or name in ("rooster_crow", "squawk"):
        return "voice"
    if name.startswith(("step_", "cowbell_")):
        return "foley"
    if name in UI_SOUNDS:
        return "ui"
    if name in BIG_SOUNDS:
        return "big"
    return "sfx"


def loudness_db(x, average):
    x = np.asarray(x, dtype=np.float64)
    if average or len(x) < int(0.4 * SR):
        return 10 * np.log10(np.mean(x ** 2) + 1e-12)
    win = int(0.4 * SR)
    c = np.concatenate([[0.0], np.cumsum(x ** 2)])
    return 10 * np.log10(np.max((c[win:] - c[:-win]) / win) + 1e-12)


def master(name, x):
    cat = sound_category(name)
    x = np.asarray(x, dtype=np.float64)
    looped = cat in ("loop",) or name.startswith("music_") and name not in ("music_ending", "music_sad")
    if looped:  # keep loops seamless: filter around the circle
        x = fft_filter_periodic(x - np.mean(x), lambda f: (f > 18).astype(float))
    else:
        x = highpass(x, 18)
    x = x * 10 ** ((LOUDNESS[cat] - loudness_db(x, cat in ("music", "loop"))) / 20)
    # soft ceiling at -1 dBFS
    a = np.abs(x)
    knee = 0.7
    y = np.where(a > knee, np.sign(x) * (knee + 0.19 * np.tanh((a - knee) / 0.19)), x)
    return y


def sad_theme() -> np.ndarray:
    """Archimoodes walks to the truck: the road-out tune from the ending, slowed and set in B minor, on a lone
    piano, then with a cello under it, then the strings take the tune. The ending plays it again in D major."""
    bpm = 66
    beat = 60 / bpm
    bar = 4 * beat
    chords = {"Bm": ("B1", ["B2", "D3", "F#3"]), "A": ("A1", ["A2", "C#3", "E3"]), "G": ("G1", ["G2", "B2", "D3"]),
              "D": ("D2", ["D3", "F#3", "A3"]), "Em": ("E2", ["E3", "G3", "B3"]), "F#m": ("F#1", ["F#2", "A2", "C#3"])}
    prog = ["Bm", "A", "G", "D", "Bm", "A", "Em", "F#m"]
    passes = 3
    total = (passes * 8 + 1) * bar
    tr = Track(total + 2)
    for pi in range(passes):
        for bi, c in enumerate(prog):
            root, tones = chords[c]
            tb = (pi * 8 + bi) * bar
            # a slow broken chord in the piano's left hand
            for j, tn in enumerate(tones):
                tr.add(tb + j * beat, piano(midi(nm(tn) + 12), bar - j * beat + 0.5, 0.22))
            tr.add(tb, strings(midi(nm(root) + 12), bar * 1.02, 0.12 + 0.06 * pi, attack=0.8, release=1.0))
            if pi >= 1:
                # a cello holding the root, then (third time round) the full strings
                tr.add(tb, strings(midi(nm(root) + 12), bar * 1.02, 0.16, attack=0.5, release=0.8, voices=2))
            if pi == 2:
                for tn in tones:
                    tr.add(tb, strings(midi(nm(tn) + 24), bar * 1.02, 0.08, attack=0.9, release=1.0))
    melody = ROAD_A[:7] + [[("A4", 2), ("C#5", 2)]]
    t = 0.0
    for b in melody:
        t = seq(tr, t, beat, b, piano, 0.38, wrap=False)
    for b in melody:
        t = seq(tr, t, beat, b, piano, 0.34, wrap=False)
    t2 = 8 * bar
    for b in melody:
        t2 = seq(tr, t2, beat, b, strings, 0.12, transpose=-12, wrap=False)
    for b in melody:
        t = seq(tr, t, beat, b, strings, 0.2, wrap=False)
    # and home, to B minor
    tb = passes * 8 * bar
    for tn in ("B2", "D3", "F#3", "B3"):
        tr.add(tb, piano(midi(nm(tn) + 12), bar * 1.5, 0.28))
        tr.add(tb, strings(midi(nm(tn) + 12), bar * 1.4, 0.1, attack=0.6, release=1.6))
    tr.add(tb, piano(midi(nm("B4")), bar * 1.5, 0.3))
    x = tr.out(tail=3.0)
    return reverb(x, decay=2.0, wet=0.2, tone=4500)[: len(x)]


# --------------------------------------------------------------------------
# catalog
# --------------------------------------------------------------------------

def _voice_catalog():
    items = {}
    for name, v in VOICES.items():
        for kind in ("short", "medium", "long", "question", "exclaim", "sad"):
            for var in range(2):
                items[f"moo_{name}_{kind}_{var}"] = (lambda v=v, kind=kind: moo(kind=kind, **v))
    for i in range(10):
        def herd(i=i):
            v = dict(VOICES["player"])
            v["f0"] = float(_rng.uniform(92, 172))
            v["rough"] = float(_rng.uniform(0.0, 0.35))
            v["fs"] = float(_rng.uniform(0.9, 1.12))
            return moo(kind=["short", "medium", "long", "question", "exclaim"][i % 5], **v)
        items[f"moo_herd_{i}"] = herd
    # farmer
    fv = {
        "short": [(0.18, 1.0), (0.26, 0.85)],
        "medium": [(0.16, 1.0), (0.14, 1.1), (0.2, 0.95), (0.28, 0.85)],
        "long": [(0.15, 1.0), (0.13, 1.1), (0.18, 1.0), (0.12, 1.15), (0.2, 0.95), (0.15, 1.0), (0.3, 0.8)],
        "question": [(0.16, 1.0), (0.14, 0.95), (0.35, 1.35)],
        "angry": [(0.12, 1.3), (0.12, 1.4), (0.14, 1.35), (0.3, 1.2)],
        "surprise": [(0.12, 1.2), (0.45, 1.7)],
        "ow": [(0.8, 1.2)],
        "laugh": [(0.1, 1.2), (0.1, 1.25), (0.1, 1.2), (0.1, 1.25)],
        "sleepy": [(0.4, 0.8), (0.5, 0.7)],
    }
    for kind, syl in fv.items():
        for var in range(2):
            items[f"farmer_{kind}_{var}"] = (lambda syl=syl, kind=kind: trombone_voice(
                [(d * _rng.uniform(0.9, 1.1), p * _rng.uniform(0.95, 1.05)) for d, p in syl],
                base=118 if kind != "angry" else 135, speed=1.0))
    return items


def catalog():
    c = {}
    c.update(_voice_catalog())
    for i in range(4):
        c[f"step_grass_{i}"] = lambda: sfx_step("grass")
        c[f"step_wood_{i}"] = lambda: sfx_step("wood")
        c[f"step_dirt_{i}"] = lambda: sfx_step("dirt")
        c[f"step_water_{i}"] = lambda: sfx_step("water")
        c[f"step_hay_{i}"] = lambda: sfx_step("hay")
        c[f"cowbell_{i}"] = lambda: sfx_cowbell_jingle()
    c.update({
        "whoosh": sfx_whoosh,
        "thump": sfx_thump,
        "headbutt": lambda: mix(sfx_thump(0.45, 50), (sfx_rock_land(), 0.3)),
        "wood_crack": sfx_wood_crack,
        "rock_land": sfx_rock_land,
        "metal_clang": lambda: metal_hit(1.2, 380),
        "crash": sfx_crash,
        "fanfare": sfx_kazoo_fanfare,
        "sad_trombone": sfx_sad_trombone,
        "alert": sfx_alert,
        "question": sfx_question,
        "ding": sfx_ding,
        "door_creak": sfx_door_creak,
        "door_close": sfx_door_close,
        "chain": sfx_chain_rattle,
        "zap": sfx_zap,
        "splash": sfx_splash,
        "flush": sfx_flush,
        "paper": sfx_paper,
        "munch": sfx_munch,
        "clover": sfx_clover,
        "blip": sfx_ui_blip,
        "blip_hi": lambda: sfx_ui_blip(1320),
        "blip_lo": lambda: sfx_ui_blip(520),
        "type": sfx_type_blip,
        "shotgun": sfx_shotgun,
        "punch": sfx_punch,
        "boing": sfx_boing,
        "gate_smash": sfx_gate_smash,
        "tractor_start": sfx_tractor_start,
        "rooster_crow": rooster_crow,
        "cluck_0": lambda: chicken_cluck(3),
        "cluck_1": lambda: chicken_cluck(4),
        "cluck_2": lambda: chicken_cluck(2),
        "squawk": squawk,
        "dun_dun": dun_dun_dunnn,
        "bell_single": lambda: bell808(0.8, 1.0),
        "cowbell_drop": lambda: mix(bell808(1.2, 1.0), (sfx_rock_land(), 0.5)),
        # loops
        "loop_tractor": loop_tractor,
        "loop_truck": loop_truck,
        "loop_generator": loop_generator,
        "loop_fence": loop_fence_hum,
        "loop_grinder": loop_grinder,
        "loop_wind": loop_wind,
        "loop_rain": loop_rain,
        "loop_birds": loop_birds,
        "loop_crickets": loop_crickets,
        "loop_snore": loop_snore,
        "loop_herd": loop_hum_crowd,
        "loop_radio": radio_loop,
        "radio_static": radio_static,
        "loop_frogs": loop_frogs,
        "loop_chickens": loop_chickens,
        "loop_windmill": loop_windmill,
        "loop_flies": loop_flies,
        "loop_owl": loop_owl,
        "loop_pigeons": loop_pigeons,
        "loop_clock": loop_clock,
        "loop_fridge": loop_fridge,
        "slide_down": lambda: slide_whistle(1500, 330, 0.75),
        "slide_up": lambda: slide_whistle(330, 1500, 0.55),
        "bonk": sfx_bonk,
        "moodal": sfx_moodal,
        "bird_flutter": sfx_bird_flutter,
        "frog_chorus": sfx_frog_chorus,
        "owl_hoot": sfx_owl_hoot,
        # music
        "music_title": title_theme,
        "music_pasture": pasture_theme,
        "music_stealth": stealth_theme,
        "music_night": night_theme,
        "music_boss": boss_theme,
        "music_sad": sad_theme,
        "music_ending": ending_theme,
        "moo_herd_argue": herd_argue,
        "music_box_theme": lambda: music_box_theme(1.0),
    })
    return c


def radio_static() -> np.ndarray:
    """A radio with no aerial: hiss, a whine, and crackles."""
    n = int(1.8 * SR)
    t = np.arange(n) / SR
    x = bandpass(noise(n), 400, 5000) * 0.45
    x += np.sin(2 * np.pi * (2400 + 300 * np.sin(2 * np.pi * 0.7 * t)) * t) * 0.04
    rng = np.random.default_rng(7)
    for i in rng.integers(0, n - 400, 40):
        x[i:i + 300] += rng.uniform(-1, 1) * np.exp(-np.arange(300) / 40)
    return fade_edges(x, 0.01, 0.2)


def radio_loop() -> np.ndarray:
    """Tinny country tune from Chuck's radio."""
    bpm = 120
    beat = 60 / bpm
    prog = [("G2", ["G3", "B3", "D4"]), ("G2", ["G3", "B3", "D4"]), ("C3", ["C4", "E4", "G4"]), ("G2", ["G3", "B3", "D4"]),
            ("D3", ["D4", "F#4", "A4"]), ("C3", ["C4", "E4", "G4"]), ("G2", ["G3", "B3", "D4"]), ("D3", ["D4", "F#4", "A4"])]
    total = len(prog) * 4 * beat
    tr = Track(total)
    for i, (bass, tones) in enumerate(prog):
        tb = i * 4 * beat
        b = nm(bass)
        for k, off in enumerate([0, 7, 0, 7]):
            tr.add_wrapped(tb + k * beat, pluck(midi(b + (off - 12 if off else 0)), 0.6, 0.9, bright=0.2), 0.6)
        for k in range(8):
            tr.add_wrapped(tb + k * beat / 2, pluck(midi(nm(tones[k % 3]) + 12), 0.4, 0.5, bright=0.9, decay=0.99), 0.3)
        tr.add_wrapped(tb + beat, snare(0.12, 0.25))
        tr.add_wrapped(tb + 3 * beat, snare(0.12, 0.25))
    lead = ["B4", "D5", "E5", "D5", "B4", "A4", "G4", "R", "E5", "G5", "E5", "D5", "B4", "D5", "A4", "R"]
    for i, n in enumerate(lead * 2):
        if n != "R":
            tr.add_wrapped(i * beat, pluck(midi(nm(n)), 0.5, 0.7, bright=0.8, decay=0.993), 0.45)
    x = tr.loop()
    x = fft_filter_periodic(x, lambda f: ((f > 350) & (f < 3200)).astype(float))
    return np.tanh(x * 2.5)


def generate_all(out_dir: str, progress=None):
    os.makedirs(out_dir, exist_ok=True)
    ver_path = os.path.join(out_dir, ".version")
    if os.path.exists(ver_path):
        with open(ver_path) as f:
            if f.read().strip() == AUDIO_VERSION:
                return False
    cat = catalog()
    names = list(cat)
    for i, name in enumerate(names):
        path = os.path.join(out_dir, name + ".wav")
        x = cat[name]()
        write_wav(path, x, name=name)
        if progress:
            progress(i + 1, len(names), name)
    with open(ver_path, "w") as f:
        f.write(AUDIO_VERSION)
    return True


if __name__ == "__main__":
    import sys
    import time
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from breakowt.engine.assets import AUDIO_DIR
    out = str(AUDIO_DIR)
    only = sys.argv[1:]
    if only:
        os.makedirs(out, exist_ok=True)
        cat = catalog()
        for name in only:
            t0 = time.time()
            write_wav(os.path.join(out, name + ".wav"), cat[name](), name=name)
            print(name, f"{time.time() - t0:.2f}s")
    else:
        t0 = time.time()
        vp = os.path.join(out, ".version")
        if os.path.exists(vp):
            os.remove(vp)
        generate_all(out, lambda i, n, name: print(f"[{i}/{n}] {name}"))
        print(f"done in {time.time() - t0:.1f}s")
