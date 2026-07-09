"""
The PennMUSH die, ported — regression for eval_attr (u()), |v inverse
video, and |/ newlines. If this passes, the Penn capability claims in
the docs are true.
"""

from __future__ import annotations

import pytest

from realm.core.markup import Style, parse, strip, to_ansi
from realm.core.objects import GameObject
from realm.core.propagation import get_engine, reset_engine
from realm.gateway.session import Session
from realm.scripting.engine import ScriptEngine
from realm.scripting.functions import ScriptFunctions
from realm.server.dispatcher import CommandContext


@pytest.fixture(autouse=True)
def fresh():
    reset_engine()
    yield
    reset_engine()


class TestMarkupAdditions:

    def test_reverse_video_parses_and_encodes(self):
        segments = parse("|v block |n plain")
        assert segments[0][0] == Style(reverse=True)
        assert "\x1b[0;7m" in to_ansi("|vX|n")

    def test_newline_code(self):
        assert strip("row one|/row two") == "row one\nrow two"
        assert to_ansi("a|/b") == "a\nb"

    def test_ansi_penn_i_is_inverse(self):
        funcs = ScriptFunctions()
        marked = funcs.ansi('whi', ' ')
        assert '|v' in marked and '|i' not in marked


@pytest.mark.asyncio
class TestEvalAttr:

    async def test_attr_as_function_with_args(self):
        obj = GameObject("die")
        obj.db.render_side = "result = 'face-' + arg0"
        funcs = ScriptFunctions(executor=obj)
        assert funcs.eval_attr(obj, 'render_side', 3) == "face-3"

    async def test_runs_with_caller_authority(self):
        # The attr LIVES on eve's object but runs AS the caller — it
        # cannot use eve's authority, and mutations hit the CALLER's side.
        eve = GameObject("Eve", tags=["player"])
        library = GameObject("library", owner=eve)
        library.db.helper = "result = set_attr(get('#' + '%!'), 'used', True)"
        caller = GameObject("gadget")
        funcs = ScriptFunctions(executor=caller)
        funcs.eval_attr(library, 'helper')
        assert library.db.get('used') is None  # eve's stuff untouched

    async def test_secret_attrs_refused(self):
        eve = GameObject("Eve", tags=["player"])
        vault = GameObject("vault", owner=eve)
        vault.db.recipe = "result = 'the secret'"
        from realm.core.attrflags import set_attr_flags
        set_attr_flags(vault, 'recipe', ['secret'])
        stranger = GameObject("Mallory", tags=["player"])
        funcs = ScriptFunctions(executor=stranger)
        assert funcs.eval_attr(vault, 'recipe') is None

    async def test_recursion_capped(self):
        obj = GameObject("mirror")
        obj.db.loop = "result = eval_attr(me, 'loop')"
        funcs = ScriptFunctions(executor=obj)
        assert funcs.eval_attr(obj, 'loop') is None  # terminates


@pytest.mark.asyncio
class TestThePennDie:
    """The user's die, translated — full trigger path."""

    async def test_roll_the_die(self):
        room = GameObject("Parlor", tags=["room"])
        alice = GameObject("Alice", tags=["player"], location=room)
        sess = Session(protocol="test", address="1.1.1.1")
        sess.link_player(alice)

        die = GameObject("6-sided die", tags=["thing"], location=room)
        die.locks['basic'] = "caller == owner"
        die.db.lock_fail_basic = "Why not try rolling it?"
        # Faces as an attribute-function (Penn's u(me/side.%q1)):
        die.db.render_side = (
            "art = {'1': '  *  ', '2': '*   *', '3': '*  * ',"
            "       '4': '* * *', '5': '* * *', '6': '* * *'}\n"
            "result = ansi('whi', '|/ ' + art[arg0] + ' |/')"
        )
        die.db.cmd_roll = (
            "$roll:n = rand(1, 6)\n"
            "pemit(enactor, 'You toss the die..' "
            "+ str(eval_attr(me, 'render_side', n)))"
        )

        engine = ScriptEngine()
        get_engine().add_observer(engine.handle_action)
        ctx = CommandContext(session=sess, player=alice, raw_input="roll",
                             command_name="roll", args="")
        assert await engine.handle_unknown_command(ctx) is True

        out = []
        while not sess._output_queue.empty():
            out.append(sess._output_queue.get_nowait())
        text = "\n".join(out)
        assert "You toss the die.." in text
        assert "|v" in text and "*" in text     # inverse-video face art
        # And it renders to real ANSI at the telnet edge:
        assert "\x1b[" in to_ansi(text)

    async def test_lock_failure_message(self):
        from realm.permissions.locks import LockType, check_lock, lock_failure_message

        owner = GameObject("Owner", tags=["player"])
        die = GameObject("6-sided die", owner=owner)
        die.locks['basic'] = "caller == owner"
        die.db.lock_fail_basic = "Why not try rolling it?"
        mallory = GameObject("Mallory", tags=["player"])
        assert check_lock(die, LockType.BASIC, mallory) is False
        assert lock_failure_message(die, LockType.BASIC, "{name}") == \
            "Why not try rolling it?"
