# 218. Puzzle reset engineering

> Checklist item 218 — now — *reset lifecycle, ON_RESET/zone_reset, stuck-state recovery — the meta-tutorial*

**What you'll build:** One small puzzle — turn a crank, a gate opens —
and then the thing this whole chapter has been pointing at: a **reset
system** that makes *any* puzzle safely repeatable. You'll wire the same
restore routine to three triggers — a manual `$reset`, an automatic
`ON_RESET` when the zone empties, and (by reference) instance teardown —
and use it to rescue a puzzle that a player has jammed.

**Concepts:** the reset *lifecycle* as a first-class concern; a single
`restore` function shared by every reset path; `zone_reset` + `ON_RESET`
for hands-off repopulation; and **stuck-state recovery** — the reason a
puzzle needs a reset button even when nobody wins.

## How it works

Every puzzle in this chapter ([levers](209_lever_combination.md),
[keypad](210_keypad_code.md), [plates](212_weight_plate.md),
[power](213_power_routing.md), [Simon](214_simon.md),
[maze](215_shifting_maze.md)…) ends in a *solved* world state: a gate
open, a flag set, a prop consumed. Left there, the next player finds it
already solved — or, worse, **jammed**: a required item carried off, a
sequence half-entered, a door that auto-closed on a bug. A puzzle you
ship is a puzzle you must be able to *put back*.

The discipline is one idea: **write the restore once, trigger it many
ways.**

1. **`restore` is the single source of truth.** One attribute on a
   controller returns the puzzle to its canonical state — re-seal the
   gate, clear progress attributes, and *re-materialize any prop that
   should be present*. Everything else just calls it. Because it recomputes
   the whole state (rather than undoing the last move), it works no matter
   *how* the puzzle got messed up.

2. **Three ways to fire it, one routine:**
   - **Manual** — a `$reset` command any player (or just staff) can type
     to un-stick a puzzle on the spot.
   - **Automatic** — attach `zone_reset` to the controller and put the
     restore in `ON_RESET`. The behavior fires only when the zone is
     **empty of players** (it defers while anyone's inside), so the world
     never snaps back under someone's feet — it tidies up after the room
     clears, exactly like a Diku area reset.
   - **By construction** — an [instanced](216_escape_room.md) puzzle
     needs no reset at all: each group gets a fresh copy and the reaper
     removes the old one. Reset is *the absence of shared state*.

3. **Stuck-state recovery is the acid test.** A good `restore` doesn't
   just re-seal the gate — it notices a *missing* crank and re-creates it.
   That's what turns "reset" from a convenience into a safety net: a
   griefer who walks off with the key can't brick the puzzle for everyone.

## Build it

A trial room (its own zone) and the vault behind the gate:

```text
@dig The Trial Room = trial, out
trial
@zone here = trialzone
@dig The Reward Vault = trial gate, trial
@desc The Reward Vault = A modest vault. The reward for turning the crank sits on a shelf.
@tag trial gate = closed
@set trial gate/locked = true
@set trial gate/locked_msg = The trial gate is sealed. Turn the crank.
```

The controller — a **zone master** (so `ON_RESET` reaches it), carrying
the shared `restore`:

```text
@create puzzle console
drop puzzle console
@desc puzzle console = A brass control console. TURN CRANK to work the gate; RESET PUZZLE to restore it.
@zone/master puzzle console = trialzone
@set puzzle console/restore = g = get('trial gate'); (add_tag(g, 'closed') if not has_tag(g, 'closed') else None); del_attr(me, 'progress'); (create_obj('brass crank', ['thing', 'crank'], location=loc(me)) if not [o for o in contents(loc(me)) if has_tag(o, 'crank')] else None); remit(loc(me), 'Gears clunk. The trial gate re-seals and the brass crank is back in its bracket.')
```

The puzzle itself — `$crank` needs a crank *in the room* (a prop that can
be carried off, which is how it gets stuck):

```text
@set puzzle console/cmd_crank = $crank: (pemit(enactor, 'There is no crank here to turn.') if not [o for o in contents(loc(me)) if has_tag(o, 'crank')] else (remove_tag(get('trial gate'), 'closed'), set_attr(me, 'progress', 'solved'), remit(loc(me), name(enactor) + ' turns the crank -- the trial gate grinds open.')))
```

Now the three reset paths, all pointing at `restore`. Manual, and the
`ON_RESET` hook (both run *as the console*, so `restore`'s writes carry
its authority):

```text
@set puzzle console/cmd_reset = $reset puzzle: eval_attr(me, 'restore')
@set puzzle console/on_reset = eval_attr(me, 'restore')
```

And the automatic driver — `zone_reset` fires `ON_RESET` when the zone is
due and empty:

```text
@behavior puzzle console = zone_reset
@set puzzle console/reset_interval = 300
```

Finally, seed the starting prop:

```text
@create brass crank
@tag brass crank = crank
drop brass crank
```

## Try it

Solve it, then put it back by hand:

```text
crank                -> ...turns the crank -- the trial gate grinds open.
reset puzzle         -> Gears clunk. The trial gate re-seals and the brass crank is back in its bracket.
```

Now jam it — carry the crank away, and watch a later visitor hit the
wall:

```text
get brass crank      -> (you pocket it and wander off)
crank                -> There is no crank here to turn.      (a newcomer, stuck)
reset puzzle         -> Gears clunk. ...the brass crank is back in its bracket.
crank                -> ...the trial gate grinds open.        (unstuck)
```

Because `restore` *re-creates* the missing crank rather than assuming it's
there, no amount of griefing can permanently brick the puzzle. And when
the room finally empties, the `zone_reset` behavior fires the same
`ON_RESET` on its own timer, quietly restoring the trial for the next
person — no one has to remember to type anything.

## Going further

- **Snapshot & restore** — for a puzzle with lots of moving parts, have
  `restore` read a saved `initial` dict of attribute values (captured once
  at build time) and write them all back, instead of hand-coding each one
  — a generic reset that survives you editing the puzzle.
- **Reset on solve** — chain a `wait(reward_window, 'trigger me/restore')`
  off the *win* so the puzzle re-arms a minute after each solve, giving
  one party time to claim the reward before the next resets it (item 29's
  timed-door pattern).
- **Full repop** — put mob/prop respawns in the console's `reset_spec`
  (the [zone-reset](147_zone_repop.md) vocabulary) and let `ON_RESET`
  handle only the door/flag cleanup the spec can't express — the two
  halves of a Diku area reset working together.
- **Staff-only reset** — gate `$reset puzzle` behind a role check
  (`enactor` has an `admin`/`builder` tag) so players can't skip a puzzle
  by resetting mid-attempt; keep the automatic `ON_RESET` for the
  hands-off case.
- **Reset every build in this chapter** — the same `restore`-plus-three-
  triggers shape re-seals a [lever vault](209_lever_combination.md),
  clears [weight plates](212_weight_plate.md), re-hides
  [searched objects](217_hidden_object_search.md), or re-aims a
  [shifting maze](215_shifting_maze.md). Write the restore; wire the
  triggers; ship a puzzle players can actually play twice.
