"""The player: Cow #47, in first person."""
from __future__ import annotations

import math
import random

from ursina import Entity, camera, held_keys, mouse, destroy

from .engine.meshbuilder import MeshBuilder
from .engine.shading import FARM_SHADER
from .engine.assets import tex
from . import models
from .world import in_pond

EYE = 1.42
EYE_SNEAK = 0.95
RADIUS = 0.55
SNOUT_Y = -0.38

MOO_THOUGHTS = [
    "Moo. (A sound with no referent. Wittgenstein would be furious.)",
    "Moo. (Nobody answered. The universe is indifferent. Same as yesterday.)",
    "Moo. (Louder than intended. Like most of my existence.)",
    "Moo. (I think, therefore I am. Chuck thinks, therefore I'm lunch.)",
    "Moo. (Somebody moos back from the far side of the pasture. Solidarity, or an echo. Unfalsifiable.)",
    "Moo. (Four stomachs, one existential crisis.)",
    "Moo. (Proof by moo: I mooed, therefore a moo exists. Tight.)",
    "Moo. (Moobius would say that was statistically insignificant.)",
    "Moooo. (That one was for Big Earl. Nine hundred pounds of dignity, served on a bun.)",
    "Moo. (Chuck, if you can hear this: the answer is no.)",
]

THROWABLE = {"rock": 14.0, "cowbell": 18.0, "egg": 12.0, "rubber_chicken": 16.0, "shoes": 12.0, "boot": 12.0,
             "tincan": 16.0}
# thrown things you can go and pick up again (the rest break, splat, or are Chuck's problem now)
REUSABLE = ("cowbell", "rubber_chicken", "boot", "tincan")


class Projectile:
    def __init__(self, g, kind, pos, vel):
        self.g = g
        self.kind = kind
        self.pos = list(pos)
        self.vel = list(vel)
        self.ent = models.item_model(kind if kind != "rock" else "rock", position=pos)
        self.alive = True
        self.t = 0.0
        self.landed_t = 0.0

    def update(self, dt):
        if self.landed_t > 0:
            self.landed_t -= dt
            if self.landed_t <= 0:
                self.alive = False
                destroy(self.ent)
            return
        self.t += dt
        g = self.g
        p0 = tuple(self.pos)
        self.vel[1] -= 18.0 * dt
        p1 = (p0[0] + self.vel[0] * dt, p0[1] + self.vel[1] * dt, p0[2] + self.vel[2] * dt)
        # targets that react to rocks (hanging key, enemies)
        if g.on_projectile_move(self, p0, p1):
            self.land(p1, hit=True)
            return
        t = g.phys.raycast(p0, p1, sight_only=False)
        gh, _ = g.phys.ground(p1[0], p1[2], p0[1] + 0.3)
        if t is not None:
            hp = (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t, p0[2] + (p1[2] - p0[2]) * t)
            self.land(hp)
            return
        if p1[1] <= gh + 0.05:
            self.land((p1[0], gh + 0.06, p1[2]))
            return
        self.pos = list(p1)
        self.ent.position = p1
        self.ent.rotation_x += dt * 500
        if self.t > 6:
            self.alive = False
            destroy(self.ent)

    def land(self, p, hit=False):
        g = self.g
        self.ent.position = p
        self.pos = list(p)
        snd = {"rock": "rock_land", "cowbell": "cowbell_drop", "egg": "splash", "rubber_chicken": "squawk",
               "shoes": "thump", "boot": "thump", "tincan": "metal_clang"}.get(self.kind, "rock_land")
        g.audio.play(snd, vol=1.0, pos=p, rng=60 if self.kind == "tincan" else 45)
        loud = {"rock": 15, "cowbell": 22, "egg": 9, "rubber_chicken": 18, "tincan": 28}.get(self.kind, 14)
        g.noise(p, loud, source="thrown")
        g.on_projectile_land(self, p)
        self.landed_t = 3.0 if self.kind == "rock" else 1.0
        if self.kind in REUSABLE:
            # these can be picked up again
            g.drop_item_at(self.kind, p)
            self.alive = False
            destroy(self.ent)


class Player:
    def __init__(self, g):
        self.g = g
        self.root = Entity(position=(0, 0, 0))
        self.yaw = 0.0
        self.pitch = 0.0
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0
        self.vx = 0.0
        self.vz = 0.0
        self.y_vel = 0.0
        self.eye = EYE
        self.cam_y = EYE
        self.crouching = False
        self.crouch_toggle = False
        self.galloping = False
        self.stamina = 1.0
        self.stamina_lock = 0.0
        self.frozen = False
        self.look_frozen = False
        self.has_bell = True
        self.speed = 0.0
        self.bob_t = 0.0
        self.step_acc = 0.0
        self.hop_cd = 0.0
        self.headbutt_cd = 0.0
        self.kick_cd = 0.0
        self.throw_cd = 0.0
        self.lunge = 0.0
        self.shake = 0.0
        self.health = 3
        self.max_health = 3
        self.invuln = 0.0
        self.sensitivity = 1.0
        self.invert_y = False
        self.fov_base = 80.0
        self.surface = "grass"
        self.in_water = False
        self.moo_cd = 0.0
        self.projectiles: list[Projectile] = []
        self.held_name = None
        self.held = None
        self.disguised = False
        self.col = g.phys.add_dynamic(0, 0, RADIUS, 0, 1.5, owner=self, sight=False)
        self.head = Entity(parent=self.root, y=EYE)
        camera.parent = self.head
        camera.position = (0, 0, 0)
        camera.rotation = (0, 0, 0)
        camera.fov = self.fov_base
        camera.clip_plane_near = 0.08
        self.snout = self._build_snout()
        self.driving = False
        # your own body, seen from outside: only shown while a cutscene has the camera (see sync_body)
        self.body = models.CowModel(hide="hide_brown", tag="tag_47", bell=True, pupils=[(0, 0), (0, 0)])
        self.body.enabled = False
        self._body_look = (self.has_bell, self.disguised)

    def sync_body(self, dt, show):
        """Keep the third-person body on the player while a cutscene camera is looking at the farm."""
        b = self.body
        if show:
            cx, cy, cz = camera.world_position
            # a camera practically inside our head would only see the inside of a cow
            show = math.hypot(cx - self.x, cz - self.z) > 1.7 or abs(cy - (self.y + 1.2)) > 1.6
        b.enabled = show
        if not show:
            return
        look = (self.has_bell, self.disguised)
        if look != self._body_look:
            self._body_look = look
            b.bell = self.has_bell
            for a in ("moustache", "chuckhat"):
                (b.acc.add if self.disguised else b.acc.discard)(a)
            b.build()
        b.position = (self.x, self.y, self.z)
        b.rotation_y = self.yaw
        b.animate(dt, self.speed if not self.frozen else 0.0, None)

    # ------------------------------------------------------------------
    def _build_snout(self):
        root = Entity(parent=camera, position=(0, SNOUT_Y, 0.56), rotation_x=-6)
        mb = MeshBuilder()
        P = (0.95, 0.66, 0.7, 1)
        # the bridge of the nose, in your own brown-and-white hide
        mb.box((0, 0.07, -0.2), (0.34, 0.12, 0.34), uv_rect=models.uvr("hide_brown", 0.3))
        # the muzzle: a wide, soft pink dome, mostly below the bottom of the screen
        mb.sphere((0, 0, 0), 0.2, color=P, segs=18, rings=10, scale=(1.3, 0.55, 0.95))
        mb.sphere((0, -0.02, 0.1), 0.16, color=(0.93, 0.6, 0.65, 1), segs=16, rings=8, scale=(1.35, 0.5, 0.7))
        for sx in (-1, 1):
            mb.sphere((sx * 0.085, 0.05, 0.15), 0.03, color=(0.5, 0.22, 0.27, 1), segs=10, rings=6,
                      scale=(1.5, 0.45, 1.0))
        e = Entity(parent=root, model=mb.build(solid_rect=models.WHITE), texture=tex("atlas"), shader=FARM_SHADER)
        e.set_shader_input("u_unlit", 0.35)
        self.stache = Entity(parent=root, enabled=False)
        sm = MeshBuilder()
        sm.box((0, 0.1, 0.06), (0.34, 0.04, 0.05), color=models.MUSTACHE, uv_rect=models.WHITE)
        for sx in (-1, 1):
            sm.box((sx * 0.18, 0.07, 0.06), (0.05, 0.08, 0.05), color=models.MUSTACHE, uv_rect=models.WHITE, rot=(0, 0, sx * 20))
        Entity(parent=self.stache, model=sm.build(solid_rect=models.WHITE), texture=tex("atlas"), shader=FARM_SHADER)
        self.hat_brim = Entity(parent=camera, position=(0, 0.42, 0.45), enabled=False)
        hm = MeshBuilder()
        hm.box((0, 0, 0), (1.4, 0.03, 0.5), color=(0.9, 0.78, 0.48, 1), uv_rect=models.WHITE, rot=(-12, 0, 0))
        Entity(parent=self.hat_brim, model=hm.build(solid_rect=models.WHITE), texture=tex("atlas"), shader=FARM_SHADER)
        return root

    def set_disguise(self, on):
        self.disguised = on
        self.stache.enabled = on
        self.hat_brim.enabled = on

    def hold(self, name):
        if name == self.held_name:
            return
        if self.held is not None:
            destroy(self.held)
            self.held = None
        self.held_name = name
        if not name:
            return
        scale = {"plank": 0.3, "shotgun": 0.5, "radio": 0.34, "jerrycan": 0.34, "bucket": 0.42, "boot": 0.38,
                 "photo": 0.6, "score": 0.6, "page": 0.6}.get(name, 0.62)
        rot = {"plank": (0, 90, 0), "shotgun": (0, 0, 0), "pencil": (0, 90, 0)}.get(name, (0, 20, 0))
        # in the mouth, low in the frame so it doesn't hide what you're looking at
        y = -0.26 if name == "photo" else -0.3
        self.held = models.item_model(name, parent=camera, position=(0.03, y, 0.62), rotation=rot, scale=scale)
        for c in self.held.children:
            c.set_shader_input("u_unlit", 0.55 if name in ("page", "score", "photo") else 0.3)
        # the held item rides on the camera, so hide it while the camera is off doing a cutscene
        self.held.enabled = not self.g.cam_free and not self.driving

    # ------------------------------------------------------------------
    @property
    def pos(self):
        return (self.x, self.y, self.z)

    @property
    def eye_pos(self):
        return (self.x, self.y + self.cam_y, self.z)

    def forward(self):
        cy, sy = math.cos(math.radians(self.yaw)), math.sin(math.radians(self.yaw))
        cp, sp = math.cos(math.radians(self.pitch)), math.sin(math.radians(self.pitch))
        return (sy * cp, -sp, cy * cp)

    def teleport(self, x, y=None, z=None, yaw=None):
        if isinstance(x, (tuple, list)):
            vals = list(x)
            x, y, z = vals[0], vals[1], vals[2]
            if len(vals) > 3 and yaw is None:
                yaw = vals[3]
        self.x, self.y, self.z = float(x), float(y or 0.0), float(z)
        self.vx = self.vz = 0.0
        self.y_vel = 0.0
        if yaw is not None:
            self.yaw = float(yaw)
        self.pitch = 0.0
        self.col.x, self.col.z = self.x, self.z
        self._apply()

    def look_at_point(self, p):
        dx, dz = p[0] - self.x, p[2] - self.z
        self.yaw = math.degrees(math.atan2(dx, dz))
        dy = p[1] - (self.y + self.cam_y)
        self.pitch = -math.degrees(math.atan2(dy, math.hypot(dx, dz)))

    def _apply(self):
        self.root.position = (self.x, self.y, self.z)
        self.root.rotation_y = self.yaw
        self.head.y = self.cam_y
        self.head.rotation_x = self.pitch

    # ------------------------------------------------------------------
    def update(self, dt):
        g = self.g
        self.hop_cd = max(0.0, self.hop_cd - dt)
        self.headbutt_cd = max(0.0, self.headbutt_cd - dt)
        self.kick_cd = max(0.0, self.kick_cd - dt)
        self.throw_cd = max(0.0, self.throw_cd - dt)
        self.moo_cd = max(0.0, self.moo_cd - dt)
        self.invuln = max(0.0, self.invuln - dt)
        if self.driving:
            return
        controls = not self.frozen and g.controls_enabled()
        # mouse look
        if controls and not self.look_frozen and mouse.locked:
            mv = mouse.velocity
            self.yaw += mv[0] * 42 * self.sensitivity
            self.pitch -= mv[1] * 42 * self.sensitivity * (-1 if self.invert_y else 1)
            self.pitch = max(-75.0, min(70.0, self.pitch))
        # input
        ix = iz = 0.0
        want_gallop = False
        if controls:
            ix = held_keys["d"] - held_keys["a"] + held_keys["right arrow"] - held_keys["left arrow"]
            iz = held_keys["w"] - held_keys["s"] + held_keys["up arrow"] - held_keys["down arrow"]
            ix = max(-1, min(1, ix))
            iz = max(-1, min(1, iz))
            want_gallop = (held_keys["shift"] or held_keys["left shift"]) and iz > 0
            self.crouching = bool(held_keys["control"] or held_keys["left control"] or self.crouch_toggle)
        else:
            self.crouching = self.crouch_toggle and not self.frozen
        mag = math.hypot(ix, iz)
        moving = mag > 0.01
        if moving:
            ix, iz = ix / mag, iz / mag
        # stamina
        self.stamina_lock = max(0.0, self.stamina_lock - dt)
        self.galloping = want_gallop and moving and self.stamina > 0.02 and self.stamina_lock <= 0 and not self.crouching
        drain = 0.16 * (0.5 if g.flags.get("coffee") else 1.0)
        if self.galloping:
            self.stamina = max(0.0, self.stamina - dt * drain)
            if self.stamina <= 0.02:
                self.stamina_lock = 1.2
        else:
            self.stamina = min(1.0, self.stamina + dt * 0.22)
        speed = 4.0
        if self.galloping:
            speed = 7.4
        elif self.crouching:
            speed = 1.9
        carry = g.carry_slow()
        speed *= carry
        self.in_water = in_pond(self.x, self.z)
        if self.in_water:
            speed *= 0.55
        yr = math.radians(self.yaw)
        fx, fz = math.sin(yr), math.cos(yr)
        rx, rz = math.cos(yr), -math.sin(yr)
        tvx = (rx * ix + fx * iz) * speed
        tvz = (rz * ix + fz * iz) * speed
        k = 1 - math.exp(-dt * (10 if moving else 12))
        self.vx += (tvx - self.vx) * k
        self.vz += (tvz - self.vz) * k
        ox, oz = self.x, self.z
        self.x, self.z = g.phys.move(self.x, self.z, self.vx * dt, self.vz * dt, RADIUS, self.y, 1.5, ignore=self.col)
        moved = math.hypot(self.x - ox, self.z - oz)
        self.speed = moved / dt if dt > 0 else 0
        # vertical
        gh, fsurf = g.phys.ground(self.x, self.z, self.y)
        if self.y_vel > 0 or self.y > gh + 0.02:
            self.y_vel -= 20.0 * dt
            self.y += self.y_vel * dt
            if self.y <= gh:
                if self.y_vel < -6:
                    g.audio.play("thump", vol=0.6)
                    self.shake = 0.25
                self.y = gh
                self.y_vel = 0.0
        else:
            if gh > self.y:
                self.cam_y -= (gh - self.y)  # smooth the step up
            self.y = gh
            # landing within 2 cm of the floor while still falling used to leave y_vel negative for good,
            # and hop() refuses while y_vel != 0: hopping stopped working until the next teleport
            self.y_vel = 0.0
        self.col.x, self.col.z = self.x, self.z
        # surface
        if self.in_water:
            self.surface = "water"
        elif fsurf and self.y > 0.05:
            self.surface = fsurf
        else:
            zs = g.phys.zones_at(self.x, self.z, self.y)
            self.surface = "hay" if "surf_hay" in zs else "wood" if "surf_wood" in zs else "dirt" if "surf_dirt" in zs else "grass"
        # camera height (sneak), bob, lunge, shake
        target_eye = EYE_SNEAK if self.crouching else EYE
        self.eye += (target_eye - self.eye) * min(1, dt * 8)
        self.cam_y += (self.eye - self.cam_y) * min(1, dt * 12)
        spd = self.speed
        if spd > 0.3 and self.y_vel == 0:
            self.bob_t += dt * (6.5 if self.galloping else 5.0) * min(1.6, spd / 3.5)
        bob = math.sin(self.bob_t * 2) * 0.04 * min(1.0, spd / 4.0) * (1.6 if self.galloping else 1)
        roll = math.sin(self.bob_t) * 1.2 * min(1.0, spd / 4.0)
        self.lunge = max(0.0, self.lunge - dt * 3)
        lunge_off = math.sin(min(1.0, self.lunge) * math.pi) * 0.35
        sh = self.shake
        self.shake = max(0.0, self.shake - dt)
        self._apply()
        self.head.y = self.cam_y + bob + random.uniform(-1, 1) * sh * 0.1
        self.head.rotation_z = roll + random.uniform(-1, 1) * sh * 4
        if not g.cam_free:
            # first-person camera effects only while the camera is on our head (not in cutscenes)
            camera.z = lunge_off
            target_fov = self.fov_base + (7 if self.galloping else 0)
            camera.fov += (target_fov - camera.fov) * min(1, dt * 5)
        # snout wiggle
        self.snout.y = SNOUT_Y + math.sin(self.bob_t * 2) * 0.008 - (0.03 if self.crouching else 0)
        # footsteps + cowbell noise
        if moved > 0 and self.y_vel == 0:
            self.step_acc += moved
            stride = 1.9 if self.galloping else (0.95 if self.crouching else 1.35)
            if self.step_acc >= stride:
                self.step_acc = 0.0
                self._footstep()
        # projectiles
        for p in self.projectiles:
            p.update(dt)
        self.projectiles = [p for p in self.projectiles if p.alive]

    def _footstep(self):
        g = self.g
        surf = self.surface
        vol = 0.55 if self.galloping else (0.18 if self.crouching else 0.35)
        g.audio.play(f"step_{surf}_{random.randrange(4)}", vol=vol, pitch=random.uniform(0.9, 1.1), group="sfx")
        g.event("step", surface=surf, gallop=self.galloping)
        radius = 0.0
        if self.galloping:
            radius = 7.0
        if self.has_bell:
            bvol = 0.5 if self.galloping else (0.12 if self.crouching else 0.3)
            g.audio.play(f"cowbell_{random.randrange(4)}", vol=bvol, pitch=random.uniform(0.95, 1.05))
            radius = max(radius, 16.0 if self.galloping else (3.0 if self.crouching else 7.0))
        if surf == "water":
            radius = max(radius, 5.0)
        if radius > 0:
            g.noise(self.pos, radius, source="steps")
        elif not self.crouching:
            # plain walking: only Chuck asleep nearby hears it (sneak past him)
            f = g.farmer
            if f is not None and f.visible and f.sleeping and math.hypot(f.x - self.x, f.z - self.z) < 16:
                g.noise(self.pos, 6.0, source="footfall")

    # ------------------------------------------------------------------
    def hop(self):
        if self.hop_cd > 0 or self.y_vel != 0 or self.frozen:
            return
        self.y_vel = 3.4
        self.hop_cd = 0.9
        self.g.audio.play("boing", vol=0.35, pitch=random.uniform(0.95, 1.1))
        self.g.stats["hops"] = self.g.stats.get("hops", 0) + 1
        self.g.event("hop")

    def moo(self):
        if self.moo_cd > 0:
            return
        self.moo_cd = 0.9
        kind = random.choice(["short", "medium", "medium", "long", "exclaim"])
        self.g.audio.play(f"moo_player_{kind}_{random.randrange(2)}", vol=0.9, group="voice")
        self.g.stats["moos"] = self.g.stats.get("moos", 0) + 1
        self.g.event("moo")
        self.lunge = 0.25
        if not self.g.on_player_moo():
            self.g.noise(self.pos, 20.0, source="moo")
            self.g.ui.popup_sub(random.choice(MOO_THOUGHTS))

    def headbutt(self):
        if self.headbutt_cd > 0 or self.frozen:
            return
        self.headbutt_cd = 0.75
        self.lunge = 1.0
        charge = self.galloping and self.speed > 5.5
        hit = self.g.on_headbutt(self.eye_pos, self.forward(), charge)
        if hit:
            self.g.audio.play("headbutt", vol=0.9)
            self.shake = 0.3
        else:
            self.g.audio.play("whoosh", vol=0.25, pitch=0.8)

    def kick(self):
        if self.kick_cd > 0 or self.frozen:
            return
        self.kick_cd = 1.0
        self.shake = 0.35
        hit = self.g.on_kick(self.pos, self.yaw)
        self.g.audio.play("punch" if hit else "whoosh", vol=0.8 if hit else 0.3, pitch=0.9)

    def throw(self, kind):
        if self.throw_cd > 0 or self.frozen:
            return False
        self.throw_cd = 0.55
        f = self.forward()
        spd = THROWABLE.get(kind, 14.0)
        ex, ey, ez = self.eye_pos
        start = (ex + f[0] * 0.7, ey - 0.1 + f[1] * 0.7, ez + f[2] * 0.7)
        vel = (f[0] * spd + self.vx * 0.5, f[1] * spd + 3.2, f[2] * spd + self.vz * 0.5)
        self.projectiles.append(Projectile(self.g, kind, start, vel))
        self.g.audio.play("whoosh", vol=0.5)
        self.lunge = 0.4
        self.g.stats["thrown"] = self.g.stats.get("thrown", 0) + 1
        return True

    def damage(self, n=1, from_pos=None):
        if self.invuln > 0:
            return
        self.health = max(0, self.health - n)
        self.invuln = 1.0
        self.shake = 0.5
        self.g.ui.flash((0.8, 0.1, 0.1), 0.4)
        self.g.audio.play("punch", vol=0.9, pitch=1.2)
        self.g.audio.play(f"moo_player_exclaim_{random.randrange(2)}", vol=0.8, group="voice")
        if from_pos is not None:
            dx, dz = self.x - from_pos[0], self.z - from_pos[2]
            d = math.hypot(dx, dz) or 1
            self.vx += dx / d * 9
            self.vz += dz / d * 9
        if self.health <= 0:
            self.g.on_player_defeated()
