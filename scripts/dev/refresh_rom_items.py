"""
Re-derive the item fields the ROM importer writes (wear slot, consumables)
on an already-converted area file, from the ``item_type``, ``rom_wear``
and ``rom_values`` each object keeps.

For a converted area whose ``.are`` source is not at hand (the shipped
Midgaard): after the importer learns a new mapping, this brings the file up
to date without a re-conversion, and leaves every other field alone.

    python scripts/dev/refresh_rom_items.py realm/examples/midgaard/data/areas/midgaard.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from realm.tools.rom_import import Area, consumable_fields, gap_lines, rom_flags, wear_slot


def refresh(data: dict) -> tuple[int, Area]:
    """Update ``data`` in place; returns how many objects changed."""
    area = Area()
    changed = 0
    for obj in data["objects"]:
        attrs = obj.get("attrs") or {}
        type_name = attrs.get("item_type")
        if type_name is None or "rom_values" not in attrs:
            continue
        before = json.dumps(obj, sort_keys=True)
        tags = obj.setdefault("tags", [])
        slot = wear_slot(type_name, rom_flags("".join(attrs.get("rom_wear") or [])))
        if slot:
            attrs["slot"] = slot
            if "wearable" not in tags:
                tags.append("wearable")
        extra_tags, fields = consumable_fields(type_name, attrs["rom_values"], area)
        tags.extend(t for t in extra_tags if t not in tags)
        attrs.update(fields)
        obj["attrs"] = attrs
        changed += json.dumps(obj, sort_keys=True) != before
    return changed, area


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    path = Path(argv[0])
    data = json.loads(path.read_text())
    changed, area = refresh(data)
    path.write_text(json.dumps(data, indent=1))     # the converter's own format
    print(f"{path}: {changed} objects updated")
    for line in gap_lines(area):
        print(f"  gap: {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
