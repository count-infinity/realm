# 128. Hydroponics Farming

> Checklist item 128 ([now]): *on_tick growth stages, stage-swapped descs*

**What you'll build:** A hydroponic tray you `plant` with a seed packet, `water`
on a schedule, and `harvest` for three glowing helio-tomatoes once the crop has
grown, days later in real time. Growth walks a stage table on a ticker, and if
the nutrient gauge runs dry the crop simply stops growing until someone tends
it.

**Concepts:** growth stages as a data table (`[name, ticks, visual]` rows), one
[`script_ticker`](006_flashlight.md) driving a persistent crop clock so the farm
survives reboots, stage visuals swapped through `desc_extras` so `look` always
shows the crop's age, water as a per-tick gauge that pauses growth at zero, and
a plant/water/harvest verb set with a numeric refusal for each.

## How it works

The finished build is a single fixed tray that holds a crop through three
growth stages and mints produce when you harvest it. No separate plant object
is ever spawned: the crop lives entirely as attributes on the tray, a ticker
advances it while its water lasts, and each stage change rewrites what `look`
appends. This section answers four questions: where the crop lives, what the
stage table holds, how water gates the clock, and what harvest does.

### Where does the crop live?

The tray owns the crop. `stage`, `stage_left`, and `water` on the tray are the
plant, which keeps every verb and the ticker pointed at one object. A per-plant
object spawned on planting would work too, but a fixed planter is the smallest
honest version, and it lets you `@desc` the permanent tray while the changing
part rides in `desc_extras`.

### What does the stage table hold?

The `stages` attribute is a list of `[name, ticks, visual]` rows: the stage
name, how many ticks it takes to complete, and the sentence shown while it is
current. The ticker decrements `stage_left`, and at zero it advances `stage`,
loads the next row's duration, and swaps the detail row. Writing
[`set_attr`](../reference/softcode.md#fn-set_attr)`(me, 'desc_extras', [['',
<visual>]])` replaces what `look` appends, so the vat visibly ages. The empty
first element is the display condition, and an empty condition shows to every
looker, so a new cultivar is a new table with no script changes.

### How does water gate the clock?

Each growth tick spends one water. At zero the tray shows a dry warning and the
stage timer holds, so neglect never kills the crop, it only stops time for it.
That is kinder and simpler than wilt-and-die (see Going further for the cruel
version). `water tray` refills the gauge to 3. The
[`[[...]]`](../reference/softcode.md#fn-v) block in the tray's `@desc` reads the
gauge live, so the description doubles as the farmer's dashboard.

### What does harvest do?

`$harvest` refuses until the final stage, quoting which stage is current (`Not
yet -- the crop is still flowering.`), then mints the produce into the room with
[`create_obj`](../reference/softcode.md#fn-create_obj) tagged `produce`, clears
every crop attribute, and the tray idles dark until the next seed. The
`produce` tag is the coupling the [galley range](129_cooking_buffs.md) keys on:
it consumes exactly that tag.

## Build it

First the tray. `@desc` gives it a permanent body with the live gauge inline,
and `stages` holds the growth data. Interval 60 is about four minutes a tick at
the default heartbeat, so a season here is minutes, not months:

```text
@create hydro tray
drop hydro tray
@desc hydro tray = A chest-high hydroponic vat webbed with drip lines under grow-lamps. [[w = V('water', 0); result = ('Nutrient gauge: ' + str(w) + '/3.') if has_attr(me, 'stage') else 'Its growth bed sits empty, lamps dimmed to standby.']]
@set hydro tray/stages = [["germinating", 2, "Pale threads spider through the growth foam."], ["flowering", 2, "White blossoms nod under the grow-lamps."], ["fruiting", 0, "Fat helio-tomatoes hang glowing faintly orange."]]
```

The `plant` verb reads the builder's inventory for a `seed`-tagged item, refuses
if the bed is already planted or no seed is carried, and otherwise consumes the
seed, seeds every crop attribute from the first stage row, and announces:

```text
@set hydro tray/cmd_plant = '''
$plant *:
seeds = [o for o in contents(enactor) if has_tag(o, 'seed')]
if has_attr(me, 'stage'):
    pemit(enactor, 'The bed is already planted.')
elif not seeds:
    pemit(enactor, 'You carry no seed stock.')
else:
    st = V('stages')
    destroy_obj(seeds[0])
    set_attr(me, 'stage', 0)
    set_attr(me, 'stage_left', st[0][1])
    set_attr(me, 'water', 2)
    set_attr(me, 'desc_extras', [['', st[0][2]]])  # empty condition shows to every looker
    remit(here, name(enactor) + ' beds a seed into the growth foam; the lamps hum up to full.')
'''
```

The `water` verb refuses when nothing is planted, and otherwise refills the
gauge to 3:

```text
@set hydro tray/cmd_water = '''
$water tray:
if not has_attr(me, 'stage'):
    pemit(enactor, 'Nothing is planted.')
else:
    set_attr(me, 'water', 3)
    remit(here, 'Nutrient mist hisses through the drip lines.')
'''
```

The `harvest` verb reads the current stage, refuses cleanly when the bed is
empty or the crop is not yet at its final stage, and otherwise mints three
produce, clears the crop, and dims the lamps:

```text
@set hydro tray/cmd_harvest = '''
$harvest *:
s = V('stage', None)
st = V('stages', [])
if s is None:
    pemit(enactor, 'Nothing is planted.')
elif s < len(st) - 1:
    pemit(enactor, 'Not yet -- the crop is still ' + st[s][0] + '.')
else:
    for i in range(3):
        create_obj('a glowing helio-tomato', ['thing', 'produce'], here)
    del_attr(me, 'stage')
    del_attr(me, 'stage_left')
    del_attr(me, 'water')
    del_attr(me, 'desc_extras')
    remit(here, name(enactor) + ' gathers 3 glowing helio-tomatoes; the lamps dim to standby.')
'''
```

The clock spends one water per beat, holds the timer when the gauge is dry, and
at the end of a stage advances `stage`, loads the next row's duration, and swaps
the visual. It runs only while a crop is growing, so a bare bed and a ripe crop
both leave it idle:

```text
@set hydro tray/on_tick = '''
s = V('stage', None)
st = V('stages', [])
if s is not None and s < len(st) - 1:  # growing: not empty, not yet ripe
    if V('water', 0) < 1:
        remit(here, 'The hydro tray blinks a dry amber warning.')
    else:
        decr('water')  # each growth tick spends one water
        if V('stage_left', 1) > 1:
            decr('stage_left')
        else:
            incr('stage')
            set_attr(me, 'stage_left', st[s + 1][1])  # load the next stage's duration
            set_attr(me, 'desc_extras', [['', st[s + 1][2]]])  # swap what look appends
            remit(here, 'In the hydro tray: ' + st[s + 1][2])
'''
@behavior hydro tray = script_ticker, interval:60
```

Finally the seed stock, a `seed`-tagged packet the `plant` verb consumes:

```text
@create packet of helio-tomato seeds
@tag packet of helio-tomato seeds = seed
```

## Try it

```text
plant seeds
look hydro tray
```

The packet is still in your builder's hands from `@create`, so a farmer would
`get` it first. The lamps hum up, the packet is gone, and the vat reads
`Nutrient gauge: 2/3. Pale threads spider through the growth foam.` Impatient
farmers force the clock, since each `@tr hydro tray/on_tick` is one growth tick
(the ticker runs `on_tick` as bare code, so `@tr` drives it directly). Two ticks
in, the room hears `In the hydro tray: White blossoms nod under the grow-lamps.`
and the gauge is empty, so the next tick only blinks `a dry amber warning` and
the blossoms hold:

```text
harvest crop
@tr hydro tray/on_tick
@tr hydro tray/on_tick
@tr hydro tray/on_tick
water tray
```

Trying to harvest early gets a numeric refusal (`Not yet -- the crop is still
flowering.`). After `water tray` and two more ticks the crop reads `Fat
helio-tomatoes hang glowing faintly orange.`, and `harvest crop` at fruiting
drops three `produce`-tagged helio-tomatoes on the deck and dims the lamps. The
[galley range](129_cooking_buffs.md) is their natural destination.

## Going further

- **Wilt stakes:** count consecutive dry ticks in a `parched` attribute and,
  past 3, clear the bed with a compost message, which is neglect with teeth and
  one extra guard in `on_tick`.
- **Cultivar packets:** put a `stages` table on the seed packet and have
  `$plant` copy it onto the tray, so one tray grows anything and the packets
  become the content.
- **Fertilizer margins:** a `$fertilize` that rolls `margin_under` and adds `1 +
  margin // 3` extra fruit to the harvest count, which is
  [121's](121_gathering_nodes.md) yield arithmetic transplanted.
- **A real greenhouse:** `@clone` trays down a bay and stagger plantings. The
  per-tray gauges in `look` make the rounds a job, and the
  [NPC schedule](068_npc_schedule.md) can even staff it.
