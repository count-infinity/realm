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

Plus the usual read functions (`get_attr`, `has_tag`, `name`, the dice
primitives…) for conditions.

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

The `mod` / `set_adata` reduction is applied to the raw damage *before* a
combat ruleset's own damage-resistance and type multipliers, so it
composes with them (an `on_check` `mod(-3)` and a native DR of 2 both
apply). It's sandboxed softcode under the usual limits — keep it small and
cheap, since it fires for every action you participate in.
