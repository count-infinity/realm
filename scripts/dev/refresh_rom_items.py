"""
Re-derive the fields the ROM importer writes for objects (wear slot, a
weapon's damage type, consumables, the ``magic`` and ``anti_*`` tags), mobs
(the trainer behavior, the special procedures' behavior parameters, money,
an ``ACT_SCAVENGER`` that picks up instead of eating corpses, an
``ACT_AGGRESSIVE`` and ``ACT_WIMPY`` mob that is not ``aggressive``, since
ROM's attacks only the sleeping; an object that
took a mob's shop, sharing its vnum, loses it), names (a mob or object
named by its ROM keywords, its short description kept as ``short_desc``,
is named by the short description and answers to the keywords as
``aliases``, spawners' mobs too)
rooms (``lamplit`` city streets, ``no_recall``, a ``ROOM_PET_SHOP``'s
keeper selling the next room's mobs as pets, a spawner's mob knowing its
vnum and coming back with what the placed mob carries) and a mob's E-reset
gear (worn and wielded, as a player's is, not a ``worn`` attribute),
doors and keys (an exit's ``key_id``, a key's ``unlocks``, not the exit's
``key`` nothing read) on an already-converted area file, from the ``item_type``, ``rom_wear``,
``rom_values``, ``rom_extra``, ``rom_act``, ``rom_room_flags`` and
``rom_spec:*`` tags each object keeps.

After the importer learns a new mapping, this brings a converted file up to
date without a re-conversion, and leaves every other field alone.

    python scripts/dev/refresh_rom_items.py area.json

What the source file lost can be given back first. A room flag, as ROM
letters: ``--room-flags 3031=M`` (3031 is Midgaard's pet shop, ROM's
``ROOM_PET_SHOP``). A magic item's spells, by vnum (several vnums comma
separated, several spells joined by ``+``): ``--spells 3083,3283="cure
light"`` writes them into the item's ``rom_values`` as a ROM 2.4 file
names them, so every later refresh keeps them. The shipped Midgaard is
made this way (docs/development/rom-import.md, "The shipped Midgaard").
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from realm.tools.rom_import import (
    CONSUMABLE_TYPES,
    RETIRED_CONSUMABLE_FIELDS,
    SPEC_BEHAVIORS,
    Area,
    carried_prototypes,
    equip_record,
    gap_lines,
    item_fields,
    item_flag_tags,
    key_token,
    keywords,
    mob_money,
    pet_shops,
    rom_flags,
    room_flag_tags,
    room_light_tags,
    scavenger_behavior,
    trainer_behavior,
    wear_slot,
)


def _add_tags(tags: list[str], new: list[str]) -> int:
    added = [t for t in new if t not in tags]
    tags.extend(added)
    return len(added)


def _refresh_mob(obj: dict) -> int:
    """Money from the raw wealth, and each mapped special procedure's
    behavior parameters as the importer writes them now."""
    attrs = obj.setdefault("attrs", {})
    changed = 0
    if "gold" in attrs:                     # converted before MUD_PLAN step 11
        attrs["rom_wealth"] = attrs.pop("gold")
        attrs["credits"] = mob_money(attrs["rom_wealth"])
        changed += 1
    behaviors = obj.setdefault("behaviors", [])
    for tag in obj.get("tags", []):
        mapped = SPEC_BEHAVIORS.get(tag.removeprefix("rom_spec:")) \
            if tag.startswith("rom_spec:") else None
        if mapped is None:
            continue
        for behavior in behaviors:
            if isinstance(behavior, dict) and \
                    behavior.get("behavior_id") == mapped["behavior_id"] and \
                    behavior.get("params") != mapped["params"]:
                behavior["params"] = dict(mapped["params"])
                changed += 1
    return changed


def _act_scavenger(mob: dict) -> int:
    """An ``ACT_SCAVENGER`` mob picks things up and eats no corpse (before
    MUD_PLAN step 17 its scavenger had the defaults, which devour corpses)."""
    if "C" not in (mob.get("attrs") or {}).get("rom_act", []):
        return 0
    changed = 0
    for behavior in mob.get("behaviors", []):
        if behavior.get("behavior_id") == "scavenger" and not behavior.get("params"):
            behavior["params"] = dict(scavenger_behavior()["params"])
            changed += 1
    return changed


def _wimpy_aggressor(mob: dict) -> int:
    """An ``ACT_AGGRESSIVE`` mob that is also ``ACT_WIMPY`` attacks only the
    sleeping in ROM, so it is not ``aggressive`` (before 2026-11-17 the
    beastly fido jumped everyone)."""
    act = (mob.get("attrs") or {}).get("rom_act", [])
    if "F" not in act or "H" not in act:
        return 0
    behaviors = mob.get("behaviors", [])
    kept = [b for b in behaviors if b.get("behavior_id") != "aggressive"]
    if len(kept) == len(behaviors):
        return 0
    mob["behaviors"] = kept
    return 1


def _spawn_vnums(room: dict) -> int:
    """What a room's spawner brings back carries ``prototype_vnum``, as the
    placed mob does (before MUD_PLAN step 17 a respawn had none), and the
    behaviors the mob it copies has now."""
    changed = 0
    for behavior in room.get("behaviors", []):
        if behavior.get("behavior_id") != "spawner":
            continue
        prototype = behavior.get("params", {}).get("prototype", {})
        attrs = prototype.get("attrs")
        if attrs is not None and "prototype_vnum" not in attrs and "rom_vnum" in attrs:
            attrs["prototype_vnum"] = attrs["rom_vnum"]
            changed += 1
        changed += _act_scavenger(prototype)
        changed += _wimpy_aggressor(prototype)
    return changed


def _equip(obj: dict, area: Area) -> int:
    """Gear an E reset gave before 2026-11-17 carried a ``worn`` attribute
    naming its ROM wear location; it is worn or wielded now."""
    wear_loc = (obj.get("attrs") or {}).pop("worn", None)
    if wear_loc is None:
        return 0
    if not equip_record(obj, str(wear_loc)):
        area.gap(f"reset E (equipped gear): wear location {wear_loc!r} has no "
                 "Merc slot; the item is carried, not worn")
    return 1


def _spawn_gear(room: dict, objects: list[dict]) -> int:
    """A room spawner's mob comes back with what the first mob it adopted
    carries (before 2026-11-17 a respawn came back empty-handed)."""
    changed = 0
    for behavior in room.get("behaviors", []):
        if behavior.get("behavior_id") != "spawner":
            continue
        params = behavior.get("params", {})
        prototype = params.get("prototype", {})
        adopted = (room.get("attrs") or {}).get(f"spawner_{params.get('key')}_ids") or []
        if "contents" in prototype or not adopted:
            continue
        prototype["contents"] = carried_prototypes(objects, adopted[0])
        changed += 1
    return changed


def _rom_names(obj: dict) -> int:
    """A thing named by its ROM keywords, with its short description kept
    as ``short_desc`` (the importer before 2026-11-16), is named by the
    short description and answers to the keywords."""
    attrs = obj.get("attrs")
    if not attrs or "short_desc" not in attrs:
        return 0
    short = str(attrs.pop("short_desc") or "").strip()
    listed = str(obj.get("name") or "")
    aliases = attrs.setdefault("aliases", [])
    aliases.extend(a for a in keywords(listed) if a not in aliases)
    obj["name"] = short or listed
    return 1


def _records(objects: list[dict]):
    """Every object record in a converted file: the objects, and the
    prototypes (and their ``contents``) its spawners and zone resets make."""
    stack = list(objects)
    while stack:
        record = stack.pop(0)
        yield record
        stack.extend(record.get("contents") or [])
        for behavior in record.get("behaviors") or []:
            prototype = (behavior.get("params") or {}).get("prototype") \
                if isinstance(behavior, dict) else None
            if prototype:
                stack.append(prototype)
        for entry in (record.get("attrs") or {}).get("reset_spec") or []:
            if entry.get("prototype"):
                stack.append(entry["prototype"])


def _door_keys(objects: list[dict]) -> int:
    """A converted door names its key in ``key_id`` and a key what it opens
    in ``unlocks``, which ``lock`` and ``unlock`` match (before 2026-11-17
    the exit's ``key`` named it and nothing read it): every ``key``-type
    object, and any other object a door names, unlocks ``rom_obj_<vnum>``."""
    changed = 0
    named: set[str] = set()
    for obj in objects:
        attrs = obj.get("attrs") or {}
        if "exit" in obj.get("tags", []) and "key" in attrs:
            attrs["key_id"] = attrs.pop("key")
            changed += 1
        if "exit" in obj.get("tags", []) and attrs.get("key_id"):
            named.add(str(attrs["key_id"]))
    for record in _records(objects):
        attrs = record.get("attrs") or {}
        vnum = attrs.get("rom_vnum")
        # Mobs and rooms share the vnum space: only an object is a key.
        if vnum is None or "unlocks" in attrs or "thing" not in record.get("tags", []):
            continue
        if attrs.get("item_type") == "key" or key_token(vnum) in named:
            # Where a conversion writes it: with the prototype's own fields,
            # before what a placed copy gains (``prototype_vnum``).
            fields = list(attrs.items())
            attrs.clear()
            for name, value in fields:
                if name == "prototype_vnum":
                    attrs["unlocks"] = key_token(vnum)
                attrs[name] = value
            attrs.setdefault("unlocks", key_token(vnum))
            changed += 1
    return changed


#: Where a ROM 2.4 magic item names its spells (``load_objects``).
SPELL_VALUES = {"potion": (1, 4), "pill": (1, 4), "scroll": (1, 4),
                "wand": (3, 1), "staff": (3, 1)}


def restore_spells(data: dict, spells: dict[int, list[str]]) -> int:
    """Write spell names into the ``rom_values`` of the magic items whose
    vnum (``rom_vnum``) is given (``{3083: ["cure light"]}``); returns how
    many objects changed. Raises ``ValueError`` for more spells than the
    item type holds."""
    changed = 0
    for obj in data["objects"]:
        attrs = obj.get("attrs") or {}
        wanted = spells.get(attrs.get("rom_vnum"))
        place = SPELL_VALUES.get(attrs.get("item_type"))
        if wanted is None or place is None or "rom_values" not in attrs:
            continue
        first, room = place
        if len(wanted) > room:
            raise ValueError(f"vnum {attrs['rom_vnum']} ({attrs['item_type']}) holds "
                             f"{room} spell(s), not {len(wanted)}")
        values = list(attrs["rom_values"]) + [0] * (5 - len(attrs["rom_values"]))
        for i in range(room):
            values[first + i] = wanted[i] if i < len(wanted) else 0
        if values != attrs["rom_values"]:
            attrs["rom_values"] = values
            changed += 1
    return changed


def restore_room_flags(data: dict, flags: dict[int, str]) -> int:
    """Add ROM room-flag letters to ``rom_room_flags`` by vnum (``{3031: "M"}``)."""
    changed = 0
    for obj in data["objects"]:
        attrs = obj.get("attrs") or {}
        letters = flags.get(attrs.get("rom_vnum")) if "room" in obj.get("tags", []) else None
        for letter in letters or "":
            stored = attrs.setdefault("rom_room_flags", [])
            if letter not in stored:
                stored.append(letter)
                changed += 1
    return changed


def refresh(data: dict) -> tuple[int, Area]:
    """Update ``data`` in place; returns how many objects changed."""
    area = Area()
    changed = pet_shops(data["objects"])
    for obj in data["objects"]:
        changed += _equip(obj, area)
    for obj in data["objects"]:
        attrs = obj.get("attrs") or {}
        tags = obj.get("tags", [])
        if "room" in tags and attrs.get("sector"):
            for behavior in obj.get("behaviors", []):
                prototype = behavior.get("params", {}).get("prototype") \
                    if behavior.get("behavior_id") == "spawner" else None
                changed += _rom_names(prototype) if prototype else 0
            changed += _spawn_vnums(obj)
            changed += _add_tags(tags, room_light_tags(str(attrs["sector"])))
            changed += _add_tags(tags, room_flag_tags(attrs.get("rom_room_flags") or []))
            continue
        for entry in attrs.get("reset_spec") or [] if "zone_master" in tags else []:
            changed += _rom_names(entry.get("prototype") or {})
        if "npc" in obj.get("tags", []) and "rom_act" in attrs:
            changed += _rom_names(obj)
            changed += _refresh_mob(obj)
            changed += _act_scavenger(obj)
            changed += _wimpy_aggressor(obj)
            trainer = trainer_behavior(attrs["rom_act"])
            behaviors = obj.setdefault("behaviors", [])
            if trainer is not None and not any(
                    isinstance(b, dict) and b.get("behavior_id") == "trainer"
                    for b in behaviors):
                behaviors.append(trainer)
                changed += 1
            continue
        type_name = attrs.get("item_type")
        if type_name is None or "rom_values" not in attrs:
            continue
        before = json.dumps(obj, sort_keys=True)
        _rom_names(obj)
        # An object whose vnum was a shopkeeper's took its shop (before
        # MUD_PLAN step 17, #SHOPS matched objects as well as mobs).
        if attrs.pop("rom_shop_buys", None) is not None:
            obj["behaviors"] = [b for b in obj.get("behaviors", [])
                                if b.get("behavior_id") not in ("shopkeeper", "restock")]
        tags = obj.setdefault("tags", [])
        slot = wear_slot(type_name, rom_flags("".join(attrs.get("rom_wear") or [])))
        if slot:
            attrs["slot"] = slot
            if "wearable" not in tags:
                tags.append("wearable")
        if type_name in CONSUMABLE_TYPES:          # food and drink before step 12
            for retired in RETIRED_CONSUMABLE_FIELDS:
                attrs.pop(retired, None)
        extra_tags, fields = item_fields(type_name, attrs["rom_values"], area)
        extra_tags = [*extra_tags, *item_flag_tags(attrs.get("rom_extra") or [])]
        tags.extend(t for t in extra_tags if t not in tags)
        attrs.update(fields)
        obj["attrs"] = attrs
        changed += json.dumps(obj, sort_keys=True) != before
    changed += _door_keys(data["objects"])
    for obj in data["objects"]:              # last: a respawn copies the gear as it is now
        if "room" in obj.get("tags", []):
            changed += _spawn_gear(obj, data["objects"])
    return changed, area


def _spells_arg(text: str) -> dict[int, list[str]] | None:
    """``3083,3283=cure light`` -> ``{3083: ["cure light"], 3283: [...]}``;
    ``a+b`` is two spells. None when it does not read so."""
    vnums, _, names = text.partition("=")
    spells = [name.strip() for name in names.split("+") if name.strip()]
    numbers = [v.strip() for v in vnums.split(",")]
    if not spells or not all(n.isdigit() for n in numbers):
        return None
    return {int(n): spells for n in numbers}


def main(argv: list[str]) -> int:
    flags: dict[int, str] = {}
    spells: dict[int, list[str]] = {}
    args = list(argv)
    while "--spells" in args:
        at = args.index("--spells")
        given = _spells_arg(args[at + 1]) if at + 1 < len(args) else None
        if given is None:
            print(__doc__)
            return 2
        spells.update(given)
        del args[at:at + 2]
    while "--room-flags" in args:
        at = args.index("--room-flags")
        vnum, _, letters = (args[at + 1] if at + 1 < len(args) else "").partition("=")
        if not vnum.isdigit() or not letters:
            print(__doc__)
            return 2
        flags[int(vnum)] = flags.get(int(vnum), "") + letters
        del args[at:at + 2]
    if len(args) != 1:
        print(__doc__)
        return 2
    path = Path(args[0])
    data = json.loads(path.read_text())
    restored = restore_room_flags(data, flags) + restore_spells(data, spells)
    changed, area = refresh(data)
    changed += restored
    path.write_text(json.dumps(data, indent=1))     # the converter's own format
    print(f"{path}: {changed} objects updated")
    for line in gap_lines(area):
        print(f"  gap: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
