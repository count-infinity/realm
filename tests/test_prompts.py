"""
Interactive prompts / wizards: session.prompt/confirm/choose, the
allow-list escape, abort, and disconnect cleanup.
"""

from __future__ import annotations

import asyncio

import pytest

from realm.gateway.session import Session


def _sess():
    return Session(protocol="test", address="1.1.1.1")


def drain(s):
    out = []
    while not s._output_queue.empty():
        out.append(s._output_queue.get_nowait())
    return out


@pytest.mark.asyncio
class TestPrompt:

    async def test_prompt_awaits_next_line(self):
        s = _sess()
        task = asyncio.create_task(s.prompt("Name your blade:"))
        await asyncio.sleep(0)
        assert s.input_handler is not None            # capture installed
        assert "Name your blade:" in drain(s)
        consumed = await s.input_handler(s, "Excalibur")
        assert consumed is True
        assert await task == "Excalibur"
        assert s.input_handler is None                # released

    async def test_abort_returns_none(self):
        s = _sess()
        task = asyncio.create_task(s.prompt("Name?"))
        await asyncio.sleep(0)
        await s.input_handler(s, "abort")
        assert await task is None
        assert s.input_handler is None

    async def test_help_passes_through(self):
        s = _sess()
        task = asyncio.create_task(s.prompt("Name?"))
        await asyncio.sleep(0)
        # help is an escape command — NOT consumed; prompt stays pending.
        consumed = await s.input_handler(s, "help")
        assert consumed is False
        assert s.input_handler is not None
        assert not task.done()
        await s.input_handler(s, "Durendal")           # now answer
        assert await task == "Durendal"

    async def test_choices_reprompt_until_valid(self):
        s = _sess()
        task = asyncio.create_task(s.prompt("Edged or blunt?", choices=["edged", "blunt"]))
        await asyncio.sleep(0)
        consumed = await s.input_handler(s, "sparkly")  # invalid
        assert consumed is True and not task.done()
        assert any("edged, blunt" in m for m in drain(s))
        await s.input_handler(s, "ed")                  # prefix match
        assert await task == "edged"

    async def test_confirm(self):
        s = _sess()
        task = asyncio.create_task(s.confirm("Forge it?"))
        await asyncio.sleep(0)
        await s.input_handler(s, "y")
        assert await task is True

    async def test_choose_numbered(self):
        s = _sess()
        task = asyncio.create_task(s.choose("Pick:", ["red", "blue", "green"]))
        await asyncio.sleep(0)
        await s.input_handler(s, "2")
        assert await task == "blue"

    async def test_disconnect_cancels_pending(self):
        from realm.gateway.session import SessionManager

        mgr = SessionManager()
        s = await mgr.create_session(protocol="test", address="1.1.1.1")
        task = asyncio.create_task(s.prompt("Name?"))
        await asyncio.sleep(0)
        await mgr.destroy_session(s)          # hang up mid-prompt
        assert await task is None             # the wizard task ends cleanly


@pytest.mark.asyncio
class TestSoftcodePrompt:

    async def _setup(self):
        from realm.core.objects import GameObject
        from realm.core.propagation import get_engine, reset_engine
        from realm.gateway.session import SessionManager
        from realm.persistence.manager import set_active_manager
        from realm.scripting.engine import ScriptEngine
        from tests.test_olc import MockPersistence

        reset_engine()
        pers = MockPersistence()
        set_active_manager(pers)
        mgr = SessionManager()
        engine = ScriptEngine(persistence=pers)
        engine.session_manager = mgr
        get_engine().add_observer(engine.handle_action)

        room = GameObject("Gate", tags=["room"])
        clerk = GameObject("clerk", location=room)
        pers.add(clerk)
        alice = GameObject("Alice", tags=["player"], location=room)
        pers.add(alice)
        sess = await mgr.create_session(protocol="test", address="1.1.1.1")
        sess.link_player(alice)
        return engine, pers, room, clerk, alice, sess

    def _drain(self, sess):
        out = []
        while not sess._output_queue.empty():
            out.append(sess._output_queue.get_nowait())
        return out

    async def test_prompt_runs_callback_with_answer(self):
        engine, pers, room, clerk, alice, sess = await self._setup()
        try:
            # The callback runs AS the executor (clerk) — it reacts with
            # the NPC's authority; the answer is arg0.
            clerk.db.ask_name = "prompt(enactor, 'Your name?', 'got_name')"
            clerk.db.got_name = ("set_attr(me, 'last_visitor', arg0)\n"
                                 "pemit(enactor, 'Welcome, ' + arg0 + '.')")
            await engine.run_object_script(clerk, "ask_name", enactor=alice)
            assert sess.input_handler is not None
            assert any("Your name?" in m for m in self._drain(sess))
            await sess.input_handler(sess, "Guinevere")
            assert clerk.db.get("last_visitor") == "Guinevere"   # NPC remembers
            assert any("Welcome, Guinevere." in m for m in self._drain(sess))
            assert sess.input_handler is None
        finally:
            from realm.persistence.manager import set_active_manager
            set_active_manager(None)

    async def test_persistent_flag_stores_db_marker(self):
        engine, pers, room, clerk, alice, sess = await self._setup()
        try:
            clerk.db.ask = "prompt(enactor, 'Password?', 'check', persistent=True)"
            clerk.db.check = "say('heard: ' + arg0)"
            await engine.run_object_script(clerk, "ask", enactor=alice)
            assert alice.db.get("input_prompt")["callback"] == "check"
            await sess.input_handler(sess, "swordfish")
            assert alice.db.get("input_prompt") is None   # cleared on answer
        finally:
            from realm.persistence.manager import set_active_manager
            set_active_manager(None)
