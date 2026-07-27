# 062. Aggressive mob

> Checklist item 62 ([now]): *aggressive behavior, disposition as faction standing, softcode faction gates*

**What you'll build:** a warren with teeth. The warren rat attacks anyone on
sight, unless they have earned its tolerance, which the engine measures with
the same disposition scale everything else uses. Deeper in, the broodmother
enforces a tag-based faction line in one softcode attribute: ratkin pass,
everyone else is prey.

**Concepts:** the built-in `aggressive` behavior
([`target_tags`, `spare_at`, `attack_chance`, `taunt`](#the-native-brain)),
disposition as faction standing (and an
[`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks) offering that buys it),
and a softcode [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) gate that
calls [`start_combat()`](../reference/softcode.md#fn-start_combat) when the
arrival is not a member of the `faction:ratkin` group.

## How it works

An NPC watches the doorway and decides, the instant someone walks in, whether to
attack. Two mechanisms do this: a native behavior that reads a remembered
attitude, and a one-attribute softcode gate that reads a faction tag. This
section answers three questions: how the native brain reaches its decision, how
a player raises a monster's opinion, and how the softcode gate keys itself on
the arrival rather than on the room it fires in.

### The native brain

`@behavior <mob> = aggressive, ...` attaches a behavior that reacts to
`event:on_enter`, both when prey walks in on the mob and when the mob wanders in
on prey. It is an engine behavior, not softcode, so its checks run in Python
before it commits. Before it lunges it consults four parameters:

- `target_tags` (default `['player']`) names what counts as prey, tested with
  [`has_tag`](../reference/softcode.md#fn-has_tag).
- **`spare_at` (default 2)** is the faction-standing check: if the mob's
  [`disposition`](../reference/softcode.md#fn-disposition) toward the arrival is
  at or above this, it stands down. Disposition
  is the engine's one attitude scale, which runs from -5 to +5 centered on 0. It
  is the same number [`consider`](031_guarded_exit.md) shows, `persuade` and
  `fasttalk` move, shop prices read (plus or minus 5 percent per point), and the
  [Town Watch](071_guard_response.md) writes on a crime. Standing with a monster
  is not a new system; it is a number the monster consults before biting.
- `attack_chance` (default 1.0) is the probability it engages once the other
  checks pass, so a value below 1.0 gives it a chance to hesitate.
- `taunt` is the line it says as it engages. It is real speech routed through the
  propagation engine, so a listen trigger elsewhere can hear the war-cry.

The attack itself goes through the combat manager (`initiate`), so encounters,
beats, strategies, and defeat all work exactly as if a player had typed
`attack`.

### How a player buys standing with a monster

`persuade` works on anything with a will, but the flavorful road is an offering:
an [`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks) hook that fires when
something is `give`n to the mob and calls
[`adjust_disposition`](../reference/softcode.md#fn-adjust_disposition)`(me,
enactor, 5)`. Five points clears `spare_at:2`. Mind the choreography, because an
on-sight mob is already on you by the time you could hand it anything, so tribute
is paid mid-scrap (`give` is not gated by combat) and it buys not this fight but
the next one. Flee, catch your breath, walk back in, and the red eyes just watch:
aggression is checked at the door, but the disposition it consults persists.

Because `give` fires on every object in the room, the rat's `ON_RECEIVE` guards
on [`target is me`](../reference/softcode.md#guard-on-target): the item's
recipient is bound as `target`, and only a gift handed to the rat should raise
the rat's opinion.

### The softcode faction gate, and why it keys on the arrival

Sometimes standing should be group membership, not individual opinion. Tag
members `faction:ratkin` and give the broodmother one `ON_ENTER` attribute: if
the arrival is a player whose [`tag_value`](../reference/softcode.md#fn-tag_value)
for `faction` is not `ratkin` (and whose personal standing is low), call
[`start_combat`](../reference/softcode.md#fn-start_combat)`(me, enactor)`. The
mob controls itself, so it is allowed to throw itself into combat with whoever it
witnesses arriving.

The guard here is the opposite of the rat's. An `ON_ENTER` action targets the
room, and the mover is the `enactor`, so the gate keys on `enactor` and takes no
`target is me` check (that would compare against the room and never fire). Keying
on `enactor` is also what keeps two mobs in one chamber from turning on each
other: every occupant's hook fires with the same arriving `enactor`, so each
attacks the newcomer and none attacks a fellow occupant. The player-tag test
doubles as a self guard, because when the broodmother is the one moving she is
the `enactor` and is not a player. Native behavior and softcode gate compose into
the audit's two faces of attacks-on-sight based on faction standing.

## Build it

Dig both rooms and walk all the way in first, then arm the deepest room and
retreat outward, because an aggressive resident does not care that you built it.
This block cuts the `warren` exit from your workroom, steps through it, then cuts
`deeper` and steps through that:

```text
@dig The Warren Mouth = warren, out
warren
@dig The Brood Chamber = deeper, out
deeper
```

Create the matriarch and give her a fighting sheet. She is safe to build here
because `ON_ENTER` fires on arrivals and you are already standing inside:

```text
@create broodmother
@tag broodmother = npc
drop broodmother
@set broodmother/hp = 14
@set broodmother/max_hp = 14
@set broodmother/skill_melee = 12
```

Her one-line faction gate, written as a block so the guard reads plainly. It
still consults `disposition(me, enactor) < 2`, so personal standing can override
faction even here and tribute works on her too:

```text
@set broodmother/on_enter = '''
# on_enter targets the room and the mover is the enactor: key on the arrival, never target is me
if has_tag(enactor, 'player') and tag_value(enactor, 'faction') != 'ratkin' and disposition(me, enactor) < 2:
    start_combat(me, enactor)
'''
```

Step back out to the warren mouth and create its resident with a weaker sheet:

```text
out
@create warren rat
@tag warren rat = npc
drop warren rat
@set warren rat/hp = 8
@set warren rat/max_hp = 8
@set warren rat/skill_melee = 10
```

The offering hook buys standing. The `target is me` guard is not decoration:
`give` fires on every object in the room, and only a gift pressed into the rat's
own hands should count:

```text
@set warren rat/on_receive = '''
if target is me:
    adjust_disposition(me, enactor, 5)
    pose(f'sniffs the offering and settles back, watching {name(enactor)} with something like tolerance.')
'''
```

Finally attach the native brain and retreat to your workroom. `spare_at:2` is
what the offering will later clear, and the `taunt` is the speech it says as it
engages:

```text
@behavior warren rat = aggressive, target_tags:["player"], spare_at:2, attack_chance:1.0, taunt:The rat's eyes go red. It lunges!
out
```

## Try it

Give yourself a fighting sheet and something to sacrifice:

```text
@set me/hp = 12
@set me/max_hp = 12
@set me/skill_melee = 12
@create dead beetle
```

Walk in cold, pay tribute under fire, and get out:

```text
warren
  -> warren rat says, "The rat's eyes go red. It lunges!"
     (you are now in combat)
give dead beetle to warren rat
  -> warren rat sniffs the offering and settles back...
flee
  -> back to your workroom, heart pounding
```

Now the gift does its work. The rat spares you (it is at +5, well past
`spare_at:2`), but the broodmother is a different animal:

```text
warren
  -> nothing moves. consider warren rat: it holds you in the highest regard.
deeper
  -> the broodmother is on you (no taunt, no hesitation: the one-line ON_ENTER gate)
flee
```

Join the family and try her again. The `faction:ratkin` tag makes
`tag_value(enactor, 'faction')` return `ratkin`, so her gate waves you through:

```text
@tag me = faction:ratkin
warren
deeper
  -> she ignores you utterly
```

## Going further

- **Standing decays.** The `disposition_boost` effect (what `fasttalk` uses) is a
  temporary bump. Apply it from `ON_RECEIVE` with
  [`apply_effect`](../reference/softcode.md#fn-apply_effect) instead of the
  permanent `adjust_disposition`, and offerings wear off, so the warren must be
  re-fed.
- **Packs.** `@clone warren rat` copies attributes, tags, and behaviors, so the
  clone is a second aggressive rat. Each clone consults its own disposition, so
  standing is per-rat unless you gate on the faction tag instead.
- **War-cries as alarms.** The taunt is real speech, so a `^*lunges*` listen on a
  nest-mother two rooms over (via a zone master) gives you mobs that call
  reinforcements, which composes with the [Town Watch dispatch](071_guard_response.md).
- **Day-tame, night-wild.** Attach and detach the `aggressive` behavior from the
  [NPC schedule](068_npc_schedule.md)'s clock states, so the warren only hunts
  after dark.
- **Picky prey.** `target_tags:["player", "npc"]` plus the
  [wanderer](060_wandering_npc.md) gives a predator that hunts the scamp too, and
  `spare_at:2` still lets it be tamed.
```
