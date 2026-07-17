# 076. Bulletin boards

> Checklist item 76 — [now] — *posts as timestamped attrs, on_tick expiry sweep, per-location state*

**What you'll build:** A cork notice board: `post <text>` pins a
notice, `board` reads what's still up, and every notice curls off and
drops on its own after a while — swept both by a slow heartbeat and
lazily whenever anyone touches the board. Then a second board on the
docks, cloned in one line, with its own independent notices.

**Concepts:** posts as **timestamped list attributes**
(`[author, text, dies_at]`), `now()` deadlines, one `sweep` subroutine
shared by the ticker and both commands (the relay idiom), the
`script_ticker` behavior, and `@clone` for stamping out per-location
copies whose *state* stays local.

## How it works

**A post is a row with a death date.** `post` appends
`[name(enactor), escape(text), now() + ttl]` to a `posts` list on the
board. `escape()` because players author the text; the absolute
`dies_at` (rather than a countdown) because attributes persist across
reboots and a timestamp needs no upkeep — comparing against `now()`
is always correct, no matter how long the server slept.

**Expiry is one subroutine, called from three places.** `sweep`
filters the list to unexpired rows and announces how many curled off.
The `script_ticker` heartbeat calls it every thirty seconds so boards
tidy themselves in empty rooms; `post` and `board` call it first so a
reader never sees a stale notice even between heartbeats. Lazy sweep
plus slow ticker is the standard pair: the ticker keeps the world
honest, the lazy call keeps the *reader's view* honest, and the logic
lives once in an `eval_attr()` subroutine so a rule change (grace
periods, archived posts) lands everywhere at once.

**Per-location is per-object.** All state sits on the board object,
so "a board in every tavern" is just more boards — `@clone` copies
attributes, tags, and behaviors, and since each copy's `posts` list is
its own, the clone starts life as the same *mechanism* with blank
*state*. Nothing global, nothing shared, nothing to namespace.

## Build it

A room and its board:

```text
@dig The Tavern Commons = tavern, out
tavern
@create notice board
drop notice board
@desc notice board = Cork and thumbtacks. POST <text> pins a notice for a while; BOARD reads what has not yet curled off.
@set notice board/ttl = 120
```

The shared sweep — keep the living, count and announce the dead:

```text
@set notice board/sweep = rows = V('posts') or []; keep = [p for p in rows if p[2] > now()]; (set_attr(me, 'posts', keep), remit(loc(me), f'{len(rows) - len(keep)} curled notice(s) drop off the {name(me)}.')) if len(keep) < len(rows) else None
```

Pinning and reading — both sweep first:

```text
@set notice board/cmd_post = $post *: eval_attr(me, 'sweep'); set_attr(me, 'posts', (V('posts') or []) + [[name(enactor), escape(arg0), now() + V('ttl', 120)]]); remit(loc(me), f'{name(enactor)} pins a notice to the {name(me)}.')
@set notice board/cmd_board = $board: eval_attr(me, 'sweep'); rows = V('posts') or []; pemit(enactor, 'The board is bare cork.') if not rows else [pemit(enactor, f'{i + 1}. {r[1]} --{r[0]} ({r[2] - now()}s left)') for i, r in enumerate(rows)]
```

The heartbeat:

```text
@set notice board/on_tick = eval_attr(me, 'sweep')
@behavior notice board = script_ticker, interval:30
```

And the second board — clone it, carry it to the docks, re-flavor it:

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

Walk to the docks and `board` there: bare cork — the harbor board's
list is its own. Post something there and each room reads only its
own notices. Back in the tavern, make a notice age out on the spot:

```text
@set notice board/ttl = 0
post SOLD, never mind.
```

That second notice was born already due (a zero TTL), so the next
touch of the board — anyone's `board`, anyone's `post`, or the
thirty-second heartbeat in an empty room — sweeps it:

```text
board
   -> 1 curled notice(s) drop off the notice board.
   -> 1. Buyer wanted: forty crates of salt cod... (...s left)
```

The salt-cod notice, posted under the old TTL, keeps its original
death date — deadlines are stamped at posting time, not read time.

## Going further

- **Numbered take-downs** — a `$unpin <n>` that removes a row, gated
  to `r[0] == name(enactor)` or the board's owner: authors manage
  their own notices.
- **Pinned permanence** — the owner posts with a huge TTL, or a
  fourth `sticky` field the sweep skips: house rules stay up.
- **Read receipts** — cache `seen_<id>` on the board and mark unread
  rows with a `*` in `board` — the mail ledger idiom
  ([item 75](075_ingame_mail.md)) in miniature.
- **A town crier** — the sweep already announces; point it at
  `act(me, ..., targeting='zone')` and expired *official* notices get
  proclaimed as they lapse ([item 78](078_pa_system.md)).
