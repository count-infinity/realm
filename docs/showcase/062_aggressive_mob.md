# 062. Aggressive mob

> Checklist item 62 — [now] — *aggressive behavior, disposition as faction standing, softcode faction gates*

**What you'll build:** a warren with teeth. The warren rat attacks
anyone on sight — unless they've earned its tolerance, which the
engine measures with the same disposition scale everything else uses.
Deeper in, the broodmother enforces a *tag-based* faction line in one
softcode attribute: ratkin pass, everyone else is prey.
**Concepts:** the built-in `aggressive` behavior (`target_tags`,
`spare_at`, `attack_chance`, `taunt`), disposition as faction standing
(and `ON_RECEIVE` offerings that buy it), the softcode `ON_ENTER` +
`start_combat()` gate keyed on a `faction:` tag.

## How it works

**The native brain.** `@behavior <mob> = aggressive, ...` reacts to
`event:on_enter` — both when prey walks in on the mob *and* when the
mob wanders in on prey. Before it lunges it runs four checks, all
params:

- `target_tags` (default `['player']`) — what counts as prey.
- **`spare_at` (default 2)** — the faction-standing check: if the
  mob's *disposition* toward the target is at or above this, it stands
  down. Disposition is the engine's one attitude scale (-5..+5) — the
  same number `consider` shows, `persuade`/`fasttalk` move, shop
  prices read, and item 71's watch writes. Standing with a monster is
  not a new system; it's a number the monster consults before biting.
- `attack_chance` — dice for hesitation.
- `taunt` — the line it says as it engages (real speech — listen
  triggers can hear a war-cry).

The attack itself goes through the combat manager (`initiate`), so
encounters, beats, strategies and defeat all work exactly as if a
player had typed `attack`.

**Buying standing.** How does a player *raise* a rat's opinion?
`persuade` works on anything with a will, but the flavorful road is an
offering: an `ON_RECEIVE` hook (fires when something is `give`n to the
mob) that calls `adjust_disposition(me, enactor, +5)`. Five points
clears `spare_at:2`. Mind the choreography, though: an on-sight mob is
*already on you* by the time you could hand it anything — so tribute
is paid mid-scrap (`give` isn't gated by combat), and it buys not this
fight but the *next* one. Flee, catch your breath, walk back in: the
red eyes just... watch. Aggression is checked at the door; memory is
forever.

**The softcode faction gate.** Sometimes standing should be *group*
membership, not individual opinion. Tag members `faction:ratkin` and
give the broodmother one `ON_ENTER` attribute: if the arrival's
`faction` tag-value isn't `ratkin` (and its personal standing is low),
`start_combat(me, enactor)`. The mob controls itself, so it may throw
itself into combat with whoever it witnesses arriving. Native behavior
and softcode gate compose — the audit's two faces of "attacks on
sight, based on faction standing."

## Build it

Dig both rooms first, then arm the deepest room and retreat outward —
never re-enter a room you've already made hostile (an aggressive mob
does not care that you built it):

```
@dig The Warren Mouth = warren, out
warren
@dig The Brood Chamber = deeper, out
deeper
```

The matriarch and her one-line faction gate (safe to build — `ON_ENTER`
fires on *arrivals*, and you're already inside):

```
@create broodmother
@tag broodmother = npc
drop broodmother
@set broodmother/hp = 14
@set broodmother/max_hp = 14
@set broodmother/skill_melee = 12
@set broodmother/on_enter = start_combat(me, enactor) if has_tag(enactor, 'player') and tag_value(enactor, 'faction') != 'ratkin' and disposition(me, enactor) < 2 else None
```

Note her gate still consults `disposition(...) < 2` — personal
standing can override faction even here, so tribute works on her too.

Step out to the warren mouth and build its resident:

```
out
@create warren rat
@tag warren rat = npc
drop warren rat
@set warren rat/hp = 8
@set warren rat/max_hp = 8
@set warren rat/skill_melee = 10
@set warren rat/on_receive = adjust_disposition(me, enactor, 5); pose('sniffs the offering and settles back, watching ' + name(enactor) + ' with something like tolerance.')
@behavior warren rat = aggressive, target_tags:["player"], spare_at:2, attack_chance:1.0, taunt:The rat's eyes go red. It lunges!
out
```

## Try it

Give yourself a fighting sheet and something to sacrifice:

```
@set me/hp = 12
@set me/max_hp = 12
@set me/skill_melee = 12
@create dead beetle
```

Walk in cold, pay tribute under fire, and get out:

```
warren                        → warren rat says, "The rat's eyes go red. It lunges!"
                                — you are in combat
give dead beetle to warren rat → it sniffs the offering and settles back...
flee                          → back to your workroom, heart pounding
```

Now the gift does its work:

```
warren                → nothing moves. consider warren rat — it holds
                        you in the highest regard.
deeper                → the broodmother is on you (no taunt, no
                        hesitation — that's the one-line softcode gate)
flee
```

Join the family and try her again:

```
@tag me = faction:ratkin
warren
deeper                → she ignores you utterly
```

## Going further

- **Standing decays:** the `disposition_boost` effect (what `fasttalk`
  uses) is a *temporary* +N — apply it from `ON_RECEIVE` instead and
  offerings wear off, so the warren must be re-fed.
- **Packs:** `@clone warren rat` — behaviors copy. Every clone
  consults its *own* disposition, so standing is per-rat unless you
  gate on the faction tag instead.
- **War-cries as alarms:** the taunt is real speech; a `^*lunges*`
  listen on a nest-mother two rooms over (via a zone master) gives you
  mobs that call reinforcements (compose with item 71's dispatch).
- **Day-tame, night-wild:** attach/detach the `aggressive` behavior
  from item 68's clock states — the warren only hunts after dark.
- **Picky prey:** `target_tags:["player", "npc"]` plus item 60's
  wanderer gives a predator that hunts the scamp too — and
  `spare_at:2` still lets it be tamed.
