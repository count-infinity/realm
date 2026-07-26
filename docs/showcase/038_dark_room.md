# 038. Dark room

> Checklist item 38 ([now]): *dark/light/nightvision tags: the perception engine*

**What you'll build:** An undercroft that is pitch black until someone
brings a light, plus the goggles and the lantern that beat it. There is
almost no softcode here, because darkness is an engine feature, and this
tutorial is a tour of its tag vocabulary.

**Concepts:** the `dark` room tag, `light` sources (and when carrying one
counts), the `wielded` rule, `nightvision` granted through a wearable's
`grants_tags`, and sight-gated targeting.

## How it works

The finished room is one ordinary room with a single extra tag on it, so
the whole effect comes from the engine reading tags rather than from any
script you write. This section answers three questions: what darkness
does to a room, what lifts it, and how a viewer can see in the dark
anyway.

**What does the `dark` tag do?** A room tagged `dark` renders as exactly
one line, `It is pitch black here. You can't see a thing.`, and nothing
else: no room name, no description, no contents, and no exits line. Since
the contents never render, the things on the floor also cannot be
targeted, so `get bones` in the black answers `You don't see 'bones'
here.` Perception is one feature the engine keeps for itself, because
every naming surface has to agree at once: a room you cannot see is a
room whose contents you cannot `look` at, `get`, or target, and a
per-command softcode patch could not keep all of those in step. The whole
system is driven by tags:

| tag | on | means |
|---|---|---|
| `dark` | a room | unlit: renders the pitch-black line, hides contents, blocks targeting |
| `light` | an object | a light source, the same convention the [flashlight](006_flashlight.md) toggles |
| `wielded` | a carried object | held up in hand, set by the `wield` command |
| `nightvision` | a viewer | sees a dark room regardless |

**What lifts the darkness?** A dark room counts as lit when a
`light`-tagged object is either sitting in the room itself (a dropped
torch) or held up by someone standing in it (`light` plus `wielded`). A
lantern buried in your pack lights nothing, because carrying is not
brandishing. That is the light convention, and it is shared with the
[flashlight](006_flashlight.md): a light source is simply an object that
carries the `light` tag, and toggling a light on or off is
[`add_tag`](../reference/softcode.md#fn-add_tag)`(me, 'light')` or
[`remove_tag`](../reference/softcode.md#fn-remove_tag)`(me, 'light')`.
Because the engine's lighting rule keys off that single tag, any gadget
that meets it lights any dark room with no coordination.

**How can a viewer see in the dark?** A viewer tagged `nightvision` sees
a dark room as if it were lit. That tag can be worn rather than innate:
`nightvision` rides the wearables convention, so a `wearable`-tagged item
with a `grants_tags` list confers its tags while worn and reclaims them
when removed, and the `wear` command does that bookkeeping with no code
of yours. Admins bypass darkness entirely through their SEE_ALL
entitlement, so use `quell` to preview the room honestly, since a quelled
admin is stripped to a mortal's sight.

## Build it

Dig the undercroft and build the two pieces of gear up in the light,
where you can see what you are doing. `@dig` gives the undercroft a
`down` exit from here and an `up` exit back:

```text
@dig The Undercroft = down, up
```

The lantern is a plain object that carries the `light` tag, which is all
a light source is:

```text
@create storm lantern
@tag storm lantern = light
```

The goggles are a wearable that grants `nightvision` while worn. The
`slot` is where they sit so a second eye-slot item cannot stack, and
`grants_tags` is the list the `wear` command hands to the wearer:

```text
@create tinker goggles
@tag tinker goggles = wearable
@set tinker goggles/slot = eyes
@set tinker goggles/grants_tags = ["nightvision"]
```

Now descend, douse the room with the `dark` tag, and leave something on
the floor to prove targeting is gated. Once `@tag here = dark` lands you
are in the black too, but your own inventory stays visible and the exits
stay walkable by name, so you can keep working by feel and climb back
`up` at the end:

```text
down
@tag here = dark
@desc here = Brick vaults sweat cold water. Something small scurries at the edge of hearing.
@create scattered bones
drop scattered bones
up
```

## Try it

Send a friend down with no light. The floor is there, but they cannot
see it, and unseen means untargetable:

```text
> down
It is pitch black here. You can't see a thing.

> get bones
You don't see 'bones' here.

> up
```

Hand over the goggles with `give tinker goggles to Kess`. Worn, they
grant `nightvision`, and the room renders in full:

```text
> wear tinker goggles
You put on the tinker goggles.

> down
The Undercroft
Brick vaults sweat cold water. Something small scurries at the edge of hearing.

You see:
  scattered bones
```

Light beats the dark too, but only when it is held up or set down. A
lantern in your pack lights nothing until you `wield` it, and dropping a
lit lantern lights the room for everyone, because a light source in the
room itself needs no wielder:

```text
> down
It is pitch black here. You can't see a thing.

> wield storm lantern
You ready storm lantern.

> look
The Undercroft
Brick vaults sweat cold water. Something small scurries at the edge of hearing.

You see:
  scattered bones
```

## Going further

- **A working flashlight:** the [flashlight](006_flashlight.md) is this
  same convention plus a `$flick` command that toggles the `light` tag
  and an `on_tick` battery drain. Any such gadget lights this room with
  zero coordination.
- **Dark by night only:** let a clock toggle the `dark` tag on outdoor
  rooms, which is what the [day/night descs](037_day_night_descs.md)
  tutorial does, so the undercroft pattern simply becomes scheduled.
- **What darkness costs:** an unlit room gives a bonus to `hide` checks,
  so the dark is a sneaker's friend. See the
  [sneaking](160_sneaking.md) tutorial for the stealth half of the
  perception engine. Note that `search` itself is not light-blind: the
  dark gates seeing and taking, not the Observation roll.
- **Creatures of the dark:** tag the cellar's rats `nightvision` and give
  them the `aggressive` behavior, so the players fumble while the rats do
  not.
