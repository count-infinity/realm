# 130. Fishing

> Checklist item 130 — [now] — *wait() + prompt() timing windows, catch tables*

**What you'll build:** A scummy dockside pool: `cast line`, wait out a
lull you can't predict, and when the float dips you have a
four-second window to `hook` — a real-time reflex beat resolved by an
angling roll against a weighted catch table (mostly mudskippers,
sometimes a dartfish, now and then a boot).

**Concepts:** a **timing minigame from two `wait()`s** — one
schedules the bite after a random lull, the second slams the window
shut — with the state between them as plain attributes (`line_out`,
`bite_open`); the [loot crate](024_loot_crate.md)'s **weighted table**
as a catch list; a graded `margin_under` hook roll with numeric miss
text; and guards for every wrong moment (no line, too early, too
late).

## How it works

**The minigame is a tiny state machine.** `cast` sets `line_out`,
remembers the angler, and schedules `trigger me/bite` after the lull
— `wait(seconds, command)` runs a script command as the pond later,
the [music box](009_music_box.md)'s chain trick. `bite` opens the
window (`bite_open`), announces the dip, and schedules `trigger
me/slack` to close it. Every script *guards on the state attribute
before acting*, which is what makes stale timers harmless: if you
hooked in time, `slack` finds `bite_open` already gone and does
nothing. (Note `wait()` is in-memory — a reboot mid-cast loses the
bite, which for a fishing lull is exactly as tragic as it sounds.)

**Hooking is a moment, not a command.** `hook` with no line out is
refused. `hook` before the dip *scares the fish* — the punishing
guard is what makes the window real: you can't mash it. Inside the
window it rolls `margin_under(roll('3d6'), angling)`, quotes the dice
on a miss, and on a hit draws from the catch table — the same
recursive one-line weighted draw as the
[loot crate](024_loot_crate.md), with `[name, weight, tags]` rows so
a junk catch is data, not a special case. The draw is a `lambda` that
**calls itself by name**: walk the rows, spend each row's weight out of
the roll, and take the row the roll lands in. (Older builds of this
pattern pass the lambda to itself — `draw(draw, t, r)` — because a
lambda could not once see the script-local it was being assigned to.
Scripts share one namespace now, so plain recursion works and the extra
parameter is gone.)

**Everything tunable is an attribute.** Lull seconds, window
seconds, and the odds are all `@set`s: a trophy pond is a longer
lull, a tighter window, and a heavier table.

## Build it

The pool, its tempo, and its odds:

```text
@create scum pond
drop scum pond
@desc scum pond = A green-skinned catch pool between dock pilings. Now and then something moves under the scum. CAST LINE here.
@set scum pond/lull = 6
@set scum pond/window = 4
@set scum pond/catches = [["a mottled mudskipper", 55, ["thing", "fish"]], ["a silver dartfish", 30, ["thing", "fish"]], ["a waterlogged boot", 15, ["thing", "junk"]]]
```

Casting — claim the line, schedule the bite:

```text
@set scum pond/cmd_cast = $cast line: pemit(enactor, 'A line is already out. Watch the float; hook when it dips.') if V('line_out', 0) else (set_attr(me, 'line_out', 1), set_attr(me, 'angler', enactor.id), remit(here, name(enactor) + ' casts a line out over the scum.'), wait(V('lull', 6), 'trigger me/bite'))
```

The bite and the closing of the window — each guarded on the state
that must still hold:

```text
@set scum pond/bite = (set_attr(me, 'bite_open', 1), remit(here, 'The float dips hard -- something is on!'), wait(V('window', 4), 'trigger me/slack')) if V('line_out', 0) else None
@set scum pond/slack = (del_attr(me, 'bite_open'), del_attr(me, 'line_out'), del_attr(me, 'angler'), remit(here, 'The water stills. The line drifts back slack, bait gone.')) if V('bite_open', 0) else None
```

And the hook — three guards, a roll, a draw:

```text
@set scum pond/cmd_hook = $hook: lined = V('line_out', 0); dip = V('bite_open', 0); pemit(enactor, 'No line in the water. cast line first.') if not lined else None; (del_attr(me, 'line_out'), del_attr(me, 'angler'), pemit(enactor, 'You yank at still water; anything under the scum is long warned off.')) if lined and not dip else None; res = margin_under(roll('3d6'), get_attr(enactor, 'skill_angling', 9)) if lined and dip else None; draw = lambda t, r: t[0] if r <= t[0][1] or len(t) == 1 else draw(t[1:], r - t[0][1]); c = draw(V('catches', []), rand(1, 100)) if lined and dip else None; (del_attr(me, 'bite_open'), del_attr(me, 'line_out'), del_attr(me, 'angler'), (create_obj(c[0], c[2], here), remit(here, f'{name(enactor)} hooks it clean -- {c[0]} lands flopping on the dock! (margin +{res.margin})')) if res.success else remit(here, f'It spits the hook and is gone. (rolled {res.roll} vs angling {res.effective})')) if lined and dip else None
```

## Try it

```text
cast line
```

...then wait. Six seconds of nothing, then the room jolts: `The float
dips hard -- something is on!` Type `hook` inside the window:
`... hooks it clean -- a mottled mudskipper lands flopping on the
dock! (margin +2)` — the catch is a real `fish`-tagged object at your
feet (dartfish and boots come up per the table's 55/30/15). Miss the
window and the pond tells you: `The water stills. The line drifts
back slack, bait gone.` Blow the roll and you get the dice: `It spits
the hook and is gone. (rolled 14 vs angling 9)`. And the guards keep
the rhythm honest — `hook` with no line: `No line in the water.`;
`hook` before the dip wastes the whole cast: `You yank at still
water; anything under the scum is long warned off.`

## Going further

- **Prompt-driven reeling:** for a longer fight, have the hook open a
  `prompt(enactor, 'It runs! REEL or SLACK?', 'on_reel')` exchange —
  two or three correct calls to land the big one (the
  [jukebox](003_jukebox.md) shows the prompt wizard shape).
- **Bait economics:** require and consume a `bait`-tagged item per
  cast; better bait swaps in a heavier `catches` table — feed the
  [galley](129_cooking_buffs.md) with the good table.
- **Fish that matter:** stamp caught fish with `value` and a size
  rolled off the margin (`str(30 + res.margin * 5) + ' cm'` in a
  `desc_extras` row) — trophies and [pawn-shop](086_currency.md)
  prices from one number.
- **Stocked ponds:** `fish_left` depletion plus a regrowth ticker —
  the [gathering node](121_gathering_nodes.md) pattern makes
  overfishing a real thing.
