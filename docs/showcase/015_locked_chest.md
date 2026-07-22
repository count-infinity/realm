# 015. Locked Chest & Key

> Checklist item 15 — [now] — *@lock, lock/unlock/pick commands, key items, gated ON_UNLOCK*

**What you'll build:** A sea chest that holds its loot behind a real
lock: the matching silver key opens it, a good lockpicker can defeat
it, and everyone else gets the hasp's polite refusal.

**Concepts:** composing the engine's three container conventions
(`container`, the `closed` tag, `locked` + `key_id`) on one thing, key
items (`unlocks`), the stock `lock`/`unlock`/`pick`/`use ... on`
commands, and `ON_UNLOCK` — a *gated* lifecycle hook — as the place to
hang reactions. The [basic container](014_basic_container.md) taught
the box; this teaches the lock.

## How it works

**Locks are two attributes, not a system.** `locked = true` makes
`open` refuse (with your `locked_msg`); `key_id` names the lock. Any
carried item whose `unlocks` matches that name powers the stock `lock`
and `unlock` commands — a key is just data on a thing, which is why a
keyring, a keycard, and a signet ring can all open the same chest.
This is the same machinery exits use, so everything in the
[lockable door](025_lockable_door.md) transfers to boxes verbatim.

One distinction worth keeping straight: `locked` is *physical state*
(what IS), while `@lock` sets *permission locks* (who MAY — traverse,
use, control). A chest can be unlocked yet still refuse a thief's
`get` through a permission lock; this build only needs the physical
kind.

**Three ways through, all built in:**

| Route | Needs | What the engine checks |
|---|---|---|
| `unlock chest` | the matching key in hand | `unlocks == key_id` |
| `pick chest` | skill | `lock_skill` roll at `-lock_difficulty` (carry `lockpicks`-tagged tools or improvise at -5) |
| `use silver key on chest` | the key | the keycard fast-path — toggles the lock each swipe |

**Reactions hang on the hooks.** `unlock` propagates `item:on_unlock`
as a *gated* event — an `on_check` ward could refuse it (a sealed
reliquary), and the chest's `ON_UNLOCK` script reacts after it
succeeds. We use it for a room-audible click: small, but it's the seam
every alarm, trap, and mimic build screws into.

## Build it

The chest, loaded then sealed — load the loot *before* closing, in the
order a real person would:

```text
@create sea chest
@tag sea chest = container
drop sea chest
@create string of pearls
put string of pearls in sea chest
close sea chest
```

The lock's identity and manners. The `locked_msg` names the command a
stuck player needs; `lock_skill`/`lock_difficulty` keep the burglar's
route open at fair odds:

```text
@set sea chest/key_id = chest_silver
@set sea chest/locked_msg = The hasp holds fast. A silver keyhole winks at you.
@set sea chest/lock_skill = lockpicking
@set sea chest/lock_difficulty = 2
@set sea chest/on_unlock = remit(loc(me), 'The lock springs with a bright click.')
```

Cut the key, and use it to lock up (`@create` leaves it in your hand —
`lock` needs it there):

```text
@create silver key
@set silver key/unlocks = chest_silver
lock sea chest
```

That last line answers `You lock sea chest with silver key.` — the
chest is armed.

## Try it

Keyless first (hand the chest to a friend, or drop the key):

```text
open sea chest        -> The hasp holds fast. A silver keyhole winks at you.
unlock sea chest      -> You don't have the key.
pick sea chest        -> The lock on sea chest resists your attempt.  (improvising is -5)
```

Carry a `lockpicks`-tagged kit and `pick sea chest` becomes a fair
fight — lockpicking at -2 — ending in `Click. You defeat the lock on
sea chest.`

With the key in hand, the whole cycle:

```text
unlock sea chest      -> You unlock sea chest with silver key.   (the room hears the click)
open sea chest        -> You open the sea chest.
get string of pearls from sea chest
close sea chest
lock sea chest        -> You lock sea chest with silver key.
```

And the fast path — one swipe toggles the state:

```text
use silver key on sea chest   -> You swipe silver key: sea chest unlocks.
use silver key on sea chest   -> You swipe silver key: sea chest locks.
```

## Engine gaps

- The `use <key> on <chest>` fast-path and a successful `pick` both
  toggle `locked` with a direct write — no `item:on_lock`/`on_unlock`
  event propagates, so the chest's `ON_UNLOCK` click (and any alarm you
  wire there) fires only on the `unlock` command. Already filed from
  the [lockable door](025_lockable_door.md); on a chest it just means
  reactions hear the key-turner, not the swiper or the safecracker.

## Going further

- **Alarmed:** swap the click remit for
  `act('guard post', 'The chest lock clicks open!')` — the
  [guard response](071_guard_response.md) pattern picks it up from
  there.
- **A trapped lock:** `pick` failure leaves no event, but the *open*
  does — a `ON_OPEN` script plus an `armed` attribute is the
  [landmine](049_landmine.md)'s boom pattern in a box.
- **Skeleton keys:** several chests sharing one `key_id` make a master
  key; several keys with the same `unlocks` make spares. It's all just
  matching strings.
- **Refuse to relock:** an `on_check` ward with
  `block('The mechanism is sprung.') if atype == 'item:on_lock' else None`
  makes a chest that, once opened, never locks again — the gated hooks
  work both directions.
