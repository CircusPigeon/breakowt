"""Moo-dals: achievements for the things a cow does when nobody's making her escape.

Progress lives in its own file next to the saves (moodals.json), so it carries across
playthroughs and survives reloading a checkpoint. Moo-dals are the only source of Golden
Clovers, Epicowrus' currency: your purse is their total payout less what a run has spent.
"""
from __future__ import annotations

import copy
import math
import time

from .engine.assets import SAVE_DIR
from .engine.persistence import pending_purchases, read_json, record_purchase, write_json
from .world import OAK, in_pond

# id, name, how to earn it, clover reward, hidden until earned
MOODALS = [
    ("moo_50", "Moo-sical Talent", "Moo 50 times.", 1, False),
    ("hop_30", "Olympic Hopeful", "Hop 30 times. Cows can't jump. You hop anyway.", 1, False),
    ("gallop_2k", "Marathon Moo-ver", "Gallop 2 km in total.", 2, False),
    ("trip_5", "Gravity's Little Helper", "Watch Chuck fall over 5 times.", 2, False),
    ("knock_all", "Bull in a China Shop", "Knock over every bucket stack, milk can, feed bin and trash can.", 3, False),
    ("tidy_3", "Job Security", "Make Chuck pick up after you 3 times.", 1, False),
    ("bonk", "Sticks and Stones", "Hit Chuck with something you threw.", 2, False),
    ("herd_20", "Census Taker", "Chat with 20 different cows in the herd.", 2, False),
    ("choir_5", "Choir Practice", "Moo in the pasture and get the herd to moo back, 5 times.", 1, False),
    ("frogs", "Frog Chorus", "Moo at the pond after dark and get an answer.", 1, True),
    ("owl", "Who Goes There", "Trade hoots with the owl at night.", 1, True),
    ("birds_10", "Bird Brain", "Scatter 10 flocks of birds.", 1, False),
    ("wade_60", "Pond Life", "Spend a full minute wading in the pond.", 1, False),
    ("ghost_day", "Ghost Cow", "Get through a whole day (Tuesday on) without being caught.", 2, False),
    ("caught_10", "Frequent Flyer", "Get marched back to the pasture 10 times. Winning, at something.", 1, False),
    ("mirror", "Know Thyself", "Look in the bathroom mirror.", 1, True),
    ("cookbook", "Required Reading", "Read '101 Ways to Cook a Cow'.", 1, True),
    ("trough_5", "Hydration Station", "Drink from the trough 5 times.", 1, False),
    ("tourist", "Tourist", "Tour the oak, pond, shed, loft, coop, house, plant and main gate.", 2, False),
    ("dale_3", "Master of Disguise", "Get mistaken for Dale three times.", 2, True),
    ("personal_space", "Personal Space", "Stay within 4 m of Chuck for 10 s where you shouldn't be, unnoticed.", 2, False),
    ("scarecrow", "Take That, Cardboard Chuck", "Headbutt Cardboard Chuck.", 1, False),
    ("ledger", "Due Diligence", "Read the intake ledger at Happy Acres.", 2, True),
    ("deer", "Do Not Shake", "Get the ammo tin down from Chuck's deer stand.", 1, True),
    ("all", "Moo-dal of Honor", "Earn every other Moo-dal.", 5, False),
]
BY_ID = {m[0]: m for m in MOODALS}

# counters with a goal
GOALS = {
    "moo_50": ("moos", 50), "hop_30": ("hops", 30), "gallop_2k": ("gallop_m", 2000), "trip_5": ("chuck_trips", 5),
    "tidy_3": ("tidies", 3), "choir_5": ("choir", 5), "birds_10": ("flocks", 10), "wade_60": ("wade_s", 60),
    "caught_10": ("caught", 10), "trough_5": ("trough", 5), "dale_3": ("dale", 3),
}
# sets with a goal: (set name, size)
SET_GOALS = {"herd_20": ("herd_talked", 20)}
TOURIST = ("oak", "pond", "shed", "loft", "coop", "house", "processing", "gate")

RANKS = [(0, "Steak-Adjacent"), (4, "Pasture Regular"), (9, "Barnyard Legend"), (15, "Moo-ster of the Universe"),
         (len(MOODALS), "Moo-dal of Honor")]


class Moodals:
    def __init__(self, g):
        self.g = g
        self.path = SAVE_DIR / "moodals.json"
        self.data = {"unlocked": {}, "counters": {}, "sets": {}, "purse": {}}
        self._dirty = False
        self._save_t = 0.0
        self._near_chuck = 0.0
        self._zone_t = 0.0
        self.load()

    # ------------------------------------------------------------------
    def load(self):
        try:
            d = read_json(self.path) or {}
            for k in ("unlocked", "counters", "sets", "purse"):
                if isinstance(d.get(k), dict):
                    self.data[k] = d[k]
        except (OSError, ValueError):
            pass

    def save(self):
        try:
            write_json(self.path, self.data)
            self._dirty = False
            return True
        except OSError as error:
            self._dirty = True
            self.g.save_failed("Moo-dals and clovers", error)
            return False

    def unlocked(self, mid):
        return mid in self.data["unlocked"]

    def count_unlocked(self):
        return sum(1 for m in self.data["unlocked"] if m in BY_ID)

    def purse(self):
        """Golden Clovers to spend: what your Moo-dals have paid out, plus any you've found, less what
        Epicowrus has had off you. All of it lives in the profile, so it carries across playthroughs."""
        pu = self.data["purse"]
        return max(0, self.total_reward() + int(pu.get("found", 0)) - int(pu.get("spent", 0)))

    def spend(self, n, key=None, keep=True, run_id=None, day=None):
        # The receipt and the debit share one atomic write. A failed write never
        # charges the purse or grants merchandise in memory.
        before = copy.deepcopy(self.data)
        receipt = record_purchase(self.data, n, key, keep, run_id, day)
        if not self.save():
            self.data = before
            return False
        return receipt or True

    def pending_purchases(self, flags):
        return pending_purchases(self.data, flags)

    def owned(self):
        return list(self.data["purse"].get("owned", []))

    def add_perk(self, name):
        """A favour's reward that stays yours in later playthroughs (the hiding-spot map, the horseshoe)."""
        perks = self.data["purse"].setdefault("perks", [])
        if name not in perks:
            perks.append(name)
            self.save()

    def perks(self):
        return list(self.data["purse"].get("perks", []))

    def find_clover(self, cid):
        pu = self.data["purse"]
        got = pu.setdefault("clovers", [])
        if cid in got:
            return False
        got.append(cid)
        pu["found"] = int(pu.get("found", 0)) + 1
        self.save()
        return True

    def clover_found(self, cid):
        return cid in self.data["purse"].get("clovers", [])

    def total_reward(self):
        """Golden Clovers every Moo-dal you hold has paid out (they're the only way to get any)."""
        return sum(BY_ID[m][3] for m in self.data["unlocked"] if m in BY_ID)

    def rank(self):
        n = self.count_unlocked()
        name = RANKS[0][1]
        for need, r in RANKS:
            if n >= need:
                name = r
        return name

    def progress(self, mid):
        """(have, need) for Moo-dals with a count, else None."""
        if mid in GOALS:
            key, need = GOALS[mid]
            return min(int(self.data["counters"].get(key, 0)), need), need
        if mid in SET_GOALS:
            key, need = SET_GOALS[mid]
            return min(len(self.data["sets"].get(key, [])), need), need
        if mid == "knock_all":
            return len(self.data["sets"].get("knocked", [])), max(1, len(self.g.knockables))
        if mid == "tourist":
            return len(self.data["sets"].get("visited", [])), len(TOURIST)
        if mid == "all":
            return min(self.count_unlocked(), len(MOODALS) - 1), len(MOODALS) - 1
        return None

    # ------------------------------------------------------------------
    def count(self, key, n=1):
        c = self.data["counters"]
        c[key] = c.get(key, 0) + n
        self._dirty = True
        for mid, (k, need) in GOALS.items():
            if k == key and c[key] >= need:
                self.unlock(mid)

    def add(self, set_name, item):
        s = self.data["sets"].setdefault(set_name, [])
        if item in s:
            return False
        s.append(item)
        self._dirty = True
        for mid, (k, need) in SET_GOALS.items():
            if k == set_name and len(s) >= need:
                self.unlock(mid)
        if set_name == "knocked" and len(s) >= len(self.g.knockables) > 0:
            self.unlock("knock_all")
        if set_name == "visited" and all(t in s for t in TOURIST):
            self.unlock("tourist")
        return True

    def unlock(self, mid):
        if mid not in BY_ID or self.unlocked(mid):
            return False
        self.data["unlocked"][mid] = int(time.time())
        self._dirty = True
        _, name, desc, reward, _ = BY_ID[mid]
        g = self.g
        if reward:
            g.refresh_hotbar()      # the clover count is worked out from the Moo-dals: see Game.clovers
        g.audio.play("moodal", vol=0.9)
        g.ui.moodal_banner(name, desc, reward)
        self.save()
        if mid != "all" and self.count_unlocked() >= len(MOODALS) - 1:
            self.unlock("all")
        return True

    # ------------------------------------------------------------------
    def on_event(self, name, **kw):
        g = self.g
        if name in ("moo", "hop", "chuck_trip", "caught", "dale", "tidy", "flock", "choir"):
            key = {"moo": "moos", "hop": "hops", "chuck_trip": "chuck_trips", "caught": "caught",
                   "dale": "dale", "tidy": "tidies", "flock": "flocks", "choir": "choir"}[name]
            self.count(key)
        elif name == "knock":
            self.add("knocked", kw.get("key"))
        elif name == "herd_talk":
            self.add("herd_talked", kw.get("idx"))
        elif name == "interact":
            key = kw.get("key", "")
            if key == "mirror":
                self.unlock("mirror")
            elif key == "cookbook":
                self.unlock("cookbook")
            elif key == "trough":
                self.count("trough")
        elif name in ("bonk", "frogs", "owl", "scarecrow", "ledger", "deer"):
            self.unlock(name)
        elif name == "day_start":
            n = kw.get("day", 0)
            prev = getattr(self, "_day_prev", None)
            caught = g.stats.get("caught", 0)
            if prev is not None and n == prev[0] + 1 and prev[0] >= 2 and caught == prev[1]:
                self.unlock("ghost_day")
            self._day_prev = (n, caught)

    def update(self, dt):
        g = self.g
        p = g.player
        if g.state == "play" and g.controls_enabled():
            if p.galloping and p.speed > 1:
                self.data["counters"]["gallop_m"] = self.data["counters"].get("gallop_m", 0) + p.speed * dt
                self._dirty = True
                if self.data["counters"]["gallop_m"] >= 2000:
                    self.unlock("gallop_2k")
            if p.in_water:
                self.data["counters"]["wade_s"] = self.data["counters"].get("wade_s", 0) + dt
                self._dirty = True
                if self.data["counters"]["wade_s"] >= 60:
                    self.unlock("wade_60")
            self._zone_t -= dt
            if self._zone_t <= 0:
                self._zone_t = 0.5
                self._check_places()
            f = g.farmer
            close = (f.visible and math.hypot(f.x - p.x, f.z - p.z) < 4.0 and g.player_restricted()
                     and f.susp < 0.25 and f.state in ("routine", "investigate") and f.detect)
            self._near_chuck = self._near_chuck + dt if close else 0.0
            if self._near_chuck >= 10.0:
                self.unlock("personal_space")
        self._save_t -= dt
        if self._dirty and self._save_t <= 0:
            self._save_t = 10.0
            self.save()

    def _check_places(self):
        g = self.g
        p = g.player
        ph = g.phys
        spots = {
            "oak": math.hypot(p.x - OAK[0], p.z - OAK[1]) < 6.0,
            "pond": in_pond(p.x, p.z),
            "shed": ph.in_zone("shed", p.x, p.z),
            "loft": ph.in_zone("loft", p.x, p.z, p.y),
            "coop": ph.in_zone("coop", p.x, p.z),
            "house": ph.in_zone("house", p.x, p.z),
            "processing": math.hypot(p.x - 52, p.z + 41) < 7.0,
            "gate": ph.in_zone("gate_area", p.x, p.z),
        }
        for k, inside in spots.items():
            if inside:
                self.add("visited", k)
