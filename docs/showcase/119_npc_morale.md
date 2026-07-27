# 119. NPC morale

> Checklist item 119 ([now]): *ON_HITPRCNT behavior swaps, fleeing behavior, dispositions*

**What you'll build:** a raider who fights like a wolf until she is hurt, then
checks her nerve. Break it and she throws down her weapon and surrenders (and
likes you better for sparing her); hold it and she bolts for the door on the
next beat. One attribute is the whole morale system.

**Concepts:** [`ON_HITPRCNT`](../reference/softcode.md#lifecycle-hooks) as the
low-HP hook, behavior swapping
([`detach_behavior`](../reference/softcode.md#fn-detach_behavior) /
[`attach_behavior`](../reference/softcode.md#fn-attach_behavior)), combat
strategies as data (`combat_strategy`), surrender as a disposition change, and a
morale check that is just a skill_def.

## How it works

An NPC crosses a low-HP line, its own softcode runs on the spot, and one skill
check decides whether it surrenders or runs. This section answers four
questions: what fires the check, how the roll is expressed as data, what
surrender does to the creature, and how flight is handed to the same engine that
runs player automation.

1. **`ON_HITPRCNT` is the morale trigger.** Give any creature a `hitprcnt`
   attribute (a percent) and the engine fires its
   [`ON_HITPRCNT`](../reference/softcode.md#lifecycle-hooks) softcode exactly
   once, the moment a wound drives its HP down through that threshold, with no
   polling and no per-tick checks. The attacker arrives as `enactor` and the
   wounded creature as `target`, and the hook carries its own numbers:
   [`adata('percent')`](../reference/softcode.md#event-data-namespace) is where
   the HP actually landed (a big hit through a 50 percent threshold can overshoot
   and leave her on 31) and `adata('threshold')` is the line she crossed. Like
   every `ON_<EVENT>` hook this one fires on every object in the room, so the
   body opens with [`if target is me:`](../reference/softcode.md#guard-on-target)
   and reacts only to its own wound. Inside that guard she first removes her
   `aggressive` behavior with `detach_behavior(me, 'aggressive')` so she never
   re-engages on sight, then her nerve check decides what happens next.

2. **The morale roll is data.**
   [`skill_check(me, 'nerve')`](../reference/softcode.md#fn-skill_check) rolls
   against a `nerve` skill_def built on Health, so a steady veteran holds and a
   sickly cutpurse folds. It is the same one-object-plus-`@reload` trick as every
   skill in this arc.

3. **Broken: surrender.** When the nerve check fails she yields. The strategy
   list becomes `[['', 'wait']]`, and because an empty condition means "always",
   "wait every beat" is what "hands up" means mechanically. A `surrendered` tag
   marks her for other systems, and
   [`adjust_disposition(me, enactor, 5)`](../reference/softcode.md#fn-adjust_disposition)
   raises the NPC's opinion of her captor.
   [Disposition](../reference/softcode.md#fn-disposition) is persistent, readable
   by `consider`, and gates the built-in guard behavior (see the
   [guarded exit](031_guarded_exit.md) and the
   [aggressive mob](062_aggressive_mob.md)), so mercy has mechanical weight.

4. **Held: flight.** When the check passes she runs instead.
   `attach_behavior(me, 'fleeing', flee_percent=99)` attaches the registered
   coward's-reflex behavior, which writes the override strategy rule
   `["!me.hp_percent < 99", "flee"]` (the same rule `wimpy` writes for players;
   the leading `!` marks it an override that preempts even a queued action). On
   the next beat she rolls the engine's flee check, which is dexterity-based, and
   is gone through an open exit.

One honest limit, reported as a gap below: the encounter has no yield or stop
primitive (by design, v1), so a surrendered NPC stays enrolled, with beats still
firing while she waits, until the player ends it: walk away (`flee`), knock her
out ([item 112's cosh](112_nonlethal_takedowns.md)), or finish it anyway.
Surrender changes behavior, not encounter membership.

## Build it

Dig the lair and step inside. It has one exit, `out`, which is the door she will
run for later:

```text
@dig Raider Lair = lair, out
lair
```

Build the `nerve` skill_def on Health, tag it, and `@reload` so the engine
registers it as a skill. A skill_def is one object that every `skill_check`
against that name consults:

```text
@create nerve
@tag nerve = skill_def
@set nerve/stat = health
@set nerve/penalty = 0
@reload
```

Create Vex and give her a fighting sheet. Health 8 means her nerve is glass, so
she will fold; the `aggressive` behavior makes her engage on sight, and its
`taunt` is the line she says as she does:

```text
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

Set the morale threshold. `hitprcnt` is a percent, so 50 fires the hook the
first beat a wound takes her under half:

```text
@set Vex/hitprcnt = 50
```

Now the morale system itself, written as a block so the guard and the branch
read plainly. The `if target is me:` line is not optional: `ON_HITPRCNT` fires on
every object in the room, so without it a second wounded raider standing nearby
would trip Vex's morale off its own wound:

```text
@set Vex/on_hitprcnt = '''
if target is me:
    # she drops the aggressive brain either way, so she never re-engages on sight
    detach_behavior(me, 'aggressive')
    if skill_check(me, 'nerve'):
        say('Not like this!')
        attach_behavior(me, 'fleeing', flee_percent=99)
    else:
        say('I yield! I yield -- the loot is yours, only stop!')
        # an empty condition always matches, so she waits every beat: hands up
        set_attr(me, 'combat_strategy', [['', 'wait']])
        add_tag(me, 'surrendered')
        adjust_disposition(me, enactor, 5)
'''
```

## Try it

Walk in. Vex engages on sight and the beats start. Trade blows until she crosses
half HP:

```text
> lair
  Vex says, "Your boots -- I want them."
  (you are now in combat)
> attack Vex
> (beats pass: 12 -> 9 -> 6)
  Vex says, "I yield! I yield -- the loot is yours, only stop!"
```

From then on she waits every beat, so swing or sheathe as you like, and
`consider Vex` shows her opinion of you warmed by five. She will not re-engage if
you leave and return, because the aggressive brain is gone, not suppressed:

```text
> consider Vex
  Vex regards you with open gratitude.
> queue wait
  (the fight continues, but she only waits)
```

For the brave version, raise her Health and run it again. At Health 13 her nerve
holds, so she flees instead of yielding:

```text
> @set Vex/health = 13
> lair
> attack Vex
> (beats pass: crosses 50%, nerve holds)
  Vex says, "Not like this!"
> (next beat: the override rule wins)
  Vex flees out!
```

The fleeing behavior's override rule won the beat, the engine rolled her
dexterity-based flee check, and the lair is yours.

**Engine gap (reported):** there is no yield or leave-combat primitive. Softcode
can make an NPC behave as surrendered (strategy set to wait) but cannot remove
her from the encounter, so the fight formally continues until defeat, flight, or
the room empties. A `yield()` or `stop_combat()` softcode verb, or a
`surrendered`-tag check in the encounter's continue rule, would close it.

## Going further

- **Group morale.** Put the `ON_HITPRCNT` on a pack leader that
  [`force`](../reference/softcode.md#fn-force)s every same-owner packmate to flee
  when it breaks: a rout, not a retreat.
- **Ransom.** A surrendered (`surrendered`-tagged) NPC with an `ON_PAYMENT`: pay
  her 20 credits and she `say`s where the stash is, so mercy plus greed becomes a
  quest surface.
- **Rally.** A second threshold (`hitprcnt` re-arms if HP climbs back above it):
  a healed raider whose nerve check passes re-attaches `aggressive`, so morale
  swings both ways.
- **Graded nerve.** `skill_check(me, 'nerve')` is pass or fail, but
  `adata('percent')` says how bad it looks from where she is standing. Feed it
  back as a penalty, `skill_check(me, 'nerve', (adata('percent', 50) - 50) //
  10)`, and a raider dropped straight to 10 percent folds far harder than one who
  bleeds gently past 49.
- **Fear the winner.** On surrender, also
  [`apply_effect`](../reference/softcode.md#fn-apply_effect)`(me,
  'modifier_effect', kind='cowed', duration=100, check_mods={'all': -2})`: a
  broken fighter fights worse if forced back into it.
