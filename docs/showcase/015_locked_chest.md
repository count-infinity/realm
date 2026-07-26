# 015. Locked Chest & Key

> Checklist item 15 ([now]): *@lock, lock/unlock/pick commands, key items, gated ON_UNLOCK*

**What you'll build:** A sea chest that holds its loot behind a real
lock: the matching silver key opens it, a good lockpicker can defeat
it, and everyone else gets the hasp's polite refusal.

**Concepts:** stacking the built-in container conventions on one object
(the `container`, `closed`, and `locked` tags plus a `key_id`
attribute), key items (`unlocks`), the stock `lock`/`unlock`/`pick`/`use
... on` commands, and [`ON_UNLOCK`](../reference/softcode.md#lifecycle-hooks),
a *gated* lifecycle hook, as the place to hang reactions. The
[basic container](014_basic_container.md) taught the box; this teaches
the lock.

## How it works

A sea chest is the [basic container](014_basic_container.md) with a lock
added, and the lock is not a subsystem. It is the `locked` tag (which
bars `open`), a `key_id` attribute (which names the lock), and a key
item carrying a matching `unlocks` attribute. The engine ships every way
a player reaches the lock, so the only softcode is one small reaction.
This section covers what the tag and attribute are, the three built-in
routes through the lock, and where a reaction attaches.

### A lock is a tag and an attribute, not a system

The `locked` tag makes `open` refuse, printing your `locked_msg`, and
the `key_id` attribute names the lock. Any carried item whose `unlocks`
attribute equals that `key_id` powers the stock `lock` and `unlock`
commands, so a key is just data on a thing, which is why a keyring, a
keycard, and a signet ring can all open the same chest. This is the same
machinery exits use, so everything in the
[lockable door](025_lockable_door.md) transfers to a box unchanged.

Keep one distinction straight: the `locked` tag is *physical state*
(what is), whereas `@lock` sets *permission locks* (who may traverse,
use, or control the object). A chest can be unlocked yet still refuse a
thief's `get` through a permission lock, but this build needs only the
physical kind.

### Three ways through, all built in

| Route | Needs | What the engine checks |
|---|---|---|
| `unlock chest` | the matching key in hand | a carried `unlocks` equals the chest's `key_id` |
| `pick chest` | skill | a `lock_skill` roll at `-lock_difficulty` (carry `lockpicks`-tagged tools, or improvise at -5) |
| `use silver key on chest` | the key | the keycard fast-path, which toggles the lock on each swipe |

### One hook for all three routes

All three routes converge on a single gated event, `item:on_unlock`.
The `unlock` command fires it, a successful `pick` fires it with
`picked` set in the
[event data](../reference/softcode.md#event-data-namespace), and an
unlocking swipe (`use silver key on chest`) fires it too, so one
[`ON_UNLOCK`](../reference/softcode.md#lifecycle-hooks) reaction answers
the key, the jimmy, and the card alike. The event is *gated*: an
`on_check` ward can refuse it (a sealed reliquary), and the reaction
runs only if the unlock actually happened. We use it for a room-audible
click with [`remit`](../reference/softcode.md#fn-remit), which is small
but is the same attachment point every alarm, trap, and mimic build
uses.

### How the chest knows the click is its own

An [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook fires on
*every* object in the room, not only the one acted on, so the reaction
opens with [`if target is me`](../reference/softcode.md#guard-on-target).
Without the guard, unlocking any other lock in the room would make this
chest announce a click it never heard. Because the reaction runs *after*
the effect (the [action-phases trio](../design/action-phases.md):
`on_check` sees the world before, `ON_<EVENT>` sees it after), the chest
is already unlocked when the script runs, and it announces to the scene
through the unlocker with [`loc(enactor)`](../reference/softcode.md#fn-loc)
rather than assuming where the chest itself sits (which matters the day
the locked thing is something a player is carrying).

## Build it

**The chest.** Create it, switch on the container verbs with the
`container` tag, and set it down:

```text
@create sea chest
@tag sea chest = container
drop sea chest
```

**Load, then seal.** Put the loot in while the chest is still open, then
close it, in the order a real person would:

```text
@create string of pearls
put string of pearls in sea chest
close sea chest
```

**The lock's identity and manners.** `key_id` names the lock,
`locked_msg` is the refusal `open` prints while it is locked (so name
the command a stuck player needs), and `lock_skill` with
`lock_difficulty` keep the burglar's route open at fair odds:

```text
@set sea chest/key_id = chest_silver
@set sea chest/locked_msg = The hasp holds fast. A silver keyhole winks at you.
@set sea chest/lock_skill = lockpicking
@set sea chest/lock_difficulty = 2
```

**The audible click.** One reaction on the gated `on_unlock` announces
the unlock to the room. It fires on every object present, so it guards
on `target is me`, and it reaches the scene through the unlocker's
location:

```text
@set sea chest/on_unlock = if target is me: remit(loc(enactor), 'The lock springs with a bright click.')  # on_unlock fires on every object in the room; react only when the chest is the target
```

**Cut the key and arm the chest.** `@create` leaves the key in your
hand, which is where `lock` needs it:

```text
@create silver key
@set silver key/unlocks = chest_silver
lock sea chest
```

That last line answers `You lock sea chest with silver key.`, and the
chest is armed.

## Try it

Keyless first (hand the chest to a friend, or drop the key). Each
refusal names the way forward:

```text
open sea chest        -> The hasp holds fast. A silver keyhole winks at you.
unlock sea chest      -> You don't have the key.
pick sea chest        -> The lock on sea chest resists your attempt.  (improvising is -5)
```

Carry a `lockpicks`-tagged kit and `pick sea chest` becomes a fair
fight, lockpicking at -2, ending in `Click. You defeat the lock on sea
chest.` A successful pick fires the same gated `ON_UNLOCK` (with `picked`
set), so the room hears the click on a jimmy exactly as on a key.

With the key in hand, the whole cycle, and the room hears the click the
moment it unlocks:

```text
unlock sea chest      -> You unlock sea chest with silver key.
                         The lock springs with a bright click.
open sea chest        -> You open the sea chest.
get string of pearls from sea chest
close sea chest
lock sea chest        -> You lock sea chest with silver key.
```

And the fast path, where one swipe toggles the state. The unlocking
swipe fires the same gated `ON_UNLOCK`, so the click rings here too; the
relocking swipe fires `ON_LOCK`, which carries no script, so it is
silent:

```text
use silver key on sea chest   -> You swipe silver key: sea chest unlocks.
                                 The lock springs with a bright click.
use silver key on sea chest   -> You swipe silver key: sea chest locks.
```

## Going further

- **Alarmed:** swap the click's
  [`remit`](../reference/softcode.md#fn-remit) for
  [`act('guard post', 'The chest lock clicks open!')`](../reference/softcode.md#fn-act),
  and the [guard response](071_guard_response.md) pattern takes it from
  there.
- **A trapped lock:** a failed `pick` leaves no event, but `open` does,
  so an `ON_OPEN` script plus an `armed` attribute is the
  [landmine](049_landmine.md)'s boom pattern in a box.
- **Skeleton keys:** several chests sharing one `key_id` make a master
  key, and several keys sharing one `unlocks` make spares. It is all
  just matching strings.
- **Refuse to relock:** `item:on_lock` is gated too, so an `on_check`
  ward of `block('The mechanism is sprung.') if atype == 'item:on_lock'
  else None` refuses every attempt to lock the chest, the mirror image
  of the unlock reaction. The gated hooks work both directions.
