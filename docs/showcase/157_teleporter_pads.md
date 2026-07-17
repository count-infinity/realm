# 157. Teleporter pads

> Checklist item 157 — now — *a self-describing network via search_world, consenting teleports, arrival effects*

**What you'll build:** A network of teleport pads. Stand on one, `dial`
the name of any other, and light swallows you — you rematerialize on the
far pad, which announces your arrival to the room. Add a fourth pad
later and it joins the network automatically; nothing is wired by hand.

**Concepts:** a **tag-based registry** — pads find each other with
`search_world` ([tutorial 083](083_message_in_bottle.md)), never a
hardcoded list; **consenting relocation** with `move_to` (you dialed, so
you may be moved); **arrival effects** with `remit`; and `@clone` to
stamp out the network from one template.

## How it works

**The network is a tag, not a table.** Every pad carries the
`teleport_pad` tag and a `pad_name`. `$dial <name>` runs
`search_world(tag='teleport_pad')`, filters to the pad whose `pad_name`
matches, and jumps you to *its* room. No pad stores a list of the
others — membership *is* the tag, so a pad built tomorrow is dialable
today. `$pads` prints the whole roster the same way.

**Dialing is consent to be moved.** A pad can't shove a stranger around —
but typing its `$dial` command is you asking to go, and the engine
grants a `$`-command's enactor the right to be relocated by it (the
portal rule). So the pad calls plain `move_to(enactor, ...)`, which
still honors the destination's locks — a warded pad-room can refuse
arrivals. (Contrast the wizardly `teleport_obj`, which needs *control*
of whoever it moves and is the wrong tool here.)

**Arrival is just narration.** `oemit` covers your vanishing for the
people you leave behind; a `remit` to the destination announces the
shimmer of your arrival to everyone already there.

**Built once, cloned out.** One template pad carries the `$dial`/`$pads`
logic; `@clone` copies its commands into each station, where you tag it
and name it. Destroying the template leaves a clean network of identical
pads.

## Build it

Three rooms for the network, and the template pad with both commands:

```text
@dig Alpha Station
@dig Beta Outpost
@dig Gamma Relay
@teleport me = Alpha Station
@create translocator pad
@set translocator pad/cmd_dial = $dial *: goal = trim(arg0).lower(); net = [p for p in search_world(tag='teleport_pad') if get_attr(p,'pad_name','').lower()==goal and p is not me]; (pemit(enactor, 'No pad answers to ' + trim(arg0) + '.') if not net else (oemit(enactor, name(enactor) + ' dissolves into a column of light.'), move_to(enactor, loc(net[0])), remit(loc(net[0]), name(enactor) + ' shimmers into being on the ' + get_attr(net[0],'pad_name') + ' pad.'), pemit(enactor, 'The world folds; you are elsewhere.')))
@set translocator pad/cmd_pads = $pads: pemit(enactor, 'Network: ' + ', '.join(sorted([get_attr(p,'pad_name','?') for p in search_world(tag='teleport_pad')])))
```

Now stamp a live pad into each station — clone, name, tag, drop — then
scrap the template:

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

From Alpha Station:

```text
pads                -> Network: Alpha, Beta, Gamma
dial Gamma          -> "The world folds; you are elsewhere."
                       you're on the Gamma Relay; the room saw you shimmer in
dial Nowhere        -> No pad answers to Nowhere.
```

Everyone you left on Alpha saw "...dissolves into a column of light."
`@clone Gamma Pad = Delta Pad` in a fourth room, tag and name it Delta,
and `pads` lists it instantly — `search_world` never needed telling.

## Going further

- **Keyed pads:** put an [enter lock](026_keycard_door.md) on a pad's
  room and `move_to` respects it — a restricted destination that refuses
  arrivals without the keycard, no change to `$dial`.
- **Arrival effects with teeth:** the destination room's `ON_ENTER` can
  do more than narrate — a disoriented `apply_effect`, a scan that
  `oob`s the room to the arriver's client ([GMCP](077_handheld_radios.md)).
- **A dialing cost:** charge with a [pay](030_toll_gate.md) step, or a
  `charge` attribute the pad checks against `credits(enactor)` before
  it fires.
- **Private lines:** a `network` attribute on each pad and a filter in
  the search — two separate mesh networks that ignore each other while
  sharing the same `$dial` code.
