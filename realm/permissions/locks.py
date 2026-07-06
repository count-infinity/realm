"""
Lock system for REALM.

Locks control who can perform actions on objects:
- basic: Who can pick up / traverse (default lock)
- enter: Who can enter this container/room
- use: Who can trigger $-commands on this
- control: Who can modify this object (delegation)
- speech: Who can speak here
- teleport: Who can teleport to this room
- examine: Who can examine this VISUAL object
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

from enum import Enum
from typing import TYPE_CHECKING, Any

from realm.core.safe_eval import SAFE_EXPR_BUILTINS, compile_expression, eval_bool
from realm.permissions.roles import Role, get_role

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action


class LockType(str, Enum):
    """Standard lock types."""

    BASIC = "basic"  # Default lock (pick up, traverse)
    ENTER = "enter"  # Enter this container
    USE = "use"  # Trigger $-commands
    CONTROL = "control"  # Modify this object
    SPEECH = "speech"  # Speak here
    TELEPORT = "teleport"  # Teleport to this
    EXAMINE = "examine"  # Examine this object
    GIVE = "give"  # Give this away
    DROP = "drop"  # Drop this
    COMMAND = "command"  # Trigger commands
    LISTEN = "listen"  # Trigger listen patterns


# Default lock expressions (when no lock is set)
DEFAULT_LOCKS = {
    LockType.BASIC: "True",  # Anyone can pick up by default
    LockType.ENTER: "True",  # Anyone can enter by default
    LockType.USE: "True",  # Anyone can use by default
    LockType.CONTROL: "caller.id == owner.id",  # Only owner can control
    LockType.SPEECH: "True",  # Anyone can speak
    LockType.TELEPORT: "True",  # Anyone can teleport
    LockType.EXAMINE: "False",  # Must be VISUAL or owner
    LockType.GIVE: "True",  # Anyone can give
    LockType.DROP: "True",  # Anyone can drop
    LockType.COMMAND: "True",  # Anyone can trigger
    LockType.LISTEN: "True",  # Anyone can trigger listen
}


class Lock:
    """
    Represents a lock on an object.

    Locks are Python expressions evaluated in a safe namespace.
    """

    def __init__(self, lock_type: LockType | str, expression: str):
        self.lock_type = LockType(lock_type) if isinstance(lock_type, str) else lock_type
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
        return f"Lock({self.lock_type.value}, {self.expression!r})"


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

    def __init__(self):
        self._cache: dict[str, Any] = {}

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
        return eval_bool(lock.expression, {
            'caller': caller,
            'target': target,
            'owner': target.owner if target.owner else target,
        })

    def check(
        self,
        target: GameObject,
        lock_type: LockType | str,
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
        if isinstance(lock_type, str):
            lock_type = LockType(lock_type)

        # God bypasses all locks
        if get_role(caller) >= Role.GOD:
            return True

        # Admin bypasses most locks except control on god-owned objects
        if get_role(caller) >= Role.ADMIN:
            if lock_type == LockType.CONTROL:
                if target.owner and get_role(target.owner) >= Role.GOD:
                    return False
            return True

        # Get the lock expression
        lock_expr = target.locks.get(lock_type.value)

        if lock_expr is None:
            # Use default lock
            lock_expr = DEFAULT_LOCKS.get(lock_type, "False")

        lock = Lock(lock_type, lock_expr)
        return self.evaluate(lock, caller, target)


# Global evaluator instance
_evaluator = LockEvaluator()


def check_lock(
    target: GameObject,
    lock_type: LockType | str,
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


def controls(actor: GameObject | None, obj: GameObject | None) -> bool:
    """
    The one authority predicate for mutating softcode and builder tools
    (see docs/design/engine_vision.md):

    1. You control yourself.
    2. You control what you own.
    3. ADMIN+ controls everything.
    4. BUILDER controls unowned (world-built) objects.
    5. The world trusts the world: an unowned non-player object controls
       other unowned non-player objects (world NPCs poking world props —
       the MUSH equivalent is everything sharing a wizard owner).
    6. Otherwise the object's ``control`` lock decides.
    """
    if actor is None or obj is None:
        return False
    if actor is obj or actor.id == obj.id:
        return True
    if obj.owner is not None and actor.id == obj.owner.id:
        return True
    role = get_role(actor)
    if role >= Role.ADMIN:
        return True
    if role >= Role.BUILDER and obj.owner is None:
        return True
    if (actor.owner is None and obj.owner is None
            and not actor.has_tag('player') and not obj.has_tag('player')):
        return True
    return _evaluator.check(obj, LockType.CONTROL, actor)


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
    if obj.locks.get(LockType.COMMAND.value) is not None:
        return check_lock(obj, LockType.COMMAND, actor)
    return False


def parse_lock(expression: str, lock_type: LockType | str = LockType.BASIC) -> Lock:
    """
    Parse a lock expression.

    Args:
        expression: The lock expression
        lock_type: The type of lock

    Returns:
        Lock object (may be invalid, check with .validate())
    """
    return Lock(lock_type, expression)


def set_lock(target: GameObject, lock_type: LockType | str, expression: str) -> bool:
    """
    Set a lock on an object.

    Args:
        target: The object to lock
        lock_type: The type of lock
        expression: The lock expression

    Returns:
        True if lock was set successfully (valid expression)
    """
    if isinstance(lock_type, LockType):
        lock_type = lock_type.value

    lock = Lock(lock_type, expression)
    valid, error = lock.validate()

    if valid:
        target.locks[lock_type] = expression
        return True

    return False


def clear_lock(target: GameObject, lock_type: LockType | str) -> bool:
    """
    Clear a lock from an object.

    Args:
        target: The object to unlock
        lock_type: The type of lock to clear

    Returns:
        True if lock was cleared
    """
    if isinstance(lock_type, LockType):
        lock_type = lock_type.value

    if lock_type in target.locks:
        del target.locks[lock_type]
        return True

    return False


def get_lock(target: GameObject, lock_type: LockType | str) -> str | None:
    """
    Get the lock expression on an object.

    Args:
        target: The object to check
        lock_type: The type of lock

    Returns:
        The lock expression or None if not set
    """
    if isinstance(lock_type, LockType):
        lock_type = lock_type.value

    return target.locks.get(lock_type)


def list_locks(target: GameObject) -> dict[str, str]:
    """
    List all locks on an object.

    Args:
        target: The object to check

    Returns:
        Dictionary of lock_type -> expression
    """
    return dict(target.locks)


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

# action_type → (lock checked ON THE TARGET, default failure message)
TARGET_ACTION_LOCKS: dict[str, tuple[LockType, str]] = {
    "item:on_get": (LockType.BASIC, "You can't pick up {name}."),
    "item:on_drop": (LockType.DROP, "You can't drop {name}."),
    "item:on_put": (LockType.ENTER, "You can't put things in {name}."),
    # All room-directed communication is gated by the room's speech lock.
    "event:speech": (LockType.SPEECH, "You can't speak here."),
    "event:shout": (LockType.SPEECH, "You can't speak here."),
    "event:ooc": (LockType.SPEECH, "You can't speak here."),
    "event:emote": (LockType.SPEECH, "You can't emote here."),
    "event:semipose": (LockType.SPEECH, "You can't emote here."),
    "event:emit": (LockType.SPEECH, "You can't emit here."),
}

# action_type → (lock checked ON THE TOOL by the actor, default message).
# The tool isn't visited by the propagation chain, so the actor — who is
# always visited — checks the lock of the thing it's wielding/giving.
TOOL_ACTION_LOCKS: dict[str, tuple[LockType, str]] = {
    "item:on_give": (LockType.GIVE, "You can't give {name} away."),
}


def lock_failure_message(
    obj: GameObject,
    lock_type: LockType,
    default_template: str,
) -> str:
    """
    The message shown when a lock blocks an action.

    Builders can override per object and lock type with a
    ``lock_fail_<type>`` attribute (e.g. ``@set door/lock_fail_basic =
    The door glows red and refuses to budge.``); otherwise the default
    template is used with ``{name}`` substituted.
    """
    custom = obj.db.get(f"lock_fail_{lock_type.value}")
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

    if obj is action.target and obj is not actor:
        entry = TARGET_ACTION_LOCKS.get(action.action_type)
        if entry:
            lock_type, template = entry
            if not check_lock(obj, lock_type, actor):
                action.block(lock_failure_message(obj, lock_type, template))
                return

    if obj is actor and action.tool is not None:
        entry = TOOL_ACTION_LOCKS.get(action.action_type)
        if entry:
            lock_type, template = entry
            if not check_lock(action.tool, lock_type, actor):
                action.block(
                    lock_failure_message(action.tool, lock_type, template)
                )
