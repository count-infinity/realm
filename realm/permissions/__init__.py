"""
Permission system for REALM.

Provides:
- Role hierarchy (God, Admin, Builder, Player, Guest)
- Lock system for fine-grained access control
- controls(): the one authority predicate for mutations
"""

from realm.permissions.locks import (
    Lock,
    LockEvaluator,
    LockType,
    check_lock,
    controls,
    may_trigger,
    parse_lock,
)
from realm.permissions.roles import (
    Role,
    get_role,
    has_permission,
)

__all__ = [
    # Roles + the one authority predicate
    "Role",
    "get_role",
    "has_permission",
    "controls",
    "may_trigger",
    # Locks
    "Lock",
    "LockType",
    "LockEvaluator",
    "check_lock",
    "parse_lock",
]
