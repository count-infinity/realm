"""
Tutorial-feedback fixes: @dig dup-exit guard, @behavior comma parse,
@eval, @foreach, quell, @detail/remove, exit prefix, @behavior/set,
@rolls, hidden-object search.
"""

from __future__ import annotations

import pytest

from realm.core.objects import GameObject
from realm.core.propagation import reset_engine
from tests.test_olc import MockPersistence, make_context, use_persistence


@pytest.fixture(autouse=True)
def fresh():
    reset_engine()
    yield
    reset_engine()


@pytest.mark.asyncio
class TestDigDuplicateExit:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_second_up_exit_refused(self):
        from realm.commands.olc.create import cmd_dig

        room = GameObject("Hub", tags=["room"])
        bea = GameObject("Bea", tags=["player", "builder"], location=room)
        self.persistence.add(room)

        await cmd_dig(make_context(bea, args="Attic = up, down",
                                   left_args="Attic", right_args="up, down"))
        ups = [o for o in room.contents if o.has_tag('exit') and o.name == 'up']
        assert len(ups) == 1

        ctx = make_context(bea, args="Loft = up, down",
                           left_args="Loft", right_args="up, down")
        await cmd_dig(ctx)
        ups = [o for o in room.contents if o.has_tag('exit') and o.name == 'up']
        assert len(ups) == 1  # NOT two
        assert any("already exists" in m for m in ctx.session.messages)


@pytest.mark.asyncio
class TestBehaviorCommaParse:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_comma_in_taunt_value(self):
        from realm.commands.olc.softcode import cmd_behavior

        room = GameObject("Lair", tags=["room"])
        bea = GameObject("Bea", tags=["player", "builder"], location=room)
        guard = GameObject("guard", tags=["npc"], location=room, owner=bea)

        ctx = make_context(
            bea, left_args="guard",
            right_args="aggressive, taunt:You should not have climbed, little one")
        await cmd_behavior(ctx)
        b = guard.get_behaviors()[0]
        assert b.get_param("taunt") == "You should not have climbed, little one"

    async def test_behavior_set_edits_interval(self):
        from realm.behaviors.ticker import ScriptTickerBehavior
        from realm.commands.olc.softcode import cmd_behavior

        room = GameObject("Lair", tags=["room"])
        bea = GameObject("Bea", tags=["player", "builder"], location=room)
        parrot = GameObject("parrot", location=room, owner=bea)
        parrot.add_behavior(ScriptTickerBehavior(interval=8))

        ctx = make_context(bea, left_args="parrot",
                           right_args="script_ticker, interval:2", switches=["set"])
        await cmd_behavior(ctx)
        assert parrot.get_behaviors()[0].get_param("interval") == 2


@pytest.mark.asyncio
class TestEvalForeach:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)
        from realm.persistence.manager import set_active_manager
        set_active_manager(self.persistence)

    def teardown_method(self):
        from realm.persistence.manager import set_active_manager
        set_active_manager(None)

    async def test_eval_reports_result(self):
        from realm.commands.olc.debug import cmd_eval
        from realm.scripting.engine import ScriptEngine, set_script_engine

        room = GameObject("Study", tags=["room"])
        bea = GameObject("Bea", tags=["player", "builder"], location=room)
        set_script_engine(ScriptEngine(persistence=self.persistence))
        try:
            ctx = make_context(bea, args="result = 2 + 40")
            await cmd_eval(ctx)
            assert any("42" in m for m in ctx.session.messages)
        finally:
            set_script_engine(None)

    async def test_foreach_runs_per_match(self):
        from realm.commands.olc.debug import cmd_foreach

        room = GameObject("Cave", tags=["room"])
        bea = GameObject("Bea", tags=["player", "builder"], location=room)
        rats = [GameObject(f"rat{i}", tags=["npc", "rat"], location=room, owner=bea)
                for i in range(3)]
        for r in rats:
            self.persistence.add(r)

        calls = []

        class RecDispatcher:
            persistence = self.persistence

            async def dispatch(self, session, line):
                calls.append(line)

        ctx = make_context(bea, left_args="tag:rat", right_args="@tag %o = halt")
        ctx.dispatcher = RecDispatcher()
        await cmd_foreach(ctx)
        assert len(calls) == 3
        assert all(c.startswith("@tag #") and c.endswith("= halt") for c in calls)


@pytest.mark.asyncio
class TestQuell:

    async def test_quell_drops_to_mortal(self):
        from realm.commands.olc.debug import cmd_quell
        from realm.permissions.locks import controls

        room = GameObject("Vault", tags=["room"])
        god = GameObject("Founder", tags=["player", "god"], location=room)
        prop = GameObject("world prop")  # unowned; god controls it normally
        assert controls(god, prop) is True

        ctx = make_context(god)
        ctx.command_name = "quell"
        await cmd_quell(ctx)
        assert god.has_tag("quelled")
        assert controls(god, prop) is False  # now a mortal

        ctx2 = make_context(god)
        ctx2.command_name = "unquell"
        await cmd_quell(ctx2)
        assert not god.has_tag("quelled")
        assert controls(god, prop) is True


@pytest.mark.asyncio
class TestDetailRemove:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_remove_one_by_index(self):
        from realm.commands.olc.modify import cmd_detail

        room = GameObject("Cellar", tags=["room"])
        bea = GameObject("Bea", tags=["player", "builder"], location=room)
        room.db.desc_extras = [["", "first"], ["", "second"], ["", "third"]]

        ctx = make_context(bea, left_args="here", right_args="2",
                           switches=["remove"])
        await cmd_detail(ctx)
        assert room.db.get("desc_extras") == [["", "first"], ["", "third"]]


class TestExitPrefix:

    def test_prefix_matches_exit(self):
        from realm.server.dispatcher import CommandDispatcher

        room = GameObject("Steps", tags=["room"])
        GameObject("trapdoor", tags=["exit"], location=room)
        GameObject("hatch", tags=["exit"], location=room)
        d = CommandDispatcher()
        assert d._find_exit(room, "trapd").name == "trapdoor"
        assert d._find_exit(room, "trapdoor").name == "trapdoor"
        assert d._find_exit(room, "h").name == "hatch"


class TestRollVisibility:

    def test_show_rolls_echoes(self):
        from realm.core.checks import check, set_check_resolver

        seen = []
        bob = GameObject("Bob", tags=["player"])
        bob.db.dexterity = 12
        bob.db.show_rolls = True
        bob.set_msg_handler(seen.append)
        set_check_resolver(None)
        try:
            check(bob, "stealth")
        finally:
            set_check_resolver(None)
        assert any("roll stealth:" in m for m in seen)


@pytest.mark.asyncio
class TestHiddenObjectSearch:

    def setup_method(self):
        self.persistence = MockPersistence()
        use_persistence(self.persistence)

    async def test_concealed_object_found_by_flat_check(self):
        from realm.commands.builtin.manipulation import cmd_search
        from realm.core.checks import CheckResult, set_check_resolver

        room = GameObject("Steps", tags=["room"])
        bob = GameObject("Bob", tags=["player"], location=room)
        key = GameObject("tide-worn key", tags=["thing", "hidden"], location=room)

        # Force success: a concealed OBJECT uses a flat observation check,
        # not a stealth contest against a statless item.
        set_check_resolver(lambda o, s, m: CheckResult(True, 3, 8, 11, s))
        try:
            ctx = make_context(bob)
            await cmd_search(ctx)
        finally:
            set_check_resolver(None)
        assert not key.has_tag("hidden")
        assert any("tide-worn key" in m for m in ctx.session.messages)
