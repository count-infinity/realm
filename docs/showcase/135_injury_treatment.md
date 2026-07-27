# 135. Injury & Treatment

> Checklist item 135 ([now]): *modifier_effect wound conditions, check_mods folding into skill_check, the native firstaid command, self-healing recovery timers*

**What you'll build:** a live power junction that shocks whoever grabs it
into a lingering **injury**, a condition that quietly drags down every roll
they make, plus a diagnostic slate that proves the penalty is real and a
splint kit that treats it. The injury also heals on its own if left alone,
because it is an effect with a clock.

**Concepts:**
[`apply_effect`](../reference/softcode.md#fn-apply_effect)`('modifier_effect',
check_mods=...)` as a named condition, why
[`skill_check`](../reference/softcode.md#fn-skill_check) folds that penalty
into every roll while
[`margin_under`](../reference/softcode.md#fn-margin_under) on raw skill would
not, the split between HP loss and a condition (and thus between the native
`firstaid` and a treatment verb), and an effect's `duration` as a recovery
timer.

## How it works

The finished bay holds three room fixtures: a junction that afflicts whoever
grips it, a slate that reads a roll out loud so you can watch the penalty
bite, and a kit that clears the condition. The wound is one primitive, a
timed effect carrying a check-modifier bag, so this section answers four
questions: why an injury is a condition rather than just lost HP, why the
penalty counts only when a roll goes through the check pipeline, who is
allowed to afflict and mend, and why two different verbs treat the two
halves of a wound.

### Why an injury is a condition, not just lost HP

REALM's timed effects (see the [tranquilizer](059_tranquilizer.md) and
[bleeding first aid](118_bleeding_first_aid.md)) carry an optional
`check_mods` bag. A `modifier_effect` with `check_mods={'all': -3}` does three
things at once when [`apply_effect`](../reference/softcode.md#fn-apply_effect)
attaches it: it mirrors its `kind` as a
[`has_tag`](../reference/softcode.md#fn-has_tag)-readable tag on the victim,
it writes its entry into the victim's `check_mods` so `-3` folds into their
rolls, and it lifts both again when it expires. That is a seized arm in one
primitive, and it is separate from
[`damage`](../reference/softcode.md#fn-damage): a wound can cost you HP *and*
leave you clumsy, and the two are healed by different verbs.

### Why the penalty counts only through a real check

When a roll runs through the engine's check pipeline, which every
[`skill_check`](../reference/softcode.md#fn-skill_check),
[`contest`](../reference/softcode.md#fn-contest), and combat roll does, every
registered condition modifier is summed in *before* the resolver sees the
dice. So a `-3` injury really is `-3` to everything, no matter who rolls or
which ruleset resolves. But a script that reaches past that pipeline and
rolls [`margin_under`](../reference/softcode.md#fn-margin_under)`(roll('3d6'),
get_attr(t, 'skill_melee', 10))` by hand reads the **raw** trained level and
silently ignores the condition, so a wounded fighter would roll as if
healthy. The field rule is to roll injuries with `skill_check`, never a
hand-rolled margin, or the carefully applied penalty evaporates. The
diagnostic slate below uses `skill_check` for exactly this reason.

### Who is allowed to afflict and mend

Treatment is proximity, not ownership.
[`apply_effect`](../reference/softcode.md#fn-apply_effect),
[`remove_effect`](../reference/softcode.md#fn-remove_effect), and
[`heal`](../reference/softcode.md#fn-heal) all work on proximity authority, so
any object or medic sharing the patient's room may afflict or mend them with
no control needed. The junction shocks whoever grabs it and the splint kit
mends whoever is in the room. Effects reach from where the *object* stands, so
both stay dropped as room fixtures rather than carried, the same furniture
rule the [tranquilizer](059_tranquilizer.md) follows.

### Why two verbs treat one wound

The native `firstaid` command restores HP with a First Aid roll and revives
an unconscious patient, but it knows nothing about conditions, so a
firstaided patient is topped up and *still* injured. The splint kit's
`$splint` is the other half: a First Aid roll that, on success, calls
[`remove_effect`](../reference/softcode.md#fn-remove_effect)`(t, 'wounded')` to
strip the condition (and presses in the last point of the wound with
`heal`). And if nobody treats it, the effect's `duration` runs out on its own
and the wound knits closed, because an injury is a timed setback rather than
a life sentence.

## Build it

Dig the bay, step in, then stand up the junction and give it a warning face:

```text
@dig The Med Bay = medbay, out
medbay
@create live junction
drop live junction
@desc live junction = An exposed power coupling, arcing softly. GRIP WIRE if you must -- it will not be gentle.
```

The junction's `$grip wire` command refuses an already-wounded arm, and
otherwise announces the shock to the room, attaches the injury, and takes two
points of HP. The `kind='wounded'` mirrors as the `wounded` tag and the
`check_mods` bag folds `-3` into every skill check for the effect's ten beats:

```text
@set live junction/cmd_grip = '''
$grip wire:
if has_tag(enactor, 'wounded'):
    pemit(enactor, 'The coupling is spent for now -- your arm still remembers it.')
else:
    remit(loc(enactor), name(enactor) + ' grabs the live wire and convulses!')
    # kind mirrors as the 'wounded' tag; check_mods folds -3 into every skill_check for duration beats
    apply_effect(enactor, 'modifier_effect', kind='wounded', duration=10, check_mods={'all': -3}, apply_msg='Current rips up your arm -- the muscle seizes and will not answer right. (-3 to everything)', expire_msg='Feeling floods back into your arm. The injury has healed.')
    damage(enactor, 2)
'''
```

Create the diagnostic slate and set it down so it shares the room with its
subjects:

```text
@create diagnostic slate
drop diagnostic slate
@desc diagnostic slate = A handheld med-scanner. CHECK <name> to read their motor control.
```

The slate's `$check` command finds the named subject with
[`get`](../reference/softcode.md#fn-get) and
[`trim`](../reference/softcode.md#fn-trim), refuses a name that is not in the
room, then rolls their Melee through `skill_check` so any active condition
folds in. The result is reported privately with
[`pemit`](../reference/softcode.md#fn-pemit):

```text
@set diagnostic slate/cmd_check = '''
$check *:
t = get(trim(arg0))
if not (t and loc(t) is loc(enactor)):
    pemit(enactor, 'No one here by that name.')
elif skill_check(t, 'melee'):
    pemit(enactor, name(t) + ': a Melee roll SUCCEEDS cleanly.')
else:
    pemit(enactor, name(t) + ': a Melee roll FAILS -- the hand is shaking.')
'''
```

Create the splint kit and drop it in the bay too:

```text
@create splint kit
drop splint kit
@desc splint kit = A roll of memory-foam splints and a nerve stimulator. SPLINT <name> to treat an injury.
```

The kit's `$splint` command refuses a name not in the room and a patient with
no injury, then rolls the medic's own First Aid with `skill_check`. On a
success it strips the condition with `remove_effect`, presses in one point
with [`heal`](../reference/softcode.md#fn-heal), and announces it to the room
with [`remit`](../reference/softcode.md#fn-remit); on a failure it reports
privately and the splint does not set:

```text
@set splint kit/cmd_splint = '''
$splint *:
t = get(trim(arg0))
if not (t and loc(t) is loc(enactor)):
    pemit(enactor, 'No patient here by that name.')
elif not has_tag(t, 'wounded'):
    pemit(enactor, 'They have no injury to splint.')
elif skill_check(enactor, 'first_aid'):
    remove_effect(t, 'wounded')  # strips the effect: the 'wounded' tag and its check_mods entry both lift
    heal(t, 1)
    remit(loc(enactor), name(enactor) + ' braces and binds ' + name(t) + "'s arm. The seizing eases.")
else:
    pemit(enactor, 'Your hands slip on the splint -- it will not set.')
'''
```

## Try it

Take a jolt, then watch the injury tell on every roll:

```text
> check Zeke
Zeke: a Melee roll SUCCEEDS cleanly.        (Melee 12, healthy)

> grip wire
Zeke grabs the live wire and convulses!
Current rips up your arm -- the muscle seizes and will not answer right. (-3 to everything)
                                            (-2 HP, tagged wounded)

> check Zeke
Zeke: a Melee roll FAILS -- the hand is shaking.   (12 - 3 = 9)
```

The `-3` folded straight into the Melee roll because `check` goes through
`skill_check`. Now treat it, and note that HP and the condition come apart.
The native `firstaid` tops up HP but leaves the injury; only the splint kit
clears the condition, and only on a good First Aid roll (so the first splint
line varies with the medic):

```text
> firstaid Zeke
You dress Zeke's wounds (2 HP).             (native: restores HP only)

> check Zeke
Zeke: a Melee roll FAILS -- the hand is shaking.   (still injured)

> splint Zeke         (weak First Aid)
Your hands slip on the splint -- it will not set.

> splint Zeke         (strong First Aid)
Mara braces and binds Zeke's arm. The seizing eases.

> check Zeke
Zeke: a Melee roll SUCCEEDS cleanly.        (condition cleared)
```

Left untreated instead, the wound clots itself: ten beats after the shock,
`Feeling floods back into your arm. The injury has healed.` arrives on its
own and the penalty lifts. Bleeding is pressure
([118](118_bleeding_first_aid.md)); an injury is friction, and both are
timers you can beat with a good roll.

## Going further

- **Located wounds:** swap `check_mods={'all': -3}` for `{'guns': -4, 'melee':
  -2}`, a mangled trigger finger that spares your footwork. The provider sums
  each entry's `'all'` and per-skill values, so conditions can be as surgical
  as your skill list.
- **Crippling, not just hindering:** apply a second effect with
  `kind='crippled', check_mods={'all': -1}` and a much longer `duration`.
  Because effects are singletons per kind, the two coexist and their modifiers
  add, so the sprint heals in beats while the limp lingers for an hour.
- **Infection on a botched splint:** on the `skill_check` failure branch,
  `apply_effect(t, 'damage_over_time', kind='sepsis', interval=4,
  duration=40)`, so untreated wounds get worse, and the
  [poison dart trap](052_poison_dart_trap.md) antidote pattern is the cure.
- **A regen ward while treated:** attach a short `regeneration` effect on a
  successful splint so a bandaged patient recovers HP for a while, the
  recovery half of [sleep & rest](138_sleep_rest.md).
```
