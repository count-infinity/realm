# 111. Grenades

> Checklist item 111 ([now]): *wait() fuses, room-loop damage(), rand scatter over exits()*

**What you'll build:** A frag grenade you arm in your hand (`pull pin`),
throw through any exit (`throw grenade <exit>`), and regret holding too
long. The blast sweeps whoever is in the room, and a failed Throwing
check scatters the grenade through the wrong doorway.

**Concepts:** [`wait()`](../reference/softcode.md#fn-wait) fuses with
`trigger me/<attr>` payloads, the [`exits()`](../reference/softcode.md#fn-exits)
graph walk from the [gas bomb](048_gas_bomb.md),
[`rand()`](../reference/softcode.md#fn-rand) scatter,
[`damage()`](../reference/softcode.md#fn-damage) proximity authority (and
how a held grenade gets around it), `skill_def` skills as data, and the
shared death path softcode damage feeds into.

## How it works

The finished grenade is a single object that answers three commands over
its own lifetime: `pull pin` lights an in-memory fuse, `throw grenade
<exit>` moves it into a neighbouring room, and the fuse then fires a
`boom` attribute that sweeps that room. This section explains where the
throwing verb comes from, how the throw resolves an exit into a room, and
why the blast has to check its own location before it can hurt anyone.

There is no native `throw` verb in the engine, so throwing is a
`$`-command on the grenade itself. Because `$`-commands are found in your
inventory as well as the room (unlike `^`-listens), a grenade in your
hand answers `pull pin` and `throw grenade ...` wherever you carry it.

1. **Arming inverts the gas bomb's rule.** The [gas bomb](048_gas_bomb.md)
   refused to arm in your hands, so you set it down first. A grenade is
   the opposite decision, made on purpose: `pull pin` requires it in hand
   (`loc(me) is enactor`), because that is what grenades are. The fuse is
   a [`wait()`](../reference/softcode.md#fn-wait)`(fuse, 'trigger
   me/boom')`, in-memory, exact, and acceptable to lose on a reboot, the
   same reasoning as the gas bomb.

2. **The throw is a graph edge.** [`exits(loc(enactor))`](../reference/softcode.md#fn-exits)
   lists the ways out (filtering `closed`, since you do not lob a grenade
   through a shut hatch), and the named exit's `destination` attribute
   resolves to the far room via [`get`](../reference/softcode.md#fn-get)`('#'
   + id)`. A passed Throwing check (a `skill_def` built from DX, like the
   [pickpocket skill](070_pickpocket_npc.md)) sends it where you aimed,
   while a failure scatters it through a random other open exit with
   [`rand()`](../reference/softcode.md#fn-rand) over the remaining
   doorways. [`teleport_obj`](../reference/softcode.md#fn-teleport_obj)`(me,
   d)` moves the grenade: it controls itself, so no further authority is
   needed.

3. **The blast is proximity authority.** [`damage()`](../reference/softcode.md#fn-damage)
   only reaches things in the executor's room, which is exactly why the
   `boom` script first checks where it is. In a room it sweeps
   [`contents()`](../reference/softcode.md#fn-contents) and hurts everyone
   who fails a Reflexes check. Still in someone's hand at zero, the
   grenade cannot sweep the room from inside a pocket (its location is the
   holder, not the room), so it drops itself to the holder's room
   (`teleport_obj(me, loc(holder))`) and re-triggers one tick later: it
   slips through your fingers, and then everyone standing there, holder
   included, eats the blast. Moves queue until the script ends, which is
   why the drop and the blast are two script runs chained by a `wait(0,
   ...)`.

4. **Deaths are real deaths.** Softcode [`damage()`](../reference/softcode.md#fn-damage)
   routes lethal results through the combat manager's single death path:
   NPCs die into lootable corpses and players fall unconscious in place,
   so a grenade kill is exactly as real as a sword kill. That one path is
   also where `combat:on_death` is announced, and it fires for every
   death whatever the cause, so [`ON_DEATH`](../reference/softcode.md#lifecycle-hooks)
   witnesses such as the [bounty board](114_bounty_board.md) do hear a
   grenade kill. The actor bound to the event is the executor of
   `damage()`, which is the grenade itself, so a witness that wants to
   credit a thrower reads the scene rather than the event's actor.

## Build it

Two rooms and the two skills, as data. A `skill_def` object named,
tagged, and given a `stat` becomes a real rollable skill once `@reload`
re-reads the table:

```text
@dig The Bunker = bunker, out
bunker
@dig The Trench = trench, bunker
@create reflexes
@tag reflexes = skill_def
@set reflexes/stat = dexterity
@set reflexes/penalty = 0
@create throwing
@tag throwing = skill_def
@set throwing/stat = dexterity
@set throwing/penalty = 0
@reload
```

Create the grenade and give it a six-second fuse:

```text
@create frag grenade
@set frag grenade/fuse = 6
```

Pin first. It refuses unless the grenade is in your hand, refuses a
second pull, and otherwise marks itself armed, pings the room, and lights
the fuse:

```text
@set frag grenade/cmd_pull = '''
$pull pin:
if loc(me) is not enactor:                 # $-commands answer from your inventory too
    pemit(enactor, 'Pick it up first -- you do not arm a grenade you are not holding.')
elif V('armed', 0):
    pemit(enactor, 'The pin is already out!')
else:
    set_attr(me, 'armed', 1)
    remit(loc(enactor), name(enactor) + ' pulls the pin. The spoon pings away.')
    wait(V('fuse', 6), 'trigger me/boom')  # in-memory fuse: a reboot defuses it
'''
```

The throw validates the exit by name, then hands off to `fly` with the
exit id. [`eval_attr`](../reference/softcode.md#fn-eval_attr) runs `fly`
as a subroutine of the grenade (the [security camera](054_security_camera.md)
idiom), so inside `fly` the grenade is still `me` and the thrower is still
`enactor`:

```text
@set frag grenade/cmd_throw = '''
$throw grenade *:
doors = [e for e in exits(loc(enactor)) if not has_tag(e, 'closed')]
aimed = [e for e in doors if name(e) == trim(arg0)]
if loc(me) is not enactor:
    pemit(enactor, 'You are not holding the grenade.')
elif not aimed:
    pemit(enactor, 'No open exit called ' + trim(arg0) + ' here.')
else:
    eval_attr(me, 'fly', aimed[0].id)      # arg0 in fly is this exit's id
'''
```

`fly` rolls the Throwing check. A pass sends the grenade through the exit
you named; a failure picks a random other open exit with `rand()`. Either
way it resolves that exit's `destination` to a room and teleports itself
there:

```text
@set frag grenade/fly = '''
e = get('#' + arg0)
good = skill_check(enactor, 'throwing')
others = [x for x in exits(loc(enactor)) if not has_tag(x, 'closed') and x is not e]
pick = e if good or not others else others[rand(0, len(others) - 1)]
d = get('#' + str(get_attr(pick, 'destination', '')))
if d:
    remit(loc(enactor), name(enactor) + ' hurls the grenade through the ' + name(pick) + ' exit' + ('!' if pick is e else ' -- no, wide! It caroms off the frame and skips the wrong way!'))
    teleport_obj(me, d)
    remit(d, 'A grenade bounces in and skitters across the floor!')
'''
```

Zero hour. `boom` handles the held case first: if the grenade is not in a
room (it is still in a hand), it drops to the holder's room and
re-triggers one tick later, otherwise it runs `blast`:

```text
@set frag grenade/boom = '''
spot = loc(me)
held = spot is not None and not has_tag(spot, 'room')
if held:                                   # at zero in a hand: drop to the room, then re-trigger
    remit(loc(spot), 'The live grenade slips through ' + name(spot) + "'s fingers!")
    teleport_obj(me, loc(spot))
    wait(0, 'trigger me/boom')
else:
    eval_attr(me, 'blast')
'''
```

`blast` is the sweep. `damage()` reaches only the executor's room, so it
walks [`contents()`](../reference/softcode.md#fn-contents) of its own
room, spares whoever passes Reflexes at -1, and hurts everyone else
before removing the spent casing:

```text
@set frag grenade/blast = '''
room = loc(me)
del_attr(me, 'armed')
if room:
    remit(room, 'WHUMP. The grenade goes off in a fist of smoke and shrapnel!')
    for o in contents(room):
        if has_tag(o, 'player') or has_tag(o, 'npc'):   # skip exits and items
            if skill_check(o, 'reflexes', -1):
                pemit(o, 'You dive clear of the blast!')
            else:
                pemit(o, 'Shrapnel tears into you!')
                damage(o, roll('2d6'))     # proximity authority: the grenade is in the room
    destroy_obj(me)
'''
drop frag grenade
```

## Try it

```text
> pull pin
Pick it up first -- you do not arm a grenade you are not holding.

> get frag grenade
> pull pin
(the room) ... pulls the pin. The spoon pings away.

> throw grenade trench
... hurls the grenade through the trench exit!
```

Six seconds later The Trench reads `WHUMP.`, and everyone there rolls
Reflexes at -1: pass and dive clear, fail and take 2d6. An NPC brought to
zero dies into a lootable corpse, while a player goes down where they
stand. Fumble the throw and the room narrates the carom as the grenade
skips through some other open doorway. And if you pull the pin and
freeze:

```text
The live grenade slips through Zeke's fingers!
WHUMP. The grenade goes off in a fist of smoke and shrapnel!
```

## Going further

- **Cook the grenade.** Store the `wait()` handle
  (`set_attr(me, 't', wait(...))`) and add a `$release spoon` command that
  `cancel_wait`s it, so the grenade is armed but safe until thrown. That
  is the [self-destruct](056_self_destruct.md) abort pattern.
- **Cover matters.** Let the blast spare anyone behind the
  [cover system's](109_cover_system.md) fixture: skip targets where
  `has_tag(o, 'prone')`, or grant +3 on the Reflexes roll if the room
  holds a `cover`-tagged object.
- **Smoke and flashbangs.** Swap the damage sweep for
  [`apply_effect`](../reference/softcode.md#fn-apply_effect)`(o,
  'modifier_effect', kind='dazzled', duration=4, check_mods={'all': -2})`,
  which is the same fuse with a different payload.
- **Frag the furniture.** Have `blast` also strip `cover` tags from
  fixtures in the room, automating the cover system's `$shred`.

## Engine gap

There is no native `throw` or projectile verb, so thrown objects are a
softcode pattern (this page). A native throw with range bands would let
grenades interact with the encounter engine's `withdraw` and `cover`
model directly.
