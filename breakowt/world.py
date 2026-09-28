"""Happy Acres Family Farm: geometry, collisions, zones, doors, props, nav graph."""
from __future__ import annotations

import heapq
import math
import random
from collections import defaultdict

from ursina import Entity, destroy
from panda3d.core import TransparencyAttrib

from .engine.assets import tex
from .engine.meshbuilder import MeshBuilder
from .engine.shading import FARM_SHADER, no_shadow
from .interact import Interactable
from . import models

# ---------------------------------------------------------------------------
# layout constants (meters; x east, z north)
# ---------------------------------------------------------------------------
PASTURE = (-78, -18, -75, 5)
COWSHED = (-66, -38, -12, 3)
SHED = (-12, -4, -26, -18)
BARN = (10, 34, -10, 14)
LOFT_Y = 3.2
COOP_HUT = (38, 44, -32, -27)
COOP_RUN = (34, 48, -42, -24)
SILO = (42, 8)
HOUSE = (44, 68, 30, 48)
HOUSE_Y = 0.3
KX = 57.6          # x of the wall between the living room and the kitchen
PROC = (56, 76, -50, -32)
GATE_Z = 86
FARM = (-80, 80, -78, 86)
POND = (-45, -60, 9, 7)
OAK = (-50, -35)
GATE_PASTURE = (-18, -38, -32)      # x, z0, z1
MOOHOLE = (-18, -67, -65.2)         # x, z0, z1

C_WHITE = (1, 1, 1, 1)


def terrain_h(x, z):
    dx = max(0.0, abs(x) - 84)
    dz = max(0.0, z - 92, -82 - z)
    d = math.hypot(dx, dz)
    if z > 84:
        k = max(0.0, min(1.0, (abs(x) - 6) / 45))
        d *= k * k * (3 - 2 * k)
    n = 0.55 + 0.25 * math.sin(x * 0.031 + 1.7) * math.cos(z * 0.027) + 0.2 * math.sin((x + z) * 0.05)
    return (1 - math.exp(-d / 45)) * (8 + 26 * n) + (1 - math.exp(-d / 12)) * 1.5 * math.sin(x * 0.2) * math.sin(z * 0.17)


def in_pond(x, z, pad=0.0):
    cx, cz, rx, rz = POND
    return ((x - cx) / (rx + pad)) ** 2 + ((z - cz) / (rz + pad)) ** 2 <= 1.0


DEFAULT_TEXT = {
    "oak": ["The Old Oak. Every calf on the farm has tried to climb it. None of them managed, being cows.",
            "Carved into the bark: 'B.E. + M. 1998'. Big Earl and Moomaw."],
    "trough": ["The trough. Today's water has a leaf in it. And a sock. Whose sock?",
               "You drink. It tastes like trough."],
    "saltlick": ["A salt lick. The closest thing this farm has to a nightclub."],
    "scarecrow": ["'Cardboard Chuck.' A life-size cutout of the farmer, placed here so you always feel watched.",
                  "The new calves salute it. You don't have the heart to tell them."],
    "hay_bed": ["Somebody else's bed. It smells like somebody else."],
    "cowshed_sign": ["COWSHED. Chuck named it himself. He was very proud."],
    "stall_sign": ["Stall 47. Chuck painted the number himself and got the 4 backwards the first time."],
    "shed_door": ["The tool shed door. Padlocked, and the padlock is newer than the door."],
    "generator": ["The generator. The fence runs off this. It hums a low note all day and all night.",
                  "A label: 'MAIN FUSE: PULL TO KILL FENCE (DON'T)'. Chuck writes very honest labels."],
    "workbench": ["Chuck's workbench. Every tool is labeled 'MINE'."],
    "poster": ["EMPLOYEE OF THE MONTH: CHUCK. Every month since 1987. The only employee since 1987."],
    "trophy": ["A bowling trophy. The plaque reads: 'CHUCK · 1998 · HIGH SCORE: 117'."],
    "tractor": ["A JOHN STEER tractor. Chuck polishes it on Sundays. He has never once polished a cow."],
    "windmill": ["The windmill creaks in a key you almost recognize. B-flat minor, maybe."],
    "silo": ["The silo. Chuck climbed it in 2004 and the fire brigade had to talk him down."],
    "processing_door": ["The big door is locked. It smells of bleach from here."],
    "processing_sign": ["'Happy Cows Come From Happy Acres!' You have never seen a cow come back from in there."],
    "pickup": ["Chuck's pickup. There's a bumper sticker: 'I BRAKE FOR BARBECUE'."],
    "mailbox": ["The mailbox. A catalog: 'GRILLS & MORE'. Chuck has circled everything."],
    "road_sign": ["'FREEDOM 12'. The next town over is called Freedom. It's twelve miles up the road."],
    "doghouse": ["A tiny doghouse. 'BISCUIT'. There's a food bowl, and it's been empty for a long time."],
    "main_gate": ["The main gate. Chained and padlocked. The road starts on the other side."],
    "cattle_grid": ["A cattle grid. Metal bars over a pit. Hooves slip right through.",
                    "Humanity's second most diabolical invention, after the hamburger."],
    "tv": ["The TV is on: 'BEEF TONIGHT with Cooking Carl'. You change the channel with your nose. It's also beef."],
    "couch": ["The couch has a Chuck-shaped dent in it, and a TV dinner tray wedged down the side."],
    "rug": ["A cowhide rug. Black and white. Large. Bull-sized.", "...You'd rather not think about who this was."],
    "fireplace": ["The fireplace. A stocking hangs from it, labeled 'CHUCK'. Only the one."],
    "fridge": ["The fridge. Milk. Cheese. Butter. Yogurt. You feel extremely conflicted.",
               "There's a steak in the freezer. You close the door very gently."],
    "stove": ["The stove. There's a cast-iron pan on it the size of a manhole cover."],
    "cookbook": ["'101 WAYS TO COOK A COW'. Recipe 47 is dog-eared. Of course it is."],
    "calendar": ["A calendar. Sunday is circled in red and labeled 'BBQ!!!'. Next to it, a doodle of a cow. It's crying. No wait, it's laughing. No, crying."],
    "dentures": ["Chuck's spare dentures, in a glass. They're smiling at you."],
    "desk": ["Chuck's desk. Bills, a cold coffee, and a stapler shaped like a cow. Oh no."],
    "filing": ["FILING CABINET. Drawers labeled 'BILLS', 'TAXES', and 'COWS I HAVE KNOWN'. That last one is locked."],
    "bed_farmer": ["Chuck's bed. The sheets have tractors on them."],
    "wardrobe": ["A wardrobe full of plaid. Seven identical shirts. One is labeled 'SUNDAY BEST'. It's also plaid."],
    "toilet": ["A human toilet. You understand it in principle."],
    "mirror": ["You look in the mirror. There's hay in your ear. There's always hay in your ear."],
    "duck": ["A rubber duck. Squeak. It's the only one on this farm who's ever been happy."],
    "bathtub": ["A bathtub. There's a ring. There's always a ring."],
    "chimes": ["Wind chimes made of seashells. Chuck has never been to the sea."],
    "gnome": ["A garden gnome with a fishing rod. He's been fishing in a flowerbed for 20 years. No bites."],
    "flowerpot": ["A flowerpot. Petunias. Wilting. Chuck waters them with coffee."],
    "doormat": ["WELCOME, it says. You don't believe it."],
    "front_door": ["Chuck's front door. Locked."],
    "back_door": ["The back door. Locked. It has a little doggy flap, much too small for you."],
    "woodpile": ["A pile of lumber. Some good planks in there."],
    "coop": ["The chicken coop. Twelve hens and one rooster, and the rooster is in charge."],
    "hens": ["A hen. She stares at you without blinking."],
    "barn_door": ["The big barn doors. Closed."],
    "lamp": ["A bare light bulb on a wire. There are moths in it."],
    "rockpile": ["A pile of good throwing rocks."],
    "gun_cabinet": ["A gun cabinet. Locked. Inside, Chuck's shotgun, 'Ol' Bessie'. You know three Bessies. None of them would approve."],
    "computer": ["Chuck's computer. ChuckOS 95. The fan sounds like a tractor with asthma."],
    "alarm_clock": ["An alarm clock shaped like a rooster. Cluck Norris would be furious."],
    "nightstand": ["A nightstand. The drawer is shut."],
    "grinder": ["A grinding wheel on a stand. The dirt around it is full of little burn marks."],
    "truck": ["The truck. 'PROCESSING TRANSPORT'. Its engine is still warm."],
    "loft_hay": ["Soft hay, piled high. You could hide a whole cow in here."],
    "fence": ["The electric fence. It ticks once a second. Everybody touches it once."],
}


class Door:
    """A hinged door/gate with a collider that follows its open state."""

    def __init__(self, world, key, hinge, length, along="x", sign=1, height=2.2, thick=0.12, y0=0.0,
                 texture="wood", color=C_WHITE, open_angle=100, locked=False, model_fn=None):
        self.world = world
        self.key = key
        self.hinge = hinge
        self.length = length
        self.along = along
        self.sign = sign
        self.open_angle = open_angle
        self.angle = 0.0
        self.target = 0.0
        self.locked = locked
        self.pivot = Entity(position=(hinge[0], y0, hinge[1]))
        mb = MeshBuilder()
        if model_fn:
            model_fn(mb, length, height)
        else:
            if along == "x":
                mb.box((sign * length / 2, height / 2, 0), (length, height, thick), color=color, uv_density=0.6)
            else:
                mb.box((0, height / 2, sign * length / 2), (thick, height, length), color=color, uv_density=0.6)
        self.ent = Entity(parent=self.pivot, model=mb.build(), texture=tex(texture), shader=FARM_SHADER)
        x, z = hinge
        if along == "x":
            x0, x1 = sorted((x, x + sign * length))
            self.col = world.phys.add_box(x0, x1, z - 0.15, z + 0.15, y0, y0 + height, tag=key)
        else:
            z0, z1 = sorted((z, z + sign * length))
            self.col = world.phys.add_box(x - 0.15, x + 0.15, z0, z1, y0, y0 + height, tag=key)

    @property
    def is_open(self):
        return self.target != 0

    def set_open(self, open_=True, instant=False, direction=1):
        self.target = self.open_angle * direction if open_ else 0.0
        if instant:
            self.angle = self.target
        self.col.enabled = not open_

    def update(self, dt):
        if abs(self.angle - self.target) > 0.01:
            d = self.target - self.angle
            self.angle += max(-dt * 160, min(dt * 160, d))
        self.pivot.rotation_y = self.angle


class WorldItem:
    """A visible pickup on the ground (bobbing optional)."""

    def __init__(self, world, key, model, pos, rot=0.0, scale=1.0, bob=False, spin=False, glow=0.0):
        self.key = key
        self.base = pos
        self.bob = bob
        self.spin = spin
        self.t = random.uniform(0, 6)
        self.ent = models.item_model(model, position=pos, rotation_y=rot, scale=scale)
        if glow:
            for c in self.ent.children:
                c.set_shader_input("u_emissive", glow)

    def update(self, dt):
        self.t += dt
        if self.bob:
            self.ent.y = self.base[1] + math.sin(self.t * 2.5) * 0.06
        if self.spin:
            self.ent.rotation_y += dt * 90

    def remove(self):
        destroy(self.ent)


class World:
    def __init__(self, game):
        self.g = game
        self.phys = game.phys
        self.ia = game.ia
        self.batches: dict[str, MeshBuilder] = defaultdict(MeshBuilder)
        self.entities: list[Entity] = []
        self.doors: dict[str, Door] = {}
        self.items: dict[str, WorldItem] = {}
        self.props: dict[str, Entity] = {}
        self.colliders: dict[str, object] = {}
        self.nav_nodes: list[tuple] = []
        self.nav_edges: dict[int, list[int]] = {}
        self.spawns: dict[str, tuple] = {}
        self.lamps: dict[str, dict] = {}
        self.clover_spots: list[tuple] = []
        self.animated: list = []
        self.t = 0.0
        random.seed(1987)
        self.build()

    # ------------------------------------------------------------------
    # low-level helpers
    # ------------------------------------------------------------------
    def mb(self, texname) -> MeshBuilder:
        return self.batches[texname]

    def box(self, texname, pos, size, color=C_WHITE, rot=(0, 0, 0), collide=False, uv=0.5, sight=True,
            y0=None, tag="", **kw):
        self.mb(texname).box(pos, size, color=color, rot=rot, uv_density=uv, **kw)
        if collide:
            yb = pos[1] - size[1] / 2 if y0 is None else y0
            return self.phys.add_box_c(pos[0], pos[2], size[0], size[2], yb, pos[1] + size[1] / 2, sight=sight, tag=tag)
        return None

    def wall(self, x0, z0, x1, z1, h, t=0.2, texname="wood", y0=0.0, tex_in=None, inside=None, color=C_WHITE,
             uv=0.5, collide=True):
        """Axis-aligned wall segment."""
        if abs(x1 - x0) < 1e-6 and abs(z1 - z0) < 1e-6:
            return
        cy = y0 + h / 2
        if abs(z1 - z0) < 1e-6:  # along x
            xa, xb = sorted((x0, x1))
            L = xb - xa
            cx = (xa + xb) / 2
            if tex_in and inside is not None:
                s = 1 if inside[1] > z0 else -1
                self.mb(texname).box((cx, cy, z0 - s * t / 4), (L, h, t / 2), color=color, uv_density=uv, uv_mode="world")
                self.mb(tex_in).box((cx, cy, z0 + s * t / 4), (L, h, t / 2), color=color, uv_density=uv, uv_mode="world")
            else:
                self.mb(texname).box((cx, cy, z0), (L, h, t), color=color, uv_density=uv, uv_mode="world")
            if collide:
                self.phys.add_box(xa, xb, z0 - t / 2, z0 + t / 2, y0, y0 + h)
        else:
            za, zb = sorted((z0, z1))
            L = zb - za
            cz = (za + zb) / 2
            if tex_in and inside is not None:
                s = 1 if inside[0] > x0 else -1
                self.mb(texname).box((x0 - s * t / 4, cy, cz), (t / 2, h, L), color=color, uv_density=uv, uv_mode="world")
                self.mb(tex_in).box((x0 + s * t / 4, cy, cz), (t / 2, h, L), color=color, uv_density=uv, uv_mode="world")
            else:
                self.mb(texname).box((x0, cy, cz), (t, h, L), color=color, uv_density=uv, uv_mode="world")
            if collide:
                self.phys.add_box(x0 - t / 2, x0 + t / 2, za, zb, y0, y0 + h)

    def wall_gaps(self, x0, z0, x1, z1, h, gaps, t=0.2, texname="wood", y0=0.0, tex_in=None, inside=None,
                  color=C_WHITE, uv=0.5):
        """Wall with openings. gaps: list of (a, b, top) in the running coordinate."""
        along_x = abs(z1 - z0) < 1e-6
        a0, a1 = (min(x0, x1), max(x0, x1)) if along_x else (min(z0, z1), max(z0, z1))
        cur = a0
        for (ga, gb, top) in sorted(gaps):
            if ga > cur:
                if along_x:
                    self.wall(cur, z0, ga, z0, h, t, texname, y0, tex_in, inside, color, uv)
                else:
                    self.wall(x0, cur, x0, ga, h, t, texname, y0, tex_in, inside, color, uv)
            if top < h:
                if along_x:
                    self.wall(ga, z0, gb, z0, h - top, t, texname, y0 + top, tex_in, inside, color, uv)
                else:
                    self.wall(x0, ga, x0, gb, h - top, t, texname, y0 + top, tex_in, inside, color, uv)
            cur = gb
        if cur < a1:
            if along_x:
                self.wall(cur, z0, a1, z0, h, t, texname, y0, tex_in, inside, color, uv)
            else:
                self.wall(x0, cur, x0, a1, h, t, texname, y0, tex_in, inside, color, uv)

    def gable_roof(self, x0, x1, z0, z1, y, rise, texname="shingles", overhang=0.6, thick=0.2, along="x",
                   end_tex=None, color=C_WHITE):
        if along == "x":
            half = (z1 - z0) / 2
            cz = (z0 + z1) / 2
            ang = math.degrees(math.atan2(rise, half))
            L = math.hypot(half, rise) + overhang
            w = x1 - x0 + overhang * 2
            for s in (-1, 1):
                mid_z = cz + s * (half / 2 + overhang / 4)
                mid_y = y + rise / 2 - overhang * math.sin(math.radians(ang)) / 4
                self.mb(texname).box(((x0 + x1) / 2, mid_y + thick / 2, mid_z), (w, thick, L), color=color,
                                     rot=(s * ang, 0, 0), uv_density=0.4)
            et = end_tex or "wood"
            for xx in (x0, x1):
                self.mb(et).poly([(xx, y, z0), (xx, y, z1), (xx, y + rise, cz)], uv_density=0.5)
        else:
            half = (x1 - x0) / 2
            cx = (x0 + x1) / 2
            ang = math.degrees(math.atan2(rise, half))
            L = math.hypot(half, rise) + overhang
            w = z1 - z0 + overhang * 2
            for s in (-1, 1):
                mid_x = cx + s * (half / 2 + overhang / 4)
                mid_y = y + rise / 2 - overhang * math.sin(math.radians(ang)) / 4
                self.mb(texname).box((mid_x, mid_y + thick / 2, (z0 + z1) / 2), (L, thick, w), color=color,
                                     rot=(0, 0, -s * ang), uv_density=0.4)
            et = end_tex or "wood"
            for zz in (z0, z1):
                self.mb(et).poly([(x0, y, zz), (x1, y, zz), (cx, y + rise, zz)], uv_density=0.5)

    def sign(self, texname, pos, size, rot_y=0.0, double=False, emissive=0.0):
        mb = MeshBuilder().quad(pos, size, rot=(0, rot_y, 0), double=double)
        e = Entity(model=mb.build(), texture=tex(texname), shader=FARM_SHADER)
        if emissive:
            e.set_shader_input("u_emissive", emissive)
        self.entities.append(e)
        return e

    def add_ia(self, key, pos, radius=0.7, name="", text_key=None, prompt="Examine", reach=2.6, **kw):
        text = DEFAULT_TEXT.get(text_key or key)
        return self.ia.add(Interactable(key, pos, radius, name, text, prompt, reach, **kw))

    def tree(self, x, z, s=1.0, collide=True, kind="round"):
        h = 3.2 * s
        self.mb("bark").cylinder((x, 0, z), 0.28 * s, h, segs=7, radius_top=0.2 * s, uv_density=1.0)
        if kind == "round":
            for (ox, oy, oz, r) in [(0, h + 1.2 * s, 0, 1.9 * s), (0.9 * s, h + 0.6 * s, 0.3 * s, 1.3 * s),
                                    (-0.8 * s, h + 0.7 * s, -0.4 * s, 1.35 * s), (0.2 * s, h + 2.2 * s, -0.2 * s, 1.2 * s)]:
                self.mb("leaves").sphere((x + ox, oy, z + oz), r, segs=8, rings=6, uv_density=0.6,
                                         color=(0.9 + random.random() * 0.2, 1, 0.9, 1))
        else:
            for i in range(3):
                self.mb("leaves").cone((x, h * 0.6 + i * 1.3 * s, z), (2.0 - i * 0.55) * s, 2.2 * s, segs=8,
                                       color=(0.7, 0.85, 0.75, 1))
        if collide:
            self.phys.add_circle(x, z, 0.35 * s, 0, h)

    def hay_bale(self, x, y, z, rot=0, size=(1.2, 0.9, 2.2), collide=True, sight=True):
        self.mb("hay").box((x, y + size[1] / 2, z), size, rot=(0, rot, 0), uv_density=0.8)
        if collide:
            w, d = (size[0], size[2]) if abs(rot % 180) < 45 else (size[2], size[0])
            return self.phys.add_box_c(x, z, w, d, y, y + size[1], sight=sight)

    def tall_grass(self, x0, x1, z0, z1, density=2.5, height=1.25, name="grass"):
        n = int((x1 - x0) * (z1 - z0) * density)
        mb = self.mb("blades")
        for _ in range(n):
            x = random.uniform(x0, x1)
            z = random.uniform(z0, z1)
            g = random.uniform(0.85, 1.1)
            for _k in range(6):
                h = height * random.uniform(0.6, 1.15)
                mb.blade((x + random.uniform(-0.25, 0.25), 0, z + random.uniform(-0.25, 0.25)), h,
                         random.uniform(0.07, 0.12), yaw=random.uniform(0, 360), lean=random.uniform(0.05, 0.3),
                         col_bottom=(0.16 * g, 0.28 * g, 0.1 * g, 1),
                         col_top=(0.52 * g, 0.68 * g, 0.3 * g, 1))
        self.phys.add_zone("hide", x0, x1, z0, z1, data={"kind": name})

    def grass_tufts(self, x0, x1, z0, z1, n):
        mb = self.mb("blades")
        for _ in range(n):
            x = random.uniform(x0, x1)
            z = random.uniform(z0, z1)
            if in_pond(x, z, 1):
                continue
            g = random.uniform(0.85, 1.12)
            for _k in range(5):
                h = random.uniform(0.18, 0.42)
                mb.blade((x + random.uniform(-0.12, 0.12), 0, z + random.uniform(-0.12, 0.12)), h,
                         random.uniform(0.05, 0.08), yaw=random.uniform(0, 360), lean=random.uniform(0.1, 0.45),
                         col_bottom=(0.22 * g, 0.36 * g, 0.12 * g, 1), col_top=(0.55 * g, 0.74 * g, 0.3 * g, 1))

    def flowers(self, x0, x1, z0, z1, n, y=0.0):
        mb = self.mb("blades")
        for _ in range(n):
            x = random.uniform(x0, x1)
            z = random.uniform(z0, z1)
            col = random.choice([(1, 0.35, 0.4, 1), (1, 0.85, 0.25, 1), (0.97, 0.97, 1, 1), (0.72, 0.5, 0.95, 1)])
            h = random.uniform(0.28, 0.42)
            mb.blade((x, y, z), h, 0.025, yaw=random.uniform(0, 180), lean=0.05,
                     col_bottom=(0.25, 0.42, 0.18, 1), col_top=(0.35, 0.6, 0.25, 1), top_width=0.6)
            for k in range(5):
                a = k / 5 * 360 + random.uniform(-10, 10)
                ar = math.radians(a)
                px, pz = x + math.sin(ar) * 0.045, z + math.cos(ar) * 0.045
                mb.box((px, y + h, pz), (0.05, 0.012, 0.075), color=col, rot=(0, a, 0))
            mb.box((x, y + h + 0.008, z), (0.035, 0.014, 0.035), color=(1, 0.8, 0.2, 1))

    def elec_fence(self, x0, z0, x1, z1, skip=()):
        """Electric fence along an axis-aligned line; skip: list of (a,b) running-coordinate gaps (no wire)."""
        along_x = abs(z1 - z0) < 1e-6
        a0, a1 = (min(x0, x1), max(x0, x1)) if along_x else (min(z0, z1), max(z0, z1))
        n = max(1, int((a1 - a0) / 4))
        post_positions = [a0 + (a1 - a0) * i / n for i in range(n + 1)]
        for (ga, gb) in skip:
            post_positions += [ga, gb]
        for a in post_positions:
            px, pz = (a, z0) if along_x else (x0, a)
            self.mb("wood_dark").box((px, 0.68, pz), (0.14, 1.36, 0.14), uv_density=1.0)
            for hy in (0.45, 0.8, 1.15):
                self.mb("white").box((px, hy, pz), (0.18, 0.06, 0.18), color=(1, 0.85, 0.2, 1))
        cur = a0
        segs = []
        for (ga, gb) in sorted(skip):
            segs.append((cur, ga))
            cur = gb
        segs.append((cur, a1))
        for (sa, sb) in segs:
            if sb - sa < 0.05:
                continue
            mid = (sa + sb) / 2
            for hy in (0.45, 0.8, 1.15):
                if along_x:
                    self.mb("white").box((mid, hy, z0), (sb - sa, 0.025, 0.025), color=(0.75, 0.75, 0.8, 1))
                else:
                    self.mb("white").box((x0, hy, mid), (0.025, 0.025, sb - sa), color=(0.75, 0.75, 0.8, 1))

    def wood_fence(self, x0, z0, x1, z1, h=1.6, collide=True):
        along_x = abs(z1 - z0) < 1e-6
        a0, a1 = (min(x0, x1), max(x0, x1)) if along_x else (min(z0, z1), max(z0, z1))
        n = max(1, int((a1 - a0) / 3))
        for i in range(n + 1):
            a = a0 + (a1 - a0) * i / n
            px, pz = (a, z0) if along_x else (x0, a)
            self.mb("fence_wood").box((px, h / 2, pz), (0.2, h, 0.2), uv_density=1)
        mid = (a0 + a1) / 2
        for hy in (0.45, 0.95, h - 0.15):
            if along_x:
                self.mb("fence_wood").box((mid, hy, z0), (a1 - a0, 0.16, 0.08), uv_density=0.5)
            else:
                self.mb("fence_wood").box((x0, hy, mid), (0.08, 0.16, a1 - a0), uv_density=0.5)
        if collide:
            if along_x:
                return self.phys.add_box(a0, a1, z0 - 0.2, z0 + 0.2, 0, h + 0.4, sight=False)
            return self.phys.add_box(x0 - 0.2, x0 + 0.2, a0, a1, 0, h + 0.4, sight=False)

    def lamp(self, key, pos, radius=10.0, col=(1.0, 0.82, 0.55), intensity=1.2, on=True, bulb=True):
        e = None
        if bulb:
            mb = MeshBuilder()
            mb.sphere((0, 0, 0), 0.13, color=(1, 0.95, 0.7, 1), segs=8, rings=6)
            mb.cylinder((0, 0.1, 0), 0.02, 0.6, color=(0.1, 0.1, 0.1, 1), segs=4)
            e = Entity(model=mb.build(), texture=tex("white"), shader=FARM_SHADER, position=pos)
            self.entities.append(e)
        self.lamps[key] = dict(pos=pos, radius=radius, col=col, intensity=intensity, on=False, ent=e)
        self.set_lamp(key, on)

    def set_lamp(self, key, on=True):
        L = self.lamps.get(key)
        if not L:
            return
        L["on"] = on
        if on:
            self.g.env.set_lamp(key, L["pos"], L["radius"], L["col"], L["intensity"])
        else:
            self.g.env.set_lamp(key, None)
        if L["ent"] is not None:
            L["ent"].set_shader_input("u_emissive", 1.6 if on else 0.0)

    def add_item(self, key, model, pos, rot=0.0, scale=1.0, bob=False, spin=False, glow=0.0):
        if key in self.items:
            self.items[key].remove()
        it = WorldItem(self, key, model, pos, rot, scale, bob, spin, glow)
        self.items[key] = it
        return it

    def remove_item(self, key):
        it = self.items.pop(key, None)
        if it:
            it.remove()

    # batches that share a texture but need their own draw settings
    BATCH_TEX = {"blades": "white"}
    BATCH_SWAY = {"blades": 0.07, "leaves": 0.012}

    def finalize(self):
        for texname, mb in self.batches.items():
            m = mb.build()
            if m is None:
                continue
            e = Entity(model=m, texture=tex(self.BATCH_TEX.get(texname, texname)), shader=FARM_SHADER)
            if texname in self.BATCH_SWAY:
                e.set_shader_input("u_sway", self.BATCH_SWAY[texname])
            self.entities.append(e)
        self.batches.clear()

    # ------------------------------------------------------------------
    # build
    # ------------------------------------------------------------------
    def build(self):
        self.build_ground()
        self.build_pasture()
        self.build_cowshed()
        self.build_shed()
        self.build_barn()
        self.build_coop()
        self.build_house()
        self.build_processing()
        self.build_gate_and_boundary()
        self.build_yard_props()
        self.build_scenery()
        self.build_zones()
        self.finalize()
        self.build_dynamic()
        self.build_nav()

    def build_ground(self):
        def col(x, y, z):
            k = 0.92 + 0.08 * math.sin(x * 0.07) * math.cos(z * 0.05)
            if y > 3:
                k *= 0.95
            return (k, k * 1.02, k * 0.95, 1)
        self.mb("grass").heightfield(-300, -300, 300, 300, terrain_h, res=120, color_fn=col, uv_density=0.22)
        d = self.mb("dirt")
        y = 0.02
        # driveway & paths
        d.ground(-3.5, 30, 3.5, 86, y=y, uv_density=0.25)
        d.ground(-3.5, 86, 3.5, 300, y=y, uv_density=0.25)
        d.ground(3.5, 20, 58, 26, y=y + 0.002, uv_density=0.25)
        d.ground(68, 24, 78, 44, y=y + 0.001, uv_density=0.25)
        d.ground(58, 20, 78, 26, y=y + 0.001, uv_density=0.25)
        d.ground(-16, -46, 40, -12, y=y, uv_density=0.25)
        d.ground(-3.5, -12, 3.5, 30, y=y + 0.001, uv_density=0.25)
        d.ground(40, -46, 56, -30, y=y + 0.001, uv_density=0.25)
        # muddy patches in the pasture
        m = self.mb("mud")
        m.ground(-30, -40, -18, -28, y=y, uv_density=0.3)
        m.ground(-60, -18, -44, -12, y=y, uv_density=0.3)
        m.disk((POND[0], 0.03, POND[1]), POND[2] + 1.6, POND[3] + 1.6, segs=32, uv_density=0.3)

    def build_pasture(self):
        x0, x1, z0, z1 = PASTURE
        gx, gz0, gz1 = GATE_PASTURE
        mx, mz0, mz1 = MOOHOLE
        # electric fence: south, west, north, east (with gate gap)
        self.elec_fence(x0, z0, x1, z0)
        self.elec_fence(x0, z0, x0, z1)
        self.elec_fence(x0, z1, x1, z1)
        self.elec_fence(x1, z0, x1, z1, skip=[(gz0, gz1)])
        H = 1.5
        self.phys.add_box(x0, x1, z0 - 0.15, z0 + 0.15, 0, H, sight=False, tag="fence")
        self.phys.add_box(x0 - 0.15, x0 + 0.15, z0, z1, 0, H, sight=False, tag="fence")
        self.phys.add_box(x0, x1, z1 - 0.15, z1 + 0.15, 0, H, sight=False, tag="fence")
        self.phys.add_box(x1 - 0.15, x1 + 0.15, z0, mz0, 0, H, sight=False, tag="fence")
        self.colliders["moohole"] = self.phys.add_box(x1 - 0.15, x1 + 0.15, mz0, mz1, 0, H, sight=False, tag="fence")
        self.phys.add_box(x1 - 0.15, x1 + 0.15, mz1, gz0, 0, H, sight=False, tag="fence")
        self.phys.add_box(x1 - 0.15, x1 + 0.15, gz1, z1, 0, H, sight=False, tag="fence")
        for (fx, fz) in [(x0 + 10, z0), (x1, -10), (-50, z1), (x0, -40)]:
            self.add_ia(f"fence_{fx}_{fz}", (fx, 0.8, fz), 0.6, "Electric fence", text_key="fence")
        # sagging wire at the moo-hole (the story decides if it's usable)
        self.add_ia("moohole", (mx, 0.5, (mz0 + mz1) / 2), 0.8, "Sagging wire", prompt="Examine")
        # oak
        ox, oz = OAK
        self.mb("bark").cylinder((ox, 0, oz), 1.0, 6.0, segs=10, radius_top=0.7, uv_density=0.7)
        for (bx, by, bz, rx, rz, L) in [(0.5, 4.5, 0, 0, -50, 3.5), (-0.5, 4.8, 0.3, 0, 45, 3.2),
                                        (0, 5.0, 0.6, -45, 0, 3.0), (0, 4.4, -0.6, 50, 0, 3.2)]:
            self.mb("bark").cylinder((ox + bx, by, oz + bz), 0.3, L, segs=6, rot=(rx, 0, rz), radius_top=0.15, uv_density=0.7)
        for (lx, ly, lz, r) in [(0, 9.0, 0, 4.6), (3.2, 7.8, 1.0, 3.2), (-3.0, 8.0, -1.0, 3.3), (0.8, 7.6, -3.1, 3.0),
                                (-1.0, 7.9, 3.0, 3.0), (0, 11.0, 0.5, 3.0)]:
            self.mb("leaves").sphere((ox + lx, ly, oz + lz), r, segs=10, rings=7, uv_density=0.35)
        self.phys.add_circle(ox, oz, 1.1, 0, 6)
        self.add_ia("oak", (ox, 1.6, oz), 1.2, "The Old Oak")
        # hollow in the oak with carving
        # pond
        cx, cz, rx, rz = POND
        self.pond = Entity(model=MeshBuilder().disk((cx, 0.06, cz), rx, rz, segs=40, uv_density=0.15).build(),
                           texture=tex("water"), shader=FARM_SHADER)
        self.pond.set_shader_input("u_water", 1.0)
        self.entities.append(self.pond)
        for _ in range(9):
            a = random.uniform(0, 6.28)
            rr = random.uniform(0.2, 0.8)
            self.mb("white").cylinder((cx + math.sin(a) * rx * rr, 0.07, cz + math.cos(a) * rz * rr), 0.45, 0.02,
                                      segs=10, color=(0.3, 0.6, 0.25, 1))
        for _ in range(26):
            a = random.uniform(0, 6.28)
            px, pz = cx + math.sin(a) * (rx + 0.3), cz + math.cos(a) * (rz + 0.3)
            h = random.uniform(1.0, 1.6)
            self.mb("white").box((px, h / 2, pz), (0.04, h, 0.04), color=(0.35, 0.55, 0.25, 1))
            self.mb("white").box((px, h - 0.1, pz), (0.09, 0.3, 0.09), color=(0.45, 0.28, 0.15, 1))
        self.add_ia("pond", (cx, 0.3, cz), 3.0, "The pond", text_key=None, reach=4.0).text = [
            "The pond. Green, still, and home to a frog named Gerald (you assume).",
            "You see your reflection. You look like someone with six days left."]
        # trough
        tx, tz = -30, -22
        self.box("wood", (tx, 0.35, tz), (1.1, 0.7, 3.4), collide=True)
        tw = Entity(model=MeshBuilder().box((tx, 0.66, tz), (0.9, 0.05, 3.2), uv_density=0.3, faces=[4]).build(),
                    texture=tex("water"), shader=FARM_SHADER)
        tw.set_shader_input("u_water", 0.6)
        self.entities.append(tw)
        self.add_ia("trough", (tx, 0.8, tz), 1.2, "Trough")
        self.spawns["trough"] = (tx + 1.6, 0, tz)
        # salt lick
        self.box("wood_dark", (-34, 0.4, -48), (0.2, 0.8, 0.2), collide=True)
        self.mb("white").box((-34, 0.95, -48), (0.5, 0.35, 0.5), color=(0.95, 0.85, 0.85, 1))
        self.add_ia("saltlick", (-34, 1.0, -48), 0.6, "Salt lick")
        # mooriarty's hideout: U of hay bales
        for (hx, hz, r, y) in [(-74, -24, 90, 0), (-74, -31, 90, 0), (-70.5, -21.5, 0, 0), (-70.5, -33.5, 0, 0),
                               (-74, -24, 90, 0.9), (-76.3, -27.5, 0, 0)]:
            self.hay_bale(hx, y, hz, r)
        self.add_ia("hideout_bales", (-73, 1.0, -27.5), 1.2, "Hay bales", text_key=None).text = [
            "Mooriarty's 'office'. A sign scratched into the hay: 'NO REFUNDS'."]
        # Cardboard Chuck
        scx, scz = -28, -66
        self.box("wood_dark", (scx, 0.6, scz), (0.08, 1.2, 0.08))
        self.sign("poster_employee", (scx, 1.4, scz - 0.05), (1.0, 1.4), rot_y=0, double=True)
        self.add_ia("scarecrow", (scx, 1.4, scz), 0.7, "Cardboard Chuck")
        # rock piles
        for i, (rx_, rz_) in enumerate([(-27, -27), (-40, -44), (-14, -31), (8, -13), (40, 22), (31, -31), (-8, 18)]):
            for k in range(6):
                self.mb("white").sphere((rx_ + random.uniform(-0.4, 0.4), 0.06, rz_ + random.uniform(-0.4, 0.4)),
                                        random.uniform(0.1, 0.16), color=(0.55, 0.54, 0.5, 1), segs=6, rings=4,
                                        scale=(1.2, 0.7, 1))
            self.add_ia(f"rockpile_{i}", (rx_, 0.2, rz_), 0.6, "Rocks", text_key="rockpile", prompt="Take a rock")
        # tall grass hiding spots
        self.tall_grass(-25, -20, -52, -44)
        self.tall_grass(-60, -55, -73, -68)
        self.grass_tufts(x0 + 1, x1 - 1, z0 + 1, z1 - 14, 260)
        self.flowers(-70, -30, -70, -15, 60)

    def build_cowshed(self):
        x0, x1, z0, z1 = COWSHED
        H = 4.2
        inside = ((x0 + x1) / 2, (z0 + z1) / 2)
        self.wall(x0, z1, x1, z1, H, 0.25, "barn_red", tex_in="wood_dark", inside=inside)
        self.wall(x0, z0, x0, z1, H, 0.25, "barn_red", tex_in="wood_dark", inside=inside)
        self.wall(x1, z0, x1, z1, H, 0.25, "barn_red", tex_in="wood_dark", inside=inside)
        self.wall_gaps(x0, z0, x1, z0, H, [(-58, -46, 3.4)], 0.25, "barn_red", tex_in="wood_dark", inside=inside)
        self.gable_roof(x0 - 0.2, x1 + 0.2, z0 - 0.2, z1 + 0.2, H, 2.6, "metal_rust", along="x", end_tex="barn_red")
        self.mb("hay").ground(x0 + 0.1, z0 + 0.1, x1 - 0.1, z1 - 0.1, y=0.025, uv_density=0.35)
        self.sign("sign_cowshed", (-52, 3.8, z0 - 0.15), (3.2, 1.0))
        # stalls along the back wall
        for i in range(9):
            sx = x0 + 3 * i
            if 0 < i < 9:
                self.box("wood", (sx, 0.6, z1 - 2.0), (0.15, 1.2, 4.0), collide=True)
        for i in range(8):
            cx = x0 + 1.5 + 3 * i
            self.mb("hay").box((cx, 0.12, z1 - 2.3), (2.4, 0.25, 3.0), uv_density=0.8)
            if cx != -43.5:
                self.add_ia(f"bed_{i}", (cx, 0.4, z1 - 2.3), 0.9, "Hay bed", text_key="hay_bed")
        # stall 47 is the last one (x -45..-42)
        self.sign("sign_47", (-42.2, 1.5, -1.0), (0.6, 0.6), rot_y=-90, double=True)
        self.add_ia("bed47", (-43.5, 0.4, 0.7), 1.0, "Your bed (stall 47)", text_key="stall_sign")
        self.spawns["bed47"] = (-43.5, 0.0, -1.2, 180)
        self.spawns["cowshed_front"] = (-52, 0, -16, 180)
        self.lamp("cowshed", (-52, 3.7, -5), radius=13, intensity=1.1, on=False)
        self.add_ia("cowshed_bulb", (-52, 3.7, -5), 0.4, "Light bulb", text_key="lamp", reach=4.0)

    def build_shed(self):
        x0, x1, z0, z1 = SHED
        H = 3.0
        inside = ((x0 + x1) / 2, (z0 + z1) / 2)
        self.wall(x0, z0, x1, z0, H, 0.2, "wood", tex_in="wood_dark", inside=inside)
        self.wall(x0, z1, x1, z1, H, 0.2, "wood", tex_in="wood_dark", inside=inside)
        # east wall with door gap z -22.8..-21.2
        self.wall_gaps(x1, z0, x1, z1, H, [(-22.8, -21.2, 2.3)], 0.2, "wood", tex_in="wood_dark", inside=inside)
        # west (back) wall with the loose board gap z -23..-21.4 (board is dynamic)
        self.wall_gaps(x0, z0, x0, z1, H, [(-23.0, -21.4, 2.0)], 0.2, "wood", tex_in="wood_dark", inside=inside)
        self.mb("metal_rust").box(((x0 + x1) / 2, H + 0.08, (z0 + z1) / 2), (x1 - x0 + 1.0, 0.14, z1 - z0 + 1.0),
                                  rot=(0, 0, -3), uv_density=0.4)
        self.mb("floorboards").ground(x0 + 0.1, z0 + 0.1, x1 - 0.1, z1 - 0.1, y=0.03, uv_density=0.5)
        # generator
        gx, gz = -10.4, -24.6
        self.box("white", (gx, 0.55, gz), (1.4, 1.1, 1.0), color=(0.95, 0.75, 0.1, 1), collide=True)
        self.mb("white").box((gx, 1.15, gz), (1.0, 0.12, 0.7), color=(0.2, 0.2, 0.2, 1))
        self.mb("white").cylinder((gx + 0.4, 1.1, gz + 0.25), 0.06, 0.5, color=(0.2, 0.2, 0.2, 1), segs=6)
        self.sign("do_not_touch", (gx, 1.9, z0 + 0.12), (1.3, 0.65), rot_y=180)
        self.add_ia("generator", (gx, 0.9, gz), 0.8, "Generator")
        self.add_ia("fuse", (gx + 0.5, 1.0, gz + 0.5), 0.35, "Main fuse", text_key="generator")
        # cable from the generator, out through the back wall, along the ground and up a fence post
        # to the wires (fence line x = -18, wires at 0.45 / 0.8 / 1.15)
        cable = (0.1, 0.1, 0.1, 1)
        cz = gz - 0.2
        self.mb("white").box(((x0 + gx - 0.7) / 2, 0.9, cz), (gx - 0.7 - x0 + 0.2, 0.05, 0.05), color=cable)
        self.mb("white").box((x0 - 0.13, 0.49, cz), (0.05, 0.86, 0.05), color=cable)
        fx = -17.905                    # east face of a fence post
        self.mb("white").box(((x0 - 0.13 + fx) / 2, 0.05, cz), ((x0 - 0.13) - fx + 0.05, 0.05, 0.05), color=cable)
        self.mb("wood_dark").box((-18, 0.68, cz), (0.14, 1.36, 0.14), uv_density=1.0)
        for hy in (0.45, 0.8, 1.15):
            self.mb("white").box((-18, hy, cz), (0.18, 0.06, 0.18), color=(1, 0.85, 0.2, 1))
        self.mb("white").box((fx, 0.6, cz), (0.05, 1.12, 0.05), color=cable)
        # workbench along north wall
        self.box("wood", (-8.5, 0.9, z1 - 0.55), (5.0, 0.1, 0.9), collide=False)
        for lx in (-10.8, -6.2):
            self.box("wood", (lx, 0.45, z1 - 0.55), (0.1, 0.9, 0.8))
        self.phys.add_box(-11, -6, z1 - 1.0, z1 - 0.1, 0, 1.0)
        self.add_ia("workbench", (-8.5, 1.0, z1 - 0.6), 1.0, "Workbench")
        # toolbox (combination lock)
        self.box("white", (-9.3, 1.1, z1 - 0.55), (0.7, 0.35, 0.35), color=(0.75, 0.1, 0.1, 1))
        self.mb("white").box((-9.3, 1.1, z1 - 0.72), (0.12, 0.12, 0.04), color=(0.8, 0.8, 0.85, 1))
        self.add_ia("toolbox", (-9.3, 1.15, z1 - 0.55), 0.45, "Toolbox", text_key=None).text = [
            "A red toolbox with a three-digit combination lock."]
        self.sign("sticky_combo", (-8.2, 1.45, z1 - 0.12), (0.4, 0.4), rot_y=0)
        self.add_ia("sticky_combo", (-8.2, 1.45, z1 - 0.15), 0.3, "Sticky note", text_key=None).text = [
            "The sticky note says: 'TOOLBOX COMBO = my PERFECT bowling score!!! (don't forget)'."]
        # shelf with trophy
        self.box("wood", (-5.3, 1.8, z1 - 0.3), (1.2, 0.06, 0.4))
        self.mb("white").box((-5.3, 1.98, z1 - 0.3), (0.2, 0.3, 0.2), color=(0.9, 0.75, 0.25, 1))
        self.mb("white").sphere((-5.3, 2.2, z1 - 0.3), 0.1, color=(0.9, 0.75, 0.25, 1))
        self.sign("trophy_plaque", (-5.3, 1.84, z1 - 0.52), (0.32, 0.16), rot_y=0)
        self.add_ia("trophy", (-5.3, 2.0, z1 - 0.3), 0.35, "Bowling trophy")
        # poster
        self.sign("poster_employee", (-6.5, 1.6, z0 + 0.12), (0.7, 1.0), rot_y=180)
        self.add_ia("poster", (-6.5, 1.6, z0 + 0.15), 0.5, "Poster")
        # shelves on south wall
        self.box("wood", (-6.4, 1.0, z0 + 0.35), (2.2, 0.06, 0.5))
        self.lamp("shed", (-8, 2.7, -22), radius=7, intensity=1.0, on=True)
        self.spawns["shed_in"] = (-7.5, 0, -22, 90)
        self.spawns["shed_back"] = (-14.5, 0, -22.2, 90)

    def build_barn(self):
        x0, x1, z0, z1 = BARN
        H = 7.0
        inside = ((x0 + x1) / 2, (z0 + z1) / 2)
        self.wall(x0, z1, x1, z1, H, 0.3, "barn_red", tex_in="wood_dark", inside=inside)
        self.wall(x1, z0, x1, z1, H, 0.3, "barn_red", tex_in="wood_dark", inside=inside)
        self.wall_gaps(x0, z0, x1, z0, H, [(18, 26, 5.0)], 0.3, "barn_red", tex_in="wood_dark", inside=inside)
        self.wall_gaps(x0, z0, x0, z1, H, [(-0.4, 1.8, 2.4)], 0.3, "barn_red", tex_in="wood_dark", inside=inside)
        # white trim X on the big doors' header
        self.mb("white").box((22, 5.3, z0 - 0.2), (8.6, 0.25, 0.1), color=(0.95, 0.95, 0.92, 1))
        # gambrel roof
        cz = (z0 + z1) / 2
        half = (z1 - z0) / 2
        pts = [(z0, H), (z0 + 3.4, H + 3.6), (cz, H + 5.2), (z1 - 3.4, H + 3.6), (z1, H)]
        for i in range(4):
            (za, ya), (zb, yb) = pts[i], pts[i + 1]
            L = math.hypot(zb - za, yb - ya)
            ang = math.degrees(math.atan2(yb - ya, zb - za))
            self.mb("shingles").box(((x0 + x1) / 2, (ya + yb) / 2 + 0.1, (za + zb) / 2), (x1 - x0 + 1.2, 0.2, L + 0.3),
                                    rot=(-ang, 0, 0), uv_density=0.4)
        for xx in (x0, x1):
            self.mb("barn_red").poly([(xx, H, z0), (xx, H, z1), (xx, H + 3.6, z1 - 3.4), (xx, H + 5.2, cz),
                                      (xx, H + 3.6, z0 + 3.4)], uv_density=0.4)
        self.mb("dirt").ground(x0 + 0.2, z0 + 0.2, x1 - 0.2, z1 - 0.2, y=0.03, uv_density=0.3)
        # hayloft floor
        self.mb("floorboards").box(((x0 + x1) / 2, LOFT_Y - 0.15, (4 + z1) / 2), (x1 - x0 - 0.3, 0.3, z1 - 4),
                                   uv_density=0.5)
        self.phys.add_floor(x0, x1, 4, z1, LOFT_Y, surface="hay")
        for px in (16, 22, 28):
            self.box("wood_dark", (px, LOFT_Y / 2, 4.1), (0.3, LOFT_Y, 0.3), collide=True)
        # railing along the loft edge (gap at the ramp top)
        self.box("wood", ((x0 + 29.3) / 2, LOFT_Y + 0.9, 4.1), (29.3 - x0, 0.1, 0.1))
        for px in range(11, 29, 2):
            self.box("wood", (px, LOFT_Y + 0.45, 4.1), (0.08, 0.9, 0.08))
        self.phys.add_box(x0, 29.3, 3.95, 4.25, LOFT_Y - 0.1, LOFT_Y + 1.2, sight=False)
        # ramp up the east side
        rx0, rx1, rz0, rz1 = 29.5, 33.4, -6.0, 4.0
        L = math.hypot(rz1 - rz0, LOFT_Y)
        ang = math.degrees(math.atan2(LOFT_Y, rz1 - rz0))
        self.mb("floorboards").box(((rx0 + rx1) / 2, LOFT_Y / 2 - 0.1, (rz0 + rz1) / 2), (rx1 - rx0, 0.2, L),
                                   rot=(-ang, 0, 0), uv_density=0.5)
        self.phys.add_floor(rx0, rx1, rz0, rz1, 0.0, LOFT_Y, axis="z", surface="wood")
        # keep things from walking underneath the ramp. Each blocker's top sits below the ramp surface
        # one body-radius before it starts, so someone walking up the slope never bumps into it.
        for k in range(1, 4):
            za = rz0 + (rz1 - rz0) * k / 4
            zb = rz0 + (rz1 - rz0) * (k + 1) / 4
            top = LOFT_Y * (za - 0.9 - rz0) / (rz1 - rz0) - 0.1
            self.phys.add_box(rx0 + 0.05, rx1 - 0.05, za, zb, 0, top, sight=False)
        self.mb("wood_dark").box((rx0, LOFT_Y / 2, (rz0 + rz1) / 2), (0.12, 0.12, L), rot=(-ang, 0, 0))
        # rafters
        for rzz in (6.0, 10.0):
            self.mb("wood_dark").box(((x0 + x1) / 2, 6.3, rzz), (x1 - x0, 0.25, 0.25))
        # loft hay
        for (hx, hz, r, y) in [(12, 12.5, 90, LOFT_Y), (12, 12.5, 90, LOFT_Y + 0.9), (14.5, 13, 0, LOFT_Y),
                               (26, 12.8, 0, LOFT_Y), (24, 12.8, 0, LOFT_Y), (25, 12.8, 0, LOFT_Y + 0.9),
                               (32.5, 12.5, 90, LOFT_Y)]:
            self.hay_bale(hx, y, hz, r)
        self.mb("hay").sphere((17, LOFT_Y, 10.5), 1.6, segs=10, rings=6, scale=(1.4, 0.7, 1.2), uv_density=0.8)
        self.mb("hay").sphere((19, LOFT_Y, 12.5), 1.4, segs=10, rings=6, scale=(1.3, 0.6, 1.0), uv_density=0.8)
        self.phys.add_zone("hide", 15, 21, 9, 13.5, y0=LOFT_Y - 0.5, data={"kind": "hay"})
        self.add_ia("loft_hay", (17, LOFT_Y + 0.7, 10.5), 1.2, "Hay pile")
        self.spawns["loft_hide"] = (14.8, LOFT_Y, 10.8, 200)
        # ground floor props: workbench, stalls under the loft
        self.box("wood", (11.2, 0.9, 8), (1.0, 0.1, 4.0), collide=False)
        self.phys.add_box(10.2, 11.8, 6, 10, 0, 1.0)
        for i, sx_ in enumerate((17, 23)):
            self.box("wood", (sx_, 0.6, 9), (0.15, 1.2, 9.5), collide=True)
        self.hay_bale(14, 0, 11.5, 90)
        self.hay_bale(31.5, 0, 11.5, 0)
        self.hay_bale(31.5, 0.9, 11.5, 0)
        self.lamp("barn", (22, 5.5, 0), radius=14, intensity=0.9, on=False)
        self.lamp("loft", (20, 6.0, 9), radius=9, intensity=0.8, on=False)
        self.spawns["barn_in"] = (22, 0, -6, 0)
        self.spawns["ramp_top"] = (31.4, LOFT_Y, 5.2, 270)

    def build_coop(self):
        x0, x1, z0, z1 = COOP_HUT
        H = 2.2
        inside = ((x0 + x1) / 2, (z0 + z1) / 2)
        self.wall(x0, z0, x1, z0, H, 0.15, "wood", inside=inside)
        self.wall(x0, z1, x1, z1, H, 0.15, "wood", inside=inside)
        self.wall(x1, z0, x1, z1, H, 0.15, "wood", inside=inside)
        self.wall_gaps(x0, z0, x0, z1, H, [(-30.2, -28.8, 1.0)], 0.15, "wood", inside=inside)
        self.gable_roof(x0 - 0.2, x1 + 0.2, z0 - 0.2, z1 + 0.2, H, 1.2, "shingles", along="x", end_tex="wood")
        self.mb("wood").box((x0 - 0.9, 0.25, -29.5), (1.8, 0.08, 1.2), rot=(0, 0, 15))
        # run fence (wood posts + translucent chicken wire)
        rx0, rx1, rz0, rz1 = COOP_RUN
        self.wood_fence(rx0, rz0, rx1, rz0, h=1.4)
        self.wood_fence(rx0, rz1, rx1, rz1, h=1.4)
        self.wood_fence(rx1, rz0, rx1, rz1, h=1.4)
        self.wood_fence(rx0, rz0, rx0, -36.2, h=1.4)
        self.wood_fence(rx0, -33.8, rx0, rz1, h=1.4)
        wire = MeshBuilder()
        for (a, b, c, d) in [(rx0, rz0, rx1, rz0), (rx0, rz1, rx1, rz1), (rx1, rz0, rx1, rz1)]:
            if b == d:
                wire.box(((a + c) / 2, 0.7, b), (c - a, 1.4, 0.01), color=(0.8, 0.8, 0.85, 0.25))
            else:
                wire.box((a, 0.7, (b + d) / 2), (0.01, 1.4, d - b), color=(0.8, 0.8, 0.85, 0.25))
        we = Entity(model=wire.build(), texture=tex("white"), shader=FARM_SHADER)
        we.setTransparency(TransparencyAttrib.MAlpha)
        no_shadow(we)
        self.entities.append(we)
        self.mb("dirt").ground(rx0, rz0, rx1, rz1, y=0.03, uv_density=0.3)
        self.add_ia("coop", (41, 1.2, -29.5), 1.5, "Chicken coop")
        self.spawns["coop_gate_out"] = (32, 0, -35, 90)

    def build_house(self):
        x0, x1, z0, z1 = HOUSE
        y = HOUSE_Y
        H = 3.0
        inside = ((x0 + x1) / 2, (z0 + z1) / 2)
        # foundation + floor
        self.box("stone", ((x0 + x1) / 2, y / 2, (z0 + z1) / 2), (x1 - x0 + 0.3, y, z1 - z0 + 0.3))
        # living room | kitchen split at x=KX (the front door opens into the living room)
        self.mb("floorboards").ground(x0, z0, KX, 40, y=y + 0.01, uv_density=0.5)
        self.mb("tiles").ground(KX, z0, x1, 40, y=y + 0.01, uv_density=0.5)
        self.mb("floorboards").ground(x0, 40, x1, 42, y=y + 0.01, uv_density=0.5)
        self.mb("carpet").ground(x0, 42, 62, z1, y=y + 0.01, uv_density=0.5)
        self.mb("tiles").ground(62, 42, x1, z1, y=y + 0.01, uv_density=0.6)
        self.phys.add_floor(x0, x1, z0, z1, y, surface="wood")
        # exterior walls
        self.wall_gaps(x0, z0, x1, z0, H, [(55.2, 56.8, 2.3)], 0.25, "siding", y0=y, tex_in="wallpaper", inside=inside)
        self.wall(x0, z1, x1, z1, H, 0.25, "siding", y0=y, tex_in="wallpaper", inside=inside)
        self.wall(x0, z0, x0, z1, H, 0.25, "siding", y0=y, tex_in="wallpaper", inside=inside)
        self.wall_gaps(x1, z0, x1, z1, H, [(40.2, 41.8, 2.3)], 0.25, "siding", y0=y, tex_in="wallpaper", inside=inside)
        # interior walls
        self.wall_gaps(KX, z0, KX, 40, H, [(33.9, 35.9, 2.3)], 0.15, "wallpaper", y0=y)
        self.wall_gaps(x0, 40, x1, 40, H, [(47.9, 49.9, 2.3), (61.9, 63.9, 2.3)], 0.15, "wallpaper", y0=y)
        self.wall_gaps(x0, 42, x1, 42, H, [(46.9, 48.9, 2.3), (55.9, 57.9, 2.3), (63.9, 65.9, 2.3)], 0.15, "wallpaper", y0=y)
        self.wall(52, 42, 52, z1, H, 0.15, "wallpaper", y0=y)
        self.wall(62, 42, 62, z1, H, 0.15, "wallpaper", y0=y)
        # ceiling (seen from inside) + roof
        self.mb("white").box(((x0 + x1) / 2, y + H + 0.05, (z0 + z1) / 2), (x1 - x0, 0.1, z1 - z0), color=(0.93, 0.9, 0.85, 1))
        self.gable_roof(x0 - 0.3, x1 + 0.3, z0 - 0.3, z1 + 0.3, y + H + 0.1, 2.8, "shingles", along="x", end_tex="siding")
        # windows (frames + glass that glows at night)
        glass = MeshBuilder()
        # (x, z, yaw of the outward-facing quad, outward normal)
        wins = [(47, z0, 0, (0, -1)), (52, z0, 0, (0, -1)), (61, z0, 0, (0, -1)), (65, z0, 0, (0, -1)),
                (48, z1, 180, (0, 1)), (57, z1, 180, (0, 1)), (65, z1, 180, (0, 1)),
                (x0, 35, 90, (-1, 0)), (x0, 45, 90, (-1, 0)), (x1, 35, -90, (1, 0))]
        for (wx, wz, ry, (nx, nz)) in wins:
            # white frame proud of the siding, glass just in front of it, and glass on the inside wall face
            fx, fz = wx + nx * 0.16, wz + nz * 0.16
            fsize = (1.6, 1.3, 0.06) if nz else (0.06, 1.3, 1.6)
            self.mb("white").box((fx, y + 1.6, fz), fsize, color=(0.95, 0.95, 0.95, 1))
            glass.quad((wx + nx * 0.195, y + 1.6, wz + nz * 0.195), (1.4, 1.1), rot=(0, ry, 0))
            glass.quad((wx - nx * 0.135, y + 1.6, wz - nz * 0.135), (1.4, 1.1), rot=(0, ry + 180, 0))
        self.house_glass = Entity(model=glass.build(), texture=tex("window"), shader=FARM_SHADER)
        no_shadow(self.house_glass)
        self.entities.append(self.house_glass)
        # porch
        px0, px1, pz0, pz1 = 50, 62, 26, 30
        self.mb("floorboards").box(((px0 + px1) / 2, y / 2, (pz0 + pz1) / 2), (px1 - px0, y, pz1 - pz0), uv_density=0.5)
        self.phys.add_floor(px0, px1, pz0, pz1, y, surface="wood")
        for ppx in (50.2, 61.8):
            self.box("white", (ppx, y + 1.4, 26.2), (0.18, 2.8, 0.18), color=(0.95, 0.95, 0.92, 1), collide=True)
        self.mb("shingles").box((56, y + 2.95, 28), (13, 0.15, 4.6), rot=(12, 0, 0), uv_density=0.4)
        # porch props
        mat = MeshBuilder().box((56, y + 0.02, 29.1), (1.4, 0.03, 0.7), uv_rect=(0, 0, 1, 1), faces=[4])
        self.props["doormat"] = Entity(model=mat.build(), texture=tex("welcome_mat"), shader=FARM_SHADER)
        self.add_ia("doormat", (56, y + 0.1, 29.1), 0.5, "Doormat", reach=3.0)
        self.mb("white").cylinder((60.6, y, 28.6), 0.3, 0.45, color=(0.75, 0.4, 0.25, 1), segs=10, radius_top=0.36)
        for k in range(5):
            self.mb("white").sphere((60.6 + random.uniform(-0.2, 0.2), y + 0.6, 28.6 + random.uniform(-0.2, 0.2)), 0.12,
                                    color=(0.8, 0.3, 0.6, 1), segs=6, rings=4)
        self.add_ia("flowerpot", (60.6, y + 0.5, 28.6), 0.5, "Flowerpot")
        self.box("wood", (52.5, y + 0.5, 28.5), (0.8, 1.0, 0.8), collide=True)
        # doghouse (RIP Biscuit)
        self.box("wood", (40, 0.6, 33), (1.3, 1.2, 1.5), collide=True)
        self.mb("shingles").box((40, 1.35, 33), (1.5, 0.1, 1.7), rot=(0, 0, 0))
        self.add_ia("doghouse", (40, 0.8, 32.2), 0.8, "Doghouse")
        # --- living room ---
        self.box("white", (48, y + 0.35, 37.2), (4.0, 0.7, 1.1), color=(0.45, 0.3, 0.55, 1), collide=True)
        self.mb("white").box((48, y + 0.8, 37.7), (4.0, 0.7, 0.3), color=(0.45, 0.3, 0.55, 1))
        self.add_ia("couch", (48, y + 0.8, 37.2), 1.0, "Couch")
        self.box("wood_dark", (48, y + 0.25, 34.5), (1.6, 0.5, 0.9), collide=True)
        self.box("wood_dark", (53.8, y + 0.35, 31.0), (1.8, 0.7, 0.6), collide=True)
        self.box("white", (53.8, y + 1.05, 31.0), (1.2, 0.7, 0.5), color=(0.15, 0.15, 0.15, 1))
        self.sign("tv", (53.8, y + 1.05, 31.26), (1.05, 0.6), rot_y=180, emissive=0.8)
        self.add_ia("tv", (53.8, y + 1.05, 31.0), 0.6, "TV")
        # fireplace on west wall
        self.box("stone", (44.6, y + 0.8, 35), (0.8, 1.6, 2.0), collide=True)
        self.mb("white").box((44.9, y + 0.5, 35), (0.4, 0.8, 1.0), color=(0.1, 0.08, 0.07, 1))
        self.add_ia("fireplace", (44.9, y + 0.8, 35), 0.8, "Fireplace")
        # the rug
        self.mb("atlas").box((50.5, y + 0.03, 33.5), (2.6, 0.02, 1.8), uv_rect=models.uvr("hide_black", 0.02))
        self.add_ia("rug", (50.5, y + 0.1, 33.5), 1.0, "Rug", reach=3.0)
        # --- kitchen ---
        self.box("wood", (67.2, y + 0.45, 35), (1.3, 0.9, 9.6), collide=True)
        self.box("white", (67.2, y + 0.92, 35), (1.35, 0.06, 9.7), color=(0.85, 0.85, 0.82, 1))
        self.box("white", (67.2, y + 1.0, 38.6), (1.2, 2.0, 1.1), color=(0.92, 0.92, 0.95, 1), collide=True)
        self.add_ia("fridge", (66.6, y + 1.2, 38.6), 0.7, "Fridge")
        self.mb("white").box((67.2, y + 0.96, 32.6), (0.9, 0.04, 0.8), color=(0.15, 0.15, 0.15, 1))
        self.add_ia("stove", (66.8, y + 1.0, 32.6), 0.6, "Stove")
        self.mb("white").box((66.9, y + 0.99, 35.8), (0.35, 0.1, 0.25), color=(0.9, 0.3, 0.25, 1))
        self.sign("cookbook", (66.62, y + 1.15, 35.8), (0.2, 0.28), rot_y=90)
        self.add_ia("cookbook", (66.7, y + 1.1, 35.8), 0.35, "Cookbook")
        self.sign("calendar", (60, y + 1.7, 39.9), (0.55, 0.7), rot_y=0)
        self.add_ia("calendar", (60, y + 1.7, 39.8), 0.4, "Calendar")
        # table + chairs
        self.box("wood", (61, y + 0.75, 34), (1.8, 0.08, 1.2), collide=False)
        for lx in (60.3, 61.7):
            for lz in (33.6, 34.4):
                self.box("wood", (lx, y + 0.37, lz), (0.08, 0.74, 0.08))
        self.phys.add_box_c(61, 34, 1.8, 1.2, y, y + 0.8)
        self.box("wood", (59.6, y + 0.45, 34), (0.5, 0.9, 0.5), collide=True)
        self.box("wood", (62.4, y + 0.45, 34), (0.5, 0.9, 0.5), collide=True)
        self.mb("white").cylinder((60.7, y + 0.79, 34.2), 0.06, 0.15, color=(0.8, 0.9, 0.95, 1), segs=8)
        self.add_ia("dentures", (60.7, y + 0.95, 34.2), 0.25, "Glass of dentures")
        # key hook on the kitchen wall (z=40, facing south)
        self.box("wood_dark", (58, y + 1.5, 39.9), (0.5, 0.12, 0.05))
        # --- office ---
        self.box("wood", (47.5, y + 0.4, 46.6), (2.4, 0.8, 1.0), collide=True)
        self.box("white", (47.5, y + 1.1, 46.9), (0.8, 0.6, 0.1), color=(0.85, 0.83, 0.75, 1))
        self.sign("monitor", (47.5, y + 1.1, 46.84), (0.66, 0.48), rot_y=0, emissive=0.9)
        self.props["monitor_screen"] = self.entities[-1]
        self.sign("sticky_password", (47.95, y + 1.3, 46.83), (0.14, 0.14), rot_y=0)
        self.add_ia("computer", (47.5, y + 1.1, 46.7), 0.5, "Computer")
        self.add_ia("desk", (46.5, y + 0.85, 46.3), 0.4, "Desk")
        self.box("white", (44.8, y + 0.7, 43.2), (0.8, 1.4, 0.8), color=(0.5, 0.5, 0.52, 1), collide=True)
        self.add_ia("filing", (45.1, y + 0.9, 43.2), 0.5, "Filing cabinet")
        # gun cabinet on the office/bedroom wall
        self.box("wood_dark", (51.4, y + 1.1, 46.5), (0.9, 2.2, 1.6), collide=True)
        self.mb("white").box((50.93, y + 1.2, 46.5), (0.03, 1.6, 1.2), color=(0.55, 0.7, 0.8, 1))
        self.add_ia("gun_cabinet", (50.9, y + 1.2, 46.5), 0.7, "Gun cabinet")
        # --- bedroom ---
        self.box("wood", (58.5, y + 0.3, 46.2), (2.2, 0.6, 3.4), collide=True)
        self.mb("white").box((58.5, y + 0.65, 46.0), (2.1, 0.12, 3.0), color=(0.35, 0.6, 0.35, 1))
        self.mb("white").box((58.5, y + 0.75, 47.4), (1.6, 0.18, 0.5), color=(0.95, 0.95, 0.95, 1))
        self.mb("wood_dark").box((58.5, y + 0.8, 47.9), (2.3, 1.6, 0.1))
        self.add_ia("bed_farmer", (58.5, y + 0.8, 46), 1.0, "Chuck's bed")
        self.box("wood", (60.9, y + 0.35, 47.4), (0.6, 0.7, 0.6), collide=True)
        self.mb("white").box((60.9, y + 0.8, 47.4), (0.25, 0.2, 0.12), color=(0.9, 0.3, 0.2, 1))
        self.add_ia("nightstand", (60.9, y + 0.6, 47.1), 0.4, "Nightstand")
        self.add_ia("alarm_clock", (60.9, y + 0.85, 47.4), 0.2, "Alarm clock")
        self.box("wood_dark", (52.7, y + 1.1, 46.4), (1.2, 2.2, 2.2), collide=True)
        self.add_ia("wardrobe", (53.35, y + 1.1, 46.4), 0.8, "Wardrobe")
        self.spawns["wardrobe_hide"] = (53.9, y, 45.4, 90)
        # --- bathroom ---
        self.box("white", (66.8, y + 0.25, 47.1), (0.7, 0.5, 0.9), color=(0.97, 0.97, 0.97, 1), collide=True)
        self.mb("white").box((66.8, y + 0.7, 47.5), (0.6, 0.5, 0.2), color=(0.97, 0.97, 0.97, 1))
        self.add_ia("toilet", (66.8, y + 0.5, 47.0), 0.5, "Toilet")
        self.box("white", (63.4, y + 0.35, 46.4), (2.4, 0.7, 2.6), color=(0.95, 0.95, 0.97, 1), collide=True)
        self.mb("white").box((63.4, y + 0.66, 46.4), (2.0, 0.05, 2.2), color=(0.7, 0.85, 0.95, 1))
        self.add_ia("bathtub", (63.4, y + 0.8, 46.4), 1.0, "Bathtub")
        self.mb("white").sphere((64.0, y + 0.72, 45.8), 0.08, color=(1, 0.9, 0.1, 1), segs=6, rings=4)
        self.add_ia("duck", (64.0, y + 0.8, 45.8), 0.2, "Rubber duck")
        self.mb("white").box((67.9, y + 1.6, 43.5), (0.05, 0.8, 0.6), color=(0.75, 0.85, 0.95, 1))
        self.add_ia("mirror", (67.8, y + 1.6, 43.5), 0.4, "Mirror")
        # lamps inside (on when Chuck is home at night)
        self.lamp("house_living", (50, y + 2.8, 35), radius=9, intensity=1.0, on=False)
        self.lamp("house_kitchen", (62, y + 2.8, 35), radius=9, intensity=1.0, on=False)
        self.lamp("house_hall", (56, y + 2.8, 41), radius=7, intensity=0.8, on=False)
        self.lamp("house_office", (48, y + 2.8, 45), radius=6, intensity=0.9, on=False)
        self.lamp("house_bed", (57, y + 2.8, 45), radius=6, intensity=0.9, on=False)
        self.lamp("house_bath", (65, y + 2.8, 45), radius=5, intensity=0.9, on=False)
        self.lamp("porch", (56, y + 2.6, 28.5), radius=9, intensity=1.1, on=False)
        self.spawns["house_front"] = (56, 0, 24, 0)
        self.spawns["house_in"] = (56, y, 32, 0)

    def build_processing(self):
        x0, x1, z0, z1 = PROC
        H = 6.0
        self.wall(x0, z0, x1, z0, H, 0.4, "concrete")
        self.wall(x0, z1, x1, z1, H, 0.4, "concrete")
        self.wall(x1, z0, x1, z1, H, 0.4, "concrete")
        self.wall(x0, z0, x0, z1, H, 0.4, "concrete")
        self.mb("concrete").box(((x0 + x1) / 2, H + 0.1, (z0 + z1) / 2), (x1 - x0 + 0.6, 0.3, z1 - z0 + 0.6))
        self.mb("metal").box((x0 - 0.25, 2.2, -41), (0.1, 4.4, 5.0), uv_density=0.5)
        self.sign("sign_processing", (x0 - 0.3, 5.2, -41), (6.0, 3.0), rot_y=90)
        self.mb("metal").cylinder((73, H, -46), 0.7, 7.0, segs=10)
        self.add_ia("processing_door", (x0 - 0.3, 1.5, -41), 2.0, "Big door", reach=3.5)
        self.add_ia("processing_sign", (x0 - 0.3, 5.2, -41), 2.5, "Sign", reach=8.0)
        # cattle chute (ominous)
        self.wood_fence(50.5, -44, 56, -44, h=1.5)
        self.wood_fence(50.5, -38, 56, -38, h=1.5)
        self.lamp("processing", (x0 - 1.0, 5.5, -41), radius=10, col=(0.9, 0.95, 1.0), intensity=1.0, on=False)
        self.spawns["processing_front"] = (52, 0, -41, 90)

    def build_gate_and_boundary(self):
        fx0, fx1, fz0, fz1 = FARM
        self.wood_fence(fx0, fz0, fx1, fz0, h=1.8)
        self.wood_fence(fx0, fz0, fx0, fz1, h=1.8)
        self.wood_fence(fx1, fz0, fx1, fz1, h=1.8)
        self.wood_fence(fx0, fz1, -4.5, fz1, h=1.8)
        self.wood_fence(4.5, fz1, fx1, fz1, h=1.8)
        # gate posts + arch sign
        for gx in (-4.6, 4.6):
            self.box("wood_dark", (gx, 3.0, GATE_Z), (0.5, 6.0, 0.5), collide=True)
        self.box("wood_dark", (0, 6.1, GATE_Z), (9.8, 0.4, 0.4))
        self.sign("sign_farm", (0, 5.0, GATE_Z - 0.25), (6.5, 2.4), rot_y=0)
        self.sign("sign_farm", (0, 5.0, GATE_Z + 0.25), (6.5, 2.4), rot_y=180)
        # cattle grid
        self.mb("white").box((0, -0.05, 82.5), (8.6, 0.1, 4.0), color=(0.08, 0.08, 0.08, 1))
        for k in range(14):
            self.mb("metal").box((-4.2 + k * 0.645, 0.04, 82.5), (0.12, 0.08, 4.0))
        self.colliders["cattle_grid"] = self.phys.add_box(-4.3, 4.3, 80.6, 84.4, 0, 1.6, sight=False, tag="grid")
        self.add_ia("cattle_grid", (0, 0.3, 82.5), 2.0, "Cattle grid", reach=3.5)
        self.spawns["grid_south"] = (0, 0, 78, 0)
        # outside: road sign + mailbox
        self.box("wood_dark", (7, 1.2, 100), (0.15, 2.4, 0.15))
        self.sign("road_sign", (7, 2.4, 99.9), (2.4, 1.2), rot_y=0, double=True)
        self.add_ia("road_sign", (7, 2.3, 100), 1.2, "Road sign", reach=4)
        self.box("wood_dark", (6, 0.6, 88.5), (0.12, 1.2, 0.12))
        self.mb("white").box((6, 1.3, 88.5), (0.4, 0.35, 0.6), color=(0.3, 0.35, 0.4, 1))
        self.add_ia("mailbox", (6, 1.3, 88.5), 0.4, "Mailbox")

    def build_yard_props(self):
        # woodpile / planks
        for k in range(5):
            self.mb("wood").box((-8, 0.1 + k * 0.1, -40 + (k % 2) * 0.1), (0.3 + k * 0.05, 0.08, 2.4), rot=(0, 90, 0), uv_density=1)
        self.phys.add_box_c(-8, -40, 2.6, 1.0, 0, 0.6)
        self.add_ia("woodpile", (-8, 0.5, -40), 1.2, "Lumber pile")
        # windmill
        wx, wz = 6, 32
        for sx in (-1, 1):
            for sz in (-1, 1):
                self.mb("metal").box((wx + sx * 0.8, 5, wz + sz * 0.8), (0.12, 10.2, 0.12), rot=(sz * 5, 0, -sx * 5))
        for yy in (2, 4.5, 7):
            self.mb("metal").box((wx, yy, wz), (1.8 - yy * 0.1, 0.08, 1.8 - yy * 0.1))
        self.phys.add_box_c(wx, wz, 2.0, 2.0, 0, 10)
        self.windmill_rotor = Entity(position=(wx, 10.3, wz - 0.6))
        rm = MeshBuilder()
        for k in range(12):
            ang = math.radians(k * 30)
            rm.box((math.sin(ang) * 1.4, math.cos(ang) * 1.4, 0), (0.4, 2.4, 0.03), color=(0.92, 0.92, 0.94, 1),
                   rot=(0, 0, -k * 30))
        rm.cylinder((0, 0, -0.2), 0.25, 0.4, color=(0.5, 0.5, 0.55, 1), segs=8, rot=(90, 0, 0))
        Entity(parent=self.windmill_rotor, model=rm.build(), texture=tex("white"), shader=FARM_SHADER)
        self.mb("metal").box((wx, 10.3, wz + 0.8), (0.05, 0.8, 1.6))
        self.add_ia("windmill", (wx, 1.5, wz), 1.2, "Windmill")
        # silo
        sx, sz = SILO
        self.mb("metal").cylinder((sx, 0, sz), 3.5, 14, segs=20, uv_density=0.4)
        self.mb("metal").sphere((sx, 14, sz), 3.5, segs=20, rings=10, scale=(1, 0.5, 1))
        self.phys.add_circle(sx, sz, 3.6, 0, 16)
        self.add_ia("silo", (sx - 3.2, 1.5, sz), 1.5, "Silo")
        # garden gnome + flowerbed by the house corner
        self.mb("dirt").ground(38, 21, 44, 27, y=0.035, uv_density=0.4)
        self.flowers(38.2, 43.8, 21.2, 26.8, 40)
        gx, gz = 41, 24
        self.gnome = Entity(position=(gx, 0, gz), rotation_y=200)
        gm = MeshBuilder()
        gm.cylinder((0, 0, 0), 0.18, 0.35, color=(0.2, 0.4, 0.8, 1), segs=8, radius_top=0.14)
        gm.sphere((0, 0.45, 0), 0.13, color=(0.95, 0.78, 0.65, 1), segs=8, rings=6)
        gm.sphere((0, 0.37, 0.05), 0.12, color=(0.97, 0.97, 0.97, 1), segs=8, rings=6, scale=(1, 1.2, 0.8))
        gm.cone((0, 0.52, 0), 0.14, 0.35, color=(0.85, 0.12, 0.12, 1), segs=8)
        gm.box((0.15, 0.3, 0.2), (0.02, 0.02, 0.8), color=(0.4, 0.3, 0.2, 1), rot=(-30, 0, 0))
        Entity(parent=self.gnome, model=gm.build(), texture=tex("white"), shader=FARM_SHADER)
        self.phys.add_circle(gx, gz, 0.25, 0, 0.9)
        self.add_ia("gnome", (gx, 0.45, gz), 0.4, "Garden gnome")
        # pickup truck parked by the house
        self.pickup = models.pickup_model(position=(74, 0, 36), rotation_y=180)
        self.colliders["pickup"] = self.phys.add_box_c(74, 36.2, 2.1, 5.0, 0, 2.0)
        self.add_ia("pickup", (74, 1.2, 36), 1.8, "Pickup truck", reach=3.0)
        # power poles along the driveway
        for pz in (40, 60, 80):
            self.mb("wood_dark").cylinder((5.5, 0, pz), 0.15, 7.5, segs=6)
            self.mb("wood_dark").box((5.5, 7.2, pz), (1.6, 0.12, 0.12))
        # misc junk near the barn: barrels, milk cans
        for (bx, bz) in [(8.5, -12.5), (9.2, -11.6), (35.5, -8)]:
            self.mb("metal_rust").cylinder((bx, 0, bz), 0.4, 1.0, segs=10)
            self.phys.add_circle(bx, bz, 0.42, 0, 1.0)
        self.hay_bale(-4, 0, -12, 90)
        self.hay_bale(-4, 0.9, -12, 90)
        self.hay_bale(-1.5, 0, -12, 90)
        self.hay_bale(36, 0, -16, 0)
        self.hay_bale(13, 0, 18, 90)
        # tall grass / bushes outside for hiding
        self.tall_grass(-17.5, -13.5, -28, -16)
        self.tall_grass(-17.4, -12, -70, -62)
        self.tall_grass(6.5, 9.4, 3, 12)
        self.tall_grass(28, 33, -30, -26)
        self.tall_grass(69, 72, 30, 34)
        self.tall_grass(44, 49.5, 27.6, 29.6)
        for (bx, bz, r) in [(-14, -63, 1.3), (-15.5, -70, 1.1), (7, 13, 1.0), (70.5, 29, 1.1), (45, 26.5, 1.0)]:
            self.mb("leaves").sphere((bx, r * 0.6, bz), r, segs=8, rings=6, uv_density=0.6, scale=(1.2, 0.8, 1.2))

    def build_scenery(self):
        random.seed(12)
        # trees along the outer fence and scattered outside
        for i in range(70):
            side = random.randrange(4)
            if side == 0:
                x, z = random.uniform(-95, 95), random.uniform(-95, -84)
            elif side == 1:
                x, z = random.uniform(-100, -86), random.uniform(-90, 95)
            elif side == 2:
                x, z = random.uniform(86, 100), random.uniform(-90, 95)
            else:
                x, z = random.choice([random.uniform(-95, -12), random.uniform(12, 95)]), random.uniform(90, 100)
            self.tree(x, z + 0, random.uniform(0.9, 1.6), collide=False, kind=random.choice(["round", "round", "pine"]))
        for i in range(90):
            a = random.uniform(0, 6.28)
            r = random.uniform(120, 250)
            x, z = math.sin(a) * r, math.cos(a) * r
            if abs(x) < 10 and z > 80:
                continue
            h = terrain_h(x, z)
            s = random.uniform(1.2, 2.2)
            kind = random.choice(["round", "pine"])
            ht = 3.2 * s
            self.mb("bark").cylinder((x, h - 0.5, z), 0.3 * s, ht, segs=6)
            if kind == "round":
                self.mb("leaves").sphere((x, h + ht + 1.0 * s, z), 2.0 * s, segs=7, rings=5, uv_density=0.4)
            else:
                self.mb("leaves").cone((x, h + ht * 0.5, z), 2.0 * s, 4.5 * s, segs=7)
        # a few trees inside the farm
        for (x, z, s) in [(-4, 45, 1.3), (20, 40, 1.1), (35, 45, 1.4), (78, 60, 1.5), (-40, 30, 1.6), (-60, 40, 1.2),
                          (-30, 60, 1.4), (30, 70, 1.3), (60, 70, 1.2), (-70, 70, 1.5), (-20, 20, 1.2), (78, -10, 1.3),
                          (78, -60, 1.4), (20, -60, 1.3), (0, -70, 1.2), (-10, -55, 1.1)]:
            self.tree(x, z, s)
        self.grass_tufts(-80, 80, 10, 85, 220)
        self.grass_tufts(-16, 80, -78, -46, 120)
        self.flowers(-78, 80, 10, 85, 80)

    def build_zones(self):
        P = self.phys
        P.add_zone("pasture", *PASTURE)
        P.add_zone("cowshed", *COWSHED)
        P.add_zone("shed", *SHED)
        P.add_zone("barn", *BARN)
        P.add_zone("loft", BARN[0], BARN[1], 4, BARN[3], y0=2.5)
        P.add_zone("coop", *COOP_RUN)
        P.add_zone("house", *HOUSE)
        P.add_zone("porch", 50, 62, 26, 30)
        P.add_zone("farm", *FARM)
        P.add_zone("gate_area", -8, 8, 70, 90)
        # footstep surfaces
        for r in [(-3.5, 3.5, 30, 300), (3.5, 58, 20, 26), (68, 78, 24, 44), (-16, 40, -46, -12), (-3.5, 3.5, -12, 30),
                  (40, 56, -46, -30), (-30, -18, -40, -28), (-60, -44, -18, -12), (BARN[0], BARN[1], BARN[2], BARN[3]),
                  COOP_RUN]:
            P.add_zone("surf_dirt", *r)
        P.add_zone("surf_hay", *COWSHED)
        P.add_zone("surf_wood", *SHED)

    def build_dynamic(self):
        g = self.g
        # pasture gate (hinge at the south end, swings east into the yard)
        gx, gz0, gz1 = GATE_PASTURE

        def gate_model(mb, length, height):
            for yy in (0.3, 0.75, 1.2):
                mb.box((0.0, yy, length / 2), (0.08, 0.1, length), color=(0.7, 0.72, 0.75, 1))
            for k in range(5):
                mb.box((0, 0.7, k * length / 4), (0.08, 1.3, 0.08), color=(0.7, 0.72, 0.75, 1))
            # diagonal brace, bottom rail to top rail, corner to corner
            rise = 1.2 - 0.3
            mb.box((0, 0.75, length / 2), (0.06, 0.08, math.hypot(length, rise)), color=(0.7, 0.72, 0.75, 1),
                   rot=(math.degrees(math.atan2(rise, length)), 0, 0))
        self.doors["pasture_gate"] = Door(self, "pasture_gate", (gx, gz0), gz1 - gz0, along="z", sign=1, height=1.45,
                                          texture="white", open_angle=100, model_fn=gate_model)
        self.add_ia("pasture_gate", (gx + 0.3, 1.0, gz1 - 0.6), 0.7, "Pasture gate", text_key=None).text = [
            "The pasture gate. The bolt is on the outside, where cows can't reach it. Clever, Chuck. Clever."]
        # shed door (east wall, hinge at south end)
        self.doors["shed_door"] = Door(self, "shed_door", (SHED[1], -22.8), 1.6, along="z", sign=1, height=2.3,
                                       texture="wood_dark", open_angle=100)
        self.add_ia("shed_door", (SHED[1] + 0.2, 1.2, -22.0), 0.7, "Shed door")
        # loose board in the back wall
        self.shed_board = Entity()
        bm = MeshBuilder()
        for k in range(3):
            bm.box((SHED[0], 1.0, -22.95 + 0.25 + k * 0.53), (0.12, 2.0, 0.5), color=(0.95 - k * 0.05, 0.9, 0.85, 1),
                   rot=(0, 0, 3 - k * 2))
        Entity(parent=self.shed_board, model=bm.build(), texture=tex("wood"), shader=FARM_SHADER)
        self.colliders["shed_board"] = self.phys.add_box(SHED[0] - 0.12, SHED[0] + 0.12, -23.0, -21.4, 0, 2.0)
        self.add_ia("shed_board", (SHED[0] - 0.2, 1.0, -22.2), 0.7, "Loose board", text_key=None).text = [
            "One of the boards back here is loose. A good headbutt would do it... but it would be LOUD."]
        # barn doors
        bx0 = BARN[0]

        def slab(mb, length, height):
            mb.box((length / 2, height / 2, 0), (length, height, 0.12), color=(1, 1, 1, 1), uv_density=0.4)
            mb.box((length / 2, height / 2, -0.08), (length * 1.1, 0.2, 0.04), color=(0.95, 0.95, 0.92, 1), rot=(0, 0, 52))
            mb.box((length / 2, height / 2, -0.08), (length * 1.1, 0.2, 0.04), color=(0.95, 0.95, 0.92, 1), rot=(0, 0, -52))
        self.doors["barn_left"] = Door(self, "barn_left", (18, BARN[2]), 4.0, along="x", sign=1, height=5.0,
                                       texture="barn_red", open_angle=105, model_fn=slab)
        self.doors["barn_right"] = Door(self, "barn_right", (26, BARN[2]), 4.0, along="x", sign=-1, height=5.0,
                                        texture="barn_red", open_angle=-105,
                                        model_fn=_slab_neg)
        self.add_ia("barn_door", (22, 1.6, BARN[2] - 0.3), 1.6, "Barn doors")
        self.doors["barn_side"] = Door(self, "barn_side", (bx0, -0.4), 2.2, along="z", sign=1, height=2.4,
                                       texture="barn_red", open_angle=-100)
        self.add_ia("barn_side", (bx0 - 0.2, 1.2, 0.7), 0.7, "Side door", text_key=None).text = [
            "The barn's side door. It's unlatched. Chuck's security is, as usual, vibes-based."]
        # house doors
        self.doors["front_door"] = Door(self, "front_door", (55.2, HOUSE[2]), 1.6, along="x", sign=1, height=2.3,
                                        y0=HOUSE_Y, texture="wood_dark", open_angle=-100)
        self.add_ia("front_door", (56, HOUSE_Y + 1.2, HOUSE[2] - 0.2), 0.7, "Front door")
        self.doors["back_door"] = Door(self, "back_door", (HOUSE[1], 40.2), 1.6, along="z", sign=1, height=2.3,
                                       y0=HOUSE_Y, texture="wood_dark", open_angle=100)
        self.add_ia("back_door", (HOUSE[1] + 0.2, HOUSE_Y + 1.2, 41.0), 0.7, "Back door")
        # coop gate
        self.doors["coop_gate"] = Door(self, "coop_gate", (COOP_RUN[0], -36.2), 2.4, along="z", sign=1, height=1.3,
                                       texture="fence_wood", open_angle=-95)
        self.add_ia("coop_gate", (COOP_RUN[0] - 0.2, 0.8, -35), 0.7, "Coop gate", text_key=None).text = [
            "The gate to the chicken run. A sign: 'BEWARE OF ROOSTER'. Underneath, in smaller letters: 'SERIOUSLY'."]
        # main gate leaves (chained)

        def leaf(mb, length, height):
            for yy in (0.4, 1.0, 1.6):
                mb.box((length / 2, yy, 0), (abs(length), 0.12, 0.1), color=(0.75, 0.77, 0.8, 1))
            for k in range(5):
                mb.box((k * length / 4, 1.0, 0), (0.1, 1.9, 0.1), color=(0.75, 0.77, 0.8, 1))
        self.doors["main_left"] = Door(self, "main_left", (-4.35, GATE_Z), 4.3, along="x", sign=1, height=2.0,
                                       texture="white", open_angle=-100, model_fn=leaf)
        self.doors["main_right"] = Door(self, "main_right", (4.35, GATE_Z), 4.3, along="x", sign=-1, height=2.0,
                                        texture="white", open_angle=100, model_fn=lambda mb, L, h: leaf(mb, -L, h))
        self.chain = Entity()
        cm = MeshBuilder()
        for k in range(8):
            cm.box((0, 0.7 + k * 0.08, GATE_Z - 0.08), (0.14, 0.05, 0.05), color=(0.4, 0.4, 0.42, 1), rot=(0, 0, 45 if k % 2 else -45))
        cm.box((0, 0.55, GATE_Z - 0.12), (0.2, 0.25, 0.08), color=(0.8, 0.65, 0.2, 1))
        Entity(parent=self.chain, model=cm.build(), texture=tex("white"), shader=FARM_SHADER)
        self.add_ia("main_gate", (0, 1.0, GATE_Z - 0.3), 1.5, "Main gate")
        # tractor (parked in the barn)
        self.tractor = models.tractor_model(position=(22, 0, 1), rotation_y=180)
        self.colliders["tractor"] = self.phys.add_box_c(22, 1.2, 2.4, 4.4, 0, 2.6)
        self.add_ia("tractor", (22, 1.4, 1.5), 1.6, "Tractor", reach=3.0,
                    follow=lambda: (self.tractor.x, 1.4, self.tractor.z))
        # wind chimes on the porch
        self.chimes = models.item_model("chimes", position=(58.5, HOUSE_Y + 2.4, 27.2))
        self.add_ia("chimes", (58.5, HOUSE_Y + 2.3, 27.2), 0.4, "Wind chimes", reach=3.2)
        # clover spots (placement decided by the game)
        self.clover_spots = [
            (-76, 0.25, -73), (-60, 0.25, 1.5), (-20.5, 0.25, -73), (-44, 0.25, -59),   # pasture (one in the pond)
            (-11, 0.25, -19), (-17, 0.25, -45),                                          # shed area
            (33, LOFT_Y + 0.3, 13.2), (11, 0.25, 13), (45.5, 0.25, 8),                  # barn / silo
            (51, 0.25, -47), (46.5, 0.25, -26),                                          # coop
            (77, 0.25, -34), (60, 0.25, -52),                                            # processing
            (45, HOUSE_Y + 0.25, 31), (67, HOUSE_Y + 0.25, 47.6), (40, 0.25, 34.2),      # house
            (78, 0.25, 84), (-78, 0.25, 84), (5, 0.25, 84),                              # far corners
            (-40, 0.25, 30),
        ]

    def build_nav(self):
        Y = HOUSE_Y
        L = LOFT_Y
        nodes = [
            # pasture
            (-22, 0, -35), (-30, 0, -30), (-40, 0, -40), (-50, 0, -25), (-52, 0, -15), (-52, 0, -6), (-30, 0, -55),
            (-60, 0, -45), (-35, 0, -20), (-45, 0, -68), (-65, 0, -20), (-70, 0, -60), (-30, 0, -70), (-35, 0, -10),
            # yard
            (-14, 0, -35), (-2, 0, -22), (-7, 0, -22), (0, 0, -30), (-8, 0, -44), (0, 0, -10), (14, 0, -14),
            (22, 0, -14), (22, 0, -7), (15, 0, 3), (29, 0, 5), (31.4, 0, -7.5), (5.5, 0, 0.7), (12.5, 0, 0.7),
            (30, 0, -20), (32, 0, -35), (38, 0, -35), (45, 0, -38), (46, 0, -26), (0, 0, 10), (0, 0, 30),
            (0, 0, 50), (0, 0, 75), (0, 0, 80), (20, 0, 23), (40, 0, 18), (56, 0, 23), (56, Y, 28),
            (56, Y, 32), (50, Y, 35), (KX, Y, 34.9), (63.5, Y, 37), (48.9, Y, 39.2), (51.2, Y, 38.9), (48.9, Y, 41),
            (57, Y, 41),
            (62.9, Y, 38.5), (64.9, Y, 41), (47.9, Y, 43.5), (48, Y, 45), (56.9, Y, 43.5), (56.5, Y, 44.8),
            (61.0, Y, 43.4), (64.9, Y, 43.5), (65.5, Y, 45.0), (70, 0, 41), (74, 0, 32), (70, 0, 25), (54, 0, -28), (49.5, 0, -47), (40, 0, -12), (-14, 0, -22), (-14, 0, -66), (-8, 0, -60), (8, 0, -40), (20, 0, -30),
            (-17, 0, 0), (-20, 0, 10), (60, 0, -20), (78, 0, 20), (40, 0, 55), (-40, 0, 20), (-10, 0, 60),
            # loft
            (31.4, L, 5.2), (25, L, 8), (18, L, 8), (13, L, 9),
            # either side of the moo-hole, the pasture gate, the shed's back wall and the cattle grid
            (-21, 0, -66.1), (-15, 0, -66.1), (-21, 0, -35), (-15, 0, -35), (-16, 0, -22.2),
            (0, 0, 88), (0, 0, 100), (0, 0, 130),
        ]
        self.nav_nodes = nodes
        n = len(nodes)
        edges = {i: [] for i in range(n)}
        # Openings (doors, gates, the moo-hole...) are built open so edges can pass through them;
        # find_path skips an edge while any opening it crosses is shut.
        gates = {k: d.col for k, d in self.doors.items()}
        for k in ("moohole", "shed_board", "cattle_grid"):
            if k in self.colliders:
                gates[k] = self.colliders[k]
        saved = {k: c.enabled for k, c in gates.items()}
        for c in gates.values():
            c.enabled = False
        self.edge_gates: dict[tuple, list] = {}
        for i in range(n):
            for j in range(i + 1, n):
                a, b = nodes[i], nodes[j]
                if abs(a[1] - b[1]) > 0.5 and not (a[1] >= L - 0.1 and b[1] >= L - 0.1):
                    continue
                d = math.dist((a[0], a[2]), (b[0], b[2]))
                if d > 45:
                    continue
                if self._segment_clear(a, b):
                    edges[i].append(j)
                    edges[j].append(i)
                    crossed = [c for c in gates.values() if _seg_hits_box(a, b, c, 0.45)]
                    if crossed:
                        self.edge_gates[(i, j)] = crossed
                        self.edge_gates[(j, i)] = crossed
        for k, c in gates.items():
            c.enabled = saved[k]
        # the ramp
        ib = nodes.index((31.4, 0, -7.5))
        it = nodes.index((31.4, L, 5.2))
        edges[ib].append(it)
        edges[it].append(ib)
        self.nav_edges = edges

    def _segment_clear(self, a, b, r=0.45):
        d = math.dist((a[0], a[2]), (b[0], b[2]))
        steps = max(1, int(d / 0.4))
        y = min(a[1], b[1])
        for k in range(steps + 1):
            t = k / steps
            x = a[0] + (b[0] - a[0]) * t
            z = a[2] + (b[2] - a[2]) * t
            yy = a[1] + (b[1] - a[1]) * t
            if self.phys.blocked_at(x, z, r, yy + 0.1, 1.7):
                return False
            if in_pond(x, z, 0.5):
                return False
        return True

    def nearest_node(self, p, y_hint=None):
        best, bd = None, 1e9
        for i, nd in enumerate(self.nav_nodes):
            if y_hint is not None and abs(nd[1] - y_hint) > 1.5:
                continue
            d = math.dist((p[0], p[2]), (nd[0], nd[2]))
            if d < bd and (d < 3 or self._segment_clear((p[0], nd[1], p[2]), nd)):
                best, bd = i, d
        if best is None:
            for i, nd in enumerate(self.nav_nodes):
                d = math.dist((p[0], p[2]), (nd[0], nd[2])) + abs(nd[1] - (y_hint or 0)) * 10
                if d < bd:
                    best, bd = i, d
        return best

    def find_path(self, start, goal):
        """A* on the nav graph; returns list of (x,y,z) waypoints ending at goal."""
        if self._segment_clear(start, goal) and abs(start[1] - goal[1]) < 0.5:
            return [goal]
        s = self.nearest_node(start, start[1])
        t = self.nearest_node(goal, goal[1])
        if s is None or t is None:
            return [goal]
        N = self.nav_nodes
        openq = [(0, s)]
        came = {s: None}
        cost = {s: 0}
        while openq:
            _, cur = heapq.heappop(openq)
            if cur == t:
                break
            for nb in self.nav_edges[cur]:
                blockers = self.edge_gates.get((cur, nb))
                if blockers and any(b.enabled for b in blockers):
                    continue
                c = cost[cur] + math.dist(N[cur], N[nb])
                if nb not in cost or c < cost[nb]:
                    cost[nb] = c
                    came[nb] = cur
                    heapq.heappush(openq, (c + math.dist(N[nb], N[t]), nb))
        if t not in came:
            return [goal]
        path = []
        cur = t
        while cur is not None:
            path.append(N[cur])
            cur = came[cur]
        path.reverse()
        # smooth: skip the first node if we can see the second one
        if len(path) > 1 and self._segment_clear(start, path[1]) and abs(start[1] - path[1][1]) < 0.5:
            path = path[1:]
        if len(path) > 1 and self._segment_clear(path[-2], goal) and abs(path[-2][1] - goal[1]) < 0.5:
            path = path[:-1]
        path.append(goal)
        return path

    # ------------------------------------------------------------------
    def update(self, dt):
        self.t += dt
        for d in self.doors.values():
            d.update(dt)
        for it in self.items.values():
            it.update(dt)
        self.windmill_rotor.rotation_z += dt * 40
        self.pond.set_shader_input("texture_offset", (self.t * 0.01, self.t * 0.006))
        self.chimes.rotation_z = math.sin(self.t * 1.3) * 4


def _seg_hits_box(a, b, box, r=0.0):
    """Does the XZ segment a->b pass within r of the box?"""
    x0, x1, z0, z1 = box.x0 - r, box.x1 + r, box.z0 - r, box.z1 + r
    t0, t1 = 0.0, 1.0
    for p, d, lo, hi in ((a[0], b[0] - a[0], x0, x1), (a[2], b[2] - a[2], z0, z1)):
        if abs(d) < 1e-9:
            if p < lo or p > hi:
                return False
            continue
        ta, tb = (lo - p) / d, (hi - p) / d
        if ta > tb:
            ta, tb = tb, ta
        t0, t1 = max(t0, ta), min(t1, tb)
        if t0 > t1:
            return False
    return True


def _slab_neg(mb, length, height):
    mb.box((-length / 2, height / 2, 0), (length, height, 0.12), color=(1, 1, 1, 1), uv_density=0.4)
    mb.box((-length / 2, height / 2, -0.08), (length * 1.1, 0.2, 0.04), color=(0.95, 0.95, 0.92, 1), rot=(0, 0, 52))
    mb.box((-length / 2, height / 2, -0.08), (length * 1.1, 0.2, 0.04), color=(0.95, 0.95, 0.92, 1), rot=(0, 0, -52))
