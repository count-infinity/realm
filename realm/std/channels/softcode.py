"""
Softcode functions: channels. The ``channels`` feature declares each; the
first parameter is the run's frame.
"""

from __future__ import annotations

from realm.std.channels.channels import find_channel, members


def cemit(frame, channel: str, text: str) -> bool:
    """
    Announce a line on a channel, as is (no speaker name): a herald, a
    server notice. False for no such channel. Queued.

    Example: cemit('gossip', 'The fair opens at dawn.')
    """
    target = find_channel(str(channel))
    if target is None:
        return False
    frame.command_queue.append(('cemit', target, str(text)))
    return True


def channel_members(frame, channel: str) -> list[str]:
    """
    The names of the online players who hear a channel now.

    Example: channel_members('gossip')
    """
    target = find_channel(str(channel))
    return [p.name for p in members(target)] if target is not None else []


__all__ = ["cemit", "channel_members"]
