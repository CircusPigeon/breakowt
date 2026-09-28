"""2.5D collision: axis-aligned boxes and vertical cylinders on an XZ grid,
walkable floor regions (flat or ramps), named zones and line-of-sight tests.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

CELL = 8.0


@dataclass(eq=False)
class Box:
    x0: float
    x1: float
    z0: float
    z1: float
    y0: float = 0.0
    y1: float = 3.0
    enabled: bool = True
    sight: bool = True      # blocks line of sight
    solid: bool = True      # blocks movement
    tag: str = ""


@dataclass(eq=False)
class Circle:
    x: float
    z: float
    r: float
    y0: float = 0.0
    y1: float = 2.0
    enabled: bool = True
    sight: bool = True
    solid: bool = True
    tag: str = ""
    owner: object = None


@dataclass(eq=False)
class Floor:
    x0: float
    x1: float
    z0: float
    z1: float
    h0: float
    h1: float = None      # ramp end height (None = flat)
    axis: str = "z"       # ramp rises along +axis
    surface: str = "wood"
    enabled: bool = True

    def height(self, x, z):
        if self.h1 is None:
            return self.h0
        if self.axis == "z":
            t = (z - self.z0) / (self.z1 - self.z0)
        elif self.axis == "-z":
            t = (self.z1 - z) / (self.z1 - self.z0)
        elif self.axis == "x":
            t = (x - self.x0) / (self.x1 - self.x0)
        else:
            t = (self.x1 - x) / (self.x1 - self.x0)
        t = min(1.0, max(0.0, t))
        return self.h0 + (self.h1 - self.h0) * t


@dataclass(eq=False)
class Zone:
    name: str
    x0: float
    x1: float
    z0: float
    z1: float
    y0: float = -10
    y1: float = 100
    enabled: bool = True
    data: dict = field(default_factory=dict)

    def contains(self, x, z, y=0.0):
        return self.enabled and self.x0 <= x <= self.x1 and self.z0 <= z <= self.z1 and self.y0 <= y <= self.y1


class Physics:
    def __init__(self):
        self.grid: dict[tuple[int, int], list] = {}
        self.shapes: list = []
        self.dynamic: list[Circle] = []
        self.floors: list[Floor] = []
        self.zones: list[Zone] = []

    # ------------------------------------------------------------------
    def _cells(self, x0, x1, z0, z1):
        for i in range(int(math.floor(x0 / CELL)), int(math.floor(x1 / CELL)) + 1):
            for j in range(int(math.floor(z0 / CELL)), int(math.floor(z1 / CELL)) + 1):
                yield (i, j)

    def _insert(self, s, x0, x1, z0, z1):
        for c in self._cells(x0, x1, z0, z1):
            self.grid.setdefault(c, []).append(s)
        self.shapes.append(s)
        return s

    def add_box(self, x0, x1, z0, z1, y0=0.0, y1=3.0, **kw) -> Box:
        if x0 > x1:
            x0, x1 = x1, x0
        if z0 > z1:
            z0, z1 = z1, z0
        b = Box(x0, x1, z0, z1, y0, y1, **kw)
        return self._insert(b, x0, x1, z0, z1)

    def add_box_c(self, cx, cz, w, d, y0=0.0, y1=3.0, **kw) -> Box:
        return self.add_box(cx - w / 2, cx + w / 2, cz - d / 2, cz + d / 2, y0, y1, **kw)

    def add_circle(self, x, z, r, y0=0.0, y1=2.0, **kw) -> Circle:
        c = Circle(x, z, r, y0, y1, **kw)
        return self._insert(c, x - r, x + r, z - r, z + r)

    def add_dynamic(self, x, z, r, y0=0.0, y1=1.6, **kw) -> Circle:
        c = Circle(x, z, r, y0, y1, **kw)
        self.dynamic.append(c)
        return c

    def remove(self, s):
        if s in self.dynamic:
            self.dynamic.remove(s)
            return
        for lst in self.grid.values():
            if s in lst:
                lst.remove(s)
        if s in self.shapes:
            self.shapes.remove(s)

    def add_floor(self, *a, **kw) -> Floor:
        f = Floor(*a, **kw)
        self.floors.append(f)
        return f

    def add_zone(self, name, x0, x1, z0, z1, **kw) -> Zone:
        z = Zone(name, min(x0, x1), max(x0, x1), min(z0, z1), max(z0, z1), **kw)
        self.zones.append(z)
        return z

    # ------------------------------------------------------------------
    def nearby(self, x0, x1, z0, z1):
        seen = set()
        for c in self._cells(x0, x1, z0, z1):
            for s in self.grid.get(c, ()):
                if id(s) not in seen:
                    seen.add(id(s))
                    yield s

    def ground(self, x, z, y_now=0.0, step=0.55):
        """Walkable height under (x,z) reachable from y_now; returns (height, surface)."""
        best, surf = 0.0, None
        for f in self.floors:
            if f.enabled and f.x0 <= x <= f.x1 and f.z0 <= z <= f.z1:
                h = f.height(x, z)
                if h <= y_now + step and h >= best:
                    best, surf = h, f.surface
        return best, surf

    def zones_at(self, x, z, y=0.0):
        return [zn.name for zn in self.zones if zn.contains(x, z, y)]

    def in_zone(self, name, x, z, y=0.0):
        for zn in self.zones:
            if zn.name == name and zn.contains(x, z, y):
                return True
        return False

    def zone(self, name):
        for zn in self.zones:
            if zn.name == name:
                return zn
        return None

    # ------------------------------------------------------------------
    def resolve(self, x, z, r, y=0.0, h=1.6, ignore=None, iterations=3, include_dynamic=True):
        """Push a circle (x,z,r) spanning [y, y+h] out of solid shapes."""
        for _ in range(iterations):
            moved = False
            for s in self.nearby(x - r, x + r, z - r, z + r):
                if not s.enabled or not s.solid or s is ignore:
                    continue
                if s.y1 <= y + 0.05 or s.y0 >= y + h:
                    continue
                if isinstance(s, Box):
                    px = min(max(x, s.x0), s.x1)
                    pz = min(max(z, s.z0), s.z1)
                    dx, dz = x - px, z - pz
                    d2 = dx * dx + dz * dz
                    if d2 < r * r:
                        if d2 > 1e-10:
                            d = math.sqrt(d2)
                            push = r - d
                            x += dx / d * push
                            z += dz / d * push
                        else:
                            # center inside box: push out through nearest side
                            opts = [(x - s.x0 + r, -1, 0), (s.x1 - x + r, 1, 0), (z - s.z0 + r, 0, -1), (s.z1 - z + r, 0, 1)]
                            dist, sx, sz = min(opts)
                            x += sx * dist
                            z += sz * dist
                        moved = True
                else:
                    dx, dz = x - s.x, z - s.z
                    d2 = dx * dx + dz * dz
                    rr = r + s.r
                    if d2 < rr * rr:
                        d = math.sqrt(d2) if d2 > 1e-10 else 1e-5
                        push = rr - d
                        if d2 <= 1e-10:
                            dx, dz = 1.0, 0.0
                        x += dx / d * push
                        z += dz / d * push
                        moved = True
            if include_dynamic:
                for s in self.dynamic:
                    if not s.enabled or not s.solid or s is ignore or s.owner is ignore:
                        continue
                    if s.y1 <= y + 0.05 or s.y0 >= y + h:
                        continue
                    dx, dz = x - s.x, z - s.z
                    d2 = dx * dx + dz * dz
                    rr = r + s.r
                    if d2 < rr * rr:
                        d = math.sqrt(d2) if d2 > 1e-10 else 1e-5
                        if d2 <= 1e-10:
                            dx, dz = 1.0, 0.0
                        push = (rr - d) * 0.6
                        x += dx / d * push
                        z += dz / d * push
                        moved = True
            if not moved:
                break
        return x, z

    def move(self, x, z, dx, dz, r, y=0.0, h=1.6, ignore=None, include_dynamic=True):
        dist = math.hypot(dx, dz)
        steps = max(1, int(dist / (r * 0.5)) + 1)
        sx, sz = dx / steps, dz / steps
        for _ in range(steps):
            x, z = self.resolve(x + sx, z + sz, r, y, h, ignore, include_dynamic=include_dynamic)
        return x, z

    def blocked_at(self, x, z, r, y=0.0, h=1.6):
        for s in self.nearby(x - r, x + r, z - r, z + r):
            if not s.enabled or not s.solid or s.y1 <= y + 0.05 or s.y0 >= y + h:
                continue
            if isinstance(s, Box):
                px = min(max(x, s.x0), s.x1)
                pz = min(max(z, s.z0), s.z1)
                if (x - px) ** 2 + (z - pz) ** 2 < r * r:
                    return True
            else:
                if (x - s.x) ** 2 + (z - s.z) ** 2 < (r + s.r) ** 2:
                    return True
        return False

    # ------------------------------------------------------------------
    @staticmethod
    def _seg_box(p0, p1, b: Box):
        """Slab test: does segment p0->p1 (3D) hit box b? returns t or None."""
        tmin, tmax = 0.0, 1.0
        for a, lo, hi in ((0, b.x0, b.x1), (1, b.y0, b.y1), (2, b.z0, b.z1)):
            d = p1[a] - p0[a]
            if abs(d) < 1e-9:
                if p0[a] < lo or p0[a] > hi:
                    return None
            else:
                t1 = (lo - p0[a]) / d
                t2 = (hi - p0[a]) / d
                if t1 > t2:
                    t1, t2 = t2, t1
                tmin = max(tmin, t1)
                tmax = min(tmax, t2)
                if tmin > tmax:
                    return None
        return tmin

    @staticmethod
    def _seg_circle(p0, p1, c: Circle):
        x0, z0 = p0[0] - c.x, p0[2] - c.z
        dx, dz = p1[0] - p0[0], p1[2] - p0[2]
        a = dx * dx + dz * dz
        if a < 1e-12:
            return None
        b = 2 * (x0 * dx + z0 * dz)
        cc = x0 * x0 + z0 * z0 - c.r * c.r
        disc = b * b - 4 * a * cc
        if disc < 0:
            return None
        sq = math.sqrt(disc)
        t = (-b - sq) / (2 * a)
        if t < 0:
            t = (-b + sq) / (2 * a)
            if cc < 0:
                t = 0.0
        if t < 0 or t > 1:
            return None
        y = p0[1] + (p1[1] - p0[1]) * t
        if c.y0 <= y <= c.y1:
            return t
        return None

    def raycast(self, p0, p1, ignore=(), sight_only=True, include_dynamic=False):
        """First hit t in [0,1] along p0->p1, or None."""
        x0, x1 = min(p0[0], p1[0]), max(p0[0], p1[0])
        z0, z1 = min(p0[2], p1[2]), max(p0[2], p1[2])
        best = None
        for s in self.nearby(x0, x1, z0, z1):
            if not s.enabled or s in ignore:
                continue
            if sight_only and not s.sight:
                continue
            if not sight_only and not s.solid:
                continue
            t = self._seg_box(p0, p1, s) if isinstance(s, Box) else self._seg_circle(p0, p1, s)
            if t is not None and (best is None or t < best):
                best = t
        if include_dynamic:
            for s in self.dynamic:
                if not s.enabled or s in ignore or s.owner in ignore or not s.sight:
                    continue
                t = self._seg_circle(p0, p1, s)
                if t is not None and (best is None or t < best):
                    best = t
        return best

    def line_of_sight(self, p0, p1, ignore=(), include_dynamic=True):
        return self.raycast(p0, p1, ignore, sight_only=True, include_dynamic=include_dynamic) is None
