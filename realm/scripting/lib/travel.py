"""
Softcode functions: Movement.

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
