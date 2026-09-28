"""Batching mesh builder.

Collects many primitives (boxes, cylinders, spheres...) into one numpy-backed
Ursina Mesh so the whole farm renders in a handful of draw calls.

Conventions (match Ursina/Panda 'y-up-left'): x right, y up, z forward.
Yaw rotates +z toward +x: forward(yaw) = (sin yaw, 0, cos yaw).
"""
from __future__ import annotations

import math

import numpy as np
from ursina import Mesh


def rot_matrix(rx=0.0, ry=0.0, rz=0.0) -> np.ndarray:
    """Rotation matrix for Ursina-style Euler angles (degrees).

    Applied as: roll (z), then pitch (x), then yaw (y). Only yaw is used for
    gameplay-critical geometry; pitch/roll are for decoration.
    """
    ax, ay, az = math.radians(rx), math.radians(ry), math.radians(rz)
    cy, sy = math.cos(ay), math.sin(ay)
    # yaw: (0,0,1) -> (sin, 0, cos)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    cx, sx = math.cos(ax), math.sin(ax)
    # pitch: positive tips +z downward (-y), like looking down
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    cz, sz = math.cos(az), math.sin(az)
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Ry @ Rx @ Rz


# unit cube faces: (normal, corner order) — corners given CCW when seen from outside
_FACES = [
    ((0, 0, 1), [(-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)]),      # front (+z)
    ((0, 0, -1), [(1, -1, -1), (-1, -1, -1), (-1, 1, -1), (1, 1, -1)]),  # back (-z)
    ((1, 0, 0), [(1, -1, 1), (1, -1, -1), (1, 1, -1), (1, 1, 1)]),       # right (+x)
    ((-1, 0, 0), [(-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)]),  # left (-x)
    ((0, 1, 0), [(-1, 1, 1), (1, 1, 1), (1, 1, -1), (-1, 1, -1)]),       # top (+y)
    ((0, -1, 0), [(-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)]),  # bottom (-y)
]


class MeshBuilder:
    def __init__(self):
        self.v: list[np.ndarray] = []
        self.n: list[np.ndarray] = []
        self.uv: list[np.ndarray] = []
        self.c: list[np.ndarray] = []
        self.t: list[np.ndarray] = []
        self.count = 0
        # a mirrored winding flag: Panda's y-up-left system flips handedness
        self.flip = True

    # ------------------------------------------------------------------
    def _push(self, verts, norms, uvs, color, tris):
        verts = np.asarray(verts, dtype=np.float32).reshape(-1, 3)
        norms = np.asarray(norms, dtype=np.float32).reshape(-1, 3)
        uvs = np.asarray(uvs, dtype=np.float32).reshape(-1, 2)
        n = len(verts)
        if isinstance(color, np.ndarray) and color.ndim == 2:
            cols = color.astype(np.float32)
        else:
            c = tuple(color) if color is not None else (1, 1, 1, 1)
            if len(c) == 3:
                c = (*c, 1.0)
            cols = np.tile(np.array(c, dtype=np.float32), (n, 1))
        tris = np.asarray(tris, dtype=np.uint32).reshape(-1, 3)
        if self.flip:
            tris = tris[:, ::-1]
        self.v.append(verts)
        self.n.append(norms)
        self.uv.append(uvs)
        self.c.append(cols)
        self.t.append(tris + self.count)
        self.count += n

    @staticmethod
    def _xf(points, pos, R, scale=None):
        p = np.asarray(points, dtype=np.float64)
        if scale is not None:
            p = p * np.asarray(scale)
        return p @ R.T + np.asarray(pos)

    # ------------------------------------------------------------------
    def box(self, pos, size, color=(1, 1, 1, 1), rot=(0, 0, 0), uv_density=0.5, faces=None,
            uv_mode="local", uv_rect=None):
        """Axis box centered at pos with full size (w,h,d), rotated by rot (rx,ry,rz).

        uv_density: texture repeats per meter. uv_rect: map the whole texture onto
        each face instead (e.g., for signs)."""
        R = rot_matrix(*rot) if isinstance(rot, (tuple, list)) else rot_matrix(0, rot, 0)
        hw, hh, hd = size[0] / 2, size[1] / 2, size[2] / 2
        verts, norms, uvs, tris = [], [], [], []
        k = 0
        for fi, (nrm, corners) in enumerate(_FACES):
            if faces is not None and fi not in faces:
                continue
            cs = np.array(corners, dtype=np.float64) * np.array([hw, hh, hd])
            wv = self._xf(cs, pos, R)
            nv = (R @ np.array(nrm, dtype=np.float64))
            # face-local 2D coordinates
            if abs(nrm[1]) > 0.5:  # top/bottom: use x,z
                uu, vv = cs[:, 0], cs[:, 2]
            elif abs(nrm[0]) > 0.5:  # left/right: z,y
                uu, vv = cs[:, 2] * (-nrm[0]), cs[:, 1]
            else:  # front/back: x,y
                uu, vv = cs[:, 0] * nrm[2], cs[:, 1]
            if uv_rect is not None:
                u0, v0, u1, v1 = uv_rect
                span_u = (uu.max() - uu.min()) or 1
                span_v = (vv.max() - vv.min()) or 1
                fu = (uu - uu.min()) / span_u
                fv = (vv - vv.min()) / span_v
                uvf = np.stack([u0 + fu * (u1 - u0), v0 + fv * (v1 - v0)], axis=1)
            else:
                if uv_mode == "world" and abs(nrm[1]) > 0.5:
                    uu, vv = wv[:, 0], wv[:, 2]
                elif uv_mode == "world":
                    base = np.array(pos, dtype=np.float64)
                    uu = uu + (base[0] if abs(nrm[2]) > 0.5 else base[2])
                    vv = vv + base[1]
                uvf = np.stack([uu * uv_density, vv * uv_density], axis=1)
            verts.append(wv)
            norms.append(np.tile(nv, (4, 1)))
            uvs.append(uvf)
            tris += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
            k += 4
        if k:
            self._push(np.concatenate(verts), np.concatenate(norms), np.concatenate(uvs), color, tris)
        return self

    def quad(self, pos, size, color=(1, 1, 1, 1), rot=(0, 0, 0), uv_rect=(0, 0, 1, 1), double=False):
        """A vertical quad facing -z before rotation (like a sign facing the viewer at -z)."""
        R = rot_matrix(*rot)
        hw, hh = size[0] / 2, size[1] / 2
        u0, v0, u1, v1 = uv_rect
        uvs = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
        cs = np.array([(-hw, -hh, 0), (hw, -hh, 0), (hw, hh, 0), (-hw, hh, 0)], dtype=np.float64)
        wv = self._xf(cs, pos, R)
        nv = R @ np.array([0, 0, -1.0])
        self._push(wv, np.tile(nv, (4, 1)), uvs, color, [(0, 2, 1), (0, 3, 2)])
        if double:
            self._push(wv, np.tile(-nv, (4, 1)), uvs, color, [(0, 1, 2), (0, 2, 3)])
        return self

    def ground(self, x0, z0, x1, z1, y=0.0, color=(1, 1, 1, 1), uv_density=0.25, segs=1):
        verts, norms, uvs, tris = [], [], [], []
        xs = np.linspace(x0, x1, segs + 1)
        zs = np.linspace(z0, z1, segs + 1)
        idx = {}
        k = 0
        for i, x in enumerate(xs):
            for j, z in enumerate(zs):
                verts.append((x, y, z))
                norms.append((0, 1, 0))
                uvs.append((x * uv_density, z * uv_density))
                idx[(i, j)] = k
                k += 1
        for i in range(segs):
            for j in range(segs):
                a, b, c, d = idx[(i, j)], idx[(i + 1, j)], idx[(i + 1, j + 1)], idx[(i, j + 1)]
                tris += [(a, d, c), (a, c, b)]
        self._push(verts, norms, uvs, color, tris)
        return self

    def heightfield(self, x0, z0, x1, z1, fn, res=64, color_fn=None, uv_density=0.1):
        xs = np.linspace(x0, x1, res + 1)
        zs = np.linspace(z0, z1, res + 1)
        X, Z = np.meshgrid(xs, zs, indexing="ij")
        Y = np.vectorize(fn)(X, Z)
        # normals via finite differences
        dx = (x1 - x0) / res
        dz = (z1 - z0) / res
        gx = np.gradient(Y, dx, axis=0)
        gz = np.gradient(Y, dz, axis=1)
        N = np.stack([-gx, np.ones_like(Y), -gz], axis=-1)
        N /= np.linalg.norm(N, axis=-1, keepdims=True)
        verts = np.stack([X, Y, Z], axis=-1).reshape(-1, 3)
        norms = N.reshape(-1, 3)
        uvs = np.stack([X.ravel() * uv_density, Z.ravel() * uv_density], axis=1)
        if color_fn is not None:
            cols = np.array([color_fn(x, y, z) for x, y, z in verts], dtype=np.float32)
        else:
            cols = np.ones((len(verts), 4), dtype=np.float32)
        tris = []
        n = res + 1
        for i in range(res):
            for j in range(res):
                a = i * n + j
                b = (i + 1) * n + j
                c = (i + 1) * n + j + 1
                d = i * n + j + 1
                tris += [(a, d, c), (a, c, b)]
        self._push(verts, norms, uvs, cols, tris)
        return self

    def cylinder(self, pos, radius, height, color=(1, 1, 1, 1), segs=10, rot=(0, 0, 0), caps=True,
                 radius_top=None, uv_density=0.5, smooth=True):
        """Cylinder standing on pos (pos is the bottom center before rotation)."""
        R = rot_matrix(*rot)
        rt = radius if radius_top is None else radius_top
        verts, norms, uvs, tris = [], [], [], []
        k = 0
        circ = 2 * math.pi * max(radius, rt)
        slope = (radius - rt) / max(height, 1e-6)
        for i in range(segs):
            a0 = 2 * math.pi * i / segs
            a1 = 2 * math.pi * (i + 1) / segs
            p = [
                (math.sin(a0) * radius, 0, math.cos(a0) * radius),
                (math.sin(a1) * radius, 0, math.cos(a1) * radius),
                (math.sin(a1) * rt, height, math.cos(a1) * rt),
                (math.sin(a0) * rt, height, math.cos(a0) * rt),
            ]
            if smooth:
                ns = [(math.sin(a0), slope, math.cos(a0)), (math.sin(a1), slope, math.cos(a1)),
                      (math.sin(a1), slope, math.cos(a1)), (math.sin(a0), slope, math.cos(a0))]
            else:
                am = (a0 + a1) / 2
                ns = [(math.sin(am), slope, math.cos(am))] * 4
            ns = [np.array(q) / np.linalg.norm(q) for q in ns]
            u0 = i / segs * circ * uv_density
            u1 = (i + 1) / segs * circ * uv_density
            verts += list(self._xf(p, pos, R))
            norms += [R @ q for q in ns]
            uvs += [(u0, 0), (u1, 0), (u1, height * uv_density), (u0, height * uv_density)]
            # outward-facing: CCW seen from outside
            tris += [(k, k + 1, k + 2), (k, k + 2, k + 3)]
            k += 4
        if caps:
            for y, r, ny in ((height, rt, 1), (0, radius, -1)):
                if r <= 0:
                    continue
                center = k
                verts.append(self._xf([(0, y, 0)], pos, R)[0])
                norms.append(R @ np.array([0, ny, 0.0]))
                uvs.append((0.5, 0.5))
                k += 1
                for i in range(segs + 1):
                    a = 2 * math.pi * i / segs
                    verts.append(self._xf([(math.sin(a) * r, y, math.cos(a) * r)], pos, R)[0])
                    norms.append(R @ np.array([0, ny, 0.0]))
                    uvs.append((0.5 + math.sin(a) * 0.5, 0.5 + math.cos(a) * 0.5))
                    k += 1
                for i in range(segs):
                    a, b = center + 1 + i, center + 2 + i
                    tris.append((center, b, a) if ny > 0 else (center, a, b))
        self._push(verts, norms, uvs, color, tris)
        return self

    def sphere(self, pos, radius, color=(1, 1, 1, 1), segs=10, rings=7, scale=(1, 1, 1), rot=(0, 0, 0),
               uv_density=None):
        R = rot_matrix(*rot)
        sc = np.array(scale, dtype=np.float64) * radius
        verts, norms, uvs, tris = [], [], [], []
        for r in range(rings + 1):
            phi = math.pi * r / rings
            for s in range(segs + 1):
                th = 2 * math.pi * s / segs
                p = np.array([math.sin(phi) * math.sin(th), math.cos(phi), math.sin(phi) * math.cos(th)])
                verts.append(p * sc)
                nn = p / np.where(sc == 0, 1, sc)
                nn = nn / (np.linalg.norm(nn) + 1e-9)
                norms.append(R @ nn)
                if uv_density:
                    uvs.append((s / segs * 2 * math.pi * radius * uv_density, r / rings * math.pi * radius * uv_density))
                else:
                    uvs.append((s / segs, 1 - r / rings))
        verts = self._xf(verts, pos, R)
        w = segs + 1
        for r in range(rings):
            for s in range(segs):
                a = r * w + s
                b = (r + 1) * w + s
                tris += [(a, b, b + 1), (a, b + 1, a + 1)]
        self._push(verts, norms, uvs, color, tris)
        return self

    def poly(self, points, color=(1, 1, 1, 1), uv_density=0.5, double=True):
        """Convex planar polygon (list of 3D points), fan-triangulated."""
        p = np.asarray(points, dtype=np.float64)
        nrm = np.cross(p[1] - p[0], p[2] - p[0])
        nrm = nrm / (np.linalg.norm(nrm) + 1e-9)
        # uv: project on the two largest axes
        ax = np.argsort(np.abs(nrm))[:2]
        uvs = p[:, sorted(ax)] * uv_density
        tris = [(0, i + 1, i + 2) for i in range(len(p) - 2)]
        self._push(p, np.tile(nrm, (len(p), 1)), uvs, color, tris)
        if double:
            self._push(p, np.tile(-nrm, (len(p), 1)), uvs, color, [(0, i + 2, i + 1) for i in range(len(p) - 2)])
        return self

    def disk(self, center, rx, rz, color=(1, 1, 1, 1), segs=24, uv_density=0.25, uv_rect=None):
        """Flat horizontal ellipse facing up."""
        cx, cy, cz = center
        verts = [(cx, cy, cz)]
        uvs = []
        for i in range(segs + 1):
            a = 2 * math.pi * i / segs
            verts.append((cx + math.sin(a) * rx, cy, cz + math.cos(a) * rz))
        for x, y, z in verts:
            if uv_rect:
                u0, v0, u1, v1 = uv_rect
                uvs.append((u0 + (x - cx + rx) / (2 * rx) * (u1 - u0), v0 + (z - cz + rz) / (2 * rz) * (v1 - v0)))
            else:
                uvs.append((x * uv_density, z * uv_density))
        tris = [(0, i + 1, i + 2) for i in range(segs)]
        self._push(verts, [(0, 1, 0)] * len(verts), uvs, color, tris)
        return self

    def cone(self, pos, radius, height, color=(1, 1, 1, 1), segs=8, rot=(0, 0, 0)):
        return self.cylinder(pos, radius, height, color, segs, rot, caps=True, radius_top=0.0)

    def extend(self, other: "MeshBuilder"):
        ob = 0
        for v, n, uv, c, t in zip(other.v, other.n, other.uv, other.c, other.t):
            base = t - ob
            ob += len(v)
            self.v.append(v)
            self.n.append(n)
            self.uv.append(uv)
            self.c.append(c)
            self.t.append(base + self.count)
            self.count += len(v)
        return self

    # ------------------------------------------------------------------
    def build(self) -> Mesh | None:
        if not self.v:
            return None
        v = np.ascontiguousarray(np.concatenate(self.v).astype(np.float32).ravel())
        n = np.ascontiguousarray(np.concatenate(self.n).astype(np.float32).ravel())
        uv = np.ascontiguousarray(np.concatenate(self.uv).astype(np.float32).ravel())
        c = np.ascontiguousarray(np.concatenate(self.c).astype(np.float32).ravel())
        t = np.ascontiguousarray(np.concatenate(self.t).astype(np.uint32).ravel())
        return Mesh(vertices=v, triangles=t, uvs=uv, normals=n, colors=c, static=True)
