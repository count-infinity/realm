"""
The ``talk`` feature.

Speech: say, pose, emit, shout, whisper.
"""

from __future__ import annotations

from realm.commands.builtin.communication import (
    cmd_emit,
    cmd_ooc,
    cmd_pose,
    cmd_say,
    cmd_semipose,
    cmd_shout,
    cmd_whisper,
)
from realm.features import Feature
from realm.std.talk.actions import TalkAction

feature = Feature(
    'talk',
    doc='Speech: say, pose, emit, shout, whisper.',
)

feature.command(
    'say',
    cmd_say,
    token=['"', "'"],
    category='communication',
    help_text='Say something to the room',
    usage='say <message> or "<message>',
)
feature.command(
    'pose',
    cmd_pose,
    aliases=['emote'],
    token=':',
    category='communication',
    help_text='Emote an action',
    usage='pose <action> or :<action>',
)
feature.command(
    'semipose',
    cmd_semipose,
    token=';',
    category='communication',
    help_text='Emote with name attached',
    usage='semipose <action> or ;<action>',
)
feature.command(
    'emit',
    cmd_emit,
    token='\\',
    permission='builder',
    category='communication',
    help_text='Emit a message to the room',
    usage='emit <message> or \\<message>',
)
feature.command(
    'ooc',
    cmd_ooc,
    category='communication',
    help_text='Out-of-character speech',
    usage='ooc <message>',
)
feature.command(
    'shout',
    cmd_shout,
    category='communication',
    help_text='Shout to the room (and nearby)',
    usage='shout <message>',
)
feature.command(
    'whisper',
    cmd_whisper,
    category='communication',
    help_text='Whisper privately to someone',
    usage='whisper <player> = <message>',
    parse_equals=True,
)


# --- script verbs: the same speech cores the commands use --------------------

@feature.script_verb("say", sugar=True, doc="say <text>: speak as the scripted object")
async def _say(engine, executor, rest):
    from realm.std.talk.verbs import do_say
    await do_say(executor, rest, scripted=True)


@feature.script_verb("pose", token=":", sugar=True, doc="pose <text> or :<text>: emote")
async def _pose(engine, executor, rest):
    from realm.std.talk.verbs import do_pose
    await do_pose(executor, rest, scripted=True)


@feature.script_verb("semipose", token=";", doc=";<text>: emote with no space after the name")
async def _semipose(engine, executor, rest):
    from realm.std.talk.verbs import do_semipose
    await do_semipose(executor, rest, scripted=True)


@feature.script_verb("emit", aliases=["@emit"], token="\\",
                     doc="emit <text> or \\<text>: room text with no name")
async def _emit(engine, executor, rest):
    from realm.std.talk.verbs import do_emit
    await do_emit(executor, rest, scripted=True)


@feature.script_verb("whisper", doc="whisper <who> = <text>: to one person in the room")
async def _whisper(engine, executor, rest):
    """The target is resolved perception-aware against the speaker's room,
    like every other name lookup. An ambiguous name is a no-op."""
    from realm.core.perception import can_see
    from realm.core.search import AmbiguousMatchError, match_one
    from realm.std.talk.verbs import do_whisper
    parts = rest.split('=', 1)
    if len(parts) != 2 or executor.location is None:
        return
    try:
        target = match_one(parts[0].strip(), [
            o for o in executor.location.contents
            if o is not executor and can_see(executor, o)])
    except AmbiguousMatchError:
        return
    if target is not None:
        await do_whisper(executor, target, parts[1].strip(), scripted=True)


# --- events: speech is gated by the room's speech lock ----------------------


_SAID = {"message": "what was said"}
feature.event(TalkAction.SPEECH, doc="say", payload=_SAID, speech=True,
              listen=True, target_lock=("speech", "You can't speak here."))
feature.event(TalkAction.SHOUT, doc="shout", payload=_SAID, speech=True,
              listen=True, target_lock=("speech", "You can't speak here."))
feature.event(TalkAction.OOC, doc="out-of-character speech", payload=_SAID, speech=True,
              listen=True, target_lock=("speech", "You can't speak here."))
feature.event(TalkAction.WHISPER, doc="whisper", payload=_SAID, speech=True)
feature.event(TalkAction.EMOTE, doc="pose", payload={"pose": "the pose text"},
              speech=True, target_lock=("speech", "You can't emote here."))
feature.event(TalkAction.SEMIPOSE, doc="semipose", payload={"pose": "the pose text"},
              speech=True, target_lock=("speech", "You can't emote here."))
feature.event(TalkAction.EMIT, doc="emit", payload={"message": "the emitted text"},
              listen=True, target_lock=("speech", "You can't emit here."))
