# 175. Player housing customization

> Checklist item 175 — [now] — *delegated building with guardrails: ownership, length caps, furniture whitelist*

**What you'll build:** a rowhouse a player can `claim`, then `decorate`
with their own description and `furnish` from an approved list — while the
guardrails hold: only the owner may change it, descriptions have a length
cap, furnishings come from a whitelist, and there's no way in for editing
scripts or locks. Delegated building, safely. (Builder permission to
*place* the house; residents need none.)

**Concepts:** the **delegated-authority boundary** (an admin-owned room
whose verbs run with the admin's authority, so the *script* is the
security policy), ownership by an `owner_id` attribute, `desc_extras` for
the resident's description (the slot softcode may write), and guardrails —
length caps and a furniture whitelist — enforced in the verbs.

## How it works

**The room is admin-owned; the script is the policy.** Every `$`-verb on
the house runs **as the house, with its owner's (admin's) authority** —
which is what lets a mortal's `furnish` spawn an object and `decorate`
rewrite the room. The resident never gains authority over the room; they
get exactly the powers the verbs choose to grant. So every mutating verb
opens with the same gate — `enactor.id == get_attr(me, 'owner_id')` — and
that gate *is* the ownership system. This is the
[player-shop](088_player_shops.md) boundary applied to a home: the
enactor is untrusted input, the executor's owner is the power, the script
is the policy.

**Guardrails are the whole point.** Handing players building tools
without limits is how you get 40 KB descriptions and a chair named
`</script>`. So:

- **Ownership:** `claim` stamps `owner_id`; every other verb checks it.
- **Length cap:** `decorate` refuses text over `decor_max`, and `escape()`s
  what it stores so markup in player prose can't leak.
- **Whitelist:** `furnish` only spawns names in `furniture_ok` — no
  arbitrary object creation, no naming a "chair" something hostile.
- **No script/lock editing:** the resident is only ever offered
  `claim`/`decorate`/`furnish`. There is no verb that sets an arbitrary
  attribute, a trigger, or a lock — the surface *is* the sandbox. (The
  resident can't `@set` the room either: they don't own it, and `@set`
  requires control.)

**Softcode sets `desc_extras`, not the description slot.** As elsewhere,
scripts can't write the render-`description` field, so the resident's
decoration lands in `desc_extras` — which `look` appends and softcode may
write. Furnishings are spawned with a `safe` attribute flag so a later
`@wipe` of the room won't sweep them away.

## Build it

The house, its limits, and the whitelist (as an admin — the delegation
depends on the room being admin-owned):

```text
@dig Rowhouse 12 = door, street
door
@set here/furniture_ok = ["chair", "table", "rug", "lamp", "bed"]
@set here/decor_max = 80
```

`claim` — first come, first served, and only once:

```text
@set here/cmd_claim = $claim: pemit(enactor, 'This home already has an owner.') if get_attr(me, 'owner_id') else (set_attr(me, 'owner_id', enactor.id), set_attr(me, 'owner_name', name(enactor)), pemit(enactor, 'You take the keys. Try: decorate <text>, furnish <item>.'))
```

`decorate` — owner-only, length-capped, escaped, written to `desc_extras`:

```text
@set here/cmd_decorate = $decorate *: txt = trim(arg0); mx = get_attr(me, 'decor_max', 80); ok = enactor.id == get_attr(me, 'owner_id'); pemit(enactor, 'This is not your home.') if not ok else (pemit(enactor, 'Too long — keep it under ' + str(mx) + ' characters.') if len(txt) > mx else (set_attr(me, 'desc_extras', [['', escape(txt)]]), pemit(enactor, 'You redecorate.')))
```

`furnish` — owner-only, whitelist-gated, spawned `safe`:

```text
@set here/cmd_furnish = $furnish *: item = trim(arg0).lower(); wl = get_attr(me, 'furniture_ok', []); ok = enactor.id == get_attr(me, 'owner_id'); pemit(enactor, 'This is not your home.') if not ok else (pemit(enactor, 'Not an allowed furnishing. Try: ' + ', '.join(wl)) if item not in wl else (set_attr(create_obj('a ' + item, tags=['thing', 'furniture'], location=me), 'safe', True), remit(me, get_attr(me, 'owner_name', 'Someone') + ' sets out a ' + item + '.')))
```

Step back out and hand the street the keys:

```text
street
```

## Try it

As a resident (Cass), standing in Rowhouse 12:

```text
claim               -> You take the keys. Try: decorate <text>, furnish <item>.
decorate A brass lamp warms the reading nook.
                    -> You redecorate.
furnish chair       -> Cass sets out a chair.
furnish jetpack     -> Not an allowed furnishing. Try: chair, table, rug, lamp, bed
```

Now watch the guardrails hold: `decorate` with 100 characters answers
"Too long — keep it under 80 characters."; and another player standing in
Cass's home gets "This is not your home." from every verb — same object,
same verbs, different enactor, different answer. There is simply no verb
that edits a script or a lock, so there's nothing to abuse.

## Going further

- **Rent and repossession:** borrow the [player-shop](088_player_shops.md)
  tick — a `script_ticker` that docks rent and clears `owner_id` when the
  resident can't pay, sweeping their `safe` furniture back to them.
- **Move furniture:** a `rearrange` verb that renames or `destroy_obj`s a
  furnishing the resident placed (gated on the same `owner_id`).
- **Bigger homes:** claim a whole zone instead of a room, and let
  `decorate`/`furnish` take a room argument — the gate stays one
  `owner_id` check.
- **Transfer:** a `bequeath <player>` verb that reassigns `owner_id` — the
  admin-authority script does what the resident's `@chown` never could.
