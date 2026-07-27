# 076. Bulletin boards

> Checklist item 76 ([now]): *posts as timestamped attrs, on_tick expiry sweep, per-location state*

**What you'll build:** A cork notice board: `post <text>` pins a
notice, `board` reads what is still up, and every notice curls off and
drops on its own after a while, swept both by a slow heartbeat and
lazily whenever anyone touches the board. Then a second board on the
docks, cloned in one line, with its own independent notices.

**Concepts:** posts as **timestamped list attributes**
(`[author, text, dies_at]`),
[`now()`](../reference/softcode.md#fn-now) deadlines, one `sweep`
subroutine shared by the ticker and both commands via
[`eval_attr()`](../reference/softcode.md#fn-eval_attr), the
`script_ticker` behavior, and `@clone` for stamping out per-location
copies whose *state* stays local.

## How it works

The finished board is a single object holding one list, `posts`, where
each row is a notice with a death date. Two commands write and read that
list, and one subroutine reaps the dead rows. This section answers three
questions: what a post actually stores, when the expiry runs, and why a
cloned board keeps its own notices.

**A post is a row with a death date.** `post` appends
`[name(enactor), escape(text), now() + ttl]` to the `posts` list on the
board. [`escape()`](../reference/softcode.md#fn-escape) is there because
players author the text, so chat is treated as text rather than markup.
The deadline is the absolute `dies_at`
([`now()`](../reference/softcode.md#fn-now) plus the time to live) rather
than a countdown, because attributes persist across reboots and a
timestamp needs no upkeep: comparing it against `now()` is always
correct, no matter how long the server slept.

**Expiry is one subroutine, called from three places.** `sweep`
filters the list to unexpired rows and announces how many curled off.
The `script_ticker` heartbeat calls it on a cadence so boards tidy
themselves in empty rooms, while `post` and `board` call it first so a
reader never sees a stale notice between heartbeats. That pairing of a
lazy call with a slow ticker is the standard shape: the ticker keeps the
world honest, the lazy call keeps the reader's view honest, and because
the logic lives once in an
[`eval_attr()`](../reference/softcode.md#fn-eval_attr) subroutine, a rule
change (grace periods, archived posts) lands everywhere at once. This is
the same shared-subroutine relay the [custom channel](074_custom_channel.md)
uses for its two talk spellings.

**Per-location is per-object.** All state sits on the board object, so
"a board in every tavern" is just more boards. `@clone` copies
attributes, tags, and behaviors, and since each copy's `posts` list is
its own, the clone starts life as the same *mechanism* with blank
*state*. Nothing is global, nothing is shared, and there is nothing to
namespace.

Nothing here needs a `target` guard. `post` and `board` are
`$`-commands that fire on the board itself when a player types them, and
`on_tick` is a periodic timer that the `script_ticker` behavior runs
directly on the board, not a room-witnessed event. The
[`target` guard](../reference/softcode.md#guard-on-target) is only for a
reactive [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook,
which fires on every object in a room and must screen out business that
is not its own. There is no such hook in this build.

## Build it

A room and its board, with a time to live of two minutes stored as a
plain number the sweep will read:

```text
@dig The Tavern Commons = tavern, out
tavern
@create notice board
drop notice board
@desc notice board = Cork and thumbtacks. POST <text> pins a notice for a while; BOARD reads what has not yet curled off.
@set notice board/ttl = 120
```

The shared sweep keeps the living rows, and when any dropped off it
writes the shorter list back with
[`set_attr`](../reference/softcode.md#fn-set_attr) and announces the loss
to the room with [`remit`](../reference/softcode.md#fn-remit):

```text
@set notice board/sweep = '''
rows = V('posts') or []
keep = [p for p in rows if p[2] > now()]   # p[2] is dies_at: keep only rows still in the future
if len(keep) < len(rows):
    set_attr(me, 'posts', keep)
    remit(loc(me), f'{len(rows) - len(keep)} curled notice(s) drop off the {name(me)}.')
'''
```

Pinning sweeps first so a fresh post never sits beside a dead one, then
appends the new row and tells the room:

```text
@set notice board/cmd_post = '''
$post *:
eval_attr(me, 'sweep')   # reap stale rows before adding one
set_attr(me, 'posts', (V('posts') or []) + [[name(enactor), escape(arg0), now() + V('ttl', 120)]])   # dies_at is stamped once, at posting time
remit(loc(me), f'{name(enactor)} pins a notice to the {name(me)}.')
'''
```

Reading sweeps first too, then either reports bare cork or lists each
surviving notice with its remaining seconds, delivered privately with
[`pemit`](../reference/softcode.md#fn-pemit):

```text
@set notice board/cmd_board = '''
$board:
eval_attr(me, 'sweep')
rows = V('posts') or []
if not rows:
    pemit(enactor, 'The board is bare cork.')
else:
    for i, r in enumerate(rows):
        pemit(enactor, f'{i + 1}. {r[1]} --{r[0]} ({r[2] - now()}s left)')
'''
```

The heartbeat is the third caller of the same subroutine. `interval:8`
runs `on_tick` every eight world beats, about thirty seconds at the
default four-second tempo, so an unwatched board still tidies itself:

```text
@set notice board/on_tick = eval_attr(me, 'sweep')
@behavior notice board = script_ticker, interval:8
```

And the second board: clone it, carry it to the docks, and re-flavor it.
The clone lands in your hands, so you walk it over and drop it:

```text
@dig The Docks = docks, tavern
@clone notice board = harbor board
get harbor board
docks
drop harbor board
@desc harbor board = Salt-stained planks and a few nails. POST and BOARD work here too, on this dock's own notices.
tavern
```

## Try it

```text
post Buyer wanted: forty crates of salt cod, ask for Bilda.
   -> Bilda pins a notice to the notice board.
board
   -> 1. Buyer wanted: forty crates of salt cod, ask for Bilda. --Bilda (119s left)
```

Walk to the docks and `board` there: bare cork, because the harbor
board's list is its own. Post something there and each room reads only
its own notices. Back in the tavern, make a notice age out on the spot:

```text
@set notice board/ttl = 0
post SOLD, never mind.
```

That second notice was born already due (a zero time to live), so the
next touch of the board (anyone's `board`, anyone's `post`, or the
heartbeat in an empty room) sweeps it:

```text
board
   -> 1 curled notice(s) drop off the notice board.
   -> 1. Buyer wanted: forty crates of salt cod... (...s left)
```

The salt-cod notice, posted under the old time to live, keeps its
original death date, because deadlines are stamped at posting time, not
at read time.

## Going further

- **Numbered take-downs:** a `$unpin <n>` that removes a row, gated to
  `r[0] == name(enactor)` or the board's owner, lets authors manage their
  own notices.
- **Pinned permanence:** the owner posts with a huge time to live, or a
  fourth `sticky` field the sweep skips, so house rules stay up.
- **Read receipts:** cache `seen_<id>` on the board and mark unread rows
  with a `*` in `board`, the mail ledger idiom
  ([in-game mail](075_ingame_mail.md)) in miniature.
- **A town crier:** the sweep already announces, so point it at
  `act(me, ..., targeting='zone')` and expired official notices get
  proclaimed across the station as they lapse (the
  [PA system](078_pa_system.md)).
```
