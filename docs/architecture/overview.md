# Architecture Overview

REALM is a **microkernel**: a small kernel of mechanisms, and everything with
game meaning in **features** a game lists in `FEATURES`. Three rings:

```
┌──────────────────────────────────────────────────────────────────────┐
│ games/      gurps/ d20/ merc/       a GameSystem, its combat ruleset │
│ ┌──────────────────────────────────────────────────────────────────┐ │
│ │ std/      accounts/ basics/ talk/ movement/ look/ items/         │ │
│ │           building/ rules/ stealth/ combat/ effects/ abilities/  │ │
│ │           economy/ social/ crime/ npc/ spawning/ instances/      │ │
│ │           wilderness/              one package per feature       │ │
│ │ ┌──────────────────────────────────────────────────────────────┐ │ │
│ │ │ kernel    core/ scripting/ commands/ permissions/            │ │ │
│ │ │           persistence/ gateway/ server/ config/ packs/       │ │ │
│ │ │           features.py                                        │ │ │
│ │ └──────────────────────────────────────────────────────────────┘ │ │
│ └──────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

Imports point inward only. `tests/test_boundaries.py` enforces it:

- the kernel imports nothing from `realm/std` or `realm/games` (it names the
  built-ins only as strings: the `FEATURES` and `GAME_SYSTEM` defaults, and
  where a built-in name resolves);
- `std` features do not import `games`;
- a feature imports another feature's parts only when it `requires` it
  (naming another feature's action types is allowed);
- a world of no features boots, saves and loads, and loads no feature module;
- the default world loads exactly the packages `CLASSIC` names.

## The kernel

```
realm/
  features.py          Feature, FeatureSet, load: how a feature joins a world
  core/                objects, tags, attrflags, propagation, events, movement,
                       search, query, zones, beats, behaviors, dice, markup,
                       safe_eval, language, teardown, pairing, perception, ops/,
                       inflate, defs, eventdefs, world, action_types
  scripting/           sandbox, engine, triggers, verbs, registry, namespace,
                       handle, inline, waits, scripted_behavior, ticker,
                       lib/ (kernel softcode functions only)
  commands/            base, dispatcher
  permissions/         locks, roles, entitlements
  persistence/         manager (SQLite), memory, store, tagindex, keyid, worldio
  gateway/             session, telnet, websocket
  server/              game (GameServer), world (build_world), puppet
  config/              loader (Settings)
  packs/               content-pack loader
  testing/             Simulator
```

- **World** (`realm/core/world.py`): the one handle to the running world.
  Code asks `get_world()` for the store, the propagation engine, the script
  engine, the rules (`world.rules`, set by the `rules` feature; the kernel
  never calls it) and features' services (`world.services["combat"]`), and
  reads configuration with `setting("EMOTE_SIGIL")`. Nothing is pushed into
  module globals at boot, so two worlds in one process switch with `use_world`.
- **build_world** (`realm/server/world.py`): the composition root. Given an
  open store and `Settings`, it builds a `World` (a fresh propagation engine,
  the dispatcher, the script engine), installs it, then wires every loaded
  feature's runtime declarations. `close()` undoes all of it. The server and
  the test Simulator both call it.
- **GameServer** (`realm/server/game.py`): opens the store, calls
  `build_world`, loads the world, runs the tick and reap loops and the
  protocol servers. Input goes the session's own prompt, then the features'
  input interceptors, then the dispatcher. It logs every setting that
  differs from its default at INFO.
- **Gateway**: each protocol accepts connections, makes a writer, calls
  `SessionManager.create_session(writer=...)` and submits input; the
  **SessionManager** treats every protocol alike.
- **CommandDispatcher** (`realm/commands/dispatcher.py`): a command's token,
  exact name, alias or unique prefix, then the features' fallbacks, then
  the unknown handler (softcode `$`-commands). It knows no command by name.
- **ScriptEngine** (`realm/scripting/engine.py`): softcode `$`-commands,
  `^listen`, `ON_<EVENT>` triggers, waits.
- **Objects, propagation, behaviors** (`realm/core/`): everything is a
  `GameObject` (tags and `db.*` attributes); every action flows through one
  two-pass pipeline ([details](events.md)); behaviors are reusable brains.
- **Persistence**: `Store` (`realm/persistence/store.py`) is what engine code
  may call on a store; `PersistenceManager` (SQLite, WAL) and `MemoryStore`
  provide it, with dirty tracking and a periodic flush.

## Features

A feature is a package `realm/std/<name>/` (a game system's is
`realm/games/<name>/`). `feature.py` declares it: its commands, behaviors,
softcode functions, observers, events, settings and the seams it fills
(see [Features](../guides/features.md)). Its other modules are its parts
and import without loading the feature:

```
realm/std/combat/
  feature.py     feature = Feature("combat", requires=["rules", "items"]) ...
  actions.py     CombatAction (its action types)
  commands.py    the command handlers
  softcode.py    its softcode functions (feature.py declares them)
  behaviors.py   its behaviors
  manager.py, encounter.py, ...   everything else it needs
```

A feature that uses another without needing it asks for its service:
`world.services.get("look")`, `"economy"`, `"social"`, `"talk"`, `"damage"`,
`"combat"`; absent means the world lacks it.

## Data Flow: Command Execution

```
1. Client sends "say hello"
        │
        ▼
2. Protocol receives data, calls on_command(session, "say hello")
        │
        ▼
3. Dispatcher.dispatch(session, "say hello")
        │
        ├─► Command found? Execute handler
        │           │
        │           ▼
        │   4. Handler sends messages: session.send("You say...")
        │           │
        │           ▼
        │   5. Handler propagates an Action (two passes:
        │      check — locks/behaviors may block; react)
        │           │
        │           ▼
        │   6. Messages render per looker; observers
        │      (softcode, stealth, combat) see it
        │
        └─► No command? The features' fallbacks (a typed exit name),
            then the unknown handler (softcode $-commands)

7. After handler completes: session.flush_output()
        │
        ▼
8. All queued messages sent to client via writer callback
```

## Design Decisions

### Why Single-Process?

Unlike Evennia's Portal/Server split, REALM uses a single async process:

- **Simpler deployment** - One process to manage
- **Lower latency** - No IPC overhead
- **Easier debugging** - Single stack trace
- **Hot reload via behaviors** - Game logic in behaviors can be reloaded

### Why Protocol-Agnostic Sessions?

Sessions don't know about telnet vs websocket:

- **Uniform API** - `session.send()` works the same everywhere
- **Easy testing** - Mock sessions without network code
- **Future-proof** - Add new protocols without changing game code

### Why Action Propagation?

One pipeline for every action decouples causes from effects:

- **Extensible** - behaviors and softcode react to any action, no registration tables
- **Vetoable** - the check pass lets locks and behaviors block before effects
- **Observable** - stealth, combat auto-initiation, and logging are just observers
  a feature declares

## Next Steps

- [Session Lifecycle](sessions.md) - Deep dive into connection handling
- [Action Propagation](events.md) - How actions flow through the system
- [Command Dispatch](commands.md) - Command registration and routing
