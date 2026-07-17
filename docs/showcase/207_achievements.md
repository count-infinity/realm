# 207. Achievements

> Checklist item 207 — [now] — *ON_* watchers, badge attrs, secret attr flags*

**What you'll build:** a Chronicle that watches the world and awards
badges — a progressive "Explorer" that climbs tiers as you visit more
landmarks, and a hidden "Trespasser" that unlocks the first time you set
foot in a sealed vault and never appears in the list until you've earned
it.

**Concepts:** a **world master as an event watcher** (`ON_ENTER` across a
`zone:world` catalog), **badge attributes on the player** (`badge_<slug>`),
**progressive tiers** driven by a threshold table, **hidden badges** kept
out of the listing until earned, and a `$badges` reader.

## How it works

Achievements are milestones the world notices on your behalf. The
Chronicle is the [zone master](036_weather_system.md) pattern pointed at
the whole game: tag your landmark rooms `zone:world` and make the Chronicle
their master, and every `ON_ENTER` in any of those rooms reaches its
`on_enter` watcher — the same cross-room witnessing the
[guard response](071_guard_response.md) uses.

Badges live on the *player* as `badge_<slug>` attributes; the Chronicle is
admin-owned, so it may write them (owner authority, as in the
[quest framework](198_quest_framework.md)). Two badge shapes show the
range:

- **Progressive "Explorer."** The Chronicle keeps a `seen_rooms` list on
  the player and, each time you enter a *new* landmark, recomputes how many
  thresholds in the badge's `tiers` table you've crossed (`[1, 2, 3]`).
  When the tier rises, it stamps `badge_explorer = <tier>` and congratulates
  you — one badge that levels up as you explore.
- **Hidden "Trespasser."** A badge flagged `secret` in the catalog. It's
  awarded by a plain `ON_ENTER` check — did you just enter a `secret`-tagged
  room? — and its *existence* is concealed: `$badges` lists only badges
  you've actually earned, so an unclaimed hidden badge leaves no trace to
  spoil the surprise.

The `on_enter` watcher stays lean (record the visit, check for the secret
room) and hands the tier arithmetic to a `visit` subroutine via
`eval_attr`. As in the quest framework, `visit` re-resolves the Chronicle
by name (`get('Chronicle')`) because `eval_attr` keeps the caller's
executor.

## Build it

Name your starting room the concourse, tag it `zone:world`, and add two
landmarks — an observatory and a *secret* sealed vault:

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

Raise the Chronicle as the world master and give it the badge catalog —
`explorer` with tiers, `trespasser` marked secret:

```text
@create Chronicle
drop Chronicle
@zone/master Chronicle = world
@set Chronicle/badges = {"explorer": {"name": "Explorer", "secret": 0, "tiers": [1, 2, 3]}, "trespasser": {"name": "Trespasser", "secret": 1}}
```

The watcher — record new landmarks, and unlock the hidden badge on a
secret room:

```text
@set Chronicle/on_enter = seen = get_attr(enactor, 'seen_rooms') or []; [eval_attr(get('Chronicle'), 'visit', enactor.id) for g in [has_tag(enactor, 'player') and here.id not in seen] if g]; [(set_attr(enactor, 'badge_trespasser', 1), pemit(enactor, 'Hidden achievement unlocked: Trespasser!')) for g in [has_tag(enactor, 'player') and has_tag(here, 'secret') and not get_attr(enactor, 'badge_trespasser', 0)] if g]
```

The tier arithmetic — append the room, count crossed thresholds, promote
if the tier rose:

```text
@set Chronicle/visit = p = get('#' + str(arg0)); seen = (get_attr(p, 'seen_rooms') or []) + [here.id]; set_attr(p, 'seen_rooms', seen); tiers = get_attr(get('Chronicle'), 'badges', {})['explorer']['tiers']; earned = len([t for t in tiers if len(seen) >= t]); [(set_attr(p, 'badge_explorer', earned), pemit(p, 'Achievement: Explorer (tier ' + str(earned) + ')!')) for g in [earned > get_attr(p, 'badge_explorer', 0)] if g]; result = 1
```

The reader — earned badges only, so hidden ones stay hidden until unlocked:

```text
@set Chronicle/cmd_badges = $badges:defs = V('badges', {}); rows = [(d['name'] + (' (tier ' + str(get_attr(enactor, 'badge_' + s, 0)) + ')' if d.get('tiers') else '')) for s, d in defs.items() if get_attr(enactor, 'badge_' + s, 0)]; pemit(enactor, 'Badges earned:' if rows else 'No badges yet.'); [pemit(enactor, '  ' + r) for r in rows]
```

## Try it

As Nova, starting in the concourse:

```text
observatory     -> Achievement: Explorer (tier 1)!
concourse       -> Achievement: Explorer (tier 2)!
vault           -> Hidden achievement unlocked: Trespasser!
                   Achievement: Explorer (tier 3)!
badges
  Badges earned:
    Explorer (tier 3)
    Trespasser
```

Each new landmark climbs the Explorer tier; the vault both completes it and
springs the hidden Trespasser. A player who never enters the vault sees
only `Explorer` in `badges` — the secret badge isn't listed as missing,
locked, or greyed-out; it simply doesn't exist for them until they earn it.
Every badge is a plain attribute on the player (`@examine Nova`), so they
persist and travel with the character.

## Going further

- **More watchers, more badges.** The Chronicle can hold `ON_DEATH`
  (kills), `ON_RECEIVE` (gifts given), or `ON_GET` (rare finds) watchers —
  one hook per milestone, all writing `badge_*` attrs the same reader
  renders.
- **Kill-count tiers.** An `ON_DEATH` watcher that bumps a `kills` counter
  and awards Slayer at 1 / 10 / 50 is the Explorer pattern with a different
  threshold table.
- **Points and titles.** Give each badge a `points` value and total them
  in `$badges` for a gamerscore; award a `title` on the capstone tier the
  player can wear.
- **Announce rare ones.** For a truly rare hidden badge, `remit` or
  broadcast the unlock so the whole server sees who cracked it — bragging
  rights as content.
