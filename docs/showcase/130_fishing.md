# 130. Fishing

> Checklist item 130 ([now]): *wait() + prompt() timing windows, catch tables*

**What you'll build:** A scummy dockside pool. You `cast line`, wait out a
lull you cannot predict, and when the float dips you have a few seconds to
`hook`. A landed catch is an angling roll against a weighted table: mostly
mudskippers, sometimes a dartfish, now and then a boot.

**Concepts:** a timing minigame built from two
[`wait()`](../reference/softcode.md#fn-wait) beats, with the state between them
held as plain attributes (`line_out`, `bite_open`); the
[loot crate](024_loot_crate.md)'s weighted table as a catch list; a graded
[`margin_under`](../reference/softcode.md#fn-margin_under) hook roll with numeric
miss text; and guards for every wrong moment (no line, too early, too late).

## How it works

A cast starts a two-part timer. Casting claims the water and schedules a bite
after an unpredictable lull, and the bite opens a short window and schedules its
own close. Between those two moments the pond's whole state lives in three plain
attributes (`line_out`, `bite_open`, and `angler`), and `hook` resolves the
reflex against a skill roll and a weighted catch table. This section walks the
timer first, then why a mistimed hook cannot break it, then how a hit chooses
its fish.

### How the pond keeps time between casts

[`wait(seconds, command)`](../reference/softcode.md#fn-wait) runs a script
command as the pond exactly that many seconds from now, once, on its own timer
rather than the world heartbeat. So `cast` ends with
`wait(V('lull', 6), 'trigger me/bite')`, which fires the pond's own `bite`
attribute after the lull. This is the same relay the
[music box](009_music_box.md) uses to plink one note per beat. The `bite`
attribute then opens the window and schedules the closer the same way, with
`wait(V('window', 4), 'trigger me/slack')`. Because `wait()` is in-memory, a
reboot mid-cast drops the pending bite, which for a fishing lull is harmless;
where a timer must survive a reboot you reach for
[`expire()`](../reference/softcode.md#fn-expire) instead.

### Why a mistimed hook cannot break the pond

Every scheduled script reads its state attribute before it acts, so a stale
timer finds nothing left to do and stays silent. If you hook inside the window,
`hook` clears `bite_open`, so when `slack` finally fires it sees the window
already closed and does nothing. The same guard covers the reverse case: a
`slack` that fires while `line_out` is gone is a no-op. That is what lets the
pond schedule freely without ever tracking or cancelling its own timers.

### How a hit chooses its catch

Hooking is a moment, not a command, so `hook` guards on the state first: with no
line it refuses, and a jab before the dip scares the fish and burns the cast.
Inside the window it rolls
[`margin_under`](../reference/softcode.md#fn-margin_under)`(`[`roll`](../reference/softcode.md#fn-roll)`('3d6'), `[`get_attr`](../reference/softcode.md#fn-get_attr)`(enactor, 'skill_angling', 9))`,
a roll-under skill check whose `margin` grades the result. On a miss it quotes
the dice; on a hit it draws from the `catches` table. That table is a list of
`[name, weight, tags]` rows held as a plain attribute, so a junk catch is data,
not a special case. The draw is a self-calling `lambda` that folds one
[`rand(1, 100)`](../reference/softcode.md#fn-rand) roll down the rows, spending
each row's weight until the roll lands inside one, the same weighted draw the
[loot crate](024_loot_crate.md) uses.
[`create_obj`](../reference/softcode.md#fn-create_obj)`(c[0], c[2], here)` then
mints the fish (or the boot) onto the dock, carrying the row's tags.

### What you can retune

The lull seconds, the window seconds, and the odds are all `@set`s, so a trophy
pond is a longer lull, a tighter window, and a heavier table. The scripts never
change.

## Build it

Create the pool and give it its tempo and its odds. `lull` is the seconds before
a bite, `window` is how long the float stays dipped, and `catches` is the
weighted table, each row `[name, weight, tags]`:

```text
@create scum pond
drop scum pond
@desc scum pond = A green-skinned catch pool between dock pilings. Now and then something moves under the scum. CAST LINE here.
@set scum pond/lull = 6
@set scum pond/window = 4
@set scum pond/catches = [["a mottled mudskipper", 55, ["thing", "fish"]], ["a silver dartfish", 30, ["thing", "fish"]], ["a waterlogged boot", 15, ["thing", "junk"]]]
```

The `$cast line` command claims the line if the water is free, tells the room,
and schedules the bite:

```text
@set scum pond/cmd_cast = '''
$cast line:
if V('line_out', 0):
    pemit(enactor, 'A line is already out. Watch the float; hook when it dips.')
else:
    set_attr(me, 'line_out', 1)
    set_attr(me, 'angler', enactor.id)  # remember who cast, for a future award
    remit(here, name(enactor) + ' casts a line out over the scum.')
    wait(V('lull', 6), 'trigger me/bite')  # fire the bite after the lull
'''
```

The bite and its closer are the timer pair, each guarded on the state that must
still hold. The bite opens the window and schedules `slack`; `slack` runs only
while `bite_open` is set, so a landed catch (which clears it) leaves `slack`
with nothing to do:

```text
@set scum pond/bite = '''
if V('line_out', 0):
    set_attr(me, 'bite_open', 1)
    remit(here, 'The float dips hard -- something is on!')
    wait(V('window', 4), 'trigger me/slack')  # schedule the window to close
'''
@set scum pond/slack = '''
if V('bite_open', 0):
    del_attr(me, 'bite_open')
    del_attr(me, 'line_out')
    del_attr(me, 'angler')
    remit(here, 'The water stills. The line drifts back slack, bait gone.')
'''
```

The `$hook` command is three guards, a roll, and a draw. It refuses with no
line, punishes a jab before the dip, and inside the window rolls angling and
either mints a catch off the table or quotes the failed dice:

```text
@set scum pond/cmd_hook = '''
$hook:
lined = V('line_out', 0)
dip = V('bite_open', 0)
if not lined:
    pemit(enactor, 'No line in the water. cast line first.')
elif not dip:
    del_attr(me, 'line_out')  # an early jab scares the fish and burns the cast
    del_attr(me, 'angler')
    pemit(enactor, 'You yank at still water; anything under the scum is long warned off.')
else:
    res = margin_under(roll('3d6'), get_attr(enactor, 'skill_angling', 9))
    del_attr(me, 'bite_open')
    del_attr(me, 'line_out')
    del_attr(me, 'angler')
    if res.success:
        draw = lambda t, r: t[0] if r <= t[0][1] or len(t) == 1 else draw(t[1:], r - t[0][1])  # spend each row's weight, take the row the roll lands in
        c = draw(V('catches', []), rand(1, 100))
        create_obj(c[0], c[2], here)
        remit(here, f'{name(enactor)} hooks it clean -- {c[0]} lands flopping on the dock! (margin +{res.margin})')
    else:
        remit(here, f'It spits the hook and is gone. (rolled {res.roll} vs angling {res.effective})')
'''
```

## Try it

Cast, then wait out the lull:

```text
> cast line
Bilda casts a line out over the scum.

(a few seconds later)
The float dips hard -- something is on!
```

Type `hook` inside the window and, on a made roll, the catch lands at your feet:

```text
> hook
Bilda hooks it clean -- a mottled mudskipper lands flopping on the dock! (margin +2)
```

The catch is a real `fish`-tagged object on the dock; a dartfish or a boot comes
up per the table's 55/30/15 split. Only the catch line varies with the roll and
the draw. Miss the window entirely and the pond closes it for you:

```text
> hook
The water stills. The line drifts back slack, bait gone.
```

Blow the roll and you get the dice on the record:

```text
> hook
It spits the hook and is gone. (rolled 14 vs angling 9)
```

And the guards keep the rhythm honest. A `hook` with no line answers
`No line in the water. cast line first.`, and a `hook` before the dip wastes the
whole cast: `You yank at still water; anything under the scum is long warned
off.`

## Going further

- **Prompt-driven reeling:** for a longer fight, have the hook open a
  `prompt(enactor, 'It runs! REEL or SLACK?', 'on_reel')` exchange, so two or
  three correct calls are needed to land the big one. The
  [jukebox](003_jukebox.md) shows the prompt wizard shape.
- **Bait economics:** require and consume a `bait`-tagged item per cast, and let
  better bait swap in a heavier `catches` table, then feed the good fish to the
  [galley](129_cooking_buffs.md).
- **Fish that matter:** stamp caught fish with a `value` and a size rolled off
  the margin (`str(30 + res.margin * 5) + ' cm'`), so trophies and
  [pawn-shop](086_currency.md) prices both come from one number.
- **Stocked ponds:** add a `fish_left` count that depletes and a regrowth
  ticker, so overfishing becomes real. The
  [gathering node](121_gathering_nodes.md) builds that pattern out.
