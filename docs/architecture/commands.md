# Command Dispatch

The command dispatcher routes player input to command handlers. Its home
is `realm.commands` — the command system's own package (`Command`,
`CommandContext`, `CommandDispatcher` live in
`realm/commands/dispatcher.py`; the server *hosts* a dispatcher, it
doesn't own the types).

## Declaring Commands

A command belongs to a feature (see [Features](../guides/features.md)).
The game declares its own in `game.py`; the built-in ones are declared the
same way in `realm/std/`:

```python
# mygame/game.py
from realm.commands import CommandContext
from realm.features import Feature

feature = Feature("mygame")

@feature.command("wave", aliases=["wav"], help_text="Wave at someone",
                 usage="wave [target]", permission="player", category="social")
async def cmd_wave(ctx: CommandContext) -> None:
    """Wave at someone."""
    if ctx.args:
        await ctx.session.send(f"You wave at {ctx.args}.")
    else:
        await ctx.session.send("You wave.")
```

When the world is built, `FeatureSet.install_runtime` registers every
declared command of the loaded features on the world's dispatcher
(`CommandDispatcher.register`). A command name or alias declared by two
features raises `FeatureError` naming both, unless one says `replace=True`.
A feature left out of `FEATURES` contributes no commands, so they are
unknown and absent from `help`.

`help` derives its listing from these declarations — set `category` (the
feature's name by default) and `help_text` and your command documents
itself.

## Commands are thin wrappers over ops

A command that changes the world parses its arguments, resolves names, and
calls the op for that operation in `realm/core/ops/` (`ops.set_attr`,
`ops.tag`, `ops.dig`, ...). The op checks authority and raises an
`OpError` whose `.reason` is shown to the player; softcode calls the same
op, so `@tag` and `add_tag()` cannot disagree. `realm.commands.base.run_op`
is the wrapper:

```python
from realm.commands.base import resolve_target, run_op
from realm.core import ops

async def cmd_tag(ctx):
    target = resolve_target(ctx, ctx.left_args.strip())
    result = await run_op(ctx, ops.tag, target, ctx.right_args)  # refusal already sent
    if result is not None and result.value:
        await ctx.session.send(f"Added tag to {target.name}.")
```

`run_op` sends the refusal, saves every object the op touched, and prints
its warnings. A game's own command uses the same ops.

The command's `permission` tier is still checked first by the dispatcher;
the op's authority check runs underneath it.

## Command Context

Handlers receive a `CommandContext` with:

```python
CommandContext(
    session,        # the player's session
    player,         # the player GameObject (guaranteed for handlers)
    command_name,   # the matched command
    args,           # everything after the command
    raw_input,      # the full line
    left_args, right_args,  # split on '=' when parse_equals=True
    switches,       # ['tag'] from "@find/tag"
    dispatcher,     # services: dispatcher.persistence, etc.
)
```

## Command Resolution Order

1. **Exact / alias match** - `look`, or `l` if aliased
2. **Token shortcuts** - `"hello` = say, `:waves` = pose
3. **Exit names** - `north`, `trapdoor` walk matching exits
4. **Unknown handler** - falls through to softcode `$`-command search

## Login vs Playing Commands

The dispatcher has separate handlers:

- **Login handler** - For unauthenticated sessions (`connect`, `create`, `quit`)
- **Command handlers** - For authenticated sessions

```python
# Set the login handler
dispatcher.set_login_handler(my_login_handler)

# Set fallback for unknown commands
dispatcher.set_unknown_handler(my_unknown_handler)
```

## Built-in Commands

| Command | Aliases | Description |
|---------|---------|-------------|
| `look` | `l` | Look at current room |
| `say` | `'` | Say something |
| `pose` | `:` | Emote an action |
| `who` | | List online players |
| `inventory` | `i`, `inv` | List carried items |
| `help` | `?` | Show available commands |
| `quit` | `QUIT` | Disconnect |

## Adding Custom Commands

See [Your First Game](../getting-started/first-game.md) for examples of adding game-specific commands.
