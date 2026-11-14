"""
Timed effects as tickable behaviors: bleeding, poison, regeneration.

An effect IS a behavior — attached at runtime (by combat, softcode, a
trapped chest, a venomous bite), advancing on **beats** (not the real-time
heartbeat: see ``realm.core.beats`` and docs/design/time-and-beats.md), and
detaching itself when it expires. A beat is the encounter's adjustable round
while its owner is fighting and the ambient the ``WORLD_BEAT`` setting otherwise, so
slowing a fight slows its poisons in lockstep. Because behaviors serialize
through the BehaviorRegistry, a poisoned character is still poisoned after a
reboot, with the remaining duration (in beats) intact in ``db.*``.

    victim.add_behavior(DamageOverTimeBehavior(
        kind="poison", damage=1, interval=2, duration=10,
        tick_msg="Venom burns through your veins!",
    ))

Effects that spend a combat-capable object's vital pool route through the
CombatManager's defeat handling (players fall unconscious, NPCs die
into corpses) — a poisoning is as real as a sword.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.core.beats import BeatBehavior
from realm.core.pools import (
    damage_pool,
    harm,
    is_spent,
    mend,
    pool_get,
    pool_max,
    settle,
    vital_pool,
)
from realm.core.world import get_world

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


def state_key(kind: str, suffix: str) -> str:
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
    param_spec = {
        'kind': (None, 'the condition name, mirrored as a tag (default: the behavior id)'),
        'duration': (15, 'beats until the effect expires (0 = permanent)'),
        'interval': (1, 'beats between pulses'),
        'jitter': (True, 'randomize the first pulse of a multi-beat interval'),
        'check_mods': (None, 'check modifiers held while active, e.g. {"all": -2}'),
        'expire_msg': (None, 'line shown to the bearer when it wears off'),
        'source_id': (None, 'id of whoever applied it (apply_effect stamps this)'),
    }

    @property
    def kind(self) -> str:
        return str(self.get_param('kind', self.behavior_id))

    def _source(self) -> GameObject | None:
        """Whoever applied this effect, if still around.

        ``apply_effect`` stamps ``source_id`` with its executor, so a kill
        arriving by poison tick rather than by swing can still name a
        killer. Without it, a bounty board hears the death and has nobody
        to pay, and an arena bell roars that "" put someone down.
        """

        source_id = self.get_param('source_id')
        if not source_id:
            return None
        persistence = get_world().store
        if persistence is None:
            return None
        return persistence.get_cached(str(source_id))

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
        wait_key = state_key(self.kind, 'wait')
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
            left = obj.db.get(state_key(self.kind, 'left'))
            left = duration if left is None else int(left)
            left -= 1
            if left <= 0:
                await self._expire(obj)
                return
            obj.db.set(state_key(self.kind, 'left'), left)

        wait = int(obj.db.get(state_key(self.kind, 'wait')) or 0)
        if wait > 0:
            obj.db.set(state_key(self.kind, 'wait'), wait - 1)
            return
        obj.db.set(state_key(self.kind, 'wait'),
                   max(0, int(self.get_param('interval', 1)) - 1))
        await self.pulse(obj)

    async def pulse(self, obj: GameObject) -> None:
        """Override: the effect's periodic work."""

    def clear_state(self, obj: GameObject) -> None:
        """Delete this effect's per-kind **timer** keys (left/wait).

        Called when the effect expires or is replaced by a fresh application
        of the same kind, so a refresh restarts from full duration rather than
        inheriting the old countdown. Deliberately does NOT touch side-effect
        flags (e.g. ``disposition_boost``'s ``applied``): those must survive a
        refresh so a re-cast doesn't double- or un-apply the effect's delta.
        """
        obj.db.delete(state_key(self.kind, 'left'))
        obj.db.delete(state_key(self.kind, 'wait'))

    async def _expire(self, obj: GameObject) -> None:
        self.clear_state(obj)
        expire_msg = self.get_param('expire_msg')
        if expire_msg:
            obj.msg(str(expire_msg))
        obj.remove_behavior(self)


class DamageOverTimeBehavior(TimedEffectBehavior):
    """
    Bleeding, poison, burning: periodic damage until it expires.

    Params (plus TimedEffectBehavior's): damage (int per pulse),
    tick_msg / room_msg (narration), kind defaults to "bleeding".
    """

    behavior_id = "damage_over_time"
    param_spec = {
        'kind': ('bleeding', 'the condition name, mirrored as a tag'),
        'damage': (1, 'harm to the damage pool (hp) per pulse'),
        'damage_type': (None, 'damage type routed through resistances '
                              '(e.g. "poison"); None = raw HP loss'),
        'room_msg': (None, 'room line on each pulse'),
    }

    @property
    def kind(self) -> str:
        return str(self.get_param('kind', 'bleeding'))

    async def pulse(self, obj: GameObject) -> None:
        if obj.has_tag('unconscious'):
            return  # mercy: the downed don't bleed out in v1
        pool = damage_pool(obj)
        if pool is None:
            return
        damage = int(self.get_param('damage', 1))
        dtype = self.get_param('damage_type')
        # Typed damage routes through resistances so a poison-immune target
        # takes 0 (DoT is real typed damage). The damage service
        # (``combat``) applies resistances; without it the damage lands
        # untyped.
        dmg = get_world().services.get("damage") if dtype else None
        if dmg is not None:
            change = dmg.apply_resisted(obj, damage, str(dtype))
            damage = change.requested       # after resistances
            if damage <= 0:
                return                      # fully resisted: nothing to narrate
        else:
            change = harm(obj, pool, damage, soak=True)

        obj.msg(self.get_param(
            'tick_msg', f"You are wracked by {self.kind} ({damage} damage)!",
        ))
        room = obj.location
        if room is not None:
            room_msg = self.get_param('room_msg')
            if room_msg:
                room.msg_contents(str(room_msg).replace('{name}', obj.name),
                                  exclude=[obj])

        spent = is_spent(obj, vital_pool(obj))
        if spent:
            await self._expire(obj)
        # Settling after the narration runs combat's observers: a spent vital
        # pool dies through the combat manager, naming the poisoner (the
        # death event is worthless to a bounty board if the killer is None),
        # and a fall through ``hitprcnt`` fires ON_HITPRCNT.
        await settle(change, source=self._source())
        if spent and obj.is_player and get_world().services.get("combat") is None:
            obj.add_tag('unconscious')
            obj.msg("Everything goes black...")


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
    param_spec = {
        'kind': ('shaken', 'the condition name, mirrored as a tag'),
        'apply_msg': (None, 'line shown to the bearer on attach'),
    }

    @property
    def kind(self) -> str:
        return str(self.get_param('kind', 'shaken'))

    def attach(self, obj: GameObject) -> None:
        super().attach(obj)
        apply_msg = self.get_param('apply_msg')
        if apply_msg:
            obj.msg(str(apply_msg))




class RegenerationBehavior(TimedEffectBehavior):
    """
    Periodic healing (a medkit's afterglow, trollish vitality).

    Params: heal (int per pulse, default 1); duration 0 = innate/permanent.
    """

    behavior_id = "regeneration"
    param_spec = {
        'kind': ('regenerating', 'the condition name, mirrored as a tag'),
        'heal': (1, 'mended into the damage pool (hp) per pulse'),
    }

    @property
    def kind(self) -> str:
        return str(self.get_param('kind', 'regenerating'))

    async def pulse(self, obj: GameObject) -> None:
        pool = damage_pool(obj)
        hp = pool_get(obj, pool) if pool else None
        max_hp = pool_max(obj, pool) if pool else None
        if hp is None or max_hp is None:
            return
        if hp >= max_hp or obj.has_tag('unconscious'):
            return
        await settle(mend(obj, pool, int(self.get_param('heal', 1))),
                     source=self._source())




__all__ = [
    "TimedEffectBehavior",
    "DamageOverTimeBehavior",
    "ModifierEffectBehavior",
    "RegenerationBehavior",
]
