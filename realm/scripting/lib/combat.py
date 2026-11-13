"""
Softcode functions: Damage, healing and starting fights.

Each function is registered with ``@softfn``; one that takes the run's
``ScriptFrame`` as ``frame`` reads the executor, enactor, store and queue
from it. See ``realm/scripting/registry.py`` for the flags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.scripting.registry import softfn

if TYPE_CHECKING:
    from realm.core.objects import GameObject

@softfn(owner='combat', group='Combat & effects', harm=True)
def damage(frame, obj: GameObject | str | None, amount: int,
           dtype: str | None = None) -> bool:
    """
    Deal damage to something in the executor's room. Lethal damage
    routes through the combat manager's death path (corpses, CP
    awards, unconsciousness) after the script finishes.

    With a damage type, the hit routes through the active ruleset's
    ``apply_damage`` — so a target's ``resistances`` (and any other
    ruleset mitigation) apply: a fire-immune mob shrugs off
    damage(enactor, 12, 'fire'). Untyped damage stays raw.

    Example: damage(enactor, 3)
             damage(enactor, 12, 'fire')
    """
    target = frame.resolve(obj)
    if not frame.in_reach(target) or int(amount) <= 0:
        return False
    hp = target.db.get('hp')
    if hp is None:
        return False
    if dtype:
        from realm.combat.damage import apply_resisted
        apply_resisted(target, int(amount), str(dtype))
    else:
        target.db.hp = int(hp) - int(amount)
    frame.command_queue.append(('death_check', target, frame.executor))
    frame.command_queue.append(('save', target, ''))
    return True

@softfn(owner='combat', group='Combat & effects')
def heal(frame, obj: GameObject | str | None, amount: int) -> bool:
    """Restore HP (capped at max_hp) to something in the executor's room.

    Example: heal(enactor, 5)
    """
    target = frame.resolve(obj)
    if not frame.in_reach(target) or int(amount) <= 0:
        return False
    hp = target.db.get('hp')
    max_hp = target.db.get('max_hp')
    if hp is None or max_hp is None:
        return False
    target.db.hp = min(int(max_hp), int(hp) + int(amount))
    frame.command_queue.append(('save', target, ''))
    return True

@softfn(owner='combat', group='Combat & effects')
def start_combat(
    frame,
    attacker: GameObject | str | None,
    target: GameObject | str | None,
) -> bool:
    """
    Throw an attacker the executor controls into combat with a
    target in the same room (queued; the encounter starts after the
    script finishes).

    Example: start_combat('beast', enactor)
    """
    atk = frame.resolve(attacker)
    tgt = frame.resolve(target)
    if atk is None or tgt is None or atk is tgt:
        return False
    if not frame.may_mutate(atk):
        return False
    if atk.location is None or atk.location is not tgt.location:
        return False
    frame.command_queue.append(('combat', atk, tgt))
    return True
