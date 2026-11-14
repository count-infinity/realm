# Your First Game

## Create a game directory

Your game is a *directory*, not a fork of the engine:

```bash
realm init mygame
cd mygame
realm start
```

This scaffolds a small project:

- `config.py` holds your settings (ports, game name, tick rate) and
  `FEATURES`, the list of features your game is made of.
- **`rules.py`** is your own game system (character creation, skills,
  advancement), pre-wired and ready to customize.
- **`game.py`** is your game's own feature: the place for your commands,
  behaviors and softcode functions. It has a commented example of each.
- `data/` holds the SQLite database and welcome screen.
- `tests/test_game.py` is a smoke test: it boots your game from its own
  `config.py` and checks a player can look around the start room.
- `README.md` says how to start, where code goes and how to test, and
  points back here.

The server is now listening on telnet port 4000.

To start smaller, pick a preset: `realm init mygame --features social`
(no rules, combat or money, and no `rules.py`) or `--features bare`
(only logging in, looking and building). `classic`, every built-in
feature, is the default.

## Choose your features

`config.py` starts with every built-in feature plus your own:

```python
from realm import CLASSIC
FEATURES = [*CLASSIC, "game"]
```

`CLASSIC` is talk, movement, items, building, rules, combat, abilities,
economy, social, crime, NPC behaviors, spawning, instances, wilderness and
the GURPS, D20 and Merc rulesets. A game that does not want some of them
lists what it does want instead; this one has no combat and no money:

```python
FEATURES = ["accounts", "basics", "talk", "movement", "look", "items", "building", "game"]
```

A left-out feature's commands, behaviors and softcode functions do not
exist in your world. See [Features](../guides/features.md) for the full
list and for writing your own.

## Connect and become the superuser

From another terminal (or any MUD client — Mudlet, TinTin++, telnet):

```bash
telnet localhost 4000
```

```text
create Keeper mypassword
```

**The first character created on a fresh database is the superuser** —
you'll be told so at creation. You'll then pick a character background
and a bonus skill (your `rules.py` builds on GURPS by default; to build
on D20 instead, change the base class in `rules.py` — see
[Game Systems](../guides/game-systems.md)) and arrive in **The Void**,
REALM's Limbo. You have every builder and admin command;
characters created after you are ordinary players (promote them with
`@tag <name> = builder`).

## Look around

```text
look
help
help building
```

`help` lists every command *you* can use, grouped by category — as the
superuser you'll see the Building section ordinary players don't.

## Try the example game

The GURPS-flavored space station example shows most engine systems in
play (character templates, an infiltration scenario, combat, shops):

```bash
cd ..
realm init spacestation --template spacegame
cd spacestation
realm start
```

Connect, create a character, and you'll be walked through **character
generation** — pick a background (soldier, infiltrator, face,
technician) and a bonus skill, then arrive in the Docking Bay. Try
`north` to the Promenade, `consider` NPCs, and `attack` something you
shouldn't.

## Test it

```bash
pip install pytest
pytest
```

`tests/test_game.py` builds your game in memory with
`Simulator.from_game(...)`, runs its first boot (your `init_world`, then a
default start room if you made none), and drives a player through the
real commands. Add a test beside it whenever you add a command; the
[Simulator](../reference/public-api.md#testing) runs softcode and commands
exactly as a connected player would see them.

## Stopping and restarting

`Ctrl-C` stops the server. Everything is in the SQLite database —
characters, rooms, your building work, even half-finished character
generation — so `realm start` picks up exactly where you left off.

Next: build something real — [The Abandoned Lighthouse](../tutorial/index.md).
