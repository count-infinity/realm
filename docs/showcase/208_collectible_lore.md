# 208. Collectible lore

> Checklist item 208 — [now] — *ON_GET/ON_USE unlocks, $codex rendering*

**What you'll build:** scattered lore — a data log you pick up, a mural you
study — that quietly unlock entries in a codex. The Archive terminal reads
your recovered lore back, showing found entries in full and the rest as
`[LOCKED]`, tracked per player.

**Concepts:** lore items whose `ON_GET`/`ON_USE` **stamp an unlock flag on
the finder** (`lore_<slug>`), a **codex master** holding the entry text,
and a `$codex` reader that renders found entries and locks the rest — a
collectible system that's just flags plus a table.

## How it works

The pattern is two halves that never need to know each other's internals:

- **The finds set flags.** Each lore object carries a one-line hook. The
  data log's `ON_GET` fires when it's picked up; the mural's `ON_USE` fires
  when it's studied. Both do the same thing: `set_attr(enactor, 'lore_<slug>',
  1)` — stamp an unlock bit on the *finder*. The items are admin-owned, so
  they may write the player's sheet (owner authority, the rule behind every
  master in this category). The finder learns nothing about the codex; it
  just flips a flag.
- **The codex reads the flags.** The Archive terminal holds an `entries`
  table — `{slug: {title, text}}` — and `$codex` walks it against the
  reader's `lore_*` flags: entries you've unlocked print in full, the rest
  print as `[LOCKED] ???`. The count line (`2/5 entries recovered`) gives
  the collector a completion target.

Because the unlock is a flag on the player and the text is a table on the
master, everything is **per player** for free (reads are open, so the
terminal reads *your* flags) and **content-only** — adding lore is adding a
key to `entries` and dropping an item whose hook sets the matching flag. No
code, no wiring between the log and the terminal beyond the shared slug.

## Build it

The Archive terminal and its codex table (two entries here; add as many as
you like):

```text
@create archive terminal
drop archive terminal
@desc archive terminal = A humming data pedestal. CODEX lists the lore you have recovered.
@set archive terminal/entries = {"beacon": {"title": "The Silent Beacon", "text": "Colony ship Meridian went dark here in 2189; its beacon still pulses on a dead channel."}, "mutiny": {"title": "The Long Mutiny", "text": "The crew that survived did not do so kindly. Three names were struck from the log."}}
```

The finds — a data log unlocked by picking it up, a mural unlocked by
studying it:

```text
@create data log
@tag data log = thing
drop data log
@set data log/on_get = set_attr(enactor, 'lore_beacon', 1); pemit(enactor, 'You recovered a data log. A codex entry was unlocked.')
@create faded mural
drop faded mural
@set faded mural/on_use = set_attr(enactor, 'lore_mutiny', 1); pemit(enactor, 'You study the faded mural. A codex entry was unlocked.')
```

The reader — found entries in full, the rest locked, with a completion
count:

```text
@set archive terminal/cmd_codex = $codex:defs = get_attr(me, 'entries', {}); found = [s for s in defs if get_attr(enactor, 'lore_' + s, 0)]; pemit(enactor, 'Codex -- ' + str(len(found)) + '/' + str(len(defs)) + ' entries recovered:'); [pemit(enactor, '  [' + defs[s]['title'] + '] ' + defs[s]['text']) for s in defs if get_attr(enactor, 'lore_' + s, 0)]; [pemit(enactor, '  [LOCKED] ???') for s in defs if not get_attr(enactor, 'lore_' + s, 0)]
```

(In a real world you'd scatter the log and mural across different rooms;
here they sit by the terminal for the demo.)

## Try it

As Sol:

```text
codex                    -> Codex -- 0/2 entries recovered:
                              [LOCKED] ???
                              [LOCKED] ???
get data log             -> You recovered a data log. A codex entry was unlocked.
codex                    -> Codex -- 1/2 entries recovered:
                              [The Silent Beacon] Colony ship Meridian went dark...
                              [LOCKED] ???
use faded mural          -> You study the faded mural. A codex entry was unlocked.
codex                    -> Codex -- 2/2 entries recovered:
                              [The Silent Beacon] ...
                              [The Long Mutiny] ...
```

The codex fills as you find lore, and every unlock is a flag on *you*
(`@examine Sol` shows `lore_beacon`, `lore_mutiny`) — another player who
found nothing sees `0/2` and two locked slots. Collecting is per-character,
persistent, and inspectable.

## Going further

- **Read-in-place.** Give each lore item a `[[...]]` desc block or an
  `examine` reveal so studying it shows the flavor text on the spot, while
  the codex is the permanent record.
- **Rewards for completion.** Have `$codex` check `len(found) ==
  len(defs)` and grant a title, credits, or a [quest](198_quest_framework.md)
  advance the first time the codex is full — the collector's payoff.
- **Categories.** Namespace slugs (`lore_ship_beacon`, `lore_crew_mutiny`)
  and let `$codex <category>` filter — a codex with tabs.
- **Hidden entries.** Mark some entries `secret` and omit them from the
  `[LOCKED]` list until found, like the hidden badges in
  [achievements](207_achievements.md) — the collector doesn't even know
  they exist until they stumble on them.
- **One-shot logs.** Add `destroy_obj(me)` to a log's `ON_GET` so it
  crumbles as you read it — the lore is in the codex now, not your pack.
