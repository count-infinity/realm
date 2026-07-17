# 167. Random dungeon generator

> Checklist item 167 — [now] — *softcode procedural gen, create_obj rooms/exits, seeded LCG, teardown by tag*

**What you'll build:** a `delve N` verb that carves a fresh dungeon out
of thin air — a connected spine of N chambers plus seeded side-alcoves,
every room tagged for one-command teardown, and reproducible from a
stored seed. (Builder permission: the forge is `@create`d; the *result*
is walkable by anyone.)

**Concepts:** procedural generation in pure softcode — `create_obj` for
rooms *and* exits, `set_attr` to wire `destination`, a **guaranteed
reachability** topology, a **seeded** linear-congruential RNG for
determinism, and a run tag for teardown.

## How it works

**Rooms and exits are just objects.** `create_obj(name, tags=['room'])`
mints a room; `create_obj(dir, tags=['exit'], location=room)` mints an
exit; `set_attr(exit, 'destination', room.id)` points it. That's the
whole vocabulary — a generator is a loop over it.

**Reachability is topology, not luck.** The generator lays a **spine**:
chamber *i* links north to *i+1* and south back. A linear chain is
connected by construction, so no random roll can ever strand a room.
Only *after* the spine is guaranteed do we add flavor — dead-end alcoves
hung off some chambers — where randomness is safe because an unreachable
alcove is impossible (each links back to its spine chamber).

**Seeded means reproducible.** `rand()` is fine for one-shot flavor, but
a *seeded* generator wants determinism: the same seed → the same
dungeon. So we run a tiny **linear-congruential generator** by hand —
`s = (s * 1103515245 + 12345) % 2**31` — stepping it once per chamber
and using `seq[i] % 3 == 0` to decide alcoves. Store the seed in an
attribute and `delve` is repeatable; bump the seed for a new layout.

**Teardown is a tag.** Every generated room and alcove is tagged
`dungeon:run`, so `collapse` is one comprehension over
`search_world(tag='dungeon:run')` calling `destroy_obj`. Generate,
explore, collapse, repeat — nothing leaks.

## Build it

The forge and its seed:

```text
@create dungeon forge
drop dungeon forge
@set dungeon forge/seed = 7
```

The generator. Read it in four beats: build N chambers, stamp each
description, link the spine north/south, then step the LCG and hang
alcoves off the chambers it selects — finally drop the caller at the
mouth:

```text
@set dungeon forge/cmd_delve = $delve *: n = clamp(int(arg0), 2, 8); s = get_attr(me, 'seed', 1); rooms = [create_obj('Cavern ' + str(i + 1), tags=['room', 'dungeon:run']) for i in range(n)]; [set_attr(rooms[i], 'desc_extras', [['', 'Hewn rock, chamber ' + str(i + 1) + ' of ' + str(n) + '.']]) for i in range(n)]; [(set_attr(create_obj('north', tags=['exit'], location=rooms[i - 1]), 'destination', rooms[i].id), set_attr(create_obj('south', tags=['exit'], location=rooms[i]), 'destination', rooms[i - 1].id)) for i in range(1, n)]; seq = []; [seq.append((s * 1103515245 + 12345) % 2147483648) if not seq else seq.append((seq[-1] * 1103515245 + 12345) % 2147483648) for i in range(n)]; picks = [i for i in range(n) if seq[i] % 3 == 0]; alcoves = [create_obj('Alcove ' + str(j + 1), tags=['room', 'dungeon:run']) for j in range(len(picks))]; [(set_attr(create_obj('east', tags=['exit'], location=rooms[picks[j]]), 'destination', alcoves[j].id), set_attr(create_obj('west', tags=['exit'], location=alcoves[j]), 'destination', rooms[picks[j]].id), set_attr(alcoves[j], 'desc_extras', [['', 'A dead-end alcove, thick with dust.']])) for j in range(len(picks))]; teleport_obj(enactor, rooms[0]); pemit(enactor, 'Delved ' + str(n) + ' chambers and ' + str(len(picks)) + ' alcoves (seed ' + str(s) + '). You stand at the mouth.')
```

Teardown — one line, keyed on the run tag:

```text
@set dungeon forge/cmd_collapse = $collapse: [destroy_obj(o) for o in search_world(tag='dungeon:run')]; pemit(enactor, 'The dungeon collapses into rubble.')
```

## Try it

```text
delve 5
  Delved 5 chambers and 4 alcoves (seed 7). You stand at the mouth.
north
north
  ... walk the spine end to end; every chamber is reachable ...
east
  A dead-end alcove, thick with dust.       <- if this chamber drew one
```

Walk out (`@teleport me = The Workshop`), `collapse`, then `delve 5`
again: **seed 7 rebuilds the same 5 chambers and 4 alcoves** — determinism.
Change `@set dungeon forge/seed = 8` and the alcoves fall differently.
`@examine` any chamber shows the `dungeon:run` tag that makes teardown
trivial.

## Going further

- **Branching mazes:** step the LCG for *each* chamber to pick an exit
  direction, keeping a "visited coordinate" set to avoid collisions — the
  spine guarantee generalizes to a spanning tree if every new room links
  back to an existing one.
- **Populate as you carve:** the [prototype library](165_prototype_library.md)'s
  `mint` pattern drops seeded monsters and loot into chambers — roll the
  same LCG so encounters are reproducible too.
- **Instance it:** wrap the whole run in an
  [instanced template](044_instanced_room.md) so each party delves a
  private copy that reaps itself, instead of tagging shared rooms.
- **Auto-map it:** point the [cartographer](174_auto_map.md) at the run
  tag to draw the dungeon you just carved.
