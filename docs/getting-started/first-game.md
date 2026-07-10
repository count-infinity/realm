# Your First Game

## Create a game directory

Your game is a *directory*, not a fork of the engine:

```bash
realm init mygame
cd mygame
realm start
```

This scaffolds a small project: `config.py` holds your settings (ports,
game name, tick rate); **`rules.py`** is your own game system (character
creation, skills, advancement) — pre-wired and ready to customize; and
`data/` holds the SQLite database and welcome screen. The server is now
listening on telnet port 4000.

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

## Stopping and restarting

`Ctrl-C` stops the server. Everything is in the SQLite database —
characters, rooms, your building work, even half-finished character
generation — so `realm start` picks up exactly where you left off.

Next: build something real — [The Abandoned Lighthouse](../tutorial/index.md).
