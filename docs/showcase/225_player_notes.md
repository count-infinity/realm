# 225. Player-to-player notes

> Checklist item 225 — [now] — *public profiles + secret staff notes, layered per-viewer visibility, secret-flagged ledger*

**What you'll build:** a Registry with two layers of writing about a
player. Anyone can set a public **profile** that shows under their name;
staff can attach private **notes** that only staff can read — and that
only *reveal their existence* to staff, invisibly to everyone else. The
same `look` shows different things to different eyes.

**Concepts:** **layered visibility** built from two native mechanisms —
per-viewer `desc_extras` **conditions** (the [room details](042_room_details.md)
gate) for what shows on `look`, and a **`secret`-flagged attribute** (the
one attr flag that blocks reads) for the notes' contents; a public-profile
line vs. a staff-only marker line on the same player; and the staff/player
boundary drawn with an `admin`-tag check.

## How it works

**Three visibility layers, each a real engine feature.**

1. **Public profile** — `bio <text>` writes the player's own blurb, which
   the Registry renders as a plain `desc_extras` line (empty condition =
   everyone). It shows under the player's name on any `look`, exactly like
   a [room detail](042_room_details.md).
2. **Staff-only marker** — when staff notes exist, the Registry adds a
   *second* `desc_extras` line whose condition is `has_tag('admin')`. The
   detail engine evaluates that per viewer, so a staffer looking at the
   player sees "[staff notes: 2 on file]" and an ordinary player sees
   nothing there. Same object, same command, different output by viewer —
   the per-viewer detail machinery doing precisely what it's for.
3. **Secret contents** — the notes themselves live in a single
   `staff_notes` dict on the Registry, **flagged `secret` with `@attr`**.
   `secret` is the one flag that closes reads: a non-controller's
   `get_attr` returns the default, so no player's script or inline block
   can fish the notes out — only the Registry (and staff, who control it)
   can read them, and the `notes` verb gates the display on the `admin`
   tag as well.

**Why the Registry writes onto the player.** Rendering a profile line onto
someone means `set_attr` on a player you don't own — so the Registry is
admin-owned and acts with its owner's authority (the
[titles](220_titles_badges.md) convention). A managed-line rewrite (track
the previous text, filter it out, re-add) keeps each layer to exactly one
line, the same discipline the Herald uses.

## Build it

A world-zone office and the Registry; declare the notes store and seal it
`secret` up front:

```text
@dig The Records Office = records, out
records
@zone here = world
@create the Registry
drop the Registry
@desc the Registry = Rows of sealed files. BIO <text> sets your public profile; PROFILE <name> reads someone's. Staff: NOTE <name> = <text>, NOTES <name>.
@zone/master the Registry = world
@set the Registry/staff_notes = {}
@attr the Registry/staff_notes = secret
```

The shared render routine — rewrite the player's public line and the
staff-only marker, dropping the prior versions of each:

```text
@set the Registry/render = pl = get('#' + str(arg0)); bio = V('bio_' + str(arg0), ''); notes = (V('staff_notes', {}) or {}).get(str(arg0), []); ob = V('bioline_' + str(arg0), ''); onl = V('noteline_' + str(arg0), ''); keep = [p for p in (get_attr(pl, 'desc_extras') or []) if not (len(p) > 1 and (str(p[1]) == ob or str(p[1]) == onl))]; bl = f'Profile: {bio}' if bio else ''; nl = f'[staff notes: {len(notes)} on file - NOTES {name(pl)}]' if notes else ''; add = ([['', bl]] if bl else []) + ([["has_tag('admin')", nl]] if nl else []); set_attr(pl, 'desc_extras', keep + add); set_attr(me, 'bioline_' + str(arg0), bl); set_attr(me, 'noteline_' + str(arg0), nl); result = 1
```

`bio` — a player's own public profile; `profile <name>` — read anyone's:

```text
@set the Registry/cmd_bio = $bio *:bio = trim(arg0); [(set_attr(me, 'bio_' + enactor.id, escape(bio)), set_attr(me, 'members', sorted(set(V('members', []) + [enactor.id]))), eval_attr(me, 'render', enactor.id), pemit(enactor, 'Your public profile is updated.')) for g in [bool(bio)] if g]; pemit(enactor, 'Type BIO <your public bio>.') if not bio else None
@set the Registry/cmd_profile = $profile *:pl = get(trim(arg0)); bio = V('bio_' + pl.id, '') if pl is not None else ''; pemit(enactor, name(pl) + ' profile: ' + (bio if bio else '(they have not written one)')) if pl is not None and has_tag(pl, 'player') else pemit(enactor, 'No such player.')
```

`note <name> = <text>` — staff annotate (capped at 20); `notes <name>` —
staff read the sealed layer:

```text
@set the Registry/cmd_note = $note * = *:pl = get(trim(arg0)); txt = trim(arg1); ok = has_tag(enactor, 'admin') and pl is not None and has_tag(pl, 'player') and bool(txt); [(set_attr(me, 'staff_notes', {**V('staff_notes', {}), p.id: (V('staff_notes', {}).get(p.id, []) + [name(enactor) + ': ' + escape(t)])[-20:]}), set_attr(me, 'members', sorted(set(V('members', []) + [p.id]))), eval_attr(me, 'render', p.id), pemit(enactor, 'Staff note added to ' + name(p) + '.')) for g, p, t in [[ok, pl, txt]] if g]; pemit(enactor, 'Only staff annotate players.') if not ok else None
@set the Registry/cmd_notes = $notes *:pl = get(trim(arg0)); ok = has_tag(enactor, 'admin') and pl is not None; rows = V('staff_notes', {}).get(pl.id, []) if ok else []; pemit(enactor, 'Staff notes on ' + name(pl) + ':') if ok else pemit(enactor, 'Only staff read notes.'); [pemit(enactor, '  ' + r) for r in rows]
```

## Try it

Bob writes a public profile; anyone reading him sees it:

```text
(Bob)  bio Freelance salvager. Ask about the Kessari job.
   -> Your public profile is updated.
(Cass) look Bob
   Bob
   Profile: Freelance salvager. Ask about the Kessari job.
(Cass) profile Bob
   -> Bob profile: Freelance salvager. Ask about the Kessari job.
```

Now Vala (staff) attaches a note. Watch what each viewer sees on the *same*
`look Bob`:

```text
(Vala) note Bob = Flagged for the airlock griefing on Deck 3. Watching.
   -> Staff note added to Bob.
(Vala) look Bob
   Bob
   Profile: Freelance salvager. Ask about the Kessari job.
   [staff notes: 1 on file - NOTES Bob]      <- staff eyes only
(Cass) look Bob
   Bob
   Profile: Freelance salvager. Ask about the Kessari job.
                                              <- no marker; Cass sees nothing
```

The contents stay sealed: `notes Bob` gives Vala the full annotation,
Cass gets "Only staff read notes," and the `secret` flag means even a
crafted `get_attr(get('the Registry'), 'staff_notes')` in Cass's own
script returns nothing.

## Going further

- **Player-visible notes** — a third layer: `endorse <name> = <text>`
  writing to a *public* notes list (no `secret` flag, plain `desc_extras`
  line), so players can leave references on each other — a reputation wall.
- **Note expiry** — stamp each staff row with `now()` and let a
  `script_ticker` drop rows older than 90 days, so warnings age out.
- **Cross-link to petitions** — resolving a [petition](224_petitions.md)
  could auto-append a staff note ("resolved ticket #12"), building a
  per-player history from the queue for free.
- **Sightings log** — an `ON_CONNECT` on the Registry that appends a
  timestamped "last seen" row to a `secret` sightings attr, giving staff a
  login trail without touching the engine's session layer.
```
