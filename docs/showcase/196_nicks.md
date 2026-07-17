# 196. Personal aliases (nicks)

> Checklist item 196 — [now] — *carried gadget, $-commands, force(), multi-line macros*

**What you'll build:** a nick ring you carry that turns short words into
full commands — `fetch <thing>` for `get <thing>`, `stow <thing>` for
`drop <thing>`, and a `patrol` macro that runs a whole sequence — all
private to you.

**Concepts:** `$`-commands on an inventory gadget, `force()` to run a
command *as* the enactor, parametric patterns (`*`), and multi-step
macros via a comprehension.

## How it works

REALM has no built-in `nick`/`alias` command — and it doesn't need one,
because a `$`-command on an object you carry *is* a personal alias. Your
inventory is on the command-search path, so any verb you set on a carried
gadget answers only for you; give the same-named ring to two players and
each gets their own private shorthands. That is nicks, per-player, with
no engine feature.

The bridge from a short verb to a real command is **`force(enactor,
"command")`**: it runs a command through the real dispatcher as the
enactor, with full parsing and permissions. Your ring is owned by you, so
it wields your authority — `force(enactor, ...)` on *yourself* is
allowed, and the forced command behaves exactly as if you'd typed it.

Two shapes cover everything:

- **Parametric alias:** `$fetch *` captures the rest as `arg0` →
  `force(enactor, 'get ' + trim(arg0))`. `fetch wrench` runs `get
  wrench`. `trim(arg0)` cleans the captured argument.
- **Macro:** a `$`-verb that forces *several* commands. A comprehension
  queues them in order — the multi-line body of
  [240](240_builder_triggers.md)'s trigger pattern, bounded by the
  sandbox like any script.

Pick verbs the engine doesn't already own. Movement is the one place
REALM ships shorthands for you — `n`/`s`/`e`/`w` (and `ne`/`sw`/`u`/`d`)
are built-in direction aliases, expanded before dispatch — so a nick is
for the shortcuts it *doesn't* give you (`fetch`, `stow`, a named route).
A word with no builtin, alias, or unique-prefix match falls through to
your ring; a word that collides is handled by the engine first and your
nick never fires.

Because `force` re-enters the dispatcher, an alias can only expand to
things you may actually do — no privilege is gained, and a forced move
still respects locked doors.

## Build it

`@create` leaves the ring in your inventory, already carried — nothing to
drop:

```text
@create nick ring
@set nick ring/cmd_fetch = $fetch *: force(enactor, 'get ' + trim(arg0))
@set nick ring/cmd_stow = $stow *: force(enactor, 'drop ' + trim(arg0))
@set nick ring/cmd_patrol = $patrol: [force(enactor, c) for c in ['north', 'get relic', 'south']]
```

`cmd_fetch` and `cmd_stow` are parametric — the `*` captures whatever
follows and `force` re-issues it as `get`/`drop`. `cmd_patrol` is the
macro: step north, grab the relic there, step back south; the
comprehension is just a way to run a list of forces in order on one line.

## Try it

Standing in the barracks with an armory to the north:

```text
> fetch pebble
You pick up a pebble.
> stow pebble
You drop a pebble.
> patrol
    ... you walk north, take the relic, and return
```

After `patrol` you're back in the barracks holding the relic — three
commands from one word. Each alias runs through the real dispatcher, so
`fetch nothing` answers "You don't see that here." exactly as `get`
would, and a locked exit still refuses a forced move.

## Going further

- **Object nicks:** `$x *` → `force(enactor, 'examine ' + trim(arg0))`,
  or a fixed `$bank` → `force(enactor, 'go north')` for a route you walk
  often.
- **Guarded macros:** put an `if_else(...)` around a force so a macro
  only fires under the right condition (in combat, holding a key).
- **Shared vs personal:** drop the ring in a room instead of carrying it
  and the aliases become *room* verbs everyone there can use — the same
  gadget, a different scope.
- **The safety story:** aliases are just sandboxed scripts, so the
  [250](250_player_scripting.md) limits (call/time/output caps, no
  privilege escalation) are exactly what keeps player-authored nicks
  safe.
