"""
`combat:on_death` fires from every death, not just from swings.

`handle_death` calls itself "the one death path, whatever the cause (a
swing, poison, a trap)" — but the event was announced somewhere else
entirely: inside `CombatSystem.attack`. So only the swing path told the
world. An NPC killed by softcode `damage()`, a poison tick or a trap died
in silence, and a player going down emitted nothing at all — which is why
the bounty board (114), arena recorder (115), replay log (120) and clone
bay (140) all had to poll.

The announcement now lives in `handle_death`, which every route reaches.
It fires *before* the body is transformed, because witnesses inspect the
fallen (`_npc_death` replaces the NPC with a corpse).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.combat.manager import CombatManager, set_combat_manager
from realm.combat.rulesets.d20 import D20Ruleset
from realm.combat.system import CombatSystem
from realm.testing import Simulator

WITNESS = (
    "set_attr(me, 'saw', name(target)); "
    "set_attr(me, 'killer', adata('killer')); "
    "set_attr(me, 'fatal', adata('fatal'))"
)


@pytest.fixture
def world():
    sim = Simulator()
    mgr = CombatManager(CombatSystem(ruleset=D20Ruleset()),
                        beat_min=4.0, beat_max=120.0, beat_default=15.0)
    set_combat_manager(mgr)
    room = sim.room("Pit")
    alice = sim.player("Alice", location=room)
    alice.db.set('hp', 10)
    mark = sim.obj("mark", location=room)
    mark.db.set('hp', 5)
    witness = sim.obj("witness", location=room)
    witness.db.set('ON_DEATH', WITNESS)
    try:
        yield SimpleNamespace(sim=sim, mgr=mgr, room=room, alice=alice,
                              mark=mark, witness=witness)
    finally:
        mgr.stop_all()
        set_combat_manager(None)
        sim.close()


@pytest.mark.asyncio
class TestEveryRouteAnnounces:

    async def test_softcode_damage_kill_is_heard(self, world):
        """The headline gap: an NPC killed by softcode died silently."""
        gun = world.sim.obj("gun", location=world.room)
        await world.sim.eval(gun, "damage(get('mark'), 99)")
        assert world.witness.db.get('saw') == "mark"
        assert world.witness.db.get('fatal') is True

    async def test_player_going_down_is_heard(self, world):
        """There was no player death event at all — the clone bay polled."""
        gun = world.sim.obj("gun", location=world.room)
        await world.sim.eval(gun, "damage(get('Alice'), 999)")
        assert world.witness.db.get('saw') == "Alice"

    async def test_direct_handle_death_is_heard(self, world):
        await world.mgr.handle_death(world.mark, killer=world.alice)
        assert world.witness.db.get('saw') == "mark"


@pytest.mark.asyncio
class TestPayload:

    async def test_killer_name_is_bound(self, world):
        """`extra['killer']` stays a NAME for compatibility with scripts
        written against the old swing-path event."""
        await world.mgr.handle_death(world.mark, killer=world.alice)
        assert world.witness.db.get('killer') == "Alice"

    async def test_killer_is_none_for_an_unattributed_death(self, world):
        await world.mgr.handle_death(world.mark, killer=None)
        assert world.witness.db.get('killer') is None
        assert world.witness.db.get('saw') == "mark"

    async def test_fatal_distinguishes_death_from_unconsciousness(self, world):
        """An NPC dies (corpse); a player drops unconscious, revivable.
        Both announce; `fatal` tells them apart."""
        await world.mgr.handle_death(world.mark, killer=None)
        assert world.witness.db.get('fatal') is True

        world.witness.db.set('fatal', None)
        await world.mgr.handle_death(world.alice, killer=None)
        assert world.witness.db.get('fatal') is False

    async def test_actor_is_the_killer_object(self, world):
        """`actor` binds the killer itself — `adata('killer')` is only its
        name, kept for backward compatibility."""
        world.witness.db.set(
            'ON_DEATH', "set_attr(me, 'aid', actor.id if actor else 'none')")
        await world.mgr.handle_death(world.mark, killer=world.alice)
        assert world.witness.db.get('aid') == world.alice.id


@pytest.mark.asyncio
class TestOrderingAndArity:

    async def test_announced_before_the_body_is_transformed(self, world):
        """Witnesses inspect the fallen — the bounty board reads the mark's
        name off the body — and `_npc_death` replaces it with a corpse. So
        the victim must still be findable when the event runs."""
        world.witness.db.set(
            'ON_DEATH',
            "set_attr(me, 'present', len([o for o in contents(here) "
            "if name(o) == 'mark']))")
        await world.mgr.handle_death(world.mark, killer=None)
        assert world.witness.db.get('present') == 1

    async def test_handle_death_announces_exactly_once(self, world):
        world.witness.db.set('ON_DEATH', "incr('count')")
        await world.mgr.handle_death(world.mark, killer=world.alice)
        assert world.witness.db.get('count') == 1


@pytest.mark.asyncio
class TestRealSwingStillFires:
    """The regression that matters most: the announcement was REMOVED from
    CombatSystem.attack. A swing must still fire it — via handle_defeat ->
    handle_death — exactly once, not zero times and not twice.
    """

    async def test_a_real_swing_kill_announces_once(self):
        from realm.combat.rulesets.gurps import GURPSRuleset
        from realm.core.checks import set_check_resolver

        sim = Simulator()
        # Diceless: every 3d6 is a 10, so swings land deterministically.
        set_check_resolver(lambda actor, skill, mod=0, **kw: SimpleNamespace(
            success=True, margin=6, critical=False, roll=10))
        mgr = CombatManager(CombatSystem(ruleset=GURPSRuleset()),
                            beat_min=4.0, beat_max=120.0, beat_default=15.0)
        set_combat_manager(mgr)
        try:
            room = sim.room("Pit")
            hero = sim.player("Hero", location=room, hp=30, max_hp=30,
                              skill_melee=16, dodge=0, strength=10,
                              dexterity=10)
            # 1 hp: the first landed blow finishes it.
            mook = sim.player("Mook", location=room, hp=1, max_hp=1,
                              skill_melee=1, dodge=0, strength=10,
                              dexterity=10)
            witness = sim.obj("witness", location=room)
            witness.db.set('ON_DEATH', "incr('count'); set_attr(me, 'who', name(target))")

            await mgr.initiate(hero, mook)
            encounter = mgr.encounter_of(hero)
            for _ in range(6):
                if witness.db.get('count'):
                    break
                await encounter.resolve_round()

            assert witness.db.get('who') == "Mook", "a swing kill went unheard"
            assert witness.db.get('count') == 1, "the swing double-announced"
        finally:
            mgr.stop_all()
            set_combat_manager(None)
            set_check_resolver(None)
            sim.close()
