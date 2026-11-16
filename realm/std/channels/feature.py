"""
The ``channels`` feature.

Talking beyond the room: tells, reply, ignore, afk, and channels defined as
data (``channel_def``) (MUD_PLAN 7.1, 7.2; docs/guides/communication.md).
"""

from __future__ import annotations

from realm.features import Feature
from realm.std.channels import softcode
from realm.std.channels.channels import broadcast, channel_fallback, cmd_channel, cmd_channels
from realm.std.channels.tells import (
    afk_field,
    cmd_afk,
    cmd_ignore,
    cmd_reply,
    cmd_tell,
    cmd_unignore,
)

feature = Feature(
    'channels',
    doc='Tells, ignore, afk, and channels defined as data.',
)

feature.def_kind("channel", "channel_def")

feature.command('tell', cmd_tell, aliases=['t'], category='communication',
                help_text='Tell a player something, anywhere', usage='tell <player> <message>')
feature.command('reply', cmd_reply, aliases=['r'], category='communication',
                help_text='Answer the last tell', usage='reply <message>')
feature.command('ignore', cmd_ignore, category='communication',
                help_text="Stop hearing a player's tells", usage='ignore [player]')
feature.command('unignore', cmd_unignore, category='communication',
                help_text="Hear a player's tells again", usage='unignore <player>')
feature.command('afk', cmd_afk, category='communication',
                help_text='Mark yourself away', usage='afk [message]')
feature.command('channels', cmd_channels, category='communication',
                help_text='List the channels')
feature.command('channel', cmd_channel, category='communication',
                help_text='Turn a channel on or off, or read its history',
                usage='channel <name> on|off|history')
# A channel's name is a command: `gossip hello`.
feature.fallback(channel_fallback)

feature.event("comm:on_tell", hook="TELL", doc="this player is told something",
              payload={"message": "what was said"})
feature.event("comm:on_channel", hook="CHANNEL",
              doc="a line is spoken on this channel (the channel_def is the target)",
              payload={"channel": "the channel's name", "message": "what was said"})

feature.softfn(softcode.cemit, group='Messaging & prompts', harm=True)
feature.softfn(softcode.channel_members, group='Messaging & prompts', readonly=True)


@feature.on_install
def _afk_on_who(world) -> None:
    """``who`` shows ``afk`` beside a player who is away (with ``basics``)."""
    who = world.services.get("who")
    if who is not None:
        who.fields.append(afk_field)


async def _cemit(engine, frame, channel, text) -> None:
    """Queued by softcode cemit()."""
    await broadcast(channel, str(text), speaker=None, message=str(text))


feature.queue_kind("cemit", _cemit)
