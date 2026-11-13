"""
Built-in script functions for REALM.

These functions are available to user scripts for common operations.
They are injected into the script namespace and provide safe access
to game functionality.

Categories:
- Object access: get(), name(), loc(), owner()
- Attribute access: get_attr(), set_attr(), has_attr()
- Tag operations: has_tag(), tags()
- String operations: ucfirst(), lcfirst(), capstr()
- Math operations: rand(), dice(), clamp()
- List operations: first(), rest(), member(), words()
- Communication: pemit(), remit(), oemit()
"""

from __future__ import annotations

from types import MethodType
from typing import TYPE_CHECKING, Any

from realm.scripting.registry import registered

if TYPE_CHECKING:
    from realm.core.objects import GameObject



# The sigil that marks a get()/reference spec as a friendly keyid lookup
# ('$banknet_core') rather than a name — game-tunable like the trigger and
# emote sigils, and (unlike the hardcoded '#' id prefix) any length. Ambient
# module state, wired at server construction alongside the other sigils.
DEFAULT_KEYID_SIGIL = '$'
_keyid_sigil = DEFAULT_KEYID_SIGIL


def set_keyid_sigil(sigil: str = DEFAULT_KEYID_SIGIL) -> None:
    """Install the keyid sigil (game config). Any length (1-16 chars); no
    whitespace or alphanumerics (a sigil of 'key' would swallow ordinary
    names), and it may not start with '#' — that prefix is reserved for raw
    id lookup, which is tested first. A bad sigil raises at boot, not
    mid-lookup."""
    global _keyid_sigil
    s = str(sigil)
    if (not s or len(s) > 16 or s.startswith('#')
            or any(c.isalnum() or c.isspace() for c in s)):
        raise ValueError(
            "keyid sigil must be 1-16 non-alphanumeric, non-space characters "
            f"and may not start with '#' (got {sigil!r})")
    _keyid_sigil = s


def get_keyid_sigil() -> str:
    return _keyid_sigil


class ScriptFrame:
    """The state of one softcode run: who runs it (``executor``), who
    triggered it (``enactor``), where (``location``), the ``store``, the
    ``subject`` of ``skill()``/``check()``, and the ``command_queue`` of
    world operations the engine delivers afterwards.

    The functions themselves live in ``realm/scripting/lib/`` and take the
    frame as their first argument. ``frame.get_attr(...)`` (any registered
    function name) calls that function with this frame, so library code and
    tests can use them directly.
    """

    def __init__(
        self,
        enactor: GameObject | None = None,
        executor: GameObject | None = None,
        location: GameObject | None = None,
        persistence: Any = None,  # PersistenceManager
        enactor_consent: bool = False,
    ):
        self.enactor = enactor
        self.executor = executor
        self.location = location
        self.store = persistence
        # True ONLY when the enactor deliberately invoked this object —
        # typed its $-command, or traversed the exit whose ON_FAIL is
        # running. Grants move_to/enter_instance the right to relocate the
        # ENACTOR (a portal moving its walker). Merely being overheard
        # (^listen) or witnessed (ON_ENTER) is NOT consent — those paths
        # leave this False, so scripts there need real control() authority.
        self.enactor_consent = enactor_consent
        # Whose skill ``skill()`` reads and who rolls ``check()``: the enactor
        # by default; build_namespace sets the viewer, caller or roller.
        self.subject = enactor

        # Deliveries queued by communication functions. Scripts execute in a
        # worker thread, so functions must never touch sessions directly —
        # the engine drains this queue on the event loop after execution.
        # Entries: (kind, obj, payload). Message kinds (pemit/remit/oemit)
        # carry a string; world-op kinds (save/destroy/death_check/combat/
        # wait) carry op-specific payloads. Drained by ScriptEngine.
        self.command_queue: list[tuple[str, GameObject, Any]] = []

    def may_mutate(self, obj: GameObject | None) -> bool:
        """Scripts run AS the executor; mutations require its authority."""
        from realm.permissions.locks import controls as _controls
        return _controls(self.executor, obj)

    def may_relocate(self, obj: GameObject | None) -> bool:
        """Relocation authority — broader than mutation: the executor may
        also move what stands in a room the executor owns (Penn's
        room-owner teleport). Used only by movement functions."""
        from realm.permissions.locks import may_relocate as _may_relocate
        return _may_relocate(self.executor, obj)

    def controlled(self, obj: GameObject | str | None) -> GameObject | None:
        """Resolve + authority in one step: None means no or not allowed."""
        target = self.resolve(obj)
        if target is None or not self.may_mutate(target):
            return None
        return target

    def touch(self, obj: GameObject) -> None:
        """Queue a persistence save for a mutated object."""
        self.command_queue.append(('save', obj, ''))

    def apply(self, op, *args, **kwargs):
        """Run a synchronous op from ``realm.core.ops`` as the executor.
        Queues a save for every object it touched and returns its
        ``OpResult``, or None when the op refused (softcode then returns
        False)."""
        from realm.core.ops import OpError
        try:
            result = op(self.executor, *args, **kwargs)
        except OpError:
            return None
        for obj in result.touched:
            self.touch(obj)
        return result

    def allowed(self, check, *args, **kwargs) -> bool:
        """Run an op's ``check_<op>`` as the executor: True when it passes."""
        from realm.core.ops import OpError
        try:
            check(self.executor, *args, **kwargs)
        except OpError:
            return False
        return True

    def in_reach(self, target: GameObject | None) -> bool:
        """
        Proximity authority for combat channels: a trap can hurt whoever
        is standing on it, not someone across the map.
        """
        if target is None or self.executor is None:
            return False
        if target is self.executor:
            return True
        if target.location is self.executor:
            return True  # standing inside the executor (room traps, containers)
        if self.executor.location is target:
            return True  # carried BY the target (a cursed idol biting its taker)
        return (target.location is not None
                and target.location is self.executor.location)

    def resolve(self, spec: GameObject | str | None) -> GameObject | None:
        """Resolve a string spec to an object; pass objects through."""
        if isinstance(spec, str):
            return self.get(spec)
        return spec

    def __getattr__(self, name: str) -> Any:
        """``frame.<softcode function>``: the registered function bound to
        this frame. Only called for names the frame itself lacks."""
        entry = registered().get(name)
        if entry is None:
            raise AttributeError(name)
        return self._bind(entry)

    def to_dict(self) -> dict[str, Any]:
        """The script namespace: every registered function, bound to this
        frame, plus the context names ``me``, ``here`` and ``enactor``.

        Harm-flagged functions are simply not bound when the executing frame
        may not author harm (see ``may_harm``). The sandbox has empty
        ``__builtins__`` and an AST allowlist, so an unbound name cannot be
        recovered: leaving it out is the boundary.
        """
        may_harm = self.may_harm()
        namespace: dict[str, Any] = {
            name: self._bind(entry) for name, entry in registered().items()
            if may_harm or not entry.harm
        }
        namespace.update(me=self.executor, here=self.location, enactor=self.enactor)
        return namespace

    def readonly_dict(self) -> dict[str, Any]:
        """The check-pass namespace: only ``readonly`` functions, plus the
        context names. No mutators, so decision-pass softcode is structurally
        unable to change the world."""
        namespace: dict[str, Any] = {
            name: self._bind(entry) for name, entry in registered().items()
            if entry.readonly
        }
        namespace.update(me=self.executor, here=self.location, enactor=self.enactor)
        return namespace

    def _bind(self, entry) -> Any:
        return MethodType(entry.fn, self) if entry.takes_frame else entry.fn

    def may_harm(self) -> bool:
        """May the executing frame author harm? (composition trust model)

        Walk the executor's owner-delegation chain: HARM anywhere -> allow
        (builder+, or a role_def grant); a ``player``/``guest`` mortal as the
        responsible principal with no HARM -> deny; an unowned / NPC / system
        world object -> allow (trusted by construction — designers, imports,
        and the world itself are not untrusted players). This gates the
        AUTHOR, carried as the executor's delegated authority, never the
        invoker: a builder's dart still fires in a player's hand because the
        dart delegates to its builder owner."""
        from realm.permissions import has_entitlement
        from realm.permissions.entitlements import HARM

        node, depth = self.executor, 0
        while node is not None and depth < 5:
            if has_entitlement(node, HARM):
                return True
            if node.is_player or node.has_tag('guest'):
                return False
            node = node.owner
            depth += 1
        return True


# Importing the function library registers every built-in softcode function.
import realm.scripting.lib  # noqa: E402,F401
