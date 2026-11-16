"""
MUD_PLAN step 16: the browser client.

One static page (``realm/web/index.html``: HTML, CSS and plain JavaScript)
is served at ``/`` by the WebSocket server when ``ENABLE_WEBSOCKET`` and
``WEB_CLIENT`` are both set. It talks the existing WebSocket protocol:
text frames (plain, or ``segments`` the page styles), a ``prompt`` frame
for its fixed prompt line, and ``oob`` frames (``Char.Vitals`` drawn as
bars). The player's display options (``color``, ``screenreader``,
``palette``) are applied before a frame leaves the server, as telnet does.

The tests that run a real HTTP server need ``aiohttp`` and skip without it.
"""

from __future__ import annotations

import asyncio
import importlib.util
import logging
import re

import pytest

from realm.config.loader import Settings
from realm.core.pools import set_pool
from realm.gateway.session import PAGER_PROMPT, Session
from realm.gateway.websocket import WebSocketHandler, client_page, make_ws_writer
from realm.testing import Simulator

HAS_AIOHTTP = importlib.util.find_spec("aiohttp") is not None
needs_aiohttp = pytest.mark.skipif(
    not HAS_AIOHTTP, reason="aiohttp is not installed (pip install 'realm[websocket]')")


class FakeWS:
    """Just enough of aiohttp's WebSocketResponse for the writer and handler."""

    def __init__(self):
        self.closed = False
        self.sent_str: list[str] = []
        self.sent_json: list[dict] = []

    async def send_str(self, s):
        self.sent_str.append(s)

    async def send_json(self, data):
        self.sent_json.append(data)


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


# --- the page ----------------------------------------------------------------------------------


class TestThePage:

    def test_the_page_is_one_self_contained_file(self):
        page = client_page()
        assert page.lstrip().lower().startswith("<!doctype html>")
        # No build step and no third-party code: nothing is fetched from elsewhere.
        assert not re.search(r"<script[^>]*\ssrc=", page)
        assert not re.search(r"<link[^>]*stylesheet", page)
        assert "http://" not in page and "https://" not in page

    def test_the_page_is_accessible_and_fits_a_phone(self):
        page = client_page()
        assert '<meta name="viewport"' in page
        assert "prefers-color-scheme: dark" in page
        # A real input with a label, and output a screen reader reads out.
        assert re.search(r'<label for="command"', page)
        assert re.search(r'<input[^>]*id="command"', page)
        assert re.search(r'id="output"[^>]*aria-live="polite"', page)

    def test_the_page_speaks_the_websocket_protocol(self):
        """The frames ``realm.gateway.websocket`` sends, by name."""
        page = client_page()
        for needle in ("'ws'", "'prompt'", "'oob'", "'Char.Vitals'", "'resize'",
                       "segments"):
            assert needle in page, needle


# --- the player's display options at the WebSocket edge ---------------------------------------


class TestOptionsAtTheEdge:
    """``color``, ``screenreader`` and ``palette`` (step 10.4) apply to
    WebSocket output as they do at the telnet edge."""

    async def test_markup_ships_as_segments_by_default(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        ws = FakeWS()
        await make_ws_writer(ws, lambda: pat)("|rRed|n and plain")
        assert ws.sent_json == [{"type": "text", "text": "Red and plain",
                                 "segments": [["r", "Red"], ["", " and plain"]]}]

    async def test_palette_swaps_colors_brightness_kept(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        pat.db.palette = {"r": "m"}
        ws = FakeWS()
        await make_ws_writer(ws, lambda: pat)("|rdark|n |Rbright|n |[rback|n")
        assert ws.sent_json[0]["segments"] == [
            ["m", "dark"], ["", " "], ["M", "bright"], ["", " "], ["[m", "back"]]

    async def test_color_off_sends_plain_text(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        pat.db.color = False
        ws = FakeWS()
        await make_ws_writer(ws, lambda: pat)("|rRed|n\n=====\nplain")
        assert ws.sent_json == [] and ws.sent_str == ["Red\n=====\nplain"]

    async def test_screenreader_drops_decoration_and_color(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        pat.db.screenreader = True
        ws = FakeWS()
        writer = make_ws_writer(ws, lambda: pat)
        await writer("|rRed|n\n=====\n+---+---+\nplain")
        await writer("+-------+")                 # nothing left once decoration went
        assert ws.sent_json == [] and ws.sent_str == ["Red\nplain"]

    async def test_text_cannot_pass_for_a_frame(self):
        """Only JSON frames start with ``{``: text that does (an ``@emit``
        of a fake prompt) arrives wrapped in a text frame."""
        ws = FakeWS()
        fake = '{"type": "prompt", "text": "<1/99hp>"}'
        await make_ws_writer(ws, lambda: None)(fake)
        assert ws.sent_str == [] and ws.sent_json == [{"type": "text", "text": fake}]

    async def test_before_login_markup_still_renders(self):
        ws = FakeWS()
        await make_ws_writer(ws, lambda: None)("|gWelcome|n")
        assert ws.sent_json == [{"type": "text", "text": "Welcome",
                                 "segments": [["g", "Welcome"]]}]

    async def test_the_prompt_frame_is_styled_like_text(self, sim):
        """The prompt is markup too: it arrives as plain text plus segments,
        never as raw ``|`` codes, and honours the palette."""
        pat = sim.player("Pat", location=sim.room("Hall"))
        session = Session(protocol="websocket")
        session.player = pat
        ws = FakeWS()
        handler = WebSocketHandler(ws, session, None, on_command=None)
        handler._send_prompt("<|r7|n/12hp> ")
        pat.db.palette = {"r": "c"}
        handler._send_prompt("<|r7|n/12hp> ")
        handler._send_prompt(PAGER_PROMPT)
        await asyncio.sleep(0.02)
        assert ws.sent_json == [
            {"type": "prompt", "text": "<7/12hp> ",
             "segments": [["", "<"], ["r", "7"], ["", "/12hp> "]]},
            {"type": "prompt", "text": "<7/12hp> ",
             "segments": [["", "<"], ["c", "7"], ["", "/12hp> "]]},
            {"type": "prompt", "text": PAGER_PROMPT},
        ]


# --- Char.Vitals for the bars ------------------------------------------------------------------


class TestVitals:
    """The page draws ``Char.Vitals`` as bars; the session sends it with the
    prompt whenever a pool changed, to any client with an OOB channel."""

    def test_pools_go_out_with_the_prompt_when_they_change(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        set_pool(pat, "hp", 7, max=12)
        pat.db.pools = {"mana": {}}                         # a declared pool
        set_pool(pat, "mana", 3, max=5)
        session = Session(protocol="websocket")
        seen = []
        session.set_oob_writer(lambda package, data: seen.append((package, data)))
        session.link_player(pat)
        session.write_prompt()
        session.write_prompt()                              # nothing changed: not again
        assert seen == [("Char.Vitals", {"hp": 7, "max_hp": 12, "mana": 3, "max_mana": 5})]
        set_pool(pat, "hp", 9)
        session.write_prompt()
        assert seen[1:] == [("Char.Vitals", {"hp": 9, "max_hp": 12, "mana": 3, "max_mana": 5})]

    def test_no_oob_channel_no_player_no_send(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        set_pool(pat, "hp", 7, max=12)
        session = Session(protocol="telnet")
        seen = []
        session.set_oob_writer(lambda package, data: seen.append(package))
        session.write_prompt()                              # not logged in yet
        assert seen == []


# --- settings ----------------------------------------------------------------------------------


class TestSettings:

    def test_off_by_default(self):
        assert Settings().web_client is False

    async def test_web_client_without_websocket_warns_with_the_fix(self, caplog):
        from realm.server.game import GameServer
        server = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                            web_client=True)
        with caplog.at_level(logging.WARNING, logger="realm.server.game"):
            await server.start()
        try:
            assert any("WEB_CLIENT" in r.message and "ENABLE_WEBSOCKET = True" in r.message
                       for r in caplog.records)
        finally:
            await server.stop()


# --- a real HTTP server ------------------------------------------------------------------------


async def _frames_until(ws, predicate, timeout: float = 5.0) -> list:
    """Frames received (str, or dict for JSON) until one satisfies ``predicate``."""
    import json

    from aiohttp import WSMsgType
    frames = []
    async with asyncio.timeout(timeout):
        while True:
            msg = await ws.receive()
            assert msg.type == WSMsgType.TEXT, msg
            data = msg.data
            frame = json.loads(data) if data.startswith("{") else data
            frames.append(frame)
            if predicate(frame):
                return frames


def _text(frame) -> str:
    if isinstance(frame, str):
        return frame
    return frame.get("text", "") if frame.get("type") == "text" else ""


@needs_aiohttp
class TestServedForReal:

    @pytest.fixture
    async def game(self):
        from realm.server.game import GameServer
        from tests.test_accounts import Instant
        server = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                            game_system=Instant)
        await server.start()
        try:
            yield server
        finally:
            await server.stop()

    def _client(self, game, web_client: bool):
        from aiohttp.test_utils import TestClient, TestServer

        from realm.gateway.websocket import WebSocketServer
        ws_server = WebSocketServer(game.session_manager, game._on_command,
                                    web_client=web_client, game_name="Testland <&>")
        return TestClient(TestServer(ws_server.make_app()))

    async def test_the_page_is_served_at_the_root(self, game):
        async with self._client(game, web_client=True) as client:
            response = await client.get("/")
            assert response.status == 200
            assert response.content_type == "text/html"
            page = await response.text()
            assert '<label for="command"' in page
            assert "<title>Testland &lt;&amp;&gt;</title>" in page   # the game's name, escaped

    async def test_no_page_unless_web_client_is_set(self, game):
        async with self._client(game, web_client=False) as client:
            assert (await client.get("/")).status == 404
            assert (await client.get("/health")).status == 200

    async def test_a_websocket_session_logs_in_and_looks(self, game):
        async with self._client(game, web_client=True) as client:
            ws = await client.ws_connect("/ws")
            welcome = await _frames_until(ws, lambda f: "connect" in _text(f))
            assert welcome
            await ws.send_str("create Ann correcthorse")
            await _frames_until(ws, lambda f: "name" in _text(f).lower())
            await ws.send_str("Bree")
            await _frames_until(ws, lambda f: isinstance(f, dict) and f.get("type") == "prompt")
            assert game.session_manager.player_count() == 1
            await ws.send_json({"type": "command", "command": "look"})
            frames = await _frames_until(
                ws, lambda f: isinstance(f, dict) and f.get("type") == "prompt")
            player = game.session_manager.online_players()[0]
            assert player.name == "Bree"
            looked = "\n".join(_text(f) for f in frames)
            assert player.location.name in looked
            await ws.close()
