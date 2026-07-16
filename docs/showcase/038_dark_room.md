# 038. Dark room

> Checklist item 38 — [now] — *dark/light/nightvision tags — the perception engine*

**What you'll build:** An undercroft that is pitch black until someone
brings a light — plus the goggles and lantern that beat it. Almost no
softcode: darkness is an engine feature, and this tutorial is a tour of
its tag vocabulary.

**Concepts:** the `dark` room tag, `light` sources (and when carrying
one counts), `wielded`, `nightvision` via wearables' `grants_tags`,
sight-gated targeting.

## How it works

Perception is one of the seams REALM keeps in the engine, because every
naming surface must agree at once — a room you can't see is a room
whose contents you can't `look` at, can't `get`, can't target. That's
not something a per-command softcode patch can promise. The whole
system is driven by tags:

| tag | on | means |
|---|---|---|
| `dark` | a room | unlit: renders "pitch black", hides contents, blocks targeting |
| `light` | an object | a light source — **the convention item 6's flashlight toggles** |
| `wielded` | a carried object | held up / in hand (the `wield` command sets it) |
| `nightvision` | a viewer | sees dark rooms regardless |

The lighting rule: a dark room is lit if a `light`-tagged object is
**in the room itself** (a dropped torch), or **held up** by someone in
it (`light` + `wielded`). A lantern buried in your pack lights
nothing — carrying is not brandishing. Admins bypass all of it (use
`quell` to test darkness honestly).

**The light convention** (shared with item 6, the flashlight): a light
source *is* an object with the `light` tag; toggling a light on or off
*is* `add_tag(me, 'light')` / `remove_tag(me, 'light')`. Item 6's
flashlight, this room's lantern, item 37's street lamps, and the
engine's lighting rule all meet on that single tag — build to it and
every light works in every dark room.

`nightvision` rides the wearables convention: a `wearable`-tagged item
with `grants_tags` confers its tags while worn and takes them back when
removed — no code, the `wear` command does the bookkeeping.

## Build it

Dig the undercroft and prepare the gear before descending:

```text
@dig The Undercroft = down, up
@create storm lantern
@tag storm lantern = light
@create tinker goggles
@tag tinker goggles = wearable
@set tinker goggles/slot = eyes
@set tinker goggles/grants_tags = ["nightvision"]
```

Now go down, douse the place, and salt it with something findable:

```text
down
@tag here = dark
@desc here = Brick vaults sweat cold water. Something small scurries at the edge of hearing.
@create scattered bones
drop scattered bones
up
```

(Note the order of business down there: once `@tag here = dark` lands,
*you're* in the black too — your inventory stays visible and exits stay
walkable by name, so a builder can always work by feel. `quell` is the
honest way to preview it; admins see through darkness.)

## Try it

Send a friend down with no light:

```text
down
  It is pitch black here. You can't see a thing.
get bones
  You don't see 'bones' here.        <- unseen means untargetable
up
```

Goggles beat it (hand them over with `give tinker goggles to Kess`):

```text
wear tinker goggles
  You put on the tinker goggles.
down
  The Undercroft
  Brick vaults sweat cold water. ...
  scattered bones
```

So does light — but only held up or set down:

```text
down                       (lantern in your pack)
  It is pitch black here. You can't see a thing.
wield storm lantern
  You ready storm lantern.           <- now the room is lit for EVERYONE
drop storm lantern
  ...still lit: a light source in the room itself counts.
```

## Going further

- **A working flashlight:** item 6 is exactly this convention plus a
  `$flick` command toggling the `light` tag and an `on_tick` battery
  drain. Any such gadget lights this room with zero coordination.
- **Dark by night only:** let a clock toggle the `dark` tag on outdoor
  rooms ([tutorial 037](037_day_night_descs.md)) — the undercroft
  pattern, scheduled.
- **What darkness costs:** `hide` checks get a darkness bonus and
  sneaking loves an unlit room — see the sneaking tutorial (item 160)
  for the stealth half of the perception engine.
- **Creatures of the dark:** tag the cellar's rats `nightvision` and
  give them the `aggressive` behavior — the players fumble, the rats
  don't.
