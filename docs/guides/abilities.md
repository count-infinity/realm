# Abilities as Data

A spell, a combat maneuver, a war shout, a "bless" on the room, a device's
power, a poison dart's prick are the **same mechanism** with different
data. REALM models them as one thing, an **ability**, and treats "spell"
or "skill" as flavors:

```
invoke  ->  gate (known? affordable?)  ->  propagate an event  ->  apply effects
```

An `ability_def` is an ordinary tagged object (the def-object pattern of
[skill_def / class_def / behavior_def](data-driven-rules.md)). Invoking it
fires one propagated `<domain>:<name>` action, so wards, resistances, a
room's rules, and reactions all hook it the usual two-pass way. Nothing in
the mechanism assumes a genre: cost is a **spec** (not hardcoded mana),
eligibility is a **rule**, and effects are a **list of specs** that
parameterize engine primitives and behaviors (the composition model).

## A rally cry is a fireball with different data

That is the whole point, so here they are side by side. Same object type,
same `invoke_ability` pipeline:

```text
# A mage's fireball: mana cost, one victim, fire damage
@create fireball
@tag fireball = ability_def          (or spell_def, the spell flavor)
@set fireball/classes = ["mage"]
@set fireball/cost = {"pool": "mana", "n": 15}
@set fireball/target = victim
@set fireball/effects = [{"type": "damage", "dice": "6d6", "damage_type": "fire", "save": "half"}]

# A captain's rally cry: no mana, twice a day, the whole room, +2 to rolls
@create rally cry
@tag rally cry = ability_def
@set rally cry/cost = {"per_day": 2}
@set rally cry/target = room
@set rally cry/effects = [{"type": "behavior", "behavior_id": "modifier_effect", "params": {"kind": "rallied", "duration": 30, "check_mods": {"all": 2}}}]
```

`cast fireball goblin` and `shout rally cry` run the identical code path;
only the data differs.

## The `ability_def` fields

| field | meaning |
|---|---|
| `target` | `self`, `ally`, `victim`, or `room` (every character present). Default: `victim` if it has a damage effect, else `self`. |
| `cost` | a spec: `{"pool": "mana", "n": 15}` (any [pool](pools.md), e.g. `stamina` or `heat`), or `{"per_day": 2}` (a counter toward a daily cap), or omitted (free). Either may add `"cooldown": <beats>` (below). Legacy `mana = 15` is sugar for the mana pool. |
| `aliases` | more verbs that run an `ability_def` typed as a command (below). |
| `hostile` | true for a harmful ability with no damage effect (a trip, a disarm), so it starts a fight. |
| `fail_msg` | what the actor sees when a `check` effect fails; `{target:the}` works. |
| `requires_weapon` | a damage type the actor's wielded weapon must deal (`piercing` for a backstab). |
| `target_unaware` / `target_fighting` | the target must not be fighting (a backstab) / must be (a rescue). |
| `effects` | a list of effect specs (below). |
| `classes` / `level` / `skill_req` | eligibility. A player must qualify; NPCs always pass (their repertoire is whatever behavior granted it). `skill_req = {"skill": "melee", "min": 12}` gates a maneuver on skill. |
| `on_invoke` / `on_cast` | bespoke softcode, run as the def, for anything the specs do not cover. |

### Costs are pools

A `pool` cost is a [pool](pools.md) `spend`: all or nothing. A down pool
(mana, stamina) must hold the whole cost and drops by it; an up pool (heat,
strain, stress) rises by it and refuses a cost that would pass its max.
Either way a cost the caster cannot pay blocks the ability with "You don't
have the <pool>." and nothing is spent. Paying fires the pool's `ON_POOL`
hook (and `ON_SPENT` when it empties or fills), so a ship can vent heat or
a caster can faint from the hook.

```text
# A gun deck that runs hot: three volleys from cold, then it must cool.
@set ship/pools = {"heat": {"direction": "up"}}
@set ship/heat = 0
@set ship/max_heat = 9
@set volley/cost = {"pool": "heat", "n": 3}
```

A caster with no such pool is told "You have no heat to spend."; an NPC
without it pays nothing.

### Cooldowns

`"cooldown": <beats>` in a cost, alone or beside a pool cost, keeps the
actor from using the ability again for that many world beats (`WORLD_BEAT`
seconds each). A use too soon is refused with "You are not ready to <name>
again yet." and pays nothing. The ready time is kept per ability on the
actor, in its `ability_ready` attribute, in wall-clock seconds, so it
survives a restart.

```text
@set kick/cost = {"cooldown": 2}
@set war cry/cost = {"pool": "move", "n": 10, "cooldown": 5}
```

### Effect specs

Each effect is a spec parameterizing an engine primitive or behavior, so
the common shapes need no softcode:

| `type` | does |
|---|---|
| `damage` | `dice`, `damage_type`, optional `save`. Fires the shared, interceptable damage event (below), routed through the ruleset's resistances/DR. |
| `heal` | `dice`, capped at `max_hp`. |
| `behavior` | attaches a behavior (`behavior_id` + `params`): bless, curse, poison, rally. Optional `save`. This is where a `modifier_effect` (+2 / -2), a `damage_over_time`, or any timed effect rides in. |
| `softcode` | a `code` body for the bespoke case, run as the def with the target bound. |
| `check` | `skill`, optional `modifier` and `on_fail` (`stop`, the default). Rolls the actor's skill through `check()` once; when it fails, the effects after it are not applied, the actor sees `fail_msg`, and the room sees them fail. This is what makes a skill miss. Effects before it apply either way. |
| `weapon_damage` | the actor's wielded weapon's damage dice times `multiplier` + `per_level` × the actor's level, of the weapon's damage type (a backstab). |
| `tag` | adds `tag` to the target (a trip leaves it `resting`). |
| `rescue` | turns everyone fighting the target (an ally) on the actor. |
| `disarm` | knocks the target's wielded weapon to the floor. |
| `charm` | makes the target the actor's companion for `duration` + `per_level` × the actor's level beats (the `companions` feature's `charmed` effect; `level_check`, `turns_hostile`, optional `save`). Nothing without `companions`. See [Pets, Charm and Mounts](companions.md#charm). |

Damage `dice` may say `{level}` for the actor's level: a kick's
`"1d{level}"` grows with the kicker.

A `save` of `half` halves damage; `negates` cancels damage or shrugs off
the effect. The saving throw is the game system's policy (`saving_throw`),
rolled once per target: Merc uses the Diku level differential; systems
with no save concept take the full effect.

## Damage is one interceptable event

Every damage effect (and every combat swing, and softcode that opts in)
funnels through one `combat:on_damage` event before the ruleset applies
resistances. So a single behavior nerfs a fireball, a sword, and a trap
alike:

```text
# A sanctuary room that halves all incoming damage — spells included.
@set temple/on_check = if atype == 'combat:on_damage': set_adata('damage', adata('damage') // 2)
```

(Softcode `damage()` deals damage directly and does **not** fire the event
by default: a builder who calls it means it. The event is the path
abilities and combat use.)

## Invoking

- **Spells:** the `cast` command and `spells` list ([Spells as
  Data](spells.md)) are the spell-flavored entry: an `ability_def` tagged
  `spell_def`, invoked with the `cast` verb and the `spell:` event domain.
- **Abilities as commands:** a player types an `ability_def`'s name (or
  one of its `aliases`) as a verb, with the target after it: `kick fido`.
  This happens only when no command and no exit matches, and only for an
  ability the player may use (class, level, skill); otherwise the line
  goes on to softcode `$`-commands and "Huh?" as any unknown verb does.
  Spells keep `cast`. `abilities` (`ab`) lists what a character can use,
  with its cost and how long until it is ready.
- **Items:** `quaff`, `recite`, `zap` and `brandish` invoke the spells an
  item names, free ([The Character Sheet](character-sheet.md#consumables)).
- **Everything else:** `invoke_ability(actor, ability_def, target, verb=...,
  free=, level=)` is the generic entry a custom command or behavior calls.
  An NPC caster behavior, a shout command, or a device's `use` all route
  through it.

### A class skill, end to end

The Merc kick, as the merc-classic pack ships it:

```text
@create kick
@tag kick = ability_def
@set kick/classes = ["warrior", "barbarian"]
@set kick/target = victim
@set kick/hostile = True
@set kick/cost = {"cooldown": 2}
@set kick/fail_msg = Your kick misses {target:the}.
@set kick/effects = [{"type": "check", "skill": "kick"}, {"type": "damage", "dice": "1d{level}", "damage_type": "bludgeoning", "magical": False}]
```

A warrior types `kick fido`: the kick skill is rolled; on a success the
fido takes 1 to the warrior's level in damage, and either way the fight is
on and the kick waits two beats.

Because an `ability_def` is a plain object, the whole loop is
softcode-first: define abilities in-game, `@export` them, and ship them in
a [content pack](content-packs.md). Authoring a harmful ability (a damage
or harmful effect) is builder-gated by the [harm model](../design/sandbox-security.md);
a purely beneficial one (a heal, a bless) is not.
