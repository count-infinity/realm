# 051. Pit Trap

> Checklist item 51 — [now] — *trap state attrs, teleport_obj, escape contests*

**What you'll build:** A rigged flagstone that drops unwary walkers into
an oubliette below — and the hard way back out: a climbable shaft that
rolls your Climbing skill every attempt.

**Concepts:** witnessed `ON_ENTER` + `teleport_obj()` as the fall,
room-owner relocation authority (why a trap may move a victim at all),
skill-gated exits (`check_skill` / `check_difficulty` /
`check_fail_msg`) as the escape, and message ordering in the script
queue.

## How it works

A pit trap is two moves the engine already knows how to make:

1. **The fall is a `teleport_obj()`.** Movement in REALM is one
   primitive with two doors: walking (gated by wards, closed doors,
   skill checks) and *placement* — `teleport_obj()`, which relocates
   straight to a destination. A trapdoor is placement: no exit is
   traversed, the floor simply stops being under you.

   The authority is the interesting part. Softcode may normally move
   only what it controls — but relocation is deliberately a *weaker*
   authority than full control: **a room's owner may move whatever is
   standing in that room** (PennMUSH's `tport_control_ok`, alive and
   well here). The flagstone runs with its owner's power, the owner
   owns the gallery, the victim is standing in the gallery — so the
   drop is legal, for *any* victim. Put the same trap in a stranger's
   room and the teleport fizzles: traps work on home turf, which is
   exactly where traps belong.

2. **The way out is a skill-gated exit** — no softcode at all. Any
   exit can carry `check_skill` and `check_difficulty`: the engine
   rolls the walker's skill at the penalty *every traversal* and turns
   failures back with your `check_fail_msg` (this is the fire-escape /
   ledge machinery from the movement engine). Name the exit `climb`
   and the escape reads like a verb: type `climb`, roll Climbing at -2,
   make it or slide back down. Failure keeps you in the cell for
   another try — an escape *contest* with no `$`-command anywhere.

The trigger itself follows the landmine's branch order (item 49): skip
non-characters, the disarmed state, and the owner; give sharp eyes an
Observation roll at -3 to sidestep; only then drop the floor. Two
details worth noticing. First, the script *pemits the fall, teleports,
then pemits the landing* — queued softcode actions run in order after
the script finishes, so the victim reads the sequence in the order it
happened to them. Second, **the fall springs the trap** (`armed = 0`,
the mine's spent-casing rule): the doors hang open until the owner
resets them. This is load-bearing, not just flavor — a climber
emerging from the pit *arrives in the gallery* and would land squarely
on a still-armed plate, falling forever. State on the trap is what
makes the loop escapable.

## Build it

The gallery, and the cell below it (dug unlinked — the only honest way
in is through the floor):

```text
@dig The Dusty Gallery = gallery, out
@dig The Oubliette
gallery
```

The flagstone. `armed` is the trap's one switch:

```text
@create rigged flagstone
drop rigged flagstone
@desc rigged flagstone = One flagstone sits a shade lower than its brothers.
@set rigged flagstone/armed = 1
@set rigged flagstone/on_enter = x = enactor; (None if not (V('armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x != owner(me)) else (pemit(x, 'A flagstone shifts under your toe -- you step around it just in time.') if skill_check(x, 'observation', -3) else (set_attr(me, 'armed', 0), remit(loc(me), f'{name(x)} vanishes through the floor with a crash!'), pemit(x, 'The floor drops away beneath you!'), teleport_obj(x, 'The Oubliette'), pemit(x, 'You land hard on cold stone, far below.'))))
```

The climb out — an exit with the skill gate on it, built from inside
the cell:

```text
@teleport me = The Oubliette
@desc here = A stone box that smells of old rain. The only light is a grey coin of sky at the top of a rough shaft.
@open climb = The Dusty Gallery
@desc climb = A rough shaft, half handholds, half wishful thinking.
@set climb/check_skill = climbing
@set climb/check_difficulty = 2
@set climb/check_fail_msg = You claw halfway up the slick stone and slide back down.
@teleport me = The Dusty Gallery
```

## Try it

Send in two walkers:

```text
(Observation 13)  -> A flagstone shifts under your toe -- you step around it just in time.
(Observation 6)   -> The floor drops away beneath you!
                     You land hard on cold stone, far below.
(the gallery sees) Zeke vanishes through the floor with a crash!
```

From the cell:

```text
climb   (Climbing 8)   -> You claw halfway up the slick stone and slide back down.
climb   (Climbing 12)  -> you're back in the gallery
```

Every `climb` is a fresh roll — a weak climber is not stuck forever,
just late. And the climber surfaces safely, because their own fall
sprang the doors; `@set rigged flagstone/armed = 1` closes the floor
over the next group.

## Going further

- **Self-resetting doors** — end the fall branch with
  `wait(60, 'trigger me/rearm')` and a one-line `rearm` attribute
  (`set_attr(me, 'armed', 1)`): a dungeon that maintains itself — but
  mind climbers still below.
- **Fall damage** — the flagstone can't hurt someone a room below
  (damage is proximity authority), so put an `on_enter` on the
  *Oubliette* itself: `damage(enactor, roll('1d6'))` for anyone who
  arrives — trapdoor victims and careless teleporters alike.
- **A rope changes everything** — drop the `check_difficulty` to 0
  when a `rope` object is present in the cell:
  `[o for o in contents(here) if has_tag(o, 'rope')]` in an inline
  `[[...]]` desc tells climbers their odds changed.
- **Oubliette with company** — a `wandering`-behavior rat (item 60)
  zone-leashed to the cell makes waiting for rescue worse.
