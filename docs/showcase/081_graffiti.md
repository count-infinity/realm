# 081. Graffiti

> Checklist item 81 ([now]): *$scrawl into desc_extras, room-authority writes, persistent details*

**What you'll build:** An underpass wall anyone can write on. Typing
`scrawl <text>` adds your line to the room's description for every future
looker, the concrete eventually fills up, and only the room's owner can
`scrub` it clean.

**Concepts:** `desc_extras` (the native `@detail` storage from
[room details](042_room_details.md)) written by softcode running *as the
room*, an authority boundary made explicit (who may write on whose room),
[`escape()`](../reference/softcode.md#fn-escape) for player-authored text,
a capacity cap, and details that persist because they are attributes.

## How it works

The finished wall is the underpass room itself carrying two commands and
one growing attribute. A passerby types `scrawl hi` and the room appends
their signed line to its own description, where it shows to everyone who
looks from then on and survives a reboot. This section answers three
questions: how a stranger writes on a room they do not own, why the room
sets a limit and signs the text, and how the whole thing persists for free.

### How a stranger writes on a room they do not own

Graffiti is a detail line. REALM's native detail system
([room details](042_room_details.md)) renders every `[condition, text]`
pair in an object's `desc_extras` after its description, once per viewer.
`@detail` is the builder's pen for that attribute, and it demands *control*
of the target, so a stranger cannot `@detail` your room. That refusal is
correct, and it is the whole design problem, because graffiti is by
definition writing on a wall you do not own.

The room lends its own hand instead. A `$`-command stored on the room runs
*as the room*, with the room owner's authority, so
[`set_attr`](../reference/softcode.md#fn-set_attr)`(me, 'desc_extras', ...)`
inside a `$scrawl *` command is the room writing on itself at a passerby's
request. The passerby never gains write access to `desc_extras`. They get
exactly the one sentence of influence the owner's script grants: their
text, their name signed, an empty condition so everyone sees it.

### Why the room caps the list and signs every line

Those are the owner's terms, and this build fixes three of them. There is
a ceiling of eight lines, because an unbounded player-fed list is the
classic way a database quietly fills up. Attribution is always appended, so
a scrawl is signed with [`name`](../reference/softcode.md#fn-name)`(enactor)`
whether the writer likes it or not. Cleanup is reserved to the owner,
because clearing `desc_extras` already belongs to whoever controls the
room, and `$scrub` is just the in-world spelling of that power.

The player's text is passed through
[`escape()`](../reference/softcode.md#fn-escape) on the way in, which
strips color markup so the wall stores what was typed as plain text rather
than letting a writer inject formatting codes into everyone else's look.

### Where the guard question lands here

Both commands are `$`-commands that fire on the room itself when someone in
the room types them, so neither needs a `target` guard. That guard is only
for a reactive `ON_<EVENT>` hook, which fires on every object in a room and
must screen out business that is not its own. There is no such hook in this
build. Rooms sit in the `$`-command search path, so the room carries these
commands with no separate prop object.

### How the wall persists

`desc_extras` is an ordinary attribute, so a reboot keeps the wall exactly
as tagged, the same as any other stored data. There is no decay here by
design. See Going further for a timestamp variant that fades.

## Build it

The wall is the room, so dig it, step inside, and describe the bare
concrete:

```text
@dig The Underpass = underpass, out
underpass
@desc here = Sodium light and old concrete. The long wall invites comment.
```

The pen checks the cap first, then appends one always-visible detail line
signed by the writer. It has branching logic, so it is a `'''` multi-line
block: read the room's own list, refuse if it is full, otherwise append the
escaped-and-signed row and announce the act with
[`remit`](../reference/softcode.md#fn-remit):

```text
@set here/cmd_scrawl = '''
$scrawl *:
rows = V('desc_extras') or []
if len(rows) >= 8:                      # cap the list; an unbounded player-fed attribute is a storage leak
    pemit(enactor, 'No bare concrete left. The wall is full; someone with the deed must SCRUB it.')
else:
    set_attr(me, 'desc_extras', rows + [['', f'Scrawled on the wall: "{escape(arg0)}" --{name(enactor)}']])   # '' condition shows the line to every looker
    remit(me, f'{name(enactor)} shakes a marker and writes on the wall.')
'''
```

Here [`V`](../reference/softcode.md#fn-v) reads the room's own `desc_extras`
(the executor is the room), [`escape`](../reference/softcode.md#fn-escape)
neuters markup in the typed text, and
[`pemit`](../reference/softcode.md#fn-pemit) delivers the full-wall refusal
privately to the writer.

The solvent is owner-only. It compares the enactor against the room's
[`owner`](../reference/softcode.md#fn-owner) by identity, refusing anyone
else and otherwise wiping the attribute with
[`del_attr`](../reference/softcode.md#fn-del_attr):

```text
@set here/cmd_scrub = '''
$scrub wall:
if enactor is not owner(me):            # identity check: only the room's owner scrubs
    pemit(enactor, 'Only whoever holds the deed scrubs this wall.')
else:
    del_attr(me, 'desc_extras')
    remit(me, f'{name(enactor)} scrubs the wall back to bare concrete.')
'''
```

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

Everyone who ever looks sees it, because it is part of the room now, and a
reboot keeps it. Pile on eight lines and the ninth marker finds no
concrete. The owner's `@detail here` lists the scrawls numbered, because
softcode wrote the very attribute the builder tool reads, so
`@detail/remove here = 3` moderates a single line. Then:

```text
(Kess) scrub wall     -> Only whoever holds the deed scrubs this wall.
(owner) scrub wall    -> ... scrubs the wall back to bare concrete.
look                  -> just the sodium light again
```

## Going further

- **A portable wall:** the same two commands on a `graffiti wall` *object*
  make the mechanism a prop you drop anywhere, with no room ownership
  involved, which is handy in a world where rooms belong to many builders.
- **Fading paint:** store `[condition, text, dies_at]`-style rows in a
  parallel attribute and sweep by `now()` like the
  [bulletin board](076_bulletin_boards.md), then rebuild `desc_extras` from
  the survivors.
- **Gang signs:** the condition field is live, so appending
  `['has_tag("thief")', text]` makes the scrawl visible only to viewers with
  the tag, giving per-viewer graffiti with no extra machinery.
- **Solvent as an item:** put `$scrub` on a purchasable `wire brush` whose
  script calls the room's cleaner via `eval_attr`, which turns moderation
  into an economy.
