"""
One builder for every softcode evaluation context.

A *profile* names a context. Each one gets registry functions according to
their flags, plus a few context names:

- ``script``: every function (harm-flagged ones only with HARM); ``me``,
  ``here``, ``enactor``, the event names, ``param``. Subject: the enactor.
- ``check``: read-only functions; the script names plus ``block``, ``mod``,
  ``set_adata``, ``is_blocked``. Subject: the enactor.
- ``inline``: every function (harm-flagged ones only with HARM); ``me``,
  ``here``, ``enactor``, ``viewer``. Subject: the viewer.
- ``lock``: read-only functions; ``caller``, ``target``, ``owner``.
  Subject: the caller.
- ``detail``: read-only functions; ``viewer``. Subject: the viewer.
- ``rule``: read-only functions; ``skill(name=<this skill>)``, ``attr``,
  ``mod``, ``skill_name``. Subject: the roller.

The *subject* is whose skill ``skill(name)`` reads and who rolls
``check(name, mod)``.

``script``, ``check`` and ``inline`` run in the script sandbox and get a
plain dict. ``lock``, ``detail`` and ``rule`` are single expressions on hot
paths; they get an :class:`ExprNamespace`, which binds a registry function
only when the expression names it and wraps objects in read-only handles.

The combat strategy namespace (``combat/strategy.py``) is not built here.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import partial
from types import MethodType
from typing import TYPE_CHECKING, Any

from realm.core.safe_eval import SAFE_EXPR_BUILTINS, LazyNamespace
from realm.scripting.functions import ScriptFrame
from realm.scripting.handle import SandboxRuntime, guarded_read
from realm.scripting.registry import registered

if TYPE_CHECKING:
    from realm.core.objects import GameObject
    from realm.core.propagation import Action

PROFILES = ("script", "check", "inline", "lock", "detail", "rule")
SANDBOX_PROFILES = frozenset({"script", "check", "inline"})
READONLY_PROFILES = frozenset({"check", "lock", "detail", "rule"})

#: What each profile adds beyond registry functions, for the reference page.
PROFILE_EXTRAS: dict[str, str] = {
    "script": "`me`, `here`, `enactor`; `atype`, `actor`, `target`, `has_atag`, "
              "`adata` (empty when no action); `param` for a behavior_def",
    "check": "everything `script` binds, plus `block`, `mod`, `set_adata`, `is_blocked`",
    "inline": "`me`, `here`, `enactor`, `viewer`",
    "lock": "`caller`, `target`, `owner` (the locked object's owner)",
    "detail": "`viewer`",
    "rule": "`skill(name=<this skill>)`, `attr(name)`, `mod`, `skill_name`",
}
PROFILE_SUBJECT = {"script": "enactor", "check": "enactor", "inline": "viewer",
                   "lock": "caller", "detail": "viewer", "rule": "the roller"}


def event_names(action: Action | None, enactor: GameObject | None = None) -> dict[str, Any]:
    """The action's own data, for scripts that observe it.

    Always bound: with no action behind the script (``@tr``, a ``$``-command)
    ``adata()`` answers its default and ``target`` is None, so a hook a
    builder ``@tr``'s does not die of NameError. Read-only: the apply pass
    runs after the decision, so it gets no veto verbs.
    """
    if action is None:
        return {
            'atype': '',
            'actor': enactor,     # keep actor == enactor, as when real
            'target': None,
            'has_atag': lambda tag: False,
            'adata': lambda key, default=None: default,
        }
    return {
        'atype': action.action_type,
        'actor': action.actor,
        'target': action.target,
        'has_atag': lambda tag: action.has_tag(str(tag)),
        'adata': lambda key, default=None: action.extra.get(key, default),
    }


def check_verbs(action: Action) -> dict[str, Any]:
    """The veto/modify verbs only the decision pass may use."""
    return {
        'set_adata': lambda key, value: action.extra.__setitem__(str(key), value),
        'block': lambda reason='': action.block(str(reason)),
        'mod': lambda value: action.add_modifier(int(value), 'on_check'),
        'is_blocked': lambda: action.blocked,
    }


class ExprNamespace(LazyNamespace):
    """A lazy, guarded namespace for one lock, detail or rule expression.

    Direct names are wrapped in read-only handles (judged from
    ``principal``). A read-only registry function is bound to the frame on
    first lookup; its arguments are unwrapped and its result wrapped, the
    same boundary the script sandbox applies. The frame (and the store
    lookup it needs) is built only if the expression calls a function that
    takes one, so a plain ``caller.has_tag('x')`` lock pays for neither.
    """

    __slots__ = ('_rt', '_frame_args', '_frame')

    def __init__(self, direct: Mapping[str, Any], frame_args: tuple,
                 principal: GameObject | None) -> None:
        dict.__init__(self, SAFE_EXPR_BUILTINS)
        rt = SandboxRuntime(None, principal)
        rt._get_attr = partial(_guarded_read_as, principal)
        self._rt = rt
        self._frame_args = frame_args    # (enactor, executor, location, store, subject)
        self._frame: ScriptFrame | None = None
        wrap = rt.wrap
        for key, value in direct.items():
            self[key] = wrap(value)

    def _make_frame(self) -> ScriptFrame:
        enactor, executor, location, store, subject = self._frame_args
        if store is None:
            from realm.persistence.manager import get_active_manager
            store = get_active_manager()
        frame = ScriptFrame(enactor=enactor, executor=executor,
                                location=location, persistence=store)
        frame.subject = subject
        self._frame = frame
        return frame

    def resolve(self, name: str) -> Any:
        entry = registered().get(name)
        if entry is None or not entry.readonly:
            raise KeyError(name)
        if entry.takes_frame:
            fn = MethodType(entry.fn, self._frame or self._make_frame())
        else:
            fn = entry.fn
        rt = self._rt

        def call(*args, **kwargs):
            args = tuple(rt.unwrap(a) for a in args)
            kwargs = {k: rt.unwrap(v) for k, v in kwargs.items()}
            return rt.wrap(fn(*args, **kwargs))
        call.__name__ = name
        return call


def _guarded_read_as(principal, obj, name, default=None):
    return guarded_read(obj, name, default, principal)


def build_namespace(profile: str, *, executor: GameObject | None,
                    enactor: GameObject | None = None,
                    location: GameObject | None = None,
                    store: Any = None,
                    action: Action | None = None,
                    params: dict[str, Any] | None = None,
                    subject: GameObject | None = None,
                    enactor_consent: bool = False,
                    extra: Mapping[str, Any] | None = None,
                    ) -> tuple[Mapping[str, Any], ScriptFrame | None]:
    """The namespace for one softcode evaluation in ``profile``.

    Returns ``(namespace, frame)``. ``frame`` holds the run's queued world
    operations (drain it after a sandbox run); it is None for the expression
    profiles until a function needs it. ``extra`` names are added last and
    win (the rule profile's ``skill``, ``attr``, ``mod``).
    """
    if profile not in PROFILES:
        raise ValueError(f"unknown softcode profile {profile!r}; one of {PROFILES}")

    if profile in SANDBOX_PROFILES:
        frame = ScriptFrame(enactor=enactor, executor=executor,
                                location=location, persistence=store,
                                enactor_consent=enactor_consent)
        frame.subject = subject if subject is not None else enactor
        namespace = frame.readonly_dict() if profile == "check" else frame.to_dict()
        if profile in ("script", "check"):
            namespace.update(event_names(action, enactor))
        if profile == "check" and action is not None:
            namespace.update(check_verbs(action))
        if profile == "inline":
            namespace['viewer'] = subject
        if params is not None:
            bound = dict(params)
            namespace['param'] = lambda key, default=None: bound.get(str(key), default)
        if extra:
            namespace.update(extra)
        return namespace, frame

    if profile == "lock":
        direct = {'caller': enactor, 'target': executor,
                  'owner': executor.owner if executor.owner else executor}
        principal = enactor
    elif profile == "detail":
        direct = {'viewer': subject}
        principal = subject
    else:  # rule
        direct = {}
        principal = executor
    if extra:
        direct.update(extra)
    namespace = ExprNamespace(
        direct, (enactor, executor, location, store, subject), principal)
    return namespace, None


__all__ = ["PROFILES", "PROFILE_EXTRAS", "PROFILE_SUBJECT", "ExprNamespace",
           "build_namespace", "event_names", "check_verbs"]
