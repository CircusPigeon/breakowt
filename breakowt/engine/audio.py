"""Audio playback on top of Panda3D's audio managers.

- one-shot sounds (optionally positional: distance attenuation + stereo pan)
- named loops (ambience, engines) with fades
- crossfading music
"""
from __future__ import annotations

import math
import random

from panda3d.core import AudioSound, Filename
from ursina import application

from .assets import AUDIO_DIR

PLAYING = AudioSound.PLAYING


class _Voice:
    __slots__ = ("snd", "base_vol", "pos", "range", "group", "fade", "target", "stop_after", "follow", "name")

    def __init__(self, snd, base_vol, pos, rng, group):
        self.snd = snd
        self.base_vol = base_vol
        self.pos = pos
        self.range = rng
        self.group = group
        self.fade = 0.0
        self.target = None
        self.stop_after = False
        self.follow = None
        self.name = None


class AudioManager:
    def __init__(self):
        base = application.base
        self.sfx_mgr = base.sfxManagerList[0] if base.sfxManagerList else None
        self.music_mgr = base.musicManager
        self.volumes = {"master": 0.9, "music": 0.6, "sfx": 0.9, "voice": 1.0, "ambient": 0.7}
        self.oneshots: list[_Voice] = []
        self.loops: dict[str, _Voice] = {}
        self.music: _Voice | None = None
        self.music_name = None
        self.old_music: list[_Voice] = []
        self.listener = (0.0, 0.0, 0.0)
        self.listener_yaw = 0.0
        self._cache_ok: dict[str, bool] = {}
        self.muffle = 1.0  # global duck (e.g. during pause)
        self.music_duck = 1.0
        self.talk_duck = 1.0          # eased toward talk_duck_target (dips music under dialogue)
        self.talk_duck_target = 1.0

    # ------------------------------------------------------------------
    def _load(self, name, music=False):
        p = AUDIO_DIR / f"{name}.wav"
        if name not in self._cache_ok:
            self._cache_ok[name] = p.exists()
        if not self._cache_ok[name]:
            return None
        mgr = self.music_mgr if music else self.sfx_mgr
        try:
            return mgr.getSound(Filename.fromOsSpecific(str(p)))
        except Exception:
            return None

    def _gvol(self, group):
        return self.volumes["master"] * self.volumes.get(group, 1.0) * self.muffle

    def _spatial(self, pos, rng):
        if pos is None:
            return 1.0, 0.0
        lx, ly, lz = self.listener
        dx, dy, dz = pos[0] - lx, pos[1] - ly, pos[2] - lz
        d = math.sqrt(dx * dx + dy * dy + dz * dz)
        att = max(0.0, 1.0 - d / rng) ** 1.6 if rng > 0 else 1.0
        if d < 0.5:
            return att, 0.0
        yaw = math.radians(self.listener_yaw)
        # right vector for yaw: (cos, -sin)
        rx, rz = math.cos(yaw), -math.sin(yaw)
        pan = (dx * rx + dz * rz) / max(d, 1e-5)
        return att, max(-1.0, min(1.0, pan)) * 0.8

    # ------------------------------------------------------------------
    def play(self, name, vol=1.0, pitch=1.0, pos=None, rng=40.0, group="sfx", follow=None):
        snd = self._load(name)
        if snd is None:
            return None
        v = _Voice(snd, vol, pos, rng, group)
        v.follow = follow
        att, pan = self._spatial(pos, rng)
        if pos is not None and att <= 0.001:
            return None
        snd.setVolume(vol * att * self._gvol(group))
        snd.setBalance(pan)
        snd.setPlayRate(pitch)
        snd.play()
        self.oneshots.append(v)
        if len(self.oneshots) > 40:
            old = self.oneshots.pop(0)
            old.snd.stop()
        return v

    def play_random(self, prefix, n, **kw):
        return self.play(f"{prefix}_{random.randrange(n)}", **kw)

    def loop(self, key, name, vol=1.0, pos=None, rng=40.0, group="ambient", fade=1.0, pitch=1.0):
        cur = self.loops.get(key)
        if cur is not None and cur.name == name:
            cur.target = vol
            cur.range = rng
            if pos is not None:
                cur.pos = pos
            cur.stop_after = False
            cur.fade = fade
            cur.snd.setPlayRate(pitch)
            return cur
        if cur is not None:
            self.stop_loop(key, fade)
        snd = self._load(name)
        if snd is None:
            return None
        snd.setLoop(True)
        v = _Voice(snd, 0.0 if fade > 0 else vol, pos, rng, group)
        v.name = name
        v.target = vol
        v.fade = fade
        snd.setVolume(0.0)
        snd.setPlayRate(pitch)
        snd.play()
        self.loops[key] = v
        return v

    def loop_playing(self, key):
        return key in self.loops

    def set_loop(self, key, vol=None, pos=None, pitch=None):
        v = self.loops.get(key)
        if v is None:
            return
        if vol is not None:
            v.target = vol
        if pos is not None:
            v.pos = pos
        if pitch is not None:
            v.snd.setPlayRate(pitch)

    def stop_loop(self, key, fade=0.5):
        v = self.loops.pop(key, None)
        if v is None:
            return
        if fade <= 0:
            v.snd.stop()
        else:
            v.target = 0.0
            v.fade = fade
            v.stop_after = True
            self.old_music.append(v)

    def stop_all_loops(self, fade=0.5):
        for k in list(self.loops):
            self.stop_loop(k, fade)

    def music_play(self, name, vol=1.0, fade=1.5, loop=True):
        if self.music_name == name and self.music is not None:
            self.music.target = vol
            return
        if self.music is not None:
            self.music.target = 0.0
            self.music.fade = fade
            self.music.stop_after = True
            self.old_music.append(self.music)
            self.music = None
        self.music_name = name
        if name is None:
            return
        snd = self._load(name, music=True)
        if snd is None:
            return
        snd.setLoop(loop)
        v = _Voice(snd, 0.0 if fade > 0 else vol, None, 0, "music")
        v.target = vol
        v.fade = fade
        snd.setVolume(0.0 if fade > 0 else vol * self._gvol("music"))
        snd.play()
        self.music = v

    def music_stop(self, fade=1.5):
        self.music_play(None, fade=fade)

    # ------------------------------------------------------------------
    def update(self, dt, listener=None, yaw=None):
        if listener is not None:
            self.listener = listener
        if yaw is not None:
            self.listener_yaw = yaw
        alive = []
        for v in self.oneshots:
            if v.snd.status() != PLAYING:
                continue
            if v.pos is not None or v.follow is not None:
                if v.follow is not None:
                    try:
                        p = v.follow()
                        v.pos = p
                    except Exception:
                        v.follow = None
                att, pan = self._spatial(v.pos, v.range)
                v.snd.setVolume(v.base_vol * att * self._gvol(v.group))
                v.snd.setBalance(pan)
            else:
                v.snd.setVolume(v.base_vol * self._gvol(v.group))
            alive.append(v)
        self.oneshots = alive

        for key, v in list(self.loops.items()):
            self._fade_step(v, dt)
            att, pan = self._spatial(v.pos, v.range)
            v.snd.setVolume(v.base_vol * att * self._gvol(v.group))
            v.snd.setBalance(pan)
        self.talk_duck += (self.talk_duck_target - self.talk_duck) * min(1.0, dt * 3.0)
        keep = []
        for v in self.old_music:
            self._fade_step(v, dt)
            g = self._gvol(v.group) * (self.music_duck * self.talk_duck if v.group == "music" else 1.0)
            att, pan = self._spatial(v.pos, v.range)
            v.snd.setVolume(v.base_vol * att * g)
            if v.base_vol <= 0.001 and v.stop_after:
                v.snd.stop()
            else:
                keep.append(v)
        self.old_music = keep
        if self.music is not None:
            self._fade_step(self.music, dt)
            self.music.snd.setVolume(self.music.base_vol * self._gvol("music") * self.music_duck * self.talk_duck)

    @staticmethod
    def _fade_step(v, dt):
        if v.target is None:
            return
        if v.fade <= 0:
            v.base_vol = v.target
        else:
            step = dt / v.fade
            if v.base_vol < v.target:
                v.base_vol = min(v.target, v.base_vol + step)
            else:
                v.base_vol = max(v.target, v.base_vol - step)

    def stop_everything(self):
        for v in self.oneshots:
            v.snd.stop()
        self.oneshots = []
        for v in self.loops.values():
            v.snd.stop()
        self.loops = {}
        for v in self.old_music:
            v.snd.stop()
        self.old_music = []
        if self.music:
            self.music.snd.stop()
        self.music = None
        self.music_name = None
