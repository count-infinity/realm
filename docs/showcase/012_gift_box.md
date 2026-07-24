# 012. Gift box

> Checklist item 12 ([now]): *containers, set_lock per recipient, ON_OPEN*

**What you'll build:** A ribboned gift box. Put anything inside, close it,
`address` it to someone, and from that moment only *they* can open it. When
they do, they get the reveal, the room gets fanfare, and the box quietly
becomes an ordinary container again, ready to re-wrap.

**Concepts:** the engine's container conventions (the `container` and
`closed` tags, with the `put`/`give`/`open` builtins doing the work), an
`on_check` **ward** vetoing `item:on_open` by identity (`actor.id`, not a
name string), [`ON_OPEN`](../reference/softcode.md#lifecycle-hooks) as the
celebration hook, fanfare split between the opener and the scene
([`pemit`](../reference/softcode.md#fn-pemit) plus
[`remit`](../reference/softcode.md#fn-remit) to
[`loc(enactor)`](../reference/softcode.md#fn-loc)), and self-cleaning state.

Builds on the [basic container](014_basic_container.md) (wards that
[`block()`](../reference/softcode.md#event-data-namespace)): the same
interception point, pointed at *who* instead of *how much*.

## How it works

A gift has three moments, and each maps onto a different engine surface:
builtins do the wrapping, a ward refuses the wrong hands before the lid can
move, and an `ON_OPEN` hook throws the party after it has. The addressing
command is the fourth piece, the one that arms the ward.

**The box is all builtins until the ribbon goes on.** Tag a thing
`container` and the stock commands do the rest: `put ... in` and
`get ... from` work, and `open`/`close` flip a `closed` tag (state lives in
tags here, not attributes). Wrapping is literally: put the gift in, close
the lid. No script has run yet.

**The ward is an identity check.** Opening propagates a *gated*
`item:on_open` action, and the box's `on_check` script runs during the
permission pass with veto power, seeing the world *before* the effect
([action phases](../design/action-phases.md)). This is the
[basic container](014_basic_container.md)'s interception point. The gift
ward is three comparisons: is this an open of *me*; is the box addressed
(`for_id` set); is the actor someone else? Then `block(reason)`: the open
never happens, the lid stays shut, and the would-be peeker reads the tag's
refusal as the whole answer. The ward keys on `actor.id`, compared against
the id captured when the box was addressed, so a prankster renaming
themselves "Kess" gains nothing. Even the giver is locked out once the
ribbon is tied; a gift, once given, keeps itself. One design note: a ward's
namespace is read-only plus the decision verbs, so it can refuse but never
act, which is why the celebration lives in the next hook over.

**`ON_OPEN` is the party.** The hook fires in the reaction pass, *after*
the effect, and only when the effect ran: by the time this script executes,
the lid is already off
([`has_tag(me, 'closed')`](../reference/softcode.md#fn-has_tag) is False)
and the reveal is certain. Two placement facts follow. First, an
`ON_<EVENT>` hook fires on
every object in the room, not only the one acted on, so the script opens
with `if target is me:` (see
[Guard on `target`](../reference/softcode.md#guard-on-target)); unguarded,
someone opening a packing crate beside the box would spill the private
reveal to the wrong person and unwrap the gift. Second, a gift is usually
opened in the recipient's hands, which means `loc(me)` is a *person*, not a
room. The [slot machine](001_slot_machine.md)'s room-side voice,
[`oemit`](../reference/softcode.md#fn-oemit), announces to the scripted
object's own room, so from inside a held box it misses the scene entirely;
the fanfare goes to `loc(enactor)` instead, the room where the opener
stands, with `remit`, while `pemit(enactor, ...)` names the contents and
the sender privately. Then the script deletes its own `for_*` attributes,
the ward's conditions go false, and what is left is a plain white box the
[basic container](014_basic_container.md) tutorial would recognize. State
that cleans itself up needs no reset command.

**Addressing is a `$`-command with a resolver.** `$address * to *` captures
the box name and the recipient name;
[`get(arg1)`](../reference/softcode.md#fn-get) resolves the person by name,
searching locally and then the whole world, and `has_tag` confirms it found
a player. The script stores their id for the ward, their display name for
the tag, and the giver's name for the card. No such player: a soft refusal,
and nothing is stored.

## Build it

The scripts here are `'''` multi-line blocks: end the `@set` line with
`'''`, write the body as ordinary indented softcode, and close with a line
of just `'''` (see
[multi-line input](../guides/world-management.md#multi-line-input-heredocs)).

**The box.** Create it, tag it a container, and give it a living face: the
`[[...]]` block reads the tag data fresh at every look with
[`V`](../reference/softcode.md#fn-v), so one description covers blank,
addressed, and re-wrapped states:

```text
@create gift box
@tag gift box = container
drop gift box
@desc gift box = A crisp white box under a red ribbon. [[to = V('for_name', ''); result = f"The tag reads: for {to}, from {V('from_name', 'a secret admirer')}." if to else 'The ribbon hangs loose; the tag is blank.']]
```

**The wrapping.** Builtins do all of it, and no script has run yet:

```text
@create silver locket
put silver locket in gift box
close gift box
```

**The addressing command.** Resolve the recipient, then either store the
three attributes ([`set_attr`](../reference/softcode.md#fn-set_attr): the
id the ward will check, plus the two names the tag shows) and let the room
watch the ribbon tied, or refuse softly:

```text
@set gift box/cmd_address = '''
$address * to *:
who = get(trim(arg1))
if who is not None and has_tag(who, 'player'):
    set_attr(me, 'for_id', who.id)  # store the id: names can change, ids cannot
    set_attr(me, 'for_name', name(who))
    set_attr(me, 'from_name', name(enactor))
    remit(here, f'{name(enactor)} ties the ribbon tight and pens a name on the tag.')
else:
    pemit(enactor, 'You find no one by that name to address it to.')
'''
```

([`trim`](../reference/softcode.md#fn-trim) strips stray spaces from the
captured name, and [`name`](../reference/softcode.md#fn-name) reads display
names.)

**The ward.** Three comparisons and a veto. `mine` narrows to "an open, of
me" (the [`atype`](../reference/softcode.md#event-data-namespace) and
`target` names describe the in-flight action); an unaddressed box blocks
nothing; anyone whose id is not the stored one is refused:

```text
@set gift box/on_check = '''
mine = atype == 'item:on_open' and target is me
to = V('for_id', '')
if mine and to and actor.id != to:
    block(f"The ribbon is charmed shut. The tag reads: for {V('for_name', '')} only.")
'''
```

**The fanfare.** Guard first, then read the contents with
[`contents`](../reference/softcode.md#fn-contents), announce to the scene,
reveal privately, and clear the address with
[`del_attr`](../reference/softcode.md#fn-del_attr). The deletes come last
so the reveal line above them can still read `from_name`:

```text
@set gift box/on_open = '''
if target is me:  # ON_OPEN fires on every object in the room, so guard it
    to = V('for_id', '')
    if to:
        inside = ', '.join(name(o) for o in contents(me))
        remit(loc(enactor), f'The ribbon leaps free as {name(enactor)} opens the gift box!')  # the box may be in the opener's hands, so loc(enactor), not loc(me), is the scene
        pemit(enactor, f"The ribbon leaps free! Inside: {inside} -- with love from {V('from_name', 'a secret admirer')}.")
        del_attr(me, 'for_id')
        del_attr(me, 'for_name')
        del_attr(me, 'from_name')
'''
```

## Try it

Wrap, address, and fail to peek (everyone but Kess gets the refusal, you
included):

```text
> address gift box to Kess
Bilda ties the ribbon tight and pens a name on the tag.

> look gift box
gift box
A crisp white box under a red ribbon. The tag reads: for Kess, from Bilda.
It is closed.

> open gift box
The ribbon is charmed shut. The tag reads: for Kess only.

> get gift box
You pick up a gift box.

> give gift box to Kess
You give a gift box to Kess.
```

Kess, box in hand:

```text
> open gift box
The ribbon leaps free as Kess opens the gift box!
The ribbon leaps free! Inside: silver locket -- with love from Bilda.
You open the gift box.

> get silver locket from gift box
You pick up a silver locket.
```

The first line is the `remit` reaching the whole scene, the opener
included: bystanders read it too, alongside the engine's own `Kess opens
the gift box.` The second line is the `pemit`, hers alone. Look again and
the tag is blank (`The ribbon hangs loose; the tag is blank.`), so close it
and *anyone* can open it now. Re-wrap at will, since the ward re-arms the
moment `address` stores a new name; and `address gift box to Zanzibar`
(no such player) just answers `You find no one by that name to address it
to.`

## Going further

- **Wrap-anything command:** `$wrap * for *` that finds the named item in
  your hands, puts it in, closes the lid, and addresses in one go: three
  builtins' worth of work, scripted.
- **Gift receipts:** on open,
  [`create_obj`](../reference/softcode.md#fn-create_obj) a card stamped
  with sender, contents, and [`now()`](../reference/softcode.md#fn-now);
  the [camera](008_camera.md)'s `desc_extras` trick makes it readable.
- **A ticking present:** if nobody opens it in time,
  [`expire()`](../reference/softcode.md#fn-expire) the box and let
  [`ON_EXPIRE`](../reference/softcode.md#lifecycle-hooks) deliver the
  fanfare to an empty room: melted cake, hurt feelings.
- **A charm that knows the peeker:** a ward is decision-only, so it cannot
  keep a tally, but its refusal is an f-string with the action's names
  bound, and the tag can single out whoever it caught:
  `block(f"The ribbon tightens under {name(actor)}'s fingers. Not yours.")`.
