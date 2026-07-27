# 175. Player housing customization

> Checklist item 175 ([now]): *delegated building with guardrails: ownership, length caps, furniture whitelist*

**What you'll build:** a rowhouse a player can `claim`, then `decorate`
with their own description and `furnish` from an approved list, while the
guardrails hold: only the owner may change it, descriptions have a length
cap, furnishings come from a whitelist, and the only verbs on offer are the
three safe ones. Delegated building, done safely. A builder places the
house, and residents need no permission of their own.

**Concepts:** the **delegated-authority boundary** (a builder-owned room
whose verbs run with the owner's authority, so the *script* is the security
policy), ownership recorded in an `owner_id` attribute, `desc_extras` for the
resident's description (the slot softcode may write), and guardrails (a
length cap and a furniture whitelist) enforced inside the verbs.

## How it works

A player walks into an empty rowhouse, types `claim`, and it becomes theirs:
now they may rewrite its description and set out furniture, and no one else
may touch it. Yet the resident never owns the room and holds no building
permission. The whole system is three `$`-commands sitting on the room, and
the finished shape is worth holding before the parts. The room is owned by a
builder, each verb runs with that owner's authority, and the verb's own code
decides exactly what a resident may do. This section answers who holds the
power, where ownership is recorded, and how each guardrail is enforced.

### Who actually holds the power?

**The room is builder-owned; the script is the policy.** Every `$`-verb on
the house runs as the house, with its owner's (the builder's) authority,
which is what lets a mortal's `furnish` spawn an object and `decorate`
rewrite the room. The resident never gains authority over the room; they get
exactly the powers the verbs choose to grant. So every mutating verb opens
with the same gate, `enactor.id == [V](../reference/softcode.md#fn-v)('owner_id')`,
and that gate *is* the ownership system. This is the
[player-shop](088_player_shops.md) boundary applied to a home: the enactor is
untrusted input, the executor's owner is the power, and the script is the
policy.

These verbs are `$`-commands, matched only when a resident types the word, so
unlike a reactive [`ON_<EVENT>` hook](../reference/softcode.md#lifecycle-hooks)
(which fires on every object in the room and needs a
[`target` guard](../reference/softcode.md#guard-on-target)) they simply run
for whoever typed them, and the `owner_id` gate is the only check they need.

### What stops a resident from abusing the tools?

Handing players building tools without limits is how you get 40 KB
descriptions and a chair named `</script>`. So each verb carries its own
guardrail:

- **Ownership:** `claim` stamps `owner_id`; every other verb checks it.
- **Length cap:** `decorate` refuses text over `decor_max`, and
  [`escape`](../reference/softcode.md#fn-escape)s what it stores so a
  player's color markup renders as literal text rather than recoloring the
  room.
- **Whitelist:** `furnish` only spawns names in `furniture_ok`, so there is
  no arbitrary object creation and no naming a "chair" something hostile.
- **No script or lock editing:** the resident is only ever offered
  `claim`/`decorate`/`furnish`. There is no verb that sets an arbitrary
  attribute, a trigger, or a lock, so the surface *is* the sandbox. The
  resident holds no control of the room either, so a direct `@set here/...`
  from them answers "Permission denied."

### Where does the resident's description go?

**Softcode writes `desc_extras`, not the description slot.** A script's
`set_attr(me, 'description', ...)` writes a plain `description` attribute, but
`look` renders the room's own description *field*, which only `@desc` sets, so
that write never shows. The resident's decoration therefore lands in
`desc_extras`, a list of `[label, text]` pairs that `look` appends beneath the
room description and that softcode is free to write. Each furnishing is also
tagged `safe` with [`add_tag`](../reference/softcode.md#fn-add_tag), so a stray
`@destroy` aimed at the piece itself is refused until someone clears the tag.

## Build it

Build the shell as a builder, since placing the room and running the
delegated verbs both draw on the owner's building authority. Dig the rowhouse
off the street and step inside:

```text
@dig Rowhouse 12 = door, street
door
```

Set the two limits the verbs read, the furniture whitelist and the
description length cap. Both are plain data, so they stay single-line `@set`s;
a `'''` block would store the list as a raw string and break the membership
test:

```text
@set here/furniture_ok = ["chair", "table", "rug", "lamp", "bed"]
@set here/decor_max = 80
```

`claim` is first come, first served. If `owner_id` is already set it turns the
caller away with [`pemit`](../reference/softcode.md#fn-pemit); otherwise it
stamps the caller as owner with [`set_attr`](../reference/softcode.md#fn-set_attr)
and records their [`name`](../reference/softcode.md#fn-name) for the furnish
announcement:

```text
@set here/cmd_claim = '''
$claim:
if V('owner_id'):
    pemit(enactor, 'This home already has an owner.')
else:
    set_attr(me, 'owner_id', enactor.id)
    set_attr(me, 'owner_name', name(enactor))
    pemit(enactor, 'You take the keys. Try: decorate <text>, furnish <item>.')
'''
```

`decorate` is owner-only and length-capped. It trims the argument with
[`trim`](../reference/softcode.md#fn-trim), checks the caller against
`owner_id`, refuses anything longer than `decor_max`, then stores the escaped
text in `desc_extras`:

```text
@set here/cmd_decorate = '''
$decorate *:
if enactor.id != V('owner_id'):
    pemit(enactor, 'This is not your home.')
else:
    txt = trim(arg0)
    mx = V('decor_max', 80)
    if len(txt) > mx:
        pemit(enactor, 'Too long, keep it under ' + str(mx) + ' characters.')
    else:
        # look renders desc_extras, so decoration lands here, not the description slot
        set_attr(me, 'desc_extras', [['', escape(txt)]])
        pemit(enactor, 'You redecorate.')
'''
```

`furnish` is owner-only and whitelist-gated. A name outside `furniture_ok` is
refused; an allowed one is minted with
[`create_obj`](../reference/softcode.md#fn-create_obj), tagged `safe`, and
announced to the room with [`remit`](../reference/softcode.md#fn-remit):

```text
@set here/cmd_furnish = '''
$furnish *:
if enactor.id != V('owner_id'):
    pemit(enactor, 'This is not your home.')
else:
    item = trim(arg0).lower()
    wl = V('furniture_ok', [])
    if item not in wl:
        pemit(enactor, 'Not an allowed furnishing. Try: ' + ', '.join(wl))
    else:
        piece = create_obj('a ' + item, tags=['thing', 'furniture'], location=me)
        add_tag(piece, 'safe')  # a stray @destroy of the piece is refused while tagged
        remit(me, V('owner_name', 'Someone') + ' sets out a ' + item + '.')
'''
```

Step back out to the street and hand over the keys:

```text
street
```

## Try it

As a resident (Cass), standing in Rowhouse 12:

```text
> claim
You take the keys. Try: decorate <text>, furnish <item>.

> decorate A brass lamp warms the reading nook.
You redecorate.

> furnish chair
Cass sets out a chair.

> furnish jetpack
Not an allowed furnishing. Try: chair, table, rug, lamp, bed
```

Now watch the guardrails hold. A `decorate` of 100 characters answers "Too
long, keep it under 80 characters."; a second `claim` (by anyone) answers
"This home already has an owner."; and another player standing in Cass's home
gets "This is not your home." from every mutating verb, the same object and
the same verbs, but a different enactor and a different answer:

```text
> decorate xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
Too long, keep it under 80 characters.

(as another player, teleported in)
> decorate I live here now
This is not your home.
```

There is simply no verb that edits a script or a lock, so there is nothing to
abuse.

## Going further

- **Rent and repossession:** borrow the [player-shop](088_player_shops.md)
  tick, a `script_ticker` that docks rent and clears `owner_id` when the
  resident falls behind, sweeping their furniture back to them.
- **Move furniture:** a `rearrange` verb that renames or destroys a
  furnishing the resident placed, gated on the same `owner_id`.
- **Bigger homes:** claim a whole zone instead of a room, and let
  `decorate`/`furnish` take a room argument. The gate stays one `owner_id`
  check.
- **Transfer:** a `bequeath <player>` verb that reassigns `owner_id`. The
  delegated script reassigns ownership for a resident who has no `@chown` of
  their own.
