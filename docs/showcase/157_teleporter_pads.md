# 157. Teleporter pads

> Checklist item 157 ([now]): *networked teleport pads, a tag registry via `search_world`, consenting `move_to`, arrival remits*

**What you'll build:** A network of teleport pads. Stand on one, `dial`
the name of any other, and light swallows you, then you rematerialize on
the far pad, which announces your arrival to the room. Add a fourth pad
later and it joins the network automatically, with nothing wired by hand.

**Concepts:** a tag-based registry (pads find each other with
[`search_world`](../reference/softcode.md#fn-search_world), never a
hardcoded list), consenting relocation with
[`move_to`](../reference/softcode.md#fn-move_to), arrival effects with
[`remit`](../reference/softcode.md#fn-remit), and `@clone` to stamp out
the network from one template.

## How it works

The finished network is a handful of rooms, each holding one pad, and
every pad runs the same two `$`-commands: `$dial <name>` sends the caller
to another pad's room, and `$pads` prints the roster. No pad knows the
others by name ahead of time; they discover each other at the moment you
dial. This section answers three questions: how a pad finds its siblings,
why a pad is allowed to move you, and how the trip is narrated at both
ends.

### How does a pad find the others without a wiring list?

Every pad carries the `teleport_pad` tag and a `pad_name` attribute. When
you dial, the local pad runs
[`search_world`](../reference/softcode.md#fn-search_world)`(tag='teleport_pad')`
to gather every pad in the world, then keeps the one whose `pad_name`
matches what you typed. Membership *is* the tag, so a pad built tomorrow
is dialable today, and `$pads` lists the whole roster the same way. This
is the same live-query idea as the bottle registry in
[083 (message in a bottle)](083_message_in_bottle.md); nothing stores a
list of siblings.

The filter also drops `p is not me` so a pad never counts itself as a
destination. Because both commands are `$`-commands rather than reactive
`ON_<EVENT>` hooks, they need no whole-room
[`target` guard](../reference/softcode.md#guard-on-target): a `$`-command
fires only on the object whose command word the caller typed, and only
that pad, the one in your room, responds.

### Why is a pad allowed to move you?

A pad has no authority over a stranger standing on it, so it cannot shove
people around at will. Typing its `$dial` command, though, is you asking
to go, and the engine grants a `$`-command's enactor the right to be
relocated by that object, which is the portal rule. So the pad calls
plain [`move_to`](../reference/softcode.md#fn-move_to)`(enactor, ...)`,
and because this is an ordinary consenting move rather than a forced one,
the destination's locks still apply. A warded pad-room may refuse the
arrival. Contrast the wizardly
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj), which requires
*control* of whoever it moves; that is the wrong tool here, since a pad
controls no one.

### How is the trip narrated at both ends?

The queued move runs only after the script finishes, so at the moment the
pad narrates, the dialer is still standing on the origin pad.
[`oemit`](../reference/softcode.md#fn-oemit) covers the vanishing for the
people left behind, and a [`remit`](../reference/softcode.md#fn-remit) to
the destination announces the shimmer of arrival to everyone already
there. A private [`pemit`](../reference/softcode.md#fn-pemit) tells the
dialer the trip landed.

### Built once, cloned out

One template pad carries the `$dial` and `$pads` logic. `@clone` copies
its attributes, tags, and locks into each station, where you then add the
`teleport_pad` tag and a `pad_name`. Destroying the template afterward
leaves a clean network of identical pads.

## Build it

Dig the three rooms, stand in the first, and create the template pad that
both commands will live on:

```text
@dig Alpha Station
@dig Beta Outpost
@dig Gamma Relay
@teleport me = Alpha Station
@create translocator pad
```

`$dial <name>` is the heart of it. It lowercases the dialed name, searches
the world for the matching pad, and either reports no answer or performs
the trip: narrate the departure to the origin room, move the caller,
announce the arrival at the far room, and confirm to the caller:

```text
@set translocator pad/cmd_dial = '''
$dial *:
goal = trim(arg0).lower()
net = [p for p in search_world(tag='teleport_pad') if get_attr(p, 'pad_name', '').lower() == goal and p is not me]
if not net:
    pemit(enactor, 'No pad answers to ' + trim(arg0) + '.')
else:
    dest = loc(net[0])
    # the move is queued until the script ends, so this oemit still
    # reaches the pad you are leaving, not the one you land on
    oemit(enactor, name(enactor) + ' dissolves into a column of light.')
    move_to(enactor, dest)
    remit(dest, name(enactor) + ' shimmers into being on the ' + get_attr(net[0], 'pad_name') + ' pad.')
    pemit(enactor, 'The world folds; you are elsewhere.')
'''
```

`$pads` is a single expression, so it stays a one-liner: it collects every
pad's `pad_name` and prints them sorted.

```text
@set translocator pad/cmd_pads = $pads: pemit(enactor, 'Network: ' + ', '.join(sorted([get_attr(p, 'pad_name', '?') for p in search_world(tag='teleport_pad')])))
```

Now stamp a live pad into each station by cloning the template, then
naming, tagging, and dropping it. Repeat for all three, then scrap the
template and return to Alpha:

```text
@clone translocator pad = Alpha Pad
@set Alpha Pad/pad_name = Alpha
@tag Alpha Pad = teleport_pad
drop Alpha Pad
@teleport me = Beta Outpost
@clone translocator pad = Beta Pad
@set Beta Pad/pad_name = Beta
@tag Beta Pad = teleport_pad
drop Beta Pad
@teleport me = Gamma Relay
@clone translocator pad = Gamma Pad
@set Gamma Pad/pad_name = Gamma
@tag Gamma Pad = teleport_pad
drop Gamma Pad
@destroy translocator pad
@teleport me = Alpha Station
```

## Try it

From Alpha Station, with a companion standing beside you:

```text
> pads
Network: Alpha, Beta, Gamma

> dial Gamma
Pat shimmers into being on the Gamma pad.
The world folds; you are elsewhere.

> dial Nowhere
No pad answers to Nowhere.
```

Dialing Gamma moves you to the Gamma Relay. You see the two lines above:
the arrival `remit` reaches the room you land in (which now includes you),
followed by your private confirmation. Meanwhile everyone left behind on
Alpha sees `Pat dissolves into a column of light.` Dialing a name no pad
answers to leaves you exactly where you were.

To grow the network, `@clone Gamma Pad = Delta Pad` in a fourth room, then
tag and name it Delta. `pads` lists it instantly, because `search_world`
never needed telling.

## Going further

- **Keyed pads:** put an [enter lock](026_keycard_door.md) on a pad's room
  and `move_to` respects it, so a restricted destination refuses arrivals
  without the keycard, with no change to `$dial`.
- **Arrival effects with teeth:** the destination room's `ON_ENTER` can do
  more than narrate. It might land a disorienting
  [`apply_effect`](../reference/softcode.md#fn-apply_effect), or run a scan
  that [`oob`](../reference/softcode.md#fn-oob)s the room to the arriver's
  client ([GMCP](077_handheld_radios.md)).
- **A dialing cost:** charge with a [pay](030_toll_gate.md) step, or add a
  `charge` attribute the pad checks against
  [`credits`](../reference/softcode.md#fn-credits)`(enactor)` before it
  fires.
- **Private lines:** add a `network` attribute to each pad and a matching
  filter in the search, giving two separate meshes that ignore each other
  while sharing the same `$dial` code.
```