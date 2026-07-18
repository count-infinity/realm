# 139. Intoxication

> Checklist item 139 — [now] — *drink impairs (check_mods) and slurs (speech renderer), progressively*

**What you'll build:** a bottle in a dockside bar. One pull and every skill
roll takes a penalty and your next `say` comes out slurred to the whole
room; keep drinking and both get worse. Sober up — the effect wears off —
and your tongue, and your aim, come back.

**Concepts:** two seams at once. The **effect machinery** as a debuff
(`apply_effect('modifier_effect', check_mods=...)` — a penalty that folds
into every check and expires on its own, the same path as the
[cooking buff](129_cooking_buffs.md)), and the **speech-renderer seam**
(`register_speech_renderer`) that slurs the spoken body for a drunk
speaker — the same hook [languages](079_languages.md) garbles on.

## How it works

Drinking does two independent things, on two different seams.

**1. The penalty is an effect, not an attribute edit.** `$drink` calls
`apply_effect(drinker, 'modifier_effect', kind='drunk', check_mods={'all':
-2})`. The modifier lives exactly as long as the effect, folds into every
`check()` without being asked, tags the drinker `drunk` while it runs, and
expires on its own beats later — the [banshee's fear](059_tranquilizer.md)
turned inward. There is no `set_attr` on a skill to desync or forget to
undo.

**2. The slur is a speech renderer.** The spoken body is resolved once per
listener (see [action propagation](../architecture/events.md)), so a
transform can rephrase it. This one keys on the *speaker* being drunk — so
it reaches every listener the same way, because it is the speaker's mouth
that is failing, not the listener's ear (the mirror of
[languages](079_languages.md), which keys on the listener). Seven lines:
stretch the vowels and soften every `s`, deterministically, scaled by how
many drinks deep they are:

```python
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

No randomness: the same words, at the same drink count, always slur the
same way — so the transform is testable and a player cannot shake off a bad
render by re-saying it. The renderer, like all of them, rewrites only the
words; *"Bex says,"* stays in the bar's own steady voice while Bex does not.

**Progressive, via a counter.** `apply_effect` *refreshes* by `kind`, so each
pull replaces the single `drunk` effect rather than stacking copies. `$drink`
keeps a `drunks` count on the drinker, bumps it each pull, and re-applies
`drunk` with a deeper penalty (`check_mods={'all': -2 * d}`) — the counter is
what deepens the buzz, since the effect itself is one-at-a-time. The renderer
reads that same counter to stretch the vowels further. The count starts fresh
once a bout wears off and the `drunk` tag is gone.

**Authority.** `$drink` writes the drinker's own `drunks` counter — a write
to a patron's sheet — so the bottle is `@create`d by an admin, borrowing
its owner's authority the way the
[introductions steward](133_short_descs.md) does. Applying the effect
itself needs only *proximity* (the bottle and the drinker share a room), so
a bottle reaches furniture-range effects like any
[gadget](059_tranquilizer.md).

## Build it

The bar, and an admin-owned bottle whose `$drink` verb deepens the
drunkenness on every pull:

```text
@dig The Rusted Flagon
@teleport The Rusted Flagon
@create bottle of rotgut
drop bottle of rotgut
@desc bottle of rotgut = A squat bottle of unlabelled dock rotgut, three-quarters full. DRINK to take a pull -- each one hits harder than the last.
@set bottle of rotgut/cmd_drink = $drink: d = (get_attr(enactor, 'drunks', 0) + 1) if has_tag(enactor, 'drunk') else 1; set_attr(enactor, 'drunks', d); apply_effect(enactor, 'modifier_effect', kind='drunk', duration=12, check_mods={'all': -2 * d}, apply_msg='The rotgut scorches down. The floor tilts a little further.', expire_msg='Your head clears and the room finally holds still.'); remit(here, name(enactor) + ' tips the bottle back and swallows hard.')
```

Each pull bumps the `drunks` count (starting at 1 if the last bout has worn
off) and re-applies `drunk` with a penalty scaled to the count. Because
`apply_effect` refreshes by kind, that single call replaces the previous
effect — exactly one `drunk` at a time, always carrying the current `-2 * d`.

## Try it

Bex, dead sober, raises a toast — clean to the whole bar:

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

Now the same toast reaches everyone slurred — and worse after the second
pull than the first:

```text
(Bex, one drink)   say Cheers, friends!
(Cass hears)  Bex says, "Cheeeersh, friieendsh!"
(Bex, two drinks)  say Cheers, friends!
(Cass hears)  Bex says, "Cheeeeeersh, friiieeendsh!"
```

The penalty rode along on the sheet the whole time. `@examine Bex` shows
the debuff the effect machinery is tracking:

```text
@examine Bex
    Tags: ... drunk, player
    Attributes:
      ...
      check_mods: {'drunk': {'all': -4}}
      drunks: 2
```

Every skill check now folds in that `-4` automatically — a
`check_roll(Bex, 'pistol')` comes back four worse than sober. Twelve beats
later the effect expires (`Your head clears and the room finally holds
still.`); the `drunk` tag and the `check_mods` entry vanish together, and
Bex speaks — and shoots — straight again.

## Going further

- **Feel the penalty.** Bolt a [dartboard](107_dart_board.md) or knife
  board to the wall that rolls `check_roll(enactor, 'throwing')`; sober you
  hit, three drinks in you miss — the `-2 * d` is already in the roll.
- **Pass out.** Gate `$drink` on the count: past five, apply
  `kind='unconscious'` instead (the [tranquilizer's](059_tranquilizer.md)
  engine tag) and Bex slides under the table.
- **A hangover.** Chain a longer, lighter `modifier_effect`
  (`kind='hung_over', duration=40, check_mods={'all': -1}`) off the
  wear-off so the morning costs something too.
- **Slur the foreign tongue too.** Register the
  [languages](079_languages.md) garble alongside this one; renderers run in
  registration order, so a drunk smuggler speaking Trade both garbles (to
  those without it) and slurs (to everyone) — two independent transforms on
  one line of speech.
