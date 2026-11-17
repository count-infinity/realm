"""
Natural regeneration (MUD_PLAN 2.1).

A character (a player or an ``npc``) regains its pools over time while out
of combat: every ``REGEN_INTERVAL`` seconds each pool below full recovers
by the game system's ``regen(obj, pool)`` (1 with no rules feature), scaled
by the product of the service's ``multipliers`` (resting and sleeping are
the first; other features add their own). A down pool rises toward its max;
an up pool (stress, heat) falls toward its floor. A pool whose definition
says ``regen: False`` stays where it is. Unconscious characters regenerate
too, which is how a lone player comes round.

Only characters known to be below full are swept: an observer on
``pool:on_change`` keeps the set, and ``on_boot`` seeds it once from the
characters already loaded.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from realm.core.action_types import ActionType
from realm.core.pools import (
    damage_pool,
    declared_pools,
    mend,
    pool_def,
    pool_get,
    pool_max,
    settle,
    vital_pool,
)

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action
    from realm.core.world import World

#: ``(obj, pool_name) -> float``: one factor of a tick's amount.
Multiplier = Callable[["GameObject", str], float]


def now() -> float:
    """The clock the regeneration sweep runs on (tests replace it)."""
    return time.monotonic()


def is_character(obj: GameObject) -> bool:
    return obj.is_player or obj.is_npc


def _room_left(obj: GameObject, name: str) -> int:
    """How far the pool is from fully recovered: 0 when it is full, when it
    does not regenerate, or when it has no bound to recover toward."""
    pool = pool_def(obj, name)
    value = pool_get(obj, name)
    if pool is None or value is None or not pool.regen:
        return 0
    if pool.direction == "down":
        maximum = pool_max(obj, name)
        return 0 if maximum is None else max(0, maximum - value)
    floor = pool.floor if pool.floor is not None else 0
    return max(0, value - floor)


def pools_to_recover(obj: GameObject) -> list[str]:
    """The object's pools that are below full and regenerate: its declared
    pools, plus its damage and vital pools when those are implicit."""
    names = list(declared_pools(obj))
    for name in (damage_pool(obj), vital_pool(obj)):
        if name is not None and name not in names:
            names.append(name)
    return [name for name in names if _room_left(obj, name) > 0]


class Vitals:
    """The ``vitals`` service: who is recovering, and one tick of it."""

    def __init__(self, world: World):
        self.world = world
        #: ids of the characters with a pool below full
        self.tracked: set[str] = set()
        #: the factors of each tick's amount (positions first; ``needs`` later)
        self.multipliers: list[Multiplier] = []
        self._last: float | None = None

    def track(self, obj: GameObject) -> None:
        """Note ``obj`` as recovering, or drop it when it is full."""
        if is_character(obj) and pools_to_recover(obj):
            self.tracked.add(obj.id)
        else:
            self.tracked.discard(obj.id)

    async def observe(self, action: Action) -> None:
        """``pool:on_change``: keep the recovering set current."""
        if action.action_type != ActionType.POOL_CHANGE or action.target is None:
            return
        if is_character(action.target):
            self.track(action.target)

    def amount(self, obj: GameObject, pool_name: str) -> int:
        """One tick's recovery for this pool: the rules' ``regen`` (1 with
        no rules) times every multiplier. 0 when a multiplier is 0."""
        rules = self.world.rules
        base = rules.regen(obj, pool_name) if rules is not None else 1
        scale = 1.0
        for factor in self.multipliers:
            scale *= float(factor(obj, pool_name))
        if scale <= 0 or base <= 0:
            return 0
        return max(1, round(base * scale))

    async def tick(self) -> None:
        """One regeneration pass over the recovering characters not in a
        fight."""
        store = self.world.store
        for obj_id in list(self.tracked):
            obj = store.get_cached(obj_id) if store is not None else None
            if obj is None:
                self.tracked.discard(obj_id)
                continue
            if obj.has_tag("in_combat"):
                continue
            for name in pools_to_recover(obj):
                amount = min(self.amount(obj, name), _room_left(obj, name))
                if amount > 0:
                    await settle(mend(obj, name, amount))
            self.track(obj)

    async def sweep(self, _store: Any = None) -> None:
        """The reaper's call (every ``REAP_INTERVAL``): a tick once
        ``REGEN_INTERVAL`` seconds have passed since the last."""
        at = now()
        if self._last is None:
            self._last = at
            return
        if at - self._last < float(self.world.setting("REGEN_INTERVAL")):
            return
        self._last = at
        await self.tick()

    def seed(self) -> None:
        """Track every loaded character below full (once, at boot)."""
        store = self.world.store
        if store is None:
            return
        for tag in ("player", "npc"):
            for obj in store.find_cached(tag=tag):
                self.track(obj)


def _service() -> Vitals | None:
    from realm.core.world import find_world
    world = find_world()
    return world.services.get("vitals") if world is not None else None


async def regen_sweep(store: Any) -> None:
    """The ``vitals`` reaper: the world's service decides whether a tick is due."""
    service = _service()
    if service is not None:
        await service.sweep(store)


async def regen_observer(action: Action) -> None:
    """The ``vitals`` observer on ``pool:on_change``."""
    if action.action_type != ActionType.POOL_CHANGE:
        return
    service = _service()
    if service is not None:
        await service.observe(action)


__all__ = ["Vitals", "Multiplier", "is_character", "pools_to_recover",
           "regen_sweep", "regen_observer"]
