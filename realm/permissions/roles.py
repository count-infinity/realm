"""
Role hierarchy for REALM.

Defines privilege levels:
    God (superuser) → bypasses everything
      ↓
    Admin (wizard) → bypasses most locks, can modify any object
      ↓
    Builder (staff) → can build, limited lock bypass
      ↓
    Player → subject to all locks
      ↓
    Guest → restricted, no building, limited commands

Role is determined by tags on the player object:
- 'god' tag → God role
- 'admin' tag → Admin role
- 'builder' tag → Builder role
- 'guest' tag → Guest role
- Otherwise → Player role
"""

from __future__ import annotations

from enum import IntEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class Role(IntEnum):
    """
    Permission levels in ascending order of privilege.

    Higher values have more privileges. This allows simple numeric comparisons:
    if actor_role >= Role.BUILDER: ...
    """

    GUEST = 0
    PLAYER = 1
    BUILDER = 2
    ADMIN = 3
    GOD = 4


# Role tag names (lowercase)
ROLE_TAGS = {
    'god': Role.GOD,
    'admin': Role.ADMIN,
    'wizard': Role.ADMIN,  # Alias
    'builder': Role.BUILDER,
    'staff': Role.BUILDER,  # Alias
    'guest': Role.GUEST,
}

# Permission levels required for various actions
PERMISSION_LEVELS = {
    'guest': Role.GUEST,
    'player': Role.PLAYER,
    'builder': Role.BUILDER,
    'admin': Role.ADMIN,
    'god': Role.GOD,
}


def get_role(obj: GameObject | None) -> Role:
    """
    Determine the role of an object (typically a player).

    Checks tags in order of highest privilege first.

    Args:
        obj: The object to check (None returns GUEST)

    Returns:
        The Role enum value
    """
    if obj is None:
        return Role.GUEST

    # A quelled admin voluntarily acts as a mortal (Evennia-style) — for
    # honest testing of perception (dark/hidden/invisible) and authority.
    if obj.has_tag('quelled'):
        return Role.PLAYER

    # Check tags in order of highest privilege
    if obj.has_tag('god'):
        return Role.GOD
    if obj.has_tag('admin') or obj.has_tag('wizard'):
        return Role.ADMIN
    if obj.has_tag('builder') or obj.has_tag('staff'):
        return Role.BUILDER
    if obj.has_tag('guest'):
        return Role.GUEST

    # Players and NPCs are full citizens of the command layer — a
    # forced/possessed NPC may run player-level commands (never builder+).
    if obj.has_tag('player') or obj.has_tag('npc'):
        return Role.PLAYER

    # Other objects default to GUEST level
    return Role.GUEST


def has_permission(actor: GameObject | None, permission: str) -> bool:
    """
    Check if an actor has a specific permission level.

    Args:
        actor: The object trying to perform the action
        permission: Permission name (guest, player, builder, admin, god)

    Returns:
        True if actor's role >= required permission level
    """
    actor_role = get_role(actor)
    required_level = PERMISSION_LEVELS.get(permission.lower(), Role.PLAYER)
    return actor_role >= required_level








# NOTE (simplicity review 2026-07-05): the former can_control/can_examine
# helpers were a second, DISAGREEING authority layer with zero runtime
# callers. realm.permissions.locks.controls() is the one predicate.
