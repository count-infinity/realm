# 186. Watchlist & alerts

> Checklist item 186 ([now]): *watched tag, world-master ON_CONNECT/ON_ATTACK witness, staff pemit fan-out, notes*

**What you'll build:** a `Watch Office` that flags a character with
`watch <name> = <note>` and pings every staffer the moment that character
connects or throws a punch, with `watchlist` to review who is flagged and
`unwatch` to clear them.

**Concepts:** a **`watched` tag** as the flag, a **world-master witnessing
`ON_CONNECT` and `ON_ATTACK`** across the whole zone (the roster idiom from
the [message in a bottle](083_message_in_bottle.md)), a **staff fan-out** via
[`search_world`](../reference/softcode.md#fn-search_world)`(tag='admin')` and
[`pemit`](../reference/softcode.md#fn-pemit)`()`, per-flag notes, and an
[`eval_attr`](../reference/softcode.md#fn-eval_attr)`()` alert helper shared by
both witnesses.

## How it works

The finished office is one admin-owned object that carries three staff verbs,
two event witnesses, and a shared alert routine. This section answers where the
flag lives, how an alert reaches every staffer, why the verbs need admin
authority, and why the office listens for connects rather than polling.

**Flagging is a tag; the alert is a witness.** `watch` tags the target
`watched` and stores a `note_<id>` for it. The Watch Office is the master of the
`world` zone, so it hears every `event:connect` and every `combat:on_attack`
action across the grid; when the acting character carries the `watched` tag, it
fires an alert. (For how an action reaches these witnesses, see the
[event model](../architecture/events.md) and the guided
[event bus tour](245_event_bus_tour.md).) Two hooks share one flag, so a connect
tells you the character has arrived and an attack tells you the character is
swinging at someone. Point more [`ON_*` hooks](../reference/softcode.md#lifecycle-hooks)
(death, payment, arrival) at the same `alert` helper and the coverage widens
without new plumbing.

**Alerts fan out to staff.** The `alert` subroutine loops over
`search_world(tag='admin')` and `pemit`s each one, so every on-duty admin sees
the line wherever they are, delivered by id. Both witnesses reach it through
`eval_attr(me, 'alert', <line>)`, the shared-helper idiom the
[custom channel](074_custom_channel.md) uses, which runs the routine with the
office's own authority. (Widen the fan-out to `builder` or `staff` if your
moderators are not all admins.)

**Setting watches needs admin authority, and reading is gated too.** `watch`
and `unwatch` tag *another player*, so the office is admin-owned and every verb
checks [`has_tag`](../reference/softcode.md#fn-has_tag)`(enactor, 'admin')`
first, the staff-tool boundary from the
[permission tour](183_permission_tiers.md). `watchlist` renders the flagged set
from `search_world(tag='watched')` with each stored note.

**Presence, honestly.** Like the [dashboard](176_staff_dashboard.md) and the
message-in-a-bottle roster, this leans on connect events because softcode has no
"who's online" query (audit gap **G4**). The alert fires *on* the connect event
rather than polling a session list, which is exactly what you want anyway, since
it means notification at the moment of arrival.

## Build it

First dig a security hub on the world zone, then create the office and make it
the zone's master so that it witnesses events grid-wide:

```text
@dig The Security Hub = hub, out
hub
@zone here = world
@create Watch Office
drop Watch Office
@desc Watch Office = Banks of monitors. WATCH <name> = <note>, UNWATCH <name>, WATCHLIST.
@zone/master Watch Office = world
```

The shared alert helper loops over every admin and
[`pemit`](../reference/softcode.md#fn-pemit)s them the line, brightened red with
[`ansi`](../reference/softcode.md#fn-ansi). The message arrives as `arg0`, since
both witnesses pass it in through `eval_attr`:

```text
@set Watch Office/alert = '''
for s in search_world(tag='admin'):
    pemit(s, ansi('rh','[WATCH] ') + str(arg0))
'''
```

The `watch` verb is a chain of guards: only an admin may set a watch, the name
must resolve to a real player, and only then does it tag the target, store the
note keyed by the target's id, and confirm. It reads the
target with [`get`](../reference/softcode.md#fn-get) after
[`trim`](../reference/softcode.md#fn-trim)ming the wildcard capture, tags with
[`add_tag`](../reference/softcode.md#fn-add_tag), and stores the note with
[`set_attr`](../reference/softcode.md#fn-set_attr) after
[`escape`](../reference/softcode.md#fn-escape)ing any color markup a staffer
typed into it:

```text
@set Watch Office/cmd_watch = '''
$watch * = *:
p = get(trim(arg0))
if not has_tag(enactor,'admin'):
    pemit(enactor,'Only staff may set watches.')
elif not (p and has_tag(p,'player')):
    pemit(enactor,f'No one named {trim(arg0)}.')
else:
    add_tag(p,'watched')
    set_attr(me,'note_'+p.id, escape(trim(arg1)))  # escape() neutralizes color markup in the staff-typed note
    pemit(enactor,'Now watching ' + name(p) + '.')
'''
```

The `unwatch` verb clears the flag with
[`remove_tag`](../reference/softcode.md#fn-remove_tag), and `watchlist` prints
each flagged player with its stored note, read back off the office with
[`V`](../reference/softcode.md#fn-v). Both refuse a non-admin first:

```text
@set Watch Office/cmd_unwatch = '''
$unwatch *:
p = get(trim(arg0))
if not has_tag(enactor,'admin'):
    pemit(enactor,'Only staff may clear watches.')
elif not (p and has_tag(p,'watched')):
    pemit(enactor,f'{trim(arg0)} is not being watched.')
else:
    remove_tag(p,'watched')
    pemit(enactor,f'Stopped watching {name(p)}.')
'''
@set Watch Office/cmd_watchlist = '''
$watchlist:
w = search_world(tag='watched')
if not has_tag(enactor,'admin'):
    pemit(enactor,'Only staff.')
elif not w:
    pemit(enactor,'No one is being watched.')
else:
    for p in w:
        pemit(enactor,f'- {name(p)} :: {V("note_"+p.id,"")}')
'''
```

Finally the two witnesses. As the world-zone master, the office hears every
connect and attack in the zone, so each hook filters by the `watched` tag rather
than a `target` guard: a zone master is a deliberate global witness watching
everyone, so it takes no target guard. Both route through the same `alert`
helper with [`eval_attr`](../reference/softcode.md#fn-eval_attr):

```text
@set Watch Office/on_connect = '''
# the zone master hears every connect in its zone; filter by the watched tag
if has_tag(enactor,'watched'):
    eval_attr(me,'alert', f'{name(enactor)} (watched) just connected.')
'''
@set Watch Office/on_attack = '''
if has_tag(enactor,'watched'):
    eval_attr(me,'alert', f'{name(enactor)} (watched) is throwing punches.')
'''
```

## Try it

Flag a suspect; from then on their arrivals and attacks page every staffer:

```text
watch Vandal = suspected smurf
   -> Now watching Vandal.

(Vandal connects)
   (staff) |Rh[WATCH]|n Vandal (watched) just connected.
(Vandal starts a fight)
   (staff) |Rh[WATCH]|n Vandal (watched) is throwing punches.
```

Review and clear:

```text
watchlist
   -> - Vandal :: suspected smurf
unwatch Vandal
   -> Stopped watching Vandal.
```

An un-flagged character's connect raises nothing, and a non-staff character who
tries `watch Kess = x` is refused: `Only staff may set watches.`

## Going further

- **Wider coverage** add `on_death`, `on_payment`, or an `on_arrive` witness
  routed through the same `alert`; a watchlist is only as useful as the events
  it watches. `on_death` is a particularly good catch: the engine announces it
  from its one death path, so it fires for a poison tick or a trap as readily as
  for a swing, and for a watched *player* going down as well as one doing the
  killing. Read the action to tell those apart, since `target` is who fell,
  [`adata`](../reference/softcode.md#event-data-namespace)`('killer')` names who
  did it, and `adata('fatal')` separates a corpse from a knockout (the
  [dashboard](176_staff_dashboard.md) feed does exactly this).
- **Severity** store a level with the note and colour the alert red versus
  amber; a `[[...]]` block in the office description can show the live count.
- **Auto-watch** have the [approval desk](179_approval_queue.md) tag
  fresh-off-probation characters `watched` for their first week, then `expire()`
  the flag.
- **Audit trail** append every alert to a `log` (as the
  [jail](177_jail_system.md) blotter does) so staff can review history, not just
  live pings.
- **Off-grid gaps** the witness only hears world-zone rooms; a genuine presence
  primitive (gap **G4**) would let you watch logins anywhere.
