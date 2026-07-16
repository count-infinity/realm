# 054. Security Camera & Monitor

> Checklist item 54 — now — *bug objects: ^listen + ON_ENTER/ON_LEAVE relays via pemit*

**What you'll build:** A camera that relays speech and movement from its
room to a monitor console in another room, where characters `watch` the
feed live — and a way for the heist crew to cut it. Part of the
[Heist arc](arc_heist.md): camera in the Vault Antechamber, monitor in
the Security Office.

**Concepts:** the bug/tap pattern (`^`-listen for speech,
`ON_ENTER`/`ON_LEAVE` for movement), cross-room delivery with `pemit()`,
an opt-in watcher list with self-pruning, `eval_attr()` as a shared
subroutine, and same-owner gadget pairs.

## How it works

An object in a room overhears what happens there through two engine
seams:

- **Speech** — a `^pattern:code` listen trigger fires for anything said
  in the object's room. The pattern `^*` matches everything, the spoken
  text arrives as `arg0`, and the speaker is `enactor`.
- **Movement** — the camera is a *witness*: arrivals fire its `ON_ENTER`
  attribute, departures its `ON_LEAVE`, with the mover as `enactor`.

That's the whole bug. The camera doesn't transform anything; it forwards
each line to whoever subscribed at the far console using `pemit()` —
which delivers to a named target anywhere, no shared room required.

Three details carry the design:

1. **One relay, three callers.** The forwarding logic lives in a single
   `relay` attribute; the listen and both event hooks call it with
   `eval_attr(me, 'relay', text)`. Fix the relay once, all three feeds
   change.
2. **The feed is diegetic.** `watch` adds you to the monitor's
   `watchers` list; each relayed line goes only to watchers *still
   standing in the monitor's room*, and anyone who wandered off is
   pruned on the next relay — no ticker needed. (`unwatch` is just the
   list minus you.)
3. **Same owner, or no deal.** The camera writes the monitor's watcher
   list (`set_attr` on another object), which works only because both
   gadgets belong to one builder — softcode wields its owner's
   authority. A pair split across owners fails quietly, and should.

One honest note: `name(enactor)` is the *true* name. Perception masking
("Someone arrives.") is a message-delivery concern; softcode reads the
world as it is. Your camera sees through stealth's anonymity — decide
whether that's a feature (thermal optics) before you hang one where
sneaks matter. Also, `@teleport` skips the departure event by design
(it's a placement, not a walk), so only walkers trip `ON_LEAVE`.

## Build it

The console first, in the office. The two `$`-commands just edit the
watcher list:

```text
@teleport me = The Security Office
@create security monitor
drop security monitor
@desc security monitor = A bank of grainy feeds. WATCH to put an eye on the vault approach; UNWATCH to look away.
@set security monitor/cmd_watch = $watch: ws = get_attr(me, 'watchers') or []; set_attr(me, 'watchers', ws if enactor.id in ws else ws + [enactor.id]); pemit(enactor, 'You settle in at the console. The antechamber feed flickers to life.')
@set security monitor/cmd_unwatch = $unwatch: set_attr(me, 'watchers', [i for i in (get_attr(me, 'watchers') or []) if i != enactor.id]); pemit(enactor, 'You look away from the monitor.')
```

The camera, in the antechamber. `feed` names its console (looked up
fresh on every relay — late binding, so you can re-point it live):

```text
@teleport me = Vault Antechamber
@create security camera
drop security camera
@desc security camera = A glass eye on a ceiling mount, cable disappearing into the wall.
@set security camera/powered = 1
@set security camera/feed = security monitor
```

The relay — resolve the console, collect watchers still in its room,
deliver, prune. The `powered` guard is the sabotage switch; note it
zeroes the audience, so every feed dies at one point:

```text
@set security camera/relay = m = get(get_attr(me, 'feed', '')); ws = (get_attr(m, 'watchers') or []) if (m and get_attr(me, 'powered', 1)) else []; live = [w for w in [get('#' + str(i)) for i in ws] if w and loc(w) == loc(m)]; [pemit(w, '[' + name(me) + '] ' + str(arg0)) for w in live]; set_attr(m, 'watchers', [w.id for w in live]) if m and len(live) != len(ws) else None
```

The three taps, each a one-line caller:

```text
@set security camera/listen_feed = ^*: eval_attr(me, 'relay', name(enactor) + ' says, "' + arg0 + '"') if enactor else None
@set security camera/on_enter = eval_attr(me, 'relay', name(enactor) + ' arrives.') if enactor else None
@set security camera/on_leave = eval_attr(me, 'relay', name(enactor) + ' leaves.') if enactor else None
```

And counterplay — an Electronics check at -2 to kill the power:

```text
@set security camera/cmd_cut = $cut *: (set_attr(me, 'powered', 0), remit(loc(me), name(enactor) + ' snips a cable -- the camera light dies.')) if skill_check(enactor, 'electronics', -2) else pemit(enactor, 'Sparks jump; the housing is trickier than it looks.')
```

## Try it

In the office:

```text
watch                        -> You settle in at the console. ...
```

Now have anyone act in the Vault Antechamber:

```text
(they say "psst")            -> [security camera] Zeke says, "psst"
(they walk out the duct)     -> [security camera] Zeke leaves.
(they crawl back in)         -> [security camera] Zeke arrives.
unwatch                      -> silence
```

Walk away from the console mid-watch and the next relay drops you from
the list. And from the antechamber side, the crew's answer:

```text
cut camera                   -> (Electronics -2) ... the camera light dies.
```

## Going further

- **Multi-camera console** — keep `watchers` per camera name and a
  `$watch *` that picks a feed; `relay` already knows which camera it is
  (`name(me)`).
- **Recording** — append each relayed line to a `log` list attribute on
  the monitor, capped with a slice, and add a `$playback` command.
- **Two-way intercom** — a `$page *` on the monitor that
  `remit(loc(get(get_attr(me, 'camera'))), ...)` — the tap reversed.
- **Combat coverage** — the camera can witness any event: an `ON_ATTACK`
  tap turns it into a gun-camera that calls guards via a zone `act()`.
