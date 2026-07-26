# 050. Tripwire Alarm

> Checklist item 50 ([now]): *ON_ENTER, pemit(owner(me)), remote notification*

**What you'll build:** A hair-thin wire across a stockroom doorway that
sends its owner a silent, cross-room alert every time someone crosses the
room, so the intruder never knows they were counted. A `search` finds the
wire, and a wire that has been found is stepped over instead of tripped.

**Concepts:** a witnessed [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks)
as a proximity trigger, [`pemit()`](../reference/softcode.md#fn-pemit) as
cross-room delivery (no shared room required),
[`owner(me)`](../reference/softcode.md#fn-owner) as a standing return
address, the `invisible` plus `conceal_difficulty` concealment kit that
the built-in `search` already understands, and a counter attribute as the
wire's memory.

## How it works

The finished wire is an ordinary object lying on the stockroom floor. When
anyone walks in, the wire counts the crossing and sends its owner one
private line, wherever that owner happens to be standing, while the walker
sees nothing at all. This section answers three questions: how a dropped
object hears an arrival, how a single line reaches a room away, and why the
wire stays quiet both for the owner and for a wire that has already been
found.

### How does a wire on the floor hear someone arrive?

Movement fires an [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks)
event at the destination, and every object already in that room witnesses
it, with the mover bound as `enactor`. An object lying on the floor with an
`on_enter` attribute is therefore a sensor with no polling and no code on
the room. `ON_ENTER` is the *after* hook in the action trio
([action phases](../design/action-phases.md)): by the time it runs the
arriver has already relocated, so it stands in the wire's own room and
`loc(enactor)` is `loc(me)`. This is the same witnessed-trigger shape as
the [landmine](049_landmine.md) and the
[security camera](054_security_camera.md), except that where the mine
answers an arrival with a bang, the wire answers with a whisper.

One consequence of "every object witnesses it" matters for the guard
below: if two wires lie in one room, an intruder trips both, and each
pages the owner once. That is correct, since each wire is its own sensor.

### How does the alert reach an owner in another room?

[`pemit()`](../reference/softcode.md#fn-pemit) delivers a line to a named
target anywhere in the world, with no shared room required, so it is the
right primitive for an alarm whose owner has walked away (the camera in
item 54 forwards its feed the same way). The target writes itself:
[`owner(me)`](../reference/softcode.md#fn-owner) is whoever built the wire,
looked up fresh on every crossing, so the alarm keeps reporting to you even
after you move, and reports to the buyer if you ever give the wire away.

### Why does it stay silent for the owner and for a found wire?

Because the reaction lives behind a guard, and softcode only says what you
tell it to say. Two facts shape the guard. First, an `ON_ENTER` event
targets the *room*, not the wire, so the usual
[`target is me`](../reference/softcode.md#guard-on-target) test is wrong
here: the wire is a witness, and it reads the mover through `enactor`
instead, filtered to real characters so that dropping a second gadget into
the room never pages anyone. Second, triggers fire for everyone, including
you while you decorate, so an owner-exemption (`enactor is not owner(me)`)
keeps the alarm from paging you about yourself. The reveal is honored the
same way: once `search` strips the `invisible` tag, the branch that runs is
a polite "stepped over" message to the walker with no page at all, because
a wire you can see is not a trap. Knowledge is safety on both sides of the
wire.

## Build it

Two rooms, your shop and the stockroom worth guarding, with the builder
ending up minding the counter:

```text
@dig The Curio Shop = shop, out
shop
@dig The Stockroom = stockroom, shop
stockroom
```

The wire itself, dropped where it will lie in wait:

```text
@create tripwire
drop tripwire
@desc tripwire = A hair-fine wire at ankle height, easy to miss.
```

Ordinary attributes hold its state. `armed` is the master switch, and
`conceal_difficulty` with `reveal_msg` is the concealment kit that the
built-in `search` command already reads, and the punctuation inside
`reveal_msg` is in-game text that displays verbatim:

```text
@set tripwire/armed = 1
@set tripwire/conceal_difficulty = 2
@set tripwire/reveal_msg = A glint at ankle height -- a wire, stretched taut across the doorway!
```

Now the trigger. The guard reacts only to an armed wire, a real character
who is not the owner, and then splits on visibility: a hidden wire counts
the crossing with [`incr`](../reference/softcode.md#fn-incr) and pages the
owner, while a revealed wire is simply stepped over and says nothing home:

```text
@set tripwire/on_enter = '''
x = enactor
# ON_ENTER fires on every object in the room, so react only to a real
# intruder who is not the owner; a bare `enactor is not owner(me)` is an
# identity check, not equality.
if V('armed', 0) and (has_tag(x, 'player') or has_tag(x, 'npc')) and x is not owner(me):
    if has_tag(me, 'invisible'):
        incr('trips')
        pemit(owner(me), f'[{name(me)}] {name(x)} crossed {name(loc(me))}.')
    else:
        pemit(x, 'You step over the exposed tripwire.')
'''
```

Hide it last, so you can see it while you work, then head back to the shop:

```text
@tag tripwire = invisible
shop
```

## Try it

Stand in the Curio Shop and have someone else walk into the stockroom:

```text
(they type: stockroom)
you see:              [tripwire] Zeke crossed The Stockroom.
they see:             (the ordinary room, nothing else)
```

Every crossing pages you wherever you are, because `pemit()` does not care
about distance, and the intruder's screen stays clean. Their way out is to
find the wire first:

```text
(they type: search)   -> A glint at ankle height -- a wire, stretched taut across the doorway!
(they leave and re-enter)
they see:             You step over the exposed tripwire.
you see:              (nothing, because a seen wire reports nothing)
```

Back home, `@examine tripwire` shows `trips` ticking up, so the wire
remembers every crossing even for the pages you were not around to read.

## Going further

- **A bell instead of a page.** Swap the `pemit()` for
  [`remit()`](../reference/softcode.md#fn-remit) on your shop room, and the
  alarm becomes diegetic: anyone minding the shop hears the bell, not just
  you.
- **A subscriber list.** Replace `owner(me)` with a `watchers` list
  attribute and a `$subscribe` command, exactly like the
  [security monitor's](054_security_camera.md) opt-in list, and a whole
  guild reads one wire.
- **Direction sense.** Add a matching `on_leave` that pages
  `f'{name(x)} left {name(loc(me))}'`; an enter without a matching leave
  means they are still inside. The [motion sensor](055_motion_sensor.md)
  builds a full log on this idea.
- **Re-hiding.** A `$reset wire` command for the owner that calls
  [`add_tag(me, 'invisible')`](../reference/softcode.md#fn-add_tag) turns a
  stepped-over wire back into a trap.
```