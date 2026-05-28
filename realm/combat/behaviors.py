"""
Combat behaviors for NPCs and automated combat.

These behaviors can be attached to GameObjects to give them
combat AI:
- AggressiveBehavior: Attacks enemies on sight
- DefensiveBehavior: Only fights back when attacked
- GuardBehavior: Protects an area or object
- FleeingBehavior: Runs when HP is low
- HealerBehavior: Heals allies
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from realm.core.behaviors import Behavior, BehaviorRegistry

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action


@BehaviorRegistry.register
class AggressiveBehavior(Behavior):
    """
    Attacks valid targets when they enter the room.

    Parameters:
        attack_chance: Probability of attacking (0.0-1.0, default 1.0)
        target_tags: Tags that mark valid targets (default ['player'])
        attack_delay: Seconds to wait before attacking (default 0)
        taunt_messages: Optional list of messages to say before attacking
    """

    behavior_id = "aggressive"

    @property
    def should_tick(self) -> bool:
        # Tick to continue combat
        return True

    @property
    def tick_interval(self) -> float:
        return 3.0  # Attack every 3 seconds in combat

    async def on_react(self, obj: GameObject, action: Action) -> None:
        """React to enter events by potentially attacking."""
        if action.action_type != "event:on_enter":
            return

        # Check if the entering object is a valid target
        entering = action.actor
        if not entering or entering == obj:
            return

        if not self._is_valid_target(entering):
            return

        # Roll for attack chance
        attack_chance = self.get_param('attack_chance', 1.0)
        if random.random() > attack_chance:
            return

        # Delay if configured
        attack_delay = self.get_param('attack_delay', 0)
        if attack_delay > 0:
            # Would need async delay, skip for now
            pass

        # Say taunt
        taunts = self.get_param('taunt_messages', [])
        if taunts:
            taunt = random.choice(taunts)
            # Would queue a trailing speech action
            pass

        # Attack the target
        await self._attack_target(obj, entering)

    async def tick(self, obj: GameObject, delta: float) -> None:
        """Continue attacking in combat."""
        from realm.combat.system import get_combat_system
        from realm.combat.combatant import get_combatant, CombatState

        combat = get_combat_system()
        if not combat:
            return

        combatant = get_combatant(obj)
        if combatant.state != CombatState.COMBAT:
            return

        # Continue attacking current target
        if combatant.target and combatant.target.is_alive:
            await combat.attack(combatant, combatant.target)
        else:
            # Find new target
            combatant.state = CombatState.IDLE
            combatant.target = None

    def _is_valid_target(self, target: GameObject) -> bool:
        """Check if target should be attacked."""
        target_tags = self.get_param('target_tags', ['player'])
        for tag in target_tags:
            if target.has_tag(tag):
                return True
        return False

    async def _attack_target(self, attacker: GameObject, target: GameObject) -> None:
        """Initiate attack on target."""
        from realm.combat.system import get_combat_system

        combat = get_combat_system()
        if combat:
            await combat.attack(attacker, target)


@BehaviorRegistry.register
class DefensiveBehavior(Behavior):
    """
    Only fights back when attacked.

    Parameters:
        retaliate_chance: Probability of fighting back (default 1.0)
        flee_threshold: HP percentage to flee at (default 0.2)
    """

    behavior_id = "defensive"

    async def on_react(self, obj: GameObject, action: Action) -> None:
        """React to being attacked."""
        if action.action_type != "combat:on_damage":
            return

        # Check if we are the target
        if action.target != obj:
            return

        attacker = action.actor
        if not attacker:
            return

        # Roll for retaliation
        retaliate_chance = self.get_param('retaliate_chance', 1.0)
        if random.random() > retaliate_chance:
            return

        # Check if we should flee instead
        from realm.combat.combatant import get_combatant

        combatant = get_combatant(obj)
        flee_threshold = self.get_param('flee_threshold', 0.2)
        if combatant.hp_percent <= flee_threshold:
            # Try to flee
            await self._try_flee(obj)
            return

        # Retaliate
        await self._attack_target(obj, attacker)

    async def _attack_target(self, attacker: GameObject, target: GameObject) -> None:
        """Counter-attack."""
        from realm.combat.system import get_combat_system

        combat = get_combat_system()
        if combat:
            await combat.attack(attacker, target)

    async def _try_flee(self, obj: GameObject) -> None:
        """Attempt to flee combat."""
        from realm.combat.combatant import get_combatant, CombatState

        combatant = get_combatant(obj)
        combatant.state = CombatState.FLEEING
        # Actual fleeing logic would go here


@BehaviorRegistry.register
class GuardBehavior(Behavior):
    """
    Protects an area, attacking those without permission.

    Parameters:
        guard_tags: Tags that mark who to block (default ['player'])
        allow_tags: Tags that mark who to let pass (default ['guard', 'admin'])
        challenge_message: What to say when challenging
        block_exits: List of exit names to guard (default all)
    """

    behavior_id = "guard"

    async def on_check(self, obj: GameObject, action: Action) -> None:
        """Potentially block movement through guarded exits."""
        if action.action_type not in ("event:on_enter", "event:on_leave"):
            return

        mover = action.actor
        if not mover or mover == obj:
            return

        # Check if mover is allowed
        allow_tags = self.get_param('allow_tags', ['guard', 'admin'])
        for tag in allow_tags:
            if mover.has_tag(tag):
                return

        # Check if mover should be blocked
        guard_tags = self.get_param('guard_tags', ['player'])
        should_block = False
        for tag in guard_tags:
            if mover.has_tag(tag):
                should_block = True
                break

        if not should_block:
            return

        # Block the movement
        challenge = self.get_param('challenge_message', "Halt! You shall not pass!")
        action.block(challenge)


@BehaviorRegistry.register
class FleeingBehavior(Behavior):
    """
    Flees when HP drops below threshold.

    Parameters:
        flee_threshold: HP percentage to flee at (default 0.25)
        flee_chance: Probability of successful flee (default 0.5)
    """

    behavior_id = "fleeing"

    async def on_react(self, obj: GameObject, action: Action) -> None:
        """Check HP after taking damage."""
        if action.action_type != "combat:on_damage":
            return

        if action.target != obj:
            return

        from realm.combat.combatant import get_combatant, CombatState

        combatant = get_combatant(obj)
        flee_threshold = self.get_param('flee_threshold', 0.25)

        if combatant.hp_percent <= flee_threshold:
            combatant.state = CombatState.FLEEING
            await self._attempt_flee(obj)

    async def _attempt_flee(self, obj: GameObject) -> None:
        """Try to escape combat."""
        flee_chance = self.get_param('flee_chance', 0.5)

        if random.random() < flee_chance:
            # Find an exit and run
            if obj.location:
                exits = [o for o in obj.location.contents if o.has_tag('exit')]
                if exits:
                    escape_exit = random.choice(exits)
                    # Would trigger movement through exit
                    pass


@BehaviorRegistry.register
class HealerBehavior(Behavior):
    """
    Heals injured allies.

    Parameters:
        heal_amount: Base healing amount (default 10)
        heal_threshold: HP percentage to trigger healing (default 0.5)
        heal_cooldown: Seconds between heals (default 5)
        ally_tags: Tags that mark allies (default ['player'])
    """

    behavior_id = "healer"

    def __init__(self, **params: Any):
        super().__init__(**params)
        self._last_heal = 0.0

    @property
    def should_tick(self) -> bool:
        return True

    @property
    def tick_interval(self) -> float:
        return 2.0

    async def tick(self, obj: GameObject, delta: float) -> None:
        """Check for injured allies and heal them."""
        import time
        from realm.combat.system import get_combat_system
        from realm.combat.combatant import get_combatant

        # Check cooldown
        cooldown = self.get_param('heal_cooldown', 5.0)
        now = time.time()
        if now - self._last_heal < cooldown:
            return

        if not obj.location:
            return

        # Find injured allies
        heal_threshold = self.get_param('heal_threshold', 0.5)
        ally_tags = self.get_param('ally_tags', ['player'])

        for other in obj.location.contents:
            if other == obj:
                continue

            # Check if ally
            is_ally = any(other.has_tag(tag) for tag in ally_tags)
            if not is_ally:
                continue

            # Check if injured
            combatant = get_combatant(other)
            if combatant.hp_percent < heal_threshold:
                await self._heal_target(obj, other)
                self._last_heal = now
                break

    async def _heal_target(self, healer: GameObject, target: GameObject) -> None:
        """Heal the target."""
        from realm.combat.system import get_combat_system

        combat = get_combat_system()
        if combat:
            heal_amount = self.get_param('heal_amount', 10)
            await combat.heal(healer, target, heal_amount)


@BehaviorRegistry.register
class CombatantBehavior(Behavior):
    """
    Basic combatant behavior - handles being in combat.

    Parameters:
        auto_retaliate: Automatically fight back when attacked (default True)
        death_message: Message when defeated
    """

    behavior_id = "combatant"

    async def on_react(self, obj: GameObject, action: Action) -> None:
        """Handle combat actions targeting this object."""
        from realm.combat.combatant import get_combatant, CombatState

        if action.action_type == "combat:on_damage" and action.target == obj:
            # We took damage
            combatant = get_combatant(obj)

            # Auto-retaliate if configured
            if self.get_param('auto_retaliate', True) and action.actor:
                if combatant.state == CombatState.IDLE:
                    combatant.state = CombatState.COMBAT
                    combatant.target = get_combatant(action.actor)

        elif action.action_type == "combat:on_death" and action.target == obj:
            # We died
            death_msg = self.get_param('death_message', '')
            if death_msg:
                # Would queue a trailing speech action
                pass

            combatant = get_combatant(obj)
            combatant.state = CombatState.DEAD


@BehaviorRegistry.register
class WanderingBehavior(Behavior):
    """
    Wanders randomly between rooms.

    Parameters:
        wander_chance: Probability of wandering each tick (default 0.1)
        wander_interval: Seconds between wander checks (default 30)
        avoid_tags: Tags of rooms to avoid
    """

    behavior_id = "wandering"

    @property
    def should_tick(self) -> bool:
        return True

    @property
    def tick_interval(self) -> float:
        return self.get_param('wander_interval', 30.0)

    async def tick(self, obj: GameObject, delta: float) -> None:
        """Potentially wander to a new room."""
        from realm.combat.combatant import get_combatant, CombatState

        # Don't wander if in combat
        combatant = get_combatant(obj)
        if combatant.state == CombatState.COMBAT:
            return

        # Roll for wandering
        wander_chance = self.get_param('wander_chance', 0.1)
        if random.random() > wander_chance:
            return

        if not obj.location:
            return

        # Find valid exits
        avoid_tags = self.get_param('avoid_tags', [])
        exits = [o for o in obj.location.contents if o.has_tag('exit')]

        if not exits:
            return

        # Pick a random exit and go through it
        exit_obj = random.choice(exits)
        # Would trigger movement through exit
        pass
