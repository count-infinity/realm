# Templates: `@parent` inheritance

Three ways an object acquires capability in REALM, and the boundary
between them:

| | What it is | Who authors it | Examples |
|---|---|---|---|
| **Tag** | An engine-recognized boolean the built-in commands respect | The engine | `closed`, `locked`, `container`, `npc` |
| **Behavior** | Stateful, ticking, lifecycle-bearing machinery, parameterized and engine-registered | The engine (Python) | `script_ticker`, `spawner`, `zone_reset` |
| **Template** | A reusable bundle of softcode (hooks, `$`-commands, defaults) written once and adopted by many objects via `@parent` | **A builder, in-game** | a LockableDoor's mirror hooks, a Shopfront's `$browse`, an AlarmPanel |

Tags are single facts, behaviors are engine machinery, and templates are
the builder-extensible layer: the way capability is *written once in
softcode and reused*, the same code-as-data move as `skill_def`.

## The model

A child object **reads through** its parent chain for db attributes it
does not have itself. That covers plain values (`price`, `locked_msg`),
`ON_<EVENT>` hook scripts, `on_check` wards, and `$`-command /
`^`-listen triggers (trigger gathering reads the merged view, so a
template's commands work for players standing near any child).

- **Child shadows parent.** The child's own attribute always wins.
  Deleting the child's copy re-exposes the template's value, which is
  how you reset an instance to template.
- **Copy-on-write.** Reads fall through; writes always land on the
  child. `incr('stock')` on a child whose template holds `stock = 5`
  reads 5 and writes 6 to the child; the template is never mutated.
  Template values are *defaults*, instance state is per-child.
- **Chains.** Parents may have parents (depth-capped at 8); cycles are
  refused at `@parent` time.
- **Inherited code runs as the child**, with the child's owner's
  authority. A template contributes code, never its own authority
  (contrast `call()`, which runs a routine AS the target object; the two
  compose).

## What never inherits

- **Tags** — instance state (one door being `closed` must not close its
  siblings) and a security boundary (role tags must never arrive by
  inheritance).
- **Behaviors** — stateful machinery attaches per object.
- **Engine fields** — name, description, location, owner, locks.
- **`PROTECTED_ATTRS`** (`password`, `keyid`) — a unique identity cannot
  be inherited by definition.
- **`secret`-flagged template attrs and the `attr_flags` table** — a
  template's internals stay on the template; a child's flag lookups are
  its own.

## The gate

`@parent child = template` requires **control of both** objects.
Adopting a template runs its code with your object's authority, so the
adoption is the consent moment. (A Penn-style `@lock/parent` opt-in for
shared templates is backlogged; Penn's rule for reference: control the
parent, or it is LINK_OK and you pass its `@lock/parent`.)

## The exemplar workflow (tags and behaviors)

Since only db attributes inherit, an object that needs tags or behaviors
gets them per instance. The idiom is one **exemplar**:

1. Build the template: hooks and defaults, as attributes.
2. Build ONE exemplar child: `@parent` it, add its tags, attach its
   behaviors.
3. `@clone` the exemplar. Clones copy tags and behaviors AND keep the
   parent link, so every copy is fully kitted and live-linked.

Template = shared code. Exemplar = identity. `@clone` = replication.
Editing the template fixes every child on the map at once.

## Mechanics for the curious

`AttributeProxy.get`/`__contains__` fall through the chain on a miss
(one `parent is None` check for the unparented common case);
`db.all()` remains own-attrs-only so persistence, export, `_snapshot`
diffs, and `@clone` never bake inherited values into instances;
`db.merged()` is the combined view used by trigger gathering and
`@examine` (which shows an "Inherited (from X)" section). worldio
exports the parent reference; a fresh-id import remaps in-file parents
to the copies and resolves out-of-file parents against the live world,
so exporting five doors without their template keeps them linked to the
shared one.

## See also

- [Lockable door tutorial](../showcase/025_lockable_door.md), whose
  mirror hooks are the motivating template.
- [World Management](../guides/world-management.md) for the builder-facing
  summary.
- [Object identity](object-identity.md) for `#id`/`$keyid` referencing.
