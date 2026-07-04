"""
DecayBehavior: things that crumble away after a while (corpses,
campfires, conjured items). Contents spill to the room first.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from realm.core.behaviors import Behavior, BehaviorRegistry

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


@BehaviorRegistry.register
class DecayBehavior(Behavior):
    """
    Destroy the owner after N ticks, spilling contents to the room.

    Params:
        ticks (int): server ticks until decay (default 150 ≈ 10 min at 4s).
        decay_msg (str): room message on decay.

    Countdown state lives in owner.db.decay_left (persists; a corpse
    keeps rotting across reboots).
    """

    behavior_id = "decay"

    @property
    def should_tick(self) -> bool:
        return True

    async def tick(self, obj: GameObject, delta: float) -> None:
        left = obj.db.get('decay_left')
        if left is None:
            left = int(self.get_param('ticks', 150))
        left = int(left) - 1
        if left > 0:
            obj.db.decay_left = left
            return

        room = obj.location
        for item in list(obj.contents):
            item.location = room
        if room is not None:
            room.msg_contents(
                self.get_param('decay_msg', f"{obj.name} crumbles away."),
            )
        obj.location = None

        from realm.persistence.manager import get_active_manager
        persistence = get_active_manager()
        if persistence is not None:
            await persistence.delete(obj)


__all__ = ["DecayBehavior"]
