# 115. Arena with spectators

> Checklist item 115 — [now] — *recorder relays: ON_ATTACK/ON_DAMAGE → remit to stands*

**What you'll build:** A fight pit with a stands room, and a ringside
bell that calls the action — every swing, every wound, every taunt in
the pit is relayed blow-by-blow to the spectators next door.

**Concepts:** the bug/tap pattern (item 54) turned sports commentary:
`ON_ATTACK`/`ON_DAMAGE`/`ON_DEATH` witnesses plus a `^*` listen tap,
reading the in-flight action from a hook (`target`, `adata('damage')`),
cross-room delivery with `remit()`, and open-read HP tallies (softcode
reads are open).

## How it works

An object standing in the pit witnesses everything that propagates
there: each swing in an encounter propagates `combat:on_attack`, each
wound `combat:on_damage`, the kill `combat:on_death` — and every one of
them fires the matching `ON_<EVENT>` attribute on the bell, with the
**acting fighter as `enactor`**. Speech is the `^*` listen trigger from
items 7 and 54. One `relay` attribute forwards to the stands
(`remit()` delivers to a whole room, anywhere), and every hook is a
one-line caller — fix the relay once, all feeds change.

**What the bell can see.** A hook gets the same read-only view of the
action that `on_check` wards always had: `target` (who is being swung
at, who is bleeding, who just went down), `atype`, `has_atag()`, and
`adata(key)` for the payload — `adata('damage')` on a wound,
`adata('weapon')` on a swing. So the bell calls the fight the way a
commentator with a good seat calls it: *who* hit *whom*, for how much,
with what.

**And what it still cannot.** Combat's own narration lines are message
delivery, not overhearable speech — only `say`/`emit`-class actions
feed `^` listens — so the bell can never simply parrot the engine's
prose. It reports the event, in its own voice. That is a feature: the
stands hear a *broadcast*, not a log tail.

**The tally, still worth keeping.** Softcode reads are open — `hp` on
anyone is readable — so a `tally` subroutine sweeps the pit for
`in_combat`-tagged fighters and posts the scoreboard alongside the
call. One timing nuance survives the payload: hooks fire while the
action is *in flight*, before the damage lands, so the tally is the
score going *into* the blow while `adata('damage')` is the blow itself.
Read them together and the arithmetic is honest — "Bruce 6/20" and
"3 on Bruce" means he is about to be on 3.

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
@set ringside bell/on_attack = eval_attr(me, 'relay', name(enactor) + ' wades in on ' + name(target) + '! ' + eval_attr(me, 'tally'))
@set ringside bell/on_damage = eval_attr(me, 'relay', name(enactor) + ' draws blood -- ' + str(adata('damage', 0)) + ' on ' + name(target) + '! ' + eval_attr(me, 'tally'))
@set ringside bell/on_death = k = name(enactor); eval_attr(me, 'relay', 'THE CROWD ROARS -- ' + (k + ' puts ' + name(target) + ' down and takes the pit!' if k else name(target) + ' is down -- and no one is claiming it!'))
@set ringside bell/listen_taunt = ^*: eval_attr(me, 'relay', name(enactor) + ' bellows: ' + escape(arg0)) if enactor else None
```

`escape()` on the taunt line because fighters write that text — the
bell treats it as words, not markup. Every other line is a hook reading
its own event: `target` on all three, `adata('damage')` on the wound.

## Try it

Seat a spectator in The Stands, start a fight in the pit (`attack`,
then let the beats run). The stands feed reads:

```text
[pit] Ace wades in on Bruce! Ace 30/30 -- Bruce 20/20
[pit] Ace draws blood -- 3 on Bruce! Ace 30/30 -- Bruce 20/20
[pit] Ace wades in on Bruce! Ace 30/30 -- Bruce 17/20
[pit] Bruce bellows: is that ALL
[pit] Ace draws blood -- 3 on Bruce! Ace 30/30 -- Bruce 17/20
...
[pit] THE CROWD ROARS -- Ace puts Bruce down and takes the pit!
```

— while the spectators never see a line of the pit's native combat
narration, and the fighters never see a `[pit]` tag. The defeated
fighter, if a player, is unconscious on the sand (native defeat rule);
send someone down with `firstaid` before the next bout.

**~~Limits~~ — FIXED 2026-07-17, and the build above is the fix.** Event
triggers used to expose only `enactor`: a witness could not read the
action's target, damage or hit/miss from the hook, so the bell inferred
everything from HP deltas and could not say who was being hit — it just
said someone "drew blood" and let the stands do the subtraction.
`ON_<EVENT>` now gets the same read-only action data `on_check` always
had, so the calls above name the defender and quote the damage. The
second gap is gone too: `combat:on_death` is announced from the one
shared death path, so a fighter finished by poison or a grenade reaches
the bell at all — it used to fire only for swings. The `tally` sweep
stays: not as a workaround now, but because a scoreboard is a genuinely
different thing from a play-by-play.

**One live limit, and it is why `on_death` above is written the long
way.** The event reaches the bell from every death, but the *killer*
does not survive every route: a `damage_over_time` tick calls
`handle_death` with no killer at all, so `enactor` and `adata('killer')`
are both `None`. `target` is always right — someone definitely died —
but "who did it" can be blank. `name(None)` is `''`, not an error, so an
unguarded call would simply roar "THE CROWD ROARS --  puts Bruce down",
which is how you find out. Poison a man in the pit and the honest call
is that nobody is claiming it. See [item 114](114_bounty_board.md),
where the same gap costs real money.

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
