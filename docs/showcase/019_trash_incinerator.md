# 019. Trash Bin / Incinerator

> Checklist item 19 ([now]): *ON_RECEIVE, expire()/ON_EXPIRE, soft-delete pattern*

**What you'll build:** A municipal bin anything can be thrown into. Nothing
dies at once: junk sits through a grace period during which `rummage <item>`
undoes the mistake, and whatever overstays goes up in a gout of flame, on
schedule even across a server reboot.

**Concepts:** the **soft-delete pattern**, where discarding and destroying are
separate moments joined by a timestamp;
[`expire()`](../reference/softcode.md#fn-expire) as the reboot-safe countdown,
since the deadline lives on the item as `expires_at` rather than in any
running script; [`ON_EXPIRE`](../reference/softcode.md#lifecycle-hooks) as the
incinerator's voice; and a sweep of
[`contents(me)`](../reference/softcode.md#fn-contents) that leases arrivals no
matter which road they came in on.

It builds on the [basic container](014_basic_container.md) for the `container`
tag, the built-in `put`/`get from` machinery, and how a reaction hook reads an
action's payload.

## How it works

The finished bin is one tag, one number, and four short scripts. The
`container` tag lets it hold things, a `grace` attribute sets the reprieve, and
the scripts turn an ordinary open container into a soft-delete queue: putting
something in leases it, `rummage` cancels the lease, the world tick reaps
whatever the lease ran out on, and the bin narrates the burn. This section
answers four questions: why nothing is destroyed on the spot, where the
countdown lives so a reboot cannot lose it, how the lease reaches the item, and
who is allowed to touch a stranger's property.

### Why not destroy it the moment it's thrown away?

[`destroy_obj()`](../reference/softcode.md#fn-destroy_obj) is instant and has no
undo, which is a dangerous thing to park one typo away from a player's
inventory. So the bin never calls it. The bin is an ordinary open container,
where `put` and `get from` just work, and putting something in merely
*sentences* it: the item gets an `expires_at` timestamp of now plus the grace
period. Destroying is a later, separate event, and the gap between the two is
the grace period. That separation of a discard moment from a destroy moment,
joined by a timestamp, is the **soft-delete pattern**.

### Where does the countdown live, so a reboot can't lose it?

[`expire(item, seconds)`](../reference/softcode.md#fn-expire) writes
`expires_at` onto the item and does nothing else. The world tick then reaps it:
it finds every object whose `expires_at` has passed, fires `event:on_expire` on
it, and destroys it. Because the deadline is a persistent attribute on the item
and not a value held in a running script, a reboot changes nothing. The item
comes back with its `expires_at` intact and is reaped on schedule. This is the
[`wait()`](../reference/softcode.md#fn-wait) versus `expire()` split the
conventions warn about: a `wait()` timer lives in memory and dies with the
server, while `expire()` is carved into the object.

### How does the lease reach the item?

An [`ON_PUT`](../reference/softcode.md#lifecycle-hooks) hook is a *reaction*: it
runs after the engine has already moved the item, so by the time the hook fires
the item is sitting in [`contents(me)`](../reference/softcode.md#fn-contents)
(the before/apply/after trio, see
[action phases](../design/action-phases.md)). The hook could therefore lease
the arrival directly with `expire(adata('item'), V('grace', 60))`, since
[`adata('item')`](../reference/softcode.md#event-data-namespace) names exactly
what was just put in.

This bin does something more general. Its `on_put` only states the terms and
schedules a sweep on the next beat with
[`wait(0, 'trigger me/do_sweep')`](../reference/softcode.md#fn-wait); the
`do_sweep` script is the one place that stamps a lease, and it leases every item
in `contents(me)` that does not already carry one. Keeping the lease in a
sweep, rather than in the put hook, makes the bin correct no matter how
something arrived. A `put` fires `on_put`, but an item teleported in, carried in
by a conveyor, or moved by an admin's `@tele` fires no such hook, and the next
sweep still catches it. Re-sweeping costs nothing, because the
[`has_attr(o, 'expires_at')`](../reference/softcode.md#fn-has_attr) filter skips
anything already sentenced. The `wait` itself is in memory and spans a single
beat; the part that must survive a reboot, the countdown, is the persistent
`expires_at` the sweep writes.

A thing *handed* to the bin with `give` rather than `put` fires
[`ON_RECEIVE`](../reference/softcode.md#lifecycle-hooks) instead, the
recipient-side hook, which also lands the item first and then runs. Pointing an
`on_receive` at the same `do_sweep` would fold that road in too (see *Going
further*).

### How does the bin get to touch the item at all?

Both `do_sweep` and `rummage` reach inside things the player owns, which takes
two distinct authorities. A script runs with its object's authority, so the bin
may *mutate* what its owner controls: [`expire`](../reference/softcode.md#fn-expire)
and [`del_attr`](../reference/softcode.md#fn-del_attr) on a thrown-away item
succeed because the bin's owner controls the item. The bin may also *relocate*
anything standing inside itself, the room-owner teleport rule, because an object
controls its own interior, and that is what lets
[`teleport_obj`](../reference/softcode.md#fn-teleport_obj) hand a rescued item
back. A public bin should therefore be owned by an admin, so its scripts can
lease and return strangers' property under owner authority, the same rule as any
shared master object.

### Who narrates the burn?

When an item inside the bin expires, the reaper fires `event:on_expire` with the
*item* as its target, and the bin, as the item's container, witnesses it. So
`ON_EXPIRE` on the bin narrates every incineration with
[`remit`](../reference/softcode.md#fn-remit) to the room, without touching any
item's attributes. This hook takes no
[`target is me`](../reference/softcode.md#guard-on-target) guard on purpose: it
is a witness reacting to its contents, so `target` is the burning item, never
the bin. That is the opposite of `on_put`, which reacts to its *own* business
and so must guard, because an `ON_<EVENT>` hook fires on every object in the
room.

## Build it

Two of the four scripts are `'''` multi-line blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)); the
other two are single statements and stay on one line.

Create the bin, tag it a container so `put` and `get` work, drop it into the
room, give it a lid stencil, and set the grace period to sixty seconds:

```text
@create rubbish bin
@tag rubbish bin = container
drop rubbish bin
@desc rubbish bin = A dented municipal bin. Stenciled on the lid: CONTENTS INCINERATED WITHOUT NOTICE.
@set rubbish bin/grace = 60
```

Arrival is two steps. The `on_put` hook states the terms with
[`pemit`](../reference/softcode.md#fn-pemit) and schedules the sweep, where
[`V('grace', 60)`](../reference/softcode.md#fn-v) reads the `grace` attribute
with 60 as the fallback; then `do_sweep` leases every unsentenced thing in the
bin. The guard earns its place, because `on_put` fires on every object in the
room, so without it the bin would react to a `put` aimed at some other
container:

```text
@set rubbish bin/on_put = '''
if target is me:  # ON_PUT fires on every object in the room, so filter to puts aimed at this bin
    pemit(enactor, f"It lands with a clang. You have {V('grace', 60)} seconds to change your mind: rummage <item>.")
    wait(0, 'trigger me/do_sweep')  # lease on the next beat; do_sweep is the one place that stamps expires_at
'''
@set rubbish bin/do_sweep = [expire(o, V('grace', 60)) for o in contents(me) if not has_attr(o, 'expires_at')]
```

The pardon is a `$rummage` command. It finds the named item still in the bin
with [`trim`](../reference/softcode.md#fn-trim) and
[`name`](../reference/softcode.md#fn-name), clears its `expires_at` so the
reaper skips it, and teleports it back to the rescuer's hands:

```text
@set rubbish bin/cmd_rummage = '''
$rummage *:
found = [o for o in contents(me) if trim(arg0).lower() in name(o).lower()]
if found:
    it = found[0]
    del_attr(it, 'expires_at')      # clearing the timestamp cancels the sentence
    teleport_obj(it, enactor)        # the bin may relocate what stands inside it
    pemit(enactor, f'You fish the {name(it)} back out. Reprieved.')
else:
    pemit(enactor, 'You paw through the muck and come up empty.')
'''
```

The last word is `on_expire`, the bin's witness to each burn. It emits to the
room with [`loc(me)`](../reference/softcode.md#fn-loc) and takes no `target is
me` guard, because the thing that expired is an item inside the bin, not the bin
itself:

```text
@set rubbish bin/on_expire = remit(loc(me), 'The bin belches a gout of flame. Something is gone for good.')
```

Finally, two things worth regretting throwing away:

```text
@create banana peel
@create broken hourglass
```

## Try it

Throw the peel in and pull it straight back out:

```text
> put banana peel in rubbish bin
It lands with a clang. You have 60 seconds to change your mind: rummage <item>.

> rummage banana
You fish the banana peel back out. Reprieved.
```

`@examine banana peel` between those two commands shows the sentence itself: an
`expires_at` timestamp, stamped a beat after the clang by the deferred sweep and
gone again after the rummage. Now commit, and add a second item to burn
alongside it:

```text
> put banana peel in rubbish bin
It lands with a clang. You have 60 seconds to change your mind: rummage <item>.

> put broken hourglass in rubbish bin
It lands with a clang. You have 60 seconds to change your mind: rummage <item>.
```

Wait out the minute. Twice the room hears `The bin belches a gout of flame.
Something is gone for good.`, and the bin is empty. Restart the server
mid-sentence and the flame still arrives on time, because the countdown was
never in memory: it was written on each item as `expires_at`.

## Going further

- **A visible fuse:** the bin's description can read each item's `expires_at`
  against [`now()`](../reference/softcode.md#fn-now) and print the seconds
  remaining, a countdown you can watch through the muck.
- **A bin with standards:** an `on_check` ward that
  [`block()`](../reference/softcode.md#event-data-namespace)s `item:on_put` for
  anything tagged `quest`, so some things refuse to be thrown away
  ([021](021_ammo_pouch.md) is this ward with the polarity flipped).
- **Reprieve by rank:** gate `$rummage` behind the `use` lock
  (`@lock/use rubbish bin = ...`) so only janitors may unmake mistakes.
- **The compactor variant:** `on_expire` on the bin could
  [`create_obj`](../reference/softcode.md#fn-create_obj)`('a dense cube of
  refuse', [], me)` every few burns, conservation of mass minus the smell.
