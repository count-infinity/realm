"""
Timed effects as tickable behaviors: bleeding, poison, regeneration.

An effect IS a behavior — attached at runtime (by combat, softcode, a
trapped chest, a venomous bite), ticking on the server heartbeat, and
detaching itself when it expires. Because behaviors serialize through
the BehaviorRegistry, a poisoned character is still poisoned after a
reboot, with the remaining duration intact in ``db.*``.

    victim.add_behavior(DamageOverTimeBehavior(
        kind="poison", damage=1, interval=2, duration=10,
        tick_msg="Venom burns through your veins!",
    ))

Effects that reduce a combat-capable object to 0 HP route through the
CombatManager's defeat handling (players fall unconscious, NPCs die
into corpses) — a poisoning is as real as a sword.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior, BehaviorRegistry

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


def _state_key(kind: str, suffix: str) -> str:
    return f"effect_{kind}_{suffix}"


class TimedEffectBehavior(Behavior):
    """
    Base for expiring effects.

    Params:
        kind (str): effect name ("bleeding", "poison", "regen"...); also
            mirrored as a tag on the owner while active, so perception,
            locks, strategies (``me`` views later) and softcode can see it.
        interval (int): ticks between pulses (default 1 = every tick).
        duration (int): total ticks before the effect expires
            (default 15 ≈ one minute at 4s ticks). 0 = permanent.
        expire_msg (str): message to the owner when it wears off.

    State lives in owner.db (persists): effect_<kind>_left,
    effect_<kind>_wait.
    """

    behavior_id = "timed_effect"

    @property
    def should_tick(self) -> bool:
        return True

    @property
    def kind(self) -> str:
        return str(self.get_param('kind', self.behavior_id))

    def attach(self, obj: GameObject) -> None:
        super().attach(obj)
        obj.add_tag(self.kind)

    def detach(self, obj: GameObject) -> None:
        obj.remove_tag(self.kind)
        super().detach(obj)

    async def tick(self, obj: GameObject, delta: float) -> None:
        duration = int(self.get_param('duration', 15))
        if duration > 0:
            left = obj.db.get(_state_key(self.kind, 'left'))
            left = duration if left is None else int(left)
            left -= 1
            if left <= 0:
                await self._expire(obj)
                return
            obj.db.set(_state_key(self.kind, 'left'), left)

        wait = int(obj.db.get(_state_key(self.kind, 'wait')) or 0)
        if wait > 0:
            obj.db.set(_state_key(self.kind, 'wait'), wait - 1)
            return
        obj.db.set(_state_key(self.kind, 'wait'),
                   max(0, int(self.get_param('interval', 1)) - 1))
        await self.pulse(obj)

    async def pulse(self, obj: GameObject) -> None:
        """Override: the effect's periodic work."""

    async def _expire(self, obj: GameObject) -> None:
        obj.db.delete(_state_key(self.kind, 'left'))
        obj.db.delete(_state_key(self.kind, 'wait'))
        expire_msg = self.get_param('expire_msg')
        if expire_msg:
            obj.msg(str(expire_msg))
        obj.remove_behavior(self)


@BehaviorRegistry.register
class DamageOverTimeBehavior(TimedEffectBehavior):
    """
    Bleeding, poison, burning: periodic damage until it expires.

    Params (plus TimedEffectBehavior's): damage (int per pulse),
    tick_msg / room_msg (narration), kind defaults to "bleeding".
    """

    behavior_id = "damage_over_time"

    @property
    def kind(self) -> str:
        return str(self.get_param('kind', 'bleeding'))

    async def pulse(self, obj: GameObject) -> None:
        if obj.has_tag('unconscious'):
            return  # mercy: the downed don't bleed out in v1
        hp = obj.db.get('hp')
        if hp is None:
            return
        damage = int(self.get_param('damage', 1))
        new_hp = max(0, int(hp) - damage)
        obj.db.hp = new_hp

        obj.msg(self.get_param(
            'tick_msg', f"You are wracked by {self.kind} ({damage} damage)!",
        ))
        room = obj.location
        if room is not None:
            room_msg = self.get_param('room_msg')
            if room_msg:
                room.msg_contents(str(room_msg).replace('{name}', obj.name),
                                  exclude=[obj])

        if new_hp <= 0:
            await self._expire(obj)
            from realm.combat.manager import get_combat_manager
            manager = get_combat_manager()
            if manager is not None:
                await manager.handle_death(obj)
            elif obj.has_tag('player'):
                obj.add_tag('unconscious')
                obj.msg("Everything goes black...")


@BehaviorRegistry.register
class RegenerationBehavior(TimedEffectBehavior):
    """
    Periodic healing (a medkit's afterglow, trollish vitality).

    Params: heal (int per pulse, default 1); duration 0 = innate/permanent.
    """

    behavior_id = "regeneration"

    @property
    def kind(self) -> str:
        return str(self.get_param('kind', 'regenerating'))

    async def pulse(self, obj: GameObject) -> None:
        hp = obj.db.get('hp')
        max_hp = obj.db.get('max_hp')
        if hp is None or max_hp is None:
            return
        if int(hp) >= int(max_hp) or obj.has_tag('unconscious'):
            return
        heal = int(self.get_param('heal', 1))
        obj.db.hp = min(int(max_hp), int(hp) + heal)


__all__ = ["TimedEffectBehavior", "DamageOverTimeBehavior", "RegenerationBehavior"]
