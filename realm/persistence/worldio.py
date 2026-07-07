"""
World import/export: areas as files.

``export_objects`` turns live objects into a JSON-safe dict (softcode
travels free — it's just string attributes); ``import_objects``
recreates them with FRESH ids, deep-remapping every reference —
location/owner/parent links AND id-bearing attribute values (exit
``destination``, spawner tracking lists) — so an area file merges into
any world without collisions. Passwords are always stripped; players
are excluded unless asked for (whole-world backup = copy the SQLite
file instead).

CLI: ``realm export area.realm [--zone castle]`` / ``realm import
area.realm`` (JSON content; the extension is convention).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

FORMAT_VERSION = 1
STRIPPED_ATTRS = {'password'}


def export_objects(objects: list[GameObject]) -> dict:
    """Serialize objects (refs by their current ids)."""
    payload = []
    for obj in objects:
        attrs = {k: v for k, v in obj.db.all().items()
                 if k not in STRIPPED_ATTRS}
        payload.append({
            'id': obj.id,
            'name': obj.name,
            'description': obj.description,
            'tags': obj.tags.to_list(),
            'attrs': attrs,
            'locks': dict(obj.locks),
            'behaviors': [b.to_dict() for b in obj.get_behaviors()],
            'location': obj.location.id if obj.location else None,
            'owner': obj.owner.id if obj.owner else None,
            'parent': obj.parent.id if obj.parent else None,
        })
    return {'realm_format': FORMAT_VERSION, 'objects': payload}


def export_zone(zone: str) -> dict:
    """Export a zone's rooms, their contents, and its masters."""
    from realm.core.zones import zone_masters, zone_rooms

    rooms = zone_rooms(zone)
    seen: dict[str, GameObject] = {}
    for room in rooms:
        seen[room.id] = room
        for obj in room.contents:
            if not obj.has_tag('player'):
                seen[obj.id] = obj
        for master in zone_masters(room):
            seen[master.id] = master
    return export_objects(list(seen.values()))


def _remap_value(value: Any, id_map: dict[str, str]) -> Any:
    """Deep-walk JSON data, rewriting any string that IS an exported id."""
    if isinstance(value, str):
        return id_map.get(value, value)
    if isinstance(value, list):
        return [_remap_value(v, id_map) for v in value]
    if isinstance(value, dict):
        return {k: _remap_value(v, id_map) for k, v in value.items()}
    return value


async def import_objects(data: dict, persistence) -> list[GameObject]:
    """
    Recreate exported objects with fresh ids. References to ids OUTSIDE
    the file resolve against the live world when present (an area whose
    rooms link back to an existing hub keeps working) and drop to None
    otherwise.
    """
    from realm.core.behaviors import BehaviorRegistry
    from realm.core.objects import GameObject as GameObjectCls

    if int(data.get('realm_format', 0)) > FORMAT_VERSION:
        raise ValueError("Area file is from a newer REALM — upgrade first.")

    entries = data.get('objects') or []
    id_map = {e['id']: str(uuid.uuid4()) for e in entries}

    # Pass 1: create everything (fresh ids, remapped attrs).
    created: dict[str, GameObject] = {}
    for entry in entries:
        obj = GameObjectCls(
            id=id_map[entry['id']],
            name=str(entry.get('name', 'thing')),
            description=str(entry.get('description', '')),
            tags=list(entry.get('tags') or []),
        )
        for key, value in (entry.get('attrs') or {}).items():
            if key in STRIPPED_ATTRS:
                continue
            obj.db.set(key, _remap_value(value, id_map))
        obj.locks.update(entry.get('locks') or {})
        for spec in entry.get('behaviors') or []:
            behavior = BehaviorRegistry.from_dict(spec)
            if behavior is not None:
                obj.add_behavior(behavior)
        created[obj.id] = obj

    def resolve(old_id):
        if not old_id:
            return None
        if old_id in id_map:
            return created[id_map[old_id]]
        return persistence.get_cached(old_id) if persistence else None

    # Pass 2: references, then persist.
    results = []
    for entry in entries:
        obj = created[id_map[entry['id']]]
        obj.location = resolve(entry.get('location'))
        obj.owner = resolve(entry.get('owner'))
        obj.parent = resolve(entry.get('parent'))
        if persistence is not None:
            await persistence.save(obj)
        results.append(obj)
    return results


__all__ = ["FORMAT_VERSION", "export_objects", "export_zone", "import_objects"]
