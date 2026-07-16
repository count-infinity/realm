# 242. Inline functions in text

> Checklist item 242 — [now] — *[[...]] inline blocks with viewer binding*

**What you'll build:** descriptions that compute — a garden whose thorns
only trained eyes notice, a mood crystal that's a different color every
look, a room that counts your visits, and an oracle whose spoken lines
are computed the moment it speaks.

**Concepts:** `[[...]]` inline blocks, the `viewer` binding, `result`,
per-viewer skill checks in text, stateful text via `get_attr`/`set_attr`,
computed speech in trigger scripts.

## How it works

MUSH softcode's killer feature was functions *inside text* — `[rand(6)]`
evaluated at display time. REALM ships the same idea: any description may
embed `[[ ... ]]` blocks (delimiters are a game setting;
`INLINE_OPEN`/`INLINE_CLOSE` in `config.py`). When someone looks, each
block runs through the script sandbox **per viewer** with the full
function library, plus three bindings that matter here:

- `me` — the described object; the block runs with *its* authority.
- `viewer` — the looker, with `skill('name')` (their stable skill level)
  and `check_roll('name', mod)` (a fresh roll *as the viewer*).
- `result` — whatever the block assigns to it replaces the block in the
  rendered text; no `result` means empty string.

Errors and forbidden code fail closed to `''` (and are logged) — a
broken block never leaks Python at a player. At most 8 blocks render per
description, the code inside nests freely (quoted `]]` and subscripts
are handled), and mutations made by a block are saved like any other
gameplay change — so text can *remember*.

One boundary worth knowing: `[[...]]` is a **render-time** feature of
descriptions (`look`, room rendering). Speech isn't re-rendered per
listener — an NPC line is computed *when it speaks*, by the same
function library inside its trigger script. You'll build both below.

## Build it

Dig a garden and hang the arc's signature line on it — this is the
README's five-line-stack example, live. Sharp-eyed visitors (effective
`observation` 12+) see a detail others never will:

```text
@dig The Garden = north, south
north
@desc here = Roses climb a broken trellis. [[result = ansi('rh', 'Thorns glint among the stems.') if skill('observation') >= 12 else '']]
```

`skill()` reads the *viewer's* level, `ansi('rh', ...)` colors the
insert bright red, and the empty-string branch makes the sentence simply
not exist for everyone else.

Randomness per look — `extract` picks the Nth word (1-indexed) from a
list:

```text
@create mood crystal
drop mood crystal
@desc mood crystal = A fist-sized crystal on a plinth. [[result = 'Right now it glows ' + extract('amber violet seafoam', rand(1, 3)) + '.']]
```

Stateful text. Blocks can read and write ordinary attributes on `me`, so
the garden can remember each visitor separately — key the attribute by
`viewer.id`. A description holds several blocks happily (up to 8), so
re-set the desc with the thorns block *and* a visit counter:

```text
@desc here = Roses climb a broken trellis. [[result = ansi('rh', 'Thorns glint among the stems.') if skill('observation') >= 12 else '']] [[n = get_attr(me, 'visits_' + viewer.id, 0) + 1; set_attr(me, 'visits_' + viewer.id, n); result = 'You have paused here ' + str(n) + ' time' + ('' if n == 1 else 's') + '.']]
```

First look: "You have paused here 1 time." Second: "2 times." Your
friend's count is their own. (The same idiom memoizes a once-ever
`check_roll` — roll once, cache the outcome in an attribute, and the
text stays consistent forever; the [main tutorial](../tutorial/04-softcode.md)
uses it for passive detection.)

Computed **speech**: same functions, but inside a trigger script, so the
line is composed at the moment of utterance:

```text
@set mood crystal/cmd_consult = $consult crystal:say('The auspices favor ' + extract('war trade rest', rand(1, 3)) + '.')
```

## Try it

```text
> look
The Garden
----------
Roses climb a broken trellis. Thorns glint among the stems. You have paused here 1 time.
...
> look mood crystal
A fist-sized crystal on a plinth. Right now it glows violet.
> consult crystal
mood crystal says, "The auspices favor trade."
```

Look again — the visit count climbs, the crystal changes color, and a
low-observation character never reads the thorns line at all. `@examine
here` shows the raw `[[...]]` source; `look` shows the render.

## Going further

- **Time of day:** `now()` returns epoch seconds — `result = 'The tide
  is ' + ('high' if (now() // 21600) % 2 == 0 else 'low') + '.'` gives a
  six-hour tide cycle with no ticker at all.
- **A door that reads you:** `if_else(has_tag(viewer, 'marked'), 'The
  sigil above the arch burns at your approach.', '')` — tags, credits,
  disposition: anything readable can steer text.
- **Delegate to a function attribute:** keep a long renderer in one
  attribute and call it from several descs with
  `result = eval_attr(me, 'render_weather')` — softcode's subroutine.
- **Keep blocks decision-only:** messages beyond the rendered text
  belong in `ON_LOOK` scripts, not inline blocks — blocks may `pemit`
  but world ops (combat, movement, timers) are dropped by design at
  render time.
