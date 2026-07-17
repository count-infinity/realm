# 057. EMP Charge

> Checklist item 57 — [now] — *tag-targeted loops, temporary state with timed restore*

**What you'll build:** A one-shot EMP charge that sweeps the room it's
set off in, kills every `electronic`-tagged device for thirty seconds,
then restores them as its own casing crumbles — plus two gadgets to
prove it on.

**Concepts:** tags as a **device convention** (`electronic` /
`disabled`), sweep loops over `contents()`, remembering what you did in
a list attribute so you can undo exactly that, `expire()` + `ON_EXPIRE`
as the restore timer (and why it beats `wait()` here), and the
gadget-checks-its-own-flag contract.

## How it works

1. **"Electronic" is a handshake, not a law.** The engine has no idea
   what electronics are. The convention is two tags: devices carry
   `electronic` (I can be EMP'd), and the EMP hangs `disabled` on them
   (you are, currently). Every device's *own* softcode honors the flag
   — one guard clause per gadget, `has_tag(me, 'disabled')`, deciding
   between working and being dead glass. The security camera's
   `powered` attribute (item 54) is the same contract with an
   attribute; tags win here because the EMP must *find* its victims,
   and `has_tag(o, 'electronic')` over `contents(loc(me))` is the
   query. A gadget that skips the guard simply isn't electronic in the
   way that matters — the sweep can tag it, but nothing will listen.

2. **The sweep remembers its victims.** The pulse collects everything
   it disables and stores the ids in a `hit` list on the charge. The
   restore then lifts exactly those flags — not "everything disabled
   in the room", which would wrongly free devices some *other* effect
   had shut down, and would miss a drone that got carried out mid-
   blackout. Undo lists beat re-queries whenever state can move.

3. **The restore is `expire()`, and that's a deliberate choice.** The
   gas bomb (item 48) laid out the rule: `wait()` is in-memory and
   dies with a reboot; `expire()` is a timestamp *on the object*,
   swept by the world tick. A `wait()`-based restore that a reboot
   swallows leaves every gadget in the room bricked forever. Instead
   the spent charge itself carries the countdown: `expire(me, 30)`,
   and its `ON_EXPIRE` runs the restore before the engine destroys the
   casing. The hazard cleans up after itself *even across a restart*,
   and the prop's death and the effect's end are one event.

4. **Authority, as always.** `add_tag`/`remove_tag` mutate, and
   mutation needs control — this EMP knocks out *its owner's* devices
   (one builder owns this whole lab, so the sweep lands). Against a
   stranger's gadget the tag write fails quietly. On a live game the
   general-purpose weapon is an admin-owned charge, exactly like the
   admin-owned gas bomb; a player-owned EMP is a tool for sabotaging
   your own tech, or tech whose owner delegated you control.

## Build it

A lab and two victims — note each gadget's guard clause is where
`disabled` gets its meaning:

```text
@dig The Drone Lab = lab, out
lab
@create sweeper drone
drop sweeper drone
@tag sweeper drone = electronic
@desc sweeper drone = A knee-high maintenance drone, rotors idling. PING it for a status check.
@set sweeper drone/cmd_ping = $ping drone: pemit(enactor, 'The drone chirps: ALL SYSTEMS NOMINAL.') if not has_tag(me, 'disabled') else pemit(enactor, 'The drone lies inert, rotors still.')
@create wall terminal
drop wall terminal
@tag wall terminal = electronic
@desc wall terminal = A recessed screen glowing standby-green. LOGIN to use it.
@set wall terminal/cmd_login = $login: pemit(enactor, 'ACCESS GRANTED. Directory listings scroll past.') if not has_tag(me, 'disabled') else pemit(enactor, 'The screen is dead glass.')
```

The charge. `arm emp` refuses to fire in your hands, then hands off to
the `pulse` payload — sweep, remember, announce, start the restore
clock:

```text
@create EMP charge
@set EMP charge/cmd_arm = $arm emp: eval_attr(me, 'pulse') if loc(me) and has_tag(loc(me), 'room') else pemit(enactor, 'Not while you are holding it. Set it down first.')
@set EMP charge/pulse = hit = [o for o in contents(loc(me)) if has_tag(o, 'electronic') and not has_tag(o, 'disabled') and o != me]; [add_tag(o, 'disabled') for o in hit]; set_attr(me, 'hit', [o.id for o in hit]); remit(loc(me), 'A soundless white PULSE. Every status light in the room goes dark.'); expire(me, 30)
@set EMP charge/on_expire = [remove_tag(get(f'#{i}'), 'disabled') for i in (V('hit') or [])]; remit(loc(me), 'One by one, status lights flicker back to life. The spent EMP casing crumbles to slag.')
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

The charge is gone — `ON_EXPIRE` ran the restore, and expiry destroyed
the prop. Try `arm emp` while carrying it and it refuses; an EMP in
your backpack disables *your* gear too, which is a lesson better read
than lived.

## Going further

- **Hardened gear** — skip targets tagged `shielded` in the sweep;
  sell Faraday cases as wearables whose `grants_tags` confers it.
- **Drones that die louder** — give the drone an `ON_TICK` patrol
  (item 60) and have its tick guard on `disabled` too: the EMP then
  visibly stops a *moving* thing, not just a status line.
- **Area denial** — sweep the whole zone instead:
  loop `zone_rooms(...)` and disable per room — but remember `remit`
  reaches one room; use `act(..., targeting='zone')` (item 56) for
  the announcement.
- **Partial fry** — on restore, roll `rand(1, 6)` per victim and leave
  a 1 permanently `disabled` until repaired with an Electronics check
  — counterplay for the *owner* of the gadgets, for a change.
