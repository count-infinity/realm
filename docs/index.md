# REALM

**Real-time Event-Action Layered MUD framework** — a modern Python
framework for building MUDs, MUSHes, and other text-based multiplayer
games. One asyncio process, SQLite persistence, and a sandboxed
in-game scripting layer so builders create *without a restart*.

## Start here

```bash
git clone https://github.com/realm-mud/realm.git && cd realm
python -m venv venv && source venv/bin/activate
pip install -e .

realm init mygame && cd mygame
realm start                 # telnet localhost 4000 — first character is superuser
```

Then build from inside the game:

```text
@dig The Garden = north, south
@create parrot
@behavior parrot = script_ticker, interval:8
@set parrot/on_tick = say Pieces of eight!
```

New here? Read **[Installation](getting-started/installation.md)** →
**[Quick Start](getting-started/quickstart.md)**, then build a full
adventure in **[the tutorial](tutorial/index.md)**.

## Finding your way around

| If you want to… | Go to |
|---|---|
| **Follow a worked example** end to end | [Tutorials](tutorial/index.md) — the Abandoned Lighthouse |
| **Do a specific task** ("add a class", "manage a world") | [How-To Guides](guides/game-systems.md) |
| **Understand how something works** and why | [Concepts](concepts/character-creation.md) & [Architecture](architecture/overview.md) |
| **Look up a function, trigger, or API** | [Reference](reference/softcode.md) |
| **Hack on REALM itself** | [Contributing](development/contributing.md) |

## What you get out of the box

- **Action propagation** — every game action flows through one two-pass,
  vetoable pipeline (perception, locks, behaviors, triggers all ride it)
- **Softcode** — a Turing-complete, sandboxed scripting layer builders
  use in-game (`$`-commands, triggers, tickers, inline `[[...]]`), with a
  real authority model
- **Swappable rules** — [GameSystem](guides/game-systems.md) packages
  (GURPS and D20 ship in-box): chargen, skills, advancement, combat
- **Playable immediately** — beat combat (melee + ranged), NPCs with
  brains, shops, dispositions, followers, zones
- **Protocol agnostic** — telnet (with GMCP), WebSocket, or your own

## Design lineage

REALM draws on three battle-tested MU* implementations — PennMUSH
(permissions, softcode, locks), Evennia (command parsing, object model),
and CoffeeMud (combat, economy, area templates) — while providing a
clean, modern Python API. The [Engine Vision](design/engine_vision.md)
lays out the north star: *the engine hides MU\* complexity; games are
built in softcode.*
