"""
One definition loader.

World data defines rules: a ``skill_def`` object is a skill, a
``class_def`` a character class, a ``role_def`` a rank, a ``behavior_def``
a scripted behavior, an ``ability_def``/``spell_def`` an ability. A
:class:`DefKind` names one such kind: its tag, how to parse an object into
a definition, and how to key it. Every kind shares one cache and one lookup:

    all_defs("skill")          # {"stealth": ("dexterity", -5), ...}
    find_def("spell", "fire")  # exact key, else a unique prefix

The cache for a kind is dropped whenever an object carrying its tag
changes (an attribute, a tag, a save, a delete): ``realm.core.objects``
calls :func:`touched`, so builders' edits are live without
``@reload``. A parser that raises is logged at WARNING with the object id
and that definition is skipped.

Features declare kinds (``feature.def_kind``); the kernel declares
``role`` and ``behavior``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


def _name_key(obj: GameObject) -> str:
    return obj.name.strip().lower()


@dataclass(frozen=True)
class DefKind:
    """A kind of in-world definition."""

    name: str                                           # "skill"
    tag: str                                            # "skill_def"
    parse: Callable[[GameObject], Any] | None = None    # None: the object itself
    key: Callable[[GameObject], str] = _name_key
    owner: str = "kernel"


_KINDS: dict[str, DefKind] = {}
_TAGS: dict[str, str] = {}            # tag -> kind name
_cache: dict[str, dict[str, Any]] = {}


def register_def_kind(kind: DefKind, *, replace: bool = False) -> None:
    """Register a kind. A name already registered to another owner raises
    ValueError unless ``replace``."""
    held = _KINDS.get(kind.name)
    if held is not None and held.owner != kind.owner and not replace:
        raise ValueError(f"definition kind {kind.name!r} is already registered by "
                         f"{held.owner!r}")
    _KINDS[kind.name] = kind
    _TAGS[kind.tag] = kind.name
    _cache.pop(kind.name, None)


def install_def_kinds(kinds: list[DefKind]) -> None:
    """The kernel kinds plus ``kinds`` (``FeatureSet.install_registries``)."""
    _KINDS.clear()
    _TAGS.clear()
    _cache.clear()
    for kind in [*kernel_kinds(), *kinds]:
        _KINDS[kind.name] = kind
        _TAGS[kind.tag] = kind.name


def def_kinds() -> dict[str, DefKind]:
    _ensure()
    return dict(_KINDS)


def _ensure() -> None:
    if not _KINDS:
        from realm.features import ensure_registries
        ensure_registries()
        if not _KINDS:
            install_def_kinds([])


def all_defs(kind: str) -> dict[str, Any]:
    """Every definition of ``kind``, by key. Objects are read in id order,
    so a duplicate key resolves the same way every time (last wins)."""
    _ensure()
    cached = _cache.get(kind)
    if cached is not None:
        return cached
    spec = _KINDS.get(kind)
    if spec is None:
        raise KeyError(f"no definition kind {kind!r}; known: {sorted(_KINDS)}")
    from realm.core.query import find_objects
    out: dict[str, Any] = {}
    for obj in sorted(find_objects(tag=spec.tag), key=lambda o: o.id):
        try:
            value = spec.parse(obj) if spec.parse is not None else obj
        except Exception as exc:
            logger.warning(f"{spec.tag} {obj.name!r} ({obj.id}) could not be read and "
                           f"is skipped: {exc}")
            continue
        if value is not None:
            out[spec.key(obj)] = value
    _cache[kind] = out
    return out


def find_def(kind: str, name: str) -> Any | None:
    """A definition by exact key (case-insensitive), else a unique prefix."""
    want = str(name).strip().lower()
    if not want:
        return None
    defs = all_defs(kind)
    if want in defs:
        return defs[want]
    prefixed = [v for k, v in defs.items() if k.startswith(want)]
    return prefixed[0] if len(prefixed) == 1 else None


def invalidate(kind: str | None = None) -> None:
    """Drop the cache for one kind, or for all."""
    if kind is None:
        _cache.clear()
    else:
        _cache.pop(kind, None)


def touched(obj: GameObject, tag: str | None = None) -> None:
    """``obj`` changed (or ``tag`` was added to or removed from it): drop
    the cache of every kind it belongs to."""
    if not _cache:
        return
    if tag is not None:
        kind = _TAGS.get(tag.lower().strip())
        if kind is not None:
            _cache.pop(kind, None)
    for def_tag, kind in _TAGS.items():
        if kind in _cache and obj.has_tag(def_tag):
            _cache.pop(kind, None)


def kernel_kinds() -> list[DefKind]:
    """``role`` (role_def ranks) and ``behavior`` (scripted behaviors). The
    ``rules`` feature declares ``skill`` and ``class``."""
    return [
        DefKind("role", "role_def"),
        DefKind("behavior", "behavior_def"),
    ]


__all__ = ["DefKind", "register_def_kind", "install_def_kinds", "def_kinds", "all_defs",
           "find_def", "invalidate", "touched", "kernel_kinds"]
