"""The action types of speech and poses (the ``talk`` feature).

A :class:`~enum.StrEnum` like the kernel's ``ActionType``: each member is its
string value, so saved worlds and softcode see the same strings.
"""

from __future__ import annotations

from enum import StrEnum


class TalkAction(StrEnum):
    SPEECH = "event:speech"
    SHOUT = "event:shout"
    OOC = "event:ooc"
    WHISPER = "event:whisper"
    EMOTE = "event:emote"
    SEMIPOSE = "event:semipose"
    EMIT = "event:emit"
    SOCIAL = "event:social"


__all__ = ["TalkAction"]
