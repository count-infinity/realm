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

Merc's class skills are things a player types. The `merc-classic` pack
ships them as ability definitions ([Abilities as Data](abilities.md)):

| Skill | Classes | Does |
|---|---|---|
| `kick` | warrior, barbarian | 1 to your level in damage |
| `bash` | warrior | damage and a round `stunned` |
| `backstab` | thief | a piercing weapon's damage, doubled and more with level, on someone not fighting |
| `rescue` | warrior | turns everyone fighting an ally on you |
| `disarm` (level 10) | warrior, thief | knocks the foe's weapon to the floor |
| `trip` | thief | the foe falls (`resting`) |

Each rolls the skill of the same name and waits a few beats before it can
be used again. `MercRuleset` adds the passive skills: a hit that lands is
still turned aside by the defender's `dodge`, then `parry` (wielding a
weapon), then `shield_block` (wearing a shield), each at ROM's chances
shifted by level difference; and a warrior's `second_attack` and
`third_attack` are more swings each round (the `Ruleset.extra_attacks`
hook). Every one of them is a `check()`, so whatever adjusts a check
adjusts them.

### What Merc implements

What a Diku player expects, and where it lives:

| Diku | In REALM under `merc` |
|---|---|
| THAC0 against descending AC, damroll, natural 20 and 1 | `MercRuleset` |
| hit points, mana and movement; regeneration by stat and level; resting and sleeping | `MercSystem.pools`, `regen`; the `vitals` feature ([Life and Death](life-and-death.md)) |
| movement points per sector | the `merc` feature's traversal gate |
| five classes, a hit die and THAC0 rate each, level-1 kit | `MERC_CLASSES`, `outfit_new_character` |
| experience, levels to `LEVEL_CAP` (50), practices and trains | `grant_award`, `advance_level`; [Progression](progression.md) |
| class titles on `who` (`Pat the Swordpupil (1 warrior)`) | each class's `titles`, `who_title` |
| percentile skills, learned by use after practice | `resolve_check`, `default_progression = "use"` |
| kick, bash, backstab, rescue, disarm, trip; dodge, parry, shield block, second and third attack | the `merc-classic` pack and `MercRuleset` (above) |
| spells, potions, scrolls, wands and staves | the `merc-classic` pack ([Spells as Data](spells.md)) |
| Diku's 14 wear places; an item's `level` is the least level to use it | `wear_slots`, `wear_refusal` |
| alignment, moved by kills; `anti_good`/`anti_evil`/`anti_neutral` gear zaps off | `on_kill`, `repels`, `alignment` on `score` |
| experience shared by level in a group; `split`, `autosplit` | `share_award`; the `economy` feature |
| `consider` by level difference | `consider` |
| hunger and thirst (CoffeeMud's, Decision D6); "You are hungry." on `score` | `pools` (`food`, `water`), `stomach`; the `needs` feature ([Life and Death](life-and-death.md#hunger-thirst-and-fatigue)) |
| `recall` costs half your movement (and 25 experience out of a fight) | `after_recall` |
| pets, charm person, mounts; one follower, one more each ten levels | `companion_limit`; the `companions` feature ([Pets, Charm and Mounts](companions.md)) |
| corpses, `autoloot`, `autogold`; death costs a quarter level | the `combat` feature, `on_death` |
| `scan`, `exits`, `where`, `report`, `brief`, `autoexit` | the `look` and `talk` features (any system) |
| guards, patrolmen, thieves, fidos, janitors, casters | behaviors the ROM importer attaches ([the import guide](../development/rom-import.md)) |

What it leaves out is ROM's mob programs; see the import guide.

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
is above 0, divides it with `system.share_award(award, members)` (neutral:
equal shares; Merc: by level) among the killer's party in the room and
pays each share with `award(member, share)` (`realm.std.rules.system`),
which runs the `rules` service's `award_filters` (the `needs` feature's
`HUNGRY_AWARD`, the `clans` feature's tax) and then calls
`system.grant_award(member, share)`; then
`system.on_kill(member, victim)` for each (neutral: nothing; Merc moves
alignment). Quest rewards pay the same way, through the `rules` service's
`award(player, amount)` ([Quests](quests.md#rewards)). It asks no more. Everything model-specific (the XP curve, the level-up
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

## The world around the character

Hooks the commands ask, each neutral by default (MUD_PLAN step 11):

| Method | Asked by | Neutral `GameSystem` | `MercSystem` |
|---|---|---|---|
| `who_title(player)` | `who`, after the name | none | `the Swordpupil (1 warrior)` |
| `consider(viewer, target)` | `consider`, before the attitude line | nothing | ROM's level-difference lines |
| `wear_refusal(player, item)` | `wear`, `wield` | none | "You must be level 10 to use a great helm." |
| `repels(player, item)` | `wear`, `wield` | never | `anti_good`, `anti_evil`, `anti_neutral` against alignment |
| `zap(player, item)` | when an item repels | it falls to the floor, "You are zapped by ..." | the same, then AC again |
| `recall_refusal(player)` | `recall` | in a fight, a `recall` check ("You failed!") | inherits; the check is 50% at wisdom 13 |
| `after_recall(player, from_combat=)` | `recall`, once moved | nothing | halves `move`; 25 experience out of a fight |
| `spendable_award(player)`, `spend_award(player, amount)` | `clan donate xp` ([Clans](clans.md#the-treasury-and-the-tax)) | None (nothing to give) | experience toward the next level (`PointBuyMixin`: unspent `character_points`) |
| `companion_limit(character)` | bonding, buying a pet, a charm, `companions` (unless `COMPANION_LIMIT_RULE` answers) | 2 | `1 + level // 10` |
| `mounted_modifiers(rider, mount)` | each attack by or on a rider | `{}` | `{}` (a game returns `{"attack": n, "defense": n}`) |

## Recovery and death

More hooks, neutral by default ([Life and Death](life-and-death.md)):

| Method | Neutral `GameSystem` | `MercSystem` |
|---|---|---|
| `regen(obj, pool_name)` | a twentieth of the pool's max, at least 1 | `hp` by constitution and level, `mana` by intelligence or wisdom and level, `move` by dexterity and level |
| `on_death(player, killer)` | nothing | lose a quarter of a level's experience, never a level |
| `stomach(obj)` | `(FOOD_FULL, WATER_FULL)`, scaled by `weight / NEEDS_BASE_WEIGHT` when `obj` has a weight | inherits |
| `fill_stomach(player)` | gives full `food` and `water` pools when `pools()` declares them and the player lacks them (creation, and each login) | inherits; Merc declares both |

`regen` is the amount one `REGEN_INTERVAL` restores to a character out of
combat, standing; the `vitals` feature multiplies it for resting and
sleeping. `on_death` is called only under `PLAYER_DEATH = "respawn"`,
after the corpse is left and before the player returns home.

`score` should speak your system's language: override `score_lines`, don't
teach the command. `pool_lines(player, exclude=())` (from
`realm.std.rules.system`) renders the pools line Merc's sheet uses; Merc
leaves out `food` and `water` and says "You are hungry." instead.

## Pools

`pools()` returns the world-default pool definitions for this game's
health and resources ([Pools](pools.md)). The base returns `[Pool("hp")]`;
`MercSystem` returns `hp`, `mana` and `move`, and its characters start
with `move` 100/100 as well as `hp` and `mana`; and `food` and `water`
(`regen=False`), full at `stomach()`, which the `needs` feature empties
([Life and Death](life-and-death.md#hunger-thirst-and-fatigue)).

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
