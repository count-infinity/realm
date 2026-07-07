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
| `ON_<EVENT>` attr | propagated actions: ENTER, LEAVE, ARRIVE, LOOK, GET, DROP, GIVE, DEATH, PAYMENT... (zone masters hear member rooms) |
| `on_tick` attr | via the `script_ticker` behavior |

## Functions

| Function | Signature | Notes |
|---|---|---|
| `add_tag` | `(obj: 'GameObject \| str \| None', tag: 'str') -> 'bool'` | Add a tag to an object the executor controls. |
| `adjust_credits` | `(obj: 'GameObject \| str \| None', delta: 'int') -> 'bool'` | Mint or burn money on an object the executor controls. |
| `adjust_disposition` | `(npc, other, delta: 'int') -> 'bool'` | Shift an NPC's attitude. Authority: the executor must control |
| `ansi` | `(codes: 'str', text: 'str') -> 'str'` | Penn-style color: ansi('rh', 'My thing') — lowercase letters = |
| `apply_effect` | `(obj: 'GameObject \| str \| None', effect_id: 'str', **params: 'Any') -> 'bool'` | Attach an effect (modifier_effect / damage_over_time / |
| `attach_behavior` | `(obj: 'GameObject \| str \| None', behavior_id: 'str', **params: 'Any') -> 'bool'` | Attach a registered behavior to an object the executor controls. |
| `behaviors` | `(obj: 'GameObject \| str \| None') -> 'list[str]'` | Behavior ids attached to an object. |
| `capstr` | `(text: 'str') -> 'str'` | Capitalize each word. |
| `ceil` | `(value: 'float') -> 'int'` | Round up to integer. |
| `clamp` | `(value: 'int \| float', low: 'int \| float', high: 'int \| float') -> 'int \| float'` | Clamp value between low and high. |
| `clear_lock` | `(obj: 'GameObject \| str \| None', lock_type: 'str') -> 'bool'` | Clear a lock from an object the executor controls. |
| `contents` | `(obj: 'GameObject \| str \| None') -> 'list[GameObject]'` | Get an object's contents. |
| `contest` | `(actor, actor_skill: 'str', opponent, opponent_skill: 'str') -> 'bool'` | Opposed quick contest; True if the actor wins. |
| `controls` | `(obj: 'GameObject \| str \| None') -> 'bool'` | Does the executor control this object? (The mutation gate.) |
| `create_obj` | `(name: 'str', tags: 'list[str] \| None' = None, location: 'GameObject \| str \| None' = None) -> 'GameObject \| None'` | Create a new thing, owned by the executor's owner (or the |
| `credits` | `(obj: 'GameObject \| str \| None') -> 'int'` | An object's balance. |
| `damage` | `(obj: 'GameObject \| str \| None', amount: 'int') -> 'bool'` | Deal damage to something in the executor's room. Lethal damage |
| `del_attr` | `(obj: 'GameObject \| str \| None', attr_name: 'str') -> 'bool'` | Delete an attribute from an object the executor controls. |
| `destroy_obj` | `(obj: 'GameObject \| str \| None') -> 'bool'` | Destroy an object the executor controls (players never). |
| `detach_behavior` | `(obj: 'GameObject \| str \| None', behavior_id: 'str') -> 'bool'` | Detach a behavior (by id) from an object the executor controls. |
| `dice` | `(num: 'int' = 1, sides: 'int' = 6, modifier: 'int' = 0) -> 'int'` | Roll dice: NdS+M |
| `disposition` | `(npc, other=None) -> 'int'` | How npc feels about other (default: the enactor). |
| `escape` | `(text: 'str') -> 'str'` | Escape color markup in player-provided text (\|\| literals). |
| `exits` | `(room: 'GameObject \| str \| None' = None) -> 'list[GameObject]'` | Open exits of a room (default: the executor's location). |
| `extract` | `(lst: 'list \| str', position: 'int', delimiter: 'str' = ' ') -> 'str'` | Get element at position (1-indexed). |
| `first` | `(lst: 'list \| str', delimiter: 'str' = ' ') -> 'str'` | Get first element of list or first word of string. |
| `floor` | `(value: 'float') -> 'int'` | Round down to integer. |
| `force` | `(obj: 'GameObject \| str \| None', command: 'str') -> 'bool'` | Make something the executor controls run a command (queued; |
| `get` | `(spec: 'str') -> 'GameObject \| None'` | Get an object by ID or name. |
| `get_attr` | `(obj: 'GameObject \| str \| None', attr_name: 'str', default: 'Any' = None) -> 'Any'` | Get an attribute from an object. |
| `has_attr` | `(obj: 'GameObject \| str \| None', attr_name: 'str') -> 'bool'` | Check if an object has an attribute. |
| `has_tag` | `(obj: 'GameObject \| str \| None', tag: 'str') -> 'bool'` | Check if an object has a tag. |
| `heal` | `(obj: 'GameObject \| str \| None', amount: 'int') -> 'bool'` | Restore HP (capped at max_hp) to something in the executor's room. |
| `if_else` | `(condition: 'bool', true_val: 'Any', false_val: 'Any') -> 'Any'` | Conditional expression. |
| `last` | `(lst: 'list \| str', delimiter: 'str' = ' ') -> 'str'` | Get last element. |
| `lcfirst` | `(text: 'str') -> 'str'` | Lowercase first character. |
| `left` | `(text: 'str', length: 'int') -> 'str'` | Get leftmost N characters. |
| `loc` | `(obj: 'GameObject \| str \| None') -> 'GameObject \| None'` | Get an object's location. |
| `member` | `(item: 'str', lst: 'list \| str', delimiter: 'str' = ' ') -> 'int'` | Find position of item in list (1-indexed, 0 if not found). |
| `mid` | `(text: 'str', start: 'int', length: 'int') -> 'str'` | Extract substring (1-indexed like MUSH). |
| `name` | `(obj: 'GameObject \| str \| None') -> 'str'` | Get an object's name. |
| `now` | `() -> 'int'` | Current time as epoch seconds — cache expiry, cooldowns. |
| `oemit` | `(exclude: 'GameObject \| str', message: 'str') -> 'None'` | Emit to the executor's room, excluding one object. |
| `oob` | `(target: 'GameObject \| str', package: 'str', data: 'dict') -> 'None'` | Send structured out-of-band data (GMCP) to a player's client — |
| `owner` | `(obj: 'GameObject \| str \| None') -> 'GameObject \| None'` | Get an object's owner. |
| `pemit` | `(target: 'GameObject \| str', message: 'str') -> 'None'` | Send a private message to a target (delivered after the script). |
| `rand` | `(low: 'int' = 0, high: 'int' = 100) -> 'int'` | Random integer between low and high (inclusive). |
| `reaction_roll` | `(npc, other=None, modifier: 'int' = 0) -> 'int'` | Memoized first-impression roll (npc must be in executor's reach). |
| `remit` | `(room: 'GameObject \| str', message: 'str') -> 'None'` | Emit a message to everyone in a room (delivered after the script). |
| `remove_effect` | `(obj: 'GameObject \| str \| None', kind: 'str') -> 'bool'` | Strip an active effect by kind (cure poison, calm fear). |
| `remove_tag` | `(obj: 'GameObject \| str \| None', tag: 'str') -> 'bool'` | Remove a tag from an object the executor controls. |
| `repeat` | `(text: 'str', count: 'int') -> 'str'` | Repeat text N times. |
| `replace` | `(text: 'str', old: 'str', new: 'str') -> 'str'` | Replace all occurrences of old with new. |
| `rest` | `(lst: 'list \| str', delimiter: 'str' = ' ') -> 'str \| list'` | Get all but first element. |
| `right` | `(text: 'str', length: 'int') -> 'str'` | Get rightmost N characters. |
| `search_world` | `(tag=None, attr=None, value=None, name=None, limit: 'int' = 100)` | Query the world: search_world(tag='zone:castle'), |
| `set_attr` | `(obj: 'GameObject \| str \| None', attr_name: 'str', value: 'Any') -> 'bool'` | Set an attribute on an object the executor controls. |
| `set_lock` | `(obj: 'GameObject \| str \| None', lock_type: 'str', expression: 'str') -> 'bool'` | Set a lock on an object the executor controls (validated). |
| `setdiff` | `(list1: 'str', list2: 'str', delimiter: 'str' = ' ') -> 'str'` | Difference of two lists (in list1 but not list2). |
| `setinter` | `(list1: 'str', list2: 'str', delimiter: 'str' = ' ') -> 'str'` | Intersection of two lists. |
| `setunion` | `(list1: 'str', list2: 'str', delimiter: 'str' = ' ') -> 'str'` | Union of two space-separated lists. |
| `skill_check` | `(obj, skill: 'str', modifier: 'int' = 0) -> 'bool'` | Roll a skill check for an object (name/#id or object). |
| `start_combat` | `(attacker: 'GameObject \| str \| None', target: 'GameObject \| str \| None') -> 'bool'` | Throw an attacker the executor controls into combat with a |
| `strlen` | `(text: 'str') -> 'int'` | Get string length. |
| `switch` | `(value: 'Any', *cases: 'Any') -> 'Any'` | Switch statement. |
| `tag_value` | `(obj, prefix: 'str')` | First value of a namespaced tag: tag_value(here, 'zone') |
| `tag_values` | `(obj, prefix: 'str') -> 'list'` | All values of a namespaced tag: tag_values(here, 'zone') |
| `tags` | `(obj: 'GameObject \| str \| None') -> 'list[str]'` | Get all tags on an object. |
| `teleport_obj` | `(obj: 'GameObject \| str \| None', destination: 'GameObject \| str \| None') -> 'bool'` | Move an object the executor controls straight to a destination. |
| `test_lock` | `(obj: 'GameObject \| str \| None', lock_type: 'str', caller: 'GameObject \| str \| None' = None) -> 'bool'` | Would ``caller`` (default: the executor) pass this lock? |
| `transfer_credits` | `(source: 'GameObject \| str \| None', dest: 'GameObject \| str \| None', amount: 'int') -> 'bool'` | Move money FROM something the executor controls. |
| `trim` | `(text: 'str') -> 'str'` | Remove leading/trailing whitespace. |
| `ucfirst` | `(text: 'str') -> 'str'` | Capitalize first character. |
| `wait` | `(seconds: 'float', command: 'str') -> 'None'` | Run a script command as the executor ~seconds from now (one-shot, |
| `words` | `(text: 'str', delimiter: 'str' = ' ') -> 'int'` | Count words/elements in text. |
| `zone_rooms` | `(zone: 'str')` | Rooms tagged into a zone: zone_rooms('castle'). |
| `zones_of` | `(obj)` | The zone names an object belongs to (no 'zone:' prefix). |

Authority in one line: **reads are open** (except `password` and
`secret`-flagged attributes), **mutations require `controls()`**
(self, owned, delegated), **combat/effects use proximity** (same
room), `wait`/`force`/`start_combat` are queued and run after the
script.
