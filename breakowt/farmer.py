"""Farmer Chuck: routines, vision, hearing, suspicion, and a lot of tripping."""
from __future__ import annotations

import math
import random

from ursina import Text, camera, color, destroy

from . import models
from .engine.shading import SHADOW_MASK
from .npc import Walker, ang_diff

INVESTIGATE_LINES = [
    "Who's there?", "Dang raccoons.", "Dale? That you?", "Huh. Could've sworn...", "Hello? ...Hello?",
    "If that's you again, Gerald, I swear...", "Probably the wind. The wind throws rocks now.",
    "I'm armed! ...With a very stern voice!", "Nothing. Nothing's ever there.",
]
GIVE_UP_LINES = ["Huh. Nothing.", "Eh. Must be hearin' things.", "Back to work, Chuck.", "Stupid wind.",
                 "Note to self: get a dog. Another dog.", "Whatever it was, it's gone now."]
SUSPICIOUS_LINES = ["Huh?", "Wha—?", "Hey...", "Is that a...?", "Hold on now..."]
TRIP_LINES = ["OOF!", "Whoa-OA-oa!", "Dang it!", "Who put the GROUND there?!", "My back!"]
GETUP_LINES = ["I'm okay!", "Nobody saw that.", "Meant to do that.", "Ground's gettin' lower every year."]
DALE_LINES = ["Mornin', Dale!", "Dale! Lookin' good, buddy!", "Hey Dale. You lose weight?", "Dale! Save some room for Sunday!"]
SLEEP_TALK = ["zzz... Dale... that's MY potato salad...", "mmf... strike... STRIKE...", "...no, Mama, I did feed 'em...",
              "zzz... hnk... Big Earl... good boy...", "...forty-seven... forty-eight... zzz..."]
DALE_SUS_LINES = ["Dale... you look different.", "Dale, why are you... chewing like that?", "You smell like a barn, Dale."]


class Farmer(Walker):
    def __init__(self, g, pos=(22, 0, -20), yaw=0.0):
        super().__init__(g, pos[0], pos[2], yaw, 0.42)
        self.model = models.FarmerModel()
        self.col = g.phys.add_dynamic(self.x, self.z, 0.42, 0, 1.9, owner=self)
        self.visible = True
        self.state = "routine"
        self.routine = []
        self.r_i = 0
        self.r_timer = 0.0
        self.r_started = False
        self.susp = 0.0
        self.marker_state = ""
        self.marker = Text("", parent=self.model, position=(0, 2.45, 0), origin=(0, 0), scale=40, billboard=True,
                           color=color.rgba(1, 0.8, 0.2, 1))
        self.marker.hide(SHADOW_MASK)
        self.last_seen = None
        self.inv_target = None
        self.inv_timer = 0.0
        self.inv_phase = ""
        self.pose = "idle"
        self.head_yaw = 0.0
        self.fov = 110.0
        self.range_day = 24.0
        self.hearing = 1.0
        self.flashlight = False
        self.trip_rate = 1 / 90.0
        self.fall_timer = 0.0
        self.detect = True
        self.dale_greeted = False
        self.dale_t = 0.0
        self.bark_cd = 0.0
        self.sees_player = False
        self.vis_timer = 0.0
        self.vis_val = 0.0
        self.sleeping = False
        self.wake_timer = 0.0
        self.boss = None
        self.tool = None
        self.catch_cb = None
        self.walk_run = False
        self._apply()

    # ------------------------------------------------------------------
    def _apply(self):
        self.model.position = (self.x, self.y, self.z)
        self.model.rotation_y = self.yaw
        self.col.x, self.col.z = self.x, self.z

    def set_visible(self, v):
        self.visible = v
        self.model.enabled = v
        self.col.enabled = v
        if not v:
            self.set_marker("")

    def teleport(self, pos, yaw=None):
        self.x, self.z = pos[0], pos[2]
        self.y = pos[1]
        if len(pos) > 3 and yaw is None:
            yaw = pos[3]
        if yaw is not None:
            self.yaw = yaw
        self.path = []
        self._apply()

    def set_tool(self, name):
        self.tool = name
        self.model.set_tool(name)

    def set_outfit(self, o):
        self.model.set_outfit(o)
        if self.tool:
            self.model.set_tool(self.tool)

    def set_marker(self, s):
        if s == self.marker_state:
            return
        self.marker_state = s
        self.marker.text = s
        self.marker.color = color.rgba(1, 0.25, 0.2, 1) if s == "!" else color.rgba(1, 0.85, 0.2, 1)

    def say(self, text, kind=None, force=False):
        """Mumble in trombone and show a subtitle if the player is near enough to hear."""
        g = self.g
        if kind is None:
            kind = "question" if text.endswith("?") else ("angry" if text.endswith("!") and text.isupper() else
                                                         "short" if len(text) < 18 else "medium" if len(text) < 45 else "long")
        g.audio.play(f"farmer_{kind}_{random.randrange(2)}", vol=1.0, pos=(self.x, 1.7, self.z), rng=45, group="voice",
                     follow=lambda: (self.x, 1.7, self.z))
        d = math.hypot(g.player.x - self.x, g.player.z - self.z)
        if d < 38 or force:
            g.ui.bark_line(text, "Chuck")

    # ------------------------------------------------------------------
    # routines
    # ------------------------------------------------------------------
    def set_routine(self, steps, start=0):
        self.routine = list(steps)
        self.r_i = start
        self.r_started = False
        self.state = "routine"
        self.susp = 0.0
        self.set_marker("")
        self.path = []
        self.sleeping = False

    def scripted(self):
        self.state = "scripted"
        self.path = []
        self.set_marker("")
        self.susp = 0.0

    def sleep(self, pos, yaw, pose="sleep", outfit="pajamas"):
        self.teleport(pos, yaw)
        self.state = "sleep"
        self.sleeping = True
        self.wake_timer = 0.0
        self.sleep_pose = pose
        self.pose = pose
        self.susp = 0.0
        self.set_marker("")
        if outfit:
            self.set_outfit(outfit)
        self.set_tool(None)
        self.g.audio.loop("snore", "loop_snore", vol=0.9, pos=(pos[0], pos[1] + 0.8, pos[2]), rng=18)

    def wake(self):
        self.sleeping = False
        self.g.audio.stop_loop("snore", 0.3)

    def _routine_step(self, dt):
        if not self.routine:
            self.pose = "idle"
            return
        if self.r_i >= len(self.routine):
            self.r_i = 0
        st = self.routine[self.r_i]
        kind = st[0]
        if kind == "go":
            if not self.r_started:
                self.goto(st[1], st[2] if len(st) > 2 else 2.0)
                self.r_started = True
            if not self.path:
                self._next()
            else:
                self.pose = "walk"
                if random.random() < dt * self.trip_rate:
                    self.trip()
        elif kind == "wait":
            dur = st[1]
            pose = st[2] if len(st) > 2 else "idle"
            lines = st[3] if len(st) > 3 else None
            face = st[4] if len(st) > 4 else None
            if not self.r_started:
                self.r_timer = dur
                self.r_started = True
                self.face_target = face
                self._bark_t = random.uniform(2, max(3, dur * 0.6))
            self.pose = pose
            self.r_timer -= dt
            if lines:
                self._bark_t -= dt
                if self._bark_t <= 0:
                    self._bark_t = random.uniform(6, 14)
                    self.say(random.choice(lines))
            if self.r_timer <= 0:
                self.face_target = None
                self._next()
        elif kind == "face":
            self.face_target = st[1]
            self._next()
        elif kind == "say":
            self.say(st[1])
            self._next()
        elif kind == "tool":
            self.set_tool(st[1])
            self._next()
        elif kind == "call":
            st[1]()
            self._next()
        elif kind == "lamp":
            self.g.world.set_lamp(st[1], st[2])
            self._next()
        elif kind == "teleport":
            self.teleport(st[1])
            self._next()
        elif kind == "hide":
            self.set_visible(False)
            self._next()
        elif kind == "show":
            self.set_visible(True)
            self._next()
        elif kind == "stop":
            self.pose = st[1] if len(st) > 1 else "idle"
        else:
            self._next()

    def _next(self):
        self.r_i = (self.r_i + 1) % max(1, len(self.routine))
        self.r_started = False

    def resume_routine(self):
        self.state = "routine"
        self.r_started = False
        self.set_marker("")

    # ------------------------------------------------------------------
    # clumsiness
    # ------------------------------------------------------------------
    def trip(self):
        if self.state not in ("routine", "investigate"):
            return
        self._pre_fall = self.state
        self.state = "fallen"
        self.fall_timer = 3.2
        self.path_saved = list(self.path)
        self.path = []
        self.pose = "fallen"
        self.say(random.choice(TRIP_LINES), kind="surprise")
        self.g.audio.play("slide_down", vol=0.8, pos=(self.x, 1.2, self.z), rng=40)
        self.g.audio.play("thump", vol=0.9, pos=(self.x, 0.5, self.z), rng=30)
        self.g.stats["chuck_trips"] = self.g.stats.get("chuck_trips", 0) + 1
        self.g.on_farmer_trip()

    # ------------------------------------------------------------------
    # senses
    # ------------------------------------------------------------------
    def eye(self):
        return (self.x, self.y + 1.72, self.z)

    def facing(self):
        return self.yaw + self.model.head.rotation_y

    def visibility(self):
        """0..1 how clearly Chuck can see the player right now."""
        g = self.g
        p = g.player
        if not self.detect or not self.visible or (self.sleeping and self.wake_timer <= 0) or g.flags.get("_hiding"):
            return 0.0, 99.0
        ex, ey, ez = self.eye()
        dx, dz = p.x - ex, p.z - ez
        dist = math.hypot(dx, dz)
        dark = g.env.is_dark
        rng = self.range_day
        if dark:
            rng = 7.5
        lit = False
        if dark:
            if self.flashlight:
                f = self.facing()
                a = abs(ang_diff(math.degrees(math.atan2(dx, dz)), f))
                if a < 24 and dist < 22:
                    lit = True
                    rng = 22
            if g.player_lit():
                lit = True
                rng = max(rng, 16)
        if dist > rng:
            return 0.0, dist
        ang = abs(ang_diff(math.degrees(math.atan2(dx, dz)), self.facing()))
        if ang > self.fov / 2:
            if dist > 2.0:
                return 0.0, dist
        # line of sight to body and head
        ignore = (self.col, p.col)
        head = (p.x, p.y + p.cam_y + 0.05, p.z)
        body = (p.x, p.y + 0.75, p.z)
        if not (g.phys.line_of_sight((ex, ey, ez), head, ignore) or g.phys.line_of_sight((ex, ey, ez), body, ignore)):
            return 0.0, dist
        v = 1.0
        if p.crouching:
            v *= 0.55
        if p.galloping:
            v *= 1.4
        hide = g.player_hidden()
        if hide:
            if dist > 2.5:
                return 0.0, dist
            v *= 0.3
        if dark and not lit:
            v *= 0.45
        # distance falloff near the edge of the range
        v *= max(0.25, 1.0 - (dist / rng) ** 2 * 0.6)
        return v, dist

    def hear(self, pos, radius, source):
        if not self.visible or self.state in ("scripted", "catch", "boss", "disabled", "fallen"):
            return False
        d = math.hypot(pos[0] - self.x, pos[2] - self.z)
        eff = radius * self.hearing * (0.45 if self.sleeping else 1.0)
        if d > eff:
            return False
        if self.g.noise_masked(pos):
            return False
        if source == "moo" and self.g.phys.in_zone("pasture", pos[0], pos[2]):
            return False
        if source == "steps" and self.g.phys.in_zone("pasture", pos[0], pos[2]):
            return False
        if self.sleeping:
            self.wake_timer = 3.5
            self.say(random.choice(["Hnnh? ...Dale?", "Wha... who's there...", "mmph... potato salad..."]), kind="sleepy")
            self.pose = "look"
            return True
        self.investigate(pos)
        return True

    def investigate(self, pos):
        if self.state == "alert" and self.susp > 0.6:
            return
        self.state = "investigate"
        self.inv_target = (pos[0], 0.0, pos[2])
        gh, _ = self.g.phys.ground(pos[0], pos[2], (pos[1] if len(pos) > 1 else 0) + 0.5)
        self.inv_target = (pos[0], gh, pos[2])
        self.goto(self.inv_target, 2.8)
        self.inv_phase = "go"
        self.inv_timer = 12.0
        self.set_marker("?")
        if self.bark_cd <= 0:
            self.say(random.choice(["Huh?", "What was that?", "Hm?", "Who's there?"]))
            self.bark_cd = 3.0

    # ------------------------------------------------------------------
    def update(self, dt):
        if not self.visible:
            return
        g = self.g
        self.bark_cd = max(0.0, self.bark_cd - dt)
        if self.boss is not None and self.state == "boss":
            self.boss.update(dt)
            self._apply()
            return
        spd = 0.0
        if self.state == "routine":
            self._routine_step(dt)
            spd = self._step(dt, self.col)
        elif self.state == "investigate":
            spd = self._step(dt, self.col)
            self.inv_timer -= dt
            if self.inv_phase == "go":
                self.pose = "walk"
                if not self.path or self.inv_timer < 6:
                    self.inv_phase = "look"
                    self.inv_timer = 4.0
                    self.pose = "look"
                    self.path = []
                    self.say(random.choice(INVESTIGATE_LINES))
            elif self.inv_phase == "look":
                self.pose = "look"
                if self.inv_timer <= 0:
                    self.say(random.choice(GIVE_UP_LINES))
                    self.set_marker("")
                    self.resume_routine()
        elif self.state == "alert":
            self.path = []
            self.pose = "look" if self.susp < 0.7 else "point"
            if self.last_seen:
                self.face_target = (self.last_seen[0], self.last_seen[2])
            self._step(dt, self.col)
        elif self.state == "fallen":
            self.fall_timer -= dt
            self.pose = "fallen"
            if self.fall_timer <= 0:
                self.say(random.choice(GETUP_LINES))
                self.state = getattr(self, "_pre_fall", "routine")
                self.path = getattr(self, "path_saved", [])
                self.r_started = self.state == "routine" and bool(self.path)
                if self.state == "routine" and not self.path:
                    self.r_started = False
        elif self.state == "sleep":
            sp = getattr(self, "sleep_pose", "sleep")
            if self.wake_timer > 0:
                self.wake_timer -= dt
                self.pose = sp if sp != "sleep" else "look"
                if sp == "sleep":
                    self.model.rig.rotation_x = -30
                if self.wake_timer <= 0:
                    self.pose = sp
                    self.say(random.choice(SLEEP_TALK), kind="sleepy")
            else:
                self.pose = sp
        elif self.state in ("scripted", "catch", "disabled"):
            spd = self._step(dt, self.col)
            if self.path:
                self.pose = "run" if self.walk_speed > 3.5 else "walk"
            elif self.pose in ("walk", "run"):
                self.pose = "idle"
        self._apply()
        # head look for alert states
        if self.state == "alert" and self.last_seen:
            want = math.degrees(math.atan2(self.last_seen[0] - self.x, self.last_seen[2] - self.z))
            self.model.head.rotation_y = max(-60, min(60, ang_diff(want, self.yaw)))
        self.model.animate(dt, spd if self.pose in ("walk", "run") else 0.0, self.pose)
        if self.marker_state:
            d = math.dist((self.x, self.y + 2.4, self.z), tuple(camera.world_position))
            self.marker.scale = 40 * max(0.2, min(1.0, d / 12.0))
        # flashlight
        if self.flashlight and g.env.is_dark:
            f = math.radians(self.facing())
            hx, hy, hz = self.x + math.sin(f) * 0.4, self.y + 1.3, self.z + math.cos(f) * 0.4
            g.env.flash = ((hx, hy, hz), (math.sin(f) * 0.97, -0.24, math.cos(f) * 0.97), 0.9, 0.96, 24.0, 2.2)
        # vision
        if self.state in ("routine", "investigate", "alert", "sleep") and self.detect:
            self._vision(dt)

    def _vision(self, dt):
        g = self.g
        p = g.player
        v, dist = self.visibility()
        self.sees_player = v > 0
        restricted = g.player_restricted()
        if self.sleeping and self.wake_timer <= 0:
            v = 0.0
        disguised = p.disguised and not p.galloping
        if v > 0 and restricted and disguised:
            if dist > 3.5:
                if not self.dale_greeted and dist < 14:
                    self.dale_greeted = True
                    self.say(random.choice(DALE_LINES))
                v = 0.0
            else:
                self.dale_t += dt
                if self.dale_t > 1.5 and self.bark_cd <= 0:
                    self.say(random.choice(DALE_SUS_LINES))
                    self.bark_cd = 5
                v *= 0.35
        if v > 0 and restricted:
            rate = v / (0.18 + dist * 0.1)
            self.susp = min(1.0, self.susp + rate * dt)
            self.last_seen = p.pos
            if self.susp >= 1.0:
                self.set_marker("!")
                self.state = "catch"
                self.path = []
                g.on_caught(self)
                return
            if self.susp > 0.3 and self.state in ("routine", "investigate", "sleep"):
                if self.state != "sleep":
                    self.state = "alert"
                self.set_marker("?")
                if self.bark_cd <= 0:
                    self.say(random.choice(SUSPICIOUS_LINES))
                    self.bark_cd = 4
                    g.audio.play("question", vol=0.7)
        else:
            decay = 0.18 if self.state in ("alert", "investigate") else 0.3
            self.susp = max(0.0, self.susp - decay * dt)
            if self.state == "alert":
                if self.susp < 0.25:
                    if self.last_seen:
                        self.investigate(self.last_seen)
                    else:
                        self.resume_routine()
        if self.state == "routine" and self.susp < 0.05 and self.marker_state:
            self.set_marker("")
