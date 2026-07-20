# Creating Your Own System — a worked walkthrough

This builds a **complete custom rules package** from scratch, so you can see
where every rule decision goes. The running example is a **percentile system**:

- **Characteristics** are **Power, Speed, Luck, Diplomacy** (not the D&D six).
- **Skills** are percentages (0–100), rolled against **d100, roll-under** —
  succeed if the roll ≤ your skill. Untrained skills default to their
  governing characteristic × 5.
- Combat splits defense into **two layers**:
  - **Active dodge** — the attacker's weapon **attack band** (min–max) is rolled
    against the defender's **dodge**, a roll that scales with **Speed**; you land
    a hit only if **attack > dodge**.
  - **Armor DR** — a landed hit's damage is then reduced by armor's
    **`DR × condition`** (`DR × 0.99` pristine … `DR × 0.01` rags).
- **Damage** = `Power + random(weapon band) − armor DR`.

It's a deliberately un-GURPS, un-D20 system, which is the point: it exercises
every seam. For the terse reference, see [Game Systems](game-systems.md); this
is the narrative build.

## The two surfaces

A rules package plugs into **two** places, and it's worth seeing the split
up front:

| Surface | Class | What it owns |
|---|---|---|
| **`GameSystem`** (`realm.systems.base`) | you subclass it | *everything non-combat*: skill-check resolution, chargen, advancement, derived stats, currency |
| **Combat `Ruleset`** (`realm.combat.ruleset`) | you subclass it | *combat only*: attack, damage, armor, defeat |

They're wired together by one line: your `GameSystem` sets
`ruleset_name = "..."`, and the engine looks that name up in the combat
`RulesetRegistry`. Skill checks and combat are separate on purpose — a check
(`stealth`, `haggle`) resolves through `GameSystem.resolve_check`; a swing
resolves through the `Ruleset`. Both are yours to define.

Put all of this in your game's `rules.py` (what `realm init` scaffolds and
`config.py`'s `GAME_SYSTEM` points at).

---

## Part 1 — the GameSystem (skills, chargen, advancement)

```python
# rules.py
from realm.systems.base import GameSystem, ChoiceStep


class PercentileSystem(GameSystem):
    system_id = "percentile"
    ruleset_name = "percentile"     # our combat ruleset, registered in Part 2
    currency_name = "shillings"

    # --- Skill resolution: d100 roll-under -------------------------------

    def skill_defaults(self):
        # Which characteristic governs each skill (used for the untrained
        # base chance below). Our four stats: power, speed, luck, diplomacy.
        return {
            "stealth":    ("speed", 0),
            "lockpick":   ("speed", 0),
            "intimidate": ("power", 0),
            "haggle":     ("diplomacy", 0),
            "gamble":     ("luck", 0),
        }

    def resolve_check(self, obj, skill, modifier):
        from realm.core.dice import margin_under, roll
        trained = obj.db.get(f"skill_{skill}")
        if trained is not None:
            target = int(trained)                    # skills are stored as %
        else:
            # Untrained base chance = governing characteristic × 5.
            stat, _ = self.skill_defaults().get(skill, ("speed", 0))
            target = int(obj.db.get(stat) or 10) * 5
        # roll ≤ target succeeds; margin = how far under (degree of success).
        return margin_under(roll("1d100"), target + modifier)

    def improve_cost(self, skill, current_level):
        return max(1, current_level // 10)           # dearer near mastery

    # --- Character creation ---------------------------------------------

    def baseline_stats(self):
        return {"power": 10, "speed": 10, "luck": 10, "diplomacy": 10,
                "hp": 12, "max_hp": 12}

    def chargen_steps(self):
        return [ChoiceStep(
            "background", "Choose a background:",
            {"footpad": "+30% stealth, +20% lockpick",
             "envoy":   "+30% haggle, +20% gamble"},
            self._apply_background)]

    def _apply_background(self, player, key):
        grants = {"footpad": {"stealth": 30, "lockpick": 20},
                  "envoy":   {"haggle": 30, "gamble": 20}}
        for name, pct in grants.get(key, {}).items():
            player.db.set(f"skill_{name}", pct)

    def finish_chargen(self, player):
        player.db.set("max_hp", 10 + player.db.get("power", 10))
        player.db.set("hp", player.db.get("max_hp"))
        return "Your fate is cast. Welcome."
```

**Two things worth understanding here:**

**The resolver returns a graded `CheckResult`, not a bool.** `margin_under(rolled,
target)` (from `realm.core.dice`) hands back `(success, margin, …)` — the *degree*
of success, which softcode and combat both branch on. You're composing a stock
**reducer** (`margin_under`) with `roll("1d100")`; you never hand-write the
success test. Other families reuse the same reducer library: `margin_over` for
roll-high, `net_successes` for dice pools, `band` for PbtA. (See
[Resolution & Bindings](resolution-and-bindings.md).)

**This is the `(stat, penalty)` escape hatch in action.** The kernel's default
`skill_level` computes an untrained level as *attribute + penalty* — a
GURPS/D20 shape that percentile skills don't fit. Because `resolve_check`
receives the full `obj`, we simply **ignore that default and compute the
untrained chance ourselves** (`characteristic × 5`). The `(stat, penalty)` table
still declares *which* characteristic governs each skill, but the kernel's
arithmetic isn't load-bearing — you bypass it whenever your skills aren't
attribute-plus-offset. (See the note in
[the rules kernel](../design/rules-kernel.md).)

**Skip the Python entirely if you like.** For *trained* skills, you don't even
need a `resolve_check` method — a **softcode resolution rule** makes the skill
half pure data:

```python
class PercentileSystem(GameSystem):
    resolve_rule = "margin_under(roll('1d100'), skill() + mod)"
```

The Python override above exists only because we wanted the `characteristic × 5`
*untrained* rule. Use whichever fits.

For the chargen API (`ChargenStep`, `ChoiceStep`, prompts, multi-step flows),
see [Custom Chargen](custom-chargen.md); the `_apply_background` shape mirrors
what's there.

---

## Part 2 — the combat Ruleset (dodge, damage, armor)

Combat lives in a separate class with four required methods. The base
`Ruleset`'s own docstring even names *"PercentileRuleset: d100 roll-under"* as an
example — you're on a supported path. Note the **two defensive layers**: dodge
decides whether a hit *lands* (in `roll_attack`), and armor decides how much of a
landed hit *gets through* (in `apply_damage`).

```python
# rules.py (continued)
import random
from realm.combat.ruleset import (
    Ruleset, AttackResult, DamageResult, RollResult, DamageType,
)
from realm.combat.system import RulesetRegistry


class PercentileRuleset(Ruleset):
    name = "Percentile"
    required_stats = ["power", "speed", "hp"]

    # 1) Does it land? Weapon attack band vs the defender's ACTIVE DODGE.
    def roll_attack(self, attacker, defender, weapon=None, modifiers=None):
        lo, hi = self._band(weapon or attacker.obj, "atk", (1, 10))
        attack = random.randint(lo, hi) + sum((modifiers or {}).values())
        dodge = self._dodge(defender)
        hit = attack > dodge                         # strictly greater = land
        roll = RollResult(total=attack, dice=[attack], target=dodge, success=hit,
                          description=f"atk {attack} vs dodge {dodge}")
        return AttackResult(hit=hit, roll=roll, margin=attack - dodge)

    # 2) Raw damage: POWER + a draw from the weapon's damage band.
    def roll_damage(self, attacker, defender, attack_result, weapon=None):
        wlo, whi = self._band(weapon, "dmg", (1, 3))
        raw = attacker.get_stat("power", 0) + random.randint(wlo, whi)
        roll = RollResult(total=raw, dice=[raw], description=f"POW+weapon = {raw}")
        return DamageResult(total=raw, roll=roll,
                            damage_by_type={DamageType.PHYSICAL: raw})

    # 3) Armor absorbs a landed hit: DR × condition.
    def apply_damage(self, target, damage):
        dr = self._armor_dr(target)
        dealt = max(0, damage.total - dr)
        target.set_stat("hp", target.get_stat("hp") - dealt)
        damage.resisted = damage.total - dealt
        return dealt

    # 4) When is someone out of the fight?
    def is_defeated(self, combatant):
        return combatant.get_stat("hp", 0) <= 0

    # --- helpers ---------------------------------------------------------
    def _band(self, obj, prefix, default):
        """Read a (min, max) band off an object's db (atk_min/atk_max, …)."""
        if obj is None:
            return default
        lo, hi = obj.db.get(f"{prefix}_min"), obj.db.get(f"{prefix}_max")
        return (int(lo), int(hi)) if lo is not None and hi is not None else default

    def _dodge(self, defender):
        """Active dodge — a roll that scales with Speed (fast = harder to hit).
        An explicit dodge_min/dodge_max band on the defender overrides."""
        lo, hi = self._band(defender.obj, "dodge", (0, 0))
        if hi > 0:
            return random.randint(lo, hi)
        return random.randint(1, max(1, defender.get_stat("speed", 10)))

    def _armor_dr(self, defender):
        """Sum of worn armor's DR × its condition (0.0 rags … 1.0 pristine)."""
        return int(sum(
            o.db.get("dr", 0) * float(o.db.get("condition", 1.0))
            for o in defender.obj.contents
            if o.has_tag("worn") and o.db.get("dr") is not None))


RulesetRegistry.register("percentile", PercentileRuleset)
```

**How this maps to your spec:**

- `roll_attack` reads the attack band from the **weapon** (or the attacker if
  unarmed) and rolls it against the defender's **active dodge** — a
  `1..Speed` roll, so a fast foe is genuinely harder to hit. You land only on
  `attack > dodge`. A creature can pin its dodge to an explicit band with
  `dodge_min`/`dodge_max` if you don't want it Speed-derived.
- `roll_damage` is `Power + random(weapon band)`, returning *raw* damage.
- `apply_damage` is the **second** defensive layer: it subtracts armor's
  **`DR × condition`** and records the absorbed part in `damage.resisted` (for
  the "…but the mail turns most of it" message). So dodge avoids the hit; armor
  softens the ones that land.
- The combatant wrapper gives you `get_stat(name, default)` / `set_stat(...)` —
  reads/writes straight to `obj.db`, so `hp`, `power`, `speed`, and your bands
  are ordinary attributes.

The **data** these read is plain attributes on ordinary objects:

```text
@set rusty sword/atk_min = 4
@set rusty sword/atk_max = 12
@set rusty sword/dmg_min = 1
@set rusty sword/dmg_max = 6
@set goblin/speed = 8               # dodges 1–8; a quicker foe is harder to hit
@create scale hauberk
@tag scale hauberk = worn
@set scale hauberk/dr = 5
@set scale hauberk/condition = 0.85       # 85% intact → DR 4
```

---

## Part 3 — wiring it up

**Point the config at your system** (a boot-time choice, not a live toggle —
pick it before players are created):

```python
# config.py
GAME_SYSTEM = "rules.PercentileSystem"
```

That's the whole hookup for skills, chargen, advancement, and currency. The
**combat** ruleset registers itself the moment `rules.py` is imported (the
`RulesetRegistry.register("percentile", …)` line), and `PercentileSystem.
ruleset_name = "percentile"` tells the engine to use it. Keep the two names in
sync and you're done.

**Skills as data (optional but recommended).** `resolve_check` reads the
governing characteristic from `skill_defaults()`, but the per-character
percentages are just `db.skill_<name>` attributes, and the *skill list itself*
can live in the world as `skill_def` objects or an importable pack rather than
the Python dict — so builders add skills with no code change. See
[Skills & Classes as Data](data-driven-rules.md) and
[Content Packs](content-packs.md).

---

## Try it

```text
# a skill check (d100 roll-under)
@eval r = check(me, 'lockpick'); result = f"{'picked' if r.success else 'jammed'} (margin {r.margin})"

# an untrained skill falls back to characteristic × 5
@eval r = check(me, 'gamble'); result = f"luck×5 = {r.effective}%, {'won' if r.success else 'lost'}"

# a fight resolves through your ruleset
wield rusty sword
attack goblin
   -> You swing (atk 9 vs dodge 3) — POW+weapon 14, the goblin's rags turn 1: 13 through.
```

## What each characteristic does

The four stats each earn their keep, so the set feels intentional:

| Stat | Non-combat (skills) | Combat |
|---|---|---|
| **Power** | intimidate | damage (`Power + weapon`), derived max-HP |
| **Speed** | stealth, lockpick | active dodge (`1..Speed`) |
| **Diplomacy** | haggle | — (social encounters) |
| **Luck** | gamble | *(open — a natural crit hook, below)* |

## Design decisions still open (tune freely)

The two big ones are now settled — untrained skills are **characteristic × 5**,
and defense is a **dodge (avoid) + armor (absorb)** split. What's left to taste:

- **Give Luck a combat role.** It currently only governs `gamble`. A natural fit:
  roll Luck for a **critical** — `AttackResult` has `critical_hit`/`critical_miss`
  flags we leave `False`, and `roll_damage` can read `attack_result` to double a
  crit's dice. One check in `roll_attack` wires it in.
- **The dodge curve.** `1..Speed` is flat and swingy; you might floor it
  (`random(Speed//2, Speed)`) so the fast are reliably slippery, or subtract a
  fatigue penalty as a combatant tires.
- **Weapon vs. unarmed attack bands.** Unarmed currently falls back to the
  attacker's own `atk_*` band (default `1..10`); you could derive an unarmed band
  from Power instead.

## See also

- [Game Systems](game-systems.md) — the reference version of this, terser.
- [Custom Chargen](custom-chargen.md) — the `ChargenStep` API in full.
- [Resolution & Bindings](resolution-and-bindings.md) — the dice reducers
  (`margin_under`/`margin_over`/`net_successes`/`highest`/`band`) and the
  softcode `resolve_rule` path.
- [The Data-Driven Rules Kernel](../design/rules-kernel.md) — why the kernel
  stays ruleset-agnostic and where the seams are.
- [Combat](../design/combat.md) — the encounter engine your `Ruleset` plugs into.
