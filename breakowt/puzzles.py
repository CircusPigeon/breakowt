"""Physical farm puzzles, mixed into Story without coupling them to day generators."""
from __future__ import annotations

import math

from ursina import Entity

from .engine.assets import tex
from .engine.meshbuilder import MeshBuilder
from .engine.puzzle_rules import (BOARD_LENGTHS, SLOTS, SUPPORTS, board_supported, bridge_status, cabinet_access,
                                  clean_layout, legacy_layout, plate_load)
from .engine.shading import FARM_SHADER
from .interact import Handler, Interactable
from .world import Door, Pushable


class FarmPuzzles:
    """Lifecycle hooks used by Story and the Saturday preparation step."""

    def setup_farm_puzzles(self, day):
        self.clear_farm_puzzles()
        self.farm_puzzles = _FarmPuzzles(self, day)

    def clear_farm_puzzles(self):
        puzzles = getattr(self, "farm_puzzles", None)
        if puzzles is not None:
            puzzles.remove()
        self.farm_puzzles = None

    def update_farm_puzzles(self, dt):
        puzzles = getattr(self, "farm_puzzles", None)
        if puzzles is not None:
            puzzles.update(dt)

    def setup_bridge(self, on_change=None):
        if getattr(self, "farm_puzzles", None) is None:
            self.farm_puzzles = _FarmPuzzles(self, self.g.day)
        self.farm_puzzles.setup_bridge(on_change)

    def bridge_finished(self):
        return bridge_status(self.flags.get("bridge_layout", legacy_layout(self.flags.get("planks_laid", 0))))[0]

    def bridge_place(self, board, slot, rotate=False):
        return self.farm_puzzles.place_board(board, slot, bool(rotate))

    def bridge_take(self, board):
        return self.farm_puzzles.take_board(board)

    def bridge_hint(self, stance="practical"):
        message = bridge_status(self.flags.get("bridge_layout", {}))[1]
        if stance == "evidence":
            return "Look beneath the ends: yellow marks identify the three solid supports. " + message
        if stance == "challenge":
            return "Three boards are a count, not a proof. A hoof needs a continuous supported lane. " + message
        return message

    def bridge_supply(self):
        g = self.g
        if self.done("puzzle_plank_supplied") or g.inv.count("plank") + len(self.flags.get("bridge_layout", {})) >= 3:
            return False
        self.setf("puzzle_plank_supplied")
        g.inv.add("plank", silent=True)
        g.ui.toast("Epicowrus contributes a recovered board. You still have to build the crossing.", "plank")
        self.save_progress()
        return True

    def puzzle_help(self, kind):
        puzzles = getattr(self, "farm_puzzles", None)
        if kind == "bridge":
            self.g.examine(self.bridge_hint(self.flags.get("_stance_cowpernicus", "practical")))
            return True
        if puzzles is None or not puzzles.optional:
            return False
        if kind == "weight":
            cow = self.g.cows["cowpernicus"]
            if puzzles.helper is cow:
                self.g.examine("Moothagoras is already on his way to the plate.")
                return True
            puzzles.helper_home = (cow.x, cow.y, cow.z, cow.yaw)
            cow.goto((3, 0, 18), 2.8)
            cow.graze = False
            puzzles.helper = cow
            self.g.examine("Moothagoras goes to stand on the plate. 'A demonstration with a very patient constant.'")
            return True
        if kind == "distraction":
            if self.g.env.time < puzzles.distraction_ready:
                self.g.examine("Moogenes is catching his breath. A philosophical objection still requires lungs.")
                return False
            puzzles.distraction_ready=self.g.env.time+40
            cow = self.g.cows["sirloin"]
            cow.bubble("MOOOOO!", 3)
            self.g.noise((cow.x, cow.y + 1, cow.z), 90, "puzzle_cow")
            return True
        return False


class _FarmPuzzles:
    def __init__(self, story, day):
        self.s, self.g = story, story.g
        self.optional = 3 <= day <= 6
        self.alive = True
        self.props, self.colliders, self.pushables, self.interactions = [], [], [], []
        self.doors = []
        self.helper = self.helper_home = None
        self.saved_routine = self.cabinet_script = None
        self.cabinet_open = False
        self.distraction_ready = 0
        self.bridge_callback = None
        self.bridge_active = False
        if self.optional:
            self.weight_store()
            self.tool_store()
        if day >= 6 or story.flags.get("bridge_layout") or story.flags.get("planks_laid"):
            self.setup_bridge()

    def mesh(self, key, boxes, texture="wood"):
        mb = MeshBuilder()
        for pos, size, color in boxes:
            mb.box(pos, size, color=color, uv_density=0.7)
        return self.prop(key, Entity(model=mb.build(), texture=tex(texture), shader=FARM_SHADER))

    def prop(self, key, entity):
        key = "st_puzzle_" + key
        self.s.prop(key, entity)
        if key not in self.props:
            self.props.append(key)
        return entity

    def box(self, x, z, w, d, y0, y1, **kw):
        collider = self.g.phys.add_box_c(x, z, w, d, y0, y1, **kw)
        self.colliders.append(collider)
        return collider

    def ia(self, key, pos, name, prompt, action, radius=0.5, reach=2.6, cond=None):
        ia = self.g.ia.add(Interactable(key, pos, radius, name, None, prompt, reach))
        ia.handlers.append(Handler(prompt, action, cond, "day"))
        self.interactions.append(key)
        return ia

    def pushable(self, key, pos, size, name, weight=0):
        pb = Pushable(self.g.world, key, pos, size=size, name=name, step=0.5)
        self.g.world.pushables[key] = pb
        self.s.prop(key, pb.ent)
        self.props.append(key)
        self.interactions.append(key)
        self.pushables.append((pb, weight))
        return pb

    def door(self, key, hinge, length, **kw):
        door = Door(self.g.world, key, hinge, length, **kw)
        self.g.world.doors[key] = door
        self.prop(key, door.pivot)
        self.colliders.append(door.col)
        self.doors.append(door)
        return door

    def weight_store(self):
        brown = (0.78, 0.66, 0.43, 1)
        yellow = (1, 0.8, 0.14, 1)
        self.mesh("weight_store", [((1, 1.2, 22), (.2, 2.4, 4), brown),
                                  ((5, 1.2, 22), (.2, 2.4, 4), brown),
                                  ((3, 1.2, 24), (4.2, 2.4, .2), brown),
                                  ((1.5, 1.2, 20), (1, 2.4, .2), brown),
                                  ((4.5, 1.2, 20), (1, 2.4, .2), brown),
                                  ((3, 2.5, 22), (4.2, .2, 4.2), brown),
                                  ((3, .045, 18), (2.4, .09, 2), yellow)])
        for x, z, w, d, y0, y1 in ((1,22,.2,4,0,2.4),(5,22,.2,4,0,2.4),(3,24,4.2,.2,0,2.4),
                                  (1.5,20,1,.2,0,2.4),(4.5,20,1,.2,0,2.4),(3,22,4.2,4.2,2.4,2.6)):
            self.box(x,z,w,d,y0,y1)
        self.weight_gate = self.door("st_weight_gate", (2,20), 2, height=2.4, texture="white",color=(.45,.49,.5,1))
        self.mesh("weight_gauge", [((5.4,1.0,18),(1,.7,.15),(0.12,.14,.16,1)),
                                  ((5.85,1.0,17.9),(.12,.55,.03),yellow)], "white")
        self.gauge = self.mesh("weight_needle", [((0,0,0),(.65,.05,.035),(1,.3,.14,1))], "white")
        self.gauge.position = (5.4,1,17.8)
        crate=self.pushable("st_weight_crate", (3,0,14.5),(1,.8,1),"Heavy feed crate (three marks)",3)
        marks=self.mesh("crate_marks",[((x,.42,-.515),(.055,.32,.02),yellow) for x in (-.2,0,.2)],"white")
        marks.parent=crate.ent
        for suffix,z in (("a",17.5),("b",18.5)):
            bag=self.pushable("st_weight_bag_"+suffix,(.0,0,z),(.65,.55,.65),"Feed sack (one and a half marks)",1.5)
            marks=self.mesh("bag_marks_"+suffix,[((-.1,.3,-.34),(.055,.3,.02),yellow),
                                                ((.1,.22,-.34),(.055,.15,.02),yellow)],"white")
            marks.parent=bag.ent
        self.ia("st_weight_plate",(3,.15,18),"Counterweight plate","Read the scale",lambda g:g.examine(
            "Three marks lift the gate. Your weight does it, until you walk off. The heavy crate has three marks; "
            "each sack has one and a half. E or a headbutt nudges them. A friend could stand here, too."),radius=1)
        self.ia("st_weight_reset",(5.5,.6,15.5),"Weight reset handle","Reset the weights",lambda g:self.reset_weights())
        self.ia("st_weight_help",(5.5,.8,19),"Cow-sized assistance bell","Ask Moothagoras to hold the plate",
                lambda g:self.s.puzzle_help("weight"))
        if not self.s.done("escape_rope_taken"):
            # Coiled rope is authored geometry, so this works with the existing texture pack.
            boxes = [((3 + math.cos(i*math.pi/8)*.35,.6,22.8 + math.sin(i*math.pi/8)*.35),(.2,.1,.2),brown)
                     for i in range(16)]
            self.rope = self.mesh("rope",boxes)
        else:
            self.rope = None
        rope_ia=self.ia("st_escape_rope",(3,.7,22.8),"Hauling rope","Take the hauling rope",lambda g:self.take_rope(),
                        cond=lambda g:not self.s.done("escape_rope_taken"))
        rope_ia.enabled=not self.s.done("escape_rope_taken")

    def reset_weights(self):
        for pb, weight in self.pushables:
            if weight:
                pb.reset()
        self.g.examine("The weights slide back onto their marked starting squares.")

    def take_rope(self):
        # Also enforce physical access for scripted/test interactions.
        if self.s.done("escape_rope_taken"):
            return False
        if not self.weight_gate.is_open or self.g.player.z < 20:
            self.g.examine("The gate is still between you and the rope. Hold the plate down with something else.")
            return False
        self.s.setf("escape_rope_taken")
        self.g.inv.add("escape_rope")
        self.s.remove_prop("st_puzzle_rope")
        self.g.ia.get("st_escape_rope").enabled = False
        self.g.side_quest("counterweight", "Recover the hauling rope from the counterweight store", "done")
        self.g.examine("A stout release cord. The plant's maintenance clipboard shows how this rope and a removable "
                       "latch could fit the main gate.")
        self.release_helper()
        self.s.save_progress()
        return True

    def release_helper(self):
        if self.helper is not None:
            self.helper.stop()
            if self.helper_home:
                self.helper.goto(self.helper_home[:3],2.6)
            self.helper = self.helper_home = None

    def tool_store(self):
        metal = (.55,.61,.59,1)
        brown = (.72,.58,.37,1)
        self.mesh("tool_store", [((33,1.3,21.8),(.15,2.6,3.6),metal),
                                ((37,1.3,21.8),(.15,2.6,3.6),metal),
                                ((33.5,1.3,20),(1,2.6,.15),metal),
                                ((36.5,1.3,20),(1,2.6,.15),metal),
                                ((35,2.7,21.8),(4.2,.2,3.8),metal),
                                ((33.65,1.3,23.6),(1.3,2.6,.15),metal),
                                ((36.35,1.3,23.6),(1.3,2.6,.15),metal),
                                ((35,.75,23.6),(1.4,1.5,.15),metal),
                                ((35,2.5,23.6),(1.4,.2,.15),metal),
                                ((31,1.4,17.5),(2,1.2,2),brown),
                                ((31,.6,17.5),(.3,1.2,.3),metal),
                                ((31,.82,16.4),(1.2,.4,.2),metal)],"white")
        for x,z,w,d,y0,y1 in ((33,21.8,.15,3.6,0,2.6),(37,21.8,.15,3.6,0,2.6),
                             (33.5,20,1,.15,0,2.6),(36.5,20,1,.15,0,2.6),
                             (35,21.8,4.2,3.8,2.6,2.8),(33.65,23.6,1.3,.15,0,2.6),
                             (36.35,23.6,1.3,.15,0,2.6),(35,23.6,1.4,.15,0,1.5),
                             (35,23.6,1.4,.15,2.4,2.6),(31,17.5,2,2,0,2)):
            self.box(x,z,w,d,y0,y1)
        self.cabinet_gate = self.door("st_tool_door",(34,20),2,height=2.6,texture="white",color=(.45,.49,.5,1))
        self.grain_pin = self.mesh("grain_pin", [((31,.85,16.23),(.13,.13,.45),(1,.75,.12,1))],"white")
        if self.s.done("hopper_jammed"):
            self.grain_pin.color=(1,.25,.1,1)
        self.ia("st_grain_hopper",(31,1,16.3),"Grain hopper","Inspect or jam the hopper",lambda g:self.hopper(),radius=.7)
        self.ia("st_tool_cabinet",(35,1,19.9),"Maintenance cabinet","Inspect the locked maintenance cabinet",
                lambda g:g.examine("Locked. Chuck's wrench lives here. The hopper instructions say: 'If feed jams, "
                                   "FETCH WRENCH.' The back wall also has a service hatch, above nose height."),radius=.7)
        latch_ia=self.ia("st_latch_kit",(35,.7,21.4),"Door latch kit","Take the door latch kit",lambda g:self.take_latch(),
                         cond=lambda g:not self.s.done("latch_kit_taken"))
        latch_ia.enabled=not self.s.done("latch_kit_taken")
        self.ia("st_service_hatch",(35,2,23.7),"High service hatch","Reach through the service hatch",
                lambda g:self.take_latch(hatch=True),radius=.55)
        self.pushable("st_service_crate",(35,0,26),(1,.95,1),"Service crate")
        self.ia("st_service_reset",(37.8,.6,26),"Crate reset handle","Reset the service crate",
                lambda g:self.g.world.pushables["st_service_crate"].reset())
        if not self.s.done("latch_kit_taken"):
            self.mesh("latch_kit", [((35,.65,21.4),(.65,.14,.3),metal),((35.15,.85,21.4),(.1,.4,.1),metal)],"white")

    def hopper(self):
        f = self.g.farmer
        if self.s.done("latch_kit_taken"):
            self.g.examine("You already have the latch kit. The hopper has suffered enough bureaucracy.")
            return False
        if self.cabinet_script:
            self.g.examine("The feed is jammed. Chuck is fetching the wrench. Watch him unlock the cabinet, then "
                           "place the radio away from it or get a friend to make a noise.")
            return False
        if f.state != "routine" or not f.visible or f.sleeping:
            self.g.examine("Chuck is busy. Jam the feed while he's doing his rounds, so he'll fetch the wrench.")
            return False
        self.saved_routine = (list(f.routine),f.r_i,f.tool)
        self.s.setf("hopper_jammed")
        self.g.side_quest("latch", "Get the maintenance latch kit: jam the hopper, watch Chuck unlock it, distract him", "active")
        self.grain_pin.color = (1,.25,.1,1)
        self.cabinet_script = [("say","Feed's jammed. Need my wrench. AGAIN."),
                               ("go",(35,0,19),2.4),("face",(35,22)),("wait",1,"look"),
                               ("call",self.open_cabinet),("go",(35,0,21.3),1.7),("tool","wrench"),("wait",4,"look"),
                               ("go",(31,0,15.3),2.1),("wait",12,"look",["Who's been shoving things in my HOPPER?!"]),
                               ("call",self.finish_hopper)]
        f.set_routine(self.cabinet_script)
        self.g.noise((31,1,16.3),5,"hopper")
        self.g.examine("You wedge the feed flap. Chuck reaches for a wrench he isn't carrying. Now watch the cabinet.")
        self.s.save_progress()
        return True

    def open_cabinet(self):
        if self.alive:
            self.cabinet_open = True
            self.cabinet_gate.set_open(True)
            self.g.audio.play("door_creak",vol=.6,pos=(35,1,20),rng=30)
            self.g.farmer.say("Wrench. Just where I left it. For once.")

    def finish_hopper(self):
        if not self.alive:
            return
        self.cabinet_gate.set_open(False)
        self.cabinet_open = False
        self.s.flags.pop("hopper_jammed",None)
        self.grain_pin.color = (1,1,1,1)
        saved = self.saved_routine
        self.saved_routine = self.cabinet_script = None
        if saved:
            self.g.farmer.set_tool(saved[2])
            # Farmer advances once after a routine's call callback returns.
            self.g.farmer.set_routine(saved[0],(saved[1]-1)%max(1,len(saved[0])))

    def take_latch(self, hatch=False):
        if self.s.done("latch_kit_taken"):
            self.g.examine("An empty shelf. You have the latch kit.")
            return False
        p,f = self.g.player,self.g.farmer
        elevated = hatch and p.y >= .65 and math.hypot(p.x-35,p.z-23.7) < 2.5
        distance = math.hypot(f.x-35,f.z-21.4)
        if not cabinet_access(self.cabinet_open,distance,elevated):
            self.g.examine("The hatch is too high from the ground. Nudge the service crate underneath, then hop "
                           "onto it." if hatch else "Chuck needs to unlock the cabinet and move away first. Try the hopper, then a radio or another noise.")
            return False
        if not elevated and (not 33.1 < p.x < 36.9 or not 20 < p.z < 23.4):
            self.g.examine("The kit is on the shelf inside. Walk through the open cabinet door.")
            return False
        self.s.setf("latch_kit_taken")
        self.g.inv.add("latch_kit")
        self.s.remove_prop("st_puzzle_latch_kit")
        self.g.ia.get("st_latch_kit").enabled = False
        self.g.side_quest("latch", "Recover the maintenance latch kit", "done")
        self.g.examine("A reversible door latch. Chuck bought a device for locking himself in, and has not considered the possibilities.")
        self.s.save_progress()
        return True

    def setup_bridge(self,on_change=None):
        if on_change is not None:
            self.bridge_callback = on_change
        if "bridge_layout" not in self.s.flags:
            self.s.flags["bridge_layout"] = legacy_layout(self.s.flags.get("planks_laid",0))
        self.s.flags["bridge_layout"] = clean_layout(self.s.flags["bridge_layout"])
        for i in range(3):
            self.s.remove_prop(f"plank{i}")
        if not self.bridge_active:
            self.bridge_active = True
            yellow = (1,.8,.1,1)
            self.mesh("grid_supports",[((0,.07,z),(2.4,.06,.12),yellow) for z in SUPPORTS],"white")
            for slot,(x,z) in SLOTS.items():
                self.mesh("peg_"+slot,[((x,.13,z),(.15,.25,.15),yellow)],"white")
                self.ia("st_bridge_"+slot,(x,.2,z),slot.replace("_"," ").title()+" support peg",
                        lambda g,slot=slot:self.peg_prompt(slot),lambda g,slot=slot:self.use_peg(slot),radius=.28,reach=4.6)
            self.ia("st_bridge_reset",(2.8,.55,79.6),"Bridge reset stake","Recover all boards",lambda g:self.reset_bridge())
            self.g.on("cattle_grid","Inspect the crossing",lambda g:g.examine(self.s.bridge_hint()),scope="day")
        self.render_bridge()

    def peg_prompt(self,slot):
        layout=self.s.flags["bridge_layout"]
        board=next((board for board,p in layout.items() if p["slot"]==slot),None)
        if board:
            return "Turn or lift the "+("long board" if board=="long" else "short board")
        next_board=self.next_board()
        return "Lay the "+("long board" if next_board=="long" else "short board")+" at "+slot.replace("_"," ") if next_board else "Inspect this support peg"

    def next_board(self):
        if not self.g.inv.has("plank"):
            return None
        return next((board for board in BOARD_LENGTHS if board not in self.s.flags["bridge_layout"]),None)

    def use_peg(self,slot):
        layout=self.s.flags["bridge_layout"]
        board=next((board for board,p in layout.items() if p["slot"]==slot),None)
        if board:
            yield from self.board_options(board)
        else:
            board=self.next_board()
            if board:
                self.place_board(board,slot)
            else:
                self.g.examine("Yellow marks are solid supports. Recover a board from the woodpile or shed, then aim at a peg. "
                               "One long board spans the pit; two short boards join at the middle support on the other side.")

    def board_options(self,board):
        choice=yield from self.g.say("you","The board can move. Geometry does not resent revisions.",
                                    ["Turn it a quarter turn","Lift it to move elsewhere","Leave it"])
        self.g.end_talk()
        if choice==0:
            placement=self.s.flags["bridge_layout"][board]
            self.place_board(board,placement["slot"],not placement["turned"])
        elif choice==1:
            self.take_board(board)

    def place_board(self,board,slot,turned=False):
        layout=self.s.flags["bridge_layout"]
        if board not in BOARD_LENGTHS or slot not in SLOTS:
            return False
        if any(other!=board and p["slot"]==slot for other,p in layout.items()):
            self.g.examine("Another board is resting on that peg. Lift it before moving this one there.")
            return False
        if board not in layout:
            if not self.g.inv.has("plank") or board!=self.next_board():
                return False
            self.g.inv.remove("plank")
        layout[board]={"slot":slot,"turned":turned}
        self.changed_bridge()
        self.g.noise((0,.1,82.5),8,"plank")
        self.g.audio.play("thump",vol=.65,pos=(0,.3,82.5),rng=30)
        self.g.examine(bridge_status(layout)[1])
        return True

    def take_board(self,board):
        if board not in self.s.flags["bridge_layout"]:
            return False
        self.s.flags["bridge_layout"].pop(board)
        self.g.inv.add("plank",silent=True)
        self.g.inv.select_key("plank")
        self.changed_bridge()
        return True

    def reset_bridge(self):
        n=len(self.s.flags["bridge_layout"])
        if n:
            self.g.inv.add("plank",n,silent=True)
        self.s.flags["bridge_layout"]={}
        self.changed_bridge()
        self.g.examine("All three boards can be recovered and tried again. No wood was harmed by the wrong answer.")

    def changed_bridge(self):
        self.s.flags["planks_laid"]=len(self.s.flags["bridge_layout"])
        self.render_bridge()
        if self.bridge_callback:
            self.bridge_callback()
        self.s.save_progress()

    def render_bridge(self):
        layout=self.s.flags["bridge_layout"]
        safe,_=bridge_status(layout)
        self.g.world.colliders["cattle_grid"].enabled=not safe
        self.s.flags["bridge_safe"]=safe
        self.s.flags["planks_laid"]=len(layout)
        for board in BOARD_LENGTHS:
            self.s.remove_prop("st_puzzle_board_"+board)
            if board not in layout:
                continue
            p=layout[board]
            x,z=SLOTS[p["slot"]]
            length=BOARD_LENGTHS[board]
            supported=board_supported(board,p)
            color=(.78,.64,.42,1) if supported else (.8,.42,.25,1)
            size=(length,.12,.9) if p["turned"] else (.9,.12,length)
            ent=self.mesh("board_"+board,[((0,0,0),size,color)])
            ent.position=(x,.14,z)
            if not supported:
                ent.rotation_x=3 if not p["turned"] else 0
                ent.rotation_z=3 if p["turned"] else 0

    def update(self,dt):
        if not self.alive:
            return
        if self.optional:
            p=self.g.player
            weights=[(p.x,p.y,p.z,3)]
            weights.extend((pb.x,pb.y,pb.z,weight) for pb,weight in self.pushables if weight)
            if self.helper and self.helper.visible:
                weights.append((self.helper.x,self.helper.y,self.helper.z,3))
            load=plate_load(weights)
            opened=load>=3 or (1.15<p.x<4.85 and 20<p.z<23.9)
            # Release handles inside keep the door from trapping a cow when the helper departs.
            self.weight_gate.set_open(opened)
            self.gauge.rotation_z=60-min(4.5,load)*27
            if self.cabinet_script and self.g.farmer.routine!=self.cabinet_script:
                self.saved_routine=self.cabinet_script=None
                self.cabinet_open=False
                self.cabinet_gate.set_open(False)

    def remove(self):
        self.alive=False
        self.release_helper()
        if self.saved_routine and self.g.farmer.routine==self.cabinet_script:
            self.g.farmer.set_routine(self.saved_routine[0],self.saved_routine[1])
            self.g.farmer.set_tool(self.saved_routine[2])
        for pb,weight in self.pushables:
            self.g.world.pushables.pop(pb.key,None)
            self.g.phys.remove(pb.col)
            if pb.floor in self.g.phys.floors:
                self.g.phys.floors.remove(pb.floor)
        for door in self.doors:
            self.g.world.doors.pop(door.key,None)
        for collider in self.colliders:
            self.g.phys.remove(collider)
        for key in self.interactions:
            self.g.ia.remove(key)
        for key in reversed(self.props):
            self.s.remove_prop(key)
