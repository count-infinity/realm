"""
Tests for realm.core.propagation — the two-pass propagation engine.

Coverage:
  - Action data class basics (block, modifiers, messages, data, trailing, format)
  - Empty propagation (no actor/target/room) doesn't crash
  - Default chain order: Actor → Room → RoomContents → Target
  - Bystanders use visit_observe_*, actor/target excluded from contents
  - Permission pass runs to completion after a block
  - Reaction pass always runs after a block
  - Modifiers, messages, and data accumulate from any object in the chain
  - Custom Action.chain overrides default
  - Custom RoomContentsStep get_contents handles room-as-target case
  - Trailing actions process depth-limited to MAX_TRAILING_DEPTH
  - Subclasses can override visit_check to walk child objects
"""

from __future__ import annotations

import pytest

from realm.core.behaviors import Behavior
from realm.core.objects import GameObject
from realm.core.propagation import (
    Action,
    ActorStep,
    PropagationEngine,
    RoomContentsStep,
    TargetStep,
    deliver_messages,
    propagate,
)
from realm.gateway.session import Session

# --- Test helpers ---------------------------------------------------------


class TraceBehavior(Behavior):
    """Records every on_check / on_react call into a shared trace list."""

    behavior_id = "trace"

    def __init__(self, label: str, trace: list, **params):
        super().__init__(**params)
        self.label = label
        self.trace = trace

    async def on_check(self, obj, action):
        self.trace.append(("check", self.label, obj.name, action.action_type))

    async def on_react(self, obj, action):
        self.trace.append(("react", self.label, obj.name, action.action_type))


class BlockingBehavior(Behavior):
    """Blocks every action it sees during the permission pass."""

    behavior_id = "block"

    def __init__(self, reason: str = "blocked", **params):
        super().__init__(**params)
        self.reason = reason

    async def on_check(self, obj, action):
        action.block(self.reason)


class ModifierBehavior(Behavior):
    """Adds a fixed modifier during the permission pass."""

    behavior_id = "modifier"

    def __init__(self, value: int, reason: str, **params):
        super().__init__(**params)
        self.value = value
        self.reason = reason

    async def on_check(self, obj, action):
        action.add_modifier(self.value, self.reason)


class MessageBehavior(Behavior):
    """Adds a message to a given audience during the reaction pass."""

    behavior_id = "msg"

    def __init__(self, audience: str, msg: str, **params):
        super().__init__(**params)
        self.audience = audience
        self.msg = msg

    async def on_react(self, obj, action):
        action.add_message(self.audience, self.msg)


class TrailingBehavior(Behavior):
    """
    Queues N trailing actions during the FIRST reaction pass it sees.

    Fire-once so the trailing actions don't recursively re-trigger this same
    behavior — for the recursive case see RecursiveTrailing in the depth test.
    """

    behavior_id = "trailing"

    def __init__(self, count: int = 1, **params):
        super().__init__(**params)
        self.count = count
        self._fired = False

    async def on_react(self, obj, action):
        if self._fired:
            return
        self._fired = True
        for _ in range(self.count):
            action.queue_trailing(
                Action(actor=action.actor, target=action.target, action_type=action.action_type)
            )


def make_room(name: str = "Room") -> GameObject:
    return GameObject(name=name, tags=["room"])


def make_object(name: str, location: GameObject | None = None) -> GameObject:
    return GameObject(name=name, location=location)


# --- Action ---------------------------------------------------------------


class TestAction:

    def test_domain_with_colon(self):
        a = Action(actor=None, target=None, action_type="event:on_enter")
        assert a.domain == "event"

    def test_domain_without_colon(self):
        a = Action(actor=None, target=None, action_type="tick")
        assert a.domain == "tick"

    def test_block_sets_state(self):
        a = Action(actor=None, target=None, action_type="x")
        a.block("locked")
        assert a.blocked
        assert a.block_reason == "locked"

    def test_modifiers_accumulate(self):
        a = Action(actor=None, target=None, action_type="x")
        a.add_modifier(2, "skill")
        a.add_modifier(-1, "darkness")
        assert a.total_modifier == 1
        assert a.modifiers == [(2, "skill"), (-1, "darkness")]

    def test_messages_grouped_by_audience(self):
        a = Action(actor=None, target=None, action_type="x")
        a.add_message("actor", "hi")
        a.add_message("room", "thud")
        a.add_message("actor", "again")
        assert a.messages["actor"] == ["hi", "again"]
        assert a.messages["room"] == ["thud"]

    def test_messages_unknown_audience_is_created(self):
        a = Action(actor=None, target=None, action_type="x")
        a.add_message("npc:guard", "alert!")
        assert a.messages["npc:guard"] == ["alert!"]

    def test_data_injection(self):
        a = Action(actor=None, target=None, action_type="x")
        a.add_data("damage", 5)
        assert a.extra["damage"] == 5

    def test_trailing_actions_queue(self):
        a = Action(actor=None, target=None, action_type="x")
        b = Action(actor=None, target=None, action_type="y")
        a.queue_trailing(b)
        assert a.trailing_actions == [b]

    def test_has_tag(self):
        a = Action(actor=None, target=None, action_type="x", tags={"hostile"})
        assert a.has_tag("hostile")
        assert not a.has_tag("magic")

    def test_format_message_substitutes(self):
        actor = make_object("Alice")
        target = make_object("Bob")
        tool = make_object("Sword")
        a = Action(actor=actor, target=target, action_type="x", tool=tool)
        assert a.format_message("{actor} hits {target} with {tool}") == "Alice hits Bob with Sword"

    def test_format_message_handles_missing(self):
        a = Action(actor=None, target=None, action_type="x")
        assert a.format_message("{actor} -> {target} ({tool})") == "Someone -> something (something)"


# --- Engine basics --------------------------------------------------------


@pytest.mark.asyncio
class TestPropagationEngine:

    async def test_no_listeners_does_not_crash(self):
        action = Action(actor=None, target=None, action_type="x")
        await PropagationEngine().propagate(action)
        assert not action.blocked

    async def test_actor_only(self):
        trace = []
        actor = make_object("Alice")
        actor.add_behavior(TraceBehavior("actor", trace))
        action = Action(actor=actor, target=None, action_type="x")

        await PropagationEngine().propagate(action)

        assert trace == [
            ("check", "actor", "Alice", "x"),
            ("react", "actor", "Alice", "x"),
        ]

    async def test_chain_order_actor_room_bystander_target(self):
        """Default chain: Actor → Room → RoomContents (bystanders) → Target."""
        trace = []
        room = make_room("Tavern")
        actor = make_object("Alice", location=room)
        target = make_object("Bob", location=room)
        bystander = make_object("Charlie", location=room)

        room.add_behavior(TraceBehavior("room", trace))
        actor.add_behavior(TraceBehavior("actor", trace))
        target.add_behavior(TraceBehavior("target", trace))
        bystander.add_behavior(TraceBehavior("bystander", trace))

        action = Action(actor=actor, target=target, action_type="x")
        await PropagationEngine().propagate(action)

        # Each phase visits in chain order; both phases run.
        labels_check = [t for t in trace if t[0] == "check"]
        labels_react = [t for t in trace if t[0] == "react"]

        assert [t[1] for t in labels_check] == ["actor", "room", "bystander", "target"]
        assert [t[1] for t in labels_react] == ["actor", "room", "bystander", "target"]
        # All checks come before any react.
        first_react_idx = next(i for i, t in enumerate(trace) if t[0] == "react")
        assert all(t[0] == "check" for t in trace[:first_react_idx])

    async def test_bystanders_exclude_actor_and_target(self):
        """RoomContentsStep skips the actor and target when iterating contents."""
        trace = []
        room = make_room()
        actor = make_object("Alice", location=room)
        target = make_object("Bob", location=room)
        bystander = make_object("Charlie", location=room)

        actor.add_behavior(TraceBehavior("actor", trace))
        target.add_behavior(TraceBehavior("target", trace))
        bystander.add_behavior(TraceBehavior("bystander", trace))

        action = Action(actor=actor, target=target, action_type="x")
        await PropagationEngine().propagate(action)

        # Actor and target each appear exactly twice (check + react), not four
        # times — they are NOT also visited as bystanders.
        actor_visits = [t for t in trace if t[2] == "Alice"]
        target_visits = [t for t in trace if t[2] == "Bob"]
        bystander_visits = [t for t in trace if t[2] == "Charlie"]
        assert len(actor_visits) == 2
        assert len(target_visits) == 2
        assert len(bystander_visits) == 2

    async def test_block_does_not_short_circuit_permission_pass(self):
        """Even after block, ALL on_check calls in the chain still run."""
        trace = []
        room = make_room()
        actor = make_object("Alice", location=room)
        target = make_object("Bob", location=room)
        bystander = make_object("Charlie", location=room)

        # Actor blocks immediately. Room/bystander/target should still see check.
        actor.add_behavior(BlockingBehavior("nope"))
        room.add_behavior(TraceBehavior("room", trace))
        bystander.add_behavior(TraceBehavior("bystander", trace))
        target.add_behavior(TraceBehavior("target", trace))

        action = Action(actor=actor, target=target, action_type="x")
        await PropagationEngine().propagate(action)

        check_labels = [t[1] for t in trace if t[0] == "check"]
        assert check_labels == ["room", "bystander", "target"]
        assert action.blocked
        assert action.block_reason == "nope"

    async def test_reaction_pass_runs_after_block(self):
        """Reaction pass always runs, even on block."""
        trace = []
        actor = make_object("Alice")
        actor.add_behavior(BlockingBehavior("denied"))
        actor.add_behavior(TraceBehavior("actor", trace))

        action = Action(actor=actor, target=None, action_type="x")
        await PropagationEngine().propagate(action)

        assert action.blocked
        assert ("react", "actor", "Alice", "x") in trace

    async def test_modifiers_accumulate_across_chain(self):
        room = make_room()
        actor = make_object("Alice", location=room)
        target = make_object("Bob", location=room)

        actor.add_behavior(ModifierBehavior(2, "skill"))
        room.add_behavior(ModifierBehavior(-1, "darkness"))
        target.add_behavior(ModifierBehavior(-3, "armor"))

        action = Action(actor=actor, target=target, action_type="combat:attack")
        await PropagationEngine().propagate(action)

        assert action.total_modifier == -2
        assert ("skill" in [r for _, r in action.modifiers]
                and "darkness" in [r for _, r in action.modifiers]
                and "armor" in [r for _, r in action.modifiers])

    async def test_messages_accumulate_per_audience(self):
        room = make_room()
        actor = make_object("Alice", location=room)
        target = make_object("Bob", location=room)
        bystander = make_object("Charlie", location=room)

        actor.add_behavior(MessageBehavior("actor", "you swing"))
        target.add_behavior(MessageBehavior("target", "alice swings at you"))
        bystander.add_behavior(MessageBehavior("room", "alice swings at bob"))

        action = Action(actor=actor, target=target, action_type="combat:attack")
        await PropagationEngine().propagate(action)

        assert action.messages["actor"] == ["you swing"]
        assert action.messages["target"] == ["alice swings at you"]
        assert action.messages["room"] == ["alice swings at bob"]


# --- Custom chains --------------------------------------------------------


@pytest.mark.asyncio
class TestCustomChains:

    async def test_action_chain_overrides_default(self):
        """Action.chain replaces the default chain entirely."""
        trace = []
        room = make_room()
        actor = make_object("Alice", location=room)
        target = make_object("Bob", location=room)

        actor.add_behavior(TraceBehavior("actor", trace))
        room.add_behavior(TraceBehavior("room", trace))
        target.add_behavior(TraceBehavior("target", trace))

        # Chain that visits only the target — no actor, no room, no bystanders.
        action = Action(
            actor=actor, target=target, action_type="x",
            chain=[TargetStep()],
        )
        await PropagationEngine().propagate(action)

        labels = {t[1] for t in trace}
        assert labels == {"target"}

    async def test_room_as_target_via_custom_contents(self):
        """When target IS a room, supply a get_contents that reads target.contents."""
        trace = []
        room = make_room("Destination")
        actor = make_object("Alice")  # actor is OUTSIDE the destination room
        bystander = make_object("Bob", location=room)

        actor.add_behavior(TraceBehavior("actor", trace))
        room.add_behavior(TraceBehavior("room", trace))
        bystander.add_behavior(TraceBehavior("bystander", trace))

        action = Action(
            actor=actor, target=room, action_type="event:on_enter",
            chain=[
                ActorStep(),
                # Target is the room itself; bystanders come from target.contents.
                RoomContentsStep(get_contents=lambda a: a.target.contents),
                # No TargetStep — that would double-visit the room.
            ],
        )
        await PropagationEngine().propagate(action)

        # Order: actor, then bystander (room is target, excluded from contents).
        check_labels = [t[1] for t in trace if t[0] == "check"]
        assert check_labels == ["actor", "bystander"]


# --- Trailing actions -----------------------------------------------------


@pytest.mark.asyncio
class TestTrailingActions:

    async def test_trailing_actions_process(self):
        trace = []
        actor = make_object("Alice")
        actor.add_behavior(TrailingBehavior(count=1))
        actor.add_behavior(TraceBehavior("actor", trace))

        action = Action(actor=actor, target=None, action_type="x")
        await PropagationEngine().propagate(action)

        # Original action + 1 trailing = 2 react calls on actor.
        react_count = sum(1 for t in trace if t[0] == "react")
        assert react_count == 2

    async def test_trailing_action_messages_are_delivered(self):
        """
        Regression: a trailing action's audience messages must reach session
        queues when propagate(deliver=True). Previously the engine recursed
        into trailing actions but only delivered the top-level action's
        messages — trailing messages were silently dropped.

        This is the AhearGreeter pattern: a behavior reacts to speech by
        queueing a trailing speech-response action; observers must hear it.
        """
        captured: list[str] = []
        room = make_room()
        actor = make_object("Alice", location=room)
        listener = make_object("Bob", location=room)
        listener.set_msg_handler(captured.append)

        class TrailingResponder(Behavior):
            behavior_id = "trailing_responder"

            async def on_react(self, obj, action):
                if action.action_type != "event:speech":
                    return
                # Queue a response action — separate event, separate audiences.
                response = Action(
                    actor=obj,
                    target=obj.location,
                    action_type="event:speech",
                    extra={"message": "echo"},
                )
                response.add_message("room", "{actor} echoes back.")
                action.queue_trailing(response)

        # Put the responder on a third party so we don't infinite-loop on
        # the actor's own speech.
        responder = make_object("Echo", location=room)
        responder.add_behavior(TrailingResponder())

        action = Action(actor=actor, target=room, action_type="event:speech")
        await propagate(action, deliver=True)

        # The trailing speech action's room message should have reached Bob.
        assert "Echo echoes back." in captured, captured

    async def test_engine_propagate_does_not_deliver_by_default(self):
        """Direct engine.propagate(action) is delivery-free for test ergonomics."""
        captured: list[str] = []
        actor = make_object("Alice")
        actor.set_msg_handler(captured.append)
        actor.add_behavior(MessageBehavior("actor", "you act"))

        action = Action(actor=actor, target=None, action_type="x")
        await PropagationEngine().propagate(action)  # no deliver arg

        assert captured == [], "engine.propagate should not deliver by default"
        assert action.messages["actor"] == ["you act"]

    async def test_trailing_depth_is_limited(self):
        """Each trailing action that queues another stops at MAX_TRAILING_DEPTH."""
        trace = []
        actor = make_object("Alice")

        class RecursiveTrailing(Behavior):
            behavior_id = "rt"

            async def on_react(self, obj, action):
                trace.append("react")
                action.queue_trailing(
                    Action(actor=action.actor, target=None, action_type="x")
                )

        actor.add_behavior(RecursiveTrailing())

        action = Action(actor=actor, target=None, action_type="x")
        engine = PropagationEngine()
        await engine.propagate(action)

        # Depth 0 (original) + depth 1, 2, 3 trailing = 4 total reactions,
        # then depth check stops further recursion.
        assert len(trace) == 1 + engine.MAX_TRAILING_DEPTH


# --- Visitor extension point ---------------------------------------------


@pytest.mark.asyncio
class TestVisitorExtension:

    async def test_subclass_can_walk_child_objects(self):
        """A GameObject subclass can override visit_check to walk children."""
        trace = []

        class CharacterWithEquipment(GameObject):
            __slots__ = ("equipment",)

            def __init__(self, name, equipment, **kwargs):
                super().__init__(name, **kwargs)
                self.equipment = equipment

            async def visit_check(self, action):
                await super().visit_check(action)
                for item in self.equipment:
                    await item.visit_check(action)

            async def visit_react(self, action):
                await super().visit_react(action)
                for item in self.equipment:
                    await item.visit_react(action)

        sword = make_object("Sword")
        sword.add_behavior(TraceBehavior("sword", trace))

        alice = CharacterWithEquipment("Alice", equipment=[sword])
        alice.add_behavior(TraceBehavior("alice", trace))

        action = Action(actor=alice, target=None, action_type="combat:attack")
        await PropagationEngine().propagate(action)

        # Actor's own behaviors run first, then equipped item's.
        check_labels = [t[1] for t in trace if t[0] == "check"]
        assert check_labels == ["alice", "sword"]


# --- Module-level convenience function ------------------------------------


@pytest.mark.asyncio
class TestPropagateConvenience:

    async def test_module_propagate_uses_singleton(self):
        actor = make_object("Alice")
        action = Action(actor=actor, target=None, action_type="x")
        result = await propagate(action, deliver=False)
        assert result is action  # propagate returns the same action

    async def test_module_propagate_accepts_custom_engine(self):
        engine = PropagationEngine()
        actor = make_object("Alice")
        action = Action(actor=actor, target=None, action_type="x")
        result = await propagate(action, engine=engine, deliver=False)
        assert result is action


# --- GameObject.msg / msg_contents / handler wiring ---------------------


class TestGameObjectMsg:

    def test_msg_with_no_handler_is_silent(self):
        obj = make_object("Alice")
        # Should not raise.
        obj.msg("hello")

    def test_msg_routes_through_installed_handler(self):
        captured: list[str] = []
        obj = make_object("Alice")
        obj.set_msg_handler(captured.append)
        obj.msg("hello")
        obj.msg("again")
        assert captured == ["hello", "again"]

    def test_clear_msg_handler_stops_delivery(self):
        captured: list[str] = []
        obj = make_object("Alice")
        obj.set_msg_handler(captured.append)
        obj.msg("first")
        obj.clear_msg_handler()
        obj.msg("dropped")
        assert captured == ["first"]

    def test_set_msg_handler_to_none_clears(self):
        captured: list[str] = []
        obj = make_object("Alice")
        obj.set_msg_handler(captured.append)
        obj.set_msg_handler(None)
        obj.msg("dropped")
        assert captured == []

    def test_msg_contents_delivers_to_each_child(self):
        room = make_room()
        a_log: list[str] = []
        b_log: list[str] = []
        a = make_object("Alice", location=room)
        b = make_object("Bob", location=room)
        a.set_msg_handler(a_log.append)
        b.set_msg_handler(b_log.append)

        room.msg_contents("the lights flicker")

        assert a_log == ["the lights flicker"]
        assert b_log == ["the lights flicker"]

    def test_msg_contents_excludes_listed_objects(self):
        room = make_room()
        a_log: list[str] = []
        b_log: list[str] = []
        c_log: list[str] = []
        a = make_object("Alice", location=room)
        b = make_object("Bob", location=room)
        c = make_object("Charlie", location=room)
        a.set_msg_handler(a_log.append)
        b.set_msg_handler(b_log.append)
        c.set_msg_handler(c_log.append)

        room.msg_contents("alice swings at bob", exclude=[a, b])

        assert a_log == []
        assert b_log == []
        assert c_log == ["alice swings at bob"]

    def test_msg_contents_handles_none_in_exclude(self):
        """Exclude list with None entries shouldn't crash."""
        room = make_room()
        a_log: list[str] = []
        a = make_object("Alice", location=room)
        a.set_msg_handler(a_log.append)
        room.msg_contents("ping", exclude=[None, None])
        assert a_log == ["ping"]


# --- deliver_messages ----------------------------------------------------


@pytest.mark.asyncio
class TestDeliverMessages:

    async def test_actor_messages_delivered(self):
        captured: list[str] = []
        actor = make_object("Alice")
        actor.set_msg_handler(captured.append)
        action = Action(actor=actor, target=None, action_type="x")
        action.add_message("actor", "you swing")
        deliver_messages(action)
        assert captured == ["you swing"]

    async def test_target_messages_delivered_when_distinct(self):
        actor_log: list[str] = []
        target_log: list[str] = []
        actor = make_object("Alice")
        target = make_object("Bob")
        actor.set_msg_handler(actor_log.append)
        target.set_msg_handler(target_log.append)
        action = Action(actor=actor, target=target, action_type="x")
        action.add_message("target", "alice swings at you")
        deliver_messages(action)
        assert actor_log == []
        assert target_log == ["alice swings at you"]

    async def test_target_messages_skipped_when_target_is_actor(self):
        """Self-target actions don't double-message the actor via 'target'."""
        captured: list[str] = []
        actor = make_object("Alice")
        actor.set_msg_handler(captured.append)
        action = Action(actor=actor, target=actor, action_type="x")
        action.add_message("actor", "you focus")
        action.add_message("target", "should-not-deliver")
        deliver_messages(action)
        assert captured == ["you focus"]

    async def test_room_messages_exclude_actor_and_target(self):
        room = make_room()
        actor_log: list[str] = []
        target_log: list[str] = []
        bystander_log: list[str] = []
        actor = make_object("Alice", location=room)
        target = make_object("Bob", location=room)
        bystander = make_object("Charlie", location=room)
        actor.set_msg_handler(actor_log.append)
        target.set_msg_handler(target_log.append)
        bystander.set_msg_handler(bystander_log.append)

        action = Action(actor=actor, target=target, action_type="x")
        action.add_message("room", "alice swings at bob")
        deliver_messages(action)

        # Actor and target receive nothing on the 'room' channel; only the
        # bystander does.
        assert actor_log == []
        assert target_log == []
        assert bystander_log == ["alice swings at bob"]

    async def test_room_messages_format_placeholders(self):
        room = make_room()
        bystander_log: list[str] = []
        actor = make_object("Alice", location=room)
        target = make_object("Bob", location=room)
        bystander = make_object("Charlie", location=room)
        bystander.set_msg_handler(bystander_log.append)

        action = Action(actor=actor, target=target, action_type="x")
        action.add_message("room", "{actor} swings at {target}")
        deliver_messages(action)

        assert bystander_log == ["Alice swings at Bob"]

    async def test_room_target_uses_target_as_room(self):
        """When target IS the room (on_enter), 'room' messages broadcast through it."""
        destination = make_room("Tavern")
        bystander_log: list[str] = []
        bystander = make_object("Charlie", location=destination)
        bystander.set_msg_handler(bystander_log.append)
        actor = make_object("Alice")  # actor is not yet in the room

        action = Action(actor=actor, target=destination, action_type="event:on_enter")
        action.add_message("room", "{actor} arrives.")
        deliver_messages(action)

        assert bystander_log == ["Alice arrives."]

    async def test_unknown_audience_ignored_by_default_delivery(self):
        """Audiences other than actor/target/room are left on action.messages."""
        captured: list[str] = []
        actor = make_object("Alice")
        actor.set_msg_handler(captured.append)
        action = Action(actor=actor, target=None, action_type="x")
        action.add_message("npc:guard", "alert!")
        deliver_messages(action)
        # Custom audience not delivered, but still inspectable on the action.
        assert captured == []
        assert action.messages["npc:guard"] == ["alert!"]


# --- Convenience propagate(deliver=...) -----------------------------------


@pytest.mark.asyncio
class TestPropagateDelivers:

    async def test_propagate_delivers_by_default(self):
        captured: list[str] = []
        actor = make_object("Alice")
        actor.set_msg_handler(captured.append)
        actor.add_behavior(MessageBehavior("actor", "you act"))

        action = Action(actor=actor, target=None, action_type="x")
        await propagate(action)

        assert captured == ["you act"]

    async def test_propagate_skips_delivery_when_opted_out(self):
        captured: list[str] = []
        actor = make_object("Alice")
        actor.set_msg_handler(captured.append)
        actor.add_behavior(MessageBehavior("actor", "you act"))

        action = Action(actor=actor, target=None, action_type="x")
        await propagate(action, deliver=False)

        # Message was accumulated but not delivered.
        assert captured == []
        assert action.messages["actor"] == ["you act"]


# --- Session integration -------------------------------------------------


@pytest.mark.asyncio
class TestSessionMsgWiring:

    async def test_link_player_wires_msg_handler(self):
        session = Session(protocol="test", address="127.0.0.1")
        player = make_object("Alice", )
        player.add_tag("player")

        session.link_player(player)

        # Calling player.msg should now enqueue on the session's output queue.
        player.msg("hello")
        assert session._output_queue.get_nowait() == "hello"

    async def test_unlink_player_clears_msg_handler(self):
        session = Session(protocol="test", address="127.0.0.1")
        player = make_object("Alice")
        session.link_player(player)
        session.unlink_player()

        # After unlink, player.msg drops messages.
        player.msg("dropped")
        assert session._output_queue.empty()

    async def test_end_to_end_action_to_session_queue(self):
        """Action propagated → behavior adds messages → session queue receives them."""
        session = Session(protocol="test", address="127.0.0.1")
        room = make_room()
        actor = make_object("Alice", location=room)
        target = make_object("Bob", location=room)
        bystander = make_object("Charlie", location=room)
        bystander_session = Session(protocol="test", address="127.0.0.1")

        session.link_player(actor)
        bystander_session.link_player(bystander)

        actor.add_behavior(MessageBehavior("actor", "you wave at {target}"))
        actor.add_behavior(MessageBehavior("room", "{actor} waves at {target}"))

        action = Action(actor=actor, target=target, action_type="event:wave")
        await propagate(action)

        # Actor saw their own message.
        assert session._output_queue.get_nowait() == "you wave at Bob"
        # Bystander saw the room message; target did not (no target message added).
        assert bystander_session._output_queue.get_nowait() == "Alice waves at Bob"
