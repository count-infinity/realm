# 190. Score screen

> Checklist item 190 ([now]): *at-a-glance character status, eval_attr layout, left/repeat/ansi*

**What you'll build:** a carried datapad whose `sheet` verb prints an
at-a-glance status panel with attributes, a drawn HP bar, and a handful of
featured skills, laid out with the text-formatting primitives.

**Concepts:** a [`$`-command](../reference/softcode.md#guard-on-target) on an
inventory gadget, reading the enactor's own attributes, and the text-layout
functions [`left`](../reference/softcode.md#fn-left) (pad and truncate to a
column), [`repeat`](../reference/softcode.md#fn-repeat) (rules and bars), and
[`ansi`](../reference/softcode.md#fn-ansi) (colour).

## How it works

The finished datapad answers a fresh verb, `sheet`, by reading your character's
attributes and drawing them into one compact panel: a coloured name header, a
rule line, the four base attributes, an HP bar with your current and maximum
hit points, and a short column of featured skills. This section covers where
those numbers live, why a carried gadget can read them, and how three layout
functions arrange them.

### Where the numbers come from

A character's sheet is just attributes. Chargen writes the four base
attributes (`strength`, `dexterity`, `intelligence`, `health`) and one
`skill_<name>` per trained skill when it applies your chosen template, and
`finish_chargen` derives `hp`, `max_hp`, and `dodge` from those. Your
`template` name and `character_points` are stored the same way. Any script
reads them with [`get_attr`](../reference/softcode.md#fn-get_attr), so a
`$sheet` command-trigger on a gadget you carry renders your own status
wherever you go.

Reading needs no special permission: REALM attributes are open unless flagged
`secret`, so the datapad reads the enactor's public stats directly. (Writing
another object's attributes would need control, but a score screen only
reads.)

### Why the verb is `sheet`, not `score`

REALM already ships a plain read-out: the builtin `points` (aliases `cp` and
`score`) lists your character points and every trained skill straight from the
sheet. That is the exhaustive list. A *score screen* is the opposite job, the
headline numbers arranged to be read in one glance, so we build it as content
rather than lean on the builtin.

Builtins dispatch **before** `$`-triggers, so a `$score` verb would be
swallowed by the native command. The datapad answers to `sheet`, a name no
builtin owns. (See [191](191_help_extensions.md) for that dispatch rule in
full.)

### How three functions lay it out

The panel is three primitives doing what they did in MUSH:

- **[`repeat`](../reference/softcode.md#fn-repeat)`(text, n)`** draws the rule
  line (`repeat('=', 32)`) and the HP bar, a run of `#` for the filled portion
  and `-` for the rest.
- **[`left`](../reference/softcode.md#fn-left)`(text, n)`** keeps the leftmost
  `n` characters. It does not pad on its own, so the skill column pads first
  and truncates second: `left(name + repeat(' ', 16), 16)` appends sixteen
  spaces and then trims back to sixteen, giving a fixed-width cell whatever the
  name's length.
- **[`ansi`](../reference/softcode.md#fn-ansi)`(codes, text)`** colours the
  name header (`'ch'`, bright cyan), the `Skills` label (`'c'`, plain cyan),
  and the filled bar (`'gh'`, bright green). It returns `|`-markup that the
  client renders as colour.

## Build it

Make the datapad. `@create` leaves it in your inventory, which is on the
command-search path, so its verbs work wherever you carry it with no need to
drop it:

```text
@create datapad
```

`skills` is the featured list the screen shows. It is a plain data literal, so
it stays a one-line `@set`; edit it to spotlight whatever your game cares
about:

```text
@set datapad/skills = ["guns", "stealth", "observation"]
```

Now the renderer, hung on a `$sheet` trigger. It reads the enactor's stats,
computes the HP bar, builds one padded line per featured skill, then stitches
header, rule, stat line, HP line, and skills into a single message. The HP bar
is the one piece of arithmetic: `fill` is the tenths of health remaining,
clamped to `0..10` with [`clamp`](../reference/softcode.md#fn-clamp), and the
bar is that many green `#` followed by grey `-`. A `$`-command verb dispatches
straight to its object, so no `if target is me:` guard is needed:

```text
@set datapad/cmd_sheet = '''
$sheet:
p = enactor
skl = V('skills', [])
st = get_attr(p, 'strength', 10)
dx = get_attr(p, 'dexterity', 10)
iq = get_attr(p, 'intelligence', 10)
ht = get_attr(p, 'health', 10)
mhp = max(get_attr(p, 'max_hp', st), 1)
hp = get_attr(p, 'hp', mhp)
fill = clamp((hp * 10) // mhp, 0, 10)
bar = '[' + ansi('gh', repeat('#', fill)) + repeat('-', 10 - fill) + ']'
# one fixed-width cell per featured skill: pad to 16, then keep leftmost 16
rows = [left(capstr(s) + repeat(' ', 16), 16) + str(get_attr(p, 'skill_' + s, '-')) for s in skl]
header = ansi('ch', capstr(name(p))) + ' the ' + get_attr(p, 'template', 'adventurer')
stats = f'ST {st}   DX {dx}   IQ {iq}   HT {ht}'
vitals = f'HP {bar} {hp}/{mhp}   Dodge {get_attr(p, "dodge", 8)}   CP {get_attr(p, "character_points", 0)}'
pemit(enactor, header + '\n' + repeat('=', 32) + '\n' + stats + '\n' + vitals + '\n' + ansi('c', 'Skills') + '\n' + '\n'.join(rows))
'''
```

Each base attribute and derived number falls back to a sane default, so the
panel renders even on a half-built character, and a featured skill the reader
has not trained shows `-` rather than blank. The final
[`pemit`](../reference/softcode.md#fn-pemit) delivers the whole panel to the
enactor after the script finishes.

## Try it

On a soldier with 8 of 12 HP. The name header, the `Skills` label, and the
filled portion of the bar arrive coloured (markup such as `|G...|n` that a
client renders); they are shown here with the colour stripped:

```text
> sheet
Bilda the soldier
================================
ST 12   DX 11   IQ 10   HT 12
HP [######----] 8/12   Dodge 8   CP 40
Skills
Guns            13
Stealth         11
Observation     12
```

The bar fills six of ten because `80 // 12 == 6`; take damage and it shortens
next time you check. Compare the builtin `score`, which dumps the raw
attributes and the whole skill list, against `sheet`, the curated dashboard.

## Going further

- **Live vitals to the client:** push the same numbers over GMCP with
  [`oob`](../reference/softcode.md#fn-oob)`(enactor, 'Char.Vitals', {'hp': hp,
  'max_hp': mhp})` so a Mudlet-class client draws a real gauge. See
  [193](193_gmcp_oob.md), which reuses that exact package name.
- **Effects and conditions:** loop a `conditions` list the way `skills` is
  looped and colour each red, so poisons and buffs show on the sheet.
- **A public finger:** a second verb, `$finger *`, renders another player's
  `visual`-flagged attributes (title, bio) instead of their raw stats, a
  courteous read-only view.
- **Column helper:** move `left(x + repeat(' ', n), n)` into its own attribute
  and call it with [`eval_attr`](../reference/softcode.md#fn-eval_attr), the
  same subroutine trick [189](189_minimap.md) uses, so every screen aligns the
  same way.
