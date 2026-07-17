# 135. Injury & Treatment

> Checklist item 135 — [now] — *modifier_effect conditions, check_mods folding, the native firstaid command, self-healing timers*

**What you'll build:** a live power junction that shocks whoever grabs it
into a lingering **injury** — a condition that quietly drags down every
roll they make — plus a diagnostic slate that proves the penalty is real
and a splint kit that treats it. The injury also heals on its own if left
alone: an effect with a clock.

**Concepts:** `apply_effect('modifier_effect', check_mods=…)` as a named
condition, why `skill_check()` folds that penalty into every roll while
`margin_under()` on raw skill would not, the split between **HP loss** and
a **condition** (and thus between the native `firstaid` and a treatment
verb), and an effect's `duration` as a recovery timer.

## How it works

1. **An injury is a condition, not just lost HP.** REALM's timed effects
   (see [059](059_tranquilizer.md), [118](118_bleeding_first_aid.md)) carry
   an optional `check_mods` bag. A `modifier_effect` with
   `check_mods={'all': -3}` tags the victim, applies −3 to their rolls,
   and lifts both when it expires — a seized arm, in one primitive. That
   is separate from `damage()`: a wound can cost you HP *and* leave you
   clumsy, and the two are healed by different verbs.

2. **The penalty only "counts" through `skill_check()`.** When a roll runs
   through the engine's `check()` path — which every `skill_check()`,
   `contest()`, and combat roll does — registered condition modifiers are
   summed in *before* the dice, so −3 fear really is −3 to everything, no
   matter who rolls. But a script that reaches past that and rolls
   `margin_under(roll('3d6'), skill_level)` by hand reads the **raw**
   skill and silently ignores the condition. Field rule: **roll injuries
   with `skill_check()`**, never a hand-rolled margin, or your carefully
   applied penalty evaporates.

3. **Treatment is proximity, not ownership.** `apply_effect`,
   `remove_effect`, and `heal` all work on **proximity** authority — any
   object or medic sharing the patient's room may afflict or mend them, no
   control needed. The junction shocks whoever grabs it; the splint kit
   mends whoever is on the table. (Effects reach from where the *object*
   stands, so both are room fixtures — the [059](059_tranquilizer.md)
   furniture rule.)

4. **Two verbs, two jobs.** The native `firstaid` command restores **HP**
   with a First Aid roll (and revives the unconscious) — but it knows
   nothing about conditions, so a firstaided patient is topped up and
   *still* injured. The splint kit's `$splint` is the other half:
   `remove_effect(t, 'wounded')`. And if nobody treats it, the effect's
   `duration` runs out on its own and the wound knits closed — injuries
   are a timed setback, not a life sentence.

## Build it

The bay, the hazard, and the diagnostic slate that reads a check out loud:

```text
@dig The Med Bay = medbay, out
medbay
@create live junction
drop live junction
@desc live junction = An exposed power coupling, arcing softly. GRIP WIRE if you must -- it will not be gentle.
@set live junction/cmd_grip = $grip wire: (pemit(enactor, 'The coupling is spent for now -- your arm still remembers it.') if has_tag(enactor, 'wounded') else (remit(loc(enactor), name(enactor) + ' grabs the live wire and convulses!'), apply_effect(enactor, 'modifier_effect', kind='wounded', duration=10, check_mods={'all': -3}, apply_msg='Current rips up your arm -- the muscle seizes and will not answer right. (-3 to everything)', expire_msg='Feeling floods back into your arm. The injury has healed.'), damage(enactor, 2)))
@create diagnostic slate
drop diagnostic slate
@desc diagnostic slate = A handheld med-scanner. CHECK <name> to read their motor control.
@set diagnostic slate/cmd_check = $check *: t = get(trim(arg0)); (pemit(enactor, 'No one here by that name.') if not (t and loc(t) == loc(enactor)) else pemit(enactor, name(t) + ': a Melee roll ' + ('SUCCEEDS cleanly.' if skill_check(t, 'melee') else 'FAILS -- the hand is shaking.')))
```

The splint kit — a First Aid roll that clears the condition (and dresses
the last point of the wound):

```text
@create splint kit
drop splint kit
@desc splint kit = A roll of memory-foam splints and a nerve stimulator. SPLINT <name> to treat an injury.
@set splint kit/cmd_splint = $splint *: t = get(trim(arg0)); (pemit(enactor, 'No patient here by that name.') if not (t and loc(t) == loc(enactor)) else (pemit(enactor, 'They have no injury to splint.') if not has_tag(t, 'wounded') else ((remove_effect(t, 'wounded'), heal(t, 1), remit(loc(enactor), name(enactor) + ' braces and binds ' + name(t) + "'s arm. The seizing eases.")) if skill_check(enactor, 'first_aid') else pemit(enactor, 'Your hands slip on the splint -- it will not set.'))))
```

## Try it

Take a jolt, then watch the injury tell on every roll:

```text
check Zeke        -> Zeke: a Melee roll SUCCEEDS cleanly.   (Melee 12, healthy)
grip wire         -> Current rips up your arm...            (-2 HP, tagged wounded)
check Zeke        -> Zeke: a Melee roll FAILS -- the hand is shaking.   (12 - 3 = 9)
```

The −3 folded straight into the Melee roll because `check` rolls through
`skill_check()`. Now treat it — and note that HP and the condition come
apart:

```text
firstaid Zeke     -> You dress Zeke's wounds (...HP).   (native: restores HP)
check Zeke        -> ...FAILS -- the hand is shaking.   (still injured!)
splint Zeke       -> (bad roll) Your hands slip on the splint -- it will not set.
splint Zeke       -> ...braces and binds Zeke's arm. The seizing eases.
check Zeke        -> Zeke: a Melee roll SUCCEEDS cleanly.   (condition cleared)
```

Left untreated instead, the wound clots itself: ten beats after the shock,
`Feeling floods back into your arm.` arrives on its own and the penalty
lifts. Bleeding is pressure ([118](118_bleeding_first_aid.md)); an injury
is friction — both are timers you can beat with a good roll.

## Going further

- **Located wounds:** swap `check_mods={'all': -3}` for `{'guns': -4,
  'melee': -2}` — a mangled trigger finger that spares your footwork.
  Conditions can be as surgical as your skill list.
- **Crippling, not just hindering:** stack a second effect
  `kind='crippled', check_mods={'all': -1}` with a much longer `duration`
  — the sprint heals in beats, the limp in an hour.
- **Infection on a botched splint:** on the `skill_check` failure branch,
  `apply_effect(t, 'damage_over_time', kind='sepsis', interval=4,
  duration=40)` — untreated wounds get worse, and the
  [052](052_poison_dart_trap.md) antidote pattern is the cure.
- **A regen ward while treated:** attach a short `regeneration` effect on a
  successful splint so a bandaged patient recovers HP for a while — the
  medkit afterglow, and the recovery half of [138](138_sleep_rest.md).
