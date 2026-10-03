"""Automated walkthrough: plays the story from a given day to the credits, the way a player would.

    xvfb-run -s "-screen 0 1280x720x24" python tools/walkthrough.py --day 1 --to 7 [--detect] [--shots]

The bot presses E on things, headbutts, throws rocks, moos, types passwords, drives the tractor and
fights. Every story step must finish within a time limit or the run fails with a state dump.
Chuck's eyes are off by default (--detect turns them on) so a run is deterministic. --caught all
(or a comma list of step keys) makes Chuck catch you once per step, the first time you're somewhere
you shouldn't be, then checks the caught sequence hands control back and the step still finishes.
"""
from __future__ import annotations

import argparse
import math
import sys
import time as _time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness  # noqa: E402

FPS = 30
DT = 1.0 / FPS


class Stuck(Exception):
    pass


class Bot:
    def __init__(self, app, g, args):
        self.app = app
        self.g = g
        self.args = args
        self.frame = 0
        self.plan = None
        self.plan_key = None
        self.errors = []
        self.log = []
        self.step_t0 = 0
        self.choice_queue = []
        self.password = "BIGAJAX"
        self.combo = "117"
        self.shots = args.shots
        self.catch = set((args.caught or "").split(",")) - {""}
        self.caught_steps = set()
        self.watch = None
        orig = g._script_error

        def on_err(s):
            self.errors.append((s.name, s.error))
            print(f"!! SCRIPT ERROR in {s.name}\n{s.error}", flush=True)
            orig(s)
        g.runner.on_error = on_err
        from ursina import application
        self.base = application.base
        self._n_outputs = 0
        if not args.render:
            self.set_rendering(False)

    def set_rendering(self, on):
        # every output, not just the window: the shadow map and the scene buffer would keep rendering
        eng = self.base.graphicsEngine
        for i in range(eng.getNumWindows()):
            eng.getWindow(i).setActive(on)
        self._n_outputs = eng.getNumWindows()

    def keep_dark(self):
        # Panda registers a new buffer on the frame after it's made, so catch late arrivals
        if not self.args.render and self.base.graphicsEngine.getNumWindows() != self._n_outputs:
            self.set_rendering(False)

    # ------------------------------------------------------------------
    def shot(self, name):
        from breakowt.engine.boot import screenshot
        self.set_rendering(True)
        self.app.step()
        shots = harness.shots_dir()
        shots.mkdir(parents=True, exist_ok=True)
        screenshot(str(shots / f"wt_{name}.png"))
        if not self.args.render:
            self.set_rendering(False)

    def tick(self):
        g = self.g
        ui = g.ui
        self.keep_dark()
        # dialogue, choices, documents, modals
        if g.in_dialogue:
            if ui.choice_root.enabled and ui.choice_items and ui.choice_result is None:
                idx = self.choice_queue.pop(0) if self.choice_queue else 0
                ui.choice_result = idx
            elif ui.dlg_revealed():
                g._advance = True
            else:
                ui.dlg_complete()
        if ui.modal == "document":
            g._modal_input("e")
        elif ui.modal == "mail":
            g._modal_input("e")
        elif ui.modal == "combo":
            st = ui._modal_state
            if st.get("result") is None:
                st["result"] = self.combo
        elif ui.modal == "password":
            st = ui._modal_state
            if st.get("result") is None:
                st["result"] = self.password
        elif ui.modal == "shop":
            st = ui._modal_state
            if st.get("back_cb"):
                st["back_cb"]()
        if g.cutscene and not g.in_dialogue:
            g._advance = True
        self.app.step()
        self.frame += 1

    # ------------------------------------------------------------------
    # actions (generators)
    # ------------------------------------------------------------------
    def wait(self, secs):
        n = int(secs * FPS)
        for _ in range(n):
            yield

    def until(self, cond, timeout=60, what="condition"):
        t = 0
        while not cond():
            t += DT
            if t > timeout:
                raise Stuck(f"timed out waiting for {what}")
            yield

    def ready(self):
        g = self.g
        return g.controls_enabled() and not g.busy and not g.in_dialogue

    def wait_ready(self, timeout=90):
        yield from self.until(self.ready, timeout, "controls")

    def place(self, x, z, yaw=None, y=None):
        g = self.g
        p = g.player
        if y is None:
            gh, _ = g.phys.ground(x, z, 10.0)
            # floors are only reachable from below within a step; take the highest floor under us
            y = gh
        p.teleport(x, y, z, yaw)

    def face(self, pt):
        self.g.player.look_at_point(pt)

    def press(self, key):
        self.g.input(key)

    def open_door(self, key):
        # E toggles a door, so only press it on a closed one (a plan can restart after a catch)
        if not self.g.world.doors[key].is_open:
            yield from self.interact(key)

    def interact(self, key, dist=None, prompt_contains=None, direct_ok=True):
        """Walk up to an interactable, look at it and press E."""
        g = self.g
        yield from self.wait_ready()
        ia = g.ia.get(key)
        if ia is None:
            raise Stuck(f"no interactable {key}")
        px, py, pz = ia.world_pos()
        p = g.player
        d = dist if dist is not None else max(1.2, min(ia.reach * 0.7, ia.reach - 0.3))
        # approach from the player's side, falling back to a ring search for a free spot
        best = None
        base_ang = math.atan2(p.x - px, p.z - pz)
        for k in range(16):
            a = base_ang + (k // 2) * (math.pi / 8) * (1 if k % 2 else -1)
            for dd in (d, d * 0.75, d * 1.2):
                x, z = px + math.sin(a) * dd, pz + math.cos(a) * dd
                gh, _ = g.phys.ground(x, z, py + 0.2)
                if g.phys.blocked_at(x, z, 0.55, gh, 1.5):
                    continue
                eye = (x, gh + 1.42, z)
                # same rule as the game: the ray stops just short of the target
                dist = math.dist(eye, (px, py, pz))
                back = max(0.0, dist - ia.radius - 0.2) / max(dist, 1e-6)
                end = (eye[0] + (px - eye[0]) * back, eye[1] + (py - eye[1]) * back, eye[2] + (pz - eye[2]) * back)
                if back > 0.05 and not g.phys.line_of_sight(eye, end, include_dynamic=False):
                    continue
                best = (x, gh, z)
                break
            if best:
                break
        if best is None:
            best = (px + math.sin(base_ang) * d, 0, pz + math.cos(base_ang) * d)
        p.teleport(best[0], best[1], best[2])
        yield
        self.face(ia.world_pos())
        yield
        yield
        if g.target is not ia:
            self.face(ia.world_pos())
            yield
        if g.target is not ia:
            msg = f"targeting: wanted {key}, got {g.target.key if g.target else None} at ({p.x:.1f},{p.z:.1f})"
            if not direct_ok:
                raise Stuck(msg)
            self.log.append("WARN " + msg)
            print("WARN", msg, flush=True)
            g.interact(ia)
        else:
            h = ia.active_handler(g)
            if self.args.verbose:
                print(f"    E on {key}: {h.prompt(g) if h and callable(h.prompt) else (h.prompt if h else ia.text)}"
                      f" busy={g.busy} ctl={g.controls_enabled()}", flush=True)
            self.press("e")
        yield
        yield

    def talk_to(self, cow_key):
        yield from self.interact(f"cow_{cow_key}")
        yield from self.until(lambda: not self.g.busy, 120, f"talk {cow_key}")

    def walk_to(self, x, z, tol=0.8, timeout=40, run=False):
        """Real walking with WASD, steering toward the point."""
        from ursina import held_keys
        g = self.g
        p = g.player
        t = 0
        last = (p.x, p.z)
        stall = 0
        sidesteps = 0
        try:
            while math.hypot(p.x - x, p.z - z) > tol:
                if not g.controls_enabled():
                    held_keys["w"] = 0
                    yield
                    continue
                want = math.degrees(math.atan2(x - p.x, z - p.z))
                p.yaw = want
                p.pitch = 0
                held_keys["w"] = 1
                held_keys["shift"] = 1 if run else 0
                yield
                t += DT
                if t > timeout:
                    raise Stuck(f"walk to ({x},{z}) from ({p.x:.1f},{p.z:.1f})")
                if int(t * FPS) % 30 == 0:
                    if math.hypot(p.x - last[0], p.z - last[1]) < 0.3:
                        stall += 1
                        if stall > 3 and sidesteps < 4:
                            # something in the way (a cow, usually): step round it, like a player would
                            sidesteps += 1
                            stall = 0
                            side = "d" if sidesteps % 2 else "a"
                            held_keys["w"] = 0
                            held_keys[side] = 1
                            for _ in range(int(0.7 * FPS)):
                                yield
                            held_keys[side] = 0
                        elif stall > 3:
                            raise Stuck(f"walk blocked at ({p.x:.1f},{p.z:.1f}) going to ({x},{z})")
                    else:
                        stall = 0
                    last = (p.x, p.z)
        finally:
            held_keys["w"] = 0
            held_keys["shift"] = 0
            held_keys["a"] = held_keys["d"] = 0

    def walk_path(self, pts, **kw):
        for x, z in pts:
            yield from self.walk_to(x, z, **kw)

    def headbutt_at(self, pt, dist=1.6):
        g = self.g
        yield from self.wait_ready()
        p = g.player
        ang = math.atan2(p.x - pt[0], p.z - pt[2])
        self.place(pt[0] + math.sin(ang) * dist, pt[2] + math.cos(ang) * dist)
        yield
        self.face(pt)
        yield
        self.press("left mouse down")
        yield from self.wait(0.9)

    def push_crate(self, key, dirx, dirz, n=1):
        """Headbutt a crate n steps along (dirx, dirz), standing behind it each time like a player would."""
        g = self.g
        pb = g.world.pushables[key]
        for _ in range(n):
            yield from self.wait_ready()
            x0, z0 = pb.x, pb.z
            self.place(pb.x - dirx * 1.3, pb.z - dirz * 1.3, y=pb.y)
            yield
            self.face((pb.x, pb.y + 0.5, pb.z))
            yield
            self.press("left mouse down")
            yield from self.wait(1.0)
            if math.hypot(pb.x - x0, pb.z - z0) < 0.5:
                raise Stuck(f"{key} didn't move from ({x0:.1f},{z0:.1f}) toward ({dirx},{dirz})")

    def push_to(self, key, tx, tz):
        """Push a crate to (tx, tz) from wherever it is now: along x first, then along z."""
        pb = self.g.world.pushables[key]
        nx = round((tx - pb.x) / pb.step)
        if nx:
            yield from self.push_crate(key, 1 if nx > 0 else -1, 0, abs(nx))
        nz = round((tz - pb.z) / pb.step)
        if nz:
            yield from self.push_crate(key, 0, 1 if nz > 0 else -1, abs(nz))

    def hop_onto(self, x, z, top, from_dx, from_dz):
        """Walk at something from (x + from_dx, z + from_dz) and hop up onto it, for real."""
        from ursina import held_keys
        g = self.g
        p = g.player
        yield from self.wait_ready()
        self.place(x + from_dx, z + from_dz, y=p.y if p.y > 0.2 else None)
        yield
        p.yaw = math.degrees(math.atan2(x - p.x, z - p.z))
        p.pitch = 0
        held_keys["w"] = 1
        try:
            for i in range(60):
                if i == 4:
                    self.press("space")
                yield
                if p.y >= top - 0.05 and math.hypot(p.x - x, p.z - z) < 0.45:
                    break
        finally:
            held_keys["w"] = 0
        yield from self.wait(0.3)
        if p.y < top - 0.05:
            raise Stuck(f"couldn't hop up onto ({x},{z}) top {top}: at y {p.y:.2f}")

    def get_rock(self):
        g = self.g
        if not g.inv.has("rock"):
            yield from self.interact("rockpile_3")
        yield

    def throw_at(self, target, from_pos):
        """Throw a rock at target from from_pos (x, y, z), solving the arc numerically."""
        g = self.g
        p = g.player
        yield from self.wait_ready()
        p.teleport(from_pos[0], from_pos[1], from_pos[2])
        yield
        ex, ey, ez = p.eye_pos
        dx, dz = target[0] - ex, target[2] - ez
        yaw = math.degrees(math.atan2(dx, dz))
        best, best_err = 0.0, 1e9
        for pitch in [x * 0.5 for x in range(-60, 150)]:
            cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
            fx, fy, fz = math.sin(math.radians(yaw)) * cp, sp, math.cos(math.radians(yaw)) * cp
            sx, sy, sz = ex + fx * 0.7, ey - 0.1 + fy * 0.7, ez + fz * 0.7
            vx, vy, vz = fx * 14, fy * 14 + 3.2, fz * 14
            err = 1e9
            for _ in range(200):
                vy -= 18 * DT
                sx, sy, sz = sx + vx * DT, sy + vy * DT, sz + vz * DT
                e = math.dist((sx, sy, sz), target)
                err = min(err, e)
            if err < best_err:
                best, best_err = pitch, err
        p.yaw = yaw
        p.pitch = -best
        g.inv.select_key("rock")
        yield
        self.press("r")
        yield from self.wait(1.5)

    # ------------------------------------------------------------------
    # plans for each story step
    # ------------------------------------------------------------------
    def plan_for(self, key):
        fn = getattr(self, "p_" + key, None)
        return fn() if fn else None

    def p_d1_oak(self):
        yield from self.headbutt_at((-50, 1.4, -35), dist=2.2)

    def p_d1_page(self):
        yield from self.until(lambda: self.g.ia.get("st_page") is not None, 10, "page item")
        yield from self.interact("st_page")

    def p_d1_crew(self):
        for k in ("moozart", "sirloin", "cowpernicus", "mooriarty", "moomaw"):
            yield from self.talk_to(k)

    def p_d1_meeting(self):
        yield from self.wait_ready()
        self.place(-50, -40, 0)
        yield from self.wait(1)

    def p_d1_pencil(self):
        g = self.g
        f = g.farmer
        yield from self.until(lambda: f.pose == "count", 60, "Chuck counting")
        yield from self.wait(1.0)
        p = g.player
        p.crouch_toggle = True
        fy = math.radians(f.yaw)
        self.place(f.x - math.sin(fy) * 1.5, f.z - math.cos(fy) * 1.5)
        yield
        yield from self.interact("st_chuck", dist=1.5)
        yield from self.until(lambda: g.inv.has("pencil"), 10, "pencil")
        p.crouch_toggle = False

    def p_d1_sleep(self):
        yield from self.interact("bed47")

    def p_d2_sleep(self):
        g = self.g
        if g.inv.has("bucket"):
            yield from self.talk_to("sirloin")
        if g.inv.has("glasses"):
            yield from self.talk_to("cowpernicus")
        yield from self.interact("bed47")

    p_d3_sleep = p_d1_sleep

    def p_d2_out(self):
        g = self.g
        yield from self.talk_to("cowleen")
        yield from self.until(lambda: g.world.doors["pasture_gate"].is_open, 120, "gate open")
        yield from self.until(lambda: g.phys.in_zone("pasture", g.farmer.x, g.farmer.z), 30, "Chuck in pasture")
        yield from self.wait(1.0)
        self.place(-21.5, -35, 90)
        yield
        yield from self.walk_to(-14.5, -35)

    def p_d2_board(self):
        g = self.g
        for i in range(3):
            yield from self.until(lambda: g.story.revving, 120, "tractor revving")
            yield from self.headbutt_at((-12.0, 1.0, -22.2), dist=1.5)
            yield from self.wait(0.5)
        yield from self.wait_ready()
        self.place(-7.5, -22, 90)
        yield from self.wait(0.5)

    def p_d2_shed(self):
        g = self.g
        # (a catch restarts this plan: skip whatever's already done)
        if not g.inv.has("pliers"):
            yield from self.interact("toolbox")
            yield from self.until(lambda: g.inv.has("pliers"), 20, "pliers")
            yield from self.until(lambda: not g.busy, 20, "bell")
        for k in ("st_glasses", "st_bucket"):
            if g.ia.get(k) is not None:
                yield from self.interact(k)
        if g.inv.has("radio"):
            return
        # the radio's on the tall cabinet: nudge the crate over, hop up, take it
        yield from self.push_to("shed_crate", -5.5, -24.6)
        pb = self.g.world.pushables["shed_crate"]
        yield from self.hop_onto(pb.x, pb.z, pb.y + pb.h, -1.4, 0)
        yield from self.interact("st_radio", dist=1.0)

    def p_d2_return(self):
        g = self.g
        yield from self.wait_ready()
        if g.phys.in_zone("pasture", g.player.x, g.player.z):
            yield from self.wait(1.0)       # a catch already put us back in the pasture: that's the step done
            return
        self.place(-7.5, -22, 270)
        yield from self.walk_path([(-11, -22), (-14, -22.2), (-15, -30), (-15.5, -35)])
        if not g.world.doors["pasture_gate"].is_open:
            yield from self.interact("pasture_gate")
        yield from self.until(lambda: g.world.doors["pasture_gate"].is_open, 5, "gate opens")
        yield from self.walk_to(-24, -35)

    def p_d2_radio(self):
        g = self.g
        if not g.flags.get("radio_static"):
            yield from self.talk_to("moozart")
        # the radio needs an aerial: set it down against the electric fence
        if g.inv.has("radio"):
            yield from self.wait_ready()
            self.place(-19.3, -45.0, 90)
            g.player.pitch = 0
            g.inv.select_key("radio")
            yield
            self.press("q")
        yield from self.until(lambda: g.story.cur != "d2_radio", 60, "farm report")

    def p_d2_ram(self):
        yield from self.talk_to("cowpernicus")
        # favors, now that nobody has anything else to say
        yield from self.talk_to("sirloin")
        yield from self.talk_to("cowpernicus")

    def p_d3_moohole(self):
        g = self.g
        if not g.inv.has("boot") and not g.flags.get("moohole_open"):
            yield from self.interact("st_boot")
        yield from self.interact("moohole")
        yield from self.until(lambda: g.flags.get("moohole_open"), 5, "moohole")
        # walk through it for real
        yield from self.wait_ready()
        self.place(-22, -66.1, 90)
        yield from self.walk_to(-14.5, -66.1)

    def p_d3_barn(self):
        g = self.g
        yield from self.wait_ready()
        self.place(4.5, 0.7, 90)
        yield from self.open_door("barn_side")
        yield from self.until(lambda: g.world.doors["barn_side"].is_open, 3, "side door")
        yield from self.wait(0.6)
        yield from self.walk_to(13, 0.7)
        yield from self.interact("tractor")

    def p_d3_parts(self):
        g = self.g
        # the key: up the ramp, nudge the loft crate under it, hop on, hop for it
        yield from self.wait_ready()
        self.place(14, 0.7)
        yield from self.walk_path([(15, -6), (29, -6.5), (31.4, -7.0), (31.4, 5.5), (25, 8)])
        yield from self.push_to("loft_crate", 22.0, 10.0)
        pb = g.world.pushables["loft_crate"]
        yield from self.hop_onto(pb.x, pb.z, pb.y + pb.h, 0, -1.4)
        yield from self.wait(0.6)
        self.press("space")
        yield from self.until(lambda: g.inv.has("tractor_key"), 3, "hop-grab the key")
        yield from self.wait(0.6)
        # the coop
        yield from self.wait_ready()
        self.place(31.5, -35, 90)
        yield from self.open_door("coop_gate")
        yield from self.until(lambda: g.world.doors["coop_gate"].is_open, 3, "coop gate")
        yield from self.wait(0.6)
        yield from self.walk_to(37.5, -35)
        yield from self.fight_cluck()
        yield from self.interact("st_jerrycan")
        yield from self.interact("tractor")
        yield from self.until(lambda: g.flags.get("tractor_fueled"), 5, "fueled")

    def fight_cluck(self):
        g = self.g
        p = g.player
        yield from self.until(lambda: g.story.enemy is not None and g.story.enemy.active, 60, "cluck fight")
        t = 0
        while g.story.enemy is not None and g.story.enemy.alive:
            e = g.story.enemy
            if not e.active:
                yield
                continue
            d = math.hypot(e.x - p.x, e.z - p.z)
            if d > 1.8:
                k = min(1.0, 5 * DT / d)
                p.x += (e.x - p.x) * k
                p.z += (e.z - p.z) * k
                p.col.x, p.col.z = p.x, p.z
            self.face((e.x, 0.6, e.z))
            if d < 2.2 and p.headbutt_cd <= 0:
                self.press("left mouse down")
            yield
            t += DT
            if t > 90:
                raise Stuck("cluck fight too long")
        yield from self.until(lambda: g.flags.get("cluck_beaten"), 60, "cluck beaten")

    def p_d3_trough(self):
        g = self.g
        yield from self.wait_ready()
        self.place(-14.5, -66.1, 270)
        yield from self.walk_to(-22, -66.1)
        self.place(-31, -18, 180)
        yield from self.until(lambda: g.is_done("trough"), 20, "trough cutscene")
        yield from self.until(lambda: any(o["key"] == "wash" for o in g.objectives), 90, "wash objective")
        yield from self.interact("trough")

    def p_d4_escort(self):
        g = self.g
        mz = g.cows["moozart"]
        yield from self.wait_ready()
        self.place(-50, -8, 180)
        route = [(-50, -16), (-40, -30), (-26, -58), (-21, -66.1), (-15, -66.1), (-14, -50), (-14.5, -36), (-14, -22.2),
                 (-16, -10), (-14, 0.7), (4.6, 0.7)]
        moo_t = [0.0]

        def pace():
            # wait for Archimoodes to catch up and shush him when he starts humming
            moo_t[0] -= DT
            st_warn = g.story.hooks.get("moo")
            if moo_t[0] <= 0 and not g.phys.in_zone("pasture", mz.x, mz.z):
                moo_t[0] = 6.0
                self.press("m")
        for x, z in route:
            yield from self.walk_to(x, z, timeout=60)
            t = 0
            while math.hypot(mz.x - g.player.x, mz.z - g.player.z) > 5:
                pace()
                yield
                t += DT
                if t > 40:
                    raise Stuck(f"Archimoodes not following at ({x},{z}); he's at ({mz.x:.1f},{mz.z:.1f})")
            pace()
        yield from self.open_door("barn_side")
        yield from self.wait(0.8)
        for x, z, y in [(13, 0.7, 0), (15, -6, 0), (29, -6.5, 0), (31.4, -7.2, 0), (31.4, 5.5, 3.2), (25, 8, 3.2),
                        (17, 9.5, 3.2)]:
            yield from self.walk_to(x, z, timeout=60)
            t = 0
            while math.hypot(mz.x - g.player.x, mz.z - g.player.z) > 5 or abs(mz.y - g.player.y) > 1.0:
                pace()
                yield
                t += DT
                if t > 40:
                    raise Stuck(f"Archimoodes not following in barn at ({x},{z}); he's at "
                                f"({mz.x:.1f},{mz.y:.1f},{mz.z:.1f})")

    def p_d4_loft(self):
        # all cutscene: Archimoodes writes the plan down
        yield from self.wait(0.5)

    def p_d4_back(self):
        yield from self.wait_ready()
        self.place(-14.5, -66.1, 270)
        yield from self.walk_to(-22, -66.1)

    def p_d4_vigil(self):
        yield from self.until(lambda: self.g.ia.get("st_prints") is not None, 30, "prints")
        yield from self.interact("st_prints")

    def p_d5_key(self):
        g = self.g
        yield from self.interact("doormat")
        yield from self.interact("flowerpot")
        # Gary: the fisherman with the bare hook (a level look, the way a player stands in front of him)
        i = g.flags["gnome_order"].index("empty")
        gx, gz = g.world.gnome_spots[i]
        yield from self.headbutt_at((gx, 1.42, gz), dist=1.5)
        yield from self.until(lambda: g.inv.has("house_key"), 5, "gnome key")
        yield from self.open_door("front_door")
        yield from self.until(lambda: g.world.doors["front_door"].is_open, 5, "front door")
        yield from self.wait(0.6)
        self.place(56, 26.5, 0)
        yield from self.walk_to(56, 33)

    def p_d5_inside(self):
        self.choice_queue = [0]
        yield from self.interact("st_sparkplug")
        yield from self.interact("st_photo")
        yield from self.interact("computer")
        yield from self.until(lambda: self.g.flags.get("emails_read"), 30, "emails")

    def p_d5_return(self):
        g = self.g
        if g.inv.has("shoes"):
            pass
        yield from self.wait_ready()
        self.place(63, 38, 90)
        yield from self.open_door("back_door")
        yield from self.until(lambda: g.world.doors["back_door"].is_open, 3, "back door")
        yield from self.wait(0.6)
        self.place(66.5, 41, 90)
        yield from self.walk_to(71, 41)
        yield from self.walk_to(74, 44)

    def p_d5_meeting(self):
        yield from self.wait_ready()
        self.place(-50, -40, 0)
        yield from self.wait(1)

    def p_d5_sleep(self):
        yield from self.talk_to("moomaw")
        yield from self.interact("bed47")

    def p_d6_prep(self):
        g = self.g
        yield from self.extras()
        yield from self.wait_ready()
        self.place(4.5, 0.7, 90)
        yield from self.open_door("barn_side")
        yield from self.wait(0.6)
        yield from self.walk_to(13, 0.7)
        yield from self.interact("tractor")
        yield from self.until(lambda: g.flags.get("sparkplug_in"), 5, "plug")
        # two long planks from the pile, and the shed board you knocked in on Tuesday (in through the hole)
        laid = g.flags.get("planks_laid", 0)
        while g.flags.get("pile_taken", 0) < 2 and g.inv.count("plank") + laid < 3:
            yield from self.interact("woodpile")
        if not g.flags.get("shed_plank_taken") and g.inv.count("plank") + laid < 3:
            yield from self.walk_path([(-15, -30), (-14.5, -22.2), (-10.2, -22.2)])
            yield from self.interact("shed_plank")
            yield from self.until(lambda: g.flags.get("shed_plank_taken"), 5, "shed board")
        # carry them for real part of the way, then over to the grid
        yield from self.wait_ready()
        self.place(0, 60, 0)
        yield from self.walk_to(0, 77)
        while g.inv.has("plank"):
            yield from self.interact("cattle_grid")
        for i in range(5):
            yield from self.interact(f"herd_{i * 3}")
            yield from self.until(lambda: not g.busy, 30, "herd talk")

    def extras(self):
        """The things off the main path: the deer stand's shells, the plant's ledger, the clovers behind it."""
        g = self.g
        from breakowt.world import DEER_STAND, PLANT_BACK
        x, z = DEER_STAND
        for _ in range(4):
            if g.flags.get("shells_found"):
                break
            yield from self.headbutt_at((x, 1.2, z - 0.9), dist=1.6)
        yield from self.until(lambda: g.ia.get("st_ammo_tin") is not None, 5, "ammo tin falls")
        yield from self.interact("st_ammo_tin")
        yield from self.until(lambda: g.inv.count("shells") >= 2, 5, "shells")
        self.combo = "2009"
        yield from self.interact("plant_keypad")
        yield from self.until(lambda: g.world.doors["plant_back"].is_open, 5, "plant door")
        yield from self.wait(0.6)
        self.place(77.6, PLANT_BACK, 270)
        yield from self.walk_to(73.5, PLANT_BACK)
        yield from self.interact("ledger")
        yield from self.until(lambda: g.flags.get("ledger_read") and not g.busy, 30, "ledger")
        for i in range(5):
            if g.ia.get(f"st_clover{i}") is not None:
                yield from self.interact(f"st_clover{i}")
        print(f"    extras: shells {g.inv.count('shells')}, ledger read, clovers {g.clovers()}", flush=True)

    def p_d6_night(self):
        g = self.g
        yield from self.wait_ready()
        self.place(56, 26.5, 0)
        yield from self.open_door("front_door")
        yield from self.wait(0.8)
        self.place(56, 32, 0)
        # sneak the whole way: walking near his bed wakes him, and a drawer opened standing up creaks
        g.player.crouch_toggle = True
        yield from self.walk_path([(51.5, 35), (51.2, 38.9), (48.9, 39.2), (48.9, 41), (56.9, 41), (56.4, 43.9)])
        yield from self.interact("nightstand")
        yield from self.until(lambda: g.inv.has("cabinet_key"), 5, "cabinet key")
        yield from self.walk_path([(56.9, 41), (47.9, 41), (47.9, 44.5)])
        yield from self.interact("gun_cabinet")
        g.player.crouch_toggle = False

    def p_d6_stars(self):
        yield from self.wait_ready()
        # well inside the 7.5 m around the oak (the herd jostles a cow standing near the edge back out of it)
        self.place(-50.5, -41.5, 0)
        yield from self.wait(2)

    def p_d7_fuse(self):
        g = self.g
        yield from self.wait_ready()
        self.place(-7.5, -22, 270)
        # the cable to the ceiling marks the shed-light fuse; every label is wrong, so the fence is the other
        # one not labelled FENCE. One pull, the right one.
        labels = ("fence", "house", "shed")
        shed = g.flags["fuse_map"].index("shed")
        fence = next(i for i in range(3) if i != shed and labels[i] != "fence")
        print(f"    the cable says fuse {shed} is the light; pulling fuse {fence}", flush=True)
        yield from self.interact(f"fuse_{fence}")
        yield from self.wait(0.5)
        if not g.is_done("fuse"):
            raise Stuck("pulled the deduced fuse and the fence is still on")

    def p_d7_tractor(self):
        g = self.g
        from ursina import held_keys
        tries = 0
        while g.story.cur == "d7_tractor":
            tries += 1
            if tries > 3:
                raise Stuck("dragged off the tractor three times")
            if tries > 1:
                print(f"    Chuck got us off the tractor ({g.flags.get('_grab')}); again", flush=True)
            yield from self.wait_ready()
            # up the ramp to the hayloft, break the rickety railing over the tractor, and drop in
            self.place(31.4, -7.0, 0)
            yield from self.walk_path([(31.4, 5.5), (22, 5.4)])
            if not g.flags.get("rail_broken"):
                yield from self.headbutt_at((22, 3.8, 4.1), dist=1.3)
                yield from self.wait(0.3)
                yield from self.headbutt_at((22, 3.8, 4.1), dist=1.3)
                yield from self.until(lambda: g.flags.get("rail_broken"), 3, "railing breaks")
            yield from self.wait_ready()
            self.place(22, 4.8, 180, y=3.2)
            yield from self.walk_to(22, 2.0, timeout=8)
            yield from self.until(lambda: g.vehicle is not None, 6, "landed in the tractor")
            g.flags.pop("_grab", None)
            yield from self.drive_out()
            for k in ("w", "a", "s", "d"):
                held_keys[k] = 0
            if not g.flags.get("_grab"):
                return      # through the gate: the rest of the step is a cutscene

    def drive_out(self):
        g = self.g
        from ursina import held_keys
        route = [(22, -14), (12, -16), (1.5, -15), (1.5, 20), (1.2, 60), (0.5, 80), (0, 92)]
        tr = g.vehicle
        for x, z in route:
            t = 0
            while g.vehicle is not None and math.hypot(tr.x - x, tr.z - z) > 2.5:
                want = math.degrees(math.atan2(x - tr.x, z - tr.z))
                err = ((want - tr.yaw + 180) % 360) - 180
                # ease off in tight turns so we don't orbit the waypoint
                slow = abs(err) > 35 and tr.speed > 3.5
                held_keys["w"] = 0 if slow else 1
                held_keys["s"] = 1 if slow and tr.speed > 5 else 0
                held_keys["a"] = 1 if err < -4 else 0
                held_keys["d"] = 1 if err > 4 else 0
                yield
                t += DT
                if t > 40:
                    raise Stuck(f"tractor stuck at ({tr.x:.1f},{tr.z:.1f}) heading to ({x},{z})")
            if g.vehicle is None:
                break
        for k in ("w", "a", "s", "d"):
            held_keys[k] = 0

    def p_d7_boss(self):
        g = self.g
        p = g.player
        yield from self.until(lambda: g.story.enemy is not None, 60, "boss")
        boss = g.story.enemy
        f = g.farmer
        t = 0
        last = None
        fired = False
        while not boss.finished:
            if self.args.verbose and (boss.state, boss.hp) != last:
                last = (boss.state, boss.hp)
                print(f"    boss {boss.state} hp={boss.hp} phase={boss.phase} player_hp={p.health} "
                      f"d={math.hypot(f.x - p.x, f.z - p.z):.1f}", flush=True)
            if not g.controls_enabled():
                yield
                continue
            d = math.hypot(f.x - p.x, f.z - p.z)
            self.face((f.x, 1.2, f.z))
            # one shell in the fight (if there are two): the other is for the end
            if not fired and g.inv.count("shells") >= 2 and d < 8 and boss.state in ("approach", "retreat"):
                # one shot from Ol' Bessie: it should land and knock him flat
                fired = True
                hp0 = boss.hp
                g.inv.select_key("shotgun")
                yield
                self.press("q")
                yield
                if abs(boss.hp - (hp0 - boss.MAX_HP / 3)) > 1e-6 or boss.state != "fallen":
                    raise Stuck(f"shotgun didn't land: hp {hp0}->{boss.hp}, state {boss.state}")
                print(f"    shotgun hit: hp {hp0}->{boss.hp}, shells left {g.inv.count('shells')}", flush=True)
                continue
            if boss.vulnerable():
                if d > 1.6:
                    k = min(1.0, 6 * DT / d)
                    p.x += (f.x - p.x) * k
                    p.z += (f.z - p.z) * k
                elif p.headbutt_cd <= 0:
                    self.press("left mouse down")
            elif boss.state in ("windup", "lunge"):
                # step sideways out of the lunge
                ang = math.atan2(p.x - f.x, p.z - f.z) + math.pi / 2
                p.x += math.sin(ang) * 6 * DT
                p.z += math.cos(ang) * 6 * DT
            elif d < 4.0:
                p.x += (p.x - f.x) / max(d, 0.1) * 3 * DT
                p.z += (p.z - f.z) / max(d, 0.1) * 3 * DT
            p.col.x, p.col.z = p.x, p.z
            yield
            t += DT
            if t > 240:
                raise Stuck(f"boss fight too long, hp {boss.hp} state {boss.state}")

    def want_catch(self, key):
        return key not in self.caught_steps and ("all" in self.catch or key in self.catch)

    # ------------------------------------------------------------------
    def run(self, to_day, limit_per_step=400):
        g = self.g
        last_key = None
        step_frames = 0
        while True:
            key = g.story.cur
            if key != last_key:
                if last_key is not None:
                    secs = step_frames / FPS
                    print(f"  done {last_key:<12} {secs:6.1f}s game time", flush=True)
                last_key = key
                step_frames = 0
                self.plan = self.plan_for(key) if key else None
                if key and self.shots:
                    self.shot(f"{key}_start")
            if key and self.want_catch(key) and step_frames > 2 * FPS and g.controls_enabled() \
                    and not g.busy and not g.in_dialogue and g.player_restricted() and g.vehicle is None \
                    and g.farmer.visible and g.farmer.state not in ("disabled", "scripted"):
                self.caught_steps.add(key)
                print(f"    caught during {key}", flush=True)
                g.on_caught(g.farmer)
                yield_frames = 0
                while g.runner.running("caught") or g.cutscene or g.in_dialogue:
                    self.tick()
                    yield_frames += 1
                    if yield_frames > 30 * FPS:
                        raise Stuck(f"caught sequence in {key} never finished")
                if g.player.frozen or not g.controls_enabled():
                    raise Stuck(f"no control after being caught in {key}")
                self.plan = self.plan_for(key)
            elif key and g.runner.running("caught"):
                # caught for real (not on purpose): let it play out, then start the step's plan again
                print(f"    caught (really) during {key}", flush=True)
                n = 0
                while g.runner.running("caught") or g.cutscene or g.in_dialogue:
                    self.tick()
                    n += 1
                    if n > 30 * FPS:
                        raise Stuck(f"caught sequence in {key} never finished")
                self.plan = self.plan_for(key)
            if self.watch is not None:
                self.watch()
            if self.plan is not None:
                try:
                    next(self.plan)
                except StopIteration:
                    self.plan = None
            self.tick()
            step_frames += 1
            if key and step_frames > limit_per_step * FPS:
                raise Stuck(f"step {key} took more than {limit_per_step}s")
            if self.errors:
                raise Stuck(f"script error: {self.errors[-1][0]}")
            if g.state == "title" and g.flags.get("game_finished"):
                print("  reached the title screen after the epilogue", flush=True)
                return "finished"
            if g.day > to_day:
                print(f"  reached day {g.day}", flush=True)
                return "day"


def resume_test(bot, day):
    """Play `day` keeping every checkpoint, then restart the day from each one (what Continue and
    Restart checkpoint do) and play it out again. Each restart must fade in, get the light of the
    moment back and still reach the next day."""
    import json
    g = bot.g
    saves = []
    light = {}
    orig = g.save_checkpoint

    def rec():
        orig()
        d = g.load_save()
        if d and d.get("day") == day:
            saves.append(json.loads(json.dumps(d)))
    g.save_checkpoint = rec

    def note_light():
        # the light a step starts in (read the same way in both runs: once its first frame has run)
        k = g.story.cur
        if k and k not in light:
            light[k] = g.flags.get("_time")
    bot.watch = note_light
    g.story.new_game(day)
    bot.run(day)
    bot.watch = None
    g.save_checkpoint = orig
    seen = set()
    for i, d in enumerate(saves):
        done = tuple(sorted(k for k, v in d["flags"].items() if v and k.startswith(f"d{day}_")))
        if done in seen or not done:
            continue
        seen.add(done)
        g.story.load_from_save(d)
        for _ in range(3 * FPS):
            if g.day == day:
                break
            bot.tick()
        first = {"key": None, "light": None}
        min_fade = [1.0]

        def watch():
            if g.story.cur and first["key"] is None:
                first["key"] = g.story.cur
                first["light"] = g.flags.get("_time")
            if first["key"] is not None:
                min_fade[0] = min(min_fade[0], g.ui.fade_alpha)
        bot.watch = watch
        bot.plan = None
        bot.run(day)
        bot.watch = None
        k = first["key"]
        if k is None:
            continue    # saved after the day's last step; Continue loads the next day's save instead
        print(f"  checkpoint {i:<2} resumed at {k}", flush=True)
        if min_fade[0] > 0.05:
            raise Stuck(f"screen stayed black after resuming at {k}")
        if k in light and light[k] != first["light"]:
            raise Stuck(f"light at {k} is {first['light']} after resume, {light[k]} in a straight run")


def dump(g):
    p = g.player
    f = g.farmer
    print(f"STATE day={g.day} step={g.story.cur} pos=({p.x:.2f},{p.y:.2f},{p.z:.2f}) busy={g.busy} "
          f"dlg={g.in_dialogue} cut={g.cutscene} modal={g.ui.modal} state={g.state}")
    print(f"      chuck state={f.state} pos=({f.x:.1f},{f.z:.1f}) pose={f.pose} visible={f.visible} r_i={f.r_i}")
    print(f"      objectives={g.objective_lines()}")
    print(f"      scripts={[s.name for s in g.runner.scripts]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", type=int, default=1)
    ap.add_argument("--to", type=int, default=7)
    ap.add_argument("--detect", action="store_true")
    ap.add_argument("--shots", action="store_true")
    ap.add_argument("--render", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--caught", default="")
    ap.add_argument("--resume", action="store_true", help="restart each day from every checkpoint")
    args = ap.parse_args()
    t0 = _time.time()
    app, g = harness.boot(size=(960, 540))
    bot = Bot(app, g, args)
    if not args.resume:
        g.story.new_game(args.day)
    if not args.detect:
        orig_setup = g.story.apply_world_flags

        def no_eyes():
            orig_setup()
            g.farmer.detect = False
        g.story.apply_world_flags = no_eyes
        g.farmer.detect = False
    print(f"walkthrough from day {args.day} to {args.to}", flush=True)
    try:
        if args.resume:
            for day in range(args.day, args.to + 1):
                print(f"day {day}", flush=True)
                resume_test(bot, day)
            print(f"OK (resume) in {_time.time() - t0:.0f}s real, {bot.frame / FPS:.0f}s game", flush=True)
            return 0
        res = bot.run(args.to)
        print(f"OK ({res}) in {_time.time() - t0:.0f}s real, {bot.frame / FPS:.0f}s game", flush=True)
        for line in bot.log:
            print(line)
        return 0
    except Stuck as e:
        print(f"FAILED: {e}", flush=True)
        dump(g)
        bot.shot("FAILED")
        return 1
    except Exception:
        traceback.print_exc()
        dump(g)
        return 2


if __name__ == "__main__":
    sys.exit(main())
