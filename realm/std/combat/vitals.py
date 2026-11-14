"""
Combat's two pool observers (KERNEL_PLAN 8.3).

Whatever harms an object, a swing, a spell, poison, a trap or a softcode
``harm_pool``, settles its change through ``realm.core.pools.settle``, which
propagates ``pool:on_change`` and ``pool:on_spent``. These observers turn
the object's **vital pool** (``vital_pool(obj)``: ``hp`` for a character,
``hull`` for a ship) into combat's two outcomes:

- spent: :meth:`CombatManager.handle_death`, with the source as the killer;
- falling through ``db.hitprcnt`` (a percent left), short of spent:
  ``ON_HITPRCNT``.

Other pools (shields, mana, heat) move without either.
"""

from __future__ import annotations

from realm.core.action_types import ActionType
from realm.core.pools import is_spent, pool_percent, vital_pool
from realm.core.propagation import Action
from realm.std.combat.actions import CombatAction


def _vital(action: Action) -> str | None:
    """The pool the action moved, when it is the target's vital pool."""
    obj = action.target
    name = action.extra.get("pool")
    if obj is None or name is None or name != vital_pool(obj):
        return None
    return name


async def death_observer(action: Action) -> None:
    """The vital pool was spent: the one death path."""
    if action.action_type != ActionType.POOL_SPENT or _vital(action) is None:
        return
    from realm.core.world import get_world
    manager = get_world().services.get("combat")
    if manager is not None:
        await manager.handle_death(action.target, killer=action.actor)


async def threshold_observer(action: Action) -> None:
    """The vital pool fell through ``db.hitprcnt``: fire ``ON_HITPRCNT``
    once, on the crossing. Not on the change that spends it (that is
    ``ON_DEATH``'s)."""
    if action.action_type != ActionType.POOL_CHANGE:
        return
    name = _vital(action)
    if name is None:
        return
    obj = action.target
    threshold = obj.db.get("hitprcnt")
    if threshold is None or is_spent(obj, name):
        return
    old = pool_percent(obj, name, action.extra["old"])
    new = pool_percent(obj, name, action.extra["new"])
    if old is None or new is None or not old > float(threshold) >= new:
        return
    from realm.core.events import fire_event
    await fire_event(action.actor, obj, CombatAction.ON_HITPRCNT,
                     extra={"percent": round(new), "threshold": int(threshold)})


__all__ = ["death_observer", "threshold_observer"]
