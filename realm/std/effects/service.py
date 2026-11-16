"""
What the ``effects`` feature offers other features, as
``world.services["effects"]``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.std.effects.behaviors import TimedEffectBehavior

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def clear(obj: GameObject) -> int:
    """End every timed effect on ``obj`` (its condition tags and check
    modifiers go with them). Returns how many were removed."""
    ended = [b for b in obj.get_behaviors() if isinstance(b, TimedEffectBehavior)]
    for behavior in ended:
        obj.remove_behavior(behavior)
    return len(ended)


__all__ = ["clear"]
