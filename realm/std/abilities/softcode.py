"""
Softcode functions: Abilities and spells.

The ``abilities`` feature declares each (``feature.py``, with its group and
flags); the first parameter is the run's ``ScriptFrame``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

def cast(
    frame,
    target: GameObject | str | None,
    ability: str = "",
    *,
    tags: list[str] | None = None,
) -> bool:
    """
    Direct an ability at a target — the ability analog of ``act``. Fires
    ``event:on_cast`` at the target with the caller's ``tags`` (a spell
    passes ``['magic']``, a psi power ``['psi']`` — the kernel forces no
    genre category), so the target's ``ON_CAST`` reacts AND its
    ``on_check`` wards resist by category: a magic-shield ring's
    ``block() if has_atag('magic')`` refuses any incoming magic power,
    not just damage — the resistance seam a spell can't otherwise reach.

    It fires the ward and reaction event only: no cost is paid and no
    effect is applied. To run an ability definition (its cost, save,
    damage and effects, as the ``cast`` command does) use ``use_ability``.
    Use ``contest()`` for a resist *roll*.

    Example:
        # a fear spell the target's wards can refuse by category
        cast(victim, 'fear', tags=['mind'])

        # the resist roll and the ward layer, together
        landed = cast(victim, 'fear', tags=['mind']) and \\
                 contest(enactor, 'occultism', victim, 'will')
    """
    tgt = frame.resolve(target)
    if tgt is None:
        return False
    extra = [str(t) for t in (tags or [])]
    frame.command_queue.append(('cast', tgt, (str(ability), extra)))
    return True


def use_ability(frame, name: str, target: GameObject | str | None = None) -> bool:
    """Use an ability or spell definition (``ability_def`` / ``spell_def``)
    as the executor: pay its cost, roll its save, apply its effects — what
    the ``cast`` command does for a player. Without ``target`` the ability
    picks its own (yourself, or your combat opponent for an attack).

    Returns False when no definition matches ``name`` or the executor does
    not qualify (class, level, skill). It runs after the script, so a False
    from a failed cost or a ward's veto is not visible here.

    Example: use_ability('fireball', enactor)
    """
    from realm.std.abilities.invoke import can_invoke, find_ability_def
    executor = frame.executor
    adef = find_ability_def(str(name))
    if executor is None or adef is None or not can_invoke(executor, adef):
        return False
    tgt = frame.resolve(target) if target is not None else None
    if target is not None and tgt is None:
        return False
    frame.command_queue.append(('ability', executor, (adef, tgt)))
    return True

