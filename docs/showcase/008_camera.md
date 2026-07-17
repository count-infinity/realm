# 008. Camera

> Checklist item 8 — [now] — *create_obj, capturing world state via contents()/name()*

**What you'll build:** A box camera. `snap` freezes the room — its
name, its description, everyone standing in it, everything lying about
— onto a photograph object you can carry away, keep, and show around.
The print is a snapshot: the world moves on, the photo doesn't.

**Concepts:** reading world state from softcode (`loc()`, `name()`,
`contents()`, tag filters, the `.description` field), `create_obj()`
minting a *stateful* item at runtime, writing a spawned thing's
visible text via `desc_extras` (the `@detail` convention) — and the
engine gap that makes that the right workaround.

Builds on the [vending machine](002_vending_machine.md) (`create_obj`
and its desc gap). The [voice recorder](007_voice_recorder.md) records
sound; this records sight.

## How it works

**A photograph is captured state.** The `$snap` script reads the world
*right now* — `loc(enactor)` for the room (the camera may be in your
hands, so it photographs where *you* stand), `contents(room)` filtered
by tags into people (`player`/`npc`) and props (everything else that
isn't an exit) — and bakes the strings it builds into attributes on a
freshly minted object. Nothing links back: the photo holds copies of
names, not references, which is exactly why it still shows Kess after
Kess leaves.

**The desc gap, and the honest workaround.** `look` reads an object's
engine-level description *field* — what `@desc` writes — and softcode
has no function to set that field on a spawned thing (the gap the
[vending machine](002_vending_machine.md) tutorial filed; its goods
come out name-only). The workaround: **`desc_extras`**, the plain
list-attribute behind the `@detail` command. Every `['', text]` row is
an unconditional detail line, and `look` renders detail lines for
things just as it does for rooms — so `set_attr(photo, 'desc_extras',
rows)` gives the print a full, viewable face using an engine
convention that already exists. (Rows with a non-empty first element
are per-viewer *conditions* — the same machinery `@detail` writes; the
[main tutorial](../tutorial/01-the-island.md) introduces it for
skill-gated detail lines.)

**One caveat worth knowing:** the room's `.description` is captured
*raw*. A plain prose description photographs perfectly; a room whose
desc computes with `[[...]]` blocks will show the block source on the
print, because inline blocks are a render-time feature and a photo is
static text. Photograph prose, or capture only names and contents.

## Build it

Give the room a face worth photographing, then the camera (it works
carried — no need to drop it):

```text
@desc here = Dust hangs in the light of one caged bulb.
@create box camera
```

The shutter. Read the scene, compose the rows, mint the print into the
photographer's hands, stamp the time, and let the whole room see the
flash:

```text
@set box camera/cmd_snap = $snap: room = loc(enactor); people = [name(o) for o in contents(room) if has_tag(o, 'player') or has_tag(o, 'npc')]; props = [name(o) for o in contents(room) if not (has_tag(o, 'player') or has_tag(o, 'npc') or has_tag(o, 'exit'))]; rows = [['', 'A stiff glossy print, edges still warm from the developer.'], ['', f'The scene: {name(room)}.']] + ([['', room.description]] if room.description else []) + ([['', f"Pictured: {', '.join(people)}."]] if people else []) + ([['', f"Scattered about: {', '.join(props)}."]] if props else []); photo = create_obj(f'a photograph of {name(room)}', tags=['thing', 'no_group'], location=enactor); set_attr(photo, 'desc_extras', rows); set_attr(photo, 'taken_at', now()); remit(here, 'FLASH. The box camera whirs and spits out a photograph.')
```

Two details in that line: the photo is named after the room (so a
satchel of prints stays navigable), and it's tagged `no_group` so the
room list never collapses two different photographs into "2
photographs".

## Try it

With Kess and a crated servitor in the room:

```text
snap
look photograph
```

Everyone sees `FLASH. The box camera whirs and spits out a
photograph.`, and the print lands in your inventory. `look photograph`
reads the whole frozen scene:

```text
a photograph of The Workshop
A stiff glossy print, edges still warm from the developer.
The scene: The Workshop.
Dust hangs in the light of one caged bulb.
Pictured: Bilda, Kess.
Scattered about: crated servitor.
```

Now have Kess walk out and look again — she's still in the picture;
that's the point. `snap` again and the *new* print omits her: two
independent objects, two moments. `@examine` a photo to see the
captured rows and the `taken_at` timestamp sitting in plain
attributes.

## Engine gaps

- Same gap as 002, restated for spawned *keepsakes*: `create_obj()`
  plus `set_attr` cannot write the engine's render-description field on
  a thing, so `look` would show nothing — `desc_extras` detail rows
  (above) are the working substitute until a `set_desc()`-style
  primitive lands.

## Going further

- **Film economy:** a `shots` counter the shutter decrements, and the
  [vending machine](002_vending_machine.md) sells film — refusal
  message when it hits zero.
- **Timestamps in prose:** render `taken_at` into the rows ("Exposed
  at hour 1400...") — `now()` is epoch seconds; arithmetic is yours.
- **Photo evidence:** capture `has_tag(o, 'hidden')` subjects only if
  the photographer passes an `observation` check — a camera that sees
  what you missed, or doesn't.
- **A gallery wall:** a container tagged for photos plus the
  [basic container](014_basic_container.md) wards — patrons `look`
  through the collection one print at a time.
