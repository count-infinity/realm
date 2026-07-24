"""
World import/export: areas as files.

Two flavours, for two jobs:

- **Clone** (``import_objects``): recreate the file's objects with FRESH
  ids. For distributing a reusable module — three taverns from one file.
  Never collides on ids; re-importing makes independent copies. A friendly
  keyid (unique by definition) carries over only when free — a copy of a
  keyed object lands keyless, reported, never merged.

- **Sync** (``diff_plan`` → ``apply_plan``): keep an area's live objects
  matching the file, matched by their STABLE ids. The builder-iteration
  loop — export from dev, tweak, re-import; the live area tracks the
  file, idempotently. Object ids are UUIDs, so a match is always "the
  same object re-imported", never an accidental collision — which is
  what makes overwrite safe. Terraform-shaped: plan (a dry-run diff)
  then apply.

Softcode travels free (it's just string attributes). Passwords are
always stripped; players are excluded from zone export (whole-world
backup = copy the SQLite file). Area membership is computed, never
tagged: rooms by their ``zone:`` tag, contents by location in an area
room.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1
STRIPPED_ATTRS = {'password'}

# Object fields a sync diff compares (refs are compared as ids).
_DIFF_FIELDS = ('name', 'description', 'tags', 'attrs', 'locks',
                'behaviors', 'location', 'owner', 'parent')


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
    """Deep-walk JSON data, rewriting any string that IS an exported id —
    bare (``<uuid>``) or reference-form (``#<uuid>``), so a stored handle
    like a door's ``partner`` re-wires to the copy on a fresh-id import
    whichever way the builder stored it."""
    if isinstance(value, str):
        if value.startswith('#') and value[1:] in id_map:
            return '#' + id_map[value[1:]]
        return id_map.get(value, value)
    if isinstance(value, list):
        return [_remap_value(v, id_map) for v in value]
    if isinstance(value, dict):
        return {k: _remap_value(v, id_map) for k, v in value.items()}
    return value


async def import_objects(data: dict, persistence, *,
                         preserve_ids: bool = False) -> list[GameObject]:
    """
    Recreate exported objects. By default each gets a **fresh id** (a clone
    — so the same area can be imported repeatedly as copies); reference
    fields are remapped to match. References to ids OUTSIDE the file resolve
    against the live world when present (an area whose rooms link back to an
    existing hub keeps working) and drop to None otherwise.

    ``preserve_ids=True`` keeps each object's authored id instead. Use it
    for a canonical first-boot load of a fixed world: it's the only way
    softcode that hardcodes an absolute id (``get('#nexagen_floor46')``)
    keeps working, since ids embedded *inside* a softcode string are not
    remapped. The caller must ensure the ids don't collide with the live
    world (i.e. an empty or non-overlapping database).
    """
    from realm.core.behaviors import BehaviorRegistry
    from realm.core.objects import GameObject as GameObjectCls

    if int(data.get('realm_format', 0)) > FORMAT_VERSION:
        raise ValueError("Area file is from a newer REALM — upgrade first.")

    entries = data.get('objects') or []
    if preserve_ids:
        id_map = {e['id']: e['id'] for e in entries}
    else:
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

    # Pass 2: references, keyid reconciliation, then persist.
    results = []
    keyid_conflicts: list[tuple[str, str]] = []
    dropped_parents: list[str] = []
    for entry in entries:
        obj = created[id_map[entry['id']]]
        obj.location = resolve(entry.get('location'))
        obj.owner = resolve(entry.get('owner'))
        obj.parent = resolve(entry.get('parent'))
        # A dropped @parent is silent capability loss (the child arrives
        # without its template's hooks/commands) — say so.
        if entry.get('parent') and obj.parent is None:
            dropped_parents.append(obj.name)
        # A friendly keyid carries over on import, but only if free: a keyid
        # already held by a DIFFERENT live object is a conflict, not a merge —
        # the copy lands keyless (no forced re-keying of the common,
        # non-colliding case). See docs/design/object-identity.md.
        desired = obj.db.get('keyid')
        if desired and persistence is not None:
            ok, reason = persistence.claim_keyid(obj, desired)
            if not ok:
                obj.db.delete('keyid')
                keyid_conflicts.append((obj.name, reason))
        if persistence is not None:
            await persistence.save(obj)
        results.append(obj)
    for name, reason in keyid_conflicts:
        logger.warning("import: '%s' imported keyless — %s", name, reason)
    for name in dropped_parents:
        logger.warning(
            "import: '%s' lost its @parent (template not in the file and "
            "not in this world) — inherited hooks/commands are gone; "
            "include the template in the export or re-@parent by hand",
            name)
    return results


# --- Sync (stable-id upsert): plan then apply ---------------------------------


def _snapshot(obj: GameObject) -> dict:
    """The live object as a diff-comparable dict (same shape as an entry)."""
    return {
        'name': obj.name,
        'description': obj.description,
        'tags': sorted(obj.tags.to_list()),
        'attrs': {k: v for k, v in obj.db.all().items()
                  if k not in STRIPPED_ATTRS},
        'locks': dict(obj.locks),
        'behaviors': [b.to_dict() for b in obj.get_behaviors()],
        'location': obj.location.id if obj.location else None,
        'owner': obj.owner.id if obj.owner else None,
        'parent': obj.parent.id if obj.parent else None,
    }


def _normalize_entry(entry: dict) -> dict:
    """A file entry reduced to the same comparable shape."""
    return {
        'name': str(entry.get('name', '')),
        'description': str(entry.get('description', '')),
        'tags': sorted(entry.get('tags') or []),
        'attrs': {k: v for k, v in (entry.get('attrs') or {}).items()
                  if k not in STRIPPED_ATTRS},
        'locks': dict(entry.get('locks') or {}),
        'behaviors': list(entry.get('behaviors') or []),
        'location': entry.get('location'),
        'owner': entry.get('owner'),
        'parent': entry.get('parent'),
    }


def _field_changes(live: dict, want: dict) -> list[str]:
    """Human-readable list of changed fields between two snapshots."""
    changes = []
    for f in _DIFF_FIELDS:
        a, b = live.get(f), want.get(f)
        if a == b:
            continue
        if f == 'attrs':
            keys = sorted(set(a or {}) | set(b or {}))
            diffs = [k for k in keys if (a or {}).get(k) != (b or {}).get(k)]
            changes.append(f"attrs ({', '.join(diffs)})")
        elif f in ('description', 'behaviors', 'locks', 'tags'):
            changes.append(f)
        else:
            changes.append(f"{f}: {a} → {b}")
    return changes


@dataclass
class SyncPlan:
    """A dry-run of what apply would do (Terraform-style)."""

    zone: str
    create: list[dict] = field(default_factory=list)          # file entries
    update: list[tuple[dict, list[str]]] = field(default_factory=list)  # (entry, changes)
    orphan: list[GameObject] = field(default_factory=list)     # live, not in file
    conflict: list[tuple[str, str]] = field(default_factory=list)  # (name, reason)

    def is_empty(self) -> bool:
        return not (self.create or self.update or self.orphan or self.conflict)

    def render(self) -> str:
        lines = [f"Plan for area '{self.zone}':"]
        for e in self.create:
            lines.append(f"  + create   {e.get('name')}")
        for e, changes in self.update:
            lines.append(f"  ~ update   {e.get('name')}   ({'; '.join(changes)})")
        for o in self.orphan:
            lines.append(f"  - orphan   {o.name}   "
                         f"(in world, not in file; left untouched)")
        for name, reason in self.conflict:
            lines.append(f"  ! conflict {name}   ({reason})")
        if len(lines) == 1:
            lines.append("  (no changes — the area matches the file)")
        else:
            c, u = len(self.create), len(self.update)
            lines.append(f"  {c} to create, {u} to update, "
                         f"{len(self.orphan)} orphaned, "
                         f"{len(self.conflict)} conflicts.")
        return "\n".join(lines)


def _area_members(zone: str, persistence) -> dict[str, GameObject]:
    """Live objects belonging to a zone: its rooms + whatever's IN them."""
    from realm.core.zones import zone_masters, zone_rooms

    members: dict[str, GameObject] = {}
    for room in zone_rooms(zone):
        members[room.id] = room
        for obj in room.contents:
            if not obj.has_tag('player'):
                members[obj.id] = obj
        for master in zone_masters(room):
            members[master.id] = master
    return members


def diff_plan(data: dict, zone: str, persistence, *, actor=None) -> SyncPlan:
    """
    Compare a file against the live area (matched by stable id) and
    return a SyncPlan. ``actor`` (if given) must control every object an
    apply would touch — anything they can't control becomes a conflict.
    """
    from realm.permissions.locks import controls

    if int(data.get('realm_format', 0)) > FORMAT_VERSION:
        raise ValueError("Area file is from a newer REALM — upgrade first.")

    plan = SyncPlan(zone=zone)
    entries = {e['id']: e for e in (data.get('objects') or [])}
    live = _area_members(zone, persistence)

    for oid, entry in entries.items():
        # A friendly keyid the file assigns to THIS object must not already
        # belong to a DIFFERENT live one — that's a conflict the plan refuses,
        # never a silent merge. Same object re-syncing its own keyid is fine.
        kid = (entry.get('attrs') or {}).get('keyid')
        if kid and persistence is not None:
            holder = persistence.keyid_holder(kid)
            if holder is not None and holder.id != oid:
                plan.conflict.append(
                    (str(entry.get('name', oid)),
                     f"keyid '{kid}' already belongs to {holder.name} "
                     f"(#{holder.id[:8]})"))
                continue

        existing = live.get(oid) or (
            persistence.get_cached(oid) if persistence else None)
        if existing is None:
            plan.create.append(entry)
            continue
        if actor is not None and not controls(actor, existing):
            plan.conflict.append(
                (str(entry.get('name', existing.name)),
                 "you don't control this object"))
            continue
        changes = _field_changes(_snapshot(existing), _normalize_entry(entry))
        if changes:
            plan.update.append((entry, changes))

    for oid, obj in live.items():
        if oid not in entries:
            if actor is not None and not controls(actor, obj):
                plan.conflict.append((obj.name, "orphan you don't control"))
            else:
                plan.orphan.append(obj)
    return plan


def _apply_entry(entry: dict, persistence) -> GameObject:
    """Create or update ONE object in place, preserving its id."""
    from realm.core.behaviors import BehaviorRegistry
    from realm.core.objects import GameObject as GameObjectCls

    oid = entry['id']
    obj = persistence.get_cached(oid) if persistence else None
    if obj is None:
        obj = GameObjectCls(id=oid, name=str(entry.get('name', 'thing')))
    obj.name = str(entry.get('name', obj.name))
    obj.description = str(entry.get('description', ''))

    for tag in obj.tags.to_list():
        obj.remove_tag(tag)
    for tag in entry.get('tags') or []:
        obj.add_tag(tag)

    for key in list(obj.db.all()):
        if key not in STRIPPED_ATTRS:
            obj.db.delete(key)
    for key, value in (entry.get('attrs') or {}).items():
        if key not in STRIPPED_ATTRS:
            obj.db.set(key, value)

    obj.locks.clear()
    obj.locks.update(entry.get('locks') or {})

    for behavior in obj.get_behaviors():
        obj.remove_behavior(behavior)
    for spec in entry.get('behaviors') or []:
        behavior = BehaviorRegistry.from_dict(spec)
        if behavior is not None:
            obj.add_behavior(behavior)
    return obj


async def apply_plan(data: dict, plan: SyncPlan, persistence) -> dict:
    """
    Execute a SyncPlan: create the new, update the changed IN PLACE
    (ids preserved), leave orphans alone. Refuses if the plan has
    conflicts. Returns a small summary. Orphans are NEVER auto-deleted —
    the plan reported them; a builder prunes explicitly.
    """
    if plan.conflict:
        raise ValueError(
            f"{len(plan.conflict)} conflict(s) — resolve them before applying.")

    entries = {e['id']: e for e in (data.get('objects') or [])}
    touched = {e['id'] for e in plan.create}
    touched |= {e['id'] for e, _c in plan.update}

    # Pass 1: create/update every touched object (ids are stable, so
    # references between them resolve directly — no remapping).
    objs = [_apply_entry(entries[oid], persistence) for oid in touched]
    batch = {o.id: o for o in objs}

    # Pass 2: wire references. Resolve against the BATCH first — a
    # reference between two objects in this apply must not depend on
    # which one persistence saved first (the bug the flaky test caught).
    def resolve(rid):
        if not rid:
            return None
        if rid in batch:
            return batch[rid]
        return persistence.get_cached(rid) if persistence else None

    for obj in objs:
        entry = entries[obj.id]
        obj.location = resolve(entry.get('location'))
        obj.owner = resolve(entry.get('owner'))
        obj.parent = resolve(entry.get('parent'))
        if persistence is not None:
            await persistence.save(obj)

    return {'created': len(plan.create), 'updated': len(plan.update),
            'orphaned': len(plan.orphan)}


__all__ = ["FORMAT_VERSION", "SyncPlan", "export_objects", "export_zone",
           "import_objects", "diff_plan", "apply_plan"]
