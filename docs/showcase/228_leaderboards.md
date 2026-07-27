# 228. Leaderboards

> Checklist item 228 ([now]): *on_tick aggregation, search_world scans, cached boards*

**What you'll build:** a Hall of Fame board that ranks the top crafters, the
deadliest fighters, and the richest players. A ticker sweeps every player in
the world, sorts them by each stat, and caches the top five, so that
`leaderboard crafters` only has to read the cache back out.

**Concepts:** periodic aggregation with
[`search_world()`](../reference/softcode.md#fn-search_world) over
`player`-tagged objects and their stat attributes; sorting and slicing to a
top five inside the sandbox; and the push-on-change idiom that
[036 (weather system)](036_weather_system.md) teaches, in which the tick pays
for the expensive scan and stamps a cached `board_<category>` attribute, while
the reading verb does one shallow attribute lookup.

## How it works

The finished board is a single object carrying three cached lists
(`board_craft`, `board_fight`, `board_rich`), one script that recomputes all
three, and two `$`-commands that print them. Everything expensive happens on
the ticker, and everything a player triggers is a lookup. This section answers
three questions in turn: why the ranking runs on a timer, how `search_world`
gathers the candidates, and why the money board is shaped differently from the
other two.

### Why the ranking runs on a timer rather than on the read

Ranking means looking at every player in the world, which is exactly the kind
of query you want to keep out of a `look` or a verb a hundred people might
spam. So the board follows the [weather system's](036_weather_system.md)
push-on-change rule: the `script_ticker` behavior runs the scan on the server's
heartbeat, sorts the results, and writes the finished top five into three
attributes with [`set_attr()`](../reference/softcode.md#fn-set_attr). The
`leaderboard` verb then reads a list that is already built, so no aggregation
ever lands on a player's call stack.

`script_ticker` counts its `interval` in **world beats**, not seconds, and a
beat is the configurable `WORLD_TICK` of about four seconds, which makes
`interval:60` a sweep roughly every four minutes. Raise the number to spare the
sweep, lower it for a livelier board, since that one parameter tunes the whole
cost.

### How `search_world` gathers the candidates

[`search_world()`](../reference/softcode.md#fn-search_world) is the aggregation
primitive, and it filters on tags and attributes together, so
`search_world(tag='player', attr='craft_score')` returns exactly the players
who have that stat recorded. Each result becomes a `[value, name]` pair, and
because the pair puts the number first, a plain `sorted(..., reverse=True)`
ranks the list; slicing `[:5]` takes the podium.

One argument is worth setting deliberately. `search_world` caps its results,
defaulting to `limit=100` and clamping any larger request down to a hard
maximum of 500, so a world with more than a hundred players would silently
rank only the first hundred the query happened to reach. Passing `limit=500`
raises that ceiling to the engine maximum.

### Why the money board scans every player

Credits live in an ordinary `credits` attribute, so
`search_world(tag='player', attr='credits')` is a legal query. It is the wrong
query here, though, because the attribute is only written once a balance
actually changes, which means a brand-new player with nothing banked is missing
from the results entirely. Reading
[`credits()`](../reference/softcode.md#fn-credits) instead reports 0 for that
player, so the money sweep takes every `player`-tagged object and sorts by the
function. Same shape as the other two boards, different value function.

### How fresh the numbers are

The board is only ever as current as the last sweep, and that is the honest
trade a leaderboard makes: it is a periodic summary rather than a live
scoreboard. A stat that changes between sweeps shows up at the next one.

## Build it

Start with the room and the board itself. The board is a plain object that
players come and read, and `script_ticker` gives it the heartbeat that will
drive the sweep.

```text
@dig The Hall of Fame
@teleport The Hall of Fame
@create the Hall of Fame board
drop the Hall of Fame board
@desc the Hall of Fame board = A lit ranking display. LEADERBOARD lists the categories; LEADERBOARD CRAFTERS | FIGHTERS | RICHEST shows a top five.
@behavior the Hall of Fame board = script_ticker, interval:60
```

Now the aggregation routine, written as a
[`'''` heredoc block](../guides/world-management.md#multi-line-input-heredocs)
because it is real control flow rather than a single expression. It runs three
sweeps, pairs each result's score with its
[`name()`](../reference/softcode.md#fn-name) using
[`get_attr()`](../reference/softcode.md#fn-get_attr) for the stat, sorts the
pairs highest first, keeps five, and stamps the formatted rows onto the board.

```text
@set the Hall of Fame board/rebuild = '''
# limit=500 is the engine maximum; the default of 100 would quietly clip a
# large world's ranking.
crafters = search_world(tag='player', attr='craft_score', limit=500)
fighters = search_world(tag='player', attr='kills', limit=500)
everyone = search_world(tag='player', limit=500)

top_craft = sorted([[get_attr(p, 'craft_score', 0), name(p)] for p in crafters], reverse=True)[:5]
top_fight = sorted([[get_attr(p, 'kills', 0), name(p)] for p in fighters], reverse=True)[:5]
# credits() reports 0 for a player who never banked any, so the money board
# sweeps everyone rather than filtering on the credits attribute.
top_rich = sorted([[credits(p), name(p)] for p in everyone], reverse=True)[:5]

set_attr(me, 'board_craft', [f'{row[1]} - {row[0]}' for row in top_craft])
set_attr(me, 'board_fight', [f'{row[1]} - {row[0]}' for row in top_fight])
set_attr(me, 'board_rich', [f'{row[1]} - {row[0]}' for row in top_rich])
'''
```

The heartbeat itself is one expression, so it stays on a single line:
[`eval_attr()`](../reference/softcode.md#fn-eval_attr) runs the routine stored
above, which keeps the schedule and the logic in separate attributes and lets
you re-run the sweep by hand with `@tr` while testing.

```text
@set the Hall of Fame board/on_tick = eval_attr(me, 'rebuild')
```

Bare `leaderboard` just names the categories, so it is a single
[`pemit()`](../reference/softcode.md#fn-pemit) and stays a one-liner too.

```text
@set the Hall of Fame board/cmd_boards = $leaderboard:pemit(enactor, 'Leaderboards: LEADERBOARD CRAFTERS | FIGHTERS | RICHEST.')
```

`leaderboard <category>` is the reader. It normalises the argument with
[`trim()`](../reference/softcode.md#fn-trim) and `.lower()`, maps the friendly
word onto the cached attribute name, reads that attribute with
[`V()`](../reference/softcode.md#fn-v), and prints the rows numbered. Both
patterns are anchored at both ends, so `$leaderboard *` requires a space and an
argument after the verb and never competes with the bare `$leaderboard` above.

```text
@set the Hall of Fame board/cmd_board = $leaderboard *:'''
boards = {'crafters': 'board_craft', 'crafting': 'board_craft', 'fighters': 'board_fight', 'fighting': 'board_fight', 'richest': 'board_rich', 'rich': 'board_rich'}
cat = trim(arg0).lower()
key = boards.get(cat, '')
if not key:
    pemit(enactor, 'Boards: crafters, fighters, richest.')
else:
    # V(key) reads the cache off the board itself; nothing is scanned here.
    rows = V(key, [])
    pemit(enactor, f'Top {cat}:')
    for i, row in enumerate(rows):
        pemit(enactor, f'  {i + 1}. {row}')
    if not rows:
        pemit(enactor, '  (empty, check back after the next tally)')
'''
```

The rows print as plain `name - score` text. If you would rather have columns,
note that [`left()`](../reference/softcode.md#fn-left) and
[`right()`](../reference/softcode.md#fn-right) truncate without padding, so
reaching a fixed width takes [`repeat()`](../reference/softcode.md#fn-repeat)
alongside them, as in
`left(nm, 16) + repeat(' ', max(0, 16 - strlen(left(nm, 16))))` with
[`strlen()`](../reference/softcode.md#fn-strlen).

Neither script needs a `target` guard. `on_tick` fires only on the object the
`script_ticker` behavior is attached to, and a `$`-command match stops at the
first object in the search order that carries the pattern, so a second board
standing in the same room stays quiet rather than answering alongside this one.
Neither is one of the room-wide
[`ON_<EVENT>` hooks](../reference/softcode.md#lifecycle-hooks) that every object
present would hear, which is where the
[`target` guard](../reference/softcode.md#guard-on-target) is required.

## Try it

Hand a few players some stats however your game awards them (crafting
experience, kill counts, credits), then run a sweep by hand instead of waiting
four minutes for the ticker:

```text
> @eval set_attr(get('Bob'), 'craft_score', 120)
> @eval set_attr(get('Cass'), 'craft_score', 80)
> @eval adjust_credits(get('Cass'), 500)
> @tr the Hall of Fame board/rebuild
  Triggered the Hall of Fame board/rebuild.
```

Now every read is instant, straight out of the cache:

```text
> leaderboard crafters
  Top crafters:
    1. Bob - 120
    2. Cass - 80

> leaderboard richest
  Top richest:
    1. Cass - 500
    2. Vala - 0
    3. Bob - 0

> leaderboard fighters
  Top fighters:
    (empty, check back after the next tally)

> leaderboard
  Leaderboards: LEADERBOARD CRAFTERS | FIGHTERS | RICHEST.
```

The money board is the one to read carefully, because it lists everyone it
found and pads the podium with zero-balance players until enough people have
earned something; the crafting board, filtered on the `craft_score` attribute,
shows only the two players who have that stat at all.

Two more results are worth confirming deliberately. An unknown category falls
back to the category list rather than erroring, and staleness is real: change a
stat without re-running the sweep and the board keeps showing the previous
number, because the read never scans.

```text
> leaderboard bakers
  Boards: crafters, fighters, richest.

> @eval set_attr(get('Bob'), 'craft_score', 999)
> leaderboard crafters
  Top crafters:
    1. Bob - 120
    2. Cass - 80
```

The next heartbeat refreshes all three boards at once.

## Going further

- **More boards, same shape:** add `board_bounty` off a `bounties` attribute,
  or `board_deaths`; each is one more sweep and one more `set_attr` in
  `rebuild`, with a different attribute name.
- **Per-zone ladders:** zone tags live on rooms rather than on players, so a
  regional Hall of Fame filters the sweep by where each player is standing,
  with `[p for p in everyone if 'frontier' in
  zones_of(loc(p))]`, using [`loc()`](../reference/softcode.md#fn-loc) and
  [`zones_of()`](../reference/softcode.md#fn-zones_of).
- **Rewards for the top:** on rebuild, hand the leading crafter a
  [title or badge](220_titles_badges.md), so the leaderboard grants the
  "Master Artisan" honor automatically.
- **Live GMCP ticker:** [`oob()`](../reference/softcode.md#fn-oob) the cached
  lists to subscribed clients on each rebuild for a scrolling scoreboard, still
  off the players' call stacks.
