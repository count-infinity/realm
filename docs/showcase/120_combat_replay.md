# 120. Combat replay log

> Checklist item 120 — [now] — *recorder objects, event-appended log attrs, $replay*

**What you'll build:** A brass chronicle automaton that scribes every
fight in its room — swings, wounds, taunts, the finish — into a capped
ledger that anyone can `replay` afterwards, timestamped. Item 7's tape
recorder and item 55's motion log, composed and pointed at combat.

**Concepts:** `ON_ATTACK`/`ON_DAMAGE`/`ON_DEATH` witnesses as the
recording heads, reading each event's own data (`target`,
`adata('damage')`, `adata('weapon')`), `^*` listen for fight talk, the
capped-list-attribute idiom (`(old + [row])[-30:]`), `now()` timestamps
replayed as "Ns ago" (item 55), `eval_attr` subroutines, and an
owner-locked `$wipe`.

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

**Writing the blow-by-blow.** Each hook can read its own event:
`target` is the fighter on the receiving end, `adata('damage')` is what
the wound cost, `adata('weapon')` is what did it. So a row records what
*happened*, in so many words — not a puzzle for the reader to solve
later. One thing a witness still cannot have is the engine's narration
text: combat messages are deliveries, not overhearable speech (only
`say`-class actions feed `^` listens), so the chronicle writes its own
prose from the event's facts rather than transcribing the room.

**The tally, alongside.** Softcode reads are open, so a `tally`
subroutine still snapshots every `in_combat` fighter's HP into each
row — a scoreboard next to the play. Hooks fire while the action is in
flight, before the wound applies, so a row's bracket is the board
*going into* that blow and the row's own damage number is what the
blow took off it. The two together are the whole fight, no subtraction
required.

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

The recording heads, each one line. `adata('weapon')` is the object
swung (or `None` for fists — hence the `if w else` branch), so the
ledger names the knife as well as the hand:

```text
@set match chronicle/on_attack = w = adata('weapon'); eval_attr(me, 'scribe', name(enactor) + ' presses the attack on ' + name(target) + (' with ' + name(w) if w else ' barehanded') + '. [' + eval_attr(me, 'tally') + ']')
@set match chronicle/on_damage = eval_attr(me, 'scribe', name(enactor) + ' lands ' + str(adata('damage', 0)) + ' on ' + name(target) + '. [' + eval_attr(me, 'tally') + ']')
@set match chronicle/on_death = k = name(enactor); eval_attr(me, 'scribe', 'FINISH -- ' + (k + ' ends ' + name(target) + '.' if k else name(target) + ' dies with no hand on record.'))
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
[42s ago] Ace presses the attack on Bruce barehanded. [Ace 30:30 / Bruce 20:20]
[42s ago] Ace lands 3 on Bruce. [Ace 30:30 / Bruce 20:20]
[27s ago] Bruce shouts: is that ALL
[27s ago] Ace presses the attack on Bruce barehanded. [Ace 30:30 / Bruce 17:20]
...
[3s ago] FINISH -- Ace ends Bruce.
```

Read it like a scorer's sheet: each row's bracket is the board *going
into* that blow, and the damage on the row is what came off it — Bruce's
20→17 is written twice over, once as a number and once as the next row's
bracket. `wipe ledger` from anyone but the owner earns a jealous clutch;
from the owner, a blank page for the next bout.

**~~Limits~~ — BOTH FIXED 2026-07-17 (same two gaps as item 115), and the
build above is the fix.** This scribe used to infer from HP deltas
alone — rows read "Ace lands a telling blow", with no *whom* and no *how
much* — because event triggers exposed only `enactor`, and
`combat:on_death` fired only on the swing path, so softcode and
damage-over-time kills never reached witnesses. Both are gone:
`ON_<EVENT>` binds `target` and `adata(...)`, so the heads above log the
defender, the number and the weapon outright; and `combat:on_death` is
announced from the one shared death path, so a poison finish reaches the
scribe at all. The tally stays, because a scoreboard is not a
play-by-play.

**What is still missing is the killer, not the death.** A
`damage_over_time` tick calls `handle_death` with no killer, so
`enactor` and `adata('killer')` are `None`; a softcode `damage()` kill
names the *scripted object* that dealt it (the grenade, the trap), not
whoever armed it. `target` is always reliable. That is why `on_death`
above tests `k` before writing a name — a ledger that records
"FINISH --  ends Bruce" is worse than one that admits it does not know.
[Item 114](114_bounty_board.md) shows what the same gap costs a system
that has to *pay* someone.

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
