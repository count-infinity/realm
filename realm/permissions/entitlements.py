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

Names are flat ``SCREAMING_SNAKE`` strings. The registry is open: the
kernel's are below, a feature declares more (``feature.entitlement``), and
a ``role_def`` may grant a game's own name that its softcode checks with
``has_entitlement``. The typo guard is a near-miss check: a ``role_def``
name within 0.8 of a registered one (``LOCK_BYPAS``) is reported by
``@reload`` and not granted. Engine call sites use the module constants (no
string literals), so a typo there is an ImportError.
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
#: Author softcode that harms others: the primitives that damage / apply a
#: harmful effect to a target you do not control, or MINT currency. Gates
#: the *authoring* of harm, not its use — a builder's poison dart (authored
#: with HARM) still fires in a player's hand, because harm rides the trusted
#: engine paths (combat / cast) and this only governs who may write the
#: harmful primitive into softcode in the first place. Composition model
#: (see BACKLOG "builder-restricted harmful softcode"): a human player may
#: not author harm; unowned world content and NPCs are trusted by
#: construction; builder+ hold this by default.
HARM = "HARM"
#: Build: attach, detach and configure behaviors on objects you control.
#: Checked through the owner chain like HARM: a mortal player as the
#: responsible principal lacks it; builders hold it; unowned world content
#: is trusted by construction (see core.ops.may_build).
BUILD = "BUILD"
#: Moderate players: disconnect a session (@boot).
MODERATE = "MODERATE"

# NOTE: entitlements deliberately do NOT gate *command access*. Command
# invocation is still a coarse role-tier check in the dispatcher
# (``has_permission``). Unifying the two — so a command's authorization lives
# in the shared service function it calls (``@teleport`` -> ``move_to`` ->
# entitlement/ownership check), rather than a per-command tier — is a tracked
# design question (see BACKLOG: "Command authorization belongs at the service
# layer"). Until then, the registry is authority capabilities only.

_BUILTIN = {
    LOCK_BYPASS_ALL: "bypass every lock, including control of a god-owned object",
    LOCK_BYPASS: "bypass locks, except control of a god-owned object",
    CONTROL_ALL: "controls() everything",
    CONTROL_UNOWNED: "controls() unowned, world-built, non-player objects",
    TELEPORT_ANY: "placement tunnels a destination's enter/teleport locks",
    SEE_ALL: "see in darkness and through invisibility",
    HARM: "author softcode that harms others or mints currency",
    BUILD: "attach, detach and configure behaviors",
    MODERATE: "disconnect players (@boot)",
}

#: Registered entitlements, name -> doc. Open: a feature declares more with
#: ``feature.entitlement(...)``, and a role_def may grant a game's own name
#: that nobody registered (the engine checks only the names it knows).
_ENTITLEMENTS: dict[str, str] = dict(_BUILTIN)


def register_entitlement(name: str, doc: str = "") -> None:
    """Register an entitlement name (the kernel's and features' own)."""
    _ENTITLEMENTS[str(name)] = doc


def install_entitlements(declared: dict[str, str]) -> None:
    """The kernel's entitlements plus ``declared`` (``install_registries``)."""
    _ENTITLEMENTS.clear()
    _ENTITLEMENTS.update(_BUILTIN)
    _ENTITLEMENTS.update(declared)


def registered_entitlements() -> dict[str, str]:
    """Every registered entitlement, by name."""
    return dict(sorted(_ENTITLEMENTS.items()))


def near_entitlement(name: str) -> str | None:
    """A registered entitlement that ``name`` is probably a typo of, or None."""
    import difflib
    if name in _ENTITLEMENTS:
        return None
    by_lower = {n.lower(): n for n in _ENTITLEMENTS}
    close = difflib.get_close_matches(name.lower(), list(by_lower), n=1, cutoff=0.8)
    return by_lower[close[0]] if close else None


def is_entitlement(name: str) -> bool:
    """Whether ``name`` is a registered entitlement."""
    return name in _ENTITLEMENTS


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
    return _read_role_defs()[0]


def _read_role_defs() -> tuple[dict[str, frozenset[str]], list[str]]:
    """``read_role_defs`` plus the problems found, each already logged."""
    from realm.core.defs import all_defs, invalidate

    invalidate("role")
    out: dict[str, frozenset[str]] = {}
    problems: list[str] = []
    for obj in all_defs("role").values():
        raw = obj.db.get("entitlements") or []
        if not isinstance(raw, (list, tuple, set)):
            problems.append(
                f"role_def {obj.name!r}: entitlements must be a list, not "
                f"{type(raw).__name__}; the role grants nothing")
            continue
        granted = set()
        for name in raw:
            name = str(name)
            near = near_entitlement(name)
            if near is not None:
                # A near miss of a real entitlement is almost certainly a typo:
                # granting it would widen nothing, so say so and skip it.
                problems.append(
                    f"role_def {obj.name!r}: unknown entitlement {name!r}, did you "
                    f"mean {near!r}? Not granted.")
                continue
            # A registered name, or a game's own (checked by its own softcode
            # with has_entitlement()).
            granted.add(name)
        out[obj.name.strip().lower()] = frozenset(granted)
    for message in problems:
        logger.warning(message)
    return out, problems


def reload_role_defs() -> list[str]:
    """Rebuild the custom-role cache from the world (call at @reload/import).
    Returns the problems found (unknown entitlements, malformed defs) so the
    caller can show them to the builder; each is also logged."""
    global _role_def_table
    try:
        _role_def_table, problems = _read_role_defs()
    except Exception as exc:  # never let a bad def break authority resolution
        message = f"reload_role_defs failed, keeping built-ins only: {exc}"
        logger.warning(message)
        _role_def_table = {}
        return [message]
    return problems


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
    "TELEPORT_ANY", "SEE_ALL", "HARM", "BUILD", "MODERATE",
    "is_entitlement", "register_entitlement", "registered_entitlements",
    "near_entitlement",
    "ROLE_DEF_TAG", "read_role_defs", "reload_role_defs", "role_def_table",
    "define_role",
]
