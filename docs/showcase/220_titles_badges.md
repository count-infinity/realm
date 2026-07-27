# 220. Titles & badges

> Checklist item 220 ([now]): *earned display titles shown in look/finger, title attributes, desc_extras rendering*

**What you'll build:** a Herald that staff use to award earned titles,
`award Bob = Void Champion`, which then hang under Bob's name whenever
anyone in the room looks at him. Bob collects badges over time and picks
which one to wear with `settitle`, and `finger <player>` reads anyone's
honors from across the map.

**Concepts:** cosmetic state as a ledger of attributes (`badges_<id>`,
`title_<id>`) on an admin-owned Herald; rendering the earned title into
the target's [`desc_extras`](042_room_details.md) so the builtin `look`
shows it to every viewer; a managed detail line that is rewritten in
place rather than appended twice; owner authority letting a staff-owned
object write onto a player; and the difference between
[`eval_attr`](../reference/softcode.md#fn-eval_attr) and
[`call`](../reference/softcode.md#fn-call) when a shared routine is
invoked from somewhere else.

## How it works

The finished Herald is a single admin-owned object standing in a
world-zone room. It holds two attributes per decorated player, one
listing every badge they have earned and one naming the badge they are
currently wearing, and every change funnels through one shared `render`
routine that stamps a line of text onto the player themselves. Because
that line lives on the player, the engine's own `look` renderer prints it
for whoever is looking. The rest of this section answers four questions:
where a title becomes visible to other people, how the Herald keeps from
stacking duplicate lines, what authority lets a staff object write on
somebody else's character, and how far from the Herald the verbs reach.

### Where does a title actually become visible?

An attribute sitting on the Herald is only as visible as the softcode
that prints it, so `finger` and `titles` show it only because they
[`pemit`](../reference/softcode.md#fn-pemit) it by hand. Nobody else's
screen changes. To put an honor in front of every
onlooker, the text has to reach a place the engine already renders.

That place is `desc_extras`, a list of `[condition, text]` rows on any
object. Looking at a player runs the description first and then prints
every `desc_extras` row whose condition passes for that particular
viewer, which is the same machinery the [room details](042_room_details.md)
tutorial builds with `@detail`. A row with an empty condition shows to
everyone, so a title is simply `['', 'Void Champion - badges: ...']`
appended to the player's own `desc_extras`, and `look Bob` prints

```text
Bob
Void Champion - badges: First Blood, Void Champion
```

Two boundaries are worth stating plainly. The builtin `who` writes a
fixed line per session (`name (idle 4s) in The Landing`) built straight
from `session.player.name`, with no attribute consulted anywhere, so a
title column there waits on the audit's G4 presence surface. Prefixing
the *name itself* ("Void Champion Bob" in every message) is a separate
mechanism again: names pass through `register_name_resolver` in
`realm/core/perception.py`, which recognition and disguise use, and that
registration is engine-side Python rather than a softcode function.
`desc_extras` is the surface softcode owns today, and it is the one the
whole room reads.

The other half of the ask, looking somebody up without standing next to
them, is a plain `$finger` verb, since `finger` is not a builtin and the
name is free to take.

### How the Herald avoids stacking duplicate lines

The Herald keeps three attributes keyed by player id:
`badges_<id>` is the list of everything earned, `title_<id>` is the one
being displayed, and `line_<id>` remembers the exact text of the row the
Herald last wrote onto that player. Remembering the text is what makes a
rewrite possible, because the shared `render` routine rebuilds the
player's `desc_extras` as "every row except the one matching
`line_<id>`", then appends the freshly composed line. A second award
therefore replaces the honor rather than adding a second copy, and any
other rows on the player, such as a scar added with `@detail`, survive
untouched.

`render` reads its own ledger with
[`V`](../reference/softcode.md#fn-v), which is shorthand for
[`get_attr(me, ...)`](../reference/softcode.md#fn-get_attr), so it
matters a great deal *who* `me` is when the
routine runs. Called from the Herald's own verbs with
[`eval_attr(me, 'render', pid)`](../reference/softcode.md#fn-eval_attr),
`me` is already the Herald and the reads land on the right object.
Invoked from a different object, `eval_attr` keeps running as the caller,
so a boss monster calling it would have `V` read the boss's attributes
instead. The primitive for that case is
[`call`](../reference/softcode.md#fn-call), which runs the routine **as**
the named object, and the Going further section uses it.

### What lets a staff object write onto a player?

[`set_attr`](../reference/softcode.md#fn-set_attr) requires that the
running script control its target, and a player controls themselves.
The Herald reaches Bob through PennMUSH-style delegation: an owned object
acts with its owner's authority, the Herald is owned by an admin, and an
admin controls everything, so the Herald's scripts may stamp Bob's
`desc_extras`. This is the same footing the [coat check](022_coat_check.md)
stands on when it hands other people's coats back. Delegation grants no
authority the owner lacked, so a Herald owned by an ordinary builder
would be refused.

Authority over the object is separate from who may drive it, which is why
`award` opens with an explicit
[`has_tag(enactor, 'admin')`](../reference/softcode.md#fn-has_tag) test
while `finger`, `titles`, and `settitle` are open to everyone.

### How far the verbs reach

REALM has no Master Room yet, so a verb that should work away from its
object is hung on a **world-zone master**: an object tagged
`zone_master` and `zone:world`, whose `$`-commands are searched for any
player standing in a room that also carries `zone:world`. That covers the
public map rather than literally everywhere, so a room you never zoned
hears nothing. The player being looked up may be anywhere, because
[`get`](../reference/softcode.md#fn-get) falls back to a world-wide name
search.

## Build it

Start with a home for the Herald and put it in the world zone, so the
verbs answer from every world room rather than only from this one:

```text
@dig The Heraldry Hall = heraldry, out
heraldry
@zone here = world
```

Create the Herald, drop it here, and make it the world zone's master. The
description doubles as the help text a visitor reads:

```text
@create the Herald
drop the Herald
@desc the Herald = A figure in tabard and chain. FINGER <name> reads a player's honors; TITLES lists your own; SETTITLE <badge> chooses which to wear. Staff AWARD <name> = <title>.
@zone/master the Herald = world
```

Now the shared `render` routine, which both writing verbs end by calling.
It resolves the player from the id it was handed, reads that player's
badges and current title off the Herald, strips the row it wrote last
time, composes the new one, writes the whole list back, and records the
text so the next pass knows what to strip:

```text
@set the Herald/render = '''
pid = str(arg0)
pl = get('#' + pid)
badges = V('badges_' + pid, [])
title = V('title_' + pid, '')
old = V('line_' + pid, '')
# Drop only the row this Herald wrote last time; @detail rows survive.
extras = [row for row in (get_attr(pl, 'desc_extras') or []) if not (old and len(row) > 1 and str(row[1]) == old)]
newline = title + (' - badges: ' + ', '.join(badges) if badges else '')
if newline:
    set_attr(pl, 'desc_extras', extras + [['', newline]])  # '' condition: everyone sees it
else:
    set_attr(pl, 'desc_extras', extras)
set_attr(me, 'line_' + pid, newline)
result = 1
'''
```

`award <player> = <title>` is the staff verb. It separates its two
refusals so the caller learns which thing was wrong, and on success it
adds the badge to the earned list (`sorted(set(...))` keeps that list
alphabetical and free of duplicates, so awarding the same honor twice is
harmless), makes it the displayed title, re-renders the player's line,
and tells both sides. An empty honor needs no test of its own,
because the `*` in the pattern requires at least one character, so
`award Bob =` never reaches the script at all:

```text
@set the Herald/cmd_award = '''
$award * = *:
pl = get(trim(arg0))
badge = trim(arg1)
if not has_tag(enactor, 'admin'):
    pemit(enactor, 'Only staff award titles.')
elif pl is None or not has_tag(pl, 'player'):
    pemit(enactor, 'Award to whom? Name a player.')
else:
    set_attr(me, 'badges_' + pl.id, sorted(set(V('badges_' + pl.id, []) + [badge])))
    set_attr(me, 'title_' + pl.id, badge)
    eval_attr(me, 'render', pl.id)  # me is the Herald here, so render's V() reads its ledger
    pemit(enactor, f'Awarded "{badge}" to {name(pl)}.')
    pemit(pl, f'You have been awarded the title: {badge}')
'''
```

`titles` reports your own honors, reading both attributes and falling
back to friendly placeholders when a player has none yet:

```text
@set the Herald/cmd_titles = '''
$titles:
earned = V('badges_' + enactor.id, [])
cur = V('title_' + enactor.id, '')
pemit(enactor, 'Displaying: ' + (cur or '(none)'))
pemit(enactor, 'Earned: ' + (', '.join(earned) or '(none yet)'))
'''
```

`settitle <badge>` lets a player wear any badge they have already earned,
and the membership test against `badges_<id>` is the whole security model:
an honor you were never given is never in the list:

```text
@set the Herald/cmd_settitle = '''
$settitle *:
want = trim(arg0)
if want in V('badges_' + enactor.id, []):
    set_attr(me, 'title_' + enactor.id, want)
    eval_attr(me, 'render', enactor.id)
    pemit(enactor, f'Now displaying: {want}')
else:
    pemit(enactor, 'You have not earned that title. TITLES lists yours.')
'''
```

`finger <player>` reads anyone's honors, including a player standing in
another room, because `get` searches the world when the name is not
local. [`trim`](../reference/softcode.md#fn-trim) tidies the typed
argument and [`name`](../reference/softcode.md#fn-name) gives back the
player's proper spelling, whatever case the caller used:

```text
@set the Herald/cmd_finger = '''
$finger *:
pl = get(trim(arg0))
if pl is not None and has_tag(pl, 'player'):
    title = V('title_' + pl.id, '') or 'no title'
    badges = ', '.join(V('badges_' + pl.id, [])) or 'none'
    pemit(enactor, f'{name(pl)} - {title} - badges: {badges}')
else:
    pemit(enactor, 'No such player.')
'''
```

## Try it

As staff, decorate Bob twice. The newest award becomes what he wears:

```text
> award Bob = First Blood
Awarded "First Blood" to Bob.
> award Bob = Void Champion
Awarded "Void Champion" to Bob.
```

Bob is told each time, in his own window:

```text
You have been awarded the title: First Blood
You have been awarded the title: Void Champion
```

Now anyone in the room who looks at Bob reads the honor under his name.
This is the line worth confirming deliberately, because it is the one
that proves the title reached somebody else's screen rather than only
Bob's:

```text
> look Bob
Bob
Void Champion - badges: First Blood, Void Champion
```

Bob prefers his first honor and switches. Note that the badge list is
unchanged and the detail line was rewritten rather than doubled:

```text
> settitle First Blood
Now displaying: First Blood
> look Bob
Bob
First Blood - badges: First Blood, Void Champion
> titles
Displaying: First Blood
Earned: First Blood, Void Champion
```

An honor he was never given is refused, since `settitle` tests against
the earned list:

```text
> settitle Unearned Glory
You have not earned that title. TITLES lists yours.
```

The lookup verb reaches him from any world-zone room, and works on a
player who has nothing yet:

```text
> finger Bob
Bob - First Blood - badges: First Blood, Void Champion
> finger Cass
Cass - no title - badges: none
```

Finally, try `award Cass = Cheater` as an ordinary player. The
`admin`-tag test answers before anything is written:

```text
> award Cass = Cheater
Only staff award titles.
```

## Engine gaps

- The builtin `who` composes its line from `session.player.name` and the
  session's idle time, consulting no attribute, so a title column in
  `who` needs the audit's **G4 presence surface**. Reported for the
  integrator; `look` and `$finger` cover the item as written.
- Per-viewer name overrides go through `register_name_resolver` in
  `realm/core/perception.py`, which is Python registration with no
  softcode equivalent, so a title woven into the name itself (and thus
  into speech attribution) is out of reach from in-game code today.

## Going further

- **Auto-badges.** Let another system award an honor on a milestone, such
  as a boss stamping "Dragonslayer" on whoever felled it.
  [`combat:on_death`](../reference/softcode.md#lifecycle-hooks) is
  announced from the single death path, so the payout lands whether the
  boss fell to a blade, a trap, or a poison tick, and
  [`adata('fatal')`](../reference/softcode.md#event-data-namespace)
  separates a real kill from a player knocked unconscious in place (see
  [245](245_event_bus_tour.md)).

  Two details make this work. The hook needs `if target is me:`, because
  an `ON_DEATH` fires on every object in the room and an unguarded boss
  would hand out "Dragonslayer" when the rat beside it dies (see
  [Guard on `target`](../reference/softcode.md#guard-on-target)). And the
  re-render uses [`call`](../reference/softcode.md#fn-call) rather than
  `eval_attr`, because `call` runs `render` **as** the Herald, so the
  routine's `V()` reads the Herald's ledger instead of the boss's
  attributes:

  ```text
  @set dragon/on_death = '''
  if target is me and actor:
      h = get('the Herald')
      earned = get_attr(h, 'badges_' + actor.id) or []
      set_attr(h, 'badges_' + actor.id, sorted(set(earned + ['Dragonslayer'])))
      set_attr(h, 'title_' + actor.id, 'Dragonslayer')
      call(h, 'render', actor.id)  # call runs render AS the Herald; eval_attr would not
  '''
  ```

- **Colored ranks.** Have `award` store the displayed title already
  wrapped, `set_attr(me, 'title_' + pl.id, ansi('yh', badge))`, and the
  rendered `desc_extras` line arrives in bright yellow while the earned
  list stays plain text for `titles` and `finger`. See
  [`ansi`](../reference/softcode.md#fn-ansi) for the code letters.
- **Badge icons over GMCP.** Add
  [`oob(pl, 'Char.Badges', {'list': badges})`](../reference/softcode.md#fn-oob)
  to `render` so a client's achievement shelf updates alongside the text.
- **Revoke.** A staff `$strip <player> = <badge>` removes one badge,
  picks a remaining one as the displayed title, and calls `render` again.
  The ledger already holds everything an un-award needs, and the managed
  line means the display corrects itself in one pass.
