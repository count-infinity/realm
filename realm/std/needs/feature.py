"""
The ``needs`` feature.

Hunger, thirst and fatigue, after CoffeeMud (MUD_PLAN step 12). The needs
are the ``food``, ``water`` and ``fatigue`` pools; the game system decides
who has them (Merc declares food and water). See
docs/guides/life-and-death.md.
"""

from __future__ import annotations

from realm.features import Feature, FeatureError
from realm.std.needs.needs import (
    Needs,
    award_filter,
    exertion,
    hungry,
    needs_multiplier,
    needs_observer,
    needs_sweep,
    thirsty,
)

feature = Feature(
    'needs',
    doc='Hunger, thirst and fatigue, after CoffeeMud.',
)

feature.setting(
    "NEEDS_INTERVAL", 4,
    "Seconds between hunger and thirst ticks (CoffeeMud's tick). Each tick an "
    "awake, online player loses food and water, and gains fatigue.")
feature.setting(
    "FOOD_LOSS", 100,
    "Percent: how much food a tick (and each room walked) costs, against 1 for a "
    "character of `NEEDS_BASE_WEIGHT`.")
feature.setting(
    "WATER_LOSS", 100,
    "Percent: how much water a tick (and each room walked) costs, against the "
    "room's thirst rate for a character of `NEEDS_BASE_WEIGHT`.")
feature.setting(
    "NEEDS_REMINDER_TICKS", 60,
    "Ticks between \"You are hungry.\" reminders (and \"You are exhausted.\").")
feature.setting(
    "HUNGER_DEATH_HOURS", 12,
    "Hours of online time with an empty `food` pool before the character dies. "
    "0: hunger never kills.")
feature.setting(
    "THIRST_DEATH_HOURS", 6,
    "Hours of online time with an empty `water` pool before the character dies. "
    "0: thirst never kills.")
feature.setting(
    "HUNGRY_AWARD", 1.0,
    "A factor on experience and character point awards while hungry or thirsty. "
    "0 is CoffeeMud's \"no experience while hungry\".")
feature.setting(
    "FATIGUE_SLEEP_RECOVERY", 3,
    "How much `fatigue` a sleeping character sheds each tick (it gains 1 awake).")

feature.reaper(needs_sweep)
feature.observer(needs_observer)
feature.after_traverse(exertion)

feature.softfn(hungry, group='Pools', readonly=True)
feature.softfn(thirsty, group='Pools', readonly=True)


@feature.on_install
def _offer_needs(world) -> None:
    """``world.services["needs"]``; hunger and thirst slow the ``vitals``
    recovery, and scale the ``rules`` awards, when those are loaded. They
    must be installed first, so ``needs`` comes after them in
    ``FEATURES``."""
    loaded = set(world.features.names)
    for name in ("vitals", "rules"):
        if name in loaded and name not in world.services:
            raise FeatureError(f"'needs' must come after {name!r} in FEATURES "
                               f"(it adds to the {name} service)")
    world.services["needs"] = Needs(world)
    vitals = world.services.get("vitals")
    if vitals is not None:
        vitals.multipliers.append(needs_multiplier)
    rules = world.services.get("rules")
    if rules is not None:
        rules.award_filters.append(award_filter)
