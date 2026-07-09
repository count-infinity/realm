# REALM

**Real-time Event-Action Layered MUD framework** — a modern Python engine
for building text-based multiplayer games (MUDs, MUSHes), with the
complexity of a MU* wrapped up so games are written in *softcode*, live,
from inside the game.

Async (asyncio) + SQLite. No Django, no Twisted, no external services.
Python 3.11+.

```python
# The whole stack in five in-game lines — no world files, no restart:
@dig The Garden = north
@desc here = Roses climb a broken trellis. [[result = ansi('rh', 'Thorns') if skill('observation') >= 12 else '']]
@create parrot
@behavior parrot = script_ticker, interval:8
@set parrot/on_tick = say Pieces of eight!
```

## Install & run

```bash
git clone https://github.com/realm-mud/realm.git && cd realm
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -e .

realm init mygame && cd mygame
realm start                       # telnet server on port 4000
```

Then connect with any MUD client (Mudlet, TinTin++) or plain telnet:

```bash
telnet localhost 4000
```

```text
create Keeper mypassword          # the first character is the SUPERUSER
look                              # you start in The Void, an empty Limbo
help                              # every command, grouped and searchable
```

`Ctrl+C` stops the server; everything lives in the SQLite database, so
`realm start` resumes exactly where you left off.

> `pip install -e .` (editable) is the install for now; once published
> it becomes `pip install realm`.

## The example game

A GURPS-flavored space station with character generation, an
infiltration scenario, combat, and shops:

```bash
realm init spacestation --template spacegame
cd spacestation && realm start
```

There's also a non-interactive combat simulation (Marine vs. Space
Pirate on the GURPS 3d6 system):

```bash
python -m examples.spacegame.game
```

## What's in the box

- **Action propagation** — every game action flows through one two-pass
  (check/react), vetoable pipeline; per-looker perception applies.
- **Softcode** — a sandboxed, Turing-complete scripting layer builders
  use *in-game*: `$`-commands, `^listen`, `ON_<EVENT>` triggers, `on_tick`
  behaviors, inline `[[...]]` in descriptions, and a Penn-style function
  library — all under an ownership/authority model (`controls()`).
- **Swappable game systems** — GURPS and D20 ship in-box and swap the
  *whole* rules package (chargen, skill dice, advancement, combat,
  currency) from one config line; write your own by subclassing.
- **Combat** — beat-driven encounters, melee + ranged (aim/cover/range
  bands), maneuvers, strategies as NPC AI, effects, loot.
- **Living worlds** — NPCs with behaviors (wander, guard, patrol,
  shopkeeper, spawners), dispositions NPCs remember, followers & parties,
  zones with zone-wide softcode and policy.
- **Systems** — economy & shops, skill checks & contests, perception
  (light/dark/invisibility), locks, per-viewer descriptions, condition
  effects, character progression.
- **Color & clients** — pipe-code markup rendered once at the protocol
  edge (efficient ANSI, no string-splitting breakage); telnet with GMCP,
  WebSocket, and custom protocols.
- **Building & operations** — rich OLC (`@dig`, `@create`, `@set`,
  `@lock`, `@behavior`, `@zone`, `@attr`, …), a searchable help system,
  world search (`@find`, `search_world`), attribute flags
  (secret/visual/safe), and Terraform-style area import/export
  (`@export` / `@import` with a plan → apply diff).

## Documentation

Plain Markdown in [`docs/`](docs/) (readable on GitHub); `mkdocs serve`
builds a searchable HTML site.

- **[Getting Started](docs/getting-started/installation.md)** — install,
  first game, the superuser.
- **[Tutorial: The Abandoned Lighthouse](docs/tutorial/index.md)** — a
  complete adventure built live, from empty database to opening night.
- **[Game Systems](docs/guides/game-systems.md)** · **[World
  Management](docs/guides/world-management.md)** · **[Softcode
  Reference](docs/reference/softcode.md)** (auto-generated from the API).
- **[Engine Vision](docs/design/engine_vision.md)** — the "Godot of
  MU*s" thesis that steers the design.

## Development

```bash
pip install -e ".[dev]"
pytest                # ~870 tests, a couple of seconds
ruff check realm/
mkdocs serve          # docs at http://127.0.0.1:8000
```

REALM draws on three battle-tested lineages — **CoffeeMud** (action
propagation, combat), **PennMUSH** (softcode, locks, attribute model),
and **Evennia** (command/typeclass patterns) — aiming for the best ideas
of each behind a clean, modern Python API.
