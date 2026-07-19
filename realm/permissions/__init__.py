"""
Permission system for REALM.

Provides:
- Role hierarchy (God, Admin, Builder, Player, Guest)
- Entitlements: the granular capabilities roles grant (has_entitlement)
- Lock system for fine-grained access control
- controls(): the one authority predicate for mutations
"""

from realm.permissions.entitlements import (
    ALL_ENTITLEMENTS,
    is_entitlement,
    reload_role_defs,
)
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
    entitlements_of,
    get_role,
    has_entitlement,
    has_permission,
)

__all__ = [
    # Roles + the one authority predicate
    "Role",
    "get_role",
    "has_permission",
    "controls",
    "may_trigger",
    # Entitlements
    "entitlements_of",
    "has_entitlement",
    "is_entitlement",
    "ALL_ENTITLEMENTS",
    "reload_role_defs",
    # Locks
    "Lock",
    "LockType",
    "LockEvaluator",
    "check_lock",
    "parse_lock",
]
