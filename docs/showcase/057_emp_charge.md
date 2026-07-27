# 057. EMP Charge

> Checklist item 57 ([now]): *tag-targeted loops, temporary state with timed restore*

**What you'll build:** A one-shot EMP charge that sweeps the room it is set
off in, kills every `electronic`-tagged device for thirty seconds, then
restores them as its own casing crumbles, plus two gadgets to prove it on.

**Concepts:** tags as a device convention (`electronic` and `disabled`), a
sweep loop over [`contents`](../reference/softcode.md#fn-contents), remembering
what you disabled in a list attribute so the restore lifts exactly that, and
[`expire`](../reference/softcode.md#fn-expire) with its
[`ON_EXPIRE`](../reference/softcode.md#lifecycle-hooks) hook as a persistent
restore timer.

## How it works

The finished charge is one prop you set down and trigger. Its pulse sweeps the
room, tags every device dark, writes down which ones it hit, and starts a
thirty-second countdown on itself. When that countdown elapses the charge
restores exactly the devices it recorded and then crumbles, all in one event.
This section answers four questions: how a device is "disabled" at all, why the
sweep keeps a list instead of re-querying the room later, why the restore is a
timer on the object rather than a scheduled callback, and who is allowed to flip
those tags.

### What does "disabled" actually mean to the engine?

Nothing. The engine has no concept of electronics, so "disabled" is a
convention two tags carry between the charge and the gadgets. A device wears
[`electronic`](../reference/softcode.md#fn-has_tag) to say it can be knocked
out, and the pulse hangs `disabled` on it to say it currently is. Every device
honors the flag in its own softcode, one guard clause per gadget that reads
`has_tag(me, 'disabled')` and decides between working and being dead glass. The
[security camera](054_security_camera.md)'s `powered` attribute is the same
contract expressed as an attribute rather than a tag. Tags win here because the
EMP has to *find* its victims, and `has_tag(o, 'electronic')` over the room's
[`contents`](../reference/softcode.md#fn-contents) is the query. A gadget that
skips the guard is simply not electronic in the way that matters: the sweep can
tag it, but nothing on it will listen.

### Why the sweep remembers its victims

The pulse collects every device it disables and stores their ids in a `hit`
list on the charge with [`set_attr`](../reference/softcode.md#fn-set_attr). The
restore then lifts exactly those flags. It does not re-scan the room for
"everything disabled here", because that would wrongly free a device some other
effect had shut down, and would miss a drone that was carried out during the
blackout. A recorded list of what you changed beats a fresh query whenever the
state can move between the two moments.

### Why the restore is `expire()`, not a scheduled callback

The [gas bomb](048_gas_bomb.md) laid out the rule: an in-memory timer dies with
a reboot, while [`expire`](../reference/softcode.md#fn-expire) writes an
`expires_at` timestamp onto the object that the world tick sweeps, so it
survives a restart. That difference is load-bearing here. A restore that a
reboot swallowed would leave every gadget in the room bricked forever. Instead
the spent charge carries the countdown itself: `expire(me, 30)` sets the
timestamp, and the charge's `ON_EXPIRE` hook runs the restore just before the
engine destroys the casing. The prop's death and the effect's end are one
event, and both hold across a restart.

### Who is allowed to flip the tags?

[`add_tag`](../reference/softcode.md#fn-add_tag) and
[`remove_tag`](../reference/softcode.md#fn-remove_tag) mutate, and mutation
needs **control** of the target, not merely being in the same room as it. This
EMP knocks out its owner's devices, and since one builder owns this whole lab,
the sweep lands. Against a stranger's gadget the tag write fails quietly. On a
live game the general-purpose weapon is an admin-owned charge, exactly like the
admin-owned gas bomb, while a player-owned EMP is a tool for sabotaging your own
tech, or tech whose owner delegated you control.

## Build it

Dig the lab and step inside. Each gadget's guard clause, added below, is where
`disabled` gets its meaning:

```text
@dig The Drone Lab = lab, out
lab
```

Make the first victim, a drone, and tag it `electronic` so the sweep can find
it:

```text
@create sweeper drone
drop sweeper drone
@tag sweeper drone = electronic
@desc sweeper drone = A knee-high maintenance drone, rotors idling. PING it for a status check.
```

The drone's `ping` verb is one conditional: it answers only while it is not
`disabled`, and reports dead otherwise. A single-statement guard stays on one
line:

```text
@set sweeper drone/cmd_ping = $ping drone: pemit(enactor, 'The drone chirps: ALL SYSTEMS NOMINAL.') if not has_tag(me, 'disabled') else pemit(enactor, 'The drone lies inert, rotors still.')
```

The second victim, a wall terminal, carries the same `electronic` tag and the
same shape of guard on its `login` verb:

```text
@create wall terminal
drop wall terminal
@tag wall terminal = electronic
@desc wall terminal = A recessed screen glowing standby-green. LOGIN to use it.
@set wall terminal/cmd_login = $login: pemit(enactor, 'ACCESS GRANTED. Directory listings scroll past.') if not has_tag(me, 'disabled') else pemit(enactor, 'The screen is dead glass.')
```

Now the charge. Its `arm emp` verb refuses to fire while you are holding it, so
you do not brick your own pockets, and otherwise hands off to the `pulse`
payload through [`eval_attr`](../reference/softcode.md#fn-eval_attr). That is a
single conditional, so it stays one line:

```text
@create EMP charge
@set EMP charge/cmd_arm = $arm emp: eval_attr(me, 'pulse') if loc(me) and has_tag(loc(me), 'room') else pemit(enactor, 'Not while you are holding it. Set it down first.')
```

The `pulse` payload does four things in order: sweep the room for live devices,
tag each one `disabled` and note its id, announce the blackout to the room with
[`remit`](../reference/softcode.md#fn-remit), and start the restore countdown on
the charge itself. It has a loop and several statements, so it is a `'''`
heredoc block:

```text
@set EMP charge/pulse = '''
hit = []
for o in contents(loc(me)):
    if has_tag(o, 'electronic') and not has_tag(o, 'disabled') and o is not me:
        add_tag(o, 'disabled')
        hit.append(o.id)  # record what THIS pulse dropped, so the restore lifts only these
set_attr(me, 'hit', hit)
remit(loc(me), 'A soundless white PULSE. Every status light in the room goes dark.')
expire(me, 30)
'''
```

The `on_expire` hook lifts the recorded flags and narrates the recovery, then
lets the engine reap the spent casing. It needs a guard: `ON_EXPIRE` fires on
every witness in the room, not only on the object whose timer elapsed, so
`if target is me:` keeps a second charge from running this charge's restore. See
[Guard on `target`](../reference/softcode.md#guard-on-target):

```text
@set EMP charge/on_expire = '''
if target is me:  # ON_EXPIRE fires on every witness in the room, so guard on the expiring object
    for i in V('hit') or []:
        remove_tag(get(f'#{i}'), 'disabled')
    remit(loc(me), 'One by one, status lights flicker back to life. The spent EMP casing crumbles to slag.')
'''
```

Set the charge down so it is ready to pick up and test:

```text
drop EMP charge
```

## Try it

Baseline first, then the pulse:

```text
ping drone     -> The drone chirps: ALL SYSTEMS NOMINAL.
login          -> ACCESS GRANTED. Directory listings scroll past.
arm emp        -> A soundless white PULSE. Every status light in the room goes dark.
ping drone     -> The drone lies inert, rotors still.
login          -> The screen is dead glass.
```

Thirty seconds of blackout, then the world tick reaps the casing:

```text
               -> One by one, status lights flicker back to life. The spent EMP casing crumbles to slag.
ping drone     -> The drone chirps: ALL SYSTEMS NOMINAL.
```

The charge is gone, because `ON_EXPIRE` ran the restore and then expiry
destroyed the prop. Try `arm emp` while carrying it and it refuses, since an EMP
in your backpack would disable your own gear too, a lesson better read than
lived.

## Going further

- **Hardened gear.** Skip targets tagged `shielded` in the sweep, and sell
  Faraday cases as wearables whose `grants_tags` confers it.
- **Drones that die louder.** Give the drone an `ON_TICK` patrol
  ([item 60](060_wandering_npc.md)) and have its tick guard on `disabled` too,
  so the EMP visibly stops a moving thing, not just a status line.
- **Area denial.** Sweep the whole zone instead: loop `zone_rooms(...)` and
  disable per room, but remember [`remit`](../reference/softcode.md#fn-remit)
  reaches one room, so use `act(..., targeting='zone')` (the
  [self-destruct sequence](056_self_destruct.md) does this) for the
  announcement.
- **Partial fry.** On restore, roll `rand(1, 6)` per victim and leave a 1
  permanently `disabled` until repaired with an Electronics check, which is
  counterplay for the *owner* of the gadgets, for a change.
```

