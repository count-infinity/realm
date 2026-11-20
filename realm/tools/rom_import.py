"""
ROM 2.4 ``.are`` -> REALM area (worldio JSON) converter, behind
``realm import-rom``.

ROM/Merc area files are section-based: each section opens with a ``#NAME``
line and records are keyed by ``#vnum``, strings are tilde-terminated, and
bit-vectors are written either as decimal numbers or ROM letter-flags
(``A``=bit0, ``B``=bit1, ... ``Z``=bit25, ``aa``=bit26 ...). This tool reads
the standard sections and emits a REALM worldio document
(``{"realm_format": 1, "objects": [...]}``) that ``@import`` /
``realm import`` / ``import_objects`` load like any area.

    realm import-rom midgaard.are --out midgaard.area.json --report
    realm import-rom areas/ --out converted/ --report parity.md

``convert`` reads one area; ``convert_tree`` converts many and aggregates a
MERC parity report (the batch run over a whole area collection).

Grounding: the #AREA header and the MOBILES/OBJECTS/ROOMS record layouts
here were checked against the real canonical Midgaard file (ROM 2.4 "new
format": a ``race~`` line on mobs, letter-flag bitvectors, the
``<type> <extra> <wear>`` object line, the ``<0> <flags> <sector>`` room
line, and ``D0``..``D5`` door blocks). RESETS/SHOPS/SPECIALS follow the ROM
2.4 ``db.c`` field order; validate them against a full file when you can, as
they are the fiddliest part.

What maps cleanly, and what does not, is summarized by ``--report`` and in
docs/development/rom-import.md.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- ROM constants ----------------------------------------------------------

# Door index -> (exit name, reverse index). ROM order: N E S W U D.
DIRS = [
    ("north", 2), ("east", 3), ("south", 0),
    ("west", 1), ("up", 5), ("down", 4),
]

#: ROM's exit reset flags for a door's lock value in the room file
#: (``load_rooms``) and for a ``D`` reset's state (``load_resets``): one table
#: in ROM 2.4's ``db.c``, and a ``D`` reset ORs its flags into the room
#: file's. 1 is closed, 2 closed and locked; NOPASS (no ``pass door``) and
#: PICKPROOF have no equivalent here and are reported.
DOOR_STATES = {
    0: (), 1: ("closed",), 2: ("closed", "locked"),
    3: ("closed", "locked", "nopass"), 4: ("closed", "locked", "pickproof"),
    5: ("closed", "locked", "nopass", "pickproof"),
}

SECTORS = {
    0: "inside", 1: "city", 2: "field", 3: "forest", 4: "hills",
    5: "mountain", 6: "water_swim", 7: "water_noswim", 8: "underwater",
    9: "air", 10: "desert",
}

# ROM item types (item_type number -> name). The common ones; others pass
# through as ``item:<n>``.
ITEM_TYPES = {
    1: "light", 2: "scroll", 3: "wand", 4: "staff", 5: "weapon",
    8: "treasure", 9: "armor", 10: "potion", 11: "clothing", 12: "furniture",
    13: "trash", 15: "container", 17: "drink_container", 18: "key",
    19: "food", 20: "money", 22: "boat", 23: "corpse_npc", 24: "corpse_pc",
    25: "fountain", 26: "pill", 27: "protect", 29: "jewelry", 30: "jukebox",
}

# ROM wear-flag letters (bit -> slot), named as MercSystem.wear_slots names
# them. Bit A(0)=take, then wear locations; B(13)=wield is a weapon, not a
# slot. ROM 2.4's Q(16)=float has no Merc slot and is reported as a gap.
WEAR_SLOTS = {
    1: "finger", 2: "neck", 3: "body", 4: "head", 5: "legs", 6: "feet",
    7: "hands", 8: "arms", 9: "shield", 10: "about", 11: "waist",
    12: "wrist", 13: "wield", 14: "held",
}
FLOAT_BIT = 16

# ROM's spell slot numbers (const.c ``skill_table``), which old-format
# areas write in potion, scroll and wand values instead of spell names.
ROM_SPELL_SLOTS: dict[int, str] = {
    1: "armor", 2: "teleport", 3: "bless", 4: "blindness", 5: "burning hands",
    6: "call lightning", 7: "charm person", 8: "chill touch", 10: "colour spray",
    11: "control weather", 12: "create food", 13: "create water",
    14: "cure blindness", 15: "cure critical", 16: "cure light", 17: "curse",
    18: "detect evil", 19: "detect invis", 20: "detect magic", 21: "detect poison",
    22: "dispel evil", 23: "earthquake", 24: "enchant weapon", 25: "energy drain",
    26: "fireball", 27: "harm", 28: "heal", 29: "invis", 30: "lightning bolt",
    31: "locate object", 32: "magic missile", 33: "poison", 34: "protection",
    35: "remove curse", 36: "sanctuary", 37: "shocking grasp", 38: "sleep",
    39: "giant strength", 40: "summon", 41: "ventriloquate", 42: "word of recall",
    43: "cure poison", 44: "detect hidden", 53: "identify", 56: "fly",
    57: "continual light", 58: "know alignment", 59: "dispel magic",
    61: "cure serious", 62: "cause light", 63: "cause critical",
    64: "cause serious", 65: "flamestrike", 66: "stone skin", 67: "shield",
    68: "weaken", 69: "mass invis", 70: "acid blast", 72: "faerie fire",
    73: "faerie fog", 74: "pass door", 77: "infravision", 80: "create spring",
    81: "refresh", 82: "change sex", 83: "gate",
    200: "acid breath", 201: "fire breath", 202: "frost breath",
    203: "gas breath", 204: "lightning breath",
}

# ROM's weapon attack words (const.c ``attack_table``) -> the REALM damage
# type their damage class is.
ATTACK_TYPES: dict[str, str] = {
    "slice": "slashing", "stab": "piercing", "slash": "slashing", "whip": "slashing",
    "claw": "slashing", "blast": "bludgeoning", "pound": "bludgeoning",
    "crush": "bludgeoning", "grep": "slashing", "bite": "piercing",
    "pierce": "piercing", "suction": "bludgeoning", "beating": "bludgeoning",
    "digestion": "acid", "charge": "bludgeoning", "slap": "bludgeoning",
    "punch": "bludgeoning", "wrath": "force", "magic": "force", "divine": "radiant",
    "cleave": "slashing", "scratch": "piercing", "peck": "piercing",
    "peckb": "bludgeoning", "chop": "slashing", "sting": "piercing",
    "smash": "bludgeoning", "shbite": "lightning", "flbite": "fire",
    "frbite": "cold", "acbite": "acid", "chomp": "piercing", "drain": "necrotic",
    "thrust": "piercing", "slime": "acid", "shock": "lightning",
    "thwack": "bludgeoning", "flame": "fire", "chill": "cold",
}


def _attack_bits() -> dict[int, str]:
    """An old-format file's attack word, read by ``_value_token`` as a flag
    word, is the bit-set of its letters; map each unambiguous one back."""
    seen: dict[int, list[str]] = {}
    for word in ATTACK_TYPES:
        seen.setdefault(rom_flags(word), []).append(word)
    return {bits: words[0] for bits, words in seen.items() if len(words) == 1}


def attack_damage_type(value: Any) -> str | None:
    """A ROM weapon's attack value (a word, or its letters' bit-set) as a
    REALM damage type; None when it is not one ROM knows."""
    if isinstance(value, str):
        return ATTACK_TYPES.get(value.strip().lower())
    word = _attack_bits().get(_int(value, -1))
    return ATTACK_TYPES.get(word) if word else None


#: CoffeeMud's importer (``Commands/Import.java``): a ROM food's hours of
#: fullness times 20 is its ``nourishment``, and a ROM drink container's
#: units times 30 its ``liquid_held`` (MUD_PLAN 12.4).
FOOD_SCALE = 20
LIQUID_SCALE = 30

#: ROM 2.4's ``liq_table`` by index, for old-format files that store a
#: drink's liquid as a number (newer ones store its name).
ROM_LIQUIDS = (
    "water", "beer", "red wine", "ale", "dark ale", "whisky", "lemonade",
    "firebreather", "local specialty", "slime mold juice", "milk", "tea", "coffee",
    "blood", "salt water", "coke", "root beer", "elvish wine", "white wine",
    "champagne", "mead", "rose wine", "benedictine wine", "vodka", "cranberry juice",
    "orange juice", "absinthe", "brandy", "aquavit", "schnapps", "icewine",
    "amontillado", "sherry", "framboise", "rum", "cordial",
)


def liquid_name(value: Any, area: Area) -> str:
    """A ROM liquid value (its name, or its index in ``liq_table``) as a
    name; ``water`` for an index ROM does not know (reported)."""
    if isinstance(value, str) and not value.lstrip("-").isdigit():
        return value.strip().lower() or "water"
    index = _int(value, -1)
    if 0 <= index < len(ROM_LIQUIDS):
        return ROM_LIQUIDS[index]
    area.gap(f"drink: unknown ROM liquid {value!r}; written as water")
    return "water"

# ROM immune/resist/vuln flag letters -> REALM damage-type name. ROM's
# IMM_/RES_/VULN_ bitvectors share one layout (merc.h); only the
# damage-typed bits map to a DamageType. The affect immunities
# (A=summon, B=charm, Q=disease, R=drowning, S=light, T=sound, X/Y/Z=
# wood/silver/iron) carry no damage-resistance meaning and are dropped from
# the resistance map (the raw letters stay on rom_imm/res/vuln for porting).
IRV_DAMAGE = {
    "C": "magical",      # IMM_MAGIC
    "D": "physical",     # IMM_WEAPON
    "E": "bludgeoning",  # IMM_BASH
    "F": "piercing",     # IMM_PIERCE
    "G": "slashing",     # IMM_SLASH
    "H": "fire",         # IMM_FIRE
    "I": "cold",         # IMM_COLD
    "J": "lightning",    # IMM_LIGHTNING
    "K": "acid",         # IMM_ACID
    "L": "poison",       # IMM_POISON
    "M": "necrotic",     # IMM_NEGATIVE
    "N": "radiant",      # IMM_HOLY
    "O": "force",        # IMM_ENERGY
    "P": "psychic",      # IMM_MENTAL
}

# ROM casting spec_procs -> the `caster` behavior, parameterized with each
# proc's canonical spell list (ROM special.c) trimmed to the spells the
# merc-classic pack ships. Import that pack alongside the area and these
# mobs cast; without it the behavior ticks but finds no spell_defs.
SPEC_CASTERS = {
    "spec_cast_adept": ["bless", "cure light"],
    "spec_cast_cleric": ["blindness", "curse", "flamestrike", "harm"],
    "spec_cast_judge": ["magic missile"],
    "spec_cast_mage": ["blindness", "chill touch", "colour spray",
                       "fireball", "acid blast"],
    "spec_cast_undead": ["curse", "chill touch", "blindness", "poison",
                         "harm"],
    "spec_cast_druid": ["poison", "curse", "flamestrike"],
    "spec_cast_necromancer": ["curse", "chill touch", "blindness", "poison",
                              "harm"],
    "spec_breath_fire": ["fire breath"],
    "spec_breath_frost": ["frost breath"],
    "spec_breath_acid": ["acid breath"],
    "spec_breath_gas": ["gas breath"],
    "spec_breath_lightning": ["lightning breath"],
    "spec_breath_any": ["fire breath", "frost breath", "acid breath",
                        "gas breath", "lightning breath"],
}

# Non-casting spec_procs that map onto a shipped behavior (the beastly
# fido's spec is spec_fido: it eats corpses).
SPEC_BEHAVIORS = {
    "spec_fido": {"behavior_id": "scavenger",
                  "params": {"eat_corpses": True, "pick_up": False}},
    "spec_janitor": {"behavior_id": "scavenger",
                     "params": {"eat_corpses": False, "pick_up": True}},
    "spec_thief": {"behavior_id": "steal", "params": {}},
    "spec_poison": {"behavior_id": "venomous", "params": {}},
    # The town watch are peacekeepers (they attack WANTED criminals, ROM's
    # KILLER and THIEF), NOT the movement-blocking `guard` behavior. ROM's
    # spec_guard also takes on the most evil fighter in a brawl, and
    # spec_patrolman breaks up any fight; spec_executioner only arrests.
    "spec_guard": {"behavior_id": "peacekeeper", "params": {"protect": "evil"}},
    "spec_patrolman": {"behavior_id": "peacekeeper", "params": {"protect": "fights"}},
    "spec_executioner": {"behavior_id": "peacekeeper", "params": {}},
}

# ROM extra-flag letters that become tags: ITEM_MAGIC (G) marks enchanted
# delivery; ITEM_ANTI_GOOD/_EVIL/_NEUTRAL (J/K/L) zap a wearer of that
# alignment off under Merc.
ITEM_FLAG_TAGS = {"G": "magic", "J": "anti_good", "K": "anti_evil", "L": "anti_neutral"}

# ROM room-flag letters that become tags: ROOM_NO_RECALL (N).
ROOM_FLAG_TAGS = {"N": "no_recall"}

# ROM's ROOM_PET_SHOP: the mobs reset into the next room (vnum + 1) are the
# pets the room's shopkeeper sells (see ``pet_shops``).
ROOM_PET_SHOP = "M"

# ROM wear *locations* (the enum used by 'E' reset lines and equip slots) —
# a DIFFERENT numbering from the wear-flag bits above.
WEAR_LOC = {
    0: "light", 1: "finger", 2: "finger", 3: "neck", 4: "neck", 5: "body",
    6: "head", 7: "legs", 8: "feet", 9: "hands", 10: "arms", 11: "shield",
    12: "about", 13: "waist", 14: "wrist", 15: "wrist", 16: "wield",
    17: "hold", 18: "float",
}


def rom_flags(token: str) -> int:
    """Decode a ROM bit-vector token: a decimal number, or letter flags
    (A=bit0 ... Z=bit25, a=bit26 ... e=bit30). Returns the integer value."""
    token = token.strip()
    if not token or token == "0":
        return 0
    if token.lstrip("-").isdigit():
        return int(token)
    bits = 0
    for ch in token:
        if "A" <= ch <= "Z":
            bits |= 1 << (ord(ch) - ord("A"))
        elif "a" <= ch <= "z":
            bits |= 1 << (26 + ord(ch) - ord("a"))
    return bits


def flag_letters(token: str) -> list[str]:
    """The individual set letters of a flag token, for readable tags —
    e.g. room flags ``CDS`` -> ``['C','D','S']``. A decimal bit-vector
    (ROM writes Midgaard's room flags so: ``266248``) reads as the letters
    of its bits, ``A`` for bit 0 to ``Z`` for bit 25, then ``a`` to ``f``."""
    token = token.strip()
    if not token or token.lstrip("-").isdigit():
        bits = int(token) if token.isdigit() else 0
        return [chr(ord("A") + b) if b < 26 else chr(ord("a") + b - 26)
                for b in range(32) if bits >> b & 1]
    return [c for c in token if c.isalpha()]


def keywords(text: str) -> list[str]:
    """A ROM keyword list (``sword long``) as the aliases a player types to
    name the thing: the whole list, as ROM accepts it typed, then each
    keyword once, in order (``["sword long", "sword", "long"]``)."""
    words = list(dict.fromkeys(text.split()))
    return [" ".join(words), *words] if len(words) > 1 else words


def rom_names(keyword_list: str, short: str) -> tuple[str, dict[str, Any]]:
    """The name and attributes a ROM mob or object is called by: its short
    description (``a long sword``, ``the wizard``) is the name, and its
    keywords answer when typed. With no short description the keywords
    are the name."""
    return (short.strip() or keyword_list.strip()), {"aliases": keywords(keyword_list)}


def resistance_map(imm: str, res: str, vuln: str) -> dict[str, float]:
    """ROM imm/res/vuln flag tokens -> a REALM ``resistances`` multiplier map.

    A damage-taken multiplier per damage type: immune -> 0.0, resist -> 0.5,
    vuln -> 1.5. Applied vuln, then res, then imm so the strongest (immune)
    wins when a type somehow appears in more than one band. Non-damage affect
    immunities are ignored (see ``IRV_DAMAGE``)."""
    out: dict[str, float] = {}
    for token, mult in ((vuln, 1.5), (res, 0.5), (imm, 0.0)):
        for ch in flag_letters(token):
            dtype = IRV_DAMAGE.get(ch)
            if dtype:
                out[dtype] = mult
    return out


def area_zone(area: Area) -> str:
    """A ``zone:`` tag slug for the area (one zone per imported area)."""
    slug = re.sub(r"[^a-z0-9]+", "_", area.name.lower()).strip("_")
    return slug or "area"


def dice_avg(spec: str) -> int:
    """Average of an ``NdS+B`` dice string (ROM hit/mana/damage dice)."""
    m = re.match(r"\s*(\d+)d(\d+)([+-]\d+)?\s*$", spec)
    if not m:
        try:
            return int(spec)
        except ValueError:
            return 0
    n, s, b = int(m.group(1)), int(m.group(2)), int(m.group(3) or 0)
    return round(n * (s + 1) / 2) + b


# --- Tokenizer ---------------------------------------------------------------

class Reader:
    """A cursor over the ``.are`` text with ROM's read primitives.

    ROM's loader is whitespace-and-tilde driven, not line driven: a string
    runs until a ``~``, numbers and words are whitespace-delimited. This
    mirrors ``fread_string`` / ``fread_number`` / ``fread_word``.
    """

    def __init__(self, text: str):
        self.text = text
        self.i = 0
        self.n = len(text)

    def eof(self) -> bool:
        return self.i >= self.n

    def _skip_ws(self) -> None:
        while self.i < self.n and self.text[self.i].isspace():
            self.i += 1

    def peek_char(self) -> str:
        self._skip_ws()
        return self.text[self.i] if self.i < self.n else ""

    def word(self) -> str:
        self._skip_ws()
        start = self.i
        while self.i < self.n and not self.text[self.i].isspace():
            self.i += 1
        return self.text[start:self.i]

    def number(self) -> int:
        tok = self.word()
        # ROM allows a leading letter-flag where a number is expected in a
        # few spots; treat non-numeric as its flag value.
        if tok and (tok.lstrip("-").isdigit()):
            return int(tok)
        return rom_flags(tok)

    def rest_of_line(self) -> str:
        """The rest of the current line (a trailing comment), which may be
        empty: unlike ``line`` it never skips to the next one."""
        start = self.i
        while self.i < self.n and self.text[self.i] != "\n":
            self.i += 1
        return self.text[start:self.i].strip()

    def line(self) -> str:
        self._skip_ws()
        start = self.i
        while self.i < self.n and self.text[self.i] != "\n":
            self.i += 1
        return self.text[start:self.i].strip()

    def string(self) -> str:
        """A tilde-terminated string (leading whitespace skipped, ~ eaten)."""
        self._skip_ws()
        end = self.text.find("~", self.i)
        if end == -1:
            s = self.text[self.i:]
            self.i = self.n
            return s.strip()
        s = self.text[self.i:end]
        self.i = end + 1
        return s.strip("\r\n")


# --- Converter ---------------------------------------------------------------

@dataclass
class Area:
    objects: list[dict] = field(default_factory=list)
    mob_protos: dict[int, dict] = field(default_factory=dict)   # vnum -> proto
    obj_protos: dict[int, dict] = field(default_factory=dict)
    rooms: dict[int, dict] = field(default_factory=dict)
    gaps: dict[str, int] = field(default_factory=dict)
    name: str = "Imported Area"
    #: --repop: emit a per-room ``spawner`` for each mob reset instead of a
    #: one-shot static placement, so the area repopulates itself.
    repop: bool = False
    #: --zone-reset: emit a single zone master carrying a ``zone_reset``
    #: behavior + reset_spec (the SMAUG whole-area restore), an ALTERNATIVE
    #: mob strategy to --repop's per-room spawners.
    zone_reset: bool = False
    mob_resets: list = field(default_factory=list)   # (mob_v, room_v)
    obj_resets: list = field(default_factory=list)   # (obj_v, room_v)
    obj_reset_rooms: set = field(default_factory=set)   # rooms with O resets
    #: ROM ``D`` resets: (room vnum, direction) -> the state's reset flags.
    door_resets: dict = field(default_factory=dict)
    _inst: int = 0

    def gap(self, msg: str) -> None:
        self.gaps[msg] = self.gaps.get(msg, 0) + 1

    def new_id(self, prefix: str) -> str:
        self._inst += 1
        return f"{prefix}_{self._inst}"


def obj_record(oid: str, name: str, desc: str, tags: list[str],
               attrs: dict, *, location: str | None = None) -> dict:
    return {
        "id": oid,
        "name": name,
        "description": desc,
        "tags": tags,
        "attrs": attrs,
        "locks": {},
        "behaviors": [],
        "location": location,
        "owner": None,
        "parent": None,
    }


def convert(text: str, repop: bool = False, zone_reset: bool = False) -> Area:
    r = Reader(text)
    area = Area()
    area.repop = repop
    area.zone_reset = zone_reset
    while not r.eof():
        ch = r.peek_char()
        if ch != "#":
            r.word()
            continue
        header = r.word()            # '#AREA', '#MOBILES', ... or '#3000'
        sect = header[1:].upper()
        if sect in ("$", "0", ""):
            break
        if sect == "AREA":
            _area_header(r, area)
        elif sect in ("AREADATA",):
            _areadata(r, area)
        elif sect == "MOBILES":
            _mobiles(r, area)
        elif sect == "OBJECTS":
            _objects(r, area)
        elif sect == "ROOMS":
            _rooms(r, area)
        elif sect == "RESETS":
            _resets(r, area)
        elif sect == "SHOPS":
            _shops(r, area)
        elif sect == "SPECIALS":
            _specials(r, area)
        elif sect in ("MOBPROGS", "OBJPROGS", "ROOMPROGS"):
            area.gap(f"#{sect}: ROM programs have no REALM equivalent "
                     "(would become softcode by hand); skipped")
            _skip_section(r)
        elif sect in ("HELPS", "SOCIALS"):
            _skip_section(r)
        else:
            area.gap(f"#{sect}: unknown section, skipped")
            _skip_section(r)
    _finalize(area)
    return area


def _skip_section(r: Reader) -> None:
    """Advance to the next ``#SECTION`` header (or EOF), ignoring content."""
    while not r.eof():
        if r.peek_char() == "#":
            # only stop at a *section* header (letters), not a #vnum record
            save = r.i
            tok = r.word()
            if tok[1:2].isalpha() or tok in ("#0", "#$"):
                r.i = save
                return
        else:
            r.word()


def _area_header(r: Reader, area: Area) -> None:
    # ROM 'old' #AREA: file_name~ name~ credits~ min_vnum max_vnum
    r.string()                       # file name
    area.name = r.string() or area.name
    r.string()                       # credits (levels/author)
    r.number()
    r.number()           # vnum range (informational)


def _areadata(r: Reader, area: Area) -> None:
    # ROM 2.4 'new' #AREADATA: keyed lines terminated by 'End'.
    while not r.eof():
        key = r.word()
        if key.lower() == "end":
            return
        if key == "Name":
            area.name = r.string()
        else:
            r.line()                 # Builders/VNUMs/Security/etc. — skip


def _mobiles(r: Reader, area: Area) -> None:
    while True:
        tok = r.word()
        if tok in ("#0", "#$") or not tok.startswith("#"):
            return
        vnum = int(tok[1:])
        name = r.string()
        short = r.string()
        long_ = r.string()
        look = r.string()
        race = r.string()
        act = r.word()
        aff = r.word()
        align = r.number()
        r.number()                 # group
        level = r.number()
        r.number()                 # hitroll
        hit = r.word()
        r.word()  # mana dice
        dam = r.word()
        r.word()                                       # damage type
        ac0 = r.number()                               # ac[pierce] (descending)
        r.number()
        r.number()
        r.number()
        off = r.word()
        imm = r.word()
        res = r.word()
        vuln = r.word()
        r.word()                                       # start pos
        r.word()                                       # default pos
        sex = r.word()
        wealth = r.number()
        r.line()                                       # form parts size material

        tags = ["npc", "prototype"]
        if race:
            tags.append(f"race:{race}")
        shown, naming = rom_names(name, short)
        attrs: dict[str, Any] = {
            "rom_vnum": vnum,
            **naming,
            "long_desc": long_,
            "level": level,
            "alignment": align,
            "sex": sex,
            # Money is the economy's one balance (``credits``); the raw
            # silver figure stays beside it.
            "credits": mob_money(wealth),
            "rom_wealth": wealth,
            # ROM does not store a kill's XP (the server derives it); a
            # level-scaled ``points`` gives the death award something to
            # divide (GameSystem.death_award = points // 10).
            "points": max(1, level) * 100,
            "max_hp": dice_avg(hit),
            "hp": dice_avg(hit),
            # MERC-native combat stats: descending AC, level-derived THAC0,
            # and a natural-attack damage die (used when the mob is unarmed).
            "armor_class": ac0,
            "thac0": max(0, 20 - level),
            "damage_dice": dam,
            "rom_act": flag_letters(act),
            "rom_affect": flag_letters(aff),
            "rom_offense": flag_letters(off),
        }
        if rom_flags(imm) or rom_flags(res) or rom_flags(vuln):
            # Normalize the ROM damage bits into a portable ``resistances``
            # multiplier map that MercRuleset.apply_damage consumes directly.
            # The raw letters stay too, for non-MERC hand-porting and for the
            # non-damage affect immunities the map drops.
            resist = resistance_map(imm, res, vuln)
            if resist:
                attrs["resistances"] = resist
            attrs["rom_imm"] = flag_letters(imm)
            attrs["rom_res"] = flag_letters(res)
            attrs["rom_vuln"] = flag_letters(vuln)
        proto = obj_record(f"rom_mob_{vnum}", shown, look, tags, attrs)
        # ACT flags -> behavior: a non-SENTINEL mob wanders (ACT_STAY_AREA
        # keeps it in its zone), so towns feel alive. Keepers get this
        # stripped in _shops (a shopkeeper who walks off has no shop).
        # ACT flags -> the shipped NPC-AI behaviors (wandering/aggressive in
        # realm/std/combat/behaviors.py; scavenger in realm/std/npc/behaviors.py).
        act_letters = flag_letters(act)
        if "B" not in act_letters:                       # not ACT_SENTINEL
            proto["behaviors"].append(
                {"behavior_id": "wandering",
                 "params": {"stay_in_zone": "G" in act_letters}})  # STAY_AREA
        if "F" in act_letters and "H" in act_letters:    # ACT_AGGRESSIVE + ACT_WIMPY
            # ROM's aggr_update: a wimpy aggressor attacks only a player
            # who is asleep (the beastly fido); no one awake is jumped.
            area.gap("ACT_AGGRESSIVE with ACT_WIMPY: attacks only the sleeping in ROM; "
                     "not aggressive here")
        elif "F" in act_letters:                         # ACT_AGGRESSIVE
            proto["behaviors"].append(
                {"behavior_id": "aggressive", "params": {}})
        if "C" in act_letters:                           # ACT_SCAVENGER
            proto["behaviors"].append(scavenger_behavior())
        trainer = trainer_behavior(act_letters)
        if trainer is not None:                          # ACT_PRACTICE / ACT_TRAIN
            proto["behaviors"].append(trainer)
        area.mob_protos[vnum] = proto


def item_flag_tags(extra_letters: list[str]) -> list[str]:
    """The tags an object's ROM extra flags give it (``ITEM_FLAG_TAGS``)."""
    return [tag for letter, tag in ITEM_FLAG_TAGS.items() if letter in extra_letters]


def room_flag_tags(flag_letters_: list[str]) -> list[str]:
    """The tags a room's ROM flags give it (``ROOM_FLAG_TAGS``)."""
    return [tag for letter, tag in ROOM_FLAG_TAGS.items() if letter in flag_letters_]


def pet_price(level: int) -> int:
    """ROM's pet price, ``10 * level * level`` silver, in gold (as
    ``mob_money``): at least 1."""
    return max(1, 10 * max(0, int(level)) ** 2 // 100)


def pet_shops(objects: list[dict]) -> int:
    """ROM's ``ROOM_PET_SHOP``: in each room flagged ``M``, the shopkeeper
    (and its prototype) sells pets, ``sells_pets`` with a ``pet_stock`` of
    the prototypes of the mobs reset into the following room (vnum + 1),
    each priced at ROM's ``10 * level * level`` silver (``pet_price``)
    unless it has a ``value``. Works on a converted document's objects, so
    ``scripts/dev/refresh_rom_items.py`` uses it too. Returns how many
    objects changed."""
    by_id = {o.get("id"): o for o in objects}
    changed = 0
    for room in objects:
        attrs = room.get("attrs") or {}
        if "room" not in room.get("tags", []) or \
                ROOM_PET_SHOP not in (attrs.get("rom_room_flags") or []):
            continue
        store_id = f"rom_{int(attrs['rom_vnum']) + 1}"
        stock: list[str] = []
        for mob in objects:
            vnum = (mob.get("attrs") or {}).get("prototype_vnum")
            proto_id = f"rom_mob_{vnum}"
            if (mob.get("location") == store_id and "npc" in mob.get("tags", [])
                    and vnum is not None and proto_id in by_id and proto_id not in stock):
                stock.append(proto_id)
        for proto_id in stock:
            proto_attrs = by_id[proto_id].setdefault("attrs", {})
            if "value" not in proto_attrs:
                proto_attrs["value"] = pet_price(proto_attrs.get("level") or 0)
                changed += 1
        keepers = [o for o in objects if o.get("location") == room["id"]
                   and any(b.get("behavior_id") == "shopkeeper" for b in o.get("behaviors", []))]
        keepers += [by_id[f"rom_mob_{k['attrs']['prototype_vnum']}"] for k in list(keepers)
                    if f"rom_mob_{k['attrs'].get('prototype_vnum')}" in by_id]
        for keeper in keepers:
            for behavior in keeper.get("behaviors", []):
                if behavior.get("behavior_id") != "shopkeeper":
                    continue
                params = behavior.setdefault("params", {})
                if params.get("sells_pets") is not True or params.get("pet_stock") != stock:
                    params["sells_pets"] = True
                    params["pet_stock"] = list(stock)
                    changed += 1
    return changed


def mob_money(wealth: int) -> int:
    """A mob's money in gold. ROM's ``wealth`` is in silver; a mob made from
    it carries about that much, split into gold and silver (``create_mobile``).
    REALM has one coin, so: wealth / 100."""
    return max(0, int(wealth)) // 100


def room_light_tags(sector_name: str) -> list[str]:
    """ROM's ``room_is_dark``: city streets stay lit at night (street
    lamps), so a city room is ``lamplit``; the clock darkens any other
    outdoor room at night."""
    return ["lamplit"] if sector_name == "city" else []


def scavenger_behavior() -> dict:
    """ROM's ``ACT_SCAVENGER``: it picks up the best thing lying in the room
    (``mobile_update``); it eats nothing. (``spec_fido`` is the corpse
    eater, a special procedure.)"""
    return {"behavior_id": "scavenger", "params": {"eat_corpses": False, "pick_up": True}}


def trainer_behavior(act_letters: list[str]) -> dict | None:
    """ROM's ``ACT_PRACTICE`` (K: a guildmaster, teaches the class's
    skills) and ``ACT_TRAIN`` (J: trains characteristics) as the
    ``trainer`` behavior; None for neither."""
    practice, train = "K" in act_letters, "J" in act_letters
    if not practice and not train:
        return None
    return {"behavior_id": "trainer",
            "params": {"teaches": "class" if practice else [], "trains_stats": train}}


def _objects(r: Reader, area: Area) -> None:
    while True:
        tok = r.word()
        if tok in ("#0", "#$") or not tok.startswith("#"):
            return
        vnum = int(tok[1:])
        name = r.string()
        short = r.string()
        look = r.string()
        r.string()                                     # material
        itype_tok = r.word()
        extra = r.word()
        wear = r.word()
        # ROM 2.4 new-format objects write the item type as a WORD
        # ('drink', 'weapon', 'armor'); old numeric files as a number.
        if itype_tok.isdigit():
            type_name = ITEM_TYPES.get(int(itype_tok), f"item:{itype_tok}")
        else:
            type_name = itype_tok
        # 5 values: numbers, flag letters, or 'quoted' strings.
        values = [_value_token(r) for _ in range(5)]
        level = r.number()
        weight = r.number()
        cost = r.number()
        r.word()                                       # condition letter
        _skip_obj_affects(r)

        tags = ["thing", "prototype", type_name]
        wear_bits = rom_flags(wear)
        if type_name == "weapon" or (wear_bits >> 13) & 1:
            tags.append("wieldable")
        wslot = wear_slot(type_name, wear_bits)
        if wslot:
            tags.append("wearable")
        elif (wear_bits >> FLOAT_BIT) & 1:
            area.gap("wear location 'float' has no Merc slot; the item is not wearable")
        # ROM ITEM_MAGIC (extra flag G): the enchanted-delivery marker. A
        # magic-tagged weapon's hits count as magical for the resistance
        # family ladder — they bypass IMM_WEAPON ('physical'), the classic
        # "you need an enchanted blade" gate. The anti-alignment flags
        # become anti_good / anti_evil / anti_neutral.
        tags.extend(item_flag_tags(flag_letters(extra)))
        shown, naming = rom_names(name, short)
        attrs: dict[str, Any] = {
            "rom_vnum": vnum, **naming,
            "item_type": type_name, "weight": weight, "value": cost,
            "level": level, "rom_values": values,
            "rom_extra": flag_letters(extra), "rom_wear": flag_letters(wear),
        }
        if wslot:
            attrs["slot"] = wslot
        extra_tags, fields = item_fields(type_name, values, area)
        tags.extend(t for t in extra_tags if t not in tags)
        attrs.update(fields)
        if type_name == "weapon":
            # ROM weapon values: [class, num_dice, dice_type, attack, flags].
            # Emit ``damage_dice`` (what MercRuleset reads) and a plain
            # ``damage`` alias for other systems.
            try:
                dice = f"{int(values[1])}d{int(values[2])}"
                attrs["damage_dice"] = dice
                attrs["damage"] = dice
            except (ValueError, TypeError):
                area.gap("weapon has non-standard ROM damage values; left in "
                         "rom_values for hand-mapping")
        if type_name == "armor":
            # ROM armor value0 = AC-apply (how much it improves AC). MERC's
            # recompute_ac subtracts this from the wearer's armor_class.
            try:
                attrs["ac_apply"] = int(values[0])
            except (ValueError, TypeError):
                pass
        if type_name == "key":
            attrs["unlocks"] = key_token(vnum)
        area.obj_protos[vnum] = obj_record(
            f"rom_obj_{vnum}", shown, look, tags, attrs)


def key_token(vnum: int) -> str:
    """The lock a ROM key object opens: an exit's ``key_id`` and the key's
    ``unlocks`` (what ``lock`` and ``unlock`` match) both name it, as ROM's
    ``has_key`` matches the key object's vnum."""
    return f"rom_obj_{vnum}"


def wear_slot(type_name: str, wear_bits: int) -> str | None:
    """The Merc slot an object is worn in: its first wear-location bit (not
    wield), else ``light`` for a light source."""
    slot = next((s for b, s in WEAR_SLOTS.items()
                 if (wear_bits >> b) & 1 and s != "wield"), None)
    if slot is None and type_name == "light":
        slot = "light"
    return slot


_PACK_SPELLS: set[str] | None = None


def _pack_spells() -> set[str]:
    """The spell names the built-in merc-classic pack defines."""
    global _PACK_SPELLS
    if _PACK_SPELLS is None:
        import importlib.resources
        source = importlib.resources.files("realm.packs") / "merc-classic" / "spells.json"
        data = json.loads(source.read_text())
        objects = data["objects"] if isinstance(data, dict) else data
        _PACK_SPELLS = {str(o["name"]).lower() for o in objects}
    return _PACK_SPELLS


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _spell_name(value: Any, type_name: str, area: Area) -> str | None:
    """A ROM spell value (a 'name', or an old-format slot number) as a
    spell name; None for an empty value."""
    if isinstance(value, str) and not value.lstrip("-").isdigit():
        name = value.strip().lower()
        if not name:
            return None
    else:
        slot = _int(value, -1)
        if slot <= 0:
            return None
        name = ROM_SPELL_SLOTS.get(slot)
        if name is None:
            area.gap(f"{type_name}: unknown ROM spell slot {slot}; left out of spells")
            return None
    if name not in _pack_spells():
        area.gap(f"{type_name} spell '{name}' has no spell_def in merc-classic; the "
                 f"item does nothing until one is defined")
    return name


def item_fields(type_name: str, values: list, area: Area) -> tuple[list[str], dict]:
    """Tags and attributes that make a ROM item work (MUD_PLAN 3.4, 4.2): a
    weapon's ``damage_type``; ``spells``, ``spell_level`` and ``charges``
    for potions, pills, scrolls, wands and staves; ``nourishment`` for food;
    ``liquid``, ``liquid_held`` and ``liquid_remaining`` for a drink
    container; ``liquid`` and the ``fountain`` tag for a fountain."""
    values = list(values) + [0] * (5 - len(values))
    attrs: dict[str, Any] = {}
    tags: list[str] = []
    if type_name == "weapon":
        dtype = attack_damage_type(values[3])
        if dtype:
            attrs["damage_type"] = dtype
        else:
            area.gap("weapon: attack type not a ROM attack word; damage_type left unset "
                     "(bludgeoning)")
    elif type_name in ("potion", "pill", "scroll"):
        spells = [n for n in (_spell_name(v, type_name, area) for v in values[1:5]) if n]
        attrs.update(spells=spells, spell_level=_int(values[0], 1))
        if not spells:
            area.gap(f"{type_name}: no spell in its values; it does nothing until it is "
                     "given one (a `spells` attribute)")
        if type_name == "pill":
            area.gap("pill: eating a pill does not cast its spells; quaff it as a potion")
            tags.append("potion")
    elif type_name in ("wand", "staff"):
        spell = _spell_name(values[3], type_name, area)
        if spell is None:
            area.gap(f"{type_name}: no spell in its values; it does nothing until it is "
                     "given one (a `spells` attribute)")
        attrs.update(spells=[spell] if spell else [], spell_level=_int(values[0], 1),
                     charges=_int(values[2]))
    elif type_name == "food":
        attrs["nourishment"] = max(0, _int(values[0])) * FOOD_SCALE
    elif type_name in ("drink", "drink_container"):
        tags.append("drink")
        attrs.update(liquid=liquid_name(values[2], area),
                     liquid_held=max(0, _int(values[0])) * LIQUID_SCALE,
                     liquid_remaining=max(0, _int(values[1])) * LIQUID_SCALE)
    elif type_name == "fountain":
        tags.extend(["drink", "fountain"])
        attrs["liquid"] = liquid_name(values[2], area)
    return tags, attrs


#: What ``item_fields`` wrote for food and drink before MUD_PLAN step 12;
#: ``scripts/dev/refresh_rom_items.py`` removes them from these types.
CONSUMABLE_TYPES = ("food", "drink", "drink_container", "fountain")
RETIRED_CONSUMABLE_FIELDS = ("restores", "charges")


def _value_token(r: Reader):
    """One object value: a 'quoted string', a flag/number word."""
    if r.peek_char() == "'":
        r._skip_ws()
        end = r.text.find("'", r.i + 1)
        s = r.text[r.i + 1:end]
        r.i = end + 1
        return s
    w = r.word()
    return int(w) if w.lstrip("-").isdigit() else rom_flags(w)


def _skip_obj_affects(r: Reader) -> None:
    # Optional trailing 'A'/'F' apply lines and 'E' extra descriptions.
    while r.peek_char() in ("A", "F", "E"):
        letter = r.word()
        if letter == "A":
            r.number()
            r.number()
        elif letter == "F":
            r.word()
            r.number()
            r.number()
            r.word()
        elif letter == "E":
            r.string()
            r.string()


def _rooms(r: Reader, area: Area) -> None:
    while True:
        tok = r.word()
        if tok in ("#0", "#$") or not tok.startswith("#"):
            return
        vnum = int(tok[1:])
        name = r.string()
        desc = r.string()
        r.number()                                     # area number (0)
        flags = r.word()
        sector = r.number()
        room = obj_record(
            f"rom_{vnum}", name, desc, ["room"],
            {"rom_vnum": vnum, "sector": SECTORS.get(sector, str(sector)),
             "rom_room_flags": flag_letters(flags)})
        room["_exits"] = []          # staged; realized in _finalize
        sector_name = SECTORS.get(sector, str(sector))
        room["tags"].append(f"sector:{sector_name}")
        # Zone membership: bounds STAY_AREA wanderers and lets a zone_reset
        # find its rooms. One zone per imported area, named for it.
        room["tags"].append(f"zone:{area_zone(area)}")
        # A plain `outdoor` tag (anything not an interior): orchestrators
        # populate "all outdoor rooms", and the clock darkens them at night.
        if sector_name != "inside":
            room["tags"].append("outdoor")
        room["tags"].extend(t for t in room_light_tags(sector_name) if t not in room["tags"])
        room["tags"].extend(room_flag_tags(flag_letters(flags)))
        # sub-records until 'S'
        while True:
            sub = r.word()
            if sub == "S":
                break
            if sub.startswith("D") and sub[1:].isdigit():
                d = int(sub[1:])
                door_desc = r.string()
                keywords = r.string()
                locks = r.number()
                key = r.number()
                to_vnum = r.number()
                room["_exits"].append({
                    "dir": d, "desc": door_desc, "keywords": keywords,
                    "locks": locks, "key": key, "to": to_vnum})
                if key > 0 and key in area.obj_protos:
                    # Any object can be ROM's key, not only a `key`-type one.
                    area.obj_protos[key]["attrs"].setdefault("unlocks", key_token(key))
            elif sub == "E":
                r.string()
                r.string()                 # extra desc kw + text
            elif sub in ("H", "M", "O", "C"):
                r.line()                               # heal/mana/owner/clan
            elif sub in ("#0", "#$") or sub.startswith("#"):
                r.i -= len(sub)                        # not ours; back up
                break
            else:
                r.line()
        area.rooms[vnum] = room


def _resets(r: Reader, area: Area) -> None:
    """ROM's ``load_resets``: a line starting with ``*`` is a comment, and
    after a reset's fields the rest of its line is one too (read to the end
    of that line, never into the next)."""
    last_mob_iid: str | None = None
    while True:
        letter = r.word()
        if letter in ("S", "#0", "#$") or letter.startswith("#"):
            if letter.startswith("#") and letter not in ("#0", "#$"):
                r.i -= len(letter)
            return
        if not letter.startswith("*"):
            last_mob_iid = _reset(r, area, letter, last_mob_iid)
        r.rest_of_line()                               # the comment


def _reset(r: Reader, area: Area, letter: str, last_mob_iid: str | None) -> str | None:
    """One reset's fields, after its letter. Returns the mob that ``G`` and
    ``E`` resets now give to (the one an ``M`` placed)."""
    if letter not in ("M", "O", "P", "G", "E", "D", "R"):
        area.gap(f"reset {letter!r} is not a ROM reset; its line was skipped")
        return last_mob_iid
    r.number()                                         # if-flag (unused, 0)
    if letter == "M":
        mob_v = r.number()
        r.number()
        room_v = r.number()
        r.number()                            # ROM room limit
        last_mob_iid = _place_mob(area, mob_v, room_v)
        if (area.repop or area.zone_reset) and last_mob_iid is not None:
            # Placed statically (so keepers keep their G/E stock); a
            # spawner (or zone_reset spec) is built from these at finalize.
            area.mob_resets.append((mob_v, room_v))
    elif letter == "O":
        obj_v = r.number()
        r.number()
        room_v = r.number()
        _place_obj(area, obj_v, room_v)
        if area.repop:
            area.obj_reset_rooms.add(room_v)         # floor loot restocks
        if area.zone_reset:
            area.obj_resets.append((obj_v, room_v))
    elif letter == "P":
        obj_v = r.number()
        r.number()
        into_v = r.number()
        r.number()
        _put_in_obj(area, obj_v, into_v)
    elif letter == "G":
        obj_v = r.number()
        r.number()
        _give_mob(area, obj_v, last_mob_iid)
    elif letter == "E":
        obj_v = r.number()
        r.number()
        wear = r.number()
        _equip_mob(area, obj_v, last_mob_iid, wear)
    elif letter == "D":
        room_v = r.number()
        door = r.number()
        state = r.number()
        _door_reset(area, room_v, door, state)
    else:
        area.gap("reset R (randomize exits) has no static equivalent; "
                 "the exits are emitted in their authored order")
    return last_mob_iid


def _door_reset(area: Area, room_v: int, door: int, state: int) -> None:
    """ROM's ``load_resets`` ``D``: the door in ``room_v``'s ``door``
    direction starts ``state`` (0 open, 1 closed, 2 closed and locked; see
    ``DOOR_STATES``). ROM refuses to boot on a ``D`` for an exit that is no
    door; here it is reported and skipped."""
    room = area.rooms.get(room_v)
    exit_ = next((ex for ex in (room or {}).get("_exits", []) if ex["dir"] == door), None)
    if exit_ is None or not exit_["locks"]:
        area.gap("reset D on an exit that is not a door (ROM refuses to boot): skipped")
        return
    if state not in DOOR_STATES:
        area.gap("reset D with a state ROM does not know: skipped")
        return
    flags = area.door_resets.setdefault((room_v, door), set())
    flags.update(DOOR_STATES[state])


def _door_flags(area: Area) -> dict[tuple[int, int], set[str]]:
    """Each door's state at boot, (room vnum, direction) -> flags: its lock
    value's (``DOOR_STATES``), ORed with its ``D`` resets', and with those of
    the door's other side, the exit beyond leading back (ROM keeps one set
    per side; REALM's two faces of a door agree, so they start agreeing)."""
    own: dict[tuple[int, int], set[str]] = {}
    for vnum, room in area.rooms.items():
        for ex in room.get("_exits", []):
            if ex["locks"]:
                own[(vnum, ex["dir"])] = (set(DOOR_STATES.get(ex["locks"], ()))
                                          | area.door_resets.get((vnum, ex["dir"]), set()))
    flags: dict[tuple[int, int], set[str]] = {}
    for (vnum, door), state in own.items():
        ex = next(e for e in area.rooms[vnum]["_exits"] if e["dir"] == door)
        back = DIRS[door][1] if door < len(DIRS) else None
        flags[(vnum, door)] = state | own.get((ex["to"], back), set())
    return flags


def _clone_proto(area: Area, protos: dict[int, dict], vnum: int,
                 kind: str) -> dict | None:
    proto = protos.get(vnum)
    if proto is None:
        area.gap(f"reset references missing {kind} vnum {vnum}; skipped")
        return None
    inst = json.loads(json.dumps(proto))            # deep copy
    inst["id"] = area.new_id(proto["id"].replace("rom_", "rom_i_", 1))
    inst["tags"] = [t for t in inst["tags"] if t != "prototype"]
    inst["attrs"]["prototype_vnum"] = vnum
    return inst


def _place_mob(area: Area, mob_v: int, room_v: int) -> str | None:
    inst = _clone_proto(area, area.mob_protos, mob_v, "mob")
    if inst is None:
        return None
    inst["location"] = f"rom_{room_v}"
    area.objects.append(inst)
    return inst["id"]


def _place_obj(area: Area, obj_v: int, room_v: int) -> str | None:
    inst = _clone_proto(area, area.obj_protos, obj_v, "object")
    if inst is None:
        return None
    inst["location"] = f"rom_{room_v}"
    area.objects.append(inst)
    return inst["id"]


def _put_in_obj(area: Area, obj_v: int, into_iid_or_vnum) -> str | None:
    inst = _clone_proto(area, area.obj_protos, obj_v, "object")
    if inst is None:
        return None
    # into_v is an object vnum in ROM; we target the most-recent instance
    # of it (a mob may share the number).
    target = next((o for o in reversed(area.objects)
                   if o["attrs"].get("prototype_vnum") == into_iid_or_vnum
                   and "npc" not in o["tags"]),
                  None)
    inst["location"] = target["id"] if target else None
    area.objects.append(inst)
    return inst["id"]


def _give_mob(area: Area, obj_v: int, mob_iid: str | None) -> str | None:
    inst = _clone_proto(area, area.obj_protos, obj_v, "object")
    if inst is None:
        return None
    inst["location"] = mob_iid
    area.objects.append(inst)
    return inst["id"]


#: A ROM wear location (``WEAR_LOC``) whose Merc slot has another name.
WEAR_LOC_SLOT = {"hold": "held"}


def equip_record(record: dict, wear_loc: str) -> bool:
    """Equip an object record as a player's gear is: ROM's ``wield`` tags it
    ``wielded``; any other wear location tags it ``worn`` with that place as
    its Merc ``slot`` (``hold`` is ``held``). False, and the record left
    alone, for a place Merc has no slot for (``float``)."""
    tags = record.setdefault("tags", [])
    if wear_loc == "wield":
        if "wielded" not in tags:
            tags.append("wielded")
        return True
    slot = WEAR_LOC_SLOT.get(wear_loc, wear_loc)
    if slot not in {*WEAR_SLOTS.values(), "light"} - {"wield"}:
        return False
    if "worn" not in tags:
        tags.append("worn")
    record.setdefault("attrs", {})["slot"] = slot
    return True


def carried_prototypes(objects: list[dict], holder_id: str) -> list[dict]:
    """Spawn prototypes (a spawner's ``contents``) of what the object
    ``holder_id`` carries, worn and wielded gear tagged as it is."""
    return [{"name": o["name"], "description": o["description"],
             "tags": list(o["tags"]), "attrs": json.loads(json.dumps(o["attrs"])),
             "behaviors": [dict(b) for b in o.get("behaviors", [])]}
            for o in objects if o.get("location") == holder_id]


def _equip_mob(area: Area, obj_v: int, mob_iid: str | None,
               wear: int) -> str | None:
    inst = _clone_proto(area, area.obj_protos, obj_v, "object")
    if inst is None:
        return None
    inst["location"] = mob_iid
    wear_loc = WEAR_LOC.get(wear, str(wear))
    if not equip_record(inst, wear_loc):
        area.gap(f"reset E (equipped gear): wear location {wear_loc!r} has no "
                 "Merc slot; the item is carried, not worn")
    area.objects.append(inst)
    return inst["id"]


def _shops(r: Reader, area: Area) -> None:
    while True:
        first = r.word()
        if first in ("0", "#0", "#$") or first.startswith("#"):
            if first.startswith("#"):
                r.i -= len(first)
            return
        keeper = int(first)
        rest = r.line().split()
        buy_types = rest[0:5]
        profit_buy = rest[5] if len(rest) > 5 else "100"
        profit_sell = rest[6] if len(rest) > 6 else "100"
        proto = area.mob_protos.get(keeper)
        if proto is None:
            area.gap(f"#SHOPS references non-area keeper {keeper}; skipped")
            continue
        behavior = {
            "behavior_id": "shopkeeper",
            "params": {"markup": _pct(profit_buy),
                       "buyback": _pct(profit_sell)},
        }
        buys = [int(x) for x in buy_types if x.lstrip("-").isdigit()]
        # The keeper is every spawned instance of this mob, not just the
        # prototype — resets ran first, so patch the placed instances too.
        # Objects share the vnum space: object 3000 is not mob 3000.
        for target in [proto, *(o for o in area.objects
                                if o["attrs"].get("prototype_vnum") == keeper
                                and "npc" in o["tags"])]:
            # A shopkeeper stays at their counter: drop any wander the ACT
            # flags gave them.
            target["behaviors"] = [b for b in target["behaviors"]
                                   if b["behavior_id"] != "wandering"]
            target["behaviors"].append(dict(behavior))
            if area.repop and not any(b["behavior_id"] == "restock"
                                      for b in target["behaviors"]):
                # Wares replenish: the shop never runs dry.
                target["behaviors"].append(
                    {"behavior_id": "restock", "params": {}})
            target["attrs"]["rom_shop_buys"] = buys
        area.gap("#SHOPS: mapped to the shopkeeper behavior (markup/buyback); "
                 "ROM per-item-type buy filters kept as rom_shop_buys attr")


def _pct(s: str) -> float:
    try:
        return round(int(s) / 100.0, 3)
    except ValueError:
        return 1.0


def _specials(r: Reader, area: Area) -> None:
    while True:
        tok = r.word()
        if tok in ("S", "#0", "#$") or tok.startswith("#"):
            if tok.startswith("#"):
                r.i -= len(tok)
            return
        if tok == "M":
            vnum = r.number()
            spec = r.word()
            r.rest_of_line()                           # a comment, or nothing
            proto = area.mob_protos.get(vnum)
            if proto is not None:
                proto["tags"].append(f"rom_spec:{spec}")
            spells = SPEC_CASTERS.get(spec)
            behavior = None
            if spells:
                behavior = {"behavior_id": "caster",
                            "params": {"spells": list(spells), "chance": 0.5}}
                note = ("caster behavior (spell list from ROM special.c; "
                        "import the merc-classic pack for the spell_defs)")
            elif spec in SPEC_BEHAVIORS:
                b = SPEC_BEHAVIORS[spec]
                behavior = {"behavior_id": b["behavior_id"],
                            "params": dict(b.get("params") or {})}
                note = f"{b['behavior_id']} behavior"
            if behavior is not None and proto is not None:
                # Like #SHOPS: resets ran first, so patch the placed
                # instances of this vnum as well as the prototype.
                for target in [proto, *(o for o in area.objects
                                        if o["attrs"].get("prototype_vnum")
                                        == vnum)]:
                    target["behaviors"].append(
                        {"behavior_id": behavior["behavior_id"],
                         "params": dict(behavior["params"])})
                area.gap(f"#SPECIALS ({spec}): mapped to the {note}")
            else:
                area.gap(f"#SPECIALS ({spec}): a compiled C spec_proc — no "
                         "REALM equivalent; tagged rom_spec:* for "
                         "hand-porting to softcode")
        else:
            r.line()


def _attach_spawners(area: Area) -> None:
    """--repop: for each room a mob reset into, attach a ``spawner`` that
    ADOPTS the statically-placed instances (tags them, seeds the spawner's
    tracking) so they respawn on death without duplicating the initial
    population. Shopkeepers are skipped — they are fixtures whose stock is
    their inventory, so respawning them (empty) would be wrong."""
    made = 0
    for (mob_v, room_v) in dict.fromkeys(area.mob_resets):   # unique, ordered
        proto = area.mob_protos.get(mob_v)
        room = area.rooms.get(room_v)
        if proto is None or room is None:
            continue
        if any(b["behavior_id"] == "shopkeeper" for b in proto["behaviors"]):
            continue                                         # keeper = fixture
        key = f"m{mob_v}"
        instances = [o for o in area.objects
                     if o["attrs"].get("prototype_vnum") == mob_v
                     and o.get("location") == f"rom_{room_v}"
                     and "npc" in o["tags"]]
        if not instances:
            continue
        for inst in instances:
            if f"spawned:{key}" not in inst["tags"]:
                inst["tags"].append(f"spawned:{key}")
        prototype = _instance_prototype(proto, mob_v)
        # ROM's repop re-runs the G and E resets after the M: a killed mob
        # comes back carrying, wearing and wielding what it did.
        prototype["contents"] = carried_prototypes(area.objects, instances[0]["id"])
        room["behaviors"].append({
            "behavior_id": "spawner",
            "params": {"key": key, "prototype": prototype,
                       "count": len(instances), "respawn_ticks": 20},
        })
        # Seed the spawner's tracking so it adopts (not duplicates) the
        # static instances: it respawns only after one is killed.
        room["attrs"][f"spawner_{key}_ids"] = [o["id"] for o in instances]
        room["attrs"][f"spawner_{key}_seeded"] = True
        made += 1
    if made:
        area.gap(f"--repop: {made} respawning mob spawners (killed mobs "
                 "return; shopkeepers stay static fixtures)")


def _attach_restockers(area: Area) -> None:
    """--repop: a room with floor-loot (O) resets gets a ``restock`` behavior,
    which snapshots its objects at boot and re-mints any that get taken. Shop
    wares restock via a keeper-side ``restock`` (attached in _shops)."""
    for room_v in area.obj_reset_rooms:
        room = area.rooms.get(room_v)
        if room is None:
            continue
        if not any(b["behavior_id"] == "restock" for b in room["behaviors"]):
            room["behaviors"].append({"behavior_id": "restock", "params": {}})


def _instance_prototype(proto: dict, vnum: int) -> dict:
    """A spawn prototype from a #MOBILES/#OBJECTS proto (drop the
    prototype tag; keep name/desc/tags/attrs/behaviors). What it spawns
    carries ``prototype_vnum``, as a reset-placed instance does, so a quest
    or a lock that names the vnum knows a respawn for the same mob."""
    return {
        "name": proto["name"],
        "description": proto["description"],
        "tags": [t for t in proto["tags"] if t != "prototype"],
        "attrs": {**proto["attrs"], "prototype_vnum": vnum},
        "behaviors": [dict(b) for b in proto["behaviors"]],
    }


def _attach_zone_reset(area: Area) -> None:
    """--zone-reset: one zone master carrying a ``zone_reset`` behavior whose
    ``reset_spec`` reloads the area's canonical mobs and floor objects when
    the zone empties of players (the SMAUG whole-area restore). The static
    instances are tagged with the master's reset marker so the first reset
    ADOPTS them (clears + reloads, no duplication)."""
    master_id = "rom_reset_master"
    marker = f"reset:{master_id}"
    spec: list[dict] = []

    def _entries(resets, protos, kind):
        counts: dict[tuple[int, int], int] = {}
        for vnum, room_v in resets:
            counts[(vnum, room_v)] = counts.get((vnum, room_v), 0) + 1
        for (vnum, room_v), count in counts.items():
            proto = protos.get(vnum)
            if proto is None or room_v not in area.rooms:
                continue
            prototype = _instance_prototype(proto, vnum)
            placed = [inst for inst in area.objects
                      if inst["attrs"].get("prototype_vnum") == vnum
                      and inst.get("location") == f"rom_{room_v}"
                      and kind in inst["tags"]]
            if placed:
                # A reset clears a mob (or a container) with what it holds and
                # reloads it with its G, E (or P) resets, as --repop's spawners do.
                prototype["contents"] = carried_prototypes(area.objects, placed[0]["id"])
            spec.append({"prototype": prototype, "room": f"rom_{room_v}", "count": count})
            for inst in placed:
                if marker not in inst["tags"]:
                    inst["tags"].append(marker)

    _entries(area.mob_resets, area.mob_protos, "npc")
    _entries(area.obj_resets, area.obj_protos, "thing")
    if not spec:
        return
    master = obj_record(
        master_id, f"{area.name} Reset",
        "The unseen hand that returns this area to its authored state.",
        ["zone_master", f"zone:{area_zone(area)}"],
        {"reset_interval": 300, "reset_spec": spec})
    master["behaviors"].append({"behavior_id": "zone_reset", "params": {}})
    area.objects.append(master)
    area.gap(f"--zone-reset: a zone master with {len(spec)} reset_spec entries "
             "(whole-area restore, presence-gated)")


def _finalize(area: Area) -> None:
    """Rooms and prototypes into the object list; doors into exit objects."""
    if area.zone_reset:
        _attach_zone_reset(area)       # restore strategy (excludes spawners)
    elif area.repop:
        _attach_spawners(area)         # after #SHOPS patched keeper protos
        _attach_restockers(area)
    doors = _door_flags(area)
    for vnum, room in area.rooms.items():
        exits = room.pop("_exits", [])
        area.objects.append(room)
        for ex in exits:
            if ex["to"] not in area.rooms:
                area.gap(f"exit from room {vnum} leads to vnum {ex['to']} "
                         "outside this area; emitted, resolves if that room "
                         "is imported alongside")
            name = DIRS[ex["dir"]][0] if ex["dir"] < len(DIRS) else \
                f"dir{ex['dir']}"
            tags = ["exit"]
            eattrs = {"destination": f"rom_{ex['to']}"}
            state = doors.get((vnum, ex["dir"]))
            if state is not None:
                tags.append("door")
                tags.extend(t for t in ("closed", "locked") if t in state)
                for flag in ("nopass", "pickproof"):
                    if flag in state:
                        area.gap(f"door flag {flag.upper()}: no equivalent; the door "
                                 "is closed and locked")
                if area.zone_reset:
                    # ROM's area reset sets every exit back to its reset
                    # flags; the zone master's reset puts these back.
                    eattrs["reset_tags"] = {"closed": "closed" in state,
                                            "locked": "locked" in state}
                elif "closed" in state:
                    area.gap("a door's state is set at boot only: nothing closes or "
                             "locks it again (ROM's area reset does; --zone-reset "
                             "puts doors back)")
            if ex["keywords"]:
                eattrs["keywords"] = ex["keywords"]
            if ex["desc"]:
                eattrs["look"] = ex["desc"]
            if ex["key"] and ex["key"] > 0:
                eattrs["key_id"] = key_token(ex["key"])
            area.objects.append(obj_record(
                f"rom_exit_{vnum}_{ex['dir']}", name, ex["desc"], tags,
                eattrs, location=f"rom_{vnum}"))
    # unplaced prototypes still ship, so a builder can @clone them
    for proto in list(area.mob_protos.values()) + list(area.obj_protos.values()):
        if proto not in area.objects:
            area.objects.append(proto)
    if pet_shops(area.objects):
        area.gap("ROOM_PET_SHOP: the room's shopkeeper sells the mobs reset into "
                 "the next room as pets (sells_pets, pet_stock)")


# --- summaries ---------------------------------------------------------------


def document(area: Area) -> dict[str, Any]:
    """The worldio document for ``area``."""
    return {"realm_format": 1, "objects": area.objects}


def counts(area: Area) -> dict[str, int]:
    """Rooms, exits, mob and object prototypes, placed instances."""
    return {
        "rooms": sum(1 for o in area.objects if "room" in o["tags"]),
        "exits": sum(1 for o in area.objects if "exit" in o["tags"]),
        "mob_protos": len(area.mob_protos),
        "obj_protos": len(area.obj_protos),
        "placed": sum(1 for o in area.objects
                      if o["attrs"].get("prototype_vnum") is not None),
    }


def summary(area: Area) -> str:
    c = counts(area)
    return (f"{area.name!r}: {c['rooms']} rooms, {c['exits']} exits, "
            f"{c['mob_protos']} mob protos, {c['obj_protos']} obj protos, "
            f"{c['placed']} placed instances")


def gap_lines(area: Area) -> list[str]:
    """The capability gaps and lossy mappings, most frequent first."""
    return [f"  ({count:4d}x) {msg}"
            for msg, count in sorted(area.gaps.items(), key=lambda kv: -kv[1])]


# --- many areas ------------------------------------------------------------------


def area_files(paths: list[Path]) -> list[Path]:
    """Each path as is when a file, else every ``*.are`` / ``*.are.txt``
    under it."""
    out: list[Path] = []
    for path in paths:
        if path.is_dir():
            for pattern in ("*.are", "*.are.txt"):
                out.extend(sorted(path.rglob(pattern)))
        else:
            out.append(path)
    return out


@dataclass
class TreeResult:
    """What ``convert_tree`` did: how many converted, and the parity report."""

    converted: int
    failed: int
    report: list[str]


def convert_tree(files: list[Path], out: Path | None, *, root: Path | None = None,
                 repop: bool = False, zone_reset: bool = False) -> TreeResult:
    """Convert every file, writing each area's JSON under ``out`` (its path
    relative to ``root``, else its name), and aggregate a MERC parity
    report: per-area stats and parse failures, each capability gap and how
    many areas hit it, the special procedures and item types with no MERC
    equivalent yet, and how many areas carry MOBprogs."""
    import traceback
    from collections import Counter

    ok = failed = mobprog_areas = 0
    totals: Counter[str] = Counter()
    gap_areas: Counter[str] = Counter()
    gap_totals: Counter[str] = Counter()
    specs: Counter[str] = Counter()
    item_types: Counter[str] = Counter()
    failures: list[tuple[str, str]] = []

    for path in files:
        rel = path.relative_to(root) if root is not None else Path(path.name)
        try:
            area = convert(path.read_text(errors="replace"),
                           repop=repop, zone_reset=zone_reset)
        except Exception as exc:                 # report, don't stop the batch
            failed += 1
            failures.append((str(rel), f"{type(exc).__name__}: {exc}"))
            traceback.print_exc(file=sys.stderr)
            continue
        ok += 1
        totals.update(counts(area))
        for msg, count in area.gaps.items():
            gap_areas[msg] += 1
            gap_totals[msg] += count
        if any("PROGS" in m for m in area.gaps):
            mobprog_areas += 1
        seen_specs: set[str] = set()
        for o in area.objects:
            for t in o["tags"]:
                if t.startswith("rom_spec:"):
                    name = t.split(":", 1)[1]
                    if name not in seen_specs:
                        specs[name] += 1
                        seen_specs.add(name)
            it = o["attrs"].get("item_type")
            if it and "prototype" in o["tags"]:
                item_types[it] += 1
        if out is not None:
            dest = (out / rel).with_suffix("")     # drop .txt
            if dest.suffix != ".json":
                dest = dest.with_suffix(".json")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(document(area), indent=2))

    report = _report(len(files), ok, failed, totals, gap_areas, gap_totals,
                     specs, item_types, mobprog_areas, failures)
    return TreeResult(ok, failed, report)


def _report(n, ok, failed, totals, gap_areas, gap_totals, specs, item_types,
            mobprog_areas, failures) -> list[str]:
    lines = ["# ROM -> REALM batch conversion & MERC parity report", "",
             f"Converted **{ok}/{n}** area files"
             + (f" ({failed} failed)" if failed else "") + ". World totals: "
             f"**{totals['rooms']} rooms, {totals['exits']} exits, "
             f"{totals['mob_protos']} mob prototypes, {totals['obj_protos']} "
             f"object prototypes, {totals['placed']} placed instances**.", ""]

    lines += ["## Capability gaps, by how many areas hit them", "",
              "| areas | occurrences | gap |", "|---:|---:|---|"]
    for msg, areas in gap_areas.most_common():
        lines.append(f"| {areas} | {gap_totals[msg]} | {msg} |")

    lines += ["", "## ROM special procedures found (no MERC equivalent)", "",
              f"{sum(specs.values())} spec-proc attachments across "
              f"{len(specs)} distinct procedures. Each is a compiled C behavior "
              "that must be re-authored as softcode or a behavior:", "",
              "| areas | spec_proc |", "|---:|---|"]
    for name, areas in specs.most_common(40):
        lines.append(f"| {areas} | `{name}` |")
    if mobprog_areas:
        lines += ["", f"Plus **{mobprog_areas}** areas carry MOBprogs/OBJprogs "
                  "(ROM's trigger scripting) — skipped, portable to softcode."]

    lines += ["", "## Object item types seen (parity of the item model)", "",
              "| count | item type | MERC status |", "|---:|---|---|"]
    known = {"weapon", "armor", "light", "food", "drink", "drink_container",
             "container", "key", "money", "potion", "scroll", "wand", "staff",
             "treasure", "clothing", "trash", "furniture", "fountain", "pill",
             "jewelry", "boat"}
    for it, count in item_types.most_common():
        status = "modeled (tag + attrs)" if it in known else "**no MERC hook**"
        lines.append(f"| {count} | `{it}` | {status} |")

    if failures:
        lines += ["", "## Parse failures", ""]
        for name, err in failures:
            lines.append(f"- `{name}` — {err}")
    return lines
