"""
call(obj, 'attr', *args) — invoke an attribute as a METHOD on obj, running
AS obj (me / V scoped to obj, enactor preserved). The run-as-target
counterpart to eval_attr's run-as-caller. Gated by control-of-obj OR the
`public` attrflag (the cross-owner opt-in). See docs/design/object-identity.md
and BACKLOG's @function entry.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.core.attrflags import set_attr_flags
from realm.testing import Simulator


@pytest.fixture
def sim():
    s = Simulator()
    s.engine.session_manager = SimpleNamespace(
        all_sessions=lambda: list(s._sessions.values()))
    try:
        yield s
    finally:
        s.close()


class TestRunsAsTarget:

    async def test_V_is_scoped_to_the_target(self, sim):
        room = sim.room("R")
        core = sim.obj("core", location=room)
        core.db.set("accounts", 42)
        core.db.set("report", "result = V('accounts')")
        term = sim.obj("terminal", location=room)
        term.db.set("accounts", 999)  # the CALLER's value must NOT win
        res, err = await sim.eval(term, "result = call(get('core'), 'report')")
        assert err is None
        assert res == 42

    async def test_me_is_the_target(self, sim):
        room = sim.room("R")
        core = sim.obj("core", location=room)
        core.db.set("whoami", "result = name(me)")
        term = sim.obj("terminal", location=room)
        res, err = await sim.eval(term, "result = call(get('core'), 'whoami')")
        assert err is None
        assert res == "core"

    async def test_enactor_is_preserved(self, sim):
        room = sim.room("R")
        ada = sim.player("Ada", location=room)
        core = sim.obj("core", location=room)
        core.db.set("who", "result = name(enactor)")
        term = sim.obj("terminal", location=room)
        res, err = await sim.eval(
            term, "result = call(get('core'), 'who')", enactor=ada)
        assert err is None
        assert res == "Ada"


class TestGating:

    async def test_co_owned_needs_no_flag(self, sim):
        # Two unowned world objects control each other -> call works, no flag.
        room = sim.room("R")
        core = sim.obj("core", location=room)
        core.db.set("ping", "result = 'pong'")
        term = sim.obj("terminal", location=room)
        res, err = await sim.eval(term, "result = call(get('core'), 'ping')")
        assert err is None
        assert res == "pong"

    async def test_cross_owner_refused_without_public(self, sim):
        room = sim.room("R")
        ada = sim.player("Ada", location=room)
        bob = sim.player("Bob", location=room)
        core = sim.obj("core", location=room)
        core.owner = ada
        core.db.set("ping", "result = 'pong'")
        gadget = sim.obj("gadget", location=room)
        gadget.owner = bob
        res, err = await sim.eval(gadget, "result = call(get('core'), 'ping')")
        assert err is None
        assert res is None

    async def test_public_flag_opens_cross_owner_call(self, sim):
        room = sim.room("R")
        ada = sim.player("Ada", location=room)
        bob = sim.player("Bob", location=room)
        core = sim.obj("core", location=room)
        core.owner = ada
        core.db.set("ping", "result = 'pong'")
        set_attr_flags(core, "ping", ["public"])
        gadget = sim.obj("gadget", location=room)
        gadget.owner = bob
        res, err = await sim.eval(gadget, "result = call(get('core'), 'ping')")
        assert err is None
        assert res == "pong"

    async def test_protected_attr_is_not_callable(self, sim):
        room = sim.room("R")
        core = sim.obj("core", location=room)
        core.db.set("password", "result = 'leak'")
        term = sim.obj("terminal", location=room)
        res, err = await sim.eval(term, "result = call(get('core'), 'password')")
        assert err is None
        assert res is None


class TestPublicIsNotEvalAttr:

    async def test_secret_public_is_an_opaque_method(self, sim):
        # secret+public: callable AS the object, but NOT eval_attr-able by a
        # non-controller (eval_attr is gated by READ, which secret blocks).
        room = sim.room("R")
        ada = sim.player("Ada", location=room)
        bob = sim.player("Bob", location=room)
        core = sim.obj("core", location=room)
        core.owner = ada
        core.db.set("svc", "result = 'served'")
        set_attr_flags(core, "svc", ["secret", "public"])
        gadget = sim.obj("gadget", location=room)
        gadget.owner = bob

        res_call, err1 = await sim.eval(gadget, "result = call(get('core'), 'svc')")
        assert err1 is None and res_call == "served"

        res_eval, err2 = await sim.eval(
            gadget, "result = eval_attr(get('core'), 'svc')")
        assert err2 is None and res_eval is None
