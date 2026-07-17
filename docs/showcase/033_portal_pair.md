# 033. Portal Pair

> Checklist item 33 — now — *programmatic exit creation: create_obj + exit tag + db.destination*

**What you'll build:** A pair of linked wormholes: step into the
shimmering portal in the Observatory and you're standing in the
Shattered Crater, and vice versa — a two-way link between rooms that
share no wall. Then let physics win: the pair collapses on a timer.

**Concepts:** exits as plain data (`exit` tag + `destination`
attribute), building them **from softcode** with `create_obj()` in one
`@eval` (what `@open` does, twice, without the walking), `expire()` on
exits (they're just objects), `ON_EXPIRE` narration, and room
`ON_ENTER` arrival effects.

## How it works

**An exit is three facts.** In the room's contents, tagged `exit`,
carrying a `destination` room id. That's everything `@open` writes —
so anything that can `create_obj` and `set_attr` can dig doors. A
"portal pair" is just two such exits pointing at each other's rooms;
"linked" is geometry, not machinery, and traversal through them gets
the full standard treatment (wards, locks, `on_enter`) because they
*are* standard exits.

**Why softcode instead of `@open`.** `@open` builds one exit, here,
facing away. A wormhole wants both ends born together — ideally from a
device, a spell, or a wand pointed at a distant room. One `@eval` (or
the body of any `$`-command) does it: resolve the far room by name,
create both exit objects with `location=`, cross-write the
`destination`s. The same dozen tokens power every teleporter-network,
spell-gate, and GM-conjured shortcut you'll ever build — this is the
programmatic face of world-building, the `[[...]]` sandbox's loops
included.

**Unstable by design.** Exits are ordinary objects, so `expire(o, 120)`
works on them: the world tick fires each portal's `ON_EXPIRE` (a
farewell `remit` to whichever room it stands in) and removes it. Two
minutes after opening, the shortcut is gone and the map heals itself —
no cleanup script, no orphaned half-link, because *both* ends carry
the same lease.

**Arrival flavor rides the rooms.** Each room's `ON_ENTER` narrates the
tumble-out. In these two rooms every arrival *is* a portal arrival, so
the line needs no guard — but on a busier map it would, and the payload
is right there: `adata('exit')` names the exit that delivered the mover
(see [028](028_one_way_exit.md)), so
`... if name(adata('exit')) == 'shimmering portal' else None` keeps the
wormhole's flavor off people who walked in through the door.

## Build it

Two rooms with no exits between them, then the wormhole — one `@eval`
that opens both ends, sets both lifetimes, and hangs a collapse line
on each:

```text
@dig The Observatory
@dig The Shattered Crater
@teleport me = The Observatory
@eval far = get('The Shattered Crater'); a = create_obj('shimmering portal', tags=['exit'], location=here); b = create_obj('shimmering portal', tags=['exit'], location=far); set_attr(a, 'destination', far.id); set_attr(b, 'destination', here.id); [expire(o, 120) for o in (a, b)]; [set_attr(o, 'on_expire', "remit(loc(me), 'The wormhole snaps shut with a thunderclap.')") for o in (a, b)]; result = f'wormhole open: {a.id[:8]} <-> {b.id[:8]}'
@desc shimmering portal = A lens of folded starlight. Things on the far side swim in it.
```

(Note the nested quoting: the `ON_EXPIRE` *script* is a string being
written by a script, so it rides in double quotes inside the `@eval`.)

Then the arrival flavor, one line per room:

```text
@set here/on_enter = pemit(enactor, 'You tumble out of the wormhole, ears popping.') if has_tag(enactor, 'player') else None
shimmering portal
@set here/on_enter = pemit(enactor, 'You tumble out of the wormhole, ears popping.') if has_tag(enactor, 'player') else None
shimmering portal
```

That walk in the middle is the point: the portal was traversable the
instant the `@eval` finished, in both directions.

## Try it

```text
look                -> Exits: shimmering portal      (it's a real exit)
shimmering portal   -> The Shattered Crater. "You tumble out of the
                       wormhole, ears popping."
shimmering portal   -> and straight back to the Observatory
```

Two minutes later, wherever you are:

```text
                    -> The wormhole snaps shut with a thunderclap.
look                -> Exits: None
```

Both ends die on the same world tick — no one-way stub survives.

## Going further

- **A wand of wormholes** — move the `@eval` body into
  `$zap *:` on a wand, with `far = get(arg0)`; any room the wand's
  owner controls becomes a valid far end (`create_obj` seeds only
  into rooms your authority reaches — softcode's owner rule doing
  border control for free).
- **Silent transit / teleport feel** — for portals that shouldn't
  print `You leave shimmering portal.`, use a *dead-end* exit (no
  destination) whose `ON_FAIL` runs `teleport_obj(enactor, far)` and
  your own narration: the engine grants the walked-into exit consent
  to relocate its walker — the sanctioned "portal pattern."
- **Keyed wormholes** — the portals are exits, so everything in this
  chapter stacks: a [keycard ward](026_keycard_door.md) on the crater,
  a [toll](030_toll_gate.md) on the lens, a `closed` tag it only drops
  at night.
- **One-way rift** — create only `a`. Half a wormhole is a
  [one-way exit](028_one_way_exit.md) with better lighting.
