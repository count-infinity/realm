"""
Entitlements: granular capabilities that roles grant.

REALM's privilege was a five-rung ladder (GUEST < PLAYER < BUILDER < ADMIN <
GOD): every gate was a rung comparison, so ``>= ADMIN`` meant
see-through-darkness *and* bypass-locks *and* teleport-anywhere *and*
control-everything at once — you could not grant one without the rest.

An **entitlement** is a single, named capability (``SEE_ALL``,
``TELEPORT_ANY``...). A **role** is just a named set of entitlements. The
built-in roles reproduce the old ladder exactly (see ``roles.py``), so the
cut-over is behaviour-preserving; the payoff is that a game can now mint a
custom rank — a "warden" who can ``TELEPORT_ANY`` but not ``CONTROL_ALL`` —
that the rung model could never express.

Names are flat ``SCREAMING_SNAKE`` constants drawn from a closed registry
(``ALL_ENTITLEMENTS``), typo-guarded like behaviour ids: a ``role_def`` that
lists an unknown entitlement is logged and skipped, and call sites use the
module constants (no string literals) so a typo is an ImportError, not a
silent ``False``.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# --- Authority entitlements (the fine-grained capabilities) -------------------

#: Bypass every lock, including CONTROL of a god-owned object (superuser).
LOCK_BYPASS_ALL = "LOCK_BYPASS_ALL"
#: Bypass locks, except CONTROL of a god-owned object (the rival-authority
#: carve-out lives at the call site, not here).
LOCK_BYPASS = "LOCK_BYPASS"
#: ``controls()`` everything — @force, possession, and mutation all ride this.
CONTROL_ALL = "CONTROL_ALL"
#: ``controls()`` unowned, world-built, non-player objects (builder reach).
CONTROL_UNOWNED = "CONTROL_UNOWNED"
#: A mover whose placement tunnels a destination's ENTER/TELEPORT locks.
TELEPORT_ANY = "TELEPORT_ANY"
#: See in darkness and through invisibility.
SEE_ALL = "SEE_ALL"

# --- Command-access tiers -----------------------------------------------------
# The command dispatcher's coarse permission gate ("player"/"builder"/...),
# expressed on the same mechanism so a custom role can be granted command
# access without inheriting the whole rung. Per-command *semantic* entitlements
# (BUILD, ADMIN_TOOLS, ...) are a future refinement layered on top of these.

TIER_GUEST = "TIER_GUEST"
TIER_PLAYER = "TIER_PLAYER"
TIER_BUILDER = "TIER_BUILDER"
TIER_ADMIN = "TIER_ADMIN"
TIER_GOD = "TIER_GOD"

#: Command-permission string -> the tier entitlement it requires.
PERMISSION_TIER_ENTITLEMENTS = {
    "guest": TIER_GUEST,
    "player": TIER_PLAYER,
    "builder": TIER_BUILDER,
    "admin": TIER_ADMIN,
    "god": TIER_GOD,
}

#: The closed registry — every valid entitlement name. A ``role_def`` may only
#: grant names in here; call sites use the constants above.
ALL_ENTITLEMENTS = frozenset({
    LOCK_BYPASS_ALL, LOCK_BYPASS, CONTROL_ALL, CONTROL_UNOWNED,
    TELEPORT_ANY, SEE_ALL,
    TIER_GUEST, TIER_PLAYER, TIER_BUILDER, TIER_ADMIN, TIER_GOD,
})


def is_entitlement(name: str) -> bool:
    """Whether ``name`` is a registered entitlement."""
    return name in ALL_ENTITLEMENTS


# --- Roles as data: role_def objects -----------------------------------------
# A ``role_def`` object names a custom rank and lists the entitlements it
# grants; a player tagged with that name gains them (unioned with any other
# role tags). Mirrors skill_def/class_def (systems/definitions.py): built-ins
# in code, content in the world.

ROLE_DEF_TAG = "role_def"

# Module cache of the merged custom-role table: {role_name: frozenset(ents)}.
# None means "not yet loaded"; {} means "loaded, no custom roles". Refreshed by
# reload_role_defs() at @reload / area-import / first use.
_role_def_table: dict[str, frozenset[str]] | None = None


def read_role_defs() -> dict[str, frozenset[str]]:
    """All ``role_def`` objects as ``{name: frozenset(entitlements)}``.

    Sorted by id so a duplicate name resolves deterministically (last wins).
    Unknown entitlement strings are logged and dropped — a typo grants nothing
    rather than silently widening authority.
    """
    from realm.core.query import find_objects

    out: dict[str, frozenset[str]] = {}
    for obj in sorted(find_objects(tag=ROLE_DEF_TAG), key=lambda o: o.id):
        raw = obj.db.get("entitlements") or []
        if not isinstance(raw, (list, tuple, set)):
            continue
        granted = set()
        for name in raw:
            name = str(name)
            if name in ALL_ENTITLEMENTS:
                granted.add(name)
            else:
                logger.warning(
                    "role_def %r lists unknown entitlement %r — ignored",
                    obj.name, name)
        out[obj.name.strip().lower()] = frozenset(granted)
    return out


def reload_role_defs() -> None:
    """Rebuild the custom-role cache from the world (call at @reload/import)."""
    global _role_def_table
    try:
        _role_def_table = read_role_defs()
    except Exception as exc:  # never let a bad def break authority resolution
        logger.warning("reload_role_defs failed, keeping built-ins only: %s", exc)
        _role_def_table = {}


def role_def_table() -> dict[str, frozenset[str]]:
    """The custom-role table, loading it on first use (empty on failure)."""
    if _role_def_table is None:
        reload_role_defs()
    return _role_def_table or {}


def define_role(name: str, entitlements: list[str]) -> object:
    """Build a ``role_def`` object (caller adds it to the world). For seeding,
    OLC, and tests. Unknown entitlements are kept as-is here; ``read_role_defs``
    is the validating boundary."""
    from realm.core.objects import GameObject

    obj = GameObject(name=name, tags=[ROLE_DEF_TAG])
    obj.db.set("entitlements", list(entitlements))
    return obj


__all__ = [
    "LOCK_BYPASS_ALL", "LOCK_BYPASS", "CONTROL_ALL", "CONTROL_UNOWNED",
    "TELEPORT_ANY", "SEE_ALL",
    "TIER_GUEST", "TIER_PLAYER", "TIER_BUILDER", "TIER_ADMIN", "TIER_GOD",
    "PERMISSION_TIER_ENTITLEMENTS", "ALL_ENTITLEMENTS", "is_entitlement",
    "ROLE_DEF_TAG", "read_role_defs", "reload_role_defs", "role_def_table",
    "define_role",
]
