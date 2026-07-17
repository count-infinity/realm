# 170. Builder wizard

> Checklist item 170 — [now] — *prompt() chains, delegated authority, create_obj rooms/exits for non-coders*

**What you'll build:** a `build` command that walks anyone — no `@`-syntax
required — through creating a room: it asks for a name, a description, and
a direction, then mints the room and a linked exit. A guided world-editor
for non-coders. (Builder permission to *place* the wizard; the point is
that the people who *use* it need none.)

**Concepts:** a **`prompt()` chain** (each callback asks the next
question), state carried across steps in a `wip_room_<id>` attribute,
**delegated authority** (the admin-owned wizard mints on the enactor's
behalf), and `create_obj` for both the room and its exit.

## How it works

**A wizard is a chain of prompts.** `prompt(player, text, 'callback')`
captures the player's *next line* and runs the named attribute as a
script with the answer bound to `arg0`. Chain them: each callback does
its bit of work and calls `prompt()` again for the next question, until
the last one finishes. The engine keeps `help`/`quit`/`exit` as escape
hatches, so a half-built room never traps anyone. (The
[typewriter](010_typewriter.md) uses the same loop for prose.)

**State rides on the wizard, keyed by the builder.** Between "name it"
and "describe it" the wizard must remember which room is in progress, so
it stashes the new room's id in `wip_room_<enactor.id>` — one slot per
concurrent user, so two players can run the wizard at once without
colliding.

**Delegated authority makes it safe for non-coders.** The wizard is
admin-owned, and every callback runs **as the wizard, with its owner's
authority** — so `create_obj` succeeds even though the *enactor* is a
mortal with no build rights. The player drives; the wizard builds. This
is the same delegation boundary the [player shop](088_player_shops.md)
leans on: the enactor is untrusted input, the executor's owner is the
power, the script is the policy. Want to gate who may build? Add a
`use` lock to the wizard.

## Build it

Place the wizard (as an admin, so its authority can mint rooms):

```text
@create build wizard
drop build wizard
```

Step 1 — the entry verb clears any stale state and asks for a name:

```text
@set build wizard/cmd_build = $build: set_attr(me, 'wip_room_' + enactor.id, ''); prompt(enactor, 'Name the new room:', 'on_name')
```

Step 2 — mint the room from the answer, remember it, ask for a
description:

```text
@set build wizard/on_name = r = create_obj(escape(trim(arg0)), tags=['room']); set_attr(me, 'wip_room_' + enactor.id, r.id); prompt(enactor, 'Describe it in a sentence:', 'on_desc')
```

Step 3 — stamp the description (into `desc_extras`, the slot softcode may
write) and ask for a direction:

```text
@set build wizard/on_desc = r = get('#' + str(get_attr(me, 'wip_room_' + enactor.id))); set_attr(r, 'desc_extras', [['', escape(trim(arg0))]]); prompt(enactor, 'Which direction leads there from here?', 'on_exit')
```

Step 4 — mint the exit from the player's current room to the new one,
clear the scratch state, and report:

```text
@set build wizard/on_exit = d = trim(arg0).lower(); r = get('#' + str(get_attr(me, 'wip_room_' + enactor.id))); e = create_obj(d, tags=['exit'], location=loc(enactor)); set_attr(e, 'destination', r.id); del_attr(me, 'wip_room_' + enactor.id); pemit(enactor, 'Done. ' + name(r) + ' is now ' + d + ' of here.')
```

## Try it

As any player, coder or not:

```text
build
  Name the new room:
> Sunny Parlor
  Describe it in a sentence:
> Light pours through tall windows.
  Which direction leads there from here?
> north
  Done. Sunny Parlor is now north of here.
north
  Sunny Parlor
  Light pours through tall windows.
```

The exit is real and walkable, the description is theirs, and they never
typed an `@`-command. Typing `quit` at any prompt bails out cleanly (the
half-built room stays; a `build` "resume" mode is an easy addition).

## Going further

- **More fields:** insert a "should there be a return exit?" step and
  mint the reverse exit when they say yes — `prompt`'s `choices`
  re-asks until the answer is valid.
- **Gate it:** `@lock/use build wizard = caller.has_tag('homesteader')`
  so only players who've earned a plot can run it.
- **Themed wizards:** one wizard per zone whose `on_name` also runs
  `@zone` on the new room keeps player-built areas tidy.
- **Housing tie-in:** point new-player onboarding at a wizard that builds
  their starter home, then hand the room to them with the
  [player-housing](175_player_housing.md) guardrails.
