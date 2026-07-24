# 005. Magic 8-ball / Oracle

> Checklist item 5 ([now]): *the hello-world $-command: one trigger, one switch(rand())*

**What you'll build:** A shakeable oracle ball. Anyone standing near it
types `shake` and the ball answers with a random cryptic line.

**Concepts:** `@create`/`@desc`/`@set`, the `$pattern:code` command
trigger (a command that lives *on an object*),
[`rand()`](../reference/softcode.md#fn-rand) plus
[`switch()`](../reference/softcode.md#fn-switch), per-instance data in
attributes, `say`/`pose` spoken *by* an object.

This is the smallest interactive object REALM can express, and the
skeleton every other build in the showcase hangs flesh on. If you only
read one tutorial, read this one.

## How it works

Three ideas, and all of softcode is some combination of them:

1. **Objects are bags of attributes.** `@create` makes the thing; `@desc`
   and `@set` write data onto it. Nothing here is code yet.
2. **An attribute whose value looks like `$pattern: code` is a command.**
   Store it under any name starting with `cmd_` and the engine treats the
   part before the colon as a player-input pattern and the part after it
   as a script. When someone in the same room types something that
   matches, the script runs *as the ball*, with the typist bound to
   `enactor`. Walk away from the ball and the command stops existing for
   you: the engine only searches the room's contents, the room itself,
   your inventory, and your zone's master for `$`-triggers, so there is no
   global registration and no name collisions.
3. **The script is sandboxed Python.** A trivial one fits on a single
   `;`-separated line; anything with real branching or several steps is a
   `'''` multi-line block instead, with real `if`/`for` and indentation
   (see [multi-line input](../guides/world-management.md#multi-line-input-heredocs)).
   Here [`rand(1, 8)`](../reference/softcode.md#fn-rand) rolls,
   [`switch(value, case, result, ..., default)`](../reference/softcode.md#fn-switch)
   picks the answer, and `say(...)` makes the ball speak to the whole room.

One rule to remember before you name a command: **built-in commands
dispatch before `$`-triggers.** A `$get` or `$look` trigger will never
fire, because the engine's own `get`/`look` win. `shake` is safe, since
no builtin claims it.

## Build it

Stand in any room you're allowed to build in. First the object: `@create`
puts it in your inventory, and `drop` places it:

```text
@create oracle ball
drop oracle ball
@desc oracle ball = A matte-black sphere the size of a fist. A small window on one side swims with dark fluid. It looks like it wants to be shaken.
```

Now the whole gadget, in one attribute. It is a single statement, but a
`'''` block lets the eight answers line up where you can read and retune
them:

```text
@set oracle ball/cmd_shake = '''
$shake:
say(switch(rand(1, 8),
    1, 'It is certain.',
    2, 'Signs point to yes.',
    3, 'Ask again later.',
    4, 'The stars are silent on this one.',
    5, 'Outlook grim.',
    6, 'Very doubtful.',
    7, 'Yes - but not the way you hope.',
    'The fluid clouds. No answer comes.'))
'''
```

Reading it back: `$shake:` declares the pattern (exactly the word
`shake`); `rand(1, 8)` picks a number; `switch` maps 1 through 7 onto
answers and uses its final unpaired argument as the default (that is what
an 8 rolls, so the "no answer" line is rarer only because it shares the
default slot; count your cases when you tune the odds). `say(...)` speaks
as the ball, so you and everyone in the room see
`oracle ball says, "Outlook grim."`. A one-liner
(`$shake: say(switch(rand(1, 8), 1, '...', ...))`) would behave exactly
the same for something this small; the block is purely for legibility.

That is the entire build, and no server restarted: the ball answers the
moment you set it.

### Retheme it with data

The answers are baked into the script above. Better style, the habit
every later tutorial leans on, is to keep *data* in one attribute and
*code* in another. `@set` parses JSON, so a list is easy, and the command
becomes a short block:

```text
@set oracle ball/answers = ["Yes.", "No.", "The dice are still rolling."]
@set oracle ball/cmd_shake = '''
$shake:
a = V('answers')
pose(f"trembles in {name(enactor)}'s grip.")
say(a[rand(0, len(a) - 1)])
'''
```

New pieces: `me` is the scripted object (the ball) and `enactor` is
whoever typed `shake`. [`V('answers')`](../reference/softcode.md#fn-v)
reads an attribute off `me`, the shorthand for
[`get_attr(me, 'answers')`](../reference/softcode.md#fn-get_attr); since a
script mostly reads its *own* object, `V` is what you'll type all day, and
the longer `get_attr(obj, ...)` form is for reading *other* objects.
`a[rand(0, len(a) - 1)]` indexes the list (plain Python, because scripts
*are* sandboxed Python, which is also why the `f"..."` string interpolates
`{name(enactor)}` inline). `pose(...)` emits a third-person action line
(`oracle ball trembles in Kess's grip.`) before the answer, the
object-side version of actor-and-room messaging etiquette. Now anyone can
retheme a specific ball by editing one data attribute, without touching
the script.

## Try it

```text
shake
```

You'll see something like:

```text
oracle ball trembles in Bilda's grip.
oracle ball says, "The dice are still rolling."
```

Everyone else in the room sees the same two lines, because the ball is
speaking, not whispering. Walk to another room and type `shake`: the
trigger is out of scope and a live server answers `Huh?`.

To inspect a script without triggering it, `@examine oracle ball` dumps
the raw attributes. `@tr` is the other testing tool, but mind what it
runs: `@tr <obj>/<attr>` executes the attribute's value *as code*, so it
drives a **plain** script attribute (an `on_look`, `on_enter`, or
`battle_cry` that holds bare code) but **not** a `$pattern:` trigger like
`cmd_shake`; the `$shake:` prefix is not valid Python, so `@tr` there
fails with a syntax error even while it reports "Triggered". Test
`cmd_shake` by typing `shake`, and save `@tr` for the `ON_<EVENT>` hooks
you'll meet next. One caveat for those: a hook fired by the engine is
handed the action that fired it (`adata`, `target`, `atype`; see the
[slot machine](001_slot_machine.md)), and `@tr` has no action behind it,
so a hook that reads the payload can't be `@tr`'d either; drive it with
the real event instead.

## Going further

- **Answer the question asked.** Wildcards capture: change the pattern to
  `$shake *` and the words typed after `shake` arrive as `arg0`, so you can
  echo them back with `say(f'You asked: {arg0} ...')`. (Keep a plain
  `$shake` version too if you want both forms.)
- **A cooldown.** Store `set_attr(me, 'last', now())` and refuse to answer
  while `now() - V('last', 0) < 10`, an `if ... else` guard written as a
  `'''` block, like the [slot machine](001_slot_machine.md)'s payment hook.
- **React to being looked at.** `@set oracle ball/on_look =
  pose('swirls ominously.')`; `ON_<EVENT>` attributes fire on world events
  the way `$`-commands fire on typed input. (And unlike `cmd_shake`, this
  bare-code attribute you *can* `@tr`.)
- **Weight the answers.** Duplicate entries in the `answers` list, or band
  a `rand(1, 100)` roll, exactly the jump the
  [slot machine](001_slot_machine.md) makes next.
