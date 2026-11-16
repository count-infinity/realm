# The Character Sheet

What a player sees of their own character: what they wear (`equipment`),
what they know (`skills`), how they are doing (the prompt), how they like
their screen ([player settings](#player-settings): `config`, the pager,
aliases), and the things they can eat, drink, quaff, recite and zap.

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

Before `wear` or `wield` does anything, the game system has its say
(`wear_refusal`, `repels`, [Game Systems](game-systems.md#the-world-around-the-character)).
Under Merc an item's `level` is the least level to use it, and an item
tagged `anti_good`, `anti_evil` or `anti_neutral` will not stay on a
character of that alignment:

```text
wear great helm
You must be level 10 to use a great helm.
wear holy ring
You are zapped by a holy ring and drop it.
```

A Merc character's alignment runs from -1000 to 1000 and shows on `score`
(`Alignment: 350 (good)`). Killing something far more evil than you moves
it toward good, far more good toward evil, and anything else a quarter of
the way to neutral; whatever you wear that the new alignment cannot wear
zaps off.

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

The template is the player's own (`prompt <template>`, or
`config prompt <template>`; one of their [settings](#player-settings)),
else the game's `PROMPT` setting. These tokens are filled in:

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
its own frame, `{"type": "prompt", "text": "..."}` (with `segments` when it
has color, like text), which the browser client shows in a fixed line
([Protocols](../protocols/overview.md#the-browser-client)). A client with an
out-of-band channel (GMCP, WebSocket) is also sent `Char.Vitals` beside the
prompt whenever one of the player's pools changed.

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

## Player settings

`config` lists a player's settings and changes them:

```text
config
Your settings (config <option> <value> changes one):
  autoexit       on (default)
  autogold       off (default)
  autoloot       off (default)
  autosplit      off (default)
  brief          off (default)
  color          on (default)
  pagelength     24 (default)
  palette        none (default)
  prompt         <{hp}/{max_hp}hp> (default)
  screenreader   off (default)
config pagelength 40
pagelength     40
config palette r=m b=c
palette        b=c r=m
config palette default
palette        none (default)
```

`config <option>` shows one with what it does, and `config <option>
default` goes back to the game's own.

| Setting | Values | Does |
|---|---|---|
| `color` | on, off | color in what the player is sent (also `color on\|off`) |
| `pagelength` | a number | lines on one screen of long output; 0 never holds output |
| `prompt` | a template, off | the [prompt](#the-prompt) (also `prompt`) |
| `screenreader` | on, off | plain text for a screen reader: no color, and no lines drawn only for looks (`=====`, `+---+---+`) |
| `palette` | `r=m b=c` ... | swaps colors the player finds hard to read; letters `x r g y b m c w`, bright stays bright |
| `autoexit` | on, off | the `Exits:` line under a room (`look`); `exits` lists them anyway (`look`) |
| `brief` | on, off | leaves the description out of a room you walk, follow or recall into; `look` still shows it (`look`) |
| `autoloot` | on, off | takes everything, money too, from the corpse of what you kill (`combat`) |
| `autogold` | on, off | takes only the money from it (`combat`) |
| `autosplit` | on, off | shares money taken that way with your party in the room, as `split` does (`combat`) |

The last five are ROM's `PLR_AUTO*` and `COMM_BRIEF` bits; each is declared
by the feature named in brackets, so a game without it does not list it.
Without `autoloot` or `autogold` a corpse keeps what it held, money
included: `look corpse` shows it and `get all from corpse` (or `get gold
from corpse`) takes it.

Settings belong to the **account** when the character has one, so every
character of one person shares them; a character with no account keeps
its own. `color`, `screenreader` and `palette` take effect where text
leaves the server for a telnet client. A character from a world saved
before settings lived on accounts carries its `color` and `prompt` on
itself; the first time it enters play they move to its account (a value
the account already has wins).

A feature adds a setting through the `options` service of `basics` (and
copes with a game that leaves `basics` out). This is how `combat` declares
`autoloot`:

```python
@feature.on_install
def _settings(world) -> None:
    options = world.services.get("options")
    if options is not None:
        options.toggle("autoloot", "Take everything from the corpses of what you kill.",
                       False)
```

Its code reads the value with `realm.core.options.get_option(player,
"autoloot")` (None when the player has set nothing). A feature installs
after `basics` when `FEATURES` lists it later (as `CLASSIC` does).
`options.number(name, doc, default)` declares a number; a feature that
requires `basics` may add any `realm.std.basics.options.Option(name, doc,
parse, show, default)`.

### Long output: the pager

Output longer than one screen is held. The player sees a screen, and the
prompt becomes:

```text
[more: enter, b back, q quit]
```

Enter shows the next screen, `b` the one before, `q` stops. Any other line
stops paging and runs as a command. A screen is the player's `pagelength`,
else the height the client reported (telnet NAWS, a web client's resize),
else the game's `PAGE_LENGTH` (24); 0 turns paging off. `help`, `who`,
`@examine`, `skills`, `socials`, `config`, `alias`, a channel's history,
`mail` and the editor's `.l` page their output. Code pages its own with
`session.send_paged(text)`.

### Aliases

```text
alias kk = kick $1
kk fido                 runs: kick fido
alias ts = tell $1 Hello, $1!
alias gc = get all corpse
alias                   lists them
unalias kk
```

In the command line, `$1` to `$9` are the words typed after the alias and
`$*` all of them; a line with none of these gets the words added at the
end. Aliases belong to the character (its `aliases` attribute), at most
`ALIAS_LIMIT` (50). An alias is one word; it is expanded once, so an alias
inside an alias's line runs as typed, and a word that begins with `@` is
never an alias. `alias` and `unalias` cannot be aliased.

## Consumables

### Food and drink (`items`)

| Command | Takes | Uses it up |
|---|---|---|
| `eat <food>` | an item tagged `food` you carry | one `bite` of its `nourishment` (default: all of it); gone when that is |
| `drink [<container>]` | an item tagged `drink` you carry or one in the room; alone, a `fountain` here or the room when it is a `water_source` | one `sip` (50) of its `liquid_remaining`; a `fountain` never runs dry; a drink with no liquid loses one of its `charges` (none: it never runs dry) |
| `fill <container> [<fountain>]` | a container with `liquid_held` you carry | nothing: it fills from a fountain, or the water here |

Each fires a gated `item:on_eat` or `item:on_drink` (hooks `EAT` and
`DRINK`), so softcode on the item runs and may refuse. It then mends the
pools named in the item's `restores` attribute (a pool the eater lacks is
skipped), and moves food into the eater's `food` pool and drink into
`water` (MUD_PLAN step 12; a full stomach refuses more). Hunger and thirst
are in [Life and Death](life-and-death.md#hunger-thirst-and-fatigue).

```text
@create a honey cake
@tag a honey cake = food
@set a honey cake/restores = {"hp": 5}
@set a honey cake/nourishment = 100
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
