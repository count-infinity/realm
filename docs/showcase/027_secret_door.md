# 027. Secret Door

> Checklist item 27 — now — *concealed exits, search + skill_check, perception engine*

**What you'll build:** A ventilation grate that is invisible until a
character finds it — deliberately with the built-in `search` command, or
passively with an Observation check the room rolls for everyone who
walks in. Part of the [Heist arc](arc_heist.md) (this is the arc's
first build; it digs the first three rooms).

**Concepts:** the perception engine's `invisible` tag,
`conceal_difficulty` / `reveal_msg`, the built-in `search` command, a
room `ON_ENTER` trigger with `skill_check()`, and the engine fact that
hidden exits stay traversable by name.

## How it works

Most of this build is *configuration of an existing engine feature*.
REALM's perception engine already knows what a concealed object is:

1. **Hiding is a tag.** Anything tagged `invisible` vanishes from room
   displays and can't be targeted by name. An exit is just an object in
   the room's contents, so a tagged exit disappears from the `Exits:`
   line too.
2. **`search` is built in.** It rolls the searcher's Observation at
   `-conceal_difficulty` against every concealed object in the room; on
   a success it strips the `invisible` tag and prints the object's
   `reveal_msg`. No softcode needed for the deliberate check.
3. **Traversal ignores concealment.** A hidden exit still works if you
   type its name — the engine deliberately exempts exits from
   perception-gated targeting, so "you knew the trick all along" is
   playable. (See `tests/test_perception.py` for the engine's own proof.)

The one thing the engine does *not* do is roll a **passive** check when
someone enters the room. That's a three-line softcode job: rooms witness
arrivals, so an `ON_ENTER` attribute on the room fires for every entry,
and `skill_check(enactor, 'observation', -4)` is the glance — stiffer
than a deliberate search, as it should be.

One honest semantic note: REALM's reveal is **world state**, not
per-character. Once anyone strips the `invisible` tag, the grate is
found for everybody. (A per-character variant is in Going further.)

## Build it

Dig the office and the corridor, and walk east:

```text
@dig The Security Office
@teleport me = The Security Office
@dig Maintenance Corridor = east, west
east
```

Dig the room *behind* the wall, and open a one-way exit to it. `@open`
creates the exit here in the corridor; nothing about it is secret yet:

```text
@dig Vault Antechamber
@open loose grate = Vault Antechamber
@desc loose grate = A dented ventilation grate low on the wall, screwed into its frame.
```

Now conceal it. `conceal_difficulty` is the penalty on the finder's
Observation check (2 = tucked away; 5 = a masterwork); `reveal_msg` is
the payoff line `search` prints:

```text
@set loose grate/conceal_difficulty = 2
@set loose grate/reveal_msg = One grate sits loose in its frame -- a crawlway yawns behind it!
@tag loose grate = invisible
```

The passive glance: the room witnesses every arrival, so its `ON_ENTER`
fires with the arriver bound as `enactor`. On a sharp enough glance
(Observation at -4) it does exactly what `search` would — strips the tag
and delivers the reveal line. The guard clauses keep it from firing on
NPCs, or after the grate is already found:

```text
@set here/on_enter = g = get('loose grate'); (remove_tag(g, 'invisible'), pemit(enactor, get_attr(g, 'reveal_msg'))) if g and has_tag(g, 'invisible') and has_tag(enactor, 'player') and skill_check(enactor, 'observation', -4) else None
```

(`remove_tag` works because the room and the grate share an owner — you.
Softcode acts with its owner's authority; a stranger's room couldn't
un-hide your grate.)

Finally, the way back — one-way secrets strand people. From inside:

```text
@teleport me = Vault Antechamber
@open duct = Maintenance Corridor
@desc duct = The crawlway back up into the maintenance corridor.
```

## Try it

As a player (as superuser you see everything — `quell` first, `unquell`
after), stand in the office:

```text
east                -> maybe: "One grate sits loose in its frame..." (Per at -4)
look                -> no grate in the exits line if you missed it
search              -> Observation at -2: "One grate sits loose in its frame -- a crawlway yawns behind it!"
look                -> Exits: ... loose grate
loose grate         -> you're in the Vault Antechamber
duct                -> and back
```

If you know it's there, `loose grate` works even while it's still
invisible — knowledge is a key.

## Going further

- **Per-character reveals** — instead of stripping the tag, cache the
  find per player (`set_attr(me, 'found_' + enactor.id, 1)`) and gate a
  `[[...]]` line in the room description on it — the same memoization
  trick as tutorial 04's loose flagstone. The tag stays on; only the
  description differs per viewer.
- **Block traversal until found** — `@lock` the exit and have the reveal
  also `clear_lock()` it, so guessing the name stops working.
- **A knock that opens it** — add `^*mellon*: remove_tag(me, 'invisible')`
  on the grate itself; speech-operated secrets fall out of listens.
- **Alarm on discovery** — swap the `pemit` for a zone-wide
  `act(..., targeting='zone')` and the find becomes an event guards can
  hear.
