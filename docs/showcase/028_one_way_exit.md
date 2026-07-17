# 028. One-Way Exit

> Checklist item 28 — now — *single exits, ON_LEAVE/ON_ARRIVE message overrides*

**What you'll build:** A laundry chute: step in upstairs, land in the
laundry vault below, and find that the way you came is not a way back —
complete with a greased dead-end `up` exit that explains itself.

**Concepts:** exits as one-way edges (`@dig` with a single exit name,
`@open`), room `ON_LEAVE`/`ON_ENTER` flavor triggers, dead-end exits
(`create_obj` with no `destination`) and their `fail_msg`, and why a
one-way room always needs *some* way out.

## How it works

**Every exit is one-way already.** A REALM exit is just an object in a
room with an `exit` tag and a `destination` — the "two-way doors"
you're used to are *two* of them, and `@dig The Garden = north` only
auto-creates the return leg because `north` has a compass opposite.
Name the exit something directionless — `laundry chute` — and `@dig`
digs exactly one edge. One-way is not a feature you add; two-way is.

**Flavor rides on the rooms.** The engine narrates every walk the same
way (`You leave laundry chute.` / `{actor} arrives.`) — there are no
per-exit message override attributes. What you *can* do is layer flavor
on top: rooms witness movement, so the landing's `ON_LEAVE` and the
vault's `ON_ENTER` fire around the stock lines.

**Which exit carried them?** Movement triggers are handed the action's
payload, so a room trigger *can* ask: `adata('exit')` is the exit
object, alongside `adata('destination')` and `adata('direction')`. On a
room with several ways out, that's how you keep the chute's flavor off
the front door — `... if adata('exit') == get('laundry chute') else
None`. This build doesn't spend the clause, because the geometry
already decides: the landing's only exit *is* the chute, and the vault
can only be *entered* by falling down it, so the guard could never be
false. Let the shape of the map do the work when it can; reach for
`adata('exit')` the moment it can't.

**The dead end that talks back.** Players below *will* try `up`. Give
them an exit that exists but goes nowhere: an exit object with no
`destination` is a dead end, and walking it shows the exit's `fail_msg`
(after firing `ON_FAIL`, for softcode that wants to react). `@open`
insists on a destination, so the dead end is one `@eval` with
`create_obj(tags=['exit'])` — the same programmatic exit-building the
[portal pair](033_portal_pair.md) leans on.

## Build it

Dig the landing, then the vault below it — one exit name, no compass
opposite, so no return leg is created:

```text
@dig Upper Landing
@teleport me = Upper Landing
@dig The Laundry Vault = laundry chute
@desc laundry chute = A brass flap in the wall, polished by ten thousand bundles.
@set here/on_leave = pemit(enactor, 'The flap snaps shut over your head. Gravity does the rest.') if has_tag(enactor, 'player') else None
```

Drop through, and dress the far end — the arrival line, the lying `up`
exit, and (because one-way secrets strand people — tutorial 027's
lesson) a legitimate way out:

```text
laundry chute
@set here/on_enter = pemit(enactor, 'You shoot out of the ceiling into a mountain of linen.') if has_tag(enactor, 'player') else None
@eval up = create_obj('up', tags=['exit'], location=here); set_attr(up, 'fail_msg', 'You scrabble two feet up the greased brass and slide right back into the linen.'); result = 'dead-end dug: ' + up.id[:8]
@open service stair = Upper Landing
```

Note the shape of the geometry now: the landing's only exit is the
chute (down), the vault's only *real* exit is the stair (up and out) —
each room has one leave-path, which is exactly what makes the room
flavor triggers safe to write without knowing which exit fired them.

## Try it

```text
laundry chute       -> The flap snaps shut over your head. Gravity does the rest.
                       You leave laundry chute.
                       You shoot out of the ceiling into a mountain of linen.
look                -> Exits: up, service stair
up                  -> You scrabble two feet up the greased brass and slide
                       right back into the linen.
service stair       -> the long way around, back to the landing
```

The `up` exit *shows* in the exits line — that's deliberate. A chute
you might climb back up is a puzzle; the refusal text is the answer.

## Engine gaps

- No authored per-exit movement messages: the audit's "ON_LEAVE/
  ON_ARRIVE message overrides" are additive flavor, not overrides — the
  stock `You leave <exit>.` / `{actor} arrives.` lines always print,
  and there is no `leave_msg`/`arrive_msg` attribute pair to replace
  them.
- ~~Room `ON_LEAVE`/`ON_ENTER` triggers can't read which exit carried
  the mover~~ — **FIXED 2026-07-17**: event triggers now bind the
  action's payload, so `adata('exit')` (and `adata('destination')` /
  `adata('direction')`) work in room movement triggers exactly as they
  always did in wards. Per-exit flavor no longer needs single-exit
  geometry — this build keeps it because it's the *design*, not a
  workaround. See "How it works".

## Going further

- **A mover-side hook:** `ON_ARRIVE` is the one movement trigger that
  fires on the *traveler* — `@set me/on_arrive = pemit(me, 'You check
  your kit.')` gives a character a personal arrival ritual anywhere
  they go. You control yourself, so any player can set their own.
- **A drop that hurts** — fold in the [climbing exit](034_climbing_exit.md)
  pattern: `check_skill = acrobatics` on the chute, `ON_FAIL` damage,
  and a graceless landing costs HP.
- **Trapdoor variant** — tag the chute `closed` and hide the `open`
  under a `$pull lever:` trigger; one-way *and* gated.
- **True oubliette** — skip the service stair and the room is a prison;
  then *someone* needs `@teleport` or a [toll](030_toll_gate.md)/
  [guard](031_guarded_exit.md) to control the only door in. Strand
  people on purpose or not at all.
