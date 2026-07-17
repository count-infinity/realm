# 083. Message in a bottle

> Checklist item 83 — [now] — *expire() drift, ON_EXPIRE self-rescue, presence roster workaround, random delivery*

**What you'll build:** A corked bottle: `pen <text>` seals a note in
it, `toss bottle` gives it to the tide — and a long, random while
later it washes up at the feet of a random player somewhere in the
world, who can `uncork bottle` and read you.

**Concepts:** `expire()` as a **persistent random-delay timer**,
`ON_EXPIRE` as a delivery event the object survives by clearing its
own `expires_at`, an **ON_CONNECT/ON_DISCONNECT presence roster** on
a world-zone master (the honest workaround for softcode's missing
presence query), `rand()` selection, and an object that relocates
*itself*.

## How it works

**The drift must survive a reboot, so it's `expire()`.** A `wait()`
dies with the server; a bottle at sea for hours cannot. `expire(me,
rand(60, 300))` stamps a persistent `expires_at` on the bottle — the
engine's world tick fires `ON_EXPIRE` when it lapses, *then destroys
the object* unless the hook clears or extends the timestamp. That
destroy-by-default is the hook's contract, and the bottle exploits
it: **delivery is a rescue.** The `ON_EXPIRE` script picks a
recipient, `del_attr(me, 'expires_at')` (the survival move),
teleports itself to the recipient's room, and announces the surf. If
it finds no one, it re-arms — `expire(me, 60)` — and drifts on.
Either way the bottle never dies; it just keeps missing landfall.

**"A random *online* player" is the honest problem.** Softcode has
no presence primitive: no function lists connected players, no attr
marks them (`who` is builtin-only; sessions are invisible to
scripts). The workaround is a roster the world maintains for itself:
a **world-zone master** — the Harbormaster — hears `event:connect` /
`event:disconnect` from every room tagged `zone:world` and keeps an
`ashore` list of ids. Two boundaries, stated plainly: logins in rooms
*outside* the zone are missed, and a hard crash can strand stale ids
(the script re-verifies each id resolves before trusting it; a
belt-and-braces variant prunes on read). If the roster comes up
empty, the bottle falls back to *any* player object in the world —
they'll find it on the tide-line by their feet whenever they return,
since the bottle and its note are persistent objects either way.

**Why the bottle may move itself.** `teleport_obj` demands control
of the moved object; the bottle, running its own script with its
owner's authority, controls itself — and rooms accept arrivals unless
locked. Tossing is likewise self-relocation to the holding room
(`The Open Sea`, a room with no exits — the tide is not a place
players visit).

## Build it

A beach on the world zone, a cliff to prove range, and the sea:

```text
@dig The Shingle Beach = beach, out
beach
@zone here = world
@dig The Sea Cliff = cliff, beach
cliff
@zone here = world
beach
@dig The Open Sea
```

The Harbormaster keeps the roster (move-to-front on connect, drop on
disconnect):

```text
@create Harbormaster
drop Harbormaster
@desc Harbormaster = A weathered official who seems to know exactly who is ashore at any hour.
@zone/master Harbormaster = world
@set Harbormaster/on_connect = set_attr(me, 'ashore', [i for i in (V('ashore') or []) if i != enactor.id] + [enactor.id])
@set Harbormaster/on_disconnect = set_attr(me, 'ashore', [i for i in (V('ashore') or []) if i != enactor.id])
```

The bottle — pen, read, toss:

```text
@create green bottle
@desc green bottle = Sea-scoured glass, stoppered with a cork. PEN <text> writes a note; TOSS BOTTLE gives it to the tide; UNCORK BOTTLE reads what is inside.
@set green bottle/cmd_pen = $pen *: (pemit(enactor, 'Hold the bottle to write.') if loc(me) != enactor else (set_attr(me, 'note', f'{escape(arg0)} --{name(enactor)}'), pemit(enactor, 'You roll the note tight and work it down the neck.')))
@set green bottle/cmd_uncork = $uncork bottle: pemit(enactor, 'The bottle is empty.') if not V('note') else pemit(enactor, f"The note reads: {V('note')}")
@set green bottle/cmd_toss = $toss bottle: (pemit(enactor, 'Hold the bottle to throw it.') if loc(me) != enactor else (pemit(enactor, 'It needs a note first. PEN <text>.') if not V('note') else (remit(loc(enactor), f'{name(enactor)} hurls the green bottle out past the breakers.'), teleport_obj(me, 'The Open Sea'), expire(me, rand(60, 300)))))
```

And landfall — the rescue-and-deliver hook:

```text
@set green bottle/on_expire = hm = get('Harbormaster'); ids = [i for i in (get_attr(hm, 'ashore') or []) if get('#' + str(i))]; pool = ids or [p.id for p in search_world(tag='player')]; w = get('#' + str(pool[rand(0, len(pool) - 1)])) if pool else None; (del_attr(me, 'expires_at'), teleport_obj(me, loc(w)), pemit(w, 'A green glass bottle washes up at your feet.'), oemit(w, 'Something glints at the tide-line.')) if w and loc(w) else expire(me, 60)
```

## Try it

```text
get green bottle
pen The lighthouse ledger is a fake. Check the cellar. Tell no one.
   -> You roll the note tight and work it down the neck.
toss bottle
   -> Bilda hurls the green bottle out past the breakers.
```

The bottle now sits in The Open Sea with a one-to-five-minute fuse.
When it lapses, someone — whoever the tide favors among players the
Harbormaster knows are ashore — gets:

```text
A green glass bottle washes up at your feet.
```

...and the bottle is really there, in their room:

```text
get green bottle
uncork bottle
   -> The note reads: The lighthouse ledger is a fake. Check the cellar. Tell no one. --Bilda
```

Toss it again and it drifts to someone else. A server reboot
mid-drift changes nothing: `expires_at` is an attribute, and the
world tick picks the countdown back up. Try `pen` or `toss` with the
bottle on the ground — the tide demands you hold it.

## Going further

- **Slower oceans** — `rand(3600, 86400)` makes landfall a
  once-a-day surprise; the mechanism doesn't care, which is the
  point of `expire()`.
- **Never the sender** — filter `pool` by
  `i != V('sender')` (stamp the sender's id at toss) so
  the sea never hands your secret straight back.
- **A bottle economy** — the [newspaper](082_newspaper.md) kiosk
  pattern sells empty bottles; castaways as content, five credits a
  throw.
- **File the gap** — if your game leans on presence, the real fix is
  an engine primitive (`connected()` or an engine-maintained tag);
  the roster is a workaround and should retire the day the engine
  learns to answer "who is online" in softcode.
