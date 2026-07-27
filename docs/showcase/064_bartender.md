# 064. Bartender

> Checklist item 64 ([now]): *^listen keyword patterns, consumables, rumor attrs*

**What you'll build:** Mira, keeper of The Rusty Flagon. Ask what is on
tap and she quotes you, pay her and a real, drinkable mug of ale appears
on the bar, and ask for rumors and she obliges, for paying patrons only
and never the same rumor twice in a row.
**Concepts:** [`^listen`](007_voice_recorder.md) keyword triggers, the
`ON_PAYMENT` hook ([lifecycle hooks](../reference/softcode.md#lifecycle-hooks))
with its [action data](../reference/softcode.md#event-data-namespace)
(`target`, `adata('amount')`),
[`create_obj()`](../reference/softcode.md#fn-create_obj) consumables that
carry their own `$`-command, and per-player rotation state kept in attrs.

## How it works

Mira is three trigger surfaces sitting on one NPC, each a plain attribute
set with `@set`: a pair of `^listen` triggers that overhear the room, an
`ON_PAYMENT` hook that reacts to money, and a template attribute she
stamps onto every mug she pours. Nothing here is a Python file; it is all
softcode typed at the prompt. This section walks the three surfaces in
the order a drinker meets them: she answers questions, she takes payment,
and the mug she pours does its own work.

### How she answers a question she overhears

A `^listen` trigger is an attribute named `listen_*` whose value is
`^pattern:action`, and it fires when speech matching the pattern is heard
where the object stands (the [voice recorder](007_voice_recorder.md)
builds a whole microphone out of this). A `*` wildcard matches any run of
text, and more than one listen trigger can fire on a single utterance, so
Mira's menu line and her rumor line are just two keyword listens watching
the same room. She cannot overhear herself, because the engine skips
every listen trigger sitting on the speaker, which means her answers may
freely contain her own keywords without looping.

### How she knows the coins were hers

When someone `pay`s her, the `pay` builtin propagates an
`event:payment` action, and every witness in the room that has an
`ON_PAYMENT` hook fires, not only the object that was paid. Mira shares
the Flagon with [Old Moss](067_dialogue_tree_npc.md), so a payment to
Moss reaches Mira's hook too. The
[action data namespace](../reference/softcode.md#event-data-namespace)
sorts that out: `target` is the object that was paid, so
[`target is me`](../reference/softcode.md#guard-on-target) is Mira asking
"were these coins put in my hand", and `adata('amount')` is how many. The
guard is an identity check written with `is`, not `==`, and it wraps the
whole body, because reacting to another NPC's sale would be a bug.

### How the mug she pours becomes a real drink

The mug is a genuine object minted with
[`create_obj()`](../reference/softcode.md#fn-create_obj). Softcode may set
`cmd_*` attributes on objects it controls, and Mira's owner owns whatever
she creates, so she authors a fresh scripted object on every sale and
stamps a `$drink *` command onto it from a template attribute. She mints
the mug onto the bar rather than into your pack because `create_obj` will
only seed an object into a room the executor occupies or controls: minting
straight into a patron's hands is refused, and handing it over would take
a `create_obj` followed by a
[`move_to`](../reference/softcode.md#fn-move_to). Setting it on the bar
needs neither.

Rumor gating rides the same attributes. Paying marks you
`patron_<your id>` on Mira, and the rumor listen checks that flag before
it speaks, walking each patron through the `rumors` list with a per-player
index so two drinkers hear the rotation independently.

## Build it

The multi-statement scripts here are `'''` heredoc blocks (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

Dig the tavern off the Square (from item 60's town, though any
`zone:town` room works) and give it a keeper:

```text
@dig The Rusty Flagon = flagon, square
flagon
@zone here = town
@create Mira
@tag Mira = npc
drop Mira
@desc Mira = The Flagon's keeper. She polishes a mug and misses nothing.
```

The menu is one listen trigger: any sentence containing "on tap" gets the
pitch. It is a single statement, so it stays a one-liner:

```text
@set Mira/listen_tap = ^*on tap*:say Ale, five credits the mug. Pay me and it is yours.
```

The sale is an `ON_PAYMENT` hook reading the payment straight off the
action. The [`target is me`](../reference/softcode.md#guard-on-target)
guard comes first because Moss hears the same events, and inside it a
three-way split serves on 5 or more, grumbles at a short payment, and
stays silent otherwise:

```text
@set Mira/on_payment = '''
if target is me:  # Moss shares the bar; react only to coins put in MY hand
    paid = adata('amount', 0)
    if paid >= 5:
        set_attr(me, 'patron_' + enactor.id, 1)  # this drinker may now hear rumors
        say('One ale, coming up.')
        trigger('pour')
    elif paid > 0:
        say('Ale is five credits, love.')
'''
```

The pour lives in its own attribute, run by `trigger('pour')` from the
sale above. It is a plain attribute, not a `$`-command, so `@tr Mira/pour`
can test-fire it alone. It mints the mug onto the bar, describes it, and
stamps the drink command onto it from the template attribute:

```text
@set Mira/pour = '''
mug = create_obj('a mug of ale', location=here)  # here is Mira's room, the one place she may mint into
set_attr(mug, 'description', 'Cloudy town ale, still foaming.')
set_attr(mug, 'cmd_drink', V('drink_script'))  # copy the template into a live cmd_* command
pose('sets a foaming mug on the bar.')
'''
```

The template is `drink_script`. It is inert on Mira, because only `cmd_*`
attributes register as commands, so it just sits there as text she copies
onto each mug's `cmd_drink`. On the mug it is a live `$drink *` command
that heals the drinker, narrates to them and the room, and then destroys
the mug:

```text
@set Mira/drink_script = '''
$drink *:
heal(enactor, 1)
pemit(enactor, 'The ale goes down warm.')
oemit(enactor, f'{name(enactor)} drains a mug of ale.')
destroy_obj(me)
'''
```

The gossip is a rumor list plus a gated, rotating listen. The list is data,
so restocking gossip later is another `@set` and no code:

```text
@set Mira/rumors = ["They say the old mine did not close for bad air alone.", "Verity shuts her shop at nine sharp - and sleeps above it.", "Scream on Market Street and count to ten. The watch is faster."]
```

The rumor listen fires on any sentence containing "rumor". Paying patrons
get the next rumor and their own index steps forward, everyone else is
told to buy a drink first:

```text
@set Mira/listen_rumor = '''
^*rumor*:
r = V('rumors', [])
i = V('idx_' + enactor.id, 0)  # each asker has their own place in the rotation
if V('patron_' + enactor.id, 0):
    say(r[i % len(r)])
    incr('idx_' + enactor.id)
else:
    say('Ale first. A wet tongue wags easier - mine included.')
'''
```

## Try it

Give yourself pocket money and a body that can feel the ale:

```text
@set me/credits = 40
@set me/hp = 9
@set me/max_hp = 12
```

Then, at the bar:

```text
say what's on tap?     -> "Ale, five credits the mug. ..."
say any rumors?        -> "Ale first. A wet tongue wags easier..."
pay 5 to Mira          -> "One ale, coming up." and a mug lands on the bar
drink ale              -> "The ale goes down warm." (+1 HP, mug gone)
say any rumors?         -> the first rumor
say rumors             -> the second, because she remembers where you were
```

## Going further

- **Stock the taps:** make the drinks data too, a `drinks` attr of name
  to price, and have `on_payment` match `adata('amount')` against it to
  serve porter at 8 and whiskey at 12.
- **Disposition pricing:** `persuade Mira` before ordering, then have
  `on_payment` accept `5 - disposition(me, enactor)`, so charm earns
  cheaper ale (see `consider` and `persuade`, and item 71 for the stick).
- **Quest hooks:** make a rumor a dict `{"text": ..., "hook": "missing_cargo"}`
  and `pemit` a follow-up lead when the rumor carries a hook, turning bar
  gossip into a quest-discovery channel.
- **Last call:** gate the whole `on_payment` on
  [item 68](068_npc_schedule.md)'s town clock via
  `get_attr('town clock', 'hour', 12)` and refuse service after two.
