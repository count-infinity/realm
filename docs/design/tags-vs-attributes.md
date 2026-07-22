# Tags vs Attributes — the object-state rule

REALM marks object state two ways, and they are **not** interchangeable. Pick by
one question: *does the marker carry a value?*

> **Tag** — a boolean fact about what an object **is**, or **is currently**
> (categorical membership / state). `has_tag('container')`, `worn`, `closed`,
> `hidden`, `npc`, `dark`.
>
> **Attribute** — **data** the object *has* (a value). `db.hp`, `db.key_id`,
> `db.slot`, `db.capacity`, `db.destination`, `db.description`.

The line is *value or no value*. "Is this a container?" is a yes/no fact → tag.
"Which key opens it?" carries an id → attribute. A locked door is a **`locked`
tag** (state) plus a **`db.key_id`** (data): the same door, split correctly.

## Why it matters (and isn't just taste)

- **Consistency is legibility.** A builder should never have to remember whether
  a capability wants `@tag x = foo` or `@set x/foo = true`. One rule, applied
  everywhere, means the right spelling is always guessable.
- **Tags are the capability vocabulary the engine already reads.** `worn`,
  `wielded`, `exit`, `closed`, `invisible`, `anchored`, `ephemeral`, `npc`,
  `player`, `quelled` are all tags. A boolean capability stored as an attribute
  is an outlier the next reader has to special-case.
- **Both are equally queryable.** `find_objects(tag=...)` and
  `find_objects(attr=..., value=...)` both exist, so this is *not* a
  performance/findability argument — it's purely about a single, predictable
  mental model.

The one honest cost: tags share a flat global namespace, so every engine tag
permanently claims a common word. Reserve tags for genuine engine-read
capabilities; don't tag-ify a builder's private bookkeeping (that's what
attributes and `attr_flags` are for).

## Worked example: the `container` migration (2026-07-20)

"Container-ness" — *can this be opened/closed and hold contents?* — is a boolean
fact, so it is a **tag**. It used to be `db.container = True`, which was doubly
wrong: an outlier attribute, **and** internally inconsistent (`ships.py` already
tagged `container` while the corpse code set the attribute, and the open/close
gate read only the attribute — so the tag silently did nothing). Migrated whole:

- `open`/`close` gate reads `has_tag('container')` / `has_tag('closable')`
  (`core/verbs.py`); corpses `add_tag('container')` (`combat/manager.py`).
- Builders mark one with **`@tag chest = container`** (which the `@tag` help text
  already advertised — now it is finally true), never `@set`.
- The ~18 container tutorials (items 12–24, 212, 222) and their content packs
  were converted; the read-from-docs tests exercise the tag spelling.

## Current inventory

**Capability/state as tags (correct):** `container`, `closable`, `closed`,
`locked`, `exit`, `worn`, `wielded`, `hidden`, `invisible`, `see_invisible`,
`dark`, `light`, `nightvision`, `npc`, `player`, `anchored`, `ephemeral`,
`quelled`, `no_group`, `wearable`, plus the role tags
(`god`/`admin`/`builder`/…) and zone/identity tags.

**Data as attributes (correct):** `hp`/`max_hp`, `key_id`, `unlocks`, `slot`,
`capacity`, `weight_limit`, `grants_tags`, `destination`, `dest_resolver`,
`description`, `locked_msg`, `lock_skill`, `lock_difficulty`, `credits`,
`check_mods`, `voice_as`, `home`, the script bodies (`on_check`/`on_tick`/
`cmd_*`), and per-object bookkeeping.

**`locked` completes the set (2026-07-20).** A locked door is now a `locked`
*tag* (state) plus `db.key_id` / `db.locked_msg` / `db.lock_skill` (data) — the
clean split, and it finally matches its sibling `closed`, which was always a
tag. Softcode toggles it with `add_tag`/`remove_tag` (as tutorials 016/025 now
do). No live-DB migration was needed (pre-production); a game with saved
`db.locked` state would need a one-time boot migration reading the old attr into
the tag, since the door-state persists.

## See also

- [Action Category Tags](action-tags.md) — the *other* tag vocabulary
  (propagated-action categories: `movement`, `magic`, …), a separate axis.
- `realm/core/attrflags.py` — per-attribute flags (`secret`/`visual`/`safe`/
  `no_clone`), the third marker kind: metadata *about* an attribute.
