# 161. Travel time

> Checklist item 161 — now — *non-instant traversal via a dead-end exit, wait() progress, teleport on arrival, interruption*

**What you'll build:** A long road where walking isn't instant. Step
onto it and you're "on the road" — progress lines tick past, and only
after the journey elapses do you arrive at the far end. Change your mind
and `turn back` to abandon the trek.

**Concepts:** a **dead-end exit** whose `ON_FAIL` launches a journey (the
portal pattern, [tutorial 033](033_portal_pair.md)); **journey tokens** —
small owned objects that hold each traveller's clock, sidestepping the
rule that scripts can't write players; a `wait()` **sweep** that delivers
progress and `teleport_obj`s arrivals; and interruption as leaving the
road.

## How it works

**The road is a dead-end that catches you.** Walk the `road` exit and it
goes nowhere — so the engine fires its `ON_FAIL`, and because *you* chose
to walk it, that hook may relocate you (the sanctioned portal grant). It
moves you into a transit room, `The Long Road`, and drops a **journey
token** beside you: a tiny object the road owns, stamped with your id,
your destination, and an `eta` (`now()` + the travel time). Tokens exist
because a road script *cannot* write attributes onto a player — but it
can freely stamp an object it owns, and read it back later.

**One sweep serves every traveller.** The road schedules a `wait()` that
runs `sweep`. Each pass walks the tokens in transit: anyone whose `eta`
has arrived is `teleport_obj`'d to their destination and their token
destroyed; everyone still en route gets a progress line. If travellers
remain, `sweep` re-arms another `wait()`; when the road empties, it
stops. (The road may relocate a player standing in a room it owns —
Penn's room-owner teleport — which is exactly the transit room.)

**Interruption is leaving the road.** `turn back`, on the transit room,
finds your token, moves you home, and destroys it — you fall out of the
sweep. Any other way off the road would do the same: no token, no
arrival.

**`wait()`, with the reboot caveat.** These timers are in-memory; a
restart mid-journey strands travellers on the road (the tokens persist,
but the `wait` chain doesn't). For journeys that must survive a reboot,
drive the sweep from a `script_ticker` instead — the tokens are already
persistent.

## Build it

Trailhead, destination, and the road-between (a transit room with no
ordinary exits):

```text
@dig The Trailhead
@teleport me = The Trailhead
@dig The Hillfort
@teleport me = The Trailhead
@dig The Long Road
@teleport me = The Trailhead
```

The `road` exit — opened, then unlinked into a dead end — and its data:
where it leads, the transit room, home, and the timings:

```text
@open road = The Trailhead
@unlink road
@set road/fail_msg = The road is long; better to set out properly.
@eval r = [e for e in contents(here) if has_tag(e,'exit') and name(e)=='road'][0]; set_attr(r,'goal','#'+get('The Hillfort').id); set_attr(r,'transit','#'+get('The Long Road').id); set_attr(r,'home','#'+here.id); set_attr(r,'travel_time', 6); set_attr(r,'step', 2); result='road armed'
```

`ON_FAIL` launches the journey — move the walker into transit, mint their
token, and start the sweep if it isn't already running:

```text
@set road/on_fail = trans = get(get_attr(me,'transit')); (move_to(enactor, trans), (lambda tok: (set_attr(tok,'traveler', '#'+enactor.id), set_attr(tok,'goal', get_attr(me,'goal')), set_attr(tok,'home', get_attr(me,'home')), set_attr(tok,'eta', now() + int(get_attr(me,'travel_time',6)))))(create_obj('a traveller', tags=['journeying'], location=trans)), pemit(enactor, 'You shoulder your pack and set out. The fort is a long walk off.'), remit(get(get_attr(me,'home')), name(enactor) + ' sets off up the road.'), (wait(int(get_attr(me,'step',2)), 'trigger me/sweep'), set_attr(me,'sweeping',1)) if not get_attr(me,'sweeping') else None)
```

The sweep — arrivals teleport and their tokens die; the rest get a
progress line; re-arm while anyone remains:

```text
@set road/sweep = trans = get(get_attr(me,'transit')); toks = [o for o in contents(trans) if has_tag(o,'journeying')]; [ (destroy_obj(tok) if get(get_attr(tok,'traveler')) is None or loc(get(get_attr(tok,'traveler'))) is not trans else ((teleport_obj(get(get_attr(tok,'traveler')), get(get_attr(tok,'goal'))), pemit(get(get_attr(tok,'traveler')), 'The walls of the Hillfort rise at last; you have arrived.'), remit(get(get_attr(tok,'goal')), name(get(get_attr(tok,'traveler'))) + ' trudges in through the gate, road-dusty.'), destroy_obj(tok)) if now() >= get_attr(tok,'eta', now()+999) else pemit(get(get_attr(tok,'traveler')), 'The road unrolls on beneath your boots...'))) for tok in toks ]; left = [o for o in contents(trans) if has_tag(o,'journeying')]; (wait(int(get_attr(me,'step',2)), 'trigger me/sweep') if left else set_attr(me,'sweeping',0))
```

And the escape hatch — `turn back`, on the transit room itself:

```text
@set The Long Road/cmd_turnback = $turn back: toks = [o for o in contents(here) if has_tag(o,'journeying') and get_attr(o,'traveler')=='#'+enactor.id]; (pemit(enactor, 'You are not on the road.') if not toks else (move_to(enactor, get(get_attr(toks[0],'home'))), destroy_obj(toks[0]), pemit(enactor, 'You give it up and trudge back the way you came.')))
@desc The Long Road = A rutted track winding through gorse, going on and on. TURN BACK to abandon the journey.
```

## Try it

```text
road                -> "You shoulder your pack and set out..."
                       you're on The Long Road now
                    -> "The road unrolls on beneath your boots..."   (each beat)
                    -> "The walls of the Hillfort rise at last; you have arrived."
```

Walk it again and `turn back` before the timer elapses — you trudge home
to the Trailhead and the sweep forgets you. Send two people up the road
at once: one sweep serves both, each on their own token clock.
`@examine` a token mid-journey to see the `eta` counting down.

## Going further

- **Distance as data:** put `travel_time` on the *exit*, and a long road
  and a short lane share all this code at different speeds.
- **Perils on the way:** the sweep already visits everyone in transit —
  roll an ambush ([tutorial 043](043_hazard_room.md)) on a bad beat, or
  a chance to find something in the ditch.
- **Reboot-proof journeys:** swap the `wait()` chain for a
  `script_ticker` on the transit room ([tutorial 152](152_reboot_surviving_timers.md));
  the tokens persist, so travel survives a restart.
- **Faster on a mount:** a [mounted](158_mounts.md) traveller could carry
  a shorter `travel_time` — read a `mounted` marker when minting the
  token.
