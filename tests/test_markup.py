"""
Color markup: the two regressions that matter (split-safety, minimal
SGR), plus strip/pad/escape, protocol edges, and the softcode surface.
"""

from __future__ import annotations

import pytest

from realm.core.markup import (
    escape,
    pad,
    parse,
    strip,
    to_ansi,
    truncate,
    visible_len,
)


class TestParsing:

    def test_basic_styles_and_reset(self):
        segs = parse("|rred|n plain")
        assert [(s.fg, t) for s, t in segs] == [('r', 'red'), (None, ' plain')]

    def test_literal_pipe_and_unknown_code(self):
        assert strip("a||b") == "a|b"
        assert strip("|qoops") == "|qoops"   # typos stay visible

    def test_dangling_pipe_is_literal(self):
        assert strip("end|") == "end|"

    def test_split_anywhere_is_safe(self):
        """The Evennia regression: splitting marked-up text never breaks
        rendering — every half parses and terminates."""
        text = "|rhe|[bllo |Gwor|nld|h!"
        for i in range(len(text) + 1):
            a, b = text[:i], text[i:]
            assert isinstance(to_ansi(a), str)
            assert isinstance(to_ansi(b), str)
            # visible text survives (markers may split into literals,
            # but nothing raises and nothing is silently eaten twice)
            assert visible_len(a) + visible_len(b) >= visible_len(text) - 1

    def test_background_and_flags(self):
        (style, _), = parse("|[r|h|ux")
        assert style.bg == 'r' and style.bold and style.underline


class TestAnsiEncoding:

    def test_minimal_transitions(self):
        # Adjacent same-style: ONE escape, not per-fragment.
        out = to_ansi("|rab|rcd|ref|n!")
        assert out.count("\x1b[") == 2          # set red once, reset once
        assert out == "\x1b[0;31mabcdef\x1b[0m!"

    def test_no_markup_no_cost(self):
        assert to_ansi("plain text") == "plain text"

    def test_trailing_reset_prevents_bleed(self):
        assert to_ansi("|rdanger").endswith("\x1b[0m")

    def test_bright_and_background_params(self):
        assert "\x1b[0;91m" in to_ansi("|Rx")       # bright fg = 9x
        assert "\x1b[0;44m" in to_ansi("|[bx")      # bg = 4x
        assert "\x1b[0;1;31m" in to_ansi("|h|rx")   # bold+red combined


class TestWidthHelpers:

    def test_visible_len_and_pad(self):
        assert visible_len("|r|h|[bhi|n") == 2
        assert pad("|rok|n", 5) == "|rok|n   "
        assert pad("|rok|n", 5, align="right") == "   |rok|n"

    def test_truncate_resets(self):
        cut = truncate("|rabcdef", 3)
        assert strip(cut) == "abc"
        assert cut.endswith("|n")

    def test_escape(self):
        assert strip(escape("price|table")) == "price|table"


@pytest.mark.asyncio
class TestProtocolEdges:

    def _telnet(self):
        from realm.gateway.telnet import TelnetProtocol
        from realm.gateway.session import Session

        class FakeTransport:
            def __init__(self):
                self.data = b""
            def is_closing(self):
                return False
            def write(self, b):
                self.data += b

        proto = TelnetProtocol.__new__(TelnetProtocol)
        proto.transport = FakeTransport()
        proto.session = Session(protocol="telnet", address="1.1.1.1")
        return proto

    async def test_telnet_renders_ansi(self):
        proto = self._telnet()
        await proto._write_to_client("|rhot|n stuff")
        assert b"\x1b[0;31mhot\x1b[0m" in proto.transport.data

    async def test_color_off_strips(self):
        from realm.core.objects import GameObject
        proto = self._telnet()
        player = GameObject("Bob", tags=["player"])
        player.db.color = False
        proto.session.link_player(player)
        await proto._write_to_client("|rhot|n stuff")
        assert b"\x1b[" not in proto.transport.data
        assert b"hot stuff" in proto.transport.data

    async def test_softcode_ansi_function(self):
        from realm.scripting.functions import ScriptFunctions
        f = ScriptFunctions()
        assert f.ansi('rh', 'My thing') == "|RMy thing|n"
        assert f.ansi('gU'.replace('U','R'), 'x') == "|g|[rx|n"  # bg mapping
        assert strip(f.escape("a|b")) == "a|b"

    async def test_room_render_carries_markup(self):
        from realm.core.objects import GameObject
        from realm.core.render import render_room

        room = GameObject("Keep", tags=["room"])
        GameObject("gate", tags=["exit"], location=room)
        viewer = GameObject("Bob", tags=["player"], location=room)
        out = render_room(room, viewer)
        assert "|cKeep|n" in out and "|ggate|n" in out
        assert "\x1b[" not in out   # rendering happens at the edge, not here
