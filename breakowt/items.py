"""Item catalog and inventory."""
from __future__ import annotations

# key: (label, description, icon, stackable, throwable, holdable)
ITEMS = {
    "page": ("Soggy Planner Page", "Chuck's week, in his own handwriting. You're in it, on Sunday.", "page", False, False, True),
    "pencil": ("Chuck's Pencil", "Stolen mid-count. Chuck has probably not noticed. Chuck has noticed.", "pencil", False, False, True),
    "rock": ("Rock", "A good throwing rock. [R] to throw. Makes noise where it lands.", "rock", True, True, True),
    "pliers": ("Pliers", "For removing things that jingle.", "pliers", False, False, True),
    "cowbell": ("Your Old Cowbell", "Throw it [R] and anyone listening goes to look where it lands.", "cowbell", False, True, True),
    "radio": ("Chuck's Radio", "Plays one station: Country Hits That Are Also Sad.", "radio", False, False, True),
    "glasses": ("Spare Reading Glasses", "Chuck's backup glasses. +2.5. Somebody nerdy would love these.", "glasses", False, False, True),
    "bucket": ("Rusty Bucket", "A rusty bucket. Sir Loin would call it a helm.", "bucket", False, False, True),
    "boot": ("Chuck's Rubber Boot", "Size 13. Rubber doesn't conduct electricity. Science!", "boot", False, False, True),
    "rubber_chicken": ("Rubber Chicken", "Non-conductive. Deeply squeaky. [R] to throw.", "rubber_chicken", False, True, True),
    "tractor_key": ("Tractor Key", "The key to the JOHN STEER. Keychain says 'WORLD'S OKAYEST FARMER'.", "tractor_key", False, False, True),
    "jerrycan": ("Jerry Can (Diesel)", "Full of diesel. The fumes make your eyes water.", "jerrycan", False, False, True),
    "egg": ("Egg", "Fresh. Throwable. Splattery. [R] to throw.", "egg", True, True, True),
    "sparkplug": ("Spark Plug", "The tractor's missing spark plug. It was soaking in vinegar next to Chuck's teeth.", "sparkplug", False, False, True),
    "house_key": ("Spare House Key", "Found inside a garden gnome, as all keys eventually are.", "house_key", False, False, True),
    "score": ("Moozart's Score", "Symphony No. 1 in Moo Major, on the back of Chuck's planner page. 'For Forty-Seven.'", "score", False, False, True),
    "photo": ("Photo of Big Earl", "'Me & Big Earl, Best in Show 2009.' Moomaw should have this.", "photo", False, False, True),
    "horseshoe": ("Big Earl's Lucky Horseshoe", "If Chuck catches you, maybe he trips on it instead. Once.", "horseshoe", False, False, False),
    "moustache": ("Fake Moustache", "Wear it with a straw hat and Chuck sees Dale. [Q] to put it on. Don't gallop. Dale doesn't gallop.", "moustache", False, False, True),
    "hat": ("Chuck's Spare Straw Hat", "From the wardrobe. Wear with a moustache to become 'Dale'.", "hat", False, False, False),
    "coffee": ("Suspiciously Strong Coffee", "Gallop twice as long today. Your heart is doing something new.", "coffee", False, False, False),
    "tincan": ("Mysterious Tin Can", "It rattles when you shake it, but there's nothing in it.", "tincan", False, False, True),
    "shoes": ("Chuck's Bowling Shoes", "Red and blue, and damp inside. [R] to throw them somewhere Chuck will go looking.", "shoes", False, True, True),
    "cabinet_key": ("Gun Cabinet Key", "Small and brass. It opens Chuck's gun cabinet.", "cabinet_key", False, False, True),
    "shotgun": ("Shotgun ('Ol' Bessie')", "Ol' Bessie. You carry her in your mouth, very carefully.", "shotgun", False, False, True),
    "plank": ("Plank", "A long plank. Three of these could bridge a cattle grid.", "plank", True, False, True),
    "fuse": ("Main Fuse", "The main fuse. Without it the fence is just wire.", "fuse", False, False, True),
    "chimes": ("Wind Chimes", "Seashells on strings.", "chimes", False, False, True),
}


class Inventory:
    def __init__(self, g):
        self.g = g
        self.items: dict[str, int] = {}
        self.order: list[str] = []
        self.sel = 0

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
        self.items[key] -= n
        if self.items[key] <= 0:
            del self.items[key]
            self.order.remove(key)
            self.sel = min(self.sel, max(0, len(self.hotbar_keys()) - 1))
        self.g.refresh_hotbar()

    def has(self, key, n=1):
        return self.items.get(key, 0) >= n

    def count(self, key):
        return self.items.get(key, 0)

    def hotbar_keys(self):
        return [k for k in self.order if ITEMS.get(k, (0, 0, 0, 0, 0, False))[5]][:9]

    def selected(self):
        keys = self.hotbar_keys()
        if not keys:
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
            self.sel = (self.sel + d) % len(keys)
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
