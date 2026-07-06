"""
Out-of-band protocol support: GMCP on telnet, the session/object OOB
channel, engine emissions (Room.Info, Char.Vitals), softcode oob().
"""

from __future__ import annotations

import json

import pytest

from realm.core.objects import GameObject
from realm.core.propagation import reset_engine
from realm.gateway.session import Session


@pytest.fixture(autouse=True)
def fresh():
    reset_engine()
    yield
    reset_engine()


class FakeTransport:
    def __init__(self):
        self.written = b""

    def write(self, data: bytes) -> None:
        self.written += data


def make_protocol():
    from realm.gateway.telnet import TelnetProtocol as TelnetServerProtocol
    proto = TelnetServerProtocol.__new__(TelnetServerProtocol)
    # minimal state the byte machine needs
    proto.transport = FakeTransport()
    proto.session = Session(protocol="telnet", address="127.0.0.1")
    proto._buffer = bytearray()
    proto._in_iac = False
    proto._iac_command = bytearray()
    return proto


class TestSessionChannel:

    def test_send_oob_noop_without_writer(self):
        sess = Session(protocol="test", address="1.1.1.1")
        sess.send_oob("Char.Vitals", {"hp": 5})  # must not raise

    def test_send_oob_routes_to_writer(self):
        sess = Session(protocol="test", address="1.1.1.1")
        seen = []
        sess.set_oob_writer(lambda p, d: seen.append((p, d)))
        sess.send_oob("Char.Vitals", {"hp": 5})
        assert seen == [("Char.Vitals", {"hp": 5})]

    def test_link_player_wires_msg_oob(self):
        sess = Session(protocol="test", address="1.1.1.1")
        seen = []
        sess.set_oob_writer(lambda p, d: seen.append(p))
        player = GameObject("Bob", tags=["player"])
        sess.link_player(player)
        player.msg_oob("Room.Info", {"id": "x"})
        assert seen == ["Room.Info"]
        sess.unlink_player()
        player.msg_oob("Room.Info", {"id": "y"})  # no-op after unlink
        assert seen == ["Room.Info"]

    def test_npc_msg_oob_is_noop(self):
        npc = GameObject("guard", tags=["npc"])
        npc.msg_oob("Char.Vitals", {"hp": 1})  # must not raise


class TestTelnetGmcp:

    def test_will_gmcp_offered_and_do_wires_channel(self):
        proto = make_protocol()
        # Client answers IAC DO GMCP
        for b in bytes([255, 253, 201]):
            if proto._in_iac:
                proto._handle_iac(b)
            elif b == 255:
                proto._in_iac = True
                proto._iac_command = bytearray([b])
        assert proto.session._oob_writer is not None

        proto.session.send_oob("Char.Vitals", {"hp": 7})
        out = proto.transport.written
        assert out.startswith(bytes([255, 250, 201]))  # IAC SB GMCP
        assert out.endswith(bytes([255, 240]))         # IAC SE
        body = out[3:-2].decode()
        package, _, payload = body.partition(" ")
        assert package == "Char.Vitals"
        assert json.loads(payload) == {"hp": 7}

    def test_inbound_gmcp_parsed_into_supports(self):
        proto = make_protocol()
        payload = b'Core.Hello {"client": "Mudlet", "version": "4.17"}'
        frame = bytes([255, 250, 201]) + payload + bytes([255, 240])
        proto.data_received(frame)
        assert proto.session.oob_supports["Core.Hello"]["client"] == "Mudlet"

    def test_sb_iac_escape(self):
        proto = make_protocol()
        # An escaped 255 inside the payload must not terminate the block.
        payload = b'Test.Bytes "a' + bytes([255, 255]) + b'b"'
        frame = bytes([255, 250, 201]) + payload + bytes([255, 240])
        proto.data_received(frame)  # must not raise; block consumed
        assert not getattr(proto, '_in_sb', False)


@pytest.mark.asyncio
class TestEngineEmissions:

    async def test_room_info_on_movement(self):
        from realm.core.movement import move_through_exit

        west = GameObject("West", tags=["room"])
        east = GameObject("East Hall", tags=["room"])
        door = GameObject("east", tags=["exit"], location=west)
        door.db.destination_obj = east
        back = GameObject("west", tags=["exit"], location=east)
        back.db.destination_obj = west

        alice = GameObject("Alice", tags=["player"], location=west)
        seen = []
        alice.set_oob_handler(lambda p, d: seen.append((p, d)))

        await move_through_exit(alice, east, exit_obj=door)
        assert seen and seen[0][0] == "Room.Info"
        assert seen[0][1]["name"] == "East Hall"
        assert "west" in seen[0][1]["exits"]

    async def test_softcode_oob(self):
        from realm.scripting.engine import ScriptEngine

        room = GameObject("Deck", tags=["room"])
        console = GameObject("console", location=room)
        alice = GameObject("Alice", tags=["player"], location=room)
        seen = []
        alice.set_oob_handler(lambda p, d: seen.append((p, d)))
        console.db.on_scan = "oob('Alice', 'Ship.Status', {'hull': 87})"

        engine = ScriptEngine()
        await engine.run_object_script(console, "on_scan")
        assert seen == [("Ship.Status", {"hull": 87})]
