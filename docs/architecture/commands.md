# Command Dispatch

The command dispatcher routes player input to command handlers.

!!! note "Work in Progress"
    This documentation is being expanded.

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

# Register with aliases
dispatcher.register("wave", cmd_wave, aliases=["wav"])
```

## Command Context

Handlers receive a `CommandContext` with:

```python
@dataclass
class CommandContext:
    session: Session          # The player's session
    player: GameObject | None # The player object (if logged in)
    command: str              # The command name
    args: str                 # Everything after the command
    raw: str                  # The full input line
```

## Command Resolution Order

1. **Exact match** - `look` matches the `look` command
2. **Alias match** - `l` matches `look` if `l` is an alias
3. **Prefix match** - `lo` matches `look` if unambiguous
4. **Unknown handler** - Falls through to softcode search

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
