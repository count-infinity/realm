"""
Lock system for REALM.

Locks control who can perform actions on objects:
- basic: Who can pick up / traverse (default lock)
- enter: Who can enter this container/room
- use: Who can trigger $-commands on this
- control: Who can modify this object (delegation)
- speech: Who can speak here
- teleport: Who can teleport to this room
- examine: Who sees detail — the detail sections of examine and look
- give: Who can give this away
- drop: Who can drop this
- command: Who can trigger commands on this
- listen: Who can trigger listen patterns

Lock expressions are Python expressions evaluated in a restricted namespace.
Available variables:
- caller: The object trying to pass the lock
- target: The object with the lock
- owner: The lock owner (usually same as target)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from realm.core.safe_eval import SAFE_EXPR_BUILTINS, compile_expression, eval_bool
from realm.permissions.entitlements import (
    CONTROL_ALL,
    CONTROL_UNOWNED,
    LOCK_BYPASS,
    LOCK_BYPASS_ALL,
)
from realm.permissions.roles import has_entitlement

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action


# --- Lock types ----------------------------------------------------------------
# A lock type is a plain string. The built-in ones are named below (and as
# ``LockType.BASIC`` etc.); a feature declares more with
# ``feature.lock_type(...)``, and any other lowercase name is a game's own
# lock: it works the moment a builder sets it.

BASIC = "basic"        # pick up, traverse
ENTER = "enter"        # enter this container
USE = "use"            # trigger $-commands
CONTROL = "control"    # modify this object
SPEECH = "speech"      # speak here
TELEPORT = "teleport"  # teleport to this
EXAMINE = "examine"    # see this object's detail sections
GIVE = "give"          # give this away
DROP = "drop"          # drop this
COMMAND = "command"    # trigger its named scripts
LISTEN = "listen"      # trigger its listen patterns
REACH = "reach"        # reach into this room from afar (scry, remote act)

#: The built-in lock type names, for ``LockType.BASIC``-style call sites.
LockType = SimpleNamespace(
    BASIC=BASIC, ENTER=ENTER, USE=USE, CONTROL=CONTROL, SPEECH=SPEECH,
    TELEPORT=TELEPORT, EXAMINE=EXAMINE, GIVE=GIVE, DROP=DROP, COMMAND=COMMAND,
    LISTEN=LISTEN, REACH=REACH,
)

LOCK_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class LockDef:
    """A registered lock type: its default expression (used when no lock of
    this type is set) and a line for builders."""

    name: str
    default: str = "True"
    doc: str = ""
    owner: str = "kernel"


def _builtin_lock_types() -> list[LockDef]:
    return [
        LockDef(BASIC, "True", "pick up / traverse"),
        LockDef(ENTER, "True", "enter or put into this"),
        LockDef(USE, "True", "use this object's $-commands"),
        LockDef(CONTROL, "caller.id == owner.id", "modify this object"),
        LockDef(SPEECH, "True", "speak in this room"),
        LockDef(TELEPORT, "True", "teleport into this"),
        # Open by default; a builder sets it to hide detail sections.
        LockDef(EXAMINE, "True", "see this object's detail sections"),
        LockDef(GIVE, "True", "give this away"),
        LockDef(DROP, "True", "drop this"),
        LockDef(COMMAND, "True", "trigger this object's named scripts"),
        LockDef(LISTEN, "True", "be overheard by its ^listen patterns"),
        LockDef(REACH, "True", "reach into this room from afar"),
    ]


_LOCK_TYPES: dict[str, LockDef] = {d.name: d for d in _builtin_lock_types()}


def register_lock_type(name: str, *, default: str = "True", doc: str = "",
                       owner: str = "kernel", replace: bool = False) -> None:
    """Register a lock type with its default expression."""
    if not LOCK_TYPE_RE.match(name):
        raise ValueError(f"lock type {name!r} must match {LOCK_TYPE_RE.pattern}")
    held = _LOCK_TYPES.get(name)
    if held is not None and held.owner != owner and not replace:
        raise ValueError(f"lock type {name!r} is already registered by {held.owner!r}")
    _LOCK_TYPES[name] = LockDef(name, default, doc, owner)


def install_lock_types(defs: list[LockDef]) -> None:
    """The built-ins plus ``defs`` (``FeatureSet.install_registries``)."""
    _LOCK_TYPES.clear()
    _LOCK_TYPES.update({d.name: d for d in _builtin_lock_types()})
    _LOCK_TYPES.update({d.name: d for d in defs})


def lock_types() -> dict[str, LockDef]:
    """Every registered lock type, by name."""
    return dict(sorted(_LOCK_TYPES.items()))


def default_lock(lock_type: str) -> str:
    """The expression a lock type uses when no lock of that type is set: its
    registered default, else ``True`` (a game's own lock that nobody set
    does not block)."""
    entry = _LOCK_TYPES.get(lock_type)
    return entry.default if entry is not None else "True"


def near_lock_type(lock_type: str) -> str | None:
    """A registered lock type ``lock_type`` is probably a typo of, or None."""
    import difflib
    if lock_type in _LOCK_TYPES:
        return None
    close = difflib.get_close_matches(lock_type, list(_LOCK_TYPES), n=1, cutoff=0.8)
    return close[0] if close else None


class Lock:
    """
    Represents a lock on an object.

    Locks are Python expressions evaluated in a safe namespace.
    """

    def __init__(self, lock_type: str, expression: str):
        self.lock_type = str(lock_type)
        self.expression = expression.strip()
        self._compiled: Any = None
        self._valid: bool | None = None
        self._error: str | None = None

    def validate(self) -> tuple[bool, str | None]:
        """
        Validate the lock expression.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if self._valid is not None:
            return self._valid, self._error

        # One validator for locks, strategies, and scripts (safe_eval).
        try:
            self._compiled = compile_expression(self.expression)
        except ValueError as e:
            self._valid = False
            self._error = str(e)
            return False, self._error

        self._valid = True
        return True, None

    def __repr__(self) -> str:
        return f"Lock({self.lock_type}, {self.expression!r})"


# Safe namespace for lock evaluation — the shared expression builtins.
LOCK_SAFE_BUILTINS = SAFE_EXPR_BUILTINS


class LockEvaluator:
    """
    Evaluates lock expressions safely.

    Provides a restricted namespace with access to:
    - caller: The object trying to pass the lock
    - target: The object with the lock
    - owner: The target's owner
    - safe built-in functions
    """

    def evaluate(
        self,
        lock: Lock | str,
        caller: GameObject,
        target: GameObject,
    ) -> bool:
        """
        Evaluate a lock expression.

        Args:
            lock: The Lock object or expression string
            caller: The object trying to pass the lock
            target: The object with the lock

        Returns:
            True if lock passes, False otherwise
        """
        # Handle string expressions
        if isinstance(lock, str):
            lock = Lock(LockType.BASIC, lock)

        # Validation, compilation, and fail-closed evaluation all live in
        # the shared safe_eval engine.
        return eval_bool(lock.expression, _lock_namespace(caller, target))

    def check(
        self,
        target: GameObject,
        lock_type: str,
        caller: GameObject,
    ) -> bool:
        """
        Check if caller passes a lock on target.

        This is the main entry point for lock checking.
        Handles admin bypass and default locks.

        Args:
            target: The object with the lock
            lock_type: Which lock to check
            caller: The object trying to pass

        Returns:
            True if lock passes
        """
        lock_type = str(lock_type)

        # Bypass every lock (superuser).
        if has_entitlement(caller, LOCK_BYPASS_ALL):
            return True

        # Bypass most locks — but not CONTROL of an object owned by someone
        # whose authority is itself unbypassable (a god): rival authority wins.
        if has_entitlement(caller, LOCK_BYPASS):
            if lock_type == LockType.CONTROL:
                if target.owner and has_entitlement(target.owner, LOCK_BYPASS_ALL):
                    return False
            return True

        # Get the lock expression
        lock_expr = target.locks.get(lock_type)

        if lock_expr is None:
            # The type's registered default; a game's own unset lock passes.
            lock_expr = default_lock(lock_type)

        # eval_bool validates, compiles (lru-cached), and fails closed.
        return eval_bool(lock_expr, _lock_namespace(caller, target))


_build_namespace = None


def _lock_namespace(caller: GameObject, target: GameObject):
    """The ``lock`` profile: ``caller``, ``target``, ``owner`` and the
    read-only softcode functions, with the caller as the subject."""
    global _build_namespace
    if _build_namespace is None:     # import once; locks load before scripting
        from realm.scripting.namespace import build_namespace
        _build_namespace = build_namespace
    namespace, _frame = _build_namespace(
        'lock', executor=target, enactor=caller, location=target.location,
        subject=caller)
    return namespace


# Global evaluator instance
_evaluator = LockEvaluator()


def check_lock(
    target: GameObject,
    lock_type: str,
    caller: GameObject,
) -> bool:
    """
    Convenience function to check a lock.

    Args:
        target: The object with the lock
        lock_type: Which lock to check
        caller: The object trying to pass

    Returns:
        True if lock passes
    """
    return _evaluator.check(target, lock_type, caller)


def controls(actor: GameObject | None, obj: GameObject | None,
             _depth: int = 0) -> bool:
    """
    The one authority predicate for mutating softcode and builder tools
    (see docs/design/engine_vision.md):

    1. You control yourself.
    2. You control what you own.
    3. ADMIN+ controls everything.
    4. BUILDER controls unowned (world-built) NON-PLAYER objects.
    5. The world trusts the world: an unowned non-player object controls
       other unowned non-player objects (world NPCs poking world props —
       the MUSH equivalent is everything sharing a wizard owner).
    6. PennMUSH delegation: your objects act with YOUR authority — an
       owned object controls whatever its owner controls (siblings
       trust each other; a builder's gadget reaches world props). Only
       the owner can script the object, so this delegates no authority
       the owner didn't already have. @chown halts scripts for exactly
       this reason.
    7. Otherwise the object's ``control`` lock decides.
    """
    if actor is None or obj is None:
        return False
    if actor is obj or actor.id == obj.id:
        return True
    if obj.owner is not None and actor.id == obj.owner.id:
        return True
    if has_entitlement(actor, CONTROL_ALL):
        return True
    if (has_entitlement(actor, CONTROL_UNOWNED)
            and obj.owner is None and not obj.is_player):
        return True
    if (actor.owner is None and obj.owner is None
            and not actor.is_player and not obj.is_player):
        return True
    # Penn delegation: walk the owner chain (cycle/depth guarded) — the
    # object wields its owner's authority.
    if actor.owner is not None and _depth < 4:
        if controls(actor.owner, obj, _depth=_depth + 1):
            return True
    return _evaluator.check(obj, LockType.CONTROL, actor)


def may_relocate(mover: GameObject | None, target: GameObject | None) -> bool:
    """
    May ``mover`` relocate ``target`` — PennMUSH's ``tport_control_ok``.

    Relocation is a *weaker* authority than full control: a room's owner may
    teleport / shove around what stands in their room without being able to
    ``@set`` or ``@destroy`` it. So this is broader than ``controls`` in
    exactly one way — you may move what stands in a room you own:

    1. ``controls(mover, target)`` — you own the target (or admin). (Penn:
       ``controls(player, victim)`` / ``Tel_Anything``.)
    2. You own the room the target is in — ``controls(mover, target.location)``
       — and the target is not ``anchored``. (Penn: ``controls(player, loc)
       && !Heavy(victim)``.)

    The ``loc.owner is not None`` guard in rule 2 is load-bearing: for an
    *unowned* world room, ``controls`` would fire the world-trusts-world rule
    and let ANY co-located object move occupants — the confused-deputy hole.
    Requiring the room to be owned means only genuine ownership / admin /
    owner-delegation grants the authority (Penn rooms always have an owner).

    ``anchored`` is Penn's ``HEAVY`` flag: an object opts out of being moved
    by room-ownership, while its own controller and admins still can (rule 1
    bypasses the check).
    """
    if controls(mover, target):
        return True
    if mover is None or target is None:
        return False
    loc = target.location
    if loc is None or target.has_tag('anchored'):
        return False
    return loc.owner is not None and controls(mover, loc)


def may_trigger(actor: GameObject | None, obj: GameObject | None) -> bool:
    """
    May ``actor`` run ``obj``'s named scripts (@tr / ``trigger``)?

    Running a script AS an object is control-level power, so the default
    is controllers-only. An owner can open it up by setting an explicit
    ``command`` lock (the trigger_ok analog): ``@lock/command bell =
    True`` lets anyone ring it.
    """
    if actor is None or obj is None:
        return False
    if controls(actor, obj):
        return True
    if obj.locks.get(COMMAND) is not None:
        return check_lock(obj, LockType.COMMAND, actor)
    return False


def parse_lock(expression: str, lock_type: str = LockType.BASIC) -> Lock:
    """
    Parse a lock expression.

    Args:
        expression: The lock expression
        lock_type: The type of lock

    Returns:
        Lock object (may be invalid, check with .validate())
    """
    return Lock(lock_type, expression)


def set_lock(target: GameObject, lock_type: str, expression: str) -> bool:
    """
    Set a lock on an object.

    Args:
        target: The object to lock
        lock_type: The type of lock
        expression: The lock expression

    Returns:
        True if lock was set successfully (valid expression)
    """
    lock_type = str(lock_type)

    lock = Lock(lock_type, expression)
    valid, error = lock.validate()

    if valid:
        target.locks[lock_type] = expression
        return True

    return False


def clear_lock(target: GameObject, lock_type: str) -> bool:
    """
    Clear a lock from an object.

    Args:
        target: The object to unlock
        lock_type: The type of lock to clear

    Returns:
        True if lock was cleared
    """
    lock_type = str(lock_type)

    if lock_type in target.locks:
        del target.locks[lock_type]
        return True

    return False


# --- Enforcement in the propagation check pass ------------------------------
#
# Locks are enforced where the data lives: each object, when visited during
# an action's permission pass, checks the lock that its role in the action
# implies. GameObject.visit_check calls enforce_lock_on_action before its
# behaviors run, so behaviors still observe lock-blocked attempts (both
# propagation passes always complete).
#
# Movement is the exception: exit traversal (basic) and destination entry
# (enter) are checked directly in realm.core.movement.move_through_exit,
# because the exit and destination aren't the target of the gating
# on_leave action.

def lock_failure_message(
    obj: GameObject,
    lock_type: str,
    default_template: str,
) -> str:
    """
    The message shown when a lock blocks an action.

    Builders can override per object and lock type with a
    ``lock_fail_<type>`` attribute (e.g. ``@set door/lock_fail_basic =
    The door glows red and refuses to budge.``); otherwise the default
    template is used with ``{name}`` substituted.
    """
    name = str(lock_type)
    custom = obj.db.get(f"lock_fail_{name}")
    if custom:
        return str(custom)
    return default_template.format(name=obj.name)


def enforce_lock_on_action(obj: GameObject, action: Action) -> None:
    """
    Check the lock implied by ``obj``'s role in ``action``; block on failure.

    Called from GameObject.visit_check for the actor and target. Does
    nothing for action types with no lock mapping, for already-blocked
    actions (first block reason wins), or for actorless actions.
    """
    actor = action.actor
    if actor is None or action.blocked:
        return

    from realm.core.eventdefs import installed
    event = installed().get(action.action_type)
    if event is None:
        return

    if obj is action.target and obj is not actor and event.target_lock:
        lock_type, template = event.target_lock
        if not check_lock(obj, lock_type, actor):
            action.block(lock_failure_message(obj, lock_type, template))
            return

    if obj is actor and action.tool is not None and event.tool_lock:
        lock_type, template = event.tool_lock
        if not check_lock(action.tool, lock_type, actor):
            action.block(lock_failure_message(action.tool, lock_type, template))
