# 068. NPC daily schedule

> Checklist item 68 ([now]): *softcode clock, attach_behavior/detach_behavior by hour*

**What you'll build:** Verity, a supplier who opens her Market Street stall at
nine, trades all day, locks up at nine in the evening, walks upstairs to her
loft, and sleeps. At night the shop stands physically empty, and the
`shopkeeper` behavior itself is off her, so even shouting `buy` at the counter
gets nothing.

**Concepts:** a softcode clock (one object, one
[`on_tick`](../reference/softcode.md#lifecycle-hooks)), deriving a state machine
from game time, [`attach_behavior`](../reference/softcode.md#fn-attach_behavior)
and [`detach_behavior`](../reference/softcode.md#fn-detach_behavior) from
softcode, a scripted move for a real commute, and composing with the built-in
[shopkeeper](063_shopkeeper.md).

## How it works

Verity's day has three parts that never touch each other directly: a clock
object that advances the hour, a ticker on Verity that reads the hour on every
beat, and two state scripts the ticker chooses between. This section covers
where the time lives, how Verity decides what to do with it, and why opening
and closing the stall need no separate "closed" flag to keep in sync.

### Where does the time come from?

REALM ships no global game clock, and that is deliberate, because a clock is
two lines of softcode: an object whose `on_tick` increments an `hour` attribute
modulo 24. [Tutorial 037](037_day_night_descs.md) builds the identical clock to
drive a plaza's day/night descriptions, which is the point of building time as
data. Attribute reads are open to every script, so the whole town shares one
clock by name:
[`get_attr`](../reference/softcode.md#fn-get_attr)`('town clock', 'hour', 12)`.
The clock advances itself with
[`set_attr`](../reference/softcode.md#fn-set_attr), reading its own hour through
[`V`](../reference/softcode.md#fn-v).

### How does Verity decide what to do each hour?

Verity runs her own `script_ticker`, so each beat her `on_tick` asks the clock
for the hour and routes to one of two state scripts with the
[`trigger`](../reference/softcode.md#script-commands-simple-scripts-cmd-output-lines)
command:

```
9 <= hour < 21  ->  open_up:    not at the shop? walk one step toward it.
                                at the shop, not trading? attach the
                                shopkeeper behavior, announce, and trade.
otherwise       ->  close_down: still trading? detach the shopkeeper and
                                announce. otherwise walk home and sleep.
```

Because `on_tick` runs only on the object that carries the ticker, this script
fires on Verity alone and needs no `if target is me` guard. A guard is for a
reactive [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook, which
fires on every object in the room, so it is not this case.

### How do opening and closing work without a "closed" flag?

Presence is the mechanic, twice over. The `buy` and `list` commands find a
merchant by scanning the room for the `shopkeeper` behavior, so closing is
literally [`detach_behavior`](../reference/softcode.md#fn-detach_behavior)`(me,
'shopkeeper')` and walking away is belt-and-braces on top of that. There is no
"closed" flag to keep in sync, because the presence of the behavior on Verity
is the state: `'shopkeeper' in
`[`behaviors`](../reference/softcode.md#fn-behaviors)`(me)` reads it straight
back. The commute is real movement too, since the scripted
[`move`](../reference/softcode.md#script-commands-simple-scripts-cmd-output-lines)`('downstairs')`
goes through exit locks and doors exactly like a player, one exit per tick, so
with a longer route you would watch her walk to work street by street.

The stock is her inventory (`give` her goods to restock), prices come from each
item's `value` times her markup, and her disposition toward the buyer still
moves the price by up to five percent per point. The built-in behavior composes
with everything the [shopkeeper tutorial](063_shopkeeper.md) taught.

## Build it

Dig the shop and the loft above it, working from the Square of
[tutorial 060](060_wandering_npc.md). The dig leaves you standing on Market
Street, which is where the clock and Verity will be dropped:

```text
@dig Market Street = market, square
market
@zone here = town
@dig The Loft = upstairs, downstairs
```

The town clock is an ordinary object, dropped so it stands in the world with a
starting hour. Its tick advances the hour modulo 24, and `interval:1` means one
game hour per world beat, which is brisk and good for testing. At the default
four-second beat, `interval:225` makes a fifteen-minute game hour instead, so
pick your tempo with one number. The body is a single statement, so it stays on
one line:

```text
@create town clock
drop town clock
@set town clock/hour = 6
@set town clock/on_tick = set_attr(me, 'hour', (V('hour', 0) + 1) % 24)
@behavior town clock = script_ticker, interval:1
```

Now the keeper. Create and drop her on Market Street, and tag her `npc`:

```text
@create Verity
@tag Verity = npc
drop Verity
```

Her dispatcher reads the shared clock and routes to one of the two state
scripts by the hour band. The body has more than one statement, so it is a
`'''` heredoc block (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)):

```text
@set Verity/on_tick = '''
h = get_attr('town clock', 'hour', 12)      # read the shared town clock
if 9 <= h < 21:
    trigger('open_up')
else:
    trigger('close_down')
'''
```

`open_up` walks her to the stall if she is not there yet, and once she is
standing on Market Street it attaches the `shopkeeper` behavior and announces
the opening. The `markup=1.2` param sets her sell price to one and a fifth of
each item's `value`:

```text
@set Verity/open_up = '''
if name(here) != 'Market Street':
    move('downstairs')          # not at the stall: step one exit toward it
elif 'shopkeeper' not in behaviors(me):
    attach_behavior(me, 'shopkeeper', markup=1.2)   # attaching the behavior opens the stall
    say('Shutters up! Fresh goods at fair prices!')
'''
```

`close_down` reads inside-out. The first off-hours tick catches her still
trading, so it detaches the behavior and announces, done for that tick. The
next tick finds her closed but not yet home, so it walks her one exit upstairs.
After that both conditions are cold and she sleeps for free, because the
attached behavior is the only state and it is already gone:

```text
@set Verity/close_down = '''
if 'shopkeeper' in behaviors(me):
    detach_behavior(me, 'shopkeeper')       # detaching the behavior shuts the stall
    say('Closing up. Come back at nine.')
elif name(here) != 'The Loft':
    move('upstairs')                        # next tick, climb home to the loft
'''
```

Attach the ticker so Verity runs on the world heartbeat:

```text
@behavior Verity = script_ticker, interval:1
```

Stock the stall from her inventory. The price the buyer pays is this `value`
times the markup, rounded:

```text
@create ration pack
@set ration pack/value = 8
give ration pack to Verity
```

## Try it

Give yourself coin and live a day beside her. With `interval:1` an hour passes
per world beat, and `@examine town clock` reports the current hour:

```text
@set me/credits = 40
list                     (before nine)
  There's no merchant here.
                         (at nine she walks down; on the next tick:)
  Verity says, "Shutters up! Fresh goods at fair prices!"
list
  ration pack, 10 credits           (value 8 times the 1.2 markup, rounded)
buy ration pack
  You buy ration pack for 10 credits.
                         (at hour 21:)
  Verity says, "Closing up. Come back at nine."
list                     (she has not even left the counter yet)
  There's no merchant here.
```

That last `list` is the point: the moment the behavior detaches, the room holds
no merchant, so the shop is shut before Verity takes a single step. Then she
climbs to the loft, and Market Street stands quiet until dawn.

## Going further

- **Lock up behind her:** in `close_down`, `cmd('close downstairs')` and set
  the exit's lock on the way out, then reopen it in `open_up` with
  `cmd('open downstairs')`, so knocking at midnight gets nowhere.
- **A longer commute:** put the loft across town and let `open_up` and
  `close_down` walk a route one exit per tick. The built-in
  [`patrol`](060_wandering_npc.md) behavior follows exactly this route-and-pause
  pattern, and townsfolk will pass Verity on her way to work.
- **Night-shift wanderer:** attach [tutorial 060](060_wandering_npc.md)'s
  `wandering` in `close_down` and detach it in `open_up`, giving a keeper who
  bar-crawls after close and still opens at nine sharp.
- **One clock, many lives:** the guard changes at the post, Mira calls last
  orders, and the scamp gets a curfew, all reading the same `town clock/hour`
  attribute you already built. [Tutorial 037](037_day_night_descs.md) hangs a
  plaza's darkness off the very same clock.
