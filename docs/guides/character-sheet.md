# The Character Sheet

What a player sees of their own character: what they wear (`equipment`),
what they know (`skills`), how they are doing (the prompt), and the things
they can eat, drink, quaff, recite and zap.

## Equipment

An item tagged `wearable` names where it goes in its `slot` attribute. The
game system says which slots exist, in what order, and how many items each
holds: `GameSystem.wear_slots()`.

| System | Slots |
|---|---|
| neutral (GURPS, D20) | none listed: any slot name an item gives, one item each |
| Merc | light, finger ×2, neck ×2, body, head, legs, feet, hands, arms, shield, about, waist, wrist ×2, held |

`wear <item>` puts it on. When the slot is full, it says what is worn there
and refuses. `wear <item> replace` takes off whatever has been worn
there longest and puts the new item on. Taking off goes through the same
gated `item:on_remove` as `remove`, so a cursed ring that refuses to come off
also refuses to be replaced. Under Merc, an item whose slot the system does
not have (ROM's `float`) cannot be worn.

`equipment` (`eq`) lists every slot in the system's order, with `nothing`
in the empty ones, then anything worn elsewhere, then the wielded weapon:

```text
You are using:
  <light>   nothing
  <finger>  a gold ring
  <finger>  nothing
  <neck>    nothing
  ...
  <wielded> a short sword
```

`inventory` lists only what is carried, not what is worn or wielded.

A system of your own lists its slots like this:

```python
from realm.games.gurps import GurpsSystem


class GameRules(GurpsSystem):
    def wear_slots(self):
        return [("head", 1), ("body", 1), ("hands", 2), ("belt", 4)]
```

## Skills

`skills` (`sk`) lists the skills the character has trained, with their
levels as the game system writes them (`GameSystem.format_skill`): `14`
under GURPS, `+14` under D20, `14%` under Merc. A skill whose `skill_def`
has a `group` attribute is listed under that heading:

```text
@set lockpicking/group = Thievery
```

`score` (`points`) no longer lists skills. It shows the rest of the sheet
in the system's own terms.

## The prompt

After each batch of output, a player sees a prompt line. Out of the box:

```text
<27/30hp>
```

The template is the player's own (`prompt <template>`), else the game's
`PROMPT` setting. These tokens are filled in:

| Token | Is |
|---|---|
| any pool name, and `max_<name>` | `{hp}`, `{max_hp}`, `{mana}`, `{move}`, `{shields}` ... |
| `{name}`, `{room}` | the character's name, the room's name |
| `{combat}` | the condition of whoever they are fighting (`excellent`, `scratched`, `bruised`, `wounded`, `nasty`, `hurt`, `awful`); empty out of a fight |
| `{level}`, `{xp}` | the attributes, when the character has them |

A token the character does not have is left as typed. `prompt` shows the
current template, `prompt default` goes back to the game's, and
`prompt off` turns it off. A template set with `prompt` always ends with a
space.

The Merc scaffold (`realm init --system merc`) and the Midgaard template
set `PROMPT = "<{hp}hp {mana}m {move}mv> "`.

When it appears:

- after every command, even one that printed nothing;
- once after a batch of unsolicited output (someone speaks, a combat
  round), not after every line;
- never before login, and not while a softcode prompt or wizard is waiting
  for an answer (its question is the prompt).

Over telnet the prompt is written without a newline and followed by
`IAC EOR` when the client accepts the EOR option (REALM offers it), or
`IAC GA` when the client refused to suppress go-ahead. Output that arrives
after a prompt starts on a new line. A WebSocket client gets the prompt as
its own frame, `{"type": "prompt", "text": "..."}`.

### Your own prompt

The prompt is a feature declaration, one per game. A game replaces the
default in its `game.py`:

```python
from realm import Feature

feature = Feature("mygame")


@feature.prompt(replace=True)
def my_prompt(player):
    hp, top = player.db.get("hp"), player.db.get("max_hp")
    return f"[{player.name} {hp}/{top}] " if top else None
```

Return `None` or `""` for no prompt. In tests, `Simulator.prompt(player)`
returns the prompt a player would see; `Simulator.seen()` never includes
prompts, because they are not messages.

## Consumables

### Food and drink (`items`)

| Command | Takes | Uses it up |
|---|---|---|
| `eat <food>` | an item tagged `food` you carry | the food is gone |
| `drink <container>` | an item tagged `drink` you carry, or one in the room (a fountain) | one of its `charges`; none means it never runs dry |

Each fires a gated `item:on_eat` or `item:on_drink` (hooks `EAT` and
`DRINK`), so softcode on the item runs and may refuse. It then mends the
pools named in the item's `restores` attribute (a pool the eater lacks is
skipped):

```text
@create a honey cake
@tag a honey cake = food
@set a honey cake/restores = {"hp": 5}
```

### Potions, scrolls, wands and staves (`abilities`)

| Command | Item tag | Aimed at | Uses it up |
|---|---|---|---|
| `quaff <potion>` | `potion` | the drinker | gone |
| `recite <scroll> [target]` | `scroll` | the target, else the spell's own default | gone |
| `zap <wand> [target]` | `wand` | the target, else the spell's own default | one charge |
| `brandish <staff>` | `staff` | the room: a harmful spell at everyone else, a kind one at everyone | one charge |

The item names its spells in `spells` (spell_def names) and the power they
come out at in `spell_level`. Each spell goes through the same pipeline as
`cast`: wards, saves and resistances apply, and a harmful one starts a
fight. It costs nothing, and anyone can use the item (a warrior can zap
a mage's wand). A wand or staff with no `charges` left fizzles. A spell
the world does not define does nothing; the item is still used up.

```text
@create a vial of bluish liquid
@tag a vial of bluish liquid = potion
@set a vial of bluish liquid/spells = ["cure light"]
@set a vial of bluish liquid/spell_level = 12
```

A line these commands cannot use (nothing by that name, or not the right
kind of item) goes to the world's softcode `$`-commands before it is
refused, as with `cast`. A builder's `$eat` on a buffet or `$drink` on a
bar still works.

ROM areas convert with all of this filled in ([Importing ROM
areas](../development/rom-import.md)).
