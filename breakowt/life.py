"""Small life around the farm: things that notice the player and answer back.

- birds that scatter when you come galloping (or make a racket)
- butterflies by day, fireflies after dark
- ripples when you wade, dust when Chuck runs, hoofprints in the mud
- the herd moos back when you moo; frogs and the owl answer at night; frogs hush when you come close
- Chuck yelps when something you threw hits him, and tidies up what you knocked over
Everything here is decoration: nothing in it can block the story.
"""
from __future__ import annotations

import math
import random

from PIL import Image, ImageDraw
from panda3d.core import TransparencyAttrib
from ursina import Entity, Texture, destroy

from .engine.assets import tex
from .engine.meshbuilder import MeshBuilder
from .engine.shading import FARM_SHADER
from .world import POND, in_pond
from . import models

OWL_POS = (-62, 9, 30)
POND_CENTER = (POND[0], 0.3, POND[1])
MUD_RECTS = [(-30, -18, -40, -28), (-60, -44, -18, -12)]
FLOCK_SPOTS = [
    # (x, y, z, spread, perched): ground flocks peck about; perched ones sit on a ridge or rail
    (-36, 0, -42, 2.5, False), (-58, 0, -48, 2.5, False), (-27, 0, -57, 2.0, False), (4, 0, -20, 2.0, False),
    (19, 0, -26, 2.0, False), (22, 12.25, 2.0, 5.0, True), (56, 6.35, 39.0, 5.0, True), (-18.0, 1.24, -18.0, 2.5, True),
]
FLOCK_COLORS = [(0.36, 0.26, 0.18, 1), (0.25, 0.25, 0.28, 1), (0.52, 0.4, 0.28, 1), (0.12, 0.12, 0.14, 1)]
BUTTERFLY_COLS = [(1.0, 0.85, 0.2, 1), (1.0, 1.0, 1.0, 1), (0.95, 0.5, 0.15, 1), (0.55, 0.7, 1.0, 1)]
TIDY_LINES = ["Who keeps knockin' this over?", "Every. Single. Day.", "Raccoons. Has to be raccoons.",
              "I just stacked these!", "If I find out who did this...", "Hmph. Gravity again."]
BONK_LINES = ["OW! Who threw that?!", "HEY! Who's out there?!", "Ow! My EVERYTHING!", "Raccoons can't throw! ...Can they?"]


def _ring_texture():
    img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([12, 12, 244, 244], outline=(255, 255, 255, 200), width=7)
    d.ellipse([40, 40, 216, 216], outline=(255, 255, 255, 90), width=4)
    t = Texture(img)
    t.filtering = "mipmap"
    return t


def _hoof_texture():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([10, 8, 30, 56], fill=(255, 255, 255, 255))
    d.ellipse([34, 8, 54, 56], fill=(255, 255, 255, 255))
    return Texture(img)


def _fade_entity(e):
    e.setTransparency(TransparencyAttrib.MAlpha)
    e.setDepthWrite(False)
    e.set_shader_input("u_unlit", 0.5)


class Bird:
    def __init__(self, parent_pos, col):
        self.ent = Entity(position=parent_pos)
        mb = MeshBuilder()
        mb.sphere((0, 0.07, 0), 0.07, color=col, segs=7, rings=5, scale=(0.85, 0.75, 1.3))
        mb.sphere((0, 0.13, 0.08), 0.045, color=col, segs=6, rings=4)
        mb.cone((0, 0.13, 0.12), 0.015, 0.05, color=(0.9, 0.7, 0.2, 1), segs=4, rot=(90, 0, 0))
        mb.box((0, 0.08, -0.12), (0.06, 0.015, 0.1), color=col, uv_rect=models.WHITE)
        Entity(parent=self.ent, model=mb.build(solid_rect=models.WHITE), texture=tex("atlas"), shader=FARM_SHADER)
        self.wings = []
        for sx in (-1, 1):
            pv = Entity(parent=self.ent, position=(sx * 0.05, 0.09, 0))
            wm = MeshBuilder().box((sx * 0.06, 0, 0), (0.12, 0.012, 0.08), color=col, uv_rect=models.WHITE)
            Entity(parent=pv, model=wm.build(), texture=tex("atlas"), shader=FARM_SHADER)
            self.wings.append((pv, sx))
        self.vel = [0.0, 0.0, 0.0]
        self.t = random.uniform(0, 6)
        self.hop_t = random.uniform(0.5, 3.0)
        self.base_y = parent_pos[1]

    def remove(self):
        destroy(self.ent)


class Flock:
    def __init__(self, life, spot):
        self.life = life
        self.x, self.y, self.z, self.spread, self.perched = spot
        self.birds: list[Bird] = []
        self.state = "gone"      # gone -> ground -> flying -> gone
        self.timer = random.uniform(0, 20)
        self.fly_t = 0.0

    def spawn(self):
        col = random.choice(FLOCK_COLORS)
        n = random.randint(3, 6)
        for i in range(n):
            if self.perched:
                off = (random.uniform(-self.spread, self.spread), 0, random.uniform(-0.1, 0.1))
            else:
                a = random.uniform(0, 6.283)
                r = random.uniform(0.3, self.spread)
                off = (math.cos(a) * r, 0, math.sin(a) * r)
            b = Bird((self.x + off[0], self.y, self.z + off[2]), col)
            b.ent.rotation_y = random.uniform(0, 360)
            self.birds.append(b)
        self.state = "ground"

    def despawn(self):
        for b in self.birds:
            b.remove()
        self.birds = []
        self.state = "gone"

    def scatter(self, from_pos):
        if self.state != "ground":
            return
        self.state = "flying"
        self.fly_t = 0.0
        g = self.life.g
        g.audio.play("bird_flutter", vol=0.8, pos=(self.x, self.y + 0.5, self.z), rng=30, pitch=random.uniform(0.9, 1.15))
        for b in self.birds:
            dx, dz = b.ent.x - from_pos[0], b.ent.z - from_pos[2]
            d = math.hypot(dx, dz) or 1.0
            s = random.uniform(3.0, 5.0)
            b.vel = [dx / d * s + random.uniform(-1, 1), random.uniform(2.5, 4.0), dz / d * s + random.uniform(-1, 1)]
            b.ent.rotation_y = math.degrees(math.atan2(b.vel[0], b.vel[2]))
        g.event("flock")

    def update(self, dt, px, pz, day, gallop):
        d = math.hypot(px - self.x, pz - self.z)
        if self.state == "gone":
            self.timer -= dt
            if day and self.timer <= 0 and 22 < d < 70:
                self.spawn()
            return
        if not day or d > 90:
            self.despawn()
            self.timer = random.uniform(20, 60)
            return
        if self.state == "ground":
            reach = 9.0 if gallop else (2.5 if self.life.g.player.crouching else 5.0)
            if self.perched:
                reach = 4.5 if gallop else 2.0
            if d < reach + self.spread:
                self.scatter((px, 0, pz))
                return
            if d > 40:
                return   # far away: no need to animate
            for b in self.birds:
                b.t += dt
                b.hop_t -= dt
                if b.hop_t <= 0:
                    b.hop_t = random.uniform(0.6, 3.0)
                    if not self.perched:
                        a = math.radians(random.uniform(0, 360))
                        nx, nz = b.ent.x + math.sin(a) * 0.3, b.ent.z + math.cos(a) * 0.3
                        if math.hypot(nx - self.x, nz - self.z) < self.spread:
                            b.ent.x, b.ent.z = nx, nz
                            b.ent.rotation_y = math.degrees(a)
                    else:
                        b.ent.rotation_y += random.choice((-90, 90, 180))
                peck = max(0.0, math.sin(b.t * 7)) if not self.perched else 0.0
                b.ent.y = b.base_y + abs(math.sin(b.t * 9)) * 0.02 * (b.hop_t < 0.15)
                b.ent.rotation_x = peck * 35
                for pv, sx in b.wings:
                    pv.rotation_z = 0
            return
        # flying away
        self.fly_t += dt
        for b in self.birds:
            b.vel[1] += 1.2 * dt
            b.ent.position += (b.vel[0] * dt, b.vel[1] * dt, b.vel[2] * dt)
            flap = math.sin(self.fly_t * 40 + b.t) * 60
            for pv, sx in b.wings:
                pv.rotation_z = flap * sx
            b.ent.rotation_x = -15
        if self.fly_t > 5.0:
            self.despawn()
            self.timer = random.uniform(40, 110)


class Butterfly:
    def __init__(self, area):
        self.area = area
        x0, x1, z0, z1 = area
        self.pos = [random.uniform(x0, x1), random.uniform(0.5, 1.4), random.uniform(z0, z1)]
        self.target = list(self.pos)
        self.ent = Entity(position=self.pos)
        col = random.choice(BUTTERFLY_COLS)
        self.wings = []
        for sx in (-1, 1):
            pv = Entity(parent=self.ent)
            mb = MeshBuilder()
            mb.box((sx * 0.05, 0, 0.01), (0.09, 0.004, 0.07), color=col, uv_rect=models.WHITE)
            mb.box((sx * 0.04, 0, -0.045), (0.06, 0.004, 0.05), color=col, uv_rect=models.WHITE)
            e = Entity(parent=pv, model=mb.build(), texture=tex("atlas"), shader=FARM_SHADER)
            e.set_shader_input("u_unlit", 0.4)
            self.wings.append((pv, sx))
        self.t = random.uniform(0, 6)

    def update(self, dt, px, py, pz):
        self.t += dt
        x0, x1, z0, z1 = self.area
        dx, dz = self.target[0] - self.pos[0], self.target[2] - self.pos[2]
        if math.hypot(dx, dz) < 0.3 or random.random() < dt * 0.2:
            self.target = [random.uniform(x0, x1), random.uniform(0.4, 1.6), random.uniform(z0, z1)]
        # shy of cows
        ax, az = self.pos[0] - px, self.pos[2] - pz
        dp = math.hypot(ax, az)
        if dp < 1.6:
            self.target = [self.pos[0] + ax / max(dp, 0.1) * 3, 1.8, self.pos[2] + az / max(dp, 0.1) * 3]
        for i in (0, 1, 2):
            self.pos[i] += (self.target[i] - self.pos[i]) * min(1.0, dt * 0.9)
        self.pos[1] += math.sin(self.t * 5) * dt * 0.4
        self.ent.setPos(*self.pos)
        self.ent.setH(-math.degrees(math.atan2(self.target[0] - self.pos[0], self.target[2] - self.pos[2])))
        flap = 25 + 55 * abs(math.sin(self.t * 14))
        for pv, sx in self.wings:
            pv.setR(flap * sx)

    def remove(self):
        destroy(self.ent)


class Firefly:
    def __init__(self, center, spread):
        self.c = center
        self.spread = spread
        self.ph = random.uniform(0, 6.283)
        self.rate = random.uniform(0.25, 0.6)
        mb = MeshBuilder().sphere((0, 0, 0), 0.055, color=(0.8, 1.0, 0.35, 1), segs=6, rings=4)
        self.ent = Entity(model=mb.build(), texture=tex("white"), shader=FARM_SHADER)
        self.ent.set_shader_input("u_unlit", 1.0)
        self.off = [random.uniform(-spread, spread), random.uniform(0.3, 1.8), random.uniform(-spread, spread)]

    def update(self, dt, t):
        # straight to Panda3D: Ursina's property setters cost far more than the maths here
        self.ph += dt * self.rate
        glow = max(0.0, math.sin(self.ph * 3.0)) ** 3
        q = round(glow * 12)
        if q != getattr(self, "_q", None):
            self._q = q
            self.ent.setShaderInput("u_emissive", 3.5 * q / 12)
            self.ent.setScale(0.5 + 1.6 * q / 12)
        cx, cy, cz = self.c
        self.ent.setPos(cx + self.off[0] + math.sin(t * 0.3 + self.ph) * 1.2, self.off[1] + math.sin(t * 0.7 + self.ph) * 0.3,
                        cz + self.off[2] + math.cos(t * 0.25 + self.ph) * 1.2)

    def remove(self):
        destroy(self.ent)


class Fx:
    """A short-lived fading sprite: dust puff (billboard) or water ring (flat)."""

    def __init__(self, texture, pos, kind, col, size, life):
        self.kind = kind
        self.life = life
        self.t = 0.0
        self.size = size
        self.col = col
        if kind == "dust":
            mesh = MeshBuilder().quad((0, 0, 0), (1, 1), double=True).build()
            self.ent = Entity(model=mesh, texture=texture, position=pos, billboard=True, color=col, scale=size * 0.4,
                              shader=FARM_SHADER)
            self.vy = random.uniform(0.3, 0.8)
        else:
            mesh = MeshBuilder().disk((0, 0, 0), 0.5, 0.5, segs=16, uv_rect=(0, 0, 1, 1)).build()
            self.ent = Entity(model=mesh, texture=texture, position=pos, color=col, scale=size * 0.2,
                              shader=FARM_SHADER)
            self.vy = 0.0
        _fade_entity(self.ent)

    def update(self, dt):
        self.t += dt
        k = self.t / self.life
        if self.kind == "dust":
            self.ent.y += self.vy * dt
            self.ent.scale = self.size * (0.4 + 0.9 * k)
        elif self.kind == "ring":
            self.ent.scale = self.size * (0.2 + 1.4 * k)
        a = max(0.0, 1.0 - k) * self.col[3]
        self.ent.color = (self.col[0], self.col[1], self.col[2], a)
        if self.t >= self.life:
            destroy(self.ent)
            return False
        return True


class Life:
    def __init__(self, g):
        self.g = g
        self.t = 0.0
        self.flocks = [Flock(self, s) for s in FLOCK_SPOTS]
        self.butterflies: list[Butterfly] = []
        self.fireflies: list[Firefly] = []
        self.fx: list[Fx] = []
        self.prints: list[list] = []
        self.ring_tex = _ring_texture()
        self.hoof_tex = _hoof_texture()
        self.dust_tex = tex("soft_circle")
        self.pending: list = []       # (time, callable)
        self.choir_cd = 0.0
        self.print_side = 1
        self.frog_hush = 0.0
        self.was_day = None
        self.tidy_cd = 0.0
        self.chuck_dust_t = 0.0
        sc = g.world.props.get("scarecrow") if hasattr(g.world, "props") else None
        self.scarecrow = sc
        self.sc_spin = 0.0
        ia = g.ia.get("scarecrow")
        if ia is not None:
            ia.on_headbutt = self._bonk_scarecrow

    # ------------------------------------------------------------------
    def later(self, delay, fn):
        self.pending.append((self.t + delay, fn))

    def clear(self):
        for f in self.flocks:
            f.despawn()
        for b in self.butterflies:
            b.remove()
        self.butterflies = []
        for f in self.fireflies:
            f.remove()
        self.fireflies = []
        for fx in self.fx:
            destroy(fx.ent)
        self.fx = []
        for pr in self.prints:
            destroy(pr[0])
        self.prints = []
        self.pending = []
        self.was_day = None

    # ------------------------------------------------------------------
    def on_event(self, name, **kw):
        g = self.g
        p = g.player
        if name == "moo":
            self._answer_moo()
        elif name == "step":
            if kw.get("surface") == "water":
                # the water parts in front of your nose, where you can see it
                r = math.radians(p.yaw)
                self.ring((p.x + math.sin(r) * 1.1, 0.085, p.z + math.cos(r) * 1.1), 1.7)
            elif self._muddy(p.x, p.z):
                self.hoofprint(p.x, p.z, p.yaw)
            if kw.get("gallop") and kw.get("surface") in ("dirt", "grass"):
                self.dust((p.x, p.y + 0.15, p.z), 2)
        elif name == "noise":
            pos, radius = kw.get("pos"), kw.get("radius", 0)
            if radius >= 12 and pos is not None:
                for f in self.flocks:
                    if f.state == "ground" and math.hypot(f.x - pos[0], f.z - pos[2]) < min(radius, 18):
                        f.scatter(pos)

    def _answer_moo(self):
        g = self.g
        p = g.player
        dark = g.env.is_dark
        # the herd answers from the pasture
        if self.choir_cd <= 0:
            near = [h for h in g.herd if not h.far and h.state != "stampede" and math.hypot(h.x - p.x, h.z - p.z) < 30]
            if near:
                self.choir_cd = 3.5
                picks = random.sample(near, min(len(near), random.randint(1, 3)))
                for i, h in enumerate(picks):
                    self.later(0.6 + i * 0.5 + random.uniform(0, 0.5), lambda h=h: self._herd_moo(h))
                self.later(1.5, lambda: g.event("choir"))
        if dark:
            if math.hypot(p.x - POND_CENTER[0], p.z - POND_CENTER[2]) < 22:
                self.frog_hush = 0.0
                self.later(0.9, lambda: (g.audio.play("frog_chorus", vol=0.9, pos=POND_CENTER, rng=45),
                                         g.event("frogs")))
            if math.hypot(p.x - OWL_POS[0], p.z - OWL_POS[2]) < 48:
                self.later(1.4, lambda: (g.audio.play("owl_hoot", vol=0.9, pos=OWL_POS, rng=120), g.event("owl")))

    def _herd_moo(self, h):
        g = self.g
        g.audio.play(h.voice, vol=0.85, pitch=h.pitch, pos=(h.x, 1.4, h.z), rng=45, group="voice")
        h.bubble(random.choice(["Moo!", "Mooo.", "Moo?", "MOO."]))

    def _bonk_scarecrow(self, g):
        g.audio.play("bonk", vol=0.8)
        self.sc_spin = 1.0
        g.event("scarecrow")
        g.examine(random.choice(["Cardboard Chuck spins like a weathervane. Deeply satisfying.",
                                 "You headbutt Cardboard Chuck. He takes it better than the real one would.",
                                 "Cardboard Chuck wobbles, and comes back. He always comes back."]))

    # ------------------------------------------------------------------
    def ring(self, pos, size=1.0):
        if len(self.fx) < 40:
            self.fx.append(Fx(self.ring_tex, pos, "ring", (0.9, 0.95, 1.0, 0.45), size, 1.9))

    def dust(self, pos, n=2, col=(0.72, 0.62, 0.48, 0.45)):
        for _ in range(n):
            if len(self.fx) < 40:
                q = (pos[0] + random.uniform(-0.3, 0.3), pos[1], pos[2] + random.uniform(-0.3, 0.3))
                self.fx.append(Fx(self.dust_tex, q, "dust", col, random.uniform(0.6, 1.0), 1.1))

    def hoofprint(self, x, z, yaw):
        self.print_side *= -1
        r = math.radians(yaw)
        ox, oz = math.cos(r) * 0.18 * self.print_side, -math.sin(r) * 0.18 * self.print_side
        mesh = MeshBuilder().disk((0, 0, 0), 0.5, 0.5, segs=12, uv_rect=(0, 0, 1, 1)).build()
        e = Entity(model=mesh, texture=self.hoof_tex, position=(x + ox, 0.045, z + oz), rotation_y=yaw,
                   scale=0.24, color=(0.22, 0.15, 0.09, 0.7), shader=FARM_SHADER)
        _fade_entity(e)
        self.prints.append([e, 60.0])
        if len(self.prints) > 40:
            destroy(self.prints.pop(0)[0])

    @staticmethod
    def _muddy(x, z):
        for x0, x1, z0, z1 in MUD_RECTS:
            if x0 <= x <= x1 and z0 <= z <= z1:
                return True
        return in_pond(x, z, 1.6) and not in_pond(x, z)

    # ------------------------------------------------------------------
    def check_chuck_hit(self, p0, p1):
        """A thrown thing crossing Chuck (outside the boss fight). Returns True if it hit him."""
        g = self.g
        f = g.farmer
        if not f.visible or f.state in ("boss", "scripted", "catch", "disabled") or g.enemies:
            return False
        dx, dz = p1[0] - p0[0], p1[2] - p0[2]
        L2 = dx * dx + dz * dz
        if L2 < 1e-9:
            return False
        t = max(0.0, min(1.0, ((f.x - p0[0]) * dx + (f.z - p0[2]) * dz) / L2))
        cx, cz = p0[0] + dx * t, p0[2] + dz * t
        cy = p0[1] + (p1[1] - p0[1]) * t
        if math.hypot(cx - f.x, cz - f.z) > 0.5 or not (f.y + 0.1 < cy < f.y + 2.0):
            return False
        g.audio.play("bonk", vol=1.0, pos=(f.x, f.y + 1.5, f.z), rng=40)
        if f.state == "sleep":
            f.hear((f.x, f.y, f.z), 60, "thrown")
        else:
            f.say(random.choice(BONK_LINES), force=True)
            p = g.player
            f.investigate((p.x, 0, p.z), quiet=True)
            f.susp = max(f.susp, 0.2)
        g.event("bonk")
        return True

    def tidy(self, dt):
        """Chuck rights anything knocked over that he walks up to."""
        g = self.g
        f = g.farmer
        self.tidy_cd = max(0.0, self.tidy_cd - dt)
        if not f.visible or f.state not in ("routine", "investigate") or self.tidy_cd > 0:
            return
        for k in g.knockables:
            if k["down"] and math.hypot(k["x"] - f.x, k["z"] - f.z) < 1.9:
                k["down"] = False
                k["ent"].animate_rotation((0, 0, 0), duration=0.5)
                f.say(random.choice(TIDY_LINES))
                g.audio.play("metal_clang", vol=0.5, pos=(k["x"], 0.5, k["z"]), rng=25)
                self.tidy_cd = 4.0
                g.event("tidy")
                return

    # ------------------------------------------------------------------
    def update(self, dt):
        g = self.g
        self.t += dt
        self.choir_cd = max(0.0, self.choir_cd - dt)
        if self.pending:
            due = [fn for (at, fn) in self.pending if at <= self.t]
            self.pending = [(at, fn) for (at, fn) in self.pending if at > self.t]
            for fn in due:
                fn()
        p = g.player
        day = not g.env.is_dark and getattr(g.env, "preset_name", "") not in ("rain",)
        if g.state != "play":
            return
        if day != self.was_day:
            self.was_day = day
            self._switch_time(day)
        for f in self.flocks:
            f.update(dt, p.x, p.z, day, p.galloping)
        for b in self.butterflies:
            b.update(dt, p.x, p.y, p.z)
        for ff in self.fireflies:
            ff.update(dt, self.t)
        self.fx = [fx for fx in self.fx if fx.update(dt)]
        keep = []
        for pr in self.prints:
            pr[1] -= dt
            if pr[1] <= 0:
                destroy(pr[0])
            else:
                if pr[1] < 10:
                    pr[0].color = (0.22, 0.15, 0.09, 0.07 * pr[1])
                keep.append(pr)
        self.prints = keep
        # frogs hush when a cow comes stomping up to the pond
        d_pond = math.hypot(p.x - POND_CENTER[0], p.z - POND_CENTER[2])
        a = g.audio
        if "env_frogs" in a.loops:
            if d_pond < 11 and not p.crouching:
                self.frog_hush = 5.0
            self.frog_hush = max(0.0, self.frog_hush - dt)
            base = g.EMITTERS["env_frogs"][3].get(getattr(g, "amb_preset", "day"), 0.3)
            a.set_loop("env_frogs", vol=0.0 if self.frog_hush > 0 else base)
        # herd cows wading make ripples too
        self.herd_ripple_t = getattr(self, "herd_ripple_t", 0.0) - dt
        if self.herd_ripple_t <= 0:
            self.herd_ripple_t = 0.6
            for h in g.herd:
                if not h.far and h.state in ("walk", "stampede") and in_pond(h.x, h.z):
                    self.ring((h.x, 0.085, h.z), 2.2)
        # Chuck kicks up dust when he runs
        f = g.farmer
        if f.visible and getattr(f, "walk_speed", 0) > 3.2 and f.path and f.y < 0.2:
            self.chuck_dust_t -= dt
            if self.chuck_dust_t <= 0:
                self.chuck_dust_t = 0.25
                self.dust((f.x, 0.15, f.z), 1)
        self.tidy(dt)
        if self.sc_spin > 0 and self.scarecrow is not None:
            self.sc_spin = max(0.0, self.sc_spin - dt * 0.5)
            self.scarecrow.rotation_y += dt * 900 * self.sc_spin ** 2

    def _switch_time(self, day):
        for b in self.butterflies:
            b.remove()
        for ff in self.fireflies:
            ff.remove()
        self.butterflies, self.fireflies = [], []
        if day:
            areas = [(-70, -30, -70, -15), (-70, -30, -70, -15), (-70, -30, -70, -15), (38, 44, 21, 27),
                     (38, 44, 21, 27), (-40, -20, -60, -40)]
            self.butterflies = [Butterfly(a) for a in areas]
        else:
            spots = [((POND[0], 0, POND[1]), 9), ((-50, 0, -35), 10), ((-30, 0, -55), 10), ((-60, 0, -20), 9),
                     ((-52, 0, -16), 6)]
            for c, s in spots:
                for _ in range(6):
                    self.fireflies.append(Firefly(c, s))
