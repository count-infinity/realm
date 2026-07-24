# 008. Camera

> Checklist item 8 ([now]): *create_obj, capturing world state via contents()/name()*

**What you'll build:** A box camera. `snap` freezes the room (its name, its
description, everyone standing in it, everything lying about) onto a
photograph object you can carry away, keep, and show around. The print is a
snapshot: the world moves on, the photo doesn't.

**Concepts:** reading world state from softcode
([`loc()`](../reference/softcode.md#fn-loc),
[`name()`](../reference/softcode.md#fn-name),
[`contents()`](../reference/softcode.md#fn-contents),
[`has_tag()`](../reference/softcode.md#fn-has_tag) filters, the
`.description` field), [`create_obj()`](../reference/softcode.md#fn-create_obj)
minting a complete, stateful item in one call, and `desc_extras` detail rows
(the `@detail` convention) as the vehicle for the print's captured text.

Builds on the [vending machine](002_vending_machine.md), which mints its
goods from prototype attributes stored on a shelf; the camera composes its
attributes from the live room instead. The
[voice recorder](007_voice_recorder.md) records sound; this records sight.

## How it works

**A photograph is captured state.** The `$snap` script reads the world right
now: `loc(enactor)` gives the room (the camera rides in your hands, so it
photographs where *you* stand), and `contents(room)` is sorted by tag into
people (`player`/`npc`) and props (everything else that isn't an exit). The
strings it builds are baked into attributes on a freshly minted object, and
nothing links back: the photo holds copies of names, not references, which is
exactly why it still shows Kess after Kess leaves.

**One call mints the whole print.** `create_obj` takes a name, a
`description` (the render description `look` shows, the same field `@desc`
writes), and an `attrs` dict stamped on at birth, so the photograph arrives
complete instead of being created bare and written to afterwards. The
[vending machine](002_vending_machine.md) mints its coffee bulbs with the
same call; the only difference here is that the attributes are computed from
the scene rather than read off a prototype.

**The scene rides as detail rows.** The captured lines go into `desc_extras`,
the list attribute behind the `@detail` command: every `['', text]` row is an
unconditional detail line, and `look` renders detail lines on things just as
it does on rooms. Rows beat one long description string twice over. First,
they stay data, since `@examine` shows them plainly and `@detail photograph`
lists them numbered. Second, they are never evaluated: a description field is
live at render time (a `[[...]]` block in it runs on every look), while a
detail row prints exactly the text it holds, which is what a photograph
wants. (Rows with a non-empty first element are per-viewer *conditions*, the
same machinery `@detail` writes; the
[main tutorial](../tutorial/01-the-island.md) introduces them for skill-gated
detail lines.)

**One caveat worth knowing:** the room's `.description` is captured raw. A
plain prose description photographs perfectly, but a room whose desc computes
with `[[...]]` blocks will show the block source on the print, because the
camera copies what the field holds, not what a viewer would see rendered.
Photograph prose, or capture only names and contents.

## Build it

The shutter script is a `'''` multi-line block: end the `@set` line with a
trailing `'''`, write the body as indented Python, and close with a line of
just `'''` (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

Give the room a face worth photographing, then the camera. There is no
`drop` step, because a carried camera photographs wherever its carrier
stands:

```text
@desc here = Dust hangs in the light of one caged bulb.
@create box camera
```

The shutter, in one attribute. In order: read the room, sort its contents
into people and props, compose the detail rows, mint the print into the
photographer's hands, and let the whole room see the flash:

```text
@set box camera/cmd_snap = '''
$snap:
room = loc(enactor)  # the camera is carried, so loc(me) is its carrier; photograph the typist's room
people = [name(o) for o in contents(room) if has_tag(o, 'player') or has_tag(o, 'npc')]
props = [name(o) for o in contents(room) if not (has_tag(o, 'player') or has_tag(o, 'npc') or has_tag(o, 'exit'))]
rows = [['', f'The scene: {name(room)}.']]  # an empty first slot shows the row to every viewer
if room.description:
    rows.append(['', room.description])
if people:
    rows.append(['', f"Pictured: {', '.join(people)}."])
if props:
    rows.append(['', f"Scattered about: {', '.join(props)}."])
photo = create_obj(f'a photograph of {name(room)}',
    tags=['thing', 'no_group'], location=enactor,
    description='A stiff glossy print, edges still warm from the developer.',
    attrs={'desc_extras': rows, 'taken_at': now()})
remit(room, 'FLASH. The box camera whirs and spits out a photograph.')
'''
```

Two details in that mint: the print is named after the room, so a satchel of
prints stays navigable, and it is tagged `no_group`, so the room listing
never collapses two different photographs into "2 photographs". The
`location=enactor` mint works because the photographer is holding the
camera (an object may mint into its own carrier's hands); a camera bolted
to a wall serving strangers would instead mint into the room and hand the
print over with [`move_to`](../reference/softcode.md#fn-move_to), the
[fortune teller](013_fortune_teller.md)'s idiom.
[`remit`](../reference/softcode.md#fn-remit) tells everyone in the
photographed room about the flash, and
[`now()`](../reference/softcode.md#fn-now) stamps `taken_at` in epoch seconds
for later arithmetic.

## Try it

With Kess and a crated servitor in the room:

```text
snap
look photograph
```

Everyone sees `FLASH. The box camera whirs and spits out a photograph.`, and
the print lands in your inventory. `look photograph` reads the whole frozen
scene:

```text
a photograph of The Workshop
A stiff glossy print, edges still warm from the developer.
The scene: The Workshop.
Dust hangs in the light of one caged bulb.
Pictured: Bilda, Kess.
Scattered about: crated servitor.
```

Now have Kess walk out and look again: she's still in the picture, and that
is the point. `snap` again and the *new* print omits her, two independent
objects for two moments. `@examine` a photo to see the captured rows and the
`taken_at` timestamp sitting in plain attributes.

## Going further

- **Film economy:** a `shots` counter the shutter decrements, film sold by
  the [vending machine](002_vending_machine.md), and a refusal message when
  the counter hits zero.
- **Timestamps in prose:** render `taken_at` into the rows ("Exposed at hour
  1400..."). `now()` is epoch seconds, so the arithmetic is yours.
- **Photo evidence:** capture `has_tag(o, 'hidden')` subjects only when the
  photographer passes a
  [`skill_check`](../reference/softcode.md#fn-skill_check) on `observation`:
  a camera that sees what you missed, or doesn't.
- **A gallery wall:** a container tagged for photos plus the
  [basic container](014_basic_container.md) wards, so patrons `look` through
  the collection one print at a time.
