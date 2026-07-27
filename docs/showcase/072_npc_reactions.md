# 072. NPC reaction emotes

> Checklist item 72 ([now]): *^listen keyword reactions, ON_EMOTE, ON_WIELD, now() cooldowns*

**What you'll build:** Nerissa, keeper of the Anchor Taproom, who misses
nothing. Greet the room and she answers, talk of fighting and she warns you
off, and pose anything at all and she marks you with a raised eyebrow. Pose a
*blade*, though, and she reads the wording and says so, and draw real steel and
she names it and tells you to put it away, with a cooldown so she does not turn
into a metronome.

**Concepts:** the three surfaces an NPC reacts through, which are `^listen`
(speech content), [`ON_EMOTE`](../reference/softcode.md#lifecycle-hooks) (someone
posed, and *what* they posed via
[`adata('pose')`](../reference/softcode.md#event-data-namespace)), and
[`ON_WIELD`](../reference/softcode.md#lifecycle-hooks) (someone drew a weapon, and
*which* weapon via `target`), plus the [`now()`](../reference/softcode.md#fn-now)
cooldown-attribute idiom and a disposition consequence.

## How it works

Nerissa is a bystander wired to three kinds of room activity. Each kind reaches
her through a different surface, and each reaction is one attribute stored on
her. This section answers four questions: how she hears speech, how she reads a
pose's wording, how she names the weapon you drew, and why none of these
reactions needs a `target is me` guard even though every one of them fires on
every object in the room.

### How she hears speech

`listen_*` attributes hold `^pattern:command` triggers that fire on overheard
speech, with the full line available to the pattern, so a reaction can key on
*what was said* (`^*evening*`, `^*fight*`). Several patterns may fire on one
line, and the speaker is excluded, so she never overhears herself. The set of
overhearable actions is `{speech, shout, ooc, emit}`, which is why a pose is not
among them (see Engine gaps).

### How she reads a pose, and its wording

A pose propagates as `event:emote`, and an
[`ON_EMOTE`](../reference/softcode.md#lifecycle-hooks) attribute on any bystander
fires whenever someone in the room emotes. The hook knows *who* through
`enactor` and *what* through
[`adata('pose')`](../reference/softcode.md#event-data-namespace), the pose text.
Nerissa uses both: talk of blades, even in the telling of a story, earns a word
from her, and anything else earns the eyebrow. That first branch is the
interesting one, because reading a pose's wording is the only way to react to it
at all, since `^listen` never hears an emote.

### How she names the weapon you drew

`wield` fires `item:on_wield`, which is a gated event (an `on_check` ward can
refuse the draw, the way cursed gear refuses removal), and every witness with an
[`ON_WIELD`](../reference/softcode.md#lifecycle-hooks) attribute hears it.
`enactor` is the one drawing and **`target` is the weapon itself**, so she can
name what you drew rather than saying "steel" and hoping. That is the general
shape: where an event's subject *is* the thing acted on, it arrives as `target`
(the same way `ON_GET` and `ON_DROP` deliver the object), while `adata` carries
the extras a target cannot express, such as a pose's text. Her reaction pairs
the line with
[`adjust_disposition(me, enactor, -1)`](../reference/softcode.md#fn-adjust_disposition),
because bare steel has a social price that other systems read later:
[the guarded exit](031_guarded_exit.md) and
[the aggressive mob](062_aggressive_mob.md) both consult that same number.

### Why these hooks take no `target is me` guard

An [`ON_<EVENT>`](../reference/softcode.md#lifecycle-hooks) hook fires on every
object in the room, so a hook that reacts only to its own business usually opens
with [`if target is me`](../reference/softcode.md#guard-on-target). Nerissa's
reactions do not, and that is correct, because a pose targets the room and a
wield targets the weapon, so `target is me` on Nerissa would be false and her
reactions would never fire. She is a bystander reacting to room activity, keyed
on `enactor` and on content, which is the global-witness style (like a
scoreboard) rather than the guard-on-target style. Two facts keep it from
misfiring. The engine never lets an actor witness its own event, so Nerissa
never reacts to her own say or pose, and with one keeper in the room there is
exactly one reaction per event and no feedback loop. Drop a second keeper in and
each reacts once to a player, and the two will also answer each other's poses,
because to each keeper the other's pose is a genuine room event. That
cross-reaction does not arise with the single keeper this tutorial builds.

### The cooldown idiom

Store [`now()`](../reference/softcode.md#fn-now) on success, then read that
stamp back with [`V('noticed', 0)`](../reference/softcode.md#fn-v) and gate on
`now() - V('noticed', 0) > 15`. A roomful of poseurs then earns one eyebrow
every fifteen seconds instead of a facial tic. It is the same one-alarm-per-brawl
rate limit [the guard response](071_guard_response.md) uses, miniaturized. The
cooldown guards only the eyebrow, the branch that would otherwise fire on every
pose, while the blade line is rare by nature and needs no governor.

## Build it

Shell first. From your workroom, dig the taproom, step in, and seat the keeper:

```text
@dig The Anchor Taproom = taproom, out
taproom
@create Nerissa
@tag Nerissa = npc
drop Nerissa
@desc Nerissa = The Anchor's keeper. Nothing in this room escapes her.
```

Two content-keyed listens for speech. Each is a single `^pattern:command`
trigger, so it stays on one line:

```text
@set Nerissa/listen_greet = ^*evening*:say Evening yourself. First one's full price, same as always.
@set Nerissa/listen_trouble = ^*fight*:say Take that talk to the alley or lose your tab.
```

The pose reaction is a `'''` block because it has control flow. Read it as two
branches: if the pose *wording* names a blade she answers its content, and
otherwise the eyebrow fires, cooled down to one glance per fifteen seconds:

```text
@set Nerissa/on_emote = '''
p = adata('pose', '')
if 'dagger' in p or 'blade' in p or 'knife' in p:  # read the pose wording; ^listen cannot
    say(f'Keep it in the story and out of my taproom, {name(enactor)}.')
elif now() - V('noticed', 0) > 15:  # eyebrow at most once per 15 seconds
    pose(f'glances up, marking {name(enactor)} with one raised eyebrow.')
    set_attr(me, 'noticed', now())  # stamp the cooldown
'''
```

The weapon-draw reaction is a `'''` block too. Here `target` is the blade, so
she names it, and a bare draw costs the drawer a point of her regard. Uniformed
law is exempt:

```text
@set Nerissa/on_wield = '''
if not has_tag(enactor, 'town_watch'):  # target is the weapon, not Nerissa, so no target-is-me guard
    say(f'That {name(target)} goes away in my taproom, {name(enactor)}. I will not ask twice.')
    adjust_disposition(me, enactor, -1)
'''
```

## Try it

She answers speech on its content:

```text
> say good evening, all
  Nerissa says, "Evening yourself. First one's full price, same as always."
> say I hear there was a fight
  Nerissa says, "Take that talk to the alley or lose your tab."
```

An ordinary pose earns the eyebrow, and a second pose inside the cooldown window
earns nothing:

```text
> pose stretches and cracks his knuckles.
  Nerissa glances up, marking Tam with one raised eyebrow.
> pose whistles innocently.
  (nothing: the cooldown attr holds. Wait fifteen seconds, pose again, and the eyebrow returns.)
```

Pose a blade and she reads the wording, not the gesture, and no cooldown
suppresses it, because the blade branch never touches one:

```text
> pose draws his dagger slowly.
  Nerissa says, "Keep it in the story and out of my taproom, Tam."
```

`^*dagger*` would never have caught that, because `^listen` does not hear poses
(see Engine gaps). Now give her a real weapon to name:

```text
> @create rusty cutlass
> wield rusty cutlass
  Nerissa says, "That rusty cutlass goes away in my taproom, Tam. I will not ask twice."
> consider Nerissa
  (cooler than she was: the -1 stuck)
```

She named the blade because `target` *is* the blade, so draw a butter knife and
she says so instead.

## Engine gaps

`^listen` does not hear poses. `LISTENABLE_ACTIONS` is `{speech, shout, ooc,
emit}`, and a pose propagates as `event:emote`, so a listen pattern cannot match
emote wording: `pose draws his dagger slowly` triggers no `^*dagger*`, and no
amount of pattern writing changes that. The answer is the hook rather than the
pattern. [`ON_EMOTE`](../reference/softcode.md#lifecycle-hooks) with
[`adata('pose')`](../reference/softcode.md#event-data-namespace) reads exactly
that text, which is what Nerissa's blade branch does.

## Going further

- **Escalation:** stamp
  [`set_attr(me, 'warned_' + enactor.id, 1)`](../reference/softcode.md#fn-set_attr)
  in `on_wield`
  and have a second offense [`force()`](../reference/softcode.md#fn-force) a
  bouncer, which is [the guard response](071_guard_response.md)'s dispatch one
  room deep.
- **Know a butter knife from a greatsword:** `target` is the weapon object, so
  gate the whole reaction on it with
  `if get_attr(target, 'damage', 0) > 2`
  ([`get_attr`](../reference/softcode.md#fn-get_attr)) and let a harmless draw
  pass without comment. A keeper who can tell a tool from a threat.
- **A whole mood:** key reactions on
  [`disposition(me, enactor)`](../reference/softcode.md#fn-disposition), so the
  eyebrow becomes a smile for a regular she likes and a glare for the fasttalker
  whose lie wore off ([the guarded exit](031_guarded_exit.md)).
- **Unwield too:** an `ON_UNWIELD` thanking them for good sense, since gated
  events come in pairs.
- **Semiposes:** `;'s dog growls` propagates `event:semipose`, so an
  `ON_SEMIPOSE` attribute catches those separately if your house style uses
  them.
