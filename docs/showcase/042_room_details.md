# 042. Room details

> Checklist item 42 — [now] — *@detail, desc_extras, per-viewer conditions*

**What you'll build:** An archive room with layered detail: a plaque
everyone reads, a false-backed shelf only sharp eyes notice, and named
`study <thing>` look-targets — all without creating a single prop
object.

**Concepts:** the native `@detail` command (`desc_extras`), per-viewer
conditions (`check`/`skill`/`has_tag` over the viewer), a `$`-verb
dictionary for *named* virtual targets, and where the builtin `look`
draws its boundary.

## How it works

REALM ships details natively. `@detail <object> = [<condition> ->]
<text>` appends `[condition, text]` pairs to a `desc_extras` attribute;
every `look` and `examine` renders the pairs *after* the description,
per viewer, showing each line only if its condition passes. Conditions
are safe expressions over the **viewer**: `check('observation', -2)`
(a fresh roll as the viewer), `skill('occultism') >= 12` (their stable
level, no dice), `has_tag('ghost')`. An empty condition means everyone.
Broken or forbidden conditions fail *closed* — the line simply doesn't
render. `@detail here` lists them numbered; `@detail/remove` and
`@detail/clear` prune.

That covers detail *lines*. The checklist also wants **named
look-targets** — `mural`, `control panel` — without real objects, and
here is the honest boundary: `look` is a builtin, builtins dispatch
before `$`-triggers, and the builtin resolves *objects*. `look plaque`
with no plaque object answers "You don't see 'plaque' here", and no
softcode can intercept that. So virtual named targets get their own
verb: a `$study *` command on the room reading a dictionary attribute.
New vocabulary instead of shadowed vocabulary — the same boundary the
zero-G room walks ([tutorial 040](040_zero_g_room.md)).

Both halves are pure data on the room: `desc_extras` for what the room
volunteers, `vtargets` for what closer study rewards.

## Build it

The room and its layered detail lines — one public, one gated behind a
Per-based Observation roll at -2:

```text
@dig Records Annex = annex, out
annex
@desc here = Steel shelving marches into the gloom, every bay tagged in fading ink.
@detail here = A brass plaque is bolted beside the door.
@detail here = check('observation', -2) -> One shelf bay sits fractionally shallower than its neighbors - a false back, maybe.
```

The named targets — a dictionary and the verb that reads it:

```text
@set here/vtargets = {"plaque": "COLLECTION 9 - DONATED. The donor's name has been filed off.", "shelves": "Harbor manifests, mostly. A century of them, and nobody has opened one twice."}
@set here/cmd_study = $study *: t = trim(arg0).lower(); d = V('vtargets', {}); pemit(enactor, d.get(t, f'You find nothing else worth studying about the {t}.'))
```

## Try it

```text
look
  Records Annex
  Steel shelving marches into the gloom, every bay tagged in fading ink.
  A brass plaque is bolted beside the door.
  One shelf bay sits fractionally shallower than its neighbors - a false back, maybe.
```

That last line only prints for viewers who make the roll — an
untrained visitor reads exactly one detail line and never knows. The
named targets:

```text
look plaque
  You don't see 'plaque' here.       <- the builtin's boundary, working as designed
study plaque
  COLLECTION 9 - DONATED. The donor's name has been filed off.
study rug
  You find nothing else worth studying about the rug.
```

Housekeeping, numbered:

```text
@detail here
  Details on Records Annex:
    1. [(always)] A brass plaque is bolted beside the door.
    2. [check('observation', -2)] One shelf bay sits fractionally shallower...
@detail/remove here = 2
```

## Going further

- **Details on things, not just rooms:** `@detail` works on any
  object — a sword whose maker's mark only a `skill('smithing')`
  viewer reads.
- **Stateful details:** conditions read the viewer, but `[[...]]`
  desc blocks read *and write* ([tutorial 242](242_inline_functions.md))
  — combine them: the desc counts your visits while details gate on
  your skills.
- **Reward the study verb:** make `study` roll — swap the flat `d.get`
  for a `check_roll`-gated variant per key, so `study shelves` with
  good Observation *finds* the false back and `@open`s the way.
- **One memo per detail:** the once-ever pattern — cache
  `found_<viewer.id>` on the room the first time the roll passes so
  the text stays consistent forever after.
