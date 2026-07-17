# 247. Testing your game

> Checklist item 247 — [now] — *the realm.testing Simulator: drive raw input, assert output, virtual-clock waits*

**What you'll build:** an automated test for softcode you wrote — the same
harness these showcase tutorials use to prove themselves. You'll spin up
an in-process world, type commands into it as a player, and assert on
exactly the text that player would have seen.

**Concepts:** `realm.testing.Simulator`, building a world in code
(`room`/`obj`/`player`), driving it (`do`, `eval`), observing it
(`seen`), the deterministic **virtual clock** for `wait()` timers, and
**reading the build straight out of the tutorial** so docs and tests
cannot drift apart.

## How it works

This is the one tutorial whose "build" is Python, because testing *is*
Python — but the thing under test is still your in-game softcode, driven
through the **real** dispatcher. `realm.testing.Simulator` wires the same
components a live server does — in-memory store, propagation engine,
softcode `ScriptEngine`, command dispatcher — so a command you send goes
down the identical path it would on a live game, and `seen(player)` is
byte-for-byte what that player's client would have printed.

Three verbs are the whole API:

- **Build:** `sim.room(name)`, `sim.obj(name, location=…)`,
  `sim.player(name, location=…)` — players get a live session so their
  output is captured.
- **Drive:** `await sim.do(player, "get sword")` runs a player command;
  `await sim.eval(obj, "pemit(...)", enactor=…)` runs raw softcode *as* an
  object (the `@eval` path).
- **Observe:** `sim.seen(player)` drains and returns that player's
  messages since you last looked.

The Simulator runs on a **virtual clock**: `wait()` timers don't fire on
wall-clock time, they wait for your test to pump `await
sim.engine.tick_waits()`. That makes time deterministic — no `sleep`, no
flakiness — and it's how you test fuses, delays, and chains.

## Build it

Here's a tiny gadget worth testing — a fortune cookie with one verb, and
a relay drone that answers on a delay:

```text
@create fortune cookie
drop fortune cookie
@set fortune cookie/cmd_crack = $crack cookie:pemit(enactor, 'Your fortune: ' + extract('travel fortune caution', rand(1, 3)) + '.')
@create relay drone
drop relay drone
@set relay drone/cmd_ping = $ping drone:wait(0, 'trigger me/reply')
@set relay drone/reply = remit(here, 'The drone pings back.')
```

Now the test that proves it. Drop this in `tests/test_my_game.py`:

```python
import pytest
from realm.testing import Simulator


@pytest.mark.asyncio
async def test_fortune_cookie_and_relay():
    sim = Simulator()
    try:
        lounge = sim.room("Crew Lounge")
        bela = sim.player("Bela", location=lounge)
        bela.add_tag("builder")
        alice = sim.player("Alice", location=lounge)

        # Build the gadget by typing the tutorial's commands.
        await sim.do(bela, "@create fortune cookie")
        await sim.do(bela, "drop fortune cookie")
        await sim.do(bela, "@set fortune cookie/cmd_crack = $crack cookie:"
                           "pemit(enactor, 'Your fortune: ' + "
                           "extract('travel fortune caution', rand(1, 3)) + '.')")

        # Drive it as a player and assert on what she saw.
        sim.seen(alice)                       # clear the buffer
        await sim.do(alice, "crack cookie")
        line = "\n".join(sim.seen(alice))
        assert "Your fortune:" in line
        assert any(w in line for w in ("travel", "fortune", "caution"))

        # A delayed action: nothing until we pump the virtual clock.
        await sim.do(bela, "@create relay drone")
        await sim.do(bela, "drop relay drone")
        await sim.do(bela, "@set relay drone/cmd_ping = $ping drone:"
                           "wait(0, 'trigger me/reply')")
        await sim.do(bela, "@set relay drone/reply = "
                           "remit(here, 'The drone pings back.')")

        sim.seen(alice)
        await sim.do(alice, "ping drone")
        assert sim.seen(alice) == []          # the wait hasn't fired yet
        await sim.engine.tick_waits()         # advance the virtual clock
        assert "The drone pings back." in "\n".join(sim.seen(alice))
    finally:
        sim.close()
```

### Keeping the doc and the test in step

That test works, but notice what it just did: it **copied** the build
commands out of the tutorial into Python string literals. Now the same
commands live in two places, and the day you improve the build in the doc,
the test happily keeps proving the *old* one. A "do these match?" test that
greps the doc for each literal is the obvious patch, and it is weaker than
it looks — a line truncated to a prefix still passes a substring check, and
a rewrite that quietly *drops* tests leaves nothing to compare in the first
place. It detects drift at best; it cannot prevent it.

The stronger move is to delete the copy. Read the build straight out of the
tutorial and run **what the doc says**:

```python
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs" / "showcase"


def build_lines(doc_name: str) -> list[str]:
    """Every command line in the tutorial's "Build it" fenced blocks."""
    body = (DOCS / doc_name).read_text()
    match = re.search(r"^## Build it$(.*?)^## ", body, re.M | re.S)
    assert match, f"{doc_name}: no Build it section"
    lines = []
    for block in re.findall(r"```text\n(.*?)```", match.group(1), re.S):
        lines.extend(line for line in block.splitlines() if line.strip())
    assert lines, f"{doc_name}: empty Build it"
    return lines


async def build(sim, builder, doc_name):
    for line in build_lines(doc_name):
        await sim.do(builder, line)
```

Then the test above opens with `await build(sim, bela, "247_testing_your_game.md")`
and keeps its assertions exactly as they are — only the *source* of the
build lines changed. Now a doc whose build is broken breaks the suite, and
a doc whose build improves is tested in its improved form. Drift stops
being something you detect and becomes something that cannot happen.

This is not a hypothetical: every suite behind this showcase
(`tests/showcase/`) is written this way, including the one that tests this
very tutorial. Your prose and your proof read from one source.

## Try it

Run it exactly like the engine's own suite:

```text
pytest tests/test_my_game.py
```

The pattern generalises to anything you can express in-game:

- **Wards and locks:** build the gadget, `await sim.do(intruder, "use
  cube")`, assert the ward's refusal is what they saw.
- **State over time:** call a verb twice, assert an attribute climbed —
  `assert obj.db.get("visits") == 2`.
- **Raw softcode:** skip the verb and test a function directly —
  `await sim.eval(obj, "result = extract('a b c', 2)")` returns
  `(result, error)`.

Because `seen()` is the real output queue, a passing test means a real
player would really see that line — the tutorials in this arc are nothing
but this harness, pointed at each build.

## Going further

- **Fixtures:** wrap `Simulator()` in a pytest fixture that `yield`s the
  world and calls `sim.close()` in a `finally` — every test starts clean.
- **Virtual-clock chains:** a `wait()` that schedules another `wait()`
  advances one `tick_waits()` at a time, so you can assert the state
  *between* steps of a relay.
- **Two players, one room:** assert that a `remit` reached the bystander
  and a `pemit` did *not* — the private/public boundary, tested.
- **Drive the sandbox limits:** replay item [250](250_player_scripting.md)'s
  attacks (import, marathon, flood) and assert the walls hold — a
  security regression test you can keep.
