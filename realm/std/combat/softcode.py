"""
Softcode functions: Damage, healing and starting fights.

The ``combat`` feature declares each (``feature.py``, with its group and
flags); the first parameter is the run's ``ScriptFrame``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.pools import damage_pool, harm, mend, pool_max

if TYPE_CHECKING:
    from realm.core.objects import GameObject

def damage(frame, obj: GameObject | str | None, amount: int,
           dtype: str | None = None) -> bool:
    """
    Deal damage to something in the executor's room: it lands in the
    target's damage pool (``hp`` unless it says otherwise). After the
    script finishes the change settles: damage that spends the target's
    vital pool runs the combat manager's death path (corpses, CP awards,
    unconsciousness), and falling through ``hitprcnt`` fires
    ``ON_HITPRCNT``.

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
    pool = damage_pool(target)
    if pool is None:
        return False
    if dtype:
        from realm.std.combat.damage import apply_resisted
        change = apply_resisted(target, int(amount), str(dtype))
    else:
        change = harm(target, pool, int(amount))
    frame.command_queue.append(('pool_settle', target, (change, frame.executor)))
    frame.command_queue.append(('save', target, ''))
    return True

def heal(frame, obj: GameObject | str | None, amount: int) -> bool:
    """Mend the damage pool (``hp`` unless the target says otherwise),
    capped at its max, of something in the executor's room.

    Example: heal(enactor, 5)
    """
    target = frame.resolve(obj)
    if not frame.in_reach(target) or int(amount) <= 0:
        return False
    pool = damage_pool(target)
    if pool is None or pool_max(target, pool) is None:
        return False
    change = mend(target, pool, int(amount))
    frame.command_queue.append(('pool_settle', target, (change, frame.executor)))
    frame.command_queue.append(('save', target, ''))
    return True

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
