# 071. Guard response

> Checklist item 71 — [now] — *zone-master ON_ATTACK witnesses, responder scripts*

**What you'll build:** a town where crime has consequences. Throw a
punch anywhere in the `town` zone and the zone master hears it: a
bystander screams, Watchman Bren is dispatched to the scene, challenges
the offender, marks them an enemy of the watch, and wades in.
**Concepts:** zone masters as event witnesses (`ON_ATTACK`), summoning
with `teleport_obj()` + `force()`, disposition drops as a reputation
mechanic, cooldown attrs (one brawl, one dispatch), simple-script
bystander flavor.

## How it works

Every swing in combat propagates a `combat:on_attack` action, and
`ON_<EVENT>` triggers fire on everything that witnesses it: the room,
its contents — **and the masters of every zone the room belongs to**.
That last clause is the whole trick. The `zone:town` tags you laid down
in item 60 already form a surveillance network; a "Town Watch" master
object with one `ON_ATTACK` attribute turns them into law.

The dispatch script, in order:

1. **Filter.** `enactor` is the attacker. If they carry the
   `town_watch` tag, this is the law working — not a crime.
2. **Rate-limit.** A `last_alarm` timestamp attr and `now()` make the
   alarm fire once per brawl, not once per swing (the victim's
   desperate swings back would otherwise summon guards onto *them*).
3. **Respond.** `adjust_disposition()` — the watch now hates the
   offender (that's persistent reputation: `consider` shows it, prices
   and guard behaviors read it). `teleport_obj()` yanks Bren to the
   scene ("running" is a variation below). Two `force()` lines make him
   challenge and attack — forced commands run through the real
   dispatcher *after* the script settles, in queue order, so by the
   time `attack` executes, the teleport has landed him at the scene.

Authority holds it together: the master runs with its owner's power,
and the same builder owns Bren — so the master may move him, force
him, and rewrite his opinions. It could do none of this to a player.

A second, purely local witness — Nettie — shows the layering: any
object in the room with an `ON_ATTACK` attr reacts too. Hers is a
one-line simple script scream; flavor and mechanics ride the same
event.

## Build it

A post for the watch, one room from Market Street (from the Square of
item 60):

```
@dig Guard Post = post, square
post
@zone here = town
@create Watchman Bren
@tag Watchman Bren = npc
@tag Watchman Bren = town_watch
@set Watchman Bren/hp = 14
@set Watchman Bren/max_hp = 14
@set Watchman Bren/skill_melee = 13
drop Watchman Bren
```

**The master.** `@zone/master` crowns it: the object gets the
`zone_master` tag plus `zone:town`, and from then on events in every
town room reach its `ON_<EVENT>` attributes:

```
@create Town Watch
@zone/master Town Watch = town
@set Town Watch/on_attack = crime = not has_tag(enactor, 'town_watch'); fresh = now() - V('last_alarm', 0) > 60; ((set_attr(me, 'last_alarm', now()), adjust_disposition('Watchman Bren', enactor, -5), teleport_obj('Watchman Bren', here), force('Watchman Bren', 'say Town watch! Drop it, NOW!'), force('Watchman Bren', 'attack ' + name(enactor))) if crime and fresh else None)
drop Town Watch
```

Inside the trigger, `here` is the room where the attack happened — not
where the master sits — so the same one line polices every street you
ever add to the zone.

**The scene.** A victim and a witness on Market Street. The dock
worker gets `combat_default = defend`: he cowers instead of swinging
back, which keeps the story honest (and is why the cooldown protects
victims who *do* fight back):

```
square
market
@create dock worker
@tag dock worker = npc
@set dock worker/hp = 10
@set dock worker/max_hp = 10
@set dock worker/skill_melee = 10
@set dock worker/combat_default = defend
drop dock worker
@create Nettie
@tag Nettie = npc
drop Nettie
@set Nettie/on_attack = say Guards! GUARDS! Blood on Market Street!
```

## Try it

Become the crime (skip the stat lines if your character already has a
sheet):

```
@set me/hp = 12
@set me/max_hp = 12
@set me/skill_melee = 12
attack dock worker
```

On the first beat: Nettie screams, and Bren materializes from the
post — "Town watch! Drop it, NOW!" — and joins the fight against you.
`consider Watchman Bren` afterwards: he remembers. Keep brawling and
no *second* alarm sounds for a minute (`last_alarm`); flee to the
Flagon and swing there and the same master catches you again — the
whole zone is wired.

## Going further

- **Make him run, not blink:** replace `teleport_obj` with an alert
  attr on Bren (`set_attr('Watchman Bren', 'scene', here.id)`) and give
  him a `script_ticker` that walks one exit toward the scene per tick,
  standing down when the trail is cold.
- **More crimes than violence:** the same master pattern hooks
  `ON_GET` (theft of tagged shop stock), `ON_UNLOCK`, or a custom
  `act()`-fired event — one `ON_<EVENT>` attr per law.
- **Escalation:** give Bren `ON_HITPRCNT` softcode that `force()`s a
  second watchman off his cot when Bren drops below half — losing
  fights summon reinforcements.
- **Jail, not death:** in the master, follow the challenge with a
  `wait 30 ...` that `teleport_obj`s a still-`in_combat` offender to a
  cell — the town would rather lock you up than cut you down.
- **Bounties from disposition:** the `-5` already gates the built-in
  guard/aggressive behaviors; pair with item 64 so Mira refuses
  service to anyone the watch despises (`disposition('Watchman Bren', enactor)`).
