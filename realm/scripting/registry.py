"""
The softcode function registry.

Every softcode function is declared once, here, with its flags:

- ``group``: its section in the reference (``docs/reference/softcode.md``).
- ``readonly``: it neither changes the world nor queues a change, so it is
  safe in the check, lock, detail and rule profiles.
- ``harm``: it can hurt a target the executor need not control, or mint
  money. It is left out of the namespace when the executor lacks the HARM
  entitlement (see ``ScriptFrame.may_harm``).

Engine functions take the per-run frame as their first argument and are
declared with :func:`softfn`. Games and packs add plain native functions
with :func:`softcode_function` (the public decorator, re-exported as
``realm.scripting.softcode_function``). Both land in the same table, so a
third-party function is visible wherever its flags allow.

Registering a name already bound to a different callable raises
``ValueError`` unless ``replace=True``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any


@dataclass(frozen=True)
class SoftFn:
    """One softcode function and its flags."""

    name: str
    fn: Callable[..., Any]
    group: str
    readonly: bool
    harm: bool
    takes_frame: bool       # True: called as fn(frame, *args)
    subject: bool = False   # True: the profile's subject is passed implicitly


_REGISTRY: dict[str, SoftFn] = {}


def _register(entry: SoftFn, *, replace: bool) -> None:
    current = _REGISTRY.get(entry.name)
    if current is not None and current.fn is not entry.fn and not replace:
        raise ValueError(
            f"softcode function {entry.name!r} is already registered "
            f"({current.fn.__module__}.{current.fn.__qualname__}). Pick another "
            f"name, or pass replace=True to override it.")
    _REGISTRY[entry.name] = entry


def softfn(name: str | None = None, *, group: str, readonly: bool = False,
           harm: bool = False, subject: bool = False, takes_frame: bool = True):
    """Register an engine function whose first parameter is the frame.

    Used on ``ScriptFrame`` methods: the method is registered unbound and
    bound to each run's frame when a namespace is built. A pure helper that
    needs no frame (a ``@staticmethod``) passes ``takes_frame=False``.
    """
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        _register(SoftFn(name or fn.__name__, fn, group, readonly, harm,
                         takes_frame=takes_frame, subject=subject), replace=False)
        return fn
    return decorator


def softcode_function(name: str | Callable[..., Any] | None = None, *,
                      group: str = "Game", readonly: bool = False,
                      harm: bool = False, replace: bool = False):
    """Register a plain native function as a softcode function.

    Usable bare (``@softcode_function``) or with arguments
    (``@softcode_function("roll_fate", readonly=True)``). Native functions
    are trusted code: a game registers them at deploy time by importing the
    module from ``config.py``; softcode cannot register them.
    """
    def decorator(fn: Callable[..., Any], fn_name: str | None = None):
        _register(SoftFn(fn_name or fn.__name__, fn, group, readonly, harm,
                         takes_frame=False), replace=replace)
        return fn

    if callable(name):                      # bare @softcode_function
        return decorator(name)
    return lambda fn: decorator(fn, name)


def registered() -> Mapping[str, SoftFn]:
    """Every registered softcode function, by name (read-only view)."""
    return MappingProxyType(_REGISTRY)


def unregister(name: str) -> None:
    """Remove a function (tests)."""
    _REGISTRY.pop(name, None)


__all__ = ["SoftFn", "softfn", "softcode_function", "registered", "unregister"]
