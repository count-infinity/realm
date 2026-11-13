"""
Softcode functions: Movement, instances and the wilderness.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.scripting.registry import softfn

if TYPE_CHECKING:
    from realm.core.objects import GameObject

@softfn(group='Movement & travel')
def move_to(
    frame,
    target: GameObject | str | None,
    destination: GameObject | str | None,
    *,
    tags: list[str] | None = None,
    force: bool = False,
) -> bool:
    """
    Relocate a player/object to a destination with the movement checks
    baked in — the one relocation verb. The move is always tagged
    ``movement``, so a Bound ward (``block() if has_atag('movement')``)
    stops it; pass extra ``tags`` (e.g. ``['magic']``) so anti-magic wards
    catch it too. Both the origin and the destination get an event-veto,
    plus the destination's ENTER/TELEPORT locks. Returns whether the move
    was *authorized and queued* — wards/locks run after the script ends,
    and a veto fizzles the move then, delivering the reason to the mover.
    (``tags`` here = ``extra_tags`` on the core ``movement.move_to``.)

    ``force=True`` (== ``teleport_obj``) skips the on_check **wards** but
    NOT the **locks** — the wizard bypass. It requires full control of the
    target; without force, the enactor may also move *themselves* (a
    ``cast teleport`` moves the caster).

    Example — a teleport spell:
    ``&spell.teleport = move_to(enactor, 'The Sanctum', tags=['magic'])``
    """
    from realm.core import ops
    tgt = frame.resolve(target)
    dest = frame.resolve(destination)
    if tgt is None or dest is None:
        return False
    # Relocation authority (own the target, or own the room it is in), or a
    # CONSENTING enactor (they typed this object's $-command or walked its
    # exit, not merely spoke near it). force (teleport_obj) never uses consent.
    consent = (not force and tgt is frame.enactor and frame.enactor_consent)
    if not frame.allowed(ops.check_relocate, tgt, dest, consent=consent):
        return False
    extra = [str(t) for t in (tags or [])]
    frame.command_queue.append(('move_to', tgt, (dest.id, extra, bool(force))))
    return True


@softfn(owner='instances', group='Movement & travel')
def enter_instance(
    frame,
    player: GameObject | str | None,
    template: str,
    *,
    mode: str = "solo",
    return_room: GameObject | str | None = None,
    idle_ttl: float | None = None,
) -> bool:
    """
    Send a player into a private, transient copy of a template area,
    materializing one on demand — and reusing their own copy (or their
    leader's, if it's ``shared``) if one already exists. The area opts in
    by tagging a room ``instance_template``; the copy is reaped when it's
    sat empty past ``idle_ttl``. The executor must control the player.

    ``mode`` — ``'solo'`` (private) or ``'shared'`` (the owner's
    followers route into the owner's copy). ``return_room`` — where a
    straggler is evacuated when the copy is reaped (else their home).
    Returns whether the entry was *authorized and queued*; the
    materialize-and-move happens after the script ends.

    Callable when the executor controls the player, or the player is the
    enactor (they walked into the portal). This is the *scripted* API —
    a game event opening a dungeon, a puzzle reward. For a portal
    **exit**, prefer a real deferred-destination exit instead:
    ``@set exit/dest_resolver = instance`` +
    ``@set exit/instance_template = crypt`` — a normal traversal, with
    follower routing.

    Example:
        # a private copy of the crypt, just for this player
        enter_instance(enactor, 'crypt')

        # one copy for the whole party; stragglers evacuate to the inn
        enter_instance(enactor, 'crypt', mode='shared',
                       return_room='The Rusty Anchor', idle_ttl=600)
    """
    from realm.core.instances import ENTRY_TAG, TEMPLATE_TAG
    from realm.permissions.locks import LockType, check_lock

    target = frame.resolve(player)
    if target is None:
        return False
    # The executor must have relocation authority over the player (own
    # them, or own the room they're in) — OR the player is a CONSENTING
    # enactor: they typed this object's $-command or walked the exit
    # whose ON_FAIL is running. Being overheard or witnessed is not
    # consent. Entry is still gated by the template's ENTER lock below.
    if not (frame.may_relocate(target)
            or (target is frame.enactor and frame.enactor_consent)):
        return False
    template = str(template)
    # Opt-in gate: only a zone with an instance_template-tagged room can
    # be instanced.
    rooms = frame.zone_rooms(template)
    if not any(r.has_tag(TEMPLATE_TAG) for r in rooms):
        return False
    # Destination-side authority: the template entry room's ENTER lock
    # (default-open) decides who may be sent in — checked against the
    # PLAYER being sent (the walker), matching move_to's convention, so
    # an author can gate a dungeon behind a key/role the entrant holds.
    entry = (next((r for r in rooms if r.has_tag(ENTRY_TAG)), None)
             or next((r for r in rooms if r.has_tag(TEMPLATE_TAG)), None))
    if entry is not None and not check_lock(entry, LockType.ENTER, target):
        return False
    ret = frame.resolve(return_room) if return_room is not None else None
    ttl = float(idle_ttl) if idle_ttl is not None else None
    frame.command_queue.append(
        ('enter_instance', target,
         (template, str(mode), ret.id if ret else None, ttl)))
    return True

@softfn(owner='wilderness', group='Movement & travel')
def enter_wilderness(frame, player: GameObject | str | None,
                     region: str, x, y) -> bool:
    """
    Send a player to the wilderness cell at ``(region, x, y)``,
    materializing it on demand — the scripted seam into a
    coordinate-keyed region. (Walking between cells needs no softcode:
    the cells' exits are real exits with deferred destinations.)

    Callable when the executor controls the player, or the player is
    the consenting enactor. Entry is gated by the region master's
    ENTER lock, checked against the player being sent. Returns whether
    the entry was *authorized and queued*; the materialize-and-move
    happens after the script ends.

    Example: enter_wilderness(enactor, 'wilds', 10, 10)
    """
    from realm.core.wilderness import get_region
    from realm.permissions.locks import LockType, check_lock

    target = frame.resolve(player)
    if target is None:
        return False
    if not (frame.may_relocate(target)
            or (target is frame.enactor and frame.enactor_consent)):
        return False
    try:
        x_i, y_i = int(x), int(y)
    except (TypeError, ValueError):
        return False
    region_obj = get_region(str(region))
    if region_obj is None:
        return False
    if not check_lock(region_obj, LockType.ENTER, target):
        return False
    frame.command_queue.append(
        ('wilderness', target, (str(region), x_i, y_i)))
    return True
