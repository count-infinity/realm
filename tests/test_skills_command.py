"""
MUD_PLAN step 3.2: the ``skills`` command lists a character's trained
skills, grouped by the skill definition's ``group`` when it has one, in the
game system's own terms. ``score`` no longer lists them.
"""

from __future__ import annotations

import pytest

from realm.testing import Simulator

SYSTEMS = {
    "gurps": ("realm.games.gurps.system.GurpsSystem", "14"),
    "d20": ("realm.games.d20.system.D20System", "+14"),
    "merc": ("realm.games.merc.system.MercSystem", "14%"),
}


@pytest.mark.parametrize("system", sorted(SYSTEMS))
async def test_skills_lists_trained_skills_in_the_systems_terms(system):
    path, shown = SYSTEMS[system]
    sim = Simulator(game_system=path)
    try:
        room = sim.room("Hall")
        pat = sim.player("Pat", location=room, skill_stealth=14, skill_melee=9)
        await sim.do(pat, "skills")
        lines = "\n".join(sim.seen(pat)).splitlines()
        stealth = next(line for line in lines if "stealth" in line)
        assert shown in stealth
        assert any("melee" in line for line in lines)
        await sim.do(pat, "sk")
        assert any("stealth" in line for line in sim.seen(pat))
        await sim.do(pat, "score")
        assert not any("stealth" in line for line in sim.seen(pat))
    finally:
        sim.close()


async def test_skills_group_by_their_definition():
    from realm.std.rules import define_skill
    sim = Simulator()
    try:
        sim.add(define_skill("lockpicking", "dexterity", -5, group="Thievery"))
        sim.add(define_skill("stealth", "dexterity", -5, group="Thievery"))
        room = sim.room("Hall")
        pat = sim.player("Pat", location=room, skill_lockpicking=12, skill_stealth=11,
                         skill_cooking=10)
        await sim.do(pat, "skills")
        lines = "\n".join(sim.seen(pat)).splitlines()
        thievery = next(i for i, line in enumerate(lines) if "Thievery" in line)
        assert any("lockpicking" in line for line in lines[thievery:])
        cooking = next(i for i, line in enumerate(lines) if "cooking" in line)
        assert cooking < thievery                  # ungrouped skills come first
    finally:
        sim.close()


async def test_no_skills_says_so():
    sim = Simulator()
    try:
        pat = sim.player("Pat", location=sim.room("Hall"))
        await sim.do(pat, "skills")
        assert "You have no trained skills." in sim.seen(pat)
    finally:
        sim.close()
