# 081. Graffiti

> Checklist item 81 — [now] — *$scrawl into desc_extras, room-authority writes, persistent details*

**What you'll build:** An underpass wall anyone can write on:
`scrawl <text>` adds your line to the room's description for every
future looker, the concrete eventually fills up, and only the room's
owner can `scrub` it clean.

**Concepts:** `desc_extras` (the native `@detail` storage) written
**by softcode running as the room**, the authority boundary — who may
write on whose room — made explicit, `escape()` for player-authored
text, a capacity cap, and details that persist because they're
attributes.

## How it works

**Graffiti is a detail line.** REALM's native detail system
([item 42](042_room_details.md)) renders every `[condition, text]`
pair in an object's `desc_extras` after its description, per viewer.
`@detail` is the builder's pen for that attribute — and it demands
*control* of the target, so a stranger cannot `@detail` your room.
That refusal is correct, and it's the whole design problem: graffiti
is, by definition, writing on a wall you don't own.

**The room lends its own hand.** A `$`-trigger on the room runs *as
the room*, with the room owner's authority — so
`set_attr(me, 'desc_extras', ...)` inside a `$scrawl *` trigger is
the room writing on itself, at a passerby's request. The passerby
never gains write access; they get exactly the one sentence of
influence the owner's script grants: their text (escaped — players
write markup at their peril, the wall treats it as chalk, not code),
their name signed, an empty condition so everyone sees it. This is
the standing softcode answer to "how do players modify things they
don't own": *they don't — owners install verbs that do it for them,
on the owner's terms.*

**The owner's terms, in this build:** at most eight lines (unbounded
player-fed lists are the classic database leak), attribution always
appended (scrawls are signed whether you like it or not — swap in
anonymity if your game wants it), and cleanup reserved to the owner,
because `@detail/clear` already belongs to them; `$scrub` is just the
diegetic spelling.

**It persists like everything else.** `desc_extras` is an ordinary
attribute: reboots keep the wall exactly as tagged. There is no decay
here by design — see Going further for the timestamp variant.

## Build it

The wall is the room:

```text
@dig The Underpass = underpass, out
underpass
@desc here = Sodium light and old concrete. The long wall invites comment.
```

The pen — cap check, then append one always-visible detail line:

```text
@set here/cmd_scrawl = $scrawl *: rows = V('desc_extras') or []; (pemit(enactor, 'No bare concrete left. The wall is full; someone with the deed must SCRUB it.') if len(rows) >= 8 else (set_attr(me, 'desc_extras', rows + [['', f'Scrawled on the wall: "{escape(arg0)}" --{name(enactor)}']]), remit(me, f'{name(enactor)} shakes a marker and writes on the wall.')))
```

The solvent — owner only:

```text
@set here/cmd_scrub = $scrub wall: (pemit(enactor, 'Only whoever holds the deed scrubs this wall.') if enactor != owner(me) else (del_attr(me, 'desc_extras'), remit(me, f'{name(enactor)} scrubs the wall back to bare concrete.')))
```

Two triggers on the room itself — rooms are in the `$`-command search
path, so no prop object is needed.

## Try it

As any passerby:

```text
scrawl Kess was here before you.
   -> Kess shakes a marker and writes on the wall.
look
   -> The Underpass
   -> Sodium light and old concrete. The long wall invites comment.
   -> Scrawled on the wall: "Kess was here before you." --Kess
```

Everyone who ever looks sees it — it's part of the room now, and a
reboot keeps it. Pile on eight lines and the ninth marker finds no
concrete. The owner's `@detail here` lists the scrawls numbered
(softcode wrote the same attribute the builder tool reads —
`@detail/remove here = 3` moderates a single line). Then:

```text
(Kess) scrub wall     -> Only whoever holds the deed scrubs this wall.
(owner) scrub wall    -> ... scrubs the wall back to bare concrete.
look                  -> just the sodium light again
```

## Going further

- **A portable wall** — the same two triggers on a `graffiti wall`
  *object* make the mechanism a prop you drop anywhere, no room
  ownership involved — softcode-safe in a world where rooms belong
  to many builders.
- **Fading paint** — store `[condition, text, dies_at]`-style rows in
  a parallel attr and sweep by `now()` like the
  [bulletin board](076_bulletin_boards.md); rebuild `desc_extras`
  from the survivors.
- **Gang signs** — the condition field is live: append
  `['has_tag("thief")', text]` and the scrawl is *cant*, visible only
  to viewers with the tag — per-viewer graffiti, no extra machinery.
- **Solvent as an item** — put `$scrub` on a purchasable `wire brush`
  whose script calls the room's cleaner via `eval_attr` — moderation
  becomes an economy.
