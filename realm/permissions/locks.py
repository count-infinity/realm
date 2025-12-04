"""
Lock system for REALM.

Locks control who can perform actions on objects:
- basic: Who can pick up / traverse (default lock)
- enter: Who can enter this container/room
- use: Who can trigger $-commands on this
- control: Who can modify this object (delegation)
- zone: Who controls objects in this zone
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

import ast
from enum import Enum
from typing import TYPE_CHECKING, Any

from realm.permissions.roles import get_role, Role

if TYPE_CHECKING:
    from realm.core.objects import GameObject


class LockType(str, Enum):
    """Standard lock types."""

    BASIC = "basic"  # Default lock (pick up, traverse)
    ENTER = "enter"  # Enter this container
    USE = "use"  # Trigger $-commands
    CONTROL = "control"  # Modify this object
    ZONE = "zone"  # Control objects in zone
    SPEECH = "speech"  # Speak here
    TELEPORT = "teleport"  # Teleport to this
    EXAMINE = "examine"  # Examine this object
    GIVE = "give"  # Give this away
    DROP = "drop"  # Drop this
    COMMAND = "command"  # Trigger commands
    LISTEN = "listen"  # Trigger listen patterns
    PAGE = "page"  # Send pages to this player
    MAIL = "mail"  # Send mail to this player


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
    LockType.PAGE: "True",  # Anyone can page
    LockType.MAIL: "True",  # Anyone can mail
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

        try:
            # Parse the expression
            tree = ast.parse(self.expression, mode='eval')

            # Check for forbidden constructs
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    self._valid = False
                    self._error = "Import statements not allowed"
                    return False, self._error

                if isinstance(node, ast.Call):
                    # Check for forbidden function calls
                    if isinstance(node.func, ast.Name):
                        if node.func.id in ('eval', 'exec', 'compile', '__import__'):
                            self._valid = False
                            self._error = f"Function '{node.func.id}' not allowed"
                            return False, self._error

                if isinstance(node, ast.Attribute):
                    # Check for private attribute access
                    if node.attr.startswith('_'):
                        self._valid = False
                        self._error = f"Private attribute access not allowed: {node.attr}"
                        return False, self._error

            # Try to compile
            self._compiled = compile(tree, '<lock>', 'eval')
            self._valid = True
            return True, None

        except SyntaxError as e:
            self._valid = False
            self._error = f"Syntax error: {e.msg}"
            return False, self._error

    def __repr__(self) -> str:
        return f"Lock({self.lock_type.value}, {self.expression!r})"


# Safe namespace for lock evaluation
LOCK_SAFE_BUILTINS = {
    'True': True,
    'False': False,
    'None': None,
    'int': int,
    'str': str,
    'len': len,
    'abs': abs,
    'min': min,
    'max': max,
    'any': any,
    'all': all,
}


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

        # Validate
        valid, error = lock.validate()
        if not valid:
            # Invalid locks fail closed
            return False

        # Build namespace
        namespace = dict(LOCK_SAFE_BUILTINS)
        namespace['caller'] = caller
        namespace['target'] = target
        namespace['owner'] = target.owner if target.owner else target

        try:
            result = eval(lock._compiled, {"__builtins__": {}}, namespace)
            return bool(result)
        except Exception:
            # Errors fail closed
            return False

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
