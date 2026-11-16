"""
Hunger, thirst and fatigue (MUD_PLAN step 12), after CoffeeMud
(``Libraries/MUDFight.java::expendEnergy``, ``Common/DefaultCharState.java``,
``Locales/StdRoom.java::thirstPerRound``).

The needs are pools: ``food`` and ``water`` (down: full at max, spent at 0)
and ``fatigue`` (up: spent at its max). A character has a need exactly
when it has that pool; the game system declares who does (Merc: food and
water). Every ``NEEDS_INTERVAL`` seconds each online player who has one:

- loses food by its weight factor (``weight / NEEDS_BASE_WEIGHT``, 1
  without a weight) and water by that times the room's thirst rate, unless
  asleep, an administrator, tagged ``no_needs`` or in a ``no_needs`` zone.
  Fractions carry over (``food_debt``, ``water_debt``). Walking a room
  costs one more interval's loss;
- while food or water is spent, counts ``hungry_ticks`` / ``thirsty_ticks``
  and is reminded in rising alarm; past ``HUNGER_DEATH_HOURS`` /
  ``THIRST_DEATH_HOURS`` of them it dies through the vital pool;
- gains 1 fatigue awake and sheds ``FATIGUE_SLEEP_RECOVERY`` asleep.

Hunger and thirst each take half of every recovery (the ``vitals``
multiplier); spent fatigue halves mana and movement recovery. Awards are
scaled by ``HUNGRY_AWARD`` while hungry or thirsty (the ``rules`` award
filter). See docs/guides/life-and-death.md.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from realm.core.action_types import ActionType
from realm.core.pools import (
    harm,
    has_pool,
    is_spent,
    mend,
    pool_def,
    pool_get,
    pool_max,
    set_pool,
    settle,
    vital_pool,
)
from realm.core.zones import zone_masters, zone_property

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action
    from realm.core.world import World

FOOD = "food"
WATER = "water"
FATIGUE = "fatigue"
NEEDS = (FOOD, WATER, FATIGUE)

#: What each climate tag adds to a room's thirst rate (CoffeeMud's
#: ``thirstPerRound``: one, plus hot, dry and windy, minus wet).
CLIMATE = {"climate:hot": 1, "climate:dry": 1, "climate:windy": 1, "climate:wet": -1}

#: How many ticks before death every tick brings a warning (CoffeeMud's 30).
NEAR_DEATH_TICKS = 30

#: Per need: the pool, its counter, its fraction carried over, its death
#: setting, and its lines (first half, past half, past three quarters, the
#: last ticks, death). CoffeeMud's words.
_HUNGER = (FOOD, "hungry_ticks", "food_debt", "HUNGER_DEATH_HOURS", (
    "You are hungry.",
    "You are famished! Eat something!",
    "You are starved! Eat something!",
    "You are starved, and near death. EAT SOMETHING!",
    "YOU ARE DYING OF HUNGER!"))
_THIRST = (WATER, "thirsty_ticks", "water_debt", "THIRST_DEATH_HOURS", (
    "You are thirsty.",
    "You are parched! Drink something!",
    "You are dehydrated! Drink something!",
    "You are dehydrated, and near death. DRINK SOMETHING!",
    "YOU ARE DYING OF THIRST!"))
EXHAUSTED_LINE = "You are exhausted."


def now() -> float:
    """The clock the sweep runs on (tests replace it)."""
    return time.monotonic()


def _setting(name: str, default: Any) -> Any:
    from realm.core.world import setting
    return setting(name, default)


# --- reading the state ----------------------------------------------------------


def is_hungry(obj: GameObject) -> bool:
    """``obj`` has a ``food`` pool and it is empty."""
    return has_pool(obj, FOOD) and is_spent(obj, FOOD)


def is_thirsty(obj: GameObject) -> bool:
    """``obj`` has a ``water`` pool and it is empty."""
    return has_pool(obj, WATER) and is_spent(obj, WATER)


def is_exhausted(obj: GameObject) -> bool:
    """``obj`` has a ``fatigue`` pool and it is at its max."""
    return has_pool(obj, FATIGUE) and is_spent(obj, FATIGUE)


def has_needs(obj: GameObject) -> bool:
    return any(has_pool(obj, name) for name in NEEDS)


def weight_factor(obj: GameObject) -> float:
    """``weight / NEEDS_BASE_WEIGHT``: how fast ``obj`` gets hungry and
    thirsty; 1 without a weight."""
    weight = obj.db.get("weight")
    if isinstance(weight, (int, float)) and not isinstance(weight, bool) and weight > 0:
        return float(weight) / float(_setting("NEEDS_BASE_WEIGHT", 150))
    return 1.0


def climate_tags(room: GameObject | None) -> list[str]:
    """The room's ``climate:*`` tags, else its zone masters'."""
    if room is None:
        return []
    tags = [t for t in room.tags.to_list() if t.startswith("climate:")]
    if tags:
        return tags
    return [t for master in zone_masters(room) for t in master.tags.to_list()
            if t.startswith("climate:")]


def thirst_rate(room: GameObject | None) -> int:
    """1, plus 1 each for ``climate:hot``, ``climate:dry`` and
    ``climate:windy``, minus 1 for ``climate:wet``; never below 0."""
    return max(0, 1 + sum(CLIMATE.get(tag, 0) for tag in set(climate_tags(room))))


def exempt(obj: GameObject) -> bool:
    """An administrator, a character tagged ``no_needs``, or one standing
    in a zone that sets ``no_needs``, neither loses nor counts."""
    from realm.permissions.roles import Role, get_role
    if obj.has_tag("no_needs") or get_role(obj) >= Role.ADMIN:
        return True
    return bool(zone_property(obj.location, "no_needs", False))


def _death_ticks(setting_name: str) -> int:
    """The setting's hours as ticks of ``NEEDS_INTERVAL``; 0 for never."""
    hours = float(_setting(setting_name, 0) or 0)
    if hours <= 0:
        return 0
    return max(1, round(hours * 3600 / float(_setting("NEEDS_INTERVAL", 4))))


def reminder(ticks: int, limit: int, every: int, lines: tuple[str, ...]) -> str | None:
    """What a character ``ticks`` intervals without is told this tick, or
    None: every tick of the last 30 before ``limit``; otherwise on the first
    tick and every ``every`` after, by how far along it is."""
    if limit and ticks > limit - NEAR_DEATH_TICKS:
        return lines[3]
    if every <= 0 or (ticks - 1) % every:
        return None
    if limit and ticks > limit // 2 + limit // 4:
        return lines[2]
    if limit and ticks > limit // 2:
        return lines[1]
    return lines[0]


# --- the recovery multiplier and the award filter ---------------------------------


def needs_multiplier(obj: GameObject, pool_name: str) -> float:
    """The ``vitals`` multiplier: 1, less a half while hungry and a half
    while thirsty; for ``mana`` and ``move``, halved again while
    exhausted."""
    factor = 1.0
    if is_hungry(obj):
        factor -= 0.5
    if is_thirsty(obj):
        factor -= 0.5
    if pool_name in ("mana", "move") and is_exhausted(obj):
        factor *= 0.5
    return max(0.0, factor)


def award_filter(player: GameObject, amount: int) -> int:
    """The ``rules`` award filter: ``HUNGRY_AWARD`` times the amount while
    hungry or thirsty (1.0, the default, changes nothing)."""
    if is_hungry(player) or is_thirsty(player):
        return round(int(amount) * float(_setting("HUNGRY_AWARD", 1.0)))
    return int(amount)


# --- the service ------------------------------------------------------------------


class Needs:
    """``world.services["needs"]``: one interval for everyone (``tick``),
    for one character (``tick_one``), and one interval's loss
    (``expend``, which walking also costs)."""

    def __init__(self, world: World):
        self.world = world
        self._last: float | None = None

    def _setting(self, name: str) -> Any:
        return self.world.setting(name)

    async def _lose(self, obj: GameObject, name: str, debt_attr: str, amount: float) -> None:
        if not has_pool(obj, name) or amount <= 0:
            return
        total = float(obj.db.get(debt_attr) or 0) + amount
        whole = int(total)
        obj.db.set(debt_attr, total - whole)
        if whole > 0:
            await settle(harm(obj, name, whole))

    async def expend(self, obj: GameObject) -> None:
        """One interval's hunger and thirst (CoffeeMud's ``expendEnergy``):
        food by the weight factor, water by that times the room's thirst
        rate, each scaled by ``FOOD_LOSS`` / ``WATER_LOSS`` percent."""
        factor = weight_factor(obj)
        await self._lose(obj, FOOD, "food_debt",
                         factor * float(self._setting("FOOD_LOSS")) / 100)
        await self._lose(obj, WATER, "water_debt",
                         factor * thirst_rate(obj.location)
                         * float(self._setting("WATER_LOSS")) / 100)

    async def _fatigue(self, obj: GameObject, asleep: bool, rising: bool) -> None:
        if not has_pool(obj, FATIGUE):
            return
        if asleep:
            amount = int(self._setting("FATIGUE_SLEEP_RECOVERY"))
            if amount > 0:
                await settle(mend(obj, FATIGUE, amount))
        elif rising:
            await settle(harm(obj, FATIGUE, 1))
        if is_exhausted(obj):
            ticks = int(obj.db.get("exhausted_ticks") or 0) + 1
            obj.db.exhausted_ticks = ticks
            every = int(self._setting("NEEDS_REMINDER_TICKS"))
            if every > 0 and (ticks - 1) % every == 0:
                obj.msg(EXHAUSTED_LINE)
        elif obj.db.get("exhausted_ticks") is not None:
            obj.db.delete("exhausted_ticks")

    async def _going_without(self, obj: GameObject, need: tuple) -> bool:
        """Count, remind, and past the limit kill. True when it killed."""
        name, counter, _debt, death_setting, lines = need
        if not (has_pool(obj, name) and is_spent(obj, name)):
            return False
        ticks = int(obj.db.get(counter) or 0) + 1
        obj.db.set(counter, ticks)
        limit = _death_ticks(death_setting)
        if limit and ticks > limit:
            obj.msg(lines[4])
            await self._die(obj)
            return True
        line = reminder(ticks, limit, int(self._setting("NEEDS_REMINDER_TICKS")), lines)
        if line is not None:
            obj.msg(line)
        return False

    async def _die(self, obj: GameObject) -> None:
        """Spend the vital pool, so the ordinary death path runs (no
        killer); then, as CoffeeMud restores a body on death, fill food
        and water and forget the counts."""
        vital = vital_pool(obj)
        pool = pool_def(obj, vital) if vital is not None else None
        value = pool_get(obj, vital) if vital is not None else None
        if pool is not None and value is not None and not is_spent(obj, vital):
            if pool.direction == "down":
                amount = max(1, value - pool.spent_at)
            else:
                amount = max(1, int(pool_max(obj, vital) or value + 1) - value)
            await settle(harm(obj, vital, amount))
        for name in (FOOD, WATER):
            maximum = pool_max(obj, name)
            if maximum is not None:
                set_pool(obj, name, maximum)
        for attr in ("hungry_ticks", "thirsty_ticks", "food_debt", "water_debt"):
            if obj.db.get(attr) is not None:
                obj.db.delete(attr)

    async def tick_one(self, obj: GameObject) -> None:
        """One interval for one character with needs."""
        if not has_needs(obj):
            return
        asleep = obj.has_tag("sleeping")
        if exempt(obj):
            await self._fatigue(obj, asleep, rising=False)
            return
        if not asleep:
            await self.expend(obj)
        await self._fatigue(obj, asleep, rising=True)
        for need in (_HUNGER, _THIRST):
            if await self._going_without(obj, need):
                return

    async def tick(self) -> None:
        """One interval for every online player."""
        from realm.gateway.session import online_players
        for player in online_players():
            await self.tick_one(player)

    async def sweep(self, _store: Any = None) -> None:
        """The reaper's call (every ``REAP_INTERVAL``): one tick for each
        whole ``NEEDS_INTERVAL`` passed since the last."""
        moment = now()
        if self._last is None:
            self._last = moment
            return
        interval = max(0.001, float(self._setting("NEEDS_INTERVAL")))
        due = int((moment - self._last) // interval)
        if due <= 0:
            return
        self._last += due * interval
        for _ in range(min(due, 10)):          # a stalled server does not starve anyone
            await self.tick()


def _service() -> Needs | None:
    from realm.core.world import find_world
    world = find_world()
    return world.services.get("needs") if world is not None else None


async def needs_sweep(store: Any) -> None:
    """The ``needs`` reaper: the world's service decides whether a tick is due."""
    service = _service()
    if service is not None:
        await service.sweep(store)


async def needs_observer(action: Action) -> None:
    """``pool:on_change``: food or water above empty ends the count of
    ticks without it, the moment it happens."""
    if action.action_type != ActionType.POOL_CHANGE or action.target is None:
        return
    name = action.extra.get("pool")
    for need in (_HUNGER, _THIRST):
        if name == need[0] and not is_spent(action.target, name):
            if action.target.db.get(need[1]) is not None:
                action.target.db.delete(need[1])


async def exertion(actor: GameObject, origin: GameObject | None,
                   destination: GameObject | None, exit_obj: GameObject | None,
                   *, fleeing: bool) -> None:
    """``feature.after_traverse``: each room walked costs one more
    interval's hunger and thirst."""
    if not actor.is_player or not has_needs(actor) or exempt(actor):
        return
    # A rider is carried: the walking is the mount's (CoffeeMud spends a
    # rider's energy only when it walks).
    from realm.core.world import find_world
    world = find_world()
    companions = world.services.get("companions") if world is not None else None
    if companions is not None and companions.payer(actor) is not actor:
        return
    service = _service()
    if service is not None:
        await service.expend(actor)


# --- softcode -------------------------------------------------------------------


def _readable(frame, obj: GameObject | str | None, name: str) -> GameObject | None:
    """The character, when the executor may read its ``name`` pool."""
    from realm.core.attrflags import readable_attr
    target = frame.resolve(obj)
    if target is None or not readable_attr(target, name, frame.executor):
        return None
    return target


def hungry(frame, obj: GameObject | str | None) -> bool:
    """
    True when the character's ``food`` pool is empty: it recovers at half
    speed and counts toward dying of hunger. False without the pool.

    Example: if hungry(enactor): pemit(enactor, 'The smell of bread makes you dizzy.')
    """
    target = _readable(frame, obj, FOOD)
    return target is not None and is_hungry(target)


def thirsty(frame, obj: GameObject | str | None) -> bool:
    """
    True when the character's ``water`` pool is empty: it recovers at half
    speed and counts toward dying of thirst. False without the pool.

    Example: thirsty(enactor)
    """
    target = _readable(frame, obj, WATER)
    return target is not None and is_thirsty(target)


__all__ = ["FOOD", "WATER", "FATIGUE", "NEEDS", "CLIMATE", "NEAR_DEATH_TICKS",
           "EXHAUSTED_LINE", "now", "is_hungry", "is_thirsty", "is_exhausted", "has_needs",
           "weight_factor", "climate_tags", "thirst_rate", "exempt", "reminder",
           "needs_multiplier", "award_filter", "Needs", "needs_sweep", "needs_observer",
           "exertion", "hungry", "thirsty"]
