# 170. Builder wizard

> Checklist item 170 ([now]): *prompt() building wizards, create_obj + exit wiring*

**What you'll build:** a `build` command that walks anyone, with no
`@`-syntax required, through creating a room. It asks for a name, a
description, and a direction, then mints the room and a linked exit. A
guided world-editor for non-coders. (A builder places the wizard; the
people who *use* it need no build rights of their own.)

**Concepts:** a [`prompt()`](../reference/softcode.md#fn-prompt) chain
(each callback asks the next question), state carried across steps in a
`wip_room_<id>` attribute, delegated ownership (the builder-owned wizard
mints on the driver's behalf), and
[`create_obj`](../reference/softcode.md#fn-create_obj) for both the room
and its exit.

## How it works

The finished tool is one object sitting in a room. A player types `build`,
answers three questions one line at a time, and walks away with a real,
walkable room on the other side of a new exit. This section answers three
questions: how one answer leads to the next, how the half-built room is
remembered between answers, and why a player who cannot even run `@create`
can drive the whole thing.

### How one question leads to the next

`prompt(player, text, 'callback')` sends `text` to the player, then
captures their **next line** and runs the named attribute as a script with
that answer bound to `arg0`. Chain them: each callback does its bit of work
and calls `prompt()` again for the next question, until the last one has no
more to ask. The [typewriter](010_typewriter.md) uses the same capture loop
to gather prose.

While the wizard is waiting for an answer, the words `help`, `quit`, and
`exit` are not captured; they pass through to the ordinary command
dispatcher, so a player mid-wizard still reaches them. Every other line is
read as the answer to the question on screen.

### How the wizard remembers the room between questions

Between "name it" and "describe it" the wizard must remember which room is
in progress, so it stashes the new room's id in `wip_room_<enactor.id>`.
Keying the slot on the driver's id gives one slot per concurrent user, so
two players can run the wizard at once without overwriting each other's
work-in-progress.

### Why a non-coder can drive it

Every callback runs **as the wizard** (the executor), with the driving
player bound as `enactor`. That matters for two reasons. First, `me` is the
wizard, so `set_attr(me, ...)` can write the scratch slot onto the wizard
itself, which the driver does not own. Second,
[`create_obj`](../reference/softcode.md#fn-create_obj) stamps ownership from
the executor's owner, so the new room and exit belong to the wizard's owner
(a builder), not to the mortal who drove the wizard.

The builtin `@create` and `@dig` commands refuse a player without build
rights, which is exactly why the wizard exists: a builder places it once,
and thereafter anyone can build through the plain `build` verb and hand the
results back to a real builder's account. This is the same delegation
boundary the [player shop](088_player_shops.md) leans on, where the enactor
is untrusted input and the executor's owner is the authority. To gate who
may build, add a `use` lock to the wizard (see [Going further](#going-further)).

## Build it

Place the wizard. Do this as a builder, so the rooms it mints are owned by a
build-capable account:

```text
@create build wizard
drop build wizard
```

Step 1 is the entry verb. Typing `build` clears any stale scratch state for
this player and asks for a name. The `$build:` line is the command trigger,
and a `use` lock on the wizard would gate it:

```text
@set build wizard/cmd_build = '''
$build:
set_attr(me, 'wip_room_' + enactor.id, '')
prompt(enactor, 'Name the new room:', 'on_name')
'''
```

Step 2 mints the room from the answer, remembers its id under the
per-player key, and asks for a description.
[`escape`](../reference/softcode.md#fn-escape) neutralizes any color markup
in the player-typed name, and [`trim`](../reference/softcode.md#fn-trim)
drops stray whitespace:

```text
@set build wizard/on_name = '''
r = create_obj(escape(trim(arg0)), tags=['room'])
# one slot per driver, so two builders never collide
set_attr(me, 'wip_room_' + enactor.id, r.id)
prompt(enactor, 'Describe it in a sentence:', 'on_desc')
'''
```

Step 3 reads the remembered room back with
[`get`](../reference/softcode.md#fn-get) and its stored id via
[`V`](../reference/softcode.md#fn-v), stamps the description onto it, and
asks for a direction. The text goes into `desc_extras`, a list of
`[condition, text]` detail lines that `look` renders under the room. An
empty condition shows the line to everyone. This is the route softcode has:
`look` prints the core `description` plus the `desc_extras` list, and
[`set_attr`](../reference/softcode.md#fn-set_attr) writes db attributes, so
`desc_extras` is the one a script can add to:

```text
@set build wizard/on_desc = '''
r = get('#' + str(V('wip_room_' + enactor.id)))
set_attr(r, 'desc_extras', [['', escape(trim(arg0))]])
prompt(enactor, 'Which direction leads there from here?', 'on_exit')
'''
```

Step 4 mints the exit from the player's current room to the new one, clears
the scratch state with [`del_attr`](../reference/softcode.md#fn-del_attr),
and reports back with [`pemit`](../reference/softcode.md#fn-pemit) and
[`name`](../reference/softcode.md#fn-name). The exit is an object tagged
`exit` whose `destination` attribute holds the target room's id, and
[`loc`](../reference/softcode.md#fn-loc) places it in the room the player is
standing in:

```text
@set build wizard/on_exit = '''
d = trim(arg0).lower()
r = get('#' + str(V('wip_room_' + enactor.id)))
e = create_obj(d, tags=['exit'], location=loc(enactor))
set_attr(e, 'destination', r.id)
del_attr(me, 'wip_room_' + enactor.id)
pemit(enactor, 'Done. ' + name(r) + ' is now ' + d + ' of here.')
'''
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
typed an `@`-command. Any line other than `help`, `quit`, or `exit` is read
as the answer to the question on screen; those three reach the normal
dispatcher instead.

## Going further

- **More fields:** insert a "should there be a return exit?" step and mint
  the reverse exit when they say yes. The softcode `prompt()` has no built-in
  choice list, so the callback checks the answer itself and calls `prompt()`
  again for the same step when it does not recognize a yes or no.
- **Gate it:** `@lock/use build wizard = caller.has_tag('homesteader')` so
  only players who have earned a plot can run it. A `use` lock on the wizard
  gates its `$build:` trigger.
- **Themed wizards:** one wizard per zone whose `on_name` also runs `@zone`
  on the new room keeps player-built areas tidy.
- **Housing tie-in:** point new-player onboarding at a wizard that builds
  their starter home, then hand the room to them with the
  [player-housing](175_player_housing.md) guardrails.
