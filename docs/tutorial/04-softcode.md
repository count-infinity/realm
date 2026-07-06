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

!!! info "Learn more"
    Scripts run *as their object* with its owner's authority — you can
    read and write your own objects' attributes, never a stranger's.
    `@tr obj/attr` test-fires any script; the `halt` tag stops a
    runaway machine. The full function list: `help` → softcode, or
    docs/design/engine_vision.md.
