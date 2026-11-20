# 011. Mirror

> Checklist item 11 ([now]): *ON_LOOK, pemit to enactor, reading open attrs*

**What you'll build:** A tall mirror that shows each looker *their own*
face (name, description, and whatever they're wearing) and lets the rest
of the room catch them preening. One living description and one guarded
hook: two of REALM's render primitives working together.

**Concepts:** the `viewer` binding in `[[...]]` inline blocks (one
description, rendered per looker), reading another object's open state
(`viewer.description`, worn-tag scans; reads are open by design),
[`ON_LOOK`](../reference/softcode.md#lifecycle-hooks) as a world event
with the looker as `enactor`, and the etiquette split: the *render*
answers the looker, while *events* narrate to everyone else.

Builds on [inline functions](242_inline_functions.md), because this is
the `viewer` binding's showcase gadget.

## How it works

**A mirror is a description that reads its reader.** Inline `[[...]]`
blocks in a description run at render time, per viewer, with `viewer`
bound to whoever is looking ([242](242_inline_functions.md) covers the
machinery). So the mirror's `@desc` simply builds its text *out of the
viewer*: [`name(viewer)`](../reference/softcode.md#fn-name) for the
caption, `viewer.description` for the face. Attribute reads are open in
REALM, which is a design position (traps read hp, shops read prices,
mirrors read faces), so no permission dance is needed. A looker who never
set `@desc me` gets a graceful fallback instead of an empty pane.

**The wardrobe scan is a one-line query.** Worn gear is just inventory
tagged `worn` (the `wear` builtin manages the tag), so
`[name(o) for o in contents(viewer) if has_tag(o, 'worn')]` is the
entire outfit system read back:
[`contents(viewer)`](../reference/softcode.md#fn-contents) lists what the
looker carries, and
[`has_tag`](../reference/softcode.md#fn-has_tag) keeps only the worn
pieces, so carried-but-not-worn items correctly stay out of the
reflection.

**`ON_LOOK` is for everyone else.** Looking at an object propagates
`event:look` at it, and an `on_look` attribute fires with the looker as
`enactor`. The render answers the looker, which leaves the event one job:
narrating outward. [`oemit(enactor, ...)`](../reference/softcode.md#fn-oemit)
shows the room its vanity while excluding the looker, who would otherwise
be told what they are already doing. That division (`[[...]]` and
[`pemit`](../reference/softcode.md#fn-pemit) for the actor, `ON_LOOK`
plus `oemit` for bystanders) is the actor-versus-room etiquette every
polished gadget follows.

**Why the hook opens with a guard.** An `ON_LOOK` hook fires on *every*
object in the room, not only the one being looked at, and a plain `look`
at the room propagates `event:look` too. Unguarded, the mirror would
announce a study of the glass every time somebody glanced at the room or
at the scarf beside it. `if target is me:` is how the mirror reacts only
to its own admirers; see
[Guard on `target`](../reference/softcode.md#guard-on-target).

## Build it

The frame first: create the mirror and stand it in the room:

```text
@create tall mirror
drop tall mirror
```

The glass is the description, and the description is the whole gadget.
Two inline blocks: the reflection (caption, then face, with the
fallback), then the outfit scan. A block whose `result` is `''` simply
vanishes, so undressed lookers see no "Worn:" stub:

```text
@desc tall mirror = A tall oval of old glass in a tarnished brass frame; whatever stands before it, it returns. [[result = f"In the glass: {name(viewer)} -- {viewer.description or 'a face the silver cannot quite fix.'}"]] [[worn = [name(o) for o in contents(viewer) if has_tag(o, 'worn')]; result = f"Worn: {', '.join(worn)}." if worn else '']]
```

The vanity hook narrates to the bystanders. The guard is control flow, so
the script is a `'''` multi-line block (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)):

```text
@set tall mirror/on_look = '''
if target is me:  # ON_LOOK fires on EVERY object in the room, so guard it
    oemit(enactor, f'{name(enactor)} pauses to study the tall mirror.')
'''
```

Something to wear, so the scan has work to do. The `wear` builtin refuses
anything not tagged `wearable`:

```text
@create woolen scarf
@tag woolen scarf = wearable
```

## Try it

Give the glass a face to work with, then check your reflection before and
after dressing up:

```text
> @desc me = Tall, wiry, one chipped tooth.
Description set for Bilda.

> look tall mirror
tall mirror
A tall oval of old glass in a tarnished brass frame; whatever stands
before it, it returns. In the glass: Bilda -- Tall, wiry, one chipped
tooth.

> wear woolen scarf
You put on the woolen scarf.

> look tall mirror
tall mirror
A tall oval of old glass in a tarnished brass frame; whatever stands
before it, it returns. In the glass: Bilda -- Tall, wiry, one chipped
tooth. Worn: woolen scarf.
```

A friend looking at the *same* mirror sees their own name and face, or,
with no `@desc me` set, `a face the silver cannot quite fix.` Meanwhile
everyone else in the room reads `Bilda pauses to study the tall mirror.`,
and the looker never sees that line, because `oemit(enactor, ...)`
excludes them. `@examine tall mirror` shows the raw blocks; `look` shows
the render.

## Going further

- **A haunted mirror:** roll [`rand`](../reference/softcode.md#fn-rand)
  in the reflection block, and on a 1 in 20 (`rand(1, 20) == 1`) show
  *someone else's* name from the room behind you.
- **An appraising mirror:** swap the worn scan's `result` for a judgment
  driven by [`credits`](../reference/softcode.md#fn-credits):
  `'The glass approves.' if credits(viewer) > 1000 else 'The glass
  sniffs.'` Anything readable can steer the text.
- **Skill-gated detail:** wrap a third block in
  `skill('observation') >= 12` (the [garden](242_inline_functions.md)
  idiom), so sharp eyes notice the crack in the silvering.
- **Two-way glass:** pair it with the
  [security camera](054_security_camera.md). The `on_look` hook can do
  more than narrate: it can log who checked their reflection, and when.
