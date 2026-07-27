# 229. Login streak rewards

> Checklist item 229 ([now]): *ON_CONNECT date math, streak attrs, catch-up grace, perk spawning*

**What you'll build:** a Daily Rewards kiosk that pays players for showing up.
Log in on a new day and your streak climbs while your payout grows; miss a
single day and a grace window forgives you; miss more and the run resets. Every
seventh day pays an anniversary bonus.

**Concepts:** date math on `ON_CONNECT`, where the day number is
[`now()`](../reference/softcode.md#fn-now)` // 86400` compared against a stored
`last_<id>`; a consecutive-day streak counter; a catch-up grace window that
tolerates one missed day; scaling rewards paid out of a funded master with
[`transfer_credits`](../reference/softcode.md#fn-transfer_credits); and an
anniversary bonus on multiples of seven.

## How it works

The finished kiosk is one object holding two numbers per player: the epoch day
that player last claimed, and how long their run is. A login hands the kiosk a
new day number, it subtracts, and the difference decides everything: pay, pay
and reset, or say nothing. This section answers three questions in that order,
namely what a "day" is, how the gap is turned into a streak, and how a single
object hears logins in rooms it is standing nowhere near.

### What counts as a new day?

Epoch seconds divided by 86400 is a plain integer day number, which is why the
whole feature is arithmetic rather than calendar handling. `now() // 86400`
returns the same five-digit integer for every player at once and ticks up one
at UTC midnight, which leaves no calendar or timezone to reconcile. The kiosk
stores that number per player as `last_<id>` and compares it to the day of the
current login:

- **Same day** (`day == last`) means the player already claimed, so nothing is
  paid.
- **First login ever** leaves `last` at its default of 0, which never equals a
  real epoch day number, so the branch that starts a run at 1 catches it.
- **A gap of 1 or 2 days** continues the run at `streak + 1`, because a gap of
  2 means exactly one missed day and the catch-up grace forgives it.
- **A gap of 3 or more** means the run is broken, so the streak resets to 1.

Splitting on the gap rather than on "was it yesterday" is what buys the grace
window for free: widening the tolerance is a change to one number.

### Where does the reward money come from?

The payout is `streak * daily`, so day 10 pays five times what day 2 pays and
the incentive compounds, and every seventh day adds a flat `weekly` bonus on
top. That money is real: `transfer_credits(me, enactor, amount)` moves credits
out of the kiosk's own balance into the player's, and it returns False (moving
nothing) once the kiosk runs dry. Fund the kiosk during the build with
[`adjust_credits`](../reference/softcode.md#fn-adjust_credits), which is the
same funded-master rule the [bank](087_bank_accounts.md) and the
[job board](094_job_board.md) follow, so that a promised reward always arrives.

### How does the kiosk hear a login it is not present for?

A login propagates as an `ON_CONNECT` event
([lifecycle hooks](../reference/softcode.md#lifecycle-hooks),
[propagation model](../architecture/events.md)) whose witnesses are the room
the player appeared in, everything in that room, and the
[zone masters](../guides/world-management.md#zones-areas) of that room. Making
the kiosk the master of the `world` zone therefore gets it the hook for every
member room, which matters because players reconnect wherever they logged out
rather than politely in front of the kiosk.

Zone membership is a tag, so the reach is exactly the set of rooms carrying
`zone:world` and no wider: tag each room where players may appear, since a
login in an untagged room is silent. Two details of the hook itself are worth
holding on to. First, the connecting player is `enactor`, and the engine skips
the actor when it walks the witnesses, so a player's own `on_connect`
attribute stays quiet on their own login and only bystanders and masters react.
Second, an `ON_CONNECT` action targets the *room*, so the usual
[`if target is me:` guard](../reference/softcode.md#guard-on-target) would be
False forever and silence the kiosk. A global witness such as this one takes no
target guard and filters on `enactor` instead, exactly like the presence
rosters in [friends list](219_friends_list.md) and
[message in a bottle](083_message_in_bottle.md). For a wider tour of what fires
where, see [245_event_bus_tour.md](245_event_bus_tour.md).

## Build it

Dig the kiosk room, tag it into the `world` zone, and stand the kiosk in it.
The `@zone/master` line is what turns an ordinary prop into the zone's brain:

```text
@dig The Daily Rewards Kiosk = kiosk, out
kiosk
@zone here = world
@create the Daily Rewards
drop the Daily Rewards
@desc the Daily Rewards = A chrome terminal that chirps when you arrive. It pays a daily login bonus that grows with your streak. STREAK shows where you stand.
@zone/master the Daily Rewards = world
```

Two knobs set the economy, namely the per-day multiplier and the flat
seventh-day bonus, and the last line stocks the kiosk so its payouts clear:

```text
@set the Daily Rewards/daily = 10
@set the Daily Rewards/weekly = 50
@eval adjust_credits(get('the Daily Rewards'), 100000)
```

Now the connect hook. It runs five steps in order: read the day and the two
stored numbers, bail out with a message if this player already claimed today,
otherwise decide the new streak from the gap, stamp the new state onto the
kiosk and pay, and finally assemble the report line so the anniversary and
grace notes only appear when they apply:

```text
@set the Daily Rewards/on_connect = '''
day = now() // 86400
last = V('last_' + enactor.id, 0)
streak = V('streak_' + enactor.id, 0)
if last == day:
    pemit(enactor, f'You have already claimed today. Streak: {streak} day(s).')
else:
    if last == 0 or day - last > 2:
        new = 1
    else:
        new = streak + 1  # a gap of 1 OR 2 days continues the run: 2 is the forgiven miss
    reward = new * V('daily', 10)
    bonus = V('weekly', 50) if new % 7 == 0 else 0
    set_attr(me, 'last_' + enactor.id, day)  # per-player keys, so streaks never collide
    set_attr(me, 'streak_' + enactor.id, new)
    transfer_credits(me, enactor, reward + bonus)
    line = f'Day {new} streak! {reward} credits'
    if bonus:
        line += f' + {bonus} anniversary bonus'
    line += ' paid.'
    if day - last == 2:
        line += ' (grace: welcome back)'
    pemit(enactor, line)
'''
```

There is no `if target is me:` line above, and that is deliberate: the kiosk is
a global witness watching every login in the zone, and the connect event's
target is the room rather than the kiosk.

Finally a `streak` verb so a player may check standing between logins. Living
on the zone master, it answers in every `zone:world` room, not only in front of
the kiosk:

```text
@set the Daily Rewards/cmd_streak = '''
$streak:
s = V('streak_' + enactor.id, 0)
last = V('last_' + enactor.id, 0)
today = now() // 86400
if last == today:
    pemit(enactor, f'Current login streak: {s} day(s). Come back tomorrow to extend it.')
else:
    pemit(enactor, f'Current login streak: {s} day(s). Log in fresh to claim today.')
nxt = (s + 1) * V('daily', 10)
if (s + 1) % 7 == 0:
    pemit(enactor, f'Next reward: {nxt} credits plus a weekly bonus!')
else:
    pemit(enactor, f'Next reward: {nxt} credits.')
'''
```

## Try it

Bob's first login ever starts the run and pays day 1:

```text
(Bob connects)
   -> Day 1 streak! 10 credits paid.
> streak
   -> Current login streak: 1 day(s). Come back tomorrow to extend it.
   -> Next reward: 20 credits.
```

To walk the ladder without waiting real days, backdate Bob's `last` with
[`set_attr`](../reference/softcode.md#fn-set_attr) and reconnect him. A gap of
one day continues the run, and the payout scales with it:

```text
> @eval set_attr(get('the Daily Rewards'), 'last_' + get('Bob').id, now() // 86400 - 1)
   -> Done.
(Bob reconnects)
   -> Day 2 streak! 20 credits paid.
```

A gap of two days is the forgiven miss, and a gap of five breaks the run back
to day 1:

```text
> @eval set_attr(get('the Daily Rewards'), 'last_' + get('Bob').id, now() // 86400 - 2)
   -> Done.
(Bob reconnects)
   -> Day 3 streak! 30 credits paid. (grace: welcome back)
> @eval set_attr(get('the Daily Rewards'), 'last_' + get('Bob').id, now() // 86400 - 5)
   -> Done.
(Bob reconnects)
   -> Day 1 streak! 10 credits paid.
```

Two results are worth confirming deliberately. Reconnecting on the same day
pays nothing, which is what makes the reward strictly one per day:

```text
(Bob reconnects, same day)
   -> You have already claimed today. Streak: 1 day(s).
```

And a run that reaches seven pays the anniversary on top of the scaled amount,
which you can force by backdating both stored numbers at once:

```text
> @eval set_attr(get('the Daily Rewards'), 'streak_' + get('Bob').id, 6)
   -> Done.
> @eval set_attr(get('the Daily Rewards'), 'last_' + get('Bob').id, now() // 86400 - 1)
   -> Done.
(Bob reconnects)
   -> Day 7 streak! 70 credits + 50 anniversary bonus paid.
```

Watch the kiosk's own balance fall by exactly what it paid, since the credits
move rather than appear: `@eval pemit(me, str(credits(get('the Daily
Rewards'))))` reads it back at any time.

## Going further

- **Item perks, not just credits.** On a milestone streak, call
  [`create_obj`](../reference/softcode.md#fn-create_obj)`('a supply crate',
  ['thing'], enactor)` under the master's owner authority for a tangible
  reward the [loot crate](024_loot_crate.md) can fill.
- **Escalating tiers.** Read a `tier_<streak>` table so day 30 grants a
  [title](220_titles_badges.md) or a cosmetic instead of merely more coins.
- **Weekly, not daily.** Swap `86400` for `604800` and the same code rewards
  weekly logins, because the period is one constant.
- **Freeze tokens.** Let a player buy a streak freeze that widens the tolerated
  gap to 3 once, banking their run through a long trip, which turns the
  mechanic into a credit sink that sells itself back to them.
