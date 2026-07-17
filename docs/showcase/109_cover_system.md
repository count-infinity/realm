# 109. Cover system

> Checklist item 109 — [now] — *the engine cover maneuver, cover-tagged fixtures*

**What you'll build:** A killhouse where fighters duck behind a wrecked
dropship hull to spoil incoming laser fire — using the combat engine's
**native** cover maneuver — plus a softcode layer that lets attackers
blow the cover apart.

**Concepts:** the engine's two-band range model (`close`/`withdraw`/
`shoot`/`aim`/`cover` maneuvers), `cover`-tagged fixtures as the builder
surface, ranged weapon attributes (`ranged` tag, `damage_dice`,
`skill_type`, `acc`), and a `$`-command for destructible-cover flavor.

## How it works

Cover is **built into the combat engine** — this tutorial is mostly a
tour plus one tag. Every REALM encounter runs a two-band range model:
band 0 is *engaged* (melee reach), band 1 is *at range*. The base
maneuver vocabulary every ruleset publishes includes:

- `shoot <target>` — attack with a wielded `ranged`-tagged weapon.
  Works at either band; -2 in close quarters (both parties engaged),
  **-2 against a target in cover**.
- `aim <target>` — bank +Acc (the weapon's `acc` attribute) on your
  next shot, +1 per extra round, capped at Acc+2.
- `close` / `withdraw` — change bands. Both **break your cover**.
- `cover` — duck behind cover. The engine grants it only if the room
  actually contains an object tagged `cover` — and that is the entire
  builder interface: **tag a fixture, and the room supports cover.**

So the builder workflow is one line: `@tag <fixture> = cover`. The
engine names the first cover fixture in its messaging ("You duck behind
the overturned dropship hull."), so make it something worth hiding
behind.

The softcode layer adds what the engine deliberately doesn't model:
cover that can be destroyed. A `$shred` command on the hull spends its
`plating` attribute and finally strips the `cover` tag — after which
the `cover` maneuver reports "There's nothing here to take cover
behind."

Two honest notes. First, cover only penalizes `shoot` — melee attackers
just walk around your barricade (GURPS would agree). Second, a fighter
who is *already* in cover when the fixture is destroyed keeps the -2
until they move (`close`/`withdraw`) — the in-cover flag lives on the
encounter participant, which softcode cannot reach. Destroying cover
denies it to the *next* taker. Noted as an engine gap below.

## Build it

The room and the fixture. The tag is the whole cover system:

```text
@dig The Killhouse = killhouse, out
killhouse
@create overturned dropship hull
drop overturned dropship hull
@desc overturned dropship hull = Half a cargo dropship, belly-up, its plating scorched and buckled. Good cover -- while it lasts.
@tag overturned dropship hull = cover
```

A ranged weapon, described entirely in data the GURPS ruleset reads:
`skill_type` picks the attack skill (`skill_ranged`), `damage_dice` is
GURPS notation, `acc` feeds the `aim` maneuver, and the `ranged` tag is
what `shoot` checks for:

```text
@create laser carbine
@set laser carbine/damage_dice = 2d
@set laser carbine/damage_type = burning
@set laser carbine/skill_type = ranged
@set laser carbine/acc = 2
@tag laser carbine = ranged
drop laser carbine
```

The destructible layer. `plating` is hit points for the fixture; when
it runs out, the `cover` tag goes with it:

```text
@set overturned dropship hull/plating = 2
@set overturned dropship hull/cmd_shred = $shred hull: p = V('plating', 0) - 1; (pemit(enactor, 'The hull is already scrap.') if not has_tag(me, 'cover') else ((set_attr(me, 'plating', 0), remove_tag(me, 'cover'), remit(loc(me), name(enactor) + ' blasts the hull apart -- it is cover for no one now!')) if p <= 0 else (set_attr(me, 'plating', p), remit(loc(me), name(enactor) + ' tears chunks off the hull. It will not stand much more.'))))
```

## Try it

Two fighters in the killhouse. The attacker picks up the carbine:

```text
get laser carbine
wield laser carbine        -> You ready laser carbine.
attack <defender>          -> You square off against ...
queue withdraw             -> Queued: Withdraw
```

On the beat, the shooter falls back to range; melee can no longer reach
them (`attack` reports "You're out of melee reach"). Then:

```text
queue shoot <defender>     -> Queued: Shoot
```

That shot resolves at full skill. Now the defender types:

```text
queue cover                -> Queued: Take Cover
```

Beat: "You duck behind the overturned dropship hull." Every later
`shoot` against them is at -2 — watch the misses pile up. The defender
gives it up by moving (`queue close`), and once someone `$shred`s the
hull twice, `queue cover` gets:

```text
There's nothing here to take cover behind.
```

**Engine gaps (reported):** (1) a participant already in cover keeps
the -2 after the cover fixture is destroyed — the participant's
`in_cover` flag is encounter state with no softcode surface to clear
it; (2) `exits()`-style, the `cover` maneuver picks the *first*
cover-tagged object in the room — there is no per-fixture capacity or
quality (a -2 flat bonus, not per-object DR).

## Going further

- **Quality cover** — the engine's -2 is flat, but nothing stops a
  *second* softcode layer: a `$vault` command that `apply_effect`s a
  `modifier_effect` with `check_mods` while crouched behind sandbags.
- **Skill-gated demolition** — wrap `$shred` in
  `skill_check(enactor, 'demolition', -2)` so tearing down cover costs
  a real roll (and a beat of standing in the open).
- **Regrowing cover** — give the scrap an `ON_EXPIRE` that respawns a
  fresh barricade on the next zone reset, the `expire()`/`ON_RESET`
  idioms from items 48 and 60.
- **Smoke as cover** — a thrown smoke canister (item 111's fuse
  pattern) that `add_tag`s itself `cover` and `expire()`s in a minute:
  pop-up concealment anywhere.
