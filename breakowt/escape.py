"""Optional preparation gives one tactical opening in the existing final fight.

The plant paperwork, Thursday escort sketch and two puzzle rewards combine into
a main-gate release rig. It never replaces the Sunday fence, tractor or boss.
"""
from __future__ import annotations

import math

CLIPBOARD = (74.05, 0.85, -33.45)
RIG_HANDLE = (-7.5, 1.0, 75.0)
HELPER_START = (-12, 0, 73)
MAINTENANCE = (
    "HAPPY ACRES — MANUAL GATE RELEASE\n\n"
    "Do not use the cattle gate itself as a weight. Fit the removable latch to the release post. Run a "
    "stout rope through the upper guide, leaving the handle clear of the doorway.\n\n"
    "The same fitting is approved for the farm's main gate. Gate-post measurements are required before "
    "installation. An incorrectly fitted latch will release under its own weight.\n\n"
    "One pull releases the holding line. Reset by hand after use. No live animals are to be used in testing.\n\n"
    "Inspection signed: Chuck.\n"
    "The signature is enormous. The box marked TESTED is empty."
)


class FightPreparation:
    def prep_ready(self):
        return bool(self.flags.get("gate_rigged"))

    def setup_fight_prep(self, day):
        self._fight_prep = None
        for key in ("prep_clipboard", "prep_gate_rig"):
            ia = self.g.ia.get(key)
            if ia is not None:
                ia.enabled = day >= 3
        if day < 3:
            return
        self._build_fight_prep()
        g = self.g
        g.on("prep_clipboard", "Read the gate maintenance clipboard", self._read_fight_prep, scope="day")
        g.on("prep_gate_rig", "Inspect the release rig" if self.prep_ready() else "Fit the gate release rig",
             self._fit_gate_rig, scope="day")

    def _build_fight_prep(self):
        from ursina import Entity
        from .engine.assets import tex
        from .engine.meshbuilder import MeshBuilder
        from .engine.shading import FARM_SHADER

        def prop(key, mb):
            return self.prop(key, Entity(model=mb.build(), texture=tex("white"), shader=FARM_SHADER))

        x, y, z = CLIPBOARD
        mb = MeshBuilder().box((x, y, z), (0.32, 0.025, 0.46), color=(0.38, 0.25, 0.15, 1))
        mb.box((x, y + 0.02, z), (0.28, 0.012, 0.40), color=(0.93, 0.90, 0.81, 1))
        mb.box((x, y + 0.035, z - 0.17), (0.13, 0.015, 0.04), color=(0.30, 0.33, 0.32, 1))
        prop("prep_clipboard_prop", mb)
        x, y, z = RIG_HANDLE
        mb = MeshBuilder().box((x, 0.7, z), (0.14, 1.4, 0.14), color=(0.37, 0.28, 0.18, 1))
        mb.box((x + 0.08, y, z), (0.07, 0.20, 0.24), color=(0.40, 0.43, 0.40, 1))
        if self.prep_ready():
            mb.box((x, 1.55, z), (0.035, 0.9, 0.035), color=(0.62, 0.46, 0.26, 1))
            mb.box((x + 0.15, y, z), (0.26, 0.055, 0.055), color=(0.65, 0.49, 0.28, 1))
            mb.box((x - 2.0, 0.55, z - 1.0), (4.0, 0.025, 0.025), color=(0.62, 0.46, 0.26, 1),
                   rot=(0, -26.5, 0))
        prop("prep_gate_rig_prop", mb)
        for key, pos, name in (("prep_clipboard", CLIPBOARD, "Gate maintenance clipboard"),
                               ("prep_gate_rig", RIG_HANDLE, "Main-gate release rig")):
            if self.g.ia.get(key) is None:
                self.g.world.add_ia(key, pos, 0.30, name, reach=2.6)

    def _read_fight_prep(self, g):
        yield from g.show_document("MANUAL GATE RELEASE", MAINTENANCE, style="note")
        if not self.flags.get("ledger_read"):
            g.examine("The intake ledger is beside it. Read what they do with the cows before borrowing their "
                      "equipment.")
            return
        if not self.flags.get("gate_rig_clue"):
            self.setf("gate_rig_clue")
            g.side_quest("gate_support", "Prepare a gate release to help in the final fight", "active")
            yield from g.talk([
                ("you", "Moo. (A rope, a removable latch, and the gate-post measurements. We could hold someone "
                        "clear of the tractor, then release them when Chuck least expects it.)"),
                ("you", "Moo. (He filled in the signature and skipped the test. We can improve on one of those.)"),
            ])
            self.save_progress()
        elif self.prep_ready():
            g.examine("The gate rig is fitted. One pull, one opening. The rest of the fight is still yours.")

    def _fit_gate_rig(self, g):
        if self.prep_ready():
            g.examine("The release rig is fitted. Moothagoras can brace here clear of the tractor, then charge "
                      "when you pull the handle. One try. We'll still have to fight Chuck.")
            return
        if not self.flags.get("gate_rig_clue"):
            g.examine("An empty release bracket. The plant's maintenance clipboard explains the fitting.")
            return
        if not self.flags.get("escort_route_sketch"):
            g.examine("The post measurements are missing from the clipboard. Somebody who has walked the "
                      "truck route could check the gate clearance for you.")
            return
        if not (g.inv.has("escape_rope") and g.inv.has("latch_kit")):
            g.examine("The sketch calls for a stout rope and a removable latch. The weigh-gate rope and the "
                      "cabinet's latch kit would fit. Bring both before fixing anything in place.")
            return
        g.inv.remove("escape_rope")
        g.inv.remove("latch_kit")
        self.setf("gate_rigged")
        self._build_fight_prep()
        g.audio.play("metal_clang", vol=0.5, pos=RIG_HANDLE, rng=12)
        g.examine("Thursday's sketch gives you the clearance. Rope through the guide, latch on the post, "
                  "handle within reach. A safe starting line for one very determined cow.")
        g.side_quest("gate_support", "Prepare a gate release to help in the final fight", "done")
        self.save_progress()

    def begin_fight_prep(self, boss):
        """Arm one optional charge per fight attempt, without changing boss HP."""
        self.end_fight_prep()
        if not self.prep_ready():
            return
        g = self.g
        c = g.cows["cowpernicus"]
        self._fight_prep = {"boss": boss, "used": False, "cow": c,
                            "home": (c.x, c.y, c.z, c.yaw), "visible": c.visible}
        c.set_visible(True)
        c.teleport(HELPER_START, 90)
        c.path = []
        g.ui.bark_line("Moo. (One measured intervention.)", "Moothagoras")
        g.on("prep_gate_rig", "Release Moothagoras' charge", self._release_prep_charge,
             cond=lambda gg: self._fight_prep is not None and not self._fight_prep["used"] and
             not self._fight_prep["boss"].finished)

    def _release_prep_charge(self, g):
        state = self._fight_prep
        if state is None or state["used"] or state["boss"].finished:
            return
        if math.hypot(g.farmer.x - RIG_HANDLE[0], g.farmer.z - RIG_HANDLE[2]) > 7:
            g.examine("Chuck is too far from the release post. Bring him closer before sending Moothagoras out.")
            return
        state["used"] = True
        g.audio.play("metal_clang", vol=0.8, pos=RIG_HANDLE, rng=30)
        g.runner.start(self._prep_charge(state), name="prep_charge", tag="day")

    def _prep_charge(self, state):
        from ursina import time
        g = self.g
        boss, c, f = state["boss"], state["cow"], g.farmer
        sx, sz = c.x, c.z
        tx, tz = f.x - 0.7, f.z + 0.3
        c.path = []
        g.ui.bark_line("Moo. (F equals ma. I am quite a lot of m.)", "Moothagoras")
        t = 0.0
        while t < 1.25 and not boss.finished:
            t += time.dt
            k = min(1, t / 1.25)
            c.x, c.z = sx + (tx - sx) * k, sz + (tz - sz) * k
            c.yaw = math.degrees(math.atan2(tx - sx, tz - sz))
            c._apply()
            c.model.animate(time.dt, 6, None)
            yield None
        if boss.finished:
            return
        if math.hypot(c.x - f.x, c.z - f.z) <= 3.0:
            boss.stun(2.4, "gate_charge", "ow")
            g.audio.play("punch", vol=0.8)
            f.say("OW! Who taught THAT one PHYSICS?!", force=True)
            g.stats["gate_assists"] = g.stats.get("gate_assists", 0) + 1
            g.ui.popup_sub("Chuck is off balance. Your opening!", 3)
        else:
            g.ui.bark_line("Moo. (He moved. That was not in the first calculation.)", "Moothagoras")
        c.goto((-11, 0, 82), 3.0)

    def end_fight_prep(self):
        ia = self.g.ia.get("prep_gate_rig")
        if ia is not None:
            ia.handlers = [h for h in ia.handlers if h.scope != "step"]
        state = getattr(self, "_fight_prep", None)
        if state is not None:
            self.g.runner.stop("prep_charge")
            c = state["cow"]
            c.teleport(state["home"][:3], state["home"][3])
            c.set_visible(state["visible"])
        self._fight_prep = None
