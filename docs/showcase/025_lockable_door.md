# 025. Lockable Door

> Checklist item 25 — [now] — *paired exits, shared door-state attrs, traverse locks*

**What you'll build:** A vault door between two rooms that behaves like
one *physical* door: close it, lock it with a brass key, open it from
either side — and both sides always agree.

**Concepts:** `@dig` paired exits, the door state convention (`closed`
tag + `locked`/`key_id` attributes), key items (`unlocks`), the
built-in `open`/`close`/`lock`/`unlock` commands, and the **mirror
pattern** — `ON_OPEN`/`ON_CLOSE`/`ON_LOCK`/`ON_UNLOCK` hooks that copy
every state change onto a partner object. The mirror pattern reuses
anywhere two objects must share state.

## How it works

**Door state is convention, all engine-enforced.** An exit with the
`closed` tag refuses traversal (`The vault door is closed.`). A
`locked` attribute refuses `open` (with your `locked_msg`). `key_id`
names the lock, and any carried item whose `unlocks` matches it powers
the stock `lock`/`unlock` commands. None of this needs scripting — one
side of a door is a solved problem.

**The two-sided problem.** `@dig The Vault = vault door, vault door`
gives you what every MU* gives you: *two independent exit objects*
wearing the same name — A→B in this room, B→A in the new one. Tag one
side `closed` and the other side still stands open; unlock the north
face and walk through, and the south face still claims to be locked.
Nothing links them. Every multi-room build hits this eventually.

**The fix: mirror on events.** Whenever a door changes state, the
engine propagates an action (`item:on_open`, `item:on_close`,
`item:on_lock`, `item:on_unlock`) with the exit as target — so the exit
can carry four tiny `ON_<EVENT>` scripts that copy the new state onto
its partner:

- the hooks fire on the *commands* (`open`/`close`/`lock`/`unlock`),
  and the script **writes raw state** (`add_tag`/`set_attr`) on the
  partner rather than "opening" it — direct writes don't propagate, so
  the mirror can't echo back and forth. Recursion-proof by
  construction.
- authority is your own: you dug both exits, so you own both, and a
  script runs with its object's owner's authority — each side may write
  its sibling. (Which side is authoritative? Neither: last write wins,
  and since every write mirrors immediately, they can never drift.)

Each side stores its partner's `#id` in a `partner` attribute; a
one-line `@eval` wires both directions by following `destination`
attributes — no copying ids by hand.

## Build it

Dig the vault with the same name on both faces, and cut the key
(`@create` leaves it in your hand — keep it there):

```text
@dig The Vault = vault door, vault door
@create brass key
@set brass key/unlocks = vault_brass
```

Wire the two sides to each other. Reading the `@eval`: `a` is this
room's `vault door`; `b` is the exit *in a's destination room* that
leads back here; then each remembers the other:

```text
@eval a = [o for o in contents(here) if has_tag(o, 'exit') and name(o) == 'vault door'][0]; b = [o for o in contents(get('#' + str(get_attr(a, 'destination')))) if has_tag(o, 'exit') and str(get_attr(o, 'destination')) == here.id][0]; set_attr(a, 'partner', '#' + b.id); set_attr(b, 'partner', '#' + a.id); result = 'both sides wired'
```

Now configure the near side — the lock identity, the refusal line, and
the four mirror hooks:

```text
@set vault door/key_id = vault_brass
@set vault door/locked_msg = The wheel spins uselessly. Locked tight.
@set vault door/on_open = remove_tag(V('partner'), 'closed')
@set vault door/on_close = add_tag(V('partner'), 'closed')
@set vault door/on_lock = set_attr(V('partner'), 'locked', True)
@set vault door/on_unlock = set_attr(V('partner'), 'locked', False)
```

Walk through the (still unlocked) doorway and give the far side the
identical six lines — `@set` resolves `vault door` locally, so the same
commands configure whichever side you're standing at:

```text
vault door
@set vault door/key_id = vault_brass
@set vault door/locked_msg = The wheel spins uselessly. Locked tight.
@set vault door/on_open = remove_tag(V('partner'), 'closed')
@set vault door/on_close = add_tag(V('partner'), 'closed')
@set vault door/on_lock = set_attr(V('partner'), 'locked', True)
@set vault door/on_unlock = set_attr(V('partner'), 'locked', False)
vault door
```

That last `vault door` walks you back to where you started. The door is
built.

## Try it

Shut and lock it, key in hand:

```text
close vault door
lock vault door
vault door
open vault door
unlock vault door
open vault door
vault door
```

Expected beats: `close` and `lock` succeed (`You lock vault door with
brass key.`) — and `@examine` the *far* side at any point to watch its
`closed` tag and `locked` attribute change in lockstep. Walking into
the closed door refuses with `The vault door is closed.`; `open`
refuses with your `locked_msg`; the key unlocks, the door opens, and
you're in the vault. Now prove the point of the whole build — lock
yourself in, and have a keyless friend try the *other* side:

```text
close vault door
lock vault door
```

Your friend in the workshop gets `The vault door is closed.` walking
in, `The wheel spins uselessly. Locked tight.` on `open`, and `You
don't have the key.` on `unlock`. One door, two faces, one truth.

## Engine gaps

- The `use <key> on <door>` keycard fast-path toggles `locked`
  directly without propagating a lock/unlock event, so `ON_LOCK`/
  `ON_UNLOCK` mirrors never hear it; `pick` likewise unlocks with a
  direct write. On a mirrored door, stick to `lock`/`unlock` (which do
  propagate) — or accept a one-sided picked door as a feature (you
  crawled in through *this* face).

## Going further

- **Pickable:** `@set vault door/lock_skill = lockpicking` and
  `@set vault door/lock_difficulty = 2` let `pick vault door` roll
  against the lock (carry lockpicks or take -5) — see the engine gap
  above for how picking interacts with the mirror.
- **Auto-closing:** after an `on_open` mirror, add
  `wait(30, 'trigger me/do_shut')` and a `do_shut` script that re-tags
  both sides `closed` — banks and airlocks love it.
- **Alarmed:** an extra line in `on_unlock` —
  `remit(loc(me), 'A klaxon barks once.')` — or `act(...)` to a guard
  post; the [guarded exit](checklist.md) items build on exactly this.
- **The same mirror pattern** runs linked teleporter pads, both halves
  of an intercom, and a lever in one room that raises a bridge in
  another: store a `partner`, write raw state, never call the partner's
  own triggers.
