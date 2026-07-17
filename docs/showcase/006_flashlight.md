# 006. Flashlight

> Checklist item 6 — [now] — *light/dark tags, add_tag/remove_tag, on_tick drain*

**What you'll build:** A clicky flashlight that defeats dark rooms —
until its battery runs down. Along the way: how REALM's darkness
actually works, and why a lit flashlight in your pocket helps nobody.

**Concepts:** the engine's `dark`/`light` tag conventions (perception
is data), `add_tag`/`remove_tag` as a state toggle, the *wielded* rule
for carried lights, `script_ticker` + `on_tick` resource drain,
messaging an object's holder vs. its room.

Builds on the [magic 8-ball](005_magic_8ball.md). The dark room you
dig here is a natural home for the [secret door](027_secret_door.md)'s
tricks.

## How it works

**Darkness is a tag; so is light.** A room tagged `dark` renders as
`It is pitch black here. You can't see a thing.` — no contents, no
exits, and things on the floor can't be targeted. The engine lifts the
darkness when the room contains any `light`-tagged object, OR when
someone present is *wielding* one. That's the whole system: no light
levels, no Python — perception rules keyed off two tags, which means a
**flashlight is just an object that can gain and lose the `light`
tag**.

**The wielded rule.** A carried light only counts if it's held up —
the `wield` builtin (alias `ready`) marks it `wielded`, and a lantern
buried in your pack lights nothing. Clicking the beam on is therefore
not enough: you'll stand in the dark holding a lit flashlight until
you either `wield` it or `drop` it (floor lights need no wielder, and
they light the room for everyone). Nightvision and admin sight bypass
all of this.

**Batteries are a countdown on a heartbeat.** The `script_ticker`
behavior runs `on_tick` on a cadence; the script decrements `battery`
*only while lit*, warns at one tick left, and at zero strips the
`light` tag — darkness comes back mid-expedition, which is the whole
drama of a flashlight. One subtlety: a carried object's location is
its *holder*, so the warning goes `pemit(holder)` when a player has
it, `remit(room)` when it lies on the floor.

**Toggle, guarded.** `$click` is a three-way branch: lit → off; dark
and charged → on; dead battery → the saddest click in games. All
state in two places (`light` tag, `battery` attribute), so `@examine
flashlight` tells you everything.

## Build it

The torch itself, built in the light — a data attribute for charge,
one command to toggle:

```text
@create flashlight
@set flashlight/battery = 3
@set flashlight/cmd_click = $click: lit = has_tag(me, 'light'); b = V('battery', 0); (remove_tag(me, 'light'), pemit(enactor, 'Click. The beam dies.')) if lit else ((add_tag(me, 'light'), pemit(enactor, 'Click. A hard white beam snaps on.')) if b > 0 else pemit(enactor, 'Click. Click. Nothing. The battery is dead.'))
```

The drain. `interval:10` heartbeats between drains; each lit tick
counts down, warns at 1, kills the beam at 0 — and routes the message
to whoever can hear it:

```text
@behavior flashlight = script_ticker, interval:10
@set flashlight/on_tick = lit = has_tag(me, 'light'); b = V('battery', 0); left = b - 1 if lit else b; decr('battery') if lit else None; remove_tag(me, 'light') if lit and left <= 0 else None; msg = 'The flashlight flickers; its battery is nearly spent.' if lit and left == 1 else ('The flashlight gutters and dies.' if lit and left <= 0 else ''); h = loc(me); (pemit(h, msg) if has_tag(h, 'player') else remit(h, msg)) if msg and h else None
```

Somewhere to need it — dig down and put out the lights (`@tag` writes
the same tag the perception engine reads):

```text
@dig The Undercroft = down, up
down
@tag here = dark
```

## Try it

Standing in the Undercroft, flashlight in hand:

```text
look                 -> It is pitch black here. You can't see a thing.
click                -> Click. A hard white beam snaps on.
look                 -> ...still pitch black! It's lit -- in your pack.
wield flashlight     -> You ready flashlight.
look                 -> The Undercroft, in full detail.
```

That middle beat is the wielded rule earning its keep. Now let the
battery go (each `@tr flashlight/on_tick` forces a drain beat):
first `The flashlight flickers; its battery is nearly spent.`, then
`The flashlight gutters and dies.` — and `look` is pitch black again.
`click` answers `Click. Click. Nothing. The battery is dead.`
Alternatively `drop` a lit flashlight: the room lights for *everyone*,
no wielding required — and unlit ticks never drain the cell.

## Going further

- **Spare batteries:** a `battery cell` item and a `$reload` command —
  `destroy_obj` the cell, reset the attribute. The vending machine
  (002) can sell them.
- **Better cells:** put `drain_interval` in data and re-attach the
  behavior with a different `interval:` — a military torch is a
  `@clone` plus two `@set`s.
- **Nightvision goggles instead:** a `wearable` item with
  `grants_tags = ["nightvision"]` skips the whole battery economy —
  the engine's wear system does it all (see the manipulation
  builtins).
- **Light as a puzzle key:** a `dark`-tagged vault plus item 27's
  concealed exit — `search` can't find what nobody can see, so the
  flashlight becomes the dungeon's real key.
