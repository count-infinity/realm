# 168. Room templates

> Checklist item 168 — [now] — *$stamp wizard, template attrs, create_obj rooms, one-way links*

**What you'll build:** a **cell stamp** — a template object that mints
identical rooms on demand. `stamp A1`, `stamp A2`, and you have a
consistent cellblock in seconds, every cell carrying the same tags and
flavor. (Builder permission: you `@create` the stamp; it does the
repetitive digging for you.)

**Concepts:** a room *template as data* (tags + description text in
attributes), `create_obj(tags=...)` minting rooms, `desc_extras` for the
stamped flavor, and a linked one-way exit so the new room is reachable.

## How it works

**The template is attributes; the stamp is `create_obj`.** Digging
twenty near-identical cells by hand is twenty chances to fumble a tag or
reword a description. Instead, store the room's *definition* once — a
`tmpl_tags` list and a `tmpl_desc` string — on a stamp object, and let a
`stamp <name>` verb mint a room that copies them. Consistency is
structural: every stamp reads the same two attributes.

**Softcode writes `desc_extras`, not the description slot.** A scripted
`create_obj` can name and tag a room and set its attributes, but it
**cannot** write the engine's render-`description` field (the slot
`@desc` fills). So the template's flavor rides in `desc_extras` — the
per-viewer description-lines list that `look` appends — which softcode
*can* set. The cell reads identically to a hand-`@desc`'d one; it's just
stored in the slot softcode is allowed to touch.

**A one-way exit makes it reachable.** The stamp also mints an exit in
*your* current room pointing at the new cell, so a fresh stamp is
immediately walkable. (No return exit — a cellblock corridor with
one-way doors is exactly the vibe; add a back exit in "Going further"
if you want one.)

> **Why not `@clone` a template room?** `@clone` refuses rooms and
> players (it's for things and NPCs), and `@parent` doesn't fall through
> on attribute reads — so a "template room" you copy structurally isn't
> available. The working idiom for rooms is a data template plus a
> minting verb, which is what this builds. See **Engine gaps**.

## Build it

The stamp, its tag list, and its flavor text:

```text
@create cell stamp
drop cell stamp
@set cell stamp/tmpl_tags = ["room", "cellblock", "dark"]
@set cell stamp/tmpl_desc = A cramped stone cell. A slot in the door passes a tin tray; the air is cold and close.
```

The `stamp` verb — mint the room with the template's tags, stamp its
flavor into `desc_extras`, and hang a one-way exit from here:

```text
@set cell stamp/cmd_stamp = $stamp *: nm = escape(trim(arg0)); r = create_obj(nm, tags=V('tmpl_tags', ['room'])); set_attr(r, 'desc_extras', [['', V('tmpl_desc', '')]]); e = create_obj('cell ' + nm, tags=['exit'], location=loc(enactor)); set_attr(e, 'destination', r.id); pemit(enactor, 'Stamped ' + nm + ', reachable as: cell ' + nm + '.')
```

## Try it

```text
stamp A1        -> Stamped A1, reachable as: cell A1.
stamp A2        -> Stamped A2, reachable as: cell A2.
cell A1
  A1
  A cramped stone cell. A slot in the door passes a tin tray; the air is cold and close.
```

Both cells carry `cellblock` and `dark` (so the [dark-room](038_dark_room.md)
rules apply for free) and read identically. Editing the *template*
changes the next stamp, not the ones already placed — a template is a
mold, not a live parent. `@examine A1` shows the tags and the
`desc_extras` the stamp wrote.

## Engine gaps

- Softcode `create_obj` cannot set the render-`description` slot, so
  templates carry flavor in `desc_extras` (which behaves the same at
  `look` time). A builder can still `@desc` a stamped room afterward.
- `@clone` explicitly refuses rooms, and `@parent` doesn't propagate
  attribute reads (see [prototype library](165_prototype_library.md)) —
  so structural room-inheritance isn't available; templates are done as
  data + a minting verb.

## Going further

- **Two-way cells:** add a return exit in `stamp` —
  `create_obj('out', tags=['exit'], location=r)` with its destination set
  to `loc(enactor)` — for corridors you can walk back down.
- **Parameterized templates:** accept `stamp <name> = <flavor>` and let
  the second half override `tmpl_desc`, so one stamp mints a *family* of
  rooms with a shared skeleton and per-room detail.
- **Furnished templates:** after minting, loop a `tmpl_contents` list of
  [prototype](165_prototype_library.md) names and `mint` each into the
  new room — a stamp that lays down a room *and* its furniture.
- **Stamp a zone:** tag every stamp into a zone and a
  [weather](036_weather_system.md) or [mass-edit](169_zone_mass_edit.md)
  pass reaches them all at once.
