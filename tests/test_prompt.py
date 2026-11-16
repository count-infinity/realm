"""
MUD_PLAN step 3.3: the prompt.

One renderer per game (``feature.prompt``; ``basics`` declares the
default) turns a player into a prompt line, which the session writes after
each batch of output, never inside the message stream. Telnet ends it with
EOR (or GA) when the client negotiated it.
"""

from __future__ import annotations

import pytest

from realm.config.loader import Settings
from realm.gateway.session import Session
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    try:
        yield s
    finally:
        s.close()


class TestRendering:

    def test_the_default_shows_hit_points(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"), hp=7, max_hp=10)
        assert sim.prompt(pat) == "<7/10hp> "

    def test_the_setting_is_the_game_default(self):
        sim = Simulator(settings=Settings(raw={"PROMPT": "[{hp}] "}))
        try:
            pat = sim.player("Pat", location=sim.room("Hall"), hp=7, max_hp=10)
            assert sim.prompt(pat) == "[7] "
        finally:
            sim.close()

    def test_tokens_and_unknown_ones(self, sim):
        sim.game_system.pools = lambda: []
        from realm.core.pools import Pool, add_default
        add_default(sim.world, Pool("mana"))
        room = sim.room("Hall")
        pat = sim.player("Pat", location=room, hp=7, max_hp=10, mana=3, max_mana=9,
                         level=4, xp=120)
        pat.db.prompt = "{name} in {room}: {hp}/{max_hp} {mana}/{max_mana}m L{level} {xp}xp {nope}"
        assert sim.prompt(pat) == "Pat in Hall: 7/10 3/9m L4 120xp {nope}"

    def test_level_and_xp_stay_as_typed_without_the_attributes(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"), hp=7, max_hp=10)
        pat.db.prompt = "{level} {xp}"
        assert sim.prompt(pat) == "{level} {xp}"

    async def test_the_prompt_command(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"), hp=7, max_hp=10)
        await sim.do(pat, "prompt <{hp}hp {name}> ")
        assert sim.prompt(pat) == "<7hp Pat> "
        await sim.do(pat, "prompt")
        assert any("<{hp}hp {name}>" in line for line in sim.seen(pat))
        await sim.do(pat, "prompt off")
        assert sim.prompt(pat) is None
        await sim.do(pat, "prompt default")
        assert sim.prompt(pat) == "<7/10hp> "

    async def test_combat_shows_the_opponents_condition(self, sim):
        room = sim.room("Pit")
        pat = sim.player("Pat", location=room, hp=10, max_hp=10, skill_melee=12,
                         dodge=8, strength=10, dexterity=10)
        rat = sim.obj("rat", location=room, tags=["npc"], hp=1, max_hp=10,
                      skill_melee=8, dodge=5, strength=5, dexterity=10)
        pat.db.prompt = "[{combat}]"
        assert sim.prompt(pat) == "[]"
        mgr = sim.world.services["combat"]
        await mgr.initiate(pat, rat)
        try:
            assert sim.prompt(pat) == "[awful]"
        finally:
            mgr.stop_all()

    def test_seen_does_not_include_prompts(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"), hp=7, max_hp=10)
        pat.msg("hello")
        assert sim.seen(pat) == ["hello"]


class TestDelivery:

    def _session(self, player=None):
        writes, prompts = [], []
        session = Session(protocol="test", address="127.0.0.1")

        async def writer(text):
            writes.append(text)

        session.set_writer(writer)
        session.set_prompt_writer(prompts.append)
        if player is not None:
            session.link_player(player)
        return session, writes, prompts

    async def test_one_prompt_after_a_batch_of_output(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"), hp=7, max_hp=10)
        session, writes, prompts = self._session(pat)
        for line in ("one", "two", "three"):
            await session.send(line)
        await session.flush_output()
        assert writes == ["one", "two", "three"]
        assert prompts == ["<7/10hp> "]
        await session.flush_output()                # nothing new: no prompt
        assert prompts == ["<7/10hp> "]
        await session.flush_output(prompt=True)     # a command with no output
        assert len(prompts) == 2

    async def test_no_prompt_before_login(self, sim):
        session, writes, prompts = self._session()
        await session.send("Welcome!")
        await session.flush_output(prompt=True)
        assert writes == ["Welcome!"] and prompts == []

    async def test_no_prompt_while_a_softcode_prompt_waits(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"), hp=7, max_hp=10)
        session, writes, prompts = self._session(pat)
        session.input_handler = lambda _s, _line: True
        await session.send("Your answer?")
        await session.flush_output(prompt=True)
        assert prompts == []

    async def test_a_command_ends_with_a_prompt(self, sim):
        """The server's input path: the dispatcher, then a prompt for the
        typist even when the command printed nothing, and for bystanders
        only when they got output."""
        from types import SimpleNamespace

        from realm.server.game import GameServer
        room = sim.room("Hall")
        pat = sim.player("Pat", location=room, hp=7, max_hp=10)
        sam = sim.player("Sam", location=room, hp=5, max_hp=5)
        quiet = sim.player("Quiet", location=sim.room("Elsewhere"), hp=1, max_hp=1)
        prompts = {}
        for player in (pat, sam, quiet):
            session = sim.session(player)

            async def writer(_text):
                pass

            session.set_writer(writer)
            prompts[player.name] = []
            session.set_prompt_writer(prompts[player.name].append)
        server = GameServer.__new__(GameServer)
        server.world = sim.world                 # its dispatcher is the world's
        server.session_manager = SimpleNamespace(
            all_sessions=lambda: [sim.session(p) for p in (pat, sam, quiet)])
        await server._on_command(sim.session(pat), "say hi")
        assert prompts == {"Pat": ["<7/10hp> "], "Sam": ["<5/5hp> "], "Quiet": []}
        await server._on_command(sim.session(pat), "prompt")    # prints its template
        await server._on_command(sim.session(pat), "")          # prints nothing
        assert len(prompts["Pat"]) == 3 and prompts["Sam"] == ["<5/5hp> "]


class TestTelnet:

    def _protocol(self, player):
        from tests.test_oob import make_protocol
        proto = make_protocol()
        proto.encoding = "utf-8"
        proto._in_sb = False
        proto.session.link_player(player)
        return proto

    def test_the_prompt_ends_with_eor_once_negotiated(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"), hp=7, max_hp=10)
        proto = self._protocol(pat)
        proto._write_prompt("<7/10hp> ")
        assert proto.transport.written == b"<7/10hp> "
        proto.transport.written = b""
        proto.data_received(bytes([255, 253, 25]))   # IAC DO EOR
        proto._write_prompt("<7/10hp> ")
        assert proto.transport.written == b"<7/10hp> " + bytes([255, 239])

    def test_ga_when_the_client_keeps_go_ahead(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"), hp=7, max_hp=10)
        proto = self._protocol(pat)
        proto.data_received(bytes([255, 254, 3]))    # IAC DONT SGA
        proto.transport.written = b""
        proto._write_prompt("> ")
        assert proto.transport.written == b"> " + bytes([255, 249])

    async def test_output_after_a_prompt_starts_on_a_new_line(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"), hp=7, max_hp=10)
        proto = self._protocol(pat)
        proto.transport.is_closing = lambda: False
        proto._write_prompt("> ")
        proto.transport.written = b""
        await proto._write_to_client("hello")
        assert proto.transport.written == b"\r\nhello\r\n"
