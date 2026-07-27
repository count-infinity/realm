# 139. Intoxication

> Checklist item 139 ([small]): *drink impairs (modifier_effect) and slurs (speech renderer), progressively*

**What you'll build:** a bottle in a dockside bar. One pull and every skill
roll takes a penalty and your next `say` comes out slurred to the whole
room; keep drinking and both get worse. Sober up, the effect wears off, and
your tongue and your aim come back together.

**Concepts:** two seams at once. The **effect machinery** as a debuff
([`apply_effect`](../reference/softcode.md#fn-apply_effect) with a
`modifier_effect`, a penalty that folds into every check and expires on its
own, the same path as the [cooking buff](129_cooking_buffs.md)), and the
per-listener **speech renderer** (`register_speech_renderer`) that slurs the
spoken body for a drunk speaker, the same hook [languages](079_languages.md)
garbles on.

## How it works

The finished bar holds one admin-owned bottle. Drink from it and two
independent things happen on two independent seams: a `modifier_effect`
lands on you so every skill roll is worse until it wears off, and a speech
renderer slurs your next `say` for everyone in the room. Drink again and
both deepen. This section answers where the penalty lives, where the slur
happens, how each pull deepens both, and who is allowed to write the counter.

### Why the penalty is an effect, not an attribute edit

`$drink` calls
[`apply_effect`](../reference/softcode.md#fn-apply_effect) with
`modifier_effect`, `kind='drunk'`, and `check_mods={'all': -2 * d}`. A
`modifier_effect` is a condition with no pulse: it does no periodic work, it
just parks a check modifier on the drinker for a while. The engine stores
that modifier in `db.check_mods` keyed by the effect's kind, so a single
pull leaves `check_mods = {'drunk': {'all': -2}}`, and every
[`check_roll`](../reference/softcode.md#fn-check_roll) folds the `all` entry
in without being asked. The modifier lives exactly as long as the effect,
tags the drinker `drunk` while it runs, and expires on its own a dozen beats
later, the [banshee's fear](059_tranquilizer.md) turned inward. Nothing
writes a skill value, so nothing can drift out of sync or be left un-undone.

### Where the slur happens

The spoken body is resolved once per listener (see
[action propagation](../architecture/events.md)), so a transform can
rephrase it on the way out. This one is a **speech renderer**, the same seam
[languages](079_languages.md) uses. It is native setup Python a game
registers once at deploy time, so the policy half lives with the game rather
than in softcode a player could rewrite. It keys on the *speaker* being
drunk, which is why it reaches every listener the same way: it is the
speaker's mouth that is failing, not the listener's ear (the mirror of
[languages](079_languages.md), which keys on the listener). It stretches the
vowels and softens every `s`, deterministically, scaled by how many drinks
deep the speaker is:

```python
# In your game's setup (config.py's on_start, or a bindings module):
from realm.core.propagation import register_speech_renderer

def slur_when_drunk(body, action, looker):
    if action.action_type != "event:speech" or not action.actor.has_tag("drunk"):
        return body
    stretch = 1 + int(action.actor.db.get("drunks") or 1)   # more drink, longer vowels
    swap = {"s": "sh", "S": "Sh"}
    return "".join(
        swap.get(c, c * stretch if c.lower() in "aeiou" else c) for c in body)

register_speech_renderer(slur_when_drunk)
```

There is no randomness, so the same words at the same drink count always
slur the same way, which keeps the transform testable and stops a player
shaking off a bad render by re-saying it. The renderer, like every one,
rewrites only the words: *"Bex says,"* stays in the bar's own steady voice
while Bex does not.

### How each pull deepens both

`apply_effect` *refreshes* by kind rather than stacking, so each pull
replaces the single `drunk` effect instead of piling up copies, and the
refresh restarts the countdown from full duration. `$drink` therefore keeps
its own `drunks` count on the drinker, bumps it each pull, and re-applies
`drunk` with a deeper penalty (`check_mods={'all': -2 * d}`); the counter is
what deepens the buzz, since the effect itself is one-at-a-time. The renderer
reads that same counter to stretch the vowels further. The count starts fresh
once a bout wears off and the `drunk` tag is gone.

### Who is allowed to write the counter

`$drink` writes the drinker's own `drunks` counter with
[`set_attr`](../reference/softcode.md#fn-set_attr), and that is a write to a
patron's sheet, so the bottle is `@create`d by an admin and borrows its
owner's authority the way the [introductions steward](133_short_descs.md)
does. Applying the effect itself needs only *proximity* (the bottle and the
drinker share a room), so a bottle reaches furniture-range effects like any
[gadget](059_tranquilizer.md).

## Build it

First dig the bar, step into it, and drop an admin-owned bottle with a
description that invites a pull:

```text
@dig The Rusted Flagon
@teleport The Rusted Flagon
@create bottle of rotgut
drop bottle of rotgut
@desc bottle of rotgut = A squat bottle of unlabelled dock rotgut, three-quarters full. Drink to take a pull; each one hits harder than the last.
```

The `$drink` verb runs only on the bottle it is set on, so it needs no
`target` guard. Each pull works out the new drink count (fresh bouts start
at one), stamps it back on the drinker, re-applies `drunk` with a penalty
scaled to that count, and then tells the room. Because `apply_effect`
refreshes by kind, that single call replaces the previous effect, so there
is exactly one `drunk` at a time always carrying the current `-2 * d`:

```text
@set bottle of rotgut/cmd_drink = '''
$drink:
if has_tag(enactor, 'drunk'):
    d = get_attr(enactor, 'drunks', 0) + 1   # already tipsy: deepen the bout
else:
    d = 1                                     # a fresh bout starts at one
set_attr(enactor, 'drunks', d)
apply_effect(enactor, 'modifier_effect', kind='drunk', duration=12, check_mods={'all': -2 * d}, apply_msg='The rotgut scorches down. The floor tilts a little further.', expire_msg='Your head clears and the room finally holds still.')
remit(here, name(enactor) + ' tips the bottle back and swallows hard.')
'''
```

## Try it

Bex, dead sober, raises a toast, and it reaches the whole bar clean:

```text
(Bex)   say Cheers, friends!
(Cass hears)  Bex says, "Cheers, friends!"
```

Bex takes a pull, then a second:

```text
(Bex)   drink
    The rotgut scorches down. The floor tilts a little further.
    Bex tips the bottle back and swallows hard.
(Bex)   drink
```

Now the same toast reaches everyone slurred, and worse after the second pull
than the first:

```text
(Bex, one drink)   say Cheers, friends!
(Cass hears)  Bex says, "Cheeeersh, friieendsh!"
(Bex, two drinks)  say Cheers, friends!
(Cass hears)  Bex says, "Cheeeeeersh, friiieeendsh!"
```

The penalty rode along on the sheet the whole time. `@examine Bex` shows the
debuff the effect machinery is tracking:

```text
@examine Bex
    Tags: ... drunk, player
    Attributes:
      ...
      check_mods: {'drunk': {'all': -4}}
      drunks: 2
```

Every skill check now folds in that `-4` automatically, so a
`check_roll(Bex, 'pistol')` comes back four worse than sober. A dozen beats
after the last pull the effect expires (`Your head clears and the room
finally holds still.`); the `drunk` tag and the `check_mods` entry vanish
together, and Bex speaks, and shoots, straight again.

## Going further

- **Feel the penalty.** Bolt a [dartboard](107_dart_board.md) or knife board
  to the wall that rolls `check_roll(enactor, 'throwing')`; sober you hit,
  three drinks in you miss, because the `-2 * d` is already in the roll.
- **Pass out.** Gate `$drink` on the count: past five, apply
  `kind='unconscious'` instead (the [tranquilizer's](059_tranquilizer.md)
  engine tag) and Bex slides under the table.
- **A hangover.** Chain a longer, lighter `modifier_effect`
  (`kind='hung_over', duration=40, check_mods={'all': -1}`) off the wear-off
  so the morning costs something too.
- **Slur the foreign tongue too.** Register the
  [languages](079_languages.md) garble alongside this one. Renderers run in
  registration order, so a drunk smuggler speaking Trade both garbles (to
  those without it) and slurs (to everyone): two independent transforms on
  one line of speech.
```
