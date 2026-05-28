"""
Two-pass propagation engine for actions.

Actions flow through a chain of Step objects. The default chain visits:
    Actor → Room → RoomContents (bystanders) → Target

Each step runs a permission pass (on_check) then a reaction pass (on_react).
Both passes always run to completion, even after a block — this is important
for behaviors that need to observe blocked attempts (traps, audit logs, NPC
reactions). Only the resolution of the action itself (if any) is skipped by
a block; that resolution lives outside the engine, in whichever behavior
cares about the specific action_type.

Each object controls its own propagation depth via the visitor pattern.
A GameObject walks its own behaviors. A Character can override visit_check
to also walk its equipment. A Pet could walk its rider. Future types add
layers by overriding the visitor, not by changing the engine.

Trailing actions queued during propagation (via action.queue_trailing) are
processed after the parent action completes, depth-limited to MAX_TRAILING_DEPTH
to prevent runaway chain reactions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional, Protocol

if TYPE_CHECKING:
    from realm.core.objects import GameObject


@dataclass
class Action:
    """
    A single event flowing through the propagation chain.

    ``action_type`` is a hierarchical string like ``event:on_enter``,
    ``skill:lockpick``, ``combat:on_hit``, ``item:on_get``. The prefix is the
    domain; the suffix names the specific action. Behaviors filter on either
    the full string or the domain.

    ``tags`` are orthogonal properties for cross-cutting matches — e.g. any
    hostile action carries ``"hostile"``, any action that makes noise carries
    ``"sound"``. A single behavior like ``AlertOnSound`` can react to any
    sound-making action regardless of action_type.

    During the permission pass behaviors may:
      - Call ``action.block(reason)`` to veto (both passes still complete).
      - Call ``action.add_modifier(value, reason)`` to accumulate adjustments.
      - Call ``action.add_data(key, value)`` to inject context for downstream.

    During the reaction pass behaviors may:
      - Call ``action.add_message(audience, msg)`` to queue output.
      - Call ``action.queue_trailing(other)`` to chain another action.
    """

    actor: Optional[GameObject]
    target: Optional[GameObject]
    action_type: str

    tool: Optional[GameObject] = None
    chain: Optional[list[Step]] = None
    tags: set[str] = field(default_factory=set)
    extra: dict[str, Any] = field(default_factory=dict)

    # Permission-pass accumulators
    blocked: bool = False
    block_reason: str = ""
    modifiers: list[tuple[int, str]] = field(default_factory=list)

    # Reaction-pass accumulators
    messages: dict[str, list[str]] = field(
        default_factory=lambda: {"actor": [], "target": [], "room": []}
    )
    trailing_actions: list[Action] = field(default_factory=list)

    @property
    def domain(self) -> str:
        """The part of action_type before the first colon, or the whole string."""
        return self.action_type.split(":", 1)[0] if ":" in self.action_type else self.action_type

    @property
    def total_modifier(self) -> int:
        """Sum of accumulated modifier values."""
        return sum(value for value, _ in self.modifiers)

    def has_tag(self, tag: str) -> bool:
        return tag in self.tags

    def block(self, reason: str) -> None:
        """Block this action. Both propagation passes still complete."""
        self.blocked = True
        self.block_reason = reason

    def add_modifier(self, value: int, reason: str) -> None:
        self.modifiers.append((value, reason))

    def add_message(self, audience: str, msg: str) -> None:
        """Queue a message. Standard audiences: 'actor', 'target', 'room'."""
        self.messages.setdefault(audience, []).append(msg)

    def add_data(self, key: str, value: Any) -> None:
        self.extra[key] = value

    def queue_trailing(self, action: Action) -> None:
        """Queue a follow-up action. Processed after this one, depth-limited."""
        self.trailing_actions.append(action)

    def format_message(self, msg: str, looker: Optional[GameObject] = None) -> str:
        """Substitute ``{actor}``, ``{target}``, and ``{tool}`` in a message."""
        actor_name = self.actor.name if self.actor is not None else "Someone"
        target_name = self.target.name if self.target is not None else "something"
        tool_name = self.tool.name if self.tool is not None else "something"
        return (
            msg.replace("{actor}", actor_name)
               .replace("{target}", target_name)
               .replace("{tool}", tool_name)
        )


class Step(Protocol):
    """A single step in the propagation chain."""

    async def on_check(self, action: Action) -> None: ...
    async def on_react(self, action: Action) -> None: ...


def _get_room(action: Action) -> Optional[GameObject]:
    """
    Find the room for an action.

    Returns target's location, or target itself if the target acts as a room
    (has contents and no location of its own — e.g. on_enter events where
    the target IS the destination room).
    """
    target = action.target
    if target is None:
        return None
    location = getattr(target, "location", None)
    if location is not None:
        return location
    if hasattr(target, "contents"):
        return target
    return None


class ActorStep:
    """Propagate through the actor (and whatever the actor chooses to walk)."""

    async def on_check(self, action: Action) -> None:
        actor = action.actor
        if actor is not None and hasattr(actor, "visit_check"):
            await actor.visit_check(action)

    async def on_react(self, action: Action) -> None:
        actor = action.actor
        if actor is not None and hasattr(actor, "visit_react"):
            await actor.visit_react(action)


class RoomStep:
    """Propagate through the room and its own behaviors."""

    async def on_check(self, action: Action) -> None:
        room = _get_room(action)
        if room is not None and hasattr(room, "visit_check"):
            await room.visit_check(action)

    async def on_react(self, action: Action) -> None:
        room = _get_room(action)
        if room is not None and hasattr(room, "visit_react"):
            await room.visit_react(action)


ContentsFn = Callable[[Action], Iterable["GameObject"]]


class RoomContentsStep:
    """
    Propagate through bystanders: room contents other than actor and target.

    By default reads contents from the room found by ``_get_room``. Pass a
    custom ``get_contents`` callable to change where contents are read from —
    for example when the target IS the room (on_enter events), contents must
    come directly from the target instead of from target.location.contents.
    """

    def __init__(self, get_contents: Optional[ContentsFn] = None):
        self._get_contents = get_contents

    def _contents(self, action: Action) -> Iterable[GameObject]:
        if self._get_contents is not None:
            return self._get_contents(action)
        room = _get_room(action)
        if room is None:
            return ()
        return room.contents

    async def on_check(self, action: Action) -> None:
        for obj in self._contents(action):
            if obj is action.actor or obj is action.target:
                continue
            if hasattr(obj, "visit_observe_check"):
                await obj.visit_observe_check(action)

    async def on_react(self, action: Action) -> None:
        for obj in self._contents(action):
            if obj is action.actor or obj is action.target:
                continue
            if hasattr(obj, "visit_observe_react"):
                await obj.visit_observe_react(action)


class TargetStep:
    """Propagate through the target (and whatever the target chooses to walk)."""

    async def on_check(self, action: Action) -> None:
        target = action.target
        if target is not None and hasattr(target, "visit_check"):
            await target.visit_check(action)

    async def on_react(self, action: Action) -> None:
        target = action.target
        if target is not None and hasattr(target, "visit_react"):
            await target.visit_react(action)


# Pre-built chain for actions whose target IS the room itself (broadcasts:
# speech, emote, on_enter, on_leave, connect/disconnect notifications). The
# default chain would visit the room twice — once via RoomStep (target.location
# falls back to target.contents) and once via TargetStep — so this chain
# explicitly drops RoomStep and reads bystanders directly from target.contents.
ROOM_TARGET_CHAIN: list[Step] = [
    ActorStep(),
    TargetStep(),  # target IS the room
    RoomContentsStep(get_contents=lambda a: a.target.contents),
]


class PropagationEngine:
    """
    Two-pass propagation engine.

    Default chain: Actor → Room → RoomContents → Target. Override per-action
    via ``Action.chain`` — see ``ROOM_TARGET_CHAIN`` for broadcast actions.

    The permission pass does not short-circuit on block — all behaviors in
    the chain run to completion, so observers (traps, loggers, NPC reactions)
    still see blocked attempts. The reaction pass likewise always runs.
    """

    default_chain: list[Step] = [
        ActorStep(),
        RoomStep(),
        RoomContentsStep(),
        TargetStep(),
    ]

    MAX_TRAILING_DEPTH = 3

    async def propagate(
        self,
        action: Action,
        _depth: int = 0,
        deliver: bool = False,
    ) -> Action:
        """
        Run an action through both passes, then optionally deliver its
        messages, then recursively propagate any trailing actions.

        ``deliver`` propagates through the recursion — when True, every action
        in the trailing tree gets its messages delivered as soon as its react
        pass completes (before any of its own trailing children fire). This
        gives a natural readout: parent event → its messages → chain reactions
        → their messages.

        Default is ``deliver=False`` so direct callers of the engine (mostly
        tests) can inspect ``action.messages`` without side effects. The
        module-level ``propagate()`` convenience function defaults to True.
        """
        chain = action.chain if action.chain is not None else self.default_chain

        for step in chain:
            await step.on_check(action)

        for step in chain:
            await step.on_react(action)

        if deliver:
            deliver_messages(action)

        if action.trailing_actions and _depth < self.MAX_TRAILING_DEPTH:
            for trailing in action.trailing_actions:
                await self.propagate(trailing, _depth=_depth + 1, deliver=deliver)

        return action


_engine: Optional[PropagationEngine] = None


def get_engine() -> PropagationEngine:
    """Return the module-level PropagationEngine singleton."""
    global _engine
    if _engine is None:
        _engine = PropagationEngine()
    return _engine


def reset_engine() -> None:
    """Drop the module-level engine (for tests that want a fresh one)."""
    global _engine
    _engine = None


async def propagate(
    action: Action,
    engine: Optional[PropagationEngine] = None,
    deliver: bool = True,
) -> Action:
    """
    Propagate an action through the engine, optionally delivering messages.

    With ``deliver=True`` (default), every action in the propagation tree —
    the parent and any trailing actions, recursively — gets its messages
    delivered as soon as its react pass completes. Pass ``deliver=False`` when
    the caller does its own messaging (combat systems are the typical case)
    or when a test wants to inspect raw accumulated messages without side
    effects.
    """
    return await (engine or get_engine()).propagate(action, deliver=deliver)


def _delivery_room(action: Action) -> Optional[GameObject]:
    """Find the room used as the audience for 'room' messages."""
    if action.actor is not None:
        loc = getattr(action.actor, "location", None)
        if loc is not None:
            return loc
    if action.target is not None:
        loc = getattr(action.target, "location", None)
        if loc is not None:
            return loc
        # Target may BE the room (on_enter case).
        if hasattr(action.target, "msg_contents"):
            return action.target
    return None


def deliver_messages(action: Action) -> None:
    """
    Deliver an action's accumulated messages to their audiences.

    - 'actor' messages go to ``action.actor.msg(...)``
    - 'target' messages go to ``action.target.msg(...)`` (skipped if target is actor)
    - 'room' messages go to the delivery room's ``msg_contents(..., exclude=[actor, target])``

    All messages are passed through ``action.format_message`` first, which
    substitutes ``{actor}`` / ``{target}`` / ``{tool}`` placeholders.

    Audiences other than 'actor' / 'target' / 'room' are ignored here — they
    can still be inspected on ``action.messages`` by any caller that wants
    custom delivery (NPC AI, channel routing, GMCP packages, etc.).
    """
    actor = action.actor
    target = action.target

    if actor is not None:
        for msg in action.messages.get("actor", ()):
            actor.msg(action.format_message(msg))

    if target is not None and target is not actor:
        for msg in action.messages.get("target", ()):
            target.msg(action.format_message(msg))

    room = _delivery_room(action)
    if room is not None and hasattr(room, "msg_contents"):
        exclude = [obj for obj in (actor, target) if obj is not None]
        for msg in action.messages.get("room", ()):
            room.msg_contents(action.format_message(msg), exclude=exclude)


__all__ = [
    "Action",
    "Step",
    "ActorStep",
    "RoomStep",
    "RoomContentsStep",
    "TargetStep",
    "ROOM_TARGET_CHAIN",
    "PropagationEngine",
    "get_engine",
    "reset_engine",
    "propagate",
    "deliver_messages",
]
