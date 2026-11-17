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

from realm.core.action_types import ActionType
from realm.core.behaviors import Behavior, BehaviorRegistry
from realm.core.markup import capitalize
from realm.core.perception import can_see
from realm.core.pools import damage_pool, mend, pool_get, pool_max, settle
from realm.core.world import get_world
from realm.std.combat.actions import CombatAction

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action


async def _say(npc: GameObject, text: str) -> None:
    """The NPC speaks, when the world has ``talk`` (``services["talk"]``)."""
    talk = get_world().services.get("talk")
    if talk is not None:
        await talk.npc_say(npc, text)


def _combat_manager():
    return get_world().services.get("combat")


def _ensure_strategy_rule(obj: GameObject, condition: str, action: str) -> None:
    """Prepend a strategy rule if an equivalent one isn't present."""
    rules = list(obj.db.get('combat_strategy') or [])
    if any(str(rule[0]) == condition for rule in rules if rule):
        return
    rules.insert(0, [condition, action])
    obj.db.combat_strategy = rules


class AggressiveBehavior(Behavior):
    """
    Attacks valid targets on sight (they enter, or it wanders in on them).

    Parameters:
        attack_chance: probability of engaging (0.0-1.0, default 1.0)
        target_tags: tags marking valid prey (default ['player'])
        taunt: line said when engaging (optional)
    """

    behavior_id = "aggressive"
    param_spec = {
        'target_tags': (['player'], 'tags marking who to attack on sight'),
        'spare_at': (2, 'disposition at or above which a target is spared'),
        'attack_chance': (1.0, 'probability per sighting that it attacks'),
        'taunt': (None, 'line said when moving to attack'),
    }

    async def on_react(self, obj: GameObject, action: Action) -> None:
        entering = action.actor
        if action.action_type != ActionType.ON_ENTER or entering is None:
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
        # A companion (``companions``' ``master``) fights beside its master
        # or on its orders, not on sight (ROM: charmed mobs are not aggressive).
        if obj.db.get('master'):
            return

        target_tags = self.get_param('target_tags', ['player'])
        if not any(target.has_tag(tag) for tag in target_tags):
            return
        # Even a monster spares those it's devoted to (spare_at=None disables).
        spare_at = self.get_param('spare_at', 2)
        if spare_at is not None:
            social = get_world().services.get("social")
            if social is not None and social.get_disposition(obj, target) >= int(spare_at):
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
            await _say(obj, str(taunt))

        await manager.initiate(obj, target)


class DefensiveBehavior(Behavior):
    """
    Fights back only when attacked (the encounter engine's defender
    auto-join already does the joining); flees when badly hurt.

    Parameters:
        flee_percent: HP percentage to flee below (default 25).
    """

    behavior_id = "defensive"
    param_spec = {
        'flee_percent': (25, 'HP percent below which it tries to flee'),
    }

    def attach(self, obj: GameObject) -> None:
        super().attach(obj)
        flee_percent = int(self.get_param('flee_percent', 25))
        _ensure_strategy_rule(obj, f"!me.hp_percent < {flee_percent}", "flee")


class FleeingBehavior(Behavior):
    """
    A coward's reflex: flee combat below an HP threshold. Implemented as
    an override strategy rule — the same wimpy players get.

    Parameters:
        flee_percent: HP percentage to flee below (default 50).
    """

    behavior_id = "fleeing"
    param_spec = {
        'flee_percent': (50, 'HP percent below which it tries to flee'),
    }

    def attach(self, obj: GameObject) -> None:
        super().attach(obj)
        flee_percent = int(self.get_param('flee_percent', 50))
        _ensure_strategy_rule(obj, f"!me.hp_percent < {flee_percent}", "flee")




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
    param_spec = {
        'heal_threshold': (50, 'ally HP percent that triggers a heal'),
        'ally_tags': (['player'], 'tags marking who counts as an ally'),
        'heal_amount': (5, 'HP restored per heal'),
        'cooldown': (3, 'world beats between heals'),
    }

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, obj: GameObject, delta: float) -> None:
        # healer_wait re-arms only after a successful heal (below).
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
            pool = damage_pool(other)
            hp = pool_get(other, pool) if pool else None
            max_hp = pool_max(other, pool) if pool else None
            if hp is None or max_hp is None or max_hp <= 0:
                continue
            if 100 * hp / max_hp >= threshold:
                continue

            heal = int(self.get_param('heal_amount', 5))
            await settle(mend(other, pool, heal), source=obj)
            other.msg(capitalize(f"{obj.name} tends your wounds (+{heal} HP)."))
            if obj.location:
                obj.location.msg_contents(
                    f"{obj.name} tends {other.name}'s wounds.",
                    exclude=[other],
                )
            obj.db.healer_wait = int(self.get_param('cooldown', 3))
            break


class CombatantBehavior(Behavior):
    """
    Combat flavor: last words on death.

    Parameters:
        death_message: line announced to the room when this one falls.
    """

    behavior_id = "combatant"
    param_spec = {
        'death_message': (None, 'line emitted to the room on death'),
    }

    async def on_react(self, obj: GameObject, action: Action) -> None:
        if action.action_type != CombatAction.ON_DEATH or action.target is not obj:
            return
        death_msg = self.get_param('death_message')
        if death_msg and obj.location is not None:
            obj.location.msg_contents(str(death_msg))




class VenomousBehavior(Behavior):
    """
    Envenoms a victim on a landed hit (ROM spec_poison, a poisoned fang).

    Reacts to this mob's own ``combat:on_damage``: on a chance roll, and
    unless the victim saves or is poison-immune, it applies a ``poison``
    damage-over-time whose ticks route through the damage path — so poison
    resistance and immunity apply exactly as they do to a direct hit
    (immunity vetoes the poison at application, the CoffeeMud way).

    Params:
        chance (float): probability of envenoming on a landed hit (0.5).
        damage (int): poison damage per tick (2).
        duration (int): poison duration in beats (24).
        interval (int): beats between poison ticks (4).
        save (bool): a failed saving throw is required to poison (True).
    """

    behavior_id = "venomous"
    param_spec = {
        'chance': (0.5, 'probability of envenoming on a landed hit'),
        'damage': (2, 'poison damage per tick'),
        'duration': (24, 'poison duration in beats'),
        'interval': (4, 'beats between poison ticks'),
        'save': (True, 'a failed saving throw is required to poison'),
    }

    async def on_react(self, obj: GameObject, action: Action) -> None:
        if action.action_type != CombatAction.ON_DAMAGE or action.actor is not obj:
            return
        if action.blocked:
            return
        target = action.target
        if target is None or target is obj:
            return
        if int(action.extra.get('damage', 0) or 0) <= 0:
            return                                  # the blow did not land
        if random.random() > float(self.get_param('chance', 0.5)):
            return
        # Immune? (poison resistance 0) — veto at application, no dead effect.
        resist = target.db.get('resistances')
        if isinstance(resist, dict) and float(resist.get('poison', 1.0)) == 0:
            return
        if self.get_param('save', True):
            system = get_world().rules
            level = int(obj.db.get('level') or 1)
            if system is not None and system.saving_throw(target, level):
                target.msg("You fight off the venom.")
                return
        poison = BehaviorRegistry.create(
            'damage_over_time', kind='poisoned',
            damage=int(self.get_param('damage', 2)),
            duration=int(self.get_param('duration', 24)),
            interval=int(self.get_param('interval', 4)),
            damage_type='poison',
            tick_msg="Venom courses through your veins!",
            room_msg="{name} shudders, poisoned.")
        if poison is not None:
            target.add_behavior(poison)
            target.msg("You are poisoned!")

