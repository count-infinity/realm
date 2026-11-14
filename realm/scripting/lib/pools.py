"""
Softcode functions: Pools (``realm.core.pools``).

Reads are plain lookups. A change happens in memory during the run and is
settled (``ON_POOL``, ``ON_SPENT``) and saved after the script finishes,
through the ``pool_settle`` queue kind.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core import pools
from realm.scripting.registry import softfn

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def _readable(frame, obj: GameObject | str | None, name: str) -> GameObject | None:
    """The object, when the executor may read the pool's storage attribute."""
    from realm.core.attrflags import PROTECTED_ATTRS, readable_attr
    target = frame.resolve(obj)
    if target is None:
        return None
    pool = pools.pool_def(target, str(name))
    storage = pool.storage if pool is not None else str(name)
    if storage in PROTECTED_ATTRS or not readable_attr(target, storage, frame.executor):
        return None
    return target


def _queue(frame, change: pools.PoolChange) -> None:
    frame.command_queue.append(('pool_settle', change.obj, (change, frame.executor)))
    frame.command_queue.append(('save', change.obj, ''))


@softfn(group='Pools', readonly=True)
def pool(frame, obj: GameObject | str | None, name: str) -> int | None:
    """A pool's value, or None when the object has no such pool.

    Example: pool(enactor, 'hp')
    """
    target = _readable(frame, obj, name)
    return None if target is None else pools.pool_get(target, str(name))


@softfn(name='pool_max', group='Pools', readonly=True)
def pool_maximum(frame, obj: GameObject | str | None, name: str) -> int | None:
    """A pool's maximum, or None when it is unbounded or absent.

    Example: pool_max(here, 'shields')
    """
    target = _readable(frame, obj, name)
    return None if target is None else pools.pool_max(target, str(name))


@softfn(name='has_pool', group='Pools', readonly=True)
def has_a_pool(frame, obj: GameObject | str | None, name: str) -> bool:
    """True when the object has the pool.

    Example: has_pool(enactor, 'mana')
    """
    target = _readable(frame, obj, name)
    return target is not None and pools.has_pool(target, str(name))


@softfn(group='Pools', readonly=True)
def spent(frame, obj: GameObject | str | None, name: str) -> bool:
    """True when the pool is used up (a down pool at or below its
    ``spent_at``, an up pool at its max).

    Example: spent(here, 'hull')
    """
    target = _readable(frame, obj, name)
    return target is not None and pools.is_spent(target, str(name))


@softfn(group='Pools', harm=True)
def harm_pool(frame, obj: GameObject | str | None, name: str, amount: int) -> int:
    """Harm a pool of something in reach, spilling into its overflow pool.
    No soak, no wards: the deliberate bypass, like ``damage()``. Returns the
    amount taken (0 when out of reach or without the pool).

    Example: harm_pool(enactor, 'stress', 2)
    """
    target = frame.resolve(obj)
    if not frame.in_reach(target):
        return 0
    change = pools.harm(target, str(name), int(amount))
    if change.total_applied:
        _queue(frame, change)
    return change.total_applied


@softfn(group='Pools')
def mend_pool(frame, obj: GameObject | str | None, name: str, amount: int) -> int:
    """Mend a pool of something in reach: raise a down pool toward its max,
    lower an up pool toward its floor. Returns the amount mended.

    Example: mend_pool(enactor, 'hp', 5)
    """
    target = frame.resolve(obj)
    if not frame.in_reach(target):
        return 0
    change = pools.mend(target, str(name), int(amount))
    if change.applied:
        _queue(frame, change)
    return change.applied


@softfn(group='Pools')
def spend_pool(frame, name: str, amount: int) -> bool:
    """Pay a cost from the executor's own pool, all or nothing. False, with
    nothing spent, when it is short.

    Example: spend_pool('heat', 3)
    """
    if frame.executor is None:
        return False
    change = pools.spend(frame.executor, str(name), int(amount))
    if change is None:
        return False
    if change.applied:
        _queue(frame, change)
    return True
