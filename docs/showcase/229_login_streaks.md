# 229. Login streak rewards

> Checklist item 229 — [now] — *ON_CONNECT day math vs last-login attr, consecutive-day streak, one-day catch-up grace, scaling + anniversary perks*

**What you'll build:** a Daily Rewards kiosk that pays players for showing
up. Log in on a new day and your streak climbs and your payout grows; miss
a single day and a grace window forgives you; miss more and it resets.
Every seventh day pays an anniversary bonus.

**Concepts:** **date math on `ON_CONNECT`** — the day number is
`now() // 86400`, compared against a stored `last_<id>`; a **consecutive
-day streak** counter; a **catch-up grace** window that tolerates one
missed day; **scaling rewards** paid from a funded master with
`transfer_credits`; and an **anniversary** bonus on multiples of seven.

## How it works

**A day is an integer, so the whole thing is arithmetic.** `now() //
86400` is the epoch day number — no calendars, no timezones. On connect
the kiosk compares it to `last_<id>`, the day the player last claimed:

- **Same day** (`day == last`) — already claimed; nothing paid.
- **First ever** (`last == 0`) — streak starts at 1.
- **Gap of 1 or 2 days** — streak continues (`streak + 1`). A gap of 2
  means exactly one missed day: the **catch-up grace** forgives it so a
  single busy day doesn't wipe a month's habit.
- **Gap of 3+** — the streak broke; reset to 1.

**The payout scales, and the vault is real.** The reward is `streak *
daily`, so day 10 pays more than day 2 — the incentive compounds. Every
seventh day adds a `weekly` anniversary bonus. The credits come from the
kiosk's own funded balance via `transfer_credits` (fund it up front — a
reward that can bounce is a broken promise, the [bank](087_bank_accounts.md)
and [job board](094_job_board.md) rule), so the payout is honest money
moving, not minting.

**Why a world-zone master.** The reward must fire wherever a player
appears at login, so the kiosk is a world-zone master hearing `ON_CONNECT`
across the zone — the [friends](219_friends_list.md) / [streaks-style
presence](083_message_in_bottle.md) footing. It stores only two attributes
per player, `last_<id>` and `streak_<id>`: the entire streak state.

## Build it

A world-zone kiosk, funded, with its reward knobs:

```text
@dig The Daily Rewards Kiosk = kiosk, out
kiosk
@zone here = world
@create the Daily Rewards
drop the Daily Rewards
@desc the Daily Rewards = A chrome terminal that chirps when you arrive. It pays a daily login bonus that grows with your streak. STREAK shows where you stand.
@zone/master the Daily Rewards = world
@set the Daily Rewards/daily = 10
@set the Daily Rewards/weekly = 50
@eval adjust_credits(get('the Daily Rewards'), 100000)
```

The connect hook — the day math, the grace, the scaling payout:

```text
@set the Daily Rewards/on_connect = day = now() // 86400; last = V('last_' + enactor.id, 0); streak = V('streak_' + enactor.id, 0); pemit(enactor, 'You have already claimed today. Streak: ' + str(streak) + ' day(s).') if last == day and last != 0 else None; new = 0 if last == day and last != 0 else (1 if last == 0 or day - last > 2 else streak + 1); reward = new * V('daily', 10); bonus = V('weekly', 50) if new and new % 7 == 0 else 0; [(set_attr(me, 'last_' + enactor.id, day), set_attr(me, 'streak_' + enactor.id, new), transfer_credits(me, enactor, reward + bonus), pemit(enactor, 'Day ' + str(new) + ' streak! ' + str(reward) + ' credits' + ((' + ' + str(bonus) + ' anniversary bonus') if bonus else '') + ' paid.' + (' (grace: welcome back)' if last and day - last == 2 else ''))) for g in [new > 0] if g]
```

The status verb:

```text
@set the Daily Rewards/cmd_streak = $streak:s = V('streak_' + enactor.id, 0); last = V('last_' + enactor.id, 0); today = now() // 86400; pemit(enactor, 'Current login streak: ' + str(s) + ' day(s). ' + ('Come back tomorrow to extend it.' if last == today else 'Log in fresh to claim today.')); pemit(enactor, 'Next reward: ' + str((s + 1) * V('daily', 10)) + ' credits' + (' plus a weekly bonus!' if (s + 1) % 7 == 0 else '') + '.')
```

## Try it

Bob's first login ever pays day 1:

```text
(Bob connects)
   -> Day 1 streak! 10 credits paid.
streak
   -> Current login streak: 1 day(s). Come back tomorrow to extend it.
```

To see the ladder without waiting a real day, backdate his `last` and
reconnect. Yesterday keeps the run going (payout scales):

```text
@eval set_attr(get('the Daily Rewards'), 'last_' + get('Bob').id, now() // 86400 - 1)
(Bob reconnects)
   -> Day 2 streak! 20 credits paid.
```

Skip a single day and the grace forgives it; skip three and it resets:

```text
@eval set_attr(get('the Daily Rewards'), 'last_' + get('Bob').id, now() // 86400 - 2)
(Bob reconnects)   -> Day 3 streak! 30 credits paid. (grace: welcome back)
@eval set_attr(get('the Daily Rewards'), 'last_' + get('Bob').id, now() // 86400 - 5)
(Bob reconnects)   -> Day 1 streak! 10 credits paid.
```

Reconnecting the same day pays nothing — "You have already claimed today"
— so the reward is strictly one per day. Ride the streak to day 7 and the
anniversary bonus lands on top.

## Going further

- **Item perks, not just credits** — on a milestone streak,
  `create_obj('a supply crate', ['thing'], enactor)` (owner authority) for
  a tangible reward the [loot crate](024_loot_crate.md) can fill.
- **Escalating tiers** — read a `tier_<streak>` table so day 30 grants a
  [title](220_titles_badges.md) or a cosmetic, not just more coins.
- **Weekly, not daily** — swap `86400` for `604800` and the same code
  rewards weekly logins; the period is one constant.
- **Freeze tokens** — let a player spend credits on a "streak freeze" that
  widens the grace to a `gap of 3` once, banking their run through a long
  trip — a credit sink that sells the mechanic back to them.
```
