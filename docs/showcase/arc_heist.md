# Arc: The Heist

Six showcase builds that stage a complete corporate break-in — case the
target from the security office, find the crawlway, mind the mine, dodge
the camera, gas the approach, crack the safe, and sneak out past the
sentry. Everything is **softcode**: a builder at a live prompt types
every line, no restart, no Python files.

Together the six exercise most of REALM's interaction machinery:
`$`-command triggers, `^`-listens, `ON_<EVENT>` witnesses, `on_check`
wards, `prompt()` wizards, `wait()` and `expire()` timing, quick
contests, behaviors (`watchful`, `script_ticker`), the perception engine
(invisible / hidden / search), attribute flags, and owner-authority.

## The tutorials, in build order

| # | Tutorial | You learn |
|---|---|---|
| 27 | [Secret door](027_secret_door.md) | concealed exits (`invisible` + `conceal_difficulty`), the built-in `search`, a passive Perception check on the room's `ON_ENTER` |
| 16 | [Combination safe](016_combination_safe.md) | a dial state machine in one attribute, `prompt()` wizards, the `secret` attribute flag, container + lock composition |
| 49 | [Landmine](049_landmine.md) | proximity triggers via witnessed `ON_ENTER`, `contest()` detection, `on_check` wards, `eval_attr()` helpers |
| 54 | [Security camera & monitor](054_security_camera.md) | the bug/tap pattern: `^listen` + `ON_ENTER`/`ON_LEAVE` relays via `pemit()`, opt-in watcher lists, same-owner gadget pairs |
| 48 | [Gas bomb](048_gas_bomb.md) | `wait()` fuses vs `expire()` lifetimes, spreading along the `exits()` graph, prototype-attribute copying, `script_ticker` exposure, skills as data |
| 160 | [Sneaking](160_sneaking.md) | the engine's stealth stack (`hide`, contests, `watchful`, loud actions) plus a creaky floor that raises a guard's alert level |

Each tutorial's **Build it** constructs one wing of the same map, in the
order above — later tutorials assume the earlier rooms exist. (Any build
also works standalone in your own rooms; only the room names in the
`@teleport` lines change.)

## The map

```
[The Security Office] <-- east/west --> [Maintenance Corridor]
   security monitor  (54)                  loose grate (27: hidden exit, search!)
   crumpled note     (16)                  gas bomb + prototype (48)
                                                |
                                        (loose grate / duct)
                                                |
                                                v
 [Nexagen Vault] <-- vault door/antechamber --> [Vault Antechamber]
    wall safe: dial 17, 4, 33 (16)          security camera -> office monitor (54)
    prototype schematics (inside)           anti-personnel mine (49: buried)
    Vault Sentry, watchful (160)            loose floorboard (160: creak)
```

A design thread runs through the arc: **concealment is one mechanism,
used three ways.** The grate (27), the mine (49), and the hiding thief
(160) all ride the same perception engine — the `invisible`/`hidden`
tags — and the one built-in `search` command finds all three. When the
engine composes like that, reuse it; don't fork it.

## The intended run

1. **Case the target** — read the `crumpled note` in the office (the
   combination is on it), then `watch` the security monitor: the camera
   shows you the antechamber before you ever set foot there.
2. **Find the way in** — go `east`, `search` the corridor until the
   loose grate turns up. Sharp-eyed characters may spot it just walking
   in.
3. **Mind your step** — entering the antechamber gives you one
   Observation-vs-concealment contest against the buried mine. You can't
   search a room you haven't entered; that's what makes it a minefield.
4. **Dodge the eye** — `cut camera` (an Electronics check) so the guards
   in the office see nothing.
5. **Gas the approach** — fetch the corridor's gas bomb, set it by the
   open vault door, `arm bomb`, and run; the cloud spreads through every
   open exit and forces HT-based fortitude rolls.
6. **Crack the safe** — `dial 17`, `dial 4`, `dial 33`. Or beat the
   lock with `pick` if your lockpicking (with tools) can absorb -4.
7. **Sneak out** — `hide`, slip past the Vault Sentry (Stealth vs. its
   Observation, floorboards permitting), and leave through the grate.

## Timing choices, stated once

- The bomb **fuse** is a `wait()` — exact, in-memory. A ten-second fuse
  that dies with a reboot is a defused bomb, which is acceptable (even
  cinematic).
- The gas **clouds** are `expire()` — persistent. A lingering hazard
  must dissipate even if the server restarts mid-linger; a `wait()`
  would orphan the cloud forever.

Every tutorial that schedules anything says which it uses and why.

## Authority notes (read before copying into a live game)

- Softcode runs with its **owner's** authority. The camera writes the
  monitor's watcher list, the corridor's `ON_ENTER` un-hides the grate,
  and the bomb spawns clouds in adjacent rooms — all of it works because
  one builder owns the whole wing. Split ownership and those writes
  quietly fail (by design).
- The mine and the gas damage whoever is **in reach** (same room) —
  proximity, not control, is the combat authority, so traps hurt players
  without owning them.

## Verification

```
cd ~/realm && source venv/bin/activate
pytest tests/showcase/test_heist.py
```

`tests/showcase/test_heist.py` reads every Build-it line of all six
tutorials **out of these markdown files** and drives it through the
real dispatcher as a builder player, then plays each Try-it flow
(16 tests). Nothing is transcribed into the test, so a build that stops
working here is a build that stopped working in the tutorial — the two
cannot drift. Dice are removed via the pluggable check
resolver — a check succeeds iff effective skill >= 10 — the same
convention as `tests/test_infiltration.py`, so contests go to the higher
skill, deterministically.
