"""
Native softcode bindings — the trusted escape hatch (VISION.md #5).

``@softcode_function`` registers a native Python function as a softcode
primitive callable by name from any script or OLC. This is the *native*
tier of the two-tier trust model: bindings are full-power, unsandboxed
Python, so they are registered at **deploy time by an operator** (a game's
``config.py`` imports the module that defines them), **never** typed at an
in-game prompt. Sandboxed softcode *composes* bindings; it cannot register
them.

    # mygame/bindings.py
    from realm.scripting import softcode_function

    @softcode_function
    def cinematic_dice(pool, tn):
        ...            # arbitrary fast/complex native Python

    # config.py:  import bindings   → softcode/OLC can now call cinematic_dice(...)

It is also the performance escape hatch: a resolution rule that is too
slow or gnarly in softcode simply *becomes a binding* — simple stays
softcode, hot/complex goes native.
"""

from __future__ import annotations

from collections.abc import Callable

_BINDINGS: dict[str, Callable] = {}


def softcode_function(name=None):
    """Register a native function as a softcode primitive. Usable bare
    (``@softcode_function``) or named (``@softcode_function("roll_fate")``)."""
    if callable(name):                      # bare @softcode_function
        _BINDINGS[name.__name__] = name
        return name

    def decorator(fn: Callable) -> Callable:
        _BINDINGS[name or fn.__name__] = fn
        return fn

    return decorator


def registered_bindings() -> dict[str, Callable]:
    """A copy of the registered native bindings (merged into the softcode
    namespace)."""
    return dict(_BINDINGS)


def clear_bindings() -> None:
    """Drop all registrations (tests)."""
    _BINDINGS.clear()


__all__ = ["softcode_function", "registered_bindings", "clear_bindings"]
