# REALM

**Real-time Event-Action Layered MUD framework** — a modern Python
framework for building MUDs, MUSHes, and other text-based multiplayer
games. One asyncio process, SQLite persistence, and a sandboxed
in-game scripting layer so builders create *without a restart*.

## Start here

```bash
git clone https://github.com/count-infinity/realm.git
python -m venv venv && source venv/bin/activate
pip install -e realm        # install the engine; stay in the parent directory

realm init mygame && cd mygame   # your game — a sibling of the engine clone
realm start                 # telnet localhost 4000 — first character is superuser
```

Then build from inside the game:

```text
@dig The Garden = north, south
@create parrot
@behavior parrot = script_ticker, interval:8
@set parrot/on_tick = say Pieces of eight!
```

New here and want a Diku-style game? **[Your First MUD](getting-started/your-first-mud.md)**
goes from `realm init demo --system merc --template midgaard` to a game you
have played, opened to builders and added to. Otherwise read
**[Installation](getting-started/installation.md)** →
**[Your First Game](getting-started/first-game.md)**, then build a full
adventure in **[the tutorial](tutorial/index.md)**. To add code to your
game, start at **[Where things go](guides/features.md#where-things-go)**.

## Finding your way around

The sections, in order:

| Section | For |
|---|---|
| **Getting Started** | [your first MUD](getting-started/your-first-mud.md), installing, `realm init`, your first game, and [the tutorial](tutorial/index.md) (the Abandoned Lighthouse) |
| **Build your game** | [features](guides/features.md) (where every kind of code goes), [pools](guides/pools.md), [rules](guides/game-systems.md) and [content packs](guides/content-packs.md) |
| **Softcode** | the [function and trigger reference](reference/softcode.md), and the [showcase](showcase/index.md) of 250 worked builds |
| **Reference** | the [public API](reference/public-api.md), [configuration](reference/config.md), the architecture, and [contributing](development/contributing.md) |
| **Design notes** | why REALM is built the way it is: the [engine vision](design/engine_vision.md) and the comparisons with other MU*s |

## What you get out of the box

- **Action propagation** — every game action flows through one two-pass,
  vetoable pipeline (perception, locks, behaviors, triggers all ride it)
- **Softcode** — a Turing-complete, sandboxed scripting layer builders
  use in-game (`$`-commands, triggers, tickers, inline `[[...]]`), with a
  real authority model
- **Swappable rules** — [GameSystem](guides/game-systems.md) packages
  (GURPS and D20 ship in-box): chargen, skills, advancement, combat. Build
  your own end-to-end in
  [Creating Your Own System](guides/creating-your-own-system.md)
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
