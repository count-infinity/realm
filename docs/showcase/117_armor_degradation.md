# 117. Armor degradation

> Checklist item 117 — [now] — *ON_DAMAGE bookkeeping, DR attrs, repair sinks*

**What you'll build:** A flak vest that actually stops bullets — using
the ruleset's **native** damage-resistance stat — and wears out doing
it: every hit that strikes home costs the vest a plate, a shredded vest
stops nothing, and an armorer's bench (with a real skill roll) is the
repair sink.

**Concepts:** the native soak model (`damage_resistance` on the
combatant), `ON_WEAR`/`ON_REMOVE` as the equip seams, an `ON_DAMAGE`
hook *on the wearer* as the degradation ledger, admin owner authority
for writing player sheets, and honest notes on what damage hooks can
and cannot see.

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
`armor_condition` (a mirror of the vest's plating), and an `on_damage`
**hook script**. On removal it copies the surviving condition back to
the vest and cleans all three off.

**Why the ledger lives on the wearer.** Witness objects hear
`combat:on_damage` with only the *attacker* as `enactor` — a bystander
cannot tell who got hit. But the **target's own** `ON_DAMAGE` fires
too, and there the executor *is* the victim: perfect identification,
no sweep. The hook runs as the wearer (players control themselves), so
it can spend `armor_condition` and, at zero, zero out its own
`damage_resistance` — but it could never write the *vest* (players do
not own it), which is why condition mirrors onto the wearer while worn.

**Authority: this is an admin build.** `ON_WEAR` runs as the vest, and
the vest writes its wearer's sheet — three attributes on a *player*.
Softcode wields its owner's authority, and only admins control other
players: **the outfitter's stock must be admin-owned.** A builder-owned
vest would fail those writes silently — correctly.

**What the hook cannot see (honest note).** `ON_DAMAGE` fires per hit
that got through active defenses, *before* the damage number is
applied, and the hook namespace carries no amount — so plating wears
**per hit**, not per point, and it wears even on a fully-soaked hit
(the plate did its job; that is why it cracked). If you want
point-accurate wear, that is an engine seam, not a softcode one.

## Build it

As an **admin**. The shop and the vest:

```text
@dig The Outfitter = outfitter, out
outfitter
@create flak vest
@tag flak vest = wearable
@set flak vest/slot = torso
@set flak vest/dr = 3
@set flak vest/condition = 3
@desc flak vest = Ceramic plates in a webbing carrier. [[c = get_attr(me, 'condition', 0); result = 'The plates look factory-fresh.' if c >= 3 else ('Cracks spider across the plates.' if c > 0 else 'The carrier is full of ceramic gravel. It will stop nothing.')]]
```

The equip seams — wear installs the soak and the ledger, removal
uninstalls and syncs:

```text
@set flak vest/on_wear = c = get_attr(me, 'condition', 0); (pemit(enactor, 'The vest is shredded -- it will stop nothing until it is repaired.') if c <= 0 else (set_attr(enactor, 'damage_resistance', get_attr(me, 'dr', 3)), set_attr(enactor, 'armor_condition', c), set_attr(enactor, 'on_damage', get_attr(me, 'degrade')), pemit(enactor, 'You cinch the flak vest tight. (DR ' + str(get_attr(me, 'dr', 3)) + ', ' + str(c) + ' plates)')))
@set flak vest/degrade = c = get_attr(me, 'armor_condition', 0); (None if c <= 0 else ((set_attr(me, 'armor_condition', 0), set_attr(me, 'damage_resistance', 0), pemit(me, 'Your vest takes the brunt -- and comes apart at the seams. It will stop nothing more.')) if c <= 1 else (set_attr(me, 'armor_condition', c - 1), pemit(me, 'Your vest soaks the worst of it. (' + str(c - 1) + ' plates left)'))))
@set flak vest/on_remove = set_attr(me, 'condition', get_attr(enactor, 'armor_condition', 0)); set_attr(enactor, 'damage_resistance', 0); del_attr(enactor, 'armor_condition'); del_attr(enactor, 'on_damage'); pemit(enactor, 'You shrug out of the vest.')
drop flak vest
```

(`degrade` is stored under an inert name and *copied* onto the wearer
as their live `on_damage` — item 48's prototype-copy idiom. `pemit(me,
...)` works because by then `me` is the wearer.)

The repair sink:

```text
@create mending bench
drop mending bench
@desc mending bench = A scarred workbench of clamps and rivet guns. Drop armor here and REPAIR VEST.
@set mending bench/cmd_repair = $repair vest: v = get('flak vest'); (pemit(enactor, 'Lay the vest on the bench first -- drop it here.') if not (v and loc(v) == loc(me)) else ((set_attr(v, 'condition', 3), remit(loc(me), name(enactor) + ' hammers the plating flat and rivets in fresh ceramic.')) if skill_check(enactor, 'armoury') else pemit(enactor, 'You bend a plate the wrong way. No good.')))
```

## Try it

Put the vest on someone and let a thug (damage 3 a swing) work them
over:

```text
get flak vest
wear flak vest        -> You cinch the flak vest tight. (DR 3, 3 plates)
```

Hits one and two: `Your vest soaks the worst of it.` — and HP does not
move, because DR 3 eats the whole blow. Hit three:

```text
Your vest takes the brunt -- and comes apart at the seams. It will stop nothing more.
```

The ledger hook runs while the damage is still in flight, so the very
blow that breaks the vest is the first one that gets through — HP
moves on hit three, and on every hit after. Afterwards:

```text
remove flak vest      -> You shrug out of the vest.       (condition 0 syncs back)
wear flak vest        -> The vest is shredded -- it will stop nothing until it is repaired.
drop flak vest
repair vest           -> ... hammers the plating flat ...  (Armoury check)
get flak vest
wear flak vest        -> You cinch the flak vest tight. (DR 3, 3 plates)
```

**Engine gap (reported):** `ON_DAMAGE` scripts get no damage payload
(amount, types, hit quality) — the hook namespace carries only
`enactor` — so armor wear is per-hit rather than per-point; and there
is no native worn-gear→stat plumbing (`grants_tags` grants tags only),
which is why equipping stats requires admin-owned softcode.

## Going further

- **Soak-as-ward instead of DR** — the wearer's `on_check` can
  `mod(-3)` a `combat:on_damage` in flight (decision-only, runs on the
  target): armor that composes with, or replaces, the native DR stat.
- **Priced repairs** — make the bench demand `pay` first: an
  `ON_PAYMENT` till (item 64) that banks one repair credit per 20 paid.
- **Damage-type plating** — keep per-type DR attrs and have `degrade`
  spend the matching one; the ruleset only reads `damage_resistance`,
  so fold them into it on wear.
- **Weapon wear** — the mirror build: `ON_ATTACK` fires on the attacker's
  victim and witnesses, but the *attacker's own* hooks never fire on
  their own swing — so weapon degradation needs the `ON_WIELD` seam
  plus a room witness, a good exercise in exactly these limits.
