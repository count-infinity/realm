"""
Timed effects as tickable behaviors: bleeding, poison, regeneration.

An effect IS a behavior — attached at runtime (by combat, softcode, a
trapped chest, a venomous bite), advancing on **beats** (not the real-time
heartbeat: see ``realm.core.beats`` and docs/design/time-and-beats.md), and
detaching itself when it expires. A beat is the encounter's adjustable round
while its owner is fighting and the ambient ``WORLD_TICK`` otherwise, so
slowing a fight slows its poisons in lockstep. Because behaviors serialize
through the BehaviorRegistry, a poisoned character is still poisoned after a
reboot, with the remaining duration (in beats) intact in ``db.*``.

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

from realm.core.beats import BeatBehavior
from realm.core.behaviors import BehaviorRegistry

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


def _state_key(kind: str, suffix: str) -> str:
    return f"effect_{kind}_{suffix}"


class TimedEffectBehavior(BeatBehavior):
    """
    Base for expiring effects — a **beat**-driven behavior (see
    ``realm.core.beats``). It advances one beat at a time: the encounter's
    beat while its owner is fighting, the ambient beat otherwise. Slow the
    fight and the poison slows with it.

    Params:
        kind (str): effect name ("bleeding", "poison", "regen"...); also
            mirrored as a tag on the owner while active, so perception,
            locks, strategies (``me`` views later) and softcode can see it.
        interval (int): beats between pulses (default 1 = every beat).
        duration (int): total beats (= rounds) before the effect expires
            (default 15). 0 = permanent.
        expire_msg (str): message to the owner when it wears off.

    State lives in owner.db (persists): effect_<kind>_left,
    effect_<kind>_wait.
    """

    behavior_id = "timed_effect"

    @property
    def kind(self) -> str:
        return str(self.get_param('kind', self.behavior_id))

    def attach(self, obj: GameObject) -> None:
        super().attach(obj)
        obj.add_tag(self.kind)
        # Phase jitter: multi-beat effects (interval > 1) seed a random initial
        # wait in [0, interval-1] so a roomful of poisoned NPCs don't all pulse
        # on the same beat. Per-beat effects (interval 1, the combat default)
        # get no jitter and thus exact, unchanged pulse counts. Opt out with
        # jitter=False for a deterministic phase. Seeded ONCE (only when the
        # key is absent) so a reboot re-attach keeps the original phase, not a
        # fresh roll.
        interval = int(self.get_param('interval', 1))
        wait_key = _state_key(self.kind, 'wait')
        if (interval > 1 and self.get_param('jitter', True)
                and obj.db.get(wait_key) is None):
            import random
            obj.db.set(wait_key, random.randint(0, interval - 1))
        # Any timed effect can carry check modifiers ("blinding poison"):
        # its entry in db.check_mods lives exactly as long as the effect.
        check_mods = self.get_param('check_mods')
        if check_mods is not None:
            mods = dict(obj.db.get('check_mods') or {})
            mods[self.kind] = check_mods
            obj.db.check_mods = mods

    def detach(self, obj: GameObject) -> None:
        obj.remove_tag(self.kind)
        mods = obj.db.get('check_mods')
        if isinstance(mods, dict) and self.kind in mods:
            mods = dict(mods)
            del mods[self.kind]
            if mods:
                obj.db.check_mods = mods
            else:
                obj.db.delete('check_mods')
        super().detach(obj)

    async def on_beat(self, obj: GameObject) -> None:
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
class ModifierEffectBehavior(TimedEffectBehavior):
    """
    A pure condition: no pulses, just check modifiers for a while.

    The banshee wail: fear that gives -2 to every roll until it wears
    off. The modifier plumbing lives in TimedEffectBehavior (any effect
    can carry ``check_mods``); this class is the named, softcode-friendly
    "just a debuff/buff" shape.

        victim.add_behavior(ModifierEffectBehavior(
            kind="fear", duration=8, check_mods={"all": -2},
            apply_msg="Terror grips you!", expire_msg="Your nerve returns.",
        ))

    Params (plus TimedEffectBehavior's): check_mods (dict of skill->mod,
    'all' for everything, or a bare int), apply_msg.
    """

    behavior_id = "modifier_effect"

    @property
    def kind(self) -> str:
        return str(self.get_param('kind', 'shaken'))

    def attach(self, obj: GameObject) -> None:
        super().attach(obj)
        apply_msg = self.get_param('apply_msg')
        if apply_msg:
            obj.msg(str(apply_msg))


@BehaviorRegistry.register
class DispositionBoostBehavior(TimedEffectBehavior):
    """
    A temporary opinion: fast-talk wears off.

    Attached to the NPC whose mind was changed; on expiry the boost is
    reversed — the guard who waved you through starts wondering why.

    Params: target_id (whose standing changes), delta (default +2),
    duration ticks, plus TimedEffectBehavior's kind/expire_msg.
    """

    behavior_id = "disposition_boost"

    @property
    def kind(self) -> str:
        # Unique per target so two con artists don't collide.
        return str(self.get_param(
            'kind', f"swayed_{str(self.get_param('target_id', ''))[:8]}"))

    def attach(self, obj: GameObject) -> None:
        super().attach(obj)
        # Applied-flag lives in owner.db (behaviors are stateless logic;
        # a reboot re-attach must not re-apply the delta).
        flag = _state_key(self.kind, 'applied')
        if not obj.db.get(flag):
            obj.db.set(flag, True)
            target = self._target(obj)
            if target is not None:
                from realm.core.disposition import adjust_disposition
                adjust_disposition(obj, target, int(self.get_param('delta', 2)))

    def _target(self, obj: GameObject) -> GameObject | None:
        from realm.persistence.manager import get_active_manager

        target_id = self.get_param('target_id')
        if not target_id:
            return None
        persistence = get_active_manager()
        if persistence is not None:
            found = persistence.get_cached(str(target_id))
            if found is not None:
                return found
        room = obj.location
        if room is not None:
            for other in room.contents:
                if other.id == target_id:
                    return other
        return None

    async def _expire(self, obj: GameObject) -> None:
        target = self._target(obj)
        if target is not None:
            from realm.core.disposition import adjust_disposition
            adjust_disposition(obj, target, -int(self.get_param('delta', 2)))
        obj.db.delete(_state_key(self.kind, 'applied'))
        await super()._expire(obj)


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


__all__ = [
    "TimedEffectBehavior",
    "DamageOverTimeBehavior",
    "DispositionBoostBehavior",
    "ModifierEffectBehavior",
    "RegenerationBehavior",
]
