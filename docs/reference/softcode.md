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

## Context names

| Name | Meaning |
|---|---|
| `me` / `executor` | the scripted object (scripts run AS it, with its owner's authority) |
| `enactor` | who triggered the script (`%#` in simple scripts) |
| `here` / `location` | where it happened |
| `viewer` | the looker (inline `[[...]]` blocks and @detail conditions) |
| `arg0..argN` / `%0..%9` | wildcard captures |
| `result` | what an inline `[[...]]` block substitutes |

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

Payloads carried today (read with `adata`):

| Action | Keys |
|---|---|
| `event:payment` | `amount` |
| `item:on_get` / `on_drop` / `on_wield` / `on_unwield` | *(none — the item IS `target`)* |
| `item:on_give` | `item` (`target` is the recipient; the item also arrives as `tool`) |
| `item:on_put` | `item` (`target` is the container) |
| `event:on_receive` | `item`, `giver` |
| `event:on_leave` | `exit`, `direction`, `destination` |
| `event:on_fail` | `reason` (`'skill'`, `'closed'`, `'locked'`, …), `exit`, `direction`, `destination` |
| `event:on_enter` / `pre_enter` / `on_look` / `on_expire` / `on_reset` | *(none — the subject is `target`)* |
| `event:on_hitprcnt` | `percent`, `threshold` |
| `event:on_cast` | `ability`, `caster` |
| `event:connect` | `returning` |
| `combat:on_damage` | `damage`, `damage_types` |
| `combat:on_attack` | `weapon`, `attacker_hp`, `defender_hp` |
| `combat:on_death` | `killer` (a name; the killer *object* is `actor`), `fatal` |
| `event:speech` / `shout` / `ooc` / `emit` / `whisper` | `message` |
| `event:emote` / `semipose` | `pose` |

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

| Hook attr | Fires when |
|---|---|
| `ON_ENTER` | something enters this location |
| `ON_LEAVE` | something leaves this location |
| `ON_ARRIVE` | this object arrives somewhere new |
| `ON_FAIL` | a move was thwarted (dead-end/locked exit) — @afail |
| `ON_LOOK` | this object is looked at |
| `ON_USE` | this object is used |
| `ON_PUSH` | this object is pushed (button, lever) |
| `ON_GET` | this object is picked up |
| `ON_DROP` | this object is dropped |
| `ON_GIVE` | this object is given away |
| `ON_RECEIVE` | this object is given something (recipient side) |
| `ON_PUT` | this object is put in a container |
| `ON_WEAR` | this object is worn |
| `ON_REMOVE` | this object is taken off (gated: cursed gear can refuse) |
| `ON_WIELD` | this weapon is readied (gated) |
| `ON_UNWIELD` | this weapon is lowered (gated) |
| `ON_OPEN` | this door/container is opened |
| `ON_CLOSE` | this door/container is closed |
| `ON_LOCK` | this is locked (gated) |
| `ON_UNLOCK` | this is unlocked (gated: a sealed door can refuse) |
| `ON_ATTACK` | this object attacks or is attacked |
| `ON_DAMAGE` | this object takes damage |
| `ON_HITPRCNT` | HP fell through this object's db.hitprcnt threshold |
| `ON_DEATH` | this object goes down — any cause (a swing, poison, a trap, softcode damage). `adata('fatal')` is True for a real death (an NPC, now a corpse), False for a player knocked unconscious in place |
| `ON_CAST` | an ability is directed at this object (resist via on_check) |
| `ON_LOAD` | this object was just spawned |
| `ON_EXPIRE` | this object's db.expires_at elapsed (then it's destroyed) |
| `ON_RESET` | this zone master resets (empty + due) — repop, re-lock doors |
| `ON_TICK` | periodic timer (on_tick behavior) |
| `ON_CONNECT` | player connects |
| `ON_DISCONNECT` | player disconnects |
| `ON_PAYMENT` | this object was paid |

## Functions

Every function below is listed in the index, then documented in full
under its section. Each entry links to its own anchor, so you can point
a tutorial straight at one function (`reference/softcode.md#fn-pemit`).

### Index

| Function | What it does | Section |
|---|---|---|
| [`act`](#fn-act) | Fire a PROPAGATED action that can reach BEYOND your own room — unlike pemit/remit (which just deliver text), this runs the two-pass engine, so behaviors can veto or react at both ends. | [Firing your own events](#firing-your-own-events) |
| [`add_tag`](#fn-add_tag) | Add a tag to an object the executor controls. | [Tags & zones](#tags-zones) |
| [`adjust_credits`](#fn-adjust_credits) | Mint or burn money on an object the executor controls. | [Money](#money) |
| [`adjust_disposition`](#fn-adjust_disposition) | Shift an NPC's attitude. | [NPCs & behaviors](#npcs-behaviors) |
| [`ansi`](#fn-ansi) | Penn-style color: ansi('rh', 'My thing') — lowercase letters = foreground (r g y b m c w x), 'h' brightens it, UPPERCASE = background, u = underline, i = inverse video. | [Messaging & prompts](#messaging-prompts) |
| [`apply_effect`](#fn-apply_effect) | Attach an effect (modifier_effect / damage_over_time / regeneration / disposition_boost) to something in the executor's room. | [Combat & effects](#combat-effects) |
| [`attach_behavior`](#fn-attach_behavior) | Attach a registered behavior to an object the executor controls. | [NPCs & behaviors](#npcs-behaviors) |
| [`band`](#fn-band) | Tiered outcome (PbtA): tier = how many ascending thresholds `value` clears. | [Dice & skill checks](#dice-skill-checks) |
| [`behaviors`](#fn-behaviors) | Behavior ids attached to an object. | [NPCs & behaviors](#npcs-behaviors) |
| [`call`](#fn-call) | Call an attribute as a METHOD on `obj` — runs AS `obj` (`me` is obj, `V()`/`get_attr(me, ...)` read obj's own data, `here` is obj's room), with `enactor` preserved and args bound as arg0..argN. | [Objects & attributes](#objects-attributes) |
| [`cancel_wait`](#fn-cancel_wait) | Cancel a pending wait by the handle `wait()` returned, before it fires. | [Time & scheduling](#time-scheduling) |
| [`capstr`](#fn-capstr) | Capitalize each word. | [Text](#text) |
| [`cast`](#fn-cast) | Direct an ability at a target — the ability analog of `act`. | [Combat & effects](#combat-effects) |
| [`ceil`](#fn-ceil) | Round up to integer. | [Math & logic](#math-logic) |
| [`check_roll`](#fn-check_roll) | Roll a skill check and return the GRADED, condition-modified result. | [Dice & skill checks](#dice-skill-checks) |
| [`clamp`](#fn-clamp) | Clamp value between low and high. | [Math & logic](#math-logic) |
| [`clear_lock`](#fn-clear_lock) | Clear a lock from an object the executor controls. | [Locks & permissions](#locks-permissions) |
| [`contents`](#fn-contents) | Get an object's contents. | [Objects & attributes](#objects-attributes) |
| [`contest`](#fn-contest) | Opposed quick contest; True if the actor wins. | [Dice & skill checks](#dice-skill-checks) |
| [`controls`](#fn-controls) | Does the executor control this object? | [Objects & attributes](#objects-attributes) |
| [`create_obj`](#fn-create_obj) | Create a new thing, owned by the executor's owner (or the executor itself), at the executor's location by default. | [Objects & attributes](#objects-attributes) |
| [`credits`](#fn-credits) | An object's balance. | [Money](#money) |
| [`damage`](#fn-damage) | Deal damage to something in the executor's room. | [Combat & effects](#combat-effects) |
| [`decr`](#fn-decr) | Decrement a numeric attribute on `me` and return the new value. | [Objects & attributes](#objects-attributes) |
| [`del_attr`](#fn-del_attr) | Delete an attribute from an object the executor controls. | [Objects & attributes](#objects-attributes) |
| [`destroy_obj`](#fn-destroy_obj) | Destroy an object the executor controls (players never). | [Objects & attributes](#objects-attributes) |
| [`detach_behavior`](#fn-detach_behavior) | Detach a behavior (by id) from an object the executor controls. | [NPCs & behaviors](#npcs-behaviors) |
| [`dice`](#fn-dice) | Roll dice: NdS+M Args: num: Number of dice sides: Sides per die modifier: Added to total | [Dice & skill checks](#dice-skill-checks) |
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
| [`get`](#fn-get) | Get an object by ID, friendly keyid, or name. | [Objects & attributes](#objects-attributes) |
| [`get_attr`](#fn-get_attr) | Get an attribute from an object. | [Objects & attributes](#objects-attributes) |
| [`has_attr`](#fn-has_attr) | Check if an object has an attribute. | [Objects & attributes](#objects-attributes) |
| [`has_entitlement`](#fn-has_entitlement) | Whether an object holds a permission entitlement (read-only). | [Locks & permissions](#locks-permissions) |
| [`has_tag`](#fn-has_tag) | Check if an object has a tag. | [Tags & zones](#tags-zones) |
| [`heal`](#fn-heal) | Restore HP (capped at max_hp) to something in the executor's room. | [Combat & effects](#combat-effects) |
| [`highest`](#fn-highest) | Highest-die tiers (Blades): 6 -> full (2), 4-5 -> partial (1), else miss (0). | [Dice & skill checks](#dice-skill-checks) |
| [`if_else`](#fn-if_else) | Conditional expression. | [Math & logic](#math-logic) |
| [`incr`](#fn-incr) | Increment a numeric attribute on `me` and return the new value. | [Objects & attributes](#objects-attributes) |
| [`last`](#fn-last) | Get last element. | [Text](#text) |
| [`lcfirst`](#fn-lcfirst) | Lowercase first character. | [Text](#text) |
| [`left`](#fn-left) | Get leftmost N characters. | [Text](#text) |
| [`loc`](#fn-loc) | Get an object's location. | [Objects & attributes](#objects-attributes) |
| [`margin_over`](#fn-margin_over) | Roll-over (D20): success if `rolled >= target`; margin is how far over. | [Dice & skill checks](#dice-skill-checks) |
| [`margin_under`](#fn-margin_under) | Roll-under (GURPS, CoC): success if `rolled <= target`; margin is how far under. | [Dice & skill checks](#dice-skill-checks) |
| [`member`](#fn-member) | Find position of item in list (1-indexed, 0 if not found). | [Text](#text) |
| [`mid`](#fn-mid) | Extract substring (1-indexed like MUSH). | [Text](#text) |
| [`move_to`](#fn-move_to) | Relocate a player/object to a destination with the movement checks baked in — the one relocation verb. | [Movement & travel](#movement-travel) |
| [`name`](#fn-name) | Get an object's name. | [Objects & attributes](#objects-attributes) |
| [`net_successes`](#fn-net_successes) | Dice-pool success-counting (Shadowrun, WoD): roll `pool` dice, count those `>= tn`. | [Dice & skill checks](#dice-skill-checks) |
| [`now`](#fn-now) | Current time as epoch seconds — cache expiry, cooldowns. | [Time & scheduling](#time-scheduling) |
| [`oemit`](#fn-oemit) | Emit to the executor's room, excluding one object. | [Messaging & prompts](#messaging-prompts) |
| [`oob`](#fn-oob) | Send structured out-of-band data (GMCP) to a player's client — custom UI panels from softcode. | [Messaging & prompts](#messaging-prompts) |
| [`owner`](#fn-owner) | Get an object's owner. | [Objects & attributes](#objects-attributes) |
| [`pemit`](#fn-pemit) | Send a private message to a target (delivered after the script). | [Messaging & prompts](#messaging-prompts) |
| [`prompt`](#fn-prompt) | Ask a player a question; their next line runs the `callback` attribute (on the executor) with the answer as arg0 — a softcode wizard. | [Messaging & prompts](#messaging-prompts) |
| [`rand`](#fn-rand) | Random integer between low and high (inclusive). | [Dice & skill checks](#dice-skill-checks) |
| [`reaction_roll`](#fn-reaction_roll) | Memoized first-impression roll (npc must be in executor's reach). | [NPCs & behaviors](#npcs-behaviors) |
| [`remit`](#fn-remit) | Emit a message to everyone in a room (delivered after the script). | [Messaging & prompts](#messaging-prompts) |
| [`remove_effect`](#fn-remove_effect) | Strip an active effect by kind (cure poison, calm fear). | [Combat & effects](#combat-effects) |
| [`remove_tag`](#fn-remove_tag) | Remove a tag from an object the executor controls. | [Tags & zones](#tags-zones) |
| [`repeat`](#fn-repeat) | Repeat text N times. | [Text](#text) |
| [`replace`](#fn-replace) | Replace all occurrences of old with new. | [Text](#text) |
| [`rest`](#fn-rest) | Get all but first element. | [Text](#text) |
| [`right`](#fn-right) | Get rightmost N characters. | [Text](#text) |
| [`roll`](#fn-roll) | Roll a dice expression to a total. | [Dice & skill checks](#dice-skill-checks) |
| [`search_world`](#fn-search_world) | Query the world: search_world(tag='zone:castle'), search_world(attr='xp_multiplier'), combinable. | [Objects & attributes](#objects-attributes) |
| [`set_attr`](#fn-set_attr) | Set an attribute on an object the executor controls. | [Objects & attributes](#objects-attributes) |
| [`set_lock`](#fn-set_lock) | Set a lock on an object the executor controls (validated). | [Locks & permissions](#locks-permissions) |
| [`setdiff`](#fn-setdiff) | Difference of two lists (in list1 but not list2). | [Text](#text) |
| [`setinter`](#fn-setinter) | Intersection of two lists. | [Text](#text) |
| [`setunion`](#fn-setunion) | Union of two space-separated lists. | [Text](#text) |
| [`skill_check`](#fn-skill_check) | Roll a skill check for an object (name/#id or object). | [Dice & skill checks](#dice-skill-checks) |
| [`start_combat`](#fn-start_combat) | Throw an attacker the executor controls into combat with a target in the same room (queued; the encounter starts after the script finishes). | [Combat & effects](#combat-effects) |
| [`strlen`](#fn-strlen) | Get string length. | [Text](#text) |
| [`switch`](#fn-switch) | Switch statement. | [Math & logic](#math-logic) |
| [`tag_value`](#fn-tag_value) | First value of a namespaced tag: tag_value(here, 'zone') -> 'castle' (None if untagged). | [Tags & zones](#tags-zones) |
| [`tag_values`](#fn-tag_values) | All values of a namespaced tag: tag_values(here, 'zone') -> ['castle', 'haunted']. | [Tags & zones](#tags-zones) |
| [`tags`](#fn-tags) | Get all tags on an object. | [Tags & zones](#tags-zones) |
| [`teleport_obj`](#fn-teleport_obj) | Move an object the executor controls straight to a destination — the wizard/admin relocation. | [Objects & attributes](#objects-attributes) |
| [`test_lock`](#fn-test_lock) | Would `caller` (default: the executor) pass this lock? | [Locks & permissions](#locks-permissions) |
| [`transfer_credits`](#fn-transfer_credits) | Move money FROM something the executor controls. | [Money](#money) |
| [`trim`](#fn-trim) | Remove leading/trailing whitespace. | [Text](#text) |
| [`ucfirst`](#fn-ucfirst) | Capitalize first character. | [Text](#text) |
| [`V`](#fn-v) | Read an attribute off `me` (the executor) — the common case. | [Objects & attributes](#objects-attributes) |
| [`wait`](#fn-wait) | Run a script command as the executor exactly `seconds` from now (one-shot, its own timer — a 0.15s fuse fires at 0.15s, not quantized to the heartbeat; pending waits don't survive a reboot). | [Time & scheduling](#time-scheduling) |
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

Destroy an object the executor controls (players never).

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
sets; a game's own `role_def` ranks may grant them too.

**Example**

```text
has_entitlement(enactor, 'SEE_ALL')
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

Emit to the executor's room, excluding one object.

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

Send a private message to a target (delivered after the script).

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

**Example**

```text
remit(here, 'The ground trembles.')
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

### `skill_check` {#fn-skill_check}

```text
skill_check(obj, skill: str, modifier: int = 0) -> bool
```

Roll a skill check for an object (name/#id or object).

**Example**

```text
skill_check(enactor, 'stealth', -2)
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

This fires the ward/reaction pass; it does not itself gate your
script (side effects run after it). Use `contest()` for the resist
*roll*, and `cast()` for the ward + `ON_CAST` layer.

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
damage(obj: GameObject | str | None, amount: int) -> bool
```

Deal damage to something in the executor's room. Lethal damage
routes through the combat manager's death path (corpses, CP
awards, unconsciousness) after the script finishes.

**Example**

```text
damage(enactor, 3)
```

### `heal` {#fn-heal}

```text
heal(obj: GameObject | str | None, amount: int) -> bool
```

Restore HP (capped at max_hp) to something in the executor's room.

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

### `detach_behavior` {#fn-detach_behavior}

```text
detach_behavior(obj: GameObject | str | None, behavior_id: str) -> bool
```

Detach a behavior (by id) from an object the executor controls.

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

### `reaction_roll` {#fn-reaction_roll}

```text
reaction_roll(npc, other=None, modifier: int = 0) -> int
```

Memoized first-impression roll (npc must be in executor's reach).

**Example**

```text
reaction_roll(me)
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
act(target: GameObject | str, message: str = '', targeting: str = 'remote', action_type: str = 'event:act') -> bool
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

**Example**

```text
# scry — watch a distant room
act(thing, 'A scrying eye blinks open.', targeting='remote')

# a zone-wide alarm every room can react to with on_alert
act(intruder, 'Klaxons wail!', targeting='zone',
    action_type='event:alert')

# a custom local event: objects with an on_toll hook answer
act(me, 'A deep bell tolls.', targeting='room',
    action_type='event:toll')
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

### `now` {#fn-now}

```text
now() -> int
```

Current time as epoch seconds — cache expiry, cooldowns.

**Example**

```text
now() - get_attr(me, 'lit_at', 0) > 300
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
