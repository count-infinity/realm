"""
Ops on whole objects: create, clone, destroy, rename, describe, chown.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from realm.core.ops import (
    Invalid,
    NotAllowed,
    OpResult,
    Refused,
    require_control,
    require_place,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)

SAFE_TAG = "safe"


def _owner_for(actor: GameObject | None) -> GameObject | None:
    """New things belong to the actor's owner, else the actor."""
    if actor is None:
        return None
    return actor.owner or actor


# --- create ------------------------------------------------------------------

def check_create(actor: GameObject | None, name: str, *,
                 location: GameObject | None = None,
                 attrs: dict | None = None,
                 parent: GameObject | None = None) -> None:
    from realm.core.ops.attrs import check_attr_name
    if not str(name).strip():
        raise Invalid("A new object needs a name.")
    require_place(actor, location)
    if parent is not None:
        require_control(actor, parent)
    for key in attrs or {}:
        check_attr_name(str(key))


def create(actor: GameObject | None, name: str, *,
           location: GameObject | None = None, description: str = "",
           tags: tuple[str, ...] | list[str] = ("thing",), attrs: dict | None = None,
           parent: GameObject | None = None) -> OpResult:
    """Create a new object at ``location``, owned by the actor's owner (or
    the actor). The actor must control ``location`` unless it is the actor
    itself or the actor's room. Attributes pass the same name gate as
    ``set_attr``. ``value`` is the new object."""
    from realm.core.inflate import inflate
    check_create(actor, name, location=location, attrs=attrs, parent=parent)
    obj = inflate({'name': str(name).strip(), 'description': description,
                   'tags': list(tags), 'attrs': attrs or {}})
    obj.owner = _owner_for(actor)
    obj.parent = parent
    obj.location = location
    return OpResult(value=obj, touched=[obj])


# --- clone -------------------------------------------------------------------

def check_clone(actor: GameObject | None, original: GameObject, *,
                location: GameObject | None = None) -> None:
    if original.is_player or original.is_room:
        raise Refused("You can't clone players or rooms.")
    require_control(actor, original)
    require_place(actor, location)


def clone(actor: GameObject | None, original: GameObject, *, name: str | None = None,
          location: GameObject | None = None) -> OpResult:
    """Copy ``original`` (attributes, tags, behaviors, locks, parent) to
    ``location``. Spawner bookkeeping tags, ``no_clone`` attributes and the
    unique keyid are not copied. ``value`` is the copy."""
    from realm.core.attrflags import cloneable_attrs
    from realm.core.inflate import inflate
    check_clone(actor, original, location=location)
    spec = {
        'name': (name or original.name).strip(),
        'description': original.description,
        'tags': [t for t in original.tags.to_list() if not t.startswith('spawned:')],
        'attrs': json.loads(json.dumps(cloneable_attrs(
            original.db.all(), original.db.get('attr_flags')))),
        'locks': dict(original.locks),
        'behaviors': [b.to_dict() for b in original.get_behaviors()],
    }
    copy = inflate(spec, strict_behaviors=True)
    copy.owner = _owner_for(actor)
    # A clone of a templated object stays templated: the parent link is a
    # reference, not a unique handle.
    copy.parent = original.parent
    copy.location = location
    return OpResult(value=copy, touched=[copy])


# --- destroy -----------------------------------------------------------------

def check_destroy(actor: GameObject | None, obj: GameObject, *,
                  allow_player: bool = False) -> None:
    """Refuse a player destroying themselves, any player (unless
    ``allow_player``, i.e. @nuke) and a ``safe``-tagged object; then require
    control. An object may destroy itself (eaten food, a spent charge)."""
    if actor is not None and obj is actor and obj.is_player:
        raise Refused("You can't destroy yourself!")
    if obj.is_player and not allow_player:
        raise Refused(f"{obj.name} is a player. Use @nuke to destroy player objects.")
    if obj.has_tag(SAFE_TAG):
        raise Refused(f"{obj.name} is protected from destruction.")
    require_control(actor, obj)


def _subtree(root: GameObject) -> list[GameObject]:
    """Every object inside ``root``, parents before children."""
    out: list[GameObject] = []
    seen = {root.id}
    stack = list(root.contents)
    while stack:
        obj = stack.pop()
        if obj.id in seen:
            continue
        seen.add(obj.id)
        out.append(obj)
        stack.extend(obj.contents)
    return out


async def destroy(actor: GameObject | None, obj: GameObject, store, *,
                  allow_player: bool = False, contents: str = "release") -> int:
    """Destroy ``obj``. Returns how many contained objects died with it.

    - a destroyed exit dissolves its pairing, so the far side is not left
      pointing at a deleted door (exits inside are handled by teardown);
    - ``contents="release"``: the R9 disposition of ``core.teardown``
      (players evacuated, player-owned items to their owner's refuge,
      everything else destroyed);
    - ``contents="destroy"`` (@nuke): every non-player object inside dies
      too; players are still evacuated.
    """
    from realm.core.pairing import dissolve_pairing
    from realm.core.teardown import release_contents

    if contents not in ("release", "destroy"):
        raise ValueError(f"contents must be 'release' or 'destroy', not {contents!r}")
    check_destroy(actor, obj, allow_player=allow_player)

    if obj.is_exit:
        former = dissolve_pairing(obj)
        if former is not None and store is not None:
            await store.save(former)

    if contents == "release":
        destroyed = await release_contents(obj, store)
    else:
        doomed = [o for o in _subtree(obj) if not o.is_player]
        destroyed = await release_contents(obj, store, doomed_ids={o.id for o in doomed})
        for victim in reversed(doomed):       # deepest first
            victim.location = None
            if store is not None:
                await store.delete(victim)
        destroyed += len(doomed)

    obj.location = None
    if store is not None:
        await store.delete(obj)
    logger.info(f"Destroyed {obj.name} ({obj.id}) and {destroyed} contained object(s)")
    return destroyed


# --- rename, describe --------------------------------------------------------

def check_rename(actor: GameObject | None, obj: GameObject, name: str) -> None:
    if not str(name).strip():
        raise Invalid("A name can't be empty.")
    require_control(actor, obj)


def rename(actor: GameObject | None, obj: GameObject, name: str) -> OpResult:
    """Rename ``obj``. ``value`` is the old name."""
    check_rename(actor, obj, name)
    old = obj.name
    obj.name = str(name).strip()
    return OpResult(value=old, touched=[obj])


def check_describe(actor: GameObject | None, obj: GameObject) -> None:
    require_control(actor, obj)


def describe(actor: GameObject | None, obj: GameObject, text: str) -> OpResult:
    """Set ``obj``'s description (empty clears it)."""
    check_describe(actor, obj)
    obj.description = str(text)
    return OpResult(value=obj.description, touched=[obj])


# --- chown -------------------------------------------------------------------

def check_chown(actor: GameObject | None, obj: GameObject, new_owner: GameObject) -> None:
    from realm.permissions import has_entitlement
    from realm.permissions.entitlements import CONTROL_ALL
    if actor is not None and not has_entitlement(actor, CONTROL_ALL):
        raise NotAllowed("Only an admin can change who owns something.")


_SCRIPT_PREFIXES = ('CMD_', 'LISTEN_', 'ON_')


def chown(actor: GameObject | None, obj: GameObject, new_owner: GameObject) -> OpResult:
    """Give ``obj`` to ``new_owner``. An object carrying scripts is tagged
    ``halt``: the old owner's scripts must not run with the new owner's
    authority until the new owner reviews them. ``value`` is the old owner;
    ``warnings`` says when it was halted."""
    check_chown(actor, obj, new_owner)
    old = obj.owner
    obj.owner = new_owner
    result = OpResult(value=old, touched=[obj])
    if any(str(k).upper().startswith(_SCRIPT_PREFIXES) for k in obj.db.all()):
        obj.add_tag('halt')
        result.warnings.append(
            f"{obj.name} carries scripts — halted for review "
            f"(@untag {obj.name} = halt to reactivate).")
    return result
