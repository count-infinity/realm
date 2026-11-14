"""
The ``social`` feature's behaviors: a timed disposition boost.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.world import get_world
from realm.std.effects.behaviors import TimedEffectBehavior, state_key

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class DispositionBoostBehavior(TimedEffectBehavior):
    """
    A temporary opinion: fast-talk wears off.

    Attached to the NPC whose mind was changed; on expiry the boost is
    reversed — the guard who waved you through starts wondering why.

    Params: target_id (whose standing changes), delta (default +2),
    duration ticks, plus TimedEffectBehavior's kind/expire_msg.
    """

    behavior_id = "disposition_boost"
    param_spec = {
        'target_id': ('', 'id of whose opinion is swayed'),
        'delta': (2, 'disposition shift while active (reversed on expiry)'),
    }

    @property
    def kind(self) -> str:
        # Unique per target so two con artists don't collide.
        return str(self.get_param(
            'kind', f"swayed_{str(self.get_param('target_id', ''))[:8]}"))

    def attach(self, obj: GameObject) -> None:
        super().attach(obj)
        # Applied-flag lives in owner.db (behaviors are stateless logic;
        # a reboot re-attach must not re-apply the delta).
        flag = state_key(self.kind, 'applied')
        if not obj.db.get(flag):
            obj.db.set(flag, True)
            target = self._target(obj)
            if target is not None:
                from realm.std.social.disposition import adjust_disposition
                adjust_disposition(obj, target, int(self.get_param('delta', 2)))

    def _target(self, obj: GameObject) -> GameObject | None:

        target_id = self.get_param('target_id')
        if not target_id:
            return None
        persistence = get_world().store
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
            from realm.std.social.disposition import adjust_disposition
            adjust_disposition(obj, target, -int(self.get_param('delta', 2)))
        obj.db.delete(state_key(self.kind, 'applied'))
        await super()._expire(obj)
