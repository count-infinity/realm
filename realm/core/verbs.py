"""
Manipulation verb cores: get / drop / give / open / close.

One implementation per verb — the player commands and the script
engine's actuators both call these, so a scripted imp picking up a
coin passes the same locks, behavior gates, and message pathway as a
player typing ``get coin``. Failures message the actor (a session-less
NPC just drops the line) and return False.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.language import singular_name
from realm.core.propagation import Action, deliver_messages, gate_action

if TYPE_CHECKING:
    from realm.core.objects import GameObject


async def gate_item_action(
    actor: GameObject,
    action_type: str,
    target: GameObject,
    *,
    tool: GameObject | None = None,
    extra: dict | None = None,
    fail_msg: str,
) -> Action | None:
    """
    Run an item action's permission pass through propagation.

    Locks (via the check-pass lock guard) and behaviors both get a chance
    to block. Returns the action on success, None on a block (the actor
    has been messaged). Every item transfer — single or bulk, typed or
    scripted — goes through this one gate.
    """
    action = Action(
        actor=actor,
        target=target,
        action_type=action_type,
        tool=tool,
        extra=extra or {},
    )
    if not await gate_action(action, fail_msg=fail_msg):
        return None
    return action


async def do_get(actor: GameObject, target: GameObject) -> bool:
    """Pick up ``target`` into ``actor``'s inventory."""
    if target.has_tag('player'):
        actor.msg("You can't pick up players!")
        return False

    action = await gate_item_action(
        actor, "item:on_get", target,
        fail_msg=f"You can't pick up {target.name}.",
    )
    if action is None:
        return False

    target.location = actor

    action.add_message("actor", "You pick up {target:a}.")
    action.add_message("room", "{actor} picks up {target:a}.")
    deliver_messages(action)
    return True


async def do_drop(actor: GameObject, target: GameObject) -> bool:
    """Drop ``target`` from ``actor``'s inventory into its location."""
    if actor.location is None:
        actor.msg("You can't drop things here.")
        return False

    action = await gate_item_action(
        actor, "item:on_drop", target,
        fail_msg=f"You can't drop {target.name}.",
    )
    if action is None:
        return False

    target.location = actor.location

    action.add_message("actor", "You drop {target:a}.")
    action.add_message("room", "{actor} drops {target:a}.")
    deliver_messages(action)
    return True


async def do_give(actor: GameObject, item: GameObject, target: GameObject) -> bool:
    """Hand ``item`` from ``actor`` to ``target``."""
    if target is actor:
        actor.msg("Give it to yourself? That doesn't make sense.")
        return False

    # For 'give', the target is the recipient and the item travels via
    # 'tool' so {tool} substitution works and the actor-side give-lock
    # check can find it.
    action = await gate_item_action(
        actor, "item:on_give", target,
        tool=item,
        extra={"item": item},
        fail_msg=f"You can't give {item.name} to {target.name}.",
    )
    if action is None:
        return False

    item.location = target

    action.add_message("actor", "You give {tool:a} to {target}.")
    action.add_message("target", "{actor} gives you {tool:a}.")
    action.add_message("room", "{actor} gives {tool:a} to {target}.")
    deliver_messages(action)
    return True


async def do_open(actor: GameObject, target: GameObject) -> bool:
    """Open a door or container (must be closed and not locked)."""
    if not target.has_tag('closed'):
        actor.msg(f"{singular_name(target).capitalize()} is already open.")
        return False
    if target.db.get('locked'):
        actor.msg(
            target.db.get('locked_msg')
            or f"{singular_name(target).capitalize()} is locked."
        )
        return False

    action = await gate_item_action(
        actor, "item:on_open", target,
        fail_msg=f"You can't open {target.name}.",
    )
    if action is None:
        return False

    target.remove_tag('closed')
    action.add_message("actor", "You open {target:the}.")
    action.add_message("room", "{actor} opens {target:the}.")
    deliver_messages(action)
    return True


async def do_close(actor: GameObject, target: GameObject) -> bool:
    """Close a door or container."""
    if target.has_tag('closed'):
        actor.msg(f"{singular_name(target).capitalize()} is already closed.")
        return False
    is_door_or_container = target.has_tag('exit') or target.db.get('container')
    if not is_door_or_container and not target.db.get('closable'):
        actor.msg(f"You can't close {target.name}.")
        return False

    action = await gate_item_action(
        actor, "item:on_close", target,
        fail_msg=f"You can't close {target.name}.",
    )
    if action is None:
        return False

    target.add_tag('closed')
    action.add_message("actor", "You close {target:the}.")
    action.add_message("room", "{actor} closes {target:the}.")
    deliver_messages(action)
    return True


def speech_action(speaker: GameObject, message: str) -> Action:
    """The canonical say shape — used by cmd_say, scripted says, and
    NPC _npc_say so narration can never drift apart."""
    from realm.core.propagation import ROOM_TARGET_CHAIN
    action = Action(
        actor=speaker,
        target=speaker.location,
        action_type="event:speech",
        chain=ROOM_TARGET_CHAIN,
        extra={"message": message},
    )
    action.add_message("actor", f'You say, "{message}"', success_only=True)
    action.add_message("room", f'{{actor}} says, "{message}"', success_only=True)
    return action


def pose_action(poser: GameObject, pose_text: str) -> Action:
    """The canonical pose shape."""
    from realm.core.propagation import ROOM_TARGET_CHAIN
    action = Action(
        actor=poser,
        target=poser.location,
        action_type="event:emote",
        chain=ROOM_TARGET_CHAIN,
        extra={"pose": pose_text},
    )
    action.add_message("actor", f"{{actor}} {pose_text}", success_only=True)
    action.add_message("room", f"{{actor}} {pose_text}", success_only=True)
    return action


def emit_action(actor: GameObject, message: str) -> Action:
    """The canonical @emit shape — raw text to the actor's room, shown
    identically to everyone including the emitter."""
    from realm.core.propagation import ROOM_TARGET_CHAIN
    action = Action(
        actor=actor,
        target=actor.location,
        action_type="event:emit",
        chain=ROOM_TARGET_CHAIN,
        extra={"message": message},
    )
    action.add_message("actor", message, success_only=True)
    action.add_message("room", message, success_only=True)
    return action


def whisper_action(
    speaker: GameObject, target: GameObject, message: str
) -> Action:
    """The canonical whisper shape — used by cmd_whisper and scripted
    whispers so the target/room/actor lines can never drift apart."""
    action = Action(
        actor=speaker,
        target=target,
        action_type="event:whisper",
        extra={"message": message},
    )
    action.add_message(
        "actor", f'You whisper to {{target}}, "{message}"', success_only=True)
    action.add_message(
        "target", f'{{actor}} whispers, "{message}"', success_only=True)
    action.add_message(
        "room", "{actor} whispers something to {target}.", success_only=True)
    return action


async def do_say(
    actor: GameObject, message: str, *, scripted: bool = False
) -> Action | None:
    """Speak aloud. Guard, build, propagate — the one say pathway for a
    player command, a scripted say, and an NPC. Returns the propagated
    action (check ``.blocked``), or None if the actor has nowhere to
    speak from."""
    if actor.location is None:
        return None
    return await _speak(speech_action(actor, message), scripted)


async def do_pose(
    actor: GameObject, pose_text: str, *, scripted: bool = False
) -> Action | None:
    """Emote/pose — the one pose pathway. Returns the action or None."""
    if actor.location is None:
        return None
    return await _speak(pose_action(actor, pose_text), scripted)


async def do_emit(
    actor: GameObject, message: str, *, scripted: bool = False
) -> Action | None:
    """Emit raw room text — the one @emit pathway. Returns the action
    or None."""
    if actor.location is None:
        return None
    return await _speak(emit_action(actor, message), scripted)


async def do_whisper(
    actor: GameObject, target: GameObject, message: str, *,
    scripted: bool = False,
) -> Action | None:
    """Whisper to an already-resolved ``target`` — the one whisper
    pathway. Callers do their own (perception-aware) target lookup and
    pass the object here. Returns the action or None."""
    if actor.location is None or target is None or target is actor:
        return None
    return await _speak(whisper_action(actor, target, message), scripted)


async def _speak(action: Action, scripted: bool) -> Action:
    """Tag (if scripted) and propagate a speech-family action."""
    from realm.core.propagation import propagate
    if scripted:
        action.tags.add("scripted")
    await propagate(action)
    return action


__all__ = [
    "speech_action",
    "pose_action",
    "emit_action",
    "whisper_action",
    "do_say",
    "do_pose",
    "do_emit",
    "do_whisper",
    "gate_item_action",
    "do_get",
    "do_drop",
    "do_give",
    "do_open",
    "do_close",
]
