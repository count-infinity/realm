# 027. Secret Door

> Checklist item 27 ([now]): *concealed exits, search + skill_check, perception engine*

**What you'll build:** A ventilation grate that stays invisible until a
character finds it, either deliberately with the built-in `search`
command or passively with an Observation check the room rolls for
everyone who walks in. It is the first build in the
[Heist arc](arc_heist.md), and it digs the arc's first three rooms.

**Concepts:** the perception engine's `invisible` tag, the
`conceal_difficulty` and `reveal_msg` attributes, the built-in `search`
command, a room [`ON_ENTER`](../reference/softcode.md#lifecycle-hooks)
trigger that rolls [`skill_check()`](../reference/softcode.md#fn-skill_check),
and the engine rule that a concealed exit stays traversable by name.

## How it works

Most of this build is configuration of an engine feature that already
exists, so the finished grate leans on the perception engine and adds
just one small script. This section covers what the engine hides for
free, how a deliberate `search` reveals it, why the exit still walks even
while hidden, and where the room's one script fits.

1. **Hiding is a tag.** Anything tagged `invisible` drops out of room
   displays and cannot be targeted by name. An exit is only an object in
   the room's contents, so a tagged exit vanishes from the `Exits:` line
   as well.
2. **`search` is built in.** It rolls the searcher's Observation at
   `-conceal_difficulty` against each concealed object in the room, and on
   a success it strips the `invisible` tag and prints the object's
   `reveal_msg`. An invisible object is searchable this way only once it
   carries a `conceal_difficulty`, so the deliberate check needs no
   softcode of yours.
3. **Traversal ignores concealment.** A hidden exit still works if you
   type its name, because the engine deliberately exempts exits from
   perception-gated targeting, so a character who knew the trick all along
   can still use it. (`tests/test_perception.py` pins both halves: the
   exit is dropped from the display yet stays walkable by name.)

The one thing the engine does not do on its own is roll a **passive**
check when someone enters the room. That is what the room's `ON_ENTER`
attribute adds. A room witnesses every arrival, so its `ON_ENTER` fires
for each entry with the arriver bound as `enactor`, and
`skill_check(enactor, 'observation', -4)` is the glance. The passive
penalty of -4 is stiffer than a deliberate search at
`-conceal_difficulty`, which is right, since a search is someone looking
on purpose.

One honest semantic note: REALM's reveal is **world state**, not
per-character. Once anyone strips the `invisible` tag, the grate is found
for everybody. A per-character variant is in Going further.

## Build it

Dig the office and the corridor, then walk east into the corridor:

```text
@dig The Security Office
@teleport me = The Security Office
@dig Maintenance Corridor = east, west
east
```

Dig the room behind the wall and open a one-way exit to it. `@open`
creates the exit here in the corridor, and nothing about it is secret
yet:

```text
@dig Vault Antechamber
@open loose grate = Vault Antechamber
@desc loose grate = A dented ventilation grate low on the wall, screwed into its frame.
```

Now conceal it. `conceal_difficulty` is the penalty on the finder's
Observation check (2 is tucked away, 5 is a masterwork), and `reveal_msg`
is the payoff line `search` prints on a success:

```text
# search reveals an invisible object only when it also carries a conceal_difficulty
@set loose grate/conceal_difficulty = 2
@set loose grate/reveal_msg = One grate sits loose in its frame -- a crawlway yawns behind it!
@tag loose grate = invisible
```

Add the passive glance as the room's one script. A room witnesses every
arrival, so its `ON_ENTER` fires with the arriver bound as `enactor`. The
block fetches the grate, and on a sharp enough glance (Observation at -4)
it does exactly what `search` would, stripping the `invisible` tag and
delivering the reveal line. The guards keep it from firing for NPCs or
after the grate is already found, and since the conditions run left to
right, the Observation roll happens only for a player facing a
still-hidden grate:

```text
@set here/on_enter = '''
g = get('loose grate')
# guards run left to right, so the Observation roll happens only for a player facing the still-hidden grate
if g and has_tag(g, 'invisible') and has_tag(enactor, 'player') and skill_check(enactor, 'observation', -4):
    remove_tag(g, 'invisible')
    pemit(enactor, get_attr(g, 'reveal_msg'))
'''
```

[`remove_tag`](../reference/softcode.md#fn-remove_tag) works here because
the room and the grate share an owner, you. Softcode acts with its
owner's authority, so a stranger's room could not un-hide your grate.

Finally, cut the way back, since a one-way secret strands whoever finds
it. From inside the antechamber:

```text
@teleport me = Vault Antechamber
@open duct = Maintenance Corridor
@desc duct = The crawlway back up into the maintenance corridor.
```

## Try it

As a player (a superuser sees everything, so `quell` first and `unquell`
after), stand in the office and walk the sequence:

```text
east                -> maybe: "One grate sits loose in its frame..." (Observation at -4)
look                -> no grate in the exits line if you missed it
search              -> Observation at -2: "One grate sits loose in its frame -- a crawlway yawns behind it!"
look                -> Exits: ... loose grate
loose grate         -> you are in the Vault Antechamber
duct                -> and back
```

If you already know it is there, `loose grate` works even while it is
still invisible, because knowledge is the key.

## Going further

- **Per-character reveals:** instead of stripping the tag, cache the find
  per player with
  [`set_attr`](../reference/softcode.md#fn-set_attr)`(me, 'found_' + enactor.id, 1)`
  and gate a `[[...]]` line in the room description on it. The tag stays
  on, so only the description differs per viewer.
- **Block traversal until found:** `@lock` the exit with the basic
  (traverse) lock the [lockable door](025_lockable_door.md) uses, and have
  the reveal also
  [`clear_lock`](../reference/softcode.md#fn-clear_lock)`()` it, so
  guessing the name stops working until the grate is found.
- **A spoken password:** set a listen trigger,
  `@set loose grate/listen_open = ^*mellon*: remove_tag(me, 'invisible')`,
  and saying the word reveals the grate, because listen triggers fire on
  overheard speech.
- **Alarm on discovery:** swap the
  [`pemit`](../reference/softcode.md#fn-pemit) for a zone-wide
  [`act`](../reference/softcode.md#fn-act)`(..., targeting='zone')`, and
  the find becomes an event guards elsewhere can hear.
