# 190. Score screen

> Checklist item 190 — [now] — *$-command, eval_attr layout, left/repeat/ansi*

**What you'll build:** a carried datapad whose `sheet` verb prints an
at-a-glance status panel — attributes, a drawn HP bar, and a handful of
featured skills — laid out with the formatting primitives.

**Concepts:** a `$`-command on an inventory gadget, reading the enactor's
own attributes, and the text-layout functions `left()` (pad/truncate to a
column), `repeat()` (rules and bars), and `ansi()` (colour).

## How it works

REALM already ships a plain character read-out: `score` (aliases `cp` /
`points`) lists your character points and **every** trained skill,
straight from the sheet. That is the exhaustive list. A *score screen* is
the opposite job — the headline numbers, arranged to be read in one
glance — so we build it as content rather than lean on the builtin.

A character's sheet is just attributes: `strength` / `dexterity` /
`intelligence` / `health`, the derived `hp` / `max_hp` / `dodge`, the
`template` they chose at chargen, `character_points`, and one `skill_<name>`
per trained skill (that is exactly what `finish_chargen` writes). Any
script can read them with `get_attr`, so a `$sheet` command-trigger on a
gadget you carry can render your own status anywhere you go — the gadget
runs with its owner's authority, and reading public stats needs no
special permission.

The layout is three primitives doing what they did in MUSH:

- **`repeat(text, n)`** draws the rule line (`repeat('=', 32)`) *and* the
  HP bar — a run of `#` for the filled portion, `-` for the rest.
- **`left(text, n)`** right-pads then truncates to a fixed width, so the
  skill column lines up: `left(name + repeat(' ', 16), 16)`.
- **`ansi(codes, text)`** colours the header and the filled bar (`'ch'` =
  bright cyan, `'gh'` = bright green).

Why not `$score`? Builtins dispatch **before** `$`-triggers, so a
`$score` would be swallowed by the native command — the datapad answers
to `sheet`, a fresh verb, instead. (See [191](191_help_extensions.md) for
that dispatch rule in full.)

## Build it

Make the datapad. `@create` leaves it in your inventory, which is on the
command-search path, so its verbs work wherever you carry it — no need to
drop it:

```text
@create datapad
@set datapad/skills = ["guns", "stealth", "observation"]
```

`skills` is the featured list the screen shows; edit it to spotlight
whatever your game cares about. Now the renderer, hung on a `$sheet`
trigger. The HP bar is the one piece of arithmetic: `fill` is the tenths
of health remaining, clamped to `0..10`, and the bar is that many green
`#` followed by grey `-`:

```text
@set datapad/cmd_sheet = $sheet: p = enactor; skl = V('skills', []); st = get_attr(p, 'strength', 10); dx = get_attr(p, 'dexterity', 10); iq = get_attr(p, 'intelligence', 10); ht = get_attr(p, 'health', 10); mhp = max(get_attr(p, 'max_hp', st), 1); hp = get_attr(p, 'hp', mhp); fill = clamp((hp * 10) // mhp, 0, 10); bar = '[' + ansi('gh', repeat('#', fill)) + repeat('-', 10 - fill) + ']'; rows = [left(capstr(s) + repeat(' ', 16), 16) + str(get_attr(p, 'skill_' + s, '-')) for s in skl]; pemit(enactor, f'{ansi("ch", capstr(name(p)))} the {get_attr(p, "template", "adventurer")}\n{repeat("=", 32)}\nST {st}   DX {dx}   IQ {iq}   HT {ht}\nHP {bar} {hp}/{mhp}   Dodge {get_attr(p, "dodge", 8)}   CP {get_attr(p, "character_points", 0)}\n{ansi("c", "Skills")}\n' + '\n'.join(rows))
```

Piece by piece: `p = enactor` is whoever typed `sheet`; the four
attributes and the derived numbers each fall back to a sane default so
the panel renders even on a half-built character; `rows` is one padded
line per featured skill, showing the trained level or `-` if untrained;
the final `pemit` stitches header, rule, stat line, HP line, and skills
into one message.

## Try it

On a soldier with 8 of 12 HP:

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

The bar fills six of ten because `80 // 12 == 6`; take damage and it
shortens next time you check. Compare `score` — the builtin dumps the raw
attributes and the whole skill list; `sheet` is the curated dashboard.

## Going further

- **Live vitals to the client:** push the same numbers over GMCP with
  `oob(enactor, 'Char.Vitals', {'hp': hp, 'max_hp': mhp})` so a
  Mudlet-class client can draw a real gauge — see
  [193](193_gmcp_oob.md).
- **Effects and conditions:** loop a `conditions` list the way `skills`
  is looped and colour each red, so poisons and buffs show on the sheet.
- **A public finger:** a second verb, `$finger *`, renders another
  player's *visual*-flagged attributes (title, bio) instead of their raw
  stats — a courteous read-only view.
- **Column helper:** move `left(x + repeat(' ', n), n)` into its own
  attribute and call it with `eval_attr` ([189](189_minimap.md) uses the
  same subroutine trick) to keep every screen aligned the same way.
