"""Item catalog and inventory."""
from __future__ import annotations

# key: (label, description, icon, stackable, throwable, holdable)
# Every item earns its keep. Holdable ones go on the hotbar (in your mouth); the rest (keys, things a
# friend asks for, things that work on their own) live in the journal and get used automatically.
ITEMS = {
    "page": ("Soggy Planner Page", "Chuck's week, in his own handwriting. You're on it. Sunday. Next to 'buy charcoal'.",
             "page", False, False, True),
    "pencil": ("Chuck's Pencil", "Stolen mid-headcount. Chewed at both ends. Archimoodes has been eyeing it: you can't "
               "finish a proof in mud.", "pencil", False, False, False),
    "rock": ("Rock", "A good throwing rock. [R] to throw. Makes noise where it lands.", "rock", True, True, True),
    "pliers": ("Pliers", "Snipped your bell off. Insulated handles, so they're also good for grabbing things that "
               "would very much like to electrocute you.", "pliers", False, False, False),
    "cowbell": ("Your Old Cowbell", "[R] to throw it: anyone listening goes to look where it lands. Pick it up again "
                "after.", "cowbell", False, True, True),
    "radio": ("Chuck's Radio", "Plays one station: Country Songs About Trucks. [Q] sets it down playing. Chuck can't "
              "leave it alone: he'll come and turn it off. Pick it up again after.", "radio", False, False, True),
    "glasses": ("Spare Reading Glasses", "Chuck's backup glasses. +2.5. Somebody nerdy would love these.", "glasses",
                False, False, True),
    "bucket": ("Rusty Bucket", "A rusty bucket. Moogenes wants a home nobody can sell him. He isn't fussy about the size.",
               "bucket", False, False, True),
    "boot": ("Chuck's Rubber Boot", "Size 13. Rubber doesn't conduct electricity. Also: [R] to throw it. It lands "
             "like a dead goose.", "boot", False, True, True),
    "rubber_chicken": ("Rubber Chicken", "Non-conductive. Deeply squeaky. [R] to throw.", "rubber_chicken", False,
                       True, True),
    "tractor_key": ("Tractor Key", "The key to the JOHN STEER. Keychain says 'WORLD'S OKAYEST FARMER'. Works from "
                    "the journal: climb on the tractor and it's in.", "tractor_key", False, False, False),
    "jerrycan": ("Jerry Can (Diesel)", "Full of diesel. The fumes make your eyes water.", "jerrycan", False, False,
                 True),
    "egg": ("Egg", "Fresh. Throwable. Splattery. [R] to throw.", "egg", True, True, True),
    "sparkplug": ("Spark Plug", "The tractor's missing spark plug. It was soaking in vinegar next to Chuck's teeth.",
                  "sparkplug", False, False, True),
    "house_key": ("Spare House Key", "Found inside a garden gnome, as all keys eventually are. Opens the front door.",
                  "house_key", False, False, False),
    "score": ("Archimoodes' Proof", "The Escape Theorem, in pencil on the back of Chuck's planner. Eleven lines. The "
              "last says 'QED', and beside it, very small, '12'. [Q] to read it out: the whole herd starts arguing about step four, loudly, "
              "and Chuck stomps over to the pasture to shut them up.", "score", False, False, True),
    "photo": ("Photo of Big Ajax", "'Me & Big Ajax, Best in Show 2009.' Heifercleitus should have this.", "photo", False,
              False, True),
    "horseshoe": ("Big Ajax's Lucky Horseshoe", "If Chuck catches you, maybe he trips on it instead. Once.",
                  "horseshoe", False, False, False),
    "moustache": ("Fake Moustache", "Wear it with a straw hat and Chuck sees Dale. [Q] to put it on. Don't gallop. "
                  "Dale doesn't gallop. Dale hasn't hurried since 1994.", "moustache", False, False, True),
    "hat": ("Chuck's Spare Straw Hat", "From the wardrobe. Wear with a moustache to become 'Dale'.", "hat", False,
            False, False),
    "coffee": ("Suspiciously Strong Coffee", "Gallop twice as long today. Your heart is doing something new.",
               "coffee", False, False, False),
    "tincan": ("Mysterious Tin Can", "Nothing in it. Rattles anyway. [R] to throw: the loudest thing on the farm. "
               "Epicowrus was right. No refunds.", "tincan", False, True, True),
    "shoes": ("Chuck's Bowling Shoes", "Red and blue, and damp inside. [R] to throw them somewhere Chuck will go "
              "looking.", "shoes", False, True, True),
    "cabinet_key": ("Gun Cabinet Key", "Small and brass. Opens Chuck's gun cabinet: just walk up to it.",
                    "cabinet_key", False, False, False),
    "shotgun": ("Shotgun ('Ol' Bessie')", "Ol' Bessie. [Q] fires, if you've found her any shells. You carry her "
                "very carefully.", "shotgun", False, False, True),
    "shells": ("Shotgun Shells", "Shells for Ol' Bessie. Chuck hid them from himself. [Q] with Bessie fires one.",
               "shells", True, False, False),
    "plank": ("Plank", "A long plank. Three of these could bridge a cattle grid.", "plank", True, False, True),
    "chimes": ("Wind Chimes", "Seashells on strings.", "chimes", False, False, True),
}

# number keys for hotbar slots: 1-9, then 0 for the tenth; past that, the scroll wheel
SLOT_KEYS = "1234567890"


class Inventory:
    def __init__(self, g):
        self.g = g
        self.items: dict[str, int] = {}
        self.order: list[str] = []
        self.sel = 0        # hotbar slot in hand; -1 = nothing (press the selected number again)

    def add(self, key, n=1, silent=False):
        new = key not in self.items
        self.items[key] = self.items.get(key, 0) + n
        if new:
            self.order.append(key)
        if not silent:
            label = ITEMS.get(key, (key,))[0]
            self.g.ui.toast(f"Got: {label}" + (f" x{n}" if n > 1 else ""), ITEMS.get(key, (0, 0, key))[2])
            self.g.audio.play("fanfare", vol=0.55)
        if new and ITEMS.get(key, (0, 0, 0, 0, 0, False))[5]:
            self.select_key(key)
        self.g.refresh_hotbar()

    def remove(self, key, n=1):
        if key not in self.items:
            return
        held = self.selected()
        self.items[key] -= n
        if self.items[key] <= 0:
            del self.items[key]
            self.order.remove(key)
            # keep holding the same item (its slot may have moved); used up the one in your mouth: mouth's empty
            keys = self.hotbar_keys()
            self.sel = keys.index(held) if held in keys else -1
        self.g.refresh_hotbar()

    def has(self, key, n=1):
        return self.items.get(key, 0) >= n

    def count(self, key):
        return self.items.get(key, 0)

    def hotbar_keys(self):
        return [k for k in self.order if ITEMS.get(k, (0, 0, 0, 0, 0, False))[5]]

    def selected(self):
        keys = self.hotbar_keys()
        if not keys or self.sel < 0:
            return None
        self.sel = min(self.sel, len(keys) - 1)
        return keys[self.sel]

    def select_key(self, key):
        keys = self.hotbar_keys()
        if key in keys:
            self.sel = keys.index(key)
            self.g.refresh_hotbar()

    def cycle(self, d):
        keys = self.hotbar_keys()
        if keys:
            if self.sel < 0:
                self.sel = 0 if d > 0 else len(keys) - 1
            else:
                self.sel = (self.sel + d) % len(keys)
            self.g.refresh_hotbar()

    def press_slot(self, i):
        """Number key i (0-based): select that slot, or put the item away if it's already in hand."""
        keys = self.hotbar_keys()
        if i >= len(keys):
            return
        self.sel = -1 if self.sel == i else i
        self.g.refresh_hotbar()

    def to_dict(self):
        return {"items": dict(self.items), "order": list(self.order), "sel": self.sel}

    def from_dict(self, d):
        self.items = dict(d.get("items", {}))
        self.order = [k for k in d.get("order", []) if k in self.items]
        for k in self.items:
            if k not in self.order:
                self.order.append(k)
        self.sel = d.get("sel", 0)
