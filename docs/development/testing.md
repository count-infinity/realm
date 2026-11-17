# Testing

REALM uses pytest with pytest-asyncio for testing.

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_session.py

# Run specific test
pytest tests/test_session.py::test_session_creation
```

## Test Structure

```
tests/                        # 800+ tests, ~2s total
├── test_propagation.py       # the action pipeline
├── test_objects.py / test_tags.py
├── test_dispatcher.py / test_commands.py / test_builtin_commands.py
├── test_scripting.py / test_script_engine.py / test_softcode_builders.py
├── test_combat*.py / test_ranged_combat.py
├── test_behaviors.py / test_disposition.py / test_economy.py / test_party.py
├── test_systems.py           # GameSystem, chargen, auth
├── test_query_zones.py / test_help_and_details.py / test_oob.py
├── test_persistence.py / test_session.py / test_permissions.py
└── test_olc.py / test_infiltration.py / test_spacegame.py
```

Live end-to-end drives (telnet scripts that boot a real server) live
outside the repo during development and verify each feature package;
the tutorial's command sequence is one of them.

## The world a test runs in

Code that needs the store, the propagation engine, the script engine, the
game system or a feature's service asks the running world
(`realm.core.world.get_world()`). The fixtures come from the pytest plugin
`realm.testing.fixtures` (`tests/conftest.py` lists it in `pytest_plugins`,
as a game's own tests do). It makes every test start and end with **no**
world installed, so nothing one test wires can leak into the next. A test
that needs a world takes a fixture:

| Fixture | World |
|---|---|
| `world` | built and installed, no features (the bare kernel) |
| `classic_world` | every built-in feature |
| `classic_world_unscripted` | every built-in feature, scripting off: the test wires its own `ScriptEngine` |
| `configure` | `configure(emote_sigil="@")` changes the bare world's settings |

`@pytest.mark.features("rules", "effects", "social")` on a test or class
makes `world` (and `configure`) a world of exactly those features instead
of a bare one: the way to test one feature's integration with another
(a shop's prices reading `social`'s dispositions) without the whole set.

To hand-wire a service, set it on the world. There is nothing to restore;
the world closes after the test:

```python
def test_rigged_check(world):
    world.services["checks"].resolver = always_succeeds
    world.store = MockPersistence()            # a test double for the store
    world.speech_renderers.append(shout)       # what feature.speech_renderer adds
```

`reconfigure(world, **changes)` (from `realm.testing`) changes a Simulator's
or another fixture's settings (`reconfigure(sim.world, keyid_sigil="$$")`).
A bad value raises `ValueError`, exactly as it would in `config.py`.

With no world installed, pure helpers still work: `setting("MARKUP_MARKER")`
reads the `Settings` default, `find_objects()` finds nothing, and `check()`
uses a neutral 3d6 resolver. Anything that needs the store or the engine
raises `RuntimeError: No world is installed`, which means the test wants
one of the fixtures above.

## Writing Tests

```python
import pytest
from realm.gateway.session import Session, SessionManager

@pytest.mark.asyncio
async def test_session_creation():
    """Test that sessions are created with correct defaults."""
    manager = SessionManager()

    messages = []
    async def mock_writer(msg):
        messages.append(msg)

    session = await manager.create_session(
        protocol="test",
        address="127.0.0.1:1234",
        writer=mock_writer,
    )

    assert session.protocol == "test"
    assert session.address == "127.0.0.1:1234"
```

## Mocking Sessions

```python
from unittest.mock import AsyncMock

# Create a mock session for testing commands
session = AsyncMock(spec=Session)
session.player = mock_player
session.send = AsyncMock()
```

## Integration testing with the Simulator

For "run this and see what a player would see," `realm.testing.Simulator`
wires the *real* engine in-process, with no sockets or database file. It
calls the same `build_world()` the live server calls, so it has the same
commands, propagation observers (softcode, stealth, equipment, combat,
crime), combat manager and game system. `tests/test_world_parity.py`
checks that the two stay alike.

```python
import pytest
from realm.testing import Simulator

@pytest.fixture
def sim():
    s = Simulator()               # defaults to the GURPS system
    try:
        yield s
    finally:
        s.close()                 # closes its world

@pytest.mark.asyncio
async def test_npc_greets(sim):
    room  = sim.room("Cantina")
    zeke  = sim.obj("Zeke", location=room)
    alice = sim.player("Alice", location=room)   # gets a live Session

    # Run softcode AS zeke (the @eval path):
    await sim.eval(zeke, "pemit(enactor, 'Welcome, ' + name(enactor))",
                   enactor=alice)
    assert "Welcome, Alice" in sim.seen(alice)   # what Alice received

    # Or run a real player command through the dispatcher:
    sim.obj("sword", location=room, tags=["thing"])
    await sim.do(alice, "get sword")
    assert "You pick up a sword." in sim.seen(alice)
```

- `sim.room / obj / player` build the world (`player` returns an object
  with a live session reachable via `seen()`).
- `sim.eval(obj, code, enactor=…)` runs softcode as `obj`; returns
  `(result, error)`.
- `await sim.do(player, "command")` runs a real command through the
  dispatcher.
- `sim.seen(player)` drains and returns that player's messages.
- Choose the ruleset with `Simulator(game_system="realm.games.d20.system.D20System")`.
- Configure it the way a game's `config.py` would with
  `Simulator(settings=Settings(command_sigil="!"))`
  (`from realm.config.loader import Settings`).
- Softcode `wait()` runs on a virtual clock: it fires when the test calls
  `sim.engine.waits.tick()`, once it is due on the waits' clock (see
  [Moving time](#moving-time)).
- The world lives in a `MemoryStore` (`sim.store`); `sim.world` is the
  installed `World`.

Because both paths go through the real engine, the transcript is exactly
what happens live — which makes it the natural way to test data-driven
content (a `class_def`, a `skill_def`, a scripted NPC) end-to-end.

## Moving time

Everything in the engine that reads the time for a game reason (an
ability's cooldown, a corpse's lock, a letter's date, the combat beat, a
session's idle time, a clan's vote, hunger, idle training ...) reads it
through its module's `now()`, called through the module. A test never
waits out real time: it replaces the clocks and moves them.

The `clock` fixture (from `realm.testing.fixtures`) replaces every one of
them with one `FakeClock`, stopped at 2027-01-15 08:00 UTC until the test
moves it:

```python
async def test_the_corpse_lock_lifts(clock, sim):
    ...                                   # Pat dies; the corpse is locked
    await sim.do(thief, "get sword from corpse")
    assert sword.location is not thief
    clock.advance(300)                    # CORPSE_LOCK_SECONDS
    await sim.do(thief, "get sword from corpse")
    assert sword.location is thief
```

`clock.t` is the time and `clock.advance(seconds)` moves it; outside
pytest, `FakeClock().install(monkeypatch)` does the same.
`realm.testing.clock.ENGINE_CLOCKS` lists the modules. Wall clocks (times
kept in the database, which survive a restart) and monotonic ones
(durations kept in memory) all read the one fake time. To move only one
module, replace its `now` alone:
`monkeypatch.setattr("realm.std.mail.mail.now", lambda: 1_800_000_000.0)`.

Install the clock before the objects that stamp a time are made (take the
`clock` fixture before a `sim` fixture that builds the world), or they
carry a real time the fake one is far from.

What a moved clock does not do by itself is run the code that looks at
it; the test runs that, as the server would:

| The server's own | A test calls |
|---|---|
| housekeeping every `REAP_INTERVAL` (regeneration, hunger, idle training, clans, quests, expiry, idle instances) | `await server._reap()`, or the feature's sweep (`task_sweep(store)`, `reap_expired(store)`) |
| softcode `wait()` timers | `await sim.engine.waits.tick()` |
| a fight's beat loop | `clock.advance(encounter.seconds_to_beat)`, then `await encounter.beat()` |
| the heartbeat (spawners, decay, wander, the ambient world beat) | `clock.advance(...)`, then `await server.pulse()` (a `GameServer`; a lone behavior: its `tick(obj, delta)`) |

`encounter.beat()` is what the encounter's loop does each time it wakes:
it fires the round when the beat is due on the clock, sets the next one a
beat away, and closes the fight when it is over (`False` from then on).
Called before the beat is due it does nothing, so a test that drives the
beats never fires one twice with the loop. `server.pulse()` is the same for
the heartbeat: each behavior ticks when its interval has passed on the
clock, and the ambient beat fires once a `WORLD_BEAT`. `tests/test_first_hour.py`
plays a whole game this way.

`tests/test_clocks.py` keeps the list honest: it scans `realm/` for every
read of the time (`time.time()`, `time.monotonic()`, `datetime.now()` ...)
and fails on one that is neither inside a module's `now()` named in
`ENGINE_CLOCKS` nor listed there as real time on purpose (a script's CPU
budget, the heartbeat loop's sleep, the backup file's name, `uptime` and the
server's own clock in `time`). A new clock is a `now()` in its module and
a line in `ENGINE_CLOCKS`.

