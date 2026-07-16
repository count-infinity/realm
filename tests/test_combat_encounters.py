"""
Tests for beat-driven combat: encounters, queues, maneuvers, defaults,
strategies, defeat, and escalation.

Determinism: attack dice come from a FixedRuleset (3d6 always rolls 10,
damage is flat 3), and skill checks use the level resolver (success iff
effective >= 10). Rounds are fired by calling resolve_round() directly —
the async beat timer is exercised separately in the live e2e drive.
"""

from __future__ import annotations

import pytest

from realm.behaviors import WatchfulBehavior
from realm.combat.manager import CombatManager, set_combat_manager
from realm.combat.maneuver import QueuedAction
from realm.combat.rulesets.gurps import GURPSRuleset
from realm.combat.system import CombatSystem
from realm.core.checks import CheckResult, set_check_resolver, skill_level
from realm.core.movement import move_through_exit
from realm.core.objects import GameObject
from realm.core.propagation import ROOM_TARGET_CHAIN, Action, propagate, reset_engine
from realm.core.propagation import get_engine as get_propagation_engine
from realm.gateway.session import Session


class FixedRuleset(GURPSRuleset):
    """GURPS with the dice removed: 3d6 always 10, damage always 3."""

    def roll_3d6(self):
        return 10, [3, 3, 4]

    def roll_damage(self, attacker, defender, attack_result, weapon=None):
        from realm.combat.ruleset import DamageResult, DamageType
        return DamageResult(
            total=3,
            damage_by_type={DamageType.PHYSICAL: 3},
        )


def level_resolver(obj, skill, modifier):
    effective = skill_level(obj, skill) + modifier
    return CheckResult(success=effective >= 10, margin=effective - 10,
                       roll=10, effective=effective, skill=skill)


@pytest.fixture
def manager():
    from realm.core.checks import SKILL_DEFAULTS
    saved_defaults = dict(SKILL_DEFAULTS)
    reset_engine()
    set_check_resolver(level_resolver)
    mgr = CombatManager(
        CombatSystem(ruleset=FixedRuleset()),
        beat_min=4.0, beat_max=120.0, beat_default=15.0,
    )
    set_combat_manager(mgr)
    yield mgr
    mgr.stop_all()
    set_combat_manager(None)
    set_check_resolver(None)
    from realm.core.checks import set_skill_defaults
    set_skill_defaults(saved_defaults)
    reset_engine()


def make_fighter(name, location=None, *, hp=10, skill=12, dodge=6,
                 player=True, **extra):
    obj = GameObject(name, location=location)
    obj.add_tag('player' if player else 'npc')
    obj.db.hp = hp
    obj.db.max_hp = hp
    obj.db.skill_melee = skill
    obj.db.dodge = dodge
    obj.db.strength = 10
    obj.db.dexterity = 12
    for key, value in extra.items():
        obj.db.set(key, value)
    sess = None
    if player:
        sess = Session(protocol="test", address="127.0.0.1")
        sess.link_player(obj)
    return obj, sess


def drain(sess):
    out = []
    while not sess._output_queue.empty():
        out.append(sess._output_queue.get_nowait())
    return out


# --- Encounter lifecycle -------------------------------------------------------


@pytest.mark.asyncio
class TestEncounterLifecycle:

    async def test_initiate_enrolls_both_with_targets(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room)
        bruiser, _ = make_fighter("Bruiser", room, player=False)

        encounter = await manager.initiate(alice, bruiser)

        assert encounter.get(alice.id).target_id == bruiser.id
        assert encounter.get(bruiser.id).target_id == alice.id
        assert alice.has_tag('in_combat') and bruiser.has_tag('in_combat')

    async def test_one_encounter_per_room(self, manager):
        room = GameObject("Arena", tags=["room"])
        a, _ = make_fighter("A", room)
        b, _ = make_fighter("B", room, player=False)
        c, _ = make_fighter("C", room, player=False)

        first = await manager.initiate(a, b)
        second = await manager.initiate(a, c)

        assert first is second
        assert len(first.participants) == 3

    async def test_noncombatants_refused(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room)
        statue = GameObject("statue", location=room, tags=["thing"])

        assert await manager.initiate(alice, statue) is None

    async def test_movement_blocked_in_combat_flee_flag_passes(self, manager):
        room = GameObject("Arena", tags=["room"])
        outside = GameObject("Street", tags=["room"])
        door = GameObject("out", location=room, tags=["exit"])
        door.db.destination_obj = outside
        alice, sess = make_fighter("Alice", room)
        bruiser, _ = make_fighter("Bruiser", room, player=False)
        await manager.initiate(alice, bruiser)

        assert await move_through_exit(alice, outside, exit_obj=door) is False
        assert alice.location is room
        assert any("flee to escape" in line for line in drain(sess))

        assert await move_through_exit(alice, outside, exit_obj=door,
                                       fleeing=True) is True


# --- Rounds, queues, defaults ---------------------------------------------------


@pytest.mark.asyncio
class TestRounds:

    async def test_queued_attack_fires_and_hurts(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room, skill=16)
        bruiser, _ = make_fighter("Bruiser", room, player=False, dodge=0)
        encounter = await manager.initiate(alice, bruiser)
        encounter.queue(alice, QueuedAction("attack", target_id=bruiser.id))
        encounter.queue(bruiser, QueuedAction("wait"))

        await encounter.resolve_round()

        assert int(bruiser.db.get('hp')) < 10

    async def test_queue_replaceable_until_fire(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room, skill=16)
        bruiser, _ = make_fighter("Bruiser", room, player=False, dodge=0)
        encounter = await manager.initiate(alice, bruiser)

        encounter.queue(alice, QueuedAction("attack", target_id=bruiser.id))
        encounter.queue(alice, QueuedAction("wait"))  # changed their mind
        encounter.queue(bruiser, QueuedAction("wait"))

        await encounter.resolve_round()

        assert int(bruiser.db.get('hp')) == 10  # the wait won

    async def test_default_policy_repeat(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room, skill=16)
        bruiser, _ = make_fighter("Bruiser", room, player=False, dodge=0, hp=30)
        encounter = await manager.initiate(alice, bruiser)
        encounter.queue(alice, QueuedAction("attack", target_id=bruiser.id))
        encounter.queue(bruiser, QueuedAction("wait"))

        await encounter.resolve_round()
        hp_after_one = int(bruiser.db.get('hp'))
        encounter.queue(bruiser, QueuedAction("wait"))
        await encounter.resolve_round()  # nothing queued: repeats the attack

        assert int(bruiser.db.get('hp')) < hp_after_one

    async def test_default_policy_nothing(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room, skill=16,
                                combat_default="nothing")
        bruiser, _ = make_fighter("Bruiser", room, player=False, dodge=0)
        encounter = await manager.initiate(alice, bruiser)
        encounter.queue(bruiser, QueuedAction("wait"))

        await encounter.resolve_round()

        assert int(bruiser.db.get('hp')) == 10

    async def test_defend_modifier_applies_then_reverts(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room)
        bruiser, _ = make_fighter("Bruiser", room, player=False, dodge=6)
        encounter = await manager.initiate(alice, bruiser)
        participant = encounter.get(bruiser.id)

        encounter.queue(alice, QueuedAction("wait"))
        encounter.queue(bruiser, QueuedAction("defend"))
        await encounter.resolve_round()
        assert participant.combatant.get_stat('dodge') == 8  # 6 + 2

        encounter.queue(alice, QueuedAction("wait"))
        encounter.queue(bruiser, QueuedAction("wait"))
        await encounter.resolve_round()
        assert participant.combatant.get_stat('dodge') == 6  # reverted

    async def test_retarget_when_target_gone(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room, skill=16)
        b1, _ = make_fighter("Thug", room, player=False, dodge=0, hp=30)
        b2, _ = make_fighter("Brute", room, player=False, dodge=0, hp=30)
        encounter = await manager.initiate(alice, b1)
        encounter.add(b2, target=alice)
        encounter.queue(b1, QueuedAction("wait"))
        encounter.queue(b2, QueuedAction("wait"))
        encounter.queue(alice, QueuedAction("attack", target_id=b1.id))
        await encounter.resolve_round()

        encounter.remove(b1.id)  # target vanishes
        encounter.queue(b2, QueuedAction("wait"))
        await encounter.resolve_round()  # repeat-attack retargets to Brute

        assert int(b2.db.get('hp')) < 30


# --- Flee -----------------------------------------------------------------------


@pytest.mark.asyncio
class TestFlee:

    async def test_flee_success_leaves_combat_and_room(self, manager):
        room = GameObject("Arena", tags=["room"])
        street = GameObject("Street", tags=["room"])
        door = GameObject("out", location=room, tags=["exit"])
        door.db.destination_obj = street
        # dexterity 14 → flee default 12 >= 10: succeeds
        alice, _ = make_fighter("Alice", room, dexterity=14)
        bruiser, _ = make_fighter("Bruiser", room, player=False)
        encounter = await manager.initiate(alice, bruiser)
        encounter.queue(alice, QueuedAction("flee", args="out"))
        encounter.queue(bruiser, QueuedAction("wait"))

        await encounter.resolve_round()

        assert alice.location is street
        assert not alice.has_tag('in_combat')
        assert encounter.get(alice.id) is None

    async def test_flee_failure_wastes_the_beat(self, manager):
        room = GameObject("Arena", tags=["room"])
        street = GameObject("Street", tags=["room"])
        door = GameObject("out", location=room, tags=["exit"])
        door.db.destination_obj = street
        # dexterity 8 → flee default 6 < 10: fails
        alice, _ = make_fighter("Alice", room, dexterity=8)
        bruiser, _ = make_fighter("Bruiser", room, player=False)
        encounter = await manager.initiate(alice, bruiser)
        encounter.queue(alice, QueuedAction("flee", args="out"))
        encounter.queue(bruiser, QueuedAction("wait"))

        await encounter.resolve_round()

        assert alice.location is room
        assert encounter.get(alice.id) is not None

    async def test_flee_refuses_instance_portals(self, manager):
        """A portal resolves to PRIVATE per-walker space — fleeing through
        one is an unpursuable teleport into a fresh dungeon import, so it
        is excluded from flee entirely (registered shared_destination=False)."""
        import realm.core.instances  # noqa: F401 — registers the resolver

        room = GameObject("Shrine", tags=["room"])
        portal = GameObject("out", location=room, tags=["exit"])
        portal.db.dest_resolver = "instance"
        portal.db.instance_template = "crypt"

        alice, _ = make_fighter("Alice", room, dexterity=14)
        bruiser, _ = make_fighter("Bruiser", room, player=False)
        encounter = await manager.initiate(alice, bruiser)
        encounter.queue(alice, QueuedAction("flee", args="out"))
        encounter.queue(bruiser, QueuedAction("wait"))

        await encounter.resolve_round()

        assert alice.location is room                 # no escape hatch
        assert encounter.get(alice.id) is not None    # still in the fight

    async def test_flee_works_through_a_deferred_destination_exit(self, manager):
        """A wilderness cell's exits carry only a dest_resolver — flee must
        route them into move_through_exit (which resolves after the gates),
        not bail at 'There's nowhere to flee!'."""
        from realm.core.movement import register_dest_resolver

        room = GameObject("Wild Cell", tags=["room"])
        beyond = GameObject("Next Cell", tags=["room"])

        async def stub_resolver(exit_obj, actor):
            return beyond

        register_dest_resolver("flee-test-stub", stub_resolver)
        door = GameObject("out", location=room, tags=["exit"])
        door.db.dest_resolver = "flee-test-stub"      # no destination stored

        alice, _ = make_fighter("Alice", room, dexterity=14)
        bruiser, _ = make_fighter("Bruiser", room, player=False)
        encounter = await manager.initiate(alice, bruiser)
        encounter.queue(alice, QueuedAction("flee", args="out"))
        encounter.queue(bruiser, QueuedAction("wait"))

        await encounter.resolve_round()

        assert alice.location is beyond
        assert not alice.has_tag('in_combat')
        assert encounter.get(alice.id) is None


# --- Defeat ----------------------------------------------------------------------


@pytest.mark.asyncio
class TestDefeat:

    async def test_player_falls_unconscious_in_place(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, sess = make_fighter("Alice", room, hp=3, dodge=0)
        bruiser, _ = make_fighter("Bruiser", room, player=False, skill=16)
        encounter = await manager.initiate(bruiser, alice)
        encounter.queue(bruiser, QueuedAction("attack", target_id=alice.id))
        encounter.queue(alice, QueuedAction("wait"))

        await encounter.resolve_round()

        assert alice.has_tag('unconscious')
        assert alice.location is room  # stays put, revivable
        assert encounter.get(alice.id) is None

    async def test_npc_death_leaves_lootable_corpse(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room, skill=18)
        thug, _ = make_fighter("Thug", room, player=False, hp=3, dodge=0)
        loot = GameObject("credit chip", location=thug, tags=["thing"])
        encounter = await manager.initiate(alice, thug)
        encounter.queue(alice, QueuedAction("attack", target_id=thug.id))
        encounter.queue(thug, QueuedAction("wait"))

        await encounter.resolve_round()

        corpses = [o for o in room.contents if o.name.startswith("corpse of")]
        assert len(corpses) == 1
        assert loot.location is corpses[0]
        assert thug.location is None

    async def test_firstaid_revives_unconscious(self, manager):
        from realm.commands.builtin.combat import cmd_firstaid
        from realm.server.dispatcher import CommandContext, CommandDispatcher

        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room)
        alice.db.hp = 0
        alice.add_tag('unconscious')
        medic, sess = make_fighter("Medic", room, skill_first_aid=14)

        ctx = CommandContext(session=sess, player=medic, raw_input="",
                             command_name="firstaid", args="Alice",
                             dispatcher=CommandDispatcher())
        await cmd_firstaid(ctx)

        assert int(alice.db.get('hp')) > 0
        assert not alice.has_tag('unconscious')


# --- Strategies -------------------------------------------------------------------


@pytest.mark.asyncio
class TestStrategies:

    async def test_strategy_drives_npc(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room, hp=30)
        guard, _ = make_fighter("Guard", room, player=False, skill=16)
        guard.db.combat_strategy = [["", "attack"]]
        encounter = await manager.initiate(alice, guard)
        encounter.queue(alice, QueuedAction("wait"))
        alice.db.dodge = 0

        await encounter.resolve_round()

        assert int(alice.db.get('hp')) < 30

    async def test_wimpy_override_preempts_manual_queue(self, manager):
        room = GameObject("Arena", tags=["room"])
        street = GameObject("Street", tags=["room"])
        door = GameObject("out", location=room, tags=["exit"])
        door.db.destination_obj = street

        alice, _ = make_fighter("Alice", room, dexterity=14)
        alice.db.hp = 2  # 20% — below wimpy threshold
        alice.db.combat_strategy = [["!me.hp_percent < 30", "flee"]]
        bruiser, _ = make_fighter("Bruiser", room, player=False)
        encounter = await manager.initiate(alice, bruiser)

        # Alice bravely queued an attack; her reflexes disagree.
        encounter.queue(alice, QueuedAction("attack", target_id=bruiser.id))
        encounter.queue(bruiser, QueuedAction("wait"))

        await encounter.resolve_round()

        assert alice.location is street  # the override fled

    async def test_plain_strategy_defers_to_manual_queue(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room, skill=16)
        alice.db.combat_strategy = [["", "defend"]]  # no override flag
        bruiser, _ = make_fighter("Bruiser", room, player=False, dodge=0)
        encounter = await manager.initiate(alice, bruiser)
        encounter.queue(alice, QueuedAction("attack", target_id=bruiser.id))
        encounter.queue(bruiser, QueuedAction("wait"))

        await encounter.resolve_round()

        assert int(bruiser.db.get('hp')) < 10  # manual attack won

    async def test_bad_condition_fails_closed(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room)
        alice.db.combat_strategy = [["import os", "flee"], ["", "wait"]]
        bruiser, _ = make_fighter("Bruiser", room, player=False)
        encounter = await manager.initiate(alice, bruiser)
        encounter.queue(bruiser, QueuedAction("wait"))

        await encounter.resolve_round()

        assert alice.location is room  # malicious rule ignored


# --- GURPS maneuvers ---------------------------------------------------------------


@pytest.mark.asyncio
class TestGURPSManeuvers:

    async def test_all_out_attack_bonus_and_forfeited_defense(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room, skill=16)
        bruiser, _ = make_fighter("Bruiser", room, player=False,
                                  skill=16, dodge=6, hp=30)
        encounter = await manager.initiate(alice, bruiser)
        participant = encounter.get(alice.id)

        encounter.queue(alice, QueuedAction("all_out_attack",
                                            target_id=bruiser.id))
        encounter.queue(bruiser, QueuedAction("wait"))
        await encounter.resolve_round()

        # Defenses forfeited for the rest of the round...
        assert participant.combatant.get_stat('dodge') < 0
        # ...and restored next round.
        encounter.queue(alice, QueuedAction("wait"))
        encounter.queue(bruiser, QueuedAction("wait"))
        await encounter.resolve_round()
        assert participant.combatant.get_stat('dodge') == 6

    async def test_feint_opens_guard_next_round(self, manager):
        room = GameObject("Arena", tags=["room"])
        # Fixed 3d6=10: Alice margin 8, Bruiser margin -2 → opening capped 4
        alice, _ = make_fighter("Alice", room, skill=18)
        bruiser, _ = make_fighter("Bruiser", room, player=False,
                                  skill=8, dodge=6, hp=30)
        encounter = await manager.initiate(alice, bruiser)
        target = encounter.get(bruiser.id)

        encounter.queue(alice, QueuedAction("feint", target_id=bruiser.id))
        encounter.queue(bruiser, QueuedAction("wait"))
        await encounter.resolve_round()
        assert target.combatant.get_stat('dodge') == 6  # not yet

        encounter.queue(alice, QueuedAction("wait"))
        encounter.queue(bruiser, QueuedAction("wait"))
        await encounter.resolve_round()
        assert target.combatant.get_stat('dodge') == 2  # the opening

    async def test_d20_lacks_gurps_maneuvers(self, manager):
        from realm.combat.rulesets.d20 import D20Ruleset
        keys = {m.key for m in D20Ruleset().maneuvers()}
        assert "attack" in keys and "all_out_attack" not in keys


# --- Escalation --------------------------------------------------------------------


@pytest.mark.asyncio
class TestEscalation:

    async def test_hostile_action_auto_initiates_with_credit(self, manager):
        get_propagation_engine().add_observer(manager.hostile_observer)
        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room)
        guard, _ = make_fighter("Guard", room, player=False)

        # A softcoded hostile zap — not the attack command.
        zap = Action(actor=alice, target=guard,
                     action_type="spell:zap", tags={"hostile"},
                     chain=ROOM_TARGET_CHAIN)
        await propagate(zap)

        encounter = manager.encounter_of(alice)
        assert encounter is not None
        assert encounter.get(guard.id) is not None
        # The zap WAS Alice's first action.
        assert encounter.get(alice.id).last_action is not None

    async def test_watchful_hostile_guard_attacks_spotted_sneak(self, manager):
        hall = GameObject("Hall", tags=["room"])
        post = GameObject("Post", tags=["room"])
        guard, _ = make_fighter("Guard", post, player=False,
                                skill_observation=18)
        guard.add_behavior(WatchfulBehavior(hostile=True, spot_msg="Intruder!"))

        sneak, _ = make_fighter("Sneak", hall, skill_stealth=11)
        sneak.add_tag('hidden')

        await move_through_exit(sneak, post)

        encounter = manager.encounter_of(guard)
        assert encounter is not None
        assert encounter.get(sneak.id) is not None


# --- Timed effects (bleeding, poison, regeneration) --------------------------------


@pytest.mark.asyncio
class TestTimedEffects:

    async def test_bleeding_ticks_damage_and_expires(self, manager):
        from realm.behaviors import DamageOverTimeBehavior

        room = GameObject("Arena", tags=["room"])
        alice, sess = make_fighter("Alice", room, hp=10)
        bleed = DamageOverTimeBehavior(kind="bleeding", damage=2,
                                       interval=1, duration=3,
                                       expire_msg="The bleeding stops.")
        alice.add_behavior(bleed)
        assert alice.has_tag("bleeding")

        await bleed.on_beat(alice)
        assert int(alice.db.get('hp')) == 8

        await bleed.on_beat(alice)
        assert int(alice.db.get('hp')) == 6

        await bleed.on_beat(alice)  # duration exhausted -> expires
        assert not alice.has_tag("bleeding")
        assert bleed not in alice.get_behaviors()
        assert any("bleeding stops" in line for line in drain(sess))

    async def test_poison_kills_through_shared_death_path(self, manager):
        from realm.behaviors import DamageOverTimeBehavior

        room = GameObject("Arena", tags=["room"])
        thug, _ = make_fighter("Thug", room, player=False, hp=2)
        loot = GameObject("shiv", location=thug, tags=["thing"])
        poison = DamageOverTimeBehavior(kind="poisoned", damage=3, duration=10)
        thug.add_behavior(poison)

        await poison.on_beat(thug)

        corpses = [o for o in room.contents if o.name.startswith("corpse of")]
        assert len(corpses) == 1 and loot.location is corpses[0]

    async def test_poisoned_player_falls_unconscious(self, manager):
        from realm.behaviors import DamageOverTimeBehavior

        room = GameObject("Arena", tags=["room"])
        alice, _ = make_fighter("Alice", room, hp=1)
        poison = DamageOverTimeBehavior(kind="poisoned", damage=2, duration=10)
        alice.add_behavior(poison)

        await poison.on_beat(alice)

        assert alice.has_tag('unconscious')
        assert alice.location is room

    async def test_regeneration_heals_and_caps(self, manager):
        from realm.behaviors import RegenerationBehavior

        room = GameObject("Arena", tags=["room"])
        troll, _ = make_fighter("Troll", room, player=False, hp=10)
        troll.db.hp = 8
        regen = RegenerationBehavior(heal=3, duration=0)  # innate
        troll.add_behavior(regen)

        await regen.on_beat(troll)
        assert int(troll.db.get('hp')) == 10  # capped at max

        await regen.on_beat(troll)
        assert int(troll.db.get('hp')) == 10
        assert regen in troll.get_behaviors()  # permanent

    async def test_effect_survives_serialization(self, manager):
        from realm.behaviors import DamageOverTimeBehavior
        from realm.core.behaviors import BehaviorRegistry

        alice = GameObject("Alice", tags=["player"])
        alice.add_behavior(DamageOverTimeBehavior(kind="poisoned", damage=1,
                                                  duration=20))
        data = alice.get_behaviors()[0].to_dict()

        revived = BehaviorRegistry.from_dict(data)
        assert revived is not None
        assert revived.get_param('kind') == "poisoned"
        assert revived.get_param('duration') == 20

    async def test_registry_tracks_behavior_owners(self, manager):
        from realm.behaviors import RegenerationBehavior
        from realm.core.behaviors import behavior_owners

        obj = GameObject("thing", tags=["thing"])
        regen = RegenerationBehavior()
        obj.add_behavior(regen)
        assert obj in behavior_owners()

        obj.remove_behavior(regen)
        assert obj not in behavior_owners()


# --- Spawner, CP awards, progression, de-stubbed brains ---------------------------


@pytest.mark.asyncio
class TestSpawner:

    def _spawner(self, room, **over):
        from realm.behaviors import SpawnerBehavior
        params = dict(
            key="thug",
            respawn_ticks=3,
            announce="Another thug slinks in.",
            prototype={
                "name": "alley thug",
                "tags": ["npc"],
                "attrs": {"hp": 5, "max_hp": 5, "points": 20},
                "behaviors": [{"behavior_id": "combatant",
                               "params": {"death_message": "The thug gurgles."}}],
            },
        )
        params.update(over)
        spawner = SpawnerBehavior(**params)
        room.add_behavior(spawner)
        return spawner

    async def test_first_spawn_is_immediate(self, manager):
        room = GameObject("Alley", tags=["room"])
        spawner = self._spawner(room)

        await spawner.tick(room, 4.0)

        thugs = [o for o in room.contents if o.name == "alley thug"]
        assert len(thugs) == 1
        assert thugs[0].has_tag("spawned:thug")
        assert thugs[0].get_behaviors()[0].behavior_id == "combatant"

    async def test_population_is_capped(self, manager):
        room = GameObject("Alley", tags=["room"])
        spawner = self._spawner(room)
        for _ in range(5):
            await spawner.tick(room, 4.0)

        assert len([o for o in room.contents if o.name == "alley thug"]) == 1

    async def test_respawn_after_death_with_countdown(self, manager):
        room = GameObject("Alley", tags=["room"])
        spawner = self._spawner(room)
        await spawner.tick(room, 4.0)
        thug = next(o for o in room.contents if o.name == "alley thug")

        # Kill it the real way: the shared death path (corpse + removal).
        await manager.handle_death(thug)
        assert thug.location is None

        # Countdown: 3 ticks of vacancy, then the replacement arrives.
        await spawner.tick(room, 4.0)
        await spawner.tick(room, 4.0)
        await spawner.tick(room, 4.0)
        assert not [o for o in room.contents if o.name == "alley thug"]
        await spawner.tick(room, 4.0)

        thugs = [o for o in room.contents if o.name == "alley thug"]
        assert len(thugs) == 1
        assert thugs[0] is not thug  # a fresh spawn, not a resurrection


@pytest.mark.asyncio
class TestProgression:

    async def test_kill_awards_character_points(self, manager):
        room = GameObject("Arena", tags=["room"])
        alice, sess = make_fighter("Alice", room, skill=18)
        thug, _ = make_fighter("Thug", room, player=False, hp=3, dodge=0,
                               points=40)
        encounter = await manager.initiate(alice, thug)
        encounter.queue(alice, QueuedAction("attack", target_id=thug.id))
        encounter.queue(thug, QueuedAction("wait"))

        await encounter.resolve_round()

        assert int(alice.db.get('character_points')) == 4  # 40 // 10
        assert any("character points" in line for line in drain(sess))

    async def test_improve_spends_points(self, manager):
        from realm.commands.builtin.combat import cmd_improve
        from realm.server.dispatcher import CommandContext, CommandDispatcher

        room = GameObject("Arena", tags=["room"])
        alice, sess = make_fighter("Alice", room)
        alice.db.skill_stealth = 12
        alice.db.character_points = 9

        ctx = CommandContext(session=sess, player=alice, raw_input="",
                             command_name="improve", args="stealth",
                             dispatcher=CommandDispatcher())
        await cmd_improve(ctx)

        assert int(alice.db.get('skill_stealth')) == 13
        assert int(alice.db.get('character_points')) == 5

        await cmd_improve(ctx)  # 5 -> 1 point left, skill 14
        assert int(alice.db.get('skill_stealth')) == 14

        await cmd_improve(ctx)  # can't afford a third
        assert int(alice.db.get('skill_stealth')) == 14
        assert any("costs 4 points" in line for line in drain(sess))

    async def test_improve_from_untrained_default(self, manager):
        from realm.commands.builtin.combat import cmd_improve
        from realm.core.checks import set_skill_defaults
        from realm.server.dispatcher import CommandContext, CommandDispatcher
        from realm.systems import GurpsSystem

        set_skill_defaults(GurpsSystem().skill_defaults())

        room = GameObject("Arena", tags=["room"])
        alice, sess = make_fighter("Alice", room)  # dexterity 12, no stealth
        alice.db.character_points = 4

        ctx = CommandContext(session=sess, player=alice, raw_input="",
                             command_name="improve", args="stealth",
                             dispatcher=CommandDispatcher())
        await cmd_improve(ctx)

        # Untrained default was DX-5 = 7; first purchase trains to 8.
        assert int(alice.db.get('skill_stealth')) == 8


@pytest.mark.asyncio
class TestDestubbedBrains:

    async def test_aggressive_engages_through_manager(self, manager):
        lair = GameObject("Lair", tags=["room"])
        outside = GameObject("Cave Mouth", tags=["room"])
        from realm.combat.behaviors import AggressiveBehavior
        beast, _ = make_fighter("beast", lair, player=False)
        beast.add_behavior(AggressiveBehavior(taunt="Fresh meat!"))

        alice, sess = make_fighter("Alice", outside)
        await move_through_exit(alice, lair)

        encounter = manager.encounter_of(beast)
        assert encounter is not None
        assert encounter.get(alice.id) is not None
        assert any('"Fresh meat!"' in line for line in drain(sess))

    async def test_defensive_writes_flee_reflex(self, manager):
        from realm.combat.behaviors import DefensiveBehavior
        npc = GameObject("merchant", tags=["npc"])
        npc.add_behavior(DefensiveBehavior(flee_percent=30))

        rules = npc.db.get('combat_strategy')
        assert ["!me.hp_percent < 30", "flee"] in rules

    async def test_wandering_moves_within_zone(self, manager):
        from realm.combat.behaviors import WanderingBehavior
        here = GameObject("Market", tags=["room", "zone:town"])
        there = GameObject("Square", tags=["room", "zone:town"])
        beyond = GameObject("Wilds", tags=["room", "zone:wild"])
        east = GameObject("east", location=here, tags=["exit"])
        east.db.destination_obj = there
        north = GameObject("north", location=here, tags=["exit"])
        north.db.destination_obj = beyond

        drifter, _ = make_fighter("drifter", here, player=False)
        wander = WanderingBehavior(wander_chance=1.0, pause=0,
                                   stay_in_zone=True)
        drifter.add_behavior(wander)

        for _ in range(12):
            await wander.tick(drifter, 4.0)
        # Always in-zone, never the wilds.
        assert drifter.location in (here, there)

    async def test_combatant_death_message(self, manager):
        from realm.combat.behaviors import CombatantBehavior
        room = GameObject("Arena", tags=["room"])
        alice, sess = make_fighter("Alice", room, skill=18)
        thug, _ = make_fighter("Thug", room, player=False, hp=3, dodge=0)
        thug.add_behavior(CombatantBehavior(
            death_message="The thug curses corporate healthcare and dies."))
        encounter = await manager.initiate(alice, thug)
        encounter.queue(alice, QueuedAction("attack", target_id=thug.id))
        encounter.queue(thug, QueuedAction("wait"))

        await encounter.resolve_round()

        assert any("corporate healthcare" in line for line in drain(sess))
