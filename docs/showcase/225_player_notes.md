# 225. Player-to-player notes

> Checklist item 225 ([now]): *staff annotations and player-visible profiles, notes attrs with secret/visual attr flags*

**What you'll build:** a Registry that keeps two layers of writing about a
player. Anyone may set a public **profile** that shows under their name, and
staff may attach **notes** whose contents are gated to staff and whose very
existence is announced only to staff eyes. The same `look Bob` renders
differently depending on who typed it.

**Concepts:** per-viewer `desc_extras` conditions (the
[room details](042_room_details.md) gate) for what shows on `look`; the
`secret` attribute flag, which is the only flag that closes a softcode read;
an admin-owned world-zone master writing onto players under its owner's
authority; and the staff boundary drawn with a
[`has_tag`](../reference/softcode.md#fn-has_tag) check on `admin`.

## How it works

The finished shape is one object, the Registry, holding every word ever
written about anybody, plus two rendered lines stamped onto each player it
knows about. A player's own blurb becomes a detail line everyone sees, and
the presence of staff notes becomes a second detail line only admins see,
while the note text itself never leaves the Registry. This section answers
three questions: what each layer is physically made of, why the Registry
does the writing rather than the player, and how private the private layer
really is.

### What the three layers are made of

The **public profile** is the simplest. `bio <text>` stores the blurb on the
Registry under a per-player key (`bio_<id>`), and the Registry then writes a
`desc_extras` row onto the player with an empty condition, which
[the detail engine](042_room_details.md) treats as "show this to everyone".
It renders under the player's name on any `look`, exactly like a room detail.

The **staff-only marker** uses the same list with a condition in it. When at
least one note exists, the Registry adds a second row whose condition string
is `has_tag('admin')`. Conditions are evaluated once per viewer at look time,
so a staffer sees `[staff notes: 2 on file - NOTES Bob]` and an ordinary
player sees nothing in its place. Notice that the marker carries a count and
a command to type, never any note text, because the marker is a rendered
line on a public object.

The **note contents** live in one `staff_notes` dict on the Registry, keyed
by player id, flagged `secret` with `@attr`. `secret` is the only attribute
flag that gates reading: a
[`get_attr`](../reference/softcode.md#fn-get_attr) from anyone who fails
`controls()` returns the supplied default instead of the value, so a script
or an inline `[[...]]` block on any object outside staff control reads back
its own fallback. The Registry itself reads the dict happily, because an
object always controls itself, and so does Vala, because an admin controls
everything.

### Why the Registry writes onto the player

Stamping a line onto somebody means
[`set_attr`](../reference/softcode.md#fn-set_attr) on an object you do not
own, and a player is nobody's property. The Registry gets there by being
**admin-owned**: an owned object acts with its owner's authority, so a
Registry owned by staff reaches players, the same arrangement the
[Herald](220_titles_badges.md) uses for titles.

Both layers therefore go through one shared routine, `render`, invoked with
[`eval_attr`](../reference/softcode.md#fn-eval_attr). It runs with the
caller's authority and, because the caller is the Registry, `me` inside
`render` is still the Registry, so
[`V('staff_notes', ...)`](../reference/softcode.md#fn-v) there reads the
sealed dict normally. `render` rebuilds both managed rows from scratch: it
remembers the exact text it wrote last time in `bioline_<id>` and
`noteline_<id>`, filters those two strings out of the player's current
`desc_extras`, and appends the freshly computed versions. That keeps each
layer at exactly one row no matter how many times it runs, and it leaves
detail rows written by other systems untouched.

### How private the private layer really is

Three separate gates protect the notes, and it is worth being exact about
what each one covers.

- The **`notes` verb** refuses non-staff outright, so the ordinary way to
  ask for the text fails for everyone but admins.
- The **`secret` flag** closes the softcode path. Stock REALM gates `@eval`
  and `@create` behind the builder role, so an ordinary player has no
  scripting surface to attack from in the first place; the flag's real
  audience is every *other* builder's gadgets. A second builder running
  `get_attr(get('the Registry'), 'staff_notes', 'BLOCKED')` receives
  `BLOCKED`, because the Registry is owned by staff and ownership is what
  `controls()` asks about.
- The **per-viewer condition** hides the marker line on `look`, so an
  ordinary player looking at Bob has no hint that a file exists.

What those gates leave open is the plain `examine` command. It prints the
whole attribute table of any object in the room or in your inventory without
consulting the `secret` flag, so a player standing next to the Registry can
read `staff_notes` in full, and `examine Bob` shows his raw `desc_extras`
list including the admin-conditioned marker row. Keep the Registry in a
staff-only room and treat that room's lock as the outermost gate; the flag
protects the scripting surface, the room protects the object. See
[Engine gaps](#engine-gaps).

## Build it

Start with the office and the Registry itself. The room is tagged into the
`world` zone and the Registry is made its master, which is how the four
verbs below reach players standing in any `zone:world` room rather than only
this one (there is no master room in REALM yet, so a world zone is the
stand-in). The builder here is staff, so the Registry ends up admin-owned,
which is what gives it the authority to write onto players.

```text
@dig The Records Office = records, out
records
@zone here = world
@create the Registry
drop the Registry
@desc the Registry = Rows of sealed files. BIO <text> sets your public profile; PROFILE <name> reads someone's. Staff: NOTE <name> = <text>, NOTES <name>.
@zone/master the Registry = world
```

Declare the note store as an empty dict and seal it in the same breath. The
value stays on one line because it is data rather than code, and `@set`
reads values as JSON, so a dict or list literal needs JSON punctuation.

```text
@set the Registry/staff_notes = {}
@attr the Registry/staff_notes = secret
```

Now the shared render routine, which takes a player id and rewrites both
managed rows on that player. It reads the blurb and the note count, recalls
the two strings it stamped last time, drops exactly those from the player's
detail list, builds the replacements, and writes the list back before
recording the new strings for next time.

```text
@set the Registry/render = '''
pl = get('#' + str(arg0))
blurb = V('bio_' + str(arg0), '')
notes = V('staff_notes', {}).get(str(arg0), [])
# The two strings this routine stamped last time, so the rewrite removes its
# own rows and leaves detail lines written by anything else alone.
mine = [t for t in [V('bioline_' + str(arg0), ''), V('noteline_' + str(arg0), '')] if t]
keep = [row for row in (get_attr(pl, 'desc_extras') or []) if len(row) < 2 or str(row[1]) not in mine]
bl = f'Profile: {blurb}' if blurb else ''
nl = f'[staff notes: {len(notes)} on file - NOTES {name(pl)}]' if notes else ''
add = []
if bl:
    add.append(['', bl])                    # empty condition: shown to everyone
if nl:
    add.append(["has_tag('admin')", nl])    # re-evaluated for each viewer on look
set_attr(pl, 'desc_extras', keep + add)
set_attr(me, 'bioline_' + str(arg0), bl)
set_attr(me, 'noteline_' + str(arg0), nl)
result = 1
'''
```

The player-facing pair comes next. `bio` writes the enactor's own blurb and
re-renders them, passing the text through
[`escape`](../reference/softcode.md#fn-escape) so that color markup someone
types into their profile is stored as literal characters rather than
rendering as color. `profile` reads anyone's blurb straight out and needs no
render at all.

```text
@set the Registry/cmd_bio = '''
$bio *:
blurb = trim(arg0)
if blurb:
    # escape() neutralizes color markup typed into player-supplied text.
    set_attr(me, 'bio_' + enactor.id, escape(blurb))
    eval_attr(me, 'render', enactor.id)
    pemit(enactor, 'Your public profile is updated.')
else:
    pemit(enactor, 'Type BIO <your public bio>.')
'''
@set the Registry/cmd_profile = '''
$profile *:
pl = get(trim(arg0))
if pl is not None and has_tag(pl, 'player'):
    blurb = V('bio_' + pl.id, '')
    pemit(enactor, name(pl) + ' profile: ' + (blurb if blurb else '(they have not written one)'))
else:
    pemit(enactor, 'No such player.')
'''
```

Finally the staff pair. `note` appends to the sealed dict, keeping the last
twenty rows per player, and re-renders so the marker's count stays honest;
`notes` prints the rows to staff only. Each verb checks the `admin` tag
first so a refusal names the real reason.

```text
@set the Registry/cmd_note = '''
$note * = *:
pl = get(trim(arg0))
txt = trim(arg1)
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff annotate players.')
elif pl is None or not has_tag(pl, 'player'):
    pemit(enactor, 'No such player.')
elif not txt:
    pemit(enactor, 'Type NOTE <player> = <what staff should know>.')
else:
    # V reads the secret attr here because an object controls itself.
    rows = dict(V('staff_notes', {}) or {})
    rows[pl.id] = (rows.get(pl.id, []) + [name(enactor) + ': ' + escape(txt)])[-20:]
    set_attr(me, 'staff_notes', rows)
    eval_attr(me, 'render', pl.id)
    pemit(enactor, 'Staff note added to ' + name(pl) + '.')
'''
@set the Registry/cmd_notes = '''
$notes *:
pl = get(trim(arg0))
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff read notes.')
elif pl is None or not has_tag(pl, 'player'):
    pemit(enactor, 'No such player.')
else:
    rows = V('staff_notes', {}).get(pl.id, [])
    pemit(enactor, 'Staff notes on ' + name(pl) + ':')
    for r in rows:
        pemit(enactor, '  ' + r)
    if not rows:
        pemit(enactor, '  (nothing on file)')
'''
```

## Try it

Bob writes a public profile, and anyone reading him sees it:

```text
> bio Freelance salvager. Ask about the Kessari job.          (as Bob)
Your public profile is updated.

> look Bob                                                    (as Cass)
Bob
Profile: Freelance salvager. Ask about the Kessari job.

> profile Bob                                                 (as Cass)
Bob profile: Freelance salvager. Ask about the Kessari job.
```

Now Vala, who carries the `admin` tag, attaches a note. Watch the *same*
`look Bob` produce two different renderings:

```text
> note Bob = Flagged for the airlock griefing on Deck 3. Watching.   (as Vala)
Staff note added to Bob.

> look Bob                                                    (as Vala)
Bob
Profile: Freelance salvager. Ask about the Kessari job.
[staff notes: 1 on file - NOTES Bob]

> look Bob                                                    (as Cass)
Bob
Profile: Freelance salvager. Ask about the Kessari job.
```

That missing third line is the whole point: Cass received no marker, because
the row's `has_tag('admin')` condition was evaluated against Cass and came
back false. The two results worth confirming deliberately are that one, and
the read gate below.

```text
> notes Bob                                                   (as Vala)
Staff notes on Bob:
  Vala: Flagged for the airlock griefing on Deck 3. Watching.

> notes Bob                                                   (as Cass)
Only staff read notes.
```

For the read gate itself you need somebody with a scripting prompt but
without staff authority, so run the last check as Dex, a builder who lacks
the `admin` tag. `@eval` is builder-gated, which is why Cass has no way to
try this at all:

```text
> @eval result = get_attr(get('the Registry'), 'staff_notes', 'BLOCKED')   (as Dex)
=> 'BLOCKED'

> look Bob                                                    (as Dex)
Bob
Profile: Freelance salvager. Ask about the Kessari job.
```

Dex wrote a perfectly valid read and got his own fallback back, and his
`look` shows the profile with no marker, because building power and staff
standing are separate things here. Finally, type `bio` again as Bob with new
text and look at him once more to confirm the profile line is replaced
rather than duplicated, since `render` filters out the string it stamped
previously.

## Engine gaps

- The `secret` flag is honored by the softcode readers
  (`get_attr`/`V`/`eval_attr`) but **not** by the player-facing `examine`
  command, which prints `target.db.all()` for any object in reach with no
  flag filter at all (`realm/commands/builtin/look.py`). The builder tool
  `@examine` does the same. Both `realm/core/attrflags.py` and the world
  management guide describe `secret` as covering `@examine`, so the intended
  behavior is clear and the filter is simply absent. Until it lands, a
  `secret` attribute is private against scripts and public against anyone
  who can stand next to the object.
- There is no per-attribute gate on `desc_extras` rows themselves, so
  `examine <player>` reveals the raw condition/text pairs, marker line
  included. A viewer-filtered attribute dump would close both holes at once,
  and it would also give the `visual` flag something to mean: `examine`
  prints visual-flagged attributes in their own section and then prints
  every attribute again below, so flagging one `visual` changes nothing that
  a reader would notice.

## Going further

- **Player-visible endorsements.** Add a third layer with
  `endorse <name> = <text>` writing to a public notes list with no `secret`
  flag and a plain `desc_extras` row, so players leave references on each
  other and the object becomes a reputation wall.
- **Notes that age out.** Stamp each staff row with
  [`now()`](../reference/softcode.md#fn-now) and let a `script_ticker` drop
  rows older than ninety days, so a warning stops following someone forever.
- **Cross-link to petitions.** Resolving a [petition](224_petitions.md) can
  append a staff note such as "resolved ticket #12", which builds a
  per-player history out of the queue for free.
- **A sightings log.** An
  [`ON_CONNECT`](../reference/softcode.md#lifecycle-hooks) hook on the
  Registry, which hears connections from every `zone:world` room, can append
  a timestamped "last seen" row to a second `secret` attribute and give
  staff a login trail without touching the session layer.
