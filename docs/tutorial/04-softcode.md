# Part 4 — Softcode

Everything so far was configuration. Now you'll write *code* — from
inside the game, on the objects themselves. This is REALM's MUSH
inheritance: the world is programmable by builders, safely.

## A command on an object

Give the keeper something to say. `$`-patterns turn attributes into
player commands:

```text
@set the keeper/cmd_story = $story:say They told me the light could go out for one night. One night!
```

Any player here can now type `story`. Wildcards capture: a pattern
like `$ask about *` gives you `%0` for what they asked.

## A reaction

`^`-patterns overhear speech:

```text
@set the keeper/listen_light = ^*light*:say The light! It must burn, do you hear? It MUST.
```

Say anything containing "light" and he answers.

## A floor that bites

Event scripts (`ON_ENTER`, `ON_LOOK`, `ON_PAYMENT`...) run real
sandboxed Python with the whole engine API. In the Cellar:

```text
@set here/on_enter = damage(enactor, 1); pemit(enactor, 'A rotten board snaps under your weight!')
```

Walk out and back in: it bites. It'll bite your players too — damage is
real, and lethal damage is *really* real (corpses and all).

## Writing it readable

One script on one line gets ugly fast. Open a **multi-line block** with a
trailing `'''` and close it with a line of just `'''`; the lines between keep
their indentation and store as one script:

```text
@set here/on_enter='''
if get_attr(enactor, 'boots'):
    pemit(enactor, 'Your boots hold. The board creaks but holds.')
else:
    damage(enactor, 1)
    pemit(enactor, 'A rotten board snaps under your weight!')
'''
```

It's the same sandboxed Python, now with real `if`/`else` and indentation
instead of a wall of semicolons. `@abort` on its own line cancels a block,
and the `'''` delimiter is configurable — see
[World Management](../guides/world-management.md#multi-line-input-heredocs).

## Living descriptions

`[[...]]` blocks in any description execute per viewer at render time —
with state. The cellar remembers who has noticed the loose stone:

```text
@desc here = Barrels rot in the brine-smell dark. [[k = 'spot_' + viewer.id; r = get_attr(me, k) or ('yes' if check_roll('observation') else 'no'); set_attr(me, k, r); result = ' One flagstone sits proud of the rest.' if r == 'yes' else '']]
```

Each character rolls observation *once*, ever — the outcome caches in
an ordinary attribute. That's the whole trick: `get_attr`/`set_attr`
plus builtins (`rand`, `now`, `check_roll`...) compose into anything.

## A heartbeat

`script_ticker` runs an object's `on_tick` softcode on a cadence:

```text
@behavior the keeper = script_ticker, interval:20
@set the keeper/on_tick = pose stares out to sea.
```

To see a description's raw source (the `[[...]]` code, not the
rendered result), use `@examine here` — the builder examine dumps raw
attribute values. And to run softcode ad-hoc, `@eval` executes anything
as you: `@eval result = len(search_world(tag='npc'))`, or drive many
objects at once with `@foreach tag:rat = @teleport %o = The Cellar`.

!!! info "Learn more"
    Scripts run *as their object* with its owner's authority — you can
    read and write your own objects' attributes, never a stranger's.
    `@tr obj/attr` test-fires any script; the `halt` tag stops a
    runaway machine. The full function list: `help` → softcode, or
    docs/design/engine_vision.md.
