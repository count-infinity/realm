"""
The ``talk`` feature's verb cores: say, pose, semipose, emit, whisper.

The ``*_action`` builders give each the canonical shape (used by the
commands, scripted speech and the script verbs); ``do_*`` propagate it.
A rich emote's ``<sigil>name`` references resolve per viewer.
"""

from __future__ import annotations

import re
from functools import cache
from typing import TYPE_CHECKING

from realm.core.propagation import Action, propagate
from realm.core.world import setting
from realm.std.talk.actions import TalkAction

if TYPE_CHECKING:
    from realm.core.objects import GameObject

# --- Emote references -------------------------------------------------------
# A rich emote references people/things with a sigil — `pose waves at /Bob` —
# and each reference is rendered per viewer, so everyone reads the name THEY
# know (a disguise, an unintroduced stranger) and the referenced person reads
# "you". The sigil is a game setting (EMOTE_SIGIL), '/' by default.

# A private, unspellable delimiter for a resolved reference in the pose body:
# U+FDD0 is a Unicode noncharacter — never valid in text, so a player cannot
# type it and it cannot collide with a name. format_message swaps
# ``﷐<i>﷐`` for the i-th referenced object, named for the looker.
_EMOTE_REF = "﷐{}﷐"


@cache
def _emote_ref_re(sigil: str) -> re.Pattern[str]:
    return re.compile(re.escape(sigil) + r"(\w+)")


def parse_emote_refs(poser: GameObject, text: str) -> tuple[str, list]:
    """Resolve ``<sigil>word`` references in an emote to room objects.

    Returns ``(body, refs)`` where ``body`` has each resolved reference
    replaced by a private marker and ``refs`` is the objects in marker
    order. A reference that matches nothing is left exactly as typed
    (so ``and/or`` or a stray slash survives untouched) — resolution is
    from the *poser's* view; rendering is per viewer, later.
    """
    from realm.core.search import match_objects

    candidates: list = []
    room = poser.location
    if room is not None:
        candidates.extend(room.contents)
    candidates.extend(poser.contents)
    candidates.append(poser)

    refs: list = []

    def _sub(m: re.Match) -> str:
        matches = match_objects(m.group(1), candidates).matches
        if not matches:
            return m.group(0)            # not a reference — leave literal
        refs.append(matches[0])
        return _EMOTE_REF.format(len(refs) - 1)

    return _emote_ref_re(setting("EMOTE_SIGIL")).sub(_sub, text), refs

if TYPE_CHECKING:
    from realm.core.objects import GameObject


def speech_action(speaker: GameObject, message: str) -> Action:
    """The canonical say shape — used by cmd_say, scripted says, and
    NPC _npc_say so narration can never drift apart."""
    from realm.core.propagation import ROOM_TARGET_CHAIN
    action = Action(
        actor=speaker,
        target=speaker.location,
        action_type=TalkAction.SPEECH,
        chain=ROOM_TARGET_CHAIN,
        extra={"message": message},
    )
    action.add_message("actor", 'You say, "{speech}"', success_only=True)
    action.add_message("room", '{actor} says, "{speech}"', success_only=True)
    return action


def pose_action(poser: GameObject, pose_text: str) -> Action:
    """The canonical pose shape.

    Rich by default: ``/name`` references in the text resolve to room
    objects and render per viewer (each reader sees the name they know;
    the referenced person reads "you"). Plain poses with no references are
    unchanged — an unmatched ``/word`` is left literal.
    """
    from realm.core.propagation import ROOM_TARGET_CHAIN
    body, refs = parse_emote_refs(poser, pose_text)
    action = Action(
        actor=poser,
        target=poser.location,
        action_type=TalkAction.EMOTE,
        chain=ROOM_TARGET_CHAIN,
        extra={"pose": body},
    )
    # `emote_refs` is an internal render aid (the resolved reference
    # objects), not a builder-facing `adata` payload — attached after
    # construction so the documented `pose` key stays the visible one.
    if refs:
        action.extra["emote_refs"] = refs
    action.add_message("actor", "{actor} {speech}", success_only=True)
    action.add_message("room", "{actor} {speech}", success_only=True)
    return action


def emit_action(actor: GameObject, message: str) -> Action:
    """The canonical @emit shape — raw text to the actor's room, shown
    identically to everyone including the emitter."""
    from realm.core.propagation import ROOM_TARGET_CHAIN
    action = Action(
        actor=actor,
        target=actor.location,
        action_type=TalkAction.EMIT,
        chain=ROOM_TARGET_CHAIN,
        extra={"message": message},
    )
    action.add_message("actor", "{speech}", success_only=True)
    action.add_message("room", "{speech}", success_only=True)
    return action


def whisper_action(
    speaker: GameObject, target: GameObject, message: str
) -> Action:
    """The canonical whisper shape — used by cmd_whisper and scripted
    whispers so the target/room/actor lines can never drift apart."""
    action = Action(
        actor=speaker,
        target=target,
        action_type=TalkAction.WHISPER,
        extra={"message": message},
    )
    action.add_message(
        "actor", 'You whisper to {target}, "{speech}"', success_only=True)
    action.add_message(
        "target", '{actor} whispers, "{speech}"', success_only=True)
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


def semipose_action(poser: GameObject, pose_text: str) -> Action:
    """The canonical semipose shape: the pose abuts the name with no space
    ("Alice's dog barks."). ``{actor}`` renders the bare name per viewer
    (disguise, sdesc, voice_as); the text stays a ``{speech}`` token."""
    from realm.core.propagation import ROOM_TARGET_CHAIN
    action = Action(
        actor=poser,
        target=poser.location,
        action_type=TalkAction.SEMIPOSE,
        chain=ROOM_TARGET_CHAIN,
        extra={"pose": pose_text},
    )
    action.add_message("actor", "{actor}{speech}", success_only=True)
    action.add_message("room", "{actor}{speech}", success_only=True)
    return action


async def do_semipose(
    actor: GameObject, pose_text: str, *, scripted: bool = False
) -> Action | None:
    """Semipose — the one semipose pathway. Returns the action or None."""
    if actor.location is None:
        return None
    return await _speak(semipose_action(actor, pose_text), scripted)


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


async def npc_say(npc: GameObject, message: str) -> None:
    """An NPC speaks through the propagation engine (real speech, tagged
    ``npc``)."""
    if npc.location is None:
        return
    action = speech_action(npc, message)
    action.tags.add("npc")
    await propagate(action)


__all__ = [
    "parse_emote_refs",
    "npc_say",
    "speech_action",
    "pose_action",
    "semipose_action",
    "emit_action",
    "whisper_action",
    "do_say",
    "do_pose",
    "do_semipose",
    "do_emit",
    "do_whisper",
]
