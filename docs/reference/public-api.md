# Public API

These are the names a game may import. They are frozen by
`tests/test_public_api.py`: changing them is a deliberate edit, and they
do not move between releases without notice. **Everything else may move
without notice**, including the module a public name happens to live in.
Import a name from its public home, not from the module behind it.

Public means:

- `realm.__all__`, below;
- `realm.features` (the `Feature` declaration API and `load`), and the
  entry-point group `realm.features` an add-on package declares its
  feature in ([Add-on packages](../guides/features.md#add-on-packages));
- `realm.testing` and its pytest plugin `realm.testing.fixtures`;
- each `realm.std.<feature>.__all__` and `realm.games.<name>.__all__`.

Every public name loads on first use, so `import realm` loads no feature:
a bare world stays bare.

## `realm`

```python
from realm import Feature, GameObject, Pool, pools
```

| Name | What it is |
|---|---|
| `Feature`, `FeatureError` | declare a feature ([Features](../guides/features.md)) |
| `CLASSIC` | every built-in feature, the default `FEATURES` |
| `GameObject` | rooms, things, exits, characters |
| `Action`, `propagate`, `fire_event` | build and propagate an action; fire a lifecycle event |
| `ActionType` | the kernel's action types |
| `Behavior` | the base class for behaviors |
| `CommandContext` | what a command function receives |
| `Pool`, `pools` | a pool definition, and the pool module (`harm`, `mend`, `spend`, `settle`, ...) ([Pools](../guides/pools.md)) |
| `ops`, `OpError` | the world operations (create, destroy, rename, ...) and their refusal |
| `dice` | the dice primitives (`roll`, `margin_under`, `margin_over`, `net_successes`, ...) |
| `defs` | definition objects (`find_def`, `all_defs`) for a feature's `def_kind` |
| `World`, `get_world` | the running world handle |
| `check_lock`, `controls`, `has_entitlement` | permissions |
| `Settings` | the game's settings |
| `softcode_function` | register a native function for softcode |
| `import_objects`, `import_pack`, `Store` | load an area file or a content pack in `init_world`; the store a loader writes to |

Rules and combat types are not in the root, because a bare world must not
load them.

## Features

| Package | Public names |
|---|---|
| `realm.std.rules` | `GameSystem`, `PointBuyMixin`, `ChargenStep`, `ChoiceStep`, `check`, `CheckResult`, `default_resolver`, `define_skill`, `define_class` |
| `realm.std.combat` | `Ruleset`, `AttackResult`, `DamageResult`, `RollResult`, `DamageType`, `Combatant`, `deal_damage`, `CombatView`, `CombatAction` |
| `realm.std.abilities` | `invoke_ability`, `AbilityAction` |
| `realm.std.items` | `gate_item_action`, `ItemAction` |
| `realm.std.talk` | `TalkAction` |
| `realm.std.economy` | `EconomyAction` |
| `realm.games.gurps` | `GurpsSystem`, `GURPSRuleset`, `TEMPLATES` |
| `realm.games.d20` | `D20System`, `D20Ruleset`, `CLASSES` |
| `realm.games.merc` | `MercSystem`, `MercRuleset`, `MERC_CLASSES` |

Every other built-in feature (`accounts`, `basics`, `building`, `crime`,
`effects`, `instances`, `look`, `movement`, `npc`, `social`, `spawning`,
`stealth`, `wilderness`) has no public names: a game uses it by listing it
in `FEATURES`.

## Testing

```python
from realm.testing import Simulator, build_test_world, reconfigure
```

A game's `tests/conftest.py` gets the fixtures with one line:

```python
pytest_plugins = ["realm.testing.fixtures"]
```

| Fixture | |
|---|---|
| `world` | a built world with no features, or the features a `@pytest.mark.features("look", ...)` marker names |
| `classic_world` | every built-in feature |
| `classic_world_unscripted` | every built-in feature, scripting off |
| `configure` | `configure(emote_sigil="@")` changes `world`'s settings |

Every test starts and ends with no world installed.

## Code in the docs

Every `import realm...` in a fenced `python` block of these docs, the
README, the templates and the examples is checked to resolve. A block that
is deliberately partial starts with `# doctest: skip`.
