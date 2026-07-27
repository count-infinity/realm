# 167. Random dungeon generator

> Checklist item 167 ([now]): *softcode room/exit carving, seeded procedural generation, teardown by tag*

**What you'll build:** a `delve N` verb that carves a fresh dungeon out of thin
air: a connected spine of N chambers plus seeded side-alcoves, every room tagged
for one-command teardown, and reproducible from a stored seed. The forge is a
builder-owned object, but the dungeon it produces is walkable by anyone.

**Concepts:** procedural generation in pure softcode, using
[`create_obj`](../reference/softcode.md#fn-create_obj) for rooms *and* exits,
[`set_attr`](../reference/softcode.md#fn-set_attr) to wire each exit's
`destination`, a topology that guarantees reachability, a seeded
linear-congruential generator for determinism, and a run tag for teardown.

## How it works

A dungeon here is nothing more special than a pile of ordinary objects wired
together, minted by a loop. This section answers three questions: what the
generator is actually making, how it keeps every room reachable, and how the
same seed rebuilds the same layout.

**Rooms and exits are just objects.**
[`create_obj(name, tags=['room'])`](../reference/softcode.md#fn-create_obj)
mints a room; `create_obj(dir, tags=['exit'], location=room)` mints an exit
sitting in that room; `set_attr(exit, 'destination', room.id)` points the exit
at its target so movement resolves it. That is the whole vocabulary, and a
generator is a loop over it.

**Reachability is topology, not luck.** The generator lays a *spine*: chamber
*i* links north to *i+1* and south back to *i-1*. A linear chain is connected by
construction, so no random roll can strand a room. Only after the spine is
guaranteed does the generator add flavor, hanging dead-end alcoves off some
chambers, where randomness is safe because each alcove links straight back to
its spine chamber and so is always reachable.

**Seeded means reproducible.** [`rand()`](../reference/softcode.md#fn-rand) is
fine for one-shot flavor, but a seeded generator wants determinism: the same
seed produces the same dungeon. So the script runs a tiny linear-congruential
generator by hand, `s = (s * 1103515245 + 12345) % 2**31`, stepping it once per
chamber and using `seq[i] % 3 == 0` to decide which chambers get an alcove. The
seed lives in an attribute, so `delve` is repeatable; bump the seed for a new
layout.

**Teardown is a tag.** Every generated room and alcove carries the tag
`dungeon:run`, so `collapse` is one loop over
[`search_world(tag='dungeon:run')`](../reference/softcode.md#fn-search_world)
calling [`destroy_obj`](../reference/softcode.md#fn-destroy_obj). Generate,
explore, collapse, repeat, and nothing leaks.

Both verbs are `$`-commands on the forge, so they dispatch without any
`target` guard: a `$`-command runs only for the object that owns it, unlike a
reactive `ON_<EVENT>` hook that fires on every object in the room.

## Build it

Create the forge, drop it in the room, and give it a starting seed:

```text
@create dungeon forge
drop dungeon forge
@set dungeon forge/seed = 7
```

Now the generator. Read it in five steps: clamp the requested size, mint the N
chambers with their descriptions, link the spine north and south, step the LCG
and hang an alcove off every chamber it selects, then drop the caller at the
mouth. Each chamber is minted in one [`create_obj`](../reference/softcode.md#fn-create_obj)
call that also writes its description, and each exit is minted and then pointed
with [`set_attr`](../reference/softcode.md#fn-set_attr):

```text
@set dungeon forge/cmd_delve = '''
$delve *:
n = clamp(int(arg0), 2, 8)
s = V('seed', 1)
rooms = [create_obj(f'Cavern {i + 1}', tags=['room', 'dungeon:run'], description=f'Hewn rock, chamber {i + 1} of {n}.') for i in range(n)]
# Spine: chamber i-1 goes north to i, and i goes south back to i-1.
for i in range(1, n):
    set_attr(create_obj('north', tags=['exit'], location=rooms[i - 1]), 'destination', rooms[i].id)
    set_attr(create_obj('south', tags=['exit'], location=rooms[i]), 'destination', rooms[i - 1].id)
# Step the linear-congruential generator once per chamber for a deterministic sequence.
seq = []
for i in range(n):
    prev = seq[-1] if seq else s
    seq.append((prev * 1103515245 + 12345) % 2**31)
picks = [i for i in range(n) if seq[i] % 3 == 0]
for j, i in enumerate(picks):
    alcove = create_obj(f'Alcove {j + 1}', tags=['room', 'dungeon:run'], description='A dead-end alcove, thick with dust.')
    set_attr(create_obj('east', tags=['exit'], location=rooms[i]), 'destination', alcove.id)
    set_attr(create_obj('west', tags=['exit'], location=alcove), 'destination', rooms[i].id)
teleport_obj(enactor, rooms[0])
pemit(enactor, f'Delved {n} chambers and {len(picks)} alcoves (seed {s}). You stand at the mouth.')
'''
```

Teardown keys on the run tag: [`search_world`](../reference/softcode.md#fn-search_world)
returns every object carrying `dungeon:run`, and
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj) removes each one:

```text
@set dungeon forge/cmd_collapse = '''
$collapse:
for o in search_world(tag='dungeon:run'):
    destroy_obj(o)
pemit(enactor, 'The dungeon collapses into rubble.')
'''
```

## Try it

```text
> delve 5
  Delved 5 chambers and 4 alcoves (seed 7). You stand at the mouth.
> north
> north
  ... walk the spine end to end; every chamber is reachable ...
> east
  A dead-end alcove, thick with dust.       <- if this chamber drew one
```

Walk out with [`@teleport`](../reference/softcode.md#fn-teleport_obj) (`@teleport
me = The Workshop`), run `collapse`, then `delve 5` again: seed 7 rebuilds the
same 5 chambers and 4 alcoves, which is the determinism the LCG buys you. Change
the seed with `@set dungeon forge/seed = 8` and the alcoves fall differently.
`@examine` any chamber shows the `dungeon:run` tag that makes teardown trivial.

## Going further

- **Branching mazes:** step the LCG for *each* chamber to pick an exit
  direction, keeping a "visited coordinate" set to avoid collisions. The spine
  guarantee generalizes to a spanning tree if every new room links back to an
  existing one.
- **Populate as you carve:** the [prototype library](165_prototype_library.md)'s
  `mint` pattern drops seeded monsters and loot into chambers; roll the same LCG
  so encounters are reproducible too.
- **Instance it:** wrap the whole run in an
  [instanced template](044_instanced_room.md) so each party delves a private
  copy that reaps itself, instead of tagging shared rooms.
- **Auto-map it:** point the [cartographer](174_auto_map.md) at the run tag to
  draw the dungeon you just carved.
