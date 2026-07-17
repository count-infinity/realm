# 165. Prototype library

> Checklist item 165 — [now] — *prototype attrs + create_obj, inheritance-by-merge, @clone*

**What you'll build:** a builder's *rack* of item prototypes — data
dicts describing objects that don't exist yet — with a `mint` verb that
spawns any of them on demand, and prototypes that **inherit** from one
another so a greatsword is "a sword, but heavier-hitting" in one line.
(Builder permission: you build the rack with `@create`/`@set`.)

**Concepts:** prototypes as attributes, `create_obj()` the spawner
vocabulary, **inheritance by dict-merge** (`{**base, **override}`),
`@clone` as the industrialized whole-library copy.

Builds on the [vending machine](002_vending_machine.md), which minted
one flat prototype per selection. This goes deeper: a *library* of
named prototypes that extend each other.

## How it works

**A prototype is data, minting is `create_obj`.** The
[vending machine](002_vending_machine.md) proved the seed idea — a JSON
dict in an `item_<name>` attribute, spawned with `create_obj(name)`.
Here we industrialize it: one **rack** object holds many `proto_<name>`
dicts, and a single `mint` verb spawns any of them, stamping the
prototype's fields onto the fresh object.

**Inheritance is a dict-merge, not a parent link.** A greatsword shares
most of a sword's stats. Rather than repeat them, its prototype names a
`parent` and overrides only what differs; `mint` reads the parent dict,
lays the child on top with `{**base, **child}`, and the merged spec is
what gets minted. Override `damage`, inherit `weight` — the deeper
story the vending machine never told.

> **Why merge and not `@parent`?** REALM objects *have* a `@parent`
> field, but attribute reads (`get_attr`) do **not** currently fall
> through to it — the link is stored, shown in `@examine`, and honored
> by the persistence/worldio layer, but a child does not inherit a
> parent's *attribute values* at read time. So prototype inheritance is
> done in data, by merge. See **Engine gaps**.

**The whole library is clonable.** Because the rack is just attributes,
`@clone prototype rack = spare rack` duplicates every prototype *and*
the `mint` verb — a second kiosk in one command. Objects are data;
duplicating data is a builtin.

## Build it

The rack, and two prototypes — a base and a child that inherits its
`weight`:

```text
@create prototype rack
drop prototype rack
@set prototype rack/proto_sword = {"name": "a sword", "damage": 3, "weight": 2}
@set prototype rack/proto_greatsword = {"parent": "sword", "name": "a greatsword", "damage": 6}
```

The `mint` verb — resolve the prototype, merge over its parent (if any),
spawn, and stamp the merged stats. Every branch is a guard; the final
tuple commits only when a spec was found:

```text
@set prototype rack/cmd_mint = $mint *: key = 'proto_' + trim(arg0); p = get_attr(me, key); base = get_attr(me, 'proto_' + str(p.get('parent')), {}) if p and p.get('parent') else {}; spec = {**base, **p} if p else None; o = create_obj(spec['name'], tags=['thing'], location=enactor) if spec else None; (set_attr(o, 'damage', spec.get('damage', 1)), set_attr(o, 'weight', spec.get('weight', 1)), pemit(enactor, 'Minted ' + spec['name'] + ': dmg ' + str(spec.get('damage')) + ', wt ' + str(spec.get('weight')) + '.')) if o else pemit(enactor, 'No such prototype.')
```

## Try it

```text
mint sword          -> Minted a sword: dmg 3, wt 2.
mint greatsword     -> Minted a greatsword: dmg 6, wt 2.
mint dagger         -> No such prototype.
```

The greatsword reads `dmg 6` (its own override) and `wt 2` (**inherited**
from the sword prototype — it never named a weight). Adding a whole new
family is one `@set`; a `proto_warhammer` with `"parent": "greatsword"`
inherits the greatsword's inheritance in turn.

Copy the entire catalogue to open a second armory:

```text
@clone prototype rack = spare rack
```

The clone carries every `proto_*` dict and the `mint` verb — edit only
the copy's data to diverge the two shops.

## Engine gaps

- `@parent` sets an inheritance link that **attribute reads do not
  traverse** — `get_attr(child, 'x')` returns the child's own value or
  the default, never the parent's. Prototype inheritance therefore lives
  in data (dict-merge), which is what this tutorial teaches. A read-time
  parent fall-through would let `@parent` back this natively.
- `create_obj()` takes `name`, `tags`, and `location` but not a
  `parent`; and (as the [vending machine](002_vending_machine.md) notes)
  softcode can't write the render-`description` slot, so minted items are
  name-and-attributes until a builder `@desc`es them.

## Going further

- **Deeper chains:** a three-level `warhammer → greatsword → sword`
  works because each `mint` merges only one level up — precompute the
  full chain in a `resolve` function attribute if you want multi-level
  inheritance in one read.
- **Tag inheritance too:** put a `"tags"` list in each prototype and
  merge/extend it, so `proto_magic_sword` adds `["glowing"]` on top of
  the base tags.
- **Spawn tables:** a `proto_loot` whose value is a list of prototype
  names lets one `mint loot` roll `rand()` and mint a random child — the
  loot-crate pattern over your own catalogue.
- **Ship it:** the rack is a zone object like any other, so `@export`
  the zone it sits in and the whole prototype library travels with the
  area file (see [batchcode areas](166_batchcode_areas.md)).
