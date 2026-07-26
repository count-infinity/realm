# 048. Gas Bomb

> Checklist item 48 ([now]): *wait() fuses, exits() graph spreading, resisted effects, expire()*

**What you'll build:** A canister you `arm` with a fuse. It detonates,
fills its room with gas, spreads through every open exit, and forces
HT-based fortitude rolls on everyone caught in a cloud, then the clouds
dissipate on their own. Part of the [Heist arc](arc_heist.md); it lives
in the Maintenance Corridor.

**Concepts:** [`wait()`](../reference/softcode.md#fn-wait) versus
[`expire()`](../reference/softcode.md#fn-expire) (and when each is
right), walking the room graph via [`exits()`](../reference/softcode.md#fn-exits),
skills as data (`skill_def` plus `@reload`), prototype-attribute
copying, [`create_obj()`](../reference/softcode.md#fn-create_obj)
authority, the `script_ticker` behavior for ongoing exposure, and a
cloud `ON_ENTER` for latecomers.

## How it works

Five pieces, each a distinct engine mechanism.

1. **The resistance roll is data.** GURPS says gas is resisted with HT.
   REALM's skill table is extendable from inside the game: a `skill_def`
   object named `fortitude` with `stat = health, penalty = 0` plus
   `@reload` makes [`skill_check`](../reference/softcode.md#fn-skill_check)`(o, 'fortitude', -1)`
   roll against the target's health attribute, with no engine change.
   It is the same skill-as-data trick as the pickpocket skill in
   [tutorial 70](070_pickpocket_npc.md), and the identical fortitude
   `skill_def` the [poison dart trap](052_poison_dart_trap.md) builds.

2. **The fuse is a [`wait()`](../reference/softcode.md#fn-wait).** It is
   in-memory and fires on its own exact timer, and pending waits die on
   a reboot. That is deliberate: a ten-second fuse that a restart
   defuses is acceptable, while a fuse that *survived* into the rebooted
   world half-fired would not be. The scheduled command is
   `trigger me/detonate`, so the bang itself is an ordinary attribute
   you can `@tr` to test (`@tr` runs an attribute body directly; it does
   not fire `$`-command triggers).

3. **Spread is a graph walk.** Rooms are nodes and exits are edges.
   [`exits(loc(me))`](../reference/softcode.md#fn-exits) lists the exits
   here; each one's `destination` attribute holds a room id that
   [`get`](../reference/softcode.md#fn-get)`('#' + id)` resolves. We skip
   `closed` exits, because closed doors hold gas back, and note the flip
   side: the *hidden* grate is open, so gas finds the secret crawlway.

4. **Clouds are objects, and their code is copied, not typed.** Writing
   scripts inside a script means quoting hell, so the cloud's two
   handlers live on a **prototype** under inert names (`cloud_tick` and
   `cloud_enter`, which are not trigger names, so the prototype itself
   never fires). Detonation copies them onto each fresh cloud under the
   live names `on_tick` and `on_enter`. Exposure is the cloud's own
   `script_ticker` heartbeat: the ticker runs the cloud's `on_tick` on
   the cloud itself (not room-wide), and that script sweeps everyone in
   the cloud's room to roll fortitude each tick. Its `on_enter` warns
   latecomers who wade in. The cloud does its own
   [`damage()`](../reference/softcode.md#fn-damage) because `damage()` is
   proximity authority: the *bomb* cannot hurt someone a room away, but a
   cloud standing next to them can, the same license the
   [landmine](049_landmine.md) uses. That is why the gas is objects at
   all.

5. **Dissipation is [`expire()`](../reference/softcode.md#fn-expire).**
   It is the persistent timer: a timestamp *on the cloud*, swept by the
   world tick, so a lingering hazard dissipates even across a server
   restart. Had we used `wait()` here, a reboot would orphan the clouds
   forever. So the fuse is `wait()` and the cloud is `expire()`: short
   and expendable versus stateful and must-not-leak.

### Why the cloud, and not the bomb, warns and damages

Both `on_tick` and `on_enter` need to reach whoever is in the cloud's
room. `on_tick` is not a room-wide reactive hook; the `script_ticker`
behavior runs it on the cloud alone, and the script loops
[`contents(loc(me))`](../reference/softcode.md#fn-contents) to apply the
AoE, filtering to players and NPCs so it never damages the exits or the
other cloud. `on_enter` *is* a reactive `ON_ENTER` hook, and it fires on
every object in the room a mover arrives in (see the
[landmine](049_landmine.md) for the same pattern). It reacts to the
arriver, `enactor`, rather than to a targeted object, so it takes no
`if target is me:` guard; the movement's target is never the cloud, so
that guard would only ever be false. A second cloud in a neighbouring
room stays silent, because `ON_ENTER` only reaches witnesses in the room
actually entered.

Authority note: [`create_obj`](../reference/softcode.md#fn-create_obj)`(..., location=r)`
seeds objects only into rooms the script's **owner** controls. One
builder owns this whole wing, so the gas spreads freely. On a live game
an admin-owned bomb is the general-purpose weapon, because admins
control everywhere, while a builder-owned one gasses only the builder's
own rooms. That is softcode's owner-authority rule working as intended.

## Build it

Set the stage and teach the skill table a new row. A `skill_def` object
named `fortitude`, tagged and given a `stat`, becomes a real rollable
skill once `@reload` re-reads the table:

```text
@teleport me = Maintenance Corridor
@create fortitude
@tag fortitude = skill_def
@set fortitude/stat = health
@set fortitude/penalty = 0
@reload
```

Create the cloud prototype, which is where the two handlers live under
inert names. Keep it in your pocket or a props closet; with no live
trigger names on it, it never fires wherever it sits:

```text
@create gas cloud prototype
```

The tick handler sweeps the cloud's room. Anyone who fails fortitude at
-1 takes 1d6 and hears the gas; anyone who passes coughs through it. It
runs on the cloud's own ticker, so it is not a room-wide reactive hook
and needs no target guard, but it does filter to living things:

```text
@set gas cloud prototype/cloud_tick = '''
for o in contents(loc(me)):
    if has_tag(o, 'player') or has_tag(o, 'npc'):  # skip exits, items, the sibling cloud
        if skill_check(o, 'fortitude', -1):
            pemit(o, 'Eyes streaming, you keep your sleeve pressed over your face.')
        else:
            pemit(o, 'The gas sears your lungs!')
            damage(o, roll('1d6'))  # proximity authority: the cloud is in the room
'''
```

The enter handler warns anyone who walks into a standing cloud. It is a
single announcement, so it stays a one-line conditional:

```text
@set gas cloud prototype/cloud_enter = pemit(enactor, 'Stinging yellow gas fills this room!') if has_tag(enactor, 'player') or has_tag(enactor, 'npc') else None
```

Create the bomb, set it on the floor, and give it a ten-second fuse.
Setting it down matters: `arm` refuses to fire while the bomb is held,
so the thrower does not gas themselves:

```text
@create gas bomb
drop gas bomb
@set gas bomb/fuse = 10
```

The `arm` command refuses in your hands, refuses if already hissing,
and otherwise marks itself armed, hisses to the room, and lights the
`wait()` fuse:

```text
@set gas bomb/cmd_arm = '''
$arm bomb:
if not (loc(me) and has_tag(loc(me), 'room')):
    pemit(enactor, 'Set it down first -- arm it in your hands and you wear it.')
elif V('armed', 0):
    pemit(enactor, 'It is already hissing.')
else:
    set_attr(me, 'armed', 1)
    remit(loc(me), f'{name(enactor)} twists the fuse cap. A thin hiss starts.')
    wait(V('fuse', 10), 'trigger me/detonate')  # in-memory fuse; dies on reboot
'''
```

Detonation resolves the open-exit destinations, spawns a cloud here and
in each, copies the prototype handlers onto every cloud, attaches the
heartbeat, sets the `expire()` lifetime, announces, and removes the
spent casing:

```text
@set gas bomb/detonate = '''
proto = get('gas cloud prototype')
dests = [get('#' + str(get_attr(e, 'destination', ''))) for e in exits(loc(me)) if not has_tag(e, 'closed')]
rooms = [loc(me)] + [d for d in dests if d]
for r in rooms:
    c = create_obj('a cloud of stinging gas', location=r)
    if c:  # create_obj returns None for a room the owner does not control
        set_attr(c, 'on_tick', get_attr(proto, 'cloud_tick'))
        set_attr(c, 'on_enter', get_attr(proto, 'cloud_enter'))
        attach_behavior(c, 'script_ticker', interval=2)
        expire(c, 60)  # persistent timer: clears even across a reboot
        remit(loc(c), 'A thick bank of stinging gas billows in!')
destroy_obj(me)
'''
```

## Try it

```text
> get gas bomb
> arm bomb
Set it down first -- arm it in your hands and you wear it.

> drop gas bomb
> arm bomb
(the room) ... twists the fuse cap. A thin hiss starts.

> west
run!
```

Ten seconds later every room behind an *open* exit reads `A thick bank
of stinging gas billows in!`, and each tick after that, occupants roll
fortitude or take 1d6. Close a door first and the room beyond stays
clean; in the arc, shutting the vault door is the difference between
gassing the sentry and gassing yourself. Wade back in early and the
cloud's `ON_ENTER` catches you:

```text
> east
Stinging yellow gas fills this room!
```

A minute later the clouds expire and the air clears on its own.

## Going further

- **Gas masks.** Start `cloud_tick`'s exposure with a
  `has_tag(o, 'gas_immune')` skip and sell goggles that `grants_tags` it,
  and the wearables system does the bookkeeping.
- **Dissipation stages.** Give clouds an `ON_EXPIRE` that spawns a
  weaker `thin haze` cloud (expire renews by re-arming, so a cloud can
  step itself down).
- **Multi-hop spread.** Carry a `potency` attribute on each cloud and
  have ground zero's cloud repeat the walk at `potency - 1`; the `_seen`
  set is just a list attribute.
- **Sticky bomb.** Drop the `has_tag(loc(me), 'room')` guard and a
  carried, armed bomb becomes a courier problem. Decide on purpose.

## Engine gaps

- [`exits()`](../reference/softcode.md#fn-exits)'s reference line reads
  "open exits", but it returns closed ones too, which is why the spread
  filters `has_tag(e, 'closed')` explicitly. The filter is what makes
  the closed-door rule visible anyway, so the tutorial wants it
  regardless.
