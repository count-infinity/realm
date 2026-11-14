"""
Public names that load on first use (PEP 562).

``realm`` and each ``realm/std/<feature>/__init__.py`` publish names that
live in their modules. Importing them eagerly would make ``import
realm.core.objects`` load the feature system, the permissions and the
softcode registry, and make importing one part of a feature load all of
it. Instead a package lists its names and where each lives; the first
access imports that module and caches the value:

    __all__, __getattr__, __dir__ = exports(globals(), {
        "Feature": "realm.features:Feature",   # a name in a module
        "pools": "realm.core.pools",           # the module itself
    })
"""

from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any


def exports(namespace: dict[str, Any], table: dict[str, str]
            ) -> tuple[list[str], Callable[[str], Any], Callable[[], list[str]]]:
    """``(__all__, __getattr__, __dir__)`` for a package publishing
    ``table``: public name -> ``"module:attribute"``, or ``"module"`` for
    the module itself."""
    package = namespace["__name__"]

    def lookup(name: str) -> Any:
        source = table.get(name)
        if source is None:
            raise AttributeError(f"module {package!r} has no attribute {name!r}")
        module, _, attribute = source.partition(":")
        value = importlib.import_module(module)
        if attribute:
            value = getattr(value, attribute)
        namespace[name] = value
        return value

    def listing() -> list[str]:
        return sorted(set(namespace) | set(table))

    return sorted(table), lookup, listing


__all__ = ["exports"]
