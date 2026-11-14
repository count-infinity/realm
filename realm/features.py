"""
Features: how code joins a REALM world.

A *feature* is a named bundle of declarations: commands, behaviors,
softcode functions, propagation observers, combat rulesets, destination
resolvers, reapers, softcode queue kinds, check modifiers, protocols and
config settings. A game is a list of features (``FEATURES`` in
``config.py``); the built-in ones live in ``realm/std/`` and
``realm/games/`` and use exactly this API.

Declaring changes nothing global. ``load(names)`` checks requirements and
collisions and returns a :class:`FeatureSet`, which installs in two steps:

- ``install_registries()``: before the world loads, so saved behaviors find
  their classes. Resets the behavior, ruleset, destination-resolver and
  softcode registries to exactly the loaded declarations.
- ``install_runtime(world)``: commands, observers, queue kinds, reapers,
  check modifiers, protocols and ``on_install`` hooks, onto a built world.

Only one world is live per process. When none is, the registries hold the
``CLASSIC`` set, so library code and tests that never build a world see
every built-in.

    # mygame/game.py
    from realm.features import Feature
    feature = Feature("mygame", requires=["rules"])

    @feature.command("wave", category="social", help_text="Wave hello")
    async def cmd_wave(ctx):
        await ctx.session.send("You wave.")
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from realm.core.behaviors import Behavior
    from realm.core.world import World

logger = logging.getLogger(__name__)


class FeatureError(Exception):
    """A feature cannot be loaded: missing, unmet requirement, or collision."""


@dataclass
class _Command:
    name: str
    handler: Callable
    aliases: tuple[str, ...]
    permission: str
    category: str
    help_text: str
    usage: str
    parse_equals: bool
    replace: bool
    tokens: tuple[str, ...] = ()


@dataclass
class _Function:
    name: str
    fn: Callable
    group: str
    readonly: bool
    harm: bool
    takes_frame: bool
    subject: bool
    replace: bool


class Feature:
    """A named set of declarations. See the module docstring."""

    def __init__(self, name: str, *, requires: Sequence[str] = (), doc: str = ""):
        self.name = name
        self.requires = tuple(requires)
        self.doc = doc
        self.commands: list[_Command] = []
        self.behaviors: list[tuple[type, bool]] = []
        self.functions: list[_Function] = []
        self.observers: list[Callable] = []
        self.rulesets: list[tuple[str, type, tuple[str, ...], bool]] = []
        self.dest_resolvers: list[tuple[str, Callable, bool, bool]] = []
        self.reapers: list[Callable] = []
        self.queue_kinds: dict[str, Callable] = {}
        self.check_modifiers: list[Callable] = []
        self.fallbacks: list[Callable] = []
        self.traversal_gates: list[tuple[Callable, str]] = []
        self.after_traverse_hooks: list[Callable] = []
        #: attribute name -> what reads it; ``@examine`` warns when an object
        #: carries one and this feature is not loaded.
        self.attributes: dict[str, str] = {}
        self.name_resolvers: list[Callable] = []
        self.speech_renderers: list[Callable] = []
        self.group_formatters: list[tuple[Callable, bool]] = []
        self.protocols: list[tuple[str, type, dict[str, Any]]] = []
        self.settings: dict[str, tuple[Any, str]] = {}
        self.script_verbs: list[Any] = []
        self.events: list[Any] = []
        self.lock_types: list[Any] = []
        self.entitlements: dict[str, str] = {}
        self.audiences: dict[str, Callable] = {}
        self.def_kinds: list[Any] = []
        self.install_hooks: list[Callable] = []
        self.boot_hooks: list[Callable] = []
        self.close_hooks: list[Callable] = []

    def __repr__(self) -> str:
        return f"<Feature {self.name!r}>"

    # --- declarations ---

    def command(self, name: str, handler: Callable | None = None, *,
                aliases: Sequence[str] = (), permission: str = "player",
                category: str | None = None, help_text: str = "", usage: str = "",
                parse_equals: bool = False, token: str | Sequence[str] = (),
                replace: bool = False):
        """Declare a command. Without ``handler``, a decorator.

        ``token`` is a one-character prefix that runs the command with the
        rest of the line as its arguments (``:waves`` is ``pose waves``);
        a sequence declares several."""
        tokens = (token,) if isinstance(token, str) else tuple(token)
        for t in tokens:
            if len(t) != 1 or t.isalnum() or t.isspace():
                raise FeatureError(f"command {name!r}: token {t!r} must be one "
                                   f"non-alphanumeric, non-space character")

        def declare(fn: Callable) -> Callable:
            self.commands.append(_Command(
                name.lower(), fn, tuple(a.lower() for a in aliases), permission,
                category or self.name, help_text, usage, parse_equals, replace, tokens))
            return fn
        return declare if handler is None else declare(handler)

    def behavior(self, cls: type[Behavior] | None = None, *, replace: bool = False):
        """Declare a behavior class (keyed by its ``behavior_id``). Usable
        as a class decorator."""
        def declare(c: type[Behavior]) -> type[Behavior]:
            self.behaviors.append((c, replace))
            return c
        return declare if cls is None else declare(cls)

    def function(self, fn: Callable | None = None, *, name: str | None = None,
                 group: str | None = None, readonly: bool = False,
                 harm: bool = False, replace: bool = False):
        """Declare a plain native softcode function."""
        def declare(f: Callable) -> Callable:
            self.functions.append(_Function(
                name or f.__name__, f, group or "Game", readonly, harm,
                takes_frame=False, subject=False, replace=replace))
            return f
        return declare if fn is None else declare(fn)

    def softfn(self, fn: Callable | None = None, *, name: str | None = None,
               group: str | None = None, readonly: bool = False, harm: bool = False,
               subject: bool = False, replace: bool = False):
        """Declare a softcode function whose first parameter is the frame."""
        def declare(f: Callable) -> Callable:
            self.functions.append(_Function(
                name or f.__name__, f, group or "Game", readonly, harm,
                takes_frame=True, subject=subject, replace=replace))
            return f
        return declare if fn is None else declare(fn)

    def script_verb(self, name: str, *, aliases: Sequence[str] = (),
                    token: str | None = None, sugar: bool = False, doc: str = "",
                    replace: bool = False):
        """Declare a script command line (``say ...``) handled by an
        ``async (engine, executor, rest_of_line)`` function. ``sugar`` also
        exposes ``name(text)`` inside Python scripts. A decorator."""
        def declare(fn: Callable) -> Callable:
            from realm.scripting.verbs import ScriptVerb
            self.script_verbs.append((ScriptVerb(
                name.lower(), fn, tuple(a.lower() for a in aliases), token, sugar,
                owner=self.name, doc=doc), replace))
            return fn
        return declare

    def event(self, action_type: str | None, *, hook: str | None = None, doc: str = "",
              payload: dict[str, str] | None = None,
              target_lock: tuple[str, str] | None = None,
              tool_lock: tuple[str, str] | None = None, speech: bool = False,
              replace: bool = False) -> None:
        """Declare an action type (or, with ``action_type=None``, a hook fired
        outside propagation): its ``ON_<hook>`` attribute, reference line,
        ``adata()`` payload keys, the lock checked on its target or tool
        (``(lock type, failure template)``), and whether ``{actor}`` is a voice."""
        from realm.core.eventdefs import EventDef
        self.events.append((EventDef(
            action_type, hook.upper() if hook else None, doc, dict(payload or {}),
            target_lock, tool_lock, speech, owner=self.name), replace))

    def lock_type(self, name: str, *, default: str = "True", doc: str = "") -> None:
        """Declare a lock type and the expression it uses when no lock of the
        type is set (``"True"``: open)."""
        from realm.permissions.locks import LOCK_TYPE_RE, LockDef
        if not LOCK_TYPE_RE.match(name):
            raise FeatureError(f"feature {self.name!r}: lock type {name!r} must match "
                               f"{LOCK_TYPE_RE.pattern}")
        self.lock_types.append(LockDef(name, default, doc, owner=self.name))

    def entitlement(self, name: str, doc: str = "") -> None:
        """Declare an entitlement name a role_def may grant and this
        feature's code checks (``has_entitlement(obj, name)``)."""
        self.entitlements[str(name)] = doc

    def audience(self, name: str):
        """Declare a message audience: the decorated ``(action) -> recipients``
        resolves who gets ``action.add_message(name, ...)``. A decorator."""
        def declare(fn: Callable) -> Callable:
            self.audiences[str(name)] = fn
            return fn
        return declare

    def def_kind(self, name: str, tag: str, parse: Callable | None = None) -> None:
        """Declare an in-world definition kind: objects tagged ``tag``, read
        with ``parse(obj)`` (None: the object itself), looked up with
        ``realm.core.defs.all_defs(name)`` / ``find_def(name, ...)``."""
        from realm.core.defs import DefKind
        self.def_kinds.append(DefKind(name, tag, parse, owner=self.name))

    def observer(self, fn: Callable) -> Callable:
        """Declare an ``async (action) -> None`` propagation observer."""
        self.observers.append(fn)
        return fn

    def ruleset(self, name: str, cls: type, *, aliases: Sequence[str] = (),
                replace: bool = False) -> None:
        """Declare a combat ruleset. Used only when ``combat`` is installed."""
        self.rulesets.append((name.lower(), cls, tuple(a.lower() for a in aliases), replace))

    def dest_resolver(self, name: str, fn: Callable, *, shared_destination: bool = True,
                      replace: bool = False) -> None:
        """Declare an async ``(exit_obj, actor) -> room | None`` resolver."""
        self.dest_resolvers.append((name, fn, shared_destination, replace))

    def reaper(self, fn: Callable) -> Callable:
        """Declare an ``async (store) -> Any`` sweep on the reap cadence."""
        self.reapers.append(fn)
        return fn

    def queue_kind(self, kind: str, handler: Callable) -> None:
        """Handle a softcode-queued world op: ``async (engine, frame, obj, payload)``."""
        self.queue_kinds[kind] = handler

    def check_modifier(self, fn: Callable) -> Callable:
        """Declare a ``(obj, skill) -> int`` modifier folded into every check."""
        self.check_modifiers.append(fn)
        return fn

    def fallback(self, fn: Callable) -> Callable:
        """Declare an ``async (ctx) -> bool`` tried when no command matches,
        in feature order, before softcode ``$``-commands. Return True when it
        handled the line (``movement`` walks a typed exit name)."""
        self.fallbacks.append(fn)
        return fn

    def traversal_gate(self, fn: Callable | None = None, *, reason: str = "gate",
                       attrs: Sequence[str] = ()):
        """Declare an ``async (actor, exit_obj, direction) -> str | None``
        asked before anyone walks through an exit. A string blocks the move
        with that message; ``event:on_fail`` fires with ``reason``. ``attrs``
        names the exit attributes the gate reads, so ``@examine`` can say
        they do nothing in a world without this feature."""
        def declare(f: Callable) -> Callable:
            self.traversal_gates.append((f, reason))
            for attr in attrs:
                self.attributes[attr] = f"read by {self.name}'s {reason} gate"
            return f
        return declare if fn is None else declare(fn)

    def after_traverse(self, fn: Callable) -> Callable:
        """Declare an ``async (actor, origin, destination, exit_obj, *,
        fleeing)`` run after anyone walks through an exit."""
        self.after_traverse_hooks.append(fn)
        return fn

    def name_resolver(self, fn: Callable) -> Callable:
        """Declare an override of the name a looker sees an object by.

        Called ``fn(obj, looker, current) -> str`` while ``obj``'s name is
        resolved for ``looker``, ``current`` being the best name so far
        (from ``obj.name``). Return a replacement, or ``current`` to pass:
        short-descs until introduced, a disguise to a looker who hasn't
        seen through it. Speech attribution flows through the same name,
        so a disguise covers a voice too.

        Resolvers run only when the looker can see the object, and only on
        narration and listings, never on ``@examine``, owner readouts or
        logs, which must show the truth. They compose in feature order; one
        that raises is logged and skipped (a cosmetic override must not
        blank a name)."""
        self.name_resolvers.append(fn)
        return fn

    def speech_renderer(self, fn: Callable) -> Callable:
        """Declare a per-listener transform of a spoken body.

        Called ``fn(body, action, looker) -> body`` once per recipient of a
        speech-family message: garble a tongue the listener doesn't know,
        hand a bystander whisper fragments, slur a drunk's line. ``looker``
        is None when nobody in particular is addressed. Renderers compose in
        feature order; one that raises is logged and skipped, keeping the
        last good body (a renderer only rephrases, so it fails open)."""
        self.speech_renderers.append(fn)
        return fn

    def group_formatter(self, fn: Callable | None = None, *, replace: bool = False):
        """Declare how a grouped contents line reads: ``(obj, count) -> str``
        (``lambda obj, n: f"{obj.name} (x{n})"``). One per game; the
        default is "an apple" / "3 apples"."""
        def declare(f: Callable) -> Callable:
            self.group_formatters.append((f, replace))
            return f
        return declare if fn is None else declare(fn)

    def protocol(self, name: str, cls: type, **kwargs: Any) -> None:
        """Declare a protocol server, started with ``(session_manager, on_command, **kwargs)``."""
        self.protocols.append((name, cls, kwargs))

    def setting(self, key: str, default: Any, doc: str = "") -> None:
        """Declare a ``config.py`` key this feature reads (``world.setting(key)``)."""
        self.settings[key] = (default, doc)

    def on_install(self, fn: Callable) -> Callable:
        """``(world) -> None``, run synchronously by ``install_runtime``."""
        self.install_hooks.append(fn)
        return fn

    def on_boot(self, fn: Callable) -> Callable:
        """``async (world) -> None``, after the world is loaded and wired."""
        self.boot_hooks.append(fn)
        return fn

    def on_close(self, fn: Callable) -> Callable:
        """``(world) -> None``, when the world closes."""
        self.close_hooks.append(fn)
        return fn


# --- loading -----------------------------------------------------------------

def _resolve(name: str, required_by: str | None) -> Feature:
    from realm.std import BUILTIN
    path = BUILTIN.get(name, name)
    who = f" (required by {required_by!r})" if required_by else ""
    try:
        module = importlib.import_module(path)
    except ModuleNotFoundError as exc:
        if exc.name and path.startswith(exc.name):
            raise FeatureError(
                f"feature {name!r}{who}: no module {path!r}. A built-in name is one of "
                f"{sorted(BUILTIN)}; anything else is a module path on sys.path "
                f"(the game directory is on it).") from exc
        raise
    feature = getattr(module, "feature", None)
    if not isinstance(feature, Feature):
        raise FeatureError(f"feature {name!r}{who}: module {path!r} has no "
                           f"`feature = Feature(...)` attribute")
    return feature


def load(names: Sequence[str]) -> FeatureSet:
    """Resolve, check and order the named features."""
    features: list[Feature] = []
    seen: dict[str, Feature] = {}
    for name in names:
        if name in seen:
            continue
        feature = _resolve(name, None)
        seen[name] = feature
        features.append(feature)
    loaded = {f.name for f in features}
    for f in features:
        for req in f.requires:
            if req not in loaded:
                raise FeatureError(
                    f"feature {f.name!r} requires {req!r}, which is not in FEATURES. "
                    f"Add {req!r} (or remove {f.name!r}).")
    return FeatureSet(_dependency_order(features))


def _dependency_order(features: list[Feature]) -> list[Feature]:
    by_name = {f.name: f for f in features}
    ordered: list[Feature] = []
    visiting: set[str] = set()
    done: set[str] = set()

    def visit(f: Feature) -> None:
        if f.name in done:
            return
        if f.name in visiting:
            raise FeatureError(f"feature requirements form a cycle through {f.name!r}")
        visiting.add(f.name)
        for req in f.requires:
            visit(by_name[req])
        visiting.discard(f.name)
        done.add(f.name)
        ordered.append(f)

    for f in features:
        visit(f)
    return ordered


class _Claims:
    """Who declared each name, for collision errors."""

    def __init__(self, what: str):
        self.what = what
        self.owner: dict[str, tuple[str, Any]] = {}

    def claim(self, key: str, value: Any, feature: str, replace: bool) -> None:
        held = self.owner.get(key)
        if held is not None and held[1] is not value and not replace:
            raise FeatureError(
                f"{self.what} {key!r} is declared by both {held[0]!r} and {feature!r}. "
                f"Rename one, leave one feature out, or pass replace=True on the "
                f"declaration that should win.")
        self.owner[key] = (feature, value)


@dataclass
class FeatureSet:
    """Loaded features, in dependency order."""

    features: list[Feature]
    settings: dict[str, tuple[Any, str, str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._check_collisions()

    @property
    def names(self) -> list[str]:
        return [f.name for f in self.features]

    def _check_collisions(self) -> None:
        from realm.config.loader import KNOWN_CONFIG_KEYS
        from realm.scripting.registry import static_functions
        commands, behaviors = _Claims("command"), _Claims("behavior")
        command_tokens = _Claims("command token")
        functions, rulesets = _Claims("softcode function"), _Claims("ruleset")
        resolvers, kinds = _Claims("destination resolver"), _Claims("queue kind")
        settings = _Claims("config key")
        verbs, tokens = _Claims("script verb"), _Claims("script verb token")
        event_types, hooks = _Claims("event"), _Claims("event hook")
        lock_names = _Claims("lock type")
        audience_names = _Claims("audience")
        kind_names = _Claims("definition kind")
        formatters = _Claims("group formatter")
        from realm.core.defs import kernel_kinds
        for dk in kernel_kinds():
            kind_names.claim(dk.name, dk.tag, "kernel", False)
        for builtin in ("actor", "target", "room", "remote"):
            audience_names.claim(builtin, builtin, "kernel", False)
        from realm.permissions.locks import _builtin_lock_types
        for lt in _builtin_lock_types():
            lock_names.claim(lt.name, lt.name, "kernel", False)
        from realm.core.eventdefs import kernel_events
        for ev in kernel_events():
            if ev.action_type:
                event_types.claim(ev.action_type, ev, "kernel", False)
            if ev.hook:
                hooks.claim(ev.hook, ev, "kernel", False)
        from realm.scripting.verbs import kernel_verbs
        for verb in kernel_verbs():
            for word in (verb.name, *verb.aliases):
                verbs.claim(word, verb.handler, "kernel", False)
        for key in KNOWN_CONFIG_KEYS:
            settings.claim(key, key, "kernel", False)
        for name, entry in static_functions().items():
            functions.claim(name, entry.fn, entry.owner, False)
        for f in self.features:
            for c in f.commands:
                for key in (c.name, *c.aliases):
                    commands.claim(key, c.handler, f.name, c.replace)
                for tok in c.tokens:
                    command_tokens.claim(tok, c.handler, f.name, c.replace)
            for cls, replace in f.behaviors:
                behaviors.claim(cls.behavior_id, cls, f.name, replace)
            for fn in f.functions:
                functions.claim(fn.name, fn.fn, f.name, fn.replace)
            for name, cls, aliases, replace in f.rulesets:
                for key in (name, *aliases):
                    rulesets.claim(key, cls, f.name, replace)
            for name, fn, _shared, replace in f.dest_resolvers:
                resolvers.claim(name, fn, f.name, replace)
            for kind, handler in f.queue_kinds.items():
                kinds.claim(kind, handler, f.name, False)
            for fn, replace in f.group_formatters:
                formatters.claim("group_formatter", fn, f.name, replace)
            for dk in f.def_kinds:
                kind_names.claim(dk.name, dk, f.name, False)
            for aname, resolver in f.audiences.items():
                audience_names.claim(aname, resolver, f.name, False)
            for lt in f.lock_types:
                lock_names.claim(lt.name, lt, f.name, False)
            for ev, replace in f.events:
                if ev.action_type:
                    event_types.claim(ev.action_type, ev, f.name, replace)
                if ev.hook:
                    hooks.claim(ev.hook, ev, f.name, replace)
            for verb, replace in f.script_verbs:
                for word in (verb.name, *verb.aliases):
                    verbs.claim(word, verb.handler, f.name, replace)
                if verb.token is not None:
                    tokens.claim(verb.token, verb.handler, f.name, replace)
            for key, (default, doc) in f.settings.items():
                settings.claim(key, default, f.name, False)
                self.settings[key] = (default, doc, f.name)

    # --- installing ---

    def install_registries(self) -> None:
        """Reset the global registries to exactly this set's declarations."""
        global _installed
        from realm.combat.system import RulesetRegistry
        from realm.core.behaviors import BehaviorRegistry
        from realm.scripting import registry

        behaviors: dict[str, type] = {cls.behavior_id: cls for cls in _kernel_behaviors()}
        rulesets: dict[str, type] = {}
        functions = []
        for f in self.features:
            for cls, _replace in f.behaviors:
                behaviors[cls.behavior_id] = cls
            for name, cls, aliases, _replace in f.rulesets:
                for key in (name, *aliases):
                    rulesets[key] = cls
            for fn in f.functions:
                functions.append(registry.SoftFn(
                    fn.name, fn.fn, fn.group, fn.readonly, fn.harm,
                    fn.takes_frame, fn.subject, owner=f.name))
        BehaviorRegistry._behaviors = behaviors
        RulesetRegistry._rulesets = rulesets
        registry.activate({"kernel", *self.names}, functions)
        from realm.scripting import verbs as verb_registry
        verb_registry.install([pair for f in self.features for pair in f.script_verbs])
        from realm.core import eventdefs
        eventdefs.install([pair for f in self.features for pair in f.events])
        from realm.permissions.locks import install_lock_types
        install_lock_types([lt for f in self.features for lt in f.lock_types])
        from realm.core.defs import install_def_kinds
        install_def_kinds([dk for f in self.features for dk in f.def_kinds])
        from realm.core.propagation import install_audiences
        install_audiences({k: v for f in self.features for k, v in f.audiences.items()})
        from realm.permissions.entitlements import install_entitlements
        install_entitlements({k: v for f in self.features for k, v in f.entitlements.items()})
        _installed = self

    def install_commands(self, dispatcher) -> None:
        """Register every declared command on ``dispatcher``."""
        for f in self.features:
            for c in f.commands:
                dispatcher.register(
                    c.name, c.handler, aliases=list(c.aliases), help_text=c.help_text,
                    usage=c.usage, permission=c.permission, parse_equals=c.parse_equals,
                    category=c.category, tokens=c.tokens)

    def install_runtime(self, world: World) -> None:
        """Wire the runtime declarations onto ``world``."""
        from realm.core.checks import Checks

        world.features = self
        checks = world.services.setdefault("checks", Checks())
        self.install_commands(world.dispatcher)
        for f in self.features:
            for fn in f.observers:
                world.observe(fn)
            checks.modifier_providers.extend(f.check_modifiers)
            for name, fn, shared, _replace in f.dest_resolvers:
                world.dest_resolvers[name] = (fn, shared)
            for fn in f.fallbacks:
                world.dispatcher.add_fallback(fn)
            world.traversal_gates.extend(f.traversal_gates)
            world.after_traverse.extend(f.after_traverse_hooks)
            world.name_resolvers.extend(f.name_resolvers)
            world.speech_renderers.extend(f.speech_renderers)
            for fn, _replace in f.group_formatters:
                world.group_formatter = fn
            if world.scripts is not None:
                world.scripts.queue_kinds.update(f.queue_kinds)
            world.reapers.extend(f.reapers)
            world.protocols.extend(f.protocols)
        for f in self.features:
            for hook in f.install_hooks:
                hook(world)

    async def boot(self, world: World) -> None:
        """Run every ``on_boot`` hook, in dependency order."""
        for f in self.features:
            for hook in f.boot_hooks:
                await hook(world)

    def close(self, world: World) -> None:
        """Run ``on_close`` hooks (newest feature first), then restore the
        default registries."""
        for f in reversed(self.features):
            for hook in f.close_hooks:
                try:
                    hook(world)
                except Exception:
                    logger.exception(f"on_close of feature {f.name!r} failed")
        install_default()


def _kernel_behaviors() -> list[type]:
    """Behaviors of the kernel's scripting runtime: always installed."""
    import realm.behaviors.scripted  # noqa: F401  (installs the behavior_def fallback)
    from realm.behaviors.ticker import ScriptTickerBehavior
    return [ScriptTickerBehavior]


# --- the default (no live world) ----------------------------------------------

_installed: FeatureSet | None = None
_installing_default = False


def install_default() -> None:
    """Install the ``CLASSIC`` registries (the state with no live world)."""
    global _installing_default
    if _installing_default:
        return
    _installing_default = True
    try:
        from realm.std import CLASSIC
        load(CLASSIC).install_registries()
    finally:
        _installing_default = False


def ensure_registries() -> None:
    """Install the default registries on first use."""
    if _installed is None:
        install_default()


def installed() -> FeatureSet | None:
    """The feature set whose registries are installed."""
    return _installed


def unloaded_attribute_owners(attrs: Iterable[str], loaded: Iterable[str]) -> dict[str, str]:
    """Which of ``attrs`` a built-in feature gives meaning to, when that
    feature is not among ``loaded``: attribute -> feature name. ``@examine``
    uses it to say a ``check_skill`` does nothing in a world without
    ``rules``."""
    from realm.std import BUILTIN
    wanted, have = set(attrs), set(loaded)
    out: dict[str, str] = {}
    for name in BUILTIN:
        if name in have or not wanted:
            continue
        for attr in _resolve(name, None).attributes:
            if attr in wanted:
                out[attr] = name
    return out


__all__ = ["Feature", "FeatureError", "FeatureSet", "load", "install_default",
           "ensure_registries", "installed", "unloaded_attribute_owners"]
