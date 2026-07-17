# 064. Bartender

> Checklist item 64 — [now] — *^listen keyword patterns, consumables, rumor attrs*

**What you'll build:** Mira, keeper of The Rusty Flagon: ask what's on
tap and she quotes you; pay her and a real, drinkable mug of ale
appears on the bar; ask for rumors and she obliges — paying patrons
only, and never the same rumor twice in a row.
**Concepts:** `^listen` keyword triggers, the `ON_PAYMENT` hook and its
action data (`target`, `adata('amount')`), `create_obj()` consumables
with their own `$`-command, per-player rotation state in attrs.

## How it works

Three trigger surfaces, all plain attributes set with `@set`:

1. **`^listen` patterns** overhear real speech. `listen_*` attributes
   hold `^pattern:action`; `*` wildcards match anything, and multiple
   listen triggers can fire on one utterance. Mira's menu and rumor
   lines are just keyword listens. (She can't overhear herself — the
   engine skips the speaker's own patterns — so her answers can even
   contain her own keywords.)
2. **`ON_PAYMENT`** fires when someone `pay`s her — and, like every
   witnessed `ON_<EVENT>`, it also fires on *bystanders* who have the
   hook. The hook gets the action's own data to sort that out:
   `target` is who was paid (so `target == me` means "the coins are
   mine"), and `adata('amount')` is how many. Two names, both
   questions answered.
3. **The mug is a real object** made with `create_obj()`, carrying its
   own `$drink *` command. Softcode may set `cmd_*` attributes on
   objects it controls, and Mira's owner owns what she creates — so
   the bartender *authors a new scripted object* every sale. `heal()`
   uses proximity authority (same room), which is why she sets the mug
   on the bar rather than teleporting it into your pack.

Rumor gating rides the same attrs: paying marks you
`patron_<your id>` on Mira, and the rumor listen checks that flag,
walking each patron through the `rumors` list with a per-player index.

## Build it

Dig the tavern off the Square (from item 60's town — any `zone:town`
room works) and give it a keeper:

```
@dig The Rusty Flagon = flagon, square
flagon
@zone here = town
@create Mira
@tag Mira = npc
drop Mira
@desc Mira = The Flagon's keeper. She polishes a mug and misses nothing.
```

**The menu** is one listen trigger — any sentence containing "on tap"
gets the pitch:

```
@set Mira/listen_tap = ^*on tap*:say Ale, five credits the mug. Pay me and it is yours.
```

**The sale.** `ON_PAYMENT`, reading the payment straight off the
action. Note the three-way split: serve on 5+, grumble at a short
payment, and stay silent when the money wasn't hers (someone paid a
*different* NPC in this room — witnessed events reach every bystander
with the hook, so `target == me` is the first thing she checks):

```
@set Mira/on_payment = paid = adata('amount', 0) if target == me else 0; ((set_attr(me, 'patron_' + enactor.id, 1), say('One ale, coming up.'), trigger('pour')) if paid >= 5 else (say('Ale is five credits, love.') if paid > 0 else None))
```

**The pour** lives in its own attribute (`trigger('pour')` runs it, and
`@tr Mira/pour` lets you test-fire it alone). It builds the mug and
installs the drink command from a template attribute:

```
@set Mira/pour = mug = create_obj('a mug of ale', location=here); set_attr(mug, 'description', 'Cloudy town ale, still foaming.'); set_attr(mug, 'cmd_drink', V('drink_script')); pose('sets a foaming mug on the bar.')
@set Mira/drink_script = $drink *:heal(enactor, 1); pemit(enactor, 'The ale goes down warm.'); oemit(enactor, f'{name(enactor)} drains a mug of ale.'); destroy_obj(me)
```

`drink_script` is inert on Mira (only `cmd_*` attributes register as
commands) — it's a template she stamps onto every mug. The mug heals,
narrates to drinker and room, and destroys itself: a consumable in one
line.

**The gossip.** A rumor list plus a gated, rotating listen:

```
@set Mira/rumors = ["They say the old mine did not close for bad air alone.", "Verity shuts her shop at nine sharp - and sleeps above it.", "Scream on Market Street and count to ten. The watch is faster."]
@set Mira/listen_rumor = ^*rumor*:r = V('rumors', []); i = V('idx_' + enactor.id, 0); ((say(r[i % len(r)]), incr('idx_' + enactor.id)) if V('patron_' + enactor.id, 0) else say('Ale first. A wet tongue wags easier - mine included.'))
```

Each asker has their own index (`idx_<id>`), so two patrons hear the
rotation independently — and the list is data, so restocking gossip is
another `@set`, no code.

## Try it

Give yourself pocket money and a body that can feel the ale:

```
@set me/credits = 40
@set me/hp = 9
@set me/max_hp = 12
```

Then, at the bar:

```
say what's on tap?           → "Ale, five credits the mug. ..."
say any rumors?              → "Ale first. A wet tongue wags easier..."
pay 5 to Mira                → "One ale, coming up." — a mug appears
drink ale                    → "The ale goes down warm." (+1 HP, mug gone)
say any rumors?              → the first rumor
say rumors                   → the second — she remembers where you were
```

## Going further

- **Stock the taps:** make `rumors`-style data of the drinks too — a
  `drinks` dict attr of name → price, and have `on_payment` match
  `adata('amount')` against it to serve porter at 8 and whiskey at 12.
- **Disposition pricing:** `persuade Mira` before ordering, then have
  `on_payment` accept `5 - disposition(me, enactor)` — charm earns
  cheaper ale (see `consider`/`persuade`, and item 71 for the stick).
- **Quest hooks:** make a rumor a dict `{"text": ..., "hook": "missing_cargo"}`
  and `pemit` a follow-up lead when the rumor carries a hook — bar
  gossip as a quest-discovery channel.
- **Last call:** gate the whole `on_payment` on item 68's town clock —
  `get_attr('town clock', 'hour', 12)` — and refuse service after two.
