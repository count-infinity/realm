"""
KERNEL_PLAN 8.4: a neutral ``GameSystem`` base.

The base keeps the interface with neutral defaults: no skill purchase, no
kill award, a score sheet that lists the character's pools. The
character-point economy GURPS and D20 share is ``PointBuyMixin``; Merc's
XP economy overrides the same hooks itself.
"""

from __future__ import annotations

import pytest

from realm.core.pools import Pool
from realm.games.d20.system import D20System
from realm.games.gurps.system import GurpsSystem
from realm.games.merc.system import MercSystem
from realm.std.rules.system import GameSystem, PointBuyMixin
from realm.testing import Simulator


class PlainRules(GameSystem):
    """A game that adds nothing to the base."""


def _player(sim, **attrs):
    room = sim.room("Square")
    return sim.player("Ann", location=room, **attrs)


class TestNeutralDefaults:

    def test_the_interface_has_neutral_answers(self):
        rules = PlainRules()
        assert rules.improve_cost("stealth", 10) is None
        assert rules.death_award(object(), None) == 0
        assert [p.name for p in rules.pools()] == ["hp"]

    def test_grant_award_does_nothing(self):
        with Simulator(game_system=PlainRules) as sim:
            ann = _player(sim)
            PlainRules().grant_award(ann, 5)
            assert ann.db.character_points is None
            assert sim.seen(ann) == []

    def test_score_lists_the_pools(self):
        with Simulator(game_system=PlainRules) as sim:
            ann = _player(sim, hp=7, max_hp=10, strength=12)
            assert PlainRules().score_lines(ann) == ["HP: 7/10"]

    def test_score_lists_a_pool_the_object_declares(self):
        with Simulator(game_system=PlainRules) as sim:
            ann = _player(sim, hp=7, max_hp=10, stress=2, max_stress=6,
                          pools={"stress": {"direction": "up"}})
            assert PlainRules().score_lines(ann) == ["HP: 7/10   Stress: 2/6"]


@pytest.mark.asyncio
class TestNeutralInPlay:

    async def test_improve_says_there_is_no_skill_purchase(self):
        with Simulator(game_system=PlainRules) as sim:
            ann = _player(sim, character_points=50)
            await sim.do(ann, "improve stealth")
            assert any("no skill purchase" in line for line in sim.seen(ann))
            assert ann.db.character_points == 50
            assert ann.db.skill_stealth is None

    async def test_a_kill_awards_nothing(self):
        from realm.core.pools import harm, settle
        with Simulator(game_system=PlainRules) as sim:
            ann = _player(sim)
            rat = sim.obj("rat", location=ann.location, hp=1, max_hp=1, points=100)
            sim.seen(ann)
            await settle(harm(rat, "hp", 1), source=ann)
            assert ann.db.character_points is None
            assert not any("You gain" in line for line in sim.seen(ann))


class TestPointBuy:

    def test_gurps_and_d20_buy_points_merc_does_not(self):
        assert isinstance(GurpsSystem(), PointBuyMixin)
        assert isinstance(D20System(), PointBuyMixin)
        assert not isinstance(MercSystem(), PointBuyMixin)

    def test_overrides_that_equal_the_default_are_gone(self):
        assert "improve_cost" not in GurpsSystem.__dict__
        assert GurpsSystem().improve_cost("stealth", 14) == 4
        assert D20System().improve_cost("stealth", 18) > 4     # still escalating

    def test_point_buy_banks_character_points(self):
        with Simulator() as sim:
            ann = _player(sim)
            D20System().grant_award(ann, 3)
            assert ann.db.character_points == 3
            assert D20System().death_award(sim.obj("ogre", points=40)) == 4


class TestMercPools:

    def test_hp_mana_and_move(self):
        assert MercSystem().pools() == [Pool("hp"), Pool("mana"), Pool("move")]

    def test_a_merc_character_has_them(self):
        with Simulator(game_system=MercSystem) as sim:
            ann = _player(sim)
            MercSystem().apply_baseline(ann)
            lines = "\n".join(MercSystem().score_lines(ann))
            assert "HP: 20/20   Mana: 100/100   Move: 100/100" in lines
