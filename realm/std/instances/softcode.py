"""
Softcode functions of the ``instances`` feature.

The feature declares each (``feature.py``, with its group and flags); the
first parameter is the run's ``ScriptFrame``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject


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
    from realm.permissions.locks import LockType, check_lock
    from realm.std.instances.instancing import ENTRY_TAG, TEMPLATE_TAG

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
