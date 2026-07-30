#!/usr/bin/env python3
"""
ROM 2.4 ``.are`` -> REALM area (worldio JSON) converter.

ROM/Merc area files are section-based: each section opens with a ``#NAME``
line and records are keyed by ``#vnum``, strings are tilde-terminated, and
bit-vectors are written either as decimal numbers or ROM letter-flags
(``A``=bit0, ``B``=bit1, ... ``Z``=bit25, ``aa``=bit26 ...). This tool reads
the standard sections and emits a REALM worldio document
(``{"realm_format": 1, "objects": [...]}``) that ``@import`` /
``realm import`` / ``import_objects`` load like any area.

    python scripts/rom_import.py midgaard.are > midgaard.area.json
    python scripts/rom_import.py midgaard.are -o midgaard.area.json --report

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

import argparse
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

# ROM wear-flag letters (bit -> slot). Bit A(0)=take, then wear locations.
WEAR_SLOTS = {
    1: "finger", 2: "neck", 3: "body", 4: "head", 5: "legs", 6: "feet",
    7: "hands", 8: "arms", 9: "shield", 10: "about", 11: "waist",
    12: "wrist", 13: "wield", 14: "hold", 16: "float",
}

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
    e.g. room flags ``CDS`` -> ``['C','D','S']``. Numbers return []."""
    token = token.strip()
    if not token or token.lstrip("-").isdigit():
        return []
    return [c for c in token if c.isalpha()]


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


def convert(text: str) -> Area:
    r = Reader(text)
    area = Area()
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
        attrs: dict[str, Any] = {
            "rom_vnum": vnum,
            "short_desc": short,
            "long_desc": long_,
            "level": level,
            "alignment": align,
            "sex": sex,
            "gold": wealth,
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
        area.mob_protos[vnum] = obj_record(
            f"rom_mob_{vnum}", name, look, tags, attrs)


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
        wslot = next((s for b, s in WEAR_SLOTS.items()
                      if (wear_bits >> b) & 1 and s not in ("wield", "hold")),
                     None)
        if wslot:
            tags.append("wearable")
        attrs: dict[str, Any] = {
            "rom_vnum": vnum, "short_desc": short,
            "item_type": type_name, "weight": weight, "value": cost,
            "level": level, "rom_values": values,
            "rom_extra": flag_letters(extra), "rom_wear": flag_letters(wear),
        }
        if wslot:
            attrs["slot"] = wslot
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
        area.obj_protos[vnum] = obj_record(
            f"rom_obj_{vnum}", name, look, tags, attrs)


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
        room["tags"].append(f"sector:{SECTORS.get(sector, sector)}")
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
    last_mob_iid: str | None = None
    while True:
        letter = r.word()
        if letter in ("S", "#0", "#$") or letter.startswith("#"):
            if letter.startswith("#") and letter not in ("#0", "#$"):
                r.i -= len(letter)
            return
        r.number()                                     # if-flag (unused, 0)
        if letter == "M":
            mob_v = r.number()
            r.number()
            room_v = r.number()
            r.number()
            last_mob_iid = _place_mob(area, mob_v, room_v)
        elif letter == "O":
            obj_v = r.number()
            r.number()
            room_v = r.number()
            r.number()
            _place_obj(area, obj_v, room_v)
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
            r.number()
            r.number()
            r.number()         # room door state
            area.gap("reset D (door open/closed/locked state): applied as "
                     "the exit's initial lock tags where possible")
        elif letter == "R":
            r.line()
            area.gap("reset R (randomize exits) has no static equivalent; "
                     "the exits are emitted in their authored order")
        else:
            r.line()


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
    # into_v is a vnum in ROM; we target the most-recent instance of it.
    target = next((o for o in reversed(area.objects)
                   if o["attrs"].get("prototype_vnum") == into_iid_or_vnum),
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


def _equip_mob(area: Area, obj_v: int, mob_iid: str | None,
               wear: int) -> str | None:
    inst = _clone_proto(area, area.obj_protos, obj_v, "object")
    if inst is None:
        return None
    inst["location"] = mob_iid
    inst["attrs"]["worn"] = WEAR_LOC.get(wear, str(wear))
    area.gap("reset E (equipped gear): item placed in the mob's inventory "
             "with a 'worn' attr; REALM auto-equip on spawn is not modeled")
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
        # The keeper is every spawned instance of this vnum, not just the
        # prototype — resets ran first, so patch the placed instances too.
        for target in [proto, *(o for o in area.objects
                                if o["attrs"].get("prototype_vnum") == keeper)]:
            target["behaviors"].append(dict(behavior))
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
            r.line()
            proto = area.mob_protos.get(vnum)
            if proto is not None:
                proto["tags"].append(f"rom_spec:{spec}")
            spells = SPEC_CASTERS.get(spec)
            if spells and proto is not None:
                behavior = {"behavior_id": "caster",
                            "params": {"spells": list(spells), "chance": 0.5}}
                # Like #SHOPS: resets ran first, so patch the placed
                # instances of this vnum as well as the prototype.
                for target in [proto, *(o for o in area.objects
                                        if o["attrs"].get("prototype_vnum")
                                        == vnum)]:
                    target["behaviors"].append(dict(behavior))
                area.gap(f"#SPECIALS ({spec}): mapped to the caster behavior "
                         "(spell list from ROM special.c; import the "
                         "merc-classic pack for the spell_defs)")
            else:
                area.gap(f"#SPECIALS ({spec}): a compiled C spec_proc — no "
                         "REALM equivalent; tagged rom_spec:* for "
                         "hand-porting to softcode")
        else:
            r.line()


def _finalize(area: Area) -> None:
    """Rooms and prototypes into the object list; doors into exit objects."""
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
            if ex["locks"]:
                tags.append("door")
                if ex["locks"] >= 2:
                    tags.append("closed")
            eattrs = {"destination": f"rom_{ex['to']}"}
            if ex["keywords"]:
                eattrs["keywords"] = ex["keywords"]
            if ex["desc"]:
                eattrs["look"] = ex["desc"]
            if ex["key"] and ex["key"] > 0:
                eattrs["key"] = f"rom_obj_{ex['key']}"
            area.objects.append(obj_record(
                f"rom_exit_{vnum}_{ex['dir']}", name, ex["desc"], tags,
                eattrs, location=f"rom_{vnum}"))
    # unplaced prototypes still ship, so a builder can @clone them
    for proto in list(area.mob_protos.values()) + list(area.obj_protos.values()):
        if proto not in area.objects:
            area.objects.append(proto)


# --- CLI ---------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("area_file", help="path to a ROM .are file")
    ap.add_argument("-o", "--output", help="write JSON here (default: stdout)")
    ap.add_argument("--report", action="store_true",
                    help="print a capability-gap report to stderr")
    args = ap.parse_args(argv)

    text = Path(args.area_file).read_text(errors="replace")
    area = convert(text)
    doc = {"realm_format": 1, "objects": area.objects}
    out = json.dumps(doc, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(out)
    else:
        sys.stdout.write(out)

    rooms = sum(1 for o in area.objects if "room" in o["tags"])
    exits = sum(1 for o in area.objects if "exit" in o["tags"])
    mobs = len(area.mob_protos)
    objs = len(area.obj_protos)
    placed = sum(1 for o in area.objects
                 if o["attrs"].get("prototype_vnum") is not None)
    print(f"[rom_import] {area.name!r}: {rooms} rooms, {exits} exits, "
          f"{mobs} mob protos, {objs} obj protos, {placed} placed instances",
          file=sys.stderr)
    if args.report and area.gaps:
        print("\n[rom_import] capability gaps / lossy mappings:", file=sys.stderr)
        for msg, count in sorted(area.gaps.items(), key=lambda kv: -kv[1]):
            print(f"  ({count:4d}x) {msg}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
