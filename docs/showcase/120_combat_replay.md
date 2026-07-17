# 120. Combat replay log

> Checklist item 120 — [now] — *recorder objects, event-appended log attrs, $replay*

**What you'll build:** A brass chronicle automaton that scribes every
fight in its room — swings, wounds, taunts, the finish — into a capped
ledger that anyone can `replay` afterwards, timestamped. Item 7's tape
recorder and item 55's motion log, composed and pointed at combat.

**Concepts:** `ON_ATTACK`/`ON_DAMAGE`/`ON_DEATH` witnesses as the
recording heads, `^*` listen for fight talk, the capped-list-attribute
idiom (`(old + [row])[-30:]`), `now()` timestamps replayed as "Ns ago"
(item 55), `eval_attr` subroutines, and an owner-locked `$wipe`.

## How it works

The chronicle is a *witness*: combat propagates a real action for every
swing (`combat:on_attack`), every wound that gets through
(`combat:on_damage`), and the kill (`combat:on_death`) — and each fires
the matching `ON_<EVENT>` attribute on anything standing in the room,
with the acting fighter as `enactor`. Speech comes in through a `^*`
listen trigger (item 7's microphone). Every head calls one `scribe`
subroutine that appends `[now(), text]` and re-slices to the newest 30
— the capped-log idiom, because unbounded lists on hot attributes are
the classic MUD database leak.

**Reconstructing the blow-by-blow.** Two things a witness cannot have:
the engine's narration text (combat messages are deliveries, not
overhearable speech — only `say`-class actions feed `^` listens), and
the hook payload (an event trigger gets `enactor` only — no defender,
no damage number). So the chronicle does what item 115's commentator
does: it *reads the room*. Softcode reads are open, so a `tally`
subroutine snapshots every `in_combat` fighter's HP into each row. The
hooks fire while the action is in flight — before the wound applies —
so each row records the state going *into* the blow and the next row
shows what it cost: a perfectly reconstructable fight, one row behind
the knife.

**Replay is diegetic.** `$replay` walks the rows and `pemit`s each with
its age (`now() - stamp`), so the ledger reads the same live or a day
later. `$wipe ledger` is gated on `enactor == owner(me)` — the
scorekeeper decides when history starts over.

## Build it

```text
@dig The Fight Cage = cage, out
cage
@create match chronicle
drop match chronicle
@desc match chronicle = A brass automaton hunched over a ledger, pen scratching by itself. REPLAY reads the record back; the owner may WIPE LEDGER.
```

The two subroutines — the scribe (append, cap) and the scoreboard:

```text
@set match chronicle/scribe = rows = (V('log') or []) + [[now(), str(arg0)]]; set_attr(me, 'log', rows[-30:])
@set match chronicle/tally = result = ' / '.join([f'{name(o)} {get_attr(o, "hp", 0)}:{get_attr(o, "max_hp", 0)}' for o in contents(loc(me)) if has_tag(o, 'in_combat')])
```

The recording heads, each one line:

```text
@set match chronicle/on_attack = eval_attr(me, 'scribe', name(enactor) + ' presses the attack. [' + eval_attr(me, 'tally') + ']')
@set match chronicle/on_damage = eval_attr(me, 'scribe', name(enactor) + ' lands a telling blow. [' + eval_attr(me, 'tally') + ']')
@set match chronicle/on_death = eval_attr(me, 'scribe', 'FINISH -- ' + name(enactor) + ' ends it.')
@set match chronicle/listen_words = ^*: eval_attr(me, 'scribe', name(enactor) + ' shouts: ' + escape(arg0)) if enactor else None
```

Playback and the eraser:

```text
@set match chronicle/cmd_replay = $replay: rows = V('log') or []; (pemit(enactor, 'The ledger is blank.') if not rows else [pemit(enactor, f'[{now() - r[0]}s ago] {r[1]}') for r in rows])
@set match chronicle/cmd_wipe = $wipe ledger: (del_attr(me, 'log'), pemit(enactor, 'You tear out the used pages. The automaton dips its pen.')) if enactor == owner(me) else pemit(enactor, 'The automaton clutches its ledger jealously.')
```

## Try it

Run a fight in the cage — a few beats, a taunt, a finish. Then, from
anyone standing there (a participant limping back in, a judge, the
loser's second):

```text
replay
[42s ago] Ace presses the attack. [Ace 30:30 / Bruce 20:20]
[42s ago] Ace lands a telling blow. [Ace 30:30 / Bruce 20:20]
[27s ago] Bruce shouts: is that ALL
[27s ago] Ace presses the attack. [Ace 30:30 / Bruce 17:20]
...
[3s ago] FINISH -- Ace ends it.
```

Read it like a scorer's sheet: each row's bracket is the board *before*
that blow, so Bruce's 20→17 between rows is the damage the earlier row
scored. `wipe ledger` from anyone but the owner earns a jealous clutch;
from the owner, a blank page for the next bout.

**~~Limits~~ — BOTH FIXED 2026-07-17 (same two gaps as item 115).** This
scribe infers from HP deltas because, when it was written, event triggers
exposed only `enactor` — no target, no damage, no hit/miss — and
`combat:on_death` fired only on the swing path, so softcode and
damage-over-time kills never reached witnesses. Both are gone: `ON_<EVENT>`
now binds `target` and `adata(...)` (so `adata('damage')` and
`adata('weapon')` let the scribe log "6 cut" outright), and
`combat:on_death` is announced from the one death path, so poison and
grenade finishes are recorded like any other. The HP-delta build below
still works and is left as written.

## Going further

- **Per-fight takes** — scribe into a `take_<n>` attr and roll `n` on
  each `on_death`: `replay 3` replays a specific bout (item 7's tape
  labels).
- **Round markers** — the chronicle can hear the room's beat prompts
  arriving? No — those are private messages; instead have it count
  `on_attack` clusters, or scribe a divider whenever the tally's names
  change.
- **Broadcast the replay** — `$replay to stands` that `remit`s rows to
  item 115's stands: the slow-motion rebroadcast.
- **Stat lines** — on `on_death`, sum each fighter's rows to a
  `record_<name>` attr (fights, finishes); a `$record *` command reads
  career stats — item 87's ledger arithmetic on item 120's data.
