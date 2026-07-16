# 056. Self-Destruct Sequence

> Checklist item 56 — [now] — *cancellable wait() chains, escalating remits, secret codes*

**What you'll build:** A station master computer with a five-stage
self-destruct: klaxons in every room of the zone, a countdown that
re-arms itself stage by stage, an `abort` console that demands a secret
code from anywhere on the station — and, if nobody types it in time,
fire in every compartment.

**Concepts:** a **cancellable `wait()` chain** (the handle is the
defuse), zone masters as station-wide `$`-commands, `act(...,
targeting='zone')` as the all-call, `prompt()` for the code entry, the
`secret` attribute flag, and spawned proximity hazards as consequences.

## How it works

1. **The countdown is a chain, not a schedule.** One `wait()` is
   pending at any moment. Each stage's script announces, decrements
   `count`, and schedules the *next* stage (`trigger me/countdown`) —
   so aborting never has to hunt down five timers, only the one in
   flight. `wait()` returns a **handle**; the script stashes it in
   `pending`, and `cancel_wait(handle)` is the entire defuse. The
   handle-in-an-attribute is the pattern: a bomb you can wire, you can
   also unwire. (`wait()` is in-memory and dies with a reboot — for a
   self-destruct, a countdown that a crash silently forgets is the
   correct failure mode. Contrast the EMP's `expire()` in item 57.)

2. **The station is a zone, and the zone does two jobs.** Rooms tagged
   `zone:station` make the master computer — an object tagged
   `zone_master` sharing the tag — audible *and* addressable
   station-wide:

   - Outbound: `act(me, '...', targeting='zone')` propagates the
     klaxon to every room in the master's zone. This is a real
     propagated action, not a text loop — wards can veto it, a room
     can lock out `reach` — but for sirens it behaves as the all-call.
   - Inbound: the softcode trigger search consults zone masters, so
     `$abort` on the master works from **any** room in the zone — the
     PennMUSH Zone-Master-Room trick. No abort consoles to scatter;
     the zone is the console.

3. **The code is a `prompt()` behind a `secret` flag.** `abort` doesn't
   parse arguments — it asks, and `prompt()` captures the player's
   next line into the `abort_check` callback (bound as `arg0`), which
   runs *as the master* — so it may read the master's `code` attribute
   and cancel the master's wait. The attribute itself is flagged
   `secret` (`@attr`), so a stranger's `get_attr` reads nothing:
   engine-enforced, like the safe combination in item 16.

4. **Consequences are spawned, not narrated.** The master cannot
   `damage()` someone three rooms away — damage is proximity
   authority. So zero-hour spawns `a sheet of roaring flame` into
   every zone room (legal: `create_obj` seeds rooms its owner
   controls), each carrying a copied `blast_tick` heartbeat that burns
   whoever is standing there, and each on an `expire()` fuse so the
   fires gutter out on their own. Same prototype-copy shape as the gas
   bomb's clouds (item 48).

## Build it

The station — two compartments, one zone:

```text
@dig Reactor Core = core, out
core
@zone here = station
@dig Cargo Bay = bay, core
bay
@zone here = station
core
```

The master computer. `@zone/master` makes it the zone's brain in one
line (it tags it `zone_master` + `zone:station`):

```text
@create Station Brain
drop Station Brain
@desc Station Brain = A pillar of screens and switches. A red panel reads: SELF DESTRUCT. A smaller one reads: ABORT.
@zone/master Station Brain = station
@set Station Brain/interval = 10
@set Station Brain/code = ZEBRA-9
@attr Station Brain/code = secret
```

Initiation — owner only, refuses to double-arm, announces zone-wide,
lights the first wait and *keeps the handle*:

```text
@set Station Brain/cmd_selfdestruct = $self destruct: pemit(enactor, 'The console demands command authority.') if enactor != owner(me) else (pemit(enactor, 'The countdown is already running.') if get_attr(me, 'pending') else (set_attr(me, 'count', 5), act(me, 'KLAXON: SELF-DESTRUCT SEQUENCE INITIATED. ' + str(5 * get_attr(me, 'interval', 10)) + ' SECONDS TO ZERO. ABORT requires command code.', targeting='zone'), set_attr(me, 'pending', wait(get_attr(me, 'interval', 10), 'trigger me/countdown'))))
```

The chain — each stage announces, re-arms, and re-stashes the handle;
stage zero hands over to `boom`:

```text
@set Station Brain/countdown = n = get_attr(me, 'count', 0) - 1; (eval_attr(me, 'boom') if n <= 0 else (set_attr(me, 'count', n), act(me, 'SELF-DESTRUCT IN ' + str(n * get_attr(me, 'interval', 10)) + ' SECONDS.', targeting='zone'), set_attr(me, 'pending', wait(get_attr(me, 'interval', 10), 'trigger me/countdown'))))
```

The abort — anywhere in the zone, anyone who knows the code:

```text
@set Station Brain/cmd_abort = $abort: prompt(enactor, 'Enter the abort code:', 'abort_check') if get_attr(me, 'pending') else pemit(enactor, 'The self-destruct is not armed.')
@set Station Brain/abort_check = (cancel_wait(get_attr(me, 'pending')), del_attr(me, 'pending'), del_attr(me, 'count'), act(me, 'KLAXON: SELF-DESTRUCT ABORTED. Authorization: ' + name(enactor) + '.', targeting='zone')) if trim(arg0) == str(get_attr(me, 'code')) else pemit(enactor, 'INVALID CODE. The countdown continues.')
```

And zero hour — fire in every compartment, on its own timer:

```text
@set Station Brain/blast_tick = [(pemit(o, 'Fire roars over you!'), damage(o, roll('2d6'))) for o in contents(loc(me)) if has_tag(o, 'player') or has_tag(o, 'npc')]
@set Station Brain/boom = del_attr(me, 'pending'); del_attr(me, 'count'); act(me, 'The deck heaves. Fire tears through every compartment!', targeting='zone'); blasts = [b for b in [create_obj('a sheet of roaring flame', location=r) for r in zone_rooms('station')] if b]; [set_attr(b, 'on_tick', get_attr(me, 'blast_tick')) for b in blasts]; [attach_behavior(b, 'script_ticker', interval=1) for b in blasts]; [expire(b, 20) for b in blasts]
```

## Try it

From the Reactor Core, as the owner:

```text
self destruct        -> (everywhere on station) KLAXON: SELF-DESTRUCT SEQUENCE INITIATED. 50 SECONDS TO ZERO. ...
```

Someone standing in the Cargo Bay hears every stage — `SELF-DESTRUCT
IN 40 SECONDS.` ... `30` ... — and can answer from right there:

```text
abort                -> Enter the abort code:
WOMBAT               -> INVALID CODE. The countdown continues.
abort                -> Enter the abort code:
ZEBRA-9              -> (everywhere) KLAXON: SELF-DESTRUCT ABORTED. Authorization: Zeke.
```

Let it run instead, and at zero every compartment reads `The deck
heaves. Fire tears through every compartment!` — then the flames
themselves take over, burning anyone present each tick until their
`expire()` gutters them out. The dead-panel check: with nothing
pending, `abort` answers `The self-destruct is not armed.`

## Going further

- **Escalating urgency** — stage the *message* too: switch on `n` to
  add `EVACUATE. EVACUATE.` under 20 seconds, or `ansi('rh', ...)` the
  final stage red.
- **Two-man rule** — require a second officer: first `$turn key` sets
  a `key_turned` timestamp, and `cmd_selfdestruct` refuses unless it
  is under 30 seconds old (`now()` arithmetic, item 55's clock).
- **Blast doors** — `boom` currently torches every zone room
  unconditionally; skip rooms whose exits are all `closed`, or spawn
  flame only along open paths from the core — the gas bomb's graph
  walk (item 48) slots straight in.
- **Wrong-code alarms** — the failed branch of `abort_check` can page
  the owner (item 50's line): three wrong codes is a story beat, not
  just a typo.
