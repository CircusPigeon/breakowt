"""Fights: Cluck Norris in the coop, and Chuck at the main gate."""
from __future__ import annotations

import math
import random

from ursina import Entity, destroy

from . import models
from .engine.meshbuilder import MeshBuilder
from .engine.shading import FARM_SHADER, no_shadow
from .engine.assets import tex
from .npc import ang_diff


def _seg_point_dist(p0, p1, q):
    dx, dy, dz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
    L2 = dx * dx + dy * dy + dz * dz
    if L2 < 1e-9:
        return math.dist(p0, q)
    t = max(0.0, min(1.0, ((q[0] - p0[0]) * dx + (q[1] - p0[1]) * dy + (q[2] - p0[2]) * dz) / L2))
    return math.dist((p0[0] + dx * t, p0[1] + dy * t, p0[2] + dz * t), q)


class Feathers:
    """A little burst of feathers (or dust) that falls and fades."""

    def __init__(self, pos, col=(0.9, 0.45, 0.15, 1), n=10):
        self.parts = []
        for _ in range(n):
            mb = MeshBuilder().box((0, 0, 0), (0.08, 0.02, 0.14), color=col, uv_rect=models.WHITE)
            e = Entity(model=mb.build(solid_rect=models.WHITE), texture=tex("atlas"), shader=FARM_SHADER,
                       position=pos, rotation=(random.uniform(0, 360), random.uniform(0, 360), 0))
            v = [random.uniform(-2, 2), random.uniform(1.5, 3.5), random.uniform(-2, 2)]
            self.parts.append([e, v])
        self.t = 0.0
        self.alive = True

    def update(self, dt):
        self.t += dt
        for e, v in self.parts:
            v[1] -= 4.0 * dt
            v[0] *= 0.96
            v[2] *= 0.96
            e.position += (v[0] * dt, max(v[1], -0.8) * dt, v[2] * dt)
            e.rotation_y += dt * 200
            if e.y < 0.02:
                e.y = 0.02
        if self.t > 1.6:
            for e, _ in self.parts:
                destroy(e)
            self.parts = []
            self.alive = False


class Enemy:
    """Shared hit tests for things the player can headbutt, kick and pelt."""
    radius = 0.5
    height = 1.0
    alive = True

    def center(self):
        return (self.x, self.y + self.height * 0.5, self.z)

    def in_front(self, eye, fwd, reach):
        cx, cy, cz = self.center()
        dx, dz = cx - eye[0], cz - eye[2]
        d = math.hypot(dx, dz)
        if d > reach + self.radius:
            return False
        if d < 0.6:
            return True
        cosang = (dx * fwd[0] + dz * fwd[2]) / (d * max(1e-6, math.hypot(fwd[0], fwd[2])))
        return cosang > math.cos(math.radians(40))

    def behind(self, pos, yaw, reach):
        dx, dz = self.x - pos[0], self.z - pos[2]
        d = math.hypot(dx, dz)
        if d > reach + self.radius:
            return False
        fx, fz = math.sin(math.radians(yaw)), math.cos(math.radians(yaw))
        return (dx * fx + dz * fz) / max(d, 1e-6) < -0.2 or d < 0.8

    def segment_hit(self, p0, p1):
        for k in range(3):
            q = (self.x, self.y + self.height * (0.2 + 0.3 * k), self.z)
            if _seg_point_dist(p0, p1, q) < self.radius + 0.12:
                return True
        return False


# ---------------------------------------------------------------------------
# Cluck Norris
# ---------------------------------------------------------------------------

class CluckNorris(Enemy):
    MAX_HP = 6
    radius = 0.45
    height = 1.1

    def __init__(self, g, pos, bounds, on_defeat=None):
        self.g = g
        self.x, self.y, self.z = pos
        self.yaw = 180.0
        self.bounds = bounds          # x0, x1, z0, z1 he stays inside
        self.model = models.RoosterModel(headband=True, scale=1.6, position=pos)
        self.hp = self.MAX_HP
        self.state = "idle"
        self.t = 1.2
        self.alive = True
        self.dash_dir = (0.0, 0.0)
        self.hit_player = False
        self.vy = 0.0
        self.on_defeat = on_defeat
        self.fx: list = []
        self.active = True

    def remove(self):
        destroy(self.model)
        for f in self.fx:
            for e, _ in f.parts:
                destroy(e)
        self.fx = []

    def _face_player(self, dt, rate=6.0):
        p = self.g.player
        want = math.degrees(math.atan2(p.x - self.x, p.z - self.z))
        self.yaw += ang_diff(want, self.yaw) * min(1.0, dt * rate)

    def _clamp(self):
        x0, x1, z0, z1 = self.bounds
        self.x = min(x1 - 0.5, max(x0 + 0.5, self.x))
        self.z = min(z1 - 0.5, max(z0 + 0.5, self.z))
        self.x, self.z = self.g.phys.resolve(self.x, self.z, 0.35, 0.0, 1.0, include_dynamic=False)

    def take_hit(self, n, kind, from_pos):
        if not self.alive or self.state == "flutter" or not self.active:
            return
        g = self.g
        self.hp -= n
        g.audio.play("squawk", vol=1.0, pos=self.center(), rng=40)
        g.audio.play("punch", vol=0.7)
        self.fx.append(Feathers(self.center()))
        dx, dz = self.x - from_pos[0], self.z - from_pos[2]
        d = math.hypot(dx, dz) or 1
        self.x += dx / d * 1.6
        self.z += dz / d * 1.6
        self._clamp()
        g.ui.set_boss("CLUCK NORRIS", max(0, self.hp) / self.MAX_HP)
        if self.hp <= 0:
            self.alive = False
            self.state = "down"
            if self.on_defeat:
                self.on_defeat()
            return
        self.state = "hurt"
        self.t = 0.55

    def update(self, dt):
        for f in self.fx:
            f.update(dt)
        self.fx = [f for f in self.fx if f.alive]
        g = self.g
        p = g.player
        spd = 0.0
        if not self.active:
            self.model.animate(dt, 0.0, False)
            self._apply()
            return
        self.t -= dt
        dist = math.hypot(p.x - self.x, p.z - self.z)
        if self.state == "down":
            self.model.rig.rotation_z = min(90, self.model.rig.rotation_z + dt * 300)
        elif self.state == "idle":
            # strut sideways, keep a respectful distance, then go
            self._face_player(dt)
            side = math.radians(self.yaw + 90)
            step = math.sin(g.env.time * 2.0) * 1.4 * dt
            self.x += math.sin(side) * step
            self.z += math.cos(side) * step
            if dist > 4.5:
                fx, fz = (p.x - self.x) / dist, (p.z - self.z) / dist
                self.x += fx * 2.2 * dt
                self.z += fz * 2.2 * dt
                spd = 2.2
            if self.t <= 0:
                if random.random() < 0.3 and dist < 7:
                    self.state = "flutter_up"
                    self.t = 0.35
                else:
                    self.state = "windup"
                    self.t = 0.7
                    g.audio.play("cluck_2", vol=0.9, pos=self.center(), rng=30)
        elif self.state == "windup":
            if self.t > 0.3:
                self._face_player(dt, 10)
            self.model.head.rotation_x = 35
            self.model.rig.x = math.sin(g.env.time * 40) * 0.03
            if self.t <= 0:
                yr = math.radians(self.yaw)
                self.dash_dir = (math.sin(yr), math.cos(yr))
                self.state = "dash"
                self.t = 0.55
                self.hit_player = False
                g.audio.play("whoosh", vol=0.6, pos=self.center(), rng=25)
        elif self.state == "dash":
            self.x += self.dash_dir[0] * 10.0 * dt
            self.z += self.dash_dir[1] * 10.0 * dt
            spd = 10.0
            if not self.hit_player and dist < 1.0:
                self.hit_player = True
                p.damage(1, (self.x, 0, self.z))
            if self.t <= 0:
                self.state = "dizzy"
                self.t = 1.3
        elif self.state == "dizzy":
            self.model.head.rotation_y = math.sin(g.env.time * 14) * 30
            if self.t <= 0:
                self.model.head.rotation_y = 0
                self.state = "idle"
                self.t = random.uniform(1.0, 1.8)
        elif self.state == "flutter_up":
            self._face_player(dt, 10)
            if self.t <= 0:
                self.state = "flutter"
                self.vy = 7.0
                tx, tz = p.x, p.z
                self.dash_dir = ((tx - self.x) / 0.9, (tz - self.z) / 0.9)
                g.audio.play("squawk", vol=0.8, pos=self.center(), rng=30)
        elif self.state == "flutter":
            self.vy -= 16 * dt
            self.y += self.vy * dt
            self.x += self.dash_dir[0] * dt
            self.z += self.dash_dir[1] * dt
            if self.y <= 0:
                self.y = 0.0
                g.audio.play("thump", vol=0.7, pos=self.center(), rng=25)
                self.fx.append(Feathers(self.center(), col=(0.6, 0.5, 0.35, 1), n=6))
                if math.hypot(p.x - self.x, p.z - self.z) < 1.6:
                    p.damage(1, (self.x, 0, self.z))
                self.state = "dizzy"
                self.t = 1.0
        elif self.state == "hurt":
            if self.t <= 0:
                self.state = "idle"
                self.t = random.uniform(0.6, 1.2)
        if self.state != "windup":
            self.model.rig.x = 0
            if self.state != "dizzy":
                self.model.head.rotation_x *= 0.9
        self._clamp()
        self.model.animate(dt, spd, False)
        self._apply()

    def _apply(self):
        self.model.position = (self.x, self.y, self.z)
        self.model.rotation_y = self.yaw


# ---------------------------------------------------------------------------
# things Chuck throws
# ---------------------------------------------------------------------------

class Thrown:
    def __init__(self, g, kind, start, target, flight=1.0):
        self.g = g
        self.kind = kind
        self.pos = list(start)
        self.t = 0.0
        self.T = flight
        self.start = start
        self.target = target
        self.ent = models.item_model(kind, position=start, scale=1.4)
        self.alive = True
        # a marker on the ground so the player can see where it will land
        mb = MeshBuilder().disk((0, 0, 0), 0.9, 0.9, color=(0.9, 0.2, 0.15, 0.55), segs=20, uv_rect=models.WHITE)
        self.mark = Entity(model=mb.build(), texture=tex("atlas"), shader=FARM_SHADER,
                           position=(target[0], 0.04, target[2]))
        self.mark.set_shader_input("u_unlit", 1.0)
        self.mark.setTransparency(True)
        no_shadow(self.mark)

    def update(self, dt):
        self.t += dt
        k = min(1.0, self.t / self.T)
        x = self.start[0] + (self.target[0] - self.start[0]) * k
        z = self.start[2] + (self.target[2] - self.start[2]) * k
        y = self.start[1] + (0.05 - self.start[1]) * k + 4.5 * k * (1 - k)
        self.ent.position = (x, y, z)
        self.ent.rotation_x += dt * 400
        self.mark.scale = 0.6 + 0.4 * k
        if k >= 1.0:
            g = self.g
            p = g.player
            g.audio.play("crash", vol=0.8, pos=(x, 0.3, z), rng=40)
            if math.hypot(p.x - x, p.z - z) < 1.3:
                p.damage(1, (x, 0, z))
            self.remove()

    def remove(self):
        if self.alive:
            destroy(self.ent)
            destroy(self.mark)
        self.alive = False


# ---------------------------------------------------------------------------
# Chuck, final round
# ---------------------------------------------------------------------------

BOSS_TAUNTS = ["Nobody's leavin'!", "Get back in that pasture!", "I raised you from a CALF!",
               "Do you know what a tractor COSTS?!", "Dale's gonna hear about this!", "Hold STILL!"]
BOSS_STUCK = ["Dang it!", "C'mon, come OUT!", "Stupid... fork...", "Gimme a second here!"]
BOSS_HURT = ["OW!", "Hey!", "That's my KIDNEY!", "Oof!", "Ow, my back!"]
BOSS_THROW = ["Catch!", "Here, have a BUCKET!", "Milk can! Fresh!", "Incoming!"]


class ChuckBoss(Enemy):
    MAX_HP = 12
    radius = 0.55
    height = 1.9

    def __init__(self, g, arena, on_phase3=None):
        self.g = g
        self.f = g.farmer
        self.arena = arena          # x0, x1, z0, z1
        self.hp = self.MAX_HP
        self.phase = 1
        self.state = "approach"
        self.t = 1.5
        self.alive = True
        self.on_phase3 = on_phase3
        self.lunge_dir = (0.0, 0.0)
        self.hit_player = False
        self.throws = 0
        self.thrown: list[Thrown] = []
        self.fx: list = []
        self.block_cd = 0.0
        self.stun_reason = ""
        self.finished = False

    @property
    def x(self):
        return self.f.x

    @property
    def z(self):
        return self.f.z

    @property
    def y(self):
        return self.f.y

    def vulnerable(self):
        return self.state in ("stuck", "stunned", "fallen", "winded")

    def remove(self):
        for t in self.thrown:
            t.remove()
        self.thrown = []
        for f in self.fx:
            for e, _ in f.parts:
                destroy(e)
        self.fx = []

    def stun(self, dur, reason="stunned", pose="ow"):
        if self.finished:
            return
        self.state = "stunned"
        self.stun_reason = reason
        self.t = dur
        self.f.pose = pose

    def take_hit(self, n, kind, from_pos):
        if not self.alive or self.finished:
            return
        g = self.g
        f = self.f
        if not self.vulnerable():
            # he swats you away with the pitchfork handle
            if self.block_cd <= 0:
                self.block_cd = 1.0
                g.audio.play("metal_clang", vol=0.6, pos=self.center(), rng=30)
                f.say(random.choice(["Ha! Missed!", "Nice try!", "Not today!"]), kind="laugh", force=True)
                p = g.player
                dx, dz = p.x - f.x, p.z - f.z
                d = math.hypot(dx, dz) or 1
                p.vx += dx / d * 7
                p.vz += dz / d * 7
            return
        self.hp -= n
        g.audio.play("punch", vol=0.9)
        f.say(random.choice(BOSS_HURT), kind="ow", force=True)
        self.fx.append(Feathers(self.center(), col=(0.95, 0.9, 0.8, 1), n=6))
        g.ui.set_boss("CHUCK", max(0, self.hp) / self.MAX_HP)
        g.stats["boss_hits"] = g.stats.get("boss_hits", 0) + 1
        if self.phase == 1 and self.hp <= 8:
            self.phase = 2
            self.state = "retreat"
            self.t = 2.0
            f.say("Okay. OKAY. You wanna play rough?", force=True)
        elif self.phase == 2 and self.hp <= 4:
            self.phase = 3
            self.finished = True
            self.state = "done"
            if self.on_phase3:
                self.on_phase3()

    def _move_toward(self, tx, tz, speed, dt):
        f = self.f
        dx, dz = tx - f.x, tz - f.z
        d = math.hypot(dx, dz)
        if d < 0.05:
            return 0.0
        step = min(d, speed * dt)
        want = math.degrees(math.atan2(dx, dz))
        f.yaw += ang_diff(want, f.yaw) * min(1, dt * 8)
        f.x, f.z = self.g.phys.move(f.x, f.z, dx / d * step, dz / d * step, 0.45, 0, 1.8, ignore=f.col,
                                    include_dynamic=False)
        self._clamp()
        return speed

    def _clamp(self):
        x0, x1, z0, z1 = self.arena
        f = self.f
        f.x = min(x1, max(x0, f.x))
        f.z = min(z1, max(z0, f.z))

    def _face(self, tx, tz, dt, rate=6):
        f = self.f
        want = math.degrees(math.atan2(tx - f.x, tz - f.z))
        f.yaw += ang_diff(want, f.yaw) * min(1, dt * rate)

    def update(self, dt):
        g = self.g
        f = self.f
        p = g.player
        for t in self.thrown:
            t.update(dt)
        self.thrown = [t for t in self.thrown if t.alive]
        for fx in self.fx:
            fx.update(dt)
        self.fx = [fx for fx in self.fx if fx.alive]
        self.block_cd = max(0.0, self.block_cd - dt)
        self.t -= dt
        dist = math.hypot(p.x - f.x, p.z - f.z)
        spd = 0.0
        st = self.state
        if st == "done":
            pass
        elif st == "approach":
            f.pose = "walk"
            if dist > 3.2:
                spd = self._move_toward(p.x, p.z, 3.3 if self.phase == 1 else 2.6, dt)
            else:
                self._face(p.x, p.z, dt)
            if self.t <= 0 and dist < 7:
                self.state = "windup"
                self.t = 0.8
                f.pose = "windup"
                if random.random() < 0.5:
                    f.say(random.choice(BOSS_TAUNTS), force=True)
            elif self.t <= 0:
                self.t = 0.5
        elif st == "windup":
            # he tracks you, then commits to a direction for the last moment: dodge on the tell
            if self.t > 0.35:
                self._face(p.x, p.z, dt, 10)
            f.pose = "windup"
            if self.t <= 0:
                yr = math.radians(f.yaw)
                self.lunge_dir = (math.sin(yr), math.cos(yr))
                self.state = "lunge"
                self.t = 0.45
                self.hit_player = False
                f.pose = "lunge"
                g.audio.play("whoosh", vol=0.8, pos=self.center(), rng=30)
        elif st == "lunge":
            f.pose = "lunge"
            f.x += self.lunge_dir[0] * 9.0 * dt
            f.z += self.lunge_dir[1] * 9.0 * dt
            f.x, f.z = g.phys.resolve(f.x, f.z, 0.45, 0, 1.8, ignore=f.col, include_dynamic=False)
            self._clamp()
            # the pitchfork tips reach about a metre ahead of him
            tipx, tipz = f.x + self.lunge_dir[0] * 1.2, f.z + self.lunge_dir[1] * 1.2
            if not self.hit_player and math.hypot(p.x - tipx, p.z - tipz) < 0.85:
                self.hit_player = True
                p.damage(1, (f.x, 0, f.z))
            if self.t <= 0:
                if self.hit_player:
                    self.state = "approach"
                    self.t = 1.6
                else:
                    self.state = "stuck"
                    self.t = 2.6
                    f.pose = "stuck"
                    g.audio.play("thump", vol=0.8, pos=self.center(), rng=30)
                    f.say(random.choice(BOSS_STUCK), force=True)
        elif st == "stuck":
            f.pose = "stuck"
            if self.t <= 0:
                self.state = "approach" if self.phase == 1 else "retreat"
                self.t = 1.5
        elif st == "retreat":
            # back off to throw things
            f.pose = "walk"
            ax, az = f.x - p.x, f.z - p.z
            d = math.hypot(ax, az) or 1
            if dist < 9:
                spd = self._move_toward(f.x + ax / d * 3, f.z + az / d * 3, 3.0, dt)
            else:
                self._face(p.x, p.z, dt)
            if self.t <= 0:
                self.state = "throw_windup"
                self.t = 0.6
                f.pose = "throw"
                f.model.pose_t = 0.0
        elif st == "throw_windup":
            self._face(p.x, p.z, dt, 10)
            f.pose = "throw"
            if self.t <= 0:
                kind = random.choice(["bucket", "rock", "radio", "boot"])
                # lead the target a little
                tx = p.x + p.vx * 0.5 + random.uniform(-0.6, 0.6)
                tz = p.z + p.vz * 0.5 + random.uniform(-0.6, 0.6)
                self.thrown.append(Thrown(g, kind, (f.x, 1.8, f.z), (tx, 0, tz), flight=max(0.8, dist / 9)))
                g.audio.play("whoosh", vol=0.7, pos=self.center(), rng=30)
                if random.random() < 0.5:
                    f.say(random.choice(BOSS_THROW), force=True)
                self.throws += 1
                if self.throws % 3 == 0:
                    self.state = "winded"
                    self.t = 3.0
                    f.say("Hoo... hang on... gotta... catch my breath...", force=True)
                elif dist < 4.5:
                    self.state = "windup"
                    self.t = 0.7
                else:
                    self.state = "retreat"
                    self.t = 0.9
        elif st == "winded":
            f.pose = "hurt"
            if self.t <= 0:
                self.state = "approach"
                self.t = 1.0
        elif st == "stunned":
            if self.t <= 0:
                self.state = "approach" if self.phase == 1 else "retreat"
                self.t = 1.2
        elif st == "fallen":
            f.pose = "fallen"
            if self.t <= 0:
                self.state = "retreat" if self.phase == 2 else "approach"
                self.t = 1.2
        f._apply()
        f.model.animate(dt, spd, f.pose)
