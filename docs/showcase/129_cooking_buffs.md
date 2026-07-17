# 129. Cooking with Buffs

> Checklist item 129 — [now] — *modifier_effect consumables, decay spoilage*

**What you'll build:** A galley range that turns two
[helio-tomatoes](128_farming.md) into a bowl of ember-root stew.
Eating it grants a real, engine-tracked buff — `+3 throwing` for ten
beats, visible to every skill check — and a bowl left out too long
goes rank and pays you back with food poisoning instead.

**Concepts:** the engine's **effect machinery as the buff system**
(`apply_effect('modifier_effect', kind=..., check_mods=...)` — the
buff *tags* its owner, folds into every `check()` automatically,
persists across reboots, and expires on its own), **kind-tags**
(`has_tag(x, 'hearty')` is readable by locks and softcode while the
buff runs), meal data riding on a spawned object while the *scripts*
are stamped on it by the range, and spoilage as
[018's](018_refrigerator.md) freshness ticker ending in a
`damage_over_time` instead of mush.

## How it works

**Buffs are `check_mods`, not attribute edits.** The wrong way to
give +3 throwing is `set_attr(player, 'skill_throwing', 12)` — it
desyncs the sheet and never expires. The engine way is
`apply_effect(target, 'modifier_effect', kind='hearty', duration=10,
check_mods={'throwing': 3})`: the modifier lives exactly as long as
the effect, every `skill_check()` anywhere folds it in without being
asked, and the `hearty` tag rides along for flavor text and locks.
(This *used* to have an honest limit: softcode that re-rolled dice by
hand with `margin_under(roll(...), attr)` — like the
[lathe](125_quality_tiers.md) — bypassed `check()` and missed these
modifiers. `check_roll(obj, skill)` closes it: it returns the graded
`CheckResult` *through* the real pipeline, so a `check_mods` buff
reaches a crafting roll too. Reach for `check_roll` when a graded roll
must honour conditions; `margin_under` stays the tool for a raw,
unmodified roll.)

**The meal is data; the range is the chef.** `$cook stew` burns two
`produce`-tagged items and mints the bowl, then stamps everything
onto it: the buff spec as a `buff` dict, a `freshness` gauge, the
`$eat` script, the spoilage `on_tick`, and a `script_ticker` — all
with `set_attr`/`attach_behavior`, legal because the range owns what
it creates. The master copies of both scripts live on the range
(`eat_code`, `spoil_code`), so tuning the cuisine is editing one
object.

**Eating needs a table.** Effects use proximity authority — a script
may buff someone *in its room*. A bowl in your hands is inside *you*,
not in the room, so the `$eat` script's first guard asks you to set
it down; on the floor (or a counter), meal and eater share a room and
`apply_effect` reaches. The spoiled branch is the same reach with the
sign flipped: eating a rank bowl applies `food_poisoning`
damage-over-time — the [dart trap](052_poison_dart_trap.md)'s venom
in a dish.

**Spoilage pauses in the cold.** The freshness tick subtracts the
*holder's* published `decay_rate` (default 1), so 018's icebox slows
a stew to quarter speed with zero coupling. A spoiled bowl isn't
destroyed — it grows a `spoiled` tag and waits for someone hungry
enough.

## Build it

The range, its master scripts, and one recipe:

```text
@create galley range
drop galley range
@desc galley range = A blackened four-ring galley range. The menu card wedged over the ignition reads: STEW.
@set galley range/cook_stew = {"name": "a bowl of ember-root stew", "needs": {"produce": 2}, "buff_kind": "hearty", "buff_skill": "throwing", "buff_mod": 3, "buff_beats": 10, "fresh": 4}
@set galley range/eat_code = $eat *: b = V('buff'); pemit(enactor, 'Both hands and a flat spot: set ' + name(me) + ' down somewhere first.') if loc(me) == enactor else ((pemit(enactor, 'One sniff says no -- but hunger wins. It has gone rank.'), apply_effect(enactor, 'damage_over_time', kind='food_poisoning', damage=1, interval=1, duration=3, tick_msg='Your stomach knots and cramps.', expire_msg='Your stomach finally settles.'), destroy_obj(me)) if has_tag(me, 'spoiled') else (apply_effect(enactor, 'modifier_effect', kind=b['kind'], duration=b['beats'], check_mods={b['skill']: b['mod']}, apply_msg='Warmth spreads from your belly: ' + b['kind'] + ' (+' + str(b['mod']) + ' ' + b['skill'] + ' while it lasts).', expire_msg='The warm, well-fed feeling fades.'), remit(here, name(enactor) + ' scrapes the bowl clean.'), destroy_obj(me)))
@set galley range/spoil_code = sp = has_tag(me, 'spoiled'); f = V('freshness', 4) - get_attr(loc(me), 'decay_rate', 1); (set_attr(me, 'freshness', f), (add_tag(me, 'spoiled'), remit(here, ucfirst(name(me)) + ' films over and goes rank.')) if f <= 0 else None) if not sp else None
@set galley range/cmd_cook = $cook *: sel = trim(arg0).lower(); r = V('cook_' + sel); carried = contents(enactor) if r else []; short = [str(n - len([o for o in carried if has_tag(o, t)])) + 'x ' + t for t, n in (r['needs'].items() if r else []) if len([o for o in carried if has_tag(o, t)]) < n]; pemit(enactor, 'The menu card lists no such dish.') if not r else None; pemit(enactor, 'Short of fixings: ' + ', '.join(short) + '.') if r and short else None; ([destroy_obj(o) for t, n in r['needs'].items() for o in [x for x in carried if has_tag(x, t)][:n]], [(set_attr(m, 'buff', {'kind': r['buff_kind'], 'skill': r['buff_skill'], 'mod': r['buff_mod'], 'beats': r['buff_beats']}), set_attr(m, 'freshness', r['fresh']), set_attr(m, 'cmd_eat', V('eat_code')), set_attr(m, 'on_tick', V('spoil_code')), attach_behavior(m, 'script_ticker', interval=45), set_attr(m, 'desc_extras', [['', 'Chunks of ember-root in a pepper-dark broth, still steaming.']]), remit(here, 'The range flares; ' + r['name'] + ' ladles out onto the counter.')) for m in [create_obj(r['name'], ['thing', 'meal'], here)]]) if r and not short else None
```

Something to feel the buff on — a knife board that rolls `throwing`
through the real check pipeline (that's what the buff hooks):

```text
@create knife board
drop knife board
@desc knife board = A scarred target board bolted by the galley door, one painted ring, many old knife scars. THROW KNIFE at it.
@set knife board/cmd_throw = $throw knife: hit = skill_check(enactor, 'throwing'); remit(here, name(enactor) + (' snaps a knife dead into the painted ring. THOCK.' if hit else ' throws wide; the knife skitters off the plating.'))
```

## Try it

With two `produce`-tagged tomatoes in your pack and a mediocre arm:

```text
@set me/skill_throwing = 9
throw knife
cook stew
eat stew
throw knife
```

Cold: some throws skitter — 9 misses a lot. `cook stew` burns the
tomatoes and ladles the bowl onto the counter (it spawns *in the
room* — already set down, ready to eat). `eat stew`: `Warmth spreads
from your belly: hearty (+3 throwing while it lasts).` — and now you
throw at an effective 12. While it runs, `@examine me` shows the
`hearty` tag and a `check_mods` entry; ten beats later `The warm,
well-fed feeling fades.` and both vanish. If you `get` a bowl and try
to eat from your hands, the guard explains itself: `Both hands and a
flat spot: set a bowl of ember-root stew down somewhere first.`

For the dark side: cook another bowl and let it sit four ticker beats
(`@tr` its `on_tick` to hurry) — `A bowl of ember-root stew films
over and goes rank.` Eating it now knots your stomach for three beats
of damage. An [icebox](018_refrigerator.md) with `decay_rate 0.25`
keeps the galley's output honest overnight.

## Going further

- **A menu, not a dish:** every `cook_<dish>` attr is a new recipe —
  regen chowder (`apply_effect(..., 'regeneration', heal=1)`),
  liquid courage (`check_mods={'all': 1}` — the everything-buff), a
  captain's feast with two effects.
- **Stacking policy:** one `hearty` at a time is the engine default
  (same kind re-tags, doesn't stack); gate `$eat` on
  `has_tag(enactor, 'hearty')` for an explicit `You are already well
  fed.`
- **Buffed crafting:** fold the eater's `check_mods` into a
  hand-rolled craft: read the dict, `sum(v.get('all', 0) +
  v.get('smithing', 0) for v in mods.values())`, add it to the
  [lathe](125_quality_tiers.md)'s target.
- **Chef margins:** roll cooking on the `$cook` and let the margin
  set `buff_mod` or `fresh` — [125's](125_quality_tiers.md) tiers,
  plated.
