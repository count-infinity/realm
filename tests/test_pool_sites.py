"""
Characterization tests for hp write sites the suite did not pin
(KERNEL_PLAN 8.2: each site was replaced by ``raise`` and the suite stayed
green). They hold the sites' behavior while they move onto pools.
"""

from __future__ import annotations

import pytest

from realm.testing import Simulator


@pytest.mark.asyncio
async def test_a_healer_tends_a_wounded_ally():
    from realm.core.behaviors import BehaviorRegistry
    with Simulator() as sim:
        room = sim.room("Infirmary")
        medic = sim.obj("medic", location=room, tags=["npc"])
        patient = sim.player("Pat", location=room, hp=2, max_hp=10)
        healthy = sim.player("Hal", location=room, hp=9, max_hp=10)
        healer = BehaviorRegistry.create("healer", heal_amount=5, cooldown=2)
        medic.add_behavior(healer)

        await healer.tick(medic, 1.0)
        assert patient.db.hp == 7 and healthy.db.hp == 9
        assert any("tends your wounds (+5 HP)" in line for line in sim.seen(patient))
        assert medic.db.healer_wait == 2

        patient.db.hp = 4
        await healer.tick(medic, 1.0)           # cooling down
        assert patient.db.hp == 4
        medic.db.healer_wait = 0
        await healer.tick(medic, 1.0)
        assert patient.db.hp == 9

        patient.db.hp, patient.db.max_hp = 2, 6  # capped at max
        medic.db.healer_wait = 0
        await healer.tick(medic, 1.0)
        assert patient.db.hp == 6


@pytest.mark.asyncio
async def test_typed_damage_over_time_without_combat():
    """With no ``combat`` (no damage service) typed damage lands untyped;
    a player brought down falls unconscious."""
    from realm.std.effects.behaviors import DamageOverTimeBehavior
    with Simulator(features=["rules", "effects"]) as sim:
        room = sim.room("Bog")
        victim = sim.player("Vic", location=room, hp=10, max_hp=10)
        dot = DamageOverTimeBehavior(kind="poisoned", damage=3, damage_type="poison")
        victim.add_behavior(dot)

        await dot.pulse(victim)
        assert victim.db.hp == 7
        victim.db.hp = 2
        await dot.pulse(victim)
        assert int(victim.db.hp) <= 0
        assert victim.has_tag("unconscious")
