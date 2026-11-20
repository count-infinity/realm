# Softcode Reference

Auto-generated from the live API (`python scripts/gen_softcode_docs.py`
regenerates). Scripts are sandboxed Python: loops, comprehensions,
generator expressions, lambdas, function defs, and **f-strings** — under
time/call/output limits. A script runs in one namespace, like module scope,
so nested scopes read the variables you just assigned:
`rows = V('scores', {}); result = sorted(rows, key=lambda r: rows[r])`.
Prefer f-strings for readable output:
`say(f"{name(enactor)} owes {V('debt',0)} cr")` reads better than string
concatenation.

The sandbox validates before it runs (see `docs/design/sandbox-security.md`):
private `_names`/`.attrs`, imports, and names like `eval`/`getattr`/`type`
are rejected, and so is the `str.format`/`.format_map` family (its
mini-language reaches attributes a string hides from the validator). Use
f-strings, which are checked normally. Builtins are an allowlist: the common
functions, types, and exception classes are present; anything else is not.

## Where softcode runs (profiles)

Every place softcode is evaluated builds its namespace with one function,
`build_namespace` (`realm/scripting/namespace.py`). A *profile* decides
which functions are visible and which context names are bound. Functions
flagged read-only (they only read, roll or format) are visible everywhere;
the rest only where the world may change.

| Profile | Runs | Functions | Extra names | Subject |
|---|---|---|---|---|
| `script` | `$`-commands, `^`-listens, `ON_<EVENT>`, `on_tick`, `@tr`, `@eval` | all (harm-flagged ones only with the HARM entitlement) | `me`, `here`, `enactor`; `atype`, `actor`, `target`, `has_atag`, `adata` (empty when no action); `param` for a behavior_def | enactor |
| `check` | `on_check` wards, a behavior_def's `on_check`, wilderness map providers | read-only only | everything `script` binds, plus `block`, `mod`, `set_adata`, `is_blocked` | enactor |
| `inline` | `[[...]]` blocks in descriptions | all (harm-flagged ones only with the HARM entitlement) | `me`, `here`, `enactor`, `viewer` | viewer |
| `lock` | lock expressions (`@lock`, `set_lock`) | read-only only | `caller`, `target`, `owner` (the locked object's owner) | caller |
| `detail` | `@detail` conditions | read-only only | `viewer` | viewer |
| `rule` | a game system's `resolve_rule` | read-only only | `skill(name=<this skill>)`, `attr(name)`, `mod`, `skill_name` | the roller |

`skill(name)` and `check(name, mod)` act for the profile's *subject*.
`me` is the scripted object (scripts run AS it, with its owner's
authority), `enactor` who triggered the script (`%#` in simple scripts),
`here` where it happened. `arg0..argN` (`%0..%9`) are wildcard captures,
and an inline block's `result` is what it substitutes.

## Substitutions (`%` tokens)

Text-substituted into the script *before* it compiles, so a token must
land where its value is valid (usually inside a string). The namespace
variables above (`enactor`, `me`, …) are usually clearer; `%` tokens are
the terse PennMUSH-style shorthand.

| Token | Expands to |
|---|---|
| `%#` | enactor id (`enactor.id`) |
| `%!` | executor id (`me.id`) |
| `%n` | enactor name |
| `%l` | location id (`here.id`) |
| `%0`..`%9` | wildcard captures (same as `arg0..arg9`) |

## Readability helpers

| Instead of | Write |
|---|---|
| `get_attr(me, 'cost', 10)` | `V('cost', 10)` |
| `set_attr(me, k, get_attr(me, k, 0) + 1)` | `incr(k)` (returns the new value; `incr(k, n)` / `decr(k)` too) |

## Event data namespace {#event-data-namespace}

**The event data namespace** is the set of names REALM binds inside a
script that is reacting to an action, describing *what happened* rather
than merely who ran the script. It is bound whenever there is an action
behind the script — every `ON_<EVENT>` hook, every `^listen`, and every
`on_check` ward. A `$`-command or a `@trigger` has no action behind it,
so these names are unbound there.

The action being described is an `Action` — one object carrying the
actor, the target, a type string, a payload, and a set of category tags.
For what an `Action` is and how it reaches your object, see
[Action Propagation](../architecture/events.md); for a guided tour with
worked examples, see
[Event bus tour](../showcase/245_event_bus_tour.md).

| Name | Meaning |
|---|---|
| `atype` | the action type (`item:on_get`, `event:payment`, `combat:on_damage`, …) |
| `actor` | who is acting (same object as `enactor`) |
| `target` | what/who the action targets |
| `adata(key, default)` | the action's payload |
| `has_atag(tag)` | orthogonal action tags (`hostile`, `sound`, …) |

### Guard on `target` — events are heard by the whole room {#guard-on-target}

**This is the one that bites.** An `ON_<EVENT>` hook fires on *every*
object in the room, not only the one the action was aimed at. So `target`
is not a nicety — it is how a witness tells **"this happened to me"** from
**"this happened near me"**:

```
@set pump/on_payment = paid = adata('amount', 0) if target is me else 0; ...
@set golem/on_receive = it = adata('item') if target is me else None; ...
```

Without the guard, paying the *vending machine* standing next to your fuel
pump runs the pump's hook with the machine's `amount`, and it cheerfully
dispenses free fuel. Anything that reacts to `ON_PAYMENT`, `ON_RECEIVE`,
`ON_GET`, `ON_DAMAGE` — any event with a target — wants this check unless
it genuinely means to react to the whole room's traffic.

Payloads carried today (read with `adata`), declared with each event
(`feature.event(..., payload=...)`). An action type not listed carries no
payload: its subject is `target`.

| Action | Keys | Feature |
|---|---|---|
| `account:on_achievement` | `achievement`: the achievement's name | `achievements` |
| `clan:on_assign` | `clan`: the clan's name; `position`: the new position id; `previous`: the old position id; `how`: assigned, voted, displaced, promoted, overthrown or overthrow | `clans` |
| `clan:on_join` | `clan`: the clan's name; `position`: the position id; `how`: joined, accepted, founded, created or added | `clans` |
| `clan:on_leave` | `clan`: the clan's name; `reason`: left, exiled, removed or dissolved | `clans` |
| `clan:on_level` | `clan`: the clan's name; `level`: the new level | `clans` |
| `clan:on_talk` | `clan`: the clan's name; `message`: what was said | `clans` |
| `combat:on_attack` | `weapon`: the weapon used; `attacker_hp`: the attacker's HP; `defender_hp`: the defender's HP | `combat` |
| `combat:on_damage` | `damage`: the amount (a ward may lower it); `damage_types`: amount per damage type | `combat` |
| `combat:on_death` | `killer`: the killer's name (the killer object is actor); `fatal`: True when the body is gone | `combat` |
| `comm:on_channel` | `channel`: the channel's name; `message`: what was said | `channels` |
| `comm:on_tell` | `message`: what was said | `channels` |
| `companion:on_bond` | `how`: bought, charmed, or set (softcode, a builder) | `companions` |
| `companion:on_release` | `reason`: dismissed, released, charm_ended, master_left, master_gone, attacked or rebonded | `companions` |
| `event:connect` | `returning`: True when the character already existed | `kernel` |
| `event:emit` | `message`: the emitted text | `talk` |
| `event:emote` | `pose`: the pose text | `talk` |
| `event:on_cast` | `ability`: the ability's name; `caster`: who directed it | `abilities` |
| `event:on_fail` | `reason`: 'skill', 'closed', 'locked', ...; `exit`: the exit object; `direction`: the exit's name; `destination`: the room beyond | `kernel` |
| `event:on_hitprcnt` | `percent`: HP percent now; `threshold`: the crossed threshold | `combat` |
| `event:on_leave` | `exit`: the exit object; `direction`: the exit's name; `destination`: the room beyond | `kernel` |
| `event:on_load` | `marker`: the spawner's tracking tag | `kernel` |
| `event:on_receive` | `item`: what was given; `giver`: who gave it | `kernel` |
| `event:ooc` | `message`: what was said | `talk` |
| `event:payment` | `amount`: the sum paid | `economy` |
| `event:semipose` | `pose`: the pose text | `talk` |
| `event:shout` | `message`: what was said | `talk` |
| `event:social` | `social`: the social's name | `talk` |
| `event:speech` | `message`: what was said | `talk` |
| `event:whisper` | `message`: what was said | `talk` |
| `item:on_give` | `item`: what was given (also the action's tool); target is the recipient | `items` |
| `item:on_put` | `item`: what was put in; target is the container | `items` |
| `item:on_unlock` | `picked`: True when a lockpick, not a key, opened it | `items` |
| `pool:on_change` | `pool`: the pool's name; `old`: its value before; `new`: its value after; `applied`: how much this pool took; `source`: who caused it, or None | `kernel` |
| `pool:on_spent` | `pool`: the pool's name; `old`: its value before; `new`: its value after; `applied`: how much this pool took; `source`: who caused it, or None | `kernel` |
| `quest:on_accept` | `quest`: the quest's name | `quests` |
| `quest:on_advance` | `quest`: the quest's name; `stage`: the new stage number, or 'ready' when it waits to be handed in | `quests` |
| `quest:on_complete` | `quest`: the quest's name | `quests` |
| `quest:on_fail` | `quest`: the quest's name; `reason`: expired, abandoned or failed | `quests` |
| `time:on_dawn` | `hour`: the hour of the day | `clock` |
| `time:on_day` | `hour`: the hour of the day | `clock` |
| `time:on_dusk` | `hour`: the hour of the day | `clock` |
| `time:on_hour` | `hour`: the hour of the day | `clock` |
| `time:on_night` | `hour`: the hour of the day | `clock` |

```
@set ogre/ON_PAYMENT = pose pockets [[adata('amount')]] and steps aside.
@set anvil/ON_GET = set_attr(me, 'last_taker', name(actor))
```

`on_check` wards get all of the above **plus** the decision verbs —
`block(reason)`, `mod(n)`, `is_blocked()`, `set_adata(k, v)`. Observers do
not: by the time an `ON_<EVENT>` runs the decision is already made, so the
apply pass is read-only.

### When a ward breaks

A ward that errors **fails closed if it could have denied** — it blocks the
action and messages the object's owner. "The ward is broken" must never look
the same to the world as "the ward allowed it", or a typo silently unlocks
your vault:

| Ward | On error |
|---|---|
| calls `block(...)` | **blocks** — it guards something |
| calls an unknown name (`blok(...)`, a typo) | **blocks** — intent unclear |
| doesn't parse | **blocks** — can't tell what it guards |
| only `mod()` / `set_adata()` (armour, resistance) | **allows**, loudly — a failed soak must not veto the swing |

`@set` also warns at the prompt when a script attribute won't parse, so a
dead ward announces itself when you type it rather than months later.

## Script commands (simple scripts / `cmd()` / `output()` lines)

`say`, `pose`/`:`, `emit`/`@emit`, `whisper x = msg`, `move <exit>`,
`get`/`take`, `drop`, `give x = y`, `open`, `close`,
`trigger [obj/]attr`, `wait <sec> <command>`.

## Triggers (attributes on objects)

| Form | Fires |
|---|---|
| `$pattern:code` (attr `cmd_*`) | player input matching the pattern (gated by the `use` lock) |
| `^pattern:code` (attr `listen_*`) | overheard speech (gated by the `listen` lock) |
| `on_tick` attr | via the `script_ticker` behavior |
| `ON_<EVENT>` attr | a lifecycle event (below); matched by suffix, so any `ON_<name>` works |

## Configurable surface syntax

The sigils and delimiters above are game settings in `config.py`; this
reference (and every example in the docs) uses the defaults.

| Setting | Default | Governs |
|---|---|---|
| `COMMAND_SIGIL` | `$` | the `$pattern:code` command-trigger prefix (any length 1-16) |
| `LISTEN_SIGIL` | `^` | the `^pattern:code` listen-trigger prefix (any length 1-16) |
| `INLINE_OPEN` / `INLINE_CLOSE` | `[[` / `]]` | inline description blocks — the code inside nests freely (`fn1(fn2(x))`, `words[idx[0]]`, quoted closers); pick a bracket-final closer (`}`, `]`, `)`) so nesting tracking applies |
| `MARKUP_MARKER` | `\|` | color markup (`\|r`, `\|n`, …) — remap it (`~`, `%%`, any length 1-16) to keep literal pipes in prose; the doubled-marker escape follows it |
| `EMOTE_SIGIL` | `/` | rich-emote reference prefix — `pose waves at /Bob` names Bob per viewer (each reader sees the name they know; Bob reads "you"). An unmatched `/word` stays literal |

Sigils and the marker take any non-alphanumeric, non-space characters;
sigils additionally exclude `:` (the pattern:action separator). A bad
value raises at boot, never mid-render.

### `ON_<EVENT>` lifecycle hooks {#lifecycle-hooks}

An `ON_<NAME>` attribute fires when that event reaches the object (zone
masters also hear their member rooms). Gated hooks let an `on_check` ward
veto (a cursed item refusing removal).

| Hook attr | Fires when | Feature |
|---|---|---|
| `ON_ACHIEVEMENT` | a character earns an achievement | `achievements` |
| `ON_ARRIVE` | this object arrives somewhere new | `kernel` |
| `ON_ATTACK` | this object attacks or is attacked | `combat` |
| `ON_BOND` | this creature became someone's companion (the master is `enactor`) | `companions` |
| `ON_CAST` | an ability is directed at this object (resist via on_check) | `abilities` |
| `ON_CHANNEL` | a line is spoken on this channel (the channel_def is the target) | `channels` |
| `ON_CLANASSIGN` | a member of this clan changed position (`enactor`) | `clans` |
| `ON_CLANJOIN` | a character joined this clan (the member is `enactor`) | `clans` |
| `ON_CLANLEAVE` | a member left this clan (the member is `enactor`) | `clans` |
| `ON_CLANLEVEL` | this clan reached a new level | `clans` |
| `ON_CLANTALK` | a member spoke on clan talk (`enactor`) | `clans` |
| `ON_CLOSE` | this door/container is closed | `items` |
| `ON_CONNECT` | player connects | `kernel` |
| `ON_DAMAGE` | this object takes damage | `combat` |
| `ON_DAWN` | dawn breaks | `clock` |
| `ON_DAY` | full day begins | `clock` |
| `ON_DEATH` | this object goes down: its vital pool is spent, by any cause (a swing, poison, a trap, softcode damage). `adata('fatal')` is True when the body is gone (a corpse, or destroyed), False when it stays (unconscious, or `when_spent` is none) | `combat` |
| `ON_DISCONNECT` | player leaves play (a dropped connection: when its link-dead wait ends) | `kernel` |
| `ON_DRINK` | this is drunk from (gated) | `items` |
| `ON_DROP` | this object is dropped | `items` |
| `ON_DUSK` | dusk falls | `clock` |
| `ON_EAT` | this food is eaten (gated) | `items` |
| `ON_ENTER` | something enters this location | `kernel` |
| `ON_EXPIRE` | this object's db.expires_at elapsed (then it's destroyed) | `kernel` |
| `ON_FAIL` | a move was thwarted (dead-end/locked exit) — @afail | `kernel` |
| `ON_GET` | this object is picked up | `items` |
| `ON_GIVE` | this object is given away | `items` |
| `ON_HITPRCNT` | the vital pool (HP) fell through this object's db.hitprcnt threshold, from any source: a swing, poison, a trap, softcode | `combat` |
| `ON_HOUR` | a game hour begins (zone masters, rooms holding players) | `clock` |
| `ON_LEAVE` | something leaves this location | `kernel` |
| `ON_LOAD` | this object was just spawned | `kernel` |
| `ON_LOCK` | this is locked (gated) | `items` |
| `ON_LOOK` | this object is looked at | `kernel` |
| `ON_NIGHT` | night falls | `clock` |
| `ON_OPEN` | this door/container is opened | `items` |
| `ON_PAYMENT` | this object was paid | `economy` |
| `ON_POOL` | one of this object's pools changed (damage, healing, a cost) | `kernel` |
| `ON_PUSH` | this object is pushed (button, lever) | `items` |
| `ON_PUT` | this object is put in a container | `items` |
| `ON_QUESTACCEPT` | a character took a quest (`enactor`; the target is the giver, or the quest's definition) | `quests` |
| `ON_QUESTADVANCE` | a character finished a stage of a quest (`enactor`) | `quests` |
| `ON_QUESTCOMPLETE` | a character completed a quest (`enactor`; the target is the giver it was handed in to, or the quest's definition) | `quests` |
| `ON_QUESTFAIL` | a character's quest ended unfinished (`enactor`) | `quests` |
| `ON_RECEIVE` | this object is given something (recipient side) | `kernel` |
| `ON_RELEASE` | this companion was freed (its former master, if any, is `enactor`) | `companions` |
| `ON_REMOVE` | this object is taken off (gated: cursed gear can refuse) | `items` |
| `ON_RESET` | this zone master resets (empty + due) — repop, re-lock doors | `kernel` |
| `ON_SOCIAL` | a social (smile, bow) is used | `talk` |
| `ON_SPENT` | one of this object's pools was just used up (the change that crossed into spent) | `kernel` |
| `ON_TALK` | a character talks to this object (`talk <npc>`) | `quests` |
| `ON_TELL` | this player is told something | `channels` |
| `ON_TICK` | periodic timer (on_tick behavior) | `kernel` |
| `ON_UNLOCK` | this is unlocked (gated: a sealed door can refuse) | `items` |
| `ON_UNWIELD` | this weapon is lowered (gated) | `items` |
| `ON_USE` | this object is used | `items` |
| `ON_WEAR` | this object is worn | `items` |
| `ON_WIELD` | this weapon is readied (gated) | `items` |

## Functions

Every function below is listed in the index, then documented in full
under its section. Each entry links to its own anchor, so you can point
a tutorial straight at one function (`reference/softcode.md#fn-pemit`).

### Index

| Function | What it does | Section |
|---|---|---|
| [`account_attr`](#fn-account_attr) | An attribute on the character's account: shared by every character the same person plays. | [Accounts](#accounts) |
| [`account_characters`](#fn-account_characters) | The names of every character on the character's account (empty for a character with none). | [Accounts](#accounts) |
| [`act`](#fn-act) | Fire a PROPAGATED action that can reach BEYOND your own room — unlike pemit/remit (which just deliver text), this runs the two-pass engine, so behaviors can veto or react at both ends. | [Firing your own events](#firing-your-own-events) |
| [`add_tag`](#fn-add_tag) | Add a tag to an object the executor controls. | [Tags & zones](#tags-zones) |
| [`adjust_credits`](#fn-adjust_credits) | Mint or burn money on an object the executor controls. | [Money](#money) |
| [`adjust_disposition`](#fn-adjust_disposition) | Shift an NPC's attitude. | [NPCs & behaviors](#npcs-behaviors) |
| [`ansi`](#fn-ansi) | Penn-style color: ansi('rh', 'My thing') — lowercase letters = foreground (r g y b m c w x), 'h' brightens it, UPPERCASE = background, u = underline, i = inverse video. | [Messaging & prompts](#messaging-prompts) |
| [`apply_effect`](#fn-apply_effect) | Attach an effect (modifier_effect / damage_over_time / regeneration / disposition_boost) to something in the executor's room. | [Combat & effects](#combat-effects) |
| [`attach_behavior`](#fn-attach_behavior) | Attach a registered behavior to an object the executor controls. | [NPCs & behaviors](#npcs-behaviors) |
| [`attackers`](#fn-attackers) | Who is attacking `target` in its fight (empty out of one). | [Combat & effects](#combat-effects) |
| [`band`](#fn-band) | Tiered outcome (PbtA): tier = how many ascending thresholds `value` clears. | [Dice & skill checks](#dice-skill-checks) |
| [`behaviors`](#fn-behaviors) | Behavior ids attached to an object. | [NPCs & behaviors](#npcs-behaviors) |
| [`call`](#fn-call) | Call an attribute as a METHOD on `obj` — runs AS `obj` (`me` is obj, `V()`/`get_attr(me, ...)` read obj's own data, `here` is obj's room), with `enactor` preserved and args bound as arg0..argN. | [Objects & attributes](#objects-attributes) |
| [`cancel_wait`](#fn-cancel_wait) | Cancel a pending wait by the handle `wait()` returned, before it fires. | [Time & scheduling](#time-scheduling) |
| [`capstr`](#fn-capstr) | Capitalize each word. | [Text](#text) |
| [`cast`](#fn-cast) | Direct an ability at a target — the ability analog of `act`. | [Combat & effects](#combat-effects) |
| [`ceil`](#fn-ceil) | Round up to integer. | [Math & logic](#math-logic) |
| [`cemit`](#fn-cemit) | Announce a line on a channel, as is (no speaker name): a herald, a server notice. | [Messaging & prompts](#messaging-prompts) |
| [`channel_members`](#fn-channel_members) | The names of the online players who hear a channel now. | [Messaging & prompts](#messaging-prompts) |
| [`character_limit`](#fn-character_limit) | How many characters the character's account may hold: `MAX_CHARACTERS`, plus the account's `bonus_characters` (set by an administrator), plus what its achievements grant. | [Accounts](#accounts) |
| [`check`](#fn-check) | Roll a skill check AS the subject; True on success. | [Dice & skill checks](#dice-skill-checks) |
| [`check_roll`](#fn-check_roll) | Roll a skill check and return the GRADED, condition-modified result. | [Dice & skill checks](#dice-skill-checks) |
| [`clamp`](#fn-clamp) | Clamp value between low and high. | [Math & logic](#math-logic) |
| [`clan`](#fn-clan) | The name of the clan `obj` belongs to (in `category`; one who has only applied is not in it yet), or None. | [Clans](#clans) |
| [`clan_add`](#fn-clan_add) | Put a character in a clan (at `position`, else the government's accept position), as if accepted. | [Clans](#clans) |
| [`clan_has_power`](#fn-clan_has_power) | Does `obj`'s position in its clan hold `power` outright (not merely vote on it)? | [Clans](#clans) |
| [`clan_level`](#fn-clan_level) | A clan's level, or None when there is no such clan. | [Clans](#clans) |
| [`clan_members`](#fn-clan_members) | A clan's members (not its applicants), highest rank first. | [Clans](#clans) |
| [`clan_position`](#fn-clan_position) | The id of `obj`'s position in its clan (`boss`, `member`), or None. | [Clans](#clans) |
| [`clan_rank`](#fn-clan_rank) | The rank of `obj`'s position in its clan, 0 the highest; None outside a clan. | [Clans](#clans) |
| [`clan_relation`](#fn-clan_relation) | Clan `a`'s declared relation toward clan `b`: war, hostile, neutral, friendly or ally (None when either is not a clan). | [Clans](#clans) |
| [`clan_remove`](#fn-clan_remove) | Take a character out of a clan (`CLANLEAVE` fires, reason `removed`). | [Clans](#clans) |
| [`clans_at_war`](#fn-clans_at_war) | True when either clan has declared war on the other. | [Clans](#clans) |
| [`clear_lock`](#fn-clear_lock) | Clear a lock from an object the executor controls. | [Locks & permissions](#locks-permissions) |
| [`clone_obj`](#fn-clone_obj) | Copy an object the executor controls: attributes, tags, behaviors, locks and parent (not its unique keyid). | [Objects & attributes](#objects-attributes) |
| [`companions`](#fn-companions) | `obj`'s companions, wherever they are. | [NPCs & behaviors](#npcs-behaviors) |
| [`contents`](#fn-contents) | Get an object's contents. | [Objects & attributes](#objects-attributes) |
| [`contest`](#fn-contest) | Opposed quick contest; True if the actor wins. | [Dice & skill checks](#dice-skill-checks) |
| [`controls`](#fn-controls) | Does the executor control this object? | [Objects & attributes](#objects-attributes) |
| [`create_obj`](#fn-create_obj) | Create a new thing, owned by the executor's owner (or the executor itself), at the executor's location by default. | [Objects & attributes](#objects-attributes) |
| [`credits`](#fn-credits) | An object's balance. | [Money](#money) |
| [`damage`](#fn-damage) | Deal damage to something in the executor's room: it lands in the target's damage pool (`hp` unless it says otherwise), with soak (each pool's `soak_attr`, a ship's armor). | [Combat & effects](#combat-effects) |
| [`decr`](#fn-decr) | Decrement a numeric attribute on `me` and return the new value. | [Objects & attributes](#objects-attributes) |
| [`del_attr`](#fn-del_attr) | Delete an attribute from an object the executor controls. | [Objects & attributes](#objects-attributes) |
| [`destroy_obj`](#fn-destroy_obj) | Destroy an object the executor controls. | [Objects & attributes](#objects-attributes) |
| [`detach_behavior`](#fn-detach_behavior) | Detach a behavior (by id) from an object the executor controls (needs BUILD behind the executor, like `attach_behavior`). | [NPCs & behaviors](#npcs-behaviors) |
| [`dice`](#fn-dice) | Roll dice: NdS+M Args: num: Number of dice sides: Sides per die modifier: Added to total | [Dice & skill checks](#dice-skill-checks) |
| [`disarm`](#fn-disarm) | Knock the target's wielded weapon to the floor. | [Combat & effects](#combat-effects) |
| [`disposition`](#fn-disposition) | How npc feels about other (default: the enactor). | [NPCs & behaviors](#npcs-behaviors) |
| [`enter_instance`](#fn-enter_instance) | Send a player into a private, transient copy of a template area, materializing one on demand — and reusing their own copy (or their leader's, if it's `shared`) if one already exists. | [Movement & travel](#movement-travel) |
| [`enter_wilderness`](#fn-enter_wilderness) | Send a player to the wilderness cell at `(region, x, y)`, materializing it on demand — the scripted seam into a coordinate-keyed region. | [Movement & travel](#movement-travel) |
| [`escape`](#fn-escape) | Escape color markup in player-provided text (\|\| literals). | [Messaging & prompts](#messaging-prompts) |
| [`eval_attr`](#fn-eval_attr) | Evaluate an attribute as a SUBROUTINE and return its `result`. | [Objects & attributes](#objects-attributes) |
| [`exits`](#fn-exits) | Open exits of a room (default: the executor's location). | [Objects & attributes](#objects-attributes) |
| [`expire`](#fn-expire) | Give an object a lifetime: after `seconds` it fires `ON_EXPIRE` and is destroyed by the world tick (a summoned creature, a smoke cloud, a temp portal). | [Time & scheduling](#time-scheduling) |
| [`extract`](#fn-extract) | Get element at position (1-indexed). | [Text](#text) |
| [`first`](#fn-first) | Get first element of list or first word of string. | [Text](#text) |
| [`floor`](#fn-floor) | Round down to integer. | [Math & logic](#math-logic) |
| [`force`](#fn-force) | Make something the executor controls run a command (queued; executes through the real dispatcher after the script). | [NPCs & behaviors](#npcs-behaviors) |
| [`game_time`](#fn-game_time) | The game's time and date: `{'hour', 'minute', 'day', 'month', 'year', 'month_name', 'day_name', 'time_of_day'}`. | [Time & scheduling](#time-scheduling) |
| [`get`](#fn-get) | Get an object by ID, friendly keyid, or name. | [Objects & attributes](#objects-attributes) |
| [`get_attr`](#fn-get_attr) | Get an attribute from an object. | [Objects & attributes](#objects-attributes) |
| [`grant_achievement`](#fn-grant_achievement) | Award an achievement (an `achievement_def`) to a character, once: recorded on its account (or on the character, for `scope = character`), announced to the player, its grants applied, and `account:on_achievement` fired. | [Accounts](#accounts) |
| [`harm_pool`](#fn-harm_pool) | Harm a pool of something in reach, spilling into its overflow pool. | [Pools](#pools) |
| [`has_achievement`](#fn-has_achievement) | Has the character (or its account) earned the achievement? | [Accounts](#accounts) |
| [`has_attr`](#fn-has_attr) | Check if an object has an attribute. | [Objects & attributes](#objects-attributes) |
| [`has_entitlement`](#fn-has_entitlement) | Whether an object holds a permission entitlement (read-only). | [Locks & permissions](#locks-permissions) |
| [`has_pool`](#fn-has_pool) | True when the object has the pool. | [Pools](#pools) |
| [`has_tag`](#fn-has_tag) | Check if an object has a tag. | [Tags & zones](#tags-zones) |
| [`heal`](#fn-heal) | Mend the damage pool (`hp` unless the target says otherwise), capped at its max, of something in the executor's room. | [Combat & effects](#combat-effects) |
| [`highest`](#fn-highest) | Highest-die tiers (Blades): 6 -> full (2), 4-5 -> partial (1), else miss (0). | [Dice & skill checks](#dice-skill-checks) |
| [`hungry`](#fn-hungry) | True when the character's `food` pool is empty: it recovers at half speed and counts toward dying of hunger. | [Pools](#pools) |
| [`idle_seconds`](#fn-idle_seconds) | Seconds since a player last typed (or since its link dropped); None when it is not on. | [Objects & attributes](#objects-attributes) |
| [`if_else`](#fn-if_else) | Conditional expression. | [Math & logic](#math-logic) |
| [`incr`](#fn-incr) | Increment a numeric attribute on `me` and return the new value. | [Objects & attributes](#objects-attributes) |
| [`incr_account_attr`](#fn-incr_account_attr) | Add `by` to a number on the character's account and return the new value (None when refused). | [Accounts](#accounts) |
| [`last`](#fn-last) | Get last element. | [Text](#text) |
| [`lcfirst`](#fn-lcfirst) | Lowercase first character. | [Text](#text) |
| [`left`](#fn-left) | Get leftmost N characters. | [Text](#text) |
| [`loc`](#fn-loc) | Get an object's location. | [Objects & attributes](#objects-attributes) |
| [`margin_over`](#fn-margin_over) | Roll-over (D20): success if `rolled >= target`; margin is how far over. | [Dice & skill checks](#dice-skill-checks) |
| [`margin_under`](#fn-margin_under) | Roll-under (GURPS, CoC): success if `rolled <= target`; margin is how far under. | [Dice & skill checks](#dice-skill-checks) |
| [`master`](#fn-master) | The character `obj` is a companion of (a pet's owner, a charmed creature's charmer), or None. | [NPCs & behaviors](#npcs-behaviors) |
| [`member`](#fn-member) | Find position of item in list (1-indexed, 0 if not found). | [Text](#text) |
| [`mend_pool`](#fn-mend_pool) | Mend a pool of something in reach: raise a down pool toward its max, lower an up pool toward its floor. | [Pools](#pools) |
| [`mid`](#fn-mid) | Extract substring (1-indexed like MUSH). | [Text](#text) |
| [`move_to`](#fn-move_to) | Relocate a player/object to a destination with the movement checks baked in — the one relocation verb. | [Movement & travel](#movement-travel) |
| [`name`](#fn-name) | Get an object's name. | [Objects & attributes](#objects-attributes) |
| [`net_successes`](#fn-net_successes) | Dice-pool success-counting (Shadowrun, WoD): roll `pool` dice, count those `>= tn`. | [Dice & skill checks](#dice-skill-checks) |
| [`now`](#fn-now) | Current time as epoch seconds — cache expiry, cooldowns. | [Time & scheduling](#time-scheduling) |
| [`oemit`](#fn-oemit) | Emit to the executor's room, excluding one object. | [Messaging & prompts](#messaging-prompts) |
| [`online_players`](#fn-online_players) | The characters in play now that the running object can see. | [Objects & attributes](#objects-attributes) |
| [`oob`](#fn-oob) | Send structured out-of-band data (GMCP) to a player's client — custom UI panels from softcode. | [Messaging & prompts](#messaging-prompts) |
| [`owner`](#fn-owner) | Get an object's owner. | [Objects & attributes](#objects-attributes) |
| [`pemit`](#fn-pemit) | Send a private message to a target (delivered after the script), exactly as written (ROM's `send_to_char`: a lowercase first letter stays lowercase). | [Messaging & prompts](#messaging-prompts) |
| [`pool`](#fn-pool) | A pool's value, or None when the object has no such pool. | [Pools](#pools) |
| [`pool_max`](#fn-pool_max) | A pool's maximum, or None when it is unbounded or absent. | [Pools](#pools) |
| [`prompt`](#fn-prompt) | Ask a player a question; their next line runs the `callback` attribute (on the executor) with the answer as arg0 — a softcode wizard. | [Messaging & prompts](#messaging-prompts) |
| [`quest_advance`](#fn-quest_advance) | Count `by` toward the objective `key` of `obj`'s current stage of `quest`: a `custom` objective, or any other. | [Quests](#quests) |
| [`quest_complete`](#fn-quest_complete) | Complete `obj`'s `quest` now, whatever is left of it, and pay its rewards. | [Quests](#quests) |
| [`quest_count`](#fn-quest_count) | How far `obj` is on the objective `key` of their current stage of `quest` (0 when they are not on it, or the stage has no such objective). | [Quests](#quests) |
| [`quest_fail`](#fn-quest_fail) | End `obj`'s `quest` unfinished (`QUESTFAIL` fires, reason `failed`). | [Quests](#quests) |
| [`quest_offer`](#fn-quest_offer) | Start `quest` for `obj` as if they had accepted it (a note read, a stranger met): True when they may take it, False (and nothing happens) when not. | [Quests](#quests) |
| [`quest_state`](#fn-quest_state) | Where `obj` stands on `quest`: None (never taken, or failed), the current stage number (1 is the first), `'ready'` (every stage met, waiting to be handed in) or `'done'`. | [Quests](#quests) |
| [`rand`](#fn-rand) | Random integer between low and high (inclusive). | [Dice & skill checks](#dice-skill-checks) |
| [`reaction_roll`](#fn-reaction_roll) | Memoized first-impression roll (npc must be in executor's reach). | [NPCs & behaviors](#npcs-behaviors) |
| [`release`](#fn-release) | Free `obj` (an NPC the executor controls) from its master; it stays where it is. | [NPCs & behaviors](#npcs-behaviors) |
| [`remit`](#fn-remit) | Emit a message to everyone in a room (delivered after the script). | [Messaging & prompts](#messaging-prompts) |
| [`remove_effect`](#fn-remove_effect) | Strip an active effect by kind (cure poison, calm fear). | [Combat & effects](#combat-effects) |
| [`remove_tag`](#fn-remove_tag) | Remove a tag from an object the executor controls. | [Tags & zones](#tags-zones) |
| [`repeat`](#fn-repeat) | Repeat text N times. | [Text](#text) |
| [`replace`](#fn-replace) | Replace all occurrences of old with new. | [Text](#text) |
| [`rest`](#fn-rest) | Get all but first element. | [Text](#text) |
| [`retarget`](#fn-retarget) | Turn a fighter on a new target in the same room (a rescue): the new target joins the fight if it was not in it. | [Combat & effects](#combat-effects) |
| [`right`](#fn-right) | Get rightmost N characters. | [Text](#text) |
| [`roll`](#fn-roll) | Roll a dice expression to a total. | [Dice & skill checks](#dice-skill-checks) |
| [`search_world`](#fn-search_world) | Query the world: search_world(tag='zone:castle'), search_world(attr='xp_multiplier'), combinable. | [Objects & attributes](#objects-attributes) |
| [`send_mail`](#fn-send_mail) | Send mail to a character, from this object (system mail: a guild's dues notice, a quest's reward slip). | [Messaging & prompts](#messaging-prompts) |
| [`set_account_attr`](#fn-set_account_attr) | Set an attribute on the character's account, for every character of that person to read. | [Accounts](#accounts) |
| [`set_attr`](#fn-set_attr) | Set an attribute on an object the executor controls. | [Objects & attributes](#objects-attributes) |
| [`set_desc`](#fn-set_desc) | Set the description `look` shows on an object the executor controls (like `@desc`; an empty string clears it). | [Objects & attributes](#objects-attributes) |
| [`set_lock`](#fn-set_lock) | Set a lock on an object the executor controls (validated). | [Locks & permissions](#locks-permissions) |
| [`set_master`](#fn-set_master) | Make `obj` (an NPC the executor controls) `master`'s companion: it follows and obeys `order`. | [NPCs & behaviors](#npcs-behaviors) |
| [`set_name`](#fn-set_name) | Rename an object the executor controls (like `@name`). | [Objects & attributes](#objects-attributes) |
| [`setdiff`](#fn-setdiff) | Difference of two lists (in list1 but not list2). | [Text](#text) |
| [`setinter`](#fn-setinter) | Intersection of two lists. | [Text](#text) |
| [`setunion`](#fn-setunion) | Union of two space-separated lists. | [Text](#text) |
| [`skill`](#fn-skill) | The subject's effective level in a skill (trained, else its default). | [Dice & skill checks](#dice-skill-checks) |
| [`skill_check`](#fn-skill_check) | Roll a skill check for an object (name/#id or object). | [Dice & skill checks](#dice-skill-checks) |
| [`spend_pool`](#fn-spend_pool) | Pay a cost from the executor's own pool, all or nothing. | [Pools](#pools) |
| [`spent`](#fn-spent) | True when the pool is used up (a down pool at or below its `spent_at`, an up pool at its max). | [Pools](#pools) |
| [`start_combat`](#fn-start_combat) | Throw an attacker the executor controls into combat with a target in the same room (queued; the encounter starts after the script finishes). | [Combat & effects](#combat-effects) |
| [`start_task`](#fn-start_task) | Make the enactor busy for `seconds`: when the time passes, this object's `done_attr` runs with the enactor bound. | [Time & scheduling](#time-scheduling) |
| [`stop_task`](#fn-stop_task) | Break off a character's task (its interrupt script runs). | [Time & scheduling](#time-scheduling) |
| [`strlen`](#fn-strlen) | Get string length. | [Text](#text) |
| [`switch`](#fn-switch) | Switch statement. | [Math & logic](#math-logic) |
| [`tag_value`](#fn-tag_value) | First value of a namespaced tag: tag_value(here, 'zone') -> 'castle' (None if untagged). | [Tags & zones](#tags-zones) |
| [`tag_values`](#fn-tag_values) | All values of a namespaced tag: tag_values(here, 'zone') -> ['castle', 'haunted']. | [Tags & zones](#tags-zones) |
| [`tags`](#fn-tags) | Get all tags on an object. | [Tags & zones](#tags-zones) |
| [`task_of`](#fn-task_of) | What a character is busy with: `{"label": ..., "left": seconds}`, or None. | [Time & scheduling](#time-scheduling) |
| [`teleport_obj`](#fn-teleport_obj) | Move an object the executor controls straight to a destination — the wizard/admin relocation. | [Objects & attributes](#objects-attributes) |
| [`test_lock`](#fn-test_lock) | Would `caller` (default: the executor) pass this lock? | [Locks & permissions](#locks-permissions) |
| [`thirsty`](#fn-thirsty) | True when the character's `water` pool is empty: it recovers at half speed and counts toward dying of thirst. | [Pools](#pools) |
| [`time_of_day`](#fn-time_of_day) | `dawn`, `day`, `dusk` or `night`. | [Time & scheduling](#time-scheduling) |
| [`transfer_credits`](#fn-transfer_credits) | Move money FROM something the executor controls. | [Money](#money) |
| [`trim`](#fn-trim) | Remove leading/trailing whitespace. | [Text](#text) |
| [`ucfirst`](#fn-ucfirst) | Capitalize first character. | [Text](#text) |
| [`use_ability`](#fn-use_ability) | Use an ability or spell definition (`ability_def` / `spell_def`) as the executor: pay its cost, roll its save, apply its effects — what the `cast` command does for a player. | [Combat & effects](#combat-effects) |
| [`V`](#fn-v) | Read an attribute off `me` (the executor) — the common case. | [Objects & attributes](#objects-attributes) |
| [`wait`](#fn-wait) | Run a script command as the executor exactly `seconds` from now (one-shot, its own timer — a 0.15s fuse fires at 0.15s, not quantized to the heartbeat; pending waits don't survive a reboot). | [Time & scheduling](#time-scheduling) |
| [`weather`](#fn-weather) | The weather in a room's zone (rolled hourly by its zone master), or None. | [Time & scheduling](#time-scheduling) |
| [`words`](#fn-words) | Count words/elements in text. | [Text](#text) |
| [`zone_rooms`](#fn-zone_rooms) | Rooms tagged into a zone: zone_rooms('castle'). | [Tags & zones](#tags-zones) |
| [`zones_of`](#fn-zones_of) | The zone names an object belongs to (no 'zone:' prefix). | [Tags & zones](#tags-zones) |

## Objects & attributes

### `call` {#fn-call}

```text
call(obj, attr_name: str, *args)
```

Call an attribute as a METHOD on `obj` — runs AS `obj` (`me` is
obj, `V()`/`get_attr(me, ...)` read obj's own data, `here` is
obj's room), with `enactor` preserved and args bound as arg0..argN.
Returns the routine's `result`.

Unlike `eval_attr` (which runs as the CALLER — a subroutine of
your own object), `call` is a method invocation on another object:
the shared-service / "function object" form. Allowed when the executor
CONTROLS `obj` (co-owned, admin, or owner) OR the attribute is
flagged `public` (the cross-owner opt-in). Protected attrs are never
callable; errors return None. Because `here` is the target's room,
reach the caller's scene with `pemit(enactor, ...)` or
`remit(loc(enactor), ...)`.

**Example**

```text
call(get('#' + V('bank_core_id')), 'net_deposit', trim(arg0))
```

### `clone_obj` {#fn-clone_obj}

```text
clone_obj(obj: GameObject | str | None, name: str | None = None, location: GameObject | str | None = None) -> GameObject | None
```

Copy an object the executor controls: attributes, tags, behaviors,
locks and parent (not its unique keyid). The copy lands in the
executor's room unless `location` names one it controls. Players and
rooms can't be cloned.

**Example**

```text
twin = clone_obj('brass key', 'spare key')
```

### `contents` {#fn-contents}

```text
contents(obj: GameObject | str | None) -> list[GameObject]
```

Get an object's contents.

**Example**

```text
[o for o in contents(here) if has_tag(o, 'npc')]
```

### `controls` {#fn-controls}

```text
controls(obj: GameObject | str | None) -> bool
```

Does the executor control this object? (The mutation gate.)

**Example**

```text
controls('lever')
```

### `create_obj` {#fn-create_obj}

```text
create_obj(name: str, tags: list[str] | None = None, location: GameObject | str | None = None, description: str = '', attrs: dict | None = None) -> GameObject | None
```

Create a new thing, owned by the executor's owner (or the
executor itself), at the executor's location by default.

`description` sets the render description `look` shows; `attrs`
is a dict of attributes stamped on at birth. Together they mint a whole
item in one call, instead of a `create_obj`/`set_attr` chain:

    create_obj('bulb of cold coffee',
               description='A dented bulb, beaded with condensation.',
               attrs={'weight': 1})

**Example**

```text
sword = create_obj('iron sword')
```

### `decr` {#fn-decr}

```text
decr(attr_name: str, by: Any = 1, default: Any = 0) -> Any
```

Decrement a numeric attribute on `me` and return the new value.

The mirror of :meth:`incr`, including its `default` (what an unset
attribute counts as). Returns None if the write is refused.

**Example**

```text
decr('ammo')                  # -1 from 0
decr('breath', default=3)     # an unset meter starts full
```

### `del_attr` {#fn-del_attr}

```text
del_attr(obj: GameObject | str | None, attr_name: str) -> bool
```

Delete an attribute from an object the executor controls.

**Example**

```text
del_attr(me, 'charged')
```

### `destroy_obj` {#fn-destroy_obj}

```text
destroy_obj(obj: GameObject | str | None) -> bool
```

Destroy an object the executor controls. Players and `safe`-tagged
objects are refused (returns False). Like `@destroy`: players inside
are sent home, player-owned items go to their owner's home, and
everything else inside is destroyed with it.

**Example**

```text
destroy_obj('slag')
```

### `eval_attr` {#fn-eval_attr}

```text
eval_attr(obj, attr_name: str, *args)
```

Evaluate an attribute as a SUBROUTINE and return its `result`.

Runs with the CALLER's authority — the executor is unchanged —
with args bound as arg0..argN / %0..%9. Secret attributes respect
their read gate; errors return None.

NOT Penn's u(), despite the resemblance (this docstring used to
claim it was): Penn swaps the executor to the object holding the
attribute (call_ufun_int -> process_expression(..., ufun->thing,
caller, ...)), so v() there reads the *attribute owner's* data and
the call can escalate — which is why Penn gates @function behind a
power. This runs as the caller and cannot escalate. The practical
consequence: inside the routine `me` is the CALLER, not `obj`,
so a shared library routine must resolve its own object by name
(`get('Quest Warden')`) to read its own attrs. See BACKLOG's
@function entry for the Penn-semantics library-call mechanism.

**Example**

```text
eval_attr(me, 'render_side', n)
```

### `exits` {#fn-exits}

```text
exits(room: GameObject | str | None = None) -> list[GameObject]
```

Open exits of a room (default: the executor's location).

**Example**

```text
move(name(exits(here)[0]))
```

### `get` {#fn-get}

```text
get(spec: str) -> GameObject | None
```

Get an object by ID, friendly keyid, or name.

Three forms, chosen by prefix:

- `#<uuid>` — exact raw-id lookup (the canonical, stable address).
- `$<keyid>` — a friendly, unique handle set with `@keyid`
  (`get('$banknet_core')`); resolves through the keyid index, so it
  is collision-proof and survives renames. The `$` is the default
  keyid sigil and is game-configurable.
- anything else — a NAME match, local first (the executor's room and
  inventory) then the whole world, taking the FIRST match and never
  raising on ambiguity. Prefer `#id`/`$keyid` when identity matters.
  A name never finds an account (a character's login record, often of
  the same name); `#id` still does.

Returns the GameObject, or None if not found.

**Example**

```text
get('rusty key')  or  get('#3fa9...')  or  get('$banknet_core')
```

### `get_attr` {#fn-get_attr}

```text
get_attr(obj: GameObject | str | None, attr_name: str, default: Any = None) -> Any
```

Get an attribute from an object.

**Example**

```text
get_attr(enactor, 'hp', 0)
```

### `has_attr` {#fn-has_attr}

```text
has_attr(obj: GameObject | str | None, attr_name: str) -> bool
```

Check if an object has an attribute.

**Example**

```text
has_attr(me, 'charged')
```

### `idle_seconds` {#fn-idle_seconds}

```text
idle_seconds(obj: GameObject | str | None) -> int | None
```

Seconds since a player last typed (or since its link dropped); None
when it is not on.

**Example**

```text
idle_seconds(enactor) > 600
```

### `incr` {#fn-incr}

```text
incr(attr_name: str, by: Any = 1, default: Any = 0) -> Any
```

Increment a numeric attribute on `me` and return the new value.

Shorthand for `set_attr(me, k, get_attr(me, k, default) + by)` that
also hands back the result. Returns None if the write is refused (no
authority or the attribute is not writable). Non-numeric current
values fall back to `default`.

`default` is what an *unset* attribute counts as — and it matters
more than it looks. Plenty of counters don't start at 0: a lot number
whose first lot is #1, a freshness meter that starts full at 6. Pass
the same default the read would have used, or the first bump silently
lands one short:

    incr('next_lot', default=1)      # first lot is 2, not 1
    decr('freshness', default=6)     # an unset meter is full

Get this backwards and you break things quietly in the other
direction too: a counter of things *in flight* (pending timers, open
sessions) means **zero** when unset, and giving it `default=1` leaves
a phantom that never drains. Match the read; don't guess.

**Example**

```text
incr('visits')             # +1 from 0, returns the new count
incr('charge', 5)
incr('next_lot', default=1)
```

### `loc` {#fn-loc}

```text
loc(obj: GameObject | str | None) -> GameObject | None
```

Get an object's location.

**Example**

```text
loc(enactor)
```

### `name` {#fn-name}

```text
name(obj: GameObject | str | None) -> str
```

Get an object's name.

**Example**

```text
name(enactor)
```

### `online_players` {#fn-online_players}

```text
online_players() -> list[GameObject]
```

The characters in play now that the running object can see.

**Example**

```text
[name(p) for p in online_players()]
```

### `owner` {#fn-owner}

```text
owner(obj: GameObject | str | None) -> GameObject | None
```

Get an object's owner.

**Example**

```text
owner(me) == enactor
```

### `search_world` {#fn-search_world}

```text
search_world(tag=None, attr=None, value=None, name=None, limit: int = 100)
```

Query the world: search_world(tag='zone:castle'),
search_world(attr='xp_multiplier'), combinable. Results capped
(default 100). Protected attributes can't be queried.

**Example**

```text
search_world(tag='zone:castle')
```

### `set_attr` {#fn-set_attr}

```text
set_attr(obj: GameObject | str | None, attr_name: str, value: Any) -> bool
```

Set an attribute on an object the executor controls.

Returns True on success, False on failure (including no
authority — see docs/design/engine_vision.md).

**Example**

```text
set_attr(me, 'visits', get_attr(me, 'visits', 0) + 1)
```

### `set_desc` {#fn-set_desc}

```text
set_desc(obj: GameObject | str | None, text: str) -> bool
```

Set the description `look` shows on an object the executor controls
(like `@desc`; an empty string clears it).

**Example**

```text
set_desc(me, 'The lantern glows a steady amber.')
```

### `set_name` {#fn-set_name}

```text
set_name(obj: GameObject | str | None, name: str) -> bool
```

Rename an object the executor controls (like `@name`).

**Example**

```text
set_name(me, 'humming lantern')
```

### `teleport_obj` {#fn-teleport_obj}

```text
teleport_obj(obj: GameObject | str | None, destination: GameObject | str | None) -> bool
```

Move an object the executor controls straight to a destination — the
wizard/admin relocation. Now a thin alias for `move_to(force=True)`:
it tunnels past on_check **wards** (a Bound field), but still honors
the destination's **locks** (its teleport lock included) and requires
control of the object. A forced arrival still fires `on_enter`.

**Example**

```text
teleport_obj(enactor, 'The Oubliette')
```

### `V` {#fn-v}

```text
V(attr_name: str, default: Any = None) -> Any
```

Read an attribute off `me` (the executor) — the common case.

Shorthand for `get_attr(me, attr_name, default)` (PennMUSH `v()`
parity). Honors the same read flags as get_attr.

**Example**

```text
V('cost', 10)   # == get_attr(me, 'cost', 10)
```


## Tags & zones

### `add_tag` {#fn-add_tag}

```text
add_tag(obj: GameObject | str | None, tag: str) -> bool
```

Add a tag to an object the executor controls.

**Example**

```text
add_tag(me, 'glowing')
Role tags (god/admin/wizard/builder/staff) are refused unless the
executor's own role outranks the privilege — control of an object
never implies control of its *rank*, or a self-owned script could
grant itself admin.
```

### `has_tag` {#fn-has_tag}

```text
has_tag(obj: GameObject | str | None, tag: str) -> bool
```

Check if an object has a tag.

**Example**

```text
has_tag(enactor, 'player')
```

### `remove_tag` {#fn-remove_tag}

```text
remove_tag(obj: GameObject | str | None, tag: str) -> bool
```

Remove a tag from an object the executor controls.

**Example**

```text
remove_tag(me, 'hostile')
Role tags follow the same rank rule as :meth:`add_tag` — you cannot
strip a privilege you do not outrank.
```

### `tag_value` {#fn-tag_value}

```text
tag_value(obj, prefix: str)
```

First value of a namespaced tag: tag_value(here, 'zone')
-> 'castle' (None if untagged).

**Example**

```text
tag_value(here, 'zone')   # -> 'castle'
```

### `tag_values` {#fn-tag_values}

```text
tag_values(obj, prefix: str) -> list
```

All values of a namespaced tag: tag_values(here, 'zone')
-> ['castle', 'haunted'].

**Example**

```text
tag_values(here, 'zone')  # -> ['castle', 'haunted']
```

### `tags` {#fn-tags}

```text
tags(obj: GameObject | str | None) -> list[str]
```

Get all tags on an object.

**Example**

```text
'npc' in tags(enactor)
```

### `zone_rooms` {#fn-zone_rooms}

```text
zone_rooms(zone: str)
```

Rooms tagged into a zone: zone_rooms('castle').

**Example**

```text
zone_rooms('castle')
```

### `zones_of` {#fn-zones_of}

```text
zones_of(obj)
```

The zone names an object belongs to (no 'zone:' prefix).

**Example**

```text
zones_of(here)
```


## Locks & permissions

### `clear_lock` {#fn-clear_lock}

```text
clear_lock(obj: GameObject | str | None, lock_type: str) -> bool
```

Clear a lock from an object the executor controls.

**Example**

```text
clear_lock(me, 'basic')
```

### `has_entitlement` {#fn-has_entitlement}

```text
has_entitlement(obj: GameObject | str | None, entitlement: str) -> bool
```

Whether an object holds a permission entitlement (read-only).

The capability layer under roles: instead of asking "is this an
admin?", ask what you actually mean. Built-in roles grant the classic
sets; a game's own `role_def` ranks may grant them too, including names
the game invents for its own checks.

**Example**

```text
has_entitlement(enactor, 'SEE_ALL') or has_entitlement(enactor, 'SMUGGLE')
```

### `set_lock` {#fn-set_lock}

```text
set_lock(obj: GameObject | str | None, lock_type: str, expression: str) -> bool
```

Set a lock on an object the executor controls (validated).

**Example**

```text
set_lock(me, 'basic', "caller.has_tag('keyholder')")
```

### `test_lock` {#fn-test_lock}

```text
test_lock(obj: GameObject | str | None, lock_type: str, caller: GameObject | str | None = None) -> bool
```

Would `caller` (default: the executor) pass this lock?

**Example**

```text
test_lock('vault door', 'enter')
```


## Money

### `adjust_credits` {#fn-adjust_credits}

```text
adjust_credits(obj: GameObject | str | None, delta: int) -> bool
```

Mint or burn money on an object the executor controls.

**Example**

```text
adjust_credits(me, 100)
```

### `credits` {#fn-credits}

```text
credits(obj: GameObject | str | None) -> int
```

An object's balance.

**Example**

```text
credits(enactor) >= 10
```

### `transfer_credits` {#fn-transfer_credits}

```text
transfer_credits(source: GameObject | str | None, dest: GameObject | str | None, amount: int) -> bool
```

Move money FROM something the executor controls.

**Example**

```text
transfer_credits(me, enactor, 25)
```


## Accounts

### `account_attr` {#fn-account_attr}

```text
account_attr(obj: GameObject | str | None, name: str, default: Any = None) -> Any
```

An attribute on the character's account: shared by every character
the same person plays. None for a character with no account.

**Example**

```text
account_attr(enactor, 'banked_gold', 0)
```

### `account_characters` {#fn-account_characters}

```text
account_characters(obj: GameObject | str | None) -> list[str]
```

The names of every character on the character's account (empty for a
character with none).

**Example**

```text
account_characters(enactor)
```

### `character_limit` {#fn-character_limit}

```text
character_limit(obj: GameObject | str | None) -> int | None
```

How many characters the character's account may hold:
`MAX_CHARACTERS`, plus the account's `bonus_characters` (set by an
administrator), plus what its achievements grant. None for a character
with no account.

**Example**

```text
character_limit(enactor) - len(account_characters(enactor))
```

### `grant_achievement` {#fn-grant_achievement}

```text
grant_achievement(obj: GameObject | str | None, name: str) -> bool
```

Award an achievement (an `achievement_def`) to a character, once:
recorded on its account (or on the character, for `scope =
character`), announced to the player, its grants applied, and
`account:on_achievement` fired. False when there is no such
achievement or it is already earned. Queued; it lands after the script.

**Example**

```text
grant_achievement(enactor, 'Banshee Slayer')
```

### `has_achievement` {#fn-has_achievement}

```text
has_achievement(obj: GameObject | str | None, name: str) -> bool
```

Has the character (or its account) earned the achievement?

**Example**

```text
has_achievement(enactor, 'Banshee Slayer')
```

### `incr_account_attr` {#fn-incr_account_attr}

```text
incr_account_attr(obj: GameObject | str | None, name: str, by: int = 1) -> Any
```

Add `by` to a number on the character's account and return the new
value (None when refused). The same rules as `set_account_attr`.

**Example**

```text
incr_account_attr(enactor, 'kills')
```

### `set_account_attr` {#fn-set_account_attr}

```text
set_account_attr(obj: GameObject | str | None, name: str, value: Any) -> bool
```

Set an attribute on the character's account, for every character of
that person to read. The executor must control the character;
protected and `system` attributes are refused, and so are the
records the engine keeps (`characters`, `bonus_characters`,
`achievements`, the ban and login dates).

**Example**

```text
set_account_attr(enactor, 'banked_gold', 50)
```


## Clans

### `clan` {#fn-clan}

```text
clan(obj: GameObject | str | None, category: str = '') -> str | None
```

The name of the clan `obj` belongs to (in `category`; one who
has only applied is not in it yet), or None.

**Example**

```text
clan(enactor) == 'Ravens'
```

### `clan_add` {#fn-clan_add}

```text
clan_add(obj: GameObject | str | None, name: str, position: str | None = None) -> bool
```

Put a character in a clan (at `position`, else the government's
accept position), as if accepted. False, changing nothing, for a
non-character, a missing clan or position, or one already in a clan of
that kind. Builders only; it lands after the script.

**Example**

```text
clan_add(enactor, 'Ravens')
```

### `clan_has_power` {#fn-clan_has_power}

```text
clan_has_power(obj: GameObject | str | None, power: str, category: str = '') -> bool
```

Does `obj`'s position in its clan hold `power` outright (not
merely vote on it)?

**Example**

```text
clan_has_power(enactor, 'home_privs')
```

### `clan_level` {#fn-clan_level}

```text
clan_level(name: str) -> int | None
```

A clan's level, or None when there is no such clan.

**Example**

```text
clan_level('Ravens') >= 3
```

### `clan_members` {#fn-clan_members}

```text
clan_members(name: str) -> list[GameObject]
```

A clan's members (not its applicants), highest rank first.

**Example**

```text
[name(m) for m in clan_members('Ravens')]
```

### `clan_position` {#fn-clan_position}

```text
clan_position(obj: GameObject | str | None, category: str = '') -> str | None
```

The id of `obj`'s position in its clan (`boss`, `member`), or
None.

**Example**

```text
clan_position(enactor) == 'treasurer'
```

### `clan_rank` {#fn-clan_rank}

```text
clan_rank(obj: GameObject | str | None, category: str = '') -> int | None
```

The rank of `obj`'s position in its clan, 0 the highest; None
outside a clan.

**Example**

```text
clan_rank(enactor) is not None and clan_rank(enactor) <= 1
```

### `clan_relation` {#fn-clan_relation}

```text
clan_relation(a: str, b: str) -> str | None
```

Clan `a`'s declared relation toward clan `b`: war, hostile,
neutral, friendly or ally (None when either is not a clan). One-sided:
an alliance holds only when both say ally.

**Example**

```text
clan_relation(clan(enactor), 'Smiths') == 'war'
```

### `clan_remove` {#fn-clan_remove}

```text
clan_remove(obj: GameObject | str | None, name: str) -> bool
```

Take a character out of a clan (`CLANLEAVE` fires, reason
`removed`). Builders only; it lands after the script.

**Example**

```text
clan_remove(enactor, 'Ravens')
```

### `clans_at_war` {#fn-clans_at_war}

```text
clans_at_war(a: str, b: str) -> bool
```

True when either clan has declared war on the other.

**Example**

```text
clans_at_war(clan(enactor), clan(target))
```


## Quests

### `quest_advance` {#fn-quest_advance}

```text
quest_advance(obj: GameObject | str | None, quest: str, key: str, by: int = 1) -> bool
```

Count `by` toward the objective `key` of `obj`'s current stage
of `quest`: a `custom` objective, or any other. False when they are
not on that stage. Builders only; it lands after the script.

**Example**

```text
quest_advance(enactor, 'The Cinder Road', 'ledger')
```

### `quest_complete` {#fn-quest_complete}

```text
quest_complete(obj: GameObject | str | None, quest: str) -> bool
```

Complete `obj`'s `quest` now, whatever is left of it, and pay its
rewards. Builders only; it lands after the script.

**Example**

```text
quest_complete(enactor, 'The Cinder Road')
```

### `quest_count` {#fn-quest_count}

```text
quest_count(obj: GameObject | str | None, quest: str, key: str) -> int
```

How far `obj` is on the objective `key` of their current stage
of `quest` (0 when they are not on it, or the stage has no such
objective). A `collect` objective counts what they hold now.

**Example**

```text
quest_count(enactor, 'Fido trouble', 'kill')
```

### `quest_fail` {#fn-quest_fail}

```text
quest_fail(obj: GameObject | str | None, quest: str) -> bool
```

End `obj`'s `quest` unfinished (`QUESTFAIL` fires, reason
`failed`). Builders only; it lands after the script.

**Example**

```text
quest_fail(enactor, 'The Cinder Road')
```

### `quest_offer` {#fn-quest_offer}

```text
quest_offer(obj: GameObject | str | None, quest: str) -> bool
```

Start `quest` for `obj` as if they had accepted it (a note read,
a stranger met): True when they may take it, False (and nothing
happens) when not. Builders only; it lands after the script.

**Example**

```text
quest_offer(enactor, 'The Cinder Road')
```

### `quest_state` {#fn-quest_state}

```text
quest_state(obj: GameObject | str | None, quest: str) -> int | str | None
```

Where `obj` stands on `quest`: None (never taken, or failed), the
current stage number (1 is the first), `'ready'` (every stage met,
waiting to be handed in) or `'done'`.

**Example**

```text
quest_state(enactor, 'Fido trouble') == 'done'
```


## Messaging & prompts

### `ansi` {#fn-ansi}

```text
ansi(codes: str, text: str) -> str
```

Penn-style color: ansi('rh', 'My thing') — lowercase letters =
foreground (r g y b m c w x), 'h' brightens it, UPPERCASE =
background, u = underline, i = inverse video. Returns
|-markup + reset.

**Example**

```text
ansi('rh', 'DANGER')
```

### `cemit` {#fn-cemit}

```text
cemit(channel: str, text: str) -> bool
```

Announce a line on a channel, as is (no speaker name): a herald, a
server notice. False for no such channel. Queued.

**Example**

```text
cemit('gossip', 'The fair opens at dawn.')
```

### `channel_members` {#fn-channel_members}

```text
channel_members(channel: str) -> list[str]
```

The names of the online players who hear a channel now.

**Example**

```text
channel_members('gossip')
```

### `escape` {#fn-escape}

```text
escape(text: str) -> str
```

Escape color markup in player-provided text (|| literals).

**Example**

```text
say('They said: ' + escape(arg0))
```

### `oemit` {#fn-oemit}

```text
oemit(exclude: GameObject | str, message: str) -> None
```

Emit to the executor's room, excluding one object. A room broadcast
is a narrated line: in a game with `CAPITALIZE_LINES` (Merc) its first
letter is capitalized, as ROM's `act()` does; otherwise it is sent as
written.

**Example**

```text
oemit(enactor, 'Bob vanishes in smoke.')
```

### `oob` {#fn-oob}

```text
oob(target: GameObject | str, package: str, data: dict) -> None
```

Send structured out-of-band data (GMCP) to a player's client —
custom UI panels from softcode. Delivered after the script,
like pemit. No-op for clients without an OOB channel.

**Example**

```text
oob(enactor, 'Ship.Status', {'hull': 87})
```

### `pemit` {#fn-pemit}

```text
pemit(target: GameObject | str, message: str) -> None
```

Send a private message to a target (delivered after the script),
exactly as written (ROM's `send_to_char`: a lowercase first letter
stays lowercase).

**Example**

```text
pemit(enactor, 'A voice only you can hear...')
```

### `prompt` {#fn-prompt}

```text
prompt(target, text: str, callback: str, persistent: bool = False) -> bool
```

Ask a player a question; their next line runs the `callback`
attribute (on the executor) with the answer as arg0 — a softcode
wizard. Chain by prompting again inside the callback.
`persistent=True` survives a reboot. Requires the executor to
control the target's own object (self/owned/admin).

**Example**

```text
prompt(enactor, 'What is your name?', 'on_name')
```

### `remit` {#fn-remit}

```text
remit(room: GameObject | str, message: str) -> None
```

Emit a message to everyone in a room (delivered after the script).
A room broadcast is a narrated line: in a game with
`CAPITALIZE_LINES` (Merc) its first letter is capitalized, as ROM's
`act()` does; otherwise it is sent as written.

**Example**

```text
remit(here, 'The ground trembles.')
```

### `send_mail` {#fn-send_mail}

```text
send_mail(to: str, subject: str, body: str) -> bool
```

Send mail to a character, from this object (system mail: a guild's
dues notice, a quest's reward slip). False when the character has no
account or a full mailbox. Queued.

**Example**

```text
send_mail('Gus', 'Dues', 'Your guild dues are late.')
```


## Dice & skill checks

### `band` {#fn-band}

```text
band(value: int, *thresholds: int, skill: str = '') -> CheckResult
```

Tiered outcome (PbtA): tier = how many ascending thresholds
`value` clears. `band(2d6+stat, 7, 10)` -> 0 miss / 1 partial /
2 full.

**Example**

```text
r = band(roll('2d6') + get_attr(enactor, 'stat_cool', 0), 7, 10)
result = switch(r.margin, 2, 'You pull it off.',
                1, 'You manage it, at a cost.',
                'It goes wrong.')
```

### `check` {#fn-check}

```text
check(name: str, mod: int = 0) -> bool
```

Roll a skill check AS the subject; True on success.

The subject is the enactor in a script, the viewer in an inline block
or `@detail` condition, the caller in a lock, the roller in a rule.
For the graded result use `check_roll(obj, skill, mod)`.

**Example**

```text
[[result = ' A loose flagstone.' if check('observation') else '']]
```

### `check_roll` {#fn-check_roll}

```text
check_roll(obj, skill: str, modifier: int = 0)
```

Roll a skill check and return the GRADED, condition-modified result.

Like :meth:`skill_check`, but hands back the whole `CheckResult`
instead of just pass/fail — read `.success`, `.margin` (degree
of success), `.roll` and `.effective` off it. And unlike the
hand-rolled `margin_under(roll('3d6'), get_attr(me, 'skill', 8))`
idiom, this goes through the real `check()` pipeline, so
`check_mods` (fear, darkness, a meal buff, encumbrance) are folded
in. That idiom reads the *trained* level raw and silently ignores
every condition — a fear-struck crafter rolled as if calm.

Returns a failing result (margin 0) for an unresolvable object.

**Example**

```text
r = check_roll(enactor, 'cooking'); quality = r.margin // 2
```

### `contest` {#fn-contest}

```text
contest(actor, actor_skill: str, opponent, opponent_skill: str) -> bool
```

Opposed quick contest; True if the actor wins.

**Example**

```text
contest(enactor, 'fast_talk', me, 'detect_lies')
```

### `dice` {#fn-dice}

```text
dice(num: int = 1, sides: int = 6, modifier: int = 0) -> int
```

Roll dice: NdS+M

Args:
    num: Number of dice
    sides: Sides per die
    modifier: Added to total

**Example**

```text
dice(3, 6)   # 3d6
```

### `highest` {#fn-highest}

```text
highest(pool: int, *, sides: int = 6, skill: str = '') -> CheckResult
```

Highest-die tiers (Blades): 6 -> full (2), 4-5 -> partial (1),
else miss (0).

**Example**

```text
r = highest(V('action_rating', 2))
result = switch(r.margin, 2, 'You do it clean.',
                1, 'You do it, but there is trouble.',
                'It goes badly.')
```

### `margin_over` {#fn-margin_over}

```text
margin_over(rolled: int, target: int, *, skill: str = '') -> CheckResult
```

Roll-over (D20): success if `rolled >= target`; margin is how far
over.

**Example**

```text
r = margin_over(roll('1d20') + V('attack_bonus', 0), 15)
result = 'Hit!' if r.success else 'Miss.'
# r.margin >= 10 -> a crit, if your game wants degrees
```

### `margin_under` {#fn-margin_under}

```text
margin_under(rolled: int, target: int, *, skill: str = '') -> CheckResult
```

Roll-under (GURPS, CoC): success if `rolled <= target`; margin is
how far under.

**Example**

```text
r = margin_under(roll('3d6'), get_attr(enactor, 'skill_stealth', 10))
result = 'Clean.' if r.success else 'A board creaks.'
# r.margin is how far under the target — the degree of success
```

### `net_successes` {#fn-net_successes}

```text
net_successes(pool: int, tn: int, *, sides: int = 6, explode: bool = True, skill: str = '') -> CheckResult
```

Dice-pool success-counting (Shadowrun, WoD): roll `pool` dice,
count those `>= tn`. Graded by the count of successes.

**Example**

```text
r = net_successes(V('hacking_pool', 6), 5)
result = f'{r.margin} successes.' if r.success else 'Glitch.'
# pool of 6 d6, each 5 or 6 counts; r.margin is the count
```

### `rand` {#fn-rand}

```text
rand(low: int = 0, high: int = 100) -> int
```

Random integer between low and high (inclusive).

**Example**

```text
rand(1, 100)
```

### `roll` {#fn-roll}

```text
roll(expr: str | int) -> int
```

Roll a dice expression to a total. Supports `NdS` / `dS`, Fudge
`NdF` (each die -1/0/+1), `!` explode, `khK` / `klK` keep
highest/lowest, and a trailing `+K` / `-K` modifier. A bare int
passes through.

**Example**

```text
roll('3d6')          # GURPS: 3 six-sided dice, totalled
roll('1d20+5')       # D20 with a +5 modifier
roll('4d6kh3')       # roll 4, keep the highest 3 (ability scores)
roll('4dF')          # Fudge/FATE: each die -1, 0 or +1
damage(enactor, roll('2d6'))
```

### `skill` {#fn-skill}

```text
skill(name: str) -> int
```

The subject's effective level in a skill (trained, else its default).

The subject is the enactor in a script, the viewer in an inline block
or `@detail` condition, the caller in a lock, the roller in a rule.

**Example**

```text
[[result = 'You read the runes.' if skill('runes') >= 12 else '']]
```

### `skill_check` {#fn-skill_check}

```text
skill_check(obj, skill: str, modifier: int = 0) -> bool
```

Roll a skill check for an object (name/#id or object).

**Example**

```text
skill_check(enactor, 'stealth', -2)
```


## Pools

### `harm_pool` {#fn-harm_pool}

```text
harm_pool(obj: GameObject | str | None, name: str, amount: int) -> int
```

Harm a pool of something in reach, spilling into its overflow pool.
No soak, no wards: the deliberate bypass, like `damage()`. Returns the
amount taken (0 when out of reach or without the pool).

**Example**

```text
harm_pool(enactor, 'stress', 2)
```

### `has_pool` {#fn-has_pool}

```text
has_pool(obj: GameObject | str | None, name: str) -> bool
```

True when the object has the pool.

**Example**

```text
has_pool(enactor, 'mana')
```

### `hungry` {#fn-hungry}

```text
hungry(obj: GameObject | str | None) -> bool
```

True when the character's `food` pool is empty: it recovers at half
speed and counts toward dying of hunger. False without the pool.

**Example**

```text
if hungry(enactor): pemit(enactor, 'The smell of bread makes you dizzy.')
```

### `mend_pool` {#fn-mend_pool}

```text
mend_pool(obj: GameObject | str | None, name: str, amount: int) -> int
```

Mend a pool of something in reach: raise a down pool toward its max,
lower an up pool toward its floor. Returns the amount mended.

**Example**

```text
mend_pool(enactor, 'hp', 5)
```

### `pool` {#fn-pool}

```text
pool(obj: GameObject | str | None, name: str) -> int | None
```

A pool's value, or None when the object has no such pool.

**Example**

```text
pool(enactor, 'hp')
```

### `pool_max` {#fn-pool_max}

```text
pool_max(obj: GameObject | str | None, name: str) -> int | None
```

A pool's maximum, or None when it is unbounded or absent.

**Example**

```text
pool_max(here, 'shields')
```

### `spend_pool` {#fn-spend_pool}

```text
spend_pool(name: str, amount: int) -> bool
```

Pay a cost from the executor's own pool, all or nothing. False, with
nothing spent, when it is short.

**Example**

```text
spend_pool('heat', 3)
```

### `spent` {#fn-spent}

```text
spent(obj: GameObject | str | None, name: str) -> bool
```

True when the pool is used up (a down pool at or below its
`spent_at`, an up pool at its max).

**Example**

```text
spent(here, 'hull')
```

### `thirsty` {#fn-thirsty}

```text
thirsty(obj: GameObject | str | None) -> bool
```

True when the character's `water` pool is empty: it recovers at half
speed and counts toward dying of thirst. False without the pool.

**Example**

```text
thirsty(enactor)
```


## Combat & effects

### `apply_effect` {#fn-apply_effect}

```text
apply_effect(obj: GameObject | str | None, effect_id: str, **params: Any) -> bool
```

Attach an effect (modifier_effect / damage_over_time /
regeneration / disposition_boost) to something in the
executor's room.

    apply_effect(enactor, 'modifier_effect', kind='fear',
                 duration=8, check_mods={'all': -2},
                 apply_msg='Terror grips you!')

**Example**

```text
apply_effect(enactor, 'modifier_effect', kind='fear',
duration=8, check_mods={'all': -2})
```

### `attackers` {#fn-attackers}

```text
attackers(target: GameObject | str | None) -> list
```

Who is attacking `target` in its fight (empty out of one).

**Example**

```text
attackers(enactor)
```

### `cast` {#fn-cast}

```text
cast(target: GameObject | str | None, ability: str = '', *, tags: list[str] | None = None) -> bool
```

Direct an ability at a target — the ability analog of `act`. Fires
`event:on_cast` at the target with the caller's `tags` (a spell
passes `['magic']`, a psi power `['psi']` — the kernel forces no
genre category), so the target's `ON_CAST` reacts AND its
`on_check` wards resist by category: a magic-shield ring's
`block() if has_atag('magic')` refuses any incoming magic power,
not just damage — the resistance seam a spell can't otherwise reach.

It fires the ward and reaction event only: no cost is paid and no
effect is applied. To run an ability definition (its cost, save,
damage and effects, as the `cast` command does) use `use_ability`.
Use `contest()` for a resist *roll*.

**Example**

```text
# a fear spell the target's wards can refuse by category
cast(victim, 'fear', tags=['mind'])

# the resist roll and the ward layer, together
landed = cast(victim, 'fear', tags=['mind']) and \
         contest(enactor, 'occultism', victim, 'will')
```

### `damage` {#fn-damage}

```text
damage(obj: GameObject | str | None, amount: int, dtype: str | None = None) -> bool
```

Deal damage to something in the executor's room: it lands in the
target's damage pool (`hp` unless it says otherwise), with soak (each
pool's `soak_attr`, a ship's armor). After the
script finishes the change settles: damage that spends the target's
vital pool runs the combat manager's death path (corpses, CP awards,
unconsciousness), and falling through `hitprcnt` fires
`ON_HITPRCNT`.

With a damage type, the hit routes through the active ruleset's
`apply_damage` — so a target's `resistances` (and any other
ruleset mitigation) apply: a fire-immune mob shrugs off
damage(enactor, 12, 'fire'). Untyped damage stays raw.

**Example**

```text
damage(enactor, 3)
damage(enactor, 12, 'fire')
```

### `disarm` {#fn-disarm}

```text
disarm(target: GameObject | str | None) -> bool
```

Knock the target's wielded weapon to the floor. Queued.

**Example**

```text
disarm(enactor)
```

### `heal` {#fn-heal}

```text
heal(obj: GameObject | str | None, amount: int) -> bool
```

Mend the damage pool (`hp` unless the target says otherwise),
capped at its max, of something in the executor's room.

**Example**

```text
heal(enactor, 5)
```

### `remove_effect` {#fn-remove_effect}

```text
remove_effect(obj: GameObject | str | None, kind: str) -> bool
```

Strip an active effect by kind (cure poison, calm fear).

**Example**

```text
remove_effect(enactor, 'fear')
```

### `retarget` {#fn-retarget}

```text
retarget(attacker: GameObject | str | None, new_target: GameObject | str | None) -> bool
```

Turn a fighter on a new target in the same room (a rescue): the new
target joins the fight if it was not in it. Queued; it happens after
the script.

**Example**

```text
retarget(attackers(enactor)[0], me)
```

### `start_combat` {#fn-start_combat}

```text
start_combat(attacker: GameObject | str | None, target: GameObject | str | None) -> bool
```

Throw an attacker the executor controls into combat with a
target in the same room (queued; the encounter starts after the
script finishes).

**Example**

```text
start_combat('beast', enactor)
```

### `use_ability` {#fn-use_ability}

```text
use_ability(name: str, target: GameObject | str | None = None) -> bool
```

Use an ability or spell definition (`ability_def` / `spell_def`)
as the executor: pay its cost, roll its save, apply its effects — what
the `cast` command does for a player. Without `target` the ability
picks its own (yourself, or your combat opponent for an attack).

Returns False when no definition matches `name` or the executor does
not qualify (class, level, skill). It runs after the script, so a False
from a failed cost or a ward's veto is not visible here.

**Example**

```text
use_ability('fireball', enactor)
```


## NPCs & behaviors

### `adjust_disposition` {#fn-adjust_disposition}

```text
adjust_disposition(npc, other, delta: int) -> bool
```

Shift an NPC's attitude. Authority: the executor must control
the NPC (its own opinions) — you can't script others' minds
about yourself.

**Example**

```text
adjust_disposition(me, enactor, 1)
```

### `attach_behavior` {#fn-attach_behavior}

```text
attach_behavior(obj: GameObject | str | None, behavior_id: str, **params: Any) -> bool
```

Attach a registered behavior to an object the executor controls.
Like `@behavior`, it also needs builder authority (BUILD) behind the
executor: a mortal player's gadget cannot attach behaviors; unowned
world objects and NPCs can.

**Example**

```text
attach_behavior('golem', 'script_ticker', interval=5)
```

### `behaviors` {#fn-behaviors}

```text
behaviors(obj: GameObject | str | None) -> list[str]
```

Behavior ids attached to an object.

**Example**

```text
'wandering' in behaviors('rat')
```

### `companions` {#fn-companions}

```text
companions(obj: GameObject | str | None) -> list[GameObject]
```

`obj`'s companions, wherever they are.

**Example**

```text
len(companions(enactor))
```

### `detach_behavior` {#fn-detach_behavior}

```text
detach_behavior(obj: GameObject | str | None, behavior_id: str) -> bool
```

Detach a behavior (by id) from an object the executor controls (needs
BUILD behind the executor, like `attach_behavior`).

**Example**

```text
detach_behavior('golem', 'wandering')
```

### `disposition` {#fn-disposition}

```text
disposition(npc, other=None) -> int
```

How npc feels about other (default: the enactor).

**Example**

```text
disposition(me, enactor) >= 2
```

### `force` {#fn-force}

```text
force(obj: GameObject | str | None, command: str) -> bool
```

Make something the executor controls run a command (queued;
executes through the real dispatcher after the script). The
possession primitive — see @force.

**Example**

```text
force('minion', 'say Yes, master.')
```

### `master` {#fn-master}

```text
master(obj: GameObject | str | None) -> GameObject | None
```

The character `obj` is a companion of (a pet's owner, a charmed
creature's charmer), or None.

**Example**

```text
pemit(master(me), 'Woof.') if master(me) else None
```

### `reaction_roll` {#fn-reaction_roll}

```text
reaction_roll(npc, other=None, modifier: int = 0) -> int
```

Memoized first-impression roll (npc must be in executor's reach).

**Example**

```text
reaction_roll(me)
```

### `release` {#fn-release}

```text
release(obj: GameObject | str | None) -> bool
```

Free `obj` (an NPC the executor controls) from its master; it
stays where it is. Happens after the script (`ON_RELEASE` fires).

**Example**

```text
release(me)
```

### `set_master` {#fn-set_master}

```text
set_master(obj: GameObject | str | None, master: GameObject | str | None) -> bool
```

Make `obj` (an NPC the executor controls) `master`'s companion:
it follows and obeys `order`. False, with nothing changed, past
`master`'s companion limit or `COMPANION_LEVEL_DIFF`, or for a
player. The bond happens after the script (`ON_BOND` fires then).

**Example**

```text
set_master(me, enactor)
```


## Movement & travel

### `enter_instance` {#fn-enter_instance}

```text
enter_instance(player: GameObject | str | None, template: str, *, mode: str = 'solo', return_room: GameObject | str | None = None, idle_ttl: float | None = None) -> bool
```

Send a player into a private, transient copy of a template area,
materializing one on demand — and reusing their own copy (or their
leader's, if it's `shared`) if one already exists. The area opts in
by tagging a room `instance_template`; the copy is reaped when it's
sat empty past `idle_ttl`. The executor must control the player.

`mode` — `'solo'` (private) or `'shared'` (the owner's
followers route into the owner's copy). `return_room` — where a
straggler is evacuated when the copy is reaped (else their home).
Returns whether the entry was *authorized and queued*; the
materialize-and-move happens after the script ends.

Callable when the executor controls the player, or the player is the
enactor (they walked into the portal). This is the *scripted* API —
a game event opening a dungeon, a puzzle reward. For a portal
**exit**, prefer a real deferred-destination exit instead:
`@set exit/dest_resolver = instance` +
`@set exit/instance_template = crypt` — a normal traversal, with
follower routing.

**Example**

```text
# a private copy of the crypt, just for this player
enter_instance(enactor, 'crypt')

# one copy for the whole party; stragglers evacuate to the inn
enter_instance(enactor, 'crypt', mode='shared',
               return_room='The Rusty Anchor', idle_ttl=600)
```

### `enter_wilderness` {#fn-enter_wilderness}

```text
enter_wilderness(player: GameObject | str | None, region: str, x, y) -> bool
```

Send a player to the wilderness cell at `(region, x, y)`,
materializing it on demand — the scripted seam into a
coordinate-keyed region. (Walking between cells needs no softcode:
the cells' exits are real exits with deferred destinations.)

Callable when the executor controls the player, or the player is
the consenting enactor. Entry is gated by the region master's
ENTER lock, checked against the player being sent. Returns whether
the entry was *authorized and queued*; the materialize-and-move
happens after the script ends.

**Example**

```text
enter_wilderness(enactor, 'wilds', 10, 10)
```

### `move_to` {#fn-move_to}

```text
move_to(target: GameObject | str | None, destination: GameObject | str | None, *, tags: list[str] | None = None, force: bool = False) -> bool
```

Relocate a player/object to a destination with the movement checks
baked in — the one relocation verb. The move is always tagged
`movement`, so a Bound ward (`block() if has_atag('movement')`)
stops it; pass extra `tags` (e.g. `['magic']`) so anti-magic wards
catch it too. Both the origin and the destination get an event-veto,
plus the destination's ENTER/TELEPORT locks. Returns whether the move
was *authorized and queued* — wards/locks run after the script ends,
and a veto fizzles the move then, delivering the reason to the mover.
(`tags` here = `extra_tags` on the core `movement.move_to`.)

`force=True` (== `teleport_obj`) skips the on_check **wards** but
NOT the **locks** — the wizard bypass. It requires full control of the
target; without force, the enactor may also move *themselves* (a
`cast teleport` moves the caster).

**Example**

```text
`&spell.teleport = move_to(enactor, 'The Sanctum', tags=['magic'])`
```


## Firing your own events

### `act` {#fn-act}

```text
act(target: GameObject | str, message: str = '', targeting: str = 'remote', action_type: str = 'event:act', extra: dict | None = None, tags: list | set | tuple | None = None) -> bool
```

Fire a PROPAGATED action that can reach BEYOND your own room —
unlike pemit/remit (which just deliver text), this runs the
two-pass engine, so behaviors can veto or react at both ends.

`targeting` chooses the audience:
  - `'remote'` — the TARGET's room (a different room from yours):
    scry, remote cast. A ward in *your* room or the destination can
    block it, and occupants there witness/react.
  - `'zone'` — every room in the target's zone (an alarm).
  - `'room'` — the target's room, local but propagated.

The message reaches the far room's occupants (the `'remote'`
audience). Reaching a destination is authority-gated by its
`reach` lock (open by default, like teleport) — a room or zone can
set `lock_reach` to lock out remote actions.

Because `ON_<EVENT>` hooks match on the action type's suffix, an
`action_type` you invent needs no registration: fire
`'event:toll'` and any object with an `on_toll` attribute reacts.

`extra` is the event's payload: each key becomes an
`adata(key)` a reactor can read, and an `on_check` ward can
rewrite it with `set_adata`. The `message` is always present as
`adata('message')`; keys named `message` or `remote_rooms`
are reserved and ignored. `tags` are action tags a ward can key
on with `has_atag`.

Note that one action object crosses every leg of a `'zone'` or
`'remote'` send, so a ward that rewrites the payload in one room
changes what the *later* rooms receive. That is the mechanism
behind a containment bulkhead, and a surprise if you expected each
room to be judged independently.

**Example**

```text
# scry — watch a distant room
act(thing, 'A scrying eye blinks open.', targeting='remote')

# a zone-wide alarm: the message reaches every room in the
# zone, and each room's wards get the two-pass. The softcode
# ON_<EVENT> hook fires in the actor's room only.
act(intruder, 'Klaxons wail!', targeting='zone',
    action_type='event:alert')

# a custom local event: objects with an on_toll hook answer
act(me, 'A deep bell tolls.', targeting='room',
    action_type='event:toll')

# a payload the reactors read and a ward can rewrite
act(me, 'Coolant vents!', targeting='zone',
    action_type='event:breach',
    extra={'severity': 8}, tags=['hazard'])
```


## Time & scheduling

### `cancel_wait` {#fn-cancel_wait}

```text
cancel_wait(wait_id: str | None) -> bool
```

Cancel a pending wait by the handle `wait()` returned, before it
fires. You must control the object that scheduled it. Returns True if
the cancellation was queued (a no-op if the handle is unknown or
already fired).

**Example**

```text
cancel_wait(get_attr(me, 'fuse'))
```

### `expire` {#fn-expire}

```text
expire(target: GameObject | str | None, seconds: float) -> bool
```

Give an object a lifetime: after `seconds` it fires `ON_EXPIRE`
and is destroyed by the world tick (a summoned creature, a smoke
cloud, a temp portal). Unlike `wait()`, the countdown lives on the
object and survives across ticks. `ON_EXPIRE` may renew the lease
by calling `expire` again. Requires control of the target.

**Example**

```text
expire(create_obj('a wisp of smoke'), 30)
```

### `game_time` {#fn-game_time}

```text
game_time() -> dict[str, Any]
```

The game's time and date: `{'hour', 'minute', 'day', 'month', 'year',
'month_name', 'day_name', 'time_of_day'}`.

**Example**

```text
game_time()['hour']
```

### `now` {#fn-now}

```text
now() -> int
```

Current time as epoch seconds — cache expiry, cooldowns.

**Example**

```text
now() - get_attr(me, 'lit_at', 0) > 300
```

### `start_task` {#fn-start_task}

```text
start_task(seconds: float, done_attr: str, label: str = '', interrupt_attr: str | None = None) -> bool
```

Make the enactor busy for `seconds`: when the time passes, this
object's `done_attr` runs with the enactor bound. Moving, a fight or
the `stop` command breaks it off and runs `interrupt_attr` instead.
The task is stored on the character, so it survives a reboot. False
when the enactor is already busy (or out of reach).

**Example**

```text
start_task(10, 'smelt_done', 'smelting ore', 'smelt_stop')
```

### `stop_task` {#fn-stop_task}

```text
stop_task(obj: GameObject | str | None) -> bool
```

Break off a character's task (its interrupt script runs). The object
that started the task may stop it, as may anything that controls the
character.

**Example**

```text
stop_task(enactor)
```

### `task_of` {#fn-task_of}

```text
task_of(obj: GameObject | str | None) -> dict | None
```

What a character is busy with: `{"label": ..., "left": seconds}`, or
None.

**Example**

```text
task_of(enactor)
```

### `time_of_day` {#fn-time_of_day}

```text
time_of_day() -> str
```

`dawn`, `day`, `dusk` or `night`.

**Example**

```text
if time_of_day() == 'night': pemit(enactor, 'The owls are out.')
```

### `wait` {#fn-wait}

```text
wait(seconds: float, command: str) -> str | None
```

Run a script command as the executor exactly `seconds` from now
(one-shot, its own timer — a 0.15s fuse fires at 0.15s, not quantized
to the heartbeat; pending waits don't survive a reboot). Returns a
HANDLE id you can pass to `cancel_wait` to call the wait off before
it fires — a defuse, an abort.

**Example**

```text
t = wait(30, 'detonate')
... set_attr(me, 'fuse', t) ...          # stash the handle
... if defused: cancel_wait(get_attr(me, 'fuse'))
```

### `weather` {#fn-weather}

```text
weather(room: GameObject | str | None = None) -> str | None
```

The weather in a room's zone (rolled hourly by its zone master), or
None.

**Example**

```text
weather(here)
```


## Text

### `capstr` {#fn-capstr}

```text
capstr(text: str) -> str
```

Capitalize each word.

**Example**

```text
capstr('the iron king')   # 'The Iron King'
```

### `extract` {#fn-extract}

```text
extract(lst: list | str, position: int, delimiter: str = ' ') -> str
```

Get element at position (1-indexed).

**Example**

```text
extract('a b c', 2)       # 'b'
```

### `first` {#fn-first}

```text
first(lst: list | str, delimiter: str = ' ') -> str
```

Get first element of list or first word of string.

**Example**

```text
first('north south east') # 'north'
```

### `last` {#fn-last}

```text
last(lst: list | str, delimiter: str = ' ') -> str
```

Get last element.

**Example**

```text
last('north south east')  # 'east'
```

### `lcfirst` {#fn-lcfirst}

```text
lcfirst(text: str) -> str
```

Lowercase first character.

**Example**

```text
lcfirst('Hello')          # 'hello'
```

### `left` {#fn-left}

```text
left(text: str, length: int) -> str
```

Get leftmost N characters.

**Example**

```text
left('lighthouse', 5)     # 'light'
```

### `member` {#fn-member}

```text
member(item: str, lst: list | str, delimiter: str = ' ') -> int
```

Find position of item in list (1-indexed, 0 if not found).

**Example**

```text
member('south', 'north south east')  # 2
```

### `mid` {#fn-mid}

```text
mid(text: str, start: int, length: int) -> str
```

Extract substring (1-indexed like MUSH).

**Example**

```text
mid('lighthouse', 5, 5)   # 'house'
```

### `repeat` {#fn-repeat}

```text
repeat(text: str, count: int) -> str
```

Repeat text N times.

**Example**

```text
repeat('-', 40)
```

### `replace` {#fn-replace}

```text
replace(text: str, old: str, new: str) -> str
```

Replace all occurrences of old with new.

**Example**

```text
replace(arg0, 'gold', 'lead')
```

### `rest` {#fn-rest}

```text
rest(lst: list | str, delimiter: str = ' ') -> str | list
```

Get all but first element.

**Example**

```text
rest('north south east')  # 'south east'
```

### `right` {#fn-right}

```text
right(text: str, length: int) -> str
```

Get rightmost N characters.

**Example**

```text
right('lighthouse', 5)    # 'house'
```

### `setdiff` {#fn-setdiff}

```text
setdiff(list1: str, list2: str, delimiter: str = ' ') -> str
```

Difference of two lists (in list1 but not list2).

**Example**

```text
setdiff('a b', 'b c')     # 'a'
```

### `setinter` {#fn-setinter}

```text
setinter(list1: str, list2: str, delimiter: str = ' ') -> str
```

Intersection of two lists.

**Example**

```text
setinter('a b', 'b c')    # 'b'
```

### `setunion` {#fn-setunion}

```text
setunion(list1: str, list2: str, delimiter: str = ' ') -> str
```

Union of two space-separated lists.

**Example**

```text
setunion('a b', 'b c')    # 'a b c'
```

### `strlen` {#fn-strlen}

```text
strlen(text: str) -> int
```

Get string length.

**Example**

```text
strlen(name(enactor))
```

### `trim` {#fn-trim}

```text
trim(text: str) -> str
```

Remove leading/trailing whitespace.

**Example**

```text
trim('  hello  ')
```

### `ucfirst` {#fn-ucfirst}

```text
ucfirst(text: str) -> str
```

Capitalize first character.

**Example**

```text
ucfirst('hello')          # 'Hello'
```

### `words` {#fn-words}

```text
words(text: str, delimiter: str = ' ') -> int
```

Count words/elements in text.

**Example**

```text
words('a b c')            # 3
```


## Math & logic

### `ceil` {#fn-ceil}

```text
ceil(value: float) -> int
```

Round up to integer.

**Example**

```text
ceil(7.1)                 # 8
```

### `clamp` {#fn-clamp}

```text
clamp(value: int | float, low: int | float, high: int | float) -> int | float
```

Clamp value between low and high.

**Example**

```text
clamp(damage, 1, 10)
```

### `floor` {#fn-floor}

```text
floor(value: float) -> int
```

Round down to integer.

**Example**

```text
floor(7.9)                # 7
```

### `if_else` {#fn-if_else}

```text
if_else(condition: bool, true_val: Any, false_val: Any) -> Any
```

Conditional expression.

**Example**

```text
if_else(credits(enactor) >= 10, 'Welcome!', 'No coin, no entry.')
```

### `switch` {#fn-switch}

```text
switch(value: Any, *cases: Any) -> Any
```

Switch statement.

Args: value, case1, result1, case2, result2, ..., default

**Example**

```text
switch(tag_value(here, 'zone'), 'castle', 'Halt!',
'forest', 'Rustle...', 'Silence.')
```


Authority in one line: **reads are open** (except `password` and
`secret`-flagged attributes), **mutations require `controls()`**
(self, owned, delegated), **combat/effects use proximity** (same
room), `wait`/`force`/`start_combat` are queued and run after the
script.
