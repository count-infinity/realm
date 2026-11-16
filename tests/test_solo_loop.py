"""
MUD_PLAN step 2 acceptance: a character playing alone can be hurt,
recover, be defeated and carry on, without another player's help.

Played on the shipped Midgaard example, booted from its own config.py
(Merc rules, ``PLAYER_DEATH = "respawn"``): a level-1 warrior fights a fido
and is hurt, rests to full, is killed by softcode damage in the next room,
wakes in the Common Square with a corpse left where they fell, walks back
and takes the sword from it.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from realm.core.movement import resolve_exit_destination
from realm.std.combat.maneuver import QueuedAction
from realm.testing import Simulator

MIDGAARD = Path(__file__).resolve().parents[1] / "realm" / "examples" / "midgaard"


@pytest.fixture
def midgaard():
    before = list(sys.path)
    sim = Simulator.from_game(MIDGAARD)
    try:
        yield sim
    finally:
        from realm.features import install_default
        from realm.std.combat.combatant import clear_combatant_cache
        clear_combatant_cache()          # the area keeps its ids across sims
        sim.close()
        sys.modules.pop("rules", None)
        sys.modules.pop("game", None)
        sys.path[:] = before
        install_default()


async def _warrior(sim, name="Brom"):
    """A character made the way connecting makes one."""
    rules = sim.game_system
    player = sim.player(name, location=sim.startup_room)
    rules.apply_baseline(player)
    step = rules.chargen_steps()[0]
    step.handle(player, "warrior")
    rules.finish_chargen(player)
    await rules.outfit_new_character(player, sim.store)
    return player


def _neighbour(room):
    """An exit out of ``room`` and the room beyond it."""
    for exit_obj in room.contents:
        if exit_obj.is_exit:
            beyond = resolve_exit_destination(exit_obj)
            if beyond is not None and beyond is not room:
                return exit_obj, beyond
    raise AssertionError(f"no way out of {room.name}")


def _way_back(room, to):
    for exit_obj in room.contents:
        if exit_obj.is_exit and resolve_exit_destination(exit_obj) is to:
            return exit_obj
    raise AssertionError(f"no way back from {room.name} to {to.name}")


async def test_a_lone_warrior_is_hurt_recovers_dies_and_recovers_the_sword(
        midgaard, monkeypatch):
    sim = midgaard
    await sim.start()
    square = sim.startup_room
    assert square.name == "The Common Square"
    assert sim.world.setting("PLAYER_DEATH") == "respawn"

    brom = await _warrior(sim)
    sword = next(o for o in brom.contents if o.has_tag("wielded"))
    start_hp = brom.db.max_hp

    # --- the fight: every die rolls its maximum, so both sides connect ------
    monkeypatch.setattr("realm.games.merc.ruleset.random.randint", lambda a, b: b)
    fido = next(o for o in square.contents if o.is_npc and "fido" in o.name)
    combat = sim.world.services["combat"]
    encounter = await combat.initiate(fido, brom)
    for _ in range(5):
        if sim.store.get_cached(fido.id) is None:
            break
        encounter.queue(brom, QueuedAction("attack", target_id=fido.id))
        await encounter.resolve_round()
    encounter.end()                         # the beat loop's own ending, run by hand
    await encounter._finish()
    assert sim.store.get_cached(fido.id) is None, "the fido should be dead"
    assert brom.db.xp > 0, "the kill should pay experience"
    full = brom.db.max_hp                             # a level gained would raise it
    assert full >= start_hp
    assert 0 < brom.db.hp < full, "the warrior should be hurt, not down"
    assert not brom.has_tag("in_combat")

    # --- rest to full ---------------------------------------------------------
    await sim.do(brom, "rest")
    assert brom.has_tag("resting")
    vitals = sim.world.services["vitals"]
    for _ in range(20):
        if brom.db.hp >= full:
            break
        await vitals.tick()
    assert brom.db.hp == full
    await sim.do(brom, "stand")

    # --- killed next door, by softcode -----------------------------------------
    out, street = _neighbour(square)
    await sim.do(brom, out.name)
    assert brom.location is street
    trap = sim.obj("a falling portcullis", location=street)
    level = brom.db.level
    brom.db.xp = 900
    penalty = sim.game_system.xp_to_next(level) // 4
    sim.seen(brom)
    await sim.eval(trap, "damage(get('Brom'), 500)")

    corpse = next(o for o in street.contents if o.name == "corpse of Brom")
    assert sword.location is corpse
    assert brom.location is square                    # no home: the start room
    assert brom.db.hp == 1
    assert brom.db.level == level                     # never a level
    assert brom.db.xp == 900 - penalty                # a quarter of a level
    assert any("The Common Square" in line for line in sim.seen(brom))

    # --- walk back and take the sword -------------------------------------------
    back = _way_back(street, square)
    assert back is not None
    moves = brom.db.move
    await sim.do(brom, out.name)
    assert brom.location is street
    assert brom.db.move < moves                       # walking cost movement
    await sim.do(brom, "get sword from corpse")
    assert sword.location is brom


async def test_no_stock_path_leaves_a_lone_player_unable_to_act(midgaard):
    """Knocked out under the default rule, a player comes round on their own."""
    sim = midgaard
    await sim.start()
    brom = await _warrior(sim)
    brom.db.when_spent = "unconscious"
    trap = sim.obj("a falling rock", location=brom.location)
    await sim.eval(trap, "damage(get('Brom'), 500)")
    assert brom.has_tag("unconscious")
    vitals = sim.world.services["vitals"]
    for _ in range(3):
        await vitals.tick()
    assert not brom.has_tag("unconscious")
