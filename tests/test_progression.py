"""
MUD_PLAN step 5.1 to 5.4: progression.

A skill improves by one of four models, named by its skill definition's
``progression`` (else the game system's ``default_progression``): points
(``improve``), practice (at a trainer), use (every check and every swing
reports to ``GameSystem.on_skill_used``) and idle (``study``, accrued from
the wall clock). Whatever the model, it writes the plain ``skill_<name>``.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.config.loader import Settings
from realm.std.rules.definitions import define_skill
from realm.testing import Simulator

MERC = "realm.games.merc.system.MercSystem"


def _resolver(success=True, effective=50):
    from realm.std.rules.checks import checks
    checks().resolver = lambda actor, skill, mod=0, **kw: SimpleNamespace(
        success=success, margin=1 if success else -1, roll=10,
        effective=effective, skill=skill)


@pytest.fixture
def merc():
    s = Simulator(game_system=MERC)
    try:
        yield s
    finally:
        s.world.services["combat"].stop_all()
        s.close()


@pytest.fixture
def gurps():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


async def _made(sim, name, cls, **attrs):
    rules = sim.game_system
    room = sim.startup_room or sim.room("Hall")
    sim.startup_room = room
    player = sim.player(name, location=room)
    rules.apply_baseline(player)
    rules.chargen_steps()[0].handle(player, cls)
    rules.finish_chargen(player)
    for key, value in attrs.items():
        player.db.set(key, value)
    return player


def _text(sim, player):
    return "\n".join(sim.seen(player))


# --- 5.1 the seam --------------------------------------------------------------------


class TestTheSeam:

    def test_progression_comes_from_the_definition_else_the_system(self, merc):
        from realm.std.rules.progression import progression_of
        pat = merc.player("Pat", location=merc.room("Hall"))
        assert progression_of(pat, "melee") == "use"                  # Decision D5
        merc.add(define_skill("herbalism", "intelligence", -5))
        merc.store.find_cached(name="herbalism")[0].db.progression = "idle"
        assert progression_of(pat, "herbalism") == "idle"

    def test_point_buy_systems_default_to_points(self, gurps):
        from realm.std.rules.progression import progression_of
        gus = gurps.player("Gus", location=gurps.room("Lab"))
        assert progression_of(gus, "stealth") == "points"

    def test_the_neutral_system_does_not_improve_skills(self):
        from realm.std.rules.progression import progression_of
        from realm.std.rules.system import GameSystem

        class Plain(GameSystem):
            pass

        assert Plain.default_progression is None
        sim = Simulator(game_system=Plain)
        try:
            pat = sim.player("Pat", location=sim.room("Hall"))
            assert progression_of(pat, "stealth") is None
        finally:
            sim.close()

    def test_the_hook_runs_once_per_check(self, gurps, monkeypatch):
        from realm.std.rules.checks import check
        seen = []
        monkeypatch.setattr(gurps.game_system, "on_skill_used",
                            lambda obj, result: seen.append((obj.name, result.skill)))
        pat = gurps.player("Pat", location=gurps.room("Hall"))
        check(pat, "stealth")
        assert seen == [("Pat", "stealth")]

    async def test_the_hook_runs_once_per_swing_with_the_weapons_skill(self, merc, monkeypatch):
        seen = []
        monkeypatch.setattr(merc.game_system, "on_skill_used",
                            lambda obj, result: seen.append((obj.name, result.skill)))
        room = merc.room("Pit")
        pat = merc.player("Pat", location=room, hp=20, max_hp=20, thac0=20, armor_class=10)
        rat = merc.obj("rat", location=room, tags=["npc"], hp=20, max_hp=20,
                       thac0=20, armor_class=10)
        system = merc.world.services["combat"].combat_system
        await system.attack(pat, rat)
        assert seen == [("Pat", "melee")]
        sword = merc.obj("a sword", location=pat, tags=["thing", "weapon", "wielded"],
                         skill="swords")
        await system.attack(pat, rat, weapon=sword)
        assert seen[-1] == ("Pat", "swords")
        assert len(seen) == 2

    def test_a_world_without_rules_is_unaffected(self):
        from realm.std.rules.checks import check
        sim = Simulator(features=["basics", "look"])
        try:
            pat = sim.player("Pat", location=sim.room("Hall"), skill_stealth=12)
            check(pat, "stealth")
            assert pat.db.skill_stealth == 12
        finally:
            sim.close()

    async def test_merc_caps_follow_class_and_level(self, merc):
        from realm.packs import import_pack
        await import_pack("merc-classic", merc.store)
        rules = merc.game_system
        pat = await _made(merc, "Pat", "warrior")
        assert rules.skill_cap(pat, "kick") == 95             # a warrior skill, gate 1
        assert rules.skill_cap(pat, "lockpicking") == 75       # not a warrior skill
        assert rules.skill_cap(pat, "disarm") == 75            # gate 10, at level 1
        pat.db.level = 10
        assert rules.skill_cap(pat, "disarm") == 95
        merc.add(define_skill("lockpicking", "dexterity", -80))
        merc.store.find_cached(name="lockpicking")[0].db.class_caps = {"warrior": 40}
        assert rules.skill_cap(pat, "lockpicking") == 40
        from realm.std.rules.system import GameSystem
        assert GameSystem.skill_cap(rules, pat, "x") is None    # neutral: no cap


# --- 5.2 learn by use -------------------------------------------------------------------


class TestLearnByUse:

    def _uses_to_level(self, sim, player, skill, *, success, limit=200):
        from realm.std.rules.checks import check
        _resolver(success=success)
        start = int(player.db.get(f"skill_{skill}") or 0)
        for n in range(1, limit + 1):
            check(player, skill)
            if int(player.db.get(f"skill_{skill}") or 0) > start:
                return n
        return None

    async def test_successes_raise_a_skill_and_failures_more_slowly(self, merc):
        pat = await _made(merc, "Pat", "thief", skill_stealth=40)
        wins = self._uses_to_level(merc, pat, "stealth", success=True)
        assert wins is not None and pat.db.skill_stealth == 41
        assert "You have become better at stealth!" in _text(merc, pat)
        sam = await _made(merc, "Sam", "thief", skill_stealth=40)
        losses = self._uses_to_level(merc, sam, "stealth", success=False)
        assert losses is not None and losses > wins

    async def test_the_cap_holds(self, merc):
        from realm.std.rules.checks import check
        pat = await _made(merc, "Pat", "thief", skill_stealth=95)
        _resolver(success=True)
        for _ in range(100):
            check(pat, "stealth")
        assert pat.db.skill_stealth == 95 == merc.game_system.skill_cap(pat, "stealth")
        assert not pat.db.get("skill_xp_stealth")

    async def test_a_certain_roll_teaches_nothing(self, merc):
        from realm.std.rules.checks import check
        pat = await _made(merc, "Pat", "thief", skill_stealth=40)
        _resolver(success=False, effective=0)               # could not succeed
        for _ in range(50):
            check(pat, "stealth")
        assert pat.db.skill_stealth == 40 and not pat.db.get("skill_xp_stealth")

    async def test_an_untaught_skill_does_not_improve_unless_it_says_so(self, merc):
        from realm.std.rules.checks import check
        pat = await _made(merc, "Pat", "warrior")
        _resolver(success=True)
        for _ in range(50):
            check(pat, "juggling")
        assert pat.db.get("skill_juggling") is None
        merc.add(define_skill("juggling", "dexterity", -20))
        merc.store.find_cached(name="juggling")[0].db.untrained_use = True
        for _ in range(50):
            check(pat, "juggling")
        assert int(pat.db.get("skill_juggling") or 0) >= 1

    async def test_a_combat_skill_rises_from_swings(self, merc, monkeypatch):
        monkeypatch.setattr("realm.games.merc.ruleset.random.randint", lambda a, b: 15)
        room = merc.room("Pit")
        pat = await _made(merc, "Pat", "warrior")
        pat.location = room
        start = pat.db.skill_melee
        rat = merc.obj("rat", location=room, tags=["npc"], hp=100000, max_hp=100000,
                       thac0=20, armor_class=10)
        system = merc.world.services["combat"].combat_system
        for _ in range(60):
            await system.attack(pat, rat)
        assert pat.db.skill_melee > start

    async def test_a_progress_rule_replaces_the_curve(self, merc):
        from realm.std.rules.checks import check
        pat = await _made(merc, "Pat", "thief", skill_stealth=40)
        merc.add(define_skill("stealth", "dexterity", -40))
        sdef = merc.store.find_cached(name="stealth")[0]
        sdef.db.progress_rule = "1000 if success else 0"
        _resolver(success=True)
        check(pat, "stealth")
        assert pat.db.skill_stealth == 41
        sdef.db.progress_rule = "0"
        for _ in range(50):
            check(pat, "stealth")
        assert pat.db.skill_stealth == 41

    async def test_a_points_skill_is_untouched(self, gurps):
        from realm.std.rules.checks import check
        pat = gurps.player("Pat", location=gurps.room("Lab"), skill_stealth=12)
        _resolver(success=True)
        for _ in range(100):
            check(pat, "stealth")
        assert pat.db.skill_stealth == 12 and pat.db.get("skill_xp_stealth") is None

    async def test_an_untrained_use_skill_starts_from_its_default(self, gurps):
        """Under GURPS an untrained skill already has an attribute default
        (dexterity 10 - 5 = 5); learning by use must raise it to 6, not
        write 1 over it."""
        from realm.std.rules.checks import check, skill_level
        sdef = define_skill("smithing", "dexterity", -5)
        sdef.db.progression = "use"
        sdef.db.untrained_use = True
        gurps.add(sdef)
        pat = gurps.player("Pat", location=gurps.room("Forge"), dexterity=10)
        assert skill_level(pat, "smithing") == 5
        _resolver(success=True)
        for _ in range(10):
            check(pat, "smithing")
            if pat.db.get("skill_smithing") is not None:
                break
        assert pat.db.skill_smithing == 6

    async def test_npcs_do_not_learn(self, merc):
        from realm.std.rules.checks import check
        rat = merc.obj("rat", location=merc.room("Pit"), tags=["npc"], skill_stealth=40)
        _resolver(success=True)
        for _ in range(100):
            check(rat, "stealth")
        assert rat.db.skill_stealth == 40

    async def test_skills_shows_progress_for_use_skills(self, merc):
        from realm.std.rules.checks import check
        pat = await _made(merc, "Pat", "thief", skill_stealth=40)
        _resolver(success=True)
        check(pat, "stealth")
        merc.seen(pat)
        await merc.do(pat, "skills")
        stealth = next(line for line in _text(merc, pat).splitlines() if "stealth" in line)
        need = merc.game_system.use_xp_needed(40)
        assert f"2/{need}" in stealth


# --- 5.3 practice -----------------------------------------------------------------------


def _trainer(sim, room, **params):
    from realm.core.behaviors import BehaviorRegistry
    master = sim.obj("the guildmaster", location=room, tags=["npc"])
    master.add_behavior(BehaviorRegistry.create("trainer", **params))
    return master


class TestPractice:

    async def test_practice_lists_then_raises_by_intelligence(self, merc):
        pat = await _made(merc, "Pat", "thief", practices=3, intelligence=13)
        _trainer(merc, pat.location, teaches="class")
        await merc.do(pat, "practice")
        out = _text(merc, pat)
        assert "disarm" in out and "backstab" in out
        before = pat.db.skill_disarm
        await merc.do(pat, "practice disarm")
        assert pat.db.skill_disarm == before + 13 // 3
        assert pat.db.practices == 2

    async def test_without_a_trainer(self, merc):
        pat = await _made(merc, "Pat", "thief", practices=3)
        await merc.do(pat, "practice disarm")
        assert "There is no one here to teach you." in _text(merc, pat)
        assert pat.db.practices == 3

    async def test_practice_stops_at_the_trainers_floor(self, merc):
        pat = await _made(merc, "Pat", "thief", practices=50, intelligence=13)
        _trainer(merc, pat.location, teaches="class")
        floor = merc.game_system.skill_cap(pat, "disarm") // 3
        for _ in range(20):
            await merc.do(pat, "practice disarm")
        assert pat.db.skill_disarm == floor
        assert "use it to improve further" in _text(merc, pat)

    async def test_running_out_of_practices(self, merc):
        pat = await _made(merc, "Pat", "thief", practices=0)
        _trainer(merc, pat.location, teaches="class")
        await merc.do(pat, "practice disarm")
        assert "You have no practice sessions left." in _text(merc, pat)

    async def test_only_what_the_trainer_teaches(self, merc):
        pat = await _made(merc, "Pat", "warrior", practices=3, skill_kick=10)
        _trainer(merc, pat.location, teaches=["kick"])
        await merc.do(pat, "practice bash")
        assert "does not teach bash" in _text(merc, pat)
        before = pat.db.skill_kick
        await merc.do(pat, "practice kick")
        assert pat.db.skill_kick > before

    async def test_a_points_skill_is_not_practiced(self, gurps):
        from realm.core.behaviors import BehaviorRegistry
        room = gurps.room("Dojo")
        pat = gurps.player("Pat", location=room, practices=3, skill_stealth=10)
        master = gurps.obj("sensei", location=room, tags=["npc"])
        master.add_behavior(BehaviorRegistry.create("trainer", teaches=["stealth"]))
        await gurps.do(pat, "practice stealth")
        assert pat.db.skill_stealth == 10
        assert "does not improve by practice" in _text(gurps, pat)

    async def test_train_strength(self, merc):
        pat = await _made(merc, "Pat", "thief", trains=1)
        _trainer(merc, pat.location, teaches="class", trains_stats=True)
        before = pat.db.strength
        await merc.do(pat, "train strength")
        assert pat.db.strength == before + 1 and pat.db.trains == 0
        await merc.do(pat, "train strength")
        assert "You have no training sessions left." in _text(merc, pat)
        pat.db.trains, pat.db.strength = 1, merc.game_system.stat_max(pat, "strength")
        await merc.do(pat, "train strength")
        assert pat.db.trains == 1
        assert "as strong as you can be" in _text(merc, pat)

    async def test_a_trainer_that_only_teaches_skills_does_not_train(self, merc):
        pat = await _made(merc, "Pat", "thief", trains=1)
        _trainer(merc, pat.location, teaches="class")
        await merc.do(pat, "train strength")
        assert pat.db.trains == 1
        assert "can't train your" in _text(merc, pat)

    async def test_a_level_grants_trains(self, merc):
        pat = await _made(merc, "Pat", "warrior", xp=1000)
        assert pat.db.trains == 3                           # ROM's nanny: 3 to start
        merc.game_system.advance_level(pat)
        assert pat.db.level == 2 and pat.db.trains == 3 + 1


# --- 5.4 idle training ------------------------------------------------------------------


@pytest.fixture
def clock(monkeypatch):
    now = [1_000_000.0]
    monkeypatch.setattr("realm.std.rules.progression.now", lambda: now[0])
    return now


def _idle_skill(sim, name, **attrs):
    sdef = define_skill(name, "intelligence", -5)
    sdef.db.progression = "idle"
    sdef.db.attributes = ["intelligence", "wisdom"]
    for key, value in attrs.items():
        sdef.db.set(key, value)
    sim.add(sdef)
    return sdef


def _expected_levels(rules, sp, rank=1, start=0):
    level = start
    while sp >= rules.idle_cost(level) * rank:
        sp -= rules.idle_cost(level) * rank
        level += 1
    return level


class TestIdleTraining:

    async def test_eight_hours_offline_raise_a_skill(self, merc, clock):
        from realm.std.rules.checks import skill_level
        _idle_skill(merc, "herbalism")
        pat = await _made(merc, "Pat", "cleric", intelligence=13, wisdom=14)
        base = skill_level(pat, "herbalism")         # the untrained default counts
        await merc.do(pat, "study herbalism")
        assert pat.db.training == "herbalism"
        clock[0] += 8 * 3600
        merc.seen(pat)
        await merc.do(pat, "skills")
        rate = 13 + 14 / 2
        assert pat.db.skill_herbalism == _expected_levels(merc.game_system, rate * 480,
                                                          start=base)
        assert pat.db.skill_herbalism > base + 5
        out = _text(merc, pat)
        assert "herbalism" in out and "(training)" in out and "next level in" in out

    async def test_the_offline_cap_limits_it(self, clock):
        sim = Simulator(game_system=MERC,
                        settings=Settings(raw={"IDLE_TRAINING_MAX_HOURS": 2}))
        try:
            from realm.std.rules.checks import skill_level
            from realm.std.rules.progression import accrue_training
            _idle_skill(sim, "herbalism")
            pat = await _made(sim, "Pat", "cleric", intelligence=13, wisdom=14)
            base = skill_level(pat, "herbalism")
            await sim.do(pat, "study herbalism")
            clock[0] += 8 * 3600
            accrue_training(pat)
            assert pat.db.skill_herbalism == _expected_levels(sim.game_system,
                                                              (13 + 7) * 120, start=base)
        finally:
            sim.close()

    async def test_switching_skills_banks_the_first(self, merc, clock):
        from realm.std.rules.checks import skill_level
        _idle_skill(merc, "herbalism")
        _idle_skill(merc, "astronomy")
        pat = await _made(merc, "Pat", "cleric", intelligence=13, wisdom=14)
        herb, astro = skill_level(pat, "herbalism"), skill_level(pat, "astronomy")
        await merc.do(pat, "study herbalism")
        clock[0] += 3600
        await merc.do(pat, "study astronomy")
        banked = pat.db.skill_herbalism
        assert banked == _expected_levels(merc.game_system, 20 * 60, start=herb)
        assert pat.db.training == "astronomy"
        clock[0] += 3600
        await merc.do(pat, "skills")
        assert pat.db.skill_herbalism == banked
        assert pat.db.skill_astronomy == _expected_levels(merc.game_system, 20 * 60,
                                                          start=astro)

    async def test_a_use_skill_refuses_study(self, merc):
        pat = await _made(merc, "Pat", "thief")
        await merc.do(pat, "study stealth")
        assert pat.db.training is None
        assert "improves by use" in _text(merc, pat)

    async def test_prerequisites_are_required(self, merc, clock):
        _idle_skill(merc, "herbalism")
        _idle_skill(merc, "alchemy", requires={"herbalism": 5})
        pat = await _made(merc, "Pat", "cleric")
        await merc.do(pat, "study alchemy")
        assert pat.db.training is None and "herbalism 5" in _text(merc, pat)
        pat.db.skill_herbalism = 5
        await merc.do(pat, "study alchemy")
        assert pat.db.training == "alchemy"

    async def test_study_stop_banks_and_ends(self, merc, clock):
        _idle_skill(merc, "herbalism")
        pat = await _made(merc, "Pat", "cleric", intelligence=13, wisdom=14)
        await merc.do(pat, "study herbalism")
        clock[0] += 3600
        await merc.do(pat, "study stop")
        assert pat.db.training is None and pat.db.skill_herbalism is not None
        level = pat.db.skill_herbalism
        clock[0] += 3600
        await merc.do(pat, "skills")
        assert pat.db.skill_herbalism == level

    async def test_the_sweep_announces_a_finished_level(self, merc, clock):
        from realm.std.rules.progression import training_sweep
        _idle_skill(merc, "herbalism")
        pat = await _made(merc, "Pat", "cleric", intelligence=13, wisdom=14)
        await merc.do(pat, "study herbalism")
        merc.seen(pat)
        clock[0] += 3600
        await training_sweep(merc.store)
        assert "You have finished training herbalism to level" in _text(merc, pat)

    async def test_a_check_of_the_skill_accrues_first(self, merc, clock):
        from realm.std.rules.checks import check
        _idle_skill(merc, "herbalism")
        pat = await _made(merc, "Pat", "cleric", intelligence=13, wisdom=14)
        await merc.do(pat, "study herbalism")
        clock[0] += 3600
        seen = []
        from realm.std.rules.checks import checks
        checks().resolver = lambda actor, skill, mod=0, **kw: (
            seen.append(actor.db.get("skill_herbalism"))
            or SimpleNamespace(success=True, margin=1, roll=1, effective=50, skill=skill))
        check(pat, "herbalism")
        assert seen and seen[0] > 0
