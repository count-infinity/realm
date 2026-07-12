"""
Stage B of the data-driven rules kernel: resolution is composed from
genre-neutral bound primitives, is graded (not bool), can be defined as a
softcode rule (game-system-as-data), and is entity-agnostic — one
resolver drives a person, a dice pool, and a ship.
"""

from __future__ import annotations

import pytest

from realm.core import dice
from realm.core.checks import resolve_with_rule, set_skill_defaults, skill_level
from realm.core.objects import GameObject
from realm.scripting import clear_bindings, softcode_function
from realm.systems import GurpsSystem
from realm.systems.base import GameSystem
from realm.systems.gurps import BUILTIN_SKILL_DEFAULTS
from realm.testing import Simulator


@pytest.fixture(autouse=True)
def gurps_skills():
    set_skill_defaults(BUILTIN_SKILL_DEFAULTS)
    yield


# --- The primitives ----------------------------------------------------------

class TestDicePrimitives:

    def test_roll_expressions(self):
        for _ in range(50):
            assert 3 <= dice.roll("3d6") <= 18
            assert 1 <= dice.roll("d20") <= 20
            assert -4 <= dice.roll("4dF") <= 4          # Fudge
            assert dice.roll("10d1") == 10              # deterministic
            assert dice.roll("2d6+3") >= 5
        assert dice.roll(7) == 7                        # bare int passes through

    def test_keep_highest(self):
        # kh3 of 4d1 keeps three 1s.
        assert dice.roll("4d1kh3") == 3

    def test_reducers_are_graded_not_bool(self):
        r = dice.margin_under(9, 12)
        assert r.success and r.margin == 3              # succeeded BY 3
        assert dice.margin_over(16, 15).margin == 1
        # dice-pool: sides=1 makes every die a guaranteed success
        assert dice.net_successes(5, 1, sides=1).margin == 5
        assert dice.band(11, 7, 10).margin == 2         # cleared both tiers
        assert dice.band(8, 7, 10).margin == 1          # cleared one
        assert dice.band(5, 7, 10).margin == 0 and not dice.band(5, 7, 10)


# --- Game system as a softcode rule ------------------------------------------

class GurpsAsData(GameSystem):
    system_id = "gurps-data"
    resolve_rule = "margin_under(roll('3d6'), skill() + mod)"


class PoolSystem(GameSystem):
    """A Shadowrun-shaped system defined entirely as data — no Python
    resolver, just a rule composing the pool primitive."""
    system_id = "pool"
    resolve_rule = "net_successes(attr('pool'), 3)"


class TestSystemAsData:

    def test_softcode_gurps_rule_behaves_like_gurps(self):
        system = GurpsAsData()
        pro = GameObject("Pro")
        pro.db.skill_stealth = 16
        oaf = GameObject("Oaf")
        oaf.db.skill_stealth = 4
        pro_wins = sum(system.resolve_check(pro, "stealth", 0).success
                       for _ in range(200))
        oaf_wins = sum(system.resolve_check(oaf, "stealth", 0).success
                       for _ in range(200))
        assert pro_wins > 180 and oaf_wins < 20          # roll-under behaviour

    def test_pool_rule_is_graded(self):
        system = PoolSystem()
        big = GameObject("Big")
        big.db.pool = 12
        small = GameObject("Small")
        small.db.pool = 1
        big_hits = sum(system.resolve_check(big, "hack", 0).margin
                       for _ in range(100))
        small_hits = sum(system.resolve_check(small, "hack", 0).margin
                         for _ in range(100))
        assert big_hits > small_hits                     # bigger pool, more hits


# --- The keystone: ONE resolver, person + pool + ship ------------------------

class TestEntityAgnosticResolver:
    """CoffeeMud paid a whole parallel siege engine because its resolver
    was MOB-typed. Ours binds by name: a ship runs the same rule as a
    person, with no hp/melee anywhere in sight."""

    def test_one_rule_resolves_person_and_ship(self):
        rule = "net_successes(attr('pool'), 2)"

        person = GameObject("Hacker")
        person.db.pool = 8
        ship = GameObject("Corvette", tags=["vehicle"])
        ship.db.pool = 8
        # The ship has NO character shape — no hp, no melee, no skills.
        assert ship.db.get("hp") is None
        assert ship.db.get("skill_melee") is None

        pr = resolve_with_rule(person, "hacking", 0, rule)
        sr = resolve_with_rule(ship, "gunnery", 0, rule)
        # Same machinery, both graded CheckResults.
        assert isinstance(pr, dice.CheckResult) and isinstance(sr, dice.CheckResult)
        assert pr.margin >= 0 and sr.margin >= 0
        assert sr.skill == "gunnery"                     # skill name threaded through

    def test_ship_attack_scales_with_its_own_stat(self):
        rule = "net_successes(attr('gunnery'), 3)"
        big = GameObject("Battleship")
        big.db.gunnery = 14
        scout = GameObject("Scout")
        scout.db.gunnery = 2
        big_hits = sum(resolve_with_rule(big, "gunnery", 0, rule).margin
                       for _ in range(100))
        scout_hits = sum(resolve_with_rule(scout, "gunnery", 0, rule).margin
                         for _ in range(100))
        assert big_hits > scout_hits


# --- Kernel stays genre-neutral (vision-keeper fixes) ------------------------

class TestKernelNeutrality:
    """The kernel must not encode a specific game's rules (#1/#3), and
    mechanics must not assume a character shape (#7)."""

    def test_gurps_owns_its_resolver_not_the_kernel(self):
        # GurpsSystem defines its OWN resolve_check (with GURPS crits) —
        # it is not inherited from the base / the neutral kernel default.
        assert GurpsSystem.resolve_check is not GameSystem.resolve_check

    def test_unlisted_skill_does_not_assume_a_humanoid_stat(self):
        # A ship with no 'intelligence' rolling an unlisted skill must NOT
        # be silently rated off intelligence — it gets a neutral floor.
        set_skill_defaults({})                    # nothing listed
        ship = GameObject("Corvette", tags=["vehicle"])
        ship.db.intelligence = 99                 # even if it had one...
        assert skill_level(ship, "gunnery") == 5  # neutral floor, not 99-5


# --- Native bindings (the escape hatch) --------------------------------------

@pytest.mark.asyncio
class TestBindings:

    async def test_binding_is_callable_from_softcode(self):
        @softcode_function
        def cinematic(pool):
            return pool * 100

        sim = Simulator()
        try:
            room = sim.room("Range")
            npc = sim.obj("NPC", location=room)
            p = sim.player("P", location=room)
            res, err = await sim.eval(
                npc, "result = cinematic(3) + net_successes(0, 5).margin",
                enactor=p)
            assert err is None
            assert res == 300                            # 3*100 + 0 hits
        finally:
            sim.close()
            clear_bindings()

    async def test_softcode_cannot_register_bindings(self):
        # Registration is a deploy-time native act; the register function is
        # NOT in the sandbox namespace (composition, not registration).
        sim = Simulator()
        try:
            npc = sim.obj("NPC", location=sim.room("R"))
            _res, err = await sim.eval(npc, "softcode_function")
            assert err is not None                       # NameError in sandbox
        finally:
            sim.close()


# --- Live through check() via a system installed in the Simulator ------------

@pytest.mark.asyncio
async def test_pool_system_live_through_check():
    """A data-defined system installed as the Simulator's game system
    resolves real in-game checks through its softcode rule."""
    from realm.core.checks import check
    sim = Simulator(game_system=PoolSystem)
    try:
        hacker = sim.obj("Hacker", pool=10)
        result = check(hacker, "intrusion")
        assert isinstance(result, dice.CheckResult)
        assert result.margin == result.roll             # net_successes: margin==count
    finally:
        sim.close()
