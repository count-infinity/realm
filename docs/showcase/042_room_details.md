# 042. Room details

> Checklist item 42 ([now]): *@detail, desc_extras, per-viewer conditions*

**What you'll build:** An archive room with layered detail: a plaque
everyone reads, a false-backed shelf only sharp eyes notice, and named
`study <thing>` look-targets, all without creating a single prop object.

**Concepts:** the native `@detail` command (`desc_extras`), per-viewer
conditions (`check`/`skill`/[`has_tag`](../reference/softcode.md#fn-has_tag)
over the viewer), a `$`-verb dictionary for *named* virtual targets, and
where the builtin `look` draws its boundary. It reuses the `desc_extras`
rows the [camera](008_camera.md) prints its captured scene onto, and pairs
them with the [inline description](242_inline_functions.md) machinery.

## How it works

The finished room answers a looker on two levels. A plain `look`
volunteers what the room is willing to show, filtered to that viewer, and
typing `study <thing>` rewards someone who examines a named feature more
closely. This section answers where those detail lines come from and why
the named targets need a verb of their own rather than riding on `look`.

### Where detail lines come from, and who sees each one

REALM ships details natively. `@detail <object> = [<condition> ->] <text>`
appends a `[condition, text]` pair to the object's `desc_extras` attribute,
and every `look` and `examine` renders those pairs *after* the description,
per viewer, printing each line only when its condition passes. An empty
condition (the row stored as `['', text]`) means everyone sees the line;
a non-empty condition (`['check(...)', text]`) is a gate. Conditions are
safe expressions over the **viewer**: `check('observation', -2)` is a fresh
roll made as the viewer with a -2 modifier, `skill('occultism') >= 12`
reads their stable level with no dice, and `has_tag('ghost')` tests a tag.
The `viewer` name is bound to the looker while the condition evaluates.
Broken or forbidden conditions fail *closed*, so a bad expression simply
drops its line rather than erroring. `@detail here` lists the rows
numbered, and `@detail/remove` and `@detail/clear` prune them.

### Why named targets need their own verb

That covers detail *lines*. The checklist also wants **named
look-targets**, `plaque` and `shelves`, without real objects, and here is
the honest boundary: `look` is a builtin, builtins dispatch before
`$`-triggers, and the builtin resolves *objects*. `look plaque` with no
plaque object answers "You don't see 'plaque' here.", and no softcode can
intercept that. So virtual named targets get their own verb: a `$study *`
command on the room reading a dictionary attribute. This is new vocabulary
instead of shadowed vocabulary, the same boundary the zero-G room walks
([tutorial 040](040_zero_g_room.md)).

Both halves are pure data on the room: `desc_extras` for what the room
volunteers, `vtargets` for what closer study rewards.

## Build it

Dig the room, step inside, and give it a plain prose description:

```text
@dig Records Annex = annex, out
annex
@desc here = Steel shelving marches into the gloom, every bay tagged in fading ink.
```

Two detail lines, both written with `@detail`. The first carries no
condition, so every visitor reads it; the second is gated behind a
Per-based Observation roll at -2, so only sharp eyes catch the false back:

```text
@detail here = A brass plaque is bolted beside the door.
@detail here = check('observation', -2) -> One shelf bay sits fractionally shallower than its neighbors - a false back, maybe.
```

The named targets are just data: a dictionary on the room mapping each
study word to its payoff. That is one assignment, so it stays a single
line:

```text
@set here/vtargets = {"plaque": "COLLECTION 9 - DONATED. The donor's name has been filed off.", "shelves": "Harbor manifests, mostly. A century of them, and nobody has opened one twice."}
```

The verb that reads the dictionary. It has three steps, so it is a `'''`
multi-line block: normalize the typed word, read the room's own dictionary
with [`V`](../reference/softcode.md#fn-v), and answer the typist with
[`pemit`](../reference/softcode.md#fn-pemit), falling back to a graceful
miss when the word is not a key:

```text
@set here/cmd_study = '''
$study *:
t = trim(arg0).lower()          # arg0 is the word typed after 'study'
d = V('vtargets', {})           # the room's own dictionary of look-targets
pemit(enactor, d.get(t, f'You find nothing else worth studying about the {t}.'))
'''
```

[`trim`](../reference/softcode.md#fn-trim) strips stray spaces off the
captured word before it is lowercased and looked up.

## Try it

```text
look
  Records Annex
  Steel shelving marches into the gloom, every bay tagged in fading ink.
  A brass plaque is bolted beside the door.
  One shelf bay sits fractionally shallower than its neighbors - a false back, maybe.
```

That last line only prints for viewers who make the roll. An untrained
visitor reads exactly one detail line and never knows. The named targets:

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

- **Details on things, not just rooms:** `@detail` works on any object,
  such as a sword whose maker's mark only a `skill('smithing')` viewer
  reads.
- **Stateful details:** conditions read the viewer, but `[[...]]` desc
  blocks read *and write* ([tutorial 242](242_inline_functions.md)).
  Combine them so the desc counts your visits while details gate on your
  skills.
- **Reward the study verb:** make `study` roll. Swap the flat `d.get` for
  a [`check_roll`](../reference/softcode.md#fn-check_roll)-gated variant per
  key, so `study shelves` with good Observation *finds* the false back and
  `@open`s the way.
- **One memo per detail:** the once-ever pattern caches `found_<viewer.id>`
  on the room the first time the roll passes, so the text stays consistent
  forever after.
