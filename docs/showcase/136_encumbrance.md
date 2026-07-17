# 136. Encumbrance Effects

> Checklist item 136 — [now] — *weight as convention, GURPS Basic Lift math, a modifier_effect that scales with load*

**What you'll build:** a cargo scale you step onto that weighs everything
you carry, works out your GURPS encumbrance level from your Strength, and
stamps the matching **penalty** onto you as a live condition — light load,
no cost; overloaded, −3 to your rolls and your Move cut to a crawl. Drop
weight and step on again; the penalty recomputes.

**Concepts:** REALM has **no weight kernel** — `weight` is an attribute
convention ([035](035_crawlspace.md)), and this tutorial supplies the
*rules* in softcode; the GURPS Basic Lift / encumbrance-level math; and a
`modifier_effect` whose strength is computed, applied fresh each check, so
"how much you're carrying" becomes "how badly you roll."

## How it works

**No engine cares what you weigh — you write the rule.** REALM ships no
capacity system on purpose (the audit calls this out: weight is a
convention, gated where it matters). An item's `weight` is just a number;
the scale is the thing that *cares*, and it defines encumbrance locally.
That means the math is yours to set, and here we use GURPS 4e's:

- **Basic Lift** (the most you heft one-handed for a second) is
  `BL = ST × ST / 5` pounds. ST 10 → BL 20; ST 14 → BL 39.
- **Encumbrance level** is where your carried weight falls against BL:

  | Level | Carrying up to | DX & roll penalty | Move multiplier |
  |---|---|---|---|
  | None | BL | 0 | ×1 (full) |
  | Light | 2 × BL | −1 | ×0.8 |
  | Medium | 3 × BL | −2 | ×0.6 |
  | Heavy | 6 × BL | −3 | ×0.4 |
  | X-Heavy | 10 × BL | −4 | ×0.2 |

- **Move** is your Basic Move stepped down by that multiplier — we compute
  it as `Move × (5 − level) / 5`, which lands on the GURPS values closely
  enough for play and keeps the arithmetic in one line.

**The penalty is a recomputed condition.** Each time you're weighed we
`remove_effect` the old encumbrance and, if you're over BL, `apply_effect`
a fresh `modifier_effect` carrying `check_mods={'all': -level}`. Because
that folds through `skill_check()` ([135](135_injury_treatment.md)), being
overloaded drags down *every* roll until you shed weight and re-weigh.
`duration=0` makes it permanent — it lasts until the next weighing
replaces it, not until a clock runs out.

**Why the scale is a floor fixture, not a backpack.** Effects reach from
where the object stands, and a scale weighing *you* must share your room
(proximity authority — the [059](059_tranquilizer.md) rule). A gadget in
your pocket has your pocket for a room and couldn't reach you; so you step
*onto* the scale. Wiring the same recompute to `ON_GET`/`ON_DROP` for
hands-free updates is the "Going further" upgrade.

## Build it

The dock, the scale, and two crates to load up with (the default weight of
an unmarked item is 0, so mark the heavy props):

```text
@dig The Loading Dock = dock, out
dock
@create cargo scale
drop cargo scale
@desc cargo scale = A battered freight scale bolted to the deck. STEP ON THE SCALE (command: HEFT) to gauge your load.
@set cargo scale/cmd_heft = $heft: st = int(get_attr(enactor, 'strength', 10)); bl = st * st // 5; load = sum([int(get_attr(o, 'weight', 0)) for o in contents(enactor)]); lvl = 0 if load <= bl else (1 if load <= 2 * bl else (2 if load <= 3 * bl else (3 if load <= 6 * bl else 4))); names = ['None', 'Light', 'Medium', 'Heavy', 'X-Heavy']; move = int(get_attr(enactor, 'basic_move', 5)); emove = move * (5 - lvl) // 5; remove_effect(enactor, 'encumbered'); (None if lvl == 0 else apply_effect(enactor, 'modifier_effect', kind='encumbered', duration=0, check_mods={'all': -lvl})); pemit(enactor, 'Basic Lift ' + str(bl) + ' lbs. You carry ' + str(load) + ' lbs -> ' + names[lvl] + ' encumbrance (DX ' + str(-lvl) + ', Move ' + str(emove) + '/' + str(move) + ').')
@create supply crate
@set supply crate/weight = 25
drop supply crate
@create ammo case
@set ammo case/weight = 45
drop ammo case
```

That's the whole system: one command, the GURPS table inline, and a
condition that scales with the sum.

## Try it

Step on empty, then start loading up (ST 10 → Basic Lift 20, Basic Move 5):

```text
heft                     -> Basic Lift 20 lbs. You carry 0 lbs -> None encumbrance (DX 0, Move 5/5).
get supply crate
heft                     -> ...You carry 25 lbs -> Light encumbrance (DX -1, Move 4/5).
get ammo case
heft                     -> ...You carry 70 lbs -> Heavy encumbrance (DX -3, Move 2/5).
```

At Heavy (70 lbs is over 3 × BL) you're wearing a −3 `encumbered`
condition, and — exactly as in [135](135_injury_treatment.md) — it folds
into any `skill_check()` you make: a climb, a dodge, a lockpick, all harder
because your arms are full. Set the load down and re-weigh, and the scale
strips the old penalty and fits a lighter one:

```text
drop ammo case
heft                     -> ...You carry 25 lbs -> Light encumbrance (DX -1, Move 4/5).
drop supply crate
heft                     -> ...You carry 0 lbs -> None encumbrance (DX 0, Move 5/5).
```

A stronger character shrugs off the same crates: raise `strength` to 14
and Basic Lift jumps to 39, so the same 70 lbs drops all the way to Light.
Encumbrance is the first place raw ST earns its keep outside a fight.

## Going further

- **Hands-free updates:** put the heft body on every haulable item's
  `on_get` and `on_drop` (reading `contents(enactor)`), so the penalty
  tracks your load without a command — the audit's `ON_GET`/`ON_DROP`
  recompute. `@parent` a "cargo" prototype so one edit covers them all.
- **A hard cap, not just a penalty:** past X-Heavy, refuse the pickup with
  an `on_check` ward that sums weight — the [035](035_crawlspace.md)
  squeeze, pointed at your own back instead of a tunnel.
- **Move that the world honors:** stash `emove` in `db.move` and have your
  travel-time exits ([161]) read it, so the overloaded literally walk
  slower, not just roll worse.
- **Encumbrance in combat:** the same `encumbered` effect already drags
  Dodge (a DX-based defense) once your ruleset routes defenses through
  `check` — heavy loads get you hit.
