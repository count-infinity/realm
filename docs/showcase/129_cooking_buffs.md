# 129. Cooking with Buffs

> Checklist item 129 ([now]): *modifier_effect consumables, decay spoilage*

**What you'll build:** A galley range that turns two
[helio-tomatoes](128_farming.md) into a bowl of ember-root stew. Eating
it grants a real, engine-tracked buff (`+3 throwing` for ten beats,
visible to every skill check), while a bowl left out too long goes rank
and pays the eater back with food poisoning.

**Concepts:** the engine's effect machinery used as the buff system,
where [`apply_effect`](../reference/softcode.md#fn-apply_effect) with a
`modifier_effect` tags its owner, folds into every
[`skill_check`](../reference/softcode.md#fn-skill_check) automatically,
persists across reboots, and expires on its own; kind-tags, so
[`has_tag`](../reference/softcode.md#fn-has_tag)`(x, 'hearty')` is
readable by locks and softcode while the buff runs; meal data riding on a
spawned object with the scripts stamped onto it by the range; and
spoilage as [018](018_refrigerator.md)'s freshness ticker ending in a
`damage_over_time` instead of mush.

## How it works

The finished build is a range that mints a bowl, stamps a small program
and a freshness clock onto it, and walks away. Eating the bowl reaches
back through the engine's effect machinery to buff (or poison) whoever
ate it, and the buff then rides along on its own until it expires. This
section answers four questions: why a buff is a check modifier rather
than a sheet edit, how the range gets its programs onto a bowl it just
created, why the bowl asks to be set down before you eat, and how the
cold slows spoilage.

**Buffs are check modifiers, not attribute edits.** The wrong way to
give `+3 throwing` is `set_attr(player, 'skill_throwing', 12)`, which
desyncs the sheet and never expires. The engine way is
[`apply_effect`](../reference/softcode.md#fn-apply_effect)`(target,
'modifier_effect', kind='hearty', duration=10, check_mods={'throwing':
3})`: the modifier lives exactly as long as the effect, every
[`skill_check`](../reference/softcode.md#fn-skill_check) anywhere folds
it in without being asked, and the `hearty` tag rides along for flavor
text and locks. Because the effect serializes with its owner, the buff
survives a reboot with its remaining beats intact.

**The meal is data; the range is the chef.** `$cook stew` burns two
`produce`-tagged items and mints the bowl with
[`create_obj`](../reference/softcode.md#fn-create_obj), then stamps
everything onto it: the buff spec as a `buff` dict, a `freshness` gauge,
the `$eat` script, the spoilage `on_tick`, and a `script_ticker`, all
with [`set_attr`](../reference/softcode.md#fn-set_attr) and
[`attach_behavior`](../reference/softcode.md#fn-attach_behavior). This is
legal because the range owns what it creates. The master copies of both
scripts live on the range (`eat_code`, `spoil_code`), so tuning the
cuisine is editing one object.

**Why eating asks you to set the bowl down.** The `$eat` script runs as
the bowl, and effects reach through proximity, so
[`apply_effect`](../reference/softcode.md#fn-apply_effect) can buff
anyone the bowl can reach. That reach includes the bowl's own carrier (a
held object may act on whoever holds it), which means a bowl in your
hands could buff you directly. This build refuses it anyway for flavor:
the first guard is `loc(me) is enactor` (an identity check, so it is
`is`, not `==`), true only while the bowl sits inside you rather than on
a surface, and it asks you to set the bowl down first. The spoiled branch
is the same reach with the sign flipped, since eating a rank bowl applies
a `food_poisoning` `damage_over_time`, the [dart
trap](052_poison_dart_trap.md)'s venom served in a dish.

**Spoilage pauses in the cold.** The freshness tick subtracts the
holder's published `decay_rate` (default 1), read fresh each beat with
[`get_attr`](../reference/softcode.md#fn-get_attr)`(loc(me),
'decay_rate', 1)`, so [018](018_refrigerator.md)'s icebox slows a stew to
quarter speed with no coupling between them. A spoiled bowl is not
destroyed: it grows a `spoiled` tag and waits for someone hungry enough.

## Build it

Create the range, drop it so it shares a room with whoever cooks, and
give it a menu card:

```text
@create galley range
drop galley range
@desc galley range = A blackened four-ring galley range. The menu card wedged over the ignition reads: STEW.
```

One recipe as a dict: the meal name, the fixings it needs by tag, the
buff it confers, and how many freshness ticks a fresh bowl keeps.

```text
@set galley range/cook_stew = {"name": "a bowl of ember-root stew", "needs": {"produce": 2}, "buff_kind": "hearty", "buff_skill": "throwing", "buff_mod": 3, "buff_beats": 10, "fresh": 4}
```

The `eat_code` template is the program each bowl will carry as its `$eat`
command. It runs as the bowl: the guard first (still in your hands, so
set it down), then the spoiled branch (food poisoning), then the good
branch, which applies the buff, announces the meal with
[`remit`](../reference/softcode.md#fn-remit), and consumes the bowl with
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj).

```text
@set galley range/eat_code = '''
$eat *:
b = V('buff')
if loc(me) is enactor:  # the bowl is inside you, not sitting on a surface
    pemit(enactor, 'Both hands and a flat spot: set ' + name(me) + ' down somewhere first.')
elif has_tag(me, 'spoiled'):
    pemit(enactor, 'One sniff says no -- but hunger wins. It has gone rank.')
    apply_effect(enactor, 'damage_over_time', kind='food_poisoning', damage=1, interval=1, duration=3, tick_msg='Your stomach knots and cramps.', expire_msg='Your stomach finally settles.')
    destroy_obj(me)
else:
    apply_effect(enactor, 'modifier_effect', kind=b['kind'], duration=b['beats'], check_mods={b['skill']: b['mod']}, apply_msg='Warmth spreads from your belly: ' + b['kind'] + ' (+' + str(b['mod']) + ' ' + b['skill'] + ' while it lasts).', expire_msg='The warm, well-fed feeling fades.')
    remit(here, name(enactor) + ' scrapes the bowl clean.')
    destroy_obj(me)
'''
```

The `spoil_code` template is each bowl's `on_tick`. While the bowl is
still fresh it burns freshness down by its holder's `decay_rate`, and at
zero it tags itself `spoiled` and announces the turn.

```text
@set galley range/spoil_code = '''
if not has_tag(me, 'spoiled'):
    f = V('freshness', 4) - get_attr(loc(me), 'decay_rate', 1)
    set_attr(me, 'freshness', f)
    if f <= 0:
        add_tag(me, 'spoiled')
        remit(here, ucfirst(name(me)) + ' films over and goes rank.')
'''
```

The `$cook` command reads the recipe, counts your carried fixings by tag
with [`contents`](../reference/softcode.md#fn-contents), and either
refuses (no such dish, short of fixings) or burns the fixings and mints
the bowl, stamping the buff spec, freshness, and both scripts onto it
before starting its ticker.

```text
@set galley range/cmd_cook = '''
$cook *:
sel = trim(arg0).lower()
r = V('cook_' + sel)
if not r:
    pemit(enactor, 'The menu card lists no such dish.')
else:
    carried = contents(enactor)
    short = [str(n - len([o for o in carried if has_tag(o, t)])) + 'x ' + t for t, n in r['needs'].items() if len([o for o in carried if has_tag(o, t)]) < n]
    if short:
        pemit(enactor, 'Short of fixings: ' + ', '.join(short) + '.')
    else:
        for t, n in r['needs'].items():
            for o in [x for x in carried if has_tag(x, t)][:n]:
                destroy_obj(o)
        m = create_obj(r['name'], ['thing', 'meal'], here)  # spawns in the room, already set down
        set_attr(m, 'buff', {'kind': r['buff_kind'], 'skill': r['buff_skill'], 'mod': r['buff_mod'], 'beats': r['buff_beats']})
        set_attr(m, 'freshness', r['fresh'])
        set_attr(m, 'cmd_eat', V('eat_code'))
        set_attr(m, 'on_tick', V('spoil_code'))
        attach_behavior(m, 'script_ticker', interval=45)
        set_attr(m, 'desc_extras', [['', 'Chunks of ember-root in a pepper-dark broth, still steaming.']])
        remit(here, 'The range flares; ' + r['name'] + ' ladles out onto the counter.')
'''
```

Something to feel the buff on: a knife board bolted by the door.

```text
@create knife board
drop knife board
@desc knife board = A scarred target board bolted by the galley door, one painted ring, many old knife scars. THROW KNIFE at it.
```

The throw is a plain
[`skill_check`](../reference/softcode.md#fn-skill_check), which routes
through the real check pipeline, so any active `check_mods` buff is
folded in without the board knowing about it.

```text
@set knife board/cmd_throw = '''
$throw knife:
hit = skill_check(enactor, 'throwing')
remit(here, name(enactor) + (' snaps a knife dead into the painted ring. THOCK.' if hit else ' throws wide; the knife skitters off the plating.'))
'''
```

## Try it

With two `produce`-tagged tomatoes in your pack and a mediocre arm
(`@set me/skill_throwing = 9`), cook a bowl and feel the difference:

```text
> throw knife
Bilda throws wide; the knife skitters off the plating.

> cook stew
The range flares; a bowl of ember-root stew ladles out onto the counter.

> eat stew
Warmth spreads from your belly: hearty (+3 throwing while it lasts).
Bilda scrapes the bowl clean.

> throw knife
Bilda snaps a knife dead into the painted ring. THOCK.
```

A cold arm of 9 misses a lot. `cook stew` burns the tomatoes and ladles
the bowl onto the counter, spawned in the room and already set down, so
eating just works. After the buff lands you throw at an effective 12.
While it runs, `@examine me` shows the `hearty` tag and a `check_mods`
entry, and ten beats later `The warm, well-fed feeling fades.` clears
both. Pick a bowl up first and the guard explains itself:

```text
> get bowl of ember-root stew
> eat stew
Both hands and a flat spot: set a bowl of ember-root stew down somewhere first.
```

For the dark side, cook another bowl and let it sit four ticker beats,
firing its `on_tick` with `@tr` to hurry the clock:

```text
> @tr a bowl of ember-root stew/on_tick
> @tr a bowl of ember-root stew/on_tick
> @tr a bowl of ember-root stew/on_tick
> @tr a bowl of ember-root stew/on_tick
A bowl of ember-root stew films over and goes rank.

> eat stew
One sniff says no -- but hunger wins. It has gone rank.
Your stomach knots and cramps.
```

Eating it now applies `food_poisoning` for three beats of damage. An
[icebox](018_refrigerator.md) that publishes `decay_rate 0.25` keeps the
galley's output honest overnight.

## Going further

- **A menu, not a dish:** every `cook_<dish>` attr is a new recipe, so
  add regen chowder (`apply_effect(..., 'regeneration', heal=1)`), liquid
  courage (`check_mods={'all': 1}`, the everything-buff), or a captain's
  feast that applies two effects.
- **Stacking policy:** `apply_effect` refreshes by `kind`, since an
  effect's state is keyed by its kind, so re-applying `hearty` replaces
  the old one (renewed duration, latest `check_mods`) rather than
  stacking a second copy. Eating twice keeps a single, freshly topped-up
  buff. To refuse the second helping, gate `$eat` on `has_tag(enactor,
  'hearty')` for an explicit `You are already well fed.`
- **Buffed crafting:** fold the eater's `check_mods` into a hand-rolled
  craft by reading the dict and summing the relevant entries, or reach
  for [`check_roll`](../reference/softcode.md#fn-check_roll) on the
  [lathe](125_quality_tiers.md), which grades through the same pipeline
  and honors the buff for you.
- **Chef margins:** roll cooking on the `$cook` and let the margin set
  `buff_mod` or `fresh`, which is [125](125_quality_tiers.md)'s quality
  tiers, plated.
