"""
Ops that move things and shape the map: relocate, dig, open, link,
unlink, pair, unpair.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.ops import Invalid, NotAllowed, OpResult, require_control, require_place

if TYPE_CHECKING:
    from realm.core.objects import GameObject

#: The compass opposite used when @dig names only the way there.
OPPOSITES = {
    'north': 'south', 'south': 'north', 'east': 'west', 'west': 'east',
    'up': 'down', 'down': 'up', 'in': 'out', 'out': 'in',
    'northeast': 'southwest', 'southwest': 'northeast',
    'northwest': 'southeast', 'southeast': 'northwest',
}


def exit_named(room: GameObject, name: str) -> GameObject | None:
    """An existing exit in a room by exact (case-insensitive) name."""
    lower = name.strip().lower()
    for obj in room.contents:
        if obj.is_exit and obj.name.lower() == lower:
            return obj
    return None


def _owner_for(actor: GameObject | None) -> GameObject | None:
    return None if actor is None else (actor.owner or actor)


def _exit(name: str, *, location: GameObject, destination: GameObject,
          actor: GameObject | None) -> GameObject:
    from realm.core.objects import GameObject
    obj = GameObject(name=name, location=location, owner=_owner_for(actor), tags=['exit'])
    obj.db.destination = destination.id
    return obj


# --- relocate ----------------------------------------------------------------

def check_relocate(actor: GameObject | None, target: GameObject,
                   destination: GameObject, *, consent: bool = False) -> None:
    """Moving yourself is always allowed; anything else needs relocation
    authority (control of it, or of the room it stands in) or the target's
    consent (it invoked the mover)."""
    from realm.permissions.locks import may_relocate
    if target is destination:
        raise Invalid("Can't teleport something to itself.")
    if actor is None or target is actor or consent:
        return
    if not may_relocate(actor, target):
        raise NotAllowed("Permission denied.")


async def relocate(actor: GameObject | None, target: GameObject, destination: GameObject,
                   *, force: bool = False, extra_tags: list[str] | tuple[str, ...] = (),
                   consent: bool = False) -> OpResult:
    """Move ``target`` to ``destination`` through the one movement core.

    ``force`` skips on_check wards but still honors the destination's
    ENTER/TELEPORT locks. ``value`` is whether the move happened (a ward or
    lock can still refuse it)."""
    from realm.core.movement import move_to
    check_relocate(actor, target, destination, consent=consent)
    moved = await move_to(target, destination, extra_tags=list(extra_tags),
                          force=force, mover=actor)
    return OpResult(value=bool(moved), touched=[target] if moved else [])


# --- dig, open ---------------------------------------------------------------

def check_dig(actor: GameObject | None, name: str, *, from_room: GameObject | None = None,
              out_name: str | None = None) -> None:
    if not str(name).strip():
        raise Invalid("A new room needs a name.")
    if out_name:
        require_place(actor, from_room)
        if from_room is not None and exit_named(from_room, out_name.lower()):
            raise Invalid(f"An exit '{out_name.lower()}' already exists here — "
                          f"pick another name.")


def dig(actor: GameObject | None, name: str, *, from_room: GameObject | None = None,
        out_name: str | None = None, back_name: str | None = None) -> OpResult:
    """Create a room. With ``out_name``, also an exit from ``from_room`` to it,
    and a paired exit back (``back_name``, else the compass opposite).
    ``value`` is ``(room, exit_out, exit_back)``; missing exits are None."""
    from realm.core.objects import GameObject
    from realm.core.pairing import pair_exits
    check_dig(actor, name, from_room=from_room, out_name=out_name)
    room = GameObject(name=str(name).strip(), owner=_owner_for(actor), tags=['room'])
    touched = [room]
    exit_out = exit_back = None
    if out_name and from_room is not None:
        out_name = out_name.lower()
        exit_out = _exit(out_name, location=from_room, destination=room, actor=actor)
        touched.append(exit_out)
        back = (back_name or OPPOSITES.get(out_name) or "").lower()
        if back and not exit_named(room, back):
            exit_back = _exit(back, location=room, destination=from_room, actor=actor)
            # The two faces of one passage are born together: pair them now,
            # while it is unambiguous (see realm/core/pairing.py).
            pair_exits(exit_out, exit_back)
            touched.append(exit_back)
    return OpResult(value=(room, exit_out, exit_back), touched=touched)


def check_open_exit(actor: GameObject | None, name: str, *, location: GameObject,
                    destination: GameObject) -> None:
    if not str(name).strip():
        raise Invalid("An exit needs a name.")
    if not destination.is_room:
        raise Invalid(f"'{destination.name}' is not a room.")
    require_place(actor, location)


def open_exit(actor: GameObject | None, name: str, *, location: GameObject,
              destination: GameObject) -> OpResult:
    """Create an exit in ``location`` leading to ``destination``."""
    check_open_exit(actor, name, location=location, destination=destination)
    exit_obj = _exit(str(name).strip(), location=location, destination=destination,
                     actor=actor)
    return OpResult(value=exit_obj, touched=[exit_obj])


# --- link, unlink ------------------------------------------------------------

def check_link(actor: GameObject | None, exit_obj: GameObject,
               destination: GameObject | None = None) -> None:
    if not exit_obj.is_exit:
        raise Invalid(f"'{exit_obj.name}' is not an exit.")
    require_control(actor, exit_obj)


def link(actor: GameObject | None, exit_obj: GameObject, destination: GameObject) -> OpResult:
    """Point an exit at ``destination``. Retargeting dissolves any pairing on
    both sides, so a mirror is never dragged to an unrelated door. ``value``
    is the former partner, or None."""
    from realm.core.pairing import dissolve_pairing
    check_link(actor, exit_obj, destination)
    former = dissolve_pairing(exit_obj)
    exit_obj.db.destination = destination.id
    touched = [exit_obj] + ([former] if former is not None else [])
    return OpResult(value=former, touched=touched)


def check_unlink(actor: GameObject | None, exit_obj: GameObject) -> None:
    check_link(actor, exit_obj)


def unlink(actor: GameObject | None, exit_obj: GameObject) -> OpResult:
    """Remove an exit's destination (and its pairing). ``value`` is the
    former partner, or None."""
    from realm.core.pairing import dissolve_pairing
    check_unlink(actor, exit_obj)
    former = dissolve_pairing(exit_obj)
    exit_obj.db.delete('destination')
    exit_obj.db.delete('destination_obj')
    touched = [exit_obj] + ([former] if former is not None else [])
    return OpResult(value=former, touched=touched)


# --- pair, unpair ------------------------------------------------------------

def check_pair(actor: GameObject | None, exit_obj: GameObject, far: GameObject) -> None:
    if not exit_obj.is_exit:
        raise Invalid(f"'{exit_obj.name}' is not an exit.")
    if not far.is_exit:
        raise Invalid(f"'{far.name}' is not an exit.")
    if far.id == exit_obj.id:
        raise Invalid("An exit cannot be its own partner.")
    require_control(actor, exit_obj)
    require_control(actor, far)


def pair(actor: GameObject | None, exit_obj: GameObject, far: GameObject) -> OpResult:
    """Marry two exits as the faces of one door. Prior marriages of either
    are dissolved first, on every side."""
    from realm.core.pairing import dissolve_pairing, pair_exits
    check_pair(actor, exit_obj, far)
    touched = [exit_obj, far]
    for prior in (dissolve_pairing(exit_obj), dissolve_pairing(far)):
        if prior is not None:
            touched.append(prior)
    pair_exits(exit_obj, far)
    return OpResult(value=far, touched=touched)


def check_unpair(actor: GameObject | None, exit_obj: GameObject) -> None:
    check_link(actor, exit_obj)


def unpair(actor: GameObject | None, exit_obj: GameObject) -> OpResult:
    """Divorce an exit from its partner, on both sides. ``value`` is the
    former partner, or None."""
    from realm.core.pairing import dissolve_pairing
    check_unpair(actor, exit_obj)
    former = dissolve_pairing(exit_obj)
    touched = [exit_obj] + ([former] if former is not None else [])
    return OpResult(value=former, touched=touched if former is not None else [])
