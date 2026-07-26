# 054. Security Camera & Monitor

> Checklist item 54 ([now]): *bug objects: ^listen + ON_ENTER/ON_LEAVE relays via pemit*

**What you'll build:** A camera that relays speech and movement from its
room to a monitor console in another room, where characters `watch` the feed
live, plus a way for the heist crew to cut it. Part of the
[Heist arc](arc_heist.md), with the camera in the Vault Antechamber and the
monitor in the Security Office.

**Concepts:** the bug pattern (`^`-listen for speech,
[`ON_ENTER`/`ON_LEAVE`](../reference/softcode.md#lifecycle-hooks) for
movement), cross-room delivery with
[`pemit()`](../reference/softcode.md#fn-pemit), an opt-in watcher list that
prunes itself, [`eval_attr()`](../reference/softcode.md#fn-eval_attr) as a
shared subroutine, and same-owner gadget pairs.

## How it works

The finished device is two objects owned by one builder. The camera stands in
the room being watched and does nothing but forward: every line it overhears or
witnesses becomes one message sent straight to whoever is sitting at the far
console. The monitor is the console, and it keeps the list of who is currently
watching. This section answers three questions: how the camera picks up what
happens, how a single line crosses to a console in another room, and why the
listen and movement hooks need no `target` guard when most event hooks do.

### How the camera picks up speech and movement

The camera reads its room through two inputs. The first is a **listen
trigger**, exactly the microphone from the [voice recorder](007_voice_recorder.md):
an attribute named `listen_*` whose value is `^pattern: code` fires when speech
matching the pattern is heard where the object stands. Under `^*` the whole
line arrives as `arg0` and the speaker is bound as `enactor`. Listen dispatch
scans the room's contents and the room itself and never anyone's inventory, so
a bug must be planted in the room, not carried, and the speaker never overhears
its own words.

The second input is movement. The camera is a **witness**: when someone walks
in, the engine fires every room object's `ON_ENTER`, and when someone walks
out, its `ON_LEAVE`, with the mover bound as `enactor`. A departure fires while
the mover still stands in the origin room and an arrival fires once the mover
has reached the destination, which is the two-action shape movement always
takes (see [action phases](../design/action-phases.md)).

### How one line reaches a console in another room

The camera does not transform anything. It hands each line to a single `relay`
attribute, and `relay` sends the line to every current watcher with
[`pemit()`](../reference/softcode.md#fn-pemit), which delivers to a named
target wherever that target stands, so no shared room is required. The listen
trigger and both movement hooks all call the same routine with
[`eval_attr(me, 'relay', text)`](../reference/softcode.md#fn-eval_attr): fix the
relay once and all three feeds change. Because `eval_attr` runs as the caller,
inside `relay` the executor is still the camera, so
[`V('feed')`](../reference/softcode.md#fn-v) reads the camera's own console
name and [`name(me)`](../reference/softcode.md#fn-name) is the camera's own
name for the feed label.

`relay` looks the console up fresh every time from the camera's `feed`
attribute with [`get()`](../reference/softcode.md#fn-get), which is late
binding: re-point `feed` and the next line goes to the new console. It then
reads the console's `watchers` list, keeps only the watchers still standing in
the console's room, delivers to those, and rewrites the list so anyone who
wandered off is dropped on this same pass. No ticker is needed because the
prune rides on the delivery. `watch` adds you to the list and `unwatch` removes
you.

The camera writes the monitor's `watchers` list, which is
[`set_attr`](../reference/softcode.md#fn-set_attr) on a *different* object. That
works only because both gadgets belong to one builder: softcode wields its
owner's authority, so the camera reaches anything its owner controls. Split the
pair across two owners and the write fails quietly, and it should.

### Why the hooks need no `target` guard

Most `ON_<EVENT>` hooks fire on every object in the room, so a hook that reacts
to its own business must open with `if target is me:` (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). The camera is
the deliberate exception, because it is a watcher of the whole room and *wants*
to react to everyone. The engine already skips the mover's own hooks and fires
each remaining witness exactly once, so the movement hooks take no `target`
guard, and the listen trigger takes none either since the engine never fires it
on the speaker. Their only filter is `if enactor` to skip a sourceless event.
Confirmed with a second camera in the same room: each camera relays every line
once, with no double or crossed feed.

Two honest notes. First, `name(enactor)` is the true name, so a camera relays
"Wraith arrives." even for a mover hidden from the room's own bystanders, since
perception masking is a message-delivery concern and softcode reads the world
as it is. Decide whether that x-ray vision is a feature before you hang one
where sneaks matter. Second, `@teleport` skips the leave event by design, since
a placement is not a walk, so only walkers trip `ON_LEAVE`. A teleported
arrival still fires `ON_ENTER`, so a mover dropped in by teleport does register
on the feed.

## Build it

Start with the console in the office. `@teleport` positions the builder, and
the two commands below create the monitor and describe it:

```text
@teleport me = The Security Office
@create security monitor
drop security monitor
@desc security monitor = A bank of grainy feeds. WATCH to put an eye on the vault approach; UNWATCH to look away.
```

`watch` adds the caller to the monitor's `watchers` list. The list stores each
watcher's id so the relay can resolve the player later:

```text
@set security monitor/cmd_watch = '''
$watch:
ws = V('watchers') or []
if enactor.id not in ws:  # store the watcher's id, one row per player
    set_attr(me, 'watchers', ws + [enactor.id])
pemit(enactor, 'You settle in at the console. The antechamber feed flickers to life.')
'''
```

`unwatch` is the same list minus the caller:

```text
@set security monitor/cmd_unwatch = '''
$unwatch:
set_attr(me, 'watchers', [i for i in (V('watchers') or []) if i != enactor.id])
pemit(enactor, 'You look away from the monitor.')
'''
```

Now the camera, over in the antechamber. `feed` names its console, which the
relay resolves fresh on every line:

```text
@teleport me = Vault Antechamber
@create security camera
drop security camera
@desc security camera = A glass eye on a ceiling mount, cable disappearing into the wall.
@set security camera/powered = 1
@set security camera/feed = security monitor
```

The relay resolves the console, collects the watchers still in its room,
delivers a labelled line to each, and prunes the rest. The `powered` guard is
the sabotage switch: when it is zero the watcher list reads empty, so no line
goes out:

```text
@set security camera/relay = '''
m = get(V('feed', ''))
ws = (get_attr(m, 'watchers') or []) if (m and V('powered', 1)) else []
live = [w for w in [get('#' + str(i)) for i in ws] if w and loc(w) is loc(m)]  # only watchers still at the console
for w in live:
    pemit(w, f'[{name(me)}] {arg0}')
if m and len(live) != len(ws):  # someone wandered off; drop them from the list
    set_attr(m, 'watchers', [w.id for w in live])
'''
```

The three taps each hand one line to the relay. The listen trigger fires on
speech, and the two movement hooks fire as the camera witnesses walkers, one
call apiece:

```text
@set security camera/listen_feed = ^*: eval_attr(me, 'relay', f'{name(enactor)} says, "{arg0}"') if enactor else None
@set security camera/on_enter = eval_attr(me, 'relay', f'{name(enactor)} arrives.') if enactor else None
@set security camera/on_leave = eval_attr(me, 'relay', f'{name(enactor)} leaves.') if enactor else None
```

Finally the crew's counterplay, an Electronics check at -2 to kill the power
with [`skill_check`](../reference/softcode.md#fn-skill_check):

```text
@set security camera/cmd_cut = '''
$cut *:
if skill_check(enactor, 'electronics', -2):
    set_attr(me, 'powered', 0)
    remit(loc(me), f'{name(enactor)} snips a cable and the camera light dies.')
else:
    pemit(enactor, 'Sparks jump; the housing is trickier than it looks.')
'''
```

## Try it

In the office, settle in at the console:

```text
watch                        -> You settle in at the console. ...
```

Now have anyone act in the Vault Antechamber, and each line arrives labelled:

```text
(they say "psst")            -> [security camera] Zeke says, "psst"
(they walk out the duct)     -> [security camera] Zeke leaves.
(they crawl back in)         -> [security camera] Zeke arrives.
unwatch                      -> silence
```

Walk away from the console mid-watch and the next relayed line reaches only the
watchers still there, dropping you from the list on that same pass. And from
the antechamber side, the crew's answer, which zeroes the audience for everyone:

```text
cut camera                   -> (Electronics -2) ... the camera light dies.
```

## Going further

- **Multi-camera console:** keep `watchers` per camera name and a `$watch *`
  that picks a feed. The relay already knows which camera it is through
  `name(me)`.
- **Recording:** append each relayed line to a `log` list attribute on the
  monitor, capped with a slice as the [voice recorder](007_voice_recorder.md)
  caps its tape, and add a `$playback` command.
- **Two-way intercom:** a `$page *` on the monitor that
  [`remit`](../reference/softcode.md#fn-remit)s into
  `loc(get(V('camera')))`, which is the tap reversed. Because `remit` is plain
  delivery rather than speech, it will not trip the camera's own listen.
- **Combat coverage:** the camera can witness any event, so an `ON_ATTACK` tap
  turns it into a gun-camera that calls guards. See the propagation model in
  [events](../architecture/events.md).
