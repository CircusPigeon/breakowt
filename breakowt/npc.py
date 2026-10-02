"""Cows: named friends, the herd, and the hens."""
from __future__ import annotations

import math
import random

from panda3d.core import BitMask32
from ursina import Entity, Text, camera, color, destroy, scene

from .engine.shading import SHADOW_MASK

MAIN_MASK = BitMask32.bit(0)     # the main camera's mask (see Environment)
from .interact import Interactable
from . import models
from .world import PASTURE, in_pond, OAK, MOOHOLE, GATE_PASTURE

# spots the herd must never park in: the gap under the fence and the pasture gate.
# A cow standing there plugs the only way through, and the player can't push cows.
KEEP_CLEAR = [(MOOHOLE[0], (MOOHOLE[1] + MOOHOLE[2]) / 2, 4.5),
              (GATE_PASTURE[0], (GATE_PASTURE[1] + GATE_PASTURE[2]) / 2, 5.0)]


def in_keep_clear(x, z, pad=0.0):
    return any(math.hypot(x - kx, z - kz) < r + pad for kx, kz, r in KEEP_CLEAR)

FRIENDS = {
    # key: (display name, voice, model kwargs, ear tag)
    "cowleen": ("Moocrates", "cowleen", dict(hide="hide_brown", acc=("daisy",), bell=True), "tag_blank"),
    # the key stays "moozart" (sounds, flags and saves use it); on screen he's Archimoodes, the logician
    "moozart": ("Archimoodes", "moozart", dict(hide="hide_black", acc=("bowtie",), bell=True), "tag_12_mud"),
    "sirloin": ("Moogenes", "sirloin", dict(hide="hide_red", bull=True, acc=("cape",)), "tag_blank"),
    "cowpernicus": ("Moothagoras", "cowpernicus", dict(hide="hide_dun", acc=("laurel",), bell=True), "tag_blank"),
    "mooriarty": ("Epicowrus", "mooriarty", dict(hide="hide_bw", acc=("fedora",)), "tag_blank"),
    "moomaw": ("Heifercleitus", "moomaw", dict(hide="hide_gray", acc=("shawl", "bonnet"), bell=True), "tag_blank"),
}


def ang_diff(a, b):
    return (a - b + 180) % 360 - 180


class Bubble:
    """A literal 'MOO' floating over a speaker's head."""
    live: list = []

    def __init__(self, parent, text, y=2.35, col=None, life=2.0):
        self.ent = Text(text, parent=parent, position=(0, y, 0), origin=(0, 0), scale=22, billboard=True,
                        color=col or color.rgba(1, 1, 0.95, 1))
        self.ent.hide(SHADOW_MASK)
        self.life = life
        self.t = 0.0
        self.alive = True
        # the newest line wins: drop older bubbles that would land on top of this one on screen
        self.n = len(text)
        Bubble.live = [b for b in Bubble.live if b.alive]
        try:
            sp, hw = self.ent.screen_position, self._half_width()
        except Exception:
            sp = None
        for b in Bubble.live if sp is not None else ():
            try:
                d = b.ent.screen_position - sp
                if abs(d[0]) < hw + b._half_width() + 0.03 and abs(d[1]) < 0.08:
                    b.kill()
            except Exception:
                b.alive = False     # its speaker was torn down with the day
        Bubble.live.append(self)

    def _half_width(self):
        # rough on-screen half width: the text keeps a constant screen size up close (see update) and
        # shrinks with distance past 10 m
        d = max(0.1, (self.ent.world_position - camera.world_position).length())
        return 0.013 * self.n * min(1.0, 10.0 / d)

    def kill(self):
        if self.alive:
            destroy(self.ent)
            self.alive = False

    def update(self, dt):
        if not self.alive:
            return
        self.t += dt
        self.ent.y += dt * 0.12
        s = 20 * (1 + 0.25 * max(0, 0.15 - self.t) / 0.15)
        # world-space text grows as you get closer; shrink it so a cow next to you doesn't fill the screen
        try:
            d = (self.ent.world_position - camera.world_position).length()
            s *= max(0.18, min(1.0, d / 10.0))
        except Exception:
            pass
        self.ent.scale = s
        if self.t > self.life:
            self.kill()


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
        self.door_keys = ()     # doors this walker opens himself (Chuck: his own house and barn)

    def goto(self, target, speed=2.0):
        tx, tz = target[0], target[2] if len(target) > 2 else target[1]
        ty = target[1] if len(target) > 2 else 0.0
        self.path = self.g.world.find_path((self.x, self.y, self.z), (tx, ty, tz), self.door_keys)
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


# the herd named themselves too: Greek, every one (Chuck only uses the numbers)
HERD_NAMES = ["Echo", "Io", "Hera", "Cassandra", "Zeno", "Achilles", "Parmoonides", "Xenophanes", "Demoocritus",
              "Empedocles", "Protagoras", "Plutarch", "Porphyry", "Chrysippus", "Aristotle", "Theophrastus", "Homer",
              "Antigone", "Niobe", "Sisyphus", "Hypatia", "Pheidippides", "Anaximoonder", "Xanthippe", "Aesop",
              "Diotima", "Penelope", "Pythia", "Europa", "Thales", "Sappho", "Chloe", "Daphne", "Calliope", "Athena",
              "Artemis", "Persephone", "Ariadne", "Thalia", "Iris", "Phoebe", "Melissa"]

HERD_TAGS = [n for n in range(1, 51) if n not in (12, 47)]

HERD_HIDES = ["hide_bw", "hide_bw", "hide_brown", "hide_black", "hide_gray", "hide_red", "hide_dun", "hide_bw"]


def _merged_copy(model):
    """The cow's parts baked into one GeomNode in their current pose (drawn in one call).
    flattenStrong() can't do it: each Ursina entity carries its own ShaderAttrib, so Panda won't merge
    the parts even though they share shader and texture."""
    from panda3d.core import GeomNode, ShaderAttrib
    parts = model.rig.findAllMatches("**/+GeomNode")
    gn = GeomNode("cow_far")
    for i in range(parts.getNumPaths()):
        part = parts[i]
        mat = part.getMat(model)
        node = part.node()
        for k in range(node.getNumGeoms()):
            geom = node.getGeom(k).makeCopy()
            geom.transformVertices(mat)
            gn.addGeom(geom, node.getGeomState(k))
    far = model.attachNewNode(gn)
    if parts.getNumPaths():
        # Take the texture and render state, but not the shader's inputs: the net ShaderAttrib carries a snapshot
        # of every scene-wide input (sun, ambient, fog, lamps, shadow matrix). A copy made by day then kept the
        # daylight after dark, so far-off cows glowed in the moonlight. Just the shader; inputs come from above.
        net = parts[0].getNetState()
        sa = net.getAttrib(ShaderAttrib)
        far.setState(net.removeAttrib(ShaderAttrib))
        if sa is not None and sa.getShader() is not None:
            far.setShader(sa.getShader())
            # the per-entity inputs Ursina gives every FARM_SHADER entity (the scene-wide ones live on render)
            for name in ("texture_scale", "texture_offset", "u_unlit", "u_emissive", "u_sway", "u_water"):
                inp = sa.getShaderInput(name)
                if inp.getName():
                    far.setShaderInput(inp)
    far.flattenStrong()     # now that it's one node with one state: pool the vertices, one Geom
    return far


class HerdCow(Walker):
    def __init__(self, g, idx, pos, yaw):
        super().__init__(g, pos[0], pos[1], yaw, 0.8)
        self.idx = idx
        # the farm has fifty head: the herd's ear tags run 1-50, skipping 12 (Archimoodes) and 47 (you)
        self.name = HERD_NAMES[idx] if idx < len(HERD_NAMES) else f"Cow #{HERD_TAGS[idx % len(HERD_TAGS)]}"
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
        self.lod_dist = 32.0
        self.lod_far = False
        self.far_np = None
        self._apply()

    def set_lod(self, dist, casts_shadow):
        self.lod_dist = dist
        if casts_shadow:
            self.model.show(SHADOW_MASK)
        else:
            self.model.hide(SHADOW_MASK)     # the blob under it still grounds it

    def _use_far_model(self, far):
        """Far away, the cow is drawn as one merged mesh: 1 draw call instead of 8."""
        if far == self.lod_far:
            return
        m = self.model
        if far:
            if self.far_np is None:
                self.far_np = _merged_copy(m)
            m.rig.hide()
            m.shadow.hide(MAIN_MASK)
            self.far_np.show()
        else:
            m.rig.show()
            m.shadow.show(MAIN_MASK)
            if self.far_np is not None:
                self.far_np.hide()
        self.lod_far = far

    def _apply(self):
        # straight to Panda: Ursina rotation_y == -H
        self.model.setPos(self.x, self.y, self.z)
        self.model.setH(-self.yaw)
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
                    not (-66 < x < -38 and -12 < z < 3) and not in_keep_clear(x, z):
                return (x, 0, z)
        return None

    def _leave_keep_clear(self):
        """Walk out of a doorway-like spot the player needs (never while stampeding)."""
        for kx, kz, r in KEEP_CLEAR:
            d = math.hypot(self.x - kx, self.z - kz)
            if d < r:
                # step back into the pasture (it lies to the west of both spots)
                az = (self.z - kz) / max(d, 0.1) * 0.5
                self.path = [(kx - (r + 2.0), 0, kz + az * (r + 2.0))]
                self.state = "walk"
                self.walk_speed = 1.6
                self.lie = False
                self.model.lying_target = 0.0
                return True
        return False

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
        if self.state == "graze" and not self.free:
            self._leave_keep_clear()
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
        # make way for a cow who's leaning on you: after a moment of shoving, step aside
        pl = self.g.player
        pd = math.hypot(pl.x - self.x, pl.z - self.z)
        if self.state != "stampede" and pd < 1.8 and pl.speed > 0.4:
            self._shoved = getattr(self, "_shoved", 0.0) + dt
            if self._shoved > 0.5 and self.state != "walk":
                # sideways relative to the way the player is heading, so she clears the path
                yr = math.radians(pl.yaw)
                fx, fz = math.sin(yr), math.cos(yr)
                side = 1.0 if (self.x - pl.x) * fz - (self.z - pl.z) * fx > 0 else -1.0
                tx, tz = self.x + fz * side * 2.8, self.z - fx * side * 2.8
                self.path = [(tx, 0, tz)]
                self.state = "walk"
                self.walk_speed = 1.8
                self.lie = False
                self.model.lying_target = 0.0
                self._shoved = 0.0
        else:
            self._shoved = 0.0
        self._apply()
        # far off and on its feet: the merged mesh; lying down, talking or close: the animated rig
        m = self.model
        self._use_far_model(d_cam > self.lod_dist and m.lying < 0.02 and m.lying_target == 0.0
                            and not self.bubbles)
        if not self.far:
            p = self.g.player
            # animation level of detail: distant cows animate every few frames
            self.anim_acc = getattr(self, "anim_acc", 0.0) + dt
            every = 1 if d_cam < 30 else (3 if d_cam < 55 else 6)
            self.anim_n = getattr(self, "anim_n", self.idx) + 1
            if self.anim_n % every == 0 and not self.lod_far:
                look = (p.x, p.z) if math.hypot(p.x - self.x, p.z - self.z) < 6 else None
                self.model.graze_target = 1.0 if (spd < 0.1 and look is None and not self.lie) else 0.0
                self.model.animate(self.anim_acc, spd, look, world_yaw=self.yaw)
                self.anim_acc = 0.0
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
                self.path = [(random.uniform(36, 46.5), 0, random.uniform(-40, -26))]
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
