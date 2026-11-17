"""
Pools: a bounded number on an object.

Health, shields, hull, mana, stress, a harm clock and a door's structure are
all the same thing: a number stored in an attribute, perhaps with a maximum
beside it. This module is the one place that changes such a number for
damage, healing or costs. It is kernel: numbers on objects, no dice, no
rules.

A pool named ``hp`` is the attributes ``hp`` and ``max_hp``, so nothing
saved changes and softcode that reads ``get_attr(obj, "hp")`` keeps working.
How a pool behaves comes from its :class:`Pool` definition, looked up in
this order (first match wins, and a match is used whole):

1. the object's own ``pools`` attribute, a dict of name to partial spec:
   ``@set ship/pools = {"shields": {"overflow": "hull"}}``;
2. the same attribute up the object's ``parent`` chain;
3. a world default: ``GameSystem.pools()`` or ``feature.pool(Pool(...))``;
4. implicit: any attribute holding a number is a pool with default settings.

``harm``, ``mend`` and ``spend`` are synchronous and touch memory only, so
the softcode worker thread can call them; they fire nothing. ``settle`` is
the async half: it propagates ``pool:on_change`` (``ON_POOL``) and, on the
change that makes a pool spent, ``pool:on_spent`` (``ON_SPENT``).

    change = harm(ship, damage_pool(ship), 12, soak=True)
    await settle(change, source=attacker)

See docs/guides/pools.md.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, replace
from typing import TYPE_CHECKING, Any, Literal

from realm.core.action_types import ActionType

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.world import World


@dataclass(frozen=True)
class Pool:
    """How one pool behaves. Unset storage names derive from ``name``."""

    name: str                          # "hp"
    attr: str | None = None            # storage attribute, default: name
    max_attr: str | None = None        # default: "max_" + name; no value means unbounded
    #: down: harm lowers it, spent at or below ``spent_at``.
    #: up: harm raises it, spent at max (stress, harm clocks, heat).
    direction: Literal["down", "up"] = "down"
    floor: int | None = 0              # lowest stored value; None allows negatives
    spent_at: int = 0                  # a down pool is spent at or below this
    overflow: str | None = None        # harm this pool could not absorb goes here
    soak_attr: str | None = None       # flat reduction read from this attribute
    #: whether it recovers over time on its own (the ``vitals`` feature):
    #: a down pool rises toward its max, an up pool falls toward its floor
    regen: bool = True
    owner: str = "kernel"

    def __post_init__(self) -> None:
        if self.direction not in ("down", "up"):
            raise ValueError(f"pool {self.name!r}: direction must be 'down' or 'up' "
                             f"(got {self.direction!r})")
        if self.overflow == self.name:
            raise ValueError(f"pool {self.name!r} overflows into itself")

    @property
    def storage(self) -> str:
        return self.attr or self.name

    @property
    def max_storage(self) -> str:
        return self.max_attr or f"max_{self.name}"

    def same_as(self, other: Pool) -> bool:
        """Equal apart from who declared it."""
        return replace(self, owner="") == replace(other, owner="")


#: The keys a partial spec in a ``pools`` attribute may set.
SPEC_KEYS = frozenset(f.name for f in fields(Pool)) - {"name", "owner"}


@dataclass
class PoolChange:
    """What one ``harm``, ``mend`` or ``spend`` did to one pool."""

    obj: GameObject
    pool: str
    old: int
    new: int
    requested: int                     # amount asked for, never negative
    applied: int                       # amount this pool took
    soaked: int = 0
    spilled: PoolChange | None = None  # the change made to the overflow pool
    became_spent: bool = False         # crossed into spent on this change

    @property
    def total_applied(self) -> int:
        """Applied here plus everything spilled down the overflow chain."""
        return self.applied + (self.spilled.total_applied if self.spilled else 0)

    def links(self) -> list[PoolChange]:
        """This change and each spilled one, in order."""
        out, link = [], self
        while link is not None:
            out.append(link)
            link = link.spilled
        return out


# --- definitions --------------------------------------------------------------


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _from_spec(name: str, spec: Any, where: GameObject) -> Pool:
    if not isinstance(spec, dict):
        raise ValueError(f"{where.name}: pools[{name!r}] must be a dict of settings "
                         f"(got {spec!r})")
    unknown = set(spec) - SPEC_KEYS
    if unknown:
        raise ValueError(f"{where.name}: pools[{name!r}] has unknown key(s) "
                         f"{sorted(unknown)}; known: {sorted(SPEC_KEYS)}")
    return Pool(name, **spec, owner=f"{where.name} ({where.id})")


def _spec_layers(obj: GameObject):
    """``(node, specs)`` for each ``pools`` attribute up the parent chain
    (sources 1 and 2), nearest first."""
    node, depth = obj, 0
    while node is not None and depth <= 8:
        specs = node.db.own("pools")
        if specs is not None:
            if not isinstance(specs, dict):
                raise ValueError(f"{node.name}: the pools attribute must be a dict "
                                 f"(got {specs!r})")
            yield node, specs
        node, depth = node.parent, depth + 1


def _world_defaults() -> dict[str, Pool]:
    from realm.core.world import find_world
    world = find_world()
    return world.pools if world is not None else {}


def _declared(obj: GameObject, name: str) -> Pool | None:
    """Sources 1 to 3: the ``pools`` attribute up the parent chain, then
    the world's defaults."""
    for node, specs in _spec_layers(obj):
        if name in specs:
            return _from_spec(name, specs[name], node)
    return _world_defaults().get(name)


def declared_pools(obj: GameObject) -> list[str]:
    """The declared pools (sources 1 to 3) the object has: the world's
    defaults in declaration order, then any its ``pools`` attribute adds.
    Implicit pools (any numeric attribute) are not listed."""
    names = list(_world_defaults())
    for _node, specs in _spec_layers(obj):
        names.extend(n for n in specs if n not in names)
    return [n for n in names if has_pool(obj, n)]


def pool_def(obj: GameObject, name: str) -> Pool | None:
    """The definition of ``name`` on ``obj``: declared (sources 1 to 3), or
    implicit when the attribute holds a number. None when neither."""
    declared = _declared(obj, name)
    if declared is not None:
        return declared
    return Pool(name) if _number(obj.db.get(name)) else None


def _value(obj: GameObject, pool: Pool) -> int | None:
    value = obj.db.get(pool.storage)
    return int(value) if _number(value) else None


def _maximum(obj: GameObject, pool: Pool) -> int | None:
    value = obj.db.get(pool.max_storage)
    return int(value) if _number(value) else None


def pool_get(obj: GameObject, name: str) -> int | None:
    """The pool's value; None when the object has no such pool."""
    pool = pool_def(obj, name)
    return None if pool is None else _value(obj, pool)


def pool_max(obj: GameObject, name: str) -> int | None:
    """The pool's maximum; None when unbounded or absent."""
    pool = pool_def(obj, name)
    return None if pool is None else _maximum(obj, pool)


def has_pool(obj: GameObject, name: str) -> bool:
    return pool_get(obj, name) is not None


def _spent(pool: Pool, value: int, maximum: int | None) -> bool:
    if pool.direction == "up":
        return maximum is not None and value >= maximum
    return value <= pool.spent_at


def is_spent(obj: GameObject, name: str | None) -> bool:
    """True when the pool is used up. False for no pool (or no name)."""
    if name is None:
        return False
    pool = pool_def(obj, name)
    value = None if pool is None else _value(obj, pool)
    return value is not None and _spent(pool, value, _maximum(obj, pool))


def pool_percent(obj: GameObject, name: str, value: int | None = None) -> float | None:
    """How much of the pool is left before it is spent, as a percent of its
    max: 100 is full health, 0 is spent. A down pool counts its value, an up
    pool what remains below its max (a harm clock at 2 of 6 is 66.7). Pass
    ``value`` to ask about a value other than the current one. None when the
    pool is absent or has no positive max."""
    pool = pool_def(obj, name)
    if pool is None:
        return None
    maximum = _maximum(obj, pool)
    if value is None:
        value = _value(obj, pool)
    if value is None or maximum is None or maximum <= 0:
        return None
    left = maximum - value if pool.direction == "up" else value
    return 100.0 * left / maximum


def damage_pool(obj: GameObject) -> str | None:
    """Where harm lands first: ``obj.db.damage_pool``, else the
    ``DAMAGE_POOL`` setting. None when the object has no such pool (it
    cannot be harmed)."""
    from realm.core.world import setting
    name = obj.db.get("damage_pool") or setting("DAMAGE_POOL")
    return str(name) if has_pool(obj, str(name)) else None


def _chain(obj: GameObject, name: str) -> list[str]:
    """``name`` and each pool it overflows into that the object defines.
    Raises ValueError on a cycle."""
    chain = [name]
    pool = pool_def(obj, name)
    while pool is not None and pool.overflow is not None:
        if pool.overflow in chain:
            loop = " -> ".join(repr(n) for n in [*chain, pool.overflow])
            raise ValueError(f"{obj.name}: pools overflow in a cycle: {loop}")
        nxt = pool_def(obj, pool.overflow)
        if nxt is None:
            break
        chain.append(pool.overflow)
        pool = nxt
    return chain


def vital_pool(obj: GameObject) -> str | None:
    """The end of the overflow chain from ``damage_pool``: the pool whose
    spending is the object's defeat."""
    first = damage_pool(obj)
    if first is None:
        return None
    present = [name for name in _chain(obj, first) if has_pool(obj, name)]
    return present[-1]


# --- changing a pool ----------------------------------------------------------


def _check_amount(amount: int) -> int:
    amount = int(amount)
    if amount < 0:
        raise ValueError(f"a pool amount may not be negative (got {amount})")
    return amount


def _write(obj: GameObject, pool: Pool, old: int, new: int) -> None:
    if new != old:
        obj.db.set(pool.storage, new)


def _absent(obj: GameObject, name: str, amount: int) -> PoolChange:
    return PoolChange(obj, name, 0, 0, amount, 0)


def _harm(obj: GameObject, name: str, amount: int, soak: bool) -> PoolChange:
    pool = pool_def(obj, name)
    old = None if pool is None else _value(obj, pool)
    if old is None:
        return _absent(obj, name, amount)
    maximum = _maximum(obj, pool)
    soaked = 0
    if soak and pool.soak_attr:
        armor = obj.db.get(pool.soak_attr)
        soaked = min(amount, max(0, int(armor))) if _number(armor) else 0
    effective = amount - soaked
    if pool.direction == "down":
        room = None if pool.floor is None else max(0, old - pool.floor)
        applied = effective if room is None else min(effective, room)
        new = old - applied
    else:
        room = None if maximum is None else max(0, maximum - old)
        applied = effective if room is None else min(effective, room)
        new = old + applied
    _write(obj, pool, old, new)
    change = PoolChange(obj, name, old, new, amount, applied, soaked,
                        became_spent=(not _spent(pool, old, maximum)
                                      and _spent(pool, new, maximum)))
    remainder = effective - applied
    if remainder > 0 and pool.overflow is not None:
        change.spilled = _harm(obj, pool.overflow, remainder, soak)
    return change


def harm(obj: GameObject, name: str, amount: int, *, soak: bool = False) -> PoolChange:
    """Harm a pool: lower a down pool to its floor, raise an up pool to its
    max. What it cannot absorb spills into its ``overflow`` pool. With
    ``soak``, each pool reached first subtracts its ``soak_attr``. An object
    without the pool takes nothing (``applied == 0``)."""
    amount = _check_amount(amount)
    _chain(obj, name)                       # a cycle fails before anything changes
    return _harm(obj, name, amount, soak)


def mend(obj: GameObject, name: str, amount: int) -> PoolChange:
    """Undo harm: raise a down pool toward its max (unbounded without one),
    lower an up pool toward its floor. Never spills."""
    amount = _check_amount(amount)
    pool = pool_def(obj, name)
    old = None if pool is None else _value(obj, pool)
    if old is None:
        return _absent(obj, name, amount)
    maximum = _maximum(obj, pool)
    if pool.direction == "down":
        new = old + amount if maximum is None else max(old, min(maximum, old + amount))
    else:
        new = old - amount if pool.floor is None else min(old, max(pool.floor, old - amount))
    _write(obj, pool, old, new)
    return PoolChange(obj, name, old, new, amount, abs(new - old),
                      became_spent=(not _spent(pool, old, maximum)
                                    and _spent(pool, new, maximum)))


def _after_spending(obj: GameObject, pool: Pool | None,
                    amount: int) -> tuple[int, int] | None:
    """``(old, new)`` if ``obj`` can pay ``amount`` from ``pool``, else None."""
    old = None if pool is None else _value(obj, pool)
    if old is None:
        return None
    if pool.direction == "down":
        new = old - amount
        if pool.floor is not None and new < pool.floor:
            return None
    else:
        new = old + amount
        maximum = _maximum(obj, pool)
        if maximum is not None and new > maximum:
            return None
    return old, new


def can_spend(obj: GameObject, name: str, amount: int) -> bool:
    """Whether ``spend(obj, name, amount)`` would pay, changing nothing: a
    cost checked now and paid later (a step's movement, paid only once the
    move has happened)."""
    return _after_spending(obj, pool_def(obj, name), _check_amount(amount)) is not None


def spend(obj: GameObject, name: str, amount: int) -> PoolChange | None:
    """Pay a cost, all or nothing: lower a down pool (not past its floor) or
    raise an up pool (not past its max). None, with nothing changed, when
    the object is short or has no such pool."""
    amount = _check_amount(amount)
    pool = pool_def(obj, name)
    paid = _after_spending(obj, pool, amount)
    if paid is None:
        return None
    old, new = paid
    maximum = _maximum(obj, pool)
    _write(obj, pool, old, new)
    return PoolChange(obj, name, old, new, amount, amount,
                      became_spent=(not _spent(pool, old, maximum)
                                    and _spent(pool, new, maximum)))


def set_pool(obj: GameObject, name: str, value: int, *, max: int | None = None) -> None:
    """Initialize or resize a pool (chargen, a level gain). Fires nothing."""
    pool = _declared(obj, name) or Pool(name)
    obj.db.set(pool.storage, int(value))
    if max is not None:
        obj.db.set(pool.max_storage, int(max))


# --- settling -----------------------------------------------------------------


async def settle(change: PoolChange, *, source: GameObject | None = None) -> None:
    """Tell the world: ``pool:on_change`` for each link that moved, and
    ``pool:on_spent`` right after the link that became spent. With no world
    installed (a unit test of a bare effect) there is nobody to tell."""
    from realm.core.propagation import Action, propagate
    from realm.core.world import find_world
    if find_world() is None:
        return
    for link in change.links():
        if link.new == link.old:
            continue
        await propagate(Action(
            actor=source, target=link.obj, action_type=ActionType.POOL_CHANGE,
            extra={"pool": link.pool, "old": link.old, "new": link.new,
                   "applied": link.applied, "source": source}))
        if link.became_spent:
            await propagate(Action(
                actor=source, target=link.obj, action_type=ActionType.POOL_SPENT,
                extra={"pool": link.pool, "old": link.old, "new": link.new,
                       "applied": link.applied, "source": source}))


# --- world defaults -----------------------------------------------------------


def add_default(world: World, pool: Pool) -> None:
    """Register a world default (source 3). A different definition of the
    same name already registered is a FeatureError."""
    held = world.pools.get(pool.name)
    if held is not None and not held.same_as(pool):
        from realm.features import FeatureError
        raise FeatureError(f"pool {pool.name!r} is defined differently by "
                           f"{held.owner!r} and {pool.owner!r}")
    world.pools.setdefault(pool.name, pool)


__all__ = [
    "Pool", "PoolChange", "SPEC_KEYS",
    "pool_def", "pool_get", "pool_max", "pool_percent", "has_pool", "is_spent",
    "declared_pools",
    "damage_pool", "vital_pool",
    "harm", "mend", "spend", "can_spend", "set_pool", "settle", "add_default",
]
