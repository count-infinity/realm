# Part 9 — The Wreck

Remember the scratches on the steps — *T-I-D-E*, and an arrow
pointing down? The keeper knew where the supply ship sank: three
strokes north, three east of the harbor mouth. The chart the ferryman
wants is still in her hold. Time for the finale: a dungeon under the
sea that's *private to each crew that dives it*.

## Author the wreck once

Build the template somewhere out of the way — it's a stencil, not a
place players visit:

```text
@dig The Flooded Hold
@teleport me = The Flooded Hold
@tag here = zone:wreck
@tag here = instance_template
@tag here = instance_entry
@desc here = Green light filters through a split hull. Crates drift in the dark water.
@create the keeper's chart
drop the keeper's chart
@create surface
@tag surface = exit
drop surface
@set surface/destination = JETTY
@teleport me = The Jetty
```

(That's your Jetty id from part 6 again.) The `instance_template` tag
is the opt-in: it marks this zone as cloneable. Add a drowned mate, a
locked sea chest, a banshee's cousin — anything in the zone comes
along with every copy.

## The landmark

Now put a door to it on the seabed. Replace the region's `cell_exits`
with the full version — compass everywhere, the way home at the
harbor mouth, and at (3, 3) a portal down (one line, `JETTY` twice):

```text
@set gullwater/cell_exits = result = ['north', 'south', 'east', 'west'] + ([{'name': 'jetty', 'destination': 'JETTY', 'aliases': ['out']}] if x == 0 and y == 0 else []) + ([{'name': 'wreck', 'attrs': {'dest_resolver': 'instance', 'instance_template': 'wreck', 'instance_mode': 'shared', 'instance_return': 'JETTY'}} if x == 3 and y == 3 else [])
```

That `attrs` block makes the landmark's exit an **instance portal**:
walking it clones the wreck zone and puts you in your copy. `shared`
means your party — anyone following you — is routed into *your*
wreck when they walk it; strangers get their own. `instance_return`
names dry land, because the cell the portal sits in is itself
transient: a straggler in a reaped copy is evacuated to the Jetty,
never to a room that no longer exists.

## The dive

```text
board
row sea
row north
row north
row north
row east
row east
row east
ashore
wreck
```

`ashore` at the mark drops you into the undertow's water — dive fast.
Inside, the hold is yours: loot the chart, walk `surface`, and hand
it over. `pay 10 to the ferryman` if you still owe him; he saw
nothing, he rows nothing.

Leave and return and you'll find a *fresh* wreck — copies reap when
abandoned, chart and all. (The greedy will notice. Let them; or set
the chart's spawn to a one-time flag with part 4's caching trick.)

## Opening night, act two

Count what the sea cost you: one region object, one skiff, one
undertow line, one template zone. For that you got a procedural
ocean that materializes under a rowed boat, drowning built from
primitives, and a per-party dungeon behind a door on the seabed —
all typed from inside the game.

!!! info "Where to go from here"
    - **Populate the deep**: `cell_populate` takes a list — add a
      shark on a `rand()` roll (encounters may be random; geography
      may not).
    - **Solo dungeons**: `'instance_mode': 'solo'` bounces even
      followers at the threshold.
    - **The full designs**: docs/design/wilderness-requirements.md
      and docs/design/ephemeral-rooms.md — everything this act used,
      with the reasoning.
