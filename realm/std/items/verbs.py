"""
The ``items`` feature's verb cores: get / drop / give / open / close.

One implementation per verb — the player commands and the script
engine's actuators both call these, so a scripted imp picking up a
coin passes the same locks, behavior gates, and message pathway as a
player typing ``get coin``. Failures message the actor (a session-less
NPC just drops the line) and return False.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from realm.core.action_types import ActionType
from realm.core.language import definite_name, singular_name
from realm.core.pairing import far_side
from realm.core.propagation import Action, deliver_messages, gate_action
from realm.std.items.actions import ItemAction
from realm.std.items.equipment import take_it_off_first

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
    apply=None,
) -> Action | None:
    """
    Run an item action through propagation, with its engine effect as
    ``apply`` (executed between the permission and reaction passes — the
    before/apply/after trio, so reaction hooks see POST-state).

    Locks (via the check-pass lock guard) and behaviors both get a chance
    to block; a block means the effect never ran. Returns the action on
    success, None on a block (the actor has been messaged). Every item
    transfer — single or bulk, typed or scripted — goes through this one
    gate.
    """
    action = Action(
        actor=actor,
        target=target,
        action_type=action_type,
        tool=tool,
        extra=extra or {},
    )
    if not await gate_action(action, fail_msg=fail_msg, apply=apply):
        return None
    return action


async def do_get(actor: GameObject, target: GameObject) -> bool:
    """Pick up ``target`` into ``actor``'s inventory."""
    if target.is_player:
        actor.msg("You can't pick up players!")
        return False

    def _apply(_a):
        target.location = actor

    action = await gate_item_action(
        actor, ItemAction.ON_GET, target,
        fail_msg=f"You can't pick up {target.name}.",
        apply=_apply,
    )
    if action is None:
        return False

    action.add_message("actor", "You pick up {target:a}.")
    action.add_message("room", "{actor} picks up {target:a}.")
    deliver_messages(action)
    return True


async def do_drop(actor: GameObject, target: GameObject) -> bool:
    """Drop ``target`` from ``actor``'s inventory into its location."""
    if actor.location is None:
        actor.msg("You can't drop things here.")
        return False
    refusal = take_it_off_first(target) if target.location is actor else None
    if refusal:
        actor.msg(refusal)
        return False

    def _apply(_a):
        target.location = actor.location

    action = await gate_item_action(
        actor, ItemAction.ON_DROP, target,
        fail_msg=f"You can't drop {target.name}.",
        apply=_apply,
    )
    if action is None:
        return False

    action.add_message("actor", "You drop {target:a}.")
    action.add_message("room", "{actor} drops {target:a}.")
    deliver_messages(action)
    return True


async def do_give(actor: GameObject, item: GameObject, target: GameObject) -> bool:
    """Hand ``item`` from ``actor`` to ``target``."""
    if target is actor:
        actor.msg("Give it to yourself? That doesn't make sense.")
        return False
    refusal = take_it_off_first(item) if item.location is actor else None
    if refusal:
        actor.msg(refusal)
        return False

    # For 'give', the target is the recipient and the item travels via
    # 'tool' so {tool} substitution works and the actor-side give-lock
    # check can find it.
    def _apply(_a):
        item.location = target

    action = await gate_item_action(
        actor, ItemAction.ON_GIVE, target,
        tool=item,
        extra={"item": item},
        fail_msg=f"You can't give {item.name} to {target.name}.",
        apply=_apply,
    )
    if action is None:
        return False

    action.add_message("actor", "You give {tool:a} to {target}.")
    action.add_message("target", "{actor} gives you {tool:a}.")
    action.add_message("room", "{actor} gives {tool:a} to {target}.")
    deliver_messages(action)

    # ON_RECEIVE — the recipient's own hook (distinct from the giver-side
    # give): a shopkeeper reacting to an item pressed into its hands.
    from realm.core.events import fire_event
    await fire_event(actor, target, ActionType.ON_RECEIVE,
                     extra={"item": item, "giver": actor})
    return True


def door_word(target: GameObject) -> str | None:
    """How an open/close/lock line names an exit whose door has ROM
    keywords: "the gate" (its first keyword, as ROM's ``$d``), never "the
    west". None for anything else."""
    keywords = target.db.get('keywords') if target.is_exit else None
    if not keywords:
        return None
    first = keywords.split()[0] if isinstance(keywords, str) else str(keywords[0])
    return f"the {first}"


def door_state(target: GameObject, tag: str, on: bool) -> GameObject | None:
    """Put ``tag`` (``closed``, ``locked``) on ``target`` or take it off. A
    door has two faces that agree: an exit's far side
    (``realm.core.pairing.far_side``: its partner, else the exit beyond
    leading back) changes too, as ROM's ``do_open``/``do_close``/
    ``do_lock``/``do_unlock`` change ``pexit_rev``. Returns that far side,
    or None. Every ``open``, ``close``, ``lock``, ``unlock``, keycard swipe
    and picked lock goes through here."""
    (target.add_tag if on else target.remove_tag)(tag)
    far = far_side(target) if target.is_exit else None
    if far is not None:
        (far.add_tag if on else far.remove_tag)(tag)
    return far


def _tell_far_side(far: GameObject | None, verb: str) -> None:
    """The room beyond hears its face of the door move: "The gate opens."
    (ROM's "The $d opens.": "the door" when the exit has no keywords and is
    named for a direction)."""
    if far is None or far.location is None:
        return
    from realm.core.ops.exits import OPPOSITES
    door = door_word(far) or ("the door" if far.name.lower() in OPPOSITES
                              else definite_name(far))
    far.location.msg_contents(f"{door[:1].upper()}{door[1:]} {verb}.")


async def do_open(actor: GameObject, target: GameObject) -> bool:
    """Open a door or container (must be closed and not locked)."""
    if not target.has_tag('closed'):
        actor.msg(f"{(door_word(target) or singular_name(target)).capitalize()} "
                  f"is already open.")
        return False
    if target.has_tag('locked'):
        actor.msg(
            target.db.get('locked_msg')
            or f"{(door_word(target) or singular_name(target)).capitalize()} is locked."
        )
        return False

    far = None

    def _open(_a):
        nonlocal far
        far = door_state(target, 'closed', False)

    action = await gate_item_action(
        actor, ItemAction.ON_OPEN, target,
        fail_msg=f"You can't open {target.name}.",
        apply=_open,
    )
    if action is None:
        return False

    door = door_word(target) or "{target:the}"
    action.add_message("actor", f"You open {door}.")
    action.add_message("room", f"{{actor}} opens {door}.")
    deliver_messages(action)
    _tell_far_side(far, "opens")
    return True


async def do_close(actor: GameObject, target: GameObject) -> bool:
    """Close a door or container."""
    if target.has_tag('closed'):
        actor.msg(f"{(door_word(target) or singular_name(target)).capitalize()} "
                  f"is already closed.")
        return False
    is_door_or_container = target.is_exit or target.has_tag('container')
    if not is_door_or_container and not target.has_tag('closable'):
        actor.msg(f"You can't close {target.name}.")
        return False

    far = None

    def _close(_a):
        nonlocal far
        far = door_state(target, 'closed', True)

    action = await gate_item_action(
        actor, ItemAction.ON_CLOSE, target,
        fail_msg=f"You can't close {target.name}.",
        apply=_close,
    )
    if action is None:
        return False

    door = door_word(target) or "{target:the}"
    action.add_message("actor", f"You close {door}.")
    action.add_message("room", f"{{actor}} closes {door}.")
    deliver_messages(action)
    _tell_far_side(far, "closes")
    return True


__all__ = ["gate_item_action", "door_word", "door_state", "do_get", "do_drop", "do_give",
           "do_open", "do_close"]
