# Communication: Tells, Channels, Socials and Mail

The `talk` feature is speech in the room (`say`, `pose`, `emit`, `shout`,
`whisper`). This page is everything else: reaching someone anywhere
(tells), talking to everyone who has tuned in (channels), gestures
(socials), and leaving word for someone who is not there (mail).

## Tells (`channels`)

| Command | Does |
|---|---|
| `tell <player> <message>` (`t`) | says something privately to a player anywhere in the game |
| `reply <message>` (`r`) | answers whoever last told you something |
| `ignore <player>` / `ignore` / `unignore <player>` | stop hearing a player's tells / list / hear them again |
| `afk [message]` | marks you away; anyone who tells you something is shown the message, and `who` shows `afk` beside you. `afk` again: back |

A tell to a player who is not online is refused, with a pointer to mail;
one to a player who ignores you is refused too. A sleeping player still
gets tells (Decision D4).

A tell is one propagated action, `comm:on_tell`, with the recipient as
its target and no room audience: the recipient's softcode hears it
(`ON_TELL`, `adata('message')`), and a ward on the teller's room or the
recipient's may refuse it, with nobody standing in either room overhearing:

```text
@set The Cell/on_check = if atype == 'comm:on_tell': block('The walls swallow your words.')
```

## Channels (`channels`)

A channel is a `channel_def` object, so a game's channels are data:

| Attribute / lock | Meaning |
|---|---|
| name, `alias` | the commands that speak on it (`gossip hello`, `gos hello`) |
| `description` | shown by `channels` |
| `speak` lock, `listen` lock | who may talk on it, who hears it |
| `format` | how a line reads, default `[{channel}] {name}: {message}` |
| `history_size` | how many recent lines are kept (default 20) |

New games get three, from the `channels` pack their `init_world` imports:
`gossip` (`gos`), `newbie` (`nb`), and `immtalk` (`imm`), whose speak and
listen locks are `has_entitlement(caller, 'BUILD')`, so only builders and
staff use it. Another channel is a few lines:

```text
@create trade
@tag trade = channel_def
@set trade/alias = trd
@set trade/description = buying and selling
@lock/speak trade = has_tag(caller, 'merchant')
```

Pick an alias no command starts with: commands match by prefix before
channels are tried, so `tr` would run `train`.

| Command | Does |
|---|---|
| `<channel> <message>` | speaks on it |
| `channels` | lists the channels you can hear, on or off |
| `channel <name> on\|off` | turns one on or off |
| `channel <name> history` | shows its recent lines |

A channel's name is a command only when no command, exit or world
`$`-command answers to the word. A line is one `comm:on_channel` action
(hook `CHANNEL`, `adata('channel')` and `adata('message')`) with the
channel definition as target, so softcode on the definition hears every
line. It reaches every online player who passes the listen lock and has
the channel on, except a sleeper. On and off are kept on the account
(`channels_off`), so they hold for every character a person plays.

Softcode: `cemit(channel, text)` announces a line as is (a herald; it is a
builder's tool), and `channel_members(channel)` names who hears it now.

Another feature can deliver its own talk the way a channel does: the
`channels` service offers `deliver(action, line, listeners, history=obj)`
(propagate the action, keep the line in `obj`'s `history`, send it to the
listeners a sleeper's deafness allows) and `remember(obj, line)`. Clan
talk (`ct`) is built on it ([Clans](clans.md#talk-who-home)).

## Socials (`talk`)

A social is a `social_def` object with up to five lines, in the usual
`{actor}` / `{target}` formatting:

| Attribute | Who sees it |
|---|---|
| `actor` | the actor, with no target |
| `room` | the room, with no target |
| `actor_at` | the actor, with a target |
| `target` | the target |
| `room_at` | everyone else, with a target |

```text
@create salaam
@tag salaam = social_def
@set salaam/actor = You touch your heart and bow.
@set salaam/room = {actor} touches their heart and bows.
@set salaam/actor_at = You touch your heart and bow to {target:the}.
@set salaam/target = {actor} touches their heart and bows to you.
@set salaam/room_at = {actor} touches their heart and bows to {target:the}.
```

Its name is a command when nothing else answers to the word, so a social
never shadows a command, an exit or a world `$`-command. An unseen actor
reads as "Someone". A social is an `event:social` action (hook `SOCIAL`,
`adata('social')`), so an NPC can bow back. `socials` lists them. New
games import the `socials-classic` pack: 48 Diku socials, from `smile` to
`grovel`.

## Mail (`mail`, needs `accounts`)

Mail is addressed to a character and kept on that character's account, so
it waits for whichever character the person plays next.

| Command | Does |
|---|---|
| `mail` | lists your messages (`*` for unread) |
| `mail <n>` | reads one |
| `mail <player> = <subject>/<body>` | sends |
| `mail <player> = <subject>` | writes the body in the [line editor](world-management.md#the-line-editor-edit) (`.s` sends, `.q` throws it away) |
| `mail/reply <n> = <body>` | answers one (with no body, in the line editor) |
| `mail/delete <n>` | deletes one |

At login a player is told how many unread messages wait; an online
recipient is told the moment mail arrives. An account holds at most
`MAIL_LIMIT` messages (default 100); mail to a full mailbox is refused.
Each message is an object tagged `mail`, held by the account (in no room),
with `sender`, `to`, `subject`, `body`, `sent` and `read`.

Softcode `send_mail(to, subject, body)` sends system mail from the object
running it (a guild's dues notice); it is a builder's tool.

## The features

| Feature | In `CLASSIC` | Needs |
|---|---|---|
| `channels` | tells, ignore, afk, channels | |
| `talk` | socials, besides room speech | |
| `mail` | mail | `accounts` |

A game without one leaves it out of `FEATURES`; the showcase's softcode
versions ([74](../showcase/074_custom_channel.md),
[75](../showcase/075_ingame_mail.md)) are for such a game.
