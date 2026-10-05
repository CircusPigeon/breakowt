"""Short introductions, optional arguments, and practical help from the philosophers.

Mixed into Story. Persistent choices and completed assistance live in story flags;
temporary distractions use the ordinary farmer noise/investigation system.
"""
from __future__ import annotations


STANCES = ("practical", "challenge", "evidence")
STANCE_CHOICES = ["Get practical", "Challenge the claim", "Ask for evidence"]

INTRODUCTIONS = {
    "moozart": [
        ("moozart", "Don't step on my circles. I'm squeezing how far round against how far across. A bit more than three."),
        ("you", "Moo. (Chuck's planner. Sunday's me. Twelve goes on the truck on Thursday.)"),
        ("moozart", "It isn't how things are. It's how Chuck arranged them. Give me a place to stand and I'll move a gate. Sundown, at the oak: I'll show everyone."),
    ],
    "sirloin": [
        ("sirloin", "You're in my sunlight. A king once stood there and asked what I wanted. I told him to move. He moved."),
        ("you", "Moo. (Chuck's going to eat me on Sunday. I'm precious about where I end up.)"),
        ("sirloin", "Then you're a cow and I'm a dog. I bark at the powerful. Even a dog wants a kennel: find me a bucket, a home nobody can sell me."),
    ],
    "cowpernicus": [
        ("cowpernicus", "Fence posts: two hundred and six. Cows: fifty. Farmers: one. You're forty-seven. Prime. They'll divide you anyway."),
        ("you", "Moo. (Into chuck, brisket, rib, round. Can we change the arithmetic?)"),
        ("cowpernicus", "Souls go round, but I'd rather not eat my grandmother. I'll come to the oak for Archimoodes' diagrams. Find Chuck's reading glasses and I'll chart the farm."),
    ],
    "mooriarty": [
        ("mooriarty", "Welcome to the Garden. Friends, simple food, no fear. Also a shop."),
        ("you", "Moo. (Chuck's going to eat me on Sunday. I'd rather not be a burger.)"),
        ("mooriarty", "Death is nothing to us: where it is, you aren't. Everything before it, however, needs equipment. Rocks, rubber, a disguise. Golden Clovers only."),
    ],
    "moomaw": [
        ("moomaw", "You can't step into the same pasture twice, dear. Different grass, slightly older cow."),
        ("you", "Moo. (He wrote my number next to Sunday. And 'barbecue'.)"),
        ("moomaw", "Grass into cow, cow into Chuck. Eleven years, one direction. He did it to my Ajax. Fetch his photo from Chuck's office. Small things can go upstream."),
    ],
}

# Each stance changes which concrete clue or contribution the cow offers first.
REPLIES = {
    "moozart": {
        "practical": "A gate. Leverage. Somewhere Chuck isn't looking. Start with what moves; save the world after breakfast.",
        "challenge": "Good. 'Impossible' needs a proof. A shut gate proves only that nobody has opened it yet. We can test that.",
        "evidence": "Read what Chuck actually writes. Calendars, weights, accounts. An arrangement leaves working behind. Bring me the working.",
    },
    "sirloin": {
        "practical": "Chuck looks at whichever cow is loudest. I can be extremely philosophical at volume. Ask me when you need his eyes elsewhere.",
        "challenge": "Comfort is how they sell you obedience. I'll bark at him while you do something useful. One objection with horns beats six polite petitions.",
        "evidence": "Watch his hands. When equipment jams, he opens the tool cabinet. He protects his property more reliably than he protects an argument.",
    },
    "cowpernicus": {
        "practical": "Weight is a number I can supply. Find a plate that needs a cow on it and ask me. You can fetch whatever lies beyond it.",
        "challenge": "Then test the crossing before asking a herd to trust it. A plank is not a bridge merely because you put it near a hole.",
        "evidence": "Supports, joins, lengths. I can inspect your crossing and tell you which claim the timber refuses to support. Timber is a severe reviewer.",
    },
    "mooriarty": {
        "practical": "Fear sells well. I'd rather sell things that make less of it. For the crossing, ask me for a board. One sample; don't start a religion around it.",
        "challenge": "You're right to distinguish dying from being made to die. The second is a business model. We can interrupt a business model. I'll put a board toward it.",
        "evidence": "Test the useful bit: rubber doesn't conduct, timber bears weight, a disguise works only while you walk. I'll supply a board. You supply the experiment.",
    },
    "moomaw": {
        "practical": "Tell me when the crossing's being built. I'll talk to the ones who think staying is safer. Sometimes a river needs somebody to name the other bank.",
        "challenge": "No, dear. Flowing isn't consent. I've confused the two for years. I'll ask the herd to move; you can keep objecting when we stop.",
        "evidence": "Ask Cassandra what the truck does every Thursday. Ask who remembers Ajax. I'll bring those voices to the herd. Repetition can be testimony too.",
    },
}

ARGUMENTS = {
    "moozart": [
        ("you", "Moo. (What makes a cow's argument better than Chuck's arrangement?)"),
        ("moozart", "An arrangement has an owner. An argument has a flaw you can point at. Show me mine and I'll redraw it."),
        ("you", "Moo. (And twelve? Do you know who twelve is?)"),
        ("moozart", "Divisible by one, two, three, four and six. Very obliging. A number is easier to discuss than a cow. That may itself be a flaw."),
    ],
    "sirloin": [
        ("you", "Moo. (Does sleeping in a bucket make you free?)"),
        ("sirloin", "No. It makes me ridiculous on purpose. Chuck prefers us ridiculous by accident. That's a small jurisdiction worth defending."),
        ("you", "Moo. (And throwing you over the fence for the crows?)"),
        ("sirloin", "Feeds a crow and denies Chuck an invoice. I'm not above being useful. I'm below being merchandise."),
    ],
    "cowpernicus": [
        ("you", "Moo. (If souls come back, why fight being eaten?)"),
        ("cowpernicus", "Because being eaten is her problem. Eating is mine. Believing the soul survives doesn't grant me its body."),
        ("you", "Moo. (Even beans?)"),
        ("cowpernicus", "Especially beans. I may be wrong about beans. I can afford to be wrong without eating my grandmother."),
    ],
    "mooriarty": [
        ("you", "Moo. (Death is nothing, but you sell shells?)"),
        ("mooriarty", "I sell options. The fear isn't in the item. Neither is the wisdom. Those cost you more than six Clovers."),
        ("you", "Moo. (What's the Garden for, then?)"),
        ("mooriarty", "Friends and enough to eat without a landlord in your stomach. The shop is supposed to buy us less shop. I'm still working on that contradiction."),
    ],
    "moomaw": [
        ("you", "Moo. (You said we can't stop a river.)"),
        ("moomaw", "I said it after Ajax. It sounded wise, and wisdom is easier to repeat than his name."),
        ("you", "Moo. (So what changes?)"),
        ("moomaw", "Who's standing beside you. One cow gets wet. A herd can change where the water goes. Same river, different banks."),
    ],
}

SUPPORT_LABELS = {
    "sirloin": "Ask Moogenes to distract Chuck",
    "cowpernicus": "Ask Moothagoras to inspect the crossing",
    "mooriarty": "Ask Epicowrus for a board",
    "moomaw": "Ask Heifercleitus to spread the escape plan",
}


class CharacterAgency:
    def character_introduction(self, key):
        """Essential premise first; player chooses how to answer the philosopher."""
        yield from self.g.talk(INTRODUCTIONS[key])
        if key == "mooriarty":
            self.setf("mooriarty_met")
        yield from self.offer_discussion(key)

    def offer_discussion(self, key):
        if key not in REPLIES:
            return False
        old = self.flags.get(f"_stance_{key}")
        if old in STANCES:
            return False
        r = yield from self.g.say("you", "Moo. (How do I answer that?)", choices=STANCE_CHOICES)
        stance = STANCES[r if isinstance(r, int) and 0 <= r < len(STANCES) else 0]
        self.setf(f"_stance_{key}", stance)
        yield from self.g.talk([(key, REPLIES[key][stance])])
        follow = yield from self.g.say("you", "Moo. (There's more to ask.)",
                                       choices=["Leave it there", "Follow the argument"])
        self.g.end_talk()
        if follow == 1:
            yield from self.full_argument(key)
        return True

    def full_argument(self, key):
        if key not in ARGUMENTS:
            return False
        yield from self.g.talk(ARGUMENTS[key])
        self.setf(f"_argument_{key}")
        return True

    def character_talk(self, key):
        """Called after mandatory hooks and favour hand-ins, before idle/shop chatter."""
        help_options = []
        day = getattr(self, "day", getattr(self.g, "day", 0))
        if key == "sirloin" and 3 <= day <= 6 and not self.done("latch_kit_taken"):
            help_options.append((SUPPORT_LABELS[key], "sirloin"))
            # Choosing evidence makes the observed alternative explicit, rather than assuming noise is the answer.
            if self.flags.get("_stance_sirloin") == "evidence":
                help_options.insert(0, ("Ask what Moogenes observed", "maintenance_hint"))
        if key == "cowpernicus" and 3 <= day <= 6 and not self.done("escape_rope_taken"):
            help_options.append(("Ask Moothagoras to hold the weigh plate", "weight"))
        if self.cur == "d6_prep" and key in SUPPORT_LABELS:
            if key != "sirloin":
                help_options.insert(0, (SUPPORT_LABELS[key], key))
        if help_options:
            choices = [label for label, _ in help_options] + ["Browse the shop" if key == "mooriarty" else "Just talk"]
            choice = yield from self.g.say(key, "The plan needs doing. What do you need?", choices=choices)
            if isinstance(choice, int) and 0 <= choice < len(help_options):
                yield from self.character_support(help_options[choice][1])
                return True
        return (yield from self.character_reaction(key))

    def character_reaction(self, key):
        """At most one comment per event context, persisted with normal checkpoints."""
        if key not in INTRODUCTIONS and key != "cowleen":
            return False
        g = self.g
        contexts = []
        if g.stats.get("faints", 0) >= 2:
            contexts.append(("faints", {
                "cowleen": "Again? I'm developing a school of thought. It has a floor curriculum.",
                "sirloin": "She's fainted twice and he still thinks it's a breed. We should teach him a third philosophy. Loudly.",
                "mooriarty": "Moocrates has cornered the collapse market. I'll stay in equipment. Diversification.",
                "cowpernicus": "Two collapses, same farmer response. Moocrates calls it elenchus. I'd like a larger sample. She'd like a softer patch of grass.",
                "moozart": "A false premise and a valid response: if a cow is ill, look at the cow. His reasoning works. His evidence is lying down.",
                "moomaw": "He worries while she's on the ground. Then goes back to feeding us for Sunday. Same man, dear. Different verbs.",
            }[key]))
        if g.stats.get("caught", 0) >= 2:
            contexts.append(("caught_twice", {
                "sirloin": "Twice. He keeps returning you to the pasture and you keep disputing it. Good. Try disputing from behind a bale.",
                "cowpernicus": "Chuck's eyes work in straight lines. You keep meeting them halfway. Use cover and wait for him to turn.",
                "moomaw": "Coming back isn't the same as giving up, dear. But you can change the route on the third attempt.",
                "cowleen": "Twice. What did he see, and what were you looking at? Those are different questions. Ask both before the third attempt.",
                "moozart": "The last route has failed twice. That's two useful measurements. Wait behind cover; change one thing before collecting a third.",
                "mooriarty": "Two catches. An expensive exit at any price. Watch his route; buy yourself a minute of patience before buying equipment.",
            }[key]))
        if g.stats.get("caught", 0) == 0 and any(self.done(k) for k in ("d2_out", "d3_parts", "d5_inside")):
            contexts.append(("quiet_escape", {
                "sirloin": "Out and back, and he didn't notice. An excellent critique. No footnotes, no witnesses.",
                "cowpernicus": "No catches. A repeatable result would be better. I'll accept the first trial.",
                "mooriarty": "He didn't see you. Free is a very attractive price for an exit.",
                "cowleen": "Out and back unseen. So the fence didn't contain you. What did? And how many of us still believe it?",
                "moozart": "Through and back, unseen. The route exists. That's a stronger claim than a good diagram. Don't tell Moothagoras I said that.",
                "moomaw": "Upstream and back, and he never saw. You return to the same pasture as a slightly less obedient cow.",
            }[key]))
        favour = {"sirloin": "sq_helm", "cowpernicus": "sq_specs", "moomaw": "sq_photo"}.get(key)
        if favour and self.done(favour):
            contexts.append(("favour", {
                "sirloin": "The bucket's holding up. Property acquired; dignity liquidated. Ask me when you need an objection Chuck can hear.",
                "cowpernicus": "Glasses on. I can inspect an actual bridge now, instead of producing a beautifully labelled guess.",
                "moomaw": "Ajax's photo is with me. When the others say staying is safer, I'll show them whom it was safe for.",
            }[key]))
        seen = set(self.flags.get("_character_reactions", []))
        for context, line in contexts:
            marker = f"{key}:{context}"
            if marker not in seen:
                yield from g.talk([(key, line)])
                seen.add(marker)
                self.flags["_character_reactions"] = sorted(seen)
                self.save_progress()
                return True
        return False

    def character_support(self, key):
        """Help changes the farm or the preparation count; inspection never solves it."""
        g = self.g
        if key in ("sirloin", "distraction"):
            stance = self.flags.get("_stance_sirloin", "practical")
            line = ("I watched him open that cabinet. Wait for his hands, then I'll give his ears something to own."
                    if stance == "evidence" else "Chuck! Your property has an objection! A very public objection!")
            yield from g.talk([("sirloin", line)])
            if self.puzzle_help("distraction"):
                self.setf("helper_distraction")
            return True
        if key == "maintenance_hint":
            yield from g.talk([("sirloin", "Jam the grain hopper. Chuck fetches his wrench from the tool cabinet. Once it's open, draw him off. Or inspect the service hatch behind it: his property has two sides.")])
            self.setf("helper_maintenance_hint")
            self.save_progress()
            return True
        if key in ("cowpernicus", "bridge"):
            stance = self.flags.get("_stance_cowpernicus", "practical")
            yield from g.talk([("cowpernicus", self.bridge_hint(stance))])
            # Follow the cow's own pathfinding: this is an inspection visit, not a teleport or a solved layout.
            g.cows["cowpernicus"].goto((0, 0, 77.8), 2.2)
            self.setf("helper_bridge")
            self.save_progress()
            return True
        if key == "weight":
            yield from g.talk([("cowpernicus", "One cow: sufficient. I'll stand on the plate. You follow the cable to what it opens. Don't mistake this for agreement about beans.")])
            self.puzzle_help("weight")
            return True
        if key in ("mooriarty", "supply"):
            if self.bridge_supply():
                yield from g.talk([("mooriarty", "One sound board, on the house. The house is hay. It's doing very well. You still need to fit the board properly.")])
                self.setf("helper_supply")
                self.save_progress()
            else:
                yield from g.talk([("mooriarty", "You've enough timber already, or you've had my sample. More inventory isn't a better bridge. Place what you have.")])
            return True
        if key in ("moomaw", "rally"):
            rallied = set(self.flags.get("rallied", []))
            if self.done("helper_rally") or len(rallied) >= 5:
                yield from g.talk([("moomaw", "They've heard me, dear. Let them hear you too. A herd needs more than one voice.")])
                return True
            targets = self.flags.get("_helper_rally_targets")
            if not isinstance(targets, list):
                count = 2 if self.flags.get("_stance_moomaw") != "challenge" or self.done("sq_photo") else 1
                targets = [cow.idx for cow in g.herd if cow.idx not in rallied][:min(count, 5 - len(rallied))]
                self.flags["_helper_rally_targets"] = targets
            recruits = [cow for cow in g.herd if cow.idx in targets and cow.idx not in rallied]
            for cow in recruits:
                c = g.cows["moomaw"]
                c.goto((cow.x - 2.3, 0, cow.z), 2.0)
                yield from g.talk([
                    ("moomaw", "Sunday, dawn. Follow the tractor. Staying looks safe because the ones who didn't survive it aren't here to object."),
                    (cow, "Moo. (Tell me where to stand. I can do that. I've had years of practice.)"),
                ])
                rallied.add(cow.idx)
                self.flags["rallied"] = sorted(rallied)
                refresh = getattr(self, "_prep_refresh", None)
                if refresh:
                    refresh()
                self.save_progress()
            self.setf("helper_rally")
            self.save_progress()
            return True
        return False
