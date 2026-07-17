# 011. Mirror

> Checklist item 11 — [now] — *ON_LOOK, pemit to enactor, reading open attrs*

**What you'll build:** A tall mirror that shows each looker *their own*
face — name, description, and whatever they're wearing — and lets the
rest of the room catch them preening. Four lines, and two of REALM's
render primitives working together.

**Concepts:** the `viewer` binding in `[[...]]` inline blocks (one
description, rendered per looker), reading another object's open state
(`viewer.description`, worn-tag scans — reads are open by design),
`ON_LOOK` as a world event with the looker as `enactor`, and the
etiquette split: *render* answers the looker, *events* narrate to
everyone else.

Builds on [inline functions](242_inline_functions.md) — this is the
`viewer` binding's showcase gadget.

## How it works

**A mirror is a description that reads its reader.** Inline `[[...]]`
blocks in a description run at render time, per viewer, with `viewer`
bound to whoever is looking (242 covers the machinery). So the
mirror's `@desc` simply builds its text *out of the viewer*:
`name(viewer)` for the caption, `viewer.description` for the face —
attribute reads are open in REALM (that's a design position: traps
read hp, shops read prices, mirrors read faces), so no permission
dance is needed. A looker who never set `@desc me` gets a graceful
fallback instead of an empty pane.

**The wardrobe scan is a one-line query.** Worn gear is just inventory
tagged `worn` (the `wear` builtin manages the tag), so
`[name(o) for o in contents(viewer) if has_tag(o, 'worn')]` is the
entire outfit system read back. Carried-but-not-worn items correctly
stay out of the reflection.

**`ON_LOOK` is for everyone else.** Looking at an object propagates
`event:look` at it; an `on_look` attribute fires with the looker as
`enactor`. The render already told the looker everything, so the event
narrates *outward*: `oemit(enactor, ...)` shows the room its vanity —
excluding the looker, who'd otherwise be told what they're already
doing. That division — `[[...]]`/`pemit` for the actor, `ON_LOOK` +
`oemit` for bystanders — is the actor-vs-room etiquette every polished
gadget follows.

## Build it

The glass. Two blocks: the reflection, then the outfit (a block whose
`result` is `''` simply vanishes — undressed lookers see no "Worn:"
stub):

```text
@create tall mirror
drop tall mirror
@desc tall mirror = A tall oval of old glass in a tarnished brass frame; whatever stands before it, it returns. [[result = f"In the glass: {name(viewer)} -- {viewer.description or 'a face the silver cannot quite fix.'}"]] [[worn = [name(o) for o in contents(viewer) if has_tag(o, 'worn')]; result = f"Worn: {', '.join(worn)}." if worn else '']]
@set tall mirror/on_look = oemit(enactor, f'{name(enactor)} pauses to study the tall mirror.')
```

Something to wear, so the scan has work to do:

```text
@create woolen scarf
@tag woolen scarf = wearable
```

## Try it

```text
@desc me = Tall, wiry, one chipped tooth.
look tall mirror
wear woolen scarf
look tall mirror
```

The first look reads `In the glass: Bilda -- Tall, wiry, one chipped
tooth.`; after `wear`, the reflection adds `Worn: woolen scarf.` A
friend looking at the *same* mirror sees their own name and face —
or, with no `@desc me` set, `a face the silver cannot quite fix.`
Meanwhile everyone else in the room reads `Bilda pauses to study the
tall mirror.` — the looker never sees that line. `@examine tall
mirror` shows the raw blocks; `look` shows the render.

## Going further

- **A haunted mirror:** make the fallback a hook — 1-in-20
  (`rand(1, 20) == 1`) show *someone else's* name from the room behind
  you.
- **An appraising mirror:** swap the worn scan's `result` for a
  `viewer.db`-driven judgment — `'The glass approves.' if
  credits(viewer) > 1000 else 'The glass sniffs.'` Anything readable
  can steer text.
- **Skill-gated detail:** wrap a third block in
  `skill('observation') >= 12` (the [garden](242_inline_functions.md)
  idiom) — sharp eyes notice the crack in the silvering.
- **Two-way glass:** pair it with the
  [security camera](054_security_camera.md): the `on_look` event can
  do more than narrate — it can log who checked their reflection, and
  when.
