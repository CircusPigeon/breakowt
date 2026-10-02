"""The JOHN STEER, driven by a cow."""
from __future__ import annotations

import math
import random

from ursina import Entity, camera, destroy, held_keys, mouse

from . import models
from .engine.meshbuilder import MeshBuilder
from .engine.shading import FARM_SHADER
from .engine.assets import tex
from .npc import ang_diff

MAX_SPEED = 9.5
REVERSE_SPEED = 3.0
RADIUS = 1.25


class Puff:
    def __init__(self, pos):
        mb = MeshBuilder().sphere((0, 0, 0), 0.18, color=(0.25, 0.25, 0.27, 1), segs=6, rings=4)
        self.e = Entity(model=mb.build(solid_rect=models.WHITE), texture=tex("atlas"), shader=FARM_SHADER,
                        position=pos)
        self.t = 0.0
        self.alive = True

    def update(self, dt):
        self.t += dt
        self.e.y += dt * 1.4
        self.e.scale = 1 + self.t * 2.5
        if self.t > 1.1:
            self.remove()

    def remove(self):
        if self.alive:
            destroy(self.e)
        self.alive = False


class Tractor:
    """Driving mode. The tractor entity is the one the world built; we move it around."""

    def __init__(self, g, ent, on_smash=None):
        self.g = g
        self.ent = ent
        self.x, self.z = ent.x, ent.z
        self.yaw = ent.rotation_y
        self.speed = 0.0
        self.look_yaw = 0.0
        self.look_pitch = 8.0
        self.seat = Entity(parent=ent, position=(0, 2.35, -0.55))
        self.puffs: list[Puff] = []
        self.puff_t = 0.0
        self.shake = 0.0
        self.on_smash = on_smash
        self.smashables: list = []     # (name, [doors])
        self.active = False
        self.bump_cd = 0.0

    # ------------------------------------------------------------------
    def enter(self):
        g = self.g
        self.active = True
        g.vehicle = self
        p = g.player
        p.driving = True
        p.frozen = False
        col = g.world.colliders.get("tractor")
        if col is not None:
            col.enabled = False
        fl = getattr(g.world, "tractor_floor", None)
        if fl is not None:
            fl.enabled = False
        camera.parent = self.seat
        camera.position = (0, 0, 0)
        camera.rotation = (0, 0, 0)
        if p.held:
            p.held.enabled = False
        p.snout.enabled = True
        g.audio.play("tractor_start", vol=1.0)
        g.audio.loop("tractor", "loop_tractor", vol=0.8, pos=(self.x, 1.5, self.z), rng=90, group="sfx")

    def leave(self):
        g = self.g
        self.active = False
        g.vehicle = None
        p = g.player
        p.driving = False
        g.audio.stop_loop("tractor", 1.0)
        camera.parent = p.head
        camera.position = (0, 0, 0)
        camera.rotation = (0, 0, 0)
        if p.held:
            p.held.enabled = True
        for pf in self.puffs:
            pf.remove()
        self.puffs = []

    def input(self, key):
        return False

    # ------------------------------------------------------------------
    def update(self, dt):
        if not self.active:
            return
        g = self.g
        controls = g.controls_enabled()
        thr = steer = 0.0
        if controls:
            thr = (held_keys["w"] + held_keys["up arrow"]) - (held_keys["s"] + held_keys["down arrow"])
            steer = (held_keys["d"] + held_keys["right arrow"]) - (held_keys["a"] + held_keys["left arrow"])
            thr = max(-1, min(1, thr))
            steer = max(-1, min(1, steer))
            if mouse.locked:
                mv = mouse.velocity
                self.look_yaw = max(-110, min(110, self.look_yaw + mv[0] * 42 * g.player.sensitivity))
                self.look_pitch = max(-30, min(45, self.look_pitch - mv[1] * 42 * g.player.sensitivity *
                                               (-1 if g.player.invert_y else 1)))
        # the head drifts back to looking ahead while driving
        if abs(self.speed) > 2 and abs(thr) > 0:
            self.look_yaw *= max(0.0, 1 - dt * 1.2)
        target = thr * (MAX_SPEED if thr > 0 else REVERSE_SPEED)
        acc = 5.0 if abs(target) > abs(self.speed) else 7.0
        self.speed += max(-acc * dt, min(acc * dt, target - self.speed))
        turn = steer * 55.0 * max(-1.0, min(1.0, self.speed / 3.0))
        self.yaw += turn * dt
        yr = math.radians(self.yaw)
        fx, fz = math.sin(yr), math.cos(yr)
        dx, dz = fx * self.speed * dt, fz * self.speed * dt
        # smash through gates and doors that are in the way
        self._check_smash(fx, fz)
        # a tractor rolls over cattle grids and through barrels, buckets and milk cans
        from .engine.physics import Circle
        ignored = []
        grid = g.world.colliders.get("cattle_grid")
        if grid is not None and grid.enabled:
            ignored.append(grid)
        for sh in g.phys.nearby(self.x - 3, self.x + 3, self.z - 3, self.z + 3):
            if isinstance(sh, Circle) and sh.enabled and sh.r <= 0.6:
                ignored.append(sh)
        for sh in ignored:
            sh.enabled = False
        ox, oz = self.x, self.z
        self.x, self.z = g.phys.move(self.x, self.z, dx, dz, RADIUS, 0.0, 2.2, include_dynamic=False)
        for sh in ignored:
            sh.enabled = True
        for k in g.knockables:
            if not k["down"] and math.hypot(k["x"] - self.x, k["z"] - self.z) < RADIUS + 0.6 and abs(self.speed) > 1:
                g.knock(k)
        moved = math.hypot(self.x - ox, self.z - oz)
        want = math.hypot(dx, dz)
        self.bump_cd = max(0.0, self.bump_cd - dt)
        if want > 0.05 and moved < want * 0.35 and abs(self.speed) > 3 and self.bump_cd <= 0:
            self.speed *= -0.25
            self.shake = 0.4
            self.bump_cd = 0.6
            g.audio.play("thump", vol=0.9)
        self.ent.position = (self.x, 0, self.z)
        self.ent.rotation_y = self.yaw
        rumble = 0.012 + abs(self.speed) * 0.002
        self.ent.rotation_z = math.sin(g.env.time * 31) * rumble * 20
        self.shake = max(0.0, self.shake - dt)
        self.seat.rotation_y = self.look_yaw
        self.seat.rotation_x = self.look_pitch + random.uniform(-1, 1) * self.shake * 5
        # the player rides along (AI, zones and audio all follow)
        p = g.player
        p.x, p.z = self.x, self.z
        p.y = 0.0
        p.yaw = self.yaw + self.look_yaw
        p.col.x, p.col.z = self.x, self.z
        p.root.position = (self.x, 0, self.z)
        g.audio.set_loop("tractor", pos=(self.x, 1.5, self.z), pitch=0.8 + abs(self.speed) / MAX_SPEED * 0.5)
        # exhaust
        self.puff_t -= dt
        if self.puff_t <= 0:
            self.puff_t = 0.25 if abs(thr) > 0 else 0.6
            # the exhaust stack sits at (0.3, 2.7, 1.3) in the tractor's own space
            ex = self.ent.world_position + self.ent.right * 0.3 + self.ent.forward * 1.3 + (0, 2.7, 0)
            self.puffs.append(Puff(ex))
        for pf in self.puffs:
            pf.update(dt)
        self.puffs = [pf for pf in self.puffs if pf.alive]

    def _check_smash(self, fx, fz):
        if abs(self.speed) < 2.5:
            return
        g = self.g
        nx, nz = self.x + fx * 2.3, self.z + fz * 2.3
        for name, doors in self.smashables:
            for d in doors:
                c = d.col
                if not c.enabled:
                    continue
                if c.x0 - 0.6 <= nx <= c.x1 + 0.6 and c.z0 - 0.6 <= nz <= c.z1 + 0.6:
                    for dd in doors:
                        dd.set_open(True)
                    g.audio.play("gate_smash", vol=1.0)
                    g.audio.play("wood_crack", vol=0.8)
                    self.shake = 0.8
                    self.speed *= 0.7
                    if self.on_smash:
                        self.on_smash(name)
                    break
