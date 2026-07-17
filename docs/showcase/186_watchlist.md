# 186. Watchlist & alerts

> Checklist item 186 — [now] — *watched tag, world-master ON_CONNECT/ON_ATTACK witness, staff pemit fan-out, notes*

**What you'll build:** a `Watch Office` that flags a character —
`watch <name> = <note>` — and pings every staffer the moment that
character connects *or* throws a punch, with `watchlist` to review who's
flagged and `unwatch` to clear them.

**Concepts:** a **`watched` tag** as the flag, a **world-master witnessing
`ON_CONNECT` and `ON_ATTACK`** across the whole zone (the
[roster idiom from 083](083_message_in_bottle.md)), a **staff fan-out**
via `search_world(tag='admin')` + `pemit()`, per-flag notes, and an
`eval_attr()` alert helper shared by both witnesses.

## How it works

**Flagging is a tag; the alert is a witness.** `watch` tags the target
`watched` and stores a `note_<id>`. The Watch Office, as master of the
`zone:world`, hears every `event:connect` and `event:attack` on the grid;
when the actor is `watched`, it fires an alert. Two hooks, one flag —
connect tells you they've arrived, attack tells you they're in trouble.
Point more `ON_*` hooks (death, payment, arrival) at the same `alert`
helper and the coverage widens without new plumbing.

**Alerts fan out to staff.** The `alert` subroutine loops
`search_world(tag='admin')` and `pemit`s each — so every on-duty admin
sees it, wherever they are, delivered by id. Both witnesses call it
through `eval_attr(me, 'alert', <line>)`, the shared-helper idiom the
[custom channel](074_custom_channel.md) uses. (Widen the fan-out to
`builder`/`staff` if your moderators aren't all admins.)

**Setting watches needs admin authority; reading is gated too.** `watch`
and `unwatch` tag *another player*, so the office is admin-owned and every
verb checks `has_tag(enactor, 'admin')` first — the staff-tool boundary
from the [permission tour](183_permission_tiers.md). `watchlist` renders
the flagged set (`search_world(tag='watched')`) with each stored note.

**Presence, honestly.** Like the [dashboard](176_staff_dashboard.md) and
the message-in-a-bottle roster, this leans on connect events because
softcode has no "who's online" query (audit gap **G4**). The alert fires
*on* the connect event rather than polling a session list — which is
exactly what you want anyway: notification at the moment of arrival.

## Build it

A security hub on the world zone and the office as its master:

```text
@dig The Security Hub = hub, out
hub
@zone here = world
@create Watch Office
drop Watch Office
@desc Watch Office = Banks of monitors. WATCH <name> = <note>, UNWATCH <name>, WATCHLIST.
@zone/master Watch Office = world
```

The shared alert helper, the staff verbs, and the two witnesses:

```text
@set Watch Office/alert = [pemit(s, ansi('rh','[WATCH] ') + str(arg0)) for s in search_world(tag='admin')]
@set Watch Office/cmd_watch = $watch * = *: p = get(trim(arg0)); (pemit(enactor,'Only staff may set watches.') if not has_tag(enactor,'admin') else (pemit(enactor,f'No one named {trim(arg0)}.') if not (p and has_tag(p,'player')) else (add_tag(p,'watched'), set_attr(me,'note_'+p.id, escape(trim(arg1))), pemit(enactor,'Now watching ' + name(p) + '.'))))
@set Watch Office/cmd_unwatch = $unwatch *: p = get(trim(arg0)); (pemit(enactor,'Only staff may clear watches.') if not has_tag(enactor,'admin') else (pemit(enactor, f'{trim(arg0)} is not being watched.') if not (p and has_tag(p,'watched')) else (remove_tag(p,'watched'), pemit(enactor,f'Stopped watching {name(p)}.'))))
@set Watch Office/cmd_watchlist = $watchlist: w = search_world(tag='watched'); (pemit(enactor,'Only staff.') if not has_tag(enactor,'admin') else (pemit(enactor,'No one is being watched.') if not w else [pemit(enactor,f'- {name(p)} :: {V("note_"+p.id,"")}') for p in w]))
@set Watch Office/on_connect = eval_attr(me,'alert', f'{name(enactor)} (watched) just connected.') if has_tag(enactor,'watched') else None
@set Watch Office/on_attack = eval_attr(me,'alert', f'{name(enactor)} (watched) is throwing punches.') if has_tag(enactor,'watched') else None
```

## Try it

Flag a suspect; from then on their arrivals and attacks page every
staffer:

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

An un-flagged character's connect raises nothing, and a non-staff
character who tries `watch Kess = x` is refused: `Only staff may set
watches.`

## Going further

- **Wider coverage** — add `on_death`, `on_payment`, or an `on_arrive`
  witness routed through the same `alert`; a watchlist is only as useful
  as the events it watches. `on_death` is a particularly good catch: the
  engine announces it from its one death path, so it fires for a poison
  tick or a trap as readily as for a swing, and for a watched *player*
  going down as well as one doing the killing. Read the action to tell
  those apart — `target` is who fell, `adata('killer')` names who did it,
  `adata('fatal')` separates a corpse from a KO (the
  [dashboard](176_staff_dashboard.md) feed does exactly this).
- **Severity** — store a level with the note and colour the alert red vs.
  amber; a `[[...]]` in the office desc can show the live count.
- **Auto-watch** — have the [approval desk](179_approval_queue.md) tag
  fresh-off-probation characters `watched` for their first week, then
  `expire()` the flag.
- **Audit trail** — append every alert to a `log` (as the
  [jail](177_jail_system.md) blotter does) so staff can review history,
  not just live pings.
- **Off-grid gaps** — the witness only hears world-zone rooms; a genuine
  presence primitive (gap **G4**) would let you watch logins anywhere.
