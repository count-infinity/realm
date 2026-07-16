# 058. Spreading Fire

> Checklist item 58 — [now] — *cellular on_tick simulation over exits(), counterplay items*

**What you'll build:** A barn fire that grows through three stages,
jumps to adjacent rooms through open doorways when it rages, burns
whoever stands in it, eventually burns itself out — and a foam
extinguisher that beats it back stage by stage.

**Concepts:** fire-as-objects running a cellular simulation on
`script_ticker` heartbeats, growth stages in a plain attribute, the
`exits()` graph walk with the closed-door filter (item 48's spread,
now *recursive*), prototype-copied handlers that copy the copier,
already-burning dedup, `expire()` as fuel, and a counterplay item.

## How it works

The gas bomb (item 48) spread once, from a single detonation. Fire is
the same graph walk made **cellular**: every burning room hosts a fire
*object*, each fire runs its own heartbeat, and one of the things a
big enough fire does on its tick is create more fires next door. No
coordinator anywhere — the blaze is an emergent property of one
object's tick script, which is the whole lesson.

1. **Stages are an attribute.** `stage` 1 is a smolder (narration
   only), 2 a blaze (burns occupants, `1d4`), 3 an inferno (burns
   harder, `2d4`, *and spreads*). Each tick raises the stage until it
   caps at 3. Damage is the fire object's own — proximity authority,
   like the cloud and the mine before it.

2. **Spread walks the exits.** `exits(loc(me))`, resolve each
   `destination`, skip `closed` doors — **closed doors hold fire back**,
   same rule as the gas — and skip rooms that already have a
   `fire`-tagged object in them (the dedup that keeps two fires from
   stacking into a paradox). Survivors get a fresh stage-1 fire.

3. **The handlers copy themselves forward.** Cloud-style, the live
   code sits on a *prototype* under inert names (`fire_tick`,
   `fire_spread`) and every new fire gets them copied on under live
   names. The twist over item 48: `fire_spread` is code that installs
   `fire_spread` on its children — the copier copies the copier, and
   that one reflexive line is what makes the spread multi-hop instead
   of one-shot.

4. **Fuel is `expire()`.** Every fire gets `expire(f, 120)`: even
   ignored, a fire dies when its fuel is spent, reboot-proof, no
   stuck infernos. (`wait()` would orphan every burning room on a
   restart — the 048 rule again.)

5. **Counterplay is a stage editor.** The extinguisher's `$spray`
   knocks the local fire down one stage; a stage-1 fire dies to a
   final spray (`destroy_obj` — note this works because extinguisher
   and fire share an owner; softcode wields its owner's authority).
   Growth is one stage per tick, so an extinguisher *outpaces* a fire
   you stand and fight — but every room it spread to fights back on
   its own clock, and an inferno you put out can be re-lit from the
   room it already infected. Fight fire room by room, and mind your
   back.

## Build it

The barn — an open ladderway the fire can climb, and a shut tack room
it can never reach. The `yard` door back out gets shut too (open it to
leave; a fire drill with the door open follows you home):

```text
@dig The Hayloft = hayloft, yard
hayloft
@dig The Stable = ladder, loft
ladder
@dig The Tack Room = tack door, stable
@tag tack door = closed
loft
@tag yard = closed
```

The prototype — handlers under inert names, so the prototype itself
never burns. Tick: narrate or burn by stage, spread at 3, then grow:

```text
@create fire prototype
@set fire prototype/fire_tick = s = get_attr(me, 'stage', 1); ([(pemit(o, 'The blaze sears you!'), damage(o, roll(str(s - 1) + 'd4'))) for o in contents(loc(me)) if has_tag(o, 'player') or has_tag(o, 'npc')] if s >= 2 else remit(loc(me), 'Smoke thickens. Flames crawl wider.')); (eval_attr(me, 'spread') if s >= 3 else None); (set_attr(me, 'stage', s + 1) if s < 3 else None)
@set fire prototype/fire_spread = proto = get('fire prototype'); dests = [get('#' + str(get_attr(e, 'destination', ''))) for e in exits(loc(me)) if not has_tag(e, 'closed')]; fresh = [d for d in dests if d and not [o for o in contents(d) if has_tag(o, 'fire')]]; new = [f for f in [create_obj('a hungry fire', ['thing', 'fire'], location=r) for r in fresh] if f]; [set_attr(f, 'on_tick', get_attr(proto, 'fire_tick')) for f in new]; [set_attr(f, 'spread', get_attr(proto, 'fire_spread')) for f in new]; [attach_behavior(f, 'script_ticker', interval=2) for f in new]; [expire(f, 120) for f in new]; [remit(loc(f), 'Fire licks through the doorway -- it catches!') for f in new]
```

Ignition and counterplay:

```text
@create box of matches
@set box of matches/cmd_light = $light fire: proto = get('fire prototype'); f = create_obj('a hungry fire', ['thing', 'fire'], location=loc(enactor)); (set_attr(f, 'on_tick', get_attr(proto, 'fire_tick')), set_attr(f, 'spread', get_attr(proto, 'fire_spread')), attach_behavior(f, 'script_ticker', interval=2), expire(f, 120), remit(loc(enactor), name(enactor) + ' drops a lit match into the straw. Flames catch!')) if f else pemit(enactor, 'The match gutters out.')
@create fire extinguisher
@set fire extinguisher/cmd_spray = $spray *: fires = [o for o in contents(loc(enactor)) if has_tag(o, 'fire')]; s = get_attr(fires[0], 'stage', 1) if fires else 0; (pemit(enactor, 'Nothing here is burning.') if not fires else ((destroy_obj(fires[0]), remit(loc(enactor), name(enactor) + ' smothers the last flames in a white cloud. Steam hisses.')) if s <= 1 else (set_attr(fires[0], 'stage', s - 1), remit(loc(enactor), name(enactor) + ' drives the fire back with a jet of foam!'))))
```

## Try it

Light the hayloft and stand well back:

```text
light fire       -> Bob drops a lit match into the straw. Flames catch!
(tick)           -> Smoke thickens. Flames crawl wider.        (stage 1 -> 2)
(tick)           -> The blaze sears you!  (1d4)                (stage 2 -> 3)
(tick)           -> The blaze sears you!  (2d4)
   (in the Stable) Fire licks through the doorway -- it catches!
```

The Stable is burning on its own clock now; the Tack Room, behind its
shut door, never catches — and neither does the yard. Fight back:

```text
spray fire       -> Bob drives the fire back with a jet of foam!   (3 -> 2)
spray fire       -> Bob drives the fire back with a jet of foam!   (2 -> 1)
spray fire       -> Bob smothers the last flames in a white cloud. Steam hisses.
```

Then down the ladder to do it again before the Stable fire reaches
stage 3 — or it will re-light the loft you just saved. Walk away
entirely and the fires exhaust their `expire()` fuel and die alone.

## Going further

- **Ash and evidence** — give fires a copied `ON_EXPIRE` that spawns
  `a drift of grey ash` (and one on `destroy` needs no hook — the
  extinguisher line can drop it): rooms should remember they burned.
- **Fuel-aware rooms** — gate spread on the destination:
  `has_tag(d, 'stone')` rooms refuse a stage-1 fire; a `tinder` tag
  skips straight to stage 2. Terrain becomes fire policy.
- **Sprinklers** — a room object with `ON_ENTER` is the wrong hook;
  use a `script_ticker` watcher that sprays (the extinguisher line
  verbatim) whenever it sees a `fire`-tagged neighbor. Automated
  counterplay is just the counterplay item with a heartbeat.
- **Burn the furniture** — the tick already sweeps `contents()`;
  extend the comprehension to `flammable`-tagged things and
  `destroy_obj` them at stage 3. Now evacuating *matters*.
