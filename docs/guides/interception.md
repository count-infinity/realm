# How-To: Wards, Resistance & Armor (the `on_check` hook)

Most softcode **reacts** to things after they happen (`^listen`,
`ON_<EVENT>`). Sometimes you need to **intercept** — veto an incoming
action, or change it before it lands: a ward that blocks magic, fire
immunity, armor that soaks damage, a counterspell. The `on_check`
attribute does that, entirely in data.

An object's `on_check` softcode runs during the propagation **check
pass** — while an action targeting it is still being decided — with the
power a hardcoded behavior has there:

```text
@set idol/on_check = if has_atag('magic'): block('the idol wards itself')
```

Now any magic-tagged action against the idol is vetoed.

## What `on_check` can see and do

The script runs with the in-flight action bound in:

| name | is |
|---|---|
| `atype` | the action's type string (`combat:on_damage`, `event:scry`…) |
| `actor` | who is acting |
| `target` | what the action targets |
| `me` | the object whose `on_check` this is (the ward/armor/effect) |
| `has_atag(tag)` | does the action carry this tag? |
| `adata(key, default)` | read the action's payload (e.g. `adata('damage')`) |

…and it can change the outcome:

| verb | effect |
|---|---|
| `block(reason)` | **veto** the action (immunity, ward, counterspell) |
| `mod(value)` | add a modifier (e.g. `mod(-3)` — armor soaking damage) |
| `set_adata(key, value)` | rewrite the payload (e.g. halve `damage`) |

Plus every **read-only** softcode function for conditions: reads
(`get_attr`, `V`, `has_tag`, `name`, `controls`…), dice and checks (`roll`,
`check_roll`, `skill`, `check`…), text and list helpers. These are the
functions marked read-only in the registry; the
[softcode reference](../reference/softcode.md#where-softcode-runs-profiles)
lists which contexts see which. A game's own native function is callable
here only if it was registered with `readonly=True`.

## Examples

```text
# A ward: no magic works in this room.
@set sanctum/on_check = if has_atag('magic'): block('magic is smothered here')

# Fire immunity on a creature.
@set salamander/on_check = if adata('damage_types', {}).get('fire'): block('immune to fire')

# Armor: soak damage equal to my `armor` attribute.
@set knight/on_check = if atype == 'combat:on_damage': mod(-get_attr(me, 'armor'))

# A damage cap: nothing hits me for more than 5.
@set boss/on_check = if adata('damage', 0) > 5: set_adata('damage', 5)
```

Combat honors all of these: a `block()` prevents the hit's damage
entirely, and `mod()` / `set_adata('damage', …)` reduce it.

## The contract: `on_check` decides, it doesn't act

`on_check` runs in the *decision* pass, so it is **veto/modify only** — and
that's enforced structurally, not by convention. The script runs against a
restricted, **read-only** namespace: the reads/queries/dice above plus
`block`/`mod`/`set_adata`. The world-mutating verbs (`say`, `pemit`,
`damage`, `create_obj`, `set_attr`, `teleport_obj`, …) simply **aren't
there** — calling one is an error, not a silent side effect. So a ward on
the veto path can allow/deny/adjust the action itself, but it can't spam,
mutate, or persist world state mid-decision. Reacting to an action belongs
in `on_react` or an `ON_<EVENT>` trigger, which run *after* it resolves.

When a ward calls a real function it may not use here, the error the
owner sees says so: `pemit() exists but changes the world, so on_check
cannot call it; do that in an ON_<EVENT> reaction instead`. The ward then
fails closed, like any ward that errors (see
[When a ward breaks](../reference/softcode.md#when-a-ward-breaks)).

The `mod` / `set_adata` reduction is applied to the raw damage *before* a
combat ruleset's own damage-resistance and type multipliers, so it
composes with them (an `on_check` `mod(-3)` and a native DR of 2 both
apply). It's sandboxed softcode under the usual limits — keep it small and
cheap, since it fires for every action you participate in.

### Where soak sits

A blow that goes through the damage event is reduced in this order:

1. **Wards** (`on_check` on the target, its room and the rest of the
   propagation chain): `block()` stops it, `mod()` and
   `set_adata('damage', …)` lower it.
2. **Resistances**: the target's `resistances` map scales each damage type.
3. **The ruleset's own armor**: GURPS DR, the Merc and D20 rules, or your
   ruleset's `apply_damage`.
4. **Soak**, last: the damage lands in the target's [damage pool](pools.md)
   with soak, and each pool the harm reaches subtracts its `soak_attr`.
   Shields with no soak over a hull whose `armor` is 2 lose the full spill,
   then the hull loses the rest less 2.

Swings and ability or spell damage take all four steps. Softcode
`damage()` and damage over time skip the event and the ruleset: they run
steps 2 and 4 only.

## Who gets an `on_check`

The `on_check` *attribute* is consulted only on an action's
**participants** — the actor, the target, and the room. A bystander
object standing in the room never has its attribute read: participants
decide, bystanders react. A bystander joins the decision pass by carrying
an **attached behavior**, and that logic can itself be data — a
[`behavior_def`](data-driven-rules.md#behaviors-as-data) object whose
`on_check` runs with this same restricted namespace, as the carrying
object. Attachment (`@behavior`, builder-gated) is the authority line
that keeps a player's dropped junk from vetoing the room's actions.
Item [252](../showcase/252_custom_action.md) demonstrates both surfaces.
