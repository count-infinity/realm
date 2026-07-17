# 134. Disguises

> Checklist item 134 — [small] — *apparent-identity override on the `register_name_resolver` seam*

**What you'll build:** a wardrobe that hands out disguises — pull one on
and the whole room reads you as **"a masked courier"** in the occupant
list, in `look`, and in every word you speak. A keen-eyed watcher can
`study` you and, on a winning perception roll, see through it — after
which *they* read your true name while everyone else still sees the mask.

**Concepts:** the **name-resolver seam** (`register_name_resolver`) —
the same one-line-of-policy hook that powers
[short-descs](133_short_descs.md), turned to the opposite purpose — plus
a `check_roll` see-through **contest**, an admin-owned wardrobe master
that writes the wearer's `disguise` / `pierced_by` attributes, and the
fact that a disguise covers your *voice* for free.

## How it works

Every place the engine names a character for a viewer — the "Players
here" list, `look <person>`, speech attribution — routes through
`get_display_name(looker)`, which runs a chain of **name resolvers**. A
disguise is one resolver: while a character carries a `disguise`
attribute, return that assumed identity to any looker who hasn't seen
through it.

The resolver is six lines. It shows the disguise to strangers, but never
to the wearer (you always know your own face) and never to anyone on the
wearer's `pierced_by` list — the ids of watchers who've already seen
through the mask:

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
`get_display_name`, so the instant you're disguised the room hears *"a
masked courier says,"* — you never registered anything for that. Item
[84](084_voice_disguise.md) is the mirror image: a modulator that masks
only the voice and leaves the face known.

**Order matters when you compose with recognition.** If you also register
133's recognition resolver, register it **first** and this one **second**
— resolvers run in order, each seeing the previous one's output, so the
assumed identity gets the last word. A friend you've been introduced to
still reads as "a masked courier" while you wear the mask; drop it and
they know you again.

**Two honest boundaries** (identical to 133). The resolver governs
*engine* narration only. Softcode's own `name(obj)` still returns the
true name — it's trusted and authoritative, which is exactly why the
`study` verb below can reveal "that is really Vale" once the roll
succeeds. And `@examine` shows the truth too: a disguise is a fiction for
players, never a wall against staff.

**Writing another player's sheet needs authority.** Donning a disguise
writes *your own* `disguise` attribute; seeing through one writes the
*wearer's* `pierced_by`. Softcode may write a player sheet only through an
admin-owned object's authority, so the wardrobe that carries these verbs
is `@create`d by an admin (the same steward pattern as 133).

## Build it

A room to change in, and the wardrobe master. `quality` is the disguise's
resistance — a penalty a watcher's perception roll must overcome:

```text
@dig The Green Room
@teleport The Green Room
@create wardrobe
drop wardrobe
@set wardrobe/quality = -4
```

`$don` stamps the wearer with the disguise, its quality, an empty
`pierced_by`, and an alias so others can address the figure by what they
see. `$doff` clears all four:

```text
@set wardrobe/cmd_don = $don *: (pemit(enactor, 'Wear what? Name a disguise.') if not arg0 else (set_attr(enactor, 'disguise', arg0), set_attr(enactor, 'disguise_quality', V('quality', -4)), set_attr(enactor, 'pierced_by', []), set_attr(enactor, 'aliases', [arg0]), pemit(enactor, 'You pull on the costume. The room now reads you as ' + arg0 + '.')))
@set wardrobe/cmd_doff = $doff: (del_attr(enactor, 'disguise'), del_attr(enactor, 'disguise_quality'), del_attr(enactor, 'pierced_by'), set_attr(enactor, 'aliases', []), pemit(enactor, 'You shed the disguise. Your own face again.'))
```

`$study` is the contest. It rolls the watcher's **perception** through
`check_roll`, modified by the disguise's `quality`, and reads `.success`
off the graded result. Win, and the watcher's id is added to the wearer's
`pierced_by` — from now on they read the true name while the rest of the
room stays fooled:

```text
@set wardrobe/cmd_study = $study *: who = get(arg0); dq = get_attr(who, 'disguise_quality', 0) if who else 0; r = check_roll(enactor, 'perception', dq) if who else None; pierced = (get_attr(who, 'pierced_by', []) or []) if who else []; (pemit(enactor, 'Study whom?') if not who else (pemit(enactor, name(who) + ' is not in disguise.') if not get_attr(who, 'disguise') else (pemit(enactor, 'You see through the disguise. That is really ' + name(who) + '.') if r.success else pemit(enactor, 'You study ' + get_attr(who, 'disguise', 'them') + ', but the disguise holds.'), set_attr(who, 'pierced_by', pierced + [enactor.id]) if (r.success and enactor.id not in pierced) else None)))
```

(`check_roll` goes through the real check pipeline, so a watcher who is
blinded or afraid rolls at the penalty their condition imposes — a raw
`margin_under(roll('3d6'), ...)` would silently ignore it. See
[quality tiers](125_quality_tiers.md).)

## Try it

Pull on a disguise, then watch the room from another character's eyes.
As **Vale**:

```text
don a masked courier
    You pull on the costume. The room now reads you as a masked courier.
```

Now, as **Wynn**, look — Vale is a stranger in a costume:

```text
look
    Players here:
      a masked courier
      Wynn
```

Vale speaks; the mask covers the voice with no extra work:

```text
(Vale)  say Package for you.
(Wynn hears)  a masked courier says, "Package for you."
```

Wynn studies the figure. With sharp eyes against a middling disguise the
roll lands, and only Wynn sees through it:

```text
(Wynn)  study a masked courier
    You see through the disguise. That is really Vale.
```

From now on Wynn reads the true name, while anyone else present still
sees — and hears — the courier:

```text
(Vale)  say Nothing to see.
(Wynn hears)  Vale says, "Nothing to see."
(Sable hears) a masked courier says, "Nothing to see."
```

Drop the costume and you're yourself to everyone again:

```text
(Vale)  doff
    You shed the disguise. Your own face again.
```

## Going further

- **A better mask, a harder roll.** `quality` is one `@set` on the
  wardrobe — a stage-grade disguise at `-8`, a thrown-together one at
  `-1`. Or read it off the specific costume item the wearer holds.
- **Costumes as items.** Instead of a naming a disguise by hand, put the
  string on a wearable mask and have `$don` read `get_attr` off the item
  the wearer is holding — pick up the courier's cap, become the courier.
- **Disguise decays.** A `$study` that *just* fails could still whittle
  `quality` down by its margin, so a persistent watcher wears the mask
  thin over several rounds.
- **Compose with recognition.** Register 133's
  [recognition resolver](133_short_descs.md) first and this one second;
  the assumed identity then overrides a face you already knew, so even a
  friend has to `study` you to place you under the mask.
