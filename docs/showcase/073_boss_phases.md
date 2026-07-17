# 073. Boss with phases

> Checklist item 73 — [now] — *ON_HITPRCNT, re-armed thresholds, phase telegraphs, minion spawns, strategy swaps*

**What you'll build:** Skarn the Bonewright, a vault-guardian who
fights in three acts. At half health he bellows, raises a bone whelp
into the fight, and turns berserk; at a quarter he goes cornered and
desperate; and his death has last words. No polling, no custom combat
code — one engine hook, re-armed from softcode.
**Concepts:** the `ON_HITPRCNT` hook and its `db.hitprcnt` threshold,
**re-arming the threshold from inside the hook** (one hook, N phases),
phase telegraphs with `remit`, mid-fight minion spawns
(`create_obj` + `start_combat`), swapping `combat_strategy` live, a
self-buff via `apply_effect`, and `ON_DEATH`.

## How it works

**The engine watches the HP line so you don't.** Give any combatant a
`hitprcnt` attribute (a percent) and the combat system fires its
`ON_HITPRCNT` script exactly once as damage carries it *through* that
threshold — not per swing, not on a timer, and never on the killing
blow (that's `ON_DEATH`'s job). `enactor` inside the hook is the
attacker who crossed the line.

**One threshold becomes a phase *machine* by re-arming.** The hook's
own script may `set_attr(me, 'hitprcnt', <next>)` — so phase two's
entrance lowers the tripwire for phase three. A `phase` counter attr
routes each firing to its own named script via `trigger()` (item 68's
dispatcher idiom), keeping each act readable and separately
test-firable with `@tr`.

Each phase then composes three primitives you already have:

- **Telegraph:** `remit(here, ...)` — the classic boss-fight tell,
  loud enough for the whole room.
- **Minions:** `create_obj` a whelp, stat it with `set_attr`, and
  `start_combat(whelp, <a foe>)`. The boss's owner owns what the boss
  creates, so it may throw its own spawn into the fight — the summon
  joins the *same encounter* (one fight per room). Pick the foe by
  scanning the room for an `in_combat` player rather than trusting
  `enactor`: the `trigger()` dispatch re-runs the phase script *as the
  boss*, so `enactor` inside a phase attr is the boss himself — a scan
  also keeps `@tr`-test-firing a phase safe.
- **Behavior change:** NPCs pick combat actions from
  `db.combat_strategy` — an ordered list of `[condition, action]`
  rules (the same engine players' `wimpy` uses). The phase script
  simply *overwrites the list*: berserk is `[["", "attack"]]` plus an
  `apply_effect` self-buff (`check_mods` gives his melee +2 while it
  lasts — proximity authority, item 59); cornered is
  `[["", "defend"]]` behind the whelps. Strategies are data on the
  object, so a phase change is an attribute write.

## Build it

The arena and the boss (from your workroom). Sheet first, then the
tripwire, then the acts:

```
@dig The Undervault = undervault, out
undervault
@create Skarn the Bonewright
@tag Skarn the Bonewright = npc
drop Skarn the Bonewright
@desc Skarn the Bonewright = A hulk of fused bone and bad intent. Something in him is still counting.
@set Skarn the Bonewright/hp = 20
@set Skarn the Bonewright/max_hp = 20
@set Skarn the Bonewright/skill_melee = 12
@set Skarn the Bonewright/dodge = 5
@set Skarn the Bonewright/combat_strategy = [["", "attack"]]
@set Skarn the Bonewright/hitprcnt = 50
@set Skarn the Bonewright/on_hitprcnt = trigger('phase_two' if V('phase', 1) == 1 else 'phase_three')
```

Act two — telegraph, whelp, re-arm to 25, go berserk:

```
@set Skarn the Bonewright/phase_two = set_attr(me, 'phase', 2); set_attr(me, 'hitprcnt', 25); remit(here, 'Skarn slams both fists to the floor. BONES OF THE DEEP - RISE!'); w = create_obj('bone whelp', tags=['npc'], location=here); set_attr(w, 'hp', 6); set_attr(w, 'max_hp', 6); set_attr(w, 'skill_melee', 10); set_attr(w, 'combat_strategy', [['', 'attack']]); foes = [p for p in contents(here) if has_tag(p, 'player') and has_tag(p, 'in_combat')]; (start_combat(w, foes[0]) if foes else None); apply_effect(me, 'modifier_effect', kind='berserk', duration=100, check_mods={'melee': 2})
```

Act three — cornered: telegraph and turtle behind the whelp:

```
@set Skarn the Bonewright/phase_three = set_attr(me, 'phase', 3); remit(here, 'Cracks spider across Skarn. He gives ground, guarding the wound.'); set_attr(me, 'combat_strategy', [["", "defend"]])
```

The curtain line:

```
@set Skarn the Bonewright/on_death = remit(here, 'Skarn comes apart at the seams, whispering: the vault... was never... mine...')
```

## Try it

Bring a sheet that can go the distance:

```
@set me/hp = 40
@set me/max_hp = 40
@set me/skill_melee = 13
attack Skarn the Bonewright
```

Trade blows. As he crosses half health, mid-fight:

```
Skarn slams both fists to the floor. BONES OF THE DEEP - RISE!
(a bone whelp joins the fight against you; Skarn hits harder — the
berserk buff is +2 melee while it lasts)
```

`@examine Skarn the Bonewright` right now: `phase: 2`,
`hitprcnt: 25` — the machine re-armed itself. Keep swinging; through a
quarter health:

```
Cracks spider across Skarn. He gives ground, guarding the wound.
(his strategy is now defend — your hits start glancing off a guard
while the whelp keeps at you)
```

And down:

```
Skarn comes apart at the seams, whispering: the vault... was never... mine...
(a lootable corpse remains — and the kill pays character points:
check `points`)
```

Each act is separately testable while building: `@tr Skarn the
Bonewright/phase_two` fires it cold (mind that it spawns a real whelp).

## Going further

- **More acts:** re-arm again in `phase_three`
  (`set_attr(me, 'hitprcnt', 10)`) and route a fourth script — the
  hook fires once per crossing, so the ladder is as long as you like.
- **Heal-based resets:** if something heals him back above a spent
  threshold, it can fire again on the way back down — for a
  regenerating boss (the `regeneration` effect), phases become a
  tide, not a ladder.
- **Enrage timers:** pair with `script_ticker` — an `on_tick` that
  counts rounds and hard-enrages at twenty ticks keeps speed-kills
  honest.
- **Terrain acts:** phase two could `close()` the exit
  (`cmd('close vault door')`) and phase three reopen it — boss
  phases that reshape the arena, not just the sheet.
- **A proper horde:** `phase_three` spawning two whelps with a loop
  (`[... for i in [1, 2]]`) — sandbox comprehensions make N-summons
  one expression.
