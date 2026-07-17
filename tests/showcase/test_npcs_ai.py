"""
NPCs & AI behaviors (showcase items 61, 62, 65, 66, 69, 70, 72, 73).

Standalone tutorials, one world per test class: every "Build it"
command line from docs/showcase/061_patrolling_guard.md,
062_aggressive_mob.md, 065_pet.md, 066_puppet.md, 069_trainer_npc.md,
070_pickpocket_npc.md, 072_npc_reactions.md and 073_boss_phases.md is
typed through the real dispatcher (Simulator), then each tutorial's
"Try it" behavior is verified: raw input in, session output out.

Determinism: behavior ticks are pumped by calling the attached
behaviors' tick() directly; combat uses a diceless GURPS ruleset
(3d6 always 10, damage flat 2) with rounds fired by resolve_round();
skill contests (item 70) use the margin-by-level resolver from the
engine's own combat tests.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.testing import Simulator

# Output fragments that only appear when a typed Build-it line failed.
_ERROR_MARKS = ("not found", "Usage:", "Unknown command", "Bad parameter",
                "Unknown behavior", "Permission denied", "Invalid lock",
                "don't control", "An error occurred")


def _find(sim, name):
    objs = sim.store.find_cached(name=name)
    assert objs, f"no object named {name!r}"
    return objs[0]


def _behavior(obj, behavior_id):
    return next(b for b in obj.get_behaviors() if b.behavior_id == behavior_id)


async def _tick(obj, behavior_id="script_ticker"):
    await _behavior(obj, behavior_id).tick(obj, 4.0)


def _text(messages):
    return "\n".join(messages)


def _steady_manager():
    """A combat manager with the dice removed: 3d6 always 10, damage 2."""
    from realm.combat.manager import CombatManager
    from realm.combat.ruleset import DamageResult, DamageType
    from realm.combat.rulesets.gurps import GURPSRuleset
    from realm.combat.system import CombatSystem

    class SteadyRuleset(GURPSRuleset):
        def roll_3d6(self):
            return 10, [3, 3, 4]

        def roll_damage(self, attacker, defender, attack_result, weapon=None):
            return DamageResult(total=2,
                                damage_by_type={DamageType.PHYSICAL: 2})

    return CombatManager(CombatSystem(ruleset=SteadyRuleset()),
                         beat_min=4.0, beat_max=600.0, beat_default=300.0)


def _end_brawl(manager, anyone):
    """Stand-in for a successful flee: unwind an encounter cleanly
    (participants lose their in_combat tags). Flee itself is exercised
    in the engine's combat tests."""
    encounter = manager.encounter_of(anyone)
    if encounter is None:
        return
    for obj_id in list(encounter.participants.keys()):
        encounter.remove(obj_id)
    manager.encounter_ended(encounter)
    encounter.end()


def _make_world(*, role="builder"):
    """A Simulator with a staff player in a workroom, plus a line runner
    that fails the test on any error-marked output."""
    sim = Simulator()
    workroom = sim.room("The Workroom")
    staff = sim.player("Tam", location=workroom)
    staff.add_tag(role)
    workroom.owner = staff
    sim.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: [sim.session(staff)])

    errors: list[str] = []

    async def run(lines, player=staff):
        for line in lines:
            await sim.do(player, line)
            for msg in sim.seen(player):
                if any(mark in msg for mark in _ERROR_MARKS):
                    errors.append(f"{line!r} -> {msg!r}")
        assert not errors, errors

    return SimpleNamespace(sim=sim, staff=staff, workroom=workroom, run=run)


async def _do(world, line, player=None):
    """Type one line, return everything that player's session printed."""
    player = player or world.staff
    await world.sim.do(player, line)
    return _text(world.sim.seen(player))


# --- 61. Patrolling guard ----------------------------------------------------

BUILD_061 = [
    "@dig The Gatehouse = gatehouse, back",
    "gatehouse",
    "@dig The North Wall = wall, gatehouse",
    "wall",
    "@dig The Battlements = battlements, wall",
    "@dig The Armory = armory door, armory door",
    "@set armory door/door = 1",
    "armory door",
    "@set armory door/door = 1",
    "armory door",
    "close armory door",
    "@create Sergeant Yara",
    "@tag Sergeant Yara = npc",
    "drop Sergeant Yara",
    "@desc Sergeant Yara = Boots you could shave in. She walks the same "
    "round she has walked for nine years.",
    "@set Sergeant Yara/on_open = (say('Who goes into the armory? State "
    "your business.'), set_attr(me, 'challenged', now())) if now() - "
    "get_attr(me, 'challenged', 0) > 20 else None",
    "@set Sergeant Yara/on_arrive = left_open = [o for o in contents(here) "
    "if has_tag(o, 'exit') and get_attr(o, 'door', 0) and not "
    "has_tag(o, 'closed')]; [(pose('mutters about lax discipline.'), "
    "cmd('close ' + name(o))) for o in left_open]",
    '@behavior Sergeant Yara = patrol, route:["battlements", "wall", '
    '"gatehouse", "wall"], pause:2',
]


@pytest.fixture
async def castle():
    world = _make_world()
    await world.run(BUILD_061)
    try:
        yield world
    finally:
        world.sim.close()


class TestPatrollingGuard:

    async def test_fixed_route_with_pauses(self, castle):
        sim = castle.sim
        yara = _find(sim, "Sergeant Yara")
        north_wall = _find(sim, "The North Wall")
        battlements = _find(sim, "The Battlements")
        gatehouse = _find(sim, "The Gatehouse")
        patrol = _behavior(yara, "patrol")
        assert yara.location is north_wall

        # pause:2 -> one step every third tick, in fixed route order.
        await patrol.tick(yara, 4.0)
        assert yara.location is battlements
        for _ in range(3):
            await patrol.tick(yara, 4.0)
        assert yara.location is north_wall
        for _ in range(3):
            await patrol.tick(yara, 4.0)
        assert yara.location is gatehouse
        for _ in range(3):
            await patrol.tick(yara, 4.0)
        assert yara.location is north_wall
        # And around again — a loop, not a one-shot.
        for _ in range(3):
            await patrol.tick(yara, 4.0)
        assert yara.location is battlements

    async def test_on_open_challenge_with_cooldown(self, castle):
        # Build ends with the builder and Yara both on the North Wall.
        out = await _do(castle, "open armory door")
        assert "Who goes into the armory? State your business." in out

        # Re-open within the cooldown window: she holds her tongue.
        await _do(castle, "close armory door")
        out = await _do(castle, "open armory door")
        assert "Who goes into the armory" not in out

    async def test_arrival_sweep_closes_doors_left_open(self, castle):
        sim = castle.sim
        yara = _find(sim, "Sergeant Yara")
        north_wall = _find(sim, "The North Wall")
        door = next(o for o in north_wall.contents
                    if o.has_tag("exit") and o.name == "armory door")
        patrol = _behavior(yara, "patrol")

        await _do(castle, "open armory door")   # the crime
        assert not door.has_tag("closed")

        # She walks her round: away to the battlements, then back — and
        # her ON_ARRIVE sweep finds the open armory door.
        await patrol.tick(yara, 4.0)
        assert yara.location is not north_wall
        for _ in range(3):
            await patrol.tick(yara, 4.0)
        assert yara.location is north_wall

        out = _text(sim.seen(castle.staff))
        assert "mutters about lax discipline" in out
        assert door.has_tag("closed")

    async def test_closed_door_on_route_stalls_the_patrol(self, castle):
        # Not her route here — so prove the movement gate generally: park
        # her mid-round and close the way she's about to take.
        sim = castle.sim
        yara = _find(sim, "Sergeant Yara")
        battlements = _find(sim, "The Battlements")
        patrol = _behavior(yara, "patrol")

        await patrol.tick(yara, 4.0)            # off to the battlements
        assert yara.location is battlements
        # Close the way back (exits close like doors: they're exits).
        wall_exit = next(o for o in battlements.contents
                         if o.has_tag("exit") and o.name == "wall")
        wall_exit.add_tag("closed")
        for _ in range(6):
            await patrol.tick(yara, 4.0)
        assert yara.location is battlements     # stalled, retrying
        wall_exit.remove_tag("closed")
        for _ in range(3):
            await patrol.tick(yara, 4.0)
        assert yara.location is not battlements


# --- 62. Aggressive mob --------------------------------------------------------

BUILD_062 = [
    "@dig The Warren Mouth = warren, out",
    "warren",
    "@dig The Brood Chamber = deeper, out",
    "deeper",
    "@create broodmother",
    "@tag broodmother = npc",
    "drop broodmother",
    "@set broodmother/hp = 14",
    "@set broodmother/max_hp = 14",
    "@set broodmother/skill_melee = 12",
    "@set broodmother/on_enter = start_combat(me, enactor) if "
    "has_tag(enactor, 'player') and tag_value(enactor, 'faction') != "
    "'ratkin' and disposition(me, enactor) < 2 else None",
    "out",
    "@create warren rat",
    "@tag warren rat = npc",
    "drop warren rat",
    "@set warren rat/hp = 8",
    "@set warren rat/max_hp = 8",
    "@set warren rat/skill_melee = 10",
    "@set warren rat/on_receive = adjust_disposition(me, enactor, 5); "
    "pose('sniffs the offering and settles back, watching ' + "
    "name(enactor) + ' with something like tolerance.')",
    '@behavior warren rat = aggressive, target_tags:["player"], spare_at:2, '
    "attack_chance:1.0, taunt:The rat's eyes go red. It lunges!",
    "out",
]


@pytest.fixture
async def warren():
    from realm.combat.manager import set_combat_manager

    world = _make_world()
    await world.run(BUILD_062)
    manager = _steady_manager()
    set_combat_manager(manager)
    try:
        yield SimpleNamespace(**vars(world), manager=manager)
    finally:
        manager.stop_all()
        set_combat_manager(None)
        world.sim.close()


class TestAggressiveMob:

    async def test_attack_on_sight_then_tribute_buys_standing(self, warren):
        from realm.core.disposition import get_disposition

        sim, tam, manager = warren.sim, warren.staff, warren.manager
        rat = _find(sim, "warren rat")

        for line in ("@set me/hp = 12", "@set me/max_hp = 12",
                     "@set me/skill_melee = 12", "@create dead beetle"):
            await _do(warren, line)

        # Walk in cold: the rat taunts and engages on sight.
        out = await _do(warren, "warren")
        assert "The rat's eyes go red. It lunges!" in out
        assert manager.encounter_of(tam) is not None
        assert manager.encounter_of(rat) is manager.encounter_of(tam)

        # Tribute is paid mid-scrap (give is not combat-gated)...
        out = await _do(warren, "give dead beetle to warren rat")
        assert "sniffs the offering and settles back" in out
        assert get_disposition(rat, tam) == 5

        # ...and buys the NEXT fight, not this one. (The tutorial flees;
        # the harness ends the brawl directly — flee itself is exercised
        # in the engine's combat tests.)
        _end_brawl(manager, tam)
        await _do(warren, "out")
        out = await _do(warren, "warren")
        assert "It lunges!" not in out
        assert manager.encounter_of(tam) is None   # spared: spare_at:2

    async def test_softcode_faction_gate(self, warren):
        sim, tam, manager = warren.sim, warren.staff, warren.manager
        brood = _find(sim, "broodmother")

        for line in ("@set me/hp = 12", "@set me/max_hp = 12",
                     "@set me/skill_melee = 12"):
            await _do(warren, line)
        # Sneak past the rat's opinion for this test: it likes rich gifts.
        await _do(warren, "@create dead beetle")
        await _do(warren, "warren")
        await _do(warren, "give dead beetle to warren rat")
        _end_brawl(manager, tam)

        # An outsider entering the chamber is attacked — no taunt, no
        # hesitation: the one-line ON_ENTER gate.
        await _do(warren, "deeper")
        assert manager.encounter_of(tam) is not None
        assert manager.encounter_of(brood) is manager.encounter_of(tam)
        _end_brawl(manager, tam)

        # Join the faction: the tag-value check waves you through.
        await _do(warren, "out")
        await _do(warren, "@tag me = faction:ratkin")
        await _do(warren, "deeper")
        assert manager.encounter_of(tam) is None


# --- 65. Pet -------------------------------------------------------------------

BUILD_065 = [
    "@dig The Kennel Yard = yard, out",
    "yard",
    "@create Biscuit",
    "@tag Biscuit = npc",
    "drop Biscuit",
    "@desc Biscuit = A ginger hound with an opinion about everything.",
    "@lock/listen Biscuit = caller.id == owner.id",
    "@set Biscuit/listen_heel = ^*heel*:set_attr(me, 'following', "
    "enactor.id); pose('falls in at ' + name(enactor) + \"'s heel.\")",
    "@set Biscuit/listen_stay = ^*stay*:del_attr(me, 'following'); "
    "pose('sits, ears up, exactly where told.')",
    "@set Biscuit/listen_speak = ^*speak*:pose('barks once, sharp and "
    "proud.')",
]


@pytest.fixture
async def kennel():
    world = _make_world()
    await world.run(BUILD_065)
    try:
        yield world
    finally:
        world.sim.close()


class TestPet:

    async def test_orders_follow_and_stay(self, kennel):
        sim, tam = kennel.sim, kennel.staff
        biscuit = _find(sim, "Biscuit")
        yard = _find(sim, "The Kennel Yard")

        out = await _do(kennel, "say Biscuit, speak")
        assert "barks once, sharp and proud." in out

        # Heel: one attribute is the whole follow system.
        out = await _do(kennel, "say Biscuit, heel")
        assert "falls in at Tam's heel." in out
        assert biscuit.db.get("following") == tam.id

        # He walks the real exits after his owner.
        await _do(kennel, "out")
        assert biscuit.location is kennel.workroom
        out = await _do(kennel, "party")
        assert "Biscuit" in out and "following" in out

        await _do(kennel, "yard")
        assert biscuit.location is yard

        # Stay: the attribute goes away, and so does the following.
        out = await _do(kennel, "say Biscuit, stay")
        assert "sits, ears up, exactly where told." in out
        assert biscuit.db.get("following") is None
        await _do(kennel, "out")
        assert biscuit.location is yard

    async def test_listen_lock_whitelists_the_owner(self, kennel):
        sim, tam = kennel.sim, kennel.staff
        biscuit = _find(sim, "Biscuit")
        yard = _find(sim, "The Kennel Yard")
        rook = sim.player("Rook", location=yard)

        await _do(kennel, "say Biscuit, heel")
        assert biscuit.db.get("following") == tam.id

        # A stranger's orders never reach his triggers: the listen lock.
        out = await _do(kennel, "say Biscuit, stay", player=rook)
        assert "sits, ears up" not in out
        assert biscuit.db.get("following") == tam.id

        # The owner's do.
        out = await _do(kennel, "say Biscuit, stay")
        assert "sits, ears up" in out
        assert biscuit.db.get("following") is None


# --- 66. Puppet ------------------------------------------------------------------

BUILD_066 = [
    "@dig The Puppeteer's Booth = booth, out",
    "booth",
    "@create marionette",
    "@tag marionette = npc",
    "drop marionette",
    "@desc marionette = A jointed wooden figure, strings trailing up into "
    "nothing.",
    "@force marionette = look",
    "@force marionette = say I dance for no one.",
    "@force marionette = out",
    "@force marionette = booth",
]


@pytest.fixture
async def booth():
    world = _make_world()
    await world.run(BUILD_066)
    try:
        yield world
    finally:
        world.sim.close()


class TestPuppet:

    async def test_forced_commands_forward_output(self, booth):
        sim = booth.sim
        marionette = _find(sim, "marionette")
        booth_room = _find(sim, "The Puppeteer's Booth")
        assert marionette.location is booth_room  # walked out and back

        # You see through its eyes, prefixed.
        out = await _do(booth, "@force marionette = look")
        assert "[marionette]" in out
        assert "The Puppeteer's Booth" in out

        # Its speech is real speech — you witness it from your own body.
        out = await _do(booth, "@force marionette = say I dance for no one.")
        assert 'marionette says, "I dance for no one."' in out

    async def test_puppet_acts_with_its_own_station(self, booth):
        # An NPC body rates as a PLAYER: no builder commands through it.
        out = await _do(booth, "@force marionette = @dig Vault")
        assert "[marionette] Permission denied." in out
        assert not booth.sim.store.find_cached(name="Vault")

    async def test_possessing_a_player_needs_their_consent(self, booth):
        sim, tam = booth.sim, booth.staff
        wren = sim.player("Wren", location=booth.workroom)
        wren.add_tag("builder")   # @lock is a builder command today
        await _do(booth, "out")   # join Wren in the workroom

        # No consent, no possession — players are nobody's property.
        out = await _do(booth, "@force Wren = say The stars are lovely.")
        assert "You don't control Wren." in out

        # Wren signs her strings over to anything tagged 'mesmerist'.
        out = await _do(booth, "@lock/control me = caller.has_tag('mesmerist')",
                        player=wren)
        assert "Lock/control set on Wren." in out
        await _do(booth, "@tag me = mesmerist")

        out = await _do(booth, "@force Wren = say The stars are lovely.")
        assert 'Wren says, "The stars are lovely."' in out
        # And Wren watches herself say it.
        assert 'You say, "The stars are lovely."' in _text(sim.seen(wren))


# --- 69. Trainer NPC --------------------------------------------------------------

BUILD_069 = [
    "@dig The Drill Yard = drills, out",
    "drills",
    "@create Sergeant Kel",
    "@tag Sergeant Kel = npc",
    "drop Sergeant Kel",
    "@desc Sergeant Kel = Scarred forearms, patient eyes. She has taught "
    "worse than you.",
    '@set Sergeant Kel/teaches = {"melee": {"fee": 15, "cap": 12}, '
    '"guns": {"fee": 25, "cap": 12, "needs": ["melee", 11]}}',
    "@set Sergeant Kel/cmd_lessons = $lessons:t = get_attr(me, 'teaches', "
    "{}); say('I drill: ' + ', '.join(sorted(t)) + '. Coin first, bruises "
    "after. Say train and the skill.')",
    "@set Sergeant Kel/cmd_train = $train *:s = trim(arg0).lower()"
    ".replace(' ', '_'); t = get_attr(me, 'teaches', {}); r = t.get(s); "
    "cur = get_attr(enactor, 'skill_' + s, 9); (say('I do not teach ' + s "
    "+ '. Ask about my lessons.') if not r else say('You are past my "
    "lessons in ' + s + '. Spend points, or find a better teacher.') if "
    "cur >= r['cap'] else say('Not yet. Come back when your ' + "
    "r['needs'][0].replace('_', ' ') + ' reaches ' + str(r['needs'][1]) + "
    "'.') if 'needs' in r and get_attr(enactor, 'skill_' + r['needs'][0], "
    "9) < r['needs'][1] else say('My fee is ' + str(r['fee']) + "
    "' credits. You are short.') if credits(enactor) < r['fee'] else "
    "(transfer_credits(enactor, me, r['fee']), set_attr(enactor, "
    "'skill_' + s, cur + 1), say('Again! ...Better. Your ' + "
    "s.replace('_', ' ') + ' is now ' + str(cur + 1) + '.')))",
]


@pytest.fixture
async def drill_yard():
    # The trainer writes other players' sheets: she must be ADMIN-owned.
    world = _make_world(role="admin")
    await world.run(BUILD_069)
    try:
        yield world
    finally:
        world.sim.close()


class TestTrainerNpc:

    async def test_lessons_fees_prereqs_caps_and_the_cp_road(self, drill_yard):
        sim, marla = drill_yard.sim, drill_yard.staff
        kel = _find(sim, "Sergeant Kel")
        yard = _find(sim, "The Drill Yard")
        rian = sim.player("Rian", location=yard)
        await _do(drill_yard, "@set Rian/credits = 100")   # staff funds the demo

        out = await _do(drill_yard, "lessons", player=rian)
        assert "I drill: guns, melee." in out

        # Prerequisite gate first.
        out = await _do(drill_yard, "train guns", player=rian)
        assert "Not yet. Come back when your melee reaches 11." in out
        assert rian.db.get("skill_guns") is None

        # Three lessons to her cap; fees flow student -> trainer.
        for level in (10, 11, 12):
            out = await _do(drill_yard, "train melee", player=rian)
            assert f"Your melee is now {level}." in out
            assert rian.db.get("skill_melee") == level
        assert rian.db.get("credits") == 55
        assert kel.db.get("credits") == 45

        # The cap.
        out = await _do(drill_yard, "train melee", player=rian)
        assert "You are past my lessons in melee." in out
        assert rian.db.get("skill_melee") == 12

        # Prereq now met: guns opens up.
        out = await _do(drill_yard, "train guns", player=rian)
        assert "Your guns is now 10." in out
        assert rian.db.get("credits") == 30

        # Not on the curriculum.
        out = await _do(drill_yard, "train basketry", player=rian)
        assert "I do not teach basketry." in out

        # Run the purse dry: the fee gate.
        out = await _do(drill_yard, "train guns", player=rian)
        assert "Your guns is now 11." in out
        out = await _do(drill_yard, "train guns", player=rian)
        assert "My fee is 25 credits. You are short." in out
        assert rian.db.get("credits") == 5

        # The built-in CP economy composes: improve pushes past her cap.
        await _do(drill_yard, "@set Rian/character_points = 8")
        out = await _do(drill_yard, "improve melee", player=rian)
        assert "You train melee to 13" in out
        out = await _do(drill_yard, "points", player=rian)
        assert "Character points: 4" in out
        assert "melee" in out


# --- 70. Pickpocket NPC -------------------------------------------------------------

BUILD_070 = [
    "@create pickpocket",
    "@tag pickpocket = skill_def",
    "@set pickpocket/stat = dexterity",
    "@set pickpocket/penalty = -5",
    "drop pickpocket",
    "@reload",
    "@dig Shadow Market = shadows, out",
    "shadows",
    "@zone here = bazaar",
    "@create Fenn",
    "@tag Fenn = npc",
    "drop Fenn",
    "@desc Fenn = Lean, quick-eyed, always somehow just behind your "
    "shoulder.",
    "@set Fenn/hp = 8",
    "@set Fenn/max_hp = 8",
    "@set Fenn/skill_pickpocket = 14",
    "@set Fenn/skill_melee = 9",
    "@set Fenn/on_tick = marks = [p for p in contents(here) if "
    "has_tag(p, 'player') and not has_tag(p, 'unconscious')]; "
    "m = marks[rand(0, len(marks) - 1)] if marks else None; "
    "loot = [o for o in contents(m)] if m else []; "
    "(((teleport_obj(loot[0], me) if loot else transfer_credits(m, me, 5)), "
    "pemit(m, 'A feather-light tug at your belt. Probably nothing.')) if "
    "contest(me, 'pickpocket', m, 'observation') else (remit(here, name(m) "
    "+ \" catches a hand in their pouch - Fenn's!\"), act(here, 'THIEF! "
    "The cry goes up.', targeting='room', action_type='event:theft'))) "
    "if m else None",
    "@behavior Fenn = script_ticker, interval:3",
    "@dig The Watch Post = watchpost, shadows",
    "watchpost",
    "@zone here = bazaar",
    "@create Constable Marsh",
    "@tag Constable Marsh = npc",
    "@tag Constable Marsh = town_watch",
    "@set Constable Marsh/hp = 14",
    "@set Constable Marsh/max_hp = 14",
    "@set Constable Marsh/skill_melee = 13",
    "drop Constable Marsh",
    "@create Bazaar Watch",
    "@zone/master Bazaar Watch = bazaar",
    "@set Bazaar Watch/on_theft = fresh = now() - get_attr(me, 'last_cry', "
    "0) > 60; ((set_attr(me, 'last_cry', now()), adjust_disposition("
    "'Constable Marsh', enactor, -5), teleport_obj('Constable Marsh', "
    "here), force('Constable Marsh', 'say Hold, cutpurse!'), "
    "force('Constable Marsh', 'attack ' + name(enactor))) if fresh "
    "else None)",
    "drop Bazaar Watch",
    "shadows",
]


@pytest.fixture
async def bazaar():
    from realm.combat.manager import set_combat_manager
    from realm.core.checks import (
        CheckResult,
        set_check_resolver,
        skill_level,
    )

    # Deterministic contests: success iff effective level >= 10, margin by
    # level (the engine's own combat-test resolver).
    def level_resolver(obj, skill, modifier):
        effective = skill_level(obj, skill) + modifier
        return CheckResult(success=effective >= 10, margin=effective - 10,
                           roll=10, effective=effective, skill=skill)

    world = _make_world(role="admin")   # Fenn's fingers need the rank
    await world.run(BUILD_070)
    manager = _steady_manager()
    set_combat_manager(manager)
    set_check_resolver(level_resolver)
    try:
        yield SimpleNamespace(**vars(world), manager=manager)
    finally:
        manager.stop_all()
        set_combat_manager(None)
        set_check_resolver(world.sim.game_system.resolve_check)
        world.sim.close()


class TestPickpocketNpc:

    async def test_theft_capture_and_crime_response(self, bazaar):
        from realm.core.disposition import get_disposition

        sim, marla, manager = bazaar.sim, bazaar.staff, bazaar.manager
        fenn = _find(sim, "Fenn")
        marsh = _find(sim, "Constable Marsh")
        shadows = _find(sim, "Shadow Market")
        post = _find(sim, "The Watch Post")
        assert marsh.location is post

        # Carry something worth taking and loiter.
        await _do(bazaar, "@create silver locket")
        locket = _find(sim, "silver locket")
        assert locket.location is marla

        # Fenn's tick: pickpocket 14 vs untrained observation — he wins,
        # the locket crosses pockets, the mark feels only a tug.
        for _ in range(4):
            await _tick(fenn)
            if locket.location is fenn:
                break
        assert locket.location is fenn
        out = _text(sim.seen(marla))
        assert "A feather-light tug at your belt. Probably nothing." in out

        # A harder mark: observation 16 out-margins his 14 — caught, and
        # the custom event:theft summons the law (item 71's dispatch).
        await _do(bazaar, "@set me/skill_observation = 16")
        for _ in range(4):
            await _tick(fenn)
            if marsh.location is shadows:
                break
        out = _text(sim.seen(marla))
        assert "catches a hand in their pouch - Fenn's!" in out
        assert "THIEF! The cry goes up." in out
        assert "Hold, cutpurse!" in out
        assert marsh.location is shadows
        assert get_disposition(marsh, fenn) == -5
        # The constable arrests the thief, not the victim.
        assert manager.encounter_of(marsh) is not None
        assert manager.encounter_of(fenn) is manager.encounter_of(marsh)
        assert manager.encounter_of(marla) is None


# --- 72. NPC reaction emotes ----------------------------------------------------------

BUILD_072 = [
    "@dig The Anchor Taproom = taproom, out",
    "taproom",
    "@create Nerissa",
    "@tag Nerissa = npc",
    "drop Nerissa",
    "@desc Nerissa = The Anchor's keeper. Nothing in this room escapes "
    "her.",
    "@set Nerissa/listen_greet = ^*evening*:say Evening yourself. First "
    "one's full price, same as always.",
    "@set Nerissa/listen_trouble = ^*fight*:say Take that talk to the "
    "alley or lose your tab.",
    "@set Nerissa/on_emote = (pose('glances up, marking ' + name(enactor) "
    "+ ' with one raised eyebrow.'), set_attr(me, 'noticed', now())) if "
    "now() - get_attr(me, 'noticed', 0) > 15 else None",
    "@set Nerissa/on_wield = (say('Steel away in my taproom, ' + "
    "name(enactor) + '. I will not ask twice.'), adjust_disposition(me, "
    "enactor, -1)) if not has_tag(enactor, 'town_watch') else None",
]


@pytest.fixture
async def taproom():
    world = _make_world()
    await world.run(BUILD_072)
    try:
        yield world
    finally:
        world.sim.close()


class TestNpcReactions:

    async def test_speech_reactions_key_on_content(self, taproom):
        out = await _do(taproom, "say good evening, all")
        assert "Evening yourself. First one's full price" in out
        out = await _do(taproom, "say I hear there was a fight")
        assert "Take that talk to the alley or lose your tab." in out

    async def test_emote_reaction_with_cooldown(self, taproom):
        out = await _do(taproom, "pose stretches and cracks his knuckles.")
        assert "glances up, marking Tam with one raised eyebrow." in out

        # Within the cooldown window she's already noticed you.
        out = await _do(taproom, "pose whistles innocently.")
        assert "raised eyebrow" not in out

        # Expire the cooldown attr and the eyebrow returns.
        nerissa = _find(taproom.sim, "Nerissa")
        nerissa.db.noticed = 0
        out = await _do(taproom, "pose drums his fingers.")
        assert "raised eyebrow" in out

    async def test_weapon_draw_reaction_and_disposition_price(self, taproom):
        from realm.core.disposition import get_disposition

        nerissa = _find(taproom.sim, "Nerissa")
        await _do(taproom, "@create rusty cutlass")
        out = await _do(taproom, "wield rusty cutlass")
        assert "Steel away in my taproom, Tam. I will not ask twice." in out
        assert get_disposition(nerissa, taproom.staff) == -1


# --- 73. Boss with phases ---------------------------------------------------------------

BUILD_073 = [
    "@dig The Undervault = undervault, out",
    "undervault",
    "@create Skarn the Bonewright",
    "@tag Skarn the Bonewright = npc",
    "drop Skarn the Bonewright",
    "@desc Skarn the Bonewright = A hulk of fused bone and bad intent. "
    "Something in him is still counting.",
    "@set Skarn the Bonewright/hp = 20",
    "@set Skarn the Bonewright/max_hp = 20",
    "@set Skarn the Bonewright/skill_melee = 12",
    "@set Skarn the Bonewright/dodge = 5",
    '@set Skarn the Bonewright/combat_strategy = [["", "attack"]]',
    "@set Skarn the Bonewright/hitprcnt = 50",
    "@set Skarn the Bonewright/on_hitprcnt = trigger('phase_two' if "
    "get_attr(me, 'phase', 1) == 1 else 'phase_three')",
    "@set Skarn the Bonewright/phase_two = set_attr(me, 'phase', 2); "
    "set_attr(me, 'hitprcnt', 25); remit(here, 'Skarn slams both fists to "
    "the floor. BONES OF THE DEEP - RISE!'); w = create_obj('bone whelp', "
    "tags=['npc'], location=here); set_attr(w, 'hp', 6); set_attr(w, "
    "'max_hp', 6); set_attr(w, 'skill_melee', 10); set_attr(w, "
    "'combat_strategy', [['', 'attack']]); foes = [p for p in "
    "contents(here) if has_tag(p, 'player') and has_tag(p, 'in_combat')]; "
    "(start_combat(w, foes[0]) if foes else None); apply_effect(me, "
    "'modifier_effect', kind='berserk', duration=100, "
    "check_mods={'melee': 2})",
    "@set Skarn the Bonewright/phase_three = set_attr(me, 'phase', 3); "
    "remit(here, 'Cracks spider across Skarn. He gives ground, guarding "
    "the wound.'); set_attr(me, 'combat_strategy', [[\"\", \"defend\"]])",
    "@set Skarn the Bonewright/on_death = remit(here, 'Skarn comes apart "
    "at the seams, whispering: the vault... was never... mine...')",
]


@pytest.fixture
async def undervault():
    from realm.combat.manager import set_combat_manager

    world = _make_world()
    await world.run(BUILD_073)
    manager = _steady_manager()
    set_combat_manager(manager)
    try:
        yield SimpleNamespace(**vars(world), manager=manager)
    finally:
        manager.stop_all()
        set_combat_manager(None)
        world.sim.close()


class TestBossPhases:

    async def test_three_acts_and_a_death(self, undervault):
        sim, tam, manager = undervault.sim, undervault.staff, undervault.manager
        skarn = _find(sim, "Skarn the Bonewright")
        vault = _find(sim, "The Undervault")

        for line in ("@set me/hp = 40", "@set me/max_hp = 40",
                     "@set me/skill_melee = 13"):
            await _do(undervault, line)

        await _do(undervault, "attack Skarn the Bonewright")
        encounter = manager.encounter_of(tam)
        assert encounter is not None

        # Act one: flat 2 damage a round carries him toward half health.
        for _ in range(4):
            await encounter.resolve_round()
        assert int(skarn.db.get("hp")) == 12
        assert "BONES OF THE DEEP" not in _text(sim.seen(tam))

        # Crossing 50%: telegraph, whelp, re-arm, berserk — one round.
        await encounter.resolve_round()
        assert int(skarn.db.get("hp")) == 10
        out = _text(sim.seen(tam))
        assert "Skarn slams both fists to the floor. BONES OF THE DEEP - RISE!" in out
        assert skarn.db.get("phase") == 2
        assert int(skarn.db.get("hitprcnt")) == 25       # re-armed
        whelps = [o for o in vault.contents if o.name == "bone whelp"]
        assert len(whelps) == 1
        assert manager.encounter_of(whelps[0]) is encounter
        assert skarn.has_tag("berserk")                  # the kind-tag mirror
        assert skarn.db.get("check_mods", {}).get("berserk") == {"melee": 2}

        # Act three at 25%: telegraph and turtle.
        for _ in range(3):
            await encounter.resolve_round()
        assert skarn.db.get("phase") == 3
        out = _text(sim.seen(tam))
        assert "Cracks spider across Skarn." in out
        assert skarn.db.get("combat_strategy") == [["", "defend"]]

        # The hook fired exactly once per crossing.
        assert out.count("BONES OF THE DEEP") == 0       # not repeated

        # Finish it: last words, and a lootable corpse remains.
        for _ in range(6):
            if int(skarn.db.get("hp")) <= 0:
                break
            await encounter.resolve_round()
        out = _text(sim.seen(tam))
        assert "Skarn comes apart at the seams" in out
        assert any(o.name == "corpse of Skarn the Bonewright"
                   for o in vault.contents)
