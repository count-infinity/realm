# 039. Underwater room

> Checklist item 39 ([now]): *per-occupant on_tick meters, skill_check, damage()*

**What you'll build:** A flooded cistern where every tick underwater
costs a swimming roll. Failures burn through your breath, and an empty
lung meter means drowning damage until you surface.

**Concepts:** a [`script_ticker`](../reference/softcode.md#lifecycle-hooks)
on the room itself, per-occupant meters stored *on the room*, skills as
data (`skill_def` + `@reload`),
[`eval_attr`](../reference/softcode.md#fn-eval_attr) as softcode's
subroutine, [`damage()`](../reference/softcode.md#fn-damage) proximity
authority, and `on_enter` / `on_leave` bookkeeping.

## How it works

The finished cistern is a single room that runs a timer over its own
occupants. Each tick, every player-tagged diver rolls to hold their
breath; a made roll costs nothing, a failure drops a personal counter
the room keeps, and once that counter hits zero the water comes in as
real damage. This section answers five questions in turn: where the
machine lives, where the meters live, where the skill comes from, how
one tick serves many divers, and why a room is allowed to hurt you.

### Where does the machine live?

Behaviors attach to any object, rooms included, so the cistern itself
carries the [`script_ticker`](../reference/softcode.md#lifecycle-hooks)
and an [`on_tick`](../reference/softcode.md#lifecycle-hooks) that sweeps
its player-tagged contents. There is no manager object and no zone
wiring, because the hazard is simply where the hazard is.

### Where do the breath meters live?

The meters live on the room, keyed by occupant (`breath_<id>`), not on
the players. That is a matter of authority, not taste: a builder-owned
room does not control someone else's character, so it may not
[`set_attr`](../reference/softcode.md#fn-set_attr) on their sheet (only
an admin-owned master writes other players under owner authority), but
it can remember anything it likes about them on itself.
[`on_leave`](../reference/softcode.md#lifecycle-hooks) deletes the key,
so surfacing resets you and the room never hoards state.

Deleting the key is also what makes the meter's *unset* value
load-bearing, since a diver with no `breath_<id>` has full lungs, not
empty ones. [`decr(k, default=V('breath_max', 3))`](../reference/softcode.md#fn-decr)
says exactly that: an unset meter counts as `breath_max`, and the first
failed roll takes it to 2. The default is an ordinary argument, so it
can be a lookup rather than a literal, which means retuning `breath_max`
on the room moves every meter's starting point with it.

### Where does the swimming skill come from?

GURPS swims on HT, and REALM's skill table extends from inside the game.
A `skill_def` object named `swimming` with `stat = health` and the
standard unskilled penalty, followed by `@reload`, registers the skill,
the same move the gas bomb makes for its `fortitude`
([tutorial 048](048_gas_bomb.md)). From then on
[`skill_check(o, 'swimming')`](../reference/softcode.md#fn-skill_check)
rolls 3d6 under the swimmer's HT-based level: trained divers use their
own `skill_swimming`, and everyone else falls back to health minus the
penalty.

### How does one tick serve many divers?

One tick handles many divers, and each diver needs read-update-branch
logic that a comprehension cannot express cleanly, so `on_tick` stays a
one-line sweep and calls
[`eval_attr`](../reference/softcode.md#fn-eval_attr)`(me, 'soak', o.id)`
per diver. That is softcode's subroutine call, the same trick
[tutorial 242](242_inline_functions.md) uses for renderers. One nuance:
`eval_attr` passes its args as strings, so we hand it the id and the
subroutine re-resolves the diver with
[`get`](../reference/softcode.md#fn-get)`('#' + arg0)`. Inside the
subroutine `me` is still the room (the caller), so `V(...)`, `decr(...)`,
and `damage(...)` all act with the room's authority.

### Why is the room allowed to hurt you?

[`damage()`](../reference/softcode.md#fn-damage) is proximity authority:
a script can damage what stands in the executor's room, and the executor
here is the room. No ownership of the victim is needed, and drowning
routes through the real death path (unconsciousness, corpses) like any
other damage.

One timing note, since this room reacts to arrivals: `on_enter` fires
*after* the diver has already arrived, with the diver as `enactor` and
the room as `target` (see [action phases](../design/action-phases.md)).
Because the room is its own target, `target is me` would be trivially
true, so the meaningful filter is
[`has_tag`](../reference/softcode.md#fn-has_tag)`(enactor, 'player')`:
without it, an object dropped into the water would run the hook too.

## Build it

The multi-line scripts below are `'''` heredoc blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)),
and the single-statement hooks stay on one line.

First, the skill, as data. `@reload` re-reads the `skill_def` objects so
`swimming` joins the skill table:

```text
@create swimming
@tag swimming = skill_def
@set swimming/stat = health
@set swimming/penalty = -4
@reload
```

Next, dig the cistern and step in, so that `here` resolves to it while
you build. `breath_max` is the lung capacity every meter starts from:

```text
@dig Flooded Cistern = dive, surface
dive
@desc here = Green water fills a drowned vault; light falls in wavering shafts from a grate far above.
@set here/breath_max = 3
```

Now the entry and exit bookkeeping. Entering announces the plunge, and
both hooks guard on the enactor because the room hears the arrival of
anything, not just players. Leaving clears your meter, which is what
makes surfacing reset you:

```text
@set here/on_enter = if has_tag(enactor, 'player'): pemit(enactor, 'You knife under. The cold clamps down; hold your breath.')
@set here/on_leave = '''
if has_tag(enactor, 'player'):
    del_attr(me, 'breath_' + enactor.id)  # clear the meter on the way out; an unset meter reads as full lungs
    pemit(enactor, 'You break the surface and drag in a long breath.')
'''
```

The per-diver subroutine comes next. Pass the roll and you spend
nothing; fail and your meter drops; once the meter is empty the water
forces its way in for 1d6 a tick:

```text
@set here/soak = '''
o = get('#' + arg0)  # eval_attr handed us the id as a string; re-resolve the diver
k = 'breath_' + o.id
if skill_check(o, 'swimming'):
    pemit(o, 'You pace your strokes and hold what air you have.')
else:
    decr(k, default=V('breath_max', 3))  # an unset meter counts as breath_max, so the first miss drops it to 2
    if V(k, 0) > 0:
        pemit(o, 'Your chest heaves. You are running out of air!')
    else:
        damage(o, roll('1d6'))
        pemit(o, 'Water forces its way in. You are drowning!')
'''
```

Finally, the sweep that drives it and the ticker that fires the sweep.
The `on_tick` is a single comprehension, so it stays one line; then
`surface` returns you to dry land:

```text
@set here/on_tick = [eval_attr(me, 'soak', o.id) for o in contents(me) if has_tag(o, 'player')]
@behavior here = script_ticker, interval:1
surface
```

`interval:1` checks every world tick (about four seconds), which is
harsh but good for testing; `interval:3` makes a kinder cistern.

## Try it

Give yourself lungs and a body to lose, then dive:

```text
@set me/hp = 12
@set me/max_hp = 12
@set me/health = 12
dive
  You knife under. The cold clamps down; hold your breath.
  You pace your strokes and hold what air you have.        <- made the roll
  Your chest heaves. You are running out of air!           <- failed one
  Your chest heaves. You are running out of air!           <- meter falling
  Water forces its way in. You are drowning!               <- meter empty: 1d6
surface
  You break the surface and drag in a long breath.
```

The per-tick lines depend on your swimming rolls, so which ones you see
varies; the meter always falls one step per failure and drowns once it
reaches zero. Between ticks, `@examine here` shows your `breath_<id>`
meter counting down, and surfacing deletes it, so the next dive starts
full.

## Going further

- **Air pockets:** a `$breathe` command on a submerged grating that
  resets `breath_<id>` to `breath_max`, a checkpoint for long flooded
  passages.
- **Diving gear:** start the `soak` branch with
  `has_tag(o, 'water_breathing')` and sell a rebreather that
  `grants_tags` it, using the wearables system from the
  [dark room](038_dark_room.md).
- **Murky water:** tag the cistern `dark` and let the lighting rules
  bite too, so waterproof lamps become treasure.
- **Currents:** on a bad failure margin, move the diver one room
  downstream, the falling-room pattern ([tutorial 047](047_falling.md))
  turned sideways.
