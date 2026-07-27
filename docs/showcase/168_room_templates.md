# 168. Room templates

> Checklist item 168 ([now]): *$stamp verb, data room template, create_obj rooms, one-way exit*

**What you'll build:** a **cell stamp**, a template object that mints
identical rooms on demand. Type `stamp A1`, `stamp A2`, and you have a
consistent cellblock in seconds, every cell carrying the same tags and
flavor. You `@create` the stamp with builder permission, and it does the
repetitive digging for you.

**Concepts:** a room *template as data* (tags plus description text stored
in attributes), [`create_obj`](../reference/softcode.md#fn-create_obj)
minting rooms, `desc_extras` carrying the stamped flavor, and a linked
one-way exit so the new room is reachable.

## How it works

The finished stamp is a single object holding three attributes: a
`tmpl_tags` list, a `tmpl_desc` string, and one `$stamp` verb that reads
those two and mints a room from them. This section explains why the template
is stored as data, where the room's flavor lives, and how the new room
becomes walkable.

### Why the template is data, not a room you copy

Digging twenty near-identical cells by hand is twenty chances to fumble a
tag or reword a description. Instead, store the room's *definition* once (a
`tmpl_tags` list and a `tmpl_desc` string) on a stamp object, and let a
`stamp <name>` verb mint a room that copies them. Consistency is structural,
because every stamp reads the same two attributes.

There is a reason the template is data rather than a room you clone
structurally. [`@clone`](../guides/world-management.md) duplicates things and
NPCs but declines players and rooms, so it will not copy a room you point it
at. REALM's object-level `@parent` *would* share a template room's
attributes with a child, since [`get_attr`](../reference/softcode.md#fn-get_attr)
on a child reads through to its parent on a miss (the
[prototype library](165_prototype_library.md) leans on exactly that for
items). A parent link is a *live* one, though, where editing the template
reshapes every child, and it still needs something to create each room. A
data template plus a minting verb gives you independent rooms that stay put
once stamped, which is the behavior a cellblock wants.

### Where the cell's flavor lives

Each stamped cell carries its description in `desc_extras`, the list of
[per-viewer description lines](038_dark_room.md) that `look` appends after a
room's base description. The
template keeps its flavor as a plain `tmpl_desc` string, and the stamp copies
it into `desc_extras` as a single always-shown line, `[['', tmpl_desc]]`
(an empty condition means every viewer sees it). Using this list rather than
[`create_obj`](../reference/softcode.md#fn-create_obj)'s `description=`
argument is a deliberate choice: `desc_extras` is where per-viewer,
skill-gated lines already live, so the same template can later grow a detail
only an observant prisoner notices without changing the mint path. See the
[dark room](038_dark_room.md) for how conditional detail lines read at a
live prompt.

### How the new room becomes reachable

Minting a room in isolation would strand it, so the stamp also mints an exit
in *your* current room whose `destination` is the new cell's id. That makes a
fresh stamp immediately walkable. It is one-way on purpose, since a cellblock
corridor with one-way doors is exactly the vibe; a return exit is a two-line
addition in "Going further".

## Build it

First create the stamp itself and drop it in the room, so its `$stamp` verb
is present to dispatch:

```text
@create cell stamp
drop cell stamp
```

The template's tag list is a data literal, so it stays a single-line `@set`
(the list must store as a real list for the verb to hand it to `create_obj`):

```text
@set cell stamp/tmpl_tags = ["room", "cellblock", "dark"]
```

The flavor text is likewise plain data on one line:

```text
@set cell stamp/tmpl_desc = A cramped stone cell. A slot in the door passes a tin tray; the air is cold and close.
```

Now the `$stamp` verb. It reads the template tags and flavor, mints the
room, stamps the flavor into `desc_extras` with
[`set_attr`](../reference/softcode.md#fn-set_attr), mints a one-way exit in
[`loc(enactor)`](../reference/softcode.md#fn-loc) (your current room), and
[`pemit`](../reference/softcode.md#fn-pemit)s where the new cell is
reachable. It is a multi-statement script,
so it is written as a `'''` heredoc block (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).
The `$stamp *` trigger captures the name as `arg0`, which
[`trim`](../reference/softcode.md#fn-trim) tidies and
[`escape`](../reference/softcode.md#fn-escape) neutralizes for color markup,
and [`V`](../reference/softcode.md#fn-v) reads the template attributes off the
stamp:

```text
@set cell stamp/cmd_stamp = '''
$stamp *:
name = escape(trim(arg0))
cell = create_obj(name, tags=V('tmpl_tags', ['room']))
set_attr(cell, 'desc_extras', [['', V('tmpl_desc', '')]])
door = create_obj('cell ' + name, tags=['exit'], location=loc(enactor))
set_attr(door, 'destination', cell.id)
pemit(enactor, 'Stamped ' + name + ', reachable as: cell ' + name + '.')
'''
```

`$stamp` is a [`$`-command](../reference/softcode.md#triggers-attributes-on-objects),
which dispatches only for the object it is typed at, so it needs no `target`
guard the way a room-wide `ON_<EVENT>` hook would.

## Try it

```text
> stamp A1
  Stamped A1, reachable as: cell A1.
> stamp A2
  Stamped A2, reachable as: cell A2.
```

Both cells carry `cellblock` and `dark` and hold the same flavor, which
`@examine` confirms:

```text
> @examine A1
  Name: A1
  Tags: cellblock, dark, room
  Attributes:
    desc_extras: [['', 'A cramped stone cell. A slot in the door passes a tin tray; the air is cold and close.']]
```

The exit is real, so `cell A1` walks you straight in:

```text
> cell A1
> look
  It is pitch black here. You can't see a thing.
```

The cell reads dark because it carries the `dark` tag, so a prisoner without
a light sees only blackness (this is the [dark-room](038_dark_room.md) rule
applying for free). Carry a lit source, and the same `look` reads the stamped
flavor:

```text
> look
  A1
  --
  A cramped stone cell. A slot in the door passes a tin tray; the air is cold and close.
```

Editing the *template* changes the next stamp, not the ones already placed,
because a template here is a mold rather than a live parent.

## Going further

- **Two-way cells:** add a return exit in `stamp` with
  `back = create_obj('out', tags=['exit'], location=cell)` and
  `set_attr(back, 'destination', loc(enactor).id)`, for corridors you can
  walk back down.
- **Skip the copy, set the slot:** pass the flavor straight to
  [`create_obj`](../reference/softcode.md#fn-create_obj) as
  `description=V('tmpl_desc', '')` to write the room's base description slot
  directly, the way the [prototype library](165_prototype_library.md) dresses
  a minted item, instead of the appended `desc_extras` line.
- **Parameterized templates:** accept `stamp <name> = <flavor>` and let the
  second half override `tmpl_desc`, so one stamp mints a *family* of rooms
  with a shared skeleton and per-room detail.
- **Furnished templates:** after minting, loop a `tmpl_contents` list of
  [prototype](165_prototype_library.md) names and mint each into the new
  room, a stamp that lays down a room *and* its furniture.
- **Stamp a zone:** tag every stamp into a zone, and a
  [weather](036_weather_system.md) or [mass-edit](169_zone_mass_edit.md) pass
  reaches them all at once.
