"""
MUD_PLAN step 4 acceptance, on the shipped Midgaard example: a level-1
warrior can ``kick`` and ``bash``, a thief can ``backstab`` an unaware
fido, and ``abilities`` lists exactly what each class can use.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from realm.testing import Simulator

MIDGAARD = Path(__file__).resolve().parents[1] / "realm" / "examples" / "midgaard"
SKILLS = {"kick", "bash", "backstab", "rescue", "disarm", "trip"}


@pytest.fixture
async def midgaard(monkeypatch):
    before = list(sys.path)
    sim = Simulator.from_game(MIDGAARD)
    await sim.start()
    from realm.std.rules.checks import checks
    checks().resolver = lambda actor, skill, mod=0, **kw: SimpleNamespace(
        success=True, margin=5, critical=False, roll=10, effective=50, skill=skill)
    monkeypatch.setattr("realm.std.abilities.abilities.random.randint", lambda a, b: b)
    try:
        yield sim
    finally:
        from realm.features import install_default
        from realm.std.combat.combatant import clear_combatant_cache
        sim.world.services["combat"].stop_all()
        clear_combatant_cache()
        sim.close()
        sys.modules.pop("rules", None)
        sys.modules.pop("game", None)
        sys.path[:] = before
        install_default()


async def _made(sim, name, cls):
    rules = sim.game_system
    player = sim.player(name, location=sim.startup_room)
    rules.apply_baseline(player)
    rules.chargen_steps()[0].handle(player, cls)
    rules.finish_chargen(player)
    await rules.outfit_new_character(player, sim.store)
    return player


def _fido(sim):
    return next(o for o in sim.startup_room.contents if o.is_npc and "fido" in o.name)


async def test_a_warrior_kicks_and_bashes_a_fido(midgaard):
    sim = midgaard
    brom = await _made(sim, "Brom", "warrior")
    fido = _fido(sim)
    start = fido.db.hp
    await sim.do(brom, "kick fido")
    after_kick = fido.db.hp
    assert after_kick < start
    await sim.do(brom, "bash fido")
    assert sim.store.get_cached(fido.id) is None or fido.db.hp < after_kick
    assert sim.store.get_cached(fido.id) is None or fido.has_tag("stunned")


async def test_a_thief_backstabs_an_unaware_fido(midgaard):
    sim = midgaard
    nim = await _made(sim, "Nim", "thief")
    fido = _fido(sim)
    assert not fido.has_tag("in_combat")
    await sim.do(nim, "backstab fido")
    assert sim.store.get_cached(fido.id) is None or fido.db.hp < 8


@pytest.mark.parametrize("cls,expected", [
    ("warrior", {"kick", "bash", "rescue"}),
    ("barbarian", {"kick"}),
    ("thief", {"backstab", "trip"}),
    ("cleric", set()),
    ("mage", set()),
])
async def test_abilities_lists_exactly_what_each_class_can_use(midgaard, cls, expected):
    sim = midgaard
    pat = await _made(sim, "Pat", cls)
    await sim.do(pat, "abilities")
    lines = "\n".join(sim.seen(pat)).splitlines()
    listed = {line.split()[0] for line in lines if line.startswith("  ")}
    assert listed & SKILLS == expected
