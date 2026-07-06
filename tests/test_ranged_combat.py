"""
Ranged combat: range bands, shoot/aim/close/withdraw/cover, wielded
weapons. Uses the deterministic FixedRuleset fixtures from
test_combat_encounters.
"""

from __future__ import annotations

# ruff: noqa: F811  (pytest fixture params shadow the imported fixture)

import pytest

from realm.combat.maneuver import QueuedAction
from realm.combat.system import find_wielded
from realm.core.objects import GameObject
from tests.test_combat_encounters import (  # noqa: F401  (manager fixture)
    drain,
    make_fighter,
    manager,  # noqa: F811
)


def make_gun(owner, *, acc=2, name="laser pistol"):
    gun = GameObject(name, location=owner, tags=["thing", "ranged", "wielded"])
    gun.db.skill_type = "guns"
    gun.db.acc = acc
    gun.db.damage = "1d6"
    return gun


async def one_round(encounter):
    await encounter.resolve_round()


@pytest.mark.asyncio
class TestRangeBands:

    async def test_melee_blocked_at_range(self, manager):
        room = GameObject("Alley", tags=["room"])
        alice, sess = make_fighter("Alice", room)
        thug, _ = make_fighter("Thug", room, player=False)
        encounter = await manager.initiate(alice, thug)

        encounter.get(alice.id).range_band = 1
        encounter.queue(alice, QueuedAction(maneuver="attack", target_id=thug.id))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)

        assert thug.db.get("hp") == 10  # untouched
        assert any("out of melee reach" in m for m in drain(sess))

    async def test_close_reengages(self, manager):
        room = GameObject("Alley", tags=["room"])
        alice, sess = make_fighter("Alice", room)
        thug, _ = make_fighter("Thug", room, player=False)
        encounter = await manager.initiate(alice, thug)

        participant = encounter.get(alice.id)
        participant.range_band = 1
        encounter.queue(alice, QueuedAction(maneuver="close"))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)
        assert participant.range_band == 0

        encounter.queue(alice, QueuedAction(maneuver="attack", target_id=thug.id))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)
        assert thug.db.get("hp") < 10  # FixedRuleset always hits for 3

    async def test_withdraw_opens_range(self, manager):
        room = GameObject("Alley", tags=["room"])
        alice, _ = make_fighter("Alice", room)
        thug, _ = make_fighter("Thug", room, player=False)
        encounter = await manager.initiate(alice, thug)

        encounter.queue(alice, QueuedAction(maneuver="withdraw"))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)
        assert encounter.get(alice.id).range_band == 1


@pytest.mark.asyncio
class TestShooting:

    async def test_shoot_needs_ranged_weapon(self, manager):
        room = GameObject("Alley", tags=["room"])
        alice, sess = make_fighter("Alice", room)
        thug, _ = make_fighter("Thug", room, player=False)
        encounter = await manager.initiate(alice, thug)

        encounter.queue(alice, QueuedAction(maneuver="shoot", target_id=thug.id))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)

        assert thug.db.get("hp") == 10
        assert any("wielded ranged weapon" in m for m in drain(sess))

    async def test_shoot_hits_at_range(self, manager):
        room = GameObject("Alley", tags=["room"])
        alice, _ = make_fighter("Alice", room, skill_guns=14)
        thug, _ = make_fighter("Thug", room, player=False)
        make_gun(alice)
        encounter = await manager.initiate(alice, thug)

        encounter.get(alice.id).range_band = 1  # melee couldn't reach
        encounter.queue(alice, QueuedAction(maneuver="shoot", target_id=thug.id))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)

        assert thug.db.get("hp") == 7  # fixed 3 damage

    async def test_melee_refuses_to_club_with_rifle(self, manager):
        room = GameObject("Alley", tags=["room"])
        alice, _ = make_fighter("Alice", room)
        thug, _ = make_fighter("Thug", room, player=False)
        gun = make_gun(alice)
        encounter = await manager.initiate(alice, thug)

        encounter.queue(alice, QueuedAction(maneuver="attack", target_id=thug.id))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)
        # Attack resolves unarmed (weapon=None); gun stays wielded.
        assert thug.db.get("hp") == 7
        assert find_wielded(alice) is gun


@pytest.mark.asyncio
class TestAimAndCover:

    async def test_aim_accumulates_and_is_consumed(self, manager):
        room = GameObject("Alley", tags=["room"])
        alice, sess = make_fighter("Alice", room, skill_guns=12)
        thug, _ = make_fighter("Thug", room, player=False)
        make_gun(alice, acc=2)
        encounter = await manager.initiate(alice, thug)
        participant = encounter.get(alice.id)

        encounter.queue(alice, QueuedAction(maneuver="aim", target_id=thug.id))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)
        assert participant.aim_bonus == 2  # weapon Acc

        encounter.queue(alice, QueuedAction(maneuver="aim", target_id=thug.id))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)
        assert participant.aim_bonus == 3  # +1 per extra round

        encounter.queue(alice, QueuedAction(maneuver="shoot", target_id=thug.id))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)
        assert participant.aim_bonus == 0  # consumed by the shot
        assert thug.db.get("hp") == 7

    async def test_cover_needs_cover_object(self, manager):
        room = GameObject("Alley", tags=["room"])
        alice, sess = make_fighter("Alice", room)
        thug, _ = make_fighter("Thug", room, player=False)
        encounter = await manager.initiate(alice, thug)

        encounter.queue(alice, QueuedAction(maneuver="cover"))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)
        assert encounter.get(alice.id).in_cover is False
        assert any("nothing here to take cover" in m for m in drain(sess))

    async def test_cover_stance_and_shoot_penalties_flow(self, manager):
        """Cover + close-quarters penalties reach the ruleset's modifier
        dict — verified through a recording ruleset hook."""
        room = GameObject("Alley", tags=["room"])
        GameObject("dumpster", location=room, tags=["thing", "cover"])
        alice, _ = make_fighter("Alice", room, skill_guns=12)
        thug, _ = make_fighter("Thug", room, player=False)
        make_gun(alice, acc=2)
        encounter = await manager.initiate(alice, thug)

        encounter.queue(thug, QueuedAction(maneuver="cover"))
        encounter.queue(alice, QueuedAction(maneuver="wait"))
        await one_round(encounter)
        assert encounter.get(thug.id).in_cover is True

        seen = {}
        ruleset = manager.combat_system.ruleset
        original = ruleset.roll_attack

        def recording(atk, dfn, weapon=None, modifiers=None):
            seen['modifiers'] = dict(modifiers or {})
            return original(atk, dfn, weapon, modifiers)

        ruleset.roll_attack = recording
        try:
            encounter.queue(alice, QueuedAction(maneuver="shoot",
                                                target_id=thug.id))
            encounter.queue(thug, QueuedAction(maneuver="wait"))
            await one_round(encounter)
        finally:
            ruleset.roll_attack = original

        assert seen['modifiers'].get('cover') == -2
        assert seen['modifiers'].get('close quarters') == -2  # both band 0

    async def test_withdraw_drops_cover(self, manager):
        room = GameObject("Alley", tags=["room"])
        GameObject("dumpster", location=room, tags=["thing", "cover"])
        alice, _ = make_fighter("Alice", room)
        thug, _ = make_fighter("Thug", room, player=False)
        encounter = await manager.initiate(alice, thug)
        participant = encounter.get(alice.id)

        encounter.queue(alice, QueuedAction(maneuver="cover"))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)
        assert participant.in_cover is True

        encounter.queue(alice, QueuedAction(maneuver="withdraw"))
        encounter.queue(thug, QueuedAction(maneuver="wait"))
        await one_round(encounter)
        assert participant.in_cover is False and participant.range_band == 1


@pytest.mark.asyncio
class TestNpcArcherStrategy:

    async def test_strategy_can_shoot(self, manager):
        """NPC AI uses the same vocabulary: a sniper strategy shoots."""
        room = GameObject("Alley", tags=["room"])
        alice, _ = make_fighter("Alice", room)
        sniper, _ = make_fighter("Sniper", room, player=False, skill_guns=14)
        make_gun(sniper)
        sniper.db.combat_strategy = [["", "shoot"]]
        encounter = await manager.initiate(alice, sniper)

        encounter.queue(alice, QueuedAction(maneuver="wait"))
        await one_round(encounter)

        assert alice.db.get("hp") == 7  # the sniper's strategy fired
