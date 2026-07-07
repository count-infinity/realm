# Command Dispatch

The command dispatcher routes player input to command handlers.

## Registering Commands

```python
from realm.server.dispatcher import CommandDispatcher, CommandContext

dispatcher = CommandDispatcher()

async def cmd_wave(ctx: CommandContext) -> None:
    """Wave at someone."""
    if ctx.args:
        await ctx.session.send(f"You wave at {ctx.args}.")
    else:
        await ctx.session.send("You wave.")

# Register with aliases, permission, and a help category
dispatcher.register("wave", cmd_wave, aliases=["wav"],
                    help_text="Wave at someone", usage="wave [target]",
                    permission="player", category="social")
```

`help` derives its listing from these registrations — set `category`
and `help_text` and your command documents itself.

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
