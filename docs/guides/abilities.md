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
| `cost` | a spec: `{"pool": "mana", "n": 15}` (any attr pool, e.g. `stamina`), or `{"per_day": 2}` (a counter toward a daily cap), or omitted (free). Legacy `mana = 15` is sugar for the mana pool. |
| `effects` | a list of effect specs (below). |
| `classes` / `level` / `skill_req` | eligibility. A player must qualify; NPCs always pass (their repertoire is whatever behavior granted it). `skill_req = {"skill": "melee", "min": 12}` gates a maneuver on skill. |
| `on_invoke` / `on_cast` | bespoke softcode, run as the def, for anything the specs do not cover. |

### Effect specs

Each effect is a spec parameterizing an engine primitive or behavior, so
the common shapes need no softcode:

| `type` | does |
|---|---|
| `damage` | `dice`, `damage_type`, optional `save`. Fires the shared, interceptable damage event (below), routed through the ruleset's resistances/DR. |
| `heal` | `dice`, capped at `max_hp`. |
| `behavior` | attaches a behavior (`behavior_id` + `params`): bless, curse, poison, rally. Optional `save`. This is where a `modifier_effect` (+2 / -2), a `damage_over_time`, or any timed effect rides in. |
| `softcode` | a `code` body for the bespoke case, run as the def with the target bound. |

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
- **Everything else:** `invoke_ability(actor, ability_def, target, verb=...)`
  is the generic entry a custom command or behavior calls. An NPC caster
  behavior, a shout command, or a device's `use` all route through it.

Because an `ability_def` is a plain object, the whole loop is
softcode-first: define abilities in-game, `@export` them, and ship them in
a [content pack](content-packs.md). Authoring a harmful ability (a damage
or harmful effect) is builder-gated by the [harm model](../design/sandbox-security.md);
a purely beneficial one (a heal, a bless) is not.
