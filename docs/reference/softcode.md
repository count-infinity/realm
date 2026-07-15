# Softcode Reference

Auto-generated from the live API (`python scripts/gen_softcode_docs.py`
regenerates). Scripts are sandboxed Python: loops, comprehensions,
function defs — under time/call/output limits.

## Context names

| Name | Meaning |
|---|---|
| `me` / `executor` | the scripted object (scripts run AS it, with its owner's authority) |
| `enactor` | who triggered the script (`%#` in simple scripts) |
| `here` / `location` | where it happened |
| `viewer` | the looker (inline `[[...]]` blocks and @detail conditions) |
| `arg0..argN` / `%0..%9` | wildcard captures |
| `result` | what an inline `[[...]]` block substitutes |

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

### `ON_<EVENT>` lifecycle hooks

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
| `ON_DEATH` | this object dies |
| `ON_CAST` | an ability is directed at this object (resist via on_check) |
| `ON_LOAD` | this object was just spawned |
| `ON_EXPIRE` | this object's db.expires_at elapsed (then it's destroyed) |
| `ON_TICK` | periodic timer (on_tick behavior) |
| `ON_CONNECT` | player connects |
| `ON_DISCONNECT` | player disconnects |
| `ON_PAYMENT` | this object was paid |

## Functions

| Function | Signature | Notes | Example |
|---|---|---|---|
| `act` | `(target: 'GameObject \| str', message: 'str' = '', targeting: 'str' = 'remote', action_type: 'str' = 'event:act') -> 'bool'` | Fire a PROPAGATED action that can reach BEYOND your own room — |  |
| `add_tag` | `(obj: 'GameObject \| str \| None', tag: 'str') -> 'bool'` | Add a tag to an object the executor controls. | `add_tag(me, 'glowing')` |
| `adjust_credits` | `(obj: 'GameObject \| str \| None', delta: 'int') -> 'bool'` | Mint or burn money on an object the executor controls. | `adjust_credits(me, 100)` |
| `adjust_disposition` | `(npc, other, delta: 'int') -> 'bool'` | Shift an NPC's attitude. Authority: the executor must control | `adjust_disposition(me, enactor, 1)` |
| `ansi` | `(codes: 'str', text: 'str') -> 'str'` | Penn-style color: ansi('rh', 'My thing') — lowercase letters = | `ansi('rh', 'DANGER')` |
| `apply_effect` | `(obj: 'GameObject \| str \| None', effect_id: 'str', **params: 'Any') -> 'bool'` | Attach an effect (modifier_effect / damage_over_time / | `apply_effect(enactor, 'modifier_effect', kind='fear',` |
| `attach_behavior` | `(obj: 'GameObject \| str \| None', behavior_id: 'str', **params: 'Any') -> 'bool'` | Attach a registered behavior to an object the executor controls. | `attach_behavior('golem', 'script_ticker', interval=5)` |
| `band` | `(value: 'int', *thresholds: 'int', skill: 'str' = '') -> 'CheckResult'` | Tiered outcome (PbtA): tier = how many ascending thresholds |  |
| `behaviors` | `(obj: 'GameObject \| str \| None') -> 'list[str]'` | Behavior ids attached to an object. | `'wandering' in behaviors('rat')` |
| `cancel_wait` | `(wait_id: 'str \| None') -> 'bool'` | Cancel a pending wait by the handle ``wait()`` returned, before it | `cancel_wait(get_attr(me, 'fuse'))` |
| `capstr` | `(text: 'str') -> 'str'` | Capitalize each word. | `capstr('the iron king')   # 'The Iron King'` |
| `cast` | `(target: 'GameObject \| str \| None', ability: 'str' = '', *, tags: 'list[str] \| None' = None) -> 'bool'` | Direct an ability at a target — the ability analog of ``act``. Fires |  |
| `ceil` | `(value: 'float') -> 'int'` | Round up to integer. | `ceil(7.1)                 # 8` |
| `clamp` | `(value: 'int \| float', low: 'int \| float', high: 'int \| float') -> 'int \| float'` | Clamp value between low and high. | `clamp(damage, 1, 10)` |
| `clear_lock` | `(obj: 'GameObject \| str \| None', lock_type: 'str') -> 'bool'` | Clear a lock from an object the executor controls. | `clear_lock(me, 'basic')` |
| `contents` | `(obj: 'GameObject \| str \| None') -> 'list[GameObject]'` | Get an object's contents. | `[o for o in contents(here) if has_tag(o, 'npc')]` |
| `contest` | `(actor, actor_skill: 'str', opponent, opponent_skill: 'str') -> 'bool'` | Opposed quick contest; True if the actor wins. | `contest(enactor, 'fast_talk', me, 'detect_lies')` |
| `controls` | `(obj: 'GameObject \| str \| None') -> 'bool'` | Does the executor control this object? (The mutation gate.) | `controls('lever')` |
| `create_obj` | `(name: 'str', tags: 'list[str] \| None' = None, location: 'GameObject \| str \| None' = None) -> 'GameObject \| None'` | Create a new thing, owned by the executor's owner (or the | `sword = create_obj('iron sword')` |
| `credits` | `(obj: 'GameObject \| str \| None') -> 'int'` | An object's balance. | `credits(enactor) >= 10` |
| `damage` | `(obj: 'GameObject \| str \| None', amount: 'int') -> 'bool'` | Deal damage to something in the executor's room. Lethal damage | `damage(enactor, 3)` |
| `del_attr` | `(obj: 'GameObject \| str \| None', attr_name: 'str') -> 'bool'` | Delete an attribute from an object the executor controls. | `del_attr(me, 'charged')` |
| `destroy_obj` | `(obj: 'GameObject \| str \| None') -> 'bool'` | Destroy an object the executor controls (players never). | `destroy_obj('slag')` |
| `detach_behavior` | `(obj: 'GameObject \| str \| None', behavior_id: 'str') -> 'bool'` | Detach a behavior (by id) from an object the executor controls. | `detach_behavior('golem', 'wandering')` |
| `dice` | `(num: 'int' = 1, sides: 'int' = 6, modifier: 'int' = 0) -> 'int'` | Roll dice: NdS+M | `dice(3, 6)   # 3d6` |
| `disposition` | `(npc, other=None) -> 'int'` | How npc feels about other (default: the enactor). | `disposition(me, enactor) >= 2` |
| `enter_instance` | `(player: 'GameObject \| str \| None', template: 'str', *, mode: 'str' = 'solo', return_room: 'GameObject \| str \| None' = None, idle_ttl: 'float \| None' = None) -> 'bool'` | Send a player into a private, transient copy of a template area, |  |
| `enter_wilderness` | `(player: 'GameObject \| str \| None', region: 'str', x, y) -> 'bool'` | Send a player to the wilderness cell at ``(region, x, y)``, | `enter_wilderness(enactor, 'wilds', 10, 10)` |
| `escape` | `(text: 'str') -> 'str'` | Escape color markup in player-provided text (\|\| literals). | `say('They said: ' + escape(arg0))` |
| `eval_attr` | `(obj, attr_name: 'str', *args)` | Evaluate an attribute as a FUNCTION and return its ``result`` — | `eval_attr(me, 'render_side', n)` |
| `exits` | `(room: 'GameObject \| str \| None' = None) -> 'list[GameObject]'` | Open exits of a room (default: the executor's location). | `move(name(exits(here)[0]))` |
| `expire` | `(target: 'GameObject \| str \| None', seconds: 'float') -> 'bool'` | Give an object a lifetime: after ``seconds`` it fires ``ON_EXPIRE`` | `expire(create_obj('a wisp of smoke'), 30)` |
| `extract` | `(lst: 'list \| str', position: 'int', delimiter: 'str' = ' ') -> 'str'` | Get element at position (1-indexed). | `extract('a b c', 2)       # 'b'` |
| `first` | `(lst: 'list \| str', delimiter: 'str' = ' ') -> 'str'` | Get first element of list or first word of string. | `first('north south east') # 'north'` |
| `floor` | `(value: 'float') -> 'int'` | Round down to integer. | `floor(7.9)                # 7` |
| `force` | `(obj: 'GameObject \| str \| None', command: 'str') -> 'bool'` | Make something the executor controls run a command (queued; | `force('minion', 'say Yes, master.')` |
| `get` | `(spec: 'str') -> 'GameObject \| None'` | Get an object by ID or name. | `get('rusty key')  or  get('#3fa9...')` |
| `get_attr` | `(obj: 'GameObject \| str \| None', attr_name: 'str', default: 'Any' = None) -> 'Any'` | Get an attribute from an object. | `get_attr(enactor, 'hp', 0)` |
| `has_attr` | `(obj: 'GameObject \| str \| None', attr_name: 'str') -> 'bool'` | Check if an object has an attribute. | `has_attr(me, 'charged')` |
| `has_tag` | `(obj: 'GameObject \| str \| None', tag: 'str') -> 'bool'` | Check if an object has a tag. | `has_tag(enactor, 'player')` |
| `heal` | `(obj: 'GameObject \| str \| None', amount: 'int') -> 'bool'` | Restore HP (capped at max_hp) to something in the executor's room. | `heal(enactor, 5)` |
| `highest` | `(pool: 'int', *, sides: 'int' = 6, skill: 'str' = '') -> 'CheckResult'` | Highest-die tiers (Blades): 6 -> full (2), 4-5 -> partial (1), |  |
| `if_else` | `(condition: 'bool', true_val: 'Any', false_val: 'Any') -> 'Any'` | Conditional expression. | `if_else(credits(enactor) >= 10, 'Welcome!', 'No coin, no entry.')` |
| `last` | `(lst: 'list \| str', delimiter: 'str' = ' ') -> 'str'` | Get last element. | `last('north south east')  # 'east'` |
| `lcfirst` | `(text: 'str') -> 'str'` | Lowercase first character. | `lcfirst('Hello')          # 'hello'` |
| `left` | `(text: 'str', length: 'int') -> 'str'` | Get leftmost N characters. | `left('lighthouse', 5)     # 'light'` |
| `loc` | `(obj: 'GameObject \| str \| None') -> 'GameObject \| None'` | Get an object's location. | `loc(enactor)` |
| `margin_over` | `(rolled: 'int', target: 'int', *, skill: 'str' = '') -> 'CheckResult'` | Roll-over (D20): success if ``rolled >= target``; margin is how far |  |
| `margin_under` | `(rolled: 'int', target: 'int', *, skill: 'str' = '') -> 'CheckResult'` | Roll-under (GURPS, CoC): success if ``rolled <= target``; margin is |  |
| `member` | `(item: 'str', lst: 'list \| str', delimiter: 'str' = ' ') -> 'int'` | Find position of item in list (1-indexed, 0 if not found). | `member('south', 'north south east')  # 2` |
| `mid` | `(text: 'str', start: 'int', length: 'int') -> 'str'` | Extract substring (1-indexed like MUSH). | `mid('lighthouse', 5, 5)   # 'house'` |
| `move_to` | `(target: 'GameObject \| str \| None', destination: 'GameObject \| str \| None', *, tags: 'list[str] \| None' = None, force: 'bool' = False) -> 'bool'` | Relocate a player/object to a destination with the movement checks |  |
| `name` | `(obj: 'GameObject \| str \| None') -> 'str'` | Get an object's name. | `name(enactor)` |
| `net_successes` | `(pool: 'int', tn: 'int', *, sides: 'int' = 6, explode: 'bool' = True, skill: 'str' = '') -> 'CheckResult'` | Dice-pool success-counting (Shadowrun, WoD): roll ``pool`` dice, |  |
| `now` | `() -> 'int'` | Current time as epoch seconds — cache expiry, cooldowns. | `now() - get_attr(me, 'lit_at', 0) > 300` |
| `oemit` | `(exclude: 'GameObject \| str', message: 'str') -> 'None'` | Emit to the executor's room, excluding one object. | `oemit(enactor, 'Bob vanishes in smoke.')` |
| `oob` | `(target: 'GameObject \| str', package: 'str', data: 'dict') -> 'None'` | Send structured out-of-band data (GMCP) to a player's client — | `oob(enactor, 'Ship.Status', {'hull': 87})` |
| `owner` | `(obj: 'GameObject \| str \| None') -> 'GameObject \| None'` | Get an object's owner. | `owner(me) == enactor` |
| `pemit` | `(target: 'GameObject \| str', message: 'str') -> 'None'` | Send a private message to a target (delivered after the script). | `pemit(enactor, 'A voice only you can hear...')` |
| `prompt` | `(target, text: 'str', callback: 'str', persistent: 'bool' = False) -> 'bool'` | Ask a player a question; their next line runs the ``callback`` | `prompt(enactor, 'What is your name?', 'on_name')` |
| `rand` | `(low: 'int' = 0, high: 'int' = 100) -> 'int'` | Random integer between low and high (inclusive). | `rand(1, 100)` |
| `reaction_roll` | `(npc, other=None, modifier: 'int' = 0) -> 'int'` | Memoized first-impression roll (npc must be in executor's reach). | `reaction_roll(me)` |
| `remit` | `(room: 'GameObject \| str', message: 'str') -> 'None'` | Emit a message to everyone in a room (delivered after the script). | `remit(here, 'The ground trembles.')` |
| `remove_effect` | `(obj: 'GameObject \| str \| None', kind: 'str') -> 'bool'` | Strip an active effect by kind (cure poison, calm fear). | `remove_effect(enactor, 'fear')` |
| `remove_tag` | `(obj: 'GameObject \| str \| None', tag: 'str') -> 'bool'` | Remove a tag from an object the executor controls. | `remove_tag(me, 'hostile')` |
| `repeat` | `(text: 'str', count: 'int') -> 'str'` | Repeat text N times. | `repeat('-', 40)` |
| `replace` | `(text: 'str', old: 'str', new: 'str') -> 'str'` | Replace all occurrences of old with new. | `replace(arg0, 'gold', 'lead')` |
| `rest` | `(lst: 'list \| str', delimiter: 'str' = ' ') -> 'str \| list'` | Get all but first element. | `rest('north south east')  # 'south east'` |
| `right` | `(text: 'str', length: 'int') -> 'str'` | Get rightmost N characters. | `right('lighthouse', 5)    # 'house'` |
| `roll` | `(expr: 'str \| int') -> 'int'` | Roll a dice expression to a total. Supports ``NdS`` / ``dS``, Fudge |  |
| `search_world` | `(tag=None, attr=None, value=None, name=None, limit: 'int' = 100)` | Query the world: search_world(tag='zone:castle'), | `search_world(tag='zone:castle')` |
| `set_attr` | `(obj: 'GameObject \| str \| None', attr_name: 'str', value: 'Any') -> 'bool'` | Set an attribute on an object the executor controls. | `set_attr(me, 'visits', get_attr(me, 'visits', 0) + 1)` |
| `set_lock` | `(obj: 'GameObject \| str \| None', lock_type: 'str', expression: 'str') -> 'bool'` | Set a lock on an object the executor controls (validated). | `set_lock(me, 'basic', "caller.has_tag('keyholder')")` |
| `setdiff` | `(list1: 'str', list2: 'str', delimiter: 'str' = ' ') -> 'str'` | Difference of two lists (in list1 but not list2). | `setdiff('a b', 'b c')     # 'a'` |
| `setinter` | `(list1: 'str', list2: 'str', delimiter: 'str' = ' ') -> 'str'` | Intersection of two lists. | `setinter('a b', 'b c')    # 'b'` |
| `setunion` | `(list1: 'str', list2: 'str', delimiter: 'str' = ' ') -> 'str'` | Union of two space-separated lists. | `setunion('a b', 'b c')    # 'a b c'` |
| `skill_check` | `(obj, skill: 'str', modifier: 'int' = 0) -> 'bool'` | Roll a skill check for an object (name/#id or object). | `skill_check(enactor, 'stealth', -2)` |
| `start_combat` | `(attacker: 'GameObject \| str \| None', target: 'GameObject \| str \| None') -> 'bool'` | Throw an attacker the executor controls into combat with a | `start_combat('beast', enactor)` |
| `strlen` | `(text: 'str') -> 'int'` | Get string length. | `strlen(name(enactor))` |
| `switch` | `(value: 'Any', *cases: 'Any') -> 'Any'` | Switch statement. | `switch(tag_value(here, 'zone'), 'castle', 'Halt!',` |
| `tag_value` | `(obj, prefix: 'str')` | First value of a namespaced tag: tag_value(here, 'zone') | `tag_value(here, 'zone')   # -> 'castle'` |
| `tag_values` | `(obj, prefix: 'str') -> 'list'` | All values of a namespaced tag: tag_values(here, 'zone') | `tag_values(here, 'zone')  # -> ['castle', 'haunted']` |
| `tags` | `(obj: 'GameObject \| str \| None') -> 'list[str]'` | Get all tags on an object. | `'npc' in tags(enactor)` |
| `teleport_obj` | `(obj: 'GameObject \| str \| None', destination: 'GameObject \| str \| None') -> 'bool'` | Move an object the executor controls straight to a destination — the | `teleport_obj(enactor, 'The Oubliette')` |
| `test_lock` | `(obj: 'GameObject \| str \| None', lock_type: 'str', caller: 'GameObject \| str \| None' = None) -> 'bool'` | Would ``caller`` (default: the executor) pass this lock? | `test_lock('vault door', 'enter')` |
| `transfer_credits` | `(source: 'GameObject \| str \| None', dest: 'GameObject \| str \| None', amount: 'int') -> 'bool'` | Move money FROM something the executor controls. | `transfer_credits(me, enactor, 25)` |
| `trim` | `(text: 'str') -> 'str'` | Remove leading/trailing whitespace. | `trim('  hello  ')` |
| `ucfirst` | `(text: 'str') -> 'str'` | Capitalize first character. | `ucfirst('hello')          # 'Hello'` |
| `wait` | `(seconds: 'float', command: 'str') -> 'str \| None'` | Run a script command as the executor ~seconds from now (one-shot, |  |
| `words` | `(text: 'str', delimiter: 'str' = ' ') -> 'int'` | Count words/elements in text. | `words('a b c')            # 3` |
| `zone_rooms` | `(zone: 'str')` | Rooms tagged into a zone: zone_rooms('castle'). | `zone_rooms('castle')` |
| `zones_of` | `(obj)` | The zone names an object belongs to (no 'zone:' prefix). | `zones_of(here)` |

Authority in one line: **reads are open** (except `password` and
`secret`-flagged attributes), **mutations require `controls()`**
(self, owned, delegated), **combat/effects use proximity** (same
room), `wait`/`force`/`start_combat` are queued and run after the
script.
