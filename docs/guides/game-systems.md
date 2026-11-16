# Game Systems (GURPS / D20 / your own)

A **GameSystem** is the swappable rules package. It bundles every rules
decision in one place — chargen, skills, how skill checks resolve,
character advancement, the combat ruleset, and the currency name — so
the engine never asks "is this GURPS?".

## Choosing one

`config.py` sets `GAME_SYSTEM` **before the first character is created**.
It's a **dotted import path** to a GameSystem subclass — one greppable
value a developer can follow straight to the source:

```python
GAME_SYSTEM = "rules.GameRules"            # your own system — the scaffolded default
GAME_SYSTEM = "realm.games.gurps.system.GurpsSystem"  # a built-in, unmodified (or ".D20System")
```

`realm init` writes the first form: the path points at your `GameRules`
class in `rules.py`, so what it subclasses is the *only* place the rules
are decided — there's no id string to fall out of sync with it.
`realm init --system gurps|d20|merc` picks that base class (GURPS by
default), and the commented examples in `rules.py` are written for it.

The `rules` feature (in `CLASSIC`) resolves it when the world is built and
installs it as `world.rules`, with the world's skill checks resolving and
defaulting through it. A world without `rules` has no game system: checks
use the kernel's neutral 3d6 roll-under, and character creation has no
steps. `GameSystem` and its helpers live in `realm.std.rules.system`.

Three systems ship in-box:

| | **GURPS** (`gurps`) | **D20** (`d20`) | **Merc** (`merc`) |
|---|---|---|---|
| Skill checks | 3d6 roll-UNDER effective skill | d20 + bonus vs DC 15 (roll-HIGH) | d100 roll-UNDER skill % |
| Chargen | template + bonus skill | pick a class | pick a class (of four) |
| Combat | 3d6 vs skill; AoA/AoD/Feint | d20 + mod + prof vs AC | d20 THAC0 vs descending AC |
| Advancement | flat 4 CP / skill level | escalating CP cost | **XP + leveling** (per-level HP) |
| Currency | credits | gold | gold |
| Derived | HP from ST | HP from HT, AC 10 + DEX | HP by class hit die; AC from worn armor |

`merc` is the Diku/Merc/ROM-lineage package (`realm.games.merc.system.MercSystem`) —
the rules a converted ROM area wants ([Importing ROM
areas](../development/rom-import.md)). Convert Midgaard, run it on `merc`,
and it plays like a real Diku. `realm/examples/midgaard` is exactly that, ready to
run: a level-1 **barbarian** wakes in the Common Square with a club, kills
respawning fidos for XP, and trades at the shops (`realm init --template
midgaard`). Its five classes are warrior, barbarian, thief, cleric, and
mage; each starts with its class weapon (the ``outfit_new_character`` seam).

The whole package swaps: under `d20`, `stealth` and `persuade` roll a
d20 too — not just combat. (This wiring was completed 2026-07-07;
before that, non-combat checks ignored the system.)

## Advancement: neutral by default, two models on top

The two ways characters grow — **point-buy** (GURPS/D20: a kill banks
character points, `improve` spends them per skill) and **XP leveling**
(Merc: a kill banks experience that auto-converts to levels, each rolling
HP and granting practices) — are genuinely different, and the base class
does **not** pick either. `GameSystem` answers its four advancement
questions neutrally:

| Method | Neutral `GameSystem` | `PointBuyMixin` (GURPS, D20) | `MercSystem` |
|---|---|---|---|
| `improve_cost(skill, level)` | `None`: `improve` says the game has no skill purchase | 4 (D20 escalates) | inherits `None`; Merc trains with practices |
| `death_award(victim, killer)` | 0: kills award nothing | the victim's `points` over ten | the victim's `points` as XP, bent by level difference |
| `grant_award(player, amount)` | nothing | bank `character_points` | bank XP, then `advance_level` |
| `score_lines(player)` | the character's pools (`HP: 7/10`) | character points, skills, the `improve` hint | level, XP to next, pools, THAC0/AC, gear |

A point-buy game lists the mixin first: `class MySystem(PointBuyMixin,
GameSystem)`. The combat death path calls `system.death_award` and, when it
is above 0, `system.grant_award(member, share)` for each party member, and
asks no more. Everything model-specific (the XP curve, the level-up
routine) lives on the subclass, not on the base, so a point-buy system and
an XP system coexist by each owning its own advancement and sharing only
the deposit. An XP system that inherited the character-point
`death_award` would starve its level curve; that bug shipped once, and is
why the seam exists.

## The character sheet

| Method | Neutral `GameSystem` | `D20System` | `MercSystem` |
|---|---|---|---|
| `wear_slots()` | `[]`: any slot name, one item each | inherits | Diku's 14 places, with two fingers, necks and wrists |
| `format_skill(skill, level)` | the number | `+14` | `14%` |

See [The Character Sheet](character-sheet.md).

## Recovery and death

Two more hooks, both neutral by default ([Life and Death](life-and-death.md)):

| Method | Neutral `GameSystem` | `MercSystem` |
|---|---|---|
| `regen(obj, pool_name)` | a twentieth of the pool's max, at least 1 | `hp` by constitution and level, `mana` by intelligence or wisdom and level, `move` by dexterity and level |
| `on_death(player, killer)` | nothing | lose a quarter of a level's experience, never a level |

`regen` is the amount one `REGEN_INTERVAL` restores to a character out of
combat, standing; the `vitals` feature multiplies it for resting and
sleeping. `on_death` is called only under `PLAYER_DEATH = "respawn"`,
after the corpse is left and before the player returns home.

`score` should speak your system's language: override `score_lines`, don't
teach the command. `pool_lines(player)` (from `realm.std.rules.system`)
renders the pools line Merc's sheet uses.

## Pools

`pools()` returns the world-default pool definitions for this game's
health and resources ([Pools](pools.md)). The base returns `[Pool("hp")]`;
`MercSystem` returns `hp`, `mana` and `move`, and its characters start
with `move` 100/100 as well as `hp` and `mana`.

## Equipment-derived stats: an event, not a command hook

When a character wears or removes gear, the command fires
`item:on_wear`/`item:on_remove` like any other propagated action, and a
boot-registered observer (`equipment_observer`, alongside the stealth and
hostile observers) forwards the applied change to the active system:

```python
# doctest: skip
def on_equipment_change(self, player) -> None:
    # default: nothing is equipment-derived
```

`MercSystem` overrides it to `recompute_ac` (Diku AC comes from worn
armor's `ac_apply`); the default no-op means systems that cache nothing
from gear ignore it. The wear command never touches the rules package —
any path that fires the event (softcode, a future auto-equip) reaches the
hook for free. A GURPS armor→DR pipeline would override this same hook.

## Changing systems after launch — don't

`GAME_SYSTEM` is a **boot-time deployment choice, not a live toggle.**
Characters are stamped with the system they were created under
(`db.game_system`). If you change the config and restart:

- Existing characters keep their attributes, but those attributes were
  authored under the old rules (a GURPS soldier's ST 12 means nothing
  to D20's AC-based combat). On login they get a warning:
  *"[!] Rook was created under 'gurps' but this server now runs 'd20'."*
- There is **no migration** — sheets are not recomputed. Pick your
  system before opening to players.

Mid-character-generation swaps are guarded (the flow won't crash) but
will hand a half-made character the new system's prompts. Again: choose
once.

## Writing your own

If you want rules unlike GURPS or D20, subclass `GameSystem` directly
instead of a built-in. Put it in `rules.py` (replacing the scaffolded
`GameRules`) and point `config.py` at it — same as any game system:

```python
# rules.py
from realm.std.rules import ChoiceStep, GameSystem, PointBuyMixin

class SavageSystem(PointBuyMixin, GameSystem):    # kills bank CP; improve spends
    system_id = "savage"
    ruleset_name = "d20"          # reuse a combat ruleset, or ship your own
    currency_name = "scrip"

    def skill_defaults(self):
        return {"shooting": ("dexterity", -4), "notice": ("intelligence", -5)}

    def resolve_check(self, obj, skill, modifier):
        # your dice here — return a CheckResult
        from realm.std.rules import default_resolver
        return default_resolver(obj, skill, modifier)

    def improve_cost(self, skill, current_level):
        return 2

    def chargen_steps(self):
        return [ChoiceStep("archetype", "Pick your archetype:",
                           {"gunslinger": "fast draw", "medic": "field surgery"},
                           self._apply)]
```

```python
# config.py
GAME_SYSTEM = "rules.SavageSystem"
```

The `resolve_check`, `improve_cost`, `death_award`, `grant_award`,
`regen`, `on_death`, `wear_slots`, `format_skill`, `score_lines`, `pools`
and `chargen_steps` methods are the seams; everything
else inherits sensible defaults. Leave out `PointBuyMixin` and the game has
no advancement economy until you write one.

Two combat-adjacent settings worth knowing:

- **`COMBAT_RULESET`** (config) defaults to unset, which means *the game
  system chooses* — each system declares its paired ruleset via
  `ruleset_name` (MercSystem → `merc`, GurpsSystem → `gurps`). Set it
  explicitly only to deliberately mix (merc rules over GURPS combat).
- **`SHOW_ROLLS`** (config) puts every combat roll's arithmetic on the
  participants' own lines — `[d20(13) vs need 16 (THAC0 20 - AC 6)]
  [2d4(5)+1 = 6]` — because every ruleset narrates its rolls
  (`RollResult.description`). Players override with `showrolls on|off`;
  bystanders never see roll detail. Ship a
custom combat ruleset by registering it with `RulesetRegistry` and
pointing `ruleset_name` at it.

For a full worked build — a percentile (d100) system with range-based combat
and condition-scaled armor, both the `GameSystem` *and* the combat `Ruleset`
end to end — follow [Creating Your Own System](creating-your-own-system.md).
