"""
Capability handles for softcode — Wall 2 of docs/design/sandbox-security.md.

Softcode never touches a live ``GameObject``. It touches a :class:`Handle`,
whose attribute access delegates to the guarded reader, so every read flows
through the same ``controls()``/``secret`` chokepoint the functions enforce,
and object-valued reads return handles (never raw objects) so there is no
walk back to the real object graph. Handles are interned per run, so
``target is me`` holds. Internals live in ``_``-slots, which the Wall 1 AST
filter already makes unreachable from softcode.

The handle is purely the AUTHORITY layer; host safety stays Wall 1's job.
Writes are blocked at the handle: attribute assignment raises, and ``.db``
returns a read-only view, so ``get('victim').db.x = 9`` and
``get('victim').db.set(...)`` both die while ``x.db.get(...)`` still reads
(guarded). All mutation must go through the ``controls()``-checked functions
(``set_attr``, ``move_to``, …) and the verbs.
"""

from __future__ import annotations

from typing import Any

from realm.core.attrflags import readable_attr
from realm.core.objects import GameObject

# Read-only object fields exposed as attributes. Object-valued ones (below)
# are wrapped into handles by the runtime; everything else falls through to
# the guarded db-attr reader, which secret-gates and hides PROTECTED_ATTRS.
_FIELD_READERS = {
    'id': lambda o: o.id,
    'name': lambda o: o.name,
    'description': lambda o: o.description,
    'location': lambda o: o.location,
    'owner': lambda o: o.owner,
    'contents': lambda o: list(o.contents),
    'tags': lambda o: frozenset(o.tags),
}
_OBJECT_FIELDS = {'location', 'owner', 'contents'}  # field reads to wrap

# Safe read-only predicate methods a handle may expose as bound callables
# (``caller.has_tag('key')`` in a lock expression). Read-only by nature; args
# are unwrapped and results wrapped. NO mutators here — that is the whole
# point of the handle.
_SAFE_METHODS = frozenset({'has_tag', 'has_entitlement'})


def guarded_read(obj: GameObject, name: str, default: Any = None,
                 principal: GameObject | None = None) -> Any:
    """Read a db attribute honoring PROTECTED_ATTRS and the secret flag
    (controller-only, judged from ``principal``). The shared reader behind
    both ``get_attr`` and the handle."""
    from realm.scripting.functions import PROTECTED_ATTRS
    if str(name) in PROTECTED_ATTRS:
        return default
    if not readable_attr(obj, str(name), principal):
        return default
    return obj.db.get(name, default)


class ReadOnlyAttrView:
    """What ``handle.db`` returns: guarded attribute *reads* only.

    ``x.db.get(k)`` / ``x.db.all()`` / ``x.db.k`` read through the same
    secret-gating reader ``get_attr`` uses; there is no ``set`` and
    assignment raises, so the write exploits (``x.db.k = v``,
    ``x.db.set(...)``) are dead while existing read idioms keep working.
    """

    __slots__ = ('_obj', '_rt')

    def __init__(self, obj: GameObject, rt: "SandboxRuntime") -> None:
        object.__setattr__(self, '_obj', obj)
        object.__setattr__(self, '_rt', rt)

    def get(self, name: str, default: Any = None) -> Any:
        return self._rt.wrap(self._rt.read_attr(self._obj, str(name), default))

    def all(self) -> dict[str, Any]:
        return self._rt.read_all(self._obj)

    #: Mutator method names intercepted for a clear message instead of the
    #: confusing "NoneType is not callable" a bare attribute read would give.
    _MUTATORS = frozenset({'set', 'delete', 'update', 'pop', 'clear',
                           'setdefault', 'add', 'remove'})

    def __getattr__(self, name: str) -> Any:
        if name in ReadOnlyAttrView._MUTATORS:
            raise AttributeError(
                f".db is read-only in softcode; use "
                f"set_attr(obj, name, value) instead of .db.{name}(...)")
        return self._rt.wrap(self._rt.read_attr(self._obj, name, None))

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError(
            f"object attributes are read-only in softcode; write '{name}' "
            f"with set_attr(obj, '{name}', value)")

    def __contains__(self, name: str) -> bool:
        return self._rt.read_attr(self._obj, str(name), None) is not None


class Handle:
    """An opaque, interned capability handle over a GameObject."""

    __slots__ = ('_obj', '_rt')

    def __init__(self, obj: GameObject, rt: "SandboxRuntime") -> None:
        object.__setattr__(self, '_obj', obj)
        object.__setattr__(self, '_rt', rt)

    def __getattr__(self, attr: str) -> Any:
        # Fires for every softcode ``handle.x`` (no class/slot attr shadows a
        # game name), routing the read through the guarded runtime.
        return self._rt.read(self._obj, attr)

    def __setattr__(self, attr: str, value: Any) -> None:
        raise AttributeError(
            f"cannot set '{attr}' on an object directly; use "
            f"set_attr(obj, '{attr}', value) for attributes, or the matching "
            f"command (move_to, @name, add_tag) for structural changes")

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Handle):
            return self._obj is other._obj
        return NotImplemented

    def __ne__(self, other: Any) -> bool:
        result = self.__eq__(other)
        return result if result is NotImplemented else not result

    def __hash__(self) -> int:
        return hash(id(self._obj))

    def __repr__(self) -> str:
        return f"<{self._obj.name}>"

    def __bool__(self) -> bool:
        return True


class SandboxRuntime:
    """Per-execution wrap/unwrap/read for handles.

    One intern cache per run, so the same object always yields the same
    handle (``target is me``). Reads route through ``get_attr`` — the
    already-guarded, secret-gating reader — so the handle adds no policy of
    its own; it only removes the raw-object surface that bypassed it.
    """

    __slots__ = ('_get_attr', '_executor', '_cache')

    def __init__(self, raw_get_attr: Any = None,
                 executor: GameObject | None = None) -> None:
        self._get_attr = raw_get_attr          # bound ScriptFunctions.get_attr
        self._executor = executor
        self._cache: dict[str, Handle] = {}    # obj.id -> Handle (interned)

    # --- boundary conversion ---

    def wrap(self, val: Any) -> Any:
        """Raw -> softcode: GameObjects become interned handles; list/tuple
        wrapped elementwise; everything else passes through unchanged."""
        if val is None or isinstance(val, (Handle, ReadOnlyAttrView)):
            return val
        if isinstance(val, GameObject):
            h = self._cache.get(val.id)
            if h is None:
                h = Handle(val, self)
                self._cache[val.id] = h
            return h
        if isinstance(val, (list, tuple)):
            return type(val)(self.wrap(v) for v in val)
        return val

    def unwrap(self, val: Any) -> Any:
        """Softcode -> raw: handles become their GameObject; containers are
        unwrapped elementwise. Called on function args and on the returned
        ``result`` so a handle never leaks back into engine code."""
        if isinstance(val, Handle):
            return object.__getattribute__(val, '_obj')
        if isinstance(val, (list, tuple)):
            return type(val)(self.unwrap(v) for v in val)
        if isinstance(val, dict):
            return {k: self.unwrap(v) for k, v in val.items()}
        return val

    # --- guarded reads ---

    def read(self, obj: GameObject, attr: str) -> Any:
        if attr == 'db':
            return ReadOnlyAttrView(obj, self)
        reader = _FIELD_READERS.get(attr)
        if reader is not None:
            val = reader(obj)
            return self.wrap(val) if attr in _OBJECT_FIELDS else val
        if attr in _SAFE_METHODS:
            return self._bind_method(obj, attr)
        # Fall through to the guarded db-attr reader (secret-gated, hides
        # PROTECTED_ATTRS). An unknown name reads as None, matching the
        # None-returning-handler convention.
        return self.wrap(self.read_attr(obj, attr))

    def _bind_method(self, obj: GameObject, attr: str):
        """A safe read-only method, exposed as a boundary-crossing callable."""
        raw = getattr(obj, attr, None)
        if not callable(raw):
            return self.wrap(raw)

        def bound(*args, **kwargs):
            args = tuple(self.unwrap(a) for a in args)
            kwargs = {k: self.unwrap(v) for k, v in kwargs.items()}
            return self.wrap(raw(*args, **kwargs))
        return bound

    def read_attr(self, obj: GameObject, name: str, default: Any = None) -> Any:
        if self._get_attr is None:
            return default
        return self._get_attr(obj, name, default)

    def read_all(self, obj: GameObject) -> dict[str, Any]:
        """Guarded ``db.all()``: readable, non-protected attributes only."""
        from realm.scripting.functions import PROTECTED_ATTRS
        out: dict[str, Any] = {}
        for key, value in obj.db.all().items():
            if key in PROTECTED_ATTRS:
                continue
            if not readable_attr(obj, key, self._executor):
                continue
            out[key] = self.wrap(value)
        return out


def guard_namespace(namespace: dict[str, Any],
                    principal: GameObject | None = None) -> dict[str, Any]:
    """Wrap the object-valued entries of an ``eval_expression``/``eval_bool``
    namespace in read-only handles.

    Lock, ``@detail``, and strategy expressions bind raw objects and are not
    run through :class:`ScriptSandbox`, so ``caller.db.set(...)`` in an
    expression would mutate the caller. Wrapping the objects gives them the
    same handle boundary the script sandbox uses: no attribute writes, no
    ``.db.set``, secret-gated reads (judged from ``principal``), safe
    predicate methods (``has_tag``) still callable. Callables and primitives
    in the namespace pass through untouched.
    """
    rt = SandboxRuntime(
        lambda o, n, d=None: guarded_read(o, n, d, principal), principal)
    return {key: rt.wrap(value) for key, value in namespace.items()}


__all__ = [
    "Handle",
    "ReadOnlyAttrView",
    "SandboxRuntime",
    "guarded_read",
    "guard_namespace",
]
