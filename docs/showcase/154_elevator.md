# 154. Elevator

> Checklist item 154 — now — *exit relinking, door-state attrs, a shared brain via eval_attr*

**What you'll build:** A two-floor elevator. The car is a room that
never actually moves — press a button inside, or thumb a CALL button on
a landing, and the car's door *relinks* to your floor while the far
landings seal shut. A bell dings, the doors part, and you step out
somewhere new. The whole illusion is exits changing where they point.

**Concepts:** an exit's `destination` is just data you can rewrite
([tutorial 033](033_portal_pair.md)); the **`closed` door-state tag**
([tutorial 025](025_lockable_door.md)) as "the car isn't here"; one
**shared routine** (`serve`) that both the in-car panel and the landing
buttons call with `eval_attr`, so the moving logic lives in exactly one
place.

## How it works

**The car is a fixed room; only exits move.** The car has one exit,
`doors`, whose `destination` names the floor it currently opens onto.
Each landing has an `elevator` exit that always points *into* the car.
"Calling the car to floor 2" is two writes: relink `doors` to point at
floor 2, and drop the `closed` tag from floor 2's `elevator` while
adding it to every other floor's. Nobody teleports; the car sits still
and the doors lie about where they lead — which is exactly what a real
elevator does.

**One brain, two front-ends.** The move-the-car logic is a `serve`
attribute on the car: give it a target floor's room id and it relinks
`doors`, opens that floor, seals the rest, and narrates. The in-car
`$press N` and each landing's `$call` are thin shells that resolve a
target floor and hand it to `serve` via `eval_attr` (Penn's `u()`), so
the logic is written **once**. `eval_attr` runs with the caller's
authority — every button is builder-owned, so it may rewrite the car's
doors and the landings' seals.

**Door-state, not locks.** A sealed `elevator` exit uses the engine's
`closed` tag: walk into it and you get "The elevator is closed" — the
car simply isn't at your floor. Call it and the tag lifts.

## Build it

Two floors and the car, then wire the exits — the car's `doors` and
each landing's `elevator`:

```text
@dig The Lobby
@teleport me = The Lobby
@dig The Mezzanine
@teleport me = The Lobby
@dig The Elevator Car
@teleport me = The Elevator Car
@open doors = The Lobby
@teleport me = The Lobby
@open elevator = The Elevator Car
@teleport me = The Mezzanine
@open elevator = The Elevator Car
```

The car's memory — the ordered `stops` list and a handle to its own
`doors` exit:

```text
@teleport me = The Elevator Car
@eval car = here; lob = get('The Lobby'); mez = get('The Mezzanine'); set_attr(car, 'stops', [lob.id, mez.id]); doors = [e for e in contents(car) if has_tag(e,'exit') and name(e)=='doors'][0]; set_attr(car, 'doors', '#'+doors.id); result='stops set'
```

The one routine that moves the car. `arg0` is the target floor's room
id, `arg1` the car's id; it relinks `doors`, then walks every stop —
opening the target, sealing the rest:

```text
@set The Elevator Car/serve = car = get('#' + str(arg1)); doors = get(get_attr(car, 'doors')); set_attr(doors, 'destination', arg0); [ (remove_tag([e for e in contents(get('#'+str(fid))) if has_tag(e,'exit') and name(e)=='elevator'][0], 'closed'), remit(get('#'+str(fid)), 'A bell chimes; the elevator doors part.')) if str(fid) == str(arg0) else (add_tag([e for e in contents(get('#'+str(fid))) if has_tag(e,'exit') and name(e)=='elevator'][0], 'closed'), remit(get('#'+str(fid)), 'The elevator doors slide shut and it departs.')) for fid in get_attr(car, 'stops') ]; remit(car, 'The car glides to a stop.'); result='served'
```

The in-car panel — press a floor number, and it hands that stop to
`serve`:

```text
@create control panel
@desc control panel = Two buttons: PRESS 1 (Lobby), PRESS 2 (Mezzanine).
drop control panel
@set control panel/cmd_press = $press *: car = here; n = int(trim(arg0)); stops = get_attr(car, 'stops'); (pemit(enactor, 'No such floor.') if n < 1 or n > len(stops) else (pemit(enactor, 'You press ' + str(n) + '.'), eval_attr(car, 'serve', str(stops[n-1]), car.id)))
```

A CALL button on each landing. `here` is the landing the presser is
standing in, so "call the car here" is `serve(here.id)`:

```text
@teleport me = The Lobby
@create call button
@desc call button = A brass CALL button, worn bright with use.
drop call button
@set call button/cmd_call = $call: car = get('The Elevator Car'); pemit(enactor, 'You thumb the call button.'); eval_attr(car, 'serve', here.id, car.id)
@teleport me = The Mezzanine
@create call button
@desc call button = A brass CALL button, worn bright with use.
drop call button
@set call button/cmd_call = $call: car = get('The Elevator Car'); pemit(enactor, 'You thumb the call button.'); eval_attr(car, 'serve', here.id, car.id)
```

Start the car parked at the Lobby — seal the Mezzanine landing:

```text
@teleport me = The Elevator Car
@eval mez = get('The Mezzanine'); ex = [e for e in contents(mez) if has_tag(e,'exit') and name(e)=='elevator'][0]; add_tag(ex, 'closed'); result='sealed mezz'
@teleport me = The Lobby
```

## Try it

From the Lobby (the car is parked here):

```text
elevator            -> you step into The Elevator Car
press 2             -> You press 2. "The car glides to a stop."
doors               -> you step out onto The Mezzanine
```

Now the car sits at the Mezzanine. A friend in the Lobby:

```text
elevator            -> The elevator is closed.   (the car isn't there)
call                -> You thumb the call button. A bell chimes...
elevator            -> the doors are open again; they ride up
```

`@examine` a landing's `elevator` exit mid-ride: it carries the
`closed` tag exactly when the car is elsewhere, and its twin the
`doors` exit's `destination` always names the floor the car is serving.

## Going further

- **More floors:** append each new landing's room id to the car's
  `stops` and give it an `elevator` exit — `serve` already walks the
  whole list, so nothing else changes.
- **A queue:** stash pressed floors in a `queue` attribute and give the
  car a `script_ticker` ([tutorial 036](036_weather_system.md)) that
  `serve`s the next one each tick — a car that visits floors in order
  instead of teleporting between them.
- **Between-floors danger:** while `serve` runs, seal *all* landings for
  a tick before opening the target, and hang an [airlock](032_airlock.md)
  style interlock so `open doors` fails while the car is "moving."
- **An out-of-order light:** a `broken` tag the panel checks first,
  refusing service with a flavor line — maintenance as content.
