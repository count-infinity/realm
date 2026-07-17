# 169. Zone mass-edit

> Checklist item 169 — [now] — *zone_rooms() queries, dry-run-by-default, apply-to-commit*

**What you'll build:** a `retheme <zone>` verb that sweeps every room in
a zone and reports **what it would change** — a dry run — and only
touches the world when you add the `apply` keyword. The safe way to edit
fifty rooms at once. (Builder permission: the warden is a builder-owned
tool.)

**Concepts:** `zone_rooms()` as the target set, the **dry-run-first**
discipline (echo the plan, commit only on `apply`), and `set_attr` across
a whole zone in one line — softcode's answer to a bulk editor with a
preview.

## How it works

**The zone is the selection.** `zone_rooms('chapel')` returns every room
tagged `zone:chapel`; a comprehension over it is your batch. Membership
is the tag, so a room added to the zone later is picked up automatically
next sweep — you never maintain a list.

**Dry-run by default is a safety rail.** Mass edits are exactly where a
typo becomes fifty typos. So the verb's *default* behavior is to
**describe** each change ("would set ambient on Nave") and mutate
nothing; only `retheme apply chapel` actually writes. The single verb
carries both modes — it splits its argument, checks whether the first
word is `apply`, and branches the comprehension between a `pemit`
(preview) and a `set_attr`+`pemit` (commit). Preview and commit share one
code path, so what you saw is exactly what you get.

This is the softcode sibling of the native `@foreach`
([batchcode areas](166_batchcode_areas.md)): `@foreach` is the
fire-and-forget bulk command, and a `retheme`-style verb is what you
build when the edit deserves a look before you pull the trigger.

## Build it

Two rooms in a zone:

```text
@dig Nave = nave, back
nave
@zone here = chapel
@dig Crypt = crypt, up
crypt
@zone here = chapel
up
```

The warden and its dual-mode sweep. Default is DRY RUN; the word `apply`
before the zone name commits:

```text
@create warden
drop warden
@set warden/cmd_retheme = $retheme *: parts = trim(arg0).split(' '); apply = parts[0] == 'apply'; zone = parts[-1]; rooms = zone_rooms(zone); pemit(enactor, ('APPLYING to ' if apply else 'DRY RUN over ') + str(len(rooms)) + ' rooms in ' + zone + ':'); [(set_attr(r, 'ambient', 'Candlewax and cold stone.'), pemit(enactor, '  set ambient on ' + name(r))) if apply else pemit(enactor, '  would set ambient on ' + name(r)) for r in rooms]
```

## Try it

```text
retheme chapel
  DRY RUN over 2 rooms in chapel:
    would set ambient on Nave
    would set ambient on Crypt
```

Nothing changed — `@examine Nave` shows no `ambient` yet. Now commit:

```text
retheme apply chapel
  APPLYING to 2 rooms in chapel:
    set ambient on Nave
    set ambient on Crypt
```

Both rooms now carry the attribute. Because the target is
`zone_rooms()`, tagging a third room into `chapel` and re-running picks
it up with no edit to the verb.

## Going further

- **Edit anything:** swap the `set_attr` for `add_tag(r, 'sanctified')`,
  a `desc_extras` stamp, or an `@behavior` attach — the dry-run
  scaffold is the reusable part.
- **Targeted sweeps:** filter the comprehension —
  `for r in zone_rooms(zone) if not has_tag(r, 'outdoors')` — to retheme
  only interiors.
- **Undo-friendly:** stamp the *old* value into a `prev_ambient` attr as
  you overwrite, and a `retheme revert` mode reads it back — a poor
  builder's transaction log.
- **Fire-and-forget:** when you don't need the preview, the native
  `@foreach tag:zone:chapel = @set %o/ambient = ...` does the same commit
  in one line — see [batchcode areas](166_batchcode_areas.md).
