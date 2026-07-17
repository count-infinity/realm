# 141. Character Sheet Display

> Checklist item 141 — [now] — *the native points command, a formatted $sheet via eval_attr layout, open reads*

**What you'll build:** a bio-scanner that prints a score-style character
sheet — attributes, an HP bar, trained skills, active conditions, and
character points — laid out as a formatted panel. The engine already has a
plain sheet (`points`); this is the pretty one, and it's a single layout
function anyone can restyle.

**Concepts:** the built-in `points`/`score` command as the no-build sheet;
`eval_attr()` as a **layout helper** (a subroutine call, not Penn's
`u()` — it runs as the caller), building a multi-line
panel from open attribute reads; `tags()` for the conditions line; and why
a sheet needs no special authority — **reads are open**.

## How it works

1. **There's already a sheet — `points`.** Type `points` (aliases `score`,
   `cp`) and the engine lists your character points and every trained
   `skill_*`, with the improve cost. It's the honest, always-current view
   and costs zero build. A *custom* sheet is about presentation: your
   attributes, a health bar, the conditions riding on you — arranged your
   way.

2. **`eval_attr` is your layout function.** The scanner stores the sheet's
   look in a `render` attribute and calls `eval_attr(me, 'render',
   enactor.id)`; the attribute builds one big string and hands it back as
   `result`, which `pemit` sends. Splitting the *layout* (a reusable
   function) from the *trigger* (`$sheet`) is the same `eval_attr` move the
   arena bell ([115](115_arena_spectators.md)) and grenade
   ([111](111_grenades.md)) use — and it means restyling the sheet is
   editing one attribute.

3. **Reads are open, so no authority is needed.** A character's stats,
   skills, HP, and tags are all readable by anyone — only `password` and
   `secret`-flagged attributes are gated. So the scanner can be a plain
   builder-owned fixture and still read a stranger's whole sheet; unlike
   the trainer or the clone bay, it never *writes*, so it never needs admin
   ownership. Which stats to surface as "skills" is itself data — a
   `skills` list on the scanner — so the sheet's contents are a `@set`, not
   a script edit.

4. **Conditions come from `tags()`.** Every effect mirrors its `kind` as a
   tag ([135](135_injury_treatment.md), [138](138_sleep_rest.md)), so the
   scanner reads `tags(p)` and shows the ones that are character states —
   `wounded`, `resting`, `encumbered`, `starving` — turning the sheet into
   a live status readout, not a static block.

## Build it

The scanner, the list of skills it surfaces, and the layout function:

```text
@dig The Med Scanner Alcove = alcove, out
alcove
@create bio-scanner
drop bio-scanner
@desc bio-scanner = A full-body med scanner on a swivel arm. Type SHEET to print your service record.
@set bio-scanner/skills = melee guns stealth first_aid observation
@set bio-scanner/cmd_sheet = $sheet: pemit(enactor, eval_attr(me, 'render', enactor.id))
@set bio-scanner/render = p = get('#' + arg0); bar = repeat('=', 40); hp = int(get_attr(p, 'hp', 0)); mhp = max(1, int(get_attr(p, 'max_hp', 1))); filled = max(0, min(10, hp * 10 // mhp)); hpbar = f'[{repeat("#", filled)}{repeat("-", 10 - filled)}]'; sk = [s for s in V('skills', '').split() if get_attr(p, 'skill_' + s) != None]; cond = [t for t in tags(p) if t in ['wounded', 'bleeding', 'resting', 'starving', 'unconscious', 'encumbered', 'restrained']]; result = '\n'.join([bar, f'  {name(p)}  --  {get_attr(p, "template", "unregistered")}', bar, f'  ST {get_attr(p, "strength", 10)}    DX {get_attr(p, "dexterity", 10)}    IQ {get_attr(p, "intelligence", 10)}    HT {get_attr(p, "health", 10)}', f'  HP {hpbar} {hp}/{mhp}     Dodge {get_attr(p, "dodge", 8)}', f'  CP {get_attr(p, "character_points", 0)}', '  Skills: ' + (', '.join([f'{s}-{get_attr(p, "skill_" + s)}' for s in sk]) or 'none trained'), '  Status: ' + (', '.join(cond) or 'nominal'), bar])
```

## Try it

Step into the alcove and print your record:

```text
sheet
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

Only trained skills show (the untrained ones default off your attributes
and would clutter the panel), and the Status line is live — take a jolt
from [135](135_injury_treatment.md) and `wounded` appears; lie down in
[138](138_sleep_rest.md) and it reads `resting`. Compare with the built-in,
which needs no build at all:

```text
points
Character points: 6
Skills:
  guns                 12
  melee                13
Spend with: improve <skill>  (4 points per level)
```

The native command is the source of truth; the scanner is the theatre.

## Going further

- **Scan anyone:** add `$scan *` that resolves `get(trim(arg0))` and calls
  the same `render` — a medic reading a patient's chart, all on open reads.
- **A GMCP sheet:** send the same fields with `oob(enactor, 'Char.Sheet',
  {...})` so a modern client draws it as a panel — the [193] surface.
- **Colour the vitals:** wrap the HP bar in `ansi('r', ...)` below 30% and
  `ansi('g', ...)` above — a health bar that reddens as you bleed
  ([color guide](../guides/color.md)).
- **Equipment & carry:** fold in worn gear and an encumbrance line from
  [136](136_encumbrance.md), reading `contents(p)` — the sheet as the one
  place a player sees everything about themselves.
