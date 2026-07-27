# 165. Prototype library

> Checklist item 165 ([now]): *prototype attrs, create_obj minting, inheritance-by-merge, @clone*

**What you'll build:** a builder's *rack* of item prototypes, which are data
dicts describing objects that do not exist yet, with a `mint` verb that spawns
any of them on demand, and prototypes that **inherit** from one another so a
greatsword is "a sword, but heavier-hitting" in one line. You build the rack
with `@create` and `@set`, so builder permission is enough.

**Concepts:** prototypes as attributes, [`create_obj`](../reference/softcode.md#fn-create_obj)
as the spawner vocabulary, **inheritance by dict-merge** (`{**base, **override}`),
and [`@clone`](../guides/world-management.md) as the whole-library copy.

This builds on the [vending machine](002_vending_machine.md), which minted one
flat prototype per selection. Here we go deeper into a *library* of named
prototypes that extend each other.

## How it works

The finished rack is a single object carrying two kinds of attribute: several
`proto_<name>` dicts that describe items, and one `mint` verb that reads a
named dict, folds in whatever it inherits, and spawns the real object. This
section explains why a prototype is stored as data, how one prototype inherits
from another, and why copying the whole library is a single builtin.

### Why a prototype is data, not an object

A prototype needs a name and a few stats, nothing more, because the object it
describes does not exist yet. Store each as a JSON dict in a `proto_<name>`
attribute (`@set` parses JSON, so the dict stores as a real dict), and the rack
can mint the object on demand with
[`create_obj`](../reference/softcode.md#fn-create_obj). The
[vending machine](002_vending_machine.md) proved the seed idea with one flat
prototype per selection; a rack simply holds many of them and a single verb
that spawns any one.

### How one prototype inherits from another

A greatsword shares most of a sword's stats, so rather than repeat them its
prototype names a `parent` and overrides only what differs. Because a prototype
is *data* rather than an object, this inheritance is expressed in data: `mint`
reads the parent dict, lays the child on top with `{**base, **child}` so the
child's keys win, and the merged spec is what gets minted. Override `damage`,
inherit `weight`, in one line.

This data merge is distinct from REALM's object-level `@parent`, which links two
real objects so that [`get_attr`](../reference/softcode.md#fn-get_attr) on a
child reads through to its template's attributes on a miss. A prototype has no
object to link until it is minted, which is exactly why the merge happens at the
data layer. See **Engine gaps** for the one place the two ideas do not yet meet.

### Why the whole library is clonable

Because the rack is nothing but attributes, `@clone prototype rack = spare rack`
duplicates every prototype dict *and* the `mint` verb, standing up a second
kiosk in one command. Objects are data, and duplicating data is a builtin.

## Build it

First create the rack itself and drop it in the room:

```text
@create prototype rack
drop prototype rack
```

Now the two prototypes: a base sword and a child greatsword that names the
sword as its `parent` and overrides only `damage`. These are data literals, so
they stay single-line `@set` (a dict must store as a real dict for `.get()` to
read it):

```text
@set prototype rack/proto_sword = {"name": "a sword", "damage": 3, "weight": 2}
@set prototype rack/proto_greatsword = {"parent": "sword", "name": "a greatsword", "damage": 6}
```

The `mint` verb resolves the named prototype, merges it over its parent when it
has one, spawns the object with [`create_obj`](../reference/softcode.md#fn-create_obj),
and stamps the merged stats with [`set_attr`](../reference/softcode.md#fn-set_attr).
It is a script with control flow, so it is a `'''` heredoc block (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).
The `$mint *` trigger captures the selection as `arg0`, which
[`trim`](../reference/softcode.md#fn-trim) tidies into a `proto_<name>` key, and
[`V`](../reference/softcode.md#fn-v) reads that dict off the rack:

```text
@set prototype rack/cmd_mint = '''
$mint *:
key = 'proto_' + trim(arg0)
p = V(key)
if p:
    base = V('proto_' + str(p.get('parent')), {}) if p.get('parent') else {}
    spec = {**base, **p}  # child p overlays base, so overrides win
    o = create_obj(spec['name'], tags=['thing'], location=enactor)
    set_attr(o, 'damage', spec.get('damage', 1))
    set_attr(o, 'weight', spec.get('weight', 1))
    pemit(enactor, f"Minted {spec['name']}: dmg {spec.get('damage')}, wt {spec.get('weight')}.")
else:
    pemit(enactor, 'No such prototype.')
'''
```

`$mint` is a `$`-command, which dispatches only for the object it is typed at,
so it needs no `target` guard the way a room-wide `ON_<EVENT>` hook would.

## Try it

```text
> mint sword
  Minted a sword: dmg 3, wt 2.
> mint greatsword
  Minted a greatsword: dmg 6, wt 2.
> mint dagger
  No such prototype.
```

The greatsword reads `dmg 6` from its own override and `wt 2` inherited from the
sword prototype, which it never named a weight for. Adding a whole new family is
one `@set`: a `proto_warhammer` with `"parent": "greatsword"` inherits the
greatsword's inheritance in turn.

Copy the entire catalogue to open a second armory:

```text
> @clone prototype rack = spare rack
  Cloned prototype rack → spare rack (#a1b2c3d4).
```

The clone carries every `proto_*` dict and the `mint` verb, so edit only the
copy's data to diverge the two shops.

## Engine gaps

- [`create_obj`](../reference/softcode.md#fn-create_obj) accepts `name`, `tags`,
  `location`, `description`, and `attrs`, but not a `parent`, so a minted object
  is born without an object-level `@parent` link. A builder who wants the live
  object to read through to a template `@parent`s it after minting. Adding a
  `parent` keyword to `create_obj` would let `mint` set that link at birth.

## Going further

- **Deeper chains:** a three-level `warhammer` to `greatsword` to `sword` works
  because each `mint` merges one level up; precompute the full chain in a
  `resolve` function attribute for multi-level inheritance in a single read.
- **Tag inheritance too:** put a `"tags"` list in each prototype and merge or
  extend it, so a `proto_magic_sword` adds `["glowing"]` on top of the base tags.
- **Give minted items a look:** pass `description=` to
  [`create_obj`](../reference/softcode.md#fn-create_obj) from a `desc` field in
  the prototype, the way the [vending machine](002_vending_machine.md) dresses
  its stock, so a fresh sword reads back a description rather than a bare name.
- **Spawn tables:** a `proto_loot` whose value is a list of prototype names lets
  one `mint loot` roll `rand()` and mint a random child, the loot-crate pattern
  over your own catalogue.
- **Ship it:** the rack is a zone object like any other, so `@export` the zone
  it sits in and the whole prototype library travels with the area file (see
  [batchcode areas](166_batchcode_areas.md)).
