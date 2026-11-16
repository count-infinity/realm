# 137. Hunger & Thirst

> Checklist item 137 ([now]): *survival meters, consumables that fill them, zone-policy toggle*

> **The engine does this.** Since 0.3.0 the `needs` feature (in `CLASSIC`)
> runs hunger, thirst and fatigue after CoffeeMud's
> ([Life and death](../guides/life-and-death.md#hunger-thirst-and-fatigue)).
> Under the Merc rules every character already has them. This build
> configures the feature for a station whose rules (here GURPS) do not:
> it gives the crew the pools, stocks the galley and sets the climate.

**What you'll build:** a mess deck with an enlistment terminal that signs a
crewman onto the station's survival rules, a ration pack eaten a bite at a
time, a water tap that never runs dry and a canteen to fill at it; a hot, dry
engine room that parches you three times as fast; and a crew lounge where
nobody gets hungry at all.

**Concepts:** a need is a **pool** (`food`, `water`), so a character has it
exactly when it has that pool, and the engine does the rest: it empties them
every few seconds, reminds, slows recovery and in the end kills. The terminal
writes another player's sheet, so it needs **owner authority** (an admin-owned
object, the [069](069_trainer_npc.md) rule). Food and drink are plain
attributes (`nourishment`, `bite`, `liquid_held`), the climate is room tags,
and the exemption is a **zone policy** (`no_needs` on a zone master).

## How it works

The finished shape is one terminal, three supplies and two tagged rooms. Nothing
ticks in softcode: the `needs` feature sweeps every online player who has the
pools. This section answers four questions: how a crewman comes to have
hunger, how the galley fills it, how a room changes it, and how a room
switches it off.

### How does a crewman come to have hunger?

The engine gives hunger and thirst to anyone with a `food` or `water` pool. A
Merc game declares both for every character; a GURPS station does not, so the
terminal's `$enlist` writes them onto the crewman: a `pools` attribute naming
`food` and `water` as pools that do not refill on their own (`regen: False`),
and each one full. From then on, every 4 seconds (`NEEDS_INTERVAL`) the
crewman loses 1 food and 1 water, and the prompt, the `score` sheet and
[`pool()`](../reference/softcode.md#fn-pool) all show it. Writing another
player's attributes needs control of them, which only an admin has, so the
terminal must be **admin-owned**: build it as your admin character.

### How does the galley fill it?

`eat` and `drink` already know food and drink. The ration pack is tagged
`food` with `nourishment` 300 and a `bite` of 100, so it takes three meals to
finish. The tap is tagged `drink` and `fountain`, so it never runs dry, and
each `drink` is a sip of 50. The canteen has `liquid_held` 300; `fill canteen`
at the tap fills it with whatever the tap's `liquid` is. A full stomach
refuses more.

### How does a room change it?

Thirst runs at the room's rate: 1, plus 1 for each `climate:hot`,
`climate:dry` and `climate:windy` tag, minus 1 for `climate:wet`. The engine
room is hot and dry, so a crewman working there dries out three times as
fast. Hunger ignores the climate. Walking costs a tick's worth of both.

### How does a room switch it off?

A zone whose master sets `no_needs` is exempt: nobody in its rooms loses
anything or counts toward starving. The lounge is that zone. (A character
tagged `no_needs`, and any administrator, is exempt everywhere.)

## Build it

As your admin character, dig the mess deck, the engine room (hot and dry) and
the crew lounge (its own zone, with a policy master that switches needs off):

```text
@dig The Mess Deck = mess, out
mess
@dig Engine Room = engine, mess
engine
@tag here = climate:hot
@tag here = climate:dry
mess
@dig Crew Lounge = lounge, mess
lounge
@zone here = lounge
@create lounge policy
@zone/master lounge policy = lounge
@set lounge policy/no_needs = 1
drop lounge policy
mess
```

The enlistment terminal gives whoever types `enlist` the two pools, full. A
`$`-command runs only on the terminal that matched the word, and `enactor` is
the crewman:

```text
@create enlistment terminal
drop enlistment terminal
@desc enlistment terminal = A crew terminal. ENLIST to sign the station's articles, meals and water included.
@set enlistment terminal/cmd_enlist = '''
$enlist:
set_attr(enactor, 'pools', {'food': {'regen': False}, 'water': {'regen': False}})
set_attr(enactor, 'max_food', 500)
set_attr(enactor, 'food', 500)
set_attr(enactor, 'max_water', 1000)
set_attr(enactor, 'water', 1000)
pemit(enactor, 'You sign the articles. The station will feed you; see that you eat.')
'''
```

Now the galley: a ration pack of three bites, a tap that never runs dry, and
an empty canteen:

```text
@create ration pack
@tag ration pack = food
@set ration pack/nourishment = 300
@set ration pack/bite = 100
drop ration pack
@create water tap
@tag water tap = drink
@tag water tap = fountain
@tag water tap = fixed
@set water tap/liquid = recycled water
drop water tap
@create canteen
@tag canteen = drink
@set canteen/liquid_held = 300
@set canteen/liquid_remaining = 0
drop canteen
```

## Try it

Sign on at the mess deck:

```text
enlist             -> You sign the articles. The station will feed you; see that you eat.
prompt <{food} food {water} water>
```

Your prompt now reads `<500 food 1000 water>`, and every 4 seconds both drop
by one. About half an hour later the food
runs out, and the reminders begin (every 60 ticks, sharper as the hours pass):

```text
                   -> You are hungry.
get ration pack
eat ration         -> You take a bite of a ration pack.
                      You are no longer hungry.
drink tap          -> You drink recycled water from a water tap.
get canteen
fill canteen       -> You fill a canteen from a water tap.
```

While a meter is empty you recover hit points at half speed; empty both and you
recover nothing. Twelve hours online without food (six without water) and you
die of it, through the ordinary death path. Walk into the engine room and your
water drains three times as fast. Walk into the lounge and both meters stop.

## Going further

- **A penalty you can feel:** read [`hungry()`](../reference/softcode.md#fn-hungry)
  in an `on_check` or a skill-check modifier to make the starving clumsy, the
  [135](135_injury_treatment.md) injury pattern.
- **Fatigue:** a third pool, `fatigue` (an up pool), rises while awake and
  falls asleep; spent, it halves mana and movement recovery. Add it in the
  terminal's `pools` with `{'direction': 'up', 'regen': False}` and a
  `max_fatigue`.
- **A restocking galley:** sell ration packs from a
  [063](063_shopkeeper.md) shopkeeper with a `restock` behavior, so the mess
  never runs out.
- **The rules in Python:** a game's `rules.py` can declare `food` and `water`
  in its own `pools()` (as Merc does), so every character has them from
  creation and the terminal is not needed.
