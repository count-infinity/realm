# Spells as Data

A spell in REALM is **not a framework** — it is one ordinary two-pass
propagated action (`spell:<name>`) whose payload is built from a
`spell_def` object, the same def-object pattern as `skill_def` /
`class_def` / `behavior_def` (see [Skills & Classes as
Data](data-driven-rules.md)). The propagation engine already supplies
everything "magical" about magic:

- **Check pass** (caster first, then room, bystanders, target): wards
  and softcode `on_check` may `block` (a counterspell, an anti-magic
  room) or *modify* the payload — `set_adata('damage', ...)` for magic
  resistance, `set_adata('mana_cost', ...)` for a mana-damping field.
- **Apply** (between the passes): requirements are *announced* in the
  payload but **enforced here, after every check-pass modification** —
  the engine's "insufficient funds reads exactly like a ward veto"
  convention. Mana is spent, the saving throw rolls, the effect lands.
- **React pass**: `ON_*` hooks and messages fire; a damaging spell is
  tagged `hostile`, so the combat manager's hostile observer
  auto-initiates combat — the fireball WAS your turn.

## Defining a spell

A `spell_def` is declarative for the common shapes:

```
@create fireball
@tag fireball = spell_def
@set fireball/level = 15
@set fireball/mana = 15
@set fireball/classes = ["mage"]
@set fireball/target = victim
@set fireball/damage_dice = 6d6
@set fireball/damage_type = fire
@set fireball/save = half
```

| attr | meaning |
|---|---|
| `level`, `mana` | minimum caster level; mana cost (modifiable in-flight) |
| `classes` | who may learn it (omit = any class; NPCs always pass) |
| `target` | `victim` (default when damaging), `ally` (them or you), `self` |
| `damage_dice`, `damage_type` | typed damage, dealt **through the active ruleset's `apply_damage`** — so `resistances` multipliers and DR fire with no spell-side code |
| `save` | `half`, `negates`, or `none` — rolled via the game system's `saving_throw` (Merc: the Diku level-differential d100; systems with no save concept take full effect) |
| `heal_dice` | HP restored, capped at `max_hp` |
| `effect` | a behavior to attach: `{"behavior_id": "modifier_effect", "params": {...}}` — bless, curse, blindness, and poison are just the shipped timed-effect behaviors as spell data |
| `hostile` | mark a non-damaging spell (curse) as combat-starting |
| `on_cast` | softcode for bespoke effects, run **as the spell_def** (its owner's authority), with the action bound (`adata`, `target`, ...) |

Then `cast fireball goblin` (or `cast 'magic missile' goblin` —
Diku-style quoting for multiword names). `spells` lists what your class
and level allow. Defensive spells with no target default to you;
offensive ones default to your current combat opponent.

Because a spell_def is a plain object, the whole loop is softcode-first:
define spells in-game, `@export` them, ship them as a
[content pack](content-packs.md).

## The merc-classic pack

`@pack import merc-classic` loads the classic Diku spellbook — 23
spells: the mage damage line (magic missile → acid blast), the cleric
line (cause light, flamestrike, harm, the cures, heal), the affects
(bless, curse, blindness, poison — riding the shipped timed-effect
behaviors), and the five breath weapons. Numbers are ROM-flavored;
edit the defs in-game like any object.

## NPC casters

The `caster` behavior is the Diku `spec_cast_*` / `spec_breath_*` family
as one parameterized behavior:

```
@behavior guildmaster = caster, spells:["chill touch", "fireball"], chance:0.5
```

On its combat tick it picks a spell from its list and casts **through
the same pipeline players use** — NPC spells are ward-able, save-able,
and resistance-checked identically. The [ROM importer](../development/rom-import.md)
attaches it automatically to `spec_cast_*`/`spec_breath_*` mobs with each
proc's canonical spell list; import `merc-classic` alongside a converted
area and its guildmasters cast.

## Interception examples

All of this is the ordinary [ward machinery](interception.md) — nothing
below is spell-specific engine code:

```python
# An anti-magic cell (softcode on_check on the room):
if atype().startswith('spell:'):
    block('The magic gutters and dies here.')

# Magic resistance (on_check on a demon):
if atype().startswith('spell:'):
    set_adata('damage', adata('damage') // 2)

# A mana well (on_check on a shrine's room): all magic is free
if atype().startswith('spell:'):
    set_adata('mana_cost', 0)
```

Enforcement reads the **final** values, so all of these compose — and a
blocked cast spends nothing.

## Typed damage from softcode

`damage(target, amount, type)` routes through the active ruleset when a
type is given, so scripted effects respect immunities too:

```
damage(enactor, 12, 'fire')     # a fire-immune mob takes 0
damage(enactor, 3)              # untyped: raw HP, as before
```
