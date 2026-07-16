# Tutorial: The Abandoned Lighthouse

A complete one-shot adventure, built live from an empty database — no
world files, no Python, just you connected as the superuser. Every
section adds one layer:

1. **[The Island](01-the-island.md)** — rooms, exits, descriptions,
   and details only sharp-eyed characters notice.
2. **[Keys and Doors](02-keys-and-doors.md)** — objects, a locked
   trapdoor, and the key hidden in plain sight.
3. **[Living Things](03-living-things.md)** — NPCs, behaviors, cloning,
   and first conversations.
4. **[Softcode](04-softcode.md)** — commands and reactions you script
   in-game: a storytelling ghost, a floor that bites.
5. **[The Banshee](05-the-banshee.md)** — fear, combat, loot, and the
   ferryman who can be bribed. Opening night.

**Act II — Across the Gullwater.** The lamp is lit, but the keeper's
chart went down with his supply ship. The sequel trades one island
for an ocean — and shows the engine's big machinery:

6. **[The Gullwater](06-the-gullwater.md)** — a procedural sea from
   one region object: wilderness cells that materialize underfoot
   and evaporate behind you.
7. **[The Ferry](07-the-ferry.md)** — a boat is not a system:
   containment, movement, and three softcode commands.
8. **[Overboard](08-overboard.md)** — build drowning from primitives
   in one line; the boat is your waterworthiness.
9. **[The Wreck](09-the-wreck.md)** — a per-party dungeon behind a
   door on the seabed: instances, landmarks, and the finale.

**Act III — Saltmarsh.** The chart is delivered and the ferryman owes
you a crossing. The town on the far shore is where the engine's
*social* machinery lives — money, opinions, crime, magic, and the law:

10. **[The Crossing](10-the-crossing.md)** — an NPC runs a timed,
    stateful, cancellable action sequence: `wait` + `trigger` +
    `force`, and the ferryman rows you to town.
11. **[Market Day](11-market-day.md)** — a shop from one behavior;
    prices that read dispositions; persuasion as a discount.
12. **[The Cutpurse](12-the-cutpurse.md)** — add a pickpocket skill
    to the *rules as data*, hang the verb on a zone, and let a
    forced shout summon the law.
13. **[The Enthrall Spell](13-the-enthrall-spell.md)** — mind-magic
    from an item: `cast()`, will contests, wards that refuse, and
    thralls that wear off.
14. **[The Reading of the Will](14-the-reading-of-the-will.md)** —
    a notary runs the finale: multi-condition gates, a witness
    errand, and a `prompt()` you answer in your own words.

The premise (all public-domain folklore): the light on Gullwing Isle
went dark three winters ago. The keeper never came ashore. The
villagers pay a ferryman to keep people *away* — but you've heard
there's something in the lighthouse worth the climb.

Total time: about an hour for Act I, half that for each act after.
Type everything yourself — the point is that a whole adventure is
buildable *from inside the game*.

!!! tip "When you want more"
    Each page ends with a **Learn more** box pointing at the deeper
    docs (behaviors, softcode reference, the authority model). The
    happy path never needs them.
