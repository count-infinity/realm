# Object identity: uuid, `#id`, and `$keyid`

Every object in REALM has one canonical identity and two ways to reference
it. Keeping those layers separate is what lets references stay stable while
still reading well.

## The canonical id is a uuid

`GameObject.id` is a `uuid.uuid4()` string (realm/core/objects.py). It is:

- **stable** — it never changes, no matter how the object is renamed, moved,
  re-owned, or re-described;
- **unique** — globally, with no coordination;
- **fast** — minted in O(1) with no lookup, index, or counter. This is the
  guarantee that keeps object creation cheap.

Softcode reaches it with the `#` prefix: `get('#3fa9c2b1-...')` does an exact
`persistence.get_cached(uuid)` — no search, no ambiguity. `#` is the one
hardcoded sigil; it is the true address of an object.

Everything friendly is a *layer on top of the uuid*, never a replacement for
it. We never derive an id from mutable fields (name, owner): a derived id is
neither stable (a rename changes it) nor unique (two swords collide), and the
whole point of referencing by id is to survive exactly those changes.

## Names are for humans, and are not identity

`get('rusty key')` matches by name: the executor's room and inventory first,
then the whole world, taking the **first** match and never raising on
ambiguity (realm/scripting/functions.py). That is convenient for typing and
fine for one-off lookups, but it is a trap for a reference that must always
point at one specific object — the day a second object shares the name, the
lookup can silently bind to the wrong one. When identity matters, use `#id`
or `$keyid`. (The [ATM tutorial](../showcase/004_atm_terminal.md) is a worked
example of moving a fragile name lookup onto a stable id.)

## `$keyid` — the friendly, unique, opt-in handle

Most objects never need a friendly id. A handful of well-known singletons do
— a bank core, a weather master, a zone controller, an economy singleton.
For those, a builder assigns a **keyid** with the `@keyid` command:

```text
@keyid BankNet Core = banknet_core
```

and everything thereafter references it as `get('$banknet_core')`. The keyid
is:

- **opt-in** — an object with no keyid does zero extra work at creation, so
  the hot path is untouched; only the few objects you key pay anything;
- **unique** — at most one live object holds a given keyid, enforced by a
  `{keyid → obj_id}` index (realm/persistence/keyid.py);
- **stable** — set once, deliberately; it does not drift when the object is
  renamed or re-owned, so stored `$keyid` references keep resolving;
- **legible** — `$banknet_core` reads far better than a uuid.

It is the DNS-hostname layer: an opaque, stable address (the uuid) plus a
friendly, optional label (the keyid), layered rather than fused.

### Why it is not an ordinary attribute

The keyid lives in the object's `keyid` db attribute (so it persists like any
other value), but it is treated as **identity, not data**:

- it is in `PROTECTED_ATTRS`, so `@set`/`set_attr` refuse to write it — only
  `@keyid` does, which is what keeps the uniqueness index consistent;
- `@clone` and prototype extraction always drop it (`cloneable_attrs`,
  realm/core/attrflags.py): a copy can no more share a keyid than it can share
  a uuid. The clone lands keyless; re-key it by hand if it should become a new
  singleton.

### Conflict, never merge

Uniqueness is enforced as *conflict, not merge*. `claim()` binds a keyid only
if no **different** live object already holds it; a genuine two-objects-one-
keyid clash is reported, never silently overwritten. Re-claiming the same
keyid on the same object is idempotent (the re-save / re-import case). Reads
are cache-validated, so a stale index entry left by a delete or a re-key
self-heals to "no holder" — no separate release bookkeeping is needed for
correctness.

### The sigil is configurable

`$` is the default keyid sigil, in the same game-tunable family as the trigger
and emote sigils (`command_sigil`, `listen_sigil`, `emote_sigil`, and the
multi-char `inline_open`/`inline_close`). Set `KEYID_SIGIL` in `config.py` to
anything 1–16 non-alphanumeric, non-space characters that does not start with
`#` (reserved for raw ids) — `"$$"`, `"key:"`, etc. `get()` tests the sigil
after the `#` branch and strips it before the index lookup.

## Import and clone

A keyid is a unique identity, so across worldio it carries over only when it
can stay unique — never merged onto another object:

- **Sync** (`diff_plan` → `apply_plan`, the two-step `@import`): matched by
  stable id. Re-importing an object re-sets its *own* keyid idempotently. A
  file entry that assigns a keyid already held by a **different** live object
  is surfaced as a plan **conflict**, and `apply_plan` refuses until it is
  resolved — no silent overwrite.
- **Clone import** (`import_objects`, fresh uuids): keyids carry over when
  free — importing an area into a world that does not already hold those
  keyids Just Works with no re-keying. A keyid already held by a different
  live object is a conflict: the imported object lands **keyless** and the
  clash is logged, rather than forcing a blanket re-key of the common,
  non-colliding case.
- **`@clone`** (interactive): the source is always live, so the copy would
  always conflict; the keyid is simply not copied, quietly.

The rule underneath all three: a keyid collision is only ever raised for a
genuine two-objects-one-keyid situation, never for "I re-ran the import."

## See also

- BACKLOG.md §2 "Friendlier object ids" — the remaining layers (short-hash
  `#a1b2c3` typing, `get()` refinement filters) and the rejected
  `<owner>:<name>` scheme.
- [ATM tutorial](../showcase/004_atm_terminal.md) — referencing a shared
  master object by stable id in practice.
- [`get` reference](../reference/softcode.md#fn-get).
