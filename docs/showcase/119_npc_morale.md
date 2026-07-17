# 119. NPC morale

> Checklist item 119 — [now] — *ON_HITPRCNT behavior swaps, fleeing behavior, dispositions*

**What you'll build:** A raider who fights like a wolf until she is
hurt — then checks her nerve. Break it and she throws down her weapon
and surrenders (and *likes you better* for sparing her); hold it and
she bolts for the door on the next beat. One attribute is the whole
morale system.

**Concepts:** `ON_HITPRCNT` as the low-HP AI seam, behavior swapping
(`detach_behavior('aggressive')` / `attach_behavior('fleeing')`),
combat strategies as data (`combat_strategy`), surrender as a
disposition change, and a morale check that is just a `skill_def`.

## How it works

1. **`ON_HITPRCNT` is the morale trigger.** Give any creature a
   `hitprcnt` attribute (a percent) and the engine fires its
   `ON_HITPRCNT` softcode exactly **once**, the moment a wound drives
   its HP down through that threshold — no polling, no per-tick checks,
   and the attacker arrives as `enactor`. The NPC executes its own
   hook, so it has full authority over itself: its behaviors, its
   strategy, its tags, its own opinions.

2. **The morale roll is data.** `skill_check(me, 'nerve')` against a
   `nerve` skill_def built on Health — a steady veteran holds, a
   sickly cutpurse folds. Same one-object-plus-`@reload` trick as every
   skill in this arc.

3. **Broken: surrender.** `detach_behavior(me, 'aggressive')` removes
   the brain that started the fight (so she never re-engages on sight),
   the strategy list becomes `[['', 'wait']]` — strategies are the
   NPC's combat policy, and *wait every beat* is what "hands up" means
   mechanically — a `surrendered` tag marks her for other systems, and
   `adjust_disposition(me, enactor, 5)` is the interesting one: the
   NPC's opinion of her captor jumps. Disposition is persistent,
   readable by `consider`, and gates the built-in guard/shopkeeper
   behaviors — mercy has mechanical weight.

4. **Held: flight.** `attach_behavior(me, 'fleeing', flee_percent=99)`
   — the registered coward's-reflex behavior, which writes the
   *override* strategy rule `!me.hp_percent < 99 → flee` (the same rule
   `wimpy` writes for players; the `!` means it preempts even a queued
   action). Next beat she rolls the engine's flee check and is gone
   through an open exit, dragging the fight's end with her.

One honest limit, reported as a gap: the encounter has no
yield/stop primitive (by design, v1), so a surrendered NPC **stays
enrolled** — beats keep firing with her waiting — until the player
stops it: walk away (`flee`), knock her out (item 112's cosh), or
finish it anyway. Surrender changes behavior, not encounter
membership.

## Build it

The lair, the nerve skill, the raider:

```text
@dig Raider Lair = lair, out
lair
@create nerve
@tag nerve = skill_def
@set nerve/stat = health
@set nerve/penalty = 0
@reload
@create Vex
@tag Vex = npc
@set Vex/hp = 12
@set Vex/max_hp = 12
@set Vex/skill_melee = 12
@set Vex/dodge = 0
@set Vex/health = 8
@set Vex/dexterity = 14
drop Vex
@behavior Vex = aggressive, taunt:"Your boots -- I want them."
```

The morale system, entire:

```text
@set Vex/hitprcnt = 50
@set Vex/on_hitprcnt = detach_behavior(me, 'aggressive'); (say('I yield! I yield -- the loot is yours, only stop!'), set_attr(me, 'combat_strategy', [['', 'wait']]), add_tag(me, 'surrendered'), adjust_disposition(me, enactor, 5)) if not skill_check(me, 'nerve') else (say('Not like this!'), attach_behavior(me, 'fleeing', flee_percent=99))
```

Health 8 means Vex's nerve is glass — she will fold. For the brave
version, raise it:

```text
@set Vex/health = 13
```

## Try it

Walk in. Vex engages on sight ("Your boots -- I want them.") and the
beats start. Trade blows until she crosses half HP:

```text
Vex says, "I yield! I yield -- the loot is yours, only stop!"
```

From then on she waits every beat — swing or sheathe, your call — and
`consider Vex` shows her opinion of you warmed by five. She will not
re-engage if you leave and return: the aggressive brain is gone, not
suppressed.

With `health = 13` instead:

```text
Vex says, "Not like this!"
(next beat) Vex flees out!
```

— the fleeing behavior's override rule won the beat, the engine rolled
her flee check (DX-based), and the lair is yours.

**Engine gap (reported):** no yield/leave-combat primitive — softcode
can make an NPC *behave* surrendered (strategy = wait) but cannot
remove it from the encounter, so the fight formally continues until
defeat, flight, or the room empties. A `yield()`/`stop_combat()`
softcode verb (or a `surrendered`-tag check in the encounter's
continue rule) would close it.

## Going further

- **Group morale** — put the `ON_HITPRCNT` on a pack leader that
  `force()`s every same-owner packmate to flee when *it* breaks: rout,
  not retreat.
- **Ransom** — a surrendered (`surrendered`-tagged) NPC with an
  `ON_PAYMENT`: pay her 20 credits and she `say`s where the stash is —
  mercy plus greed as a quest surface.
- **Rally** — a second threshold (`hitprcnt` re-arms if HP climbs back
  above it): a healed raider whose nerve check *passes* re-attaches
  `aggressive` — morale swings both ways.
- **Fear the winner** — on surrender, also
  `apply_effect(me, 'modifier_effect', kind='cowed', duration=100,
  check_mods={'all': -2})`: a broken fighter fights worse if forced
  back into it.
