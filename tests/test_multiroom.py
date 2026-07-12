"""
Stage C of the rules kernel: multiroom actions via a targeting vocabulary.

An action can reach BEYOND the actor's room (a scry, a remote cast, a zone
alarm) while still riding the two-pass engine — so a ward in the origin
room OR the destination can veto, and occupants of the far room witness and
react. Exercised through the softcode ``act(target, msg, targeting=…)``
surface, end-to-end via the Simulator.
"""

from __future__ import annotations

import pytest

from realm.core.behaviors import Behavior
from realm.testing import Simulator


class NoMagicWard(Behavior):
    """A room ward that vetoes magical actions in the check pass."""

    name = "no_magic_ward"

    async def on_check(self, obj, action):
        if action.action_type == "event:scry" or action.has_tag("magic"):
            action.block("The air here smothers magic.")


def scry(sim, caster, target, msg="A scrying eye blinks open."):
    return sim.eval(
        caster,
        f"act('#{target.id}', '{msg}', targeting='remote', "
        f"action_type='event:scry')",
    )


@pytest.fixture
def world():
    sim = Simulator()
    study = sim.room("Study")
    vault = sim.room("Vault")
    mage = sim.player("Mage", location=study)
    orb = sim.obj("Orb", location=vault)
    witness = sim.player("Guard", location=vault)
    try:
        yield sim, study, vault, mage, orb, witness
    finally:
        sim.close()


@pytest.mark.asyncio
class TestRemoteAction:

    async def test_scry_reaches_the_remote_room(self, world):
        sim, study, vault, mage, orb, witness = world
        _res, err = await scry(sim, mage, orb)
        assert err is None
        assert any("scrying eye" in m for m in sim.seen(witness))

    async def test_origin_ward_blocks_the_scry(self, world):
        sim, study, vault, mage, orb, witness = world
        study.add_behavior(NoMagicWard())          # ward in the CASTER's room
        await scry(sim, mage, orb)
        assert sim.seen(witness) == []             # never left the study

    async def test_remote_ward_blocks_the_scry(self, world):
        sim, study, vault, mage, orb, witness = world
        vault.add_behavior(NoMagicWard())          # ward in the DESTINATION
        await scry(sim, mage, orb)
        assert sim.seen(witness) == []             # smothered on arrival

    async def test_ward_is_selective(self, world):
        # A non-magical remote action passes a NO_MAGIC ward untouched.
        sim, study, vault, mage, orb, witness = world
        vault.add_behavior(NoMagicWard())
        await sim.eval(
            mage,
            f"act('#{orb.id}', 'A courier drone hums in.', "
            f"targeting='remote', action_type='event:courier')",
        )
        assert any("courier drone" in m for m in sim.seen(witness))

    async def test_caster_stays_in_own_room(self, world):
        # The scry doesn't teleport the caster — they're still in the study;
        # only the message travels.
        sim, study, vault, mage, orb, witness = world
        await scry(sim, mage, orb)
        assert mage.location is study

    async def test_reach_lock_denies_the_scry(self, world):
        # The AUTHORITY gate (not a hoped-for ward): a room can lock out
        # remote reach. Safe by default is the lock, not the victim's ward.
        sim, study, vault, mage, orb, witness = world
        vault.locks["reach"] = "False"
        await scry(sim, mage, orb)
        assert sim.seen(witness) == []             # denied at the gate


@pytest.mark.asyncio
async def test_zone_destination_ward_vetoes_the_broadcast():
    """A ward in a NON-origin zone room gets the destination two-pass and
    can veto — proving zone reaches destinations through the engine, not a
    bare message fanout."""
    sim = Simulator()
    try:
        hub = sim.room("Hub")
        hub.add_tag("zone:tower")
        wing = sim.room("Wing")
        wing.add_tag("zone:tower")
        wing.add_behavior(NoMagicWard())           # ward in a far zone room
        klaxon = sim.obj("Klaxon", location=hub)
        guard = sim.player("Guard", location=wing)
        await sim.eval(
            klaxon,
            f"act('#{klaxon.id}', 'ALERT', targeting='zone', "
            f"action_type='event:scry')",           # tagged so the ward matches
        )
        assert sim.seen(guard) == []               # the far ward vetoed it
    finally:
        sim.close()


@pytest.mark.asyncio
async def test_zone_broadcast_reaches_every_room_in_the_zone():
    """targeting='zone' fans out to every room carrying the same zone tag —
    a wing-wide alarm — with the origin ward still able to veto."""
    sim = Simulator()
    try:
        hub = sim.room("Hub", )
        hub.add_tag("zone:tower")
        wing = sim.room("Wing")
        wing.add_tag("zone:tower")
        klaxon = sim.obj("Klaxon", location=hub)
        guard_here = sim.player("GuardA", location=hub)
        guard_there = sim.player("GuardB", location=wing)

        await sim.eval(
            klaxon,
            f"act('#{klaxon.id}', 'INTRUDER ALERT', targeting='zone', "
            f"action_type='event:alarm')",
        )
        # Both rooms in the zone hear it.
        assert any("INTRUDER" in m for m in sim.seen(guard_there))
        assert any("INTRUDER" in m for m in sim.seen(guard_here))
    finally:
        sim.close()
