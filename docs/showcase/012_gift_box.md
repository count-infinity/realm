# 012. Gift box

> Checklist item 12 — [now] — *containers, set_lock per recipient, ON_OPEN*

**What you'll build:** A ribboned gift box. Put anything inside, close
it, `address` it to someone — from that moment only *they* can open
it, and when they do, the room gets fanfare, they get the reveal, and
the box quietly becomes an ordinary container again, ready to re-wrap.

**Concepts:** the engine's container conventions (`container`,
`closed`, `put`/`give`/`open` builtins doing the work), an `on_check`
**ward** vetoing `item:on_open` by identity (`actor.id`, not a name
string), `ON_OPEN` as the celebration hook, actor-vs-room fanfare
(`pemit` + `oemit`), self-cleaning state.

Builds on the [basic container](014_basic_container.md) (wards that
`block()`) — same interception point, pointed at *who* instead of
*how much*.

## How it works

**The box is all builtins until the ribbon goes on.** `container =
true` makes `put ... in` and `get ... from` work; the `closed` tag
makes `open`/`close` work. Wrapping is literally: put the gift in,
close the lid. No script has run yet.

**The ward is an identity check.** Opening propagates a *gated*
`item:on_open` action, and the target's `on_check` script runs during
the check pass with veto power (this is the
[sack](014_basic_container.md)'s interception point). The gift ward is
three comparisons: is this an open of *me*; is the box addressed
(`for_id` set); is the actor someone else? Then `block(...)` — the
open never happens, the lid stays shut, and the would-be peeker reads
the tag's refusal. It keys on `actor.id` — captured as an *object
identity* when the box was addressed — so a prankster renaming
themselves "Kess" gains nothing. Even the giver is locked out once
the ribbon is tied; a gift, once given, keeps itself.

**`ON_OPEN` is the party.** When the *right* person opens it, the
gated action passes and the box's `on_open` attribute fires with the
opener as `enactor`. Fanfare follows the etiquette split:
`pemit(enactor, ...)` names the contents and the sender privately to
the recipient; `oemit(enactor, ...)` gives everyone else the ribbon
leaping free. Then the script deletes its own `for_*` attributes — the
ward's conditions go false, and what's left is a plain white box any
container tutorial would recognize. State that cleans itself up needs
no reset command.

**Addressing is a `$`-command with a resolver.** `$address * to *`
captures box-name and recipient-name; `get(arg1)` resolves the person
(anywhere in the world), and the script stores their id, their display
name (for the tag), and the giver's name (for the card). No such
player: a soft refusal, nothing stored.

## Build it

The box and the wrapping — builtins do the first half:

```text
@create gift box
@set gift box/container = true
drop gift box
@desc gift box = A crisp white box under a red ribbon. [[to = V('for_name', ''); result = f"The tag reads: for {to}, from {V('from_name', 'a secret admirer')}." if to else 'The ribbon hangs loose; the tag is blank.']]
@create silver locket
put silver locket in gift box
close gift box
```

The addressing command, the ward, and the fanfare:

```text
@set gift box/cmd_address = $address * to *: who = get(trim(arg1)); ok = who is not None and has_tag(who, 'player'); (set_attr(me, 'for_id', who.id), set_attr(me, 'for_name', name(who)), set_attr(me, 'from_name', name(enactor)), remit(here, f'{name(enactor)} ties the ribbon tight and pens a name on the tag.')) if ok else pemit(enactor, 'You find no one by that name to address it to.')
@set gift box/on_check = mine = atype == 'item:on_open' and target is me; to = V('for_id', ''); block(f"The ribbon is charmed shut. The tag reads: for {V('for_name', '')} only.") if mine and to and actor.id != to else None
@set gift box/on_open = to = V('for_id', ''); inside = ', '.join(name(o) for o in contents(me)); (oemit(enactor, f'The ribbon leaps free as {name(enactor)} opens the gift box!'), pemit(enactor, f"The ribbon leaps free! Inside: {inside} -- with love from {V('from_name', 'a secret admirer')}."), del_attr(me, 'for_id'), del_attr(me, 'for_name'), del_attr(me, 'from_name')) if to else None
```

## Try it

```text
address gift box to Kess
look gift box            -> The tag reads: for Kess, from Bilda.
open gift box            -> The ribbon is charmed shut. The tag reads: for Kess only.
give gift box to Kess
```

Anyone but Kess — including you, the wrapper — gets the charmed-shut
refusal and the lid stays closed. Kess opens it and reads `The ribbon
leaps free! Inside: silver locket -- with love from Bilda.` while the
room sees `The ribbon leaps free as Kess opens the gift box!`; then
`get silver locket from gift box` collects the prize. Look again: `The
ribbon hangs loose; the tag is blank.` — close it and *anyone* can
open it now. Re-wrap at will; the ward re-arms the moment `address`
writes a new name.

## Going further

- **Wrap-anything command:** `$wrap * for *` that finds the named item
  in your hands, puts it in, closes the lid, and addresses in one go —
  three builtins' worth of work, scripted.
- **Gift receipts:** on open, `create_obj` a card stamped with sender,
  contents, and `now()` — the [camera](008_camera.md)'s `desc_extras`
  trick makes it readable.
- **A ticking present:** if nobody opens it, `expire()` the box and
  let `ON_EXPIRE` deliver the fanfare to an empty room — melted cake,
  hurt feelings.
- **Tamper evidence:** the ward *sees* every blocked attempt — count
  them in an attribute and let the recipient's reveal mention "someone
  tried the ribbon 3 times."
