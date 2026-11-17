# 207. Achievements

> Checklist item 207 ([now]): *ON_ENTER watchers, achievement_def data, hidden achievements, account-wide grants*

**What you'll build:** a Chronicle that watches the whole world and awards
achievements: a progressive Explorer run of three (Wanderer, Pathfinder,
Cartographer) as you visit more landmarks, and a hidden Trespasser that
unlocks the first time you set foot in a sealed vault and stays out of the
list until you have earned it. Earned on one character, each one counts for
every character on the same account.

**Concepts:** achievements as data (`achievement_def` objects, the engine's
[achievements](../guides/accounts.md#achievements)), a world master as an
event witness (one
[`ON_ENTER`](../reference/softcode.md#lifecycle-hooks) hook reached from every
room in a zone) deciding *when* to grant, progressive tiers driven by a
threshold table,
[`grant_achievement`](../reference/softcode.md#fn-grant_achievement), and the
built-in `achievements` listing.

## How it works

The engine keeps the achievements: what exists (an `achievement_def` object
each), who has earned what (recorded on the account, with the date), what
an achievement grants, and the `achievements` command that lists them. What
a game builds is the part only it can know: *when* an achievement is
deserved. Here that is one object, the Chronicle, with an `on_enter` watcher
that hears every landmark, a `visit` subroutine that counts the landmarks
you have seen, and a `tiers` table pairing counts with achievements.

### How does one object hear every room?

A [zone master](036_weather_system.md) is an object tagged into a zone with
`@zone/master`, and the event system delivers every action in any room of that
zone to it as well as to the objects standing in the room
([Action Propagation](../architecture/events.md)). Tag the landmark
rooms `zone:world`, crown the Chronicle master of `world`, and its `on_enter`
attribute runs whenever anything enters any of those rooms. Because there is no
Master Room in REALM yet, a `zone:world` master is how a build gets a global
witness, and it scales by tagging: a room joins the achievement system the
moment you type `@zone here = world` in it.

Inside the hook, `enactor` is whoever moved and `here` is the room they moved
*into*. A global witness takes no `if target is me:` guard (see
[Guard on `target`](../reference/softcode.md#guard-on-target)), because it is
watching everyone; what it must get right is *whose* achievement this is,
and it only ever credits `enactor`.

### Who may award an achievement, and keep a tally on a player?

[`grant_achievement`](../reference/softcode.md#fn-grant_achievement) is a
builder's tool: an object a mortal made cannot award one. The Chronicle also
keeps the `seen_rooms` tally on the player with
[`set_attr`](../reference/softcode.md#fn-set_attr), which writes on a
player's sheet only for an executor with authority over it. An object acts
with its owner's authority, so raise the Chronicle as an admin.

### How does a tier climb without awarding twice?

The player carries a `seen_rooms` list of room ids. The watcher calls
`visit` only for a room not already in it, and `visit` grants every tier
whose count the new total has reached. `grant_achievement` does nothing for
an achievement already earned, so granting Wanderer again on the third
landmark is harmless: only Cartographer is new.

### What keeps the Trespasser out of the list?

`hidden = True` on its definition. The `achievements` command lists hidden
achievements only once earned, and otherwise says only how many are left to
find.

### Why the account?

An achievement's `scope` is `account` unless it says `character`, so it is
recorded on the account and every character the same person plays has it:
`has_achievement` answers yes for all of them, and what it `grants` (tags,
check modifiers) reaches each one, including a character made later; a
`characters` grant raises the account's own character limit.

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

Define the achievements. Each is an object tagged `achievement_def`; the
Trespasser is hidden and leaves a `trespasser` tag on whoever earns it:

```text
@create Wanderer
@tag Wanderer = achievement_def
@set Wanderer/description = Visit a landmark.
@create Pathfinder
@tag Pathfinder = achievement_def
@set Pathfinder/description = Visit two landmarks.
@create Cartographer
@tag Cartographer = achievement_def
@set Cartographer/description = Visit three landmarks.
@create Trespasser
@tag Trespasser = achievement_def
@set Trespasser/description = Set foot where you should not.
@set Trespasser/hidden = True
@set Trespasser/grants = {"tags": ["trespasser"]}
```

Raise the Chronicle, crown it master of the `world` zone, and give it the
tier table, one `[count, achievement]` pair per tier:

```text
@create Chronicle
drop Chronicle
@zone/master Chronicle = world
@set Chronicle/tiers = [[1, "Wanderer"], [2, "Pathfinder"], [3, "Cartographer"]]
```

Now the watcher. It filters to players, hands a first-time landmark to the
`visit` subroutine, and awards the hidden achievement on a `secret` room:

```text
@set Chronicle/on_enter = '''
if has_tag(enactor, 'player'):
    seen = get_attr(enactor, 'seen_rooms') or []
    if here.id not in seen:
        # here is the room just entered, not the Chronicle's own room.
        eval_attr(me, 'visit', enactor.id)
    if has_tag(here, 'secret'):
        grant_achievement(enactor, 'Trespasser')
'''
```

The `visit` subroutine records the room and grants every tier the new total
has reached:

```text
@set Chronicle/visit = '''
p = get('#' + str(arg0))  # arg0 arrives as a string, so pass ids, not objects
seen = (get_attr(p, 'seen_rooms') or []) + [here.id]
set_attr(p, 'seen_rooms', seen)
for count, name in V('tiers', []):
    if len(seen) >= count:
        grant_achievement(p, name)
result = 1
'''
```

## Try it

As Nova, starting in the concourse. Each new landmark earns the next tier,
announced before the room description because the hook runs on the arrival
itself:

```text
> observatory
You leave observatory.
Achievement earned: Wanderer!

The Observatory
...
> concourse
Achievement earned: Pathfinder!
...
> vault
Achievement earned: Cartographer!
Achievement earned: Trespasser!
...
> achievements
Achievements earned:
  Cartographer             2026-11-15  Visit three landmarks.
  Pathfinder               2026-11-15  Visit two landmarks.
  Trespasser               2026-11-15  Set foot where you should not.
  Wanderer                 2026-11-15  Visit a landmark.
```

Walk back into the vault and nothing is announced: everything it could
grant is earned. A player who never opened the vault sees the three Explorer
tiers they have, the ones still to earn, and
`...and 1 hidden achievement still to find.`, with no hint of its name.

## Going further

- **More watchers, more achievements.** The Chronicle can hold `ON_DEATH`
  (kills), `ON_RECEIVE` (gifts) or `ON_GET` (rare finds), one hook per
  milestone, each ending in `grant_achievement`. Since a zone master is
  never the subject of what it witnesses, the question is never `target is
  me` but *who deserves the credit*: `actor` did the thing and `target` had
  it done to them. A hook on a *participant*, such as a boss awarding its own
  slayer, does need `target is me`; see [245](245_event_bus_tour.md).
- **A reward that matters.** `@set Cartographer/grants = {"check_mods":
  {"observation": 1}}` gives every character on the account +1 to
  observation for good. The worked example in the
  [accounts guide](../guides/accounts.md#a-worked-example) does the same
  for the banshee's slayer and will. `{"characters": 1}` gives the
  account a character slot beyond `MAX_CHARACTERS` instead (CoffeeMud's
  `BONUSCHARLIMIT`; [How many characters](../guides/accounts.md#how-many-characters)).
- **Per character.** `@set Wanderer/scope = character` keeps an
  achievement on the character that earned it, for milestones a new
  character should earn again.
- **Fanfare.** React to `ON_ACHIEVEMENT` (the `account:on_achievement`
  event, `adata('achievement')` naming it) on the Chronicle with
  [`remit`](../reference/softcode.md#fn-remit) or a zone-wide
  [`act`](../reference/softcode.md#fn-act), so the whole server sees who
  cracked the vault.
