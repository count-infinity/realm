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

    # Check tags in order of highest privilege
    if obj.has_tag('god'):
        return Role.GOD
    if obj.has_tag('admin') or obj.has_tag('wizard'):
        return Role.ADMIN
    if obj.has_tag('builder') or obj.has_tag('staff'):
        return Role.BUILDER
    if obj.has_tag('guest'):
        return Role.GUEST

    # Default for non-guest players
    if obj.has_tag('player'):
        return Role.PLAYER

    # Non-player objects default to GUEST level
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


def can_control(actor: GameObject | None, target: GameObject | None) -> bool:
    """
    Check if actor can control (modify) target.

    Control rules:
    1. God can control anything
    2. Admin can control anything except God-owned objects
    3. Owner can control their own objects
    4. Objects with a 'control' lock must pass the lock check
    5. Zone controllers can control objects in their zone

    Args:
        actor: The object trying to control
        target: The object being controlled

    Returns:
        True if actor can control target
    """
    if actor is None or target is None:
        return False

    actor_role = get_role(actor)

    # God controls everything
    if actor_role >= Role.GOD:
        return True

    # Admin controls everything except God-owned
    if actor_role >= Role.ADMIN:
        if target.owner and target.owner.has_tag('god'):
            return False
        return True

    # Owner controls their own objects
    if target.owner and target.owner.id == actor.id:
        return True

    # Check for control lock (evaluated elsewhere)
    # This function just handles the basic hierarchy

    return False


def can_examine(actor: GameObject | None, target: GameObject | None) -> bool:
    """
    Check if actor can examine (see details of) target.

    Examine rules:
    1. Can always examine if you control it
    2. VISUAL flag allows anyone to examine
    3. Otherwise need to pass examine lock

    Args:
        actor: The object trying to examine
        target: The object being examined

    Returns:
        True if actor can examine target
    """
    if actor is None or target is None:
        return False

    # Can examine what you control
    if can_control(actor, target):
        return True

    # VISUAL flag allows examination
    if target.has_tag('visual'):
        return True

    # Otherwise check examine lock (handled by lock system)
    return False


def is_god(obj: GameObject | None) -> bool:
    """Check if object has God role."""
    return get_role(obj) >= Role.GOD


def is_admin(obj: GameObject | None) -> bool:
    """Check if object has Admin role or higher."""
    return get_role(obj) >= Role.ADMIN


def is_builder(obj: GameObject | None) -> bool:
    """Check if object has Builder role or higher."""
    return get_role(obj) >= Role.BUILDER


def is_player(obj: GameObject | None) -> bool:
    """Check if object has Player role or higher."""
    return get_role(obj) >= Role.PLAYER


def get_role_name(role: Role) -> str:
    """Get the display name for a role."""
    return {
        Role.GOD: "God",
        Role.ADMIN: "Admin",
        Role.BUILDER: "Builder",
        Role.PLAYER: "Player",
        Role.GUEST: "Guest",
    }.get(role, "Unknown")


def set_role(obj: GameObject, role: Role) -> None:
    """
    Set an object's role by adding the appropriate tag.

    Removes any existing role tags first.

    Args:
        obj: The object to modify
        role: The role to set
    """
    # Remove existing role tags
    for tag in ['god', 'admin', 'wizard', 'builder', 'staff', 'guest']:
        if obj.has_tag(tag):
            obj.remove_tag(tag)

    # Add new role tag
    tag_map = {
        Role.GOD: 'god',
        Role.ADMIN: 'admin',
        Role.BUILDER: 'builder',
        Role.GUEST: 'guest',
        Role.PLAYER: None,  # No tag needed for player
    }

    tag = tag_map.get(role)
    if tag:
        obj.add_tag(tag)
