# 241. Response scripting in data

> Checklist item 241 — [now] — *packs/area files carrying listen_*/cmd_* attrs*

**What you'll build:** a tavern NPC whose keyword/response repertoire
lives in a data file — built in-game, exported with `@export`, extended
in a text editor, and installed back with `@import`'s plan/apply cycle.

**Concepts:** triggers as ordinary attributes (and therefore ordinary
*data*), `@zone`, `@export`, `@import` plan → `@import/apply`, area files
under `data/areas/`, `@pack` content bundles.

## How it works

Items [243](243_object_verbs.md) and [240](240_builder_triggers.md) put
responses on NPCs one `@set` at a time. That's perfect for one reaction;
an NPC with a dozen responses shared across three taverns wants to be a
*file*.

REALM needs no second engine for this, because triggers already *are*
data: a `listen_rumor` or `cmd_menu` attribute is a plain string in the
object's attribute table. Anything that round-trips attributes therefore
round-trips conversation. The area exporter is exactly that:

- `@export <zone>` writes every room tagged `zone:<zone>`, their
  contents, and the zone's masters to `data/areas/<zone>.realm` — a JSON
  worldio file (`{"realm_format": 1, "objects": [...]}`) in which each
  object carries its `attrs`, triggers included. (One historical note:
  the checklist calls this item "YAML responses" after the sibling
  Evennia showcase; REALM's native format is JSON.)
- `@import <name>` is Terraform-style: it prints a **plan** — a dry-run
  diff of file against world, matched by stable object id — and changes
  nothing. `@import/apply <name>` executes the plan. You must control
  every object the plan would touch; objects in the world but not in the
  file are reported as orphans, never auto-deleted.

So a "response pack" is just an area file you keep in version control.
Edit the NPC's `attrs` in your editor, `@import` to see exactly what
would change, apply, and the NPC answers the new keyword on the next
line of speech — no restart, no reload.

## Build it

Build the tavern's conversation in-game first. Tag the room into a zone
so the exporter knows what to take:

```text
@zone here = dockside
@create Old Marta
drop Old Marta
@set Old Marta/listen_rumor = ^*rumor*:say They say the lighthouse keeper has not slept in years.
@set Old Marta/cmd_menu = $menu:pemit(enactor, 'Chowder, hardtack, and black coffee.')
say Any rumors, Marta?
```

She answers — the responses work. Now capture them as data:

```text
@export dockside
```

`Exported 2 objects to areas/dockside.realm.` Open
`data/areas/dockside.realm` in your editor and find Old Marta's entry.
Her repertoire is right there in `attrs`:

```json
"attrs": {
  "listen_rumor": "^*rumor*:say They say the lighthouse keeper has not slept in years.",
  "cmd_menu": "$menu:pemit(enactor, 'Chowder, hardtack, and black coffee.')"
}
```

Add a response *in the file* — one new key:

```json
  "listen_wreck": "^*wreck*:say Half her cargo still lies out on the reef."
```

Back in the game, ask for the plan:

```text
@import dockside
```

```text
Plan for area 'dockside':
  ~ update   Old Marta   (attrs (listen_wreck))
  0 to create, 1 to update, 0 orphaned, 0 conflicts.
Run @import/apply dockside to execute.
```

Only Marta changes, and the plan says exactly which attribute. Apply it:

```text
@import/apply dockside
say What about the wreck?
```

Marta answers from the file: *"Half her cargo still lies out on the
reef."* The file is now the source of truth for the whole zone —
re-export after in-game edits, re-import after file edits, and the plan
keeps the two honest.

Packs are the same mechanism shipped as a folder — a manifest plus
worldio files, importable whole or one file at a time:

```text
@pack
```

lists the built-ins (`gurps-scifi` ships with the engine); `@pack
<name>` imports one, and its content — classes, skills, gear, and yes,
NPCs with response attributes — goes live immediately.

## Try it

Any player in the tavern:

```text
> say Any rumors, Marta?
Old Marta says, "They say the lighthouse keeper has not slept in years."
> menu
Chowder, hardtack, and black coffee.
> say What about the wreck?
Old Marta says, "Half her cargo still lies out on the reef."
```

## Going further

- **Shared small talk:** keep a `tavern-talk` area file of stock
  responses and paste its `attrs` block onto any barkeep entry — or
  `@clone` a fully-loaded NPC in-game and re-export.
- **Ship it as a pack:** wrap your area files in a directory with a
  `pack.json` manifest and any REALM game can `@pack` it — see the
  [content packs guide](../guides/content-packs.md).
- **Conflict safety:** if someone edited Marta in-game since your
  export, the plan flags a conflict instead of silently clobbering —
  re-export, merge, then apply.
- **Whole quarters at once:** the same flow moves entire zones between
  worlds — rooms, exits, NPCs, triggers, locks — which is how the
  showcase's bigger builds travel.
