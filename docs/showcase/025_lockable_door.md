# 025. Lockable Door

> Checklist item 25 ([now]): *paired exits, shared door-state attrs, traverse locks*

**What you'll build:** A vault door between two rooms that behaves like
one *physical* door: close it, lock it with a brass key, open it from
either side, and both sides always agree.

**Concepts:** `@dig` paired exits (and the `@pair` command that
marries hand-built ones), the door state convention (`closed` and
`locked` tags plus a `key_id` attribute), key items (`unlocks`), the
built-in `open`/`close`/`lock`/`unlock` commands, and the **mirror
pattern**: [`ON_OPEN`/`ON_CLOSE`/`ON_LOCK`/`ON_UNLOCK`](../reference/softcode.md#lifecycle-hooks)
hooks that copy every state change onto a partner object. The mirror
pattern reuses anywhere two objects must share state.

## How it works

**Door state is convention, all engine-enforced.** An exit with the
`closed` tag refuses traversal (`The vault door is closed.`). A `locked`
tag refuses `open` (with your `locked_msg`). `key_id` names the lock,
and any carried item whose `unlocks` matches it powers the stock
`lock`/`unlock` commands. None of this needs scripting; one side of a
door is a solved problem.

**The two-sided problem.** `@dig The Vault = vault door, vault door`
gives you what every MU* gives you: *two independent exit objects*
wearing the same name, A→B in this room and B→A in the new one. Tag one
side `closed` and the other side still stands open; unlock the north
face and walk through, and the south face still claims to be locked.
Every multi-room build hits this eventually. What links them is the
**pairing** the engine made at birth: a two-way `@dig` stamps each
exit's `partner` attribute with the other's `#id`, and the engine owns
that relationship end to end. Relinking a paired exit (`@link`,
`@unlink`) *dissolves* the pairing on both sides, loudly, rather than
silently dragging a mirror along to an unrelated door, and `@destroy`
of one side clears the survivor; `@pair <exit> = <far exit>` marries
hand-built `@open` exits, disambiguates double doors between the same
two rooms, and re-marries after a relink.

**The fix: mirror on events.** Whenever a door changes state, the engine
propagates an action (`item:on_open`, `item:on_close`, `item:on_lock`,
`item:on_unlock`) with the exit as target, so the exit can carry four
tiny [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) scripts
that copy the new state onto its partner. Three rules make the mirror
sound:

- **Guard every hook with [`target is me`](../reference/softcode.md#guard-on-target).**
  An `ON_<EVENT>` hook fires on *every* object in the room, not only the
  one acted on, so an unguarded `on_open` mirror would fire when someone
  opens a *crate* beside the door and quietly un-close the far side. The
  guard makes the hook react to its own business only.
- **Write raw state, never commands.** The hooks fire on the *commands*
  (`open`/`close`/`lock`/`unlock`), and the script writes raw state
  ([`add_tag`](../reference/softcode.md#fn-add_tag)/[`remove_tag`](../reference/softcode.md#fn-remove_tag))
  on the partner rather than "opening" it. Direct writes don't
  propagate, so the mirror can't echo back and forth: recursion-proof by
  construction.
- **Authority is your own.** You dug both exits, so you own both, and a
  script runs with its object's owner's authority, so each side may
  write its sibling. (Which side is authoritative? Neither: last write
  wins, and since every write mirrors immediately, they can never
  drift.)

The mirror scripts simply read that engine-maintained `partner`
attribute with `V('partner')`; nothing is wired by hand.

## Build it

Dig the vault with the same name on both faces, and cut the key
(`@create` leaves it in your hand; keep it there). The `@dig` output
confirms the two faces were **paired** at creation, which is the whole
wiring step:

```text
@dig The Vault = vault door, vault door
@create brass key
@set brass key/unlocks = vault_brass
```

Now configure the near side: the lock identity, the refusal line, and
the four mirror hooks. Each hook is one guarded statement, and the
guard is not optional (see above):

```text
@set vault door/key_id = vault_brass
@set vault door/locked_msg = The wheel spins uselessly. Locked tight.
@set vault door/on_open = if target is me: remove_tag(V('partner'), 'closed')
@set vault door/on_close = if target is me: add_tag(V('partner'), 'closed')
@set vault door/on_lock = if target is me: add_tag(V('partner'), 'locked')
@set vault door/on_unlock = if target is me: remove_tag(V('partner'), 'locked')
```

Walk through the (still unlocked) doorway and give the far side the
identical six lines; `@set` resolves `vault door` locally, so the same
commands configure whichever side you're standing at:

```text
vault door
@set vault door/key_id = vault_brass
@set vault door/locked_msg = The wheel spins uselessly. Locked tight.
@set vault door/on_open = if target is me: remove_tag(V('partner'), 'closed')
@set vault door/on_close = if target is me: add_tag(V('partner'), 'closed')
@set vault door/on_lock = if target is me: add_tag(V('partner'), 'locked')
@set vault door/on_unlock = if target is me: remove_tag(V('partner'), 'locked')
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
brass key.`), and `@examine` the *far* side at any point to watch its
`closed` and `locked` tags change in lockstep. Walking into the closed
door refuses with `The vault door is closed.`; `open` refuses with your
`locked_msg`; the key unlocks, the door opens, and you're in the vault.
Now prove the point of the whole build: lock yourself in, and have a
keyless friend try the *other* side:

```text
close vault door
lock vault door
```

Your friend in the workshop gets `The vault door is closed.` walking in,
`The wheel spins uselessly. Locked tight.` on `open`, and `You don't
have the key.` on `unlock`. One door, two faces, one truth.

## Going further

- **Pickable:** `@set vault door/lock_skill = lockpicking` and
  `@set vault door/lock_difficulty = 2` let `pick vault door` roll
  against the lock (carry lockpicks or take -5). A successful pick fires
  the same `ON_UNLOCK` event a key does, with `picked` set in the
  [event data](../reference/softcode.md#event-data-namespace), so the
  mirror follows and an alarm script can single out picks
  (`if adata('picked'): ...`). A keycard swipe (`use card on door`)
  mirrors the same way.
- **Auto-closing:** after an `on_open` mirror, add
  [`wait(30, 'trigger me/do_shut')`](../reference/softcode.md#fn-wait)
  and a `do_shut` script that re-tags both sides `closed`; banks and
  airlocks love it.
- **Alarmed:** an extra line in `on_unlock`,
  [`remit(loc(me), 'A klaxon barks once.')`](../reference/softcode.md#fn-remit),
  or [`act(...)`](../reference/softcode.md#fn-act) to a guard post; the
  guarded-exit items in the [checklist](checklist.md) build on exactly
  this.
- **The same mirror pattern** runs linked teleporter pads, both halves
  of an intercom, and a lever in one room that raises a bridge in
  another: store a `partner`, write raw state, never call the partner's
  own triggers.
