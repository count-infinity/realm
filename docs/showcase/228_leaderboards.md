# 228. Leaderboards

> Checklist item 228 — [now] — *periodic aggregation via search_world over tagged players, cached board attrs, push-on-change reads*

**What you'll build:** a Hall of Fame board that ranks the top crafters,
the deadliest fighters, and the richest players. A heartbeat sweeps every
player in the world, sorts them by each stat, and caches the top five;
`leaderboard crafters` just reads the cache.

**Concepts:** **periodic aggregation** with `search_world` over
`player`-tagged objects and their stat attributes; sorting and slicing to
a top-N; the **push-on-change** idiom the [weather system](036_weather_system.md)
teaches — the *tick* does the expensive scan and stamps a cached
`board_<cat>` attribute; the *read* verb does one shallow attribute
lookup, never a live world scan.

## How it works

**One heavy sweep, many cheap reads.** Ranking means looking at every
player — an expensive query you never want to run inside a `look` or a
command a hundred players might spam. So the board follows the
[weather](036_weather_system.md) push-on-change rule: a `script_ticker`
does the scan on its own worker stack, sorts, and writes the finished top-
five into `board_craft`, `board_fight`, `board_rich`. `leaderboard` then
reads a ready-made list — no computation on the player's call stack.

**`search_world` is the aggregation primitive.** `search_world(tag=
'player', attr='craft_score')` returns exactly the players who have that
stat; wrap each in `[value, name]`, `sorted(..., reverse=True)`, slice
`[:5]`. "Richest" is the one that can't filter on a stat attribute —
credits are the engine's ledger, not an attribute — so it scans all
players and sorts by `credits(p)`. Same shape, different value function.

**The board is only ever as fresh as the last tick,** and that's the
honest trade: leaderboards are a summary, not a live scoreboard. Tighten
the interval for a livelier board, widen it to spare the sweep — one
number tunes the whole cost.

## Build it

The board and its heartbeat (a plain room object — players come to read
it, or check it from a terminal that `eval_attr`s the same cache):

```text
@dig The Hall of Fame
@teleport The Hall of Fame
@create the Hall of Fame board
drop the Hall of Fame board
@desc the Hall of Fame board = A lit ranking display. LEADERBOARD lists the categories; LEADERBOARD CRAFTERS | FIGHTERS | RICHEST shows a top five.
@behavior the Hall of Fame board = script_ticker, interval:60
```

The aggregation routine — three sweeps, three cached lists:

```text
@set the Hall of Fame board/rebuild = crafters = sorted([[get_attr(p, 'craft_score', 0), name(p)] for p in search_world(tag='player', attr='craft_score')], reverse=True)[:5]; fighters = sorted([[get_attr(p, 'kills', 0), name(p)] for p in search_world(tag='player', attr='kills')], reverse=True)[:5]; rich = sorted([[credits(p), name(p)] for p in search_world(tag='player')], reverse=True)[:5]; set_attr(me, 'board_craft', [r[1] + ' - ' + str(r[0]) for r in crafters]); set_attr(me, 'board_fight', [r[1] + ' - ' + str(r[0]) for r in fighters]); set_attr(me, 'board_rich', [r[1] + ' - ' + str(r[0]) for r in rich]); result = 1
@set the Hall of Fame board/on_tick = eval_attr(me, 'rebuild')
```

The reader — bare `leaderboard` lists categories, `leaderboard <cat>`
prints a cached top five:

```text
@set the Hall of Fame board/cmd_boards = $leaderboard:pemit(enactor, 'Leaderboards: LEADERBOARD CRAFTERS | FIGHTERS | RICHEST.')
@set the Hall of Fame board/cmd_board = $leaderboard *:cat = trim(arg0).lower(); key = {'crafters': 'board_craft', 'crafting': 'board_craft', 'fighters': 'board_fight', 'fighting': 'board_fight', 'richest': 'board_rich', 'rich': 'board_rich'}.get(cat, ''); rows = get_attr(me, key, []) if key else []; pemit(enactor, 'Top ' + cat + ':') if key else pemit(enactor, 'Boards: crafters, fighters, richest.'); [pemit(enactor, '  ' + str(i + 1) + '. ' + r) for i, r in enumerate(rows)]; pemit(enactor, '  (empty - check back after the next tally)') if key and not rows else None
```

## Try it

Give a few players stats however your game hands them out (crafting XP,
kill counts, credits), then run a tally:

```text
@eval set_attr(get('Bob'), 'craft_score', 120)
@eval set_attr(get('Cass'), 'craft_score', 80)
@eval adjust_credits(get('Cass'), 500)
@tr the Hall of Fame board/rebuild
```

Now the reads are instant, straight from cache:

```text
leaderboard crafters
   Top crafters:
     1. Bob - 120
     2. Cass - 80
leaderboard richest
   Top richest:
     1. Cass - 500
     ...
leaderboard
   -> Leaderboards: LEADERBOARD CRAFTERS | FIGHTERS | RICHEST.
```

Change a stat and *don't* re-tally — the board still shows the old numbers,
because the read never scans. That staleness is the design: the next
heartbeat refreshes everything at once.

## Going further

- **More boards, same shape** — add `board_bounty` off a `bounties`
  attribute, or `board_deaths`; each is one more line in `rebuild` with a
  different attribute name.
- **Per-zone ladders** — filter the sweep with `search_world(tag=
  'zone:frontier')` intersected with players, for a regional Hall of Fame.
- **Rewards for the top** — on rebuild, hand the #1 crafter a
  [title/badge](220_titles_badges.md) via the Herald, so the leaderboard
  *grants* the "Master Artisan" honor automatically.
- **Live GMCP ticker** — `oob` the cached lists to subscribed clients each
  rebuild for a scrolling scoreboard, still off the players' call stacks.
```
