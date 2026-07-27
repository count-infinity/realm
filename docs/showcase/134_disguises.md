# 134. Disguises

> Checklist item 134 ([small]): *apparent-identity override on the register_name_resolver seam*

**What you'll build:** a wardrobe that hands out disguises. Pull one on and
the whole room reads you as **"a masked courier"** in the occupant list, in
`look`, and in every word you speak. A keen-eyed watcher can `study` you and,
on a winning perception roll, see through it, after which *they* read your
true name while everyone else still sees the mask.

**Concepts:** the **name-resolver seam** (`register_name_resolver`), the same
short binding that powers [short-descs](133_short_descs.md) turned to the
opposite purpose, plus a [`check_roll`](../reference/softcode.md#fn-check_roll)
see-through contest, an admin-owned wardrobe that writes the wearer's
`disguise` and `pierced_by` attributes, and the fact that a disguise covers
your *voice* for free.

## How it works

A disguise is one small policy on the name every viewer reads. This section
shows where the engine asks that policy for a name, what the policy returns,
and how a watcher earns the right to see past it.

Every place the engine names a character for a viewer (the "Players here"
list, `look <person>`, speech attribution) routes through
`get_display_name(looker)`, which runs a chain of **name resolvers**. A
disguise is one resolver: while a character carries a `disguise` attribute, it
returns that assumed identity to any looker who has not seen through it.

The resolver shows the disguise to strangers, but never to the wearer (you
always know your own face) and never to anyone on the wearer's `pierced_by`
list, the ids of watchers who have already seen through the mask:

```python
# In your game's setup (config.py's on_start, or a bindings module):
from realm.core.perception import register_name_resolver

def wear_a_disguise(obj, looker, current):
    disguise = obj.db.get('disguise')
    pierced = obj.db.get('pierced_by') or []
    if (disguise and looker is not None and looker is not obj
            and looker.id not in pierced):
        return disguise          # the room reads the assumed identity
    return current               # you, and anyone who saw through it

register_name_resolver(wear_a_disguise)
```

**Voice comes free.** Speech attribution is named through the very same
`get_display_name`, so the instant you are disguised the room hears *"a masked
courier says,"*, with nothing registered for that. Item
[84](084_voice_disguise.md) is the mirror image: a modulator that masks only
the voice and leaves the face known.

**Order matters when you compose with recognition.** If you also register
133's recognition resolver, register it **first** and this one **second**.
Resolvers run in order, each seeing the previous one's output, so the assumed
identity gets the last word. A friend you have been introduced to still reads
as "a masked courier" while you wear the mask; drop it and they know you
again.

**Two honest boundaries** (identical to 133). The resolver governs *engine*
narration only. Softcode's own [`name(obj)`](../reference/softcode.md#fn-name)
still returns the true name, because it is trusted and authoritative, which is
exactly why the `study` verb below can reveal "that is really Vale" once the
roll succeeds. And `@examine` shows the truth too: a disguise is a fiction for
players, never a wall against staff.

**Writing another player's sheet needs authority.** Donning a disguise writes
*your own* `disguise` attribute; seeing through one writes the *wearer's*
`pierced_by`. Softcode may write a player sheet only through an admin-owned
object's authority, so the wardrobe that carries these verbs is `@create`d by
an admin (the same steward pattern as 133). All three verbs are `$`-commands,
dispatched only to the wardrobe whose pattern matched the typed line, so unlike
a room-wide `ON_<EVENT>` hook they need no `if target is me` guard.

## Build it

Start with a room to change in and the wardrobe itself. `@teleport` positions
the builder, and `quality` is the disguise's resistance, a penalty a watcher's
perception roll must overcome:

```text
@dig The Green Room
@teleport The Green Room
@create wardrobe
drop wardrobe
@set wardrobe/quality = -4
```

`$don` stamps the wearer with the disguise, its quality, an empty `pierced_by`,
and an alias so others can address the figure by what they see, then confirms
with [`pemit`](../reference/softcode.md#fn-pemit).
[`set_attr`](../reference/softcode.md#fn-set_attr) writes each attribute and
[`V`](../reference/softcode.md#fn-v) reads `quality` off the wardrobe:

```text
@set wardrobe/cmd_don = '''
$don *:
if not arg0:
    pemit(enactor, 'Wear what? Name a disguise.')
else:
    set_attr(enactor, 'disguise', arg0)
    set_attr(enactor, 'disguise_quality', V('quality', -4))
    set_attr(enactor, 'pierced_by', [])
    set_attr(enactor, 'aliases', [arg0])   # so others can address the figure by the mask
    pemit(enactor, 'You pull on the costume. The room now reads you as ' + arg0 + '.')
'''
```

`$doff` clears all four attributes with
[`del_attr`](../reference/softcode.md#fn-del_attr) and empties the alias, so
you read as yourself again to everyone:

```text
@set wardrobe/cmd_doff = '''
$doff:
del_attr(enactor, 'disguise')
del_attr(enactor, 'disguise_quality')
del_attr(enactor, 'pierced_by')
set_attr(enactor, 'aliases', [])
pemit(enactor, 'You shed the disguise. Your own face again.')
'''
```

`$study` is the contest. It resolves the target with
[`get`](../reference/softcode.md#fn-get), reads the mask's `disguise_quality`
with [`get_attr`](../reference/softcode.md#fn-get_attr), rolls the watcher's
**perception** through `check_roll` modified by that quality, and reads
`.success` off the graded result. On a win, `name(who)` gives the true name and
the watcher's id joins the wearer's `pierced_by`, so from then on they read the
true name while the rest of the room stays fooled:

```text
@set wardrobe/cmd_study = '''
$study *:
who = get(arg0)
if not who:
    pemit(enactor, 'Study whom?')
elif not get_attr(who, 'disguise'):
    pemit(enactor, name(who) + ' is not in disguise.')
else:
    dq = get_attr(who, 'disguise_quality', 0)
    r = check_roll(enactor, 'perception', dq)   # quality penalty folds into the real check pipeline
    pierced = get_attr(who, 'pierced_by', []) or []
    if r.success:
        pemit(enactor, 'You see through the disguise. That is really ' + name(who) + '.')
        if enactor.id not in pierced:
            set_attr(who, 'pierced_by', pierced + [enactor.id])   # this watcher now reads the true name
    else:
        pemit(enactor, 'You study ' + get_attr(who, 'disguise', 'them') + ', but the disguise holds.')
'''
```

`check_roll` goes through the real check pipeline, so a watcher who is blinded
or afraid rolls at the penalty their condition imposes; a raw
`margin_under(roll('3d6'), ...)` would silently ignore it. See
[quality tiers](125_quality_tiers.md).

## Try it

Pull on a disguise, then watch the room from another character's eyes. As
**Vale**:

```text
don a masked courier
    You pull on the costume. The room now reads you as a masked courier.
```

Now, as **Wynn**, look. Vale is a stranger in a costume:

```text
look
    Players here:
      a masked courier
      Wynn
```

Vale speaks, and the mask covers the voice with no extra work:

```text
(Vale)  say Package for you.
(Wynn hears)  a masked courier says, "Package for you."
```

Wynn studies the figure. The outcome rides one perception roll against the
wardrobe's `-4` quality; with sharp eyes the roll lands here, and only Wynn
sees through it (a duller-eyed watcher would read "the disguise holds"):

```text
(Wynn)  study a masked courier
    You see through the disguise. That is really Vale.
```

From now on Wynn reads the true name, while anyone else present still sees, and
hears, the courier:

```text
(Vale)  say Nothing to see.
(Wynn hears)  Vale says, "Nothing to see."
(Sable hears) a masked courier says, "Nothing to see."
```

Drop the costume and you are yourself to everyone again:

```text
(Vale)  doff
    You shed the disguise. Your own face again.
```

## Going further

- **A better mask, a harder roll.** `quality` is one `@set` on the wardrobe, a
  stage-grade disguise at `-8`, a thrown-together one at `-1`. Or read it off
  the specific costume item the wearer holds.
- **Costumes as items.** Instead of naming a disguise by hand, put the string
  on a wearable mask and have `$don` read `get_attr` off the item the wearer is
  holding, so picking up the courier's cap makes you the courier.
- **Disguise decays.** A `$study` that *just* fails could still whittle
  `quality` down by its margin, so a persistent watcher wears the mask thin
  over several rounds.
- **Compose with recognition.** Register 133's
  [recognition resolver](133_short_descs.md) first and this one second; the
  assumed identity then overrides a face you already knew, so even a friend has
  to `study` you to place you under the mask.
