"""Cows: named friends, the herd, and the hens."""
from __future__ import annotations

import math
import random

from ursina import Entity, Text, color, destroy, scene

from .interact import Interactable
from . import models
from .world import PASTURE, in_pond, OAK

FRIENDS = {
    # key: (display name, voice, model kwargs, ear tag)
    "cowleen": ("Cowleen", "cowleen", dict(hide="hide_brown", acc=("daisy",), bell=True), "tag_blank"),
    "moozart": ("Moozart", "moozart", dict(hide="hide_black", acc=("wig",), bell=True), "tag_12_mud"),
    "sirloin": ("Sir Loin", "sirloin", dict(hide="hide_red", bull=True, acc=("cape",)), "tag_blank"),
    "cowpernicus": ("Cowpernicus", "cowpernicus", dict(hide="hide_dun", acc=("bowtie",), bell=True), "tag_blank"),
    "mooriarty": ("Mooriarty", "mooriarty", dict(hide="hide_bw", acc=("fedora",)), "tag_blank"),
    "moomaw": ("Moomaw", "moomaw", dict(hide="hide_gray", acc=("shawl", "bonnet"), bell=True), "tag_blank"),
}


def ang_diff(a, b):
    return (a - b + 180) % 360 - 180


class Bubble:
    """A literal 'MOO' floating over a speaker's head."""

    def __init__(self, parent, text, y=2.35, col=None, life=2.0):
        self.ent = Text(text, parent=parent, position=(0, y, 0), origin=(0, 0), scale=22, billboard=True,
                        color=col or color.rgba(1, 1, 0.95, 1))
        self.life = life
        self.t = 0.0
        self.alive = True

    def update(self, dt):
        self.t += dt
        self.ent.y += dt * 0.12
        s = 22 * (1 + 0.25 * max(0, 0.15 - self.t) / 0.15)
        self.ent.scale = s
        if self.t > self.life:
            destroy(self.ent)
            self.alive = False


class Walker:
    """Shared movement logic: path following with collisions."""

    def __init__(self, g, x, z, yaw, radius):
        self.g = g
        self.x, self.y, self.z = x, 0.0, z
        self.yaw = yaw
        self.radius = radius
        self.path: list = []
        self.walk_speed = 2.0
        self.cur_speed = 0.0
        self.face_target = None
        self.trail_fn = None
        self.follow_dist = 3.0
        self.stuck_t = 0.0

    def goto(self, target, speed=2.0):
        tx, tz = target[0], target[2] if len(target) > 2 else target[1]
        ty = target[1] if len(target) > 2 else 0.0
        self.path = self.g.world.find_path((self.x, self.y, self.z), (tx, ty, tz))
        self.walk_speed = speed
        self.trail_fn = None
        self.stuck_t = 0.0

    def stop(self):
        self.path = []
        self.trail_fn = None

    @property
    def moving(self):
        return bool(self.path) or self.trail_fn is not None

    def arrived(self, tol=0.8):
        return not self.path

    def _step(self, dt, col=None):
        spd_target = 0.0
        if self.trail_fn is not None:
            tx, ty, tz = self.trail_fn()
            d = math.hypot(tx - self.x, tz - self.z)
            if d > self.follow_dist:
                if not self.path or math.hypot(self.path[-1][0] - tx, self.path[-1][2] - tz) > 2.0:
                    self.path = self.g.world.find_path((self.x, self.y, self.z), (tx, ty, tz))
                spd_target = self.walk_speed * (1.4 if d > self.follow_dist * 2.5 else 1.0)
            else:
                self.path = []
        elif self.path:
            spd_target = self.walk_speed
        if self.path:
            nx, ny, nz = self.path[0]
            dx, dz = nx - self.x, nz - self.z
            d = math.hypot(dx, dz)
            if d < 0.5:
                self.path.pop(0)
            else:
                want = math.degrees(math.atan2(dx, dz))
                self.yaw += ang_diff(want, self.yaw) * min(1, dt * 6)
                self.cur_speed += (spd_target - self.cur_speed) * min(1, dt * 4)
                step = min(d, self.cur_speed * dt)
                ox, oz = self.x, self.z
                self.x, self.z = self.g.phys.move(self.x, self.z, dx / d * step, dz / d * step, self.radius,
                                                  self.y, 1.5, ignore=col)
                moved = math.hypot(self.x - ox, self.z - oz)
                if moved < step * 0.2 and step > 0.01:
                    self.stuck_t += dt
                    if self.stuck_t > 1.2:
                        # nudge sideways, then skip the waypoint if still stuck
                        self.x += math.cos(math.radians(self.yaw)) * 0.3
                        if self.stuck_t > 2.5:
                            self.path.pop(0)
                            self.stuck_t = 0.0
                else:
                    self.stuck_t = max(0.0, self.stuck_t - dt)
                gh, _ = self.g.phys.ground(self.x, self.z, self.y)
                self.y += (gh - self.y) * min(1, dt * 10)
                return moved / dt if dt > 0 else 0
        else:
            self.cur_speed = 0.0
            if self.face_target is not None:
                fx, fz = self.face_target
                want = math.degrees(math.atan2(fx - self.x, fz - self.z))
                self.yaw += ang_diff(want, self.yaw) * min(1, dt * 3)
        gh, _ = self.g.phys.ground(self.x, self.z, self.y)
        self.y += (gh - self.y) * min(1, dt * 10)
        return 0.0


class NPCCow(Walker):
    def __init__(self, g, key, pos=(0, 0, 0), yaw=0.0):
        name, voice, mkw, tag = FRIENDS[key]
        super().__init__(g, pos[0], pos[2], yaw, 0.8)
        self.key = key
        self.name = name
        self.voice = voice
        self.model = models.CowModel(tag=tag, **mkw)
        self.col = g.phys.add_dynamic(self.x, self.z, 0.8, 0, 1.6, owner=self)
        self.look = "player"
        self.graze = False
        self.bubbles: list[Bubble] = []
        self.visible = True
        self.ia = g.ia.add(Interactable(f"cow_{key}", (0, 0, 0), 0.9, name, None, f"Talk to {name}", 2.8,
                                        follow=lambda: (self.x, self.y + 1.3, self.z)))
        self.idle_moo_t = random.uniform(20, 60)
        self._apply()

    def teleport(self, pos, yaw=None):
        self.x, self.z = pos[0], pos[2] if len(pos) > 2 else pos[1]
        self.y = pos[1] if len(pos) > 2 else 0.0
        if len(pos) > 3 and yaw is None:
            yaw = pos[3]
        if yaw is not None:
            self.yaw = yaw
        self.path = []
        self.trail_fn = None
        self._apply()

    def set_visible(self, v):
        self.visible = v
        self.model.enabled = v
        self.col.enabled = v
        self.ia.enabled = v

    def follow(self, fn, dist=3.0, speed=2.6):
        self.trail_fn = fn
        self.follow_dist = dist
        self.walk_speed = speed

    def bubble(self, text, life=2.2):
        self.bubbles.append(Bubble(self.model, text, y=2.4 if not self.model.bull else 2.6, life=life))
        self.model.talk_t = 0.9

    def _apply(self):
        self.model.position = (self.x, self.y, self.z)
        self.model.rotation_y = self.yaw
        self.col.x, self.col.z = self.x, self.z

    def update(self, dt):
        if not self.visible:
            return
        spd = self._step(dt, self.col)
        self._apply()
        p = self.g.player
        look = None
        if self.look == "player":
            if math.hypot(p.x - self.x, p.z - self.z) < 9:
                look = (p.x, p.z)
        elif isinstance(self.look, tuple):
            look = self.look
        self.model.graze_target = 1.0 if (self.graze and spd < 0.1 and look is None) else 0.0
        self.model.animate(dt, spd, look)
        for b in self.bubbles:
            b.update(dt)
        self.bubbles = [b for b in self.bubbles if b.alive]
        self.idle_moo_t -= dt
        if self.idle_moo_t <= 0:
            self.idle_moo_t = random.uniform(25, 70)
            if not self.g.in_dialogue:
                self.g.audio.play(f"moo_{self.voice}_{random.choice(['short', 'medium'])}_{random.randrange(2)}",
                                  vol=0.6, pos=(self.x, 1.5, self.z), rng=35, group="voice")


HERD_NAMES = ["Clarabelle", "Buttercup", "Brie", "Moozie", "Cud-ney", "Moo-ana", "Beefany", "Barb Wire",
              "Milky Joe", "Daisy Duke", "Heifer Lock", "Cow-lin Firth", "Lactose Tolerant", "Moo-donna",
              "Steer Crow", "Udderly Amazing", "Madame Moo-ssaud", "Bovine Wonder", "Hay-ley", "Moo-lissa",
              "Cow-abunga", "Miss Moo-ppet", "Moogan", "Chew-bacca", "Moo-riel"]

HERD_HIDES = ["hide_bw", "hide_bw", "hide_brown", "hide_black", "hide_gray", "hide_red", "hide_dun", "hide_bw"]


class HerdCow(Walker):
    def __init__(self, g, idx, pos, yaw):
        super().__init__(g, pos[0], pos[1], yaw, 0.8)
        self.idx = idx
        self.name = HERD_NAMES[idx % len(HERD_NAMES)] if idx < len(HERD_NAMES) else f"Cow #{idx + 60}"
        self.model = models.CowModel(hide=random.choice(HERD_HIDES), bell=True, tag="tag_blank",
                                     horns=random.random() < 0.2)
        self.col = g.phys.add_dynamic(self.x, self.z, 0.85, 0, 1.6, owner=self)
        self.state = "graze"
        self.timer = random.uniform(2, 12)
        self.area = PASTURE
        self.free = False
        self.pitch = random.uniform(0.9, 1.15)
        self.voice = f"moo_herd_{random.randrange(10)}"
        self.ia = g.ia.add(Interactable(f"herd_{idx}", (0, 0, 0), 0.9, self.name, None, f"Talk to {self.name}", 2.6,
                                        follow=lambda: (self.x, self.y + 1.3, self.z)))
        self.bubbles = []
        self.lie = random.random() < 0.15
        self.model.lying_target = 1.0 if self.lie else 0.0
        self.far = False
        self._apply()

    def _apply(self):
        self.model.position = (self.x, self.y, self.z)
        self.model.rotation_y = self.yaw
        self.col.x, self.col.z = self.x, self.z

    def bubble(self, text, life=2.2):
        self.bubbles.append(Bubble(self.model, text, life=life))
        self.model.talk_t = 0.9

    def random_target(self):
        x0, x1, z0, z1 = self.area
        for _ in range(12):
            x = min(x1 - 2, max(x0 + 2, self.x + random.uniform(-12, 12)))
            z = min(z1 - 2, max(z0 + 2, self.z + random.uniform(-12, 12)))
            if not in_pond(x, z, 1.5) and not self.g.phys.blocked_at(x, z, 1.0) and \
                    not (-66 < x < -38 and -12 < z < 3):
                return (x, 0, z)
        return None

    def update(self, dt, cam_x, cam_z):
        d_cam = math.hypot(cam_x - self.x, cam_z - self.z)
        self.far = d_cam > 80
        self.timer -= dt
        spd = 0.0
        if self.state == "walk":
            if self.path:
                spd = self._step(dt, self.col)
            else:
                self.state = "graze"
                self.timer = random.uniform(4, 14)
        elif self.state == "stampede":
            spd = self._step(dt, self.col)
            if not self.path:
                self.state = "graze"
                self.timer = 999
        else:
            self._step(dt, self.col)
            if self.timer <= 0 and not self.free:
                if self.lie and random.random() < 0.7:
                    self.timer = random.uniform(10, 25)
                else:
                    self.lie = random.random() < 0.12
                    self.model.lying_target = 1.0 if self.lie else 0.0
                    if not self.lie:
                        t = self.random_target()
                        if t:
                            self.path = [t]
                            self.walk_speed = random.uniform(0.9, 1.5)
                            self.state = "walk"
                    self.timer = random.uniform(6, 16)
        # avoid Chuck: shuffle out of his way
        fm = self.g.farmer
        if fm is not None and fm.visible and self.state != "stampede":
            fd = math.hypot(fm.x - self.x, fm.z - self.z)
            if fd < 2.4 and self.state != "walk":
                ax, az = self.x - fm.x, self.z - fm.z
                self.path = [(self.x + ax / max(fd, 0.1) * 3, 0, self.z + az / max(fd, 0.1) * 3)]
                self.state = "walk"
                self.walk_speed = 2.0
                self.lie = False
                self.model.lying_target = 0.0
        self._apply()
        if not self.far:
            p = self.g.player
            look = (p.x, p.z) if math.hypot(p.x - self.x, p.z - self.z) < 6 else None
            self.model.graze_target = 1.0 if (spd < 0.1 and look is None and not self.lie) else 0.0
            self.model.animate(dt, spd, look)
            for b in self.bubbles:
                b.update(dt)
            self.bubbles = [b for b in self.bubbles if b.alive]
            if random.random() < dt / 45:
                self.g.audio.play(self.voice, vol=0.5, pitch=self.pitch, pos=(self.x, 1.4, self.z), rng=40, group="voice")


class Hen(Walker):
    def __init__(self, g, pos):
        super().__init__(g, pos[0], pos[1], random.uniform(0, 360), 0.25)
        self.model = models.RoosterModel()
        for c in self.model.rig.children + self.model.head.children:
            c.color = color.rgba(1, 1, 0.95, 1)
        self.model.scale = 0.75
        self.timer = random.uniform(1, 4)
        self.peck = False

    def update(self, dt):
        self.timer -= dt
        if self.timer <= 0:
            self.timer = random.uniform(1.5, 5)
            if random.random() < 0.5:
                self.path = [(random.uniform(36, 50), 0, random.uniform(-40, -26))]
                self.walk_speed = 1.2
                self.peck = False
            else:
                self.path = []
                self.peck = random.random() < 0.6
            if random.random() < 0.25:
                self.g.audio.play(f"cluck_{random.randrange(3)}", vol=0.35, pos=(self.x, 0.5, self.z), rng=25)
        spd = self._step(dt)
        self.model.position = (self.x, self.y, self.z)
        self.model.rotation_y = self.yaw
        self.model.animate(dt, spd, self.peck and spd < 0.1)
