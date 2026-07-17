"""
A failing ``on_check`` ward must never silently fail OPEN.

`on_check` is the veto surface: cursed items refusing removal, landmines
refusing pickup, clearance gates, capacity limits, escrow, the jail door.
Before this, ANY error in a ward — a typo'd name, a missing paren, a stray
ZeroDivision — was logged at warning level and the action proceeded. "The
ward is broken" and "the ward allowed it" were indistinguishable to the
world, and the only trace was a log line nobody reads.

The rule now: a ward that *could have denied* fails CLOSED. A ward that
provably could not (it only mod()s or set_adata()s — armour, resistance)
fails open, because an armour calculation that raises must not veto the
swing. Either way the failure is loud.

_run_check's own docstring already stated this invariant ("a ward must not
silently *fail open*") — it just wasn't true of the error path.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from realm.scripting.engine import ScriptEngine
from realm.testing import Simulator


@pytest.fixture
def world():
    sim = Simulator()
    room = sim.room("Vault")
    alice = sim.player("Alice", location=room)
    try:
        yield SimpleNamespace(sim=sim, room=room, alice=alice)
    finally:
        sim.close()


async def _try_take(w, ward: str) -> bool:
    """Put `ward` on a relic, try to take it, return whether it was taken."""
    relic = w.sim.obj("relic", location=w.room)
    relic.db.set('on_check', ward)
    await w.sim.do(w.alice, "get relic")
    return any(o.name == "relic" for o in w.alice.contents)


@pytest.mark.asyncio
class TestDenyCapableWardsFailClosed:
    """If it could have said no, an error means no."""

    async def test_working_ward_blocks(self, world):
        assert await _try_take(world, "block('the relic is warded')") is False

    async def test_misspelled_block_fails_closed(self, world):
        """The case that matters most: `blok(...)` is the likeliest ward bug
        there is, and the AST cannot see it as a block() call — it's just an
        unknown callable. Unknown intent must not mean 'allow'."""
        assert await _try_take(world, "blok('the relic is warded')") is False

    async def test_wrong_namespace_fails_closed(self, world):
        """incr() is (correctly) absent from the ward namespace — but that
        guardrail plus fail-open equalled a hole, not a guardrail."""
        assert await _try_take(world, "incr('touches'); block('warded')") is False

    async def test_runtime_error_fails_closed(self, world):
        assert await _try_take(world, "x = 1/0; block('warded')") is False

    async def test_syntax_error_fails_closed(self, world):
        """@set stores an unparseable ward without complaint, so this ward
        never worked from the moment it was typed."""
        assert await _try_take(world, "block('warded'") is False

    async def test_conditional_block_that_errors_fails_closed(self, world):
        assert await _try_take(
            world, "block('x') if V('nope') + 1 else None") is False

    async def test_block_reason_reaches_the_actor(self, world):
        await _try_take(world, "blok('warded')")
        assert any("malfunctioning" in line for line in world.sim.seen(world.alice))


@pytest.mark.asyncio
class TestAdvisoryWardsStayOpen:
    """A mod()-only ward cannot open a hole by failing, so failing must not
    veto — armour that raises should not stop the swing."""

    async def test_mod_only_ward_that_errors_allows(self, world):
        assert await _try_take(world, "mod(-get_attr(me, 'nope') - 1)") is True

    async def test_mod_only_using_safe_builtins_allows(self, world):
        assert await _try_take(world, "mod(-int(str(V('armor', 2))))") is True

    async def test_healthy_world_unaffected(self, world):
        assert await _try_take(world, "") is True


@pytest.mark.asyncio
class TestSetWarnsOnDeadScripts:
    """The other half: @set used to store an unparseable script without a
    word, so a ward could be dead from the moment it was typed and nothing
    ever said so. Warn (don't refuse — placeholders and @import are
    legitimate, and the runtime fails safe now anyway)."""

    async def _set(self, w, cmd: str) -> list[str]:
        b = w.sim.player("Bilda", location=w.room)
        b.add_tag('builder')
        b.add_tag('admin')
        w.sim.obj("relic", location=w.room)
        await w.sim.do(b, cmd)
        return w.sim.seen(b)

    async def test_warns_on_broken_ward(self, world):
        out = await self._set(world, "@set relic/on_check = block('warded'")
        assert any("will not run" in line for line in out)

    async def test_warns_on_broken_dollar_command(self, world):
        out = await self._set(
            world, "@set relic/cmd_x = $poke:pemit(enactor, 'hi'")
        assert any("will not run" in line for line in out)

    async def test_warns_on_broken_event_hook(self, world):
        out = await self._set(world, "@set relic/ON_GET = say('mine'")
        assert any("will not run" in line for line in out)

    async def test_silent_on_good_script(self, world):
        out = await self._set(world, "@set relic/on_check = block('warded')")
        assert not any("will not run" in line for line in out)

    async def test_silent_on_data_attributes(self, world):
        """A desc with an unbalanced paren is prose, not code."""
        out = await self._set(world, "@set relic/desc = A relic (cracked")
        assert not any("will not run" in line for line in out)


class TestScriptCodeOf:
    """Which attributes are scripts — recognised the way the engine does."""

    def test_sigil_values_are_scripts(self):
        from realm.scripting.triggers import script_code_of
        assert script_code_of('cmd_x', "$poke:say('hi')") == "say('hi')"
        assert script_code_of('listen_x', "^*gold*:say('hi')") == "say('hi')"

    def test_named_hooks_are_scripts(self):
        from realm.scripting.triggers import script_code_of
        assert script_code_of('on_check', "block('x')") == "block('x')"
        assert script_code_of('ON_GET', "say('x')") == "say('x')"
        assert script_code_of('on_tick', "say('x')") == "say('x')"

    def test_data_attributes_are_not_scripts(self):
        from realm.scripting.triggers import script_code_of
        assert script_code_of('weight', 5) is None
        assert script_code_of('desc', 'A relic (cracked') is None
        assert script_code_of('wants', '[["a", "b"]]') is None


class TestWardCanDeny:
    """The classifier itself. `known` = check namespace + safe builtins."""

    KNOWN = {'block', 'mod', 'set_adata', 'V', 'get_attr', 'adata', 'int', 'str'}

    @pytest.mark.parametrize('code', [
        "block('no')",                       # explicit deny
        "block('x') if cond else None",      # conditional deny
        "blok('no')",                        # typo'd deny -> unknown callable
        "mystery_fn(1)",                     # unknown callable
        "block('warded'",                    # unparseable
        "mod(-2); block('also')",            # mixed
    ])
    def test_guards(self, code):
        assert ScriptEngine._ward_can_deny(code, self.KNOWN) is True

    @pytest.mark.parametrize('code', [
        "mod(-2)",                           # pure advisory
        "mod(-get_attr(me, 'armor'))",       # advisory w/ known calls
        "set_adata('damage', adata('damage', 0) // 2)",
        "mod(-int(str(V('armor', 2))))",     # advisory w/ safe builtins
        "x = 1",                             # no calls at all
    ])
    def test_advisory(self, code):
        assert ScriptEngine._ward_can_deny(code, self.KNOWN) is False
