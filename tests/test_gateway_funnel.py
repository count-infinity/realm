"""
The protocol-agnostic input funnel and the websocket adapter's parity
with telnet — the AresMUSH steal-list #1 discipline: protocols decode
bytes into ONE common representation (a normalized line in the session
input queue), a per-session pump drains it through the server's single
sink in order, and structured OOB push reaches every protocol the same
way.
"""

from __future__ import annotations

import asyncio

import pytest

from realm.gateway.session import Session, SessionManager
from realm.gateway.websocket import WebSocketHandler, make_ws_writer


class FakeWS:
    """Just enough of aiohttp's WebSocketResponse for the handler."""

    def __init__(self):
        self.closed = False
        self.sent_str: list[str] = []
        self.sent_json: list[dict] = []

    async def send_str(self, s):
        self.sent_str.append(s)

    async def send_json(self, data):
        self.sent_json.append(data)


@pytest.mark.asyncio
class TestInputPump:

    async def test_lines_are_processed_in_arrival_order(self):
        """Rapid input drains one line at a time, in order — no
        per-line task races (the old telnet behavior)."""
        seen: list[str] = []

        async def sink(session, line):
            await asyncio.sleep(0.01)   # a slow command
            seen.append(line)

        session = Session()
        session.start_input_pump(sink)
        try:
            for i in range(5):
                session.submit_input(f"cmd {i}")
            await asyncio.sleep(0.1)
            assert seen == [f"cmd {i}" for i in range(5)]
        finally:
            session.stop_input_pump()

    async def test_submit_normalizes_and_drops_empty(self):
        seen: list[str] = []

        async def sink(session, line):
            seen.append(line)

        session = Session()
        session.start_input_pump(sink)
        try:
            session.submit_input("  look  \r")
            session.submit_input("   ")
            session.submit_input("")
            await asyncio.sleep(0.05)
            assert seen == ["look"]
        finally:
            session.stop_input_pump()

    async def test_sink_error_does_not_kill_the_pump(self):
        seen: list[str] = []

        async def sink(session, line):
            if line == "boom":
                raise RuntimeError("bad command handler")
            seen.append(line)

        session = Session()
        session.start_input_pump(sink)
        try:
            session.submit_input("boom")
            session.submit_input("still alive")
            await asyncio.sleep(0.05)
            assert seen == ["still alive"]
        finally:
            session.stop_input_pump()

    async def test_manager_wires_the_sink_and_teardown_stops_the_pump(self):
        seen: list[str] = []

        async def sink(session, line):
            seen.append(line)

        manager = SessionManager()
        manager.set_input_sink(sink)
        session = await manager.create_session(protocol="test")
        session.submit_input("hello")
        await asyncio.sleep(0.05)
        assert seen == ["hello"]

        await manager.destroy_session(session)
        assert session._input_task is None      # pump stopped


@pytest.mark.asyncio
class TestWebSocketParity:

    def _handler(self, sink=None):
        manager = SessionManager()
        if sink is not None:
            manager.set_input_sink(sink)
        session = Session(protocol="websocket")
        ws = FakeWS()
        handler = WebSocketHandler(ws, session, manager, on_command=None)
        return ws, session, handler

    async def test_commands_plain_and_json_land_in_the_same_funnel(self):
        seen: list[str] = []

        async def sink(session, line):
            seen.append(line)

        ws, session, handler = self._handler()
        session.start_input_pump(sink)
        try:
            await handler._handle_text("look")
            await handler._handle_text('{"type": "command", "command": "north"}')
            await asyncio.sleep(0.05)
            assert seen == ["look", "north"]
        finally:
            session.stop_input_pump()

    async def test_msg_oob_reaches_web_clients(self):
        """Parity with telnet+GMCP: session.send_oob produces a
        structured frame, not silence."""
        ws, session, handler = self._handler()
        session.set_oob_writer(handler._send_oob)

        session.send_oob("Room.Info", {"id": "abc", "name": "The Jetty"})
        await asyncio.sleep(0.02)

        assert ws.sent_json == [{
            "type": "oob",
            "package": "Room.Info",
            "data": {"id": "abc", "name": "The Jetty"},
        }]

    async def test_inbound_oob_is_remembered_like_gmcp(self):
        ws, session, handler = self._handler()
        await handler._handle_json({
            "type": "oob",
            "package": "Core.Supports",
            "data": ["Room 1", "Char 1"],
        })
        assert session.oob_supports["Core.Supports"] == ["Room 1", "Char 1"]

    async def test_welcome_writer_renders_markup_from_the_first_byte(self):
        """The writer installed before create_session must render pipe
        markup as segments — no raw-markup leak window on the welcome
        screen."""
        from realm.core.markup import MARKER
        ws = FakeWS()
        writer = make_ws_writer(ws)

        await writer(f"Welcome to {MARKER}rREALM{MARKER}n, traveler.")
        await writer("plain line")

        assert len(ws.sent_json) == 1
        frame = ws.sent_json[0]
        assert frame["type"] == "text"
        assert frame["text"] == "Welcome to REALM, traveler."
        assert any("REALM" == seg for _style, seg in frame["segments"])
        assert ws.sent_str == ["plain line"]
