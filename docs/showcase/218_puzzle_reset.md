# 218. Puzzle reset engineering

> Checklist item 218 ([now]): *reset lifecycle, ON_RESET/zone_reset, instances, $reset scripts, stuck-state recovery*

**What you'll build:** A one-move puzzle (turn a crank, a gate opens) wrapped
in the thing this chapter has been pointing at, which is a reset system that
makes the puzzle safely repeatable. A single `restore` routine is wired to a
manual `reset puzzle` command and to an automatic
[`ON_RESET`](../reference/softcode.md#lifecycle-hooks), and it rescues a
puzzle that a player has jammed by walking off with the crank.

**Concepts:** the reset *lifecycle* as a first-class concern; one `restore`
attribute shared by every reset path;
[`eval_attr`](../reference/softcode.md#fn-eval_attr) and whose authority a
shared routine runs with; the `zone_reset` behavior plus `ON_RESET` for
hands-off repopulation; the [`target` guard](../reference/softcode.md#guard-on-target)
that keeps a hook on its own business; and stuck-state recovery, which is why
a puzzle needs a reset even when nobody wins.

## How it works

The finished machine is three objects and one routine. A sealed `trial gate`
is the prize, a `brass crank` is the prop that opens it, and a `puzzle
console` owns both the puzzle logic and the routine that puts everything
back. Every way of resetting the puzzle calls that one routine, so there is
exactly one description of "correct" in the build. This section answers four
questions in the order you hit them: what a reset actually has to put back,
where the routine lives and whose authority it runs with, what fires it, and
why the automatic path needs a guard.

The puzzle here is deliberately tiny and self-contained, because the subject
is the reset rather than the puzzle. The console and crank below are this
tutorial's own; the [lever vault](209_lever_combination.md) stays where it
is, and its "Going further" points back here for the shape rather than for
these objects.

### What does a reset have to put back?

Every puzzle in this chapter ([levers](209_lever_combination.md),
[keypad](210_keypad_code.md), [plates](212_weight_plate.md),
[power](213_power_routing.md), [Simon](214_simon.md),
[maze](215_shifting_maze.md)) ends in a *solved* world state: a gate open, a
flag set, a prop moved. Left that way, the next player finds the puzzle
already solved, or finds it **jammed**, which is worse: a required item
carried off, a sequence half-entered, a door left open by a path you never
tested.

So `restore` **recomputes the canonical state** instead of undoing the last
move. It re-seals the gate, clears the progress attribute, and re-creates the
crank if no crank is in the room. Recomputing is what makes it total, because
it lands the puzzle in the same shape no matter which of the many broken
states it started from, including the ones you never anticipated. That is the
difference between a convenience and a safety net: a player who wanders off
with the crank inconveniences the next visitor for one reset cycle rather
than bricking the puzzle for everybody.

### Where does the routine live, and whose authority does it run with?

`restore` is an ordinary attribute on the console, and every reset path
reaches it with
[`eval_attr(me, 'restore')`](../reference/softcode.md#fn-eval_attr), which
runs an attribute as a subroutine.

The detail that decides the whole design is that `eval_attr` runs with the
**caller's** authority, and `me` inside the routine is the **caller**, not
the object holding the attribute. Both callers below are the console itself
(a `$`-command on the console and the console's own `ON_RESET`), so `me` is
the console and the routine writes the gate under the console's authority,
which it has because the builder who dug the gate also created the console.
Call the same routine from a player's script and you get a very different
result: `me` becomes the player, so
[`del_attr`](../reference/softcode.md#fn-del_attr) clears an attribute on the
player, [`add_tag`](../reference/softcode.md#fn-add_tag) on the gate is
refused for lack of control, and only the
[`remit`](../reference/softcode.md#fn-remit) line lands. Keep the callers on
the console and the routine keeps its authority.

### What fires it?

Three paths, one routine:

1. **Manual.** A `$reset puzzle` command on the console, which any player can
   type to un-stick the puzzle on the spot. The script runs as the console
   whoever types it, so no player needs rights over the gate. (See "Going
   further" for gating it to staff.)
2. **Automatic.** Attach the `zone_reset` behavior to the console and put the
   restore in [`ON_RESET`](../reference/softcode.md#lifecycle-hooks). The
   behavior fires that event only when the zone is **due and empty of
   players**, so an occupied zone defers and the world never snaps back under
   someone's feet, exactly like a Diku area reset. [147, zone
   repop](147_zone_repop.md) drives the same behavior for mobs.
3. **By construction.** An [instanced](216_escape_room.md) puzzle needs no
   reset at all, because
   [`enter_instance()`](../reference/softcode.md#fn-enter_instance) hands each
   party a private copy and the idle-instance reaper tears the copy down once
   it has been empty for its `instance_ttl`. Reset is the absence of shared
   state.

### Why the automatic path needs a target guard

`ON_RESET` is a reactive hook, and reactive hooks reach **every object in the
room**, not only the object the event named. Fire a reset at one zone master
and a second console standing beside it hears the same event, so an unguarded
`on_reset` on the neighbour runs its restore too. The fix is the standard
[guard on `target`](../reference/softcode.md#guard-on-target): open the body
with `if target is me:` (identity, not `==`) and indent the reaction under
it. `zone_reset` fires the event *at* the master, so the guard reads true on
the master whose zone reset and false on every bystander in the room.

The guard has one consequence worth knowing before it confuses you.
`@tr puzzle console/on_reset` leaves `target` bound to `None`, because there
is no action behind a manual trigger, so the guard is false and the hook
quietly does nothing. To exercise the restore by hand, call the routine
directly with `@tr puzzle console/restore`, or just type `reset puzzle`. The
`$`-commands need no guard at all, since a `$`-command only runs on the
object whose pattern matched.

### What the timer actually counts

`reset_interval` is in **wall-clock seconds**, and `zone_reset` compares it
against the time of the last successful reset, so `300` means "try roughly
every five minutes". The world tick polls the behavior on its own cadence
(about every four seconds), which makes the interval a floor rather than an
exact alarm. Two details of the timer are worth knowing: the console has
no recorded last reset when you build it, so the puzzle restores itself on
the first tick that finds the zone empty; and while a player is present the
timer keeps counting, so the reset lands on the first tick after the last
player leaves.

The presence check walks the rooms **tagged into the zone**, which is why the
build below tags the Reward Vault as well as the Trial Room. A room you
forget to tag is invisible to the gate, and the gate would re-seal on a
player standing behind it.

## Build it

Dig the trial room and the vault behind the gate, and tag **both** rooms into
one zone so the presence gate sees a player anywhere in the puzzle:

```text
@dig The Trial Room = trial, out
trial
@zone here = trialzone
@dig The Reward Vault = trial gate, trial
@desc The Reward Vault = A modest vault. The reward for turning the crank sits on a shelf.
@zone The Reward Vault = trialzone
```

Seal the gate. `closed` is what movement checks and `locked` is what the
built-in `open` verb checks, and `locked_msg` is the line `open` prints
instead, so point it at the crank:

```text
@tag trial gate = closed
@tag trial gate = locked
@set trial gate/locked_msg = The trial gate is sealed. Turn the crank.
```

Stand the console in the room and crown it master of the zone, which is what
puts it in line for `ON_RESET`:

```text
@create puzzle console
drop puzzle console
@desc puzzle console = A brass control console. Two labels are engraved under the dials: CRANK works the gate, RESET PUZZLE puts it back.
@zone/master puzzle console = trialzone
```

Now the routine everything else calls. It runs four steps in order: re-seal
the gate, clear the progress attribute, re-create the crank if the room holds
none, and tell the room. [`add_tag`](../reference/softcode.md#fn-add_tag) is
idempotent, so re-sealing an already-sealed gate is safe and needs no test,
while the crank does need one, since
[`create_obj`](../reference/softcode.md#fn-create_obj) would happily mint a
second one:

```text
@set puzzle console/restore = '''
gate = get('trial gate')
add_tag(gate, 'closed')
del_attr(me, 'progress')
if not [o for o in contents(loc(me)) if has_tag(o, 'crank')]:
    # a carried-off crank is the jam this whole tutorial exists to undo
    create_obj('brass crank', ['thing', 'crank'], location=loc(me))
remit(loc(me), 'Gears clunk. The trial gate re-seals and the brass crank is back in its bracket.')
'''
```

[`get`](../reference/softcode.md#fn-get) resolves the gate by name,
[`del_attr`](../reference/softcode.md#fn-del_attr) removes the `progress`
attribute outright (rather than writing a falsy value, so `@examine` shows a
genuinely clean console), and
[`contents`](../reference/softcode.md#fn-contents) plus
[`has_tag`](../reference/softcode.md#fn-has_tag) ask the room whether a crank
is present rather than trusting a remembered flag.

The puzzle itself is one `$crank` command. It needs a crank **in the room**,
which is what makes the prop stealable and the puzzle jammable:

```text
@set puzzle console/cmd_crank = '''
$crank:
if not [o for o in contents(loc(me)) if has_tag(o, 'crank')]:
    pemit(enactor, 'There is no crank here to turn.')
else:
    remove_tag(get('trial gate'), 'closed')
    set_attr(me, 'progress', 'solved')
    remit(loc(me), f'{name(enactor)} turns the crank and the trial gate grinds open.')
'''
```

[`remove_tag`](../reference/softcode.md#fn-remove_tag) strips only `closed`,
so the gate becomes walkable while still reading as locked to the `open`
verb, and [`set_attr`](../reference/softcode.md#fn-set_attr) records the
solved state that `restore` clears. The refusal goes to one player through
[`pemit`](../reference/softcode.md#fn-pemit) while the success goes to
everyone through [`remit`](../reference/softcode.md#fn-remit).

The manual path is a single expression, so it stays a one-line `@set`:

```text
@set puzzle console/cmd_reset = $reset puzzle: eval_attr(me, 'restore')
```

The automatic path is the same call inside the `target` guard, which is what
keeps this console from restoring itself every time some *other* zone master
in the room resets:

```text
@set puzzle console/on_reset = '''
if target is me:
    # ON_RESET reaches every object in the room, so react only to our own
    eval_attr(me, 'restore')
'''
```

Attach the driver. `zone_reset` is a shipped behavior, so attaching it is all
the automation there is; the world tick polls it, and `reset_interval` is in
seconds:

```text
@behavior puzzle console = zone_reset
@set puzzle console/reset_interval = 300
```

Finally, seed the starting prop, which is an ordinary carryable thing with a
`crank` tag:

```text
@create brass crank
@tag brass crank = crank
drop brass crank
```

## Try it

Stand in the Trial Room. The gate turns away the obvious approach, the crank
opens it, and the manual reset puts it back:

```text
> open trial gate
The trial gate is sealed. Turn the crank.

> crank
Zeke turns the crank and the trial gate grinds open.

> trial gate
You leave trial gate.

The Reward Vault
----------------
A modest vault. The reward for turning the crank sits on a shelf.

Exits: trial

> trial
You leave trial.

The Trial Room
--------------

You see:
  a puzzle console
  a brass crank

Exits: out, trial gate

> reset puzzle
Gears clunk. The trial gate re-seals and the brass crank is back in its bracket.
```

The gate carries `closed` again, and as the builder you can confirm the other
half: `@examine puzzle console` listed `progress: 'solved'` a moment ago and
now lists no `progress` line at all, because `restore` deletes the attribute
rather than blanking it. Now jam the puzzle by pocketing the crank, and watch
the next visitor hit the wall:

```text
> get brass crank
You pick up a brass crank.
```

Cass arrives with the crank nowhere in the room:

```text
> crank
There is no crank here to turn.

> reset puzzle
Gears clunk. The trial gate re-seals and the brass crank is back in its bracket.

> crank
Cass turns the crank and the trial gate grinds open.
```

Two results are worth confirming deliberately. First, the room now holds
exactly one crank, because `restore` re-created the missing prop instead of
assuming one was there, and the tag check kept it from minting a duplicate
when one already sits in the bracket. Second, the automatic path reaches the
same routine with nobody typing anything: leave the zone empty and the
`zone_reset` behavior fires `ON_RESET` on the next due tick, the guard reads
`target is me` as true on the console, and the puzzle is standing ready again
before the next player walks in.

Testing the hook by hand is the one place to be careful.
`@tr puzzle console/on_reset` prints `Triggered puzzle console/on_reset.` and
changes nothing, because a manual trigger leaves `target` as `None` and the
guard is false. Use `@tr puzzle console/restore` to run the routine directly.

## Going further

- **Snapshot and restore.** For a puzzle with many moving parts, store an
  `initial` dict of attribute values captured at build time (a data literal,
  so a one-line `@set` with JSON double quotes) and have `restore` write them
  all back in a loop, which gives you a generic reset that survives your
  editing the puzzle.
- **Reset on solve.** Chain
  [`wait(60, 'trigger me/restore')`](../reference/softcode.md#fn-wait) off the
  *win* so the puzzle re-arms a minute after each solve, giving one party time
  to claim the reward before the next attempt. Waits are in-memory and die on
  restart, so use [`expire()`](../reference/softcode.md#fn-expire) or the
  `ON_RESET` path for anything that must survive a reboot. That is the
  [timed door](029_timed_door.md)'s reversion pattern.
- **Full repop.** Put mob and prop respawns in the console's `reset_spec`
  (the [zone repop](147_zone_repop.md) vocabulary) and leave `ON_RESET` the
  door and flag cleanup the spec has no words for. `ON_RESET` runs first and
  the spec's clear-and-reload follows, so the hook always sees the world
  before the mobs are rebuilt.
- **Staff-only reset.** Guard `$reset puzzle` with
  `if has_tag(enactor, 'builder'):` so players skip no puzzle by resetting
  mid-attempt, and keep the automatic `ON_RESET` for the hands-off case.
- **Reset every build in this chapter.** The same restore-plus-triggers shape
  re-seals a [lever vault](209_lever_combination.md), clears
  [weight plates](212_weight_plate.md), re-hides
  [searched objects](217_hidden_object_search.md), and re-aims a
  [shifting maze](215_shifting_maze.md). Write the restore, wire the
  triggers, and ship a puzzle players can play twice.

## Engine gaps

- `@tr <obj>/<hook>` runs a hook with no action behind it, so `target` binds
  to `None` and any `ON_<EVENT>` body written with the recommended
  `if target is me:` guard is skipped in silence. A builder testing a guarded
  hook sees `Triggered ...` and no effect. A switch that supplies a target
  (something like `@tr/target <obj>/<hook>`), or a `@fire <obj> = <event>`
  command that propagates a real action, would let a guarded hook be tested
  the way it actually runs. The workaround this tutorial uses is to put the
  body in its own attribute and `@tr` that instead.
