# 071. Guard response

> Checklist item 71 ([now]): *zone-master ON_ATTACK witnesses, responder scripts*

**What you'll build:** a town where crime has consequences. Throw a punch
anywhere in the `town` zone and the zone master hears it: a bystander screams,
Watchman Bren is summoned to the scene, challenges the offender, marks them an
enemy of the watch, and wades in.
**Concepts:** zone masters as event witnesses
([`ON_ATTACK`](../reference/softcode.md#lifecycle-hooks)), summoning with
[`teleport_obj()`](../reference/softcode.md#fn-teleport_obj) and
[`force()`](../reference/softcode.md#fn-force), a disposition drop as a
reputation mechanic, a cooldown attribute so one brawl means one dispatch, and a
bystander whose simple-script scream rides the same event.

## How it works

The finished shape is one law object watching a whole district. Any attack
anywhere in the zone reaches a "Town Watch" master, and its single
[`ON_ATTACK`](../reference/softcode.md#lifecycle-hooks) attribute decides whether
a crime just happened, and if so summons Bren, sours his opinion of the
offender, and sends him into the fight. A separate bystander reacts to the same
attack with a scream, which shows that flavor and enforcement layer on one
event. This section answers how one object can police the whole zone, why the
alarm fires once per brawl rather than once per swing, how the master reaches
out and acts through Bren, and why the screaming bystander needs no guard.

### How one object polices a whole zone

Every swing in combat propagates a `combat:on_attack`
[action](../architecture/events.md), and `ON_<EVENT>` triggers fire on
everything that witnesses it: the room, its contents, and the masters of every
zone the room belongs to. That last clause is the whole trick. The `zone:town`
tags you laid down building [the wandering scamp](060_wandering_npc.md) and [the
market stall](068_npc_schedule.md) already form a surveillance network, so a
"Town Watch" master carrying one `ON_ATTACK` attribute turns them into law. The
`enactor` bound inside that attribute is the attacker, which is all the master
needs to know who to blame.

### Why the alarm fires once per brawl, not once per swing

The first two lines of the script are a filter and a rate limit. If the attacker
carries the `town_watch` tag, this is the law working and not a crime, so
[`has_tag(enactor, 'town_watch')`](../reference/softcode.md#fn-has_tag) rules out
Bren's own swings. Then a `last_alarm` timestamp attribute and
[`now()`](../reference/softcode.md#fn-now) make the alarm sound once per brawl:
without it, every trade of blows would re-summon the watch, and because the
victim's desperate swings back are also `combat:on_attack` actions, an
unthrottled master would summon guards onto the victim. The cooldown reads
`last_alarm` off the master itself with
[`V()`](../reference/softcode.md#fn-v), the shorthand for an attribute on the
executor.

### How the master reaches out and acts through Bren

Once the script decides a fresh crime occurred it does three things in order.
[`adjust_disposition()`](../reference/softcode.md#fn-adjust_disposition) drops
the watch's opinion of the offender to hostile, which is persistent reputation:
`consider` shows it, and disposition-aware behaviors read it, the same attitude
scale [the guarded exit](031_guarded_exit.md) and [the aggressive
mob](062_aggressive_mob.md) consult.
[`teleport_obj()`](../reference/softcode.md#fn-teleport_obj) yanks Bren to the
scene (making him walk there instead is a variation below). Two
[`force()`](../reference/softcode.md#fn-force) lines then make him challenge and
attack. Forced commands run through the real dispatcher after the script
settles, in queue order, so by the time `attack` executes the teleport has
already landed Bren at the scene.

The binding that makes this work at zone scale is `here`. Inside a witnessed
hook `here` is the room where the attack happened, not where the master sits, so
the same one attribute polices every street you ever add to the zone.
[`name(enactor)`](../reference/softcode.md#fn-name) supplies the offender's name
for the `attack` line. Authority holds it together: the master runs with its
owner's power and the same builder owns Bren, so the master may move him, force
him, and rewrite his opinions. It could do none of this to a player.

### Why the screaming bystander needs no guard

Nettie is a second, purely local witness, and her `ON_ATTACK` is a one-line
scream. An `ON_<EVENT>` hook that reacts on behalf of a specific subject must
check [`target is me`](../reference/softcode.md#guard-on-target) first, because
the hook fires on every object in the room. Nettie needs no such guard: she is a
general witness reacting to any crime she sees, not the thing that was attacked,
so screaming for every attack is exactly right. The Town Watch master is the
other unguarded case, a global witness watching everyone; it takes no
`target is me` either, and instead filters on `enactor` and rate-limits on
`last_alarm`.

## Build it

Stand up a post for the watch one room off the Square (dug building [the
wandering scamp](060_wandering_npc.md)). The `@zone here = town` line folds the
post into the district, and the `town_watch` tag on Bren is what keeps his own
swings from re-triggering the alarm:

```text
@dig Guard Post = post, square
post
@zone here = town
@create Watchman Bren
@tag Watchman Bren = npc
@tag Watchman Bren = town_watch
drop Watchman Bren
```

Give Bren a fighting sheet so he can back up the challenge:

```text
@set Watchman Bren/hp = 14
@set Watchman Bren/max_hp = 14
@set Watchman Bren/skill_melee = 13
```

Create the master and crown it. `@zone/master` gives the object the
`zone_master` tag plus `zone:town`, and from then on events in every town room
reach its `ON_<EVENT>` attributes:

```text
@create Town Watch
@zone/master Town Watch = town
drop Town Watch
```

Now its one law. The script filters out the watch's own violence, throttles to
one alarm per brawl, then summons and directs Bren. It is control flow across
several statements, so it is a `'''` heredoc block rather than a one-liner (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)):

```text
@set Town Watch/on_attack = '''
crime = not has_tag(enactor, 'town_watch')    # the watch doing its job is not a crime
fresh = now() - V('last_alarm', 0) > 60       # one alarm per brawl, not per swing
if crime and fresh:
    set_attr(me, 'last_alarm', now())
    adjust_disposition('Watchman Bren', enactor, -5)
    teleport_obj('Watchman Bren', here)        # here is the room the attack happened in
    force('Watchman Bren', 'say Town watch! Drop it, NOW!')
    force('Watchman Bren', 'attack ' + name(enactor))
'''
```

Walk to Market Street for the scene of the crime, and put a victim there. The
dock worker gets `combat_default = defend` so he cowers instead of swinging
back, which keeps the story honest and is why the cooldown also protects victims
who do fight back:

```text
square
market
@create dock worker
@tag dock worker = npc
drop dock worker
@set dock worker/hp = 10
@set dock worker/max_hp = 10
@set dock worker/skill_melee = 10
@set dock worker/combat_default = defend
```

Add a witness. Nettie's scream is a single statement, so it stays on one line,
and she takes no `target is me` guard because she reacts to any attack she sees,
not to being attacked herself:

```text
@create Nettie
@tag Nettie = npc
drop Nettie
@set Nettie/on_attack = say Guards! GUARDS! Blood on Market Street!
```

## Try it

Give yourself a sheet and become the crime (skip the stat lines if your
character already has one):

```text
@set me/hp = 12
@set me/max_hp = 12
@set me/skill_melee = 12
attack dock worker
  -> You square off against dock worker.
```

On the first exchange of blows, Nettie screams and Bren arrives from the post,
challenges you, and joins the fight:

```text
(first round resolves)
  -> Nettie says, "Guards! GUARDS! Blood on Market Street!"
     Watchman Bren says, "Town watch! Drop it, NOW!"
```

Afterward the watch remembers you. `consider Watchman Bren` reports him hostile,
because the master set his disposition toward you to -5. Keep brawling and no
second alarm sounds for a minute, held off by `last_alarm`. Flee to [the Rusty
Flagon](064_bartender.md) and swing there and the same master catches you again,
since the whole zone is wired:

```text
consider Watchman Bren
  -> Watchman Bren regards you with open hostility.
```

## Going further

- **Make him run, not blink:** replace `teleport_obj` with an alert attribute on
  Bren (`set_attr('Watchman Bren', 'scene', here.id)`) and give him a
  `script_ticker` that walks one exit toward the scene per tick, standing down
  when the trail is cold.
- **More crimes than violence:** the same master pattern hooks
  [`ON_GET`](../reference/softcode.md#lifecycle-hooks) (theft of tagged shop
  stock), `ON_UNLOCK`, or a custom event, one `ON_<EVENT>` attribute per law.
- **Escalation:** give Bren `ON_HITPRCNT` softcode that `force()`s a second
  watchman off his cot when Bren drops below half, so losing fights summon
  reinforcements.
- **Jail, not death:** in the master, follow the challenge with a
  [`start_combat`](../reference/softcode.md#fn-start_combat) alternative and a
  timed `teleport_obj` that moves a still-fighting offender to a cell, since the
  town would rather lock you up than cut you down.
- **Bounties from disposition:** the -5 already gates the built-in
  guard and aggressive behaviors; pair with [the bartender](064_bartender.md) so
  a shopkeeper refuses service to anyone the watch despises, reading
  [`disposition('Watchman Bren', enactor)`](../reference/softcode.md#fn-disposition).
```
