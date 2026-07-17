# 117. Armor degradation

> Checklist item 117 — [now] — *ON_DAMAGE bookkeeping, DR attrs, repair sinks*

**What you'll build:** A flak vest that actually stops bullets — using
the ruleset's **native** damage-resistance stat — and wears out doing
it: every hit costs the vest **exactly the damage it stopped**, a
shredded vest stops nothing, and an armorer's bench (with a real skill
roll) is the repair sink.

**Concepts:** the native soak model (`damage_resistance` on the
combatant), `ON_WEAR`/`ON_REMOVE` as the equip seams, an `ON_DAMAGE`
hook *on the wearer* as the degradation ledger, reading the in-flight
action with `adata('damage')`, and admin owner authority for writing
player sheets.

## How it works

**The native soak model.** The GURPS ruleset reads one stat at damage
time: `damage_resistance` on the *defender* — flat DR subtracted from
every damage roll before type multipliers, exactly GURPS's armor line.
That is the whole native model: a number on the combatant. There is no
built-in worn-armor-to-DR plumbing (the `wear` command natively grants
**tags** via `grants_tags`, not stats) — which is exactly the gap this
tutorial's softcode fills.

**Equipping through the native seams.** The vest is an ordinary
`wearable` (slot `torso`), so players use the real `wear`/`remove`
commands — and those fire the vest's gated `ON_WEAR` / `ON_REMOVE`
softcode with the wearer as `enactor`. On wear, the vest writes three
things onto its wearer: `damage_resistance` (the native soak),
`armor_plating` (a mirror of the vest's remaining ceramic), and an
`on_damage` **hook script**. On removal it copies the surviving plating
back to the vest and cleans all three off.

**Why the ledger lives on the wearer.** The hook runs *as* the wearer,
and players control themselves — so it can spend `armor_plating` and,
at zero, zero out its own `damage_resistance`. A bystander hears the
same event and can write none of that. That is the rule worth learning:
put bookkeeping on the object that *owns* the state, not on whoever
happened to see it. (The hook could never write the *vest* — players do
not own it — which is why plating mirrors onto the wearer while worn.)

**But being the executor does not make you the victim.**
`combat:on_damage` is a *witnessed* event: it fires the `ON_DAMAGE`
attribute of **everything in the room**, not just whoever got hit. So
your vest's hook runs when the man next to you takes a sword — `me` is
still you, because it is still your hook, but the blow was never yours.
`target` is the defender, and `target == me` is the only thing that
tells the two apart. Leave it out and your armor rots from other
people's wounds: stand in a busy room and you are gravel before anyone
touches you.

**Reading the blow.** With that settled, `ON_DAMAGE` carries the
payload: `adata('damage')` is the damage roll and
`adata('damage_types')` its breakdown by type. That is what makes the
wear **point-accurate**: the vest spends `min(DR, damage)` — exactly
the number of points of ceramic that stood between you and the wound.
A graze for 1 costs one point; a cannon shell for 20 costs the full DR
3 and nothing more, because 3 is all the vest ever stopped.

**Authority: this is an admin build.** `ON_WEAR` runs as the vest, and
the vest writes its wearer's sheet — three attributes on a *player*.
Softcode wields its owner's authority, and only admins control other
players: **the outfitter's stock must be admin-owned.** A builder-owned
vest would fail those writes silently — correctly.

**Timing (worth knowing).** `ON_DAMAGE` fires per hit that got through
active defenses, *after* the damage is rolled but *before* it is
applied — and `damage_resistance` is read at apply time. So the hook
and the wound are in the same instant: the blow that spends the vest's
last point is the first one that gets through, because `degrade` zeroed
the DR a heartbeat before the ruleset subtracted it.

## Build it

As an **admin**. The shop and the vest — `plating` is **points of
ceramic**, not a plate count: the number of damage points this carrier
can eat before it is gravel.

```text
@dig The Outfitter = outfitter, out
outfitter
@create flak vest
@tag flak vest = wearable
@set flak vest/slot = torso
@set flak vest/dr = 3
@set flak vest/plating = 9
@desc flak vest = Ceramic plates in a webbing carrier. [[p = V('plating', 0); result = 'The plates look factory-fresh.' if p >= 9 else ('Cracks spider across the plates.' if p > 0 else 'The carrier is full of ceramic gravel. It will stop nothing.')]]
```

The equip seams — wear installs the soak and the ledger, removal
uninstalls and syncs:

```text
@set flak vest/on_wear = p = V('plating', 0); (pemit(enactor, 'The vest is shredded -- it will stop nothing until it is repaired.') if p <= 0 else (set_attr(enactor, 'damage_resistance', V('dr', 3)), set_attr(enactor, 'armor_plating', p), set_attr(enactor, 'on_damage', V('degrade')), pemit(enactor, 'You cinch the flak vest tight. (DR ' + str(V('dr', 3)) + ', ' + str(p) + ' points of plating)')))
@set flak vest/degrade = soak = min(V('damage_resistance', 0), adata('damage', 0)) if target == me else 0; p = V('armor_plating', 0); (None if p <= 0 or soak <= 0 else ((set_attr(me, 'armor_plating', 0), set_attr(me, 'damage_resistance', 0), pemit(me, 'Your vest takes the brunt -- and comes apart at the seams. It will stop nothing more.')) if soak >= p else pemit(me, 'Your vest soaks ' + str(soak) + ' -- ' + str(decr('armor_plating', soak)) + ' points of plating left.')))
@set flak vest/on_remove = set_attr(me, 'plating', get_attr(enactor, 'armor_plating', 0)); set_attr(enactor, 'damage_resistance', 0); del_attr(enactor, 'armor_plating'); del_attr(enactor, 'on_damage'); pemit(enactor, 'You shrug out of the vest.')
drop flak vest
```

(`degrade` is stored under an inert name and *copied* onto the wearer
as their live `on_damage` — item 48's prototype-copy idiom. `pemit(me,
...)` works because by then `me` is the wearer, and so does
`V('damage_resistance', 0)`: the hook reads the live DR it installed
itself, so `min(DR, damage)` is the ceramic that actually took the
blow. `decr(k, n)` spends and returns in one call. And note the
`if target == me` — without it the vest wears every time *anyone* in
the room is hit.)

The repair sink:

```text
@create mending bench
drop mending bench
@desc mending bench = A scarred workbench of clamps and rivet guns. Drop armor here and REPAIR VEST.
@set mending bench/cmd_repair = $repair vest: v = get('flak vest'); (pemit(enactor, 'Lay the vest on the bench first -- drop it here.') if not (v and loc(v) == loc(me)) else ((set_attr(v, 'plating', 9), remit(loc(me), name(enactor) + ' hammers the plating flat and rivets in fresh ceramic.')) if skill_check(enactor, 'armoury') else pemit(enactor, 'You bend a plate the wrong way. No good.')))
```

## Try it

Put the vest on someone and let a thug (damage 3 a swing) work them
over:

```text
get flak vest
wear flak vest        -> You cinch the flak vest tight. (DR 3, 9 points of plating)
```

Hits one and two: `Your vest soaks 3 -- 6 points of plating left.`,
then `3 points`. HP does not move: DR 3 eats the whole blow, and the
vest is billed the 3 it stopped. Hit three:

```text
Your vest takes the brunt -- and comes apart at the seams. It will stop nothing more.
```

The ledger hook runs while the damage is still in flight, so the very
blow that spends the last of the ceramic is the first one that gets
through — HP moves on hit three, and on every hit after. Change the
thug's weapon and the arithmetic follows the fiction: a 1-point graze
buys you nine grazes; a 20-point slug still only spends 3, because 3 is
what the vest stopped. Afterwards:

```text
remove flak vest      -> You shrug out of the vest.       (plating 0 syncs back)
wear flak vest        -> The vest is shredded -- it will stop nothing until it is repaired.
drop flak vest
repair vest           -> ... hammers the plating flat ...  (Armoury check)
get flak vest
wear flak vest        -> You cinch the flak vest tight. (DR 3, 9 points of plating)
```

**Engine gap (reported):** there is no native worn-gear→stat plumbing —
`wear` grants **tags** via `grants_tags`, never stats — which is why
equipping `damage_resistance` at all requires admin-owned softcode. (The
older gap here, "`ON_DAMAGE` scripts get no damage payload", is **fixed
as of 2026-07-17**: hooks now carry `target` and `adata(...)`, which is
exactly what the point-accurate `degrade` above spends.)

## Going further

- **Soak-as-ward instead of DR** — the wearer's `on_check` can
  `mod(-3)` a `combat:on_damage` in flight (decision-only, runs on the
  target): armor that composes with, or replaces, the native DR stat.
- **Priced repairs** — make the bench demand `pay` first: an
  `ON_PAYMENT` till (item 64) that banks one repair credit per 20 paid.
- **Damage-type plating** — `adata('damage_types')` is the roll broken
  down by type (`{'burning': 6}`), so ceramic can hate lasers: spend
  `2 * adata('damage_types', {}).get('burning', 0)` alongside the
  ordinary soak, and the same vest that shrugs off bullets cooks
  through in two shots.
- **Weapon wear** — the mirror build, and now a fair fight:
  `combat:on_attack` carries `adata('weapon')` and `target`, so a room
  witness (item 115's bell, item 120's chronicle) can bill the right
  weapon for the right swing. The attacker's *own* hooks still never
  fire on their own swing, so the witness — or the `ON_WIELD` seam — is
  still how you reach it.
