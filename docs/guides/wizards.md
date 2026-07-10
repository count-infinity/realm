# Interactive Prompts (Wizards)

Sometimes a command or an NPC needs to *stop and ask*. Character
creation is the obvious case — "pick a class", "confirm?" — but so is a
shopkeeper haggling, a locked terminal asking for a password, or a
builder tool walking you through a multi-step setup. REALM calls these
**wizards**, and there are two ways to write one: from hardcode (a
Python command) and from softcode (in-game, no restart).

Both rest on the same idea. A session can install a single **input
handler** that intercepts the player's *next* line before it reaches
the command dispatcher. While a prompt is pending, the player is
"inside" the wizard; when they answer, the handler fires and normal
command dispatch resumes.

## The escape hatch

No wizard can trap a player. A short allowlist of commands always passes
straight through to the dispatcher even mid-prompt — by default
`help`, `quit`, and `exit` — so a player can always read the docs or log
off. And `abort` (also `exit`/`quit` as words) cancels the prompt
outright, returning `None` to the wizard.

A wizard that genuinely must not be interrupted (rare — a
point-of-no-return confirmation, say) can override both: pass a custom
`allow` set and `allow_abort=False`. Prefer not to; the escape hatch is
there for a reason.

## Hardcode wizards: `await session.prompt()`

Inside any command you can simply *await* the player's answer. This
works because the telnet layer runs each input line as its own task, so
awaiting one line never blocks the session's other input.

```python
async def execute(self, ctx):
    session = ctx.session

    # Free-text question — returns the raw line, or None if aborted.
    name = await session.prompt("What shall we call your ship?")
    if name is None:
        await session.send("Maybe later.")
        return

    # Constrained to choices (prefix-matched, re-prompts until valid).
    hull = await session.prompt(
        "Hull type?", choices=["scout", "freighter", "cruiser"])

    # Yes/no convenience — returns a bool.
    if await session.confirm(f"Register the {hull} '{name}'?"):
        await session.send("Registered.")
```

Three primitives, all on the session:

| Call | Returns | Notes |
|------|---------|-------|
| `prompt(text, *, choices=None, allow=None, allow_abort=True)` | the line, or `None` | `choices` prefix-matches and re-prompts |
| `confirm(text)` | `bool` | yes/no; anything not "yes" is False |
| `choose(text, options)` | the chosen string, or `None` | prints a numbered menu; accepts number or name |

Because you're just `await`-ing, control flow is ordinary Python — loop
for validation, branch on answers, call one prompt after another. If the
player disconnects mid-wizard, the pending prompt is cancelled and your
`await` returns `None`, so always handle the `None` case.

This is exactly how character creation is built, and it survives a
reboot the same way chargen does — see [Sessions](../architecture/sessions.md).

## Softcode wizards: `prompt(target, text, callback)`

Builders don't touch Python. From softcode, `prompt` asks a player a
question and names a **callback attribute** to run when they answer.
The answer arrives as `arg0` (equivalently `%0`).

```text
# On an NPC clerk. A $-command "apply" starts the wizard:
@set clerk/cmd_apply = $apply: prompt(enactor, 'Your name, citizen?', 'on_name')

# The callback runs when the player answers. It runs AS the clerk,
# with the answer bound to arg0. Chain by prompting again.
@set clerk/on_name = set_attr(me, 'applicant', arg0)
prompt(enactor, 'And your homeworld?', 'on_world')

@set clerk/on_world = pemit(enactor, 'Welcome, ' + get_attr(me, 'applicant') + ' of ' + arg0 + '.')
```

(A multi-line callback is set the same way you set any multi-line
attribute — `|/` line breaks in a one-liner, or the OLC attribute
editor; see the [tutorial](../tutorial/04-softcode.md).)

That's a two-step dialogue tree with no restart, no Python, and full
persistence.

### The authority rule (important)

A softcode callback runs **as the executor** — the object the callback
lives on (the clerk above), *not* the player. This is deliberate: it
means a builder's wizard has exactly the builder's authority and no
more. A callback can set the clerk's own attributes, `pemit` to the
player, open a door the clerk controls, give an item — anything the
NPC could already do.

What it *cannot* do is rewrite the *player's* sheet, because the clerk
doesn't control the player. (If callbacks ran as the player, a builder's
`add_tag(me, 'admin')` would run with the player's authority — a
privilege hole. So they don't.) To configure a player, use a hardcode
command wizard, or chargen, both of which run with real authority.

### `persistent=True` — surviving a reboot

By default a softcode prompt is transient: it lives on the live session,
and a reboot forgets it. Pass `persistent=True` and the pending prompt
is written to the player's own storage (`db.input_prompt`), so if the
server reboots while the player is mid-answer, their next line after
reconnecting still runs the callback:

```python
prompt(enactor, 'Enter the vault code:', 'check_code', persistent=True)
```

Use it for anything a player might be sitting on across a restart. Leave
it off for quick, throwaway questions.

## Which do I use?

- **Configuring the player** (chargen-style, setting stats/tags on the
  player): a hardcode command wizard, or chargen itself. Real authority.
- **NPC dialogue, builder tools, world reactions** (the NPC remembers,
  reacts, opens doors, hands out items): softcode `prompt`. No restart,
  and `persistent=True` when it must outlive a reboot.
