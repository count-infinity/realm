# 177. Jail system

> Checklist item 177 ([now]): *admin-owned world master, tag-gated exit lock, expire()/ON_EXPIRE auto-release, action log*

**What you'll build:** a `Warden` desk that jails a troublemaker with one
command, `jail <name> = <minutes>`, hauling them to a locked Holding Cell they
cannot walk out of and cutting them loose automatically when the sentence
lapses (or early, on `free <name>`), with every action written to a blotter.

**Concepts:** an [admin-owned world master](183_permission_tiers.md) acting on
players with owner authority, a tag-gated exit lock as the cell wall, a
self-expiring sentence timer ([`expire()`](../reference/softcode.md#fn-expire)
plus [`ON_EXPIRE`](../reference/softcode.md#lifecycle-hooks)) as the persistent
release clock, [`eval_attr()`](../reference/softcode.md#fn-eval_attr) as a
constructor helper, and a rolling action log.

## How it works

The `Warden` desk sits on the world zone as an admin-owned master, so its
scripts run with staff authority and may act on other players. The verb `jail
<name> = <minutes>` tags the target `jailed`, teleports them into a Holding
Cell whose only exit is locked against that tag, writes a blotter line, and
arms a one-shot timer that releases the prisoner when the sentence lapses.
`free <name>` runs the same release by hand and destroys the pending timer.
This section answers four questions: why the Warden may act on players at all,
what keeps a tagged prisoner in the cell, how release survives a reboot, and
how each timer reacts only to its own expiry.

### Why the Warden may act on other players

Jailing means tagging, teleporting, and later releasing *other players*, and
[`controls()`](../reference/softcode.md#fn-controls) only lets a script mutate
what its owner owns, or, for an ADMIN owner, everything. So the Warden is built
and owned by an admin: its scripts run with that owner's authority, which is
exactly what a moderation tool needs. This is the boundary the
[permission tour](183_permission_tiers.md) draws, where a builder-owned object
stays inside its own property and an admin-owned one is meant to reach past it.

### What keeps a prisoner in the cell

The Holding Cell's exit carries a `basic` lock,
`not caller.has_tag('jailed')`. `@lock` without a type sets the `basic` lock,
which is the one the engine evaluates for pick-up and traversal, so anyone
tagged `jailed` is refused by the movement gate itself, the same enforcement
the [locked chest](015_locked_chest.md) and every locked exit rely on. Staff,
as admins, bypass the lock and can come and go. Jail adds the tag with
[`add_tag`](../reference/softcode.md#fn-add_tag); release removes it with
[`remove_tag`](../reference/softcode.md#fn-remove_tag).

### How release survives a reboot

A [`wait()`](../reference/softcode.md#fn-wait) timer lives only in memory and
dies on restart, which would leave a rebooted server holding everyone forever.
[`expire()`](../reference/softcode.md#fn-expire) stamps a lifetime onto an
object that persists across ticks and reboots, which is the same durability the
[message in a bottle](083_message_in_bottle.md) relies on. Each jailing mints a
one-shot sentence timer in the cell with
[`create_obj`](../reference/softcode.md#fn-create_obj), stamped with the
prisoner's id and its own release script, and calls `expire()` on it. When the
world tick finds the timer past due it fires the timer's
[`ON_EXPIRE`](../reference/softcode.md#lifecycle-hooks) hook and then destroys
the object, because a hook that leaves `expires_at` in the past is reaped where
it sits. The release script removes the `jailed` tag and teleports the prisoner
home, so release *is* the timer dying. `free` performs the same release
directly and destroys the pending timer with
[`destroy_obj`](../reference/softcode.md#fn-destroy_obj) so it never fires a
second time.

### How the timer knows the expiry is its own

An [`ON_EXPIRE`](../reference/softcode.md#lifecycle-hooks) hook, like every
`ON_<EVENT>`, is heard by *every object in the room*, not only by the one that
expired. With two prisoners serving time, both timers sit in the cell, so when
the first timer reaps, the second timer hears the event too. Each timer's
release script therefore opens with `if target is me:`, the
[target guard](../reference/softcode.md#guard-on-target): a timer runs its
release only when it is itself the object that expired (an identity check with
`is`, not `==`). Without the guard, the first expiry would also free the second
prisoner early and leave a stale timer behind.

### Why the timer is built by a helper

Building and configuring the timer is several statements on one new object, so
the `jail` verb hands that work to a subroutine with
[`eval_attr(me, 'arm', p.id, mins)`](../reference/softcode.md#fn-eval_attr). The
`arm` routine creates the timer, stamps the prisoner and warden ids onto it,
copies the Warden's stored `release` script onto the timer as its `on_expire`
hook, and sets the countdown. One detail matters: `eval_attr` delivers its
extra arguments as *strings*, so `arm` reads the minutes back with `int()`
before multiplying to seconds.

## Build it

The whole build runs from a staff prompt, since only an admin owner can raise a
world master and act on players.

First dig a precinct and a cell on the world zone, and lock the cell's exit
against the jailed:

```text
@dig The Precinct = precinct, out
precinct
@zone here = world
@dig The Holding Cell = cell, back
cell
@zone here = world
@lock back = not caller.has_tag('jailed')
precinct
```

Then create the Warden, drop it in the precinct, and crown it a world master so
its `$` verbs answer from anywhere on the world zone:

```text
@create Warden
drop Warden
@desc Warden = A duty desk with a wall of cell keys. JAIL <name> = <minutes>, FREE <name>, JAIL LOG.
@zone/master Warden = world
```

The `release` script is the code each timer runs when its sentence lapses. It
is stored on the Warden and copied onto every timer, so it is written once as
real control flow. It resolves the prisoner and the warden from the ids stamped
on the timer, removes the tag, teleports the prisoner home, and appends a line
to the blotter:

```text
@set Warden/release = '''
# every object in the cell witnesses an expiry, so react only to our own timer
if target is me:
    p = get('#' + str(V('prisoner')))
    w = get('#' + str(V('warden')))
    if p and w:
        remove_tag(p, 'jailed')
        teleport_obj(p, 'The Precinct')
        pemit(p, 'The cell door clicks open. Time served.')
        set_attr(w, 'log', ((get_attr(w, 'log') or []) + ['auto-released ' + name(p)])[-50:])
'''
```

The `arm` subroutine constructs one sentence timer, stamps it with the prisoner
and warden ids, gives it the `release` script as its `on_expire` hook, and
starts the countdown:

```text
@set Warden/arm = '''
t = create_obj('a sentence timer', ['thing', 'jail_timer'], 'The Holding Cell')
set_attr(t, 'prisoner', arg0)
set_attr(t, 'warden', me.id)
set_attr(t, 'on_expire', V('release'))
# eval_attr delivers extra args as strings, so read the minutes back with int()
expire(t, int(arg1) * 60)
'''
```

The `jail` verb is the staff entry point. It refuses a non-admin, resolves the
target, tags and teleports them, records the blotter line, and arms the timer:

```text
@set Warden/cmd_jail = '''
$jail * = *:
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff may work the Warden.')
else:
    p = get(trim(arg0))
    mins = int(trim(arg1)) if trim(arg1).isdigit() else 5
    if not (p and has_tag(p, 'player')):
        pemit(enactor, f'No one named {trim(arg0)} to jail.')
    else:
        add_tag(p, 'jailed')
        teleport_obj(p, 'The Holding Cell')
        pemit(p, f'You are hauled off to the Holding Cell. Sentence: {mins} minute(s).')
        set_attr(me, 'log', ((V('log') or []) + [f'{name(enactor)} jailed {name(p)} ({mins}m)'])[-50:])
        eval_attr(me, 'arm', p.id, mins)
        pemit(enactor, f'Jailed {name(p)} for {mins} minute(s).')
'''
```

The `free` verb releases early. It runs the same tag-and-teleport, then finds
the prisoner's pending timer by tag and destroys it so it cannot fire later:

```text
@set Warden/cmd_free = '''
$free *:
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff may work the Warden.')
else:
    p = get(trim(arg0))
    if not (p and has_tag(p, 'jailed')):
        pemit(enactor, f'{trim(arg0)} is not currently jailed.')
    else:
        remove_tag(p, 'jailed')
        teleport_obj(p, 'The Precinct')
        pemit(p, 'You are released early. Stay out of trouble.')
        for t in contents(get('The Holding Cell')):
            if has_tag(t, 'jail_timer') and get_attr(t, 'prisoner') == p.id:
                destroy_obj(t)
        set_attr(me, 'log', ((V('log') or []) + [f'{name(enactor)} freed {name(p)}'])[-50:])
        pemit(enactor, f'Freed {name(p)}.')
'''
```

The `jail log` verb prints the recent blotter to staff:

```text
@set Warden/cmd_jaillog = '''
$jail log:
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff may work the Warden.')
elif not V('log'):
    pemit(enactor, 'The blotter is empty.')
else:
    for ln in V('log')[-10:]:
        pemit(enactor, ln)
'''
```

## Try it

Jail Vandal for a minute. He is hauled off, and the cell's locked exit refuses
him:

```text
jail Vandal = 1
   -> Jailed Vandal for 1 minute(s).
   (Vandal) You are hauled off to the Holding Cell. Sentence: 1 minute(s).

(Vandal) back
   -> You can't go back — it's locked.
```

A minute later, on the world tick, the sentence timer reaps itself, and Vandal
lands back at the Precinct un-jailed with the timer gone:

```text
(Vandal) The cell door clicks open. Time served.
```

`free <name>` does the same release early and cancels the pending timer. Jailing
for five minutes, freeing at once, then reading the blotter shows both actions:

```text
jail Vandal = 5
   -> Jailed Vandal for 5 minute(s).

free Vandal
   -> Freed Vandal.

jail log
   -> Bob jailed Vandal (5m)
   -> Bob freed Vandal
```

A non-staff prisoner who tries `jail Vandal = 99` is turned away with `Only
staff may work the Warden.`, because the desk answers only to admins.

## Going further

- **A visible sentence** stamps the remaining seconds from `expires_at` into
  the cell's `[[...]]` description so prisoners can read the clock on the wall.
  Keep it a single shallow [`get_attr`](../reference/softcode.md#fn-get_attr) per
  the [weather system](036_weather_system.md) push-on-change rule.
- **Escalating sentences** key a `priors_<id>` counter on the Warden so repeat
  offenders draw longer stints.
- **Bail** adds a `$bail` verb on the cell that runs
  [`transfer_credits`](../reference/softcode.md#fn-transfer_credits) to the
  Precinct and then takes the same release path early.
- **Cellblock work** hands the cell a `zone_reset`-style tidy or a ticker that
  emotes the drip of a leaky pipe, since a jail is a room like any other.
- **The proper ban** is a different tool: jail confines in-world, while
  account and IP bans with expiry live in the ban registry (audit gap **G12**,
  item 178).
```
