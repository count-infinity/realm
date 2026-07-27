# 136. Encumbrance Effects

> Checklist item 136 ([now]): *weight as convention, GURPS Basic Lift math, a modifier_effect that scales with load*

**What you'll build:** a cargo scale you step onto that weighs everything
you carry, works out your GURPS encumbrance level from your Strength, and
stamps the matching **penalty** onto you as a live condition. A light load
costs nothing; an overloaded one is a -3 to your rolls with your Move cut to
a crawl. Drop weight and step on again, and the penalty recomputes.

**Concepts:** weight as an attribute convention, GURPS Basic Lift and
encumbrance math done in softcode, and a computed
[`modifier_effect`](../reference/softcode.md#fn-apply_effect) applied fresh
each check, so "how much you are carrying" becomes "how badly you roll."

## How it works

The finished system is one object with one command. You step onto a scale,
type `heft`, and it reads your Strength and the weight of everything in your
hands, decides which of the five GURPS encumbrance bands you are in, and
either clears your encumbrance condition or replaces it with one whose
penalty matches the band. This section answers three questions: where the
rule lives, how the penalty is stored and how it reaches your rolls, and how
the scale reaches you at all.

**No engine cares what you weigh, so you write the rule.** REALM ships no
capacity system on purpose (the audit calls this out: weight is a
convention, gated where it matters). An item's `weight` is just a number, as
in [035](035_crawlspace.md); the scale is the thing that *cares*, and it
defines encumbrance locally. That means the math is yours to set, and here
we use GURPS 4e's:

- **Basic Lift** (the most you heft one-handed for a second) is
  `BL = ST × ST / 5` pounds. ST 10 gives BL 20; ST 14 gives BL 39.
- **Encumbrance level** is where your carried weight falls against BL:

  | Level | Carrying up to | DX & roll penalty | Move multiplier |
  |---|---|---|---|
  | None | BL | 0 | ×1 (full) |
  | Light | 2 × BL | -1 | ×0.8 |
  | Medium | 3 × BL | -2 | ×0.6 |
  | Heavy | 6 × BL | -3 | ×0.4 |
  | X-Heavy | 10 × BL | -4 | ×0.2 |

- **Move** is your Basic Move stepped down by that multiplier. We compute it
  as `Move × (5 − level) / 5`, which lands on the GURPS values closely enough
  for play (level 1 gives ×0.8, level 4 gives ×0.2) and keeps the arithmetic
  simple.

**The penalty is a recomputed condition.** Each time you are weighed the
scale calls [`remove_effect`](../reference/softcode.md#fn-remove_effect) on
the old encumbrance and, if you are over BL,
[`apply_effect`](../reference/softcode.md#fn-apply_effect) fits a fresh
`modifier_effect` carrying `check_mods={'all': -level}`. Applying a
`modifier_effect` writes that dict into your `db.check_mods` under its
`kind`, and stripping it removes exactly that entry, so the condition lives
precisely as long as the effect. Because
[`skill_check()`](../reference/softcode.md#fn-skill_check) folds `check_mods`
into every roll (the same plumbing as [135](135_injury_treatment.md)), being
overloaded drags down *every* roll until you shed weight and re-weigh.
`duration=0` makes the effect permanent, since a zero duration is never
counted down: it lasts until the next weighing replaces it, not until a clock
runs out.

**How the scale reaches you.** `apply_effect` and `remove_effect` run under
proximity authority, the [059](059_tranquilizer.md) rule: they reach whatever
shares the object's room. The scale is bolted to the deck, so once you stand
on its square you share its room and it stamps the condition onto you. A held
version would reach its carrier just as well, which is what the hands-free
`on_get`/`on_drop` upgrade in "Going further" relies on; the floor scale is
simply the version you step onto. Because `heft` is a `$`-command, it runs
only on the scale that matched the word, so it needs no `target` guard the way
a room-wide `ON_<EVENT>` hook would.

## Build it

First dig the dock, walk in, and build the scale itself: create it, drop it
so it stands on the deck rather than in your hands, and describe it with the
`heft` command spelled out for players.

```text
@dig The Loading Dock = dock, out
dock
@create cargo scale
drop cargo scale
@desc cargo scale = A battered freight scale bolted to the deck. STEP ON THE SCALE (command: HEFT) to gauge your load.
```

Now wire the command. It reads your Strength with
[`get_attr`](../reference/softcode.md#fn-get_attr), sums the `weight` of your
[`contents`](../reference/softcode.md#fn-contents), picks the encumbrance
level with a plain `if`/`elif` ladder against the GURPS thresholds, computes
your reduced Move, then clears any old penalty and, when you are over BL, fits
a new one sized to the level before reporting the result with
[`pemit`](../reference/softcode.md#fn-pemit):

```text
@set cargo scale/cmd_heft = '''
$heft:
st = int(get_attr(enactor, 'strength', 10))
bl = st * st // 5
load = sum(int(get_attr(o, 'weight', 0)) for o in contents(enactor))
if load <= bl:
    lvl = 0
elif load <= 2 * bl:
    lvl = 1
elif load <= 3 * bl:
    lvl = 2
elif load <= 6 * bl:
    lvl = 3
else:
    lvl = 4
names = ['None', 'Light', 'Medium', 'Heavy', 'X-Heavy']
move = int(get_attr(enactor, 'basic_move', 5))
emove = move * (5 - lvl) // 5
# Strip the last weighing's penalty, then fit a fresh one only when over BL.
remove_effect(enactor, 'encumbered')
if lvl:
    apply_effect(enactor, 'modifier_effect', kind='encumbered', duration=0, check_mods={'all': -lvl})
pemit(enactor, f'Basic Lift {bl} lbs. You carry {load} lbs -> {names[lvl]} encumbrance (DX {-lvl}, Move {emove}/{move}).')
'''
```

Finally, two crates to load up with. An unmarked item weighs 0, so mark the
heavy props explicitly:

```text
@create supply crate
@set supply crate/weight = 25
drop supply crate
@create ammo case
@set ammo case/weight = 45
drop ammo case
```

## Try it

Step on empty, then start loading up (ST 10 gives Basic Lift 20 and Basic
Move 5):

```text
> heft
Basic Lift 20 lbs. You carry 0 lbs -> None encumbrance (DX 0, Move 5/5).
> get supply crate
> heft
Basic Lift 20 lbs. You carry 25 lbs -> Light encumbrance (DX -1, Move 4/5).
> get ammo case
> heft
Basic Lift 20 lbs. You carry 70 lbs -> Heavy encumbrance (DX -3, Move 2/5).
```

At Heavy (70 lbs is over 3 × BL) you are wearing a -3 `encumbered`
condition, and exactly as in [135](135_injury_treatment.md) it folds into any
[`skill_check()`](../reference/softcode.md#fn-skill_check) you make: a climb, a
dodge, a lockpick, all harder because your arms are full. Set the load down
and re-weigh, and the scale strips the old penalty and fits a lighter one:

```text
> drop ammo case
> heft
Basic Lift 20 lbs. You carry 25 lbs -> Light encumbrance (DX -1, Move 4/5).
> drop supply crate
> heft
Basic Lift 20 lbs. You carry 0 lbs -> None encumbrance (DX 0, Move 5/5).
```

A stronger character shrugs off the same crates: raise `strength` to 14 and
Basic Lift jumps to 39, so the same 70 lbs drops all the way to Light.
Encumbrance is the first place raw ST earns its keep outside a fight.

## Going further

- **Hands-free updates:** put the heft body on every haulable item's
  `on_get` and `on_drop` (reading `contents(enactor)`), so the penalty tracks
  your load without a command, the audit's `ON_GET`/`ON_DROP` recompute.
  Because those hooks fire on every object in the room, guard each with
  `if target is me:` so a crate only recomputes when it is the crate that
  moved. `@parent` a "cargo" prototype so one edit covers them all.
- **A hard cap, not just a penalty:** past X-Heavy, refuse the pickup with an
  `on_check` ward that sums weight, the [035](035_crawlspace.md) squeeze
  pointed at your own back instead of a tunnel.
- **Move that the world honors:** stash `emove` in `db.move` and have your
  travel-time exits ([161](161_travel_time.md)) read it, so the overloaded
  literally walk slower, not just roll worse.
- **Encumbrance in combat:** the same `encumbered` effect already drags Dodge
  (a DX-based defense) once your ruleset routes defenses through `check`, so
  heavy loads get you hit.
