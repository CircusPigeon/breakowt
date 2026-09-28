"""Character and prop models, built from primitives with a shared atlas."""
from __future__ import annotations

import math
import random

from ursina import Entity, scene

from .engine.assets import tex
from .engine.meshbuilder import MeshBuilder
from .engine.shading import FARM_SHADER, no_shadow
from .texgen import ATLAS, ATLAS_H, ATLAS_W


def uvr(key, inset=0.0):
    x0, y0, x1, y1 = ATLAS[key]
    ix = (x1 - x0) * inset
    iy = (y1 - y0) * inset
    return ((x0 + ix) / ATLAS_W, 1 - (y1 - iy) / ATLAS_H, (x1 - ix) / ATLAS_W, 1 - (y0 + iy) / ATLAS_H)


WHITE = uvr("white", 0.35)

PINK = (0.96, 0.66, 0.70, 1)
HOOF = (0.16, 0.13, 0.11, 1)
HORN = (0.93, 0.89, 0.76, 1)
EYEW = (1, 1, 1, 1)
PUPIL = (0.04, 0.04, 0.05, 1)
NOSTRIL = (0.38, 0.14, 0.18, 1)
SKIN = (0.95, 0.76, 0.64, 1)
MUSTACHE = (0.45, 0.28, 0.14, 1)
BOOT = (0.32, 0.21, 0.13, 1)
BRASS = (0.85, 0.7, 0.25, 1)
DARK = (0.12, 0.12, 0.13, 1)
RED = (0.75, 0.12, 0.1, 1)
METAL = (0.62, 0.64, 0.68, 1)
WOOD = (0.6, 0.43, 0.26, 1)


def blob_shadow(parent, w, d, alpha=0.5, y=0.045):
    """A soft dark ellipse on the ground under a character."""
    mb = MeshBuilder().box((0, y, 0), (w, 0.001, d), uv_rect=(0, 0, 1, 1), faces=[4])
    e = Entity(parent=parent, model=mb.build(), texture=tex("blob_shadow"), shader=FARM_SHADER,
               color=(0, 0, 0, alpha))
    e.set_shader_input("u_unlit", 1.0)
    from panda3d.core import TransparencyAttrib
    e.setTransparency(TransparencyAttrib.MAlpha)
    e.setDepthWrite(False)
    e.setBin("transparent", 0)
    no_shadow(e)
    return e


def part(parent, mb: MeshBuilder, texture="atlas", **kw):
    m = mb.build(solid_rect=WHITE if texture == "atlas" else None)
    if m is None:
        return Entity(parent=parent, **kw)
    return Entity(parent=parent, model=m, texture=tex(texture), shader=FARM_SHADER, **kw)


# --------------------------------------------------------------------------
# cows
# --------------------------------------------------------------------------

class CowModel(Entity):
    def __init__(self, hide="hide_bw", bull=False, horns=False, tag="tag_blank", acc=(), scale_=1.0,
                 bell=False, pupils=None, parent=None, **kw):
        super().__init__(parent=parent or scene, **kw)
        self.hide_key = hide
        self.bull = bull
        self.horns = horns or bull
        self.tag = tag
        self.acc = set(acc)
        self.bell = bell
        self.scale_ = scale_
        self.pupil_off = pupils or [(random.uniform(-0.03, 0.03), random.uniform(-0.03, 0.02)) for _ in range(2)]
        self.phase = random.uniform(0, 6.28)
        self.t = random.uniform(0, 10)
        self.graze = 0.0
        self.graze_target = 0.0
        self.head_yaw = 0.0
        self.head_yaw_target = 0.0
        self.head_pitch_extra = 0.0
        self.talk_t = 0.0
        self.lying = 0.0
        self.lying_target = 0.0
        self._leg_rx = [0.0, 0.0, 0.0, 0.0]
        self._body_y = 0.0
        self.rig = Entity(parent=self, scale=scale_)
        self.shadow = blob_shadow(self, 1.5 * scale_ * (1.1 if bull else 1.0), 2.5 * scale_ * (1.1 if bull else 1.0), 0.6)
        self.build()

    def build(self):
        for c in list(self.rig.children):
            c.parent = None
            c.remove_node()
        H = uvr(self.hide_key, 0.02)
        sz = 1.1 if self.bull else 1.0
        self.body = Entity(parent=self.rig)
        mb = MeshBuilder()
        mb.box((0, 1.06, 0), (0.92 * sz, 0.8 * sz, 1.68 * sz), uv_rect=H)
        mb.box((0, 1.14, -0.72 * sz), (0.88 * sz, 0.72 * sz, 0.36), uv_rect=H)
        mb.box((0, 0.72, 0.05), (0.8 * sz, 0.22, 1.3 * sz), uv_rect=H)
        mb.box((0, 1.27, 0.86 * sz), (0.54 * sz, 0.58 * sz, 0.42), uv_rect=H)
        if not self.bull:
            mb.box((0, 0.6, -0.35), (0.4, 0.2, 0.38), color=PINK, uv_rect=WHITE)
            for tx in (-0.1, 0.1):
                for tz in (-0.46, -0.24):
                    mb.box((tx, 0.46, tz), (0.06, 0.12, 0.06), color=PINK, uv_rect=WHITE)
        if self.bell:
            mb.box((0, 1.0, 1.12 * sz), (0.18, 0.2, 0.12), color=BRASS, uv_rect=WHITE)
            mb.box((0, 1.16, 1.06 * sz), (0.5, 0.05, 0.05), color=(0.35, 0.22, 0.12, 1), uv_rect=WHITE)
        if "shawl" in self.acc:
            mb.box((0, 1.4, 0.72), (1.0, 0.18, 0.7), color=(0.55, 0.3, 0.6, 1), uv_rect=WHITE)
            for i in range(5):
                mb.box((-0.4 + i * 0.2, 1.22, 1.0), (0.05, 0.3, 0.05), color=(0.6, 0.35, 0.65, 1), uv_rect=WHITE)
        if "bowtie" in self.acc:
            mb.box((-0.1, 1.08, 1.09), (0.16, 0.14, 0.06), color=RED, uv_rect=WHITE, rot=(0, 0, 20))
            mb.box((0.1, 1.08, 1.09), (0.16, 0.14, 0.06), color=RED, uv_rect=WHITE, rot=(0, 0, -20))
            mb.box((0, 1.08, 1.11), (0.07, 0.08, 0.06), color=(0.5, 0.05, 0.05, 1), uv_rect=WHITE)
        if "cape" in self.acc:
            mb.box((0, 1.3, -0.1), (1.0, 0.1, 1.2), color=(0.55, 0.1, 0.15, 1), uv_rect=WHITE)
            mb.box((0.5, 1.0, -0.1), (0.05, 0.6, 1.2), color=(0.55, 0.1, 0.15, 1), uv_rect=WHITE)
            mb.box((-0.5, 1.0, -0.1), (0.05, 0.6, 1.2), color=(0.55, 0.1, 0.15, 1), uv_rect=WHITE)
        part(self.body, mb)

        self.head = Entity(parent=self.body, position=(0, 1.4, 1.02 * sz))
        self.build_head()

        self.legs = []
        leg_uv = H
        for lx, lz in [(-0.3, 0.62), (0.3, 0.62), (-0.3, -0.62), (0.3, -0.62)]:
            pv = Entity(parent=self.body, position=(lx * sz, 0.78, lz * sz))
            lm = MeshBuilder()
            lm.box((0, -0.36, 0), (0.2, 0.72, 0.22), uv_rect=leg_uv)
            lm.box((0, -0.72, 0.01), (0.23, 0.12, 0.26), color=HOOF, uv_rect=WHITE)
            part(pv, lm)
            self.legs.append(pv)

        self.tail = Entity(parent=self.body, position=(0, 1.36, -0.9 * sz))
        tm = MeshBuilder()
        tm.box((0, -0.36, -0.03), (0.06, 0.72, 0.06), uv_rect=H)
        tm.box((0, -0.76, -0.03), (0.13, 0.18, 0.13), color=(0.16, 0.13, 0.11, 1), uv_rect=WHITE)
        part(self.tail, tm)

    def build_head(self):
        for c in list(self.head.children):
            c.parent = None
            c.remove_node()
        H = uvr(self.hide_key, 0.02)
        hm = MeshBuilder()
        hm.box((0, 0.02, 0.28), (0.52, 0.52, 0.6), uv_rect=H)
        hm.box((0, -0.13, 0.65), (0.48, 0.32, 0.24), color=PINK, uv_rect=WHITE)
        for nx in (-0.11, 0.11):
            hm.box((nx, -0.1, 0.775), (0.08, 0.06, 0.02), color=NOSTRIL, uv_rect=WHITE)
        hm.box((0, -0.24, 0.77), (0.32, 0.025, 0.02), color=NOSTRIL, uv_rect=WHITE)
        for sx in (-1, 1):
            hm.box((sx * 0.37, 0.14, 0.2), (0.26, 0.07, 0.15), uv_rect=H, rot=(0, 0, sx * 18))
            hm.box((sx * 0.37, 0.14, 0.215), (0.2, 0.05, 0.1), color=PINK, uv_rect=WHITE, rot=(0, 0, sx * 18))
        if self.horns:
            L = 0.34 if self.bull else 0.2
            for sx in (-1, 1):
                if self.bull:
                    hm.cylinder((sx * 0.2, 0.22, 0.18), 0.07, L, color=HORN, segs=8, rot=(0, 0, -sx * 70),
                                radius_top=0.035, uv_density=1.0)
                    hm.cone((sx * 0.5, 0.33, 0.18), 0.04, 0.2, color=HORN, segs=6, rot=(0, 0, -sx * 10))
                else:
                    hm.cone((sx * 0.16, 0.26, 0.18), 0.055, L, color=HORN, segs=6, rot=(0, 0, -sx * 22))
        # googly eyes
        for i, sx in enumerate((-1, 1)):
            hm.sphere((sx * 0.19, 0.17, 0.52), 0.105, color=EYEW, segs=10, rings=7, scale=(1, 1, 0.55))
            ox, oy = self.pupil_off[i]
            hm.sphere((sx * 0.19 + ox, 0.155 + oy, 0.575), 0.05, color=PUPIL, segs=8, rings=5, scale=(1, 1, 0.5))
        # ear tag
        if self.tag:
            hm.box((0.44, 0.06, 0.24), (0.02, 0.14, 0.14), uv_rect=uvr(self.tag, 0.05), rot=(0, 0, 18))
        if "wig" in self.acc:
            W = (0.97, 0.96, 0.93, 1)
            for (x, y, z, r) in [(0, 0.36, 0.22, 0.2), (-0.16, 0.34, 0.1, 0.16), (0.16, 0.34, 0.1, 0.16),
                                 (-0.3, 0.18, 0.12, 0.13), (0.3, 0.18, 0.12, 0.13), (-0.32, 0.0, 0.1, 0.12),
                                 (0.32, 0.0, 0.1, 0.12), (0, 0.3, -0.05, 0.17), (-0.3, -0.16, 0.08, 0.1),
                                 (0.3, -0.16, 0.08, 0.1)]:
                hm.sphere((x, y, z), r, color=W, segs=8, rings=6)
            hm.box((0, 0.18, -0.2), (0.1, 0.34, 0.1), color=W, uv_rect=WHITE)
            hm.box((0, 0.02, -0.22), (0.2, 0.08, 0.06), color=DARK, uv_rect=WHITE)
        if "daisy" in self.acc:
            cx, cy, cz = 0.3, 0.3, 0.12
            for k in range(7):
                a = k / 7 * 6.283
                hm.box((cx + math.cos(a) * 0.07, cy + math.sin(a) * 0.07, cz), (0.07, 0.04, 0.02),
                       color=(1, 1, 1, 1), uv_rect=WHITE, rot=(0, 0, math.degrees(a)))
            hm.sphere((cx, cy, cz + 0.01), 0.04, color=(1, 0.8, 0.1, 1), segs=6, rings=4)
        if "fedora" in self.acc:
            hm.cylinder((0, 0.27, 0.22), 0.36, 0.03, color=(0.22, 0.2, 0.2, 1), segs=14)
            hm.cylinder((0, 0.29, 0.22), 0.22, 0.22, color=(0.25, 0.23, 0.23, 1), segs=12, radius_top=0.19)
            hm.cylinder((0, 0.29, 0.22), 0.225, 0.06, color=(0.08, 0.08, 0.08, 1), segs=12)
        if "bonnet" in self.acc:
            hm.sphere((0, 0.22, 0.2), 0.34, color=(0.7, 0.82, 0.95, 1), segs=10, rings=6, scale=(1, 0.6, 1))
            hm.box((0, -0.1, 0.42), (0.04, 0.4, 0.04), color=(0.7, 0.82, 0.95, 1), uv_rect=WHITE)
        if "glasses" in self.acc:
            for sx in (-1, 1):
                hm.cylinder((sx * 0.19, 0.17, 0.60), 0.12, 0.02, color=DARK, segs=12, rot=(90, 0, 0), caps=True)
            hm.box((0, 0.2, 0.61), (0.16, 0.025, 0.02), color=DARK, uv_rect=WHITE)
        if "bucket" in self.acc:
            hm.cylinder((0, 0.02, 0.26), 0.31, 0.46, color=METAL, segs=14, radius_top=0.26)
            hm.box((0, 0.2, 0.555), (0.34, 0.05, 0.03), color=DARK, uv_rect=WHITE)
            hm.cylinder((0, 0.48, 0.26), 0.05, 0.12, color=RED, segs=6)
        if "moustache" in self.acc:
            hm.box((0, -0.02, 0.78), (0.44, 0.08, 0.05), color=MUSTACHE, uv_rect=WHITE)
        if "chuckhat" in self.acc:
            hm.cylinder((0, 0.27, 0.22), 0.42, 0.03, color=(0.86, 0.75, 0.45, 1), segs=14)
            hm.cylinder((0, 0.29, 0.22), 0.24, 0.2, color=(0.9, 0.78, 0.48, 1), segs=12)
        part(self.head, hm)

    def set_acc(self, name, on=True):
        if on:
            self.acc.add(name)
        else:
            self.acc.discard(name)
        self.build_head()

    def set_tag(self, tag):
        self.tag = tag
        self.build_head()

    # ------------------------------------------------------------------
    def animate(self, dt, speed=0.0, look_target=None, world_yaw=None):
        """speed in m/s; look_target: world (x,z) to turn the head toward.

        Writes rotations straight to Panda (setHpr) instead of through Ursina's property setters,
        which matters with ~50 cows on screen. Ursina rotation (x, y, z) == Panda HPR (-y, -x, z)."""
        self.t += dt
        self.phase += dt * (2.6 + speed * 2.6) if speed > 0.05 else 0
        amp = min(1.0, speed / 2.5) * 26
        s = math.sin(self.phase)
        lr = self._leg_rx
        if speed > 0.05:
            lr[0] = lr[3] = s * amp
            lr[1] = lr[2] = -s * amp
            by = abs(math.cos(self.phase)) * 0.035 * min(1.0, speed / 2)
        else:
            k = max(0.0, 1 - dt * 8)
            for i in range(4):
                lr[i] *= k
            by = self._body_y * k
        self._body_y = by
        # lying down
        self.lying += (self.lying_target - self.lying) * min(1, dt * 2)
        if self.lying > 0.01:
            by -= self.lying * 0.55
            for i in range(4):
                lr[i] = (-80 if i < 2 else 80) * self.lying
        self.body.setY(by)
        for i, lg in enumerate(self.legs):
            lg.setHpr(0, -lr[i], 0)
        self.tail.setHpr(0, -12, math.sin(self.t * 2.1) * 14 + math.sin(self.t * 5.3) * 4)
        # head
        if look_target is not None:
            dx = look_target[0] - self.getX()
            dz = look_target[1] - self.getZ()
            yaw = -self.getH() if world_yaw is None else world_yaw
            ang = math.degrees(math.atan2(dx, dz)) - yaw
            ang = (ang + 180) % 360 - 180
            self.head_yaw_target = max(-55, min(55, ang))
        else:
            self.head_yaw_target = math.sin(self.t * 0.3) * 8
        self.head_yaw += (self.head_yaw_target - self.head_yaw) * min(1, dt * 4)
        self.graze += (self.graze_target - self.graze) * min(1, dt * 2)
        nod = 0.0
        if self.talk_t > 0:
            self.talk_t -= dt
            nod = math.sin(self.talk_t * 18) * 8
        rx = self.graze * 45 + nod + self.head_pitch_extra + math.sin(self.t * 1.3) * 2
        self.head.setHpr(-self.head_yaw, -rx, 0)


# --------------------------------------------------------------------------
# farmer
# --------------------------------------------------------------------------

class FarmerModel(Entity):
    def __init__(self, parent=None, outfit="day", **kw):
        super().__init__(parent=parent or scene, **kw)
        self.outfit = outfit
        self.t = 0.0
        self.phase = 0.0
        self.pose = "idle"
        self.pose_t = 0.0
        self.tool_name = None
        self.rig = Entity(parent=self)
        self.shadow = blob_shadow(self, 1.0, 0.85, 0.55)
        self.build()

    def _colors(self):
        o = self.outfit
        if o == "pajamas":
            return dict(shirt=(0.55, 0.7, 0.9, 1), pants=(0.55, 0.7, 0.9, 1), shirt_uv=WHITE, pants_uv=WHITE, hat="nightcap",
                        belly=(0.55, 0.7, 0.9, 1))
        if o == "underwear":
            return dict(shirt=(0.97, 0.97, 0.95, 1), pants=SKIN, shirt_uv=WHITE, pants_uv=WHITE, hat="straw", briefs=True,
                        belly=(0.97, 0.97, 0.95, 1))
        return dict(shirt=(1, 1, 1, 1), pants=(1, 1, 1, 1), shirt_uv=uvr("plaid", 0.02), pants_uv=uvr("denim", 0.02), hat="straw",
                    belly=(0.2, 0.3, 0.52, 1))

    def build(self):
        for c in list(self.rig.children):
            c.parent = None
            c.remove_node()
        C = self._colors()
        self.hips = Entity(parent=self.rig, position=(0, 0.95, 0))
        tm = MeshBuilder()
        # torso: overalls lower + shirt upper
        tm.box((0, 0.28, 0), (0.58, 0.56, 0.38), color=C["pants"], uv_rect=C["pants_uv"])
        tm.sphere((0, 0.3, 0.13), 0.34, color=C["belly"], segs=12, rings=8, scale=(1.0, 0.9, 0.85))
        tm.box((0, 0.72, 0), (0.62, 0.38, 0.4), color=C["shirt"], uv_rect=C["shirt_uv"])
        if self.outfit == "day":
            tm.box((0, 0.6, 0.23), (0.36, 0.3, 0.06), color=(1, 1, 1, 1), uv_rect=uvr("denim", 0.02))
            for sx in (-1, 1):
                tm.box((sx * 0.15, 0.78, 0.2), (0.07, 0.4, 0.05), color=(1, 1, 1, 1), uv_rect=uvr("denim", 0.02))
                tm.box((sx * 0.15, 0.7, 0.24), (0.06, 0.06, 0.03), color=BRASS, uv_rect=WHITE)
        if C.get("briefs"):
            tm.box((0, 0.08, 0.02), (0.6, 0.2, 0.42), color=(0.97, 0.97, 0.97, 1), uv_rect=WHITE)
            tm.box((0, 0.17, 0.02), (0.61, 0.04, 0.43), color=(0.3, 0.4, 0.8, 1), uv_rect=WHITE)
        part(self.hips, tm)
        self.legs = []
        for sx in (-1, 1):
            pv = Entity(parent=self.hips, position=(sx * 0.15, 0.02, 0))
            lm = MeshBuilder()
            lm.box((0, -0.44, 0), (0.22, 0.86, 0.24), color=C["pants"], uv_rect=C["pants_uv"])
            lm.box((0, -0.88, 0.06), (0.26, 0.18, 0.38), color=BOOT, uv_rect=WHITE)
            part(pv, lm)
            self.legs.append(pv)
        self.arms = []
        for sx in (-1, 1):
            pv = Entity(parent=self.hips, position=(sx * 0.4, 0.84, 0))
            am = MeshBuilder()
            am.box((0, -0.3, 0), (0.17, 0.62, 0.18), color=C["shirt"] if self.outfit != "underwear" else SKIN,
                   uv_rect=C["shirt_uv"] if self.outfit != "underwear" else WHITE)
            am.sphere((0, -0.66, 0.02), 0.1, color=SKIN, segs=8, rings=6)
            part(pv, am)
            self.arms.append(pv)
        self.hand_r = Entity(parent=self.arms[1], position=(0, -0.68, 0.06))
        self.head = Entity(parent=self.hips, position=(0, 0.92, 0))
        hm = MeshBuilder()
        hm.box((0, 0.04, 0), (0.18, 0.1, 0.18), color=SKIN, uv_rect=WHITE)
        hm.sphere((0, 0.26, 0.0), 0.2, color=SKIN, segs=12, rings=9, scale=(0.95, 1.15, 1.0))
        hm.sphere((0, 0.24, 0.2), 0.065, color=(0.93, 0.55, 0.5, 1), segs=8, rings=5)
        # what's left of his hair, round the back and sides
        hm.sphere((0, 0.22, -0.04), 0.2, color=(0.42, 0.33, 0.25, 1), segs=12, rings=8, scale=(1.0, 0.75, 0.95))
        # huge mustache
        hm.box((0, 0.16, 0.2), (0.34, 0.08, 0.08), color=MUSTACHE, uv_rect=WHITE)
        for sx in (-1, 1):
            hm.box((sx * 0.19, 0.11, 0.18), (0.08, 0.14, 0.07), color=MUSTACHE, uv_rect=WHITE, rot=(0, 0, sx * 15))
        for sx in (-1, 1):
            hm.sphere((sx * 0.075, 0.32, 0.18), 0.03, color=PUPIL, segs=6, rings=4)
            hm.box((sx * 0.08, 0.38, 0.18), (0.1, 0.03, 0.03), color=MUSTACHE, uv_rect=WHITE, rot=(0, 0, -sx * 12))
            hm.sphere((sx * 0.2, 0.26, 0.0), 0.05, color=SKIN, segs=6, rings=4, scale=(0.5, 1, 1))
        if C["hat"] == "straw":
            # hat band (the straw itself is a separate part below, with the straw texture)
            hm.cylinder((0, 0.45, 0), 0.228, 0.05, color=RED, segs=12)
        elif C["hat"] == "nightcap":
            hm.cylinder((0, 0.38, 0), 0.21, 0.35, color=(0.9, 0.3, 0.3, 1), segs=10, radius_top=0.04, rot=(-20, 0, 0))
            hm.sphere((0, 0.72, -0.13), 0.06, color=(1, 1, 1, 1), segs=6, rings=4)
        # use straw texture on hat via separate part
        part(self.head, hm)
        if C["hat"] == "straw":
            sm = MeshBuilder()
            sm.cylinder((0, 0.42, 0), 0.42, 0.03, color=(1, 1, 1, 1), segs=16, uv_density=2)
            sm.cylinder((0, 0.44, 0), 0.22, 0.2, color=(1, 1, 1, 1), segs=12, radius_top=0.2, uv_density=2)
            part(self.head, sm, texture="straw")
        self.tool = None
        if self.tool_name:
            self.set_tool(self.tool_name)

    def set_outfit(self, outfit):
        if outfit != self.outfit:
            self.outfit = outfit
            self.build()

    def set_tool(self, name):
        self.tool_name = name
        if self.tool is not None:
            self.tool.parent = None
            self.tool.remove_node()
            self.tool = None
        if not name:
            return
        mb = MeshBuilder()
        if name == "pitchfork":
            mb.box((0, 0, 0.2), (0.04, 0.04, 1.6), color=WOOD, uv_rect=WHITE)
            mb.box((0, 0, 1.02), (0.3, 0.03, 0.04), color=METAL, uv_rect=WHITE)
            for x in (-0.13, 0, 0.13):
                mb.box((x, 0, 1.2), (0.025, 0.025, 0.36), color=METAL, uv_rect=WHITE)
        elif name == "clipboard":
            mb.box((0, 0.05, 0.15), (0.26, 0.34, 0.02), color=WOOD, uv_rect=WHITE, rot=(-60, 0, 0))
            mb.box((0, 0.07, 0.16), (0.22, 0.26, 0.022), color=(0.97, 0.97, 0.95, 1), uv_rect=WHITE, rot=(-60, 0, 0))
        elif name == "flashlight":
            mb.cylinder((0, 0, 0), 0.04, 0.26, color=DARK, segs=8, rot=(90, 0, 0))
            mb.cylinder((0, 0, 0.24), 0.055, 0.06, color=(1, 1, 0.8, 1), segs=8, rot=(90, 0, 0))
        elif name == "wrench":
            mb.box((0, 0, 0.12), (0.05, 0.03, 0.34), color=METAL, uv_rect=WHITE)
            mb.box((0, 0, 0.3), (0.12, 0.03, 0.08), color=METAL, uv_rect=WHITE)
        elif name == "rope":
            mb.cylinder((0, -0.05, 0.05), 0.14, 0.08, color=(0.8, 0.7, 0.45, 1), segs=10)
        elif name == "knife":
            mb.box((0, 0, 0.05), (0.04, 0.05, 0.14), color=DARK, uv_rect=WHITE)
            mb.box((0, 0, 0.25), (0.015, 0.06, 0.26), color=(0.85, 0.87, 0.9, 1), uv_rect=WHITE)
        elif name == "bowling_ball":
            mb.sphere((0, -0.05, 0.1), 0.14, color=(0.2, 0.3, 0.8, 1), segs=10, rings=7)
        elif name == "hammer":
            mb.box((0, 0, 0.15), (0.04, 0.04, 0.4), color=WOOD, uv_rect=WHITE)
            mb.box((0, 0, 0.35), (0.16, 0.06, 0.06), color=DARK, uv_rect=WHITE)
        elif name == "bucket":
            mb.cylinder((0, -0.3, 0.05), 0.16, 0.3, color=METAL, segs=10, radius_top=0.19)
        elif name == "oilcan":
            mb.cylinder((0, -0.1, 0.05), 0.08, 0.14, color=RED, segs=8)
            mb.box((0, 0.05, 0.14), (0.02, 0.02, 0.2), color=METAL, uv_rect=WHITE, rot=(-30, 0, 0))
        self.tool = part(self.hand_r, mb)

    # ------------------------------------------------------------------
    def animate(self, dt, speed=0.0, pose=None):
        self.t += dt
        if pose is not None and pose != self.pose:
            self.pose = pose
            self.pose_t = 0.0
        self.pose_t += dt
        p = self.pose
        L, R = self.legs
        AL, AR = self.arms
        self.rig.rotation_x = 0
        self.rig.y = 0
        self.hips.rotation_z = 0
        self.head.rotation_x = 0
        if p in ("walk", "run") or speed > 0.1:
            rate = 5.5 if speed < 3 else 9.0
            self.phase += dt * rate * max(0.6, speed / 2.2)
            a = min(1.0, speed / 2.0) * (30 if speed < 3 else 45)
            s = math.sin(self.phase)
            L.rotation_x = s * a
            R.rotation_x = -s * a
            AL.rotation_x = -s * a * 0.8
            if self.tool_name in ("flashlight", "pitchfork", "clipboard", "rope", "knife"):
                AR.rotation_x = -70 if self.tool_name == "flashlight" else -50
            else:
                AR.rotation_x = s * a * 0.8
            self.hips.y = 0.95 + abs(math.cos(self.phase)) * 0.04
            self.hips.rotation_z = math.sin(self.phase) * 3
        else:
            for lg in (L, R):
                lg.rotation_x *= max(0, 1 - dt * 10)
            self.hips.y = 0.95 + math.sin(self.t * 2) * 0.01
            if p == "work":
                AR.rotation_x = -60 + math.sin(self.t * 9) * 35
                AL.rotation_x = -30
                self.head.rotation_x = 20
            elif p == "sharpen":
                AR.rotation_x = -60 + math.sin(self.t * 5) * 15
                AL.rotation_x = -55 + math.sin(self.t * 5 + 1) * 12
                self.head.rotation_x = 25
            elif p == "talk":
                AR.rotation_x = -30 + math.sin(self.t * 6) * 20
                AL.rotation_x = -10
                self.head.rotation_x = math.sin(self.t * 9) * 6
            elif p == "look":
                self.head.rotation_y = math.sin(self.pose_t * 1.8) * 60
                AL.rotation_x = AR.rotation_x = -5
            elif p == "point":
                AR.rotation_x = -90
                AL.rotation_x = 0
            elif p == "count":
                AR.rotation_x = -45
                AL.rotation_x = -60
                self.head.rotation_x = 10 + math.sin(self.t * 3) * 6
                self.head.rotation_y = math.sin(self.t * 0.9) * 35
            elif p == "ow":
                AL.rotation_x = -150
                AR.rotation_x = -10
                self.head.rotation_z = math.sin(self.t * 8) * 8
            elif p == "lunge":
                k = min(1.0, self.pose_t / 0.25)
                AR.rotation_x = -80 * k
                AL.rotation_x = -80 * k
                self.rig.rotation_x = 20 * k
            elif p == "windup":
                AR.rotation_x = -150 + math.sin(self.t * 20) * 5
                AL.rotation_x = -140
                self.rig.rotation_x = -10
            elif p == "stuck":
                AR.rotation_x = -80 + math.sin(self.t * 20) * 8
                AL.rotation_x = -80 + math.sin(self.t * 20 + 1) * 8
                self.rig.rotation_x = 25
            elif p == "fallen":
                k = min(1.0, self.pose_t / 0.35)
                self.rig.rotation_x = 88 * k
                self.rig.y = 0.25 * k
                AL.rotation_x = AR.rotation_x = -160 * k
            elif p == "sleep":
                self.rig.rotation_x = -88
                self.rig.y = 0.8
                AL.rotation_x = AR.rotation_x = 0
            elif p in ("nap", "sit"):
                # sitting in a chair; "nap" leans back with the head lolling
                self.hips.y = 0.5
                L.rotation_x = R.rotation_x = -85
                self.rig.rotation_x = -14 if p == "nap" else 0
                AL.rotation_x = AR.rotation_x = -25 if p == "nap" else -40
                self.head.rotation_x = -22 + math.sin(self.t * 0.8) * 3 if p == "nap" else 0
            elif p == "hurt":
                self.rig.rotation_x = -15
                AL.rotation_x = AR.rotation_x = -40
            elif p == "throw":
                k = self.pose_t / 0.4
                AR.rotation_x = -160 + min(1, k) * 200
            elif p == "shrug":
                AL.rotation_x = AR.rotation_x = -40
                self.hips.rotation_z = 0
            else:
                AL.rotation_x += (0 - AL.rotation_x) * min(1, dt * 6)
                AR.rotation_x += ((-20 if self.tool_name else 0) - AR.rotation_x) * min(1, dt * 6)
                self.head.rotation_y *= max(0, 1 - dt * 3)


# --------------------------------------------------------------------------
# rooster
# --------------------------------------------------------------------------

class RoosterModel(Entity):
    def __init__(self, parent=None, headband=False, **kw):
        super().__init__(parent=parent or scene, **kw)
        self.t = 0
        self.rig = Entity(parent=self)
        blob_shadow(self, 0.6, 0.7, 0.4, y=0.03)
        mb = MeshBuilder()
        body = (0.85, 0.35, 0.12, 1)
        mb.sphere((0, 0.45, 0), 0.26, color=body, segs=10, rings=7, scale=(0.9, 0.9, 1.2))
        mb.box((0, 0.6, -0.3), (0.06, 0.4, 0.2), color=(0.1, 0.35, 0.25, 1), uv_rect=WHITE, rot=(-30, 0, 0))
        mb.box((0.06, 0.62, -0.28), (0.04, 0.36, 0.16), color=(0.08, 0.2, 0.4, 1), uv_rect=WHITE, rot=(-40, 0, 10))
        for sx in (-1, 1):
            mb.box((sx * 0.08, 0.1, 0.02), (0.03, 0.22, 0.03), color=(0.95, 0.75, 0.2, 1), uv_rect=WHITE)
            mb.box((sx * 0.08, 0.0, 0.06), (0.08, 0.02, 0.12), color=(0.95, 0.75, 0.2, 1), uv_rect=WHITE)
        part(self.rig, mb)
        self.head = Entity(parent=self.rig, position=(0, 0.68, 0.22))
        hm = MeshBuilder()
        hm.sphere((0, 0.06, 0), 0.12, color=body, segs=8, rings=6)
        hm.box((0, 0.2, 0), (0.04, 0.12, 0.16), color=(0.9, 0.1, 0.1, 1), uv_rect=WHITE)
        hm.box((0, -0.06, 0.1), (0.04, 0.1, 0.06), color=(0.9, 0.1, 0.1, 1), uv_rect=WHITE)
        hm.cone((0, 0.04, 0.1), 0.04, 0.1, color=(0.95, 0.75, 0.2, 1), segs=5, rot=(90, 0, 0))
        for sx in (-1, 1):
            hm.sphere((sx * 0.08, 0.1, 0.06), 0.035, color=EYEW, segs=6, rings=4)
            hm.sphere((sx * 0.1, 0.1, 0.07), 0.018, color=PUPIL, segs=5, rings=3)
        if headband:
            hm.cylinder((0, 0.12, 0), 0.125, 0.04, color=(0.85, 0.1, 0.1, 1), segs=10)
            hm.box((0, 0.13, -0.16), (0.03, 0.03, 0.1), color=(0.85, 0.1, 0.1, 1), uv_rect=WHITE, rot=(30, 0, 0))
            hm.box((0.03, 0.1, -0.19), (0.03, 0.03, 0.1), color=(0.85, 0.1, 0.1, 1), uv_rect=WHITE, rot=(50, 20, 0))
        part(self.head, hm)

    def animate(self, dt, speed=0.0, peck=False):
        self.t += dt
        self.rig.y = abs(math.sin(self.t * 12)) * 0.05 * min(1, speed)
        if peck:
            self.head.rotation_x = 40 + math.sin(self.t * 25) * 20
        else:
            self.head.rotation_x = math.sin(self.t * 3) * 10
            self.head.z = 0.22 + math.sin(self.t * 6) * 0.03


# --------------------------------------------------------------------------
# vehicles and props
# --------------------------------------------------------------------------

def tractor_model(parent=None, **kw):
    root = Entity(parent=parent or scene, **kw)
    mb = MeshBuilder()
    G = (0.18, 0.5, 0.2, 1)
    Y = (0.95, 0.8, 0.15, 1)
    mb.box((0, 1.25, 0.9), (1.0, 0.9, 2.0), color=G, uv_rect=WHITE)
    mb.box((0, 1.05, -0.5), (1.3, 0.5, 1.4), color=G, uv_rect=WHITE)
    mb.box((0, 1.5, -0.6), (0.7, 0.12, 0.6), color=(0.15, 0.15, 0.15, 1), uv_rect=WHITE)
    mb.box((0, 1.85, -0.9), (0.7, 0.6, 0.1), color=(0.15, 0.15, 0.15, 1), uv_rect=WHITE)
    mb.box((0, 1.25, 1.92), (0.8, 0.7, 0.06), color=(0.2, 0.2, 0.2, 1), uv_rect=WHITE)
    mb.cylinder((0.3, 1.7, 1.3), 0.06, 1.0, color=DARK, segs=8)
    mb.cylinder((0, 1.6, 0.0), 0.03, 0.5, color=DARK, segs=6, rot=(-40, 0, 0))
    mb.cylinder((0, 1.98, 0.3), 0.22, 0.04, color=DARK, segs=12, rot=(-40, 0, 0))
    for sx in (-1, 1):
        mb.cylinder((sx * 0.75, 0.85, -0.6), 0.85, 0.45, color=(0.12, 0.12, 0.12, 1), segs=16,
                    rot=(0, 0, 90 if sx < 0 else -90))
        mb.cylinder((sx * 0.8, 0.85, -0.6), 0.45, 0.42, color=Y, segs=12, rot=(0, 0, 90 if sx < 0 else -90))
        mb.cylinder((sx * 0.6, 0.45, 1.4), 0.45, 0.3, color=(0.12, 0.12, 0.12, 1), segs=14,
                    rot=(0, 0, 90 if sx < 0 else -90))
        mb.cylinder((sx * 0.64, 0.45, 1.4), 0.25, 0.28, color=Y, segs=10, rot=(0, 0, 90 if sx < 0 else -90))
    part(root, mb)
    lm = MeshBuilder()
    for sx in (-1, 1):
        lm.quad((sx * 0.505, 1.35, 1.0), (1.3, 0.33), rot=(0, -90 * sx, 0))
    Entity(parent=root, model=lm.build(), texture=tex("john_steer"), shader=FARM_SHADER)
    root.exhaust_top = (0.3, 2.7, 1.3)
    return root


def pickup_model(parent=None, color_=(0.7, 0.12, 0.1, 1), **kw):
    root = Entity(parent=parent or scene, **kw)
    mb = MeshBuilder()
    mb.box((0, 0.9, 0.9), (1.9, 0.8, 1.8), color=color_, uv_rect=WHITE)
    mb.box((0, 1.6, 0.35), (1.8, 0.7, 1.3), color=color_, uv_rect=WHITE)
    mb.box((0, 1.65, 1.0), (1.7, 0.5, 0.05), color=(0.55, 0.75, 0.9, 1), uv_rect=WHITE, rot=(-25, 0, 0))
    mb.box((0, 0.9, -1.3), (1.9, 0.7, 2.6), color=color_, uv_rect=WHITE)
    mb.box((0, 1.1, -1.3), (1.7, 0.4, 2.5), color=(0.25, 0.08, 0.06, 1), uv_rect=WHITE)
    mb.box((0, 0.8, 1.82), (1.8, 0.3, 0.1), color=METAL, uv_rect=WHITE)
    for sx in (-1, 1):
        for zz in (1.1, -1.6):
            mb.cylinder((sx * 0.85, 0.42, zz), 0.42, 0.3, color=(0.1, 0.1, 0.1, 1), segs=12, rot=(0, 0, 90 if sx < 0 else -90))
        mb.box((sx * 0.6, 0.95, 1.84), (0.3, 0.18, 0.05), color=(1, 1, 0.8, 1), uv_rect=WHITE)
    part(root, mb)
    return root


def cattle_truck_model(parent=None, **kw):
    root = Entity(parent=parent or scene, **kw)
    mb = MeshBuilder()
    W = (0.9, 0.9, 0.88, 1)
    mb.box((0, 1.4, 3.3), (2.3, 1.8, 1.8), color=W, uv_rect=WHITE)
    mb.box((0, 2.0, 4.1), (2.1, 0.7, 0.3), color=(0.4, 0.6, 0.75, 1), uv_rect=WHITE)
    mb.box((0, 0.8, 0.0), (2.4, 0.3, 6.0), color=DARK, uv_rect=WHITE)
    for i in range(6):
        y = 1.1 + i * 0.4
        for sx in (-1, 1):
            mb.box((sx * 1.2, y, -0.2), (0.06, 0.22, 5.4), color=(0.75, 0.75, 0.78, 1), uv_rect=WHITE)
    mb.box((0, 3.4, -0.2), (2.46, 0.08, 5.5), color=(0.75, 0.75, 0.78, 1), uv_rect=WHITE)
    mb.box((0, 2.2, 2.5), (2.46, 2.4, 0.08), color=(0.7, 0.7, 0.72, 1), uv_rect=WHITE)
    for sx in (-1, 1):
        for zz in (3.4, -1.0, -2.3):
            mb.cylinder((sx * 1.1, 0.5, zz), 0.5, 0.35, color=(0.1, 0.1, 0.1, 1), segs=12, rot=(0, 0, 90 if sx < 0 else -90))
    part(root, mb)
    root.door = Entity(parent=root, position=(0, 1.0, -2.95))
    dm = MeshBuilder()
    dm.box((0, 1.2, 0), (2.4, 2.4, 0.08), color=(0.7, 0.7, 0.72, 1), uv_rect=WHITE)
    part(root.door, dm)
    return root


def rock_model(parent=None, **kw):
    e = Entity(parent=parent or scene, **kw)
    mb = MeshBuilder()
    mb.sphere((0, 0, 0), 0.12, color=(0.55, 0.54, 0.5, 1), segs=7, rings=5, scale=(1.2, 0.8, 1.0))
    part(e, mb)
    return e


def item_model(name, parent=None, **kw):
    """Small 3D model for an item (world pickup or held in the mouth)."""
    e = Entity(parent=parent or scene, **kw)
    mb = MeshBuilder()
    texname = "atlas"
    if name == "rock":
        mb.sphere((0, 0, 0), 0.12, color=(0.55, 0.54, 0.5, 1), segs=7, rings=5, scale=(1.2, 0.8, 1.0))
    elif name == "radio":
        mb.box((0, 0, 0), (0.42, 0.26, 0.14), color=(0.72, 0.25, 0.2, 1), uv_rect=WHITE)
        mb.cylinder((-0.1, 0, 0.07), 0.08, 0.01, color=DARK, segs=10, rot=(90, 0, 0))
        mb.box((0.1, 0.04, 0.072), (0.14, 0.06, 0.01), color=(0.95, 0.92, 0.75, 1), uv_rect=WHITE)
        mb.box((0.15, 0.3, 0), (0.015, 0.4, 0.015), color=METAL, uv_rect=WHITE, rot=(0, 0, -20))
        mb.box((0, 0.16, 0), (0.3, 0.03, 0.03), color=DARK, uv_rect=WHITE)
    elif name == "pliers":
        mb.box((-0.03, 0, -0.08), (0.03, 0.02, 0.2), color=RED, uv_rect=WHITE, rot=(0, 10, 0))
        mb.box((0.03, 0, -0.08), (0.03, 0.02, 0.2), color=RED, uv_rect=WHITE, rot=(0, -10, 0))
        mb.box((0, 0, 0.08), (0.04, 0.025, 0.12), color=METAL, uv_rect=WHITE)
    elif name in ("key", "tractor_key", "house_key", "cabinet_key"):
        c = {"tractor_key": (0.2, 0.6, 0.25, 1), "cabinet_key": (0.6, 0.45, 0.25, 1), "house_key": METAL}.get(name, BRASS)
        mb.cylinder((0, 0, -0.06), 0.045, 0.012, color=c, segs=10, rot=(90, 0, 0))
        mb.box((0, 0, 0.04), (0.02, 0.012, 0.14), color=c, uv_rect=WHITE)
        mb.box((0.02, 0, 0.09), (0.03, 0.012, 0.015), color=c, uv_rect=WHITE)
    elif name == "jerrycan":
        mb.box((0, 0, 0), (0.18, 0.4, 0.32), color=(0.78, 0.15, 0.12, 1), uv_rect=WHITE)
        mb.box((0, 0.24, 0.08), (0.06, 0.1, 0.06), color=DARK, uv_rect=WHITE)
        mb.box((0, 0.22, -0.06), (0.04, 0.05, 0.16), color=(0.6, 0.1, 0.08, 1), uv_rect=WHITE)
    elif name == "sparkplug":
        mb.cylinder((0, -0.06, 0), 0.02, 0.06, color=METAL, segs=6)
        mb.cylinder((0, 0.0, 0), 0.03, 0.03, color=METAL, segs=6)
        mb.cylinder((0, 0.03, 0), 0.02, 0.08, color=(0.95, 0.95, 0.95, 1), segs=8)
    elif name == "bucket":
        mb.cylinder((0, -0.15, 0), 0.15, 0.3, color=METAL, segs=12, radius_top=0.18)
    elif name == "boot":
        mb.box((0, 0.1, 0), (0.14, 0.4, 0.16), color=(0.2, 0.45, 0.22, 1), uv_rect=WHITE)
        mb.box((0, -0.06, 0.08), (0.14, 0.1, 0.3), color=(0.2, 0.45, 0.22, 1), uv_rect=WHITE)
    elif name == "rubber_chicken":
        Yl = (0.98, 0.85, 0.2, 1)
        mb.sphere((0, 0, 0), 0.1, color=Yl, segs=8, rings=6, scale=(1, 0.8, 1.4))
        mb.box((0, 0.1, 0.16), (0.04, 0.2, 0.04), color=Yl, uv_rect=WHITE, rot=(-30, 0, 0))
        mb.sphere((0, 0.2, 0.22), 0.05, color=Yl, segs=6, rings=4)
        mb.box((0, 0.26, 0.22), (0.02, 0.04, 0.06), color=RED, uv_rect=WHITE)
    elif name == "shotgun":
        mb.box((0, 0, 0.3), (0.05, 0.05, 0.8), color=(0.3, 0.3, 0.32, 1), uv_rect=WHITE)
        mb.box((0, -0.02, -0.2), (0.06, 0.1, 0.35), color=(0.5, 0.3, 0.15, 1), uv_rect=WHITE, rot=(10, 0, 0))
        mb.box((0, -0.035, 0.12), (0.055, 0.04, 0.25), color=(0.5, 0.3, 0.15, 1), uv_rect=WHITE)
    elif name == "plank":
        mb.box((0, 0, 0), (0.25, 0.05, 2.2), color=(0.72, 0.55, 0.35, 1), uv_rect=WHITE)
    elif name == "fuse":
        mb.cylinder((0, -0.06, 0), 0.03, 0.12, color=(0.95, 0.95, 0.9, 1), segs=8, rot=(0, 0, 0))
        mb.cylinder((0, -0.08, 0), 0.032, 0.03, color=BRASS, segs=8)
        mb.cylinder((0, 0.05, 0), 0.032, 0.03, color=BRASS, segs=8)
    elif name == "cowbell":
        mb.cylinder((0, -0.08, 0), 0.08, 0.16, color=BRASS, segs=4, radius_top=0.05)
        mb.box((0, 0.1, 0), (0.03, 0.05, 0.03), color=(0.35, 0.22, 0.12, 1), uv_rect=WHITE)
    elif name == "egg":
        mb.sphere((0, 0, 0), 0.05, color=(0.98, 0.95, 0.88, 1), segs=8, rings=6, scale=(1, 1.3, 1))
    elif name in ("page", "score", "photo", "email"):
        if name == "photo":
            mb.box((0, 0, 0), (0.26, 0.2, 0.02), color=(0.4, 0.28, 0.18, 1), uv_rect=WHITE)
            for sz in (-1, 1):
                mb.box((0, 0, sz * 0.011), (0.21, 0.15, 0.002), color=(0.62, 0.55, 0.42, 1), uv_rect=WHITE)
                mb.box((0.02, -0.01, sz * 0.013), (0.08, 0.1, 0.002), color=(0.32, 0.2, 0.12, 1), uv_rect=WHITE)
        else:
            mb.box((0, 0, 0), (0.22, 0.28, 0.01), color=(0.97, 0.94, 0.84, 1), uv_rect=WHITE)
            # a few lines of ink (or a stave) on both sides so it reads as paper
            ink = (0.2, 0.22, 0.35, 1) if name != "score" else (0.15, 0.12, 0.1, 1)
            rows = 6 if name != "score" else 5
            for sz in (-1, 1):
                for k in range(rows):
                    y = 0.09 - k * (0.035 if name != "score" else 0.018)
                    w = 0.16 if (name == "score" or k % 3 != 2) else 0.1
                    mb.box((-(0.16 - w) / 2, y, sz * 0.006), (w, 0.006, 0.002), color=ink, uv_rect=WHITE)
                if name == "score":
                    for k in range(5):
                        mb.box((-0.06 + k * 0.03, 0.055 - (k % 3) * 0.009, sz * 0.007), (0.012, 0.01, 0.002),
                               color=ink, uv_rect=WHITE)
    elif name == "glasses":
        for sx in (-1, 1):
            mb.cylinder((sx * 0.05, 0, 0), 0.04, 0.008, color=DARK, segs=10, rot=(90, 0, 0))
        mb.box((0, 0, 0), (0.04, 0.008, 0.008), color=DARK, uv_rect=WHITE)
    elif name == "pencil":
        mb.box((0, 0, 0), (0.015, 0.015, 0.18), color=(0.98, 0.8, 0.2, 1), uv_rect=WHITE)
    elif name == "horseshoe":
        for k in range(7):
            a = math.pi * (k / 6) - math.pi
            mb.box((math.cos(a) * 0.07, 0, math.sin(a) * 0.07 + 0.03), (0.03, 0.02, 0.04), color=METAL,
                   uv_rect=WHITE, rot=(0, -math.degrees(a), 0))
    elif name == "coffee":
        mb.cylinder((0, -0.06, 0), 0.05, 0.12, color=(0.95, 0.95, 0.95, 1), segs=10)
    elif name == "tincan":
        mb.cylinder((0, -0.06, 0), 0.05, 0.12, color=METAL, segs=10)
    elif name == "shoes":
        mb.box((-0.06, 0, 0), (0.08, 0.06, 0.2), color=(0.8, 0.15, 0.15, 1), uv_rect=WHITE)
        mb.box((0.06, 0, 0), (0.08, 0.06, 0.2), color=(0.15, 0.4, 0.8, 1), uv_rect=WHITE)
    elif name == "chimes":
        mb.cylinder((0, 0.1, 0), 0.08, 0.02, color=WOOD, segs=10)
        for k in range(5):
            a = k / 5 * 6.283
            mb.cylinder((math.sin(a) * 0.06, -0.12, math.cos(a) * 0.06), 0.012, 0.2 - k * 0.02, color=METAL, segs=5)
    elif name == "moustache":
        mb.box((0, 0, 0), (0.2, 0.04, 0.03), color=MUSTACHE, uv_rect=WHITE)
    elif name == "hat":
        mb.cylinder((0, 0, 0), 0.3, 0.02, color=(0.86, 0.75, 0.45, 1), segs=12)
        mb.cylinder((0, 0.02, 0), 0.16, 0.14, color=(0.9, 0.78, 0.48, 1), segs=10)
    elif name == "wrench":
        mb.box((0, 0, 0), (0.03, 0.02, 0.24), color=METAL, uv_rect=WHITE)
    elif name == "clover":
        G = (1.0, 0.82, 0.15, 1)
        for k in range(3):
            a = k / 3 * 6.283 + 0.5
            mb.sphere((math.sin(a) * 0.08, 0.02, math.cos(a) * 0.08), 0.07, color=G, segs=8, rings=5, scale=(1, 0.3, 1))
        mb.box((0, -0.05, -0.05), (0.02, 0.02, 0.14), color=(0.7, 0.55, 0.1, 1), uv_rect=WHITE, rot=(30, 0, 0))
    else:
        mb.box((0, 0, 0), (0.15, 0.15, 0.15), color=(0.8, 0.8, 0.8, 1), uv_rect=WHITE)
    part(e, mb, texture=texname)
    return e
