# 109. Cover system

> Checklist item 109 ([now]): *the engine cover maneuver, cover-tagged fixtures*

**What you'll build:** A killhouse where fighters duck behind a wrecked
dropship hull to spoil incoming laser fire, using the combat engine's **native**
cover maneuver, plus a softcode layer that lets attackers blow the cover apart.

**Concepts:** the engine's two-band range model (`close`/`withdraw`/`shoot`/
`aim`/`cover` maneuvers), `cover`-tagged fixtures as the builder surface, ranged
weapon attributes (`ranged` tag, `damage_dice`, `skill_type`, `acc`), and a
`$`-command for destructible-cover flavor.

## How it works

Cover is built into the combat engine, so this tutorial is mostly a tour plus
one tag. Every REALM encounter runs a two-band range model: band 0 is *engaged*
(melee reach) and band 1 is *at range*. The base maneuver vocabulary every
ruleset publishes, queued in a fight with `queue <maneuver>`, includes:

- `shoot <target>` attacks with a wielded `ranged`-tagged weapon. It works at
  either band, takes -2 in close quarters (both parties engaged), and takes a
  further -2 against a target in cover.
- `aim <target>` banks +Acc (the weapon's `acc` attribute) onto your next shot
  at that target, +1 per extra round, capped at Acc+2.
- `close` and `withdraw` change bands, and both break your cover.
- `cover` ducks you behind cover. The engine grants it only if the room actually
  contains an object tagged `cover`, and that is the entire builder interface:
  tag a fixture, and the room supports cover.

So the builder workflow is one line, `@tag <fixture> = cover`. The engine names
the first cover-tagged fixture in its messaging ("You duck behind the overturned
dropship hull."), so make it something worth hiding behind.

The softcode layer adds what the engine deliberately does not model: cover that
can be destroyed. A `$shred` command on the hull spends its `plating` attribute
and finally strips the `cover` tag with
[`remove_tag`](../reference/softcode.md#fn-remove_tag), after which the `cover`
maneuver reports "There's nothing here to take cover behind."

Two honest notes. First, cover only penalizes `shoot`, because the engine
applies the -2 inside its ranged resolution alone, so melee attackers simply
walk around your barricade (GURPS would agree). Second, a fighter who is
*already* in cover when the fixture is destroyed keeps the -2 until they move
(`close` or `withdraw`), because the in-cover flag lives on the encounter
participant, which softcode cannot reach. Destroying cover denies it to the
*next* taker. That limit is noted as an engine gap below.

## Build it

Dig the room, walk in, and build the fixture. The `cover` tag is the whole cover
system, since the engine scans the room for a `cover`-tagged object and grants
the maneuver only if it finds one. The `--` in the description is game text, so
it stays as written:

```text
@dig The Killhouse = killhouse, out
killhouse
@create overturned dropship hull
drop overturned dropship hull
@desc overturned dropship hull = Half a cargo dropship, belly-up, its plating scorched and buckled. Good cover -- while it lasts.
@tag overturned dropship hull = cover
```

A ranged weapon is described entirely in data the GURPS ruleset reads.
`skill_type` picks the attack skill, so `ranged` resolves to the `skill_ranged`
stat; `damage_dice` is GURPS notation; `acc` feeds the `aim` maneuver; and the
`ranged` tag is what `shoot` checks for before it will fire:

```text
@create laser carbine
@set laser carbine/damage_dice = 2d
@set laser carbine/damage_type = burning
@set laser carbine/skill_type = ranged
@set laser carbine/acc = 2
@tag laser carbine = ranged
drop laser carbine
```

The destructible layer is one `$`-command. `plating` is the fixture's hit
points, and when it runs out the `cover` tag goes with it. The command reads the
plating one lower, then branches three ways: an already-scrapped hull, the shot
that finally breaks it, and a glancing shot that only chips it. It is written as
a `'''` block so the branches read plainly:

```text
@set overturned dropship hull/plating = 2
@set overturned dropship hull/cmd_shred = '''
$shred hull:
p = V('plating', 0) - 1
if not has_tag(me, 'cover'):
    pemit(enactor, 'The hull is already scrap.')
elif p <= 0:
    set_attr(me, 'plating', 0)
    remove_tag(me, 'cover')  # stripping the cover tag is what disables the engine Take Cover maneuver here
    remit(loc(me), name(enactor) + ' blasts the hull apart -- it is cover for no one now!')
else:
    set_attr(me, 'plating', p)
    remit(loc(me), name(enactor) + ' tears chunks off the hull. It will not stand much more.')
'''
```

[`V`](../reference/softcode.md#fn-v) reads the current `plating` (it is
shorthand for [`get_attr`](../reference/softcode.md#fn-get_attr)),
[`set_attr`](../reference/softcode.md#fn-set_attr) writes the new count, and
[`remit`](../reference/softcode.md#fn-remit) narrates to the whole room using the
shredder's [`loc`](../reference/softcode.md#fn-loc) and
[`name`](../reference/softcode.md#fn-name), while
[`pemit`](../reference/softcode.md#fn-pemit) speaks only to the shredder. The
[`has_tag`](../reference/softcode.md#fn-has_tag) test comes first so an
already-scrapped hull answers before the arithmetic matters. Because a
`$`-command runs only on the object whose attribute holds it, it needs no
`target is me` guard, unlike an
[`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook that fires on every
object in the room.

## Try it

Put two fighters in the killhouse and give yourself the carbine. Wielding it
readies a ranged weapon, and `attack` opens the fight through the same combat
manager the [aggressive mob](062_aggressive_mob.md) uses:

```text
> get laser carbine
> wield laser carbine
You ready laser carbine.
> attack Bruce
You square off against Bruce!
> queue withdraw
Queued: Withdraw
```

On the beat the shooter falls back to range, and melee can no longer reach them
(a queued `attack` now reports "You're out of melee reach"). Then open fire:

```text
> queue shoot Bruce
Queued: Shoot
```

That shot resolves at full skill. Now the defender digs in:

```text
> queue cover
Queued: Take Cover
```

On the next beat: "You duck behind the overturned dropship hull." Every later
`shoot` against them is at -2, so watch the misses pile up. The defender gives
cover up by moving (`queue close`), and once someone runs `shred hull` twice,
`queue cover` gets:

```text
There's nothing here to take cover behind.
```

**Engine gaps (reported):** (1) a participant already in cover keeps the -2 after
the cover fixture is destroyed, because the participant's `in_cover` flag is
encounter state with no softcode surface to clear it; (2) the `cover` maneuver
picks the *first* cover-tagged object in the room, so there is no per-fixture
capacity or quality (the bonus is a flat -2, not per-object damage resistance).

## Going further

- **Quality cover.** The engine's -2 is flat, but nothing stops a second
  softcode layer: a `$vault` command that
  [`apply_effect`](../reference/softcode.md#fn-apply_effect)s a `modifier_effect`
  carrying `check_mods`, stacking a further defensive modifier while a fighter is
  crouched behind sandbags.
- **Skill-gated demolition.** Wrap `$shred` in a
  [`skill_check`](../reference/softcode.md#fn-skill_check)`(enactor,
  'demolition', -2)` so tearing down cover costs a real roll, plus a beat of
  standing in the open.
- **Regrowing cover.** Give the scrap an
  [`ON_RESET`](../reference/softcode.md#lifecycle-hooks) that respawns a fresh
  barricade on the next zone reset, the [zone repop](147_zone_repop.md) idiom, or
  an [`expire`](../reference/softcode.md#fn-expire) timer like the
  [gas bomb](048_gas_bomb.md)'s.
- **Smoke as cover.** A thrown smoke canister (the [grenade](111_grenades.md)'s
  fuse pattern) that [`add_tag`](../reference/softcode.md#fn-add_tag)s itself
  `cover` and expires in a minute gives pop-up concealment anywhere.
