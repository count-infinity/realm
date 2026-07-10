# How a Character Is Born

When someone types `create Rook hunter2`, a chain of well-defined steps
turns an empty account into a playable character. Understanding that
chain is the key to changing *any* of the initial decisions — what
classes exist, what questions are asked, whether there's a creation
menu at all. This page is the map; the [how-to guides](#where-to-go-next)
are the turn-by-turn directions.

## The one object that owns the rules

Every rules decision lives in a single swappable object called the
**[GameSystem](../guides/game-systems.md)**. GURPS and D20 ship in-box;
you pick one with a line in `config.py`:

```python
GAME_SYSTEM = "gurps"   # or "d20", or your own id
```

The GameSystem answers a small, fixed set of questions:

| Method | Answers |
|--------|---------|
| `baseline_stats()` | what every fresh character starts with |
| `chargen_steps()` | the questions asked at creation (empty = no menu) |
| `finish_chargen()` | derived stats + the welcome line |
| `skill_defaults()` | untrained skill → (attribute, penalty) |
| `resolve_check()` | how a skill roll is resolved (3d6 vs d20…) |
| `improve_cost()` | character points to raise a skill |

The engine **never branches on "is this GURPS?"** — it asks the
GameSystem. That's the whole design: swap the object, swap the game.

## The birth sequence

Here is what actually happens, in order, when a character is created
([realm/server/game.py](https://github.com/realm-mud/realm) `_do_create`):

```
create Rook hunter2
   │
   ├─ AuthService.create_account          → account + GameObject exist
   │     └─ system.apply_baseline(player) → baseline_stats() written on
   │                                         the sheet (ST 10, HP 10, …)
   │
   ├─ steps = system.chargen_steps()
   │
   ├─ if steps:  ── drive the creation menu ───────────────────┐
   │     db.chargen_step = 0                                    │
   │     show steps[0].prompt(player)                           │  one
   │     … player answers … steps[i].handle() → advance        │  step
   │     (state in db.chargen_step — survives a reboot mid-way) │  loop
   │     when the last step is done ───────────────────────────┘
   │
   └─ system.finish_chargen(player)   → derived stats (HP from ST…),
         │                              returns "a soldier walks in…"
         └─ enter_world → player is dropped into the start room
```

Two things worth pinning down:

- **`chargen_steps()` returning `[]` is a first-class path.** No steps
  means `create` skips the whole menu and goes straight to
  `finish_chargen` → the world. That's how you get instant characters
  (see [Customizing Character Creation](../guides/custom-chargen.md)).
- **Creation is reboot-safe.** Mid-creation state is just
  `db.chargen_step` on the character. Reboot the server and the player
  reconnects exactly where they left off — the same mechanism the
  interactive [wizard system](../guides/wizards.md) uses.

## Where the "classes" actually come from

There is no class *system* — a "class" is just an entry a chargen step
offers. In GURPS it's the `TEMPLATES` dict at the top of
`realm/systems/gurps.py`:

```python
TEMPLATES = {
    "soldier": ("tough and dangerous …",
                {'strength': 12, 'health': 12, …},   # stats
                {'melee': 12, 'guns': 12, …}),        # skills
    "infiltrator": ( … ),
    …
}
```

`chargen_steps()` turns that dict into a `ChoiceStep` — a numbered menu
— and an `apply` function writes the chosen template's stats and skills
onto the character. So:

- **Adding a class** = adding a dict entry. It appears in the menu
  automatically. → [Add a Character Class](../guides/add-a-class.md)
- **A "class" is data, not a type.** Nothing in the engine knows a
  soldier from a face; both are a bag of attributes on a `GameObject`.
  This is why swapping to D20's class list, or a point-buy flow, or no
  flow at all, changes nothing else.

## The four levers, from smallest to largest

When you want to change an initial decision, reach for the smallest
lever that does the job:

1. **Change the options** — edit the `TEMPLATES` (GURPS) or `CLASSES`
   (D20) dict. New backgrounds, different stats.
2. **Change the questions** — subclass the system, override
   `chargen_steps()`: add a point-buy step, ask for a homeworld, reorder.
3. **Remove the questions** — `chargen_steps()` returns `[]`. Instant
   characters, or send players to an in-world academy to spend points
   with `improve`.
4. **Replace the rules wholesale** — subclass `GameSystem`, register it,
   point `config.py` at it. Your dice, your currency, your advancement.

Levers 2–4 never touch the `realm/` package: a game author registers
their system from `config.py`, which the engine imports at boot.

## Where to go next

- [Game Systems](../guides/game-systems.md) — the reference for GURPS,
  D20, and writing your own (lever 4).
- [Add a Character Class](../guides/add-a-class.md) — lever 1, the
  common case (levers 1).
- [Customizing Character Creation](../guides/custom-chargen.md) — levers
  2–3: reshape the flow, or drop it entirely for a training-school start.
