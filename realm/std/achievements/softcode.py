"""
Softcode functions: achievements. The ``achievements`` feature declares
each; the first parameter is the run's frame.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.std.achievements.achievements import definition, has

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def grant_achievement(frame, obj: GameObject | str | None, name: str) -> bool:
    """
    Award an achievement (an ``achievement_def``) to a character, once:
    recorded on its account (or on the character, for ``scope =
    character``), announced to the player, its grants applied, and
    ``account:on_achievement`` fired. False when there is no such
    achievement or it is already earned. Queued; it lands after the script.

    Example: grant_achievement(enactor, 'Banshee Slayer')
    """
    target = frame.resolve(obj)
    adef = definition(str(name))
    if target is None or not target.is_player or adef is None or has(target, adef.name):
        return False
    frame.command_queue.append(('achievement', target, adef.name))
    return True


def has_achievement(frame, obj: GameObject | str | None, name: str) -> bool:
    """
    Has the character (or its account) earned the achievement?

    Example: has_achievement(enactor, 'Banshee Slayer')
    """
    target = frame.resolve(obj)
    return target is not None and has(target, str(name))


__all__ = ["grant_achievement", "has_achievement"]
