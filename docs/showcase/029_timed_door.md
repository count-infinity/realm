# 029. Timed Door

> Checklist item 29 — now — *wait()/cancel_wait, state reversion, atomicity*

**What you'll build:** A blast door that only a wall switch opens — and
thirty seconds later, slams itself shut. Press twice and the countdown
extends instead of slamming early: one door, any number of presses,
exactly one slam.

**Concepts:** `$`-command triggers driving door state (`closed` tag as
raw writes), `wait()` for short mechanical timers (and why not
`expire()`), and a **pending-ticket generation counter** — the small
piece of state that makes stacked timers collapse into a single
reversion instead of racing each other.

## How it works

**The door is stock parts.** A `closed`-tagged exit refuses traversal
with its `closed_msg`; the switch's script `remove_tag`s / `add_tag`s
that state directly (raw writes, owner authority — switch and door
share a builder). No new machinery on the door at all: everything
interesting lives on the switch.

**`wait()` is the right timer.** Two schedulers exist and they are not
interchangeable: `wait(sec, cmd)` is an in-memory countdown, exact and
cheap, that **dies with a restart**; `expire(obj, sec)` is a persistent
*lifetime* — it survives reboots, but it fires `ON_EXPIRE` and then
**destroys the object** unless the handler pushes the timestamp out.
For a thirty-second mechanical relay, `wait()` is the honest choice:
the worst a badly-timed reboot can do is leave the door open until
someone presses the switch again, while bending `expire()` to the job
means hanging a self-destruct on your door and remembering to defuse it
in the handler every time. Short and expendable: `wait()`. Long-lived
and must-not-leak: `expire()`. (The gas bomb, tutorial 048, uses both
for exactly these reasons.)

**The double-slam problem.** Naive version: every press does
`open + wait(30, close)`. Press at t=0 and again at t=20 and there are
now *two* countdowns in flight: the first slams the door at t=30 — ten
seconds into the second press's window — and the second slams again at
t=50, possibly onto someone mid-doorway who pressed at t=45. Timers
you can't cancel from inside must be **defused by state**: each press
takes a *ticket* (`incr('pending')`), each slam retires one
(`decr('pending')`, which hands back the new count), and only the slam
that retires the **last** ticket actually closes the door. Stale
timers wake up, see a newer generation outstanding, and go back to
sleep. (`cancel_wait()` — cancel the stored handle, schedule a fresh
one — solves the same race by keeping only one timer alive; the ticket
counter is the belt-and-braces version that stays correct even if a
handle ever goes missing, and it's the pattern that generalizes to
timers you *didn't* schedule yourself.)

## Build it

The door first — dig it closed, with a refusal line that points at the
switch. `blast door` has no compass opposite, so the vault's only door
is this one face:

```text
@dig Generator Room
@teleport me = Generator Room
@dig Reactor Vault = blast door
@tag blast door = closed
@set blast door/closed_msg = The blast door is sealed. There must be a switch.
```

The vault's only door is that one face, and it *will* slam behind
people — so give the room a humble way back out (a slammed door that
strands players is tutorial 028's cautionary tale):

```text
@teleport me = Reactor Vault
@open service hatch = Generator Room
@teleport me = Generator Room
```

Now the switch. `delay` is data, so the countdown is tunable without
touching code. The press script: take a ticket, open the door (or just
reset the countdown if it's already open), and light the fuse:

```text
@create pressure switch
drop pressure switch
@set pressure switch/delay = 30
@set pressure switch/cmd_press = $press switch: d = get('blast door'); incr('pending'); (remove_tag(d, 'closed'), remit(loc(me), 'Hydraulics whine -- the blast door grinds open. Somewhere a countdown starts ticking.')) if has_tag(d, 'closed') else remit(loc(me), 'Clunk. The countdown resets.'); wait(V('delay', 30), 'trigger me/slam')
```

And the slam — retire a ticket, and only the last one standing gets to
close anything:

```text
@set pressure switch/slam = d = get('blast door'); p = decr('pending'); (add_tag(d, 'closed'), remit(loc(me), 'WHAM! The blast door slams shut.')) if p <= 0 and not has_tag(d, 'closed') else None
```

The `not has_tag(d, 'closed')` guard is the second half of atomicity:
if someone `close`d the door by hand mid-window, the expiring timer
doesn't slam a door that's already shut.

## Try it

```text
blast door          -> The blast door is sealed. There must be a switch.
press switch        -> Hydraulics whine -- the blast door grinds open.
                       Somewhere a countdown starts ticking.
press switch        -> Clunk. The countdown resets.      (20s later, say)
                       ...one WHAM!, ~30s after the SECOND press
press switch
blast door          -> you're in the Reactor Vault, and behind you: WHAM!
service hatch       -> the crawl back out to the generator room
```

Watch the second run of presses: two countdowns were genuinely
scheduled, but the room hears exactly one slam, at the *later*
deadline. `@examine pressure switch` mid-window and you can see the
ticket count climb and fall.

## Going further

- **Restart-proof variant** — if this door guards something that must
  never stay open across a reboot, move the timer onto the door:
  `expire(d, 30)` on press, and on the door
  `@set blast door/on_expire = add_tag(me, 'closed'); del_attr(me, 'expires_at'); remit(loc(me), 'WHAM!')`.
  The `del_attr` is load-bearing: an `ON_EXPIRE` whose timestamp still
  reads past-due afterwards gets **destroyed** by the world tick.
- **`cancel_wait()` flavor** — store the handle
  (`set_attr(me, 'timer', wait(...))`) and cancel it on re-press; the
  ticket check then never fires stale. Both patterns compose.
- **Both sides** — this door is one face; for a two-faced timed door,
  pair the exits and mirror state per [tutorial 025](025_lockable_door.md),
  and have press/slam write both faces.
- **Alarm coupling** — the slam script is just softcode: add
  `act(...)` to a guard post, or have the [security camera](054_security_camera.md)
  relay the WHAM.
