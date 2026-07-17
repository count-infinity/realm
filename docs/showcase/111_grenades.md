# 111. Grenades

> Checklist item 111 — [now] — *wait() fuses, room-loop damage(), rand scatter over exits()*

**What you'll build:** A frag grenade you arm **in your hand** (`pull
pin`), throw through any exit (`throw grenade <exit>`), and regret
holding too long. The blast sweeps whoever is in the room; a failed
Throwing check scatters the grenade through the wrong doorway.

**Concepts:** `wait()` fuses with `trigger me/<attr>` payloads, the
`exits()` graph walk from item 48, `rand()` scatter, `damage()`
proximity authority (and how a held grenade gets around it),
`skill_def` skills as data, and the shared death path softcode damage
feeds into.

## How it works

There is **no native `throw` verb** — throwing is a `$`-command on the
grenade itself, and since `$`-commands are found in your inventory as
well as the room (unlike `^`-listens), a grenade in your hand answers
`pull pin` and `throw grenade ...` wherever you carry it.

1. **Arming inverts item 48's rule.** The gas bomb *refused* to arm in
   your hands — set it down first. A grenade is the opposite decision,
   made on purpose: `pull pin` **requires** it in hand
   (`loc(me) == enactor`), because that's what grenades are. The fuse
   is a `wait(fuse, 'trigger me/boom')` — in-memory, exact, and
   acceptable to lose on a reboot, same reasoning as 48.

2. **The throw is a graph edge.** `exits(loc(enactor))` lists the ways
   out (filtering `closed` — you don't lob a grenade through a shut
   hatch); the named exit's `destination` attribute resolves to the far
   room via `get('#' + id)`. A passed Throwing check (a `skill_def`
   built from DX, like the pickpocket skill of tutorial 12) sends it
   where you aimed; a failure scatters it through a random *other* open
   exit — `rand()` over the remaining doorways. `teleport_obj(me, d)`
   moves the grenade: it controls itself, so no further authority is
   needed.

3. **The blast is proximity authority.** `damage()` only reaches things
   in the executor's room — which is exactly why the boom script first
   checks where it is. In a room: sweep `contents()` and hurt everyone
   who fails a Reflexes check. Still in someone's *hand* at zero: the
   grenade cannot damage the room from inside a pocket (its location is
   the holder, not the room), so it drops itself to the holder's room
   (`teleport_obj(me, loc(holder))`) and re-triggers one tick later —
   "it slips through your fingers," and then everyone standing there,
   holder included, eats the blast. Moves queue until the script ends,
   which is why the drop and the blast are two script runs chained by a
   `wait(0, ...)`.

4. **Deaths are real deaths.** Softcode `damage()` routes lethal
   results through the combat manager's one death path: NPCs die into
   lootable corpses, players fall unconscious in place — a grenade kill
   is exactly as real as a sword kill. (One caveat for other builds:
   this path does *not* propagate `combat:on_death`, so `ON_DEATH`
   witnesses — item 114's bounty board — never hear grenade kills. See
   the gap note there.)

## Build it

Two rooms and the two skills, as data:

```text
@dig The Bunker = bunker, out
bunker
@dig The Trench = trench, bunker
@create reflexes
@tag reflexes = skill_def
@set reflexes/stat = dexterity
@set reflexes/penalty = 0
@create throwing
@tag throwing = skill_def
@set throwing/stat = dexterity
@set throwing/penalty = 0
@reload
```

The grenade. Pin first — in-hand required, one-way, lights the fuse:

```text
@create frag grenade
@set frag grenade/fuse = 6
@set frag grenade/cmd_pull = $pull pin: pemit(enactor, 'Pick it up first -- you do not arm a grenade you are not holding.') if loc(me) != enactor else (pemit(enactor, 'The pin is already out!') if V('armed', 0) else (set_attr(me, 'armed', 1), remit(loc(enactor), name(enactor) + ' pulls the pin. The spoon pings away.'), wait(V('fuse', 6), 'trigger me/boom')))
```

The throw — validate the exit by name, then hand off to `fly` with the
exit id (`eval_attr` as a subroutine, the item 54 idiom):

```text
@set frag grenade/cmd_throw = $throw grenade *: doors = [e for e in exits(loc(enactor)) if not has_tag(e, 'closed')]; aimed = [e for e in doors if name(e) == trim(arg0)]; (pemit(enactor, 'You are not holding the grenade.') if loc(me) != enactor else (pemit(enactor, 'No open exit called ' + trim(arg0) + ' here.') if not aimed else eval_attr(me, 'fly', aimed[0].id)))
@set frag grenade/fly = e = get('#' + arg0); good = skill_check(enactor, 'throwing'); others = [x for x in exits(loc(enactor)) if not has_tag(x, 'closed') and x != e]; pick = e if good or not others else others[rand(0, len(others) - 1)]; d = get('#' + str(get_attr(pick, 'destination', ''))); (None if not d else (remit(loc(enactor), name(enactor) + ' hurls the grenade through the ' + name(pick) + ' exit' + ('!' if pick == e else ' -- no, wide! It caroms off the frame and skips the wrong way!')), teleport_obj(me, d), remit(d, 'A grenade bounces in and skitters across the floor!')))
```

Zero hour. The held-case drop, then the sweep:

```text
@set frag grenade/boom = spot = loc(me); held = spot != None and not has_tag(spot, 'room'); (remit(loc(spot), 'The live grenade slips through ' + name(spot) + "'s fingers!"), teleport_obj(me, loc(spot)), wait(0, 'trigger me/boom')) if held else eval_attr(me, 'blast')
@set frag grenade/blast = room = loc(me); del_attr(me, 'armed'); (None if not room else (remit(room, 'WHUMP. The grenade goes off in a fist of smoke and shrapnel!'), [pemit(o, 'You dive clear of the blast!') if skill_check(o, 'reflexes', -1) else (pemit(o, 'Shrapnel tears into you!'), damage(o, roll('2d6'))) for o in contents(room) if has_tag(o, 'player') or has_tag(o, 'npc')], destroy_obj(me)))
drop frag grenade
```

## Try it

```text
pull pin                    -> Pick it up first -- you do not arm a grenade you are not holding.
get frag grenade
pull pin                    -> (room) ... pulls the pin. The spoon pings away.
throw grenade trench        -> ... hurls the grenade through the trench exit!
```

Six seconds later The Trench reads `WHUMP.` — everyone there rolls
Reflexes at -1: pass and dive clear, fail and take 2d6. An NPC brought
to zero dies into a lootable corpse; a player goes down where they
stand. Fumble the throw and the room narrates the carom as it skips
through some *other* open doorway. And if you pull the pin and freeze:

```text
The live grenade slips through Zeke's fingers!
WHUMP. The grenade goes off in a fist of smoke and shrapnel!
```

**Engine gap (reported):** no native `throw`/projectile verb — thrown
objects are a softcode pattern (this page); a native throw with range
bands would let grenades interact with the encounter engine's
`withdraw`/`cover` model.

## Going further

- **Cook the grenade** — store the `wait()` handle
  (`set_attr(me, 't', wait(...))`) and add `$release spoon` to
  `cancel_wait` it: armed-but-safe until thrown, item 56's abort
  pattern.
- **Cover matters** — let the blast spare anyone behind item 109's
  fixture: skip targets where `has_tag(o, 'prone')` or grant +3 on the
  Reflexes roll if the room has a `cover`-tagged object.
- **Smoke and flashbangs** — swap the damage sweep for
  `apply_effect(o, 'modifier_effect', kind='dazzled', duration=4,
  check_mods={'all': -2})` — same fuse, different payload.
- **Frag the furniture** — have `blast` also strip `cover` tags from
  fixtures in the room (item 109's `$shred`, automated).
