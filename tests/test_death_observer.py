"""
KERNEL_PLAN 8.3: death and the HP threshold are observers on pools.

Combat registers one observer on ``pool:on_spent`` (the vital pool spent
runs ``CombatManager.handle_death``) and one on ``pool:on_change`` (the
vital pool falling through ``db.hitprcnt`` fires ``ON_HITPRCNT``). Every
source of harm that settles its change reaches both: a swing, softcode,
a poison tick, a pool function. ``db.when_spent`` says what death does to
the body.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core.pools import harm, settle
from realm.testing import Simulator

COUNT_DEATHS = "incr('deaths'); set_attr(me, 'fatal', adata('fatal'))"


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


def _arena(sim):
    room = sim.room("Pit")
    witness = sim.obj("witness", location=room)
    witness.db.on_death = COUNT_DEATHS
    return room, witness


@pytest.mark.asyncio
class TestDeathIsAnObserver:

    async def test_a_python_harm_that_spends_the_vital_pool_kills(self, sim):
        room, witness = _arena(sim)
        rat = sim.obj("rat", location=room, hp=3, max_hp=3)
        await settle(harm(rat, "hp", 5))
        assert witness.db.deaths == 1
        assert rat.location is None
        assert any(o.name == "corpse of rat" for o in room.contents)

    async def test_softcode_harm_pool_kills(self, sim):
        room, witness = _arena(sim)
        trap = sim.obj("trap", location=room)
        rat = sim.obj("rat", location=room, hp=3, max_hp=3)
        await sim.eval(trap, "harm_pool(get('rat'), 'hp', 9)")
        assert witness.db.deaths == 1
        assert rat.location is None

    async def test_a_spent_pool_that_is_not_vital_does_not_kill(self, sim):
        room, witness = _arena(sim)
        ship = sim.obj("ship", location=room, shields=4, max_shields=20,
                       hull=30, max_hull=30, damage_pool="shields",
                       pools={"shields": {"overflow": "hull"}})
        await settle(harm(ship, "shields", 4))
        assert ship.db.shields == 0
        assert witness.db.deaths is None
        assert ship.location is room

    async def test_harming_the_already_fallen_does_not_kill_again(self, sim):
        room, witness = _arena(sim)
        gun = sim.obj("gun", location=room)
        pat = sim.player("Pat", location=room, hp=4, max_hp=10)
        await sim.eval(gun, "damage(get('Pat'), 9)")
        await sim.eval(gun, "damage(get('Pat'), 9)")
        assert pat.has_tag("unconscious")
        assert witness.db.deaths == 1

    async def test_the_killer_is_the_source(self, sim):
        room, witness = _arena(sim)
        witness.db.on_death = "set_attr(me, 'killer', adata('killer'))"
        ann = sim.player("Ann", location=room)
        rat = sim.obj("rat", location=room, hp=1, max_hp=1)
        await settle(harm(rat, "hp", 1), source=ann)
        assert witness.db.killer == "Ann"

    async def test_the_death_check_queue_kind_is_gone(self, sim):
        assert "death_check" not in sim.world.scripts.queue_kinds


@pytest.mark.asyncio
class TestASwingKill:

    async def test_the_hit_is_told_before_the_fall(self, sim):
        from realm.std.rules.checks import checks
        checks().resolver = lambda actor, skill, mod=0, **kw: SimpleNamespace(
            success=True, margin=6, critical=False, roll=10)
        room, witness = _arena(sim)
        hero = sim.player("Hero", location=room, hp=30, max_hp=30,
                          skill_melee=16, dodge=0, strength=10, dexterity=10)
        mook = sim.player("Mook", location=room, hp=1, max_hp=1,
                          skill_melee=1, dodge=0, strength=10, dexterity=10)
        mgr = sim.world.services["combat"]
        await mgr.initiate(hero, mook)
        encounter = mgr.encounter_of(hero)
        for _ in range(6):
            if witness.db.deaths:
                break
            await encounter.resolve_round()

        assert witness.db.deaths == 1
        lines = sim.seen(hero)
        hit = next(i for i, line in enumerate(lines) if "is defeated!" in line)
        fall = next(i for i, line in enumerate(lines) if "collapses, unconscious" in line)
        assert hit < fall
        assert encounter.get(mook.id) is None
        mgr.stop_all()


@pytest.mark.asyncio
class TestHitPercentIsAnObserver:

    async def test_a_poison_tick_crosses_the_threshold(self, sim):
        from realm.std.effects.behaviors import DamageOverTimeBehavior
        room = sim.room("Bog")
        mark = sim.obj("mark", location=room, hp=10, max_hp=10, hitprcnt=50)
        mark.db.on_hitprcnt = (
            "if target is me: incr('crossed'); set_attr(me, 'pct', adata('percent'))")
        dot = DamageOverTimeBehavior(kind="poisoned", damage=3)
        mark.add_behavior(dot)

        await dot.pulse(mark)                     # 10 -> 7: 70%
        assert mark.db.crossed is None
        await dot.pulse(mark)                     # 7 -> 4: 40%, crosses 50
        assert mark.db.crossed == 1
        assert mark.db.pct == 40
        await dot.pulse(mark)                     # 4 -> 1: already below
        assert mark.db.crossed == 1

    async def test_not_on_the_killing_blow(self, sim):
        room, witness = _arena(sim)
        mark = sim.obj("mark", location=room, hp=10, max_hp=10, hitprcnt=50)
        mark.db.on_hitprcnt = "incr('crossed')"
        await settle(harm(mark, "hp", 10))
        assert witness.db.deaths == 1
        assert witness.db.crossed is None

    async def test_an_up_pool_counts_what_is_left(self, sim):
        room = sim.room("Street")
        runner = sim.obj("runner", location=room, harm=0, max_harm=6,
                         damage_pool="harm", hitprcnt=50,
                         pools={"harm": {"direction": "up"}})
        runner.db.on_hitprcnt = "incr('crossed'); set_attr(me, 'pct', adata('percent'))"
        await settle(harm(runner, "harm", 2))     # 4 of 6 left: 67%
        assert runner.db.crossed is None
        await settle(harm(runner, "harm", 2))     # 2 of 6 left: 33%
        assert runner.db.crossed == 1
        assert runner.db.pct == 33

    async def test_only_the_vital_pool(self, sim):
        room = sim.room("Dock")
        ship = sim.obj("ship", location=room, shields=20, max_shields=20,
                       hull=30, max_hull=30, damage_pool="shields", hitprcnt=50,
                       pools={"shields": {"overflow": "hull"}})
        ship.db.on_hitprcnt = "incr('crossed')"
        await settle(harm(ship, "shields", 15))   # shields 25%, hull untouched
        assert ship.db.crossed is None
        await settle(harm(ship, "shields", 25))   # hull 30 -> 10: 33%
        assert ship.db.crossed == 1


@pytest.mark.asyncio
class TestWhenSpent:

    async def test_none_leaves_the_body_alone(self, sim):
        room, witness = _arena(sim)
        hulk = sim.obj("hulk", location=room, hp=5, max_hp=5, when_spent="none")
        await settle(harm(hulk, "hp", 5))
        assert witness.db.deaths == 1             # the fall is still announced
        assert witness.db.fatal is False
        assert hulk.location is room
        assert not hulk.has_tag("unconscious")
        assert not any(o.name.startswith("corpse") for o in room.contents)

    async def test_destroy_leaves_no_corpse(self, sim):
        """The one destroy path (``ops.objects.destroy``): unowned contents
        go with it, and nothing is left inside a deleted object."""
        room, witness = _arena(sim)
        crate = sim.obj("crate", location=room, hp=5, max_hp=5, when_spent="destroy")
        coin = sim.obj("coin", location=crate)
        watcher = sim.player("Wat", location=room)
        await settle(harm(crate, "hp", 5))
        assert witness.db.deaths == 1
        assert witness.db.fatal is True
        assert crate.location is None
        assert coin.location is None
        assert not any(o.name.startswith("corpse") for o in room.contents)
        assert any("crate is destroyed" in line for line in sim.seen(watcher))

    async def test_unconscious_spares_an_npc(self, sim):
        room, witness = _arena(sim)
        guard = sim.obj("guard", location=room, hp=5, max_hp=5,
                        when_spent="unconscious")
        await settle(harm(guard, "hp", 5))
        assert guard.has_tag("unconscious")
        assert guard.location is room
        assert witness.db.fatal is False

    async def test_corpse_is_the_npc_default(self, sim):
        room, _witness = _arena(sim)
        rat = sim.obj("rat", location=room, hp=1, max_hp=1, when_spent="corpse")
        await settle(harm(rat, "hp", 1))
        assert any(o.name == "corpse of rat" for o in room.contents)

    async def test_an_unknown_rule_is_an_error(self, sim):
        room = sim.room("Pit")
        blob = sim.obj("blob", location=room, when_spent="explode")
        with pytest.raises(ValueError, match="blob.*when_spent.*explode"):
            await sim.world.services["combat"].handle_death(blob)

    async def test_a_player_is_never_destroyed(self, sim):
        room = sim.room("Pit")
        pat = sim.player("Pat", location=room, when_spent="destroy")
        with pytest.raises(ValueError, match="Pat.*player"):
            await sim.world.services["combat"].handle_death(pat)
        assert pat.location is room
