"""
Heredoc multi-line input — a command line ending in the OPEN sigil ('''
by default) starts collecting; a line of the CLOSE sigil ends it, and the
whole block is dispatched as one command with indentation intact. Lets a
builder @set a readable multi-line script instead of a `;` one-liner.

Two layers: the session-level accumulator (this is where indentation must
survive the usual per-line strip), and the reconstructed command running
end to end through the real dispatcher.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from realm.gateway.session import (
    DEFAULT_HEREDOC_CLOSE,
    DEFAULT_HEREDOC_OPEN,
    HEREDOC_ABORT,
    HEREDOC_MAX_LINES,
    Session,
    set_heredoc_sigils,
)
from realm.testing import Simulator


@pytest.fixture(autouse=True)
def _reset_heredoc_sigils():
    set_heredoc_sigils(DEFAULT_HEREDOC_OPEN, DEFAULT_HEREDOC_CLOSE)
    yield
    set_heredoc_sigils(DEFAULT_HEREDOC_OPEN, DEFAULT_HEREDOC_CLOSE)


def _session_with_player() -> Session:
    s = Session(protocol="test")
    s.player = object()  # gating only checks `is not None`
    return s


def _drain(session: Session) -> list[str]:
    out: list[str] = []
    while True:
        try:
            out.append(session._input_queue.get_nowait())
        except asyncio.QueueEmpty:
            return out


class TestAccumulation:

    def test_basic_block_reconstructs_one_command(self):
        s = _session_with_player()
        s.submit_input("@set obj/greet='''")
        s.submit_input("a = 1")
        s.submit_input("if a:")
        s.submit_input("    result = 'hi'")
        s.submit_input("'''")
        assert _drain(s) == ["@set obj/greet=a = 1\nif a:\n    result = 'hi'"]
        assert s._heredoc is None

    def test_indentation_is_preserved(self):
        s = _session_with_player()
        s.submit_input("@set x/s='''")
        s.submit_input("for i in range(3):")
        s.submit_input("    total = i")  # 4-space indent must survive the strip
        s.submit_input("'''")
        assert "\n    total = i" in _drain(s)[0]

    def test_nothing_queued_while_collecting(self):
        s = _session_with_player()
        s.submit_input("@set x/s='''")
        s.submit_input("a = 1")
        assert _drain(s) == []
        assert s._heredoc is not None

    def test_abort_discards_the_block(self):
        s = _session_with_player()
        s.submit_input("@set x/s='''")
        s.submit_input("a = 1")
        s.submit_input(HEREDOC_ABORT)
        assert _drain(s) == []
        assert s._heredoc is None

    def test_line_cap_aborts(self):
        s = _session_with_player()
        s.submit_input("@set x/s='''")
        for i in range(HEREDOC_MAX_LINES):
            s.submit_input(f"a{i} = {i}")
        assert s._heredoc is not None          # still collecting at the cap
        s.submit_input("one_too_many = 1")     # trips the cap
        assert s._heredoc is None              # aborted, block discarded
        assert not any(q.startswith("@set") for q in _drain(s))


class TestGating:

    def test_no_heredoc_before_login(self):
        s = Session(protocol="test")  # player is None
        s.submit_input("@set x/s='''")
        assert s._heredoc is None
        assert _drain(s) == ["@set x/s='''"]

    def test_no_heredoc_during_a_prompt(self):
        s = _session_with_player()
        s._prompt_future = object()
        s.submit_input("@set x/s='''")
        assert s._heredoc is None
        assert _drain(s) == ["@set x/s='''"]

    def test_multiline_paste_is_not_an_open(self):
        # A whole block arriving as ONE message (websocket paste) has an
        # internal newline and must not be misread as an opening line.
        s = _session_with_player()
        s.submit_input("look\nsay hi'''")
        assert s._heredoc is None
        assert _drain(s) == ["look\nsay hi'''"]


class TestDistinctSigils:

    def test_angle_brackets_let_triple_quote_live_in_the_body(self):
        set_heredoc_sigils("<<<", ">>>")
        s = _session_with_player()
        s.submit_input("@set x/s=<<<")
        s.submit_input("a = 1")
        s.submit_input("'''")   # just a body line now — not the close
        s.submit_input(">>>")
        assert _drain(s) == ["@set x/s=a = 1\n'''"]

    def test_bad_sigils_rejected(self):
        for bad in ("", "END", "a1", "x" * 17, "a b"):
            with pytest.raises(ValueError):
                set_heredoc_sigils(bad, bad)


class TestEndToEnd:

    @pytest.fixture
    def sim(self):
        s = Simulator()
        s.engine.session_manager = SimpleNamespace(
            all_sessions=lambda: list(s._sessions.values()))
        try:
            yield s
        finally:
            s.close()

    async def test_reconstructed_command_stores_and_execs(self, sim):
        room = sim.room("Room")
        ada = sim.player("Ada", location=room)
        ada.add_tag("admin")
        gadget = sim.obj("gadget", location=room)
        sess = sim._sessions[ada.id]

        # Type a readable multi-line @set, line by line, as a builder would.
        sess.submit_input("@set gadget/probe='''")
        sess.submit_input("a = get('gadget')")
        sess.submit_input("if a is not None:")
        sess.submit_input("    result = 'found ' + a.name")
        sess.submit_input("'''")

        # The accumulator emitted exactly one reconstructed command.
        command = sess._input_queue.get_nowait()
        with pytest.raises(asyncio.QueueEmpty):
            sess._input_queue.get_nowait()

        # Run it through the real dispatcher: the multi-line body lands in
        # the attribute verbatim.
        await sim.do(ada, command)
        stored = gadget.db.get("probe")
        assert "\n" in stored
        assert "if a is not None:" in stored
        assert "    result =" in stored  # indentation survived end to end

        # And it execs as real multi-line softcode.
        result, error = await sim.eval(gadget, "result = eval_attr(me, 'probe')")
        assert error is None
        assert result == "found gadget"
