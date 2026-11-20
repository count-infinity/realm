"""
How a narrated line is presented: ROM's capital first letter.

ROM's ``act()`` capitalizes the first letter of every line it sends, so a
message template that starts with a name ("{actor} arrives." naming "the
cityguard") reads "The cityguard arrives."; ``send_to_char`` is sent as
written. That is Diku presentation, not every game's: a MUSH builder's
deliberately lowercase ``remit`` must stay lowercase. So it is a setting,
``CAPITALIZE_LINES`` (off; the Merc scaffold and Midgaard turn it on), and
the rule is a ``feature.line_formatter``: the kernel passes every
``deliver_messages`` line and room broadcast through the world's
formatters, and a feature passes the sentences it composes for one player
through ``realm.core.world.format_line``.
"""

from __future__ import annotations

from realm.core.markup import capitalize
from realm.core.world import get_world


def capitalize_lines(text: str) -> str:
    """``text`` with its first visible letter capitalized when the game's
    ``CAPITALIZE_LINES`` is on (``realm.core.markup.capitalize``: colour
    codes stepped over, the first character only, never each line); else
    as written."""
    return capitalize(text) if get_world().setting("CAPITALIZE_LINES") else text


__all__ = ["capitalize_lines"]
