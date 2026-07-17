# 128. Hydroponics Farming

> Checklist item 128 — [now] — *on_tick growth stages, stage-swapped descs*

**What you'll build:** A hydroponic tray you `plant` with a seed
packet, `water` on a schedule, and `harvest` three glowing
helio-tomatoes from — days later, in real time. Growth walks a
stage table on a ticker; let the nutrient gauge run dry and the crop
simply stops growing until someone tends it.

**Concepts:** **growth stages as a data table** (`[name, ticks,
visual]` rows), one `script_ticker` driving a persistent crop clock
(tickers survive reboots — a farm must), **stage visuals via
`desc_extras` swaps** (each transition stamps a new detail row, so
`look` always shows the crop's age), water as a consumed-per-tick
gauge that *pauses* growth at zero, and the plant/water/harvest verb
set with a numeric refusal each.

## How it works

**The tray owns the crop.** No plant object is spawned: `stage`,
`stage_left`, and `water` on the tray *are* the plant, which keeps
every verb and the ticker pointed at one thing. (`ON_LOAD`-style
per-plant objects work too, but a fixed planter is the honest smallest
version — and it means the builder can `@desc` the permanent tray
while the *changing* part rides in `desc_extras`.)

**The stage table is the genome.** `stages = [["germinating", 2,
"..."], ["flowering", 2, "..."], ["fruiting", 0, "..."]]` — name,
ticks to complete, and the sentence shown while it's current. The
ticker decrements `stage_left`; at zero it advances `stage`, loads the
next row's duration, and **swaps the detail row** —
`set_attr(me, 'desc_extras', [['', <visual>]])` replaces what `look`
appends, so the vat visibly ages. A new cultivar is a new table, no
script changes.

**Water gates the clock.** Each growth tick *spends* one water; at
zero the tray blinks a dry warning and the stage timer holds — neglect
never kills the crop, it just stops time for it (kinder, and simpler,
than wilt-and-die; see Going further for the cruel version). `water
tray` refills the gauge to 3. The `[[...]]` in the tray's `@desc`
reads the gauge live, so the description doubles as the farmer's
dashboard.

**Harvest resets to empty.** `$harvest` refuses until the final
stage (`Not yet -- the crop is still flowering.`), then mints the
produce into the room (`create_obj`, tagged `produce` — cooking-grade:
[129](129_cooking_buffs.md) consumes exactly that tag), clears every
crop attribute, and the tray idles dark until the next seed.

## Build it

The tray — permanent description by `@desc`, live gauge inline,
growth data as a table (interval 60 ≈ four minutes a tick at the
default heartbeat; a season is minutes, not months):

```text
@create hydro tray
drop hydro tray
@desc hydro tray = A chest-high hydroponic vat webbed with drip lines under grow-lamps. [[w = get_attr(me, 'water', 0); result = ('Nutrient gauge: ' + str(w) + '/3.') if has_attr(me, 'stage') else 'Its growth bed sits empty, lamps dimmed to standby.']]
@set hydro tray/stages = [["germinating", 2, "Pale threads spider through the growth foam."], ["flowering", 2, "White blossoms nod under the grow-lamps."], ["fruiting", 0, "Fat helio-tomatoes hang glowing faintly orange."]]
```

The verbs — plant (consumes a `seed`-tagged item), water, harvest:

```text
@set hydro tray/cmd_plant = $plant *: seeds = [o for o in contents(enactor) if has_tag(o, 'seed')]; pemit(enactor, 'The bed is already planted.') if has_attr(me, 'stage') else (pemit(enactor, 'You carry no seed stock.') if not seeds else (destroy_obj(seeds[0]), set_attr(me, 'stage', 0), set_attr(me, 'stage_left', get_attr(me, 'stages')[0][1]), set_attr(me, 'water', 2), set_attr(me, 'desc_extras', [['', get_attr(me, 'stages')[0][2]]]), remit(here, name(enactor) + ' beds a seed into the growth foam; the lamps hum up to full.')))
@set hydro tray/cmd_water = $water tray: pemit(enactor, 'Nothing is planted.') if not has_attr(me, 'stage') else (set_attr(me, 'water', 3), remit(here, 'Nutrient mist hisses through the drip lines.'))
@set hydro tray/cmd_harvest = $harvest *: s = get_attr(me, 'stage', None); st = get_attr(me, 'stages', []); ripe = s is not None and s >= len(st) - 1; pemit(enactor, 'Nothing is planted.') if s is None else None; pemit(enactor, 'Not yet -- the crop is still ' + st[s][0] + '.') if s is not None and not ripe else None; ([create_obj('a glowing helio-tomato', ['thing', 'produce'], here) for i in range(3)], del_attr(me, 'stage'), del_attr(me, 'stage_left'), del_attr(me, 'water'), del_attr(me, 'desc_extras'), remit(here, name(enactor) + ' gathers 3 glowing helio-tomatoes; the lamps dim to standby.')) if ripe else None
```

The clock — spend water, advance the stage, swap the visual:

```text
@set hydro tray/on_tick = s = get_attr(me, 'stage', None); st = get_attr(me, 'stages', []); w = get_attr(me, 'water', 0); ripe = s is not None and s >= len(st) - 1; go = s is not None and not ripe; (remit(here, 'The hydro tray blinks a dry amber warning.') if w < 1 else (set_attr(me, 'water', w - 1), (set_attr(me, 'stage_left', get_attr(me, 'stage_left', 1) - 1) if get_attr(me, 'stage_left', 1) > 1 else (set_attr(me, 'stage', s + 1), set_attr(me, 'stage_left', st[s + 1][1]), set_attr(me, 'desc_extras', [['', st[s + 1][2]]]), remit(here, 'In the hydro tray: ' + st[s + 1][2]))))) if go else None
@behavior hydro tray = script_ticker, interval:60
```

And seed stock:

```text
@create packet of helio-tomato seeds
@tag packet of helio-tomato seeds = seed
```

## Try it

```text
plant seeds
look hydro tray
```

(The packet is still in your builder's hands from `@create`; a farmer
would `get` it first.) The lamps hum up, the packet is gone, and the vat reads `Nutrient
gauge: 2/3. Pale threads spider through the growth foam.` Impatient
farmers force the clock: each `@tr hydro tray/on_tick` is one growth
tick. Two ticks in, the room hears `In the hydro tray: White blossoms
nod under the grow-lamps.` — and the gauge is empty, so the next tick
only blinks `a dry amber warning` and the blossoms hold. `water tray`,
two more ticks: `Fat helio-tomatoes hang glowing faintly orange.`
Trying early gets arithmetic-honest refusals (`Not yet -- the crop is
still flowering.`); `harvest crop` at fruiting drops three
`produce`-tagged helio-tomatoes on the deck and dims the lamps. The
[galley range](129_cooking_buffs.md) is their natural destination.

## Going further

- **Wilt stakes:** count consecutive dry ticks in a `parched` attr
  and, past 3, clear the bed with a compost message — neglect with
  teeth, one extra guard in `on_tick`.
- **Cultivar packets:** put a `stages` table *on the seed packet* and
  have `$plant` copy it onto the tray — one tray grows anything;
  packets become the content.
- **Fertilizer margins:** a `$fertilize` that rolls
  `margin_under` and adds `1 + margin // 3` extra fruit to the
  harvest count — [121's](121_gathering_nodes.md) yield arithmetic,
  transplanted.
- **A real greenhouse:** `@clone` trays down a bay and stagger
  plantings; the per-tray gauges in `look` make the rounds a job —
  the [NPC schedule](068_npc_schedule.md) can even staff it.
