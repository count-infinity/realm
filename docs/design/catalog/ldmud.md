# LDMud Command & Efun Surface Catalog (driver efuns + lp-245 mudlib commands)

| Codebase | Type | Group | Name | Scope | Description |
|----------|------|-------|------|-------|-------------|
| ldmud | Player | comm | say(msg) / '(msg) | any | Speak to everyone in the room |
| ldmud | Player | comm | tell(who,msg) | any | Send private message to a player |
| ldmud | Player | comm | whisper(who,msg) | any | Whisper privately to someone present |
| ldmud | Player | comm | shout(msg) | any | Broadcast message to whole mud |
| ldmud | Player | comm | converse | any | Enter continuous say/chat mode |
| ldmud | Player | comm | emote/pose(action) | any | Emote a freeform action |
| ldmud | Player | comm | feelings (smile,bow,hug,...) | any | ~65 soul social verbs |
| ldmud | Player | info | look(obj) | any | Look at room or object |
| ldmud | Player | info | examine/exa(obj) | any | Detailed inspect of an object |
| ldmud | Player | info | who | any | List players currently online |
| ldmud | Player | info | people | any | List players with locations (wiz) |
| ldmud | Player | info | score | any | Show own stats/hp/experience |
| ldmud | Player | info | help(topic) | any | Show help text for a topic |
| ldmud | Player | info | brief | any | Toggle brief room descriptions |
| ldmud | Player | inventory | inventory/i | any | List carried items |
| ldmud | Player | inventory | get/take(obj) | any | Pick up an object |
| ldmud | Player | inventory | drop(obj) | any | Drop a carried object |
| ldmud | Player | inventory | put(obj in cont) | any | Put object into a container |
| ldmud | Player | inventory | give(obj to who) | any | Give an object to someone |
| ldmud | Player | movement | home | any | Teleport to your workroom |
| ldmud | Player | movement | (exits: north,south,...) | any | Move via room exit verbs |
| ldmud | Player | system | quit | any | Save and disconnect |
| ldmud | Player | system | save | any | Save character to disk |
| ldmud | Player | system | password | any | Change your password |
| ldmud | Player | system | wimpy | any | Toggle auto-flee at low hp |
| ldmud | Player | system | stop | any | Stop hunting/combat pursuit |
| ldmud | Player | system | kill(who) | any | Attack a living target |
| ldmud | Player | system | email | any | Set your email address |
| ldmud | Player | system | idea/typo/bug(text) | any | File a report to wizards |
| ldmud | Builder | wizard | clone(path) | wizard | Clone an object into your inventory |
| ldmud | Builder | wizard | destruct(obj) | wizard | Destroy an object |
| ldmud | Builder | wizard | load(path) | wizard | Load/compile an object file |
| ldmud | OLC | wizard | update(obj) | wizard | Recompile/reload changed source |
| ldmud | Builder | movement | goto/teleport(dest) | wizard | Teleport to a room or player |
| ldmud | Builder | movement | in(room)(cmd) | wizard | Execute command in a remote room |
| ldmud | Builder | wizard | trans(who) | wizard | Transfer a player to you |
| ldmud | OLC | editing | ed(file) | wizard | Invoke line editor on a file |
| ldmud | Builder | wizard | ls(dir) | wizard | List directory contents |
| ldmud | Builder | wizard | cat(file) | wizard | Print a file to screen |
| ldmud | Builder | wizard | tail(file) | wizard | Show end of a file |
| ldmud | Builder | wizard | more(file) | wizard | Page through a file |
| ldmud | Builder | wizard | cd/pwd | wizard | Change/print working directory |
| ldmud | Builder | wizard | mkdir/rmdir(dir) | wizard | Create/remove a directory |
| ldmud | Builder | wizard | rm(file) | wizard | Delete a file |
| ldmud | Builder | wizard | echo/echoto/echoall(msg) | wizard | Echo text to room/player/all |
| ldmud | Admin | wizard | force(who,cmd) | wizard | Force a player to run a command |
| ldmud | Builder | wizard | heal(who) | wizard | Restore a living's hit points |
| ldmud | Builder | wizard | zap(who) | wizard | Damage/zap a target (test) |
| ldmud | Builder | wizard | stat(obj) | wizard | Show internal stats of object |
| ldmud | Admin | wizard | snoop(who) | wizard | Monitor a player's I/O |
| ldmud | Builder | wizard | invis/vis | wizard | Toggle wizard invisibility |
| ldmud | Builder | wizard | review | wizard | Review your movement messages |
| ldmud | Builder | wizard | title(text) | wizard | Set your player title |
| ldmud | Builder | wizard | setmin/setmout/setmmin/setmmout | wizard | Set enter/leave movement messages |
| ldmud | Builder | info | localcmd | wizard | List locally available commands |
| ldmud | Admin | info | wizlist | wizard | Show wizard ranking by work |
| ldmud | Admin | system | shutdown | wizard | Shut the game down |
| ldmud | Softcode-fn | object | clone_object(path) | any | Create a new clone of a blueprint |
| ldmud | Softcode-fn | object | load_object(path) | any | Load/return the blueprint object |
| ldmud | Softcode-fn | object | destruct(obj) | any | Destroy an object |
| ldmud | Softcode-fn | object | find_object(name) | any | Find loaded object by name |
| ldmud | Softcode-fn | object | blueprint(obj) | any | Get blueprint of a clone |
| ldmud | Softcode-fn | object | clones(path) | any | List clones of a blueprint |
| ldmud | Softcode-fn | object | clonep(obj) / objectp(x) | any | Test if clone / is object |
| ldmud | Softcode-fn | object | objects() | any | Iterate over all objects |
| ldmud | Softcode-fn | object | object_name(obj) | any | Get object's full name |
| ldmud | Softcode-fn | object | load_name(obj) | any | Get blueprint load name |
| ldmud | Softcode-fn | object | program_name(obj) | any | Get program file name |
| ldmud | Softcode-fn | object | object_info(obj,flag) | any | Query object internals |
| ldmud | Softcode-fn | object | this_object() | any | The object running this code |
| ldmud | Softcode-fn | object | previous_object() | any | Object that called current fn |
| ldmud | Softcode-fn | object | set_this_object(obj) | driver | Fake this_object (privileged) |
| ldmud | Softcode-fn | object | replace_program(str) | any | Swap running program in place |
| ldmud | Softcode-fn | object | save_object/restore_object | any | Persist/reload object vars to file |
| ldmud | Softcode-fn | object | save_value/restore_value | any | Serialize a value to/from string |
| ldmud | Softcode-fn | object | deep_copy/copy(x) | any | Deep or shallow value copy |
| ldmud | Softcode-fn | movement | move_object(obj,dest) | any | Move object into destination |
| ldmud | Softcode-fn | movement | environment(obj) | any | Object containing given object |
| ldmud | Softcode-fn | movement | present(id,env) | any | Find object by id in environment |
| ldmud | Softcode-fn | movement | present_clone(path,env) | any | Find a clone of blueprint in env |
| ldmud | Softcode-fn | movement | first_inventory(obj) | any | First item inside an object |
| ldmud | Softcode-fn | movement | next_inventory(obj) | any | Next sibling in inventory |
| ldmud | Softcode-fn | movement | all_inventory(obj) | any | Array of contained objects |
| ldmud | Softcode-fn | movement | deep_inventory(obj) | any | Recursive contents array |
| ldmud | Softcode-fn | movement | all_environment(obj) | any | Chain of enclosing environments |
| ldmud | Softcode-fn | movement | set_environment(obj,env) | driver | Force object's environment |
| ldmud | Softcode-fn | movement | transfer(obj,dest) | any | Legacy guarded move |
| ldmud | Softcode-fn | living | this_player() | any | Current interactive command giver |
| ldmud | Softcode-fn | living | this_interactive() | any | The interactive that triggered call |
| ldmud | Softcode-fn | living | set_this_player(obj) | driver | Set command giver (privileged) |
| ldmud | Softcode-fn | living | set_living_name(name) | any | Register a living's find name (sefun) |
| ldmud | Softcode-fn | living | find_living/find_player(name) | any | Locate a living/player by name |
| ldmud | Softcode-fn | living | set_heart_beat(flag) | any | Enable/disable heart_beat() calls |
| ldmud | Softcode-fn | living | users() | any | Array of interactive players |
| ldmud | Softcode-fn | living | query_idle(obj) | any | Idle time of interactive |
| ldmud | Softcode-fn | living | interactive_info(obj,f) | any | Query connection details |
| ldmud | Softcode-fn | living | snoop(a,b) | wizard | Set/clear snoop on interactive |
| ldmud | Softcode-fn | living | exec(new,old) | driver | Move connection between objects |
| ldmud | Softcode-fn | living | remove_interactive(obj) | wizard | Disconnect an interactive |
| ldmud | Softcode-fn | living | net_connect(host,port) | driver | Open outgoing TCP connection |
| ldmud | Softcode-fn | comm | write(msg) | any | Write text to this_player |
| ldmud | Softcode-fn | comm | tell_object(obj,msg) | any | Send text to a specific object |
| ldmud | Softcode-fn | comm | tell_room(room,msg,excl) | any | Send text to all in a room |
| ldmud | Softcode-fn | comm | say(msg,excl) | any | Emit to room except source |
| ldmud | Softcode-fn | comm | printf/sprintf(fmt,...) | any | Formatted output / string |
| ldmud | Softcode-fn | comm | terminal_colour(str,map) | any | Expand %^COLOR^% color codes |
| ldmud | Softcode-fn | comm | binary_message(bytes) | any | Send raw bytes to connection |
| ldmud | Softcode-fn | comm | send_udp(host,port,msg) | any | Send a UDP datagram |
| ldmud | Softcode-fn | comm | input_to(fn) | any | Capture player's next input line |
| ldmud | Softcode-fn | comm | add_action(fn,verb) | any | Bind a command verb to a function |
| ldmud | Softcode-fn | comm | remove_action(verb) | any | Unbind a command verb |
| ldmud | Softcode-fn | comm | query_actions(obj) | any | List actions available on object |
| ldmud | Softcode-fn | comm | query_verb() | any | Verb that triggered the action |
| ldmud | Softcode-fn | comm | notify_fail(msg) | any | Set failure message for command |
| ldmud | Softcode-fn | comm | command(str) / execute_command | any | Run a command as this object |
| ldmud | Softcode-fn | comm | enable_commands() | any | Make object able to run commands |
| ldmud | Softcode-fn | call | call_other(obj,fn,args) | any | Call a function in another object |
| ldmud | Softcode-fn | call | funcall(cl,args) / apply(cl,arr) | any | Invoke a closure with args |
| ldmud | Softcode-fn | call | call_resolved/call_direct | any | Explicit-resolution calls |
| ldmud | Softcode-fn | call | bind_lambda / unbound_lambda | any | Build/bind lambda closures |
| ldmud | Softcode-fn | call | symbol_function/symbol_variable | any | Make closures for fn/var symbols |
| ldmud | Softcode-fn | call | function_exists/functionlist | any | Introspect object functions |
| ldmud | Softcode-fn | call | variable_exists/variable_list | any | Introspect object variables |
| ldmud | Softcode-fn | call | compile_string(src) | wizard | Compile LPC source at runtime |
| ldmud | Softcode-fn | call | caller_stack / command_stack | any | Inspect call/command stacks |
| ldmud | Softcode-fn | call | closurep/typeof/lpctypep | any | Type predicates |
| ldmud | Softcode-fn | scheduling | call_out(fn,delay,args) | any | Schedule a delayed call |
| ldmud | Softcode-fn | scheduling | remove_call_out(fn) | any | Cancel a scheduled call |
| ldmud | Softcode-fn | scheduling | call_out_info() | any | List pending call_outs |
| ldmud | Softcode-fn | scheduling | find_call_out(fn) | any | Time remaining for a call_out |
| ldmud | Softcode-fn | scheduling | set_next_reset(delay) | any | Schedule object's next reset() |
| ldmud | Softcode-fn | string | explode(str,sep) | any | Split string into array |
| ldmud | Softcode-fn | string | sscanf(str,fmt,vars) | any | Parse fields from a string |
| ldmud | Softcode-fn | string | lower_case/upper_case/capitalize | any | Case conversion helpers |
| ldmud | Softcode-fn | string | strstr/strrstr(a,b) | any | Substring search |
| ldmud | Softcode-fn | string | trim(str) / text_width(str) | any | Trim whitespace / measure width |
| ldmud | Softcode-fn | string | regexp/regreplace/regmatch | any | Regex match and replace |
| ldmud | Softcode-fn | string | regexplode(str,pat) | any | Split by regex |
| ldmud | Softcode-fn | string | process_string(str) | any | Expand embedded value refs |
| ldmud | Softcode-fn | string | make_shared_string(str) | any | Intern a shared string |
| ldmud | Softcode-fn | string | md5/sha1/crypt(str) | any | Hashing and password crypt |
| ldmud | Softcode-fn | array | allocate(size) | any | Create a new array |
| ldmud | Softcode-fn | array | sizeof(x) | any | Element count of array/mapping |
| ldmud | Softcode-fn | array | member/rmember(arr,val) | any | Find index of a value |
| ldmud | Softcode-fn | array | filter(arr,cl) / map(arr,cl) | any | Filter/transform elements |
| ldmud | Softcode-fn | array | filter_objects/map_objects | any | Filter/map by calling a method |
| ldmud | Softcode-fn | array | sort_array(arr,cl) | any | Sort with comparator closure |
| ldmud | Softcode-fn | array | unique_array(arr,cl) | any | Group by discriminator |
| ldmud | Softcode-fn | array | reverse(arr) / transpose_array | any | Reverse / transpose arrays |
| ldmud | Softcode-fn | array | to_array(x) / quote / unquote | any | Convert to array / (un)quote |
| ldmud | Softcode-fn | mapping | mkmapping(keys,vals) | any | Build a mapping |
| ldmud | Softcode-fn | mapping | m_indices/m_values(map) | any | Keys / values of a mapping |
| ldmud | Softcode-fn | mapping | m_contains(map,key) | any | Test/fetch a mapping entry |
| ldmud | Softcode-fn | mapping | m_delete(map,key) | any | Remove a mapping entry |
| ldmud | Softcode-fn | mapping | m_add(map,key,vals) / m_entry | any | Add/fetch a widened entry |
| ldmud | Softcode-fn | mapping | m_allocate/m_reallocate | any | Allocate/reshape mappings |
| ldmud | Softcode-fn | mapping | widthof(map) | any | Value-width of a mapping |
| ldmud | Softcode-fn | mapping | walk_mapping(map,cl) | any | Iterate a mapping with closure |
| ldmud | Softcode-fn | mapping | map_indices/filter_indices | any | Map/filter by keys |
| ldmud | Softcode-fn | mapping | unmkmapping(map) | any | Split mapping into arrays |
| ldmud | Softcode-fn | system | time() / utime() | any | Unix time (sec / micro) |
| ldmud | Softcode-fn | system | ctime/localtime/mktime/strftime | any | Time formatting/parsing |
| ldmud | Softcode-fn | system | random(n) | any | Random integer 0..n-1 |
| ldmud | Softcode-fn | system | rusage() | any | Driver resource usage stats |
| ldmud | Softcode-fn | system | debug_message(str) | any | Write to driver debug log |
| ldmud | Softcode-fn | system | garbage_collection() | wizard | Force a GC sweep |
| ldmud | Softcode-fn | system | driver_info/dump_driver_info | any | Query/dump driver internals |
| ldmud | Softcode-fn | system | configure_driver/configure_object | wizard | Runtime driver/object settings |
| ldmud | Softcode-fn | system | get_eval_cost() | any | Remaining evaluation ticks |
| ldmud | Softcode-fn | system | master() / efun / extern_call | any | Master object / call context |
| ldmud | Softcode-fn | system | throw/catch/raise_error | any | Exception raise and handling |
| ldmud | Softcode-fn | system | shutdown() | wizard | Terminate the driver |
| ldmud | Softcode-fn | math | abs/sgn/min/max | any | Basic numeric helpers |
| ldmud | Softcode-fn | math | sin/cos/tan/asin/acos/atan | any | Trigonometric functions |
| ldmud | Softcode-fn | math | sqrt/pow/exp/log/floor/ceil | any | Float math functions |
| ldmud | Softcode-fn | math | to_int/to_float/to_string/to_object | any | Type conversions |
| ldmud | Softcode-fn | parse | parse_command(str,env,pat) | any | NL command pattern matcher |
| ldmud | Softcode-fn | parse | match_command(str,obj) | any | Match a command against actions |
| ldmud | Softcode-fn | files | read_file/write_file(path) | any | Read/write text files |
| ldmud | Softcode-fn | files | read_bytes/write_bytes | any | Binary file I/O |
| ldmud | Softcode-fn | files | get_dir(path) / file_size | any | List directory / file size |
| ldmud | Softcode-fn | files | mkdir/rmdir/rm(path) | any | Directory and file management |
| ldmud | Softcode-fn | files | rename/copy_file(a,b) | any | Rename or copy a file |
| ldmud | Softcode-fn | files | ed(file,fn) | any | Invoke the built-in line editor |
| ldmud | Softcode-fn | security | geteuid(obj)/getuid(obj) | any | Effective / real uid of object |
| ldmud | Softcode-fn | security | creator(obj) | any | Creator (owner) of an object |
| ldmud | Softcode-fn | security | get_extra_wizinfo/set_extra_wizinfo | wizard | Per-wizard extra data slot |
| ldmud | Softcode-fn | security | wizlist_info() | wizard | Full wizard accounting table |
| ldmud | Softcode-fn | security | export_uid(obj) | driver | Propagate uid to another object |
| ldmud | Softcode-fn | security | shadow/unshadow(obj) | any | Attach/detach a shadow object |
| ldmud | Softcode-fn | system | db_connect/db_exec/db_fetch | wizard | MySQL database access (pkg) |
| ldmud | Softcode-fn | system | sl_open/sl_exec/sl_close | wizard | SQLite database access (pkg) |
| ldmud | Softcode-fn | system | pg_connect/pg_query/pg_close | wizard | PostgreSQL access (pkg) |
| ldmud | Softcode-fn | system | tls_init_connection/tls_query_* | wizard | TLS/SSL connection control (pkg) |
| ldmud | Softcode-fn | system | xml_parse/xml_generate | any | XML (de)serialization (pkg) |
| ldmud | Softcode-fn | scheduling | this_coroutine/call_coroutine | any | Coroutine control (LDMud 3.6) |
