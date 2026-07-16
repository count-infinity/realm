# Part 13 — The Enthrall Spell

That pendant in Mother Salt's tray has been staring back all part.
Time to build a *spell*: resistible mind-magic with a target who
rolls, a ward that refuses, and consequences that wear off. The
kernel has no magic system — which is the point. A spell is an item,
a category tag, a contest, and the victims' own reactions.

## The caster's half

Mesmerism should be a skill you can be bad at:

```text
@create hypnotism
@tag hypnotism = skill_def
@set hypnotism/stat = intelligence
@set hypnotism/penalty = -6
@reload
improve hypnotism
improve hypnotism
```

Then buy your focus (persuaded her first, did you?) and enchant it —
two attributes:

```text
buy milk-opal pendant
@tag a milk-opal pendant = charm
@set a milk-opal pendant/cmd_enthrall = $enthrall *:v = get(arg0); pemit(enactor, 'No one by that name catches the light.') if not v or loc(v) != here else (pemit(enactor, 'You tilt the opal until ' + name(v) + ' catches the light swimming in it.'), cast(v, 'enthrall', tags=['mind']))
```

`cast()` is the ability layer: it aims a *categorized event* at the
target — `event:on_cast`, tagged `mind` because you say so (the
kernel forces no genre; your psi game tags `psi`). What it does to
the target is decided by the target.

## The victim's half

In the tavern, the sailor learns what an opal is for:

```text
tavern
@set the sailor/ON_CAST = h = loc(enactor) if has_tag(enactor, 'charm') else enactor; (apply_effect(me, 'disposition_boost', target_id=h.id, delta=3, duration=30), force(me, 'follow ' + name(h)), say('Aye... anything you say, friend.')) if not contest(me, 'will', h, 'hypnotism') else say('You keep OUT of my head!')
```

The first clause is the subtle one. Part 4 said scripts run *as their
object* — so the cast arrives from **the pendant**, and `enactor`
here is the charm itself. `loc(enactor)` follows the chain to the
hand that holds it. Then it's an honest **quick contest** — his
`will` against your `hypnotism` — and on a loss *he does the
enthralling to himself*: +3 disposition toward you for thirty beats
(the same expiring boost fast-talk uses, reversed when it lapses),
and he falls in behind you. Try it:

```text
enthrall the sailor
```

Walk out; he follows. Different minds, different surrender — give
Mother Salt the merchant's version (glassy eyes, no walkies):

```text
market
@set Mother Salt/ON_CAST = h = loc(enactor) if has_tag(enactor, 'charm') else enactor; (apply_effect(me, 'disposition_boost', target_id=h.id, delta=3, duration=30), say('Of course, dear. For you, anything.')) if not contest(me, 'will', h, 'hypnotism') else say('You keep OUT of my head!')
enthrall mother salt
list
```

Those are enthralled prices — the +3 boost is the same disposition
the shop reads, so the whole list melts 15%. In a couple of minutes
the glaze lifts, the boost reverses itself, and she'll wonder why she
let the cloak go for that.

## The iron mind

```text
enthrall the watchman
```

Nothing. Not rudeness — a **ward**. Set it yourself:

```text
@set the watchman/on_check = block('iron discipline') if has_atag('mind') else None
```

`on_check` runs in the action's *permission pass*, read-only, before
anything reacts: `block()` vetoes the event, so his `ON_CAST` — had
he one — never fires, and the caster gets no tell but the silence.
Wards match on the tags *you* chose (`mind`), which is how one line
refuses a whole school of magic.

## Release

```text
@set a milk-opal pendant/cmd_release = $release *:force(get(arg0), 'unfollow'); pemit(enactor, 'You palm the opal dark.')
release the sailor
```

!!! info "Learn more"
    A cast is *witnessed*: the room and bystanders see the event too,
    and a bystander's `ON_CAST` fires alongside the target's — so
    keep one impressionable mind per room (as here), or open the
    reaction with a guard. Bystander wards, though, protect only
    their bearer — the watchman's iron mind can't shield Mother Salt
    beside him. The split to remember: `contest()` is the *roll*,
    `cast()` is the *ward + reaction* layer, and effects like
    `disposition_boost` are the aftermath that cleans up after
    itself.
