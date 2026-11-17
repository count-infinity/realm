# Accounts, Achievements and Bans

A person logs in to an **account**; an account holds several
**characters**. Anything a game keeps on the account (achievements,
unlocks, a shared bank, a reputation) reaches every character that person
plays.

## Logging in

At the welcome screen:

| Command | Does |
|---|---|
| `create <account> <password>` | makes an account, then asks you to name its first character |
| `connect <account> <password>` | logs in |
| `who` | who is playing |
| `quit` | disconnects |

A new player reaches the game in two lines: `create ann correcthorse`, then
`Bree`. The game system's character creation follows, as it always did.

After `connect`, an account with exactly one character goes straight into
play (Decision D2). Otherwise it shows the **character menu**:

```text
Account: ann
Your characters (2 of 5):
  Bree             level 3 warrior
  Cole             level 1 thief
Commands: play <name>, new <name>, delete <name>, password <old> <new>, quit
```

| Menu command | Does |
|---|---|
| `play <name>` | enters play as that character |
| `new <name>` | makes another character, through character creation |
| `delete <name>` | asks for the password again, then deletes the character forever (the last superuser on the server cannot be deleted) |
| `password <old> <new>` | changes the password |
| `quit` | disconnects |

In play, `characters` returns to the menu without disconnecting (the
character leaves play as on a disconnect), `logout` returns to the welcome
screen, and `password <old> <new>` works too.

A character out of play keeps its place in the world for its next login,
but nobody sees it there: a room's "Players here" and `scan` leave it
out. A link-dead character is still listed, marked `(linkdead)`, until its
wait runs out ([Operations](operations.md)).

The first character made on the first account of a new server is the
**superuser**, as the first character always was.

### How many characters

An account may hold `MAX_CHARACTERS` characters (5), plus its own extra
slots (Decision D2, after CoffeeMud's `BONUSCHARLIMIT`):

- **an administrator's**: `@account/slots ann = 2` gives the account two
  slots beyond `MAX_CHARACTERS` (kept on it as `bonus_characters`; `= 0`
  takes them away);
- **rewards'**: every account achievement it has earned whose `grants`
  hold `"characters": 1` adds that many ([Achievements](#achievements)).

The menu shows the account's limit ("Your characters (2 of 7):"), and `new`
past it answers "An account may hold at most 7 characters." Softcode reads
it with `character_limit(obj)`, and the administrator's part with
`account_attr(obj, 'bonus_characters')`.

### Settings

| Key | Default | Meaning |
|---|---|---|
| `MAX_CHARACTERS` | 5 | how many characters one account may hold, before its own extra slots ([How many characters](#how-many-characters)) |
| `ACCOUNT_MULTIPLAY` | False | off: one account, one connection; a second login takes over the first (with a message to it). On: one connection per character, so a person may play two characters at once |

Five failed passwords in a minute lock that account name for a minute.

### What an account is

An account is an object tagged `account`, with no location. It holds its
`password` (an scrypt hash; softcode can never read it), `characters` (the
characters' ids), `created`, `last_login`, `last_address`, an optional
`email`, `banned_until` and `ban_reason`, `bonus_characters` (its extra
character slots), and anything a game adds. A
character holds `account`, its account's id. Account names are unique
among accounts and character names among characters; the two namespaces
are separate, so an account and a character may share a name.

In Python, `account_of(character)` and `characters_of(account)` (from
`realm.std.accounts`) follow the links.

A world saved before accounts existed is carried over on its next boot:
each character with a password gets an account of the same name holding
that password. Its players log in exactly as before (`connect <name>
<password>`) and land in the same character, in the same room.

## Account data in softcode

Five functions reach the account behind a character ("Accounts" in the
[softcode reference](../reference/softcode.md)):

| Function | Does |
|---|---|
| `account_attr(obj, name, default=None)` | read an attribute on the character's account (None for a character with no account) |
| `set_account_attr(obj, name, value)` | set one |
| `incr_account_attr(obj, name, by=1)` | add to a number, returning the new value |
| `account_characters(obj)` | the names of the account's characters |
| `character_limit(obj)` | how many characters the account may hold ([How many characters](#how-many-characters)); None with no account |

The setters need the executor to control the character: the character
itself, its owner, or an admin's object (a game's bank or quest board
belongs to an admin). They refuse protected attributes, anything flagged
`system`, and the records the engine keeps on an account (`characters`,
`bonus_characters`, `achievements`, `created`, `last_login`,
`last_address`, `banned_until`, `ban_reason`): a script cannot give its
owner character slots, achievements or a lifted ban.

```text
@set bank/cmd_deposit = $deposit *: incr_account_attr(enactor, 'banked', int(arg0)) and pemit(enactor, f"Banked. The account holds {account_attr(enactor, 'banked')} coins.")
```

Every character of that person sees the same balance.

## Achievements

The `achievements` feature (in `CLASSIC`; it needs `accounts`) keeps
achievements as data. An achievement is an object tagged
`achievement_def`:

| Attribute | Meaning |
|---|---|
| `description` | what `achievements` shows |
| `hidden` | not listed until earned |
| `scope` | `account` (the default): earned once for every character of the account; `character`: for the one character only |
| `grants` | `{"tags": [...], "check_mods": {"will": 1, "all": 0}, "characters": 1}`: tags put on every character of the account, modifiers to their checks, and character slots for the account |

Softcode decides when an achievement is earned, and awards it with
`grant_achievement(obj, name)`; `has_achievement(obj, name)` asks. Granting
records the achievement once, with the date, tells the player, fires
`account:on_achievement` (hook `ACHIEVEMENT`, `adata('achievement')`
naming it), and applies the grants. A character logging in later takes the
tags too. `grant_achievement` is a builder's tool: an object a mortal made
cannot award one.

`characters` raises the account's character limit by that many (an
`account`-scoped achievement only: one scoped to a character raises
nothing, and granting it logs a warning saying so). The player is told
"Your account may now hold 6 characters." The slots are counted from what
the account has earned whenever the limit is asked, as the check
modifiers are, so changing an achievement's `grants` changes every account
that earned it:

```text
@create Founder
@tag Founder = achievement_def
@set Founder/description = Play in the first month.
@set Founder/grants = {"characters": 1}
```

`achievements` lists what a character has earned, with dates, what is
still to earn, and how many hidden ones remain.

### A worked example

Slay the banshee on any character, and every character on the account gets
+1 to will:

```text
@create Banshee Slayer
@tag Banshee Slayer = achievement_def
@set Banshee Slayer/description = Lay the wailing banshee to rest.
@set Banshee Slayer/grants = {"tags": ["banshee_slayer"], "check_mods": {"will": 1}}
@set banshee/on_death = if target is me and actor: grant_achievement(actor, 'Banshee Slayer')
```

The banshee's `ON_DEATH` names her killer as `actor`. From then on, every
`check()` of will by any of that person's characters counts +1, and each
of them carries the `banshee_slayer` tag (a door can be locked to it). The
showcase builds a whole achievement system on this:
[207](../showcase/207_achievements.md).

## Bans and administration

Admins only:

| Command | Does |
|---|---|
| `@account <name>` | the account: its characters and its character limit (`MAX_CHARACTERS` + bonus + achievements), when it was made, its last login and from where, any ban |
| `@account/password <name> = <new>` | resets its password |
| `@account/ban <name> <30m\|2h\|3d\|1w\|forever> = <reason>` | bans it, and disconnects it |
| `@account/unban <name>` | lifts a ban |
| `@account/boot <name>` | disconnects its sessions |
| `@account/slots <name> = <n>` | gives it `n` character slots beyond `MAX_CHARACTERS` (0: none) |
| `@sitelock <address-or-prefix> [= reason]` | refuses connections from an address, or every address starting with a prefix (`10.9.`) |
| `@sitelock/remove <prefix>`, `@sitelock/list` | lifts one, lists them |

`connect` to a banned account answers with the reason and when the ban
ends; an expired ban lifts itself. A sitelocked connection is told the
reason and closed; `create` from a sitelocked address is refused too. Every
ban, unban, password reset, boot, slot change and sitelock change is logged at INFO on
the `realm.admin` logger, naming who did it and to whom.
