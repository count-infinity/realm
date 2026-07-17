# 177. Jail system

> Checklist item 177 — [now] — *admin-owned master authority, tag-gated exit lock, expire()/ON_EXPIRE auto-release, action logging*

**What you'll build:** a `Warden` desk that jails a troublemaker with one
command — `jail <name> = <minutes>` — hauling them to a locked Holding
Cell they cannot walk out of, and cutting them loose automatically when
the sentence lapses (or early, on `free <name>`), with every action
written to a blotter.

**Concepts:** an **admin-owned world master** acting on players with
owner authority, a **tag-gated exit lock** (native lock enforcement) as
the cell wall, a self-expiring **sentence timer** (`expire()` +
`ON_EXPIRE`) as the persistent, reboot-proof release clock, `eval_attr()`
as a constructor helper, and a rolling action log.

## How it works

**The Warden acts with staff authority — legitimately.** Jailing means
tagging, teleporting, and later releasing *other players*, and
`controls()` only lets you mutate what you own or (as ADMIN) everything.
So the Warden is built and owned by an admin: its scripts run with its
owner's authority, which is exactly what a moderation tool needs. This is
the honest boundary the [permission tour](183_permission_tiers.md)
draws — a builder-owned object could never do this; an admin-owned one
is *meant* to.

**The cell wall is a lock, not magic.** The Holding Cell's exit carries a
`basic` lock, `not caller.has_tag('jailed')`. Anyone tagged `jailed` is
refused by the engine's own movement gate (the same enforcement the
[locked chest](015_locked_chest.md) and every locked exit use); staff, as
admins, bypass it. Jail adds the tag, release removes it.

**Auto-release is a self-expiring timer, so it survives a reboot.** A
`wait()` would evaporate on restart and free everyone mid-sentence; a
persistent `expires_at` does not (this is the
[message-in-a-bottle](083_message_in_bottle.md) lesson). Each jailing
mints a one-shot **sentence timer** object in the cell, stamped with the
prisoner's id and an `on_expire` script of its own. When the world tick
reaps it, that script removes the `jailed` tag, teleports the prisoner to
the Precinct, and lets the timer be destroyed (the default `ON_EXPIRE`
fate) — release *is* the timer dying. `free` does the same by hand and
destroys the pending timer so it can't fire twice.

**Why a helper for the timer.** Building-and-configuring the timer is
three statements on one new object — awkward inside the conditional
expression the verb is. So the verb calls `eval_attr(me, 'arm', p.id,
mins)`; the `arm` subroutine does the construction. (One wrinkle worth
knowing: `eval_attr` passes its extra args as *strings*, so `arm` coerces
the minutes with `int()`.)

## Build it

A precinct and a cell on the world zone; the cell's exit locked against
the jailed:

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

The Warden, admin-owned and crowned world master:

```text
@create Warden
drop Warden
@desc Warden = A duty desk with a wall of cell keys. JAIL <name> = <minutes>, FREE <name>, JAIL LOG.
@zone/master Warden = world
```

The timer constructor — note the prisoner's own `on_expire` is written
onto the timer as data, to run later with the timer's (admin) authority:

```text
@set Warden/arm = t = create_obj('a sentence timer', ['thing','jail_timer'], 'The Holding Cell'); set_attr(t, 'prisoner', arg0); set_attr(t, 'warden', me.id); set_attr(t, 'on_expire', "p = get('#'+str(get_attr(me,'prisoner'))); w = get('#'+str(get_attr(me,'warden'))); (remove_tag(p,'jailed'), teleport_obj(p,'The Precinct'), pemit(p,'The cell door clicks open. Time served.'), set_attr(w,'log', ((get_attr(w,'log') or []) + ['auto-released ' + name(p)])[-50:])) if p and w else None"); expire(t, int(arg1) * 60)
```

Jail, free, and the blotter — each gated to staff:

```text
@set Warden/cmd_jail = $jail * = *: p = get(trim(arg0)); mins = int(trim(arg1)) if trim(arg1).isdigit() else 5; (pemit(enactor,'Only staff may work the Warden.') if not has_tag(enactor,'admin') else (pemit(enactor,'No one named ' + trim(arg0) + ' to jail.') if not (p and has_tag(p,'player')) else (add_tag(p,'jailed'), teleport_obj(p,'The Holding Cell'), pemit(p,'You are hauled off to the Holding Cell. Sentence: ' + str(mins) + ' minute(s).'), set_attr(me,'log', ((get_attr(me,'log') or []) + [name(enactor) + ' jailed ' + name(p) + ' (' + str(mins) + 'm)'])[-50:]), eval_attr(me,'arm', p.id, mins), pemit(enactor,'Jailed ' + name(p) + ' for ' + str(mins) + ' minute(s).'))))
@set Warden/cmd_free = $free *: p = get(trim(arg0)); (pemit(enactor,'Only staff may work the Warden.') if not has_tag(enactor,'admin') else (pemit(enactor, trim(arg0) + ' is not currently jailed.') if not (p and has_tag(p,'jailed')) else (remove_tag(p,'jailed'), teleport_obj(p,'The Precinct'), pemit(p,'You are released early. Stay out of trouble.'), [destroy_obj(t) for t in contents(get('The Holding Cell')) if has_tag(t,'jail_timer') and get_attr(t,'prisoner') == p.id], set_attr(me,'log', ((get_attr(me,'log') or []) + [name(enactor) + ' freed ' + name(p)])[-50:]), pemit(enactor,'Freed ' + name(p) + '.'))))
@set Warden/cmd_jaillog = $jail log: (pemit(enactor,'Only staff may work the Warden.') if not has_tag(enactor,'admin') else (pemit(enactor,'The blotter is empty.') if not get_attr(me,'log') else [pemit(enactor, ln) for ln in get_attr(me,'log')[-10:]]))
```

## Try it

Jail Vandal for a minute; he can't leave, and the tide of time frees him:

```text
jail Vandal = 1
   -> Jailed Vandal for 1 minute(s).
   (Vandal) You are hauled off to the Holding Cell. Sentence: 1 minute(s).

(Vandal) back
   -> You can't go back — it's locked.
```

A minute later, on the world tick, the sentence timer reaps itself:

```text
(Vandal) The cell door clicks open. Time served.
```

...and Vandal is back at the Precinct, un-jailed, the timer gone. `free
Vandal` does it early and cancels the timer. `jail log` prints the
blotter:

```text
jail log
   -> Bob jailed Vandal (5m)
   -> Bob freed Vandal
```

A non-staff prisoner who tries `jail Vandal = 99` gets `Only staff may
work the Warden.` — the desk answers only to admins.

## Going further

- **A visible sentence** — stamp `expires_at`'s remaining seconds into the
  cell's `[[...]]` desc so prisoners can read the clock on the wall (keep
  it a single shallow `get_attr` per the
  [weather system](036_weather_system.md) push-on-change rule).
- **Escalating sentences** — key a `priors_<id>` counter on the Warden;
  repeat offenders draw longer stints.
- **Bail** — a `$bail` verb on the cell: `transfer_credits` to the
  Precinct, then run the same release path early.
- **Cellblock work** — hand the cell a `zone_reset`-style tidy or a
  `script_ticker` that emotes the drip of a leaky pipe; a jail is a room
  like any other.
- **The proper ban** — jail confines in-world; account/IP **bans** with
  expiry are a different tool (audit gap **G12**, item 178).
