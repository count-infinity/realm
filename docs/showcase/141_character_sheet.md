# 141. Character Sheet Display

> Checklist item 141 ([now]): *the native points command, a formatted $sheet via eval_attr layout, open reads*

**What you'll build:** a bio-scanner that prints a score-style character sheet
(attributes, an HP bar, trained skills, active conditions, and character
points) laid out as a formatted panel. The engine already ships a plain sheet,
the `points` command; this is the pretty one, and it is a single layout
function anyone can restyle.

**Concepts:** the built-in `points`/`score` command as the no-build sheet;
[`eval_attr()`](../reference/softcode.md#fn-eval_attr) as a **layout helper**
(a subroutine call that runs as the caller, unlike PennMUSH's `u()`), building
a multi-line panel from open attribute reads;
[`tags()`](../reference/softcode.md#fn-tags) for the conditions line; and why a
sheet needs no special authority, because **reads are open**.

## How it works

The finished piece is a fixture in a room that answers `sheet` with a boxed
panel of somebody's vital statistics. It reads the character, never writes, and
draws the whole panel from one stored layout attribute. This section answers
three questions: why you barely need to build anything, where the layout lives,
and why an object can read a stranger's whole sheet without any special
authority.

### Why is there almost nothing to build?

There is already a sheet. Type `points` (aliases `score` and `cp`) and the
engine lists your character points and every trained `skill_*`, with the cost
to improve each one. It is the honest, always-current view and it costs zero
build. A *custom* sheet is purely about presentation: your attributes, a health
bar, and the conditions riding on you, arranged the way you want them.

### Where does the layout live?

The scanner stores the sheet's look in a `render` attribute and calls
[`eval_attr(me, 'render', enactor.id)`](../reference/softcode.md#fn-eval_attr).
The attribute builds one big string and hands it back as `result`, which
[`pemit`](../reference/softcode.md#fn-pemit) then sends. `eval_attr` runs the
routine with the caller's authority (the executor stays the scanner, so inside
`render` `me` is still the scanner), which is exactly why `V('skills')` reads
the scanner's own list rather than the viewer's. Splitting the *layout* (a
reusable function) from the *trigger* (`$sheet`) is the same `eval_attr` move
the arena bell ([115](115_arena_spectators.md)) and the grenade
([111](111_grenades.md)) use, and it means restyling the sheet is editing one
attribute.

### Why does reading a stranger's sheet need no authority?

A character's stats, skills, HP, and tags are all readable by anyone; only
`secret`-flagged attributes and a couple of protected identity fields (such as
`password`) are gated. So the scanner can be a plain builder-owned fixture and
still read a stranger's whole sheet. Unlike the trainer or the clone bay, it
never *writes*, so it never needs admin ownership. Which stats to surface as
"skills" is itself data, a `skills` list on the scanner, so the sheet's
contents are a `@set`, not a script edit.

### Where do the conditions come from?

Every effect mirrors its `kind` as a tag
([135](135_injury_treatment.md), [138](138_sleep_rest.md)), so the scanner
reads [`tags(p)`](../reference/softcode.md#fn-tags) and shows the ones that are
character states (`wounded`, `resting`, `encumbered`, `starving`), which turns
the sheet into a live status readout rather than a static block.

## Build it

First dig the alcove, stand in it, and create the scanner with a description
that tells a visitor how to use it:

```text
@dig The Med Scanner Alcove = alcove, out
alcove
@create bio-scanner
drop bio-scanner
@desc bio-scanner = A full-body med scanner on a swivel arm. Type SHEET to print your service record.
```

The scanner decides which stats count as "skills" from a plain list attribute,
so retuning the panel is a `@set`, never a code edit:

```text
@set bio-scanner/skills = melee guns stealth first_aid observation
```

The `$sheet` trigger is a single expression, so it stays a one-liner: it hands
the enactor's id to the layout routine and pemits whatever comes back. A
`$`-command runs only on the object whose trigger matched, so it needs no
`target` guard:

```text
@set bio-scanner/cmd_sheet = $sheet: pemit(enactor, eval_attr(me, 'render', enactor.id))
```

The layout is the one substantial script, so it is a `'''` heredoc block of
ordinary Python. In order, it resolves the viewer from `arg0`, measures the HP
bar, keeps only the skills the character has actually trained, collects the
condition tags, and joins the whole panel into `result`:

```text
@set bio-scanner/render = '''
p = get('#' + arg0)
bar = repeat('=', 40)
hp = int(get_attr(p, 'hp', 0))
mhp = max(1, int(get_attr(p, 'max_hp', 1)))
filled = max(0, min(10, hp * 10 // mhp))
hpbar = f'[{repeat("#", filled)}{repeat("-", 10 - filled)}]'
# a skill only reaches the panel if the character has trained it (skill_* is set)
sk = [s for s in V('skills', '').split() if get_attr(p, 'skill_' + s) is not None]
cond = [t for t in tags(p) if t in ['wounded', 'bleeding', 'resting', 'starving', 'unconscious', 'encumbered', 'restrained']]
result = '\n'.join([
    bar,
    f'  {name(p)}  --  {get_attr(p, "template", "unregistered")}',
    bar,
    f'  ST {get_attr(p, "strength", 10)}    DX {get_attr(p, "dexterity", 10)}    IQ {get_attr(p, "intelligence", 10)}    HT {get_attr(p, "health", 10)}',
    f'  HP {hpbar} {hp}/{mhp}     Dodge {get_attr(p, "dodge", 8)}',
    f'  CP {get_attr(p, "character_points", 0)}',
    '  Skills: ' + (', '.join([f'{s}-{get_attr(p, "skill_" + s)}' for s in sk]) or 'none trained'),
    '  Status: ' + (', '.join(cond) or 'nominal'),
    bar,
])
'''
```

The layout reads five functions worth naming as they appear:
[`get`](../reference/softcode.md#fn-get) resolves the viewer by raw id;
[`repeat`](../reference/softcode.md#fn-repeat) draws the rule and the bar;
[`get_attr`](../reference/softcode.md#fn-get_attr) reads each stat with a
sensible default; [`V`](../reference/softcode.md#fn-v) reads the scanner's own
`skills` list (shorthand for `get_attr(me, 'skills')`); and
[`name`](../reference/softcode.md#fn-name) prints the character's name.

## Try it

Step into the alcove and print your record:

```text
> sheet
========================================
  Ivo  --  soldier
========================================
  ST 12    DX 11    IQ 10    HT 12
  HP [#######---] 9/12     Dodge 9
  CP 6
  Skills: melee-13, guns-12
  Status: wounded
========================================
```

Only trained skills show, since the untrained ones default off your attributes
and would clutter the panel, and the Status line is live: take a jolt from
[135](135_injury_treatment.md) and `wounded` appears; lie down in
[138](138_sleep_rest.md) and it reads `resting`. A brand-new character with no
`skill_*` and no condition tags reads cleanly, printing `Skills: none trained`
and `Status: nominal`. Compare with the built-in, which needs no build at all:

```text
> points
Character points: 6
Skills:
  guns                 12
  melee                13

Spend with: improve <skill>  (4 points per level)
```

The native command is the source of truth; the scanner is the theatre.

## Going further

- **Scan anyone:** add a `$scan *` trigger that resolves
  [`get(trim(arg0))`](../reference/softcode.md#fn-get) and calls the same
  `render`, a medic reading a patient's chart, all on open reads.
- **A GMCP sheet:** send the same fields with
  [`oob(enactor, 'Char.Sheet', {...})`](../reference/softcode.md#fn-oob) so a
  modern client draws it as a panel, the [193](193_gmcp_oob.md) surface.
- **Colour the vitals:** wrap the HP bar in
  [`ansi('r', ...)`](../reference/softcode.md#fn-ansi) below 30% and
  `ansi('g', ...)` above, a health bar that reddens as you bleed
  ([color guide](../guides/color.md)).
- **Equipment and carry:** fold in worn gear and an encumbrance line from
  [136](136_encumbrance.md), reading
  [`contents(p)`](../reference/softcode.md#fn-contents), so the sheet becomes
  the one place a player sees everything about themselves.
