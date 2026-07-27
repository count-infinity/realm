# 115. Arena with spectators

> Checklist item 115 ([now]): *recorder relays: ON_ATTACK/ON_DAMAGE → remit to stands*

**What you'll build:** a fight pit with a stands room next door, and a
ringside bell that calls the action, so every swing, every wound, and every
taunt in the pit is relayed blow by blow to the spectators.

**Concepts:** the bug and tap pattern from the
[security camera](054_security_camera.md) turned sports commentary, namely
`ON_ATTACK`, `ON_DAMAGE`, and `ON_DEATH` witnesses plus a `^*` listen tap,
reading the in-flight action from a hook (`target`, `adata('damage')`),
cross-room delivery with [`remit()`](../reference/softcode.md#fn-remit), and
open-read HP tallies.

## How it works

Two rooms, one gadget. A brass bell stands in the fight pit and does nothing
but call the fight: every swing, wound, taunt, and finish that happens in the
pit is relayed next door to the stands, where spectators read the action blow
by blow while never seeing a line of the engine's own combat prose. This
section answers four questions: how a bystander object hears a fight it is not
part of, what a witness can read about each blow, how one line crosses into the
other room, and why the scoreboard reads the way it does.

### How the bell hears a fight it is not fighting

An object standing in the pit witnesses every combat action that propagates
there. Each swing propagates a `combat:on_attack` action, each wound a
`combat:on_damage`, and a defeat a `combat:on_death`, and the engine fires the
matching [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) attribute
(`on_attack`, `on_damage`, `on_death`) on every object in the room except the
two the action names, the attacker and the defender. So a bystander bell three
feet away catches all of them, with the acting fighter bound as `enactor` and
the fighter being swung at, wounded, or put down bound as `target` (see the
[propagation model](../architecture/events.md)).

Because the bell is a deliberate witness of the whole room rather than a
participant, its hooks take no [`if target is me`](../reference/softcode.md#guard-on-target)
guard: the bell is never the target, and it wants every blow, the same way the
[security camera](054_security_camera.md) wants every line. A second bell in
the same pit would relay each event too, once apiece, so one bell is enough.
Speech is caught on a separate channel, the `^*` listen trigger from the
[voice recorder](007_voice_recorder.md) and the camera.

### What a witness can read about each blow

A witnessing hook gets the same read-only
[event data](../reference/softcode.md#event-data-namespace) an `on_check` ward
gets: `target`, `atype`, `has_atag()`, and `adata(key)` for the payload. The
payload differs by event, so a `combat:on_attack` carries `adata('weapon')`
while a `combat:on_damage` carries `adata('damage')`, the points of the blow.
That is enough for the bell to name who hit whom and quote the number, the way
a commentator with a good seat calls it.

Combat's own narration ("You attack...", the round summaries) is message
delivery, not overhearable speech, and only say-class and emit-class actions
feed a `^` listen. So the bell does not parrot the engine's prose; it reports
the event in its own voice, which is what makes the stands hear a broadcast
rather than a log tail.

### How one line reaches the stands

The bell hands every call to one `relay` attribute, and `relay` delivers with
[`remit()`](../reference/softcode.md#fn-remit), which emits to everyone in a
named room wherever that room stands, so no shared room is required. `relay`
resolves the stands room fresh on every call with
[`get()`](../reference/softcode.md#fn-get) from the bell's `stands` attribute,
which is late binding: re-point `stands` and the next call goes to the new
room. Every hook is a one-line caller of `relay` through
[`eval_attr()`](../reference/softcode.md#fn-eval_attr), so fixing the relay
once changes all the feeds.

`get()` searches the caller's own room first, which is why the doorway into the
stands is named `seats` and not `stands`. An exit named `stands` answers
`get('The Stands')` with the exit rather than the room, so the relay would
deliver into a doorway instead of the seats. Naming the doorway and the
destination differently keeps the lookup unambiguous.

### Why the scoreboard reads the score going into the blow

Softcode reads are open, so any object's `hp` is readable, and a `tally`
subroutine sweeps the pit for `in_combat`-tagged fighters with
[`contents()`](../reference/softcode.md#fn-contents) of
[`loc(me)`](../reference/softcode.md#fn-loc) and posts the scoreboard beside
each call. One timing point matters: the combat engine propagates the damage
event before it subtracts the wound from HP, so during `on_damage` the tally
shows the score before this blow while `adata('damage')` is the blow itself.
Read together they are honest, since "Bruce 6/20" beside "3 on Bruce" means
Bruce is about to be on 3.

### Ringside versus the stands

The fighters see the engine's native narration and do not get the relay,
because `remit` targets the stands room only. The spectators get only the
relay, because native combat messages never leave the pit. Two rooms, two
accounts of one fight.

## Build it

Dig the pit from your workroom and step into it, then dig the stands from the
pit. That last dig leaves you standing in the pit, which is where the bell
belongs:

```text
@dig The Fight Pit = pit, out
pit
@dig The Stands = seats, pit
```

The `seats` exit is named so it does not collide with the room name when the
bell resolves `get('The Stands')`, since `get()` searches the local room first
and an exit named `stands` would shadow the room.

Now the bell, and its `stands` attribute naming the room the relay resolves:

```text
@create ringside bell
drop ringside bell
@desc ringside bell = A brass bell on a rope, sized to be heard over a crowd. It rings itself when blood is up.
@set ringside bell/stands = The Stands
```

The `relay` attribute is the single delivery point every hook calls. It
resolves the stands room fresh, then emits the line there with
[`remit()`](../reference/softcode.md#fn-remit). Written as a block so the
lookup and the guard read plainly:

```text
@set ringside bell/relay = '''
# resolve the stands room fresh each call, then deliver the line there
s = get(V('stands', ''))
if s:
    remit(s, '[pit] ' + str(arg0))
'''
```

The `tally` subroutine is the scoreboard. It reads every fighter's HP straight
off the object, which open reads allow, and lists the `in_combat` ones. It is a
single statement, so it stays on one line:

```text
@set ringside bell/tally = result = ' -- '.join([f'{name(o)} {get_attr(o, "hp", 0)}/{get_attr(o, "max_hp", 0)}' for o in contents(loc(me)) if has_tag(o, 'in_combat')])
```

The swing and the wound are one-line calls into `relay`. Each reads its own
event: [`name(enactor)`](../reference/softcode.md#fn-name) and `name(target)`
name the fighters, and `adata('damage', 0)` quotes the points of the wound:

```text
@set ringside bell/on_attack = eval_attr(me, 'relay', name(enactor) + ' wades in on ' + name(target) + '! ' + eval_attr(me, 'tally'))
@set ringside bell/on_damage = eval_attr(me, 'relay', name(enactor) + ' draws blood -- ' + str(adata('damage', 0)) + ' on ' + name(target) + '! ' + eval_attr(me, 'tally'))
```

The finish needs real branching, so it is a block. A swing names its killer
through `enactor`, but a death with no killer (a poison tick calls the shared
death path with none) arrives with `enactor` as `None`, so the block checks for
one before it crowns anybody:

```text
@set ringside bell/on_death = '''
# a poison tick reaches here with no killer, so enactor can be None
if enactor:
    call = name(enactor) + ' puts ' + name(target) + ' down and takes the pit!'
else:
    call = name(target) + ' is down -- and no one is claiming it!'
eval_attr(me, 'relay', 'THE CROWD ROARS -- ' + call)
'''
```

That last case is a real limit, not a courtesy: a `damage_over_time` tick reaches
the death path with no killer at all, so `enactor` and `adata('killer')` are both
`None`. Poison a fighter in the pit and the honest call is that nobody is
claiming it. The [bounty board](114_bounty_board.md) meets the same gap, where
it costs real money.

Finally the taunt tap, a `^*` listen that fires on any speech in the pit.
[`escape()`](../reference/softcode.md#fn-escape) wraps the spoken text because a
fighter writes it, so the bell treats it as words rather than markup. It is a
single-expression trigger, so it stays on one line:

```text
@set ringside bell/listen_taunt = ^*: eval_attr(me, 'relay', name(enactor) + ' bellows: ' + escape(arg0)) if enactor else None
```

## Try it

Seat a spectator in The Stands, start a fight in the pit with `attack`, and let
the beats run. The stands feed reads (HP numbers depend on the fighters' sheets;
these follow a 20-HP defender taking flat 3-point hits):

```text
[pit] Ace wades in on Bruce! Ace 30/30 -- Bruce 6/20
[pit] Ace draws blood -- 3 on Bruce! Ace 30/30 -- Bruce 6/20
```

The tally beside the wound shows 6, the score going into the blow, while
`draws blood -- 3` is the blow itself, so Bruce lands on 3. A taunt from the pit
comes through the listen tap:

```text
(in the pit) say is that ALL   -> [pit] Bruce bellows: is that ALL
```

Run the beat that drops him and the crowd gets the finish:

```text
[pit] Ace wades in on Bruce! Ace 30/30 -- Bruce 3/20
[pit] THE CROWD ROARS -- Ace puts Bruce down and takes the pit!
```

Meanwhile the fighters never see a `[pit]` line, and the stands never see the
pit's native combat narration: two rooms, two scripts of the same fight. A
defeated player is left unconscious on the sand by the native defeat rule, so
send a medic down with `firstaid` before the next bout.

## Going further

- **Betting windows:** bolt the [dueling stone](113_dueling.md) into the stands,
  so spectators stake on a name before the first `on_attack` relay and the
  bell's `on_death` settles the book.
- **A challenge queue:** a `$signup` list on the bell whose `on_death` announces
  who fights next and [`force()`](../reference/softcode.md#fn-force)s the pit
  gate open (the bell and gate share an owner).
- **Crowd noise back into the pit:** a second tap in the stands relaying
  spectator cheers into the pit, two bugs pointed at each other. Tag each relay
  line and filter it out on the far side so the two feeds do not echo forever;
  the engine's script depth guard will cut a runaway loop, but the tags keep it
  from starting.
- **Season records:** the bell's `on_death` appends `[winner, now()]` to a
  capped `champions` list, and a `$records` command reads it back, which is the
  [combat replay log](120_combat_replay.md) aggregated across matches.
