"""
The ``achievements`` feature.

Achievements as data (``achievement_def``), earned once per account or per
character, granting tags and check modifiers to every character of the
account and character slots to the account (MUD_PLAN 6.5, Decision D2;
docs/guides/accounts.md).
"""

from __future__ import annotations

from types import SimpleNamespace

from realm.features import Feature
from realm.std.achievements import softcode
from realm.std.achievements.achievements import (
    ACHIEVEMENT_EVENT,
    achievement_modifier,
    character_slots,
    clear_cache,
    cmd_achievements,
    grant,
    has,
    login_observer,
)

feature = Feature(
    'achievements',
    requires=['accounts'],
    doc='Achievements that reach every character of an account.',
)

feature.def_kind("achievement", "achievement_def")
feature.command('achievements', cmd_achievements, category='utility',
                help_text='List your achievements')
feature.check_modifier(achievement_modifier)
feature.observer(login_observer)
feature.on_reload(clear_cache)
feature.on_close(clear_cache)
feature.event(ACHIEVEMENT_EVENT, hook="ACHIEVEMENT",
              doc="a character earns an achievement",
              payload={"achievement": "the achievement's name"})

feature.softfn(softcode.grant_achievement, group='Accounts', harm=True)
feature.softfn(softcode.has_achievement, group='Accounts', readonly=True)


async def _grant(engine, frame, obj, name) -> None:
    """Queued by softcode grant_achievement()."""
    await grant(obj, name)


feature.queue_kind("achievement", _grant)


@feature.on_install
def _offer_achievements(world) -> None:
    """Other features grant achievements through
    ``world.services["achievements"]`` (``grant``, ``has``): ``quests``'
    rewards. Its earned achievements' ``characters`` grants raise an
    account's character limit, through the ``accounts`` service's
    ``slot_sources`` (``accounts`` may not import this feature)."""
    world.services["achievements"] = SimpleNamespace(grant=grant, has=has)
    world.services["accounts"].slot_sources.append(character_slots)
