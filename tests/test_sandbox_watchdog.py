"""Call-free infinite loops are interrupted.

The per-call budget (`max_function_calls`, `max_time_ms`) is enforced
inside `_wrap_function`, so it only fires when a script *calls* something.
A script that spins without calling anything — `while True: pass`, or a
comprehension/generator over a huge range — was never checked and pinned
its worker thread. That is the one hole in "softcode is safe to hand to
adversaries" (the item-250 thesis).

A line-level `sys.settrace` watchdog catches it, installed ONLY for
scripts that can loop, so loop-free scripts (guard chains, inline reads)
pay nothing. `sys` is not in the sandbox namespace, so a script cannot
clear its own trace.
"""

from __future__ import annotations

import sys
import time

import pytest

from realm.scripting.sandbox import (
    ScriptContext,
    ScriptError,
    ScriptLimits,
    ScriptSandbox,
    ScriptTimeout,
)


def _run(code: str, ms: int = 300):
    sb = ScriptSandbox(limits=ScriptLimits(max_time_ms=ms))
    return sb.execute(code, ScriptContext())


class TestRunawayLoopsAreCaught:
    def test_bare_infinite_loop(self):
        t = time.time()
        with pytest.raises(ScriptTimeout):
            _run("while True:\n    x = 1")
        assert time.time() - t < 2.0, "did not interrupt promptly"

    def test_for_over_a_huge_range(self):
        with pytest.raises(ScriptTimeout):
            _run("t = 0\nfor i in range(10**12):\n    t = i")

    def test_generator_over_a_huge_range(self):
        """The subtle one: the spin is inside a generator frame, which the
        line tracer must also see."""
        with pytest.raises(ScriptTimeout):
            _run("result = sum(i for i in range(10**12))")

    def test_nested_call_free_loops(self):
        with pytest.raises(ScriptTimeout):
            _run("while True:\n    for i in range(10):\n        x = i")


class TestWellBehavedScriptsSurvive:
    def test_normal_comprehension(self):
        r, _ = _run("result = sum([i for i in range(500)])")
        assert r == sum(range(500))

    def test_finite_loop(self):
        r, _ = _run("t = 0\nfor i in range(1000):\n    t = t + i\nresult = t")
        assert r == sum(range(1000))

    def test_loop_free_script(self):
        r, _ = _run("result = 2 + 2")
        assert r == 4


class TestTraceHygiene:
    def test_trace_is_restored_after_a_loop_script(self):
        before = sys.gettrace()
        _run("t = 0\nfor i in range(10):\n    t = i")
        assert sys.gettrace() is before

    def test_trace_is_restored_even_when_a_loop_script_times_out(self):
        before = sys.gettrace()
        with pytest.raises(ScriptTimeout):
            _run("while True:\n    x = 1")
        assert sys.gettrace() is before

    def test_loop_free_script_does_not_install_a_tracer(self):
        """A loop-free script must not touch the trace at all — this is
        what keeps the inline-`[[...]]` hot path free of overhead."""
        def sentinel(frame, event, arg):
            return sentinel

        sys.settrace(sentinel)
        try:
            _run("result = 1 + 1")           # no loop -> no watchdog
            # If the sandbox had installed (and restored) its own tracer it
            # would have restored *sentinel*; if it left the trace alone,
            # sentinel is still here either way — so assert it never even
            # swapped by checking the classifier said "no loop".
            assert ScriptSandbox._has_loop("result = 1 + 1") is False
            assert sys.gettrace() is sentinel
        finally:
            sys.settrace(None)

    def test_a_script_cannot_clear_its_own_trace(self):
        """`sys` is not in the sandbox, so a loop cannot disable the
        watchdog and then spin freely."""
        with pytest.raises(ScriptError):
            _run("import sys\nsys.settrace(None)\nwhile True:\n    x = 1")


class TestHasLoopClassifier:
    @pytest.mark.parametrize("code", [
        "while True: pass",
        "for i in range(3): pass",
        "x = [i for i in range(3)]",
        "x = {i for i in range(3)}",
        "x = {i: i for i in range(3)}",
        "x = sum(i for i in range(3))",
    ])
    def test_loops_are_detected(self, code):
        assert ScriptSandbox._has_loop(code) is True

    @pytest.mark.parametrize("code", [
        "result = 2 + 2",
        "result = V('x', 0)",
        "say('hello')",
        "x = 1 if cond else 2",
    ])
    def test_loop_free_is_detected(self, code):
        assert ScriptSandbox._has_loop(code) is False
