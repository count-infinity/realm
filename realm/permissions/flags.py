"""
Object flags for REALM.

Flags modify object behavior:
- HALT: Cannot execute any scripts/commands
- GAGGED: Cannot communicate (say, pose, etc.)
- DARK: Hidden from normal view
- QUIET: Suppresses action feedback
- VISUAL: Can be examined by anyone
- SAFE: Protected from destruction
- ORPHAN: Skips ancestor inheritance

Flags are implemented as tags with a 'flag:' prefix for namespacing.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class Flag(str, Enum):
    """Standard object flags."""

    # Scripting/command control
    HALT = "halt"  # Cannot execute scripts or commands
    GAGGED = "gagged"  # Cannot communicate (say, pose, etc.)

    # Visibility
    DARK = "dark"  # Hidden from normal view (look, contents)
    VISUAL = "visual"  # Can be examined by anyone
    OPAQUE = "opaque"  # Contents not visible from outside

    # Behavior modifiers
    QUIET = "quiet"  # Suppresses action feedback messages
    VERBOSE = "verbose"  # Extra feedback (opposite of quiet)
    PUPPET = "puppet"  # Relays what it sees/hears to owner

    # Protection
    SAFE = "safe"  # Protected from destruction
    STICKY = "sticky"  # Returns to owner when dropped
    WIZARD = "wizard"  # Wizard-level object (admin protection)

    # Inheritance
    ORPHAN = "orphan"  # Skips ancestor inheritance

    # State
    CONNECTED = "connected"  # Player is online (set by system)
    HAVEN = "haven"  # Cannot be attacked/paged
    UNFINDABLE = "unfindable"  # Cannot be found via @find/@where

    # Movement
    FLOATING = "floating"  # Doesn't fall with gravity
    FIXED = "fixed"  # Cannot be moved/teleported


# Flags that only admins can set
ADMIN_ONLY_FLAGS = {
    Flag.WIZARD,
    Flag.SAFE,
}

# Flags that are set by the system, not players
SYSTEM_FLAGS = {
    Flag.CONNECTED,
}

# Flag descriptions for help text
FLAG_DESCRIPTIONS = {
    Flag.HALT: "Object cannot execute scripts or trigger commands",
    Flag.GAGGED: "Object cannot communicate (say, pose, emote)",
    Flag.DARK: "Object is hidden from normal view",
    Flag.VISUAL: "Object can be examined by anyone",
    Flag.OPAQUE: "Object's contents are not visible from outside",
    Flag.QUIET: "Object receives less feedback from actions",
    Flag.VERBOSE: "Object receives extra feedback from actions",
    Flag.PUPPET: "Object relays what it sees/hears to its owner",
    Flag.SAFE: "Object is protected from destruction",
    Flag.STICKY: "Object returns to owner when dropped",
    Flag.WIZARD: "Object has wizard-level protection",
    Flag.ORPHAN: "Object skips ancestor attribute inheritance",
    Flag.CONNECTED: "Player is currently connected (system flag)",
    Flag.HAVEN: "Object cannot be attacked or paged",
    Flag.UNFINDABLE: "Object cannot be found via @find or @where",
    Flag.FLOATING: "Object doesn't fall with gravity",
    Flag.FIXED: "Object cannot be moved or teleported",
}


def _flag_tag(flag: Flag | str) -> str:
    """Get the tag name for a flag."""
    if isinstance(flag, Flag):
        return flag.value
    return flag.lower()


def has_flag(obj: GameObject | None, flag: Flag | str) -> bool:
    """
    Check if an object has a flag set.

    Args:
        obj: The object to check
        flag: The flag to check for

    Returns:
        True if the flag is set
    """
    if obj is None:
        return False
    return obj.has_tag(_flag_tag(flag))


def set_flag(obj: GameObject, flag: Flag | str) -> None:
    """
    Set a flag on an object.

    Args:
        obj: The object to modify
        flag: The flag to set
    """
    obj.add_tag(_flag_tag(flag))


def clear_flag(obj: GameObject, flag: Flag | str) -> None:
    """
    Clear a flag from an object.

    Args:
        obj: The object to modify
        flag: The flag to clear
    """
    tag = _flag_tag(flag)
    if obj.has_tag(tag):
        obj.remove_tag(tag)


def get_flags(obj: GameObject | None) -> list[Flag]:
    """
    Get all flags set on an object.

    Args:
        obj: The object to check

    Returns:
        List of Flag enum values
    """
    if obj is None:
        return []

    result = []
    for flag in Flag:
        if obj.has_tag(flag.value):
            result.append(flag)
    return result


def get_flag_names(obj: GameObject | None) -> list[str]:
    """
    Get flag names as strings.

    Args:
        obj: The object to check

    Returns:
        List of flag names
    """
    return [f.value.upper() for f in get_flags(obj)]


def toggle_flag(obj: GameObject, flag: Flag | str) -> bool:
    """
    Toggle a flag on an object.

    Args:
        obj: The object to modify
        flag: The flag to toggle

    Returns:
        True if flag is now set, False if cleared
    """
    if has_flag(obj, flag):
        clear_flag(obj, flag)
        return False
    else:
        set_flag(obj, flag)
        return True


def can_set_flag(actor: GameObject | None, target: GameObject, flag: Flag) -> bool:
    """
    Check if an actor can set a flag on a target.

    Args:
        actor: The object trying to set the flag
        target: The object to set the flag on
        flag: The flag to set

    Returns:
        True if allowed
    """
    from realm.permissions.roles import can_control, is_admin

    # Must be able to control the target
    if not can_control(actor, target):
        return False

    # System flags cannot be set by players
    if flag in SYSTEM_FLAGS:
        return False

    # Admin-only flags require admin role
    if flag in ADMIN_ONLY_FLAGS:
        return is_admin(actor)

    return True


# Convenience functions for common flag checks

def is_halted(obj: GameObject | None) -> bool:
    """Check if object is halted (cannot execute scripts)."""
    return has_flag(obj, Flag.HALT)


def is_gagged(obj: GameObject | None) -> bool:
    """Check if object is gagged (cannot communicate)."""
    return has_flag(obj, Flag.GAGGED)


def is_dark(obj: GameObject | None) -> bool:
    """Check if object is dark (hidden from view)."""
    return has_flag(obj, Flag.DARK)


def is_safe(obj: GameObject | None) -> bool:
    """Check if object is safe (protected from destruction)."""
    return has_flag(obj, Flag.SAFE)


def is_quiet(obj: GameObject | None) -> bool:
    """Check if object is quiet (suppressed feedback)."""
    return has_flag(obj, Flag.QUIET)


def is_connected(obj: GameObject | None) -> bool:
    """Check if player is connected."""
    return has_flag(obj, Flag.CONNECTED)


def is_visual(obj: GameObject | None) -> bool:
    """Check if object can be examined by anyone."""
    return has_flag(obj, Flag.VISUAL)
