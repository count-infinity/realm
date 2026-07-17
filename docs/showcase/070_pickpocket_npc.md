# 070. Pickpocket NPC

> Checklist item 70 — [now] — *contest(), skill_def, admin-owned theft authority, act() custom events, crime response*

**What you'll build:** Fenn, a cutpurse working the Shadow Market on a
timer. Each pass he picks a mark and rolls a *contested* check —
pickpocket against the mark's observation. Win: something leaves your
pack (or five credits leave your purse) and all you feel is a tug.
Lose: he's caught wrist-deep, the cry goes up as a **custom
propagated event**, and the bazaar's zone master dispatches a
constable — item 71's crime response, wired to a new crime.
**Concepts:** `contest()` opposed rolls, a `skill_def` making
"pickpocket" a real skill, admin-owned NPCs' authority to
`teleport_obj`/`transfer_credits` against players, `act()` firing a
custom `event:theft`, zone-master dispatch, `script_ticker` pacing.

## How it works

**The roll is a real contest.** `contest(me, 'pickpocket', m,
'observation')` — both sides roll under the live game system; margins
compare; **ties go to the defender** (the wrist gets caught). The
victim's `observation` matters, so perceptive characters are genuinely
harder marks — theft plugs into the same skill economy as sneaking
(item 160) and guard-spotting (the `watchful` behavior). "Pickpocket"
isn't in the built-in table, so we add it as data first: a
`skill_def` object (stat + penalty + `@reload`, item 59's pattern) and
the whole engine can roll it.

**The theft is owner authority, again.** Moving an item out of a
player's pack (`teleport_obj(loot, me)`) and taking their credits
(`transfer_credits(m, me, 5)`) are mutations against a player — the
executor must `controls()` them, so **Fenn must be admin-owned**
(item 69 walks through this model). The engine isn't winking at
theft: it's the same rank that lets the watch master move its
guardsman. A builder-owned Fenn simply fails to steal — authority,
not error handling.

**Getting caught is a propagated event you invent.** `ON_<EVENT>`
matching is by suffix — *any* `ON_<name>` attribute fires if something
propagates a matching action. So a caught Fenn fires
`act(here, 'THIEF! ...', targeting='room', action_type='event:theft')`
— and the zone master (who witnesses every event in its member rooms,
item 71) reacts with an `ON_THEFT` attribute nobody had to add to the
engine. Crimes are a *namespace*, not a feature list. The dispatch
itself is 71's exact pattern: cooldown attr, disposition drop,
`teleport_obj` the constable in, `force()` the challenge and the
arrest — queued forces run after the script, in order, so the
constable lands before he swings.

## Build it

**As your admin character** (Fenn's fingers need the rank — see
above). First, make "pickpocket" a rollable skill, then the market:

```
@create pickpocket
@tag pickpocket = skill_def
@set pickpocket/stat = dexterity
@set pickpocket/penalty = -5
drop pickpocket
@reload
@dig Shadow Market = shadows, out
shadows
@zone here = bazaar
```

The cutpurse. His tick: choose a mark, roll the contest, then either
lift (an item if the mark carries one, else credits) or get caught —
and the catch *propagates*:

```
@create Fenn
@tag Fenn = npc
drop Fenn
@desc Fenn = Lean, quick-eyed, always somehow just behind your shoulder.
@set Fenn/hp = 8
@set Fenn/max_hp = 8
@set Fenn/skill_pickpocket = 14
@set Fenn/skill_melee = 9
@set Fenn/on_tick = marks = [p for p in contents(here) if has_tag(p, 'player') and not has_tag(p, 'unconscious')]; m = marks[rand(0, len(marks) - 1)] if marks else None; loot = [o for o in contents(m)] if m else []; (((teleport_obj(loot[0], me) if loot else transfer_credits(m, me, 5)), pemit(m, 'A feather-light tug at your belt. Probably nothing.')) if contest(me, 'pickpocket', m, 'observation') else (remit(here, f"{name(m)} catches a hand in their pouch - Fenn's!"), act(here, 'THIEF! The cry goes up.', targeting='room', action_type='event:theft'))) if m else None
@behavior Fenn = script_ticker, interval:3
```

The law: a watch post next door, a constable, and the zone master
whose `ON_THEFT` answers the cry (compare it line for line with item
71's `ON_ATTACK` — same law, new crime):

```
@dig The Watch Post = watchpost, shadows
watchpost
@zone here = bazaar
@create Constable Marsh
@tag Constable Marsh = npc
@tag Constable Marsh = town_watch
@set Constable Marsh/hp = 14
@set Constable Marsh/max_hp = 14
@set Constable Marsh/skill_melee = 13
drop Constable Marsh
@create Bazaar Watch
@zone/master Bazaar Watch = bazaar
@set Bazaar Watch/on_theft = fresh = now() - V('last_cry', 0) > 60; ((set_attr(me, 'last_cry', now()), adjust_disposition('Constable Marsh', enactor, -5), teleport_obj('Constable Marsh', here), force('Constable Marsh', 'say Hold, cutpurse!'), force('Constable Marsh', f'attack {name(enactor)}')) if fresh else None)
drop Bazaar Watch
shadows
```

Inside `ON_THEFT`, `enactor` is whoever fired the act — Fenn — so the
constable arrests the right pair of hands.

## Try it

Carry something worth taking and loiter:

```
@create silver locket
shadows
(a tick or two passes)
→ A feather-light tug at your belt. Probably nothing.
   ...the locket is gone. @examine Fenn: there it sits.
```

Now become a harder mark and let him try again:

```
@set me/skill_observation = 16
(next tick)
→ You catch a hand in their pouch - Fenn's!
  THIEF! The cry goes up.
  Constable Marsh arrives from nowhere: "Hold, cutpurse!" — and takes
  Fenn down. consider Constable Marsh afterwards: the watch remembers
  the thief, not you.
```

One cry per minute (`last_cry`) — a market of screaming victims
dispatches one constable, not a stampede.

## Going further

- **Fencing the goods:** give Fenn item 68's schedule — pickpocket by
  day, walk to a fence NPC at dusk and `give` the haul over; stolen
  property re-enters the economy.
- **Player pickpockets:** the same contest as a `$dip *` command on a
  glove object — with the authority flipped, softcode can't move a
  victim's items for a mere player... which is exactly the design
  question item 160's sneaking answers with skill gates. Try it.
- **Fenn learns:** on a catch, `set_attr(me, 'burned_' + m.id, 1)` and
  skip burned marks — a thief who remembers who caught him.
- **Insurance:** an `ON_THEFT` on the *market room* (witnesses fire
  too, not just zone masters) that logs victims to a claims ledger a
  clerk NPC pays out — one crime event, many listeners.
