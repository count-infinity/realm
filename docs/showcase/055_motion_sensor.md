# 055. Motion Sensor Log

> Checklist item 55 — [now] — *ON_ENTER/ON_LEAVE, now(), in-object log attrs*

**What you'll build:** A little black dome that records who entered and
left its room, with timestamps, into a capped in-object log — and a
`review` command that plays the record back as "so-many-seconds ago"
lines.

**Concepts:** paired `ON_ENTER`/`ON_LEAVE` witnesses, `now()` as the
clock, a **list attribute as an append-only log** with a slice cap (no
unbounded growth), and the honest limits of the departure event.

## How it works

The camera (item 54) relays live; the sensor *remembers*. Same two
witness hooks — an object in a room hears every arrival as `ON_ENTER`
and every walk-out as `ON_LEAVE`, mover bound as `enactor` — but
instead of forwarding, each event appends a record to a `log` attribute
on the sensor itself.

Three design points carry it:

1. **Records are plain data.** Each entry is a three-element list:
   `[name, verb, timestamp]`. `now()` is epoch seconds — arithmetic,
   not formatting, is the point: `now() - stamp` at playback time gives
   an age in seconds that is true whenever you read it.

2. **The cap is a slice.** Append-then-slice —
   `(log + [entry])[-20:]` — keeps the newest twenty records and lets
   old ones fall off the front. An attribute that only ever grows is a
   leak wearing a disguise; cap every log you build. (The camera's
   "Recording" variation in item 54 wants the same slice.)

3. **Playback is a loop over data.** `$review` walks the list and
   `pemit()`s one line per record. Sandboxed softcode does loops and
   comprehensions fine — the log is just a list, so rendering it is
   list work.

And the honest limit, worth teaching: **`@teleport` does not fire
`ON_LEAVE`.** A teleport is a placement, not a walk — the engine fires
arrival events (your sensor logs teleporters *appearing*) but no
departure (item 54 documents the same asymmetry). An "entered" with no
matching "left" therefore means one of two things: they are still
inside, or they left by means your sensor cannot see. Real
surveillance has the same gap; read your logs accordingly.

## Build it

One room worth watching:

```text
@dig The Server Vault = vault, out
vault
@create motion sensor
drop motion sensor
@desc motion sensor = A black dome in the corner. A red LED blinks, twice a second, forever. REVIEW plays back its log.
```

The two witnesses. Identical shape, one word different — and note the
append-then-slice cap on both:

```text
@set motion sensor/on_enter = set_attr(me, 'log', ((V('log') or []) + [[name(enactor), 'entered', now()]])[-20:]) if has_tag(enactor, 'player') or has_tag(enactor, 'npc') else None
@set motion sensor/on_leave = set_attr(me, 'log', ((V('log') or []) + [[name(enactor), 'left', now()]])[-20:]) if has_tag(enactor, 'player') or has_tag(enactor, 'npc') else None
```

Playback — oldest first, ages computed at read time:

```text
@set motion sensor/cmd_review = $review: entries = V('log') or []; (pemit(enactor, 'The log is empty.') if not entries else [pemit(enactor, f'[{now() - e[2]}s ago] {e[0]} {e[1]}.') for e in entries])
```

## Try it

Have someone wander through, then read the dome:

```text
(Zeke walks in, waits, walks out; you walk in)
review
  [31s ago] Zeke entered.
  [12s ago] Zeke left.
  [3s ago] You entered.
```

Now the gap, demonstrated: `@teleport` yourself out and back, and
`review` again — your teleport *out* left **no** "left" line, while
your teleport back *in* was logged (arrivals fire for placements and
walks alike; departures only for walks). Twenty records is the whole
memory;
walk in and out enough times and Zeke's visit quietly scrolls off the
front of the list.

## Going further

- **Owner's eyes only** — open the `$review` with
  `pemit(enactor, 'The readout is locked.') if enactor != owner(me)
  else ...`; the log keeps recording either way.
- **Silent alarm splice** — the sensor already has the event; add item
  50's line (`pemit(owner(me), ...)`) inside `on_enter` and it logs
  *and* pages.
- **Occupancy count** — track a single `inside` counter (+1 enter, -1
  leave) alongside the log; an inline `[[...]]` block in the sensor's
  desc can show `Currently inside: N` — mind the teleport gap you just
  learned about.
- **A wipe switch** — `$wipe: set_attr(me, 'log', [])` gated to the
  owner. Every surveillance state needs a guilty conscience feature.
