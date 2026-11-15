# REALM

REALM is a Python engine for text-based multiplayer games: MUDs, MUSHes and
their relatives. It runs as a single asyncio process with a SQLite
database, so there is nothing else to install or operate. It needs Python
3.12 or newer, and it is pre-alpha: the API changed a great deal in 0.2.0
(see the [changelog](CHANGELOG.md)).

A REALM game is made in two places. Rules that need real code, such as how
characters are created, how skills improve and how combat resolves, are
written in Python in your game's own directory. The world itself (rooms,
objects, NPCs and the scripts that make them react) is built from inside
the running game, in a sandboxed scripting language called softcode, with
no restart. The two are independent. You can run a stock rules system and
only build, or write your own rules and leave the building to others.

## Install and run

```bash
git clone https://github.com/count-infinity/realm.git
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -e realm              # install the cloned engine (stay in the parent dir)

realm init mygame && cd mygame    # your game is a sibling of the engine clone, not inside it
realm start                       # telnet server on port 4000
```

Connect with any MUD client (Mudlet, TinTin++) or plain telnet:

```bash
telnet localhost 4000
```

```text
create Keeper mypassword          # the first character is the superuser
look                              # you start in The Void, an empty room
help                              # every command, grouped and searchable
```

`Ctrl+C` stops the server. Everything lives in the SQLite database, so
`realm start` resumes exactly where you left off.

`pip install -e realm` (an editable install of the clone) is the only
install for now. Once REALM is published it becomes `pip install realm`.

## Pick a starting point

`realm init` can start you in three different places, depending on how
much of a game you want on the first day.

### A complete Diku-style game

```bash
realm init mygame --template midgaard
cd mygame && realm start
```

This gives you the classic town of Midgaard (143 rooms, with shops, guards
and monsters that respawn) running on the Merc rules: five classes, THAC0
combat, experience and levels, and a pack of 23 spells. Create a
character and you can play at once, or start building new areas onto the
town. Other ROM areas can be converted and loaded beside it with
`realm import-rom` ([Importing ROM areas](docs/development/rom-import.md)).

The template is a full project like any other: `config.py`, `rules.py`
(a class that inherits the Merc rules), `game.py` (your own commands and
behaviors), a smoke test and a short README, plus the area file.

### An empty world with a rules system you can change

```bash
realm init mygame
```

This writes `config.py` (settings), `rules.py` (your rules), `game.py`
(your own commands and behaviors), a smoke test and a short README. The
world is empty, which is what you want if you plan to build your own.

`rules.py` holds a class that inherits a stock rules system, GURPS by
default, and you change the game by overriding parts of it. `--system`
picks the system it inherits: `gurps`, `d20` or `merc` (Diku-style rules
on an empty world):

```bash
realm init mygame --system merc
```

The commented examples in `rules.py` (adding a class, a skill) are written
for the system you picked.

Choose the rules system before the first character is created. Characters
record the system they were made under, and there is no migration between
systems.

### A smaller game

`realm init mygame --features social` leaves out rules, combat and money,
for a game that is about talking and building. `--features bare` keeps
only logging in, looking and building. Either can grow later by adding
features to the list in `config.py`.

There is also a second example game, a GURPS-based space station with an
infiltration scenario: `realm init mygame --template spacegame`.

## Building: work done inside the game

The first character created on a server is the superuser and has every
building command. To let another player build, give them the builder tag:
`@tag <name> = builder`.

Building is done live. These five lines make a room, give it a description
that shows an extra word to observant characters, and add a parrot that
speaks every eight seconds:

```text
@dig The Garden = north
@desc here = Roses climb a broken trellis. [[result = ansi('rh', 'Thorns') if skill('observation') >= 12 else '']]
@create parrot
@behavior parrot = script_ticker, interval:8
@set parrot/on_tick = say Pieces of eight!
```

Three documents teach it, in this order:

1. [The tutorial](docs/tutorial/index.md) builds a complete adventure, The
   Abandoned Lighthouse, from an empty database over fourteen chapters. It
   starts with rooms and doors and ends with shops, crime and magic.
2. [The showcase](docs/showcase/index.md) is 231 worked builds, each one a
   thing a builder might want and the softcode that makes it: a trainer
   NPC, recipe crafting, achievements, a bank, a boss with phases.
3. [The softcode reference](docs/reference/softcode.md) lists every
   function, trigger and event.

[World Management](docs/guides/world-management.md) covers exporting and
importing areas and the tools for running a live world.

## Programming: work done in Python

Your game is a directory, and REALM is a library it uses. You never edit
the engine to change your game.

`rules.py` is the game system. It decides how a character is created, how
a skill check is rolled, what a kill awards and how that award turns into
advancement, what the `score` command shows, and which resource pools
(hit points, mana, anything else) characters have. A Diku-like game with
a few changes usually starts as a subclass of `MercSystem` that overrides
the parts that differ. [Game Systems](docs/guides/game-systems.md)
explains each of those decisions, and
[Creating Your Own System](docs/guides/creating-your-own-system.md) builds
a new one from nothing, including its combat rules.

`game.py` is your game's feature: the place for new commands, NPC
behaviors, softcode functions for your builders, reactions to events,
settings and the rest. One table says what to declare for each of them,
with a short example of every row:
[Where things go](docs/guides/features.md#where-things-go).

The names a game may import are listed in the
[Public API](docs/reference/public-api.md), and they are the only ones
that will not move between releases without notice. The scaffold includes
a test that boots your game in memory; run it with `pytest`, and add your
own beside it.

## What is not built yet

It is better to know these before you plan a game around them.

- **Accounts.** A login is one character with its own password. There is
  no account that owns several characters, so nothing (achievements,
  unlocks, a shared bank) can apply across a player's characters. Login is
  itself a feature, so a game can replace it with its own, but that is a
  substantial piece of work and no guide covers it yet.
- **How skills improve.** Two models are implemented: spending character
  points (GURPS, D20) and gaining levels (Merc). Skills that improve
  through use, and training that takes real time, are designed
  ([Skills Inventory](docs/design/skills-inventory.md)) but not
  implemented. A game can build either from existing parts, for example an
  observer that watches attacks land or a timed softcode `wait`, and the
  showcase has softcode versions of a trainer and of achievements for a
  single character.
- **Merc is not all of Diku.** Characters earn practices when they gain a
  level, but there is no `practice` command to spend them. Walking does
  not cost movement points. ROM mob programs are not converted on import.
  The [import guide](docs/development/rom-import.md#merc-parity-the-punch-list)
  lists what converts and what does not.

## What is there

Underneath everything is one mechanism. Every action in the game, whether
a spoken line, a sword blow or a step through a door, passes through a
single pipeline in which nearby objects may first refuse or alter it and
then react to it. Softcode triggers, locks, wards and NPC behaviors all
attach to that pipeline, which is why a builder can make a door that
refuses thieves or a room that punishes spellcasting without anyone
writing Python.

On top of it, the built-in features provide combat in timed rounds with
melee and ranged attacks, NPC behaviors (wandering, guarding, patrolling,
shopkeeping, respawning), money and shops, opinions that NPCs hold about
individual characters, parties and followers, stealth, darkness and
invisibility, timed effects such as poison, spells and abilities defined
as data, health and resources on anything (a ship's shields and hull work
like a character's hit points), instanced areas, procedural wilderness,
the building commands, a searchable help system, and area import and
export. Three rules systems are included: GURPS, D20 and Merc. Players
connect by telnet (with GMCP) or WebSocket.

Each of these is a feature, and a game lists the ones it wants. A feature
that is left out does not exist in that game: its commands are unknown and
its softcode functions are undefined. `realm features` shows what is
available, including features installed from other packages.

## Documentation

The documentation is plain Markdown in [`docs/`](docs/) and reads well on
GitHub. `mkdocs serve` builds a searchable site from it.

- Getting started: [installation](docs/getting-started/installation.md)
  and [your first game](docs/getting-started/first-game.md).
- For builders: [the tutorial](docs/tutorial/index.md),
  [the showcase](docs/showcase/index.md),
  [the softcode reference](docs/reference/softcode.md) and
  [world management](docs/guides/world-management.md).
- For programmers: [features](docs/guides/features.md),
  [game systems](docs/guides/game-systems.md),
  [creating your own system](docs/guides/creating-your-own-system.md),
  [pools](docs/guides/pools.md),
  [content packs](docs/guides/content-packs.md) and the
  [public API](docs/reference/public-api.md).
- Design: [VISION.md](VISION.md) states the rules the engine is held to,
  and the [design notes](docs/design/engine_vision.md) explain why it is
  built the way it is.

## Working on the engine

To change REALM itself, work inside the clone:

```bash
cd realm
pip install -e ".[dev]"
pytest                # about 2,700 tests, half a minute
ruff check realm/
mkdocs serve          # docs at http://127.0.0.1:8000
```

The kernel (`realm/core`, `scripting`, `server` and their neighbors) holds
mechanisms and imports no feature. Every built-in is a feature package in
`realm/std/<name>/`, and each rules system is one in `realm/games/<name>/`,
declared with the same API your `game.py` uses.
[Contributing](docs/development/contributing.md#where-new-code-goes)
explains the rule and the tests that enforce it.

REALM borrows from three older engines: CoffeeMud for action propagation
and combat, PennMUSH for softcode, locks and the attribute model, and
Evennia for its command and object patterns.
