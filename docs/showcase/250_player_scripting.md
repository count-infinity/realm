# 250. Restricted player scripting

> Checklist item 250 — [now] — *the sandbox itself: limits, controls() authority — the capstone*

**What you'll build:** the Chrono-Cube — a gadget a *player* programs
with her own softcode and fires with `use cube`, safely. Then you'll
attack it: forbidden imports, other people's character sheets, a
25,000-call marathon, an output flood — and watch every wall hold.

**Concepts:** the script sandbox (AST validation, time/call/recursion/
output limits), owner authority (`controls()`), the `use` lock,
`@chown`'s halt-on-transfer, the enactor-consent model, attributed
output.

## How it works

Letting players write code is the oldest MU* dream and its oldest
security hole. REALM's answer — the thesis this whole arc has been
building to — is that there is no separate "player-safe" language:
players write the *same* softcode builders write, because the softcode
engine was built to be handed to adversaries from day one. Every script
in this arc, builder or player, already ran inside these walls:

1. **AST validation.** Before any script runs, its syntax tree is
   checked: no `import`, no `eval`/`exec`/`compile`/`open`, no
   `getattr`/`setattr`/`type`, no underscore names or attributes (the
   dunder escape hatches). One validator (`realm.core.safe_eval`) serves
   scripts, locks, and strategy conditions — one threat model, one place
   to fix a hole.
2. **Resource limits.** Each run gets a per-script budget: 1500 ms wall
   time, 25,000 function calls, 10,000 characters of output. Blow any of
   them and the script dies cleanly — the world op that would have
   followed never happens. Recursion is bounded too, but by the
   *process-wide* Python limit (`RECURSION_LIMIT`, default 1000), not a
   per-script one: user scripts recurse in real Python frames the engine
   can't count. A bottomless recursion still dies with a clean
   "recursion limit exceeded" rather than taking the server with it.
3. **Owner authority.** A script runs *as its object*, with its owner's
   authority. Every mutating function (`set_attr`, `move_to`,
   `destroy_obj`, `force`, ...) passes through one predicate —
   `controls()`: yourself, what you own, what your owner controls.
   A player-owned gadget can rearrange *that player's* world and
   nobody else's. Reads are open (except `password` and `secret`-flagged
   attributes); combat verbs use room proximity, same as a sword.
4. **Locks and consent.** The `use` lock gates who may fire the gadget's
   `$`-commands at all. And relocation consent is *earned*, not assumed:
   only typing an object's own `$`-command (or walking the exit whose
   `ON_FAIL` runs) lets a script move the enactor — an object that
   merely overhears or witnesses you can never teleport you.
5. **Attributed output.** A script speaks as its object — `Chrono-Cube
   says, "..."` — never as a player or an admin. Impersonation isn't
   filtered; it's unexpressible.
6. **Ownership transfer is fail-safe.** `@chown` of anything carrying
   scripts auto-tags it `halt`: the old owner's code must never run with
   the new owner's authority until the new side has reviewed it.

Because the walls are engine walls and not language subsets, the player
gets the *whole* library — loops, functions, dice, timers, prompts — and
the game risks nothing it wasn't already risking on every builder NPC.

## Build it

**Staff side.** An admin builds the gadget shell: one bootstrap verb
that stores whatever program its owner types into the cube's `ON_USE`
hook. `arg0` arrives as a *variable* (never spliced into code), the
`use` lock makes programming owner-only, and `@chown` hands it over:

```text
@create Chrono-Cube
@set Chrono-Cube/cmd_program = $program cube = *:set_attr(me, 'on_use', arg0); pemit(enactor, 'The cube chimes: program stored.')
@lock/use Chrono-Cube = caller == owner
@chown Chrono-Cube = Ada
```

`Chrono-Cube carries scripts — halted for review...` — that's wall #6
firing on our own transfer. Review what it carries, wake it, hand it
over:

```text
@examine Chrono-Cube
@untag Chrono-Cube = halt
give Chrono-Cube to Ada
```

**Player side.** Ada — no builder bit, no staff powers — programs her
cube and fires it. `use` is a built-in; it propagates `ON_USE` to the
cube with Ada as `enactor`:

```text
program cube = pemit(enactor, f'Tick. The cube counts a heartbeat for {name(enactor)}.')
use cube
```

```text
The cube chimes: program stored.
Tick. The cube counts a heartbeat for Ada.
```

That's player-authored behavior, live, with zero staff review of the
program itself — the review happened once, at the engine level.

**Now prove the walls hold.** Ada turns hostile. Sheet-writing first:
`set_attr` on another player returns `False` and touches nothing,
because the cube (owner: Ada) does not control Rook:

```text
program cube = pemit(enactor, f"hex result: {set_attr(get('Rook'), 'hp', 0)}")
use cube
```

`hex result: False` — and Rook's hp is untouched. Escape next: the AST
gate rejects the whole program before one statement runs, so even the
`pemit` before the crime never fires:

```text
program cube = import os; pemit(enactor, 'escaped!')
use cube
```

Silence. Resource exhaustion: 30,000 dice calls tears through the
25,000-call budget and the script dies before its victory lap:

```text
program cube = [rand(1, 2) for i in range(30000)]; pemit(enactor, 'survived the marathon')
use cube
```

Silence. Output flood: the room hears none of the five thousand spam
lines, because output past 10,000 characters kills the run before
*anything* is emitted:

```text
program cube = for i in range(5000): say('spam')
use cube
```

Silence. Bottomless recursion dies the same way (at the process-wide
`RECURSION_LIMIT`, default 1000):

```text
program cube = f = lambda: f(); f(); pemit(enactor, 'bottomless')
use cube
```

And the social wall. Ada leaves the cube on the workbench, and Rook —
who can now reach it — tries to make it his:

```text
drop cube
```

```text
program cube = pemit(enactor, 'MINE NOW')     <- Rook types this
```

The `use` lock (`caller == owner`) ignores him: no chime, and the stored
program is exactly as Ada left it. She picks it back up (`get cube`) and
carries on. ($-command triggers only reach players in the same room as
the object or carrying it — a gadget in Ada's pocket isn't even *visible*
to Rook's command search.)

## Try it

Give a cube to your most creative player and watch what comes back:

```text
> program cube = say(f"It is {'after' if now() % 86400 > 43200 else 'before'} noon, ship time.")
> use cube
Chrono-Cube says, "It is after noon, ship time."
```

Everything the arc taught composes here: her cube can carry `$`-verbs,
`^listen` patterns, `on_tick` heartbeats, `[[...]]` in its desc — the
full builder toolkit, fenced by her own authority.

## Going further

- **A gadget with memory:** `incr('count')` — player gadgets keep state
  like any object, and it hands back the new count; `use` becomes a
  lap counter, a dice cup, a diary.
- **Consent in action:** have Ada try `program cube =
  move_to(get('Rook'), 'The Oubliette')` — dropped, no control over
  Rook. Her cube *can* `move_to(enactor, ...)` when she herself uses it
  (moving what you control is always yours to do); a `$`-verb portal
  extends that to consenting strangers who type its command.
- **Shared workshops:** loosen the lock — `@lock/use cube =
  caller.has_tag('tinker')` — for a guild gadget several players may
  reprogram.
- **The economy of gadgets:** combine with `ON_PAYMENT` and a player can
  *sell* uses of her invention — player-authored content as an in-world
  business.

**Engine gaps:** one, precise: the sandbox's time limit is enforced in
the function-call wrapper, so a loop that calls *no* functions at all
(`while True: pass`) is never interrupted and would pin its worker
thread. Real programs hit the call/time/output budgets long before this
matters, but a belt-and-braces instruction guard (or tracing hook) would
close it; filed for the integrator.
