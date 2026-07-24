# 006. Flashlight

> Checklist item 6 ([now]): *light/dark tags, add_tag/remove_tag, on_tick drain*

**What you'll build:** A clicky flashlight that defeats dark rooms, until
its battery runs down. Along the way: how REALM's darkness actually
works, and why a lit flashlight in your pocket helps nobody.

**Concepts:** the engine's `dark`/`light` tag conventions (perception
is data), [`add_tag`](../reference/softcode.md#fn-add_tag) and
[`remove_tag`](../reference/softcode.md#fn-remove_tag) as a state
toggle, the *wielded* rule for carried lights, a `script_ticker`
running [`on_tick`](../reference/softcode.md#lifecycle-hooks) as
resource drain, and messaging an object's holder versus its room.

Builds on the [magic 8-ball](005_magic_8ball.md). The dark room you
dig here is a natural home for the [secret door](027_secret_door.md)'s
tricks.

## How it works

**Darkness is a tag; so is light.** A room tagged `dark` renders as
`It is pitch black here. You can't see a thing.` and nothing else: no
contents, no exits line, and things on the floor can't be targeted.
The engine lifts the darkness when the room contains any `light`-tagged
object, or when someone present is *wielding* one. That is the whole
system: no light levels, no Python, only perception rules keyed off two
tags, which means a **flashlight is just an object that can gain and
lose the `light` tag**.

**The wielded rule.** A carried light only counts if it is held up: the
`wield` builtin (alias `ready`) marks it with the `wielded` tag, and a
lantern buried in your pack lights nothing. Clicking the beam on is
therefore not enough, and you will stand in the dark holding a lit
flashlight until you either `wield` it or `drop` it (floor lights need
no wielder, and they light the room for everyone). Nightvision and
admin sight bypass all of this.

**Batteries are a countdown on a heartbeat.** The `script_ticker`
behavior runs `on_tick` on a cadence; the script spends charge *only
while lit*, warns at one charge left, and at zero strips the `light`
tag, so darkness comes back mid-expedition, which is the whole drama of
a flashlight. One subtlety: a carried object's location is its
*holder*, so the warning goes
[`pemit`](../reference/softcode.md#fn-pemit)`(holder)` when a player
has it, [`remit`](../reference/softcode.md#fn-remit)`(room)` when it
lies on the floor.

**The toggle is a three-way branch.** Lit clicks off; dark and charged
clicks on; a dead battery gives the saddest click in games. All state
lives in two places (the `light` tag, the `battery` attribute), so
`@examine flashlight` tells you everything.

## Build it

The scripts here are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

**The torch itself, built in the light.** `@create` leaves it in your
inventory, and this build never drops it, because everything
interesting about a flashlight happens in someone's hand:

```text
@create flashlight
@desc flashlight = A rubber-armored pocket torch with a fat clicky button. Three cells rattle in the tube.
```

**Charge, then toggle.** The cell is one data attribute. The `$click`
trigger reads the beam state with
[`has_tag`](../reference/softcode.md#fn-has_tag) and branches three
ways: lit clicks off, unlit with charge left clicks on, and a dead cell
is just noise. [`V('battery', 0)`](../reference/softcode.md#fn-v) reads
the flashlight's own `battery` with a default:

```text
@set flashlight/battery = 3
@set flashlight/cmd_click = '''
$click:
if has_tag(me, 'light'):
    remove_tag(me, 'light')
    pemit(enactor, 'Click. The beam dies.')
elif V('battery', 0) > 0:
    add_tag(me, 'light')
    pemit(enactor, 'Click. A hard white beam snaps on.')
else:
    pemit(enactor, 'Click. Click. Nothing. The battery is dead.')
'''
```

**The drain.** `interval:10` runs `on_tick` every ten world heartbeats
(about forty seconds at the default beat). Each lit beat spends one
charge with [`decr`](../reference/softcode.md#fn-decr); at one charge
the beam flickers, at zero it dies and the `light` tag goes with it.
Then the message routes to whoever can hear it, and unlit beats spend
nothing:

```text
@behavior flashlight = script_ticker, interval:10
@set flashlight/on_tick = '''
if has_tag(me, 'light'):
    left = decr('battery')  # decr returns the NEW value
    msg = ''
    if left <= 0:
        remove_tag(me, 'light')
        msg = 'The flashlight gutters and dies.'
    elif left == 1:
        msg = 'The flashlight flickers; its battery is nearly spent.'
    h = loc(me)  # a carried object's location is its holder, not the room
    if msg and h:
        if has_tag(h, 'player'):
            pemit(h, msg)
        else:
            remit(h, msg)
'''
```

[`loc(me)`](../reference/softcode.md#fn-loc) is the routing pivot: a
flashlight in someone's hand is *inside* that person, so the holder
gets a private `pemit`, while one lying on the floor is inside the
room, which hears the same line room-wide through `remit`.

**Somewhere to need it.** Dig down and put out the lights. `@tag`
writes the same `dark` tag the perception engine reads:

```text
@dig The Undercroft = down, up
down
@tag here = dark
```

## Try it

Standing in the Undercroft, flashlight in your pack:

```text
look                 -> It is pitch black here. You can't see a thing.
click                -> Click. A hard white beam snaps on.
look                 -> still pitch black! The beam is lit, in your pack.
wield flashlight     -> You ready flashlight.
look                 -> The Undercroft, in full detail.
```

That middle beat is the wielded rule earning its keep. Now let the
battery go: each `@tr flashlight/on_tick` forces a drain beat, which
works because `on_tick` holds bare code (the
[magic 8-ball](005_magic_8ball.md) covers what `@tr` can and cannot
fire). The first beat spends a charge silently, the second warns
`The flashlight flickers; its battery is nearly spent.`, and the third
prints `The flashlight gutters and dies.`, at which point `look` is
pitch black again and `click` answers
`Click. Click. Nothing. The battery is dead.` Alternatively `drop` a
lit flashlight: the room lights for *everyone*, no wielding required,
and unlit ticks never drain the cell.

## Going further

- **Spare batteries:** a `battery cell` item and a `$reload` command:
  [`destroy_obj`](../reference/softcode.md#fn-destroy_obj) the cell and
  reset the attribute. The [vending machine](002_vending_machine.md)
  can sell them.
- **Better cells:** `@behavior/set flashlight = script_ticker,
  interval:30` retunes the drain cadence in place. A military torch is
  `@clone flashlight = military torch` (a clone keeps attributes, tags,
  and behaviors) plus a fatter `battery` and its own `@behavior/set`.
- **Nightvision goggles instead:** an item tagged `wearable` with
  `grants_tags = ["nightvision"]` skips the whole battery economy,
  because the `wear` command grants and reclaims the tags itself; the
  [dark room](038_dark_room.md) tour builds exactly these goggles.
- **Light as a puzzle key:** a `dark`-tagged vault hides its exits line
  and makes floor loot untargetable, so the flashlight becomes the
  dungeon's real key; pair it with the
  [secret door](027_secret_door.md)'s concealed exit for a vault with
  two locks. One honest note: the `search` roll itself is light-blind
  (darkness aids `hide`, not Observation), so what the dark really
  locks is seeing and taking.
