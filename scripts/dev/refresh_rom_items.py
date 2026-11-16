"""
Re-derive the fields the ROM importer writes for objects (wear slot, a
weapon's damage type, consumables, the ``magic`` and ``anti_*`` tags), mobs
(the trainer behavior, the special procedures' behavior parameters, money,
an ``ACT_SCAVENGER`` that picks up instead of eating corpses; an object that
took a mob's shop, sharing its vnum, loses it)
and rooms (``lamplit`` city streets, ``no_recall``, a ``ROOM_PET_SHOP``'s
keeper selling the next room's mobs as pets, a spawner's mob knowing its
vnum)
on an already-converted area file, from the ``item_type``, ``rom_wear``,
``rom_values``, ``rom_extra``, ``rom_act``, ``rom_room_flags`` and
``rom_spec:*`` tags each object keeps.

For a converted area whose ``.are`` source is not at hand (the shipped
Midgaard): after the importer learns a new mapping, this brings the file up
to date without a re-conversion, and leaves every other field alone.

    python scripts/dev/refresh_rom_items.py realm/examples/midgaard/data/areas/midgaard.json

A room flag the stored file lost can be given back first, as ROM letters:
``--room-flags 3031=M`` (Midgaard was converted with its room flags empty;
3031 is its pet shop, ROM's ``ROOM_PET_SHOP``).
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
    gap_lines,
    item_fields,
    item_flag_tags,
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
        attrs = obj.get("attrs") or {}
        tags = obj.get("tags", [])
        if "room" in tags and attrs.get("sector"):
            changed += _spawn_vnums(obj)
            changed += _add_tags(tags, room_light_tags(str(attrs["sector"])))
            changed += _add_tags(tags, room_flag_tags(attrs.get("rom_room_flags") or []))
            continue
        if "npc" in obj.get("tags", []) and "rom_act" in attrs:
            changed += _refresh_mob(obj)
            changed += _act_scavenger(obj)
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
    return changed, area


def main(argv: list[str]) -> int:
    flags: dict[int, str] = {}
    args = list(argv)
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
    restored = restore_room_flags(data, flags)
    changed, area = refresh(data)
    changed += restored
    path.write_text(json.dumps(data, indent=1))     # the converter's own format
    print(f"{path}: {changed} objects updated")
    for line in gap_lines(area):
        print(f"  gap: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
