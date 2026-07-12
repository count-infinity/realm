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

import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from realm.core.objects import GameObject

logger = logging.getLogger(__name__)


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

    actor: GameObject | None
    target: GameObject | None
    action_type: str

    tool: GameObject | None = None
    chain: list[Step] | None = None
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
    # Messages that only make sense if the action succeeds ("You say ...").
    # deliver_messages suppresses these when the action is blocked, while
    # regular messages (a trap announcing itself) always deliver.
    success_messages: dict[str, list[str]] = field(default_factory=dict)
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

    def add_message(self, audience: str, msg: str, *, success_only: bool = False) -> None:
        """
        Queue a message. Standard audiences: 'actor', 'target', 'room'.

        ``success_only=True`` marks a message that must not deliver if the
        action ends up blocked — the calling convention for a command's own
        outcome lines ("You say ..."), letting the command bake them before
        propagating and still gate on ``action.blocked`` afterwards.
        """
        if success_only:
            self.success_messages.setdefault(audience, []).append(msg)
        else:
            self.messages.setdefault(audience, []).append(msg)

    def add_data(self, key: str, value: Any) -> None:
        self.extra[key] = value

    def queue_trailing(self, action: Action) -> None:
        """Queue a follow-up action. Processed after this one, depth-limited."""
        self.trailing_actions.append(action)

    def format_message(self, msg: str, looker: GameObject | None = None) -> str:
        """
        Substitute participant tokens in a message template.

        Tokens, for each of ``actor`` / ``target`` / ``tool``:
          - ``{target}``     — bare name: "apple"
          - ``{target:a}``   — indefinite: "an apple" (article overrides
                               and proper nouns handled by core.language)
          - ``{target:the}`` — definite: "the apple"

        ``looker`` makes formatting perception-aware: each participant is
        named via ``get_display_name(looker)``, so a recipient who can't
        see the actor reads "Someone picks up an apple." Unseen
        participants take no article.
        """
        from realm.core.language import definite_name, singular_name

        result = msg
        for token, obj, missing in (
            ("actor", self.actor, "Someone"),
            ("target", self.target, "something"),
            ("tool", self.tool, "something"),
        ):
            if f"{{{token}" not in result:
                continue
            if obj is None:
                bare = indefinite = definite = missing
            else:
                bare = obj.get_display_name(looker)
                if bare == obj.name:
                    indefinite = singular_name(obj)
                    definite = definite_name(obj)
                else:
                    # Unseen: "Someone"/"something" reads wrong with an
                    # article attached.
                    indefinite = definite = bare
            result = (
                result.replace(f"{{{token}:a}}", indefinite)
                      .replace(f"{{{token}:the}}", definite)
                      .replace(f"{{{token}}}", bare)
            )
        return result


class Step(Protocol):
    """A single step in the propagation chain."""

    async def on_check(self, action: Action) -> None: ...
    async def on_react(self, action: Action) -> None: ...


def _get_room(action: Action) -> GameObject | None:
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

    def __init__(self, get_contents: ContentsFn | None = None):
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


def _room_of(obj: GameObject | None) -> GameObject | None:
    """An object's room: its location, or itself if it acts as a room."""
    if obj is None:
        return None
    loc = getattr(obj, "location", None)
    if loc is not None:
        return loc
    if hasattr(obj, "contents"):
        return obj
    return None


RoomsFn = Callable[[Action], Iterable["GameObject"]]


class RemoteStep:
    """
    Visit a SET of rooms and their occupants — the far leg of a multiroom
    action (scry, remote cast, zone alarm). Each room *participates* via
    ``visit_check`` (a ward there can veto), and its occupants *observe*
    (they witness and may react). The rooms are resolved from the action on
    each pass, so one step serves one destination or a whole zone —
    identical two-pass semantics either way.
    """

    def __init__(self, get_rooms: RoomsFn):
        self._get_rooms = get_rooms

    async def _visit(self, action: Action, room_method: str,
                     obs_method: str) -> None:
        for room in self._get_rooms(action) or ():
            if room is None:
                continue
            visit = getattr(room, room_method, None)
            if visit is not None:
                await visit(action)
            for obj in list(getattr(room, "contents", ())):
                if obj is action.actor or obj is action.target:
                    continue
                obs = getattr(obj, obs_method, None)
                if obs is not None:
                    await obs(action)

    async def on_check(self, action: Action) -> None:
        await self._visit(action, "visit_check", "visit_observe_check")

    async def on_react(self, action: Action) -> None:
        await self._visit(action, "visit_react", "visit_observe_react")


def _origin_rooms(action: Action) -> list[GameObject]:
    """The actor's own room — the origin leg (local wards + bystanders)."""
    room = _room_of(action.actor)
    return [room] if room is not None else []


def remote_chain(get_rooms: RoomsFn) -> list[Step]:
    """
    A chain for a **multiroom** action: actor → the actor's own room (local
    wards + bystanders) → the target itself → the destination room(s) (each
    room's ward + occupants). Every leg gets the two-pass, so an action can
    be vetoed at the origin *or* at any destination, and all react. One
    destination (scry) and many (a zone alarm) are the same mechanism.
    """
    return [ActorStep(), RemoteStep(_origin_rooms), TargetStep(),
            RemoteStep(get_rooms)]


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

    def __init__(self):
        # Cross-cutting systems (the script engine) that see every action
        # after its react pass. Not for per-object logic — that's behaviors.
        self._observers: list[Callable[[Action], Awaitable[None]]] = []

    def add_observer(self, observer: Callable[[Action], Awaitable[None]]) -> None:
        """
        Register an async callable invoked with every propagated action,
        at every depth of the trailing tree, after the reaction pass and
        message delivery. Observers see blocked actions too (check
        ``action.blocked``). An observer that emits new actions must bound
        its own recursion — a fresh ``propagate()`` starts a fresh tree.
        """
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer: Callable[[Action], Awaitable[None]]) -> None:
        """Unregister an observer registered with add_observer."""
        if observer in self._observers:
            self._observers.remove(observer)

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

        # Observers run after delivery so their own output (an NPC replying
        # to overheard speech) reads after the action that provoked it. A
        # failing observer must never break the action being propagated.
        for observer in list(self._observers):
            try:
                await observer(action)
            except Exception:
                logger.exception(
                    f"Action observer failed on {action.action_type}"
                )

        if action.trailing_actions and _depth < self.MAX_TRAILING_DEPTH:
            for trailing in action.trailing_actions:
                await self.propagate(trailing, _depth=_depth + 1, deliver=deliver)

        return action


_engine: PropagationEngine | None = None


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
    engine: PropagationEngine | None = None,
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


async def gate_action(
    action: Action,
    *,
    fail_msg: str = "You can't do that.",
    engine: PropagationEngine | None = None,
) -> bool:
    """
    Propagate an action that a lock or behavior may veto.

    The gated calling convention: build the action WITHOUT success
    messages, gate it, and only on True mutate state, add the success
    messages, and call deliver_messages(action).

    On a block this messages the actor with the block reason (or
    ``fail_msg``) and delivers any behavior-added messages (a trap
    announcing itself), then returns False. Trailing actions propagate
    without delivery here — the same trade-off as the movement gate.
    """
    await propagate(action, engine=engine, deliver=False)
    if action.blocked:
        if action.actor is not None:
            action.actor.msg(action.block_reason or fail_msg)
        deliver_messages(action)
        return False
    return True


def _delivery_room(action: Action) -> GameObject | None:
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
    - 'room' messages go to everyone else in the delivery room

    Every message is formatted **per recipient** via
    ``action.format_message(msg, looker=recipient)``, so perception rules
    apply: a bystander who can't see the actor reads "Someone picks up an
    apple." while an admin in the same room reads "Alice picks up an
    apple." Recipients without a message handler (unlinked NPCs, items)
    are skipped before formatting.

    Audiences other than 'actor' / 'target' / 'room' are ignored here — they
    can still be inspected on ``action.messages`` by any caller that wants
    custom delivery (NPC AI, channel routing, GMCP packages, etc.).
    """
    actor = action.actor
    target = action.target

    def audience_messages(audience: str) -> list[str]:
        msgs: list[str] = []
        if not action.blocked:
            msgs.extend(action.success_messages.get(audience, ()))
        msgs.extend(action.messages.get(audience, ()))
        return msgs

    if actor is not None:
        for msg in audience_messages("actor"):
            actor.msg(action.format_message(msg, looker=actor))

    if target is not None and target is not actor:
        for msg in audience_messages("target"):
            target.msg(action.format_message(msg, looker=target))

    room = _delivery_room(action)
    if room is not None:
        room_msgs = audience_messages("room")
        if room_msgs:
            # Every non-participant gets the message (matching the old
            # msg_contents semantics — subclasses may override .msg() for
            # listen-style reactions even without a session handler).
            for recipient in room.contents:
                if recipient is actor or recipient is target:
                    continue
                for msg in room_msgs:
                    recipient.msg(action.format_message(msg, looker=recipient))

    # 'remote' messages go to the occupants of a far room (multiroom
    # actions — scry, zone alarm). The room(s) come from extra['remote_rooms']
    # (a list) or extra['remote_room'] (one).
    remote_rooms = action.extra.get("remote_rooms")
    if remote_rooms is None:
        one = action.extra.get("remote_room")
        remote_rooms = [one] if one is not None else []
    if remote_rooms:
        remote_msgs = audience_messages("remote")
        for remote_room in remote_rooms:
            for recipient in list(getattr(remote_room, "contents", ())):
                if recipient is actor:
                    continue
                for msg in remote_msgs:
                    recipient.msg(action.format_message(msg, looker=recipient))


__all__ = [
    "Action",
    "Step",
    "ActorStep",
    "RoomStep",
    "RoomContentsStep",
    "TargetStep",
    "RemoteStep",
    "remote_chain",
    "ROOM_TARGET_CHAIN",
    "PropagationEngine",
    "get_engine",
    "reset_engine",
    "propagate",
    "gate_action",
    "deliver_messages",
]
