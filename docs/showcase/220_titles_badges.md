# 220. Titles & badges

> Checklist item 220 — [now] — *earned display titles rendered in look via desc_extras, cosmetic ledger attrs, staff award authority*

**What you'll build:** a Herald that staff use to award earned titles —
`award Bob = Void Champion` — which then hang under Bob's name whenever
anyone looks at him. Bob collects badges over time and picks which one to
wear with `settitle`; `finger <player>` reads anyone's honors.

**Concepts:** cosmetic state as a **ledger of attributes** (`badges_<id>`,
`title_<id>`) on an admin-owned Herald; rendering an earned title into the
target's **`desc_extras`** so the builtin `look` shows it per the
[room details](042_room_details.md) machinery; a **managed detail line**
(re-rendered in place, never duplicated); **owner authority** letting the
staff-owned master write onto a player; and the honest boundary around the
builtin `who`.

## How it works

**Why not the `who` list?** The checklist asks for titles "in who/look."
The `who` columns are fixed builtin output — softcode can't add a column
(audit gap G4). `look`, though, renders every object's `desc_extras`
lines after its description, per viewer, using the exact
[detail machinery](042_room_details.md). So a title is a `desc_extras`
line the Herald stamps onto the player: `look Bob` shows

```text
Bob
Void Champion - badges: First Blood, Void Champion
```

with no column-hacking and no new engine seam. (A custom `$finger` verb
covers the "look someone up from anywhere" half; `finger` isn't a
builtin, so it's ours to define.)

**The Herald owns the ledger; the player wears the result.** Two attribute
families live on the master: `badges_<id>` (everything a player has
earned) and `title_<id>` (the one they're currently displaying). Awarding
appends a badge and makes it the current title; `settitle` lets the player
switch to any badge they've earned. Every change calls one shared
`render` routine that rewrites the player's managed `desc_extras` line —
and *only* that line: it filters out the previous version (tracked in
`line_<id>`) before appending the new one, so the honor never doubles up.

**Owner authority is what lets it write onto a player.** `set_attr` needs
control of its target, and a player isn't yours. But the Herald is
admin-owned, and an object acts with its owner's authority (PennMUSH
delegation), so the admin's master may stamp the player's `desc_extras` —
the same convention the [coat check](022_coat_check.md) uses to handle
other people's coats. Awarding itself is gated to staff by an
`admin`-tag check; anyone may `finger`, `titles`, or `settitle`.

## Build it

A world-zone home so `finger` and `settitle` work from anywhere:

```text
@dig The Heraldry Hall = heraldry, out
heraldry
@zone here = world
```

The Herald, an admin-owned world-zone master:

```text
@create the Herald
drop the Herald
@desc the Herald = A figure in tabard and chain. FINGER <name> reads a player's honors; TITLES lists your own; SETTITLE <badge> chooses which to wear. Staff AWARD <name> = <title>.
@zone/master the Herald = world
```

The shared render routine — rewrite the player's one managed detail line,
dropping the previous version by the text we stored last time:

```text
@set the Herald/render = pl = get('#' + str(arg0)); badges = V('badges_' + str(arg0), []); title = V('title_' + str(arg0), ''); old = V('line_' + str(arg0), ''); extras = [p for p in (get_attr(pl, 'desc_extras') or []) if not (len(p) > 1 and str(p[1]) == old)]; newline = title + (' - badges: ' + ', '.join(badges) if badges else ''); has = bool(title or badges); set_attr(pl, 'desc_extras', extras + [['', newline]]) if has else set_attr(pl, 'desc_extras', extras); set_attr(me, 'line_' + str(arg0), newline if has else ''); result = 1
```

`award <player> = <title>` — staff only; append the badge, display it,
render, and tell both sides:

```text
@set the Herald/cmd_award = $award * = *:pl = get(trim(arg0)); badge = trim(arg1); ok = has_tag(enactor, 'admin') and pl is not None and has_tag(pl, 'player') and bool(badge); [(set_attr(me, 'badges_' + p.id, sorted(set(V('badges_' + p.id, []) + [b]))), set_attr(me, 'title_' + p.id, b), set_attr(me, 'members', sorted(set(V('members', []) + [p.id]))), eval_attr(me, 'render', p.id), pemit(enactor, 'Awarded "' + b + '" to ' + name(p) + '.'), pemit(p, 'You have been awarded the title: ' + b)) for g, b, p in [[ok, badge, pl]] if g]; pemit(enactor, 'Only staff award titles, to a real player, with a non-empty title.') if not ok else None
```

`titles` — your own honors; `settitle` — wear a different earned badge:

```text
@set the Herald/cmd_titles = $titles:earned = V('badges_' + enactor.id, []); cur = V('title_' + enactor.id, ''); pemit(enactor, 'Displaying: ' + (cur if cur else '(none)')); pemit(enactor, 'Earned: ' + (', '.join(earned) if earned else '(none yet)'))
@set the Herald/cmd_settitle = $settitle *:want = trim(arg0); earned = V('badges_' + enactor.id, []); ok = want in earned; [(set_attr(me, 'title_' + enactor.id, w), eval_attr(me, 'render', enactor.id), pemit(enactor, 'Now displaying: ' + w)) for g, w in [[ok, want]] if g]; pemit(enactor, 'You have not earned that title. TITLES lists yours.') if not ok else None
```

`finger <player>` — anyone's honors, from anywhere:

```text
@set the Herald/cmd_finger = $finger *:pl = get(trim(arg0)); pemit(enactor, name(pl) + ' - ' + (V('title_' + pl.id, '') or 'no title') + ' - badges: ' + (', '.join(V('badges_' + pl.id, [])) or 'none')) if pl is not None and has_tag(pl, 'player') else pemit(enactor, 'No such player.')
```

## Try it

As staff, decorate Bob twice; the newest award becomes what he wears:

```text
award Bob = First Blood
   -> Awarded "First Blood" to Bob.
award Bob = Void Champion
   -> Awarded "Void Champion" to Bob.
```

Now anyone who looks at Bob reads his honor under his name:

```text
look Bob
   Bob
   Void Champion - badges: First Blood, Void Champion
```

Bob prefers his first honor and switches:

```text
settitle First Blood
   -> Now displaying: First Blood
look Bob
   Bob
   First Blood - badges: First Blood, Void Champion
```

And the lookup verb reaches him from any world room:

```text
finger Bob
   -> Bob - First Blood - badges: First Blood, Void Champion
```

Try `award Bob = Nobody` as an ordinary player — the `admin`-tag gate
answers "Only staff award titles."

## Going further

- **Auto-badges** — have another system award on a milestone:
  `eval_attr(get('the Herald'), 'award', ...)` won't gate on the tag if
  you call the ledger writes directly from a trusted master (a boss's
  `ON_DEATH` stamping "Dragonslayer"). Titles then earn themselves.
- **Colored ranks** — store the title with `ansi('yh', 'Void Champion')`
  so the rendered `desc_extras` line glows gold.
- **Badge icons over GMCP** — `oob(pl, 'Char.Badges', {'list': badges})`
  feeds a client's achievement shelf alongside the text line.
- **Revoke** — a staff `$strip <player> = <badge>` that removes one badge,
  reselects a remaining title, and re-`render`s — the ledger already has
  everything the un-award needs.
```
