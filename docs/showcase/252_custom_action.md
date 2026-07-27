# 252. Invent an action: a coolant breach

> Checklist item 252 ([now]): *act() with a payload, adata reactors, on_check interception with set_adata and block*

**What you'll build:** a reactor that declares its own emergency. A purge
console fires a `breach` event nobody coded into the engine, carrying a
severity and a section number. Three unrelated objects hear it and answer
differently, and a scrubber wired into the room catches the event in
flight and cuts the severity before any of them ever see it.

**Concepts:** `act()` with an `extra` payload and action `tags`,
`adata()` and `has_atag()` in a reactor, and the `on_check` decision pass
where `set_adata()` rewrites a payload and `block()` vetoes it outright.

## How it works

An event in REALM is a string and a payload. `ON_<EVENT>` hooks match on
the action type's suffix, so `event:breach` needs no registration
anywhere: any object holding an `on_breach` attribute is already a
subscriber. What makes the event *useful* is what rides along with it,
and what a third party is allowed to do to it on the way past.

### What can a custom event carry?

`act(target, message, targeting=…, action_type=…, extra=…, tags=…)`.

The `message` is the line the room reads, and it always arrives as
`adata('message')`. `extra` is the structured payload: every key becomes
an `adata(key)` the reactor can read. `tags` are action tags, which is
what a ward keys on with `has_atag()`. Between them, a reactor can tell
*what happened*, *how badly*, and *what kind of thing it is*, without
reaching back into the emitter's attributes.

Keys named `message` and `remote_rooms` belong to the propagation layer
and are ignored if you pass them.

### Who is allowed to intercept it?

This is the part worth slowing down for. Propagation runs two passes: a
**decision** pass (`on_check`) and a **reaction** pass (`on_react` and
the `ON_<EVENT>` hooks). Softcode `on_check` runs only on the action's
**participants**: the actor, the target, and the room. An ordinary object
standing in the room is a bystander, and a bystander's `on_check` is
never consulted, only its behaviors.

So a scrubber sitting on the floor with an `on_check` attribute does
nothing at all. Put the same line on the **room** and it fires. That is
the design in one sentence: participants decide, bystanders react.

### What can the decision pass do to the payload?

Two things, and both reach the reactors that run afterwards:

| verb | effect on the event |
|---|---|
| `set_adata(key, value)` | rewrite the payload; reactors read the new value |
| `block(reason)` | veto it; no `ON_<EVENT>` hook runs at all |

A severity of 8 rewritten to 2 in the check pass is a 2 by the time the
medbay monitor reads it. The decision pass runs against a deliberately
read-only namespace, so a ward can allow, deny, or adjust, and nothing
else: `pemit`, `set_attr`, and the rest are absent. Reacting belongs in
the reaction pass.

### How far does the event travel?

`targeting='room'` keeps it local, and this build uses that.

`'zone'` and `'remote'` broadcast the **message** further, to every room
in the zone or to the target's room. Be precise about what that buys:
the message reaches those rooms and their wards get the two-pass, but the
softcode `ON_<EVENT>` hook fires in the **actor's room only**. A monitor
two rooms away hears the klaxon text and never runs its `on_breach`. For
reactions in another room, put the reacting object where the action is,
or give the far room a hook of its own to trigger.

## Build it

Dig the control room and step in.

```text
@dig Reactor Control = core, out
core
```

The console. Its verb invents the event: a type nobody registered, a
message for the room, a payload the reactors will read, and a `hazard`
tag for the wards to key on.

```text
@create purge console
drop purge console
@set purge console/cmd_purge = '''
$purge:
act(me, 'A coolant klaxon shrills through the deck.', targeting='room', action_type='event:breach', extra={'severity': 8, 'section': 'C'}, tags=['hazard'])
'''
```

Now three subscribers that never heard of each other. The medbay monitor
triages off the number.

```text
@create medbay monitor
drop medbay monitor
@set medbay monitor/on_breach = '''
sev = adata('severity', 0)
if sev >= 6:
    remit(here, 'MEDBAY: trauma team standing by for section ' + str(adata('section', '?')) + '.')
else:
    remit(here, 'MEDBAY: logged a minor exposure, no team dispatched.')
'''
```

The blast door keys on the tag rather than the number, so it answers any
hazard event you invent later without being touched again.

```text
@create blast door
drop blast door
@set blast door/on_breach = '''
if has_atag('hazard'):
    set_attr(me, 'sealed', 1)
    remit(here, 'The blast door slams and seals.')
'''
```

The logbook records the message the event carried, which is the one key
every event has.

```text
@create logbook
drop logbook
@set logbook/on_breach = '''
row = 'sev ' + str(adata('severity', 0)) + ': ' + adata('message', '')
set_attr(me, 'entries', ((V('entries') or []) + [row])[-20:])
'''
```

Last the scrubber, and note where the script goes. The hook lives on the
**room**, because only a participant's `on_check` is consulted. The
scrubber object is there to be looked at; the room is what decides.

```text
@create scrubber array
drop scrubber array
@set here/on_check = '''
if has_atag('hazard') and get_attr(get('scrubber array'), 'online'):
    set_adata('severity', 2)
'''
@set scrubber array/online = 1
```

## Try it

With the scrubber online, the check pass rewrites the payload before any
subscriber reads it, so the monitor takes the quiet branch.

```text
> purge
A coolant klaxon shrills through the deck.
MEDBAY: logged a minor exposure, no team dispatched.
The blast door slams and seals.
```

Take the scrubber offline and fire the same event. Nothing about the
console changed; the severity simply arrives intact.

```text
> @set scrubber array/online = 0
Set scrubber array/online = 0

> purge
A coolant klaxon shrills through the deck.
MEDBAY: trauma team standing by for section C.
The blast door slams and seals.
```

The blast door answered both times, because it reads the tag rather than
the number. To watch a veto instead of an edit, swap the room's hook for
`block` and fire again: the klaxon line still prints, and not one
subscriber runs.

```text
> @set here/on_check = if has_atag('hazard'): block('containment holds')
Set here/on_check = ...

> purge
A coolant klaxon shrills through the deck.
```

## Going further

- **A second emitter, no new subscribers.** Fire
  `action_type='event:breach'` with `tags=['hazard']` from a ruptured
  pipe and the blast door seals for that too. Subscribers bind to the
  event, not the emitter.
- **Escalate on repeats.** Have the logbook count entries in a window and
  fire its own `act()` at a higher severity once the count passes a
  threshold, so events beget events.
- **Guard the reactors.** These hooks fire for every object in the room,
  which is fine here because each acts only on itself. A hook that acts
  on `target` needs the
  [`target` guard](../reference/softcode.md#guard-on-target).
- **Reach further.** [245](245_event_bus_tour.md) covers `targeting` and
  the two-pass model in depth, and
  [Wards, Resistance & Armor](../guides/interception.md) covers
  `on_check` against the engine's own actions rather than an invented one.
