# 207. Achievements

> Checklist item 207 ([now]): *ON_ENTER watchers, badge attrs, hidden badge flags*

**What you'll build:** a Chronicle that watches the whole world and awards
badges, namely a progressive "Explorer" that climbs tiers as you visit more
landmarks, and a hidden "Trespasser" that unlocks the first time you set foot
in a sealed vault and stays out of your badge list until you have earned it.

**Concepts:** a world master as an event witness (one
[`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) hook reached from every
room in a zone), badge attributes written onto the player (`badge_<slug>`),
progressive tiers driven by a threshold table, a hidden badge kept out of the
listing until it is earned, and a `$badges` reader.

## How it works

The finished system is one object, the Chronicle, carrying four attributes: a
`badges` catalog naming what exists, an `on_enter` watcher that hears every
landmark in the game, a `visit` subroutine that does the tier arithmetic, and
a `cmd_badges` reader that players type. What a player has earned lives on the
*player* as a `badge_<slug>` attribute, so the Chronicle keeps no roster of its
own and a character carries their trophies wherever they go. This section
answers four questions: how one object hears every room, what authority lets
it write on a player, how a tier climbs without awarding twice, and what keeps
the hidden badge hidden.

### How does one object hear every room?

A [zone master](036_weather_system.md) is an object tagged into a zone with
`@zone/master`, and the event system delivers every action in any room of that
zone to it as well as to the objects standing in the room
([Action Propagation](../architecture/events.md)). Tag the landmark
rooms `zone:world`, crown the Chronicle master of `world`, and its `on_enter`
attribute runs whenever anything enters any of those rooms. That is the same
cross-room witnessing the [town watch](071_guard_response.md) uses, pointed at
the whole game instead of one district. Because there is no Master Room in
REALM yet, a `zone:world` master is how a build gets a global witness, and it
scales by tagging: a room joins the achievement system the moment you type
`@zone here = world` in it.

Inside the hook, `enactor` is whoever moved and `here` is the room they moved
*into*, not the room the Chronicle is standing in, since a witnessed hook runs
with the action's own location bound. The mover does not fire its own
`ON_ENTER` (it gets `ON_ARRIVE` instead), and in this build the Chronicle is
the only object carrying the hook, so it is the only thing that reacts.

An `ON_<EVENT>` hook fires on every object in the room, which is why a hook
reacting to its own business opens with `if target is me:` (see
[Guard on `target`](../reference/softcode.md#guard-on-target)). A global
witness is the deliberate exception and takes no such guard, because it is
watching everyone and is never the subject of the events it collects. What it
must get right instead is *whose* badge this is: the Chronicle only ever reads
and writes `enactor`, so a second player already standing in the vault when
someone else walks in earns nothing.

### Who may write a badge onto another player's sheet?

[`set_attr`](../reference/softcode.md#fn-set_attr) writes only where the
executor has authority, and a player's own sheet is the strictest case.
`@create` stamps the creator as the object's owner, and an object acts with its
owner's authority, so a Chronicle created by an admin may stamp
`badge_explorer` onto anyone, exactly as the Warden in the
[quest framework](198_quest_framework.md) stamps quest stages. Raise this
object as an admin: a Chronicle owned by a plain builder has its writes
refused, and the badge quietly never appears.

### How does a tier climb without awarding twice?

The player carries a `seen_rooms` list of room ids. On entry the watcher
compares `here.id` against that list and calls the `visit` subroutine only for
a room that is new, so pacing back and forth between two landmarks adds
nothing. `visit` appends the room, counts how many thresholds in the catalog's
`tiers` table the new total has crossed, and writes `badge_explorer` only when
that count is *higher* than the value already on the player. Two independent
guards therefore stand between a footstep and a duplicate award.

`visit` runs through
[`eval_attr`](../reference/softcode.md#fn-eval_attr), which evaluates an
attribute as a subroutine and hands back its `result`. It keeps the caller's
executor rather than swapping to the attribute's owner the way PennMUSH's
`u()` does, and here the caller *is* the Chronicle, so inside `visit` the name
`me` still refers to the Chronicle and
[`V('badges')`](../reference/softcode.md#fn-v) reads its own catalog. That is
worth contrasting with the quest framework, where the same subroutine is called
from a hook on a *relic*, so `me` is the relic and the routine has to find its
own home with [`get('Quest Warden')`](../reference/softcode.md#fn-get).
Arguments arrive as `arg0`, `arg1`, and so on, always as strings, which is why
the player is passed as an id and recovered with `get('#' + str(arg0))`.

### What keeps the hidden badge out of the list?

The reader walks the catalog and
[`pemit`](../reference/softcode.md#fn-pemit)s a row only where
[`get_attr`](../reference/softcode.md#fn-get_attr) finds a `badge_<slug>`
attribute set on the player who typed it. An unearned badge produces no row at
all, so it is not shown as missing, locked, or greyed out, and the Trespasser
leaves no trace to spoil the surprise.

The `secret` key in the catalog is plain builder data recording which badges
are meant to stay unannounced. It is separate from the engine's per-attribute
`secret` flag (`@attr obj/attr = secret`), which governs who may *read* an
attribute; the concealment here comes from the reader's earned-only rule, and
the catalog key is what a fuller reader consults before listing anything as
locked (see "Going further").

## Build it

Name your starting room the concourse, tag it `zone:world`, and add two
landmarks, an observatory and a sealed vault. The vault also gets a plain
`secret` tag, which is what the watcher tests for:

```text
@name here = The Grand Concourse
@zone here = world
@dig The Observatory = observatory, concourse
observatory
@zone here = world
concourse
@dig The Sealed Vault = vault, concourse
vault
@zone here = world
@tag here = secret
concourse
```

Raise the Chronicle and crown it master of the `world` zone, which is what
routes every landmark's events to it:

```text
@create Chronicle
drop Chronicle
@zone/master Chronicle = world
```

Give it the badge catalog: `explorer` with its threshold table, `trespasser`
marked as one to keep quiet about. This is a data attribute rather than a
script, so it stays on one line, because a `'''` block would store the text
as a raw string and `V('badges', {})['explorer']` would then index characters
instead of the dict:

```text
@set Chronicle/badges = {"explorer": {"name": "Explorer", "secret": 0, "tiers": [1, 2, 3]}, "trespasser": {"name": "Trespasser", "secret": 1}}
```

Now the watcher. It filters to players, hands a first-time landmark to the
`visit` subroutine, and unlocks the hidden badge on a `secret` room:

```text
@set Chronicle/on_enter = '''
if has_tag(enactor, 'player'):
    seen = get_attr(enactor, 'seen_rooms') or []
    if here.id not in seen:
        # here is the room just entered, not the Chronicle's own room.
        eval_attr(me, 'visit', enactor.id)
    if has_tag(here, 'secret') and not get_attr(enactor, 'badge_trespasser', 0):
        set_attr(enactor, 'badge_trespasser', 1)
        pemit(enactor, 'Hidden achievement unlocked: Trespasser!')
'''
```

A global witness takes no `if target is me:` guard, since it is collecting
everyone's events on purpose. The filter that matters is
[`has_tag(enactor, 'player')`](../reference/softcode.md#fn-has_tag), which
keeps wandering NPCs and pushed crates out of the badge tables, and every write
in the body names `enactor`, so a bystander in the room is untouched.

The `visit` subroutine does the arithmetic: record the room, count the
thresholds crossed, and promote only when the tier actually rose:

```text
@set Chronicle/visit = '''
p = get('#' + str(arg0))  # arg0 arrives as a string, so pass ids, not objects
seen = (get_attr(p, 'seen_rooms') or []) + [here.id]
set_attr(p, 'seen_rooms', seen)
tiers = V('badges', {})['explorer']['tiers']
earned = len([t for t in tiers if len(seen) >= t])
if earned > get_attr(p, 'badge_explorer', 0):
    set_attr(p, 'badge_explorer', earned)
    pemit(p, f'Achievement: Explorer (tier {earned})!')
result = 1
'''
```

Finally the reader, a `$badges` command that lists earned badges only, which
is what keeps an unclaimed hidden badge invisible:

```text
@set Chronicle/cmd_badges = '''
$badges:
defs = V('badges', {})
rows = []
for slug, d in defs.items():
    earned = get_attr(enactor, 'badge_' + slug, 0)
    if earned:
        rows.append(d['name'] + (f' (tier {earned})' if d.get('tiers') else ''))
pemit(enactor, 'Badges earned:' if rows else 'No badges yet.')
for row in rows:
    pemit(enactor, '  ' + row)
'''
```

## Try it

As Nova, starting in the concourse with the builder Bela still standing there
after the build. Each new landmark climbs the Explorer tier, and the award
lands before the room description because the hook runs on the arrival itself:

```text
> observatory
You leave observatory.
Achievement: Explorer (tier 1)!

The Observatory
---------------

Exits: concourse

> concourse
You leave concourse.
Achievement: Explorer (tier 2)!

The Grand Concourse
-------------------

You see:
  Chronicle

Players here:
  Bela

Exits: observatory, vault
```

The vault is the third distinct landmark, so it completes the Explorer tiers
and springs the hidden badge in the same step. Explorer is announced first
because the watcher records the visit before it tests for a secret room:

```text
> vault
You leave vault.
Achievement: Explorer (tier 3)!
Hidden achievement unlocked: Trespasser!

The Sealed Vault
----------------

Exits: concourse

> badges
Badges earned:
  Explorer (tier 3)
  Trespasser
```

Two results are worth confirming deliberately. Walk back to the concourse and
into the vault a second time and nothing is announced, because the room is
already in `seen_rooms` and the tier count has not risen. Then look at a player
who never opened the vault: their `badges` shows Explorer alone, with no hint
that a second badge exists. Every badge is an ordinary attribute on the
character, so `@examine Nova` lists `badge_explorer`, `badge_trespasser`, and
`seen_rooms` alongside the rest of the sheet, and they persist with the
character.

## Going further

- **More watchers, more badges.** The Chronicle can hold `ON_DEATH` (kills),
  `ON_RECEIVE` (gifts, where
  [`adata('item')`](../reference/softcode.md#event-data-namespace) came from
  `adata('giver')` and
  `target` is the recipient), or `ON_GET` (rare finds, where the item is
  `target`), one hook per milestone, all writing `badge_*` attributes that the
  same reader renders. Since a zone master is never the subject of what it
  witnesses, the question is never `target is me` but *who deserves the
  credit*: `actor` did the thing and `target` had it done to them, so crediting
  the wrong one puts the trophy on the corpse. A hook on a *participant*, such
  as a boss awarding its own slayer, has the opposite job and does need
  `target is me`; see [245](245_event_bus_tour.md).
- **Kill-count tiers.** An `ON_DEATH` watcher that bumps `actor`'s kill counter
  and awards Slayer at 1, 10, and 50 is the Explorer pattern with a different
  threshold table. Every route into death runs through one path, so
  `combat:on_death` reaches the Chronicle whether the blow was a swing,
  softcode [`damage()`](../reference/softcode.md#fn-damage), a poison tick, or
  a trap. Filter on `adata('fatal')` to count real deaths only and skip players
  knocked unconscious, and expect `actor` to be `None` when nobody swung.
  Crediting `target` instead of `actor` on the same hook earns the other side
  of the record, a "Survivor" badge for going down and getting back up, since
  `not adata('fatal')` is exactly a player knocked out.
- **Show what is still locked.** Read the catalog's `secret` key in
  `cmd_badges` and print a `[LOCKED]` row for unearned badges where
  `secret` is 0, leaving the secret ones out entirely. That turns the catalog
  flag into working code and gives players a visible checklist without leaking
  the surprises.
- **Points, titles, and fanfare.** Give each badge a `points` value and total
  it in `$badges` for a score, award a wearable `title` on the capstone tier,
  and for a genuinely rare unlock use [`remit`](../reference/softcode.md#fn-remit)
  or a zone-wide [`act`](../reference/softcode.md#fn-act) so the whole server
  sees who cracked it.
