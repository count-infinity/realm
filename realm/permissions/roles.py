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

from realm.permissions.entitlements import (
    CONTROL_ALL,
    CONTROL_UNOWNED,
    LOCK_BYPASS,
    LOCK_BYPASS_ALL,
    PERMISSION_TIER_ENTITLEMENTS,
    SEE_ALL,
    TELEPORT_ANY,
    TIER_ADMIN,
    TIER_BUILDER,
    TIER_GOD,
    TIER_GUEST,
    TIER_PLAYER,
    role_def_table,
)

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


# Built-in role -> the entitlements it grants, cumulative up the ladder so the
# old rung comparisons stay exactly true (a GOD has everything an ADMIN has,
# etc.). This table is the single definition of "what each rung could do";
# every former ``get_role(x) >= Role.Y`` gate now asks for the one entitlement
# it actually meant.
_BUILTIN_ROLE_ENTITLEMENTS: dict[Role, frozenset[str]] = {}


def _build_role_entitlements() -> None:
    guest = frozenset({TIER_GUEST})
    player = guest | {TIER_PLAYER}
    builder = player | {TIER_BUILDER, CONTROL_UNOWNED}
    admin = builder | {TIER_ADMIN, LOCK_BYPASS, CONTROL_ALL, TELEPORT_ANY,
                       SEE_ALL}
    god = admin | {TIER_GOD, LOCK_BYPASS_ALL}
    _BUILTIN_ROLE_ENTITLEMENTS.update({
        Role.GUEST: guest,
        Role.PLAYER: player,
        Role.BUILDER: builder,
        Role.ADMIN: admin,
        Role.GOD: god,
    })


_build_role_entitlements()


def entitlements_of(obj: GameObject | None) -> frozenset[str]:
    """The set of entitlements ``obj`` holds.

    The base set is its built-in role's cumulative grant (via ``get_role``, so
    quell / guest / npc handling is inherited verbatim). Any ``role_def`` tags
    it carries union their entitlements on top — the "roles as data" layer that
    lets a game mint custom ranks. A quelled actor is stripped to the player
    set and its custom-role tags are ignored, so quell still means quelled.
    """
    role = get_role(obj)
    base = _BUILTIN_ROLE_ENTITLEMENTS[role]
    defs = role_def_table()
    if not defs or obj is None or obj.has_tag('quelled'):
        return base                       # common path: no allocation
    granted = set(base)
    for name, ents in defs.items():
        if obj.has_tag(name):
            granted |= ents
    return frozenset(granted)


def has_entitlement(obj: GameObject | None, entitlement: str) -> bool:
    """Whether ``obj`` holds ``entitlement``. Call sites pass the module
    constants from ``permissions.entitlements`` (never a string literal)."""
    return entitlement in entitlements_of(obj)


def role_conferred_by_tag(tag: str) -> Role | None:
    """The role a privilege tag grants, or ``None`` for an ordinary tag."""
    return ROLE_TAGS.get(tag.lower())


def may_change_role_tag(actor: GameObject | None, tag: str) -> bool:
    """May ``actor`` add or remove the privilege ``tag``?

    Ordinary (non-role) tags always pass here — object *control* is checked
    separately, at the mutation site. This predicate governs the one thing
    control does not: writing a tag that changes **authority itself**.

    ``controls()`` alone is the wrong gate for a role tag, because everyone
    controls themselves (rule 1) and their own objects (rule 2 + Penn
    delegation) — so ``@tag me = god`` or a self-owned script's
    ``add_tag(me, 'admin')`` would otherwise self-promote. The rule: you may
    change a role tag only if you are GOD (the superuser mints anyone,
    including gods) **or** your own role *strictly* outranks the privilege the
    tag confers. Consequences:

    - only GOD may grant/revoke ``admin``/``wizard``;
    - only ADMIN+ may grant/revoke ``builder``/``staff``;
    - ``god`` can be conferred by a GOD in-world, but never *reached* by
      anyone below it — superuser is seeded at the data layer (`auth.py`).

    Note this reads the actor's role *directly* (no owner delegation), so a
    player-owned script executor stays PLAYER here and cannot launder a grant
    through an object it controls.
    """
    conferred = ROLE_TAGS.get(tag.lower())
    if conferred is None:
        return True
    actor_role = get_role(actor)
    return actor_role >= Role.GOD or actor_role > conferred


def has_permission(actor: GameObject | None, permission: str) -> bool:
    """
    Check if an actor may run a command gated at ``permission``.

    The coarse command tiers (guest/player/builder/admin/god) now resolve
    through the entitlement mechanism: each tier maps to a ``TIER_*``
    entitlement the built-in roles grant cumulatively, so behaviour is
    identical to the old rung comparison — but a custom ``role_def`` can be
    granted a command tier independently of the authority entitlements.
    """
    required = PERMISSION_TIER_ENTITLEMENTS.get(permission.lower(), TIER_PLAYER)
    return has_entitlement(actor, required)








# NOTE (simplicity review 2026-07-05): the former can_control/can_examine
# helpers were a second, DISAGREEING authority layer with zero runtime
# callers. realm.permissions.locks.controls() is the one predicate.
