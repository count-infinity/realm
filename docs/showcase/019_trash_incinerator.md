# 019. Trash Bin / Incinerator

> Checklist item 19 — [now] — *ON_RECEIVE, expire()/ON_EXPIRE, soft-delete pattern*

**What you'll build:** A municipal bin anything can be thrown into.
Nothing dies at once — junk sits through a grace period during which
`rummage <item>` undoes the mistake; whatever overstays goes up in a
gout of flame, and keeps going up even across a server reboot.

**Concepts:** the **soft-delete pattern** ("discarded" and "destroyed"
are separate moments, joined by a timestamp), `expire()` as the
reboot-safe countdown — the lease lives *on the item* as
`expires_at`, not in any script's memory — `ON_EXPIRE` as the
incinerator's voice, and the deferred-sweep idiom for reacting to
arrivals a hook can't name.

## How it works

**Never destroy on receipt.** `destroy_obj()` is instant and
unrecoverable — a terrible thing to park one typo away from a
player's inventory. So the bin is an ordinary open container (`put`
and `get from` just work), and putting something in merely *sentences*
it: the item gets `expires_at`, now + grace. The world tick reaps
anything past its timestamp: `ON_EXPIRE` fires, then the object is
destroyed. Because the sentence is an attribute on the item, a reboot
changes nothing — this is exactly the `wait()` vs `expire()` split the
conventions warn about: `wait()` dies with the server, `expire()` is
carved into the object.

**The deferred sweep.** One timing fact from
[014](014_basic_container.md): event hooks fire while the action is
still being gated, *before* the item lands — and an `ON_PUT` script
has no `adata()` to name the incoming item anyway (only wards see the
action payload). So the bin's `ON_PUT` does two things: tells the
depositor the terms, and schedules `wait(0, 'trigger me/do_sweep')` —
one beat later, the item *is* inside, and the sweep leases everything
in `contents(me)` that doesn't already have a lease. The `wait` is
in-memory, but it spans milliseconds; the part that must survive a
reboot — the countdown itself — is the persistent `expires_at`.

**Rescue is just deleting the timestamp.** `$rummage <item>` clears
`expires_at` and hands the item back. The bin may do both because of
two authority rules: it can *mutate* what its owner controls, and it
can *relocate* anything standing inside itself (the room-owner
teleport rule — the bin owns its own interior). Throw it back in and
the next sweep issues a fresh sentence: the grace period restarts,
which is what a player expects.

**The bin eulogizes.** When something inside the bin expires, the
reaper fires `event:on_expire` with the item as target — and the
*bin*, as the place where it happened, is a witness. So `ON_EXPIRE` on
the bin narrates every incineration without touching any item's
attributes. (A public bin should be owned by an admin so its scripts
can lease strangers' property — owner authority, the same rule as any
shared master object.)

## Build it

The bin, its terms, and its lid stencil:

```text
@create rubbish bin
@set rubbish bin/container = true
drop rubbish bin
@desc rubbish bin = A dented municipal bin. Stenciled on the lid: CONTENTS INCINERATED WITHOUT NOTICE.
@set rubbish bin/grace = 60
```

Arrival: state the terms, then defer the sweep one beat:

```text
@set rubbish bin/on_put = pemit(enactor, f"It lands with a clang. You have {V('grace', 60)} seconds to change your mind: rummage <item>."); wait(0, 'trigger me/do_sweep')
@set rubbish bin/do_sweep = [expire(o, V('grace', 60)) for o in contents(me) if not has_attr(o, 'expires_at')]
```

The pardon, and the last word:

```text
@set rubbish bin/cmd_rummage = $rummage *: found = [o for o in contents(me) if trim(arg0).lower() in name(o).lower()]; it = found[0] if found else None; (del_attr(it, 'expires_at'), teleport_obj(it, enactor), pemit(enactor, f'You fish the {name(it)} back out. Reprieved.')) if it else pemit(enactor, 'You paw through the muck and come up empty.')
@set rubbish bin/on_expire = remit(loc(me), 'The bin belches a gout of flame. Something is gone for good.')
```

Something to regret throwing away:

```text
@create banana peel
@create broken hourglass
```

## Try it

```text
put banana peel in rubbish bin
   -> It lands with a clang. You have 60 seconds to change your mind: rummage <item>.
rummage banana
   -> You fish the banana peel back out. Reprieved.
```

`@examine` the peel between those two lines and you'll see the
sentence itself: an `expires_at` timestamp, set a beat after the clang
and gone after the rummage. Now commit:

```text
put banana peel in rubbish bin
put broken hourglass in rubbish bin
```

Wait out the minute. Twice, the room hears `The bin belches a gout of
flame. Something is gone for good.` — and the bin is empty. Restart
the server mid-sentence and the flame still comes on schedule: the
countdown was never in RAM.

## Engine gaps

- Same payload gap as [018](018_refrigerator.md): `ON_PUT` (and
  `ON_RECEIVE`) scripts cannot reference the arriving item — `adata()`
  is ward-only — hence the `wait(0)` + sweep idiom instead of leasing
  the item directly in the hook. A one-beat window where a restart
  leaves an unleased item in the bin is the cost; the next deposit's
  sweep picks up any such stragglers.

## Going further

- **A visible fuse:** the bin's description can read each item's
  `expires_at` against `now()` and print seconds remaining — a
  countdown you can watch through the muck.
- **An incinerator with standards:** an `on_check` ward that
  `block()`s `item:on_put` for anything tagged `quest` — some things
  refuse to be thrown away ([021](021_ammo_pouch.md) is this ward with
  the polarity flipped).
- **Reprieve by rank:** gate `$rummage` behind the `use` lock
  (`@lock/use rubbish bin = ...`) so only janitors may unmake
  mistakes.
- **The compactor variant:** `ON_EXPIRE` on the bin could
  `create_obj('a dense cube of refuse', [], me)` every few burns —
  conservation of mass, minus the smell.
