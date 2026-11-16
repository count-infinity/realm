"""
Features: how code joins a REALM world.

A *feature* is a named bundle of declarations: commands, behaviors,
softcode functions, propagation observers, combat rulesets, destination
resolvers, reapers, softcode queue kinds, check modifiers, protocols,
pool definitions and config settings. A game is a list of features (``FEATURES`` in
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

import functools
import importlib
import importlib.util
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
        self.input_interceptors: list[tuple[int, Callable]] = []
        self.logins: list[Callable] = []
        self.traversal_gates: list[tuple[Callable, str]] = []
        self.after_traverse_hooks: list[Callable] = []
        #: attribute name -> what reads it; ``@examine`` warns when an object
        #: carries one and this feature is not loaded.
        self.attributes: dict[str, str] = {}
        self.sight_rules: list[Callable] = []
        self.markers: list[Callable] = []
        self.name_resolvers: list[Callable] = []
        self.speech_renderers: list[Callable] = []
        self.deaf_rules: list[Callable] = []
        self.prompts: list[tuple[Callable, bool]] = []
        self.group_formatters: list[tuple[Callable, bool]] = []
        self.protocols: list[tuple[str, type, dict[str, Any]]] = []
        self.pools: list[tuple[Any, bool]] = []
        self.settings: dict[str, tuple[Any, str]] = {}
        self.script_verbs: list[Any] = []
        self.events: list[Any] = []
        self.lock_types: list[Any] = []
        self.entitlements: dict[str, str] = {}
        self.audiences: dict[str, Callable] = {}
        self.def_kinds: list[Any] = []
        self.install_hooks: list[Callable] = []
        self.reload_hooks: list[Callable] = []
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
              listen: bool = False, replace: bool = False) -> None:
        """Declare an action type (or, with ``action_type=None``, a hook fired
        outside propagation): its ``ON_<hook>`` attribute, reference line,
        ``adata()`` payload keys, the lock checked on its target or tool
        (``(lock type, failure template)``), whether ``{actor}`` is a voice,
        and whether its ``extra["message"]`` is overheard by softcode
        ``^listen`` triggers (``listen``)."""
        from realm.core.eventdefs import EventDef
        self.events.append((EventDef(
            action_type, hook.upper() if hook else None, doc, dict(payload or {}),
            target_lock, tool_lock, speech, listen, owner=self.name), replace))

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

    def input_interceptor(self, fn: Callable | None = None, *, order: int = 0):
        """Declare an ``async (world, session, line) -> bool`` that sees a
        line of input after the session's own prompt and before the
        dispatcher, lowest ``order`` first. True means it consumed the line
        (``accounts`` routes a character still in creation to chargen)."""
        def declare(f: Callable) -> Callable:
            self.input_interceptors.append((order, f))
            return f
        return declare if fn is None else declare(fn)

    def login(self, fn: Callable) -> Callable:
        """Declare the ``async (ctx) -> None`` that handles input from a
        session with no player (``connect``, ``create``). One per game."""
        self.logins.append(fn)
        return fn

    def fallback(self, fn: Callable) -> Callable:
        """Declare an ``async (ctx) -> bool`` tried when no command matches,
        in feature order, before softcode ``$``-commands. Return True when it
        handled the line (``movement`` walks a typed exit name)."""
        self.fallbacks.append(fn)
        return fn

    def traversal_gate(self, fn: Callable | None = None, *, reason: str = "gate",
                       attrs: Sequence[str] = ()):
        """Declare an ``async (actor, exit_obj, direction, *, fleeing) ->
        str | None`` asked before anyone walks (``exit_obj`` may be None). A
        string blocks the move with that message; ``event:on_fail`` fires with ``reason``. ``attrs``
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

    def sight_rule(self, fn: Callable) -> Callable:
        """Declare a ``(viewer, obj) -> bool | None`` rule of sight, asked
        after the kernel's (you see yourself; SEE_ALL sees everything):
        False hides ``obj`` from ``viewer``, None has no opinion. The
        ``sight`` feature's darkness and invisibility, and ``stealth``'s
        ``hidden``, are rules like this."""
        self.sight_rules.append(fn)
        return fn

    def marker(self, fn: Callable) -> Callable:
        """Declare a ``(obj, looker) -> str | None`` parenthetical marker on
        a name in room listings (``a key (hidden)``, ``a torch (glowing)``),
        in feature order."""
        self.markers.append(fn)
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

    def deaf_rule(self, fn: Callable) -> Callable:
        """Declare a ``(recipient, action) -> bool`` rule of hearing, asked
        for each recipient of an action's queued messages
        (``deliver_messages``): True keeps every message of that action
        from that recipient. ``vitals`` makes a sleeper deaf to the room
        (but not to what is addressed to them, the action's target)."""
        self.deaf_rules.append(fn)
        return fn

    def prompt(self, fn: Callable | None = None, *, replace: bool = False):
        """Declare the game's prompt: ``(player) -> str | None``, the line a
        player sees after each batch of output (None or "" for none). One
        per game; ``basics`` declares the default, and a game's own
        replaces it with ``replace=True``."""
        def declare(f: Callable) -> Callable:
            self.prompts.append((f, replace))
            return f
        return declare if fn is None else declare(fn)

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

    def pool(self, pool: Any, *, replace: bool = False) -> None:
        """Declare a world-default pool definition (``realm.core.pools.Pool``):
        how ``shields`` or ``hull`` behaves on every object that has one and
        does not define it in its own ``pools`` attribute."""
        from dataclasses import replace as with_fields
        self.pools.append((with_fields(pool, owner=self.name), replace))

    def setting(self, key: str, default: Any, doc: str = "") -> None:
        """Declare a ``config.py`` key this feature reads (``world.setting(key)``)."""
        self.settings[key] = (default, doc)

    def on_install(self, fn: Callable) -> Callable:
        """``(world) -> None``, run synchronously by ``install_runtime``."""
        self.install_hooks.append(fn)
        return fn

    def on_reload(self, fn: Callable) -> Callable:
        """Declare a ``(world) -> None`` run when the world's data is reloaded
        (``@reload``, an area or pack import): ``rules`` re-reads its skill
        table."""
        self.reload_hooks.append(fn)
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

#: Where a built-in feature named ``x`` is declared, first match wins.
BUILTIN_ROOTS = ("realm.std", "realm.games")

#: The entry-point group an installed package declares its features in:
#: ``[project.entry-points."realm.features"]`` / ``weather = "realm_weather:feature"``.
ENTRY_POINT_GROUP = "realm.features"


def default_features() -> list[str]:
    """The ``FEATURES`` default (``Settings``), as a list of names."""
    from realm.config.loader import Settings
    return feature_names(Settings().features)


def feature_names(spec: Sequence[str] | str | None) -> list[str]:
    """``spec`` as a list of feature names: a list as is, a dotted path to a
    list (``"realm.std.CLASSIC"``) imported, None the default."""
    if spec is None:
        return default_features()
    if isinstance(spec, str):
        module_path, _, attr = spec.rpartition(".")
        try:
            return list(getattr(importlib.import_module(module_path), attr))
        except (ImportError, AttributeError, ValueError) as exc:
            raise FeatureError(f"FEATURES = {spec!r}: not a dotted path to a list of "
                               f"feature names ({exc})") from exc
    return list(spec)


def _builtin_module(name: str) -> str | None:
    """The module declaring built-in feature ``name`` (``realm.std.talk.feature``),
    or None when no built-in has that name."""
    if "." in name:
        return None
    for root in BUILTIN_ROOTS:
        if importlib.util.find_spec(f"{root}.{name}") is not None:
            return f"{root}.{name}.feature"
    return None


def builtin_names() -> list[str]:
    """Every built-in feature: each package under ``BUILTIN_ROOTS`` with a
    ``feature.py``."""
    import pkgutil
    names = []
    for root in BUILTIN_ROOTS:
        package = importlib.import_module(root)
        for info in pkgutil.iter_modules(package.__path__):
            if info.ispkg and importlib.util.find_spec(f"{root}.{info.name}.feature"):
                names.append(info.name)
    return sorted(names)


def _distribution(entry: Any) -> str:
    """``realm-weather 1.0`` for an entry point's package."""
    dist = getattr(entry, "dist", None)
    return f"{dist.name} {dist.version}" if dist is not None else entry.value


def installed_packages() -> dict[str, list[Any]]:
    """The features installed packages declare: entry-point name -> its
    entry points (more than one is a conflict). Nothing is imported. The
    scan is cached per ``sys.path``: what is installed changes only with it
    (a package installed into a running process is seen at its next start)."""
    import sys
    return _scan_packages(tuple(sys.path))


@functools.lru_cache(maxsize=8)
def _scan_packages(path: tuple[str, ...]) -> dict[str, list[Any]]:
    from importlib.metadata import entry_points
    found: dict[str, list[Any]] = {}
    seen: set[tuple[str, str, str]] = set()
    for entry in entry_points(group=ENTRY_POINT_GROUP):
        key = (entry.name, entry.value, _distribution(entry))
        if key in seen:                     # one package found twice on sys.path
            continue
        seen.add(key)
        found.setdefault(entry.name, []).append(entry)
    return found


def _check_installed(packages: dict[str, list[Any]]) -> None:
    """An installed package may not claim a built-in name, and two may not
    claim one name."""
    for name, entries in sorted(packages.items()):
        sources = ", ".join(sorted(_distribution(e) for e in entries))
        if _builtin_module(name) is not None:
            raise FeatureError(
                f"feature {name!r} is built in, and also installed by {sources}. "
                f"Uninstall the package or ask its author to rename the entry point.")
        if len(entries) > 1:
            raise FeatureError(f"feature {name!r} is installed by more than one "
                               f"package ({sources}); uninstall all but one.")


def _from_entry_point(name: str, entry: Any, who: str) -> Feature:
    source = _distribution(entry)
    feature = entry.load()
    if not isinstance(feature, Feature):
        raise FeatureError(f"feature {name!r}{who}: the entry point {entry.value!r} in "
                           f"{source} is not a Feature ({type(feature).__name__})")
    if feature.name != name:
        raise FeatureError(f"feature {name!r}{who}: the entry point in {source} loads "
                           f"a feature named {feature.name!r}; the names must match")
    return feature


def _resolve(name: str, required_by: str | None,
             packages: dict[str, list[Any]]) -> Feature:
    """``name`` as a built-in, then an installed package's entry point, then
    a module path (``game`` is the game directory's ``game.py``)."""
    who = f" (required by {required_by!r})" if required_by else ""
    path = _builtin_module(name)
    if path is None and name in packages:
        return _from_entry_point(name, packages[name][0], who)
    if path is None:
        path = name
    try:
        module = importlib.import_module(path)
    except ModuleNotFoundError as exc:
        if exc.name and path.startswith(exc.name):
            listed = sorted(packages) or ["none"]
            raise FeatureError(
                f"feature {name!r}{who}: no module {path!r}. A built-in name is one of "
                f"{builtin_names()}; installed packages provide {listed}; anything "
                f"else is a module path on sys.path (the game directory is on it)."
            ) from exc
        raise
    feature = getattr(module, "feature", None)
    if not isinstance(feature, Feature):
        raise FeatureError(f"feature {name!r}{who}: module {path!r} has no "
                           f"`feature = Feature(...)` attribute")
    return feature


def load(names: Sequence[str] | str | None = None) -> FeatureSet:
    """Resolve, check and order the named features (a list, a dotted path
    to one, or None for the ``FEATURES`` default). A name is a built-in, an
    installed package's feature (``ENTRY_POINT_GROUP``) or a module path.
    Installed packages are only read: one runs when ``names`` lists it."""
    packages = installed_packages()
    _check_installed(packages)
    features: list[Feature] = []
    seen: dict[str, Feature] = {}
    for name in feature_names(names):
        if name in seen:
            continue
        feature = _resolve(name, None, packages)
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
        prompts = _Claims("prompt")
        logins = _Claims("login handler")
        pool_names = _Claims("pool")
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
            for fn, replace in f.prompts:
                prompts.claim("prompt", fn, f.name, replace)
            for fn in f.logins:
                logins.claim("login", fn, f.name, False)
            for pool, replace in f.pools:
                pool_names.claim(pool.name, pool, f.name, replace)
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
        _RULESETS.clear()
        _RULESETS.update(rulesets)
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

        world.features = self
        self.install_commands(world.dispatcher)
        for f in self.features:
            for fn in f.observers:
                world.observe(fn)
            world.check_modifiers.extend(f.check_modifiers)
            for name, fn, shared, _replace in f.dest_resolvers:
                world.dest_resolvers[name] = (fn, shared)
            for fn in f.fallbacks:
                world.dispatcher.add_fallback(fn)
            world.input_interceptors.extend(f.input_interceptors)
            world.reload_hooks.extend(f.reload_hooks)
            for fn in f.logins:
                world.dispatcher.set_login_handler(fn)
            world.traversal_gates.extend(f.traversal_gates)
            world.after_traverse.extend(f.after_traverse_hooks)
            world.sight_rules.extend(f.sight_rules)
            world.markers.extend(f.markers)
            world.name_resolvers.extend(f.name_resolvers)
            world.speech_renderers.extend(f.speech_renderers)
            world.deaf_rules.extend(f.deaf_rules)
            for fn, _replace in f.group_formatters:
                world.group_formatter = fn
            for fn, _replace in f.prompts:
                world.prompt_renderer = fn
            if world.scripts is not None:
                world.scripts.queue_kinds.update(f.queue_kinds)
            world.reapers.extend(f.reapers)
            world.protocols.extend(f.protocols)
            for pool, _replace in f.pools:
                world.pools[pool.name] = pool
        world.input_interceptors.sort(key=lambda pair: pair[0])
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
    from realm.scripting.ticker import ScriptTickerBehavior
    return [ScriptTickerBehavior]


# --- the default (no live world) ----------------------------------------------

_installed: FeatureSet | None = None
_installing_default = False


def install_default() -> None:
    """Install the default features' registries (``CLASSIC``: the state
    with no live world)."""
    global _installing_default
    if _installing_default:
        return
    _installing_default = True
    try:
        load().install_registries()
    finally:
        _installing_default = False


def ensure_registries() -> None:
    """Install the default registries on first use."""
    if _installed is None:
        install_default()


#: The installed features' combat rulesets, by name (``feature.ruleset``);
#: the ``combat`` feature's ``RulesetRegistry`` reads it.
_RULESETS: dict[str, type] = {}


def ruleset_table() -> dict[str, type]:
    """The installed rulesets by name (the CLASSIC set when no world is live).
    Mutable: ``RulesetRegistry.register`` adds to it (tests)."""
    ensure_registries()
    return _RULESETS


@dataclass
class Available:
    """A feature a game could list in ``FEATURES``, for ``realm features``."""

    name: str
    source: str                      # "built-in", "installed: pkg 1.0", "game directory (game)"
    feature: Feature | None = None
    error: str | None = None         # why it could not be read

    def declared(self) -> dict[str, int]:
        """What the feature declares: label -> count, for the non-empty ones."""
        if self.feature is None:
            return {}
        skip = {"name", "requires", "doc"}
        out = {}
        for attr, value in vars(self.feature).items():
            if attr in skip or not isinstance(value, (list, dict, tuple)) or not value:
                continue
            label = "softcode functions" if attr == "functions" else attr.replace("_", " ")
            out[label] = len(value)
        return out


def available(game_names: Sequence[str] = ()) -> list[Available]:
    """Every feature a game could list: the built-ins, each installed
    package's, and the game directory's (the names in ``game_names`` that
    are neither, imported to read them). Conflicts are shown, not raised."""
    out = [Available(name, "built-in", feature=_resolve(name, None, {}))
           for name in builtin_names()]
    packages = installed_packages()
    for name, entries in sorted(packages.items()):
        for entry in entries:
            item = Available(name, f"installed: {_distribution(entry)}")
            if _builtin_module(name) is not None:
                item.error = "conflicts with the built-in of that name"
            elif len(entries) > 1:
                item.error = "installed by more than one package"
            else:
                try:
                    item.feature = _from_entry_point(name, entry, "")
                except Exception as exc:  # a broken package is reported, not fatal
                    item.error = str(exc)
            out.append(item)
    for name in game_names:
        if _builtin_module(name) is not None or name in packages:
            continue
        try:
            feature = _resolve(name, None, packages)
        except Exception as exc:
            out.append(Available(name, f"game directory ({name})", error=str(exc)))
            continue
        out.append(Available(feature.name, f"game directory ({name})", feature=feature))
    return out


def installed() -> FeatureSet | None:
    """The feature set whose registries are installed."""
    return _installed


def unloaded_attribute_owners(attrs: Iterable[str], loaded: Iterable[str]) -> dict[str, str]:
    """Which of ``attrs`` a built-in feature gives meaning to, when that
    feature is not among ``loaded``: attribute -> feature name. ``@examine``
    uses it to say a ``check_skill`` does nothing in a world without
    ``rules``."""
    wanted, have = set(attrs), set(loaded)
    out: dict[str, str] = {}
    for name in default_features():
        if name in have or not wanted:
            continue
        for attr in _resolve(name, None, {}).attributes:
            if attr in wanted:
                out[attr] = name
    return out


__all__ = ["Feature", "FeatureError", "FeatureSet", "load", "feature_names",
           "default_features", "install_default", "builtin_names", "installed_packages",
           "Available", "available",
           "ENTRY_POINT_GROUP",
           "ensure_registries", "installed", "unloaded_attribute_owners"]
