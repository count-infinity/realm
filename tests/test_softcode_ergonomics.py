"""
Tests for the softcode-ergonomics batch (BACKLOG 2026-07-17):

- V(name, default)       — read an attr off `me`
- incr(name, by) / decr  — bump a numeric attr on `me`, return the new value
- per-room db.dark_msg    — override the default darkness line
- confirms %#-substitution and f-strings already work in the sandbox

Direct ScriptFunctions tests exercise the methods; sandbox tests prove the
names are injected into the script namespace; the readonly test proves `V`
(read-only) is usable in check-pass wards while `incr`/`decr` (mutators)
are not.
"""

from __future__ import annotations

import pytest

from realm.core.objects import GameObject
from realm.scripting.functions import ScriptFunctions
from realm.scripting.sandbox import ScriptContext, ScriptSandbox

from tests.test_olc import MockPersistence


def _funcs(executor: GameObject, persistence: MockPersistence) -> ScriptFunctions:
    return ScriptFunctions(
        enactor=executor,
        executor=executor,
        location=executor.location,
        persistence=persistence,
    )


class TestVShorthand:
    def test_reads_own_attr_with_default(self):
        obj = GameObject("Gadget")
        obj.db.set('cost', 25)
        p = MockPersistence()
        p.add(obj)
        fn = _funcs(obj, p)
        assert fn.V('cost', 10) == 25
        assert fn.V('missing', 10) == 10
        # V is exactly get_attr(me, ...)
        assert fn.V('cost') == fn.get_attr(obj, 'cost')

    def test_available_in_sandbox_namespace(self):
        obj = GameObject("Gadget")
        obj.db.set('cost', 7)
        p = MockPersistence()
        p.add(obj)
        fn = _funcs(obj, p)
        ctx = ScriptContext(enactor=obj, executor=obj, location=obj.location)
        result, _ = ScriptSandbox().execute(
            "result = V('cost', 99)", ctx, functions=fn.to_dict()
        )
        assert result == 7

    def test_v_is_in_readonly_ward_namespace(self):
        obj = GameObject("Gadget")
        p = MockPersistence()
        p.add(obj)
        fn = _funcs(obj, p)
        assert 'V' in fn.readonly_dict()
        # mutators must NOT leak into the check-pass namespace
        assert 'incr' not in fn.readonly_dict()
        assert 'decr' not in fn.readonly_dict()


class TestIncrDecr:
    def test_incr_from_unset_starts_at_zero(self):
        obj = GameObject("Counter")
        p = MockPersistence()
        p.add(obj)
        fn = _funcs(obj, p)
        assert fn.incr('visits') == 1
        assert fn.incr('visits') == 2
        assert obj.db.get('visits') == 2

    def test_incr_by_amount_and_decr(self):
        obj = GameObject("Counter")
        p = MockPersistence()
        p.add(obj)
        fn = _funcs(obj, p)
        assert fn.incr('charge', 5) == 5
        assert fn.incr('charge', 5) == 10
        assert fn.decr('charge', 3) == 7
        assert fn.decr('charge') == 6

    def test_non_numeric_current_falls_back_to_default(self):
        obj = GameObject("Counter")
        obj.db.set('tally', "oops")
        p = MockPersistence()
        p.add(obj)
        fn = _funcs(obj, p)
        assert fn.incr('tally') == 1
        obj.db.set('tally', "oops")
        assert fn.incr('tally', default=10) == 11

    def test_default_for_an_unset_attribute(self):
        """The trap four sweep agents caught independently: counters that
        read with a default of 1 (a lot number, a fire stage, a pending
        count). incr() assuming 0 silently produced 1 where the script
        meant 2 — and the tutorials' builds pre-set the attr, so tests
        wouldn't catch it; only a reader copying the build would."""
        obj = GameObject("Auction")
        p = MockPersistence()
        p.add(obj)
        fn = _funcs(obj, p)
        # 089's next_lot: reads with default 1, so the first bump gives 2.
        assert fn.incr('next_lot', default=1) == 2
        assert obj.db.get('next_lot') == 2
        # ...versus the old hardcoded-0 behaviour, still the default.
        assert fn.incr('other') == 1

    def test_decr_threads_its_default(self):
        obj = GameObject("Diver")
        p = MockPersistence()
        p.add(obj)
        fn = _funcs(obj, p)
        # 039's breath meter: an unset meter starts full, then drains.
        assert fn.decr('breath', default=3) == 2

    def test_bool_is_not_treated_as_a_number(self):
        obj = GameObject("Counter")
        obj.db.set('flag', True)
        p = MockPersistence()
        p.add(obj)
        fn = _funcs(obj, p)
        assert fn.incr('flag', default=5) == 6

    def test_incr_returns_none_when_write_refused(self):
        # Executor does not control a foreign player -> V/incr target `me`,
        # but a `safe`-flagged attr is refused even on self.
        obj = GameObject("Counter")
        obj.db.set('locked_stat', 3)
        p = MockPersistence()
        p.add(obj)
        # Flag the attribute non-writable.
        obj.db.set('attr_flags', {'locked_stat': ['safe']})
        fn = _funcs(obj, p)
        assert fn.incr('locked_stat') is None
        assert obj.db.get('locked_stat') == 3  # unchanged

    def test_incr_in_sandbox_namespace(self):
        obj = GameObject("Counter")
        p = MockPersistence()
        p.add(obj)
        fn = _funcs(obj, p)
        ctx = ScriptContext(enactor=obj, executor=obj, location=obj.location)
        result, _ = ScriptSandbox().execute(
            "result = incr('n', 4)", ctx, functions=fn.to_dict()
        )
        assert result == 4
        assert obj.db.get('n') == 4


class TestDarkMessageOverride:
    def test_default_when_unset(self, monkeypatch):
        import realm.core.perception as perception
        monkeypatch.setattr(perception, 'can_see_room', lambda v, r: False)
        from realm.core.render import render_room
        room = GameObject("Cave", tags=['room'])
        assert "pitch black" in render_room(room, None)

    def test_custom_dark_msg_used(self, monkeypatch):
        import realm.core.perception as perception
        monkeypatch.setattr(perception, 'can_see_room', lambda v, r: False)
        from realm.core.render import render_room
        room = GameObject("Mine", tags=['room'])
        room.db.set('dark_msg', "The mine shaft swallows all light.")
        assert render_room(room, None) == "The mine shaft swallows all light."


class TestInterpreterRecursionLimit:
    """The limit is a process-wide game setting, applied once at boot —
    not a per-script knob. Bad values must raise at boot, not mid-render."""

    def teardown_method(self):
        import sys
        sys.setrecursionlimit(self._old) if hasattr(self, '_old') else None

    def setup_method(self):
        import sys
        self._old = sys.getrecursionlimit()

    def test_sets_the_limit(self):
        import sys
        from realm.scripting.sandbox import set_interpreter_recursion_limit
        set_interpreter_recursion_limit(1234)
        assert sys.getrecursionlimit() == 1234

    def test_default_matches_cpython_default(self):
        import sys
        from realm.scripting.sandbox import (
            DEFAULT_RECURSION_LIMIT,
            set_interpreter_recursion_limit,
        )
        set_interpreter_recursion_limit()
        assert sys.getrecursionlimit() == DEFAULT_RECURSION_LIMIT == 1000

    @pytest.mark.parametrize('bad', [10, 99, 0, -5, 100_001])
    def test_rejects_out_of_range(self, bad):
        from realm.scripting.sandbox import set_interpreter_recursion_limit
        with pytest.raises(ValueError, match="process-wide|between"):
            set_interpreter_recursion_limit(bad)

    @pytest.mark.parametrize('bad', ["1000", 1000.5, None, True])
    def test_rejects_non_int(self, bad):
        from realm.scripting.sandbox import set_interpreter_recursion_limit
        with pytest.raises(ValueError):
            set_interpreter_recursion_limit(bad)

    def test_floor_protects_the_engines_own_stack(self):
        """The old code effectively set 60 — below the engine's own depth.
        The floor exists so that can never be configured again."""
        from realm.scripting.sandbox import (
            MIN_RECURSION_LIMIT,
            set_interpreter_recursion_limit,
        )
        assert MIN_RECURSION_LIMIT > 60
        with pytest.raises(ValueError):
            set_interpreter_recursion_limit(60)


class TestAlreadyWorks:
    """Confirm the two items that turned out to already work, so the docs
    claims are test-anchored."""

    def test_hash_hash_enactor_substitution(self):
        actor = GameObject("Alice")
        ctx = ScriptContext(enactor=actor, executor=actor)
        # %# expands to the enactor id before compile.
        result, _ = ScriptSandbox().execute("result = '%#'", ctx)
        assert result == actor.id

    def test_fstrings_run_in_sandbox(self):
        obj = GameObject("Gadget")
        obj.db.set('cost', 12)
        p = MockPersistence()
        p.add(obj)
        fn = _funcs(obj, p)
        ctx = ScriptContext(enactor=obj, executor=obj, location=obj.location)
        result, _ = ScriptSandbox().execute(
            "result = f'costs {V(\"cost\")} credits'",
            ctx, functions=fn.to_dict(),
        )
        assert result == "costs 12 credits"
