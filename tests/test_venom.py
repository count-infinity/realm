"""Poison-on-hit: the `venomous` behavior + poison DoT through resistances.

Confirmed against CoffeeMud's design (Poisons/Poison.java): a lightweight
"venomous" reaction on the attacker fires on its own damage event and
applies a poison damage-over-time whose ticks route through the normal
damage/resistance path, so a poison-immune target is unaffected (immunity
vetoes at application).
"""

from __future__ import annotations

import pytest

from realm.behaviors.effects import DamageOverTimeBehavior
from realm.combat.behaviors import VenomousBehavior
from realm.core.propagation import Action
from realm.systems import MercSystem, set_game_system
from realm.testing import Simulator


def _hit(attacker, target, amount=5):
    return Action(actor=attacker, target=target,
                  action_type="combat:on_damage",
                  extra={"damage": amount})


# --- DoT routes through resistances -----------------------------------------

@pytest.mark.asyncio
class TestPoisonDoT:

    async def test_poison_tick_is_resisted(self):
        sim = Simulator()
        try:
            room = sim.room("Swamp")
            victim = sim.obj("victim", location=room)
            victim.db.set("hp", 100)
            victim.db.set("max_hp", 100)
            victim.db.set("resistances", {"poison": 0.5})   # half
            dot = DamageOverTimeBehavior(kind="poisoned", damage=10,
                                         damage_type="poison", interval=1)
            victim.add_behavior(dot)
            await dot.pulse(victim)
            assert victim.db.get("hp") == 95                # 10 -> 5 resisted
        finally:
            sim.close()

    async def test_immune_target_takes_no_poison(self):
        sim = Simulator()
        try:
            room = sim.room("Swamp")
            victim = sim.obj("golem", location=room)
            victim.db.set("hp", 100)
            victim.db.set("resistances", {"poison": 0.0})   # immune
            dot = DamageOverTimeBehavior(kind="poisoned", damage=10,
                                         damage_type="poison")
            victim.add_behavior(dot)
            await dot.pulse(victim)
            assert victim.db.get("hp") == 100               # nothing
        finally:
            sim.close()

    async def test_untyped_dot_is_raw_hp_unchanged(self):
        # No damage_type: the classic raw-HP bleed, unaffected by resistances.
        sim = Simulator()
        try:
            room = sim.room("Field")
            victim = sim.obj("victim", location=room)
            victim.db.set("hp", 50)
            victim.db.set("resistances", {"poison": 0.0})
            dot = DamageOverTimeBehavior(kind="bleeding", damage=3)
            victim.add_behavior(dot)
            await dot.pulse(victim)
            assert victim.db.get("hp") == 47                # raw
        finally:
            sim.close()


# --- venomous applies poison on hit -----------------------------------------

@pytest.mark.asyncio
class TestVenomous:

    async def test_a_landed_hit_poisons(self, monkeypatch):
        sim = Simulator()
        try:
            set_game_system(MercSystem())
            room = sim.room("Nest")
            snake = sim.obj("a viper", location=room, tags=["npc"])
            snake.db.set("level", 5)
            victim = sim.player("Grog", location=room)
            victim.db.set("hp", 30)
            monkeypatch.setattr("realm.combat.behaviors.random.random",
                                lambda: 0.0)                # always envenom
            monkeypatch.setattr(MercSystem, "saving_throw",
                                lambda self, t, level: False)  # no save
            venom = VenomousBehavior()
            await venom.on_react(snake, _hit(snake, victim))
            poisons = [b for b in victim.get_behaviors()
                       if getattr(b, "kind", None) == "poisoned"]
            assert len(poisons) == 1
            assert poisons[0].get_param("damage_type") == "poison"
        finally:
            set_game_system(None)
            sim.close()

    async def test_a_save_fights_off_the_venom(self, monkeypatch):
        sim = Simulator()
        try:
            set_game_system(MercSystem())
            room = sim.room("Nest")
            snake = sim.obj("a viper", location=room, tags=["npc"])
            victim = sim.player("Grog", location=room)
            monkeypatch.setattr("realm.combat.behaviors.random.random",
                                lambda: 0.0)
            monkeypatch.setattr(MercSystem, "saving_throw",
                                lambda self, t, level: True)   # saved
            await VenomousBehavior().on_react(snake, _hit(snake, victim))
            assert not any(getattr(b, "kind", None) == "poisoned"
                           for b in victim.get_behaviors())
        finally:
            set_game_system(None)
            sim.close()

    async def test_poison_immune_target_is_not_poisoned(self, monkeypatch):
        # Immunity vetoes at application: no dead poison effect attached.
        sim = Simulator()
        try:
            set_game_system(MercSystem())
            room = sim.room("Nest")
            snake = sim.obj("a viper", location=room, tags=["npc"])
            golem = sim.obj("iron golem", location=room, tags=["npc"])
            golem.db.set("resistances", {"poison": 0.0})
            monkeypatch.setattr("realm.combat.behaviors.random.random",
                                lambda: 0.0)
            await VenomousBehavior().on_react(snake, _hit(snake, golem))
            assert not any(getattr(b, "kind", None) == "poisoned"
                           for b in golem.get_behaviors())
        finally:
            set_game_system(None)
            sim.close()

    async def test_a_miss_does_not_poison(self, monkeypatch):
        sim = Simulator()
        try:
            room = sim.room("Nest")
            snake = sim.obj("a viper", location=room, tags=["npc"])
            victim = sim.player("Grog", location=room)
            monkeypatch.setattr("realm.combat.behaviors.random.random",
                                lambda: 0.0)
            # damage 0 = no blow landed.
            await VenomousBehavior().on_react(snake, _hit(snake, victim, 0))
            assert not any(getattr(b, "kind", None) == "poisoned"
                           for b in victim.get_behaviors())
        finally:
            sim.close()
