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


# --- MUD_PLAN 2.3: coming round ---------------------------------------------------


@pytest.mark.asyncio
class TestComingRound:

    async def test_a_lone_player_comes_round_by_regenerating(self, sim):
        room = sim.room("Pit")
        here = sim.room("Glade")
        door = sim.obj("north", location=room, tags=["exit"])
        door.db.set("destination", here.id)
        gun = sim.obj("gun", location=room)
        pat = sim.player("Pat", location=room, hp=4, max_hp=10)
        sam = sim.player("Sam", location=room)
        await sim.eval(gun, "damage(get('Pat'), 9)")
        assert pat.has_tag("unconscious")
        await sim.do(pat, "north")
        assert pat.location is room                # still down: the existing gate
        sim.seen(pat), sim.seen(sam)

        await sim.world.services["vitals"].tick()
        assert not pat.has_tag("unconscious")
        assert "You come to." in sim.seen(pat)
        assert "Pat stirs." in sim.seen(sam)
        await sim.do(pat, "north")
        assert pat.location is here

    async def test_softcode_heal_revives(self, sim):
        room = sim.room("Pit")
        gun = sim.obj("gun", location=room)
        pat = sim.player("Pat", location=room, hp=4, max_hp=10)
        await sim.eval(gun, "damage(get('Pat'), 9)")
        assert pat.has_tag("unconscious")
        await sim.eval(gun, "heal(get('Pat'), 3)")
        assert not pat.has_tag("unconscious")
        assert "You come to." in sim.seen(pat)

    async def test_firstaid_revives_through_the_observer(self, sim):
        from realm.std.rules.checks import checks
        checks().resolver = lambda actor, skill, mod=0, **kw: SimpleNamespace(
            success=True, margin=4, critical=False, roll=10)
        room = sim.room("Pit")
        medic = sim.player("Medic", location=room)
        pat = sim.player("Pat", location=room, hp=4, max_hp=10)
        await settle(harm(pat, "hp", 9))
        assert pat.has_tag("unconscious")
        await sim.do(medic, "firstaid Pat")
        assert not pat.has_tag("unconscious")
        assert sum(line == "You come to." for line in sim.seen(pat)) == 1

    async def test_a_still_spent_pool_does_not_revive(self, sim):
        room = sim.room("Pit")
        pat = sim.player("Pat", location=room, hp=0, max_hp=10,
                         pools={"hp": {"spent_at": 2}})
        pat.add_tag("unconscious")
        from realm.core.pools import mend
        await settle(mend(pat, "hp", 1))           # 1: still at or below spent_at
        assert pat.has_tag("unconscious")


# --- MUD_PLAN 2.4: death and respawn -----------------------------------------------


def _respawn_sim(**raw):
    from realm.config.loader import Settings
    return Simulator(settings=Settings(raw={"PLAYER_DEATH": "respawn", **raw}))


@pytest.fixture
def rsim():
    s = _respawn_sim()
    try:
        yield s
    finally:
        s.close()


def _corpse(room):
    return next(o for o in room.contents if o.name.startswith("corpse of"))


@pytest.mark.asyncio
class TestRespawn:

    async def _killed(self, rsim, **attrs):
        field = rsim.room("Field")
        home = rsim.room("Home")
        witness = rsim.obj("witness", location=field)
        witness.db.on_death = COUNT_DEATHS
        pat = rsim.player("Pat", location=field, hp=10, max_hp=10, home=home.id, **attrs)
        sword = rsim.obj("a sword", location=pat, tags=["thing", "weapon"])
        ring = rsim.obj("a bound ring", location=pat, tags=["thing", "soulbound"])
        wolf = rsim.obj("wolf", location=field, tags=["npc"], hp=10, max_hp=10)
        await settle(harm(pat, "hp", 30), source=wolf)
        return field, home, witness, pat, sword, ring, wolf

    async def test_the_player_wakes_at_home_at_one_hit_point(self, rsim):
        field, home, witness, pat, sword, ring, _wolf = await self._killed(rsim)
        assert pat.location is home
        assert pat.db.hp == 1
        assert not pat.has_tag("unconscious")
        assert witness.db.deaths == 1
        assert witness.db.fatal is True
        assert any("Home" in line for line in rsim.seen(pat))   # shown the room

    async def test_the_corpse_holds_what_they_carried_but_soulbound(self, rsim):
        field, home, _w, pat, sword, ring, _wolf = await self._killed(rsim)
        corpse = _corpse(field)
        assert corpse.name == "corpse of Pat"
        assert sword.location is corpse
        assert ring.location is pat
        assert corpse.owner is pat
        assert corpse.has_tag("player_corpse")

    async def test_only_the_owner_loots_until_the_lock_lapses(self, rsim, monkeypatch):
        field, home, _w, pat, sword, _ring, _wolf = await self._killed(rsim)
        thief = rsim.player("Thief", location=field)
        await rsim.do(thief, "get sword from corpse")
        assert sword.location is not thief
        assert any("belongs to Pat" in line for line in rsim.seen(thief))

        import time
        later = time.time() + 301                  # CORPSE_LOCK_SECONDS 300
        monkeypatch.setattr("realm.std.combat.corpses.time.time", lambda: later)
        await rsim.do(thief, "get sword from corpse")
        assert sword.location is thief

    async def test_the_owner_loots_their_own_corpse(self, rsim):
        field, home, _w, pat, sword, _ring, _wolf = await self._killed(rsim)
        pat.location = field                        # walks back from home
        await rsim.do(pat, "get sword from corpse")
        assert sword.location is pat

    async def test_a_zero_lock_leaves_it_open(self):
        sim = _respawn_sim(CORPSE_LOCK_SECONDS=0)
        try:
            field, home, _w, pat, sword, _ring, _wolf = await self._killed(sim)
            thief = sim.player("Thief", location=field)
            await sim.do(thief, "get sword from corpse")
            assert sword.location is thief
        finally:
            sim.close()

    async def test_no_home_means_the_start_room(self, rsim):
        start = rsim.room("Start")
        rsim.startup_room = start
        field = rsim.room("Field")
        pat = rsim.player("Pat", location=field, hp=10, max_hp=10)
        await settle(harm(pat, "hp", 30))
        assert pat.location is start

    async def test_positions_combat_and_effects_are_cleared(self, rsim):
        from realm.std.effects.behaviors import ModifierEffectBehavior
        field = rsim.room("Field")
        home = rsim.room("Home")
        pat = rsim.player("Pat", location=field, hp=10, max_hp=10, home=home.id)
        pat.add_tag("resting")
        pat.add_behavior(ModifierEffectBehavior(kind="cursed", duration=0))
        assert pat.has_tag("cursed")
        await settle(harm(pat, "hp", 30))
        for tag in ("resting", "sleeping", "in_combat", "unconscious", "cursed"):
            assert not pat.has_tag(tag), tag

    async def test_no_kill_award_for_a_player_death(self, rsim):
        field = rsim.room("Field")
        home = rsim.room("Home")
        killer = rsim.player("Killer", location=field)
        pat = rsim.player("Pat", location=field, hp=10, max_hp=10, home=home.id,
                          points=500)
        paid = []
        rsim.game_system.grant_award = lambda player, amount: paid.append(amount)
        await settle(harm(pat, "hp", 30), source=killer)
        assert paid == []

    async def test_a_scavenger_leaves_a_player_corpse_alone(self, rsim, monkeypatch):
        from realm.std.npc.behaviors import ScavengerBehavior
        field, home, _w, pat, sword, _ring, _wolf = await self._killed(rsim)
        fido = rsim.obj("fido", location=field, tags=["npc"])
        monkeypatch.setattr("realm.std.npc.behaviors.random.random", lambda: 0.0)
        await ScavengerBehavior().tick(fido, 4.0)
        assert _corpse(field) is not None and sword.location is _corpse(field)

    async def test_respawn_is_for_players(self, rsim):
        room = rsim.room("Pit")
        rat = rsim.obj("rat", location=room, when_spent="respawn")
        with pytest.raises(ValueError, match="rat.*respawn.*player"):
            await rsim.world.services["combat"].handle_death(rat)

    async def test_the_default_is_still_unconscious(self, sim):
        room = sim.room("Pit")
        pat = sim.player("Pat", location=room, hp=10, max_hp=10)
        await settle(harm(pat, "hp", 30))
        assert pat.has_tag("unconscious") and pat.location is room

    async def test_an_unknown_player_death_setting_is_an_error(self):
        sim = _respawn_sim(PLAYER_DEATH="explode")
        try:
            room = sim.room("Pit")
            pat = sim.player("Pat", location=room, hp=10, max_hp=10)
            with pytest.raises(ValueError, match="PLAYER_DEATH.*explode"):
                await sim.world.services["combat"].handle_death(pat)
        finally:
            sim.close()


@pytest.mark.asyncio
class TestMercDeathPenalty:

    async def test_merc_loses_a_quarter_level_of_experience_never_a_level(self):
        from realm.config.loader import Settings
        sim = Simulator(game_system="realm.games.merc.system.MercSystem",
                        settings=Settings(raw={"PLAYER_DEATH": "respawn"}))
        try:
            home = sim.room("Temple")
            field = sim.room("Field")
            pat = sim.player("Pat", location=field, hp=10, max_hp=10, home=home.id,
                             level=3, xp=1000)
            await settle(harm(pat, "hp", 30))
            assert pat.db.level == 3
            assert pat.db.xp == 250                # 1000 - (3000 // 4)
            pat.location = field
            pat.db.hp = 10
            await settle(harm(pat, "hp", 30))
            assert (pat.db.level, pat.db.xp) == (3, 0)
        finally:
            sim.close()
