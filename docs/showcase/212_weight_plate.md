# 212. Weight-plate puzzle

> Checklist item 212 ([now]): *contents sensing, tag-typed objects, recheck-on-change*

**What you'll build:** Two pressure plates set into the floor. Load the
*heavy* object onto the pressure plate and the *light* object onto the
feather plate and the prize gate swings open; take the wrong thing back
off and it slams shut again. The puzzle senses what is sitting on each
plate.

**Concepts:** plates as containers, tag-typed objects (a "weight" is a
tag), `$`-commands standing in for the built-in placement verbs, one
shared subroutine reached with
[`eval_attr`](../reference/softcode.md#fn-eval_attr) that **re-checks the
whole puzzle whenever a plate changes**, and the queued nature of
[`move_to`](../reference/softcode.md#fn-move_to).

## How it works

The finished machine has three parts: two plates, each declaring the tag
it wants; a controller object owning the `load` and `unload` verbs plus a
shared `recheck` routine; and a sealed gate whose `closed` tag the
controller adds and removes. Every load and every unload ends by running
the same re-check, which recomputes the whole puzzle and moves the gate to
match. This section answers the three questions a builder hits in order:
why the puzzle brings its own verbs, why each plate records what was put
on it instead of reading its own contents, and why the check re-evaluates
everything every time.

### Why `load` rather than `put`?

`put` (alias `place`) and `get` (aliases `take` and `grab`) are built-in
commands, and builtins dispatch before `$`-commands, so softcode never
shadows them. A puzzle that wants placement wording of its own therefore
picks free words, and `load <thing> onto <plate>` with
`unload <thing> from <plate>` gives the controller a matched pair it owns
end to end: one place that records the placement, one place that runs the
check, and identical treatment in both directions.

Sensing through the built-in verbs is possible too, because a reaction
hook sees the world *after* the effect: a plate's `ON_PUT` runs once the
item is already seated, so [`contents(me)`](../reference/softcode.md#fn-contents)
inside it already includes that item. That is the hook trio at work, where
an `on_check` ward sees the world before the effect and may `block()`, the
effect then runs, and finally the
[`ON_<EVENT>` hooks](../reference/softcode.md#lifecycle-hooks) observe the
result (see [Action Propagation](../architecture/events.md) and the
[event bus tour](245_event_bus_tour.md)). "Going further" wires that
variant, with the guard such a hook always needs.

### Why the plate records the item instead of reading its contents

`move_to` is queued rather than immediate. It authorizes the relocation
and hands it to the engine, and the move lands once the script has
finished, which means that inside the same script both `contents(plate)`
and [`loc(item)`](../reference/softcode.md#fn-loc) still describe the
world as it was before the move. Both verbs therefore stamp the plate with
a `load` attribute holding the item's id (`'#' + it.id`), which
[`set_attr`](../reference/softcode.md#fn-set_attr) writes immediately, and
the re-check reads that attribute rather than the plate's contents.

### How a plate knows what it wants

Each plate stores `wants`, the name of a tag, so the pressure plate wants
`heavy` and the feather plate wants `light`. An item satisfies a plate
when it carries that tag, which
[`has_tag`](../reference/softcode.md#fn-has_tag) plus
[`get_attr`](../reference/softcode.md#fn-get_attr) settle in one line as
`has_tag(item, get_attr(pl, 'wants'))`. REALM has no weight kernel of any
kind, so weight is always a convention the builder chooses:
[item 14](014_basic_container.md) and [item 17](017_bag_of_holding.md)
choose a numeric `weight` attribute and sum it, while this puzzle only
needs to sort items into kinds, so a tag carries the whole idea. The first
"Going further" idea swaps in the numeric version.

### Why the check re-evaluates everything

`recheck` walks both plates, asks each whether the item recorded on it
carries the wanted tag, and then sets the gate: all satisfied strips the
`closed` tag, anything missing puts it back. Nothing in it depends on
which plate changed or how, so loading, unloading, and swapping are all
covered by the one routine, and running it twice in a row changes nothing
the second time. Both verbs call it as
`eval_attr(me, 'recheck')`, which runs the routine with the caller's
authority and leaves the executor alone, so `me` inside `recheck` is still
the mechanism and `loc(me)` is still the chamber.

The gate itself is the `closed` plus `locked` exit from
[item 209](209_lever_combination.md), where `closed` blocks the walk and
`locked` makes the built-in `open` verb refuse with `locked_msg`, so only
the controller's tag writes ever move it.

## Build it

Dig the chamber and the prize room behind it, then seal the gate the way
item 209 seals its vault:

```text
@dig The Trial Chamber = chamber, out
chamber
@dig The Prize Room = prize gate, chamber
@desc The Prize Room = A small vault. A single reliquary waits on a pedestal.
@tag prize gate = closed
@tag prize gate = locked
@set prize gate/locked_msg = The prize gate is seamless stone. The plates in the floor must be satisfied.
```

Set the two plates into the floor and stand the controller beside them.
The `container` tag marks a plate as something that holds items, which is
what the built-in `open` and `close` verbs key on; the seating itself is
[`move_to`](../reference/softcode.md#fn-move_to)'s job, and it will put an
item into whatever destination you name:

```text
@create pressure plate
drop pressure plate
@tag pressure plate = container
@desc pressure plate = A broad iron plate, sprung to sink under real weight.
@create feather plate
drop feather plate
@tag feather plate = container
@desc feather plate = A gossamer plate that trembles at a breath; any real load would jam it.
@create balance mechanism
drop balance mechanism
@desc balance mechanism = A counterweight rig linked to the floor plates. LOAD <thing> ONTO <plate> / UNLOAD <thing> FROM <plate>.
```

Each plate declares the tag it wants as a plain data attribute, which is
the only thing that distinguishes one plate from the other:

```text
@set pressure plate/wants = heavy
@set feather plate/wants = light
```

Now the shared routine. `recheck` walks the plates, resolves whatever each
one has recorded, decides whether every plate is satisfied, and then opens
or re-closes the gate, announcing the change with
[`remit`](../reference/softcode.md#fn-remit) only when the gate actually
moves:

```text
@set balance mechanism/recheck = '''
ok = True
for pl in [get('pressure plate'), get('feather plate')]:
    stamped = get_attr(pl, 'load')
    item = get(str(stamped)) if stamped else None
    if not (item and has_tag(item, get_attr(pl, 'wants'))):
        ok = False
gate = get('prize gate')
shut = has_tag(gate, 'closed')
if ok and shut:
    remove_tag(gate, 'closed')
    remit(loc(me), 'Counterweights settle with a boom. The prize gate swings open.')
elif not ok and not shut:
    add_tag(gate, 'closed')
    remit(loc(me), 'The balance lurches. The prize gate slams shut.')
'''
```

`load` checks that the player is holding the thing and that the named
plate is one of ours standing in this room, then records the placement,
sends the item across, tells the room, and re-checks:

```text
@set balance mechanism/cmd_load = '''
$load * onto *:
it = get(trim(arg0))
pl = get(trim(arg1))
if not (it and loc(it) is enactor):
    pemit(enactor, 'You are not holding that.')
elif not (pl and get_attr(pl, 'wants') and loc(pl) is loc(me)):
    pemit(enactor, 'There is no such plate here.')
else:
    # move_to lands after this script ends, so record the placement first
    set_attr(pl, 'load', '#' + it.id)
    move_to(it, pl)
    remit(loc(me), f'{name(enactor)} sets {name(it)} on {name(pl)}.')
    eval_attr(me, 'recheck')
'''
```

`unload` is the mirror image: it verifies the item really is on that
plate, clears the record with
[`del_attr`](../reference/softcode.md#fn-del_attr), hands the item back,
and runs the very same check:

```text
@set balance mechanism/cmd_unload = '''
$unload * from *:
it = get(trim(arg0))
pl = get(trim(arg1))
if not (it and pl and loc(it) is pl):
    pemit(enactor, 'That is not on that plate.')
else:
    del_attr(pl, 'load')
    move_to(it, enactor)
    remit(loc(me), f'{name(enactor)} lifts {name(it)} off {name(pl)}.')
    eval_attr(me, 'recheck')
'''
```

Finally the props, one of each weight plus an unmarked decoy that
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

Stand in the Trial Chamber, pick up the two marked props, and load them
one at a time. Watch for the silence after the first load, since one plate
alone leaves the gate shut and the boom only arrives when both are
satisfied:

```text
> get iron ingot
You pick up an iron ingot.

> get dried feather
You pick up a dried feather.

> load iron ingot onto pressure plate
Bilda sets iron ingot on pressure plate.

> load dried feather onto feather plate
Bilda sets dried feather on feather plate.
Counterweights settle with a boom. The prize gate swings open.

> prize gate
You leave prize gate.

The Prize Room
--------------
A small vault. A single reliquary waits on a pedestal.

Exits: chamber
```

Walk back and take the ingot off again; the same routine answers
immediately, with the gate line arriving right after the room sees the
lift:

```text
> chamber
You leave chamber.

The Trial Chamber
-----------------

You see:
  a pressure plate
  a feather plate
  a balance mechanism
  a clay shard

Exits: out, prize gate

> unload iron ingot from pressure plate
Bilda lifts iron ingot off pressure plate.
The balance lurches. The prize gate slams shut.
```

The decoy is the step worth confirming deliberately, because it proves the
sensing goes by *kind* rather than by presence. You are still holding the
ingot after that unload and the feather is still on its own plate, so
carry straight on: loading the clay shard onto the pressure plate moves
the shard and says so, yet the gate stays shut since the shard carries no
`heavy` tag, and loading the ingot onto that same plate afterwards opens
it:

```text
> get clay shard
You pick up a clay shard.

> load clay shard onto pressure plate
Bilda sets clay shard on pressure plate.

> load iron ingot onto pressure plate
Bilda sets iron ingot on pressure plate.
Counterweights settle with a boom. The prize gate swings open.

> look pressure plate

pressure plate
A broad iron plate, sprung to sink under real weight.

Contains:
  clay shard
  iron ingot
```

The plate now holds two things while its record names only the newest one,
which is the item satisfying it. Ask for the shard back at this point and
the record goes with it, so the gate shuts although the ingot is still
lying there:

```text
> unload clay shard from pressure plate
Bilda lifts clay shard off pressure plate.
The balance lurches. The prize gate slams shut.
```

That is the honest limit of a one-item record, and the first "Going
further" idea, which weighs the plate's contents instead, is the version
that survives stacking.

## Going further

- **Exact weights.** Replace the `wants` tag with a numeric `weight`
  attribute on the props, in the convention
  [item 14](014_basic_container.md) uses, and have `recheck` sum
  `get_attr(o, 'weight', 0)` across `contents(pl)` and compare against a
  target range, so overloading a plate fails as surely as underloading it.
- **Sense from the plate's own `ON_PUT`.** Because reaction hooks see
  post-effect state, a plate can keep its own record when a player reaches
  for the built-in `put`, with the item arriving in the payload as
  [`adata('item')`](../reference/softcode.md#event-data-namespace) while
  `target` is the container:

    ```text
    @set pressure plate/on_put = '''
    if target is me:  # an ON_PUT fires on every object in the room
        set_attr(me, 'load', '#' + adata('item').id)
        eval_attr(get('balance mechanism'), 'recheck')
    '''
    ```

    The guard is compulsory here, and it is an identity check, `is` rather
    than `==` (see
    [Guard on `target`](../reference/softcode.md#guard-on-target)): drop
    it, and putting the ingot into the pressure plate makes the *feather*
    plate record that ingot as its own too. Removal is the harder half,
    because `ON_GET` runs after the item has moved, which leaves
    `loc(target)` pointing at the taker with no trace of the plate it came
    from, so a plate reacting that way should re-derive its record from
    `contents(me)` rather than trust the event.
- **Order-sensitive plates.** Record the sequence of loads on the
  controller and require one specific order, folding in
  [item 209](209_lever_combination.md)'s compare-the-whole-list check.
- **Reset.** [Item 218](218_puzzle_reset.md) covers the reset lifecycle
  that makes a puzzle repeatable: clear each plate's `load`, return the
  props to the floor, and re-add the gate's `closed` tag.
