"""Look-at interaction targets."""
from __future__ import annotations

import math


class Handler:
    __slots__ = ("prompt", "action", "cond", "scope")

    def __init__(self, prompt, action, cond=None, scope="step"):
        self.prompt = prompt
        self.action = action
        self.cond = cond
        self.scope = scope


class Interactable:
    def __init__(self, key, pos, radius=0.7, name="", text=None, prompt="Examine", reach=2.6,
                 entity=None, enabled=True, follow=None, visible_cond=None):
        self.key = key
        self.pos = tuple(pos)
        self.radius = radius
        self.name = name or key.replace("_", " ").title()
        self.text = text
        self.prompt = prompt
        self.reach = reach
        self.entity = entity
        self.enabled = enabled
        self.follow = follow
        self.handlers: list[Handler] = []
        self.on_rock = None       # callable(game, hit_pos) when a thrown rock hits
        self.on_headbutt = None   # callable(game)
        self.visible_cond = visible_cond
        self.text_i = 0

    def world_pos(self):
        if self.follow is not None:
            try:
                return self.follow()
            except Exception:
                return self.pos
        return self.pos

    def active_handler(self, g):
        for h in reversed(self.handlers):
            try:
                if h.cond is None or h.cond(g):
                    return h
            except Exception:
                continue
        return None


class InteractionSystem:
    def __init__(self, game):
        self.g = game
        self.items: dict[str, Interactable] = {}

    def add(self, ia: Interactable) -> Interactable:
        self.items[ia.key] = ia
        return ia

    def remove(self, key):
        self.items.pop(key, None)

    def get(self, key):
        return self.items.get(key)

    def clear_scope(self, scope):
        for ia in self.items.values():
            ia.handlers = [h for h in ia.handlers if h.scope != scope]

    def find_target(self, eye, fwd):
        """Best interactable the player is looking at."""
        best, best_score = None, 1e9
        ex, ey, ez = eye
        fx, fy, fz = fwd
        phys = self.g.phys
        for ia in self.items.values():
            if not ia.enabled:
                continue
            if ia.visible_cond is not None and not ia.visible_cond(self.g):
                continue
            px, py, pz = ia.world_pos()
            dx, dy, dz = px - ex, py - ey, pz - ez
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist > ia.reach + ia.radius or dist < 1e-4:
                continue
            cosang = (dx * fx + dy * fy + dz * fz) / dist
            if cosang <= 0:
                continue
            ang = math.degrees(math.acos(max(-1.0, min(1.0, cosang))))
            allow = math.degrees(math.atan2(ia.radius, max(dist, 0.3))) + 7
            if ang > allow:
                continue
            # don't interact through walls: stop the ray just short of the target
            back = max(0.0, dist - ia.radius - 0.2) / dist
            if back > 0.05:
                end = (ex + dx * back, ey + dy * back, ez + dz * back)
                if not phys.line_of_sight(eye, end, include_dynamic=False):
                    continue
            score = ang / allow + dist * 0.05
            if score < best_score:
                best, best_score = ia, score
        return best
