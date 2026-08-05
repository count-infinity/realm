# The Bare Kernel & Feature Packs

*Planned 2026-08-04.* The target shape of REALM's engine/content boundary:
**out of the box, REALM is a social MU\*.** No stats, no skills, no
stealth, no `dark` tag, no combat. Everything genre-shaped arrives as an
importable **feature pack** — stealth, light, locksmithing, combat, a game
system, a skill list. The kernel keeps mechanisms; packs keep every
vocabulary word.

```python
# config.py — a social MU*: nothing to add, this is the default
GAME_SYSTEM = None

# config.py — an adventure game: opt in
GAME_SYSTEM = "realm.systems.GurpsSystem"
PACKS = ["light", "stealth", "locksmith", "adventure", "fantasy-skills"]
```

This document is the plan for getting there. It generalizes two earlier
findings: [skill roles](skills-inventory.md) (stock commands hardcode
skill names) and the perception audit below (the kernel hardcodes
*concept* names — `hidden`, `dark`, `invisible`).

## The architectural claim: push vs pull

Can almost everything be built as content over action events, propagation,
and react pipelines? **Yes for everything push-shaped; pull-shaped
questions need resolver seams — and three of the four already exist.**

- **Push** — someone *does* something and the world reacts: commands,
  `$command` softcode, the two-pass check/react propagation, `ON_<EVENT>`
  hooks, wards, behaviors, global observers
  (`add_observer` is already public — [game.py:378](realm/server/game.py#L378)
  merely hardwires which ones boot registers). This half is **already
  open**. A pack's verbs, reactions, traps, and alarms are content today.
- **Pull** — the engine *asks a question* mid-render or mid-roll: *who can
  see whom? what's this thing called to this looker? what modifies this
  check? how does a check resolve?* A query cannot be an event reaction —
  it needs an answer *now*, synchronously, inside `look` or `check()`. The
  kernel pattern for this is the **resolver chain**: the kernel owns one
  choke point; registered policy answers the question.

| Pull question | Choke point | Seam | Status |
|---|---|---|---|
| what is this called (to this looker)? | `perceived_name` | `register_name_resolver` | ✅ shipped |
| what modifies this check? | `condition_modifier` | `add_modifier_provider` | ✅ shipped |
| how does a check resolve? | `check()` | `set_check_resolver` / `resolve_rule` | ✅ shipped |
| **who can see whom?** | `can_see` / `room_is_lit` | `register_visibility_resolver` | ❌ **missing** |

Visibility is the one closed pull seam:
[`can_see`](realm/core/perception.py#L83) is a fixed if-chain over five
blessed tags (`dark`/`light`/`nightvision`/`invisible`/`see_invisible`/
`hidden`). The choke point is right (rendering, message attribution, and
targeting all consult it — an unseen actor is "Someone" everywhere, with
no way to leak); the policy is hardcoded. Open it and the wraith-world is
a three-line resolver:

```python
def wraith_plane(viewer, obj, current):
    if obj.has_tag('wraithworld'):
        return viewer.has_tag('wraithsight')
    return current
```

**A feature pack is push + pull together**: verbs and reactions on the
open push half, resolvers and providers on the pull seams, plus the data
(`skill_def`s, `ability_def`s, prototype objects) they operate on.

## What a feature pack is

Today a pack is worldio JSON only ([realm/packs](realm/packs/__init__.py)).
A feature pack adds a **native side**, honoring the existing trust
boundary (operators enable Python at deploy time; builders import data
in-game — the [bindings rule](../guides/resolution-and-bindings.md)):

```text
realm/packs/stealth/
  pack.json          # manifest: name, description, files, modules
  skills.json        # data: skill_defs (worldio) — imported into the world
  module.py          # native: commands, observers, resolvers, behaviors
```

- `modules:` in the manifest names Python to activate at **boot** when the
  pack is listed in `PACKS` (config). Third-party packs are pip packages
  exposing the same interface via an entry point (`realm.packs`).
- The data files import in-game (`@import pack`), exactly as today.
- A pack module registers through **public seams only**: command
  registration, `add_observer`, `register_visibility_resolver`,
  `add_modifier_provider`, behavior registration. If a stock pack needs a
  private hook, the kernel is missing a seam — that's the dogfood test.

## De-hardcoding inventory (what leaves the kernel)

| Today (hardcoded) | Becomes |
|---|---|
| `perception.py` policy: `dark`/`light`/`nightvision` in `room_is_lit`/`can_see_room` | **light pack** (resolvers + tags + help) |
| `hidden` in `can_see`, `LOUD_ACTIONS`, `break_stealth`, `stealth_observer`, `sneak`/`hide`/`search` commands | **stealth pack** (resolver + observer + commands + skill_defs) |
| `invisible`/`see_invisible`, `detect_magic` markers | **stealth pack** initially (split to an *arcane-sight* pack if it grows) |
| `pick` command | **locksmith pack** (`open`/`close`/`lock`/`unlock` stay kernel — lock *state* is kernel; defeating it by skill is content) |
| `persuade`/`fasttalk`/`consider` in social.py | **adventure pack** (`follow`/`party` stay kernel — they're social-MU\* material) |
| combat + magic command modules, hostile observer | **combat pack** (pairs with a `GAME_SYSTEM`) |
| crime observer | **crime pack** |
| `display_markers` (`glowing`, `magic`) | resolver-chain'd like names; stock markers move to their packs |
| skill roles (the six-entry kernel table from the skills doc) | **demoted to per-pack config** — each pack's commands read their skill from target attr → pack config → pack default. Only `flee` stays engine-floor (`ENGINE_SKILL_DEFAULTS`), and it fires only when combat runs |

**The kernel keeps** (mechanism, no vocabulary): objects/tags/attrs/locks,
propagation + events + observers, softcode engine (`$commands`,
`^listens`, `ON_<EVENT>`), the checks engine (name-free), the four pull
choke points and their seams, movement, communication, look/inventory/OLC,
game-system seam, persistence, the pack loader itself.

Out of the box that *is* a social MU\*: rooms, exits, say/pose/emote,
look, OLC, softcode, name resolvers for recognition/sdesc games. With an
empty visibility chain, everyone sees everyone — correct default for a
social game.

## Compatibility

`realm init` scaffolds a config with the adventure defaults **enabled**
(`PACKS = ["light", "stealth", "locksmith", "adventure"]` + a system), so
the tutorial, showcase, and every existing test see identical behavior.
`realm init --social` (or emptying `PACKS`) gives the bare kernel. The
Simulator grows a `packs=` argument mirroring `game_system=`, defaulting
to the adventure set so the ~47 existing test call sites run unchanged.

## Build order

1. **Visibility resolver seam** — `register_visibility_resolver` (compose
   over current verdict, like name resolvers; must-not-raise). Reimplement
   the five stock tags as pre-registered resolvers *through the public
   seam* (pure refactor, behavior identical). This is the dogfood proof
   and unblocks everything else.
2. **`PACKS` config + native pack side** — manifest `modules:`, boot-time
   activation, entry-point discovery for pip packs. Split
   `register_all_commands` into kernel-set + per-pack registration.
3. **Extract the stock packs** — light, stealth, locksmith, adventure,
   combat, crime — each moving its commands, observers, resolvers, tags,
   and help topics out of kernel modules. `realm init` default-enables
   them; tests green throughout.
4. **Softcode twins for the pull seams** — so a builder can do this
   in-game without Python: a `sight_def`-style data object (or
   `visibility_rule` softcode attr) evaluated by a stock resolver, and
   softcode-subscribed global observers (an object whose `ON_*` hooks hear
   a declared action-type set world-wide, not just its room). This is what
   makes the wraith-world buildable from an OLC prompt.
5. **Skills roadmap continues on top** — specialization (`@parent` +
   `requires`), progression seam, the fantasy-62 as a *data-only* pack
   ([skills-inventory.md](skills-inventory.md)). Roles shrink to pack
   config; the skills doc's Axis 1 is superseded accordingly.

## What this buys

- The user-workflow promise in CLAUDE.md becomes literal: `pip install
  realm`, pick packs, never touch REALM source.
- Every "can I build X from scratch?" gets one answer: *yes — the same way
  the stock pack does it*, because stock packs use only public seams.
- The engine-vision analogy completes: Godot ships a renderer you can
  swap; REALM ships perception/checks/resolution policy you can swap —
  and a default game (the stock packs) you can delete.
