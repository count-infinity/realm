# Operating a Live Game

This page is for whoever runs the server: keeping connections healthy,
announcing and stopping, watching a troublemaker, backing up, and
upgrading. The admin commands are the `operations` feature (in
`CLASSIC`); everything else is the engine's and the `realm` command's.

## Connections

| Setting | Default | Meaning |
|---|---|---|
| `IDLE_TIMEOUT` | 0 | minutes without input before a connection is closed (0: never); admins are exempt |
| `LINKDEAD_SECONDS` | 120 | how long a character whose connection dropped waits in the room |
| `COMMAND_RATE` | 10 | lines a connection may send per second, sustained (0: no limit) |
| `COMMAND_BURST` | 30 | lines it may send at once before the rate applies |
| `FLOOD_DISCONNECT_SECONDS` | 30 | how long it may stay over the rate before it is closed (0: never) |

**Link-dead.** When a connection drops without `quit` (the client crashed,
the network went), the character stays where it was, tagged `linkdead`;
the room hears "Ann has lost their link." and sees `Ann (linkdead)`. A
fight goes on: the character keeps its default action. If the player
connects again within `LINKDEAD_SECONDS`, they resume in place ("Welcome
back"); otherwise the character leaves play as on `logout` ("Ann has
disconnected.", and `ON_DISCONNECT` fires then). `quit`, `@boot`, an idle
timeout and a shutdown are not link loss: the character leaves at once.
A server that stops with characters link-dead clears the tag at the next
start.

**Idle.** Every `REAP_INTERVAL` seconds the server closes connections idle
for `IDLE_TIMEOUT` minutes, at the login screen or in play, except an
admin's character.

**Flood control.** Each connection has a bucket of `COMMAND_BURST` lines
that refills at `COMMAND_RATE` a second. A line that finds it empty is
dropped, and the first drop says so ("You are sending commands too fast;
the extra ones were dropped."). A connection that keeps it empty for
`FLOOD_DISCONNECT_SECONDS` is closed and logged (a warning naming the
address and character). A multi-line `'''` block counts as one line. The
defaults leave room for a client's speedwalk.

## Who is on

`who` lists the characters in play with their idle time and where they
are, then the link-dead ones, leaving out anyone the viewer cannot see (an
invisible admin). Beside a name it shows marks: `linkdead`, `afk` (with
`channels`), and whatever the game adds. The marks come from
`world.services["who"].fields`, a list of `(viewer, player) -> str | None`
callables:

```python
# game.py
@feature.on_install
def _titles_on_who(world):
    world.services["who"].fields.append(
        lambda viewer, player: player.db.get("title"))
```

Softcode reads the same: `online_players()` (the characters in play the
running object can see) and `idle_seconds(obj)` (seconds since the player
last typed or lost their link; `None` when they are not on). A nudge for
the idle is one line on an object running the `script_ticker` behavior:

```text
@behavior concierge = script_ticker
@set concierge/on_tick = [pemit(p, 'You seem to be away; type afk to say so.') for p in online_players() if idle_seconds(p) > 900]
```

## Announcing and stopping

| Command | Does |
|---|---|
| `@wall <message>` | sends a line to every connection, playing or at the login screen |
| `@shutdown [seconds] [= reason]` | counts down (default 60 seconds), announcing at once, each minute, and 30, 10 and 5 seconds out; then saves everything and stops |
| `@shutdown/cancel` | stops the countdown and says so to everyone |
| `@reboot [seconds] [= reason]` | the same, and `realm start` exits with status 3 so a supervisor starts it again |
| `@reboot/cancel` | as `@shutdown/cancel` |

All are admin commands, logged on the `realm.admin` logger. `realm start`
exits with 0 after `@shutdown` or a signal (`Ctrl-C`, `systemctl stop`),
1 when it could not start, and 3 after `@reboot`.

## Watching and holding

| Command | Does |
|---|---|
| `@snoop <player>` | everything the player is sent is copied to you, each line marked `[Name]` |
| `@snoop` | stops every snoop you have running |
| `@freeze <player>` | everything they type is answered "You are frozen and cannot act." (`quit` still works) |
| `@thaw <player>` | lets them act again |

A snoop ends when either connection closes. A snoop that would loop (you
snoop someone who already sees your output) is refused. Each command is
logged on `realm.admin`. A frozen character stays frozen across restarts
(it is the `frozen` tag).

## Backup and restore

```bash
realm backup                    # data/backups/game-20261116-101500-123456.db
realm backup nightly.db         # or a file of your choosing
realm backup --keep 7           # then delete all but the newest 7 in data/backups/
realm restore data/backups/game-20261116-101500-123456.db
```

A backup uses SQLite's online backup API: it is a consistent copy even
while the server runs and writes. It holds what has been saved; the server
saves changed objects every `FLUSH_INTERVAL` seconds. `realm restore`
checks the backup is a sound REALM database and replaces the game's
database with it; it refuses while the server is running on that
database (the server keeps a pid file beside it, `game.db.pid`).

The server can take backups itself:

| Setting | Default | Meaning |
|---|---|---|
| `BACKUP_INTERVAL_HOURS` | 0 | hours between automatic backups, the first one interval after start (0: off) |
| `BACKUP_KEEP` | 0 | after each, keep only the newest this many (0: keep all) |

It saves everything first, then writes to `data/backups/`.

## Running under systemd

```ini
# /etc/systemd/system/mygame.service
[Unit]
Description=My REALM game
After=network.target

[Service]
User=mud
WorkingDirectory=/home/mud/mygame
ExecStart=/home/mud/venv/bin/realm start
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

`Restart=on-failure` starts the server again after `@reboot` (status 3)
or a crash, and not after `@shutdown` or `systemctl stop` (status 0;
`stop` sends SIGTERM, which shuts down cleanly). Without systemd, a shell
loop does the same:

```bash
while realm start; [ $? -eq 3 ]; do :; done
```

## Upgrading

1. Stop the server (`@shutdown`).
2. Back up: `realm backup`.
3. Upgrade the engine (`pip install -U realm`, or pull your checkout).
4. `realm migrate`.
5. Start it again.

The database's schema has a version. A REALM whose schema is newer than
the database refuses to start and says to run `realm migrate`; it never
changes the tables by itself. `realm migrate` runs each step from the
database's version to the engine's, in order, each in its own
transaction, and refuses while the server is running. A database newer
than the engine is refused too: upgrade the engine. Changes to the
objects themselves (accounts made from old characters, a new clock, command
aliases moved out of `aliases` into `command_aliases`) are made at boot,
and need nothing from you.

| Version | Change |
|---|---|
| 1 | the `objects` table |
| 2 | an index on `parent_id` |
