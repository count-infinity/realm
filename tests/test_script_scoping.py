"""
Scripts see their own variables from every nested scope.

Scripts used to `exec` with separate globals/locals dicts, which makes code
behave like a *class body*: assignments land in locals, but every nested
scope compiles free names to LOAD_GLOBAL and cannot see them. The damage:

- `n = {...}; sorted(x, key=lambda k: n[k])` raised NameError on a name
  defined one statement earlier — on EVERY Python version.
- List comprehensions behaved differently across versions: broken on 3.11,
  working on 3.12+ (PEP 709 inlines them), so the test suite (3.13) hid a
  real break for anyone on the declared floor.

Sharing one namespace makes a script behave like module scope: uniform
across versions, and lambdas/genexprs can read what the script computed.
"""

from __future__ import annotations

import pytest

from realm.scripting.sandbox import ScriptContext, ScriptSandbox


@pytest.fixture
def run():
    sb, ctx = ScriptSandbox(), ScriptContext()

    def _run(code: str):
        result, _ = sb.execute(code, ctx)
        return result

    return _run


class TestNestedScopesSeeScriptLocals:
    """The regression this exists to prevent."""

    def test_list_comprehension(self, run):
        assert run("n = {'a': 2}; result = [n[k] for k in ['a']]") == [2]

    def test_set_comprehension(self, run):
        assert run("n = {'a': 2}; result = list({n[k] for k in ['a']})") == [2]

    def test_dict_comprehension(self, run):
        assert run("n = {'a': 2}; result = {k: n[k] for k in ['a']}") == {'a': 2}

    def test_generator_expression(self, run):
        """Genexprs cannot be inlined by PEP 709 — they were broken on every
        version, not just 3.11."""
        assert run("n = {'a': 2}; result = list(n[k] for k in ['a'])") == [2]

    def test_lambda(self, run):
        assert run("n = {'a': 2}; f = lambda k: n[k]; result = f('a')") == 2

    def test_sorted_with_key_lambda(self, run):
        """The idiom that made the whole thing worth fixing: `key=lambda`
        over a table the script just built (bookshelves, leaderboards,
        poker hands, race odds)."""
        assert run(
            "n = {'b': 1, 'a': 2}; result = sorted(n, key=lambda k: n[k])"
        ) == ['b', 'a']

    def test_all_over_a_generator(self, run):
        assert run("n = {'a': 2}; result = all(n[k] > 1 for k in ['a'])") is True

    def test_nested_comprehension_reading_a_local(self, run):
        assert run(
            "rows = [[1, 2], [3]]; n = 1; "
            "result = [x for row in rows for x in row if x > n]"
        ) == [2, 3]


class TestBackwardCompatible:
    """The workarounds the tutorials teach must keep working — they are
    harmless now, just no longer necessary."""

    def test_smuggle_through_first_for_clause(self, run):
        assert run("n = {'a': 2}; result = [d[k] for d in [n] for k in ['a']]") == [2]

    def test_self_passing_lambda(self, run):
        assert run("w = lambda w, o: o * 2; result = w(w, 3)") == 6

    def test_bound_method_as_key(self, run):
        assert run("n = {'b': 1, 'a': 2}; result = sorted(n, key=n.get)") == ['b', 'a']


class TestNamespaceHygiene:
    def test_result_is_returned(self, run):
        assert run("result = 41 + 1") == 42

    def test_absent_result_is_none(self, run):
        assert run("x = 1") is None

    def test_scripts_do_not_leak_into_each_other(self):
        """safe_globals is built per execution — one script's variables must
        not be visible to the next."""
        sb, ctx = ScriptSandbox(), ScriptContext()
        sb.execute("secret = 'hunter2'", ctx)
        with pytest.raises(Exception):
            sb.execute("result = secret", ctx)

    def test_injected_functions_still_reachable(self, run):
        assert run("result = len([1, 2, 3])") == 3
