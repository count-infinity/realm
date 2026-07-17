# 212. Weight-plate puzzle

> Checklist item 212 — now — *contents-sensing, tag-typed objects, recheck-on-change*

**What you'll build:** Two pressure plates set into the floor. Load the
*heavy* object onto the pressure plate and the *light* object onto the
feather plate and the prize gate swings open; take the wrong thing back
off and it slams shut again. The puzzle senses what's sitting on each
plate.

**Concepts:** plates as containers, tag-typed objects (a "weight" is a
tag), a controller that **re-checks the whole puzzle whenever a plate
changes**, and — importantly — *why* the sensing runs from a `$`-command
rather than the built-in `put`/`get` (a timing lesson worth learning
once).

## How it works

The obvious build is "make each plate a container and react in its
`ON_PUT`." It doesn't work, and the reason is instructive: **`item:on_put`
fires during the permission pass, before the item's location actually
changes.** A plate that inspected `contents(me)` from its own `ON_PUT`
would see the *old* contents every time — the thing being placed isn't in
yet. (The same is true of `ON_GET`.)

So we drive placement from our own verb, where we control the ordering:

1. **`load <thing> onto <plate>`** and **`unload <thing> from <plate>`**
   are `$`-commands on a `balance mechanism` controller. (`place`, `put`,
   `take`, and `get` are all built-in verbs — softcode can't shadow them —
   so we pick free words.) Each verb **records the placement on the plate
   right away** — a `load` attribute naming the item — because `move_to`
   (like every relocation) actually completes *after* the script ends. If
   the re-check read `contents(plate)`, it would see the *old* contents;
   reading the `load` attribute we just wrote is immediate and correct.

2. **A plate wants a tag.** Each plate stores `wants` = a tag name
   (`heavy`, `light`). An object satisfies a plate if the item loaded onto
   it carries that tag. Weight here is a *convention* — a tag you put on
   the object — exactly as [item 14](014_basic_container.md) and
   [item 17](017_bag_of_holding.md) treat weight; REALM has no weight
   kernel to fight.

3. **The re-check is idempotent.** `recheck` evaluates *all* plates every
   time and sets the gate to match: all-satisfied opens it, anything
   missing closes it. It doesn't matter which plate changed or how — the
   check recomputes the truth from scratch, so loading, unloading, and
   swapping all just work. The controller runs the check with
   `eval_attr(me, 'recheck')`, keeping the sensing logic in one named
   place both verbs share.

The gate is the `closed`+`locked` exit from
[item 209](209_lever_combination.md): only the controller's raw tag
writes move it.

## Build it

The chamber and the prize room behind the gate:

```text
@dig The Trial Chamber = chamber, out
chamber
@dig The Prize Room = prize gate, chamber
@desc The Prize Room = A small vault. A single reliquary waits on a pedestal.
@tag prize gate = closed
@set prize gate/locked = true
@set prize gate/locked_msg = The prize gate is seamless stone. The plates in the floor must be satisfied.
```

Two plates — real containers (`container = true` lets `move_to` seat
items in them) — each declaring the weight it wants:

```text
@create pressure plate
drop pressure plate
@set pressure plate/container = true
@set pressure plate/wants = heavy
@desc pressure plate = A broad iron plate, sprung to sink under real weight.
@create feather plate
drop feather plate
@set feather plate/container = true
@set feather plate/wants = light
@desc feather plate = A gossamer plate that trembles at a breath -- too much weight would jam it.
```

The controller, and its shared `recheck`. `recheck` opens the gate when
every plate holds something of its wanted weight and re-closes it
otherwise:

```text
@create balance mechanism
drop balance mechanism
@desc balance mechanism = A counterweight rig linked to the floor plates. LOAD <thing> ONTO <plate> / UNLOAD <thing> FROM <plate>.
@set balance mechanism/recheck = ok = all([get_attr(pl, 'load') and has_tag(get(str(get_attr(pl, 'load'))), get_attr(pl, 'wants')) for pl in [get('pressure plate'), get('feather plate')]]); g = get('prize gate'); (remove_tag(g, 'closed'), remit(loc(me), 'Counterweights settle with a boom. The prize gate swings open.')) if ok and has_tag(g, 'closed') else ((add_tag(g, 'closed'), remit(loc(me), 'The balance lurches. The prize gate slams shut.')) if not ok and not has_tag(g, 'closed') else None)
```

The two verbs — stamp the `load` attribute, relocate for realism, then
re-check off the attribute we just wrote:

```text
@set balance mechanism/cmd_load = $load * onto *: it = get(trim(arg0)); pl = get(trim(arg1)); (pemit(enactor, 'You are not holding that.') if not (it and loc(it) == enactor) else (pemit(enactor, 'There is no such plate here.') if not (pl and get_attr(pl, 'wants') and loc(pl) == loc(me)) else (set_attr(pl, 'load', '#' + it.id), move_to(it, pl), remit(loc(me), name(enactor) + ' sets ' + name(it) + ' on ' + name(pl) + '.'), eval_attr(me, 'recheck'))))
@set balance mechanism/cmd_unload = $unload * from *: pl = get(trim(arg1)); it = get(trim(arg0)); (pemit(enactor, 'That is not on that plate.') if not (it and pl and loc(it) == pl) else (del_attr(pl, 'load'), move_to(it, enactor), remit(loc(me), name(enactor) + ' lifts ' + name(it) + ' off ' + name(pl) + '.'), eval_attr(me, 'recheck')))
```

Finally the props — one of each weight, plus an unmarked decoy that
satisfies nothing:

```text
@create iron ingot
@tag iron ingot = heavy
drop iron ingot
@create dried feather
@tag dried feather = light
drop dried feather
@create clay shard
drop clay shard
```

## Try it

Pick up the props (`get iron ingot`, `get dried feather`) and load them.
One plate alone isn't enough:

```text
load iron ingot onto pressure plate    -> ...sets iron ingot on pressure plate.   (gate still shut)
load dried feather onto feather plate  -> Counterweights settle with a boom. The prize gate swings open.
prize gate                             -> the Prize Room
```

Take the ingot back and the gate answers immediately:

```text
unload iron ingot from pressure plate  -> The balance lurches. The prize gate slams shut.
```

The decoy proves the sensing is by *type*: `load clay shard onto pressure
plate` leaves the gate shut — the shard has no `heavy` tag — and
loading the ingot *as well* opens it (any wanted item on the plate
counts).

## Going further

- **Exact weights** — instead of a `wants` tag, give objects a numeric
  `weight` attribute and have `recheck` sum `contents(pl)` and compare to
  a target range; now over-loading a plate fails too (the classic
  "too much/too little" balance puzzle).
- **A traversal ward instead of a gate tag** — sense the plates from an
  `on_check` ward on the *room* keyed to `atype == 'event:on_leave'`
  (the [snare](053_snare.md) pattern), vetoing the walk unless the plates
  are satisfied. Wards fire only for participants (actor, room, target),
  so the room — always a participant in a departure — is where this
  sensing has to live.
- **Order-sensitive plates** — record the sequence of loads and require a
  specific order, folding in [item 209](209_lever_combination.md)'s
  compare-the-whole-list check.
- **Reset** — [item 218](218_puzzle_reset.md) shows how to sweep the
  plates clear and re-seal the gate for the next party.
