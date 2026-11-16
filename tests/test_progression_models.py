"""
MUD_PLAN step 5 acceptance: one Merc game runs every progression model at
once (melee by use, lockpicking by practice then use, a custom herbalism
by idle study), and a GURPS game keeps buying skills with points.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core.behaviors import BehaviorRegistry
from realm.std.rules.checks import check, checks, skill_level
from realm.std.rules.definitions import define_skill
from realm.testing import Simulator

MERC = "realm.games.merc.system.MercSystem"


def _pass_every_check():
    checks().resolver = lambda actor, skill, mod=0, **kw: SimpleNamespace(
        success=True, margin=5, roll=10, effective=50, skill=skill)


async def _made(sim, name, cls, room, **attrs):
    rules = sim.game_system
    player = sim.player(name, location=room)
    rules.apply_baseline(player)
    rules.chargen_steps()[0].handle(player, cls)
    rules.finish_chargen(player)
    for key, value in attrs.items():
        player.db.set(key, value)
    return player


@pytest.fixture
def clock(monkeypatch):
    now = [3_000_000.0]
    monkeypatch.setattr("realm.std.rules.progression.now", lambda: now[0])
    return now


async def test_one_merc_game_runs_every_model(clock, monkeypatch):
    sim = Simulator(game_system=MERC)
    try:
        room = sim.room("Guild Hall")
        herbalism = define_skill("herbalism", "wisdom", -10)
        herbalism.db.progression = "idle"
        sim.add(herbalism)
        master = sim.obj("the guildmaster", location=room, tags=["npc"])
        master.add_behavior(BehaviorRegistry.create("trainer", teaches="class"))

        # melee, by use: swings raise it.
        brom = await _made(sim, "Brom", "warrior", room)
        monkeypatch.setattr("realm.games.merc.ruleset.random.randint", lambda a, b: 15)
        dummy = sim.obj("a straw dummy", location=room, tags=["npc"], hp=10**6,
                        max_hp=10**6, thac0=20, armor_class=10)
        start = brom.db.skill_melee
        system = sim.world.services["combat"].combat_system
        for _ in range(80):
            await system.attack(brom, dummy)
        assert brom.db.skill_melee > start

        # lockpicking, by practice to the floor, then by use past it.
        nim = await _made(sim, "Nim", "thief", room, practices=20, skill_lockpicking=5)
        floor = sim.game_system.skill_cap(nim, "lockpicking") // 3
        for _ in range(20):
            await sim.do(nim, "practice lockpicking")
        assert nim.db.skill_lockpicking == floor
        _pass_every_check()
        for _ in range(100):
            check(nim, "lockpicking")
        assert nim.db.skill_lockpicking > floor

        # herbalism, by idle study: time away raises it.
        tamsin = await _made(sim, "Tamsin", "cleric", room)
        before = skill_level(tamsin, "herbalism")
        await sim.do(tamsin, "study herbalism")
        clock[0] += 6 * 3600
        await sim.do(tamsin, "skills")
        assert tamsin.db.skill_herbalism > before
        # ...and it does not learn by use.
        level = tamsin.db.skill_herbalism
        for _ in range(50):
            check(tamsin, "herbalism")
        clock[0] += 0
        assert tamsin.db.skill_herbalism == level
    finally:
        sim.world.services["combat"].stop_all()
        sim.close()


async def test_a_gurps_game_keeps_buying_skills_with_points():
    sim = Simulator()
    try:
        room = sim.room("Lab")
        pat = sim.player("Pat", location=room, skill_stealth=12, character_points=8)
        _pass_every_check()
        for _ in range(100):
            check(pat, "stealth")
        assert pat.db.skill_stealth == 12
        await sim.do(pat, "improve stealth")
        assert pat.db.skill_stealth == 13 and pat.db.character_points == 4
    finally:
        sim.close()
