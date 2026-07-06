"""
Combat behaviors for NPCs: brains that join, taunt, guard, heal, and roam.

All of these route through the CombatManager and the encounter engine —
an NPC never swings outside a fight's beats. Reflex-style behaviors
(fleeing when hurt) are implemented as strategy rules written onto the
owner, so they share the exact selection engine players use and are
inspectable via ``@examine``.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior, BehaviorRegistry

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action


def _combat_manager():
    from realm.combat.manager import get_combat_manager
    return get_combat_manager()


def _ensure_strategy_rule(obj: GameObject, condition: str, action: str) -> None:
    """Prepend a strategy rule if an equivalent one isn't present."""
    rules = list(obj.db.get('combat_strategy') or [])
    if any(str(rule[0]) == condition for rule in rules if rule):
        return
    rules.insert(0, [condition, action])
    obj.db.combat_strategy = rules


@BehaviorRegistry.register
class AggressiveBehavior(Behavior):
    """
    Attacks valid targets on sight (they enter, or it wanders in on them).

    Parameters:
        attack_chance: probability of engaging (0.0-1.0, default 1.0)
        target_tags: tags marking valid prey (default ['player'])
        taunt: line said when engaging (optional)
    """

    behavior_id = "aggressive"

    async def on_react(self, obj: GameObject, action: Action) -> None:
        entering = action.actor
        if action.action_type != "event:on_enter" or entering is None:
            return
        if entering is obj or obj.has_tag('in_combat'):
            return
        # Fires both when prey enters our room and when we arrive in theirs.
        if obj.location is None:
            return
        if entering is not obj and action.target is not obj.location:
            return
        await self._maybe_engage(obj, entering)

    async def _maybe_engage(self, obj: GameObject, target: GameObject) -> None:
        from realm.core.perception import can_see

        target_tags = self.get_param('target_tags', ['player'])
        if not any(target.has_tag(tag) for tag in target_tags):
            return
        # Even a monster spares those it's devoted to (spare_at=None disables).
        spare_at = self.get_param('spare_at', 2)
        if spare_at is not None:
            from realm.core.disposition import get_disposition
            if get_disposition(obj, target) >= int(spare_at):
                return
        if not can_see(obj, target):
            return
        if random.random() > float(self.get_param('attack_chance', 1.0)):
            return

        manager = _combat_manager()
        if manager is None:
            return

        taunt = self.get_param('taunt')
        if taunt:
            from realm.behaviors.npc import _npc_say
            await _npc_say(obj, str(taunt))

        await manager.initiate(obj, target)


@BehaviorRegistry.register
class DefensiveBehavior(Behavior):
    """
    Fights back only when attacked (the encounter engine's defender
    auto-join already does the joining); flees when badly hurt.

    Parameters:
        flee_percent: HP percentage to flee below (default 25).
    """

    behavior_id = "defensive"

    def attach(self, obj: GameObject) -> None:
        super().attach(obj)
        flee_percent = int(self.get_param('flee_percent', 25))
        _ensure_strategy_rule(obj, f"!me.hp_percent < {flee_percent}", "flee")


@BehaviorRegistry.register
class FleeingBehavior(Behavior):
    """
    A coward's reflex: flee combat below an HP threshold. Implemented as
    an override strategy rule — the same wimpy players get.

    Parameters:
        flee_percent: HP percentage to flee below (default 50).
    """

    behavior_id = "fleeing"

    def attach(self, obj: GameObject) -> None:
        super().attach(obj)
        flee_percent = int(self.get_param('flee_percent', 50))
        _ensure_strategy_rule(obj, f"!me.hp_percent < {flee_percent}", "flee")


@BehaviorRegistry.register
class GuardBehavior(Behavior):
    """
    Blocks movement for those without permission.

    Parameters:
        guard_tags: tags marking who to block (default ['player'])
        allow_tags: tags marking who passes (default ['guard', 'admin'])
        challenge_message: the block reason shown
    """

    behavior_id = "guard"

    async def on_check(self, obj: GameObject, action: Action) -> None:
        if action.action_type not in ("event:on_enter", "event:on_leave"):
            return

        mover = action.actor
        if not mover or mover == obj:
            return

        allow_tags = self.get_param('allow_tags', ['guard', 'admin'])
        if any(mover.has_tag(tag) for tag in allow_tags):
            return

        # Friends (and the successfully fast-talked) get waved through.
        from realm.core.disposition import get_disposition
        if get_disposition(obj, mover) >= int(self.get_param('allow_disposition', 2)):
            return

        guard_tags = self.get_param('guard_tags', ['player'])
        if not any(mover.has_tag(tag) for tag in guard_tags):
            return

        challenge = self.get_param('challenge_message', "Halt! You shall not pass!")
        action.block(challenge)


@BehaviorRegistry.register
class HealerBehavior(Behavior):
    """
    Heals injured allies in the room, periodically.

    Parameters:
        heal_amount: HP restored per heal (default 5)
        heal_threshold: HP percentage that triggers healing (default 50)
        cooldown: ticks between heals (default 3)
        ally_tags: tags marking allies (default ['player'])
    """

    behavior_id = "healer"

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, obj: GameObject, delta: float) -> None:
        wait = int(obj.db.get('healer_wait') or 0)
        if wait > 0:
            obj.db.healer_wait = wait - 1
            return

        if obj.location is None:
            return
        threshold = int(self.get_param('heal_threshold', 50))
        ally_tags = self.get_param('ally_tags', ['player'])

        for other in obj.location.contents:
            if other is obj:
                continue
            if not any(other.has_tag(tag) for tag in ally_tags):
                continue
            hp = other.db.get('hp')
            max_hp = other.db.get('max_hp')
            if hp is None or max_hp is None or int(max_hp) <= 0:
                continue
            if 100 * int(hp) / int(max_hp) >= threshold:
                continue

            heal = int(self.get_param('heal_amount', 5))
            other.db.hp = min(int(max_hp), int(hp) + heal)
            other.msg(f"{obj.name} tends your wounds (+{heal} HP).")
            if obj.location:
                obj.location.msg_contents(
                    f"{obj.name} tends {other.name}'s wounds.",
                    exclude=[other],
                )
            obj.db.healer_wait = int(self.get_param('cooldown', 3))
            break


@BehaviorRegistry.register
class CombatantBehavior(Behavior):
    """
    Combat flavor: last words on death.

    Parameters:
        death_message: line announced to the room when this one falls.
    """

    behavior_id = "combatant"

    async def on_react(self, obj: GameObject, action: Action) -> None:
        if action.action_type != "combat:on_death" or action.target is not obj:
            return
        death_msg = self.get_param('death_message')
        if death_msg and obj.location is not None:
            obj.location.msg_contents(str(death_msg))


@BehaviorRegistry.register
class WanderingBehavior(Behavior):
    """
    Roams through random open exits.

    Parameters:
        wander_chance: probability of moving on each check (default 0.25)
        pause: ticks between wander checks (default 7 ≈ 30s at 4s ticks)
        avoid_tags: destination-room tags never entered (default
            ['no_wander']); wanderers also never leave their zone if
            stay_in_zone is set.
        stay_in_zone: keep to rooms sharing the owner's zone: tag
            (default True).
    """

    behavior_id = "wandering"

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, obj: GameObject, delta: float) -> None:
        if obj.has_tag('in_combat') or obj.location is None:
            return

        wait = int(obj.db.get('wander_wait') or 0)
        if wait > 0:
            obj.db.wander_wait = wait - 1
            return
        obj.db.wander_wait = int(self.get_param('pause', 7))

        if random.random() > float(self.get_param('wander_chance', 0.25)):
            return

        from realm.core.movement import move_through_exit, resolve_exit_destination

        avoid = set(self.get_param('avoid_tags', ['no_wander']))
        my_zones = {t for t in obj.location.tags.to_list() if t.startswith('zone:')}
        stay_in_zone = bool(self.get_param('stay_in_zone', True))

        candidates = []
        for exit_obj in obj.location.contents:
            if not exit_obj.has_tag('exit') or exit_obj.has_tag('closed'):
                continue
            destination = resolve_exit_destination(exit_obj)
            if destination is None:
                continue
            if any(destination.has_tag(tag) for tag in avoid):
                continue
            if stay_in_zone and my_zones:
                dest_zones = {t for t in destination.tags.to_list()
                              if t.startswith('zone:')}
                if not (my_zones & dest_zones):
                    continue
            candidates.append((exit_obj, destination))

        if not candidates:
            return
        exit_obj, destination = random.choice(candidates)
        await move_through_exit(obj, destination, exit_obj=exit_obj)
