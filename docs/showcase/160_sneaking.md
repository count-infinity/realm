# 160. Sneaking

> Checklist item 160 ([now]): *hide command, stealth contests, concealment state*

**What you'll build:** almost nothing, and that is the lesson. REALM's
stealth stack (`hide`, quiet movement, spotting contests, `search`, and
loud-action exposure) is engine-native, so this tutorial composes it into
the heist's endgame and adds the two pieces softcode owns: a `watchful`
sentry whose alertness ratchets up, and a creaky floorboard that does the
ratcheting. It is part of the [Heist arc](arc_heist.md) and builds in the
Nexagen Vault.

**Concepts:** the `hidden` tag and its life cycle, the `hide` and `search`
contests, the `watchful` behavior with its `alert_level`, `@behavior` with
parameters, a `^listen` reacting to an object's emit, and
[`skill_check`](../reference/softcode.md#fn-skill_check) fired from a
movement witness.

## How it works

The finished scene is a guarded room you try to slip into unseen. Almost
every rule of that scene is already in the engine: hiding, quiet movement,
the guard's spotting roll, searching, and the way talking blows your cover.
The one thing the engine has no opinion about is a guard who grows more
suspicious over time, and that is exactly what the two softcode objects add.
This section walks the engine parts first, then the escalation you layer on
top.

### What the engine already does for stealth

These behaviors are proven by the engine's own tests, `tests/test_infiltration.py`
and `tests/test_perception.py`:

- **`hide`** rolls Stealth and sets the `hidden` tag; standing in an unlit
  room adds +3. A hidden character drops out of room displays, is passed
  over as a target, and reads as "Someone" in any message they cause, so
  stealth conceals *who* acted, never *that* something happened.
- **Movement is quiet.** Walking does not break stealth, because sneaking
  from room to room is the whole point. Bystanders see the arrival line
  `Someone arrives.`: the door plainly moved, but not who moved it.
- **A `watchful` NPC contests arrivals.** When a hidden character enters
  the room, the watcher runs a Perception-versus-Stealth
  [`contest`](../reference/softcode.md#fn-contest) with its own `alert_level`
  added to its side of the roll. A win breaks the sneak, speaks the
  `spot_msg`, and raises `alert_level` by one. A visible arrival instead
  gets the `challenge` line.
- **`search`** contests hiders directly (Observation versus Stealth), and a
  tie goes to the hider, so the status quo holds until the searcher clearly
  wins.
- **Loud actions** break stealth on their own: speaking, shouting, grabbing
  an object, and the like are all watched by the engine's stealth observer,
  which reveals the actor the instant they act.

### What softcode adds: a guard who learns

The extra piece is escalation. The floorboard is a witness object: its
[`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) hook rolls the
arriving sneak's Stealth at a -3 penalty. On a failure the board itself, not
the sneak, emits a creak into the room. An emit is real, overhearable output
(see the [script commands](../reference/softcode.md#script-commands-simple-scripts-cmd-output-lines)),
so the sentry's `^*creak*` listen trigger fires, bumps the sentry's own
`alert_level`, and makes it call out. The chain is five things you already
know (a witness, a check, an emit, a listen, an attribute) composing into
"the guard grows warier every time the floor gives you away," with no
dedicated system behind it. The [security camera](054_security_camera.md)
builds a similar listen relay if you want to contrast the two.

Notice whose stealth breaks on a creak: nobody's. The creak's actor is the
floorboard, so the sneak stays hidden. The sentry now knows someone is
there, but not where, which is exactly right for a noise in the dark.

## Build it

Start in the vault and stand up the sentry as a plain NPC. `@teleport`,
`@create`, `@tag`, and `drop` are the shell commands; the sentry's mind
comes from the attributes and behavior below.

```text
@teleport me = Nexagen Vault
@create Vault Sentry
@tag Vault Sentry = npc
drop Vault Sentry
```

Give it vitality and an Observation skill. The `watchful` behavior uses
Observation as its default perception skill, and 12 makes an even contest
against a middling sneak.

```text
@set Vault Sentry/hp = 13
@set Vault Sentry/max_hp = 13
@set Vault Sentry/health = 10
@set Vault Sentry/skill_observation = 12
```

Attach the engine's `watchful` behavior with parameters. `@behavior` takes
comma-separated `key:value` pairs, so `challenge` is the line for visible
arrivals and `spot_msg` is the line for a caught sneak.

```text
@behavior Vault Sentry = watchful, challenge:This wing is off limits., spot_msg:Intruder! Show yourself!
```

Now give the sentry an ear. Any overheard creak raises its alert one notch
and prompts a challenge. A listen trigger takes no `target` guard, because it
is already scoped to speech this one object hears; `incr` writes to the
sentry itself.

```text
@set Vault Sentry/listen_creak = ^*creak*: incr('alert_level'); say('Who goes there?')
```

Build the floorboard and describe it. It is an ordinary object; its whole
job lives in one hook.

```text
@create loose floorboard
drop loose floorboard
@desc loose floorboard = One plank sits a hair prouder than its brothers.
```

The board's `ON_ENTER` fires on every arrival into its room, so the first
line filters down to the case it cares about: a hidden player. A clean
Stealth check at -3 slips by silently; a failure makes the board itself
emit the creak, which is what the sentry overhears. `cmd('emit ...')` speaks
as the floorboard, keeping the sneak's cover intact.

```text
@set loose floorboard/on_enter = '''
if has_tag(enactor, 'hidden') and has_tag(enactor, 'player'):
    # only a hidden player trips the board; other arrivals pass through
    if skill_check(enactor, 'stealth', -3):
        pemit(enactor, 'You cross the boards without a sound.')
    else:
        cmd('emit A floorboard creaks sharply!')
'''
```

## Try it

Walk in openly and the sentry simply warns you off:

```text
> vault door
Vault Sentry says, "This wing is off limits."
```

Now sneak in with middling Stealth (12, against the sentry's Observation 12,
where a tie goes to the hider):

```text
> hide
You slip out of sight.

> vault door
Someone arrives.
A floorboard creaks sharply!
Vault Sentry says, "Who goes there?"
```

You are still hidden, but the sentry's `alert_level` is now 1, so its next
contest rolls at +1. Slip back out and try again, and the alerted sentry
wins the roll:

```text
> antechamber

> vault door
Vault Sentry spots you!
Vault Sentry says, "Intruder! Show yourself!"
```

A master sneak (Stealth 15) crosses the boards silently and beats an
unalerted sentry, right up until they speak:

```text
> vault door
You cross the boards without a sound.

> say the vault is ours
Your action gives you away!
```

And a patient searcher settles it with dice, since `search` contests
Observation against the hider's Stealth:

```text
> search
Your search turns up: Wraith.
```

The hider reads `Hawk spots you!` on the losing end of that contest.

## Going further

- **Cooling off.** Attach `@behavior Vault Sentry = script_ticker, interval:40`
  and an `on_tick` that decrements `alert_level` toward zero, so an alarm
  fades if the intruder goes to ground.
- **Alert consequences.** At `alert_level` 3 or higher, have the tick lock
  the vault door with [`add_tag`](../reference/softcode.md#fn-add_tag) or
  [`force`](../reference/softcode.md#fn-force) the sentry onto a patrol
  route. The number is just an attribute every script may read.
- **Dark-side advantage.** `@tag` the vault `dark`: `hide` gains its +3
  there, and a sentry without `nightvision` is on the wrong end of the
  perception engine.
- **Backup.** Swap the sentry's call-out for a zone-wide
  [`act`](../reference/softcode.md#fn-act) with `targeting='zone'`, so every
  guard in the wing hears the creak; add `hostile:true` to `watchful` and a
  spot starts real combat.
