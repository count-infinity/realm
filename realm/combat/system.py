"""
Combat system orchestrator for REALM.

Ties together:
- Ruleset: How combat is resolved
- Combatants: Who is fighting
- Actions: Combat actions propagated through the engine (attack, damage, death)
- Messaging: What players see

The CombatSystem is the main entry point for all combat operations. Combat
emits actions through ``propagate(action, deliver=False)`` because it does
its own messaging via the ruleset's formatted message dicts; behaviors
attached to combatants/rooms can still observe and influence each step
(blocking an attack, modifying damage, reacting to a death).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from realm.combat.combatant import Combatant, CombatState, get_combatant
from realm.combat.ruleset import (
    AttackResult,
    DamageResult,
    Ruleset,
)
from realm.core.propagation import Action, propagate

if TYPE_CHECKING:
    from realm.core.objects import GameObject


logger = logging.getLogger(__name__)


@dataclass
class CombatRound:
    """Represents a single combat round with initiative order."""

    round_number: int
    combatants: list[Combatant]
    initiative_order: list[tuple[int, Combatant]] = field(default_factory=list)
    current_index: int = 0

    def sort_by_initiative(self) -> None:
        """Sort combatants by initiative (highest first)."""
        self.initiative_order.sort(key=lambda x: x[0], reverse=True)

    @property
    def current_combatant(self) -> Combatant | None:
        """Get the current combatant in initiative order."""
        if 0 <= self.current_index < len(self.initiative_order):
            return self.initiative_order[self.current_index][1]
        return None

    def next_turn(self) -> Combatant | None:
        """Advance to next combatant. Returns None if round is over."""
        self.current_index += 1
        if self.current_index >= len(self.initiative_order):
            return None
        return self.current_combatant


@dataclass
class CombatResult:
    """Complete result of a combat action."""

    success: bool
    attack_result: AttackResult | None = None
    damage_result: DamageResult | None = None
    defense_result: Any = None  # DefenseResult
    messages: dict[str, str] = field(default_factory=dict)
    effects: list[str] = field(default_factory=list)
    target_defeated: bool = False


class CombatSystem:
    """
    Main combat system orchestrator.

    Handles:
    - Attack resolution using the configured ruleset
    - Damage application
    - Combat state management
    - Event emission for combat events
    - Message generation
    """

    def __init__(self, ruleset: Ruleset):
        """
        Initialize combat system.

        Args:
            ruleset: The combat ruleset to use
        """
        self.ruleset = ruleset
        self._active_combats: dict[str, list[Combatant]] = {}

    async def attack(
        self,
        attacker: GameObject | Combatant,
        defender: GameObject | Combatant,
        weapon: Any | None = None,
        modifiers: dict[str, int] | None = None,
    ) -> CombatResult:
        """
        Perform an attack from attacker to defender.

        This is the main entry point for combat. It:
        1. Wraps objects as Combatants
        2. Rolls attack using the ruleset
        3. Allows active defense (if ruleset supports)
        4. Rolls and applies damage on hit
        5. Emits combat events
        6. Returns complete combat result

        Args:
            attacker: The attacking object/combatant
            defender: The defending object/combatant
            weapon: Optional weapon being used
            modifiers: Situational modifiers

        Returns:
            CombatResult with all details
        """
        # Wrap as combatants if needed
        atk = self._ensure_combatant(attacker)
        dfn = self._ensure_combatant(defender)

        # Set combat states
        atk.state = CombatState.COMBAT
        dfn.state = CombatState.COMBAT
        atk.target = dfn

        # Propagate attack action — behaviors can block (e.g. a "frozen" debuff
        # vetoes the attack) or add modifiers picked up by the ruleset.
        attack_action = await self._propagate_attack(atk, dfn, weapon)
        if attack_action.blocked:
            return CombatResult(
                success=False,
                messages={
                    'attacker_msg': attack_action.block_reason or "Attack prevented.",
                },
            )

        # Roll attack
        attack_result = self.ruleset.roll_attack(atk, dfn, weapon, modifiers)

        # Handle miss
        if not attack_result.hit:
            messages = self.ruleset.format_attack_message(atk, dfn, attack_result)
            return CombatResult(
                success=False,
                attack_result=attack_result,
                messages=messages,
                effects=attack_result.effects,
            )

        # Check active defense (if supported)
        defense_result = None
        if hasattr(self.ruleset, 'roll_defense'):
            defense_result = self.ruleset.roll_defense(dfn)
            if defense_result.success:
                messages = {
                    'attacker_msg': f"{dfn.name} defends against your attack!",
                    'defender_msg': f"You defend against {atk.name}'s attack!",
                    'others_msg': f"{dfn.name} defends against {atk.name}!",
                }
                return CombatResult(
                    success=False,
                    attack_result=attack_result,
                    defense_result=defense_result,
                    messages=messages,
                )

        # Roll damage
        damage_result = self.ruleset.roll_damage(atk, dfn, attack_result, weapon)

        # Propagate damage action — a "ward" or "shield" behavior can block
        # damage even after a successful hit.
        damage_action = await self._propagate_damage(atk, dfn, damage_result)
        if damage_action.blocked:
            return CombatResult(
                success=True,
                attack_result=attack_result,
                messages={
                    'attacker_msg': damage_action.block_reason or "Damage prevented.",
                },
            )

        # Apply damage
        actual_damage = self.ruleset.apply_damage(dfn, damage_result)

        # Check if defeated
        target_defeated = self.ruleset.is_defeated(dfn)
        if target_defeated:
            dfn.state = CombatState.DEFEATED
            await self._propagate_death(dfn, atk)

        # Generate messages
        messages = self.ruleset.format_attack_message(atk, dfn, attack_result, damage_result)

        if target_defeated:
            messages['attacker_msg'] += f" {dfn.name} is defeated!"
            messages['defender_msg'] += " You have been defeated!"
            messages['others_msg'] += f" {dfn.name} falls!"

        return CombatResult(
            success=True,
            attack_result=attack_result,
            damage_result=damage_result,
            defense_result=defense_result,
            messages=messages,
            effects=attack_result.effects + damage_result.effects,
            target_defeated=target_defeated,
        )

    async def heal(
        self,
        healer: GameObject | Combatant | None,
        target: GameObject | Combatant,
        amount: int,
    ) -> int:
        """
        Heal a target.

        Args:
            healer: Who is doing the healing (can be None for items/effects)
            target: Who is being healed
            amount: Base healing amount

        Returns:
            Actual amount healed
        """
        tgt = self._ensure_combatant(target)
        hlr = self._ensure_combatant(healer) if healer else None

        # Calculate healing through ruleset
        final_amount = self.ruleset.calculate_healing(hlr, tgt, amount)

        # Apply healing
        actual = tgt.heal(final_amount)

        # If target was defeated and now has HP, revive them
        if tgt.state == CombatState.DEFEATED and tgt.hp > 0:
            tgt.state = CombatState.IDLE

        return actual

    def roll_initiative(
        self,
        combatants: list[GameObject | Combatant],
    ) -> CombatRound:
        """
        Roll initiative for a group of combatants.

        Returns a CombatRound with sorted initiative order.
        """
        wrapped = [self._ensure_combatant(c) for c in combatants]

        round_obj = CombatRound(
            round_number=1,
            combatants=wrapped,
        )

        # Roll initiative for each
        for combatant in wrapped:
            roll = self.ruleset.roll_initiative(combatant)
            round_obj.initiative_order.append((roll.total, combatant))

        # Sort by initiative
        round_obj.sort_by_initiative()

        return round_obj

    def start_combat(
        self,
        combatants: list[GameObject | Combatant],
        combat_id: str | None = None,
    ) -> str:
        """
        Start a combat encounter.

        Args:
            combatants: List of participants
            combat_id: Optional ID (generated if not provided)

        Returns:
            Combat ID
        """
        import uuid
        combat_id = combat_id or str(uuid.uuid4())[:8]

        wrapped = [self._ensure_combatant(c) for c in combatants]
        for c in wrapped:
            c.state = CombatState.COMBAT

        self._active_combats[combat_id] = wrapped

        logger.info(f"Combat started: {combat_id} with {len(wrapped)} combatants")
        return combat_id

    def end_combat(self, combat_id: str) -> None:
        """End a combat encounter."""
        if combat_id in self._active_combats:
            combatants = self._active_combats.pop(combat_id)
            for c in combatants:
                if c.state == CombatState.COMBAT:
                    c.state = CombatState.IDLE
                c.target = None
                c.clear_modifiers()

            logger.info(f"Combat ended: {combat_id}")

    def get_combatants(self, combat_id: str) -> list[Combatant]:
        """Get combatants in an active combat."""
        return self._active_combats.get(combat_id, [])

    def _ensure_combatant(self, obj: GameObject | Combatant) -> Combatant:
        """Wrap a GameObject as a Combatant if needed."""
        if isinstance(obj, Combatant):
            return obj
        return get_combatant(obj)

    # --- Action Propagation ---
    #
    # Combat propagates actions through the engine but opts out of default
    # message delivery (deliver=False) — the ruleset produces the
    # attacker/defender/others message dict and the caller delivers those
    # itself. Behaviors can still block actions or accumulate modifiers.

    async def _propagate_attack(
        self,
        attacker: Combatant,
        defender: Combatant,
        weapon: Any | None,
    ) -> Action:
        action = Action(
            actor=attacker.obj,
            target=defender.obj,
            action_type="combat:on_attack",
            tool=weapon if hasattr(weapon, 'name') else None,
            tags={"hostile"},
            extra={
                'weapon': weapon,
                'attacker_hp': attacker.hp,
                'defender_hp': defender.hp,
            },
        )
        await propagate(action, deliver=False)
        return action

    async def _propagate_damage(
        self,
        attacker: Combatant,
        defender: Combatant,
        damage: DamageResult,
    ) -> Action:
        action = Action(
            actor=attacker.obj,
            target=defender.obj,
            action_type="combat:on_damage",
            tags={"hostile"},
            extra={
                'damage': damage.total,
                'damage_types': {k.value: v for k, v in damage.damage_by_type.items()},
            },
        )
        await propagate(action, deliver=False)
        return action

    async def _propagate_death(
        self,
        victim: Combatant,
        killer: Combatant | None,
    ) -> Action:
        action = Action(
            actor=killer.obj if killer else None,
            target=victim.obj,
            action_type="combat:on_death",
            extra={
                'killer': killer.name if killer else None,
            },
        )
        await propagate(action, deliver=False)
        return action


# Global combat system instance
_combat_system: CombatSystem | None = None


def get_combat_system() -> CombatSystem | None:
    """Get the global combat system."""
    return _combat_system


def set_combat_system(system: CombatSystem) -> None:
    """Set the global combat system."""
    global _combat_system
    _combat_system = system


def create_combat_system(
    ruleset_name: str = "d20",
    **ruleset_options: Any,
) -> CombatSystem:
    """
    Create a combat system with the specified ruleset.

    Args:
        ruleset_name: Name of ruleset ("d20", "gurps")
        **ruleset_options: Options passed to ruleset constructor

    Returns:
        Configured CombatSystem
    """
    from realm.combat.rulesets.d20 import D20Ruleset
    from realm.combat.rulesets.gurps import GURPSRuleset

    ruleset_map = {
        'd20': D20Ruleset,
        'dnd': D20Ruleset,
        'gurps': GURPSRuleset,
        '3d6': GURPSRuleset,
    }

    ruleset_class = ruleset_map.get(ruleset_name.lower())
    if not ruleset_class:
        raise ValueError(f"Unknown ruleset: {ruleset_name}. Available: {list(ruleset_map.keys())}")

    ruleset = ruleset_class(**ruleset_options)
    return CombatSystem(ruleset=ruleset)
