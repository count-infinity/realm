"""
MUD_PLAN step 3 acceptance, on the shipped Midgaard example: a new
character buys armour at the Armoury, wears it, sees it under
``equipment``, is hurt, buys and quaffs a cure light potion at the
apothecary, and watches the prompt follow its hit points.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from realm.testing import Simulator

MIDGAARD = Path(__file__).resolve().parents[1] / "realm" / "examples" / "midgaard"
ARMOURY, APOTHECARY = "rom_3020", "rom_3056"


@pytest.fixture
def midgaard():
    before = list(sys.path)
    sim = Simulator.from_game(MIDGAARD)
    try:
        yield sim
    finally:
        from realm.features import install_default
        from realm.std.combat.combatant import clear_combatant_cache
        clear_combatant_cache()
        sim.close()
        sys.modules.pop("rules", None)
        sys.modules.pop("game", None)
        sys.path[:] = before
        install_default()


async def test_buy_wear_see_it_quaff_and_watch_the_prompt(midgaard, monkeypatch):
    sim = midgaard
    await sim.start()
    rules = sim.game_system
    brom = sim.player("Brom", location=sim.startup_room)
    rules.apply_baseline(brom)
    rules.chargen_steps()[0].handle(brom, "warrior")
    rules.finish_chargen(brom)
    await rules.outfit_new_character(brom, sim.store)
    brom.db.credits = 5000
    full = brom.db.max_hp
    assert sim.prompt(brom) == f"<{full}hp 100m 100mv> "

    # --- buy armour and wear it --------------------------------------------------
    brom.location = sim.store.get_cached(ARMOURY)
    await sim.do(brom, "buy jerkin")
    jerkin = next(o for o in brom.contents if "jerkin" in o.name)
    await sim.do(brom, "wear jerkin")
    assert jerkin.has_tag("worn")
    sim.seen(brom)
    await sim.do(brom, "equipment")
    sheet = "\n".join(sim.seen(brom)).splitlines()
    body = next(line for line in sheet if "<body>" in line)
    assert jerkin.name in body
    assert any("<wielded>" in line and "sword" in line for line in sheet)
    await sim.do(brom, "inventory")
    assert not any(jerkin.name in line for line in sim.seen(brom))

    # --- hurt, then a potion ---------------------------------------------------------
    trap = sim.obj("a dart trap", location=brom.location)
    await sim.eval(trap, "damage(get('Brom'), 6)")
    hurt = brom.db.hp
    assert hurt < full
    assert sim.prompt(brom).startswith(f"<{hurt}hp ")

    brom.location = sim.store.get_cached(APOTHECARY)
    await sim.do(brom, "buy cure light")
    potion = next(o for o in brom.contents if o.db.spells == ["cure light"])
    monkeypatch.setattr("realm.std.abilities.abilities.random.randint", lambda a, b: b)
    await sim.do(brom, f"quaff {potion.name.split()[-1]}")
    assert sim.store.get_cached(potion.id) is None
    assert brom.db.hp > hurt
    assert sim.prompt(brom).startswith(f"<{brom.db.hp}hp ")
