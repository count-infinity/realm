"""The crime core (systems/crime.py): wanted flags + peacekeeper guards.

The Diku-modernized minimal model: a player who assaults/murders another
player is flagged wanted (a timed tag + heat); attacking someone already
wanted is free (self-enforcing); peacekeeper guards attack the wanted;
death or expiry clears it. Detection is passive on the combat events.
"""

from __future__ import annotations

import pytest

from realm.combat.behaviors import PeacekeeperBehavior
from realm.combat.manager import CombatManager, set_combat_manager
from realm.combat.rulesets.merc import MercRuleset
from realm.combat.system import CombatSystem
from realm.core.propagation import Action
from realm.systems import MercSystem, set_game_system
from realm.systems.crime import (
    clear_wanted,
    crime_observer,
    flag_wanted,
    is_wanted,
    wanted_heat,
)
from realm.testing import Simulator


def _dmg(actor, target, amount=5):
    return Action(actor=actor, target=target,
                  action_type="combat:on_damage", extra={"damage": amount})


def _death(killer, victim):
    return Action(actor=killer, target=victim,
                  action_type="combat:on_death",
                  extra={"killer": killer.name if killer else None})


# --- detection --------------------------------------------------------------

@pytest.mark.asyncio
class TestDetection:

    async def test_assaulting_a_player_flags_the_aggressor(self):
        sim = Simulator()
        try:
            room = sim.room("Street")
            alice = sim.player("Alice", location=room)
            bob = sim.player("Bob", location=room)
            await crime_observer(_dmg(alice, bob))
            assert is_wanted(alice) and "wanted:assault" in alice.tags
            assert not is_wanted(bob)                   # the victim is clean
            assert any(b.behavior_id == "wanted"
                       for b in alice.get_behaviors())  # decay timer attached
        finally:
            sim.close()

    async def test_hitting_an_outlaw_is_free(self):
        sim = Simulator()
        try:
            room = sim.room("Street")
            alice = sim.player("Alice", location=room)
            bob = sim.player("Bob", location=room)
            flag_wanted(bob, "assault", 1)              # bob is already wanted
            await crime_observer(_dmg(alice, bob))
            assert not is_wanted(alice)                 # self-enforcing rule
        finally:
            sim.close()

    async def test_attacking_a_mob_is_not_a_crime(self):
        sim = Simulator()
        try:
            room = sim.room("Wilds")
            hunter = sim.player("Hunter", location=room)
            deer = sim.obj("a deer", location=room, tags=["npc"])
            await crime_observer(_dmg(hunter, deer))
            assert not is_wanted(hunter)
        finally:
            sim.close()

    async def test_murder_flags_higher_than_assault(self):
        sim = Simulator()
        try:
            room = sim.room("Alley")
            killer = sim.player("Killer", location=room)
            victim = sim.player("Victim", location=room)
            await crime_observer(_death(killer, victim))
            assert "wanted:murder" in killer.tags
            assert wanted_heat(killer) >= 5             # murder heat
        finally:
            sim.close()

    async def test_death_pardons_the_outlaw(self):
        sim = Simulator()
        try:
            room = sim.room("Alley")
            outlaw = sim.player("Outlaw", location=room)
            hunter = sim.player("Hunter", location=room)
            flag_wanted(outlaw, "murder", 5)
            # A bounty hunter kills the outlaw: outlaw is pardoned by death,
            # and killing a wanted target does not make the hunter a murderer.
            await crime_observer(_death(hunter, outlaw))
            assert not is_wanted(outlaw)
            assert not is_wanted(hunter)
        finally:
            sim.close()


# --- decay + peacekeeper ----------------------------------------------------

@pytest.mark.asyncio
class TestConsequences:

    async def test_wanted_status_expires_clean(self):
        sim = Simulator()
        try:
            room = sim.room("Street")
            crook = sim.player("Crook", location=room)
            flag_wanted(crook, "assault", 1)
            timer = next(b for b in crook.get_behaviors()
                         if b.behavior_id == "wanted")
            await timer._expire(crook)                  # sentence served
            assert not is_wanted(crook)
            assert wanted_heat(crook) == 0
            assert not any(b.behavior_id == "wanted"
                           for b in crook.get_behaviors())
        finally:
            sim.close()

    async def test_a_peacekeeper_arrests_the_wanted(self):
        sim = Simulator()
        try:
            set_game_system(MercSystem())
            mgr = CombatManager(CombatSystem(ruleset=MercRuleset()))
            set_combat_manager(mgr)
            room = sim.room("Market")
            guard = sim.obj("a cityguard", location=room, tags=["npc"])
            guard.db.set("hp", 30)
            guard.db.set("max_hp", 30)
            outlaw = sim.player("Outlaw", location=room)
            outlaw.db.set("hp", 20)
            innocent = sim.player("Innocent", location=room)
            innocent.db.set("hp", 20)
            flag_wanted(outlaw, "murder", 5)
            await PeacekeeperBehavior().tick(guard, 4.0)
            assert guard.has_tag("in_combat")
            assert outlaw.has_tag("in_combat")          # the criminal
            assert not innocent.has_tag("in_combat")    # not the bystander
        finally:
            set_combat_manager(None)
            set_game_system(None)
            sim.close()

    async def test_clear_wanted_removes_everything(self):
        sim = Simulator()
        try:
            room = sim.room("Street")
            crook = sim.player("Crook", location=room)
            flag_wanted(crook, "assault", 3)
            clear_wanted(crook)
            assert not is_wanted(crook) and wanted_heat(crook) == 0
            assert not any(b.behavior_id == "wanted"
                           for b in crook.get_behaviors())
        finally:
            sim.close()
