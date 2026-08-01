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
GAME_SYSTEM = "realm.systems.GurpsSystem"  # a built-in, unmodified (or ".D20System")
```

`realm init` writes the first form: the path points at your `GameRules`
class in `rules.py`, so what it subclasses is the *only* place the rules
are decided — there's no id string to fall out of sync with it.

Three systems ship in-box:

| | **GURPS** (`gurps`) | **D20** (`d20`) | **Merc** (`merc`) |
|---|---|---|---|
| Skill checks | 3d6 roll-UNDER effective skill | d20 + bonus vs DC 15 (roll-HIGH) | d100 roll-UNDER skill % |
| Chargen | template + bonus skill | pick a class | pick a class (of four) |
| Combat | 3d6 vs skill; AoA/AoD/Feint | d20 + mod + prof vs AC | d20 THAC0 vs descending AC |
| Advancement | flat 4 CP / skill level | escalating CP cost | **XP + leveling** (per-level HP) |
| Currency | credits | gold | gold |
| Derived | HP from ST | HP from HT, AC 10 + DEX | HP by class hit die; AC from worn armor |

`merc` is the Diku/Merc/ROM-lineage package (`realm.systems.MercSystem`) —
the rules a converted ROM area wants ([Importing ROM
areas](../development/rom-import.md)). Convert Midgaard, run it on `merc`,
and it plays like a real Diku. `examples/midgaard` is exactly that, ready to
run: a level-1 **barbarian** wakes in the Common Square with a club, kills
respawning fidos for XP, and trades at the shops (`realm init --template
midgaard`). Its five classes are warrior, barbarian, thief, cleric, and
mage; each starts with its class weapon (the ``outfit_new_character`` seam).

The whole package swaps: under `d20`, `stealth` and `persuade` roll a
d20 too — not just combat. (This wiring was completed 2026-07-07;
before that, non-combat checks ignored the system.)

## Advancement: two models, one seam

The two ways characters grow — **point-buy** (GURPS/D20: a kill banks
character points, `improve` spends them per skill) and **XP leveling**
(Merc: a kill banks experience that auto-converts to levels, each rolling
HP and granting practices) — are genuinely different, and the ABC does
**not** try to unify them into one model. Instead it exposes the single
point they share: a method that deposits a kill's reward.

```python
def grant_award(self, player, amount) -> None:
    # default: bank character points (point-buy)
    player.db.character_points = (player.db.get('character_points') or 0) + amount
```

The combat death path calls `system.grant_award(member, share)` and asks
no more. GURPS/D20 use the default; `MercSystem` overrides it to bank XP
and call its own `advance_level`. Everything model-specific — the XP
curve, the level-up routine — lives on the subclass, **not** on the ABC.
So a point-buy system and an XP system coexist by each owning its own
advancement and sharing only the deposit. If your system needs leveling,
override `grant_award` and add your own advancement methods; if it's
point-buy, do nothing and use `improve`.

Two sibling seams follow the same pattern:

- **`death_award(victim, killer=None)`** prices a kill in the system's
  own currency. The default is CP scaling (`points // 10`); MercSystem
  overrides it to pay the victim's full `points` as XP, bent by the
  killer/victim level difference (tough prey pays a premium, grey-con
  prey a pittance). An XP system that inherits the CP default starves
  its level curve — that exact bug shipped and is why the seam exists.
- **`score_lines(player)`** renders the `score` sheet in the system's
  vocabulary. The default is the point-buy view (character points +
  skills + `improve` hint); MercSystem shows level, experience-to-next,
  HP/mana, THAC0/AC, and what's wielded and worn. `score` should speak
  your system's language — override this, don't teach the command.

## Equipment-derived stats: an event, not a command hook

When a character wears or removes gear, the command fires
`item:on_wear`/`item:on_remove` like any other propagated action, and a
boot-registered observer (`equipment_observer`, alongside the stealth and
hostile observers) forwards the applied change to the active system:

```python
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
from realm.systems.base import GameSystem, ChoiceStep

class SavageSystem(GameSystem):
    system_id = "savage"
    ruleset_name = "d20"          # reuse a combat ruleset, or ship your own
    currency_name = "scrip"

    def skill_defaults(self):
        return {"shooting": ("dexterity", -4), "notice": ("intelligence", -5)}

    def resolve_check(self, obj, skill, modifier):
        # your dice here — return a CheckResult
        from realm.core.checks import default_resolver
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

The `resolve_check`, `improve_cost`, `death_award`, `score_lines`, and
`chargen_steps` methods are the seams; everything else inherits sensible
defaults.

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
