"""Farmer Chuck: routines, vision, hearing, suspicion, and a lot of tripping."""
from __future__ import annotations

import math
import random

from ursina import Text, camera, color, destroy

from . import models
from .engine.shading import SHADOW_MASK
from .npc import Walker, ang_diff
from .world import _seg_hits_box

# doors Chuck opens for himself on the way through, and shuts behind him (his house, his barn)
OWN_DOORS = ("front_door", "back_door", "barn_side")
# how far he sees: by day, in the dark, with the flashlight on you, and when you're under a lamp
SIGHT_DAY, SIGHT_DARK, SIGHT_TORCH, SIGHT_LIT = 30.0, 9.5, 27.0, 19.0

INVESTIGATE_LINES = [
    "Who's there?", "Dang raccoons.", "Dale? That you?", "Huh. Could've sworn...", "Hello? ...Hello?",
    "If that's you again, Gerald, I swear...", "Probably the wind. The wind throws rocks now.",
    "I'm armed! ...With a very stern voice!", "Nothing. Nothing's ever there.",
    "Show yourself! Unless you're big. Then don't.", "Is somebody stealin' my stuff? I got very little stuff!",
]
GIVE_UP_LINES = ["Huh. Nothing.", "Eh. Must be hearin' things.", "Back to work, Chuck.", "Stupid wind.",
                 "Note to self: get a dog. Another dog. A dog that stays.", "Whatever it was, it's gone now.",
                 "Mama always said I'd hear things. She was right about everything. Except Dale."]
SUSPICIOUS_LINES = ["Huh?", "Wha—?", "Hey...", "Is that a...?", "Hold on now..."]
TRIP_LINES = ["OOF!", "Whoa-OA-oa!", "Dang it!", "Who put the GROUND there?!", "My back!", "MY OTHER BACK!",
              "I'm suin' this dirt!"]
GETUP_LINES = ["I'm okay!", "Nobody saw that.", "Meant to do that.", "Ground's gettin' lower every year.",
               "That's a bruise. That's gonna be a bruise I show Dale."]
DALE_LINES = ["Mornin', Dale!", "Dale! Lookin' good, buddy!", "Hey Dale. You lose weight?",
              "Dale! Save some room for Sunday!", "Dale! Love the new look! Real... bovine!"]
SLEEP_TALK = ["zzz... Dale... that's MY potato salad...", "mmf... strike... STRIKE...", "...no, Mama, I did feed 'em...",
              "zzz... hnk... Big Earl... good boy... tasty boy...", "...forty-seven... forty-eight... zzz...",
              "...mmf... brisket... with a little rub... zzz..."]
DALE_SUS_LINES = ["Dale... you look different.", "Dale, why are you... chewing like that?", "You smell like a barn, Dale.",
                  "Dale, have you always had four legs?"]
STIR_LINES = ["Hnnh? ...Dale?", "Wha... who's there...", "mmph... potato salad...", "...mm? ...Mama?",
              "...zzz... hooves?... on the floor?... zzz..."]
GET_UP_LINES = ["Alright. Who's in my HOUSE?", "Somebody's down there. I heard that.", "That's it. I'm up. I'm UP.",
                "Gerald, if that's you, I've got a flashlight and I'm not afraid to shine it.",
                "Is somebody walkin' around in hooves? Who WEARS hooves?"]
HUM_LINES = ["Hey! HEY! No singin' in the pasture!", "Cows don't HUM! Stop HUMMIN'!",
             "Y'all sound like a transmission goin'. Knock it OFF!", "Is that... HARMONY? Who taught you harmony?!",
             "I'm comin' over there and I'm bringin' my stern voice!"]
BACK_TO_BED_LINES = ["Nothin'. Back to bed, Chuck.", "Probably the house settlin'. Houses settle.", "...Stupid raccoons.",
                     "If that was a ghost, I'm not payin' it rent."]
DOOR_LINES = {"pasture_gate": ["Who left the GATE open?!", "The gate's open. The gate is OPEN. Who opens a gate?"],
              "front_door": ["Now why's my front door open?", "Did I leave the door open? ...I didn't leave the door open.",
                             "Front door's open. If I've been robbed, they better've taken the lamp."],
              "back_door": ["Back door's open. I always lock the back door.", "Who's been usin' my back door?"],
              "_": ["Huh. Who left that open?", "That was shut. I know that was shut.", "Now that's funny. That was closed."]}


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
        self.range_day = SIGHT_DAY
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
        self.drowse = 0.0           # how disturbed his sleep is; at 1 he gets up to look
        self.bed = None             # (pos, yaw, pose, outfit, getup) while he has somewhere to go back to sleep
        self.door_to_close = None   # a door he's walking over to shut
        self.door_t = 0.0
        self.door_keys = OWN_DOORS
        self._my_doors = set()      # doors he opened (or found open on his way) and will shut behind him
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
        self.bed = None
        self.door_to_close = None

    def scripted(self):
        self.state = "scripted"
        self.path = []
        self.set_marker("")
        self.susp = 0.0

    def sleep(self, pos, yaw, pose="sleep", outfit="pajamas", getup=None):
        """getup: where he stands when something wakes him properly (in bed only); None = he just stirs."""
        self.bed = (pos, yaw, pose, outfit, getup)
        self.teleport(pos, yaw)
        self.state = "sleep"
        self.sleeping = True
        self.wake_timer = 0.0
        self.drowse = 0.0
        self.flashlight = False
        self.door_to_close = None
        if getattr(self, "_lit_house", False):
            self._lit_house = False
            for k in ("house_bed", "house_hall"):
                self.g.world.set_lamp(k, False)
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
        self.g.event("chuck_trip")
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
            rng = SIGHT_DARK
        lit = False
        if dark:
            if self.flashlight:
                f = self.facing()
                a = abs(ang_diff(math.degrees(math.atan2(dx, dz)), f))
                if a < 24 and dist < SIGHT_TORCH:
                    lit = True
                    rng = SIGHT_TORCH
            if g.player_lit():
                lit = True
                rng = max(rng, SIGHT_LIT)
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
        if self.sleeping:
            return self._hear_asleep(pos, radius, source)
        if source == "footfall":
            return False        # ordinary walking: only a light sleeper notices that
        d = math.hypot(pos[0] - self.x, pos[2] - self.z)
        if source == "herd_hum":
            # the herd singing: he stomps over to the pasture gate to yell at them
            if self.state not in ("routine", "investigate") or d > radius * self.hearing:
                return False
            self.say(random.choice(HUM_LINES), force=True)
            self.bark_cd = 5.0
            self.investigate(pos, quiet=True)
            self.inv_timer = 30.0       # long enough to get there from anywhere on the farm
            return True
        eff = radius * self.hearing * (0.45 if self.sleeping else 1.0)
        if d > eff:
            return False
        if self.g.noise_masked(pos):
            return False
        if source == "moo" and self.g.phys.in_zone("pasture", pos[0], pos[2]):
            return False
        if source == "steps" and self.g.phys.in_zone("pasture", pos[0], pos[2]):
            return False
        self.investigate(pos)
        return True

    # ------------------------------------------------------------------
    # asleep: noises in the house carry, and he's a light sleeper
    # ------------------------------------------------------------------
    def _disturbance(self, pos, radius, source):
        g = self.g
        d = math.hypot(pos[0] - self.x, pos[2] - self.z)
        if source == "footfall":
            # walking (not sneaking) near him: a few strides close by and he's up, further off it takes a while
            if g.phys.in_zone("house", pos[0], pos[2]) and g.phys.in_zone("house", self.x, self.z):
                return 0.3 * max(0.2, 1.0 - d / 14.0)
            return 0.3 * max(0.0, 1.0 - d / 6.0)
        if g.phys.in_zone("house", pos[0], pos[2]) and g.phys.in_zone("house", self.x, self.z):
            # anything that clatters wakes him outright; galloping on the floorboards takes a few strides
            return {"thrown": 1.0, "crash": 1.0, "flush": 1.0, "radio": 1.0, "moo": 1.0, "shotgun": 1.0, "headbutt": 0.7,
                    "steps": 0.35 if g.player.galloping else 0.2, "door": 0.35,
                    "drawer": 0.0 if g.player.crouching else 0.25}.get(source, 0.5)
        if source == "steps" and g.player.galloping and d < 9.0:
            return 0.45     # hooves at a gallop: never quieter than walking past
        if d > radius * self.hearing * 0.45:
            return 0.0
        return 1.0 if source in ("thrown", "crash", "moo", "radio", "flush", "shotgun") else 0.45

    def _hear_asleep(self, pos, radius, source):
        amt = self._disturbance(pos, radius, source)
        if amt <= 0 or self.g.noise_masked(pos):
            return False
        can_get_up = self.bed is not None and self.bed[4] is not None
        self.drowse += amt
        if can_get_up and self.drowse >= 0.99:
            self.get_up(pos)
            return True
        if self.wake_timer <= 0:
            self.say(random.choice(STIR_LINES), kind="sleepy")
        self.wake_timer = 3.5
        return True

    def get_up(self, pos):
        """Properly awake: out of bed, flashlight on, lights on, and off to see what that was."""
        g = self.g
        self.wake()
        self.drowse = 0.0
        self.wake_timer = 0.0
        gx, gy, gz = self.bed[4]
        self.teleport((gx, gy, gz), math.degrees(math.atan2(pos[0] - gx, pos[2] - gz)))
        self.set_outfit(self.bed[3] or "pajamas")
        self.flashlight = True
        self.state = "routine"
        self.routine = []
        self.pose = "idle"
        self._lit_house = True
        for k in ("house_bed", "house_hall"):
            g.world.set_lamp(k, True)
        self.say(random.choice(GET_UP_LINES), force=True)
        self.bark_cd = 3.0
        g.audio.play("question", vol=0.8)
        self.investigate(pos)

    def back_to_bed(self):
        self.state = "tobed"
        self.set_marker("")
        self.goto(self.bed[4], 2.0)

    # ------------------------------------------------------------------
    # doors he knows he shut
    # ------------------------------------------------------------------
    def _check_doors(self, dt):
        """Notice a door the player opened and left open: suspicious, and he goes to shut it."""
        self.door_t -= dt
        if self.door_t > 0 or self.door_to_close:
            return
        self.door_t = 0.4
        g = self.g
        ex, ey, ez = self.eye()
        dark = g.env.is_dark
        for key, d in g.world.doors.items():
            if not d.is_open or not d.player_opened:
                continue
            cx, cz = d.center()
            dist = math.hypot(cx - ex, cz - ez)
            rng = 22.0 if not dark else (18.0 if self.flashlight else 8.0)
            if dist > rng:
                continue
            if abs(ang_diff(math.degrees(math.atan2(cx - ex, cz - ez)), self.facing())) > self.fov / 2:
                continue
            if not g.phys.line_of_sight((ex, ey, ez), (cx, 1.2, cz), (self.col, d.col)):
                continue
            d.player_opened = False
            self.say(random.choice(DOOR_LINES.get(key, DOOR_LINES["_"])), force=dist < 20)
            self.bark_cd = 4.0
            g.audio.play("question", vol=0.7)
            self.susp = max(self.susp, 0.45)
            if key in self.door_keys and self._route_crosses(d):
                # he's going through it anyway: in he goes, and he shuts it behind him
                self._my_doors.add(key)
                return
            self.door_to_close = key
            # walk up to it from his side and shut it
            k = 1.3 / max(dist, 0.01)
            self.investigate((cx + (ex - cx) * k, 0.0, cz + (ez - cz) * k), quiet=True)
            return

    def _route_crosses(self, d, legs=4):
        """Does the path he's on go through door d?"""
        pts = [(self.x, self.y, self.z)] + list(self.path[:legs])
        if len(pts) < 2 and self.state == "routine" and self.routine:
            # between routine steps: the next "go" is where he's headed
            for st in self.routine[self.r_i:self.r_i + 3]:
                if st[0] == "go":
                    pts.append(st[1])
                    break
        return any(_seg_hits_box(a, b, d.col, 0.2) for a, b in zip(pts, pts[1:]))

    def _doors_tick(self):
        """Open his own doors when one's in his way; shut the ones he opened once he's through."""
        g = self.g
        doors = g.world.doors
        if self.path:
            nx, _, nz = self.path[0]
            dx, dz = nx - self.x, nz - self.z
            d = math.hypot(dx, dz)
            if d > 1e-3:
                ahead = min(d, 1.3)
                a = (self.x, self.y, self.z)
                b = (self.x + dx / d * ahead, self.y, self.z + dz / d * ahead)
                for key in self.door_keys:
                    door = doors.get(key)
                    if door is None or door.is_open or not _seg_hits_box(a, b, door.col, 0.25):
                        continue
                    door.set_open(True)
                    cx, cz = door.center()
                    g.audio.play("door_creak", vol=0.7, pos=(cx, self.y + 1, cz), rng=40)
                    self._my_doors.add(key)
        for key in list(self._my_doors):
            door = doors.get(key)
            if door is None or not door.is_open:
                self._my_doors.discard(key)
                continue
            cx, cz = door.center()
            if math.hypot(self.x - cx, self.z - cz) < 2.2 or self._route_crosses(door, 2):
                continue
            p = g.player
            if math.hypot(p.x - cx, p.z - cz) < 1.3:
                continue        # not on a cow standing in the doorway
            door.set_open(False)
            g.audio.play("door_close", vol=0.7, pos=(cx, self.y + 1, cz), rng=35)
            self._my_doors.discard(key)

    def _shut_door(self):
        key, self.door_to_close = self.door_to_close, None
        d = self.g.world.doors.get(key)
        if d is not None and d.is_open:
            d.set_open(False)
            self.g.audio.play("door_close", vol=0.8, pos=(self.x, 1, self.z), rng=35)

    def investigate(self, pos, quiet=False):
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
        if self.bark_cd <= 0 and not quiet:
            self.say(random.choice(["Huh?", "What was that?", "Hm?", "Who's there?"]))
            self.bark_cd = 3.0

    # ------------------------------------------------------------------
    def update(self, dt):
        tucked = self.visible and self.state == "sleep" and getattr(self, "sleep_pose", "") == "sleep"
        # a couple of frames in, so the model is already lying down when the quilt is shaped to him
        self._tuck_n = getattr(self, "_tuck_n", 0) + 1 if tucked else 0
        self.g.world.show_bed_covers(self._tuck_n > 2, self.model)
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
                    if self.door_to_close:
                        self._shut_door()
                        self.say("There.")
                    else:
                        self.say(random.choice(INVESTIGATE_LINES))
            elif self.inv_phase == "look":
                self.pose = "look"
                if self.inv_timer <= 0:
                    self.set_marker("")
                    if self.bed is not None and self.bed[4] is not None:
                        self.say(random.choice(BACK_TO_BED_LINES))
                        self.back_to_bed()
                    else:
                        self.say(random.choice(GIVE_UP_LINES))
                        self.resume_routine()
        elif self.state == "tobed":
            spd = self._step(dt, self.col)
            self.pose = "walk" if self.path else "idle"
            if not self.path:
                pos, yaw, pose, outfit, getup = self.bed
                self.sleep(pos, yaw, pose, outfit, getup)
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
            self.drowse = max(0.0, self.drowse - dt * 0.05)
            if self.wake_timer > 0:
                self.wake_timer -= dt
                # lying there, head turning on the pillow (or looking round from his chair)
                self.pose = "sleep_look" if sp == "sleep" else "look"
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
        if self.state != "sleep":
            self._doors_tick()
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
        if self.state in ("routine", "investigate", "alert", "sleep", "tobed") and self.detect:
            self._vision(dt)
        if self.state in ("routine", "investigate", "tobed") and self.detect:
            self._check_doors(dt)

    def _vision(self, dt):
        g = self.g
        p = g.player
        v, dist = self.visibility()
        self.sees_player = v > 0
        restricted = g.player_restricted()
        if self.sleeping and (self.wake_timer <= 0 or self.wake_timer > 3.0):
            v = 0.0     # asleep, or only just stirring (half a second to duck before his eyes open)
        disguised = p.disguised and not p.galloping
        if v > 0 and restricted and disguised:
            if dist > 3.5:
                if not self.dale_greeted and dist < 14:
                    self.dale_greeted = True
                    self.say(random.choice(DALE_LINES))
                    self.g.event("dale")
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
            if self.susp > 0.3 and self.state in ("routine", "investigate", "sleep", "tobed"):
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
