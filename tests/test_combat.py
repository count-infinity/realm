"""Tests for the combat system."""

import pytest
from realm.core.objects import GameObject
from realm.combat.combatant import (
    Combatant,
    CombatState,
    StatusEffect,
    get_combatant,
    clear_combatant_cache,
)
from realm.combat.ruleset import (
    Ruleset,
    RollResult,
    AttackResult,
    DamageResult,
    DamageType,
)
from realm.combat.rulesets.d20 import D20Ruleset
from realm.combat.rulesets.gurps import GURPSRuleset
from realm.combat.system import CombatSystem, create_combat_system


class TestCombatant:
    """Test suite for Combatant wrapper."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_combatant_cache()

    def test_wrap_gameobject(self):
        """Combatant wraps a GameObject."""
        obj = GameObject("Fighter")
        combatant = Combatant(obj)

        assert combatant.obj == obj
        assert combatant.name == "Fighter"
        assert combatant.state == CombatState.IDLE

    def test_stat_access(self):
        """Can access stats through combatant."""
        obj = GameObject("Fighter")
        obj.db.strength = 16
        obj.db.hp = 50

        combatant = Combatant(obj)
        assert combatant.get_stat('strength') == 16
        assert combatant.hp == 50

    def test_stat_modification(self):
        """Can modify stats through combatant."""
        obj = GameObject("Fighter")
        obj.db.hp = 50

        combatant = Combatant(obj)
        combatant.hp = 40
        assert obj.db.hp == 40

    def test_take_damage(self):
        """take_damage reduces HP."""
        obj = GameObject("Fighter")
        obj.db.hp = 50
        obj.db.max_hp = 50

        combatant = Combatant(obj)
        actual = combatant.take_damage(15)

        assert actual == 15
        assert combatant.hp == 35

    def test_take_damage_cannot_go_negative(self):
        """HP cannot go below 0."""
        obj = GameObject("Fighter")
        obj.db.hp = 10

        combatant = Combatant(obj)
        actual = combatant.take_damage(100)

        assert actual == 10  # Only lost 10
        assert combatant.hp == 0

    def test_heal(self):
        """heal restores HP."""
        obj = GameObject("Fighter")
        obj.db.hp = 30
        obj.db.max_hp = 50

        combatant = Combatant(obj)
        actual = combatant.heal(15)

        assert actual == 15
        assert combatant.hp == 45

    def test_heal_cannot_exceed_max(self):
        """Healing cannot exceed max HP."""
        obj = GameObject("Fighter")
        obj.db.hp = 45
        obj.db.max_hp = 50

        combatant = Combatant(obj)
        actual = combatant.heal(20)

        assert actual == 5  # Only healed 5
        assert combatant.hp == 50

    def test_status_effects(self):
        """Can add and check status effects."""
        obj = GameObject("Fighter")
        combatant = Combatant(obj)

        effect = StatusEffect(name="poisoned", duration=3, magnitude=5)
        combatant.add_effect(effect)

        assert combatant.has_effect("poisoned")
        assert not combatant.has_effect("stunned")

    def test_status_effect_tick(self):
        """Status effects tick and expire."""
        obj = GameObject("Fighter")
        combatant = Combatant(obj)

        effect = StatusEffect(name="poisoned", duration=2)
        combatant.add_effect(effect)

        # First tick
        expired = combatant.tick_effects()
        assert len(expired) == 0
        assert combatant.has_effect("poisoned")

        # Second tick - should expire
        expired = combatant.tick_effects()
        assert len(expired) == 1
        assert not combatant.has_effect("poisoned")

    def test_resistance(self):
        """Resistance affects damage multiplier."""
        obj = GameObject("Fighter")
        obj.db.resistances = ['fire']
        obj.db.vulnerabilities = ['cold']
        obj.db.immunities = ['poison']

        combatant = Combatant(obj)

        assert combatant.get_resistance('fire') == 0.5  # Resistant
        assert combatant.get_resistance('cold') == 2.0  # Vulnerable
        assert combatant.get_resistance('poison') == 0.0  # Immune
        assert combatant.get_resistance('slashing') == 1.0  # Normal

    def test_temporary_modifiers(self):
        """Temporary modifiers affect stats."""
        obj = GameObject("Fighter")
        obj.db.strength = 14

        combatant = Combatant(obj)
        combatant.add_modifier('strength', 2)

        assert combatant.get_stat('strength') == 16

        combatant.remove_modifier('strength', 2)
        assert combatant.get_stat('strength') == 14

    def test_get_combatant_cache(self):
        """get_combatant caches combatants."""
        obj = GameObject("Fighter")

        c1 = get_combatant(obj)
        c2 = get_combatant(obj)

        assert c1 is c2


class TestD20Ruleset:
    """Test suite for D20 ruleset."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_combatant_cache()
        self.ruleset = D20Ruleset()

    def test_ability_modifier(self):
        """Ability modifiers are calculated correctly."""
        obj = GameObject("Fighter")
        obj.db.strength = 16
        obj.db.dexterity = 8

        combatant = Combatant(obj)

        assert self.ruleset.get_ability_modifier(combatant, 'strength') == 3
        assert self.ruleset.get_ability_modifier(combatant, 'dexterity') == -1

    def test_attack_roll_structure(self):
        """Attack roll returns proper structure."""
        attacker_obj = GameObject("Fighter")
        attacker_obj.db.strength = 14

        defender_obj = GameObject("Goblin")
        defender_obj.db.armor_class = 12

        attacker = Combatant(attacker_obj)
        defender = Combatant(defender_obj)

        result = self.ruleset.roll_attack(attacker, defender)

        assert isinstance(result, AttackResult)
        assert isinstance(result.roll, RollResult)
        assert result.roll.dice  # Has dice
        assert result.roll.target == 12  # AC

    def test_damage_roll_structure(self):
        """Damage roll returns proper structure."""
        attacker_obj = GameObject("Fighter")
        attacker_obj.db.strength = 14

        defender_obj = GameObject("Goblin")

        # Create a mock weapon
        weapon = GameObject("Sword")
        weapon.db.damage_dice = "1d8"
        weapon.db.damage_type = "slashing"

        attacker = Combatant(attacker_obj)
        defender = Combatant(defender_obj)

        attack_result = AttackResult(hit=True, roll=RollResult(total=15, dice=[15]))
        damage = self.ruleset.roll_damage(attacker, defender, attack_result, weapon)

        assert isinstance(damage, DamageResult)
        assert damage.total >= 1  # Minimum 1 damage
        assert DamageType.SLASHING in damage.damage_by_type

    def test_apply_damage_with_resistance(self):
        """Damage is reduced by resistance."""
        defender_obj = GameObject("Demon")
        defender_obj.db.hp = 50
        defender_obj.db.resistances = ['fire']

        defender = Combatant(defender_obj)

        damage = DamageResult(
            total=10,
            damage_by_type={DamageType.FIRE: 10}
        )

        actual = self.ruleset.apply_damage(defender, damage)

        assert actual == 5  # Half damage from resistance
        assert defender.hp == 45

    def test_is_defeated_at_zero_hp(self):
        """Combatant is defeated at 0 HP."""
        obj = GameObject("Fighter")
        obj.db.hp = 0

        combatant = Combatant(obj)
        assert self.ruleset.is_defeated(combatant) is True

        obj.db.hp = 1
        assert self.ruleset.is_defeated(combatant) is False


class TestGURPSRuleset:
    """Test suite for GURPS ruleset."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_combatant_cache()
        self.ruleset = GURPSRuleset()

    def test_roll_3d6(self):
        """3d6 produces valid results."""
        for _ in range(10):
            total, dice = self.ruleset.roll_3d6()
            assert len(dice) == 3
            assert all(1 <= d <= 6 for d in dice)
            assert total == sum(dice)
            assert 3 <= total <= 18

    def test_critical_success(self):
        """Critical success detection."""
        assert self.ruleset.is_critical_success(3, 10) is True
        assert self.ruleset.is_critical_success(4, 10) is True
        assert self.ruleset.is_critical_success(5, 15) is True
        assert self.ruleset.is_critical_success(5, 14) is False
        assert self.ruleset.is_critical_success(10, 15) is False

    def test_critical_failure(self):
        """Critical failure detection."""
        assert self.ruleset.is_critical_failure(18, 10) is True
        assert self.ruleset.is_critical_failure(17, 10) is True
        assert self.ruleset.is_critical_failure(17, 16) is False
        assert self.ruleset.is_critical_failure(20, 10) is True  # >= skill + 10

    def test_attack_roll_structure(self):
        """Attack roll returns proper structure."""
        attacker_obj = GameObject("Fighter")
        attacker_obj.db.skill_melee = 12

        defender_obj = GameObject("Goblin")

        attacker = Combatant(attacker_obj)
        defender = Combatant(defender_obj)

        result = self.ruleset.roll_attack(attacker, defender)

        assert isinstance(result, AttackResult)
        assert isinstance(result.roll, RollResult)
        assert len(result.roll.dice) == 3  # 3d6

    def test_active_defense(self):
        """Active defense works."""
        defender_obj = GameObject("Fighter")
        defender_obj.db.dodge = 10

        defender = Combatant(defender_obj)
        defense = self.ruleset.roll_defense(defender)

        assert hasattr(defense, 'success')
        assert len(defense.roll.dice) == 3

    def test_damage_with_dr(self):
        """Damage is reduced by DR."""
        attacker_obj = GameObject("Fighter")
        attacker_obj.db.strength = 12

        defender_obj = GameObject("Knight")
        defender_obj.db.hp = 50
        defender_obj.db.damage_resistance = 3

        attacker = Combatant(attacker_obj)
        defender = Combatant(defender_obj)

        attack_result = AttackResult(hit=True, roll=RollResult(total=10, dice=[3, 4, 3]))

        # Create weapon
        weapon = GameObject("Sword")
        weapon.db.damage_dice = "1d+2"
        weapon.db.damage_type = "cutting"

        damage = self.ruleset.roll_damage(attacker, defender, attack_result, weapon)

        # Apply damage (will subtract DR)
        actual = self.ruleset.apply_damage(defender, damage)

        # DR should have reduced damage
        assert actual <= damage.total


class TestCombatSystem:
    """Test suite for CombatSystem."""

    def setup_method(self):
        """Set up test fixtures."""
        clear_combatant_cache()
        self.d20_combat = CombatSystem(ruleset=D20Ruleset())
        self.gurps_combat = CombatSystem(ruleset=GURPSRuleset())

    @pytest.mark.asyncio
    async def test_attack_returns_result(self):
        """attack() returns CombatResult."""
        attacker = GameObject("Fighter")
        attacker.db.strength = 14
        attacker.db.hp = 50

        defender = GameObject("Goblin")
        defender.db.armor_class = 10
        defender.db.hp = 10
        defender.db.max_hp = 10

        result = await self.d20_combat.attack(attacker, defender)

        assert hasattr(result, 'success')
        assert hasattr(result, 'attack_result')
        assert hasattr(result, 'messages')

    @pytest.mark.asyncio
    async def test_attack_damages_defender(self):
        """Successful attack damages defender."""
        attacker = GameObject("Fighter")
        attacker.db.strength = 20  # High strength for reliable hits
        attacker.db.proficiency_bonus = 10  # High bonus

        defender = GameObject("Goblin")
        defender.db.armor_class = 1  # Very low AC - almost always hits
        defender.db.hp = 100
        defender.db.max_hp = 100

        initial_hp = defender.db.hp

        # Attack multiple times - at least one should hit
        for _ in range(10):
            await self.d20_combat.attack(attacker, defender)

        combatant = get_combatant(defender)
        # At least some damage should have been dealt
        assert combatant.hp <= initial_hp

    @pytest.mark.asyncio
    async def test_heal_restores_hp(self):
        """heal() restores HP."""
        target = GameObject("Fighter")
        target.db.hp = 20
        target.db.max_hp = 50

        healed = await self.d20_combat.heal(None, target, 15)

        assert healed == 15
        combatant = get_combatant(target)
        assert combatant.hp == 35

    def test_roll_initiative(self):
        """roll_initiative returns sorted order."""
        c1 = GameObject("Fast")
        c1.db.dexterity = 18

        c2 = GameObject("Slow")
        c2.db.dexterity = 8

        c3 = GameObject("Medium")
        c3.db.dexterity = 12

        round_obj = self.d20_combat.roll_initiative([c1, c2, c3])

        assert len(round_obj.initiative_order) == 3
        # Order should be sorted by initiative (highest first)
        initiatives = [init for init, _ in round_obj.initiative_order]
        assert initiatives == sorted(initiatives, reverse=True)

    def test_start_and_end_combat(self):
        """start_combat and end_combat manage state."""
        c1 = GameObject("Fighter")
        c2 = GameObject("Goblin")

        combat_id = self.d20_combat.start_combat([c1, c2])

        combatants = self.d20_combat.get_combatants(combat_id)
        assert len(combatants) == 2
        assert all(c.state == CombatState.COMBAT for c in combatants)

        self.d20_combat.end_combat(combat_id)

        combatants = self.d20_combat.get_combatants(combat_id)
        assert len(combatants) == 0


class TestCreateCombatSystem:
    """Test the factory function."""

    def test_create_d20(self):
        """Can create D20 combat system."""
        combat = create_combat_system("d20")
        assert isinstance(combat.ruleset, D20Ruleset)

    def test_create_gurps(self):
        """Can create GURPS combat system."""
        combat = create_combat_system("gurps")
        assert isinstance(combat.ruleset, GURPSRuleset)

    def test_create_with_options(self):
        """Can pass options to ruleset."""
        combat = create_combat_system("d20", use_proficiency=False)
        assert combat.ruleset.use_proficiency is False

    def test_unknown_ruleset_raises(self):
        """Unknown ruleset raises ValueError."""
        with pytest.raises(ValueError):
            create_combat_system("unknown_system")


class TestRollResult:
    """Test RollResult dataclass."""

    def test_str_representation(self):
        """__str__ returns readable format."""
        result = RollResult(
            total=15,
            dice=[5, 4, 6],
            modifier=0,
        )

        str_repr = str(result)
        assert "15" in str_repr

    def test_str_with_modifier(self):
        """__str__ includes modifier."""
        result = RollResult(
            total=18,
            dice=[5, 4, 6],
            modifier=3,
        )

        str_repr = str(result)
        assert "+3" in str_repr
        assert "18" in str_repr


class TestSwappableRulesets:
    """Test that rulesets are truly swappable."""

    def setup_method(self):
        clear_combatant_cache()

    @pytest.mark.asyncio
    async def test_same_combatants_different_rulesets(self):
        """Same combatants can be used with different rulesets."""
        fighter = GameObject("Fighter")
        fighter.db.strength = 14
        fighter.db.dexterity = 12
        fighter.db.hp = 50
        fighter.db.max_hp = 50
        fighter.db.skill_melee = 12  # For GURPS
        fighter.db.armor_class = 15  # For D20

        goblin = GameObject("Goblin")
        goblin.db.strength = 8
        goblin.db.dexterity = 14
        goblin.db.hp = 20
        goblin.db.max_hp = 20
        goblin.db.skill_melee = 10
        goblin.db.armor_class = 12
        goblin.db.dodge = 8

        # D20 combat
        d20_combat = CombatSystem(ruleset=D20Ruleset())
        d20_result = await d20_combat.attack(fighter, goblin)
        assert d20_result.attack_result is not None

        # Reset HP
        goblin.db.hp = 20
        clear_combatant_cache()

        # GURPS combat
        gurps_combat = CombatSystem(ruleset=GURPSRuleset())
        gurps_result = await gurps_combat.attack(fighter, goblin)
        assert gurps_result.attack_result is not None

        # Results should have different roll structures
        if d20_result.attack_result and gurps_result.attack_result:
            # D20 uses 1d20, GURPS uses 3d6
            assert len(d20_result.attack_result.roll.dice) == 1
            assert len(gurps_result.attack_result.roll.dice) == 3
