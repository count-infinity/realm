# 196. Personal aliases (nicks)

> Checklist item 196 ([now]): *carried gadget, $-commands, force(), multi-line macros*

**What you'll build:** a nick ring you carry that turns short words into
full commands: `fetch <thing>` for `get <thing>`, `stow <thing>` for
`drop <thing>`, and a `patrol` macro that runs a whole sequence, all
private to you.

**Concepts:** `$`-commands on an inventory gadget, [`force()`](../reference/softcode.md#fn-force)
to run a command *as* the enactor, parametric patterns (`*`), and a
multi-step macro written as a `'''` heredoc loop.

## How it works

A nick is a short word you type that expands into a real command. The
finished ring holds three of them, and every one is a `$`-command stored
on an object in your inventory, so the ring itself is the whole feature.
This section answers three questions: why a carried object gives you
private shorthands, how a short verb reaches the real command, and how one
verb runs several commands in a row.

### Why does a carried object give me private aliases?

REALM ships no `nick` or `alias` command, and it needs none, because a
`$`-command on an object you carry already behaves as a personal alias.
Your inventory sits on the command-search path, so any verb you set on a
carried gadget answers only when you type it. Give the same-named ring to
two players and each carries a separate object, so each gets their own
private shorthands. That is per-player nicks with no engine feature.

Pick verbs the engine does not already own. A word is matched first
against builtins, their aliases, and unique command prefixes, then against
room exits, and only a word that matches none of those falls through to
your ring; a word that collides is handled by the engine and your nick
never fires. Movement is the one place REALM ships shorthands for you:
`n`/`s`/`e`/`w` (and `ne`/`sw`/`u`/`d`, plus `in`/`out`) are built-in
direction aliases, expanded before dispatch, so a nick earns its keep on
the shortcuts the engine leaves to you (`fetch`, `stow`, a named route).

### How does a short verb reach the real command?

The bridge from a short verb to a real command is
[`force(enactor, "command")`](../reference/softcode.md#fn-force), which
runs a command through the real dispatcher as the enactor, with full
parsing, permissions, and propagation. Your ring is owned by you, so it
carries your authority, which means `force(enactor, ...)` aimed at
yourself is allowed and the forced command behaves as if you had typed it.
Because `force` re-enters the dispatcher, an alias expands only to things
you may actually do: no privilege is gained, and a forced move still
respects a locked exit.

Two shapes cover everything. A parametric alias captures the rest of the
line: `$fetch *` binds whatever follows as `arg0`, and
`force(enactor, 'get ' + trim(arg0))` re-issues it, so `fetch wrench` runs
`get wrench`. [`trim(arg0)`](../reference/softcode.md#fn-trim) removes the
leading and trailing whitespace from the captured argument. A macro is a
`$`-verb that forces *several* commands in order, which reads best as a
heredoc loop, the multi-line body of
[240](240_builder_triggers.md)'s trigger pattern, bounded by the sandbox
like any script.

## Build it

The `@create` command drops the ring straight into your inventory, so
there is nothing to `drop`; it is already on the command-search path.

```text
@create nick ring
```

Set two parametric aliases. The `*` captures the rest of the line as
`arg0`, and `force` re-issues it as a real `get` or `drop`, so each is a
single expression and stays a one-liner.

```text
@set nick ring/cmd_fetch = $fetch *: force(enactor, 'get ' + trim(arg0))
@set nick ring/cmd_stow = $stow *: force(enactor, 'drop ' + trim(arg0))
```

The `patrol` macro forces several commands in sequence: step north, take
the relic in the room beyond, and step back south. A multi-step body reads
best as a heredoc, so end the `@set` line with `'''`, put the `$patrol:`
trigger pattern on its own first line, and write the loop beneath it as
ordinary softcode.

```text
@set nick ring/cmd_patrol = '''
$patrol:
# the $patrol: pattern leads; the forced steps run in order after the body
for step in ['north', 'get relic', 'south']:
    force(enactor, step)
'''
```

## Try it

Standing in the Barracks with an Armory to the north and a relic waiting
there:

```text
> fetch pebble
You pick up a pebble.
> stow pebble
You drop a pebble.
> patrol
You leave north.
You pick up a relic.
You leave south.
```

After `patrol` you are back in the Barracks holding the relic, three
commands from one word. Each step runs as a forced command, so the rooms
you pass through are not re-described; you see the actions themselves.

Every alias runs through the real dispatcher, so it gains no privilege and
reaches nothing you could not reach yourself. A locked exit still refuses a
forced move, and the refusal comes straight back to you:

```text
> patrol
You leave north.
You pick up a relic.
You can't go south — it's locked.
```

## Going further

- **Object nicks:** `$x *` with `force(enactor, 'examine ' + trim(arg0))`,
  or a fixed `$bank` with `force(enactor, 'go north')` for a route you
  walk often.
- **Guarded macros:** wrap a force in
  [`if_else(...)`](../reference/softcode.md#fn-if_else) so a step only
  fires under the right condition (in combat, holding a key).
- **Shared instead of personal:** drop the ring in a room rather than
  carrying it and the aliases become *room* verbs everyone there can use,
  the same gadget at a different scope.
- **The safety story:** aliases are sandboxed scripts, so the
  [250](250_player_scripting.md) limits (call, time, and output caps, and
  no privilege escalation) are exactly what keeps player-authored nicks
  safe.
```
