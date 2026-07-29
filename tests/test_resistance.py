"""Damage-type resistance: the neutral ``apply_type_resistance`` helper and
MercRuleset's use of it in ``apply_damage``.

Resistance is stored as a portable per-type *multiplier* map (0.0 immune,
0.5 half, 1.5 vuln, or any float like 0.85 = 15% resistance), so it expresses
a continuous knob rather than three fixed Diku tiers. The helper is
ruleset-agnostic; MERC consults it because Diku has no flat DR.
"""

from __future__ import annotations

from realm.combat.combatant import Combatant
from realm.combat.ruleset import DamageType, apply_type_resistance
from realm.combat.system import RulesetRegistry
from realm.testing import Simulator


def _merc():
    RulesetRegistry._ensure_builtins()
    return RulesetRegistry.get("merc")()


# --- the neutral helper -----------------------------------------------------

class TestApplyTypeResistance:

    def test_none_or_empty_passes_through(self):
        dbt = {DamageType.FIRE: 10}
        assert apply_type_resistance(dbt, None) == ({DamageType.FIRE: 10}, 0)
        assert apply_type_resistance(dbt, {}) == ({DamageType.FIRE: 10}, 0)

    def test_immune_zeroes_the_type(self):
        scaled, resisted = apply_type_resistance(
            {DamageType.FIRE: 10}, {"fire": 0.0})
        assert scaled == {DamageType.FIRE: 0}
        assert resisted == 10

    def test_half_resistance(self):
        scaled, resisted = apply_type_resistance(
            {DamageType.COLD: 10}, {"cold": 0.5})
        assert scaled == {DamageType.COLD: 5}
        assert resisted == 5

    def test_continuous_partial_resistance(self):
        # 15% resistance = 0.85 multiplier -> 100 * 0.85 = 85 taken, 15 gone.
        scaled, resisted = apply_type_resistance(
            {DamageType.ACID: 100}, {"acid": 0.85})
        assert scaled == {DamageType.ACID: 85}
        assert resisted == 15
        # 77% resistance = 0.23 multiplier -> 23 taken.
        scaled, _ = apply_type_resistance(
            {DamageType.ACID: 100}, {"acid": 0.23})
        assert scaled == {DamageType.ACID: 23}

    def test_vulnerability_adds_damage(self):
        scaled, resisted = apply_type_resistance(
            {DamageType.POISON: 10}, {"poison": 1.5})
        assert scaled == {DamageType.POISON: 15}
        assert resisted == -5              # net: damage was added, not removed

    def test_true_damage_bypasses_the_map(self):
        scaled, resisted = apply_type_resistance(
            {DamageType.TRUE: 10}, {"true": 0.0, "fire": 0.0})
        assert scaled == {DamageType.TRUE: 10}
        assert resisted == 0

    def test_untyped_component_is_left_alone(self):
        # A type with no entry keeps its full value.
        scaled, resisted = apply_type_resistance(
            {DamageType.FIRE: 10, DamageType.COLD: 10}, {"fire": 0.0})
        assert scaled == {DamageType.FIRE: 0, DamageType.COLD: 10}
        assert resisted == 10


# --- MercRuleset.apply_damage -----------------------------------------------

class TestMercApplyDamage:

    def _target(self, sim, room, **attrs):
        obj = sim.obj("dummy", location=room)
        obj.db.set("hp", 100)
        for k, v in attrs.items():
            obj.db.set(k, v)
        return Combatant(obj)

    def _hit(self, dtype, amount):
        from realm.combat.ruleset import DamageResult
        return DamageResult(total=amount, damage_by_type={dtype: amount})

    def test_no_resistances_is_full_damage(self):
        sim = Simulator()
        try:
            room = sim.room("Arena")
            tgt = self._target(sim, room)
            dealt = _merc().apply_damage(tgt, self._hit(DamageType.FIRE, 20))
            assert dealt == 20
            assert tgt.get_stat("hp") == 80
        finally:
            sim.close()

    def test_immune_target_takes_nothing(self):
        sim = Simulator()
        try:
            room = sim.room("Arena")
            tgt = self._target(sim, room, resistances={"fire": 0.0})
            dmg = self._hit(DamageType.FIRE, 20)
            dealt = _merc().apply_damage(tgt, dmg)
            assert dealt == 0
            assert tgt.get_stat("hp") == 100
            assert dmg.resisted == 20          # recorded for logging/messages
        finally:
            sim.close()

    def test_partial_resistance_scales_hp_loss(self):
        sim = Simulator()
        try:
            room = sim.room("Arena")
            tgt = self._target(sim, room, resistances={"cold": 0.85})
            dealt = _merc().apply_damage(tgt, self._hit(DamageType.COLD, 100))
            assert dealt == 85
            assert tgt.get_stat("hp") == 15
        finally:
            sim.close()

    def test_vulnerable_target_takes_extra(self):
        sim = Simulator()
        try:
            room = sim.room("Arena")
            tgt = self._target(sim, room, resistances={"poison": 1.5})
            dealt = _merc().apply_damage(tgt, self._hit(DamageType.POISON, 20))
            assert dealt == 30
            assert tgt.get_stat("hp") == 70
        finally:
            sim.close()

    def test_wrong_type_is_unaffected(self):
        # Fire-immune target still takes full cold damage.
        sim = Simulator()
        try:
            room = sim.room("Arena")
            tgt = self._target(sim, room, resistances={"fire": 0.0})
            dealt = _merc().apply_damage(tgt, self._hit(DamageType.COLD, 20))
            assert dealt == 20
        finally:
            sim.close()
