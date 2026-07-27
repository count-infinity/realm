# 058. Spreading Fire

> Checklist item 58 ([now]): *cellular on_tick simulation over exits(), counterplay items*

**What you'll build:** A barn fire that grows through three stages, jumps
to adjacent rooms through open doorways once it rages, burns whoever
stands in it, eventually burns itself out, and a foam extinguisher that
beats it back stage by stage.

**Concepts:** fire-as-objects running a cellular simulation on
`script_ticker` heartbeats, growth stages in a plain attribute, the
[`exits()`](../reference/softcode.md#fn-exits) graph walk with the
closed-door filter (the [gas bomb](048_gas_bomb.md)'s spread, now made
recursive), prototype-copied handlers that copy the copier, already-burning
dedup, [`expire()`](../reference/softcode.md#fn-expire) as fuel, and a
counterplay item.

## How it works

The finished barn is a set of rooms, some of them holding a *fire object*.
Each fire runs its own heartbeat, and one of the things a big enough fire
does on its tick is create more fires next door. There is no coordinator
anywhere: the blaze is an emergent property of one object's tick script
copying itself forward, which is the whole lesson. This section answers
four questions: what a stage is, how a fire reaches the next room, how the
live code gets onto each new fire, and how a fire finally stops.

The [gas bomb](048_gas_bomb.md) spread once, from a single detonation.
Fire is the same graph walk made *cellular*: every burning room hosts a
fire, and every fire can seed the rooms around it.

### What is a stage?

`stage` is a plain attribute on each fire. Stage 1 is a smolder (narration
only), stage 2 a blaze that burns occupants for `1d4`, and stage 3 an
inferno that burns harder (`2d4`) and *also* spreads. A fresh fire carries
no `stage` attribute at all, so [`V('stage', 1)`](../reference/softcode.md#fn-v)
reads it as 1. Each tick raises the stage until it caps at 3, and the
[`damage()`](../reference/softcode.md#fn-damage) roll is `{s - 1}d4`, so
the harm climbs with the stage. The damage is the fire's own, by proximity
authority: a fire standing in the room may burn who is in it, the same
license the [landmine](049_landmine.md) uses.

The growth write stays longhand,
[`set_attr`](../reference/softcode.md#fn-set_attr)`(me, 'stage', s + 1)` guarded by
`if s < 3`. [`incr`](../reference/softcode.md#fn-incr) accepts a `default`,
so `incr('stage', default=1)` looks like the obvious tidy-up, but it writes
*unconditionally*, and the `if s < 3` is exactly what makes 3 a ceiling
rather than a waypoint. Without the guard the stage would climb forever and
`{s - 1}d4` would climb with it. A guarded write, one that happens only on
one branch, is the case `incr` cannot express; the [self-destruct
sequence](056_self_destruct.md) keeps its countdown longhand for the same
reason.

### How does a fire reach the next room?

Rooms are nodes and exits are edges. [`exits(loc(me))`](../reference/softcode.md#fn-exits)
lists the exits of the fire's room, each one carries a `destination` room
id, and [`get`](../reference/softcode.md#fn-get)`('#' + id)` resolves that
id to the room object. (`@dig` writes the id into the exit's `destination`
attribute, so this reads exactly what the engine's own movement uses.) The
spread walks those exits and skips two kinds of room: one reached through a
`closed` exit, because a shut door holds the fire back, and one that already
holds a `fire`-tagged object, which is the dedup that keeps two fires from
stacking in the same room. Every survivor gets a fresh stage-1 fire.

### How does the live code get onto each new fire?

Writing scripts inside a script means quoting misery, so the live code
sits on a *prototype* under inert names, `fire_tick` and `fire_spread`.
Those are not trigger or hook names, so the prototype itself never burns.
When a fire is lit or spreads, the tick handler is copied onto the new
fire as [`on_tick`](../reference/softcode.md#lifecycle-hooks) and the spread
handler as `spread`, and a
`script_ticker` behavior is attached so the engine runs `on_tick` on a
cadence.

The reflexive twist over the gas bomb is that `fire_spread` is code that
installs `fire_spread` onto its children. The copier copies the copier,
and that one line is what turns a single spread into a multi-hop blaze:
each new fire is born knowing how to spread in turn.

### Where the tick fires, and why it needs no guard

A `script_ticker` runs the fire's `on_tick` on the fire *itself*, not on
every object in the room. Inside `on_tick`, `me` is always this fire, so
the script needs no `if target is me:` guard of the kind a room-wide
reactive `ON_<EVENT>` hook needs. This build has no reactive hook at all:
the tick is a ticker, and `light` and `spray` are `$`-command triggers the
player types, so every piece of code here runs on the object that owns it.
The tick reaches the people in the room by looping
[`contents(loc(me))`](../reference/softcode.md#fn-contents) and filtering to
players and NPCs with [`has_tag`](../reference/softcode.md#fn-has_tag), so it
never tries to burn an exit or the fire itself.

The tick calls its own spread through
[`eval_attr`](../reference/softcode.md#fn-eval_attr)`(me, 'spread')`. That
runs the `spread` attribute as a subroutine with the caller's authority, so
inside it `me` is still the fire, and the graph walk reads the fire's own
room.

### How does a fire stop?

Two ways. Left alone, every fire gets [`expire`](../reference/softcode.md#fn-expire)`(f, 120)`,
a persistent lifetime swept by the world tick, so even an ignored fire dies
when its fuel is spent and no burning room survives a reboot as a stuck
inferno. ([`wait()`](../reference/softcode.md#fn-wait) would orphan every
fire on a restart, the same rule the [gas bomb](048_gas_bomb.md) follows.)
Fought, a fire is knocked down by the extinguisher: `spray` drops the local
fire one stage, and a stage-1 fire dies to a final spray through
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj) (which works because
the extinguisher and the fire share an owner, so softcode wields its owner's
authority). Growth is one stage per tick, so an extinguisher outpaces a fire
you stand and fight, but every room it spread to burns on its own clock, and
an inferno you put out can be re-lit from a room it already infected. Fight
fire room by room, and mind your back.

## Build it

The barn is a chain of rooms with one open ladderway the fire can climb and
one shut tack room it can never reach. Dig the loft, climb up into it, then
dig the stable below and the tack room past it, closing the tack door so the
fire is walled off from it:

```text
@dig The Hayloft = hayloft, yard
hayloft
@dig The Stable = ladder, loft
ladder
@dig The Tack Room = tack door, stable
@tag tack door = closed
```

Climb back up to the hayloft and shut the `yard` door out to Limbo, so a
fire drill does not follow you home:

```text
loft
@tag yard = closed
```

Make the prototype. It holds the live code under inert names, so it never
burns wherever it sits:

```text
@create fire prototype
```

The tick handler is the fire's heartbeat. Its steps in order: read the
stage, either burn every player and NPC in the room (at a blaze or hotter)
or narrate a smolder, run the spread once at inferno, then grow one stage
unless already capped:

```text
@set fire prototype/fire_tick = '''
s = V('stage', 1)  # a fresh fire has no stage attribute, so it reads as 1
if s >= 2:
    for o in contents(loc(me)):
        if has_tag(o, 'player') or has_tag(o, 'npc'):  # skip exits, items, the fire itself
            pemit(o, 'The blaze sears you!')
            damage(o, roll(f'{s - 1}d4'))  # 1d4 at a blaze, 2d4 at an inferno
else:
    remit(loc(me), 'Smoke thickens. Flames crawl wider.')
if s >= 3:
    eval_attr(me, 'spread')  # only an inferno reaches next door
if s < 3:
    set_attr(me, 'stage', s + 1)  # guarded climb: 3 is the ceiling, not a waypoint
'''
```

The spread handler is the graph walk. For each exit of this fire's room it
skips a shut door and a dead-end, skips a room that is already burning, then
seeds a fresh stage-1 fire and stamps the live code onto it, including its
own `spread` line so the new fire can spread in turn:

```text
@set fire prototype/fire_spread = '''
proto = get('fire prototype')
for e in exits(loc(me)):
    if has_tag(e, 'closed'):
        continue  # a shut door holds the fire back
    d = get(f"#{get_attr(e, 'destination', '')}")  # the room the exit leads to
    if not d:
        continue
    if [o for o in contents(d) if has_tag(o, 'fire')]:
        continue  # already burning: do not stack a second fire
    f = create_obj('a hungry fire', ['thing', 'fire'], location=d)
    if not f:  # create_obj returns None for a room the owner does not control
        continue
    set_attr(f, 'on_tick', get_attr(proto, 'fire_tick'))
    set_attr(f, 'spread', get_attr(proto, 'fire_spread'))  # the copier copies the copier
    attach_behavior(f, 'script_ticker', interval=2)
    expire(f, 120)  # fuel: even ignored, the fire dies when it is spent
    remit(loc(f), 'Fire licks through the doorway -- it catches!')
'''
```

Ignition is a box of matches. Its `$light` trigger creates a fire in the
striker's room, stamps the prototype's handlers onto it, arms the ticker,
sets the fuel, and announces, or gutters out if the room refuses the fire:

```text
@create box of matches
@set box of matches/cmd_light = '''
$light fire:
proto = get('fire prototype')
f = create_obj('a hungry fire', ['thing', 'fire'], location=loc(enactor))
if not f:
    pemit(enactor, 'The match gutters out.')
else:
    set_attr(f, 'on_tick', get_attr(proto, 'fire_tick'))
    set_attr(f, 'spread', get_attr(proto, 'fire_spread'))
    attach_behavior(f, 'script_ticker', interval=2)
    expire(f, 120)
    remit(loc(enactor), f'{name(enactor)} drops a lit match into the straw. Flames catch!')
'''
```

Counterplay is a fire extinguisher. Its `$spray` trigger finds the local
fire, knocks it down one stage, and destroys it outright once it is down to
a smolder:

```text
@create fire extinguisher
@set fire extinguisher/cmd_spray = '''
$spray *:
fires = [o for o in contents(loc(enactor)) if has_tag(o, 'fire')]
if not fires:
    pemit(enactor, 'Nothing here is burning.')
else:
    s = get_attr(fires[0], 'stage', 1)
    if s <= 1:
        destroy_obj(fires[0])  # a stage-1 fire dies to a final spray
        remit(loc(enactor), f'{name(enactor)} smothers the last flames in a white cloud. Steam hisses.')
    else:
        set_attr(fires[0], 'stage', s - 1)  # knock it back one stage
        remit(loc(enactor), f'{name(enactor)} drives the fire back with a jet of foam!')
'''
```

## Try it

Light the hayloft and stand well back. On a live server the fire grows on
its own heartbeat; the stages below are what each tick prints:

```text
light fire       -> Bob drops a lit match into the straw. Flames catch!
(tick)           -> Smoke thickens. Flames crawl wider.        (stage 1 -> 2)
(tick)           -> The blaze sears you!  (1d4)                (stage 2 -> 3)
(tick)           -> The blaze sears you!  (2d4)
   (in the Stable) Fire licks through the doorway -- it catches!
```

The Stable is burning on its own clock now. The Tack Room, behind its shut
door, never catches, and neither does the yard. Fight back with the
extinguisher, one stage per spray:

```text
spray fire       -> Bob drives the fire back with a jet of foam!   (3 -> 2)
spray fire       -> Bob drives the fire back with a jet of foam!   (2 -> 1)
spray fire       -> Bob smothers the last flames in a white cloud. Steam hisses.
```

Then climb down the ladder and put out the Stable fire before it reaches
stage 3, or it will re-light the loft you just saved. Walk away entirely
and the fires exhaust their `expire()` fuel and die alone.

## Going further

- **Ash and evidence.** Give fires a copied `ON_EXPIRE` that spawns `a
  drift of grey ash` (the extinguisher line can drop one on a manual kill),
  so rooms remember that they burned.
- **Fuel-aware rooms.** Gate the spread on the destination: a
  `has_tag(d, 'stone')` room refuses a stage-1 fire, and a `tinder` tag
  starts one at stage 2. Terrain becomes fire policy.
- **Sprinklers.** A room object on a `script_ticker` that runs the
  extinguisher line whenever it sees a `fire`-tagged neighbor is automated
  counterplay, which is just the counterplay item with a heartbeat.
- **Burn the furniture.** The tick already sweeps `contents()`, so extend
  the comprehension to `flammable`-tagged things and `destroy_obj` them at
  stage 3. Now evacuating matters.
```
