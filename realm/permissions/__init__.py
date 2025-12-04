"""
Permission system for REALM.

Provides:
- Role hierarchy (God, Admin, Builder, Player, Guest)
- Lock system for fine-grained access control
- Object flags (HALT, GAGGED, DARK, etc.)
- Permission checking utilities
"""

from realm.permissions.roles import (
    Role,
    get_role,
    has_permission,
    can_control,
    is_god,
    is_admin,
    is_builder,
)
from realm.permissions.locks import (
    Lock,
    LockType,
    LockEvaluator,
    check_lock,
    parse_lock,
)
from realm.permissions.flags import (
    Flag,
    has_flag,
    set_flag,
    clear_flag,
    get_flags,
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
