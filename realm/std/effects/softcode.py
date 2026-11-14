"""
Softcode functions: Timed effects.

The ``effects`` feature declares each (``feature.py``, with its group and
flags); the first parameter is the run's ``ScriptFrame``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

EFFECT_BEHAVIOR_IDS = ('modifier_effect', 'damage_over_time',
                       'regeneration', 'disposition_boost')

def apply_effect(
    frame,
    obj: GameObject | str | None,
    effect_id: str,
    **params: Any,
) -> bool:
    """
    Attach an effect (modifier_effect / damage_over_time /
    regeneration / disposition_boost) to something in the
    executor's room.

        apply_effect(enactor, 'modifier_effect', kind='fear',
                     duration=8, check_mods={'all': -2},
                     apply_msg='Terror grips you!')

    Example: apply_effect(enactor, 'modifier_effect', kind='fear',
             duration=8, check_mods={'all': -2})
    """
    from realm.core.behaviors import BehaviorRegistry

    if str(effect_id) not in EFFECT_BEHAVIOR_IDS:
        return False
    target = frame.resolve(obj)
    if not frame.in_reach(target):
        return False
    # Record who applied this, so an indirect kill can still name its
    # killer: a poison tick that finishes someone announces the death,
    # but had nobody to blame — bounty boards heard the death and could
    # not pay. The applier is simply whoever ran this script.
    if frame.executor is not None:
        params.setdefault('source_id', frame.executor.id)
    behavior = BehaviorRegistry.create(str(effect_id), **params)
    if behavior is None:
        return False
    # Effects are singletons per kind: their state lives in owner.db under
    # effect_<kind>_left / _wait and check_mods[<kind>] — one slot per kind
    # (see TimedEffectBehavior.attach). So re-applying the same kind
    # REFRESHES (renew/deepen), never stacks: a second same-kind behavior
    # would share those keys and corrupt both countdowns, and the first to
    # expire would strip the shared tag/mods out from under the other. Drop
    # any live same-kind effect and clear its timer so the new one starts
    # from full duration (side-effect flags like `applied` are preserved).
    from realm.behaviors.effects import TimedEffectBehavior
    if isinstance(behavior, TimedEffectBehavior):
        for existing in list(target.get_behaviors()):
            if (isinstance(existing, TimedEffectBehavior)
                    and existing.kind == behavior.kind):
                target.remove_behavior(existing)
        behavior.clear_state(target)
    target.add_behavior(behavior)
    frame.command_queue.append(('save', target, ''))
    return True

def remove_effect(frame, obj: GameObject | str | None, kind: str) -> bool:
    """Strip an active effect by kind (cure poison, calm fear).

    Example: remove_effect(enactor, 'fear')
    """
    target = frame.resolve(obj)
    if not frame.in_reach(target):
        return False
    from realm.behaviors.effects import TimedEffectBehavior
    for behavior in target.get_behaviors():
        if isinstance(behavior, TimedEffectBehavior) and behavior.kind == str(kind):
            target.remove_behavior(behavior)
            frame.command_queue.append(('save', target, ''))
            return True
    return False
