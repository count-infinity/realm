"""
MUD_PLAN step 10: comfort.

Long output is held a screen at a time (``Session.send_paged``), long text
is written in a line editor (``@edit``, ``@desc``, ``mail``), players make
their own aliases, and ``config`` lists and sets their display options,
which live on the account when there is one. Pager and editor input goes
through ``Simulator.submit_line``, the path a live connection uses.
"""

from __future__ import annotations

import pytest

from realm.config.loader import Settings
from realm.core.markup import to_ansi, undecorate
from realm.core.options import get_option, options_holder
from realm.gateway.session import PAGER_PROMPT, Session
from realm.gateway.telnet import render_for
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator(settings=Settings(page_length=4))
    try:
        yield s
    finally:
        s.close()


def numbered(count: int) -> str:
    return "\n".join(f"line {n}" for n in range(1, count + 1))


def text(sim, player) -> str:
    return "\n".join(sim.seen(player))


async def all_pages(sim, player) -> str:
    """Everything sent, pressing enter until the pager lets go."""
    out = sim.seen(player)
    while sim.session(player).paging:
        await sim.submit_line(player, "")
        out += sim.seen(player)
    return "\n".join(line for line in out if line != PAGER_PROMPT)


# --- 10.1 the pager ---------------------------------------------------------------------------


class TestPager:

    async def test_long_output_is_held_a_screen_at_a_time(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        session = sim.session(pat)
        session.send_paged(numbered(8))
        # A screen of 4: three lines and the pager's prompt.
        assert sim.seen(pat) == ["line 1\nline 2\nline 3", PAGER_PROMPT]
        assert session.paging and sim.prompt(pat) == PAGER_PROMPT
        await sim.submit_line(pat, "")                      # enter: the next page
        assert sim.seen(pat) == ["line 4\nline 5\nline 6", PAGER_PROMPT]
        await sim.submit_line(pat, "b")                     # back
        assert sim.seen(pat) == ["line 1\nline 2\nline 3", PAGER_PROMPT]
        await sim.submit_line(pat, "")
        sim.seen(pat)
        await sim.submit_line(pat, "")                      # the last page ends it
        assert sim.seen(pat) == ["line 7\nline 8"]
        assert not session.paging and sim.prompt(pat) != PAGER_PROMPT

    async def test_q_stops_and_any_other_line_is_a_command(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        session = sim.session(pat)
        session.send_paged(numbered(8))
        sim.seen(pat)
        await sim.submit_line(pat, "q")
        assert sim.seen(pat) == [] and not session.paging
        session.send_paged(numbered(8))
        sim.seen(pat)
        await sim.submit_line(pat, "think still here")
        assert not session.paging
        assert "You think: still here" in text(sim, pat)

    async def test_short_output_is_not_held(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        sim.session(pat).send_paged(numbered(4))
        assert sim.seen(pat) == [numbered(4)]
        assert not sim.session(pat).paging

    async def test_a_blank_line_is_input_only_while_paging(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        session = sim.session(pat)
        session.submit_input("")
        assert session.receive_nowait() is None
        session.send_paged(numbered(8))
        session.submit_input("")
        assert session.receive_nowait() == ""

    def test_the_screen_is_the_players_option_then_the_client_then_the_setting(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        session = sim.session(pat)
        assert session.page_length() == 4                   # PAGE_LENGTH
        session.set_data("terminal_height", 30)             # NAWS
        assert session.page_length() == 30
        pat.db.pagelength = 0                               # the player's own
        assert session.page_length() == 0
        session.send_paged(numbered(100))
        assert sim.seen(pat) == [numbered(100)]

    async def test_commands_page_their_output(self, sim):
        bea = sim.player("Bea", location=sim.room("Hall"))
        bea.add_tag("builder")
        for command in ("help", "@examine me"):
            await sim.do(bea, command)
            assert sim.seen(bea)[-1] == PAGER_PROMPT, command
            await sim.submit_line(bea, "q")
        for name in ("help", "who", "skills", "socials", "mail", "channel"):
            # (mail's list and letters, a channel's history: the same call)
            assert sim.dispatcher.get_command(name) is not None

    async def test_the_server_shows_the_pagers_prompt(self, sim):
        from types import SimpleNamespace

        from realm.server.game import GameServer
        pat = sim.player("Pat", location=sim.room("Hall"), hp=7, max_hp=10)
        session = sim.session(pat)
        written: list[str] = []
        prompts: list[str] = []

        async def writer(message):
            written.append(message)

        session.set_writer(writer)
        session.set_prompt_writer(prompts.append)
        server = GameServer.__new__(GameServer)
        server.world = sim.world
        server.session_manager = SimpleNamespace(all_sessions=lambda: [session])
        await server._on_command(session, "help")
        assert prompts == [PAGER_PROMPT]
        assert PAGER_PROMPT not in written                  # it is the prompt, not text
        await server._on_command(session, "q")
        assert prompts[-1] == "<7/10hp> "


# --- 10.2 the editor --------------------------------------------------------------------------


@pytest.fixture
def workshop(sim):
    room = sim.room("Workshop")
    bea = sim.player("Bea", location=room)
    bea.add_tag("builder")
    box = sim.obj("box", location=room)
    box.owner = bea
    return room, bea, box


class TestEditor:

    async def test_editing_an_attribute_line_by_line(self, sim, workshop):
        _room, bea, box = workshop
        box.db.note = "first"
        await sim.submit_line(bea, "@edit box/note")
        assert "Editing box/note (1 line)" in text(sim, bea)
        for line in ("third", "", "    indented", ".i 2 second", ".r 3 third!"):
            await sim.submit_line(bea, line)
        sim.seen(bea)
        await sim.submit_line(bea, ".l")                     # five lines: a page and more
        assert sim.seen(bea) == ["1: first\n2: second\n3: third!", PAGER_PROMPT]
        await sim.submit_line(bea, "")                       # the pager's, not the text's
        assert sim.seen(bea) == ["4: \n5:     indented"]
        await sim.submit_line(bea, ".d 4")
        await sim.submit_line(bea, "  kept as typed")
        await sim.submit_line(bea, ".s")
        assert "Saved box/note." in text(sim, bea)
        assert box.db.note == "first\nsecond\nthird!\n    indented\n  kept as typed"
        await sim.submit_line(bea, "think back to commands")
        assert "You think: back to commands" in text(sim, bea)

    async def test_quit_saves_nothing(self, sim, workshop):
        _room, bea, box = workshop
        await sim.submit_line(bea, "@edit box/note")
        await sim.submit_line(bea, "scribble")
        await sim.submit_line(bea, ".q")
        assert "nothing saved" in text(sim, bea)
        assert box.db.get("note") is None
        assert sim.session(bea).input_handler is None and not sim.session(bea).raw_lines

    async def test_softcode_is_checked_on_save_like_set(self, sim, workshop):
        _room, bea, box = workshop
        await sim.submit_line(bea, "@edit box/CMD_PUSH")
        await sim.submit_line(bea, "$push:")
        await sim.submit_line(bea, "  if (:")
        await sim.submit_line(bea, ".s")
        out = text(sim, bea)
        assert "Warning: box/CMD_PUSH will not run" in out and "Fix it" in out
        assert sim.session(bea).input_handler is not None     # still editing
        await sim.submit_line(bea, ".r 2   pemit(enactor, 'pushed')")
        await sim.submit_line(bea, ".s")
        assert sim.session(bea).input_handler is None
        assert box.db.CMD_PUSH == "$push:\n  pemit(enactor, 'pushed')"
        await sim.do(bea, "push")
        assert "pushed" in text(sim, bea)

    async def test_descriptions_and_desc_with_no_text(self, sim, workshop):
        room, bea, box = workshop
        await sim.submit_line(bea, "@edit box")
        await sim.submit_line(bea, "A plain box.")
        await sim.submit_line(bea, ".s")
        assert box.description == "A plain box."
        await sim.submit_line(bea, "@desc here")
        assert "Editing the description of Workshop" in text(sim, bea)
        await sim.submit_line(bea, "Sawdust everywhere.")
        await sim.submit_line(bea, "")
        await sim.submit_line(bea, "A bench.")
        await sim.submit_line(bea, ".s")
        assert room.description == "Sawdust everywhere.\n\nA bench."
        await sim.submit_line(bea, "@desc box =")              # = with nothing clears
        assert box.description == ""

    async def test_the_writes_are_gated_like_set(self, sim, workshop):
        room, bea, box = workshop
        stranger = sim.player("Stu", location=room)
        stranger.add_tag("builder")
        await sim.submit_line(stranger, "@edit box/note")
        assert "control" in text(sim, stranger)
        assert sim.session(stranger).input_handler is None
        box.db.count = 3
        await sim.submit_line(bea, "@edit box/count")
        assert "not text" in text(sim, bea)

    async def test_mail_with_no_body_opens_the_editor(self, sim):
        room = sim.room("Post office")
        ann = sim.player("Ann", location=room)
        bob = sim.player("Bob", location=room)
        sim.account("ann", ann)
        bob_account = sim.account("bob", bob)
        await sim.submit_line(ann, "mail Bob = Lunch")
        assert "Editing a letter to Bob: Lunch" in text(sim, ann)
        await sim.submit_line(ann, ".s")
        assert "The letter is empty" in text(sim, ann)
        await sim.submit_line(ann, "Noon at the inn?")
        await sim.submit_line(ann, ".s")
        assert "Mail sent to Bob." in text(sim, ann)
        letters = [o for o in sim.store.all_cached() if o.has_tag("mail")]
        assert [(m.db.subject, m.db.body, m.location) for m in letters] == \
            [("Lunch", "Noon at the inn?", bob_account)]
        await sim.submit_line(bob, "mail/reply 1")
        assert "Editing a letter to Ann: Re: Lunch" in text(sim, bob)
        await sim.submit_line(bob, "Yes.")
        await sim.submit_line(bob, ".s")
        assert "Mail sent to Ann." in text(sim, bob)


# --- 10.3 aliases -----------------------------------------------------------------------------


class TestAliases:

    async def test_alias_expands_with_its_words(self, sim):
        room = sim.room("Hall")
        pat = sim.player("Pat", location=room)
        await sim.do(pat, "alias th = think $2 then $1")
        await sim.do(pat, "alias tt = think")
        await sim.do(pat, "alias ta = think all: $*")
        sim.seen(pat)
        await sim.input(pat, "th one two")
        await sim.input(pat, "TT plain words")               # no $: the words go after
        await sim.input(pat, "ta x y")
        assert sim.seen(pat) == ["You think: two then one", "You think: plain words",
                                 "You think: all: x y"]
        await sim.do(pat, "alias")
        listing = text(sim, pat)
        assert "th" in listing and "think $2 then $1" in listing
        await sim.do(pat, "unalias th")
        assert pat.db.aliases == {"tt": "think", "ta": "think all: $*"}

    async def test_no_recursion_and_never_over_an_at_word(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        pat.add_tag("builder")
        await sim.do(pat, "alias aa = bb")
        await sim.do(pat, "alias bb = think deep")
        await sim.do(pat, "alias @ex = think no")
        assert "may not begin with @" in text(sim, pat)
        await sim.input(pat, "aa")                           # runs "bb", unexpanded
        assert "You think" not in text(sim, pat)
        pat.db.aliases = {**pat.db.aliases, "@ex": "think no"}  # even if stored
        await sim.input(pat, "@ex me")
        assert "You think: no" not in text(sim, pat)

    async def test_alias_runs_before_sleep_sees_the_line(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        await sim.do(pat, "alias up = wake")
        await sim.do(pat, "sleep")
        sim.seen(pat)
        await sim.input(pat, "up")
        assert "asleep" not in text(sim, pat).lower()
        assert not pat.has_tag("sleeping")

    async def test_bad_names_and_the_limit(self, sim):
        sim.world.settings.raw["ALIAS_LIMIT"] = 1
        pat = sim.player("Pat", location=sim.room("Hall"))
        await sim.do(pat, "alias alias = look")
        await sim.do(pat, "alias two words = look")
        await sim.do(pat, "alias l = look")
        await sim.do(pat, "alias k = kick $1")
        out = text(sim, pat)
        assert "cannot be an alias" in out and "one word" in out
        assert "the most you may keep" in out
        assert pat.db.aliases == {"l": "look"}


# --- 10.4 player settings ---------------------------------------------------------------------


class TestConfig:

    async def test_config_lists_and_sets(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        await sim.do(pat, "config")
        listing = await all_pages(sim, pat)
        for name in ("color", "pagelength", "prompt", "screenreader", "palette"):
            assert name in listing
        assert "4 (default)" in listing                       # PAGE_LENGTH
        await sim.do(pat, "config pagelength 40")
        await sim.do(pat, "config color off")
        await sim.do(pat, "config palette r=m b=c")
        await sim.do(pat, "config prompt <{hp}hp>")
        assert (pat.db.pagelength, pat.db.color, pat.db.palette, pat.db.prompt) == \
            (40, False, {"r": "m", "b": "c"}, "<{hp}hp> ")
        await sim.do(pat, "config pagelength lots")
        await sim.do(pat, "config palette r=purple")
        await sim.do(pat, "config nosuch 1")
        out = text(sim, pat)
        assert "whole number" in out and "letter=letter" in out and "no setting" in out
        await sim.do(pat, "config pagelength default")
        assert pat.db.get("pagelength") is None

    async def test_options_live_on_the_account_and_are_shared(self, sim):
        room = sim.room("Hall")
        ann, cole = sim.player("Ann", location=room), sim.player("Cole", location=room)
        account = sim.account("ann", ann, cole)
        await sim.do(ann, "config color off")
        await sim.do(ann, "prompt [{hp}]")
        assert options_holder(ann) is account and account.db.color is False
        assert ann.db.get("color") is None
        assert get_option(cole, "color") is False
        assert get_option(cole, "prompt") == "[{hp}] "
        await sim.do(cole, "color on")
        assert get_option(ann, "color") is True

    async def test_a_feature_adds_its_own_setting(self, sim):
        """The guide's example: another feature declares a setting through
        the service, with no import of ``basics``."""
        options = sim.world.services.get("options")
        options.toggle("autosacrifice", "Offer up what you kill.", False)
        options.number("wrap", "Wrap long lines at this width.", 80)
        with pytest.raises(ValueError, match="already declared"):
            options.toggle("color", "Again.", True)
        pat = sim.player("Pat", location=sim.room("Hall"))
        await sim.do(pat, "config autosacrifice")
        await sim.do(pat, "config wrap")
        assert text(sim, pat) == ("autosacrifice  off (default)\n  Offer up what you kill.\n"
                                  "wrap           80 (default)\n  Wrap long lines at this width.")
        await sim.do(pat, "config autosacrifice on")
        assert get_option(pat, "autosacrifice") is True

    def test_render_options_at_the_protocol_edge(self, sim):
        pat = sim.player("Pat", location=sim.room("Hall"))
        message = "|rRed|n and |Bblue|n\n=====\n+---+---+\nplain"
        assert render_for(pat, message) == to_ansi(message)
        pat.db.palette = {"r": "m"}
        assert render_for(pat, "|rRed|n") == to_ansi("|mRed|n")
        assert render_for(pat, "|RRed|n") == to_ansi("|MRed|n")   # bright stays bright
        pat.db.color = False
        assert render_for(pat, message) == "Red and blue\n=====\n+---+---+\nplain"
        pat.db.screenreader = True
        assert render_for(pat, message) == "Red and blue\nplain"
        assert undecorate("a == b\n...") == "a == b"

    async def test_options_kept_on_a_character_move_to_its_account(self):
        """Saved worlds: a character from before step 10 keeps its color and
        prompt on itself; entering play moves them to the account, whose
        own value wins."""
        from realm.server.game import GameServer
        from tests.test_accounts import Instant, _client
        server = GameServer(db_path=":memory:", enable_telnet=False, tick_interval=0,
                            game_system=Instant)
        await server.start()
        try:
            c = await _client(server)
            await c.send("create Ann correcthorse")
            await c.send("Bree")
            bree, account = c.player, c.account
            await c.send("logout")
            bree.db.color = False                            # as an old world stored it
            bree.db.prompt = "old> "
            account.db.prompt = "mine> "
            await c.send("connect Ann correcthorse")
            assert c.player is bree
            assert account.db.color is False and account.db.prompt == "mine> "
            assert bree.db.get("color") is None and bree.db.get("prompt") is None
        finally:
            await server.stop()


def test_a_session_with_no_player_still_pages():
    session = Session(protocol="test")
    session.send_paged(numbered(30))
    assert session.paging                                   # PAGE_LENGTH, no world: 24
