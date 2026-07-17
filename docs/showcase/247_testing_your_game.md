# 247. Testing your game

> Checklist item 247 — [now] — *the realm.testing Simulator: drive raw input, assert output, virtual-clock waits*

**What you'll build:** an automated test for softcode you wrote — the same
harness these showcase tutorials use to prove themselves. You'll spin up
an in-process world, type commands into it as a player, and assert on
exactly the text that player would have seen.

**Concepts:** `realm.testing.Simulator`, building a world in code
(`room`/`obj`/`player`), driving it (`do`, `eval`), observing it
(`seen`), and the deterministic **virtual clock** for `wait()` timers.

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

Run it exactly like the engine's own suite:

```text
pytest tests/test_my_game.py
```

## Try it

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
