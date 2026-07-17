# 235. JSON content packs

> Checklist item 235 — [now] — *versioned pack/area files: item & NPC definitions as data*

**What you'll build:** a "relics" area whose item and NPC definitions live
in a versioned JSON file — built in-game, captured with `@export`, edited
in a text editor, and re-installed with `@import`'s plan/apply cycle. Then
you'll meet the shipped `gurps-scifi` pack and the version guard that
keeps old games safe from newer files.

**Concepts:** worldio area files (`realm_format` version stamp), `@export`
/ `@import` plan → `@import/apply`, the forward-compatibility version
guard, `@pack` content bundles and their `pack.json` manifest.

## How it works

Item [241](241_yaml_responses.md) proved that triggers are just data, so
a *response* round-trips through the area exporter. Item 235 zooms out:
**every** definition — an item's stats, an NPC's repertoire, a whole
room — is data, so a pack is nothing more than a directory of versioned
JSON files. Nothing here is a second engine; it's the same
`@export`/`@import` you already met, seen as a *content pipeline*.

Two file shapes, one format:

- **Area file** (`data/areas/<zone>.realm`): a JSON worldio document,
  `{"realm_format": 1, "objects": [...]}`. `@export <zone>` writes every
  room tagged `zone:<zone>`, their contents, and the zone's masters —
  each object carrying its `attrs` (item stats, `cmd_*`/`listen_*`
  triggers, everything).
- **Pack** (`realm/packs/<name>/`): the same worldio files, plus a
  `pack.json` manifest (name, description, file list). The shipped
  `gurps-scifi` pack bundles six classes, ship/combat skills, and gear as
  plain data — `@pack gurps-scifi` makes it all live.

The `realm_format` integer is the **version stamp**, and it is load-
bearing. On import REALM refuses any file whose format is *newer* than
the engine understands — a forward-compatibility guard, so a file written
by a future REALM never gets half-applied by an old one. That is the
migration contract: bump the format when the shape changes, and old
engines fail closed instead of corrupting a world.

`@import` is Terraform-style: a **plan** first (a dry-run diff matched by
stable object id — nothing changes), then `@import/apply`. You must
control every object the plan would touch; in-world objects absent from
the file are reported as orphans, never auto-deleted.

## Build it

Tag a room into a zone, then define an item and an NPC entirely in-game.
The item's "stats" are ordinary attributes; the NPC's repertoire is a
`listen_*` trigger — both are just data:

```text
@zone here = relics
@create ration bar
drop ration bar
@set ration bar/heals = 2
@create Quartermaster
drop Quartermaster
@set Quartermaster/listen_supply = ^*supply*:say Rations are rationed, recruit.
```

Capture the whole zone as a versioned file:

```text
@export relics
```

`Exported 3 objects to areas/relics.realm.` Open
`data/areas/relics.realm` — the version stamp leads the file, and every
definition is right there:

```json
{
  "realm_format": 1,
  "objects": [
    { "name": "ration bar", "attrs": { "heals": 2 } },
    { "name": "Quartermaster",
      "attrs": { "listen_supply": "^*supply*:say Rations are rationed, recruit." } }
  ]
}
```

Edit a definition *in the file* — give the quartermaster a second line:

```json
  "listen_price": "^*price*:say A medkit runs you forty credits."
```

Back in-game, plan then apply. The plan names exactly which object and
which attribute would change:

```text
@import relics
@import/apply relics
```

The quartermaster answers the new keyword on the next line of speech — no
restart, no reload. The file is now the source of truth for the zone:
re-export after in-game edits, re-import after file edits, and the plan
keeps the two honest.

## Try it

Any player in the area, before and after the file edit:

```text
> say Any supply news, Quartermaster?
Quartermaster says, "Rations are rationed, recruit."
> say What is the price of a medkit?
Quartermaster says, "A medkit runs you forty credits."
```

Meet the shipped pack, and the version guard. First the pack:

```text
@pack
```

lists `gurps-scifi` (classes, skills, and gear as data); `@pack
gurps-scifi` imports it and its content goes live immediately — pilots
appear in chargen, piloting appears in the check table.

Now the guard. Hand-edit `data/areas/relics.realm` and set
`"realm_format": 999` (pretend it came from a future REALM), then:

```text
@import relics
```

```text
Area file is from a newer REALM — upgrade first.
```

Nothing is applied. That single integer is what lets versioned content
travel safely between games of different vintages.

## Going further

- **Ship your area as a pack:** wrap `relics.realm` in a directory with a
  `pack.json` (`{"name": "relics", "description": "...", "files":
  ["relics.realm"]}`) and any REALM game can `@pack relics`. Item
  [249](249_writing_a_contrib.md) walks the full contrib packaging.
- **À la carte:** a pack imports whole *or* one file at a time — "import
  the sci-fi pack" and "import just the gear file" are the same operation
  underneath, so a game can take only the pieces it wants.
- **Idempotent definitions:** re-importing a pack skips any
  `class_def`/`skill_def` whose name already exists, so you never
  accumulate duplicate definitions — safe to re-run after every edit.
- **Migration in practice:** when a future format renames a field, the
  new engine reads old files (its format is lower, so the guard passes)
  and upgrades on apply; old engines refuse new files. Version up, never
  sideways. See the [content packs guide](../guides/content-packs.md).
