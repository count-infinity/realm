# 048. Gas Bomb

> Checklist item 48 — now — *wait() fuses, exits() graph spreading, resisted effects, expire()*

**What you'll build:** A canister you `arm` with a fuse. It detonates,
fills its room with gas, spreads through every open exit, and forces
HT-based fortitude rolls on everyone caught in a cloud — then the clouds
dissipate on their own. Part of the [Heist arc](arc_heist.md); it lives
in the Maintenance Corridor.

**Concepts:** `wait()` vs `expire()` (and when each is right), walking
the room graph via `exits()`, skills as data (`skill_def` + `@reload`),
prototype-attribute copying, `create_obj()` authority, `script_ticker`
for ongoing exposure, and cloud `ON_ENTER` for latecomers.

## How it works

Five pieces, each an engine seam:

1. **The resistance roll is data.** GURPS says gas is resisted with HT.
   REALM's skill table is extendable from inside the game: a `skill_def`
   object named `fortitude` with `stat = health, penalty = 0` plus
   `@reload` makes `skill_check(o, 'fortitude', -1)` roll against the
   target's health attribute — no engine change, same trick as the
   pickpocket skill in tutorial 12.

2. **The fuse is a `wait()`** — in-memory and exact to the tenth of a
   second. Deliberately so: pending waits die with a reboot, and a
   ten-second fuse that a restart defuses is acceptable (a fuse that
   *survived* into the rebooted world half-fired would not be). The
   scheduled command is `trigger me/detonate`, so the bang itself is an
   ordinary attribute you can `@tr` to test.

3. **Spread is a graph walk.** Rooms are nodes, exits are edges.
   `exits(loc(me))` lists the exits here; each one's `destination`
   attribute holds a room id that `get('#' + id)` resolves. We skip
   `closed` exits — **closed doors hold gas back** — and note the flip
   side: the *hidden* grate is open, so gas finds the secret crawlway.

4. **Clouds are objects, and their code is copied, not typed.** Writing
   scripts inside a script means quoting hell, so the cloud's two
   handlers live on a **prototype** under inert names (`cloud_tick`,
   `cloud_enter` — not trigger names, so the prototype itself never
   fires). Detonation copies them onto each fresh cloud under the live
   names `on_tick` / `on_enter`. Exposure is the cloud's own
   `script_ticker` heartbeat — everyone in the cloud's room rolls
   fortitude each tick — and `ON_ENTER` warns latecomers who wade in.
   The cloud does its own damage because `damage()` is proximity
   authority: the *bomb* can't hurt someone a room away, but a cloud
   standing next to them can. That's why the gas is objects at all.

5. **Dissipation is `expire()`** — the persistent timer. It's a
   timestamp *on the cloud*, swept by the world tick, so a lingering
   hazard dissipates even across a server restart. Used `wait()` here,
   a reboot would orphan the clouds forever. Fuse: `wait()`. Cloud:
   `expire()`. Short and expendable versus stateful and must-not-leak.

Authority note: `create_obj(..., location=r)` seeds objects only into
rooms the script's **owner** controls. One builder owns this whole wing,
so the gas spreads freely; on a live game an admin-owned bomb is the
general-purpose weapon (admins control everywhere), and a builder-owned
one gasses only the builder's own rooms — softcode's owner-authority
rule, working as intended.

*Engine nit (reported):* `exits()`'s reference line says "open exits" but
it returns closed ones too — hence the explicit `has_tag(e, 'closed')`
filter, which you'd want anyway to make the door rule visible.

## Build it

The resistance skill, as data:

```text
@teleport me = Maintenance Corridor
@create fortitude
@tag fortitude = skill_def
@set fortitude/stat = health
@set fortitude/penalty = 0
@reload
```

The cloud prototype — handlers under inert names. The tick sweeps the
cloud's room: fail fortitude at -1 and take 1d6; pass and cough through
it. The enter line warns anyone walking into a standing cloud:

```text
@create gas cloud prototype
@set gas cloud prototype/cloud_tick = [(pemit(o, 'The gas sears your lungs!'), damage(o, roll('1d6'))) if not skill_check(o, 'fortitude', -1) else pemit(o, 'Eyes streaming, you keep your sleeve pressed over your face.') for o in contents(loc(me)) if has_tag(o, 'player') or has_tag(o, 'npc')]
@set gas cloud prototype/cloud_enter = pemit(enactor, 'Stinging yellow gas fills this room!') if has_tag(enactor, 'player') or has_tag(enactor, 'npc') else None
```

(Keep the prototype in your pocket or a props closet — with no live
trigger names on it, it's inert wherever it sits.)

The bomb. `arm` refuses to fire in your hands (set it down first),
marks itself armed, hisses to the room, and lights the `wait()` fuse:

```text
@create gas bomb
@set gas bomb/fuse = 10
@set gas bomb/cmd_arm = $arm bomb: pemit(enactor, 'Set it down first -- arm it in your hands and you wear it.') if not (loc(me) and has_tag(loc(me), 'room')) else (pemit(enactor, 'It is already hissing.') if V('armed', 0) else (set_attr(me, 'armed', 1), remit(loc(me), f'{name(enactor)} twists the fuse cap. A thin hiss starts.'), wait(V('fuse', 10), 'trigger me/detonate')))
```

Detonation: resolve open-exit destinations, spawn a cloud here and in
each, copy the prototype handlers on, attach the heartbeat, set the
`expire()` lifetime, announce, and remove the spent casing:

```text
@set gas bomb/detonate = proto = get('gas cloud prototype'); dests = [get('#' + str(get_attr(e, 'destination', ''))) for e in exits(loc(me)) if not has_tag(e, 'closed')]; clouds = [c for c in [create_obj('a cloud of stinging gas', location=r) for r in [loc(me)] + [d for d in dests if d]] if c]; [set_attr(c, 'on_tick', get_attr(proto, 'cloud_tick')) for c in clouds]; [set_attr(c, 'on_enter', get_attr(proto, 'cloud_enter')) for c in clouds]; [attach_behavior(c, 'script_ticker', interval=2) for c in clouds]; [expire(c, 60) for c in clouds]; [remit(loc(c), 'A thick bank of stinging gas billows in!') for c in clouds]; destroy_obj(me)
drop gas bomb
```

## Try it

```text
get gas bomb
arm bomb            -> Set it down first -- arm it in your hands and you wear it.
drop gas bomb
arm bomb            -> (the room) ... twists the fuse cap. A thin hiss starts.
west                -> run!
```

Ten seconds later every room behind an *open* exit reads `A thick bank
of stinging gas billows in!`, and each tick after that, occupants roll
fortitude or take 1d6. Close a door first and the room beyond stays
clean — in the arc, shutting the vault door is the difference between
gassing the sentry and gassing yourself. Wade back in early:

```text
east                -> Stinging yellow gas fills this room!
```

A minute later the clouds expire and the air clears on its own.

## Going further

- **Gas masks** — start `cloud_tick`'s exposure with
  `has_tag(o, 'gas_immune')` and sell goggles that `grants_tags` it —
  the wearables system does the bookkeeping.
- **Dissipation stages** — give clouds an `ON_EXPIRE` that spawns a
  weaker `thin haze` cloud (expire renews by re-arming, so a cloud can
  step itself down).
- **Multi-hop spread** — carry a `potency` attribute on each cloud and
  have ground zero's cloud repeat the walk at `potency - 1`; the `_seen`
  set is just a list attribute.
- **Sticky bomb** — drop the `has_tag(loc(me), 'room')` guard and a
  carried, armed bomb becomes a courier problem. Decide on purpose.
