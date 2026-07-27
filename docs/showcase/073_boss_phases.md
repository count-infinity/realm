# 073. Boss with phases

> Checklist item 73 ([now]): *ON_HITPRCNT, re-armed thresholds, phase telegraphs, minion spawns, strategy swaps*

**What you'll build:** Skarn the Bonewright, a vault guardian who fights in three
acts. At half health he bellows, raises a bone whelp into the fight, and turns
berserk; at a quarter he goes cornered and desperate; and his death has last
words. There is no polling and no custom combat code, just one engine hook that
re-arms itself from softcode.

**Concepts:** the [`ON_HITPRCNT`](../reference/softcode.md#lifecycle-hooks) hook
and its `db.hitprcnt` threshold, re-arming that threshold from inside the hook
(one hook, N phases), phase telegraphs with
[`remit`](../reference/softcode.md#fn-remit), mid-fight minion spawns
([`create_obj`](../reference/softcode.md#fn-create_obj) plus
[`start_combat`](../reference/softcode.md#fn-start_combat)), swapping
`combat_strategy` live, a self-buff via
[`apply_effect`](../reference/softcode.md#fn-apply_effect), and
[`ON_DEATH`](../reference/softcode.md#lifecycle-hooks).

## How it works

The finished boss is one combatant carrying a small state machine. The engine
watches his HP line and fires a single hook each time damage carries him through
a set percentage; that hook reads a `phase` counter off his own sheet and routes
to the act for that crossing, and each act re-arms the threshold lower so the
next crossing routes one act further on. Four questions carry the whole build:
how the engine tells you HP crossed a line, how one hook becomes a machine, why
the hook needs a guard, and what an act is made of.

### How the boss knows his HP crossed a line

Give any combatant a `hitprcnt` attribute (a percent) and the combat system
fires its [`ON_HITPRCNT`](../reference/softcode.md#lifecycle-hooks) hook exactly
once as damage carries the HP *through* that threshold. It does not fire per
swing, it does not fire on a timer, and it does not fire on the killing blow,
which is [`ON_DEATH`](../reference/softcode.md#lifecycle-hooks)'s job instead.
Inside the hook `enactor` is the attacker who crossed the line, and the crossing
carries a payload you can read with
[`adata`](../reference/softcode.md#event-data-namespace): `adata('percent')` is
the HP percent he landed on and `adata('threshold')` the line he crossed.

### How one threshold becomes a phase machine

The hook re-arms itself. Its script may call
[`set_attr`](../reference/softcode.md#fn-set_attr)`(me, 'hitprcnt', <next>)`, so
act two's entrance lowers the tripwire for act three. A `phase` counter on the
boss records which act he is in, and the hook reads it with
[`V`](../reference/softcode.md#fn-v)`('phase', 1)` (shorthand for
[`get_attr`](../reference/softcode.md#fn-get_attr)`(me, 'phase', 1)`) to route
each firing to its own named script. The routing is an ordinary if/elif ladder
on that counter, and the act is fired with the `trigger` script command, the
same dispatcher idiom the [NPC schedule](068_npc_schedule.md) uses to route its
hours. Keeping each act in its own named attribute is deliberate: a plain
attribute can be fired cold with `@tr` while you build, whereas a `$`-command
trigger only matches typed input and `@tr` cannot fire one.

### Why the hook needs a guard

An [`ON_HITPRCNT`](../reference/softcode.md#lifecycle-hooks) fires on *every*
object in the room, not only on the combatant who crossed the line (events are
heard by the whole room, see
[Guard on `target`](../reference/softcode.md#guard-on-target)). So the hook opens
with `if target is me:`, where `target` is the combatant the crossing belongs to
and `me` is the object running the hook. Without that line, a second Skarn
standing in the same vault would advance his own phase counter every time the
first Skarn dropped through a threshold. Write `is`, not `==`: it is an identity
check, and the sandbox interns objects so identity holds.

### What one act is made of

Each act composes three primitives you already have:

- **Telegraph.** [`remit`](../reference/softcode.md#fn-remit)`(here, ...)` prints
  a line loud enough for the whole room, the classic boss-fight tell.
- **Minions.** [`create_obj`](../reference/softcode.md#fn-create_obj) mints a
  whelp, [`set_attr`](../reference/softcode.md#fn-set_attr) stats it, and
  [`start_combat`](../reference/softcode.md#fn-start_combat)`(whelp, <a foe>)`
  throws it in. The boss's owner owns what the boss creates, so he may commit his
  own spawn to the fight, and the summon joins the *same* encounter because there
  is one fight per room. Pick the foe by scanning the room's
  [`contents`](../reference/softcode.md#fn-contents) for an `in_combat` player
  rather than trusting `enactor`. The `trigger` dispatch re-runs the act script
  *as the boss*, so `enactor` inside an act is the boss himself, and a room scan
  also keeps `@tr`-firing an act safe while you build.
- **Behavior change.** NPCs pick combat actions from `db.combat_strategy`, an
  ordered list of `[condition, action]` rules (the same engine a player's
  `wimpy` writes). An act simply overwrites the list: berserk is
  `[["", "attack"]]` plus an
  [`apply_effect`](../reference/softcode.md#fn-apply_effect) self-buff, where
  `check_mods` gives his melee +2 for the duration (proximity authority, the
  effect road the [tranquilizer](059_tranquilizer.md) travels); cornered is
  `[["", "defend"]]` behind the whelp. Strategies are data on the object, so a
  behavior change is an attribute write.

## Build it

Dig the arena from your workroom, step in, and create the boss. Tag him `npc`,
drop him so he stands in the room, and give him a face:

```text
@dig The Undervault = undervault, out
undervault
@create Skarn the Bonewright
@tag Skarn the Bonewright = npc
drop Skarn the Bonewright
@desc Skarn the Bonewright = A hulk of fused bone and bad intent. Something in him is still counting.
```

Now his combat sheet: hit points, a melee skill and dodge, and a starting
strategy of plain attack:

```text
@set Skarn the Bonewright/hp = 20
@set Skarn the Bonewright/max_hp = 20
@set Skarn the Bonewright/skill_melee = 12
@set Skarn the Bonewright/dodge = 5
@set Skarn the Bonewright/combat_strategy = [["", "attack"]]
```

The tripwire and the dispatcher. Arm the first threshold at 50 percent, then set
the hook that fires when HP crosses it. The guard runs first; the if/elif ladder
reads the `phase` counter and fires the act for this crossing:

```text
@set Skarn the Bonewright/hitprcnt = 50
@set Skarn the Bonewright/on_hitprcnt = '''
if target is me:  # ON_HITPRCNT fires on every object in the room, so guard it
    phase = V('phase', 1)
    if phase == 1:
        trigger('phase_two')
    elif phase == 2:
        trigger('phase_three')
'''
```

Act two is the loud one. It stamps the phase, re-arms the threshold down to 25
percent, telegraphs, raises a bone whelp and throws it at whoever is already
fighting him, then buffs his own melee:

```text
@set Skarn the Bonewright/phase_two = '''
set_attr(me, 'phase', 2)
set_attr(me, 'hitprcnt', 25)  # re-arm: lower the tripwire for act three
remit(here, 'Skarn slams both fists to the floor. BONES OF THE DEEP - RISE!')
w = create_obj('bone whelp', tags=['npc'], location=here)
set_attr(w, 'hp', 6)
set_attr(w, 'max_hp', 6)
set_attr(w, 'skill_melee', 10)
set_attr(w, 'combat_strategy', [['', 'attack']])
foes = [p for p in contents(here) if has_tag(p, 'player') and has_tag(p, 'in_combat')]
if foes:  # enactor here is the boss, so scan for the real foe instead
    start_combat(w, foes[0])
apply_effect(me, 'modifier_effect', kind='berserk', duration=100, check_mods={'melee': 2})
'''
```

Act three is the turn inward. It stamps the phase, telegraphs the crack, and
swaps the strategy to defend so he turtles behind the whelp:

```text
@set Skarn the Bonewright/phase_three = '''
set_attr(me, 'phase', 3)
remit(here, 'Cracks spider across Skarn. He gives ground, guarding the wound.')
set_attr(me, 'combat_strategy', [["", "defend"]])
'''
```

The curtain line is a single statement, so it stays a one-liner. `ON_DEATH`
fires on the killing blow, which `ON_HITPRCNT` never sees:

```text
@set Skarn the Bonewright/on_death = remit(here, 'Skarn comes apart at the seams, whispering: the vault... was never... mine...')
```

## Try it

Bring a sheet that can go the distance, then start the fight:

```text
> @set me/hp = 40
> @set me/max_hp = 40
> @set me/skill_melee = 13
> attack Skarn the Bonewright
You attack Skarn the Bonewright!
```

Trade blows. As he crosses half health, mid-fight, the first act fires:

```text
Skarn slams both fists to the floor. BONES OF THE DEEP - RISE!
(a bone whelp joins the fight against you; Skarn hits harder, the
berserk buff is +2 melee while it lasts)
```

Run `@examine Skarn the Bonewright` right now and you see `phase: 2` and
`hitprcnt: 25`: the machine re-armed itself. Keep swinging, and through a quarter
health the second act fires:

```text
Cracks spider across Skarn. He gives ground, guarding the wound.
(his strategy is now defend, so your hits start glancing off a guard
while the whelp keeps at you)
```

And down:

```text
Skarn comes apart at the seams, whispering: the vault... was never... mine...
(a lootable corpse remains, and the kill pays character points:
check points)
```

Each act is separately testable while you build: `@tr Skarn the
Bonewright/phase_two` fires it cold, though mind that it spawns a real whelp.

## Going further

- **More acts:** re-arm again inside `phase_three`
  (`set_attr(me, 'hitprcnt', 10)`) and add an `elif phase == 3: trigger('phase_four')`
  rung to the dispatcher. The hook fires once per crossing, so the ladder is as
  long as you like.
- **Quote the crossing:** the telegraph can name the number. Put
  `remit(here, f"Skarn reels at {adata('percent')}%!")` in the hook itself, where
  the live crossing is bound. This build routes on the `phase` counter rather
  than on `adata` deliberately: the counter is real state you can `@examine` and
  re-fire cold with `@tr`, whereas `adata` only exists inside a live crossing and
  reads empty in an act fired by `trigger`.
- **Heal-based resets:** if something heals him back above a spent threshold, it
  can fire again on the way back down. For a regenerating boss (the
  `regeneration` effect), phases become a tide, not a ladder.
- **Enrage timers:** pair with a `script_ticker` whose `on_tick` counts rounds
  and hard-enrages at twenty ticks, which keeps speed-kills honest.
- **Terrain acts:** act two could `close` the exit (`cmd('close vault door')`)
  and act three reopen it, boss phases that reshape the arena and not just the
  sheet.
- **A proper horde:** have `phase_three` spawn two whelps with a comprehension
  (`[create_obj('bone whelp', tags=['npc'], location=here) for i in [1, 2]]`), so
  an N-summon is one expression.
