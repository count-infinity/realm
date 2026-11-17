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

from realm.core.action_tags import HOSTILE
from realm.core.markup import capitalize, wrap
from realm.core.pools import PoolChange, settle
from realm.core.propagation import Action, propagate
from realm.core.world import find_world
from realm.features import ruleset_table
from realm.std.combat.actions import CombatAction
from realm.std.combat.combatant import Combatant, CombatState, get_combatant
from realm.std.combat.damage import deal_damage
from realm.std.combat.ruleset import (
    AttackResult,
    DamageResult,
    Ruleset,
)

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
    #: The blow's pool changes, unsettled: the caller shows the messages,
    #: then settles them (``pools.settle``), which runs the death and
    #: ``ON_HITPRCNT`` observers. ``CombatEncounter.land`` does both.
    changes: list[PoolChange] = field(default_factory=list)


class RulesetRegistry:
    """Combat rulesets by name. A game declares its own with
    ``feature.ruleset('mysystem', MyRuleset)`` and selects it via
    COMBAT_RULESET / GameSystem.ruleset_name; the shipped ones come from the
    ``gurps``, ``d20`` and ``merc`` features (``realm/games/``). The table
    holds exactly the installed features' rulesets (see realm.features).
    ``register`` is the low-level call, for tests."""

    @classmethod
    def register(cls, name: str, ruleset_class: type, *,
                 replace: bool = False) -> None:
        """Register ``ruleset_class`` under ``name`` (case-insensitive).
        Raises ValueError when the name is taken by a different class,
        unless ``replace`` is true."""
        table = ruleset_table()
        key = name.lower()
        current = table.get(key)
        if current is not None and current is not ruleset_class and not replace:
            raise ValueError(
                f"Ruleset {key!r} is already registered to "
                f"{current.__module__}.{current.__qualname__}. Pick another "
                f"name, or pass replace=True to override it.")
        table[key] = ruleset_class

    @classmethod
    def get(cls, name: str) -> type | None:
        return ruleset_table().get(name.lower())

    @classmethod
    def list_all(cls) -> list[str]:
        return sorted(ruleset_table())


def find_wielded(obj) -> Any | None:
    """The first carried object tagged ``wielded`` — the readied weapon."""
    for item in obj.contents:
        if item.has_tag('wielded'):
            return item
    return None


# --- Roll visibility ---------------------------------------------------------
# Every ruleset already narrates its rolls (RollResult.description:
# "d20(13) vs need 35 (THAC0 20 - AC -15)"); this surfaces them on combat
# messages. Game-wide default from config SHOW_ROLLS (the combat feature's
# setting); per-player override on db.show_rolls (`showrolls on|off`).


def shows_rolls(obj: Any | None) -> bool:
    """Does this participant want roll detail on their combat lines?"""
    if obj is None:
        return False
    db = getattr(obj, 'db', None)
    if db is None:
        return False
    pref = db.get('show_rolls')
    if pref is None:
        from realm.core.world import setting
        return bool(setting("SHOW_ROLLS", False))
    return bool(pref)


def append_roll_notes(messages: dict, attacker: Any | None,
                      defender: Any | None, *rolls: Any) -> None:
    """Append ``[roll description]`` notes to the attacker's and defender's
    combat lines, each according to their own preference. Bystanders never
    see roll detail."""
    note = "  ".join(wrap('c', f"[{r.description}]") for r in rolls
                     if r is not None and getattr(r, 'description', ''))
    if not note:
        return
    if messages.get('attacker_msg') and shows_rolls(attacker):
        messages['attacker_msg'] += f"\n  {note}"
    if messages.get('defender_msg') and shows_rolls(defender):
        messages['defender_msg'] += f"\n  {note}"


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

        # Roll attack (riding changes it when the game system says so)
        modifiers = {**(modifiers or {}), **_mounted(atk.obj, dfn.obj)}
        attack_result = self.ruleset.roll_attack(atk, dfn, weapon, modifiers)
        self._report_skill_use(atk, weapon, attack_result)

        # Handle miss
        if not attack_result.hit:
            messages = self.ruleset.format_attack_message(atk, dfn, attack_result)
            append_roll_notes(messages, atk.obj, dfn.obj, attack_result.roll)
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
                append_roll_notes(messages, atk.obj, dfn.obj,
                                  attack_result.roll, defense_result.roll)
                return CombatResult(
                    success=False,
                    attack_result=attack_result,
                    defense_result=defense_result,
                    messages=messages,
                )

        # Roll damage
        damage_result = self.ruleset.roll_damage(atk, dfn, attack_result, weapon)

        # Deal it through the shared chokepoint: fires the interceptable
        # combat:on_damage event (a ward/shield/room rule may block or
        # reduce it), honors the reduction, then applies via the ruleset.
        _dealt, damage_action, changes = await deal_damage(
            atk.obj, dfn, damage_result, self.ruleset)
        if damage_action.blocked:
            return CombatResult(
                success=True,
                attack_result=attack_result,
                messages={
                    'attacker_msg': damage_action.block_reason or "Damage prevented.",
                },
            )

        # Defeat ends the defender's part in the fight. Death itself, and
        # ON_HITPRCNT, come from the observers on the vital pool when the
        # caller settles ``changes`` (realm.std.combat.vitals).
        target_defeated = dfn.vital_spent
        if target_defeated:
            dfn.state = CombatState.DEFEATED

        # Generate messages
        messages = self.ruleset.format_attack_message(atk, dfn, attack_result, damage_result)

        if target_defeated:
            messages['attacker_msg'] += f" {capitalize(dfn.name)} is defeated!"
            messages['defender_msg'] += " You have been defeated!"
            messages['others_msg'] += f" {capitalize(dfn.name)} falls!"

        # Roll notes go LAST so suffixes ("X is defeated!") stay on the
        # message line, not dangling after the dice.
        append_roll_notes(messages, atk.obj, dfn.obj,
                          attack_result.roll,
                          defense_result.roll if defense_result else None,
                          damage_result.roll)

        return CombatResult(
            success=True,
            attack_result=attack_result,
            damage_result=damage_result,
            defense_result=defense_result,
            messages=messages,
            effects=attack_result.effects + damage_result.effects,
            target_defeated=target_defeated,
            changes=changes,
        )

    def _report_skill_use(self, atk: Combatant, weapon: Any | None,
                          attack_result: Any) -> None:
        """An attack roll is a use of the weapon's skill (its ``skill``
        attribute, else ``skill_type``, else ``melee``): the game system
        hears it as it hears a check, so a weapon skill can learn by use
        under rulesets that do not roll attacks through ``check()``."""
        from realm.core.dice import CheckResult
        from realm.core.world import find_world
        world = find_world()
        if world is None or world.rules is None:
            return
        skill = (self.ruleset.weapon_prop(weapon, "skill", None)
                 or self.ruleset.weapon_prop(weapon, "skill_type", None) or "melee")
        roll = attack_result.roll
        world.rules.on_skill_used(atk.obj, CheckResult(
            success=bool(attack_result.hit), margin=int(attack_result.margin or 0),
            roll=int(roll.total or 0), effective=int(roll.target or 0), skill=str(skill)))

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
        for change in tgt.drain_changes():
            await settle(change, source=hlr.obj if hlr else None)

        # If target was defeated and is no longer spent, revive them
        if tgt.state == CombatState.DEFEATED and not tgt.vital_spent:
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
            action_type=CombatAction.ON_ATTACK,
            tool=weapon if hasattr(weapon, 'name') else None,
            tags={HOSTILE},
            extra={
                'weapon': weapon,
                'attacker_hp': attacker.vital,
                'defender_hp': defender.vital,
            },
        )
        await propagate(action, deliver=False)
        return action





def _mounted(attacker: Any, defender: Any) -> dict[str, int]:
    """The situational modifiers riding gives (MUD_PLAN 13.3): the game
    system's ``mounted_modifiers`` for whichever side is riding, through
    the ``companions`` service (none without it)."""
    world = find_world()
    companions = world.services.get("companions") if world is not None else None
    if companions is None:
        return {}
    found: dict[str, int] = {}
    mount = companions.mount_of(attacker)
    if mount is not None:
        bonus = int(world.rules.mounted_modifiers(attacker, mount).get("attack") or 0)
        if bonus:
            found["mounted"] = bonus
    mount = companions.mount_of(defender)
    if mount is not None:
        guard = int(world.rules.mounted_modifiers(defender, mount).get("defense") or 0)
        if guard:
            found["target_mounted"] = -guard
    return found


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
    ruleset_class = RulesetRegistry.get(ruleset_name.lower())
    if not ruleset_class:
        raise ValueError(
            f"Unknown ruleset: {ruleset_name}. "
            f"Available: {RulesetRegistry.list_all()}")

    ruleset = ruleset_class(**ruleset_options)
    return CombatSystem(ruleset=ruleset)
