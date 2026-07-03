"""
Permission system for REALM.

Provides:
- Role hierarchy (God, Admin, Builder, Player, Guest)
- Lock system for fine-grained access control
- Object flags (HALT, GAGGED, DARK, etc.)
- Permission checking utilities
"""

from realm.permissions.flags import (
    Flag,
    clear_flag,
    get_flags,
    has_flag,
    set_flag,
)
from realm.permissions.locks import (
    Lock,
    LockEvaluator,
    LockType,
    check_lock,
    parse_lock,
)
from realm.permissions.roles import (
    Role,
    can_control,
    get_role,
    has_permission,
    is_admin,
    is_builder,
    is_god,
)

__all__ = [
    # Roles
    "Role",
    "get_role",
    "has_permission",
    "can_control",
    "is_god",
    "is_admin",
    "is_builder",
    # Locks
    "Lock",
    "LockType",
    "LockEvaluator",
    "check_lock",
    "parse_lock",
    # Flags
    "Flag",
    "has_flag",
    "set_flag",
    "clear_flag",
    "get_flags",
]
