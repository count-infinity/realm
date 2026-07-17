# 115. Arena with spectators

> Checklist item 115 — [now] — *recorder relays: ON_ATTACK/ON_DAMAGE → remit to stands*

**What you'll build:** A fight pit with a stands room, and a ringside
bell that calls the action — every swing, every wound, every taunt in
the pit is relayed blow-by-blow to the spectators next door.

**Concepts:** the bug/tap pattern (item 54) turned sports commentary:
`ON_ATTACK`/`ON_DAMAGE`/`ON_DEATH` witnesses plus a `^*` listen tap,
cross-room delivery with `remit()`, open-read HP tallies (softcode
reads are open), and the honest limits of what a witness object can
see.

## How it works

An object standing in the pit witnesses everything that propagates
there: each swing in an encounter propagates `combat:on_attack`, each
wound `combat:on_damage`, the kill `combat:on_death` — and every one of
them fires the matching `ON_<EVENT>` attribute on the bell, with the
**acting fighter as `enactor`**. Speech is the `^*` listen trigger from
items 7 and 54. One `relay` attribute forwards to the stands
(`remit()` delivers to a whole room, anywhere), and every hook is a
one-line caller — fix the relay once, all feeds change.

**What the bell cannot see — and how it commentates anyway.** An
`ON_<EVENT>` trigger gets the enactor and nothing else: no defender, no
damage number, and combat's narration lines are message delivery, not
overhearable speech (only `say`/`emit`-class actions feed `^` listens).
So the bell does what a good commentator does: it looks at the
fighters. Softcode reads are open — `hp` on anyone is readable — so a
`tally` subroutine sweeps the pit for `in_combat`-tagged fighters and
reads the scoreboard aloud with every event. One timing nuance: hooks
fire while the action is *in flight*, before damage is applied, so each
tally shows the score going *into* the blow; the next event reads out
what it cost. Blow-by-blow, one blow behind — like real ringside radio.

**Ringside vs pit.** The fighters see the engine's native narration
("You attack…", the round summaries) and do **not** get the relay —
`remit` targets the stands room only. The spectators get *only* the
relay: native combat messages never leave the pit. Two rooms, two
scripts of the same fight.

## Build it

The venue:

```text
@dig The Fight Pit = pit, out
pit
@dig The Stands = seats, pit
pit
```

(The `seats` exit is named so it won't collide with the room name when
the bell looks up "The Stands" — `get()` searches the local room first,
and a `stands` exit would shadow the room. Name the doorway and the
destination differently and the lookup stays unambiguous.)

The bell — relay first (late-bound stands lookup, item 54's idiom),
then the scoreboard, then the taps:

```text
@create ringside bell
drop ringside bell
@desc ringside bell = A brass bell on a rope, sized to be heard over a crowd. It rings itself when blood is up.
@set ringside bell/stands = The Stands
@set ringside bell/relay = s = get(V('stands', '')); (remit(s, '[pit] ' + str(arg0)) if s else None)
@set ringside bell/tally = result = ' -- '.join([f'{name(o)} {get_attr(o, "hp", 0)}/{get_attr(o, "max_hp", 0)}' for o in contents(loc(me)) if has_tag(o, 'in_combat')])
@set ringside bell/on_attack = eval_attr(me, 'relay', name(enactor) + ' wades in! ' + eval_attr(me, 'tally'))
@set ringside bell/on_damage = eval_attr(me, 'relay', name(enactor) + ' draws blood! ' + eval_attr(me, 'tally'))
@set ringside bell/on_death = eval_attr(me, 'relay', 'THE CROWD ROARS -- ' + name(enactor) + ' takes the pit!')
@set ringside bell/listen_taunt = ^*: eval_attr(me, 'relay', name(enactor) + ' bellows: ' + escape(arg0)) if enactor else None
```

`escape()` on the taunt line because fighters write that text — the
bell treats it as words, not markup.

## Try it

Seat a spectator in The Stands, start a fight in the pit (`attack`,
then let the beats run). The stands feed reads:

```text
[pit] Ace wades in! Ace 30/30 -- Bruce 20/20
[pit] Ace draws blood! Ace 30/30 -- Bruce 20/20
[pit] Ace wades in! Ace 30/30 -- Bruce 17/20
[pit] Bruce bellows: is that ALL
[pit] Ace draws blood! Ace 30/30 -- Bruce 17/20
...
[pit] THE CROWD ROARS -- Ace takes the pit!
```

— while the spectators never see a line of the pit's native combat
narration, and the fighters never see a `[pit]` tag. The defeated
fighter, if a player, is unconscious on the sand (native defeat rule);
send someone down with `firstaid` before the next bout.

**~~Limits~~ — FIXED 2026-07-17.** The tally-sweep idiom below exists
because event triggers used to expose only `enactor`: a witness could not
read the action's target, damage or hit/miss from the hook. `ON_<EVENT>`
now gets the same read-only action data `on_check` always had — `target`,
`atype`, `has_atag()`, `adata(...)` — so the bell *can* call "a 6-point
cutting wound!" honestly (`adata('damage')`, `adata('weapon')`), and
`combat:on_death` now reaches it from poison and grenade kills too, not
just swings. The sweep build is left as written and still works.

## Going further

- **Betting windows** — bolt item 113's stone into the stands:
  spectators stake on a name before the first `on_attack` relay, the
  bell's `on_death` settles the book.
- **A challenge queue** — a `$signup` list on the bell; its `on_death`
  announces who fights next and `force()`s the pit gate open (the bell
  and gate share an owner).
- **Crowd noise back into the pit** — a second tap in the *stands*
  relaying spectator cheers into the pit: two bugs pointed at each
  other (mind the loop; the engine's script depth guard will cut it,
  but tag your relay lines and filter them out on each side).
- **Season records** — the bell's `on_death` appends `[winner, now()]`
  to a capped `champions` list; a `$records` command reads it back —
  item 120's replay ledger, aggregated.
