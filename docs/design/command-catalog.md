# Consolidated Command & Function Catalog — 14 MU* Codebases

One table of the **player- and builder-facing command & softcode-function surface** of every reference codebase, extracted from source by per-codebase agents against a uniform schema, so REALM's surface can be diffed against the field. **2072 rows across 14 codebases.** Per-codebase source tables live in [`catalog/`](catalog/).

**Schema:** `Codebase | Type | Group | Name | Scope | Description`. `Type` ∈ {OLC, Builder, Player, Softcode-fn, Admin}; `Scope` = who/what may use it. Filter `Type = Softcode-fn` to see the *function* surface (the PennMUSH-`@function` analog). Trivial arithmetic/string/social families were grouped into representative rows; see each source file's caveats. For the *analysis* of what REALM should adopt, see [reference-synthesis.md](reference-synthesis.md) — this doc is the raw data.

## Per-codebase summary

| Codebase | Lineage | Rows | Softcode-fns | Scripting / distinctive surface |
|---|---|--:|--:|---|
| realm | REALM (baseline) | 182 | 88 | **baseline** — 94 cmds + 88 softcode fns; $-cmds/^listen/ON_<EVENT> |
| pennmush | MUSH | 218 | 134 | MUSHcode: u/iter/switch/lattr/sql/json/vectors; @force/@dolist/@function |
| tinymux | MUSH | 155 | 83 | MUSHcode + MUX-distinct route()/sandbox()/lua()/@program/@cron/@hook |
| aresmush | modern Ruby MUSH | 153 | 0 | **no softcode** — Ruby plugin handlers; builds via plain commands |
| evennia | Python | 101 | 22 | FuncParser $func (3 registries) + @py; default cmdsets |
| coffeemud | Java/Diku-OO | 115 | 32 | Scriptable/MOBprog: 61 triggers, 101 MP* cmds, 119 conditions; CREATE/MODIFY/DESTROY |
| smaug | Diku/SMAUG | 184 | 44 | MOBprograms (do_mp*, $-codes, ifchecks); redit + mset/oset/aset |
| tbamud | CircleMUD/DG | 169 | 82 | **DG Scripts** — richest Diku: mob/obj/wld cmds + %actor.field% + OLC |
| awakemud | Shadowrun/Circle | 158 | 0 | 4 modal interpreter tables (matrix/rig/hitcher); Shadowrun magic/decking/rigging |
| dikumud3 | DIL | 141 | 84 | **DIL** — a real embedded scripting language (statements + builtins) |
| swr | SMAUG/space | 63 | 0 | space/ship (cockpit-room gated); land/launch/board/dock |
| swfote | SMAUG/Force | 91 | 0 | Force powers (data-file dispatch) + empire/clans/senate |
| ldmud | LPMud/LPC | 196 | 139 | LPC **efuns** (305 documented) + wizard cmds; no OLC (ed + clone) |
| gomud | modern Go | 146 | 51 | **goja JavaScript** + event handlers (onCommand/onEnter/onIdle/onDie/onCast) |
| **TOTAL** | | **2072** | | |

## The consolidated table

| Codebase | Type | Group | Name | Scope | Description |
|---|---|---|---|---|---|
| realm | Player | perception | look (l) | any | Look at surroundings or an object |
| realm | Player | perception | examine (ex/exam) | any | Examine an object in detail |
| realm | Player | perception | search | any | Search room/container for hidden things |
| realm | Player | movement | go <dir> | any | Move in a direction |
| realm | Player | movement | <direction> (n/s/e/w/u/d...) | any | Directional movement shortcuts |
| realm | Player | movement | in / out | any | Enter or exit |
| realm | Player | movement | recall | any | Return to your home |
| realm | Player | object | inventory (i/inv) | any | Show your inventory and money balance |
| realm | Player | object | get (take/grab) | any | Pick up an object (get all) |
| realm | Player | object | drop | any | Drop an object (drop all) |
| realm | Player | object | give <x>=<who> | any | Give an object to someone |
| realm | Player | object | put (place) <x> in <c> | any | Put an object in a container |
| realm | Player | object | open / close | any | Open or close door/container |
| realm | Player | object | lock / unlock | any | Lock/unlock with carried key |
| realm | Player | object | pick | any | Pick a lock (skill) |
| realm | Player | object | use | any | Use/activate an item |
| realm | Player | object | wear / remove (unwear) | any | Wear or take off gear |
| realm | Player | object | hide | any | Conceal yourself |
| realm | Player | comm | say (') | any | Say something to the room |
| realm | Player | comm | pose (emote) | any | Emote an action |
| realm | Player | comm | semipose (;) | any | Emote with name attached (no space) |
| realm | Player | comm | emit (\\) | builder | Emit a raw message to the room |
| realm | Player | comm | whisper (w) <who>=<msg> | any | Whisper privately to someone |
| realm | Player | comm | ooc | any | Out-of-character speech |
| realm | Player | comm | shout | any | Shout to room and nearby |
| realm | Player | comm | think | any | Think to yourself |
| realm | Player | social | consider (con) | any | Size up an NPC's attitude (reaction) |
| realm | Player | social | persuade | any | Win someone over (persuasion vs will) |
| realm | Player | social | fasttalk (fast-talk) | any | Bend truth for temp goodwill |
| realm | Player | social | follow | any | Walk exits after someone |
| realm | Player | social | unfollow | any | Stop following |
| realm | Player | social | party (group) | any | Show who travels with you |
| realm | Player | combat | attack (kill/att) | any | Attack a target, start combat |
| realm | Player | combat | queue (q) | any | Queue a combat maneuver |
| realm | Player | combat | defend | any | Shortcut: defensive stance |
| realm | Player | combat | flee | any | Flee from combat |
| realm | Player | combat | combat (cstat) | any | Show combat status |
| realm | Player | combat | pace | any | Set combat pacing |
| realm | Player | combat | combatdefault | any | Set default maneuver |
| realm | Player | combat | wimpy | any | Auto-flee HP threshold |
| realm | Player | combat | firstaid (aid) | any | Heal wounds (first aid skill) |
| realm | Player | combat | points (cp/score) | any | Show character points/score |
| realm | Player | combat | wield (ready/draw) | any | Wield a weapon |
| realm | Player | combat | unwield (lower/sheathe) | any | Put weapon away |
| realm | Player | combat | improve | any | Spend points to improve skills |
| realm | Player | economy | credits (money/balance) | any | Show your balance |
| realm | Player | economy | list (wares) | any | See what merchant here sells |
| realm | Player | economy | buy (purchase) | any | Buy from merchant here |
| realm | Player | economy | sell | any | Sell to merchant here |
| realm | Player | economy | pay <who>=<amt> | any | Pay someone (fires ON_PAYMENT) |
| realm | Player | info | who | any | Show who is online |
| realm | Player | info | help (?) | any | Show help on commands |
| realm | Player | info | commands | any | List all available commands |
| realm | Player | info | time | any | Show current time |
| realm | Player | info | uptime | any | Show server uptime |
| realm | Player | info | color | any | Toggle color output |
| realm | Player | info | quit (QUIT) | any | Disconnect from the game |
| realm | Player | info | logout | any | Leave your character; back to the connection screen (connection stays open) |
| realm | Player | admin | quell / unquell | any | Drop to / restore full authority |
| realm | OLC | building | @create | builder | Create a new object |
| realm | OLC | building | @dig <room>=<exits> | builder | Create a room with exits |
| realm | OLC | building | @open <exit>=<room> | builder | Create an exit to a room |
| realm | OLC | building | @link <exit>=<dest> | builder | Link an exit to a destination |
| realm | OLC | building | @unlink | builder | Unlink an exit |
| realm | OLC | building | @desc (@describe) | controls target | Set an object's description |
| realm | OLC | building | @name | controls target | Rename an object |
| realm | OLC | building | @detail | controls target | Add per-viewer conditional desc line |
| realm | OLC | object | @set <obj>/<attr>=<val> | controls target | Set an attribute on an object |
| realm | OLC | object | @attr | controls target | Flag attrs: secret/visual/safe/no_clone |
| realm | OLC | object | @wipe | controls target | Clear all attributes from an object |
| realm | OLC | object | @parent | controls target | Set an object's parent |
| realm | OLC | object | @tag / @untag | controls target | Add/remove a tag on an object |
| realm | OLC | object | @lock <obj>=<type>:<expr> | controls target | Set a lock on an object |
| realm | OLC | object | @unlock | controls target | Remove all locks from an object |
| realm | OLC | scripting | @behavior (@behaviors) | controls target | Attach/detach/list behaviors |
| realm | OLC | object | @clone | controls target | Duplicate object (attrs/tags/behaviors) |
| realm | OLC | scripting | @trigger (@trigger) | controls target | Run script stored in an attribute |
| realm | OLC | building | @zone | builder | Manage zone membership/masters/rooms |
| realm | Builder | building | @areas | builder | List importable area files |
| realm | Builder | building | @pack | builder | List/import built-in content packs |
| realm | Builder | building | @export | builder | Export a zone to an area file |
| realm | Builder | building | @import | builder | Import an area (plan; /apply) |
| realm | Builder | movement | @teleport (@tel) | builder | Teleport to a location |
| realm | Builder | perception | @examine (@ex) | builder | Show detailed object info |
| realm | Builder | admin | @find (@search) | builder | Search for objects |
| realm | Admin | admin | @chown | admin | Change ownership of an object |
| realm | Admin | admin | @destroy (@recycle) | admin | Destroy an object |
| realm | Admin | admin | @nuke | admin | Destroy a player object |
| realm | Admin | admin | @force <obj>=<cmd> | controls target | Force object to run a command |
| realm | Admin | admin | @boot | admin | Disconnect a player |
| realm | Admin | scripting | @eval (@ev) | admin | Run arbitrary softcode, report result |
| realm | Admin | admin | @foreach | admin | Run a command per matching object (%o) |
| realm | Admin | admin | @reload | admin | Re-read data-driven rules from world |
| realm | Admin | admin | @stats (@metrics) | admin | Live engine metrics |
| realm | Admin | admin | @rolls | admin | Toggle skill-roll visibility for self |
| realm | Softcode-fn | perception | act(target,msg,targeting,type) | any | Fire propagated action beyond own room |
| realm | Softcode-fn | scripting | add_tag(obj,tag) | controls target | Add a tag to a controlled object |
| realm | Softcode-fn | economy | adjust_credits(obj,delta) | controls target | Mint/burn money on controlled object |
| realm | Softcode-fn | social | adjust_disposition(npc,other,delta) | controls target | Shift an NPC's attitude |
| realm | Softcode-fn | scripting | ansi(codes,text) | any | Penn-style color markup |
| realm | Softcode-fn | combat | apply_effect(obj,effect_id,**p) | proximity | Attach effect (modifier/dot/etc) |
| realm | Softcode-fn | scripting | attach_behavior(obj,id,**p) | controls target | Attach a registered behavior |
| realm | Softcode-fn | dice | band(value,*thresholds,skill) | any | Tiered PbtA outcome by thresholds |
| realm | Softcode-fn | scripting | behaviors(obj) | any | List behavior ids on an object |
| realm | Softcode-fn | scripting | capstr(text) | any | Capitalize each word |
| realm | Softcode-fn | dice | ceil(value) | any | Round up to integer |
| realm | Softcode-fn | dice | clamp(value,low,high) | any | Clamp value between bounds |
| realm | Softcode-fn | scripting | clear_lock(obj,type) | controls target | Clear a lock from an object |
| realm | Softcode-fn | perception | contents(obj) | any | Get an object's contents |
| realm | Softcode-fn | dice | contest(a,askill,b,bskill) | any | Opposed quick contest; actor wins? |
| realm | Softcode-fn | scripting | controls(obj) | any | Does executor control this object? |
| realm | Softcode-fn | object | create_obj(name,tags,location) | any | Create a new thing (executor-owned) |
| realm | Softcode-fn | economy | credits(obj) | any | An object's balance |
| realm | Softcode-fn | combat | damage(obj,amount) | proximity | Deal damage to something in room |
| realm | Softcode-fn | scripting | del_attr(obj,attr) | controls target | Delete an attribute |
| realm | Softcode-fn | object | destroy_obj(obj) | controls target | Destroy a controlled object |
| realm | Softcode-fn | scripting | detach_behavior(obj,id) | controls target | Detach a behavior by id |
| realm | Softcode-fn | dice | dice(num,sides,mod) | any | Roll NdS+M |
| realm | Softcode-fn | social | disposition(npc,other) | any | How npc feels about other |
| realm | Softcode-fn | movement | enter_instance(player,template,...) | any | Send player into transient area copy |
| realm | Softcode-fn | scripting | escape(text) | any | Escape color markup in player text |
| realm | Softcode-fn | scripting | eval_attr(obj,attr,*args) | any | Evaluate attribute as a function |
| realm | Softcode-fn | perception | exits(room) | any | Open exits of a room |
| realm | Softcode-fn | scripting | extract(lst,pos,delim) | any | Get element at 1-indexed position |
| realm | Softcode-fn | scripting | first(lst,delim) | any | First element/word |
| realm | Softcode-fn | dice | floor(value) | any | Round down to integer |
| realm | Softcode-fn | scripting | force(obj,command) | controls target | Make controlled obj run a command |
| realm | Softcode-fn | perception | get(spec) | any | Get an object by id or name |
| realm | Softcode-fn | scripting | get_attr(obj,attr,default) | any | Get an attribute (reads open) |
| realm | Softcode-fn | scripting | has_attr(obj,attr) | any | Check if object has attribute |
| realm | Softcode-fn | scripting | has_tag(obj,tag) | any | Check if object has tag |
| realm | Softcode-fn | combat | heal(obj,amount) | proximity | Restore HP to something in room |
| realm | Softcode-fn | dice | highest(pool,sides,skill) | any | Highest-die tiers (Blades) |
| realm | Softcode-fn | scripting | if_else(cond,true,false) | any | Conditional expression |
| realm | Softcode-fn | scripting | last(lst,delim) | any | Last element |
| realm | Softcode-fn | scripting | lcfirst(text) | any | Lowercase first character |
| realm | Softcode-fn | scripting | left(text,length) | any | Leftmost N characters |
| realm | Softcode-fn | perception | loc(obj) | any | Get an object's location |
| realm | Softcode-fn | dice | margin_over(rolled,target,skill) | any | Roll-over (D20) success + margin |
| realm | Softcode-fn | dice | margin_under(rolled,target,skill) | any | Roll-under (GURPS/CoC) success + margin |
| realm | Softcode-fn | scripting | member(item,lst,delim) | any | Position of item in list |
| realm | Softcode-fn | scripting | mid(text,start,length) | any | Substring (1-indexed) |
| realm | Softcode-fn | movement | move_to(target,dest,tags,force) | proximity | Relocate with movement checks |
| realm | Softcode-fn | perception | name(obj) | any | Get an object's name |
| realm | Softcode-fn | dice | net_successes(pool,tn,...) | any | Dice-pool success counting (SR/WoD) |
| realm | Softcode-fn | scripting | now() | any | Current epoch seconds |
| realm | Softcode-fn | comm | oemit(exclude,message) | proximity | Emit to room excluding one object |
| realm | Softcode-fn | comm | oob(target,package,data) | any | Send GMCP out-of-band data |
| realm | Softcode-fn | perception | owner(obj) | any | Get an object's owner |
| realm | Softcode-fn | comm | pemit(target,message) | any | Private message to a target |
| realm | Softcode-fn | comm | prompt(target,text,callback,persist) | any | Ask player; next line runs callback |
| realm | Softcode-fn | dice | rand(low,high) | any | Random integer in range |
| realm | Softcode-fn | social | reaction_roll(npc,other,mod) | proximity | Memoized first-impression roll |
| realm | Softcode-fn | comm | remit(room,message) | any | Emit to everyone in a room |
| realm | Softcode-fn | combat | remove_effect(obj,kind) | proximity | Strip an active effect by kind |
| realm | Softcode-fn | scripting | remove_tag(obj,tag) | controls target | Remove a tag |
| realm | Softcode-fn | scripting | repeat(text,count) | any | Repeat text N times |
| realm | Softcode-fn | scripting | replace(text,old,new) | any | Replace all occurrences |
| realm | Softcode-fn | scripting | rest(lst,delim) | any | All but first element |
| realm | Softcode-fn | scripting | right(text,length) | any | Rightmost N characters |
| realm | Softcode-fn | dice | roll(expr) | any | Roll dice expression to a total |
| realm | Softcode-fn | perception | search_world(tag,attr,value,name,limit) | any | Query the world for objects |
| realm | Softcode-fn | scripting | set_attr(obj,attr,value) | controls target | Set an attribute on controlled object |
| realm | Softcode-fn | scripting | set_lock(obj,type,expr) | controls target | Set a validated lock |
| realm | Softcode-fn | scripting | setdiff(l1,l2,delim) | any | List difference |
| realm | Softcode-fn | scripting | setinter(l1,l2,delim) | any | List intersection |
| realm | Softcode-fn | scripting | setunion(l1,l2,delim) | any | List union |
| realm | Softcode-fn | dice | skill_check(obj,skill,mod) | any | Roll a skill check |
| realm | Softcode-fn | combat | start_combat(attacker,target) | controls target | Throw controlled attacker into combat |
| realm | Softcode-fn | scripting | strlen(text) | any | String length |
| realm | Softcode-fn | scripting | switch(value,*cases) | any | Switch statement |
| realm | Softcode-fn | scripting | tag_value(obj,prefix) | any | First value of namespaced tag |
| realm | Softcode-fn | scripting | tag_values(obj,prefix) | any | All values of namespaced tag |
| realm | Softcode-fn | scripting | tags(obj) | any | Get all tags on an object |
| realm | Softcode-fn | movement | teleport_obj(obj,dest) | controls target | Move controlled obj straight to dest |
| realm | Softcode-fn | scripting | test_lock(obj,type,caller) | any | Would caller pass this lock? |
| realm | Softcode-fn | economy | transfer_credits(src,dest,amount) | controls target | Move money from controlled object |
| realm | Softcode-fn | scripting | trim(text) | any | Strip leading/trailing whitespace |
| realm | Softcode-fn | scripting | ucfirst(text) | any | Capitalize first character |
| realm | Softcode-fn | scripting | wait(seconds,command) | any | Run command ~seconds later (queued) |
| realm | Softcode-fn | scripting | words(text,delim) | any | Count words/elements |
| realm | Softcode-fn | perception | zone_rooms(zone) | any | Rooms tagged into a zone |
| realm | Softcode-fn | perception | zones_of(obj) | any | Zone names an object belongs to |
| pennmush | OLC | building | @dig <room>[=<exits>] | builder | Create room, optionally open exits to/from |
| pennmush | OLC | building | @open <exit>[=<dest>] | builder | Open exit in current room to destination |
| pennmush | OLC | building | @create <object> | builder | Create a new thing object |
| pennmush | OLC | building | @clone <obj>[=<name>] | controls target | Duplicate an object with its attributes |
| pennmush | OLC | building | @link <obj>=<dest> | controls target | Set exit dest / object home / player home |
| pennmush | OLC | building | @unlink <exit> | controls target | Remove exit destination or room drop-to |
| pennmush | OLC | building | @parent <obj>=<parent> | controls target | Set attribute-inheritance parent |
| pennmush | OLC | building | @name <obj>=<name> | controls target | Rename object (and player aliases) |
| pennmush | Builder | object | @set <obj>=<flag/attr> | controls target | Set flags or attributes on object |
| pennmush | Builder | object | @lset <obj>/<attr>=<flag> | controls target | Set attribute flags (locked, no_command...) |
| pennmush | Builder | object | @lock <obj>[/<type>]=<key> | controls target | Set a boolean lock (basic/use/enter/...) |
| pennmush | Builder | object | @unlock/@ulock/@elock | controls target | Remove or manage locks of a type |
| pennmush | Builder | object | @atrlock <obj>/<attr> | controls target | Lock/unlock an attribute against edits |
| pennmush | Builder | object | @atrchown <obj>/<attr>=<who> | controls target | Change attribute owner |
| pennmush | Builder | object | @cpattr <o>/<a>=<o>/<a> | controls target | Copy attribute(s) between objects |
| pennmush | Builder | object | @mvattr <o>/<a>=<o>/<a> | controls target | Move (rename) attribute(s) |
| pennmush | Builder | object | @edit <obj>/<attr>=<old>,<new> | controls target | Search/replace within attribute text |
| pennmush | Builder | object | @wipe <obj>[/<pat>] | controls target | Delete matching attributes en masse |
| pennmush | Builder | object | @chown <obj>=<player> | controls target | Change object owner |
| pennmush | Builder | object | @chzone <obj>=<zone> | controls target | Set object's zone master |
| pennmush | Builder | object | @destroy/@recycle/@nuke <obj> | controls target | Destroy object (undestroy to restore) |
| pennmush | Builder | object | @undestroy <obj> | controls target | Cancel pending destruction |
| pennmush | Builder | object | @teleport <obj>=<dest> | controls target | Move object to a location |
| pennmush | Builder | object | @flag/@power/@attribute | wizard | Define/alter flags, powers, attribute perms |
| pennmush | Builder | object | @firstexit <exit-list> | controls target | Reorder exit to front of room's exit list |
| pennmush | Builder | object | @quota / @squota | builder | View/set object-creation quota |
| pennmush | Builder | info | @decompile <obj> | controls target | Emit commands to recreate object |
| pennmush | Builder | info | @find / @search | builder | Find objects by name/owner/type/attr |
| pennmush | Builder | info | @entrances <obj> | builder | List exits/links pointing at object |
| pennmush | Builder | info | @scan <obj> | any | Show which $-commands would match input |
| pennmush | Builder | info | @grep <obj>/<pat> | controls target | Search object's attributes (regex/wild) |
| pennmush | Builder | info | @sweep [here/inv] | any | List listening/puppet/connected objects |
| pennmush | Player | object | @describe/@idescribe <obj>=<text> | controls target | Set DESCRIBE attr (@desc alias of @set) |
| pennmush | Player | object | @succ/@fail/@osucc/@drop/@ex... | controls target | Set standard message/action attributes |
| pennmush | Admin | admin | @force <obj>=<cmd> | controls target | Make object execute command as itself |
| pennmush | Admin | queue | @switch <str>=<pat>,<act>,... | any | Branch: run action for first matching pattern |
| pennmush | Admin | queue | @select <str>=<pat>,<act>,... | any | Like @switch, non-regex first-match branch |
| pennmush | Admin | queue | @dolist <list>=<cmd> | any | Iterate command over list items (##/#@) |
| pennmush | Admin | queue | @wait <secs>/<pid>=<cmd> | any | Delay command; @wait until <time> |
| pennmush | Admin | queue | @trigger <obj>/<attr>=<args> | controls target | Queue an attribute as a command with args |
| pennmush | Admin | queue | @include <obj>/<attr> | any | Inline-run attr in current queue/registers |
| pennmush | Admin | queue | @break/@assert <cond>=<cmd> | any | Abort/continue action list on condition |
| pennmush | Admin | queue | @retry / @skip / @ifelse | any | Loop-restart / conditional queue control |
| pennmush | Admin | queue | @halt [<obj>] | controls target | Clear queued/waiting commands for object |
| pennmush | Admin | queue | @ps [all/summary] | any | List queued/semaphore/wait commands |
| pennmush | Admin | queue | @notify/@drain <obj>[=<n>] | controls target | Signal/flush semaphore queue on object |
| pennmush | Admin | admin | @function <name>=<obj>/<attr> | wizard | Define global user function (softcode) |
| pennmush | Admin | admin | @hook <cmd>=<obj>/<attr> | wizard | Attach pre/post hooks to a built-in command |
| pennmush | Admin | admin | @command <name> | wizard | Add/restrict/inspect a command definition |
| pennmush | Admin | admin | @program / @quitprogram | wizard | Route object's input to an attribute (prompt) |
| pennmush | Admin | admin | @boot/@kick/@newpassword | wizard | Disconnect player, force cycle, reset pass |
| pennmush | Admin | admin | @shutdown/@restart/@dump | wizard | Server lifecycle and DB save control |
| pennmush | Admin | admin | @sitelock / @disable / @enable | wizard | Ban sites; toggle commands/functions |
| pennmush | Admin | admin | @config [set] | wizard | View/change runtime config options |
| pennmush | Admin | admin | @sql <query> | wizard | Run raw SQL against configured database |
| pennmush | Admin | admin | @mapsql <obj>/<attr>=<query> | wizard | Run SQL, trigger attr per result row |
| pennmush | Admin | admin | @wall/@rwall/@wizwall | wizard | Broadcast to all / royalty / wizards |
| pennmush | Admin | comm | @emit <msg> | any | Emit text to room, unattributed |
| pennmush | Admin | comm | @pemit <obj>=<msg> | any | Send private message to object/player |
| pennmush | Admin | comm | @remit <room>=<msg> | any | Emit to all contents of a room |
| pennmush | Admin | comm | @oemit <obj>=<msg> | any | Emit to room except named object |
| pennmush | Admin | comm | @lemit <msg> | any | Emit to object's outermost location |
| pennmush | Admin | comm | @zemit <zone>=<msg> | any | Emit to all rooms in a zone |
| pennmush | Admin | comm | @nspemit/@nsemit/... | wizard | Nospoof-suppressed emit variants |
| pennmush | Admin | comm | @prompt <obj>=<msg> | any | Pemit without trailing newline (prompt) |
| pennmush | Admin | comm | @message <recip>=<attr>,<args> | any | Format+send localizable attr-based message |
| pennmush | Player | comm | say <msg> / " <msg> | any | Speak aloud to the room |
| pennmush | Player | comm | pose <msg> / : <msg> | any | Emote an action (Name does...) |
| pennmush | Player | comm | semipose / ; <msg> | any | Emote with no leading space |
| pennmush | Player | comm | whisper <obj>=<msg> | any | Private message to someone in same room |
| pennmush | Player | comm | page <player>=<msg> | any | Send remote page; supports lists/ports |
| pennmush | Player | comm | think <msg> | any | Evaluate/echo text only to yourself |
| pennmush | Player | channel | @chat/@channel/@cemit | any | Join, admin, and speak on channels |
| pennmush | Player | channel | addcom/delcom/comtitle/comlist | any | Channel alias management |
| pennmush | Player | mail | @mail [<msg>] | any | Send/read/manage internal @mail |
| pennmush | Player | mail | @malias | any | Manage mail alias lists |
| pennmush | Player | info | look [<obj>] | any | Examine room/object/attribute |
| pennmush | Player | info | examine <obj> | controls target | Full dump of flags/attrs/locks |
| pennmush | Player | info | inventory / score | any | List carried items / money |
| pennmush | Player | info | who / doing / session | any | Online player list and connection info |
| pennmush | Player | info | brief <obj> | any | Look without long descriptions |
| pennmush | Player | object | get/drop/give/enter/leave | any | Manipulate/move objects and self |
| pennmush | Player | object | goto/go/home/follow/desert | any | Movement and follow mechanics |
| pennmush | Player | object | use / buy / with | any | Trigger USE, economy, WITH-object actions |
| pennmush | Softcode-fn | softcode | u(obj/attr,args) | any | Call attr as user function, return result |
| pennmush | Softcode-fn | softcode | ulocal(...) | any | Like u() but preserves q-registers |
| pennmush | Softcode-fn | softcode | ulambda(<code>,args) | any | Call anonymous/inline code as function |
| pennmush | Softcode-fn | softcode | pfun(attr,args) | any | Call attr respecting caller permissions |
| pennmush | Softcode-fn | softcode | zfun/ufun(...) | any | Zone-master u(); generic user-fn call |
| pennmush | Softcode-fn | softcode | udefault(obj/attr,def,args) | any | u() with default if attr absent |
| pennmush | Softcode-fn | softcode | fn(name,args) | any | Call built-in even if overridden |
| pennmush | Softcode-fn | softcode | eval(obj,attr) / get_eval | controls target | Get attribute and evaluate its contents |
| pennmush | Softcode-fn | softcode | objeval(obj,code) | see_all | Evaluate code as if by another object |
| pennmush | Softcode-fn | softcode | localize(code) | any | Evaluate with saved/restored registers |
| pennmush | Softcode-fn | softcode | benchmark(code,n) | any | Time repeated evaluation of code |
| pennmush | Softcode-fn | list | iter(list,expr[,idelim,odelim]) | any | Map expr over list (##=item, #@=index) |
| pennmush | Softcode-fn | list | map(obj/attr,list[,delim]) | any | Apply user-fn to each list element |
| pennmush | Softcode-fn | list | filter(attr,list,...) / filterbool | any | Keep elements where fn returns true/1 |
| pennmush | Softcode-fn | list | fold(attr,list[,base]) | any | Left-fold/reduce list through a user-fn |
| pennmush | Softcode-fn | list | munge(attr,l1,l2,delim) | any | Permute l2 by fn's reordering of l1 |
| pennmush | Softcode-fn | list | mix(attr,l1,l2,...) | any | Apply fn across parallel lists elementwise |
| pennmush | Softcode-fn | list | step(attr,list,n,...) | any | Apply fn to list n elements at a time |
| pennmush | Softcode-fn | list | foreach(attr,string) | any | Apply fn to each character of a string |
| pennmush | Softcode-fn | list | sort/sortby/sortkey(list) | any | Sort list (typed / by user-fn / by key) |
| pennmush | Softcode-fn | list | setunion/setinter/setdiff/setsymdiff | any | Set operations on two lists |
| pennmush | Softcode-fn | list | itemize/elist/list | any | Human-readable "a, b, and c" listing |
| pennmush | Softcode-fn | list | match/matchall/grab/graball | any | Wildcard-find element(s) in a list |
| pennmush | Softcode-fn | list | regrab/regraball/reglmatch(all)(i) | any | Regex-find element(s) in a list |
| pennmush | Softcode-fn | list | namegrab/namegraball | any | Match list by object name |
| pennmush | Softcode-fn | list | fold/extract/elements/index/ldelete | any | Slice/index/delete positional list items |
| pennmush | Softcode-fn | list | lreplace/linsert/lset/splice/merge | any | Positional insert/replace/merge on lists |
| pennmush | Softcode-fn | list | shuffle/randword/randextract/unique | any | Randomize / dedupe list elements |
| pennmush | Softcode-fn | list | first/rest/last/revwords/flip | any | Head/tail/reverse word helpers |
| pennmush | Softcode-fn | list | words/wordpos/lnum/table | any | Count words; number lists; column tables |
| pennmush | Softcode-fn | softcode | switch(str,pat,act,...) / switchall | any | Function-form pattern branch (case alias) |
| pennmush | Softcode-fn | softcode | reswitch(all)(i)(str,re,act,...) | any | Regex-based switch |
| pennmush | Softcode-fn | softcode | cond/condall/ncond(pairs) | any | Evaluate first true condition's value |
| pennmush | Softcode-fn | softcode | if/ifelse(cond,then,else) | any | Boolean branch, lazy-evaluated |
| pennmush | Softcode-fn | softcode | firstof/allof/strfirstof/strallof | any | First non-false / all-true collector |
| pennmush | Softcode-fn | softcode | default/edefault/udefault | any | Fallback value if attr empty/missing |
| pennmush | Softcode-fn | softcode | setq/setr/r/letq/listq/unsetq | any | Set/read q-registers (0-9,a-z,named) |
| pennmush | Softcode-fn | softcode | ibreak/ilev/itext/inum/ if/stext/slev | any | Introspect iter()/switch() nesting state |
| pennmush | Softcode-fn | object | get(obj/attr) | controls target | Read attribute value (no eval) |
| pennmush | Softcode-fn | object | xget(obj,attr) | controls target | get() with separate obj/attr args |
| pennmush | Softcode-fn | object | set(obj,attr:val) | controls target | Set an attribute or flag |
| pennmush | Softcode-fn | object | attrib_set(obj/attr,val) | controls target | Set/clear attribute (clears if no val) |
| pennmush | Softcode-fn | object | lattr/xattr/regxattr(obj[,pat]) | controls target | List attribute names by wildcard/regex |
| pennmush | Softcode-fn | object | nattr/regnattr | controls target | Count matching attributes |
| pennmush | Softcode-fn | object | hasattr(p)(val)(obj/attr) | controls target | Test attribute existence/value |
| pennmush | Softcode-fn | object | grep/grepi/wildgrep/regrep(obj,pat,txt) | controls target | Search attribute contents |
| pennmush | Softcode-fn | object | scan(obj,cmd) | see_all | Which $-commands match a command string |
| pennmush | Softcode-fn | object | v(attr) / get_eval | any | Read+eval attr on self (%-substitution) |
| pennmush | Softcode-fn | object | edit(str,old,new) | any | String search/replace |
| pennmush | Softcode-fn | object | clone/create/dig/open/pcreate | builder | Object creation from softcode |
| pennmush | Softcode-fn | object | link/tel/set/name/lock(function forms) | controls target | Side-effecting build ops in softcode |
| pennmush | Softcode-fn | object | wipe(obj) | controls target | Delete attributes via softcode |
| pennmush | Softcode-fn | info | name/fullname/iname/accname/moniker | any | Object display names and variants |
| pennmush | Softcode-fn | info | num/objid/pmatch/locate | any | Resolve name/dbref to object reference |
| pennmush | Softcode-fn | info | loc/rloc/where/home/room/con/exit/next | any | Object location and container walking |
| pennmush | Softcode-fn | info | lcon/lexits/lplayers/lvcon/xcon(...) | any | List contents/exits (visible/typed) db-walk |
| pennmush | Softcode-fn | info | ncon/nexits/nplayers(...) | any | Count contents/exits db-walk variants |
| pennmush | Softcode-fn | info | children/parent/lparent/nchildren | any | Parent/child inheritance chain |
| pennmush | Softcode-fn | info | type/hastype/owner/money/quota | any | Object type/owner/economy metadata |
| pennmush | Softcode-fn | info | controls(a,b) | any | Does a control b? (core permission test) |
| pennmush | Softcode-fn | info | visible/nearby/findable/valid | any | Visibility, proximity, name-validity tests |
| pennmush | Softcode-fn | info | flags/lflags/hasflag/orflags/andflags | any | Read/test object flags |
| pennmush | Softcode-fn | info | powers/haspower/orlpowers/andlpowers | any | Read/test object powers |
| pennmush | Softcode-fn | info | lock/locks/elock/testlock/lockfilter | controls target | Read/evaluate/filter by lock expressions |
| pennmush | Softcode-fn | info | lockflags/lockowner/clock | controls target | Lock metadata |
| pennmush | Softcode-fn | info | zone/zwho/zfun | any | Zone membership and zone-master calls |
| pennmush | Softcode-fn | info | config/mudname/mudurl/version | any | Server identity and config values |
| pennmush | Softcode-fn | info | nextdbref/objmem/playermem/lstats | wizard | DB internals, memory, object stats |
| pennmush | Softcode-fn | info | followers/following/entrances | any | Follow relationships; inbound links |
| pennmush | Softcode-fn | info | lsearch/nlsearch/nsearch(class,...) | any | Search DB by owner/type/flag/eval |
| pennmush | Softcode-fn | string | ansi(codes,text) | any | Apply ANSI/color markup to text |
| pennmush | Softcode-fn | string | render(text,type) / tag/endtag/tagwrap | any | Emit Pueblo/HTML/markup for clients |
| pennmush | Softcode-fn | string | align/lalign(widths,cols) | any | Multi-column aligned text layout |
| pennmush | Softcode-fn | string | center/ljust/rjust/wrap/table | any | Pad, justify, wrap text |
| pennmush | Softcode-fn | string | strlen/strcat/mid/left/right/strinsert | any | Basic string length/slice/concat family |
| pennmush | Softcode-fn | string | before/after/strdelete/strreplace | any | Substring extract/delete/replace family |
| pennmush | Softcode-fn | string | ucstr/lcstr/capstr/space/repeat/trim/squish | any | Case, whitespace, repeat helpers |
| pennmush | Softcode-fn | string | escape/secure/decompose/lit | any | Neutralize special chars for safe eval |
| pennmush | Softcode-fn | string | strmatch/regmatch(i)/wildmatch | any | Wildcard/regex match with capture groups |
| pennmush | Softcode-fn | string | regedit(all)(i)(str,re,repl) | any | Regex search-and-replace |
| pennmush | Softcode-fn | string | edit/tr/scramble/reverse/merge | any | Character transform/replace helpers |
| pennmush | Softcode-fn | string | pos/lpos/member/comp/strmatch | any | Locate substring/element position |
| pennmush | Softcode-fn | string | accent/stripaccents/chr/ord/art/spellnum | any | Accents, char codes, articles, num words |
| pennmush | Softcode-fn | string | soundex/soundslike/suggest | any | Phonetic match / spelling suggestions |
| pennmush | Softcode-fn | string | encode64/decode64/urlencode/formdecode | any | Base64 / URL / form encoding |
| pennmush | Softcode-fn | math | add/sub/mul/div/fdiv/floordiv/modulo/... | any | Core arithmetic family (2..N args) |
| pennmush | Softcode-fn | math | max/min/bound/abs/sign/inc/dec/round/trunc | any | Scalar numeric helpers |
| pennmush | Softcode-fn | math | sqrt/power/log/ln/e/pi/sin/cos/tan/... | any | Transcendental / trig family |
| pennmush | Softcode-fn | math | and/or/not/xor/nand/nor/cand/cor/t | any | Boolean logic (cand/cor short-circuit) |
| pennmush | Softcode-fn | math | eq/neq/gt/gte/lt/lte/comp | any | Comparison family |
| pennmush | Softcode-fn | math | band/bor/bxor/bnand/bnot/shl/shr/baseconv | any | Bitwise ops and base conversion |
| pennmush | Softcode-fn | math | lmath(op,list) | any | Apply arithmetic op across a whole list |
| pennmush | Softcode-fn | math | mean/median/stddev/root/remainder/fraction | any | Statistics and number formatting |
| pennmush | Softcode-fn | math | rand/die(n,sides)/lnum | any | Random numbers and dice rolls |
| pennmush | Softcode-fn | math | isint/isnum/isdbref/isobjid/isword/isregexp | any | Type/format predicates |
| pennmush | Softcode-fn | vector | vadd/vsub/vmul/vdot/vcross | any | Vector arithmetic on space-delim lists |
| pennmush | Softcode-fn | vector | vmag/vunit/vdim/vmax/vmin | any | Vector magnitude, normalize, dimension |
| pennmush | Softcode-fn | vector | dist2d/dist3d | any | Euclidean distance between points |
| pennmush | Softcode-fn | vector | ctu(deg,rad,grad) | any | Convert angle units |
| pennmush | Softcode-fn | json | json(type,val...) | any | Construct JSON value of given type |
| pennmush | Softcode-fn | json | json_query(json,path...) | any | Query/extract/size/type from JSON |
| pennmush | Softcode-fn | json | json_map(attr,json) / json_mod | any | Map fn over JSON; modify JSON in place |
| pennmush | Softcode-fn | json | isjson(str) | any | Validate JSON text |
| pennmush | Softcode-fn | json | oob(...) / wsjson / wshtml | any | Out-of-band / websocket JSON+HTML output |
| pennmush | Softcode-fn | sql | sql(query[,delims]) | wizard | Run SQL, return rows as delimited list |
| pennmush | Softcode-fn | sql | mapsql(attr,query) | wizard | Run SQL, apply user-fn per result row |
| pennmush | Softcode-fn | sql | sqlescape(str) | wizard | Escape a string for safe SQL |
| pennmush | Softcode-fn | crypt | digest(algo,str) | any | Hash string (sha256, md5, ...) |
| pennmush | Softcode-fn | crypt | hmac(algo,key,str) | any | Keyed HMAC digest |
| pennmush | Softcode-fn | crypt | encrypt/decrypt(str,key) | any | Symmetric string cipher |
| pennmush | Softcode-fn | crypt | checkpass(player,pass) | wizard | Verify a player's password |
| pennmush | Softcode-fn | time | time/utctime/mtime/ctime/secs/msecs | any | Current/object timestamps |
| pennmush | Softcode-fn | time | convsecs/convtime/csecs/ctime | any | Convert between epoch and formatted time |
| pennmush | Softcode-fn | time | timefmt(fmt,secs) / etimefmt | any | strftime-style time formatting |
| pennmush | Softcode-fn | time | timestring/stringsecs/etime/timecalc | any | Duration formatting/parsing/arithmetic |
| pennmush | Softcode-fn | time | starttime/restarttime/uptime/restarts | any | Server timing info |
| pennmush | Softcode-fn | time | isdaylight/secscalc | any | DST check; second arithmetic |
| pennmush | Softcode-fn | info | lwho/mwho/nwho/xwho/zwho(id) | any | Online player dbref lists (filtered) |
| pennmush | Softcode-fn | info | conn/idle/doing/hidden/recv/sent | any | Per-connection state (idle, doing, bytes) |
| pennmush | Softcode-fn | info | ports/lports/host/ipaddr/ssl/terminfo | wizard | Descriptor/network info per player |
| pennmush | Softcode-fn | info | pidinfo/lpids/getpids | any | Queue process (PID) introspection |
| pennmush | Softcode-fn | info | player/pmatch/alias/fullalias/quota | any | Player lookup and metadata |
| pennmush | Softcode-fn | comm | emit/pemit/remit/oemit/lemit/zemit | any | Side-effecting emit functions |
| pennmush | Softcode-fn | comm | prompt/message/speak/cemit | any | Prompt, formatted, RP-speech, channel emit |
| pennmush | Softcode-fn | comm | ns*emit (nspemit,nsemit,...) | wizard | Nospoof-suppressed emit function forms |
| pennmush | Softcode-fn | channel | cwho/cflags/cinfo/cbuffer/cdesc/cowner | any | Channel roster and metadata |
| pennmush | Softcode-fn | channel | channels/clock/cstatus/ctitle/crecall | any | Channel membership, locks, recall buffer |
| pennmush | Softcode-fn | channel | cbufferadd/cmsgs/cusers/cmogrifier | controls target | Channel buffer/message admin |
| pennmush | Softcode-fn | mail | mail/maillist/mailfrom/mailsend | any | Read/list/send @mail from softcode |
| pennmush | Softcode-fn | mail | mailstats/mailstatus/mailsubject/mailtime | any | Mail metadata queries |
| pennmush | Softcode-fn | info | textfile/textentries/textsearch | any | Read/search server help/text files |
| pennmush | Softcode-fn | info | functions/commands/cmds/config/colors | any | Introspect available fns/cmds/config |
| pennmush | Softcode-fn | softcode | null(x) / @@(x) | any | Discard args, return empty (comments) |
| pennmush | Softcode-fn | info | connlog/connrecord/addrlog | wizard | Connection-history log queries |
| tinymux | Player | info | look [<obj>] | any | Look at room/object, show description & contents |
| tinymux | Player | object | examine <obj> | controls/see | Show object attributes, flags, owner |
| tinymux | Player | object | get/drop/give <obj> | location | Pick up, drop, or give objects/money |
| tinymux | Player | object | goto/enter/leave/use <exit> | location | Move via exit, enter/leave vehicle, use object |
| tinymux | Player | object | inventory / score | any | List carried objects / show money & stats |
| tinymux | Player | comm | say/pose/"/:/;/\\ <msg> | location | Speak or emote to the room |
| tinymux | Player | comm | whisper <who>=<msg> | location | Private message to someone in room |
| tinymux | Player | comm | page <who>=<msg> | any | Send remote private message (switches: /list /reply) |
| tinymux | Player | info | who / doing / session | any | List connected players, doing lines, session info |
| tinymux | Player | info | +help/help/info | any | Read help & info text files |
| tinymux | Player | object | kill/slay <who> | any/wizard | Attack player (kill=combat, slay=instant/wizard) |
| tinymux | Player | queue | think <expr> | any | Evaluate expression, show result to self |
| tinymux | Player | admin | quit/logout/QUIT | any | Disconnect or drop to login screen |
| tinymux | Builder | building | @dig <room>=<exitto>,<exitback> | builder | Create room with linked exits (MUX-distinct argv) |
| tinymux | Builder | building | @open <exit>=<loc>,<back> | builder | Create exit in current room, optional linkback |
| tinymux | Builder | building | @create <obj>[=<cost>] | builder | Create a thing object |
| tinymux | Builder | building | @clone <obj>[=<newname>] | controls | Duplicate object with attributes |
| tinymux | Builder | building | @link <obj>=<dest> | builder/controls | Link exit/home/drop-to destination |
| tinymux | Builder | building | @unlink <exit> | controls | Remove exit link / room drop-to |
| tinymux | Builder | building | @destroy <obj> | controls | Destroy object (switch: /override) |
| tinymux | Builder | building | @teleport <obj>=<dest> | controls | Move object to location |
| tinymux | Builder | object | @name <obj>=<name>[;aliases] | controls | Rename object |
| tinymux | Builder | object | @moniker <obj>=<text> | controls | Set ANSI display moniker (MUX-distinct) |
| tinymux | Builder | object | @describe/@desc <obj>=<text> | controls | Set description (via @set/attr; @edit edits it) |
| tinymux | Builder | object | @set <obj>=<flag>/<attr>:<val> | controls | Set flags or attributes on object |
| tinymux | Builder | object | &<attr> <obj>=<val> | controls | Set user attribute (leadin shorthand) |
| tinymux | Builder | object | @lock <obj>[/<type>]=<key> | controls | Set a lock (default/use/enter/etc.) |
| tinymux | Builder | object | @unlock <obj>[/<type>] | controls | Remove a lock |
| tinymux | Builder | object | @parent <obj>=<parent> | controls | Set attribute-inheritance parent |
| tinymux | Builder | object | @chown <obj>[=<player>] | controls/wizard | Change object owner (@chownall wizard) |
| tinymux | Builder | object | @chzone <obj>=<zone> | controls | Assign object to a zone master |
| tinymux | Builder | object | @cpattr / @mvattr / @edit | controls | Copy, move, or search-replace attributes |
| tinymux | Builder | object | @wipe <obj> | controls | Delete all attributes on object |
| tinymux | Builder | object | @decompile <obj> | controls | Emit commands to recreate object's attrs/flags |
| tinymux | Builder | info | @find / @entrances / @search | builder | Find owned objects / exits leading to / DB search |
| tinymux | Builder | info | @scan / @sweep | any | Show which cmds match / list listeners & bugs |
| tinymux | Builder | object | @quota | any/wizard | Show or set building quota |
| tinymux | Builder | object | @reference <name>=<obj> | any | Named #-reference alias for a dbref (MUX-distinct) |
| tinymux | Admin | queue | @force <obj>=<cmd> | controls | Make object execute a command as itself |
| tinymux | Admin | queue | @switch <val>=<pat>,<cmd>,... | any | Branch command execution on pattern match |
| tinymux | Admin | queue | @dolist <list>=<cmd> | any | Run command once per list element (##/#@ tokens) |
| tinymux | Admin | queue | @wait <secs>[/<sem>]=<cmd> | any | Queue command after delay or on semaphore |
| tinymux | Admin | queue | @notify/@drain <obj>[=<n>] | controls | Signal/drain semaphore-waiting queue entries |
| tinymux | Admin | queue | @halt <obj> | controls | Halt queued commands for object |
| tinymux | Admin | queue | @ps [<obj>] | any | Show queued command entries |
| tinymux | Admin | queue | @kick / @restart | wizard | Force queue cycle / soft process restart |
| tinymux | Admin | queue | @trigger <obj>/<attr>[=args] | controls | Run an attribute as a command |
| tinymux | Admin | queue | @assert / @break <cond>=<cmd> | any | Abort or continue action list on condition |
| tinymux | Admin | queue | @if <cond>=<then>,<else> | any | Conditional command (argv form) |
| tinymux | Admin | queue | @include <obj>/<attr> | any | Inline-execute another attribute's actions |
| tinymux | Admin | queue | @program <obj>=<attr> | controls | Capture player input into an attribute (@quitprogram) |
| tinymux | Admin | admin | @function <name>=<obj>/<attr> | god | Register a global user-defined softcode function |
| tinymux | Admin | admin | @addcommand/@delcommand | god | Add/remove a global command hooked to an attr (MUX-distinct) |
| tinymux | Admin | admin | @hook <cmd>=<obj>/<attr> | god | Attach before/after/permit hook to a builtin cmd (MUX-distinct) |
| tinymux | Admin | admin | @icmd <player>=<cmds> | god | Enable/disable commands per-object (MUX-distinct) |
| tinymux | Admin | admin | @attribute / @flag / @power | god | Define/rename attributes, flags, powers |
| tinymux | Admin | admin | @cron / @crontab / @crondel | any | Schedule recurring commands cron-style (MUX-distinct) |
| tinymux | Admin | admin | @query <db>=<sql> | wizard | Run SQL against configured external DB |
| tinymux | Admin | admin | @lua <code> | any | Execute embedded Lua (MUX-distinct) |
| tinymux | Admin | admin | @toad/@newpassword/@boot/@pcreate | wizard | Destroy player / reset pw / disconnect / make player |
| tinymux | Admin | admin | @shutdown/@dump/@dbck/@restart | wizard | Server lifecycle, DB save & integrity |
| tinymux | Admin | admin | @wall / @motd / @admin / @config | wizard | Broadcast, message-of-day, runtime config |
| tinymux | Admin | comm | @emit/@nemit/@femit <msg> | location | Emit unattributed text to room |
| tinymux | Admin | comm | @pemit/@npemit <who>=<msg> | any | Emit text to specific player(s) |
| tinymux | Admin | comm | @oemit <who>=<msg> | location | Emit to room except named player |
| tinymux | Admin | comm | @fpose/@fsay/@fwd | controls | Force pose/say/forward as another object |
| tinymux | Player | mail | @mail <who>=<subj>/<msg> | any | Send/read/manage @mail (switches: read/list/etc.) |
| tinymux | Player | mail | @malias / @folder | any | Mail aliases and folder management |
| tinymux | Player | channel | addcom/delcom/comlist/allcom/clearcom | any | Comsys: join/leave/list channel aliases |
| tinymux | Player | channel | comtitle <alias>=<title> | any | Set per-channel title |
| tinymux | Admin | channel | @ccreate/@cdestroy/@cset/@clist | owner/wizard | Create/destroy/configure/list channels |
| tinymux | Admin | channel | @cemit/@cboot/@cchown/@cwho | owner | Emit to, boot from, reassign, list channel |
| tinymux | Softcode-fn | softcode | u(obj/attr,args) / ulocal / ulambda | any | Call attribute as function (ulocal preserves q-regs) |
| tinymux | Softcode-fn | softcode | get / xget / get_eval / eval / v(x) | controls attr | Fetch attribute value, optionally evaluated |
| tinymux | Softcode-fn | softcode | set / attrib_set(obj,attr,val) | controls | Set attribute from softcode |
| tinymux | Softcode-fn | softcode | default/edefault/udefault(attr,alt) | any | Attribute value with fallback (u-form calls) |
| tinymux | Softcode-fn | softcode | setq/setr/r(n)/listq/unsetq/letq | any | Read/write/scope q-registers (setr returns value) |
| tinymux | Softcode-fn | softcode | localize(expr) / objeval(obj,expr) | any | Evaluate with saved regs / as another object's perms |
| tinymux | Softcode-fn | softcode | switch/switchall/case/caseall | any | Pattern-branch evaluation |
| tinymux | Softcode-fn | softcode | if/ifelse/firstof/allof/@@(cmt) | any | Conditionals and null/comment |
| tinymux | Softcode-fn | softcode | iter/list/ilev/itext/inum | any | Loop over a list (##/itext nesting context) |
| tinymux | Softcode-fn | softcode | fold/foreach/map/filter/filterbool/munge | any | Higher-order list transforms |
| tinymux | Softcode-fn | softcode | while/step | any | Loop with condition / in chunks |
| tinymux | Softcode-fn | softcode | sandbox(obj/attr,...) | any | Evaluate under restricted permissions (MUX-distinct) |
| tinymux | Softcode-fn | softcode | trace / benchmark / astbench / rvbench | any/wizard | Debug/profile evaluation |
| tinymux | Softcode-fn | softcode | s/secure/escape/lit/subeval/asteval | any | Control (re)parsing & escaping of text |
| tinymux | Softcode-fn | softcode | lua(code) | any | Call embedded Lua from softcode (MUX-distinct) |
| tinymux | Softcode-fn | object | create/clone/destroy(obj) | controls | Create/clone/destroy object from softcode |
| tinymux | Softcode-fn | object | num/name/fullname/moniker/objid | any | Object dbref, name, unique objid |
| tinymux | Softcode-fn | object | owner/cowner/controls/isobjid/valid | any | Ownership & control checks |
| tinymux | Softcode-fn | object | loc/rloc/where/home/room/rooms | see | Object location, recursive loc, absolute room |
| tinymux | Softcode-fn | object | con/exit/next/lcon/lexits/children | see | Contents/exit-list iteration and traversal |
| tinymux | Softcode-fn | object | parent/lparent/name derivation | any | Parent chain queries |
| tinymux | Softcode-fn | object | locate/pmatch/pfind/lsearch/search | see | Match objects/players by name or criteria |
| tinymux | Softcode-fn | object | findable/nearby/lastcreate/entrances | any | Reachability, adjacency, recent creations |
| tinymux | Softcode-fn | object | link/tel/rloc/moniker (mutators) | controls | Softcode link/teleport helpers |
| tinymux | Softcode-fn | object | zone/inzone/zwho/zfun/zexits/zrooms/zthings/zchildren | any | Zone (ZMO) membership & delegated funcs |
| tinymux | Softcode-fn | list | lattr/lattrp/reglattr/nattr/attrcnt | see | List / regex-list / count attributes on object |
| tinymux | Softcode-fn | list | lattrcmds/lcmds/cmds | see | List $-command attributes on object (MUX-distinct) |
| tinymux | Softcode-fn | list | hasattr/hasattrp/objmem/wipe | controls | Attribute existence, memory, bulk clear |
| tinymux | Softcode-fn | info | flags/lflags/hasflag/andflags/orflags | any | Object flag queries |
| tinymux | Softcode-fn | info | type/hastype/hasquota/bittype/objmem | any | Object type & quota queries |
| tinymux | Softcode-fn | info | powers/haspower/hasflag | any | Power/permission queries |
| tinymux | Softcode-fn | info | visible/elock/lock/lockencode/lockdecode | see | Visibility and lock evaluation |
| tinymux | Softcode-fn | info | money/pack/unpack/baseconv | any | Money value and base/number conversions |
| tinymux | Softcode-fn | comm | emit/pemit/oemit/remit/cemit/pose/prompt | see | Emit text from softcode to room/player/channel |
| tinymux | Softcode-fn | comm | nsemit/nsoemit/nspemit/nsremit | wizard | No-spoof variants of emit functions |
| tinymux | Softcode-fn | comm | trigger(obj/attr,args) | controls | Fire an attribute as a command from softcode |
| tinymux | Softcode-fn | route | route(obj,cmd[,default]) | controls | Route/dispatch command by object's routing attr (MUX-distinct) |
| tinymux | Softcode-fn | info | verb(...) | controls | Trigger verb with actor/others/default messaging |
| tinymux | Softcode-fn | mail | mail/mailfrom/mailsubj/mailinfo/maillist | any | Read @mail metadata from softcode |
| tinymux | Softcode-fn | mail | mailcount/mailsize/mailstats/mailsend/mailreview | any | Mail counts, stats, send, review |
| tinymux | Softcode-fn | mail | malias/mailflags | any | Mail alias & flag queries |
| tinymux | Softcode-fn | channel | channels/chanobj/chaninfo/chanfind/cflags | any | Channel enumeration & metadata |
| tinymux | Softcode-fn | channel | chanuser(s)/cwho/cusers/cstatus/cbuffer/crecall | any | Channel membership & history |
| tinymux | Softcode-fn | channel | comalias/comtitle/cdesc/cowner/cmsgs/cmogrifier | any | Comsys alias/title/config lookups |
| tinymux | Softcode-fn | info | version/mudname/motd/config/stats/mtime | any | Server identity, config, uptime, DB stats |
| tinymux | Softcode-fn | info | lwho/lports/ports/who-style | any/wizard | Connected players/ports lists |
| tinymux | Softcode-fn | info | conn/idle/doing/host/siteinfo/poll/motd | any/wizard | Per-connection info & poll string |
| tinymux | Softcode-fn | info | conn{last,left,max,num,record,total}/playmem | any | Connection history & memory stats |
| tinymux | Softcode-fn | info | lplayers/nplayers/nthings/lrooms/lthings/lexits | any | Enumerate/count DB objects by type |
| tinymux | Softcode-fn | info | restarts/starttime/restarttime/startsecs/uptime | any | Server restart & start-time info |
| tinymux | Softcode-fn | info | textfile/dynhelp/terminfo/colordepth/gmcp | any/wizard | Help-file lookup, terminal caps, GMCP push |
| tinymux | Softcode-fn | math | add/sub/mul/div/fdiv/mod/floordiv/remainder/... | any | Core arithmetic (grouped; incl. i-integer variants) |
| tinymux | Softcode-fn | math | abs/sign/inc/dec/bound/round/trunc/ceil/floor/max/min | any | Scalar numeric helpers (grouped) |
| tinymux | Softcode-fn | math | sin/cos/tan/asin/acos/atan/atan2/exp/ln/log/sqrt/pi/e/power | any | Trig, log, exponent (grouped) |
| tinymux | Softcode-fn | math | band/bor/bxor/bnand/shl/shr/baseconv | any | Bitwise & base ops (grouped) |
| tinymux | Softcode-fn | math | eq/neq/gt/gte/lt/lte/and/or/not/xor/*bool/cand/cor | any | Comparison & boolean logic (grouped) |
| tinymux | Softcode-fn | math | mean/median/stddev/dist2d/dist3d/fmod | any | Statistics & geometry (grouped) |
| tinymux | Softcode-fn | math | vadd/vsub/vmul/vdot/vcross/vmag/vunit/vdim | any | Vector math (grouped) |
| tinymux | Softcode-fn | math | rand/lrand/die/pickrand/shuffle | any | Randomness & dice |
| tinymux | Softcode-fn | math | lmath/limath(op,list) | any | Apply arithmetic op across a list (MUX-distinct) |
| tinymux | Softcode-fn | math | roman/spellnum/digittime/isint/isnum/israt/isdbref/isobjid | any | Number formatting & type predicates |
| tinymux | Softcode-fn | string | strlen/strcat/cat/mid/left/right/first/rest/... | any | Core string slice/concat (grouped) |
| tinymux | Softcode-fn | string | ucstr/lcstr/capstr/caplist/trim/squish/space/repeat | any | Case, pad-trim, whitespace (grouped) |
| tinymux | Softcode-fn | string | ljust/rjust/center/cpad/lpad/rpad/columns/table/wrap | any | Alignment & column/table layout (grouped) |
| tinymux | Softcode-fn | string | edit/replace/strreplace/strinsert/strdelete/delete/insert | any | In-string edit/replace (grouped) |
| tinymux | Softcode-fn | string | pos/posn/lpos/wordpos/strmatch/match/matchall/member/after/before | any | Search/position within string/list (grouped) |
| tinymux | Softcode-fn | string | secure/escape/stripansi/stripaccents/accent/ansi/translate | any | ANSI/accent/escape handling (grouped) |
| tinymux | Softcode-fn | string | regmatch/regmatchi/regrab*/regedit*/reglattr* | any | Regex match/extract/edit (grouped) |
| tinymux | Softcode-fn | string | grab/graball/grep/grepi/regrep(i)/scramble/reverse/revwords | any | Grab/grep/scramble helpers (grouped) |
| tinymux | Softcode-fn | string | soundex/soundlike/strdistance/tr/chr/ord/art/subj/poss/aposs | any | Phonetic, char, pronoun helpers (grouped) |
| tinymux | Softcode-fn | list | words/vdim/wordstart/wordend/isword/elements/index/extract | any | Word/element extraction from list (grouped) |
| tinymux | Softcode-fn | list | sort/sortby/sortkey/strsort/shuffle/revwords | any | List sorting (grouped) |
| tinymux | Softcode-fn | list | ldelete/linsert/lreplace/ledit/lrand/lrest/last/itemize | any | List edit ops (grouped) |
| tinymux | Softcode-fn | list | setunion/setinter/setdiff/strunion/strinter/strdiff/unique/strunique | any | Set operations on lists (grouped) |
| tinymux | Softcode-fn | list | splice/merge/mix/zip/pack/unpack/remove/distribute/choose | any | List combine/split helpers (grouped) |
| tinymux | Softcode-fn | list | lnum/lreplace/wordpos/pickrand/table/columns | any | List generation & tabular output (grouped) |
| tinymux | Softcode-fn | time | time/secs/convsecs/convtime/timefmt/etimefmt/digittime | any | Time formatting & conversion (grouped) |
| tinymux | Softcode-fn | time | ctime/mtime/writetime/singletime/exptime/moon | any | Object timestamps, moon phase (grouped) |
| tinymux | Softcode-fn | info | json/json_query/json_mod/isjson | any | JSON build/query/modify (MUX-distinct) |
| tinymux | Softcode-fn | info | encrypt/decrypt/digest/sha1/hmac/crc32/crc32obj | any | Hash/crypto/checksum (grouped) |
| tinymux | Softcode-fn | info | encode64/decode64/url_escape/url_unescape | any | Encoding helpers |
| tinymux | Softcode-fn | info | die/error/beep/null/t/config/siteinfo | any | Misc control & info primitives |
| tinymux | Softcode-fn | info | sql/mapsql | wizard | Inline SQL query into softcode (build-time option) |
| aresmush | Player | communication | page <name>=<msg> | any | Private message to online player(s) |
| aresmush | Player | communication | page/new, page/reply | any | Start new page thread / reply to last |
| aresmush | Player | communication | page/dnd, page/autospace, page/color | any | Do-not-disturb, spacing, color prefs |
| aresmush | Player | communication | page/scan, page/review | any | Scan unread pages / review history |
| aresmush | Admin | communication | page/report | staff | Report page conversation to staff |
| aresmush | Player | communication | +<channel> <msg> (chat) | any | Talk on a subscribed channel |
| aresmush | Player | channel | channel/join, channel/leave | any | Join or leave a channel |
| aresmush | Player | channel | channel/mute, channel/unmute | any | Mute/unmute a channel |
| aresmush | Player | channel | channel/alias, channel/title | any | Set personal alias/title on channel |
| aresmush | Player | channel | channel (list), channel/who | any | List channels / who is listening |
| aresmush | Player | channel | channel/recall, channel/review | any | Recall recent channel history |
| aresmush | Admin | channel | channel/create, channel/delete | admin | Create/delete a channel |
| aresmush | Admin | channel | channel/desc, channel/rename, channel/color | admin | Configure channel desc/name/color |
| aresmush | Admin | channel | channel/announce, channel/defaultalias | admin | Announce / set default alias |
| aresmush | Admin | channel | channel/joinroles, channel/talkroles | admin | Restrict channel by role |
| aresmush | Admin | channel | channel/addchar, channel/removechar | admin | Force-join/remove a character |
| aresmush | Admin | channel | channel/report, channel/showtitles | admin | Moderation and title display |
| aresmush | Player | scene | pose <text> / :<text> | any | Pose an action in current room |
| aresmush | Player | scene | say <text> / "<text> | any | Speak in current room |
| aresmush | Player | scene | emit <text> / \\<text> | any | Freeform emit to room |
| aresmush | Player | scene | ooc <text> | any | Out-of-character speech |
| aresmush | Player | scene | pose/order, pose/ordertype, pose/nudge | any | Manage pose turn order |
| aresmush | Player | scene | pose/drop | any | Drop out of pose order |
| aresmush | Player | scene | nospoof, autospace, quotecolor | any | Personal scene display prefs |
| aresmush | Player | scene | scene (list), scene <id> | any | List scenes / view scene log |
| aresmush | Player | scene | scene/start, scene/stop, scene/restart | any | Start/stop/restart a scene |
| aresmush | Player | scene | scene/join, scene/leave, scene/invite | any | Join/leave/invite to scene |
| aresmush | Player | scene | scene/addchar, scene/removechar | staff | Add/remove chars from scene |
| aresmush | Player | scene | scene/summary, scene/title, scene/location | any | Edit scene metadata |
| aresmush | Player | scene | scene/type, scene/privacy, scene/icdate, scene/plot | any | Set scene attributes |
| aresmush | Player | scene | scene/share, scene/unshare, scene/report | any | Share scene log / report |
| aresmush | Player | scene | scene/undo, scene/repose, scene/replace (typo) | any | Edit/undo poses in log |
| aresmush | Player | scene | scene/stats, scene/webstart | any | Scene stats / start via web |
| aresmush | GM | scene | emit/gm, emit/set | gm | GM-set pose/emit |
| aresmush | Player | scene | place/join, place/leave, place (list) | any | Join/leave sub-locations (places) |
| aresmush | Player | scene | place/create, place/delete, place/rename | builder | Manage places in a room |
| aresmush | Player | scene | place/emit | any | Emit to a place |
| aresmush | Player | roster | roster (list), roster <name> | any | List rosters / view roster char |
| aresmush | Admin | roster | roster/add, roster/remove | staff | Add/remove char to roster |
| aresmush | Admin | roster | roster/approve, roster/reject | staff | Approve/reject roster claim |
| aresmush | Player | roster | roster/claim | any | Claim a roster character |
| aresmush | Admin | roster | roster/restrict, roster/note, roster/contact | staff | Restrict/annotate roster entries |
| aresmush | Player | profile | profile <name> (finger) | any | View character profile/finger |
| aresmush | Player | profile | profile/add, profile/edit, profile/delete | any | Manage own profile sections |
| aresmush | Player | profile | relationship, relationship/add, /delete, /move | any | Manage character relationships |
| aresmush | Player | profile | backup | any | Download personal character backup |
| aresmush | Player | jobs | request (list), request <id> | any | Player job requests / view |
| aresmush | Player | jobs | request/create, request/new, request/respond | any | Create/respond to a request |
| aresmush | Admin | jobs | job (list), job <id>, job/all | staff | List/view staff jobs |
| aresmush | Admin | jobs | job/create, job/delete, job/close | staff | Create/delete/close a job |
| aresmush | Admin | jobs | job/handle, job/assign | staff | Assign/handle a job |
| aresmush | Admin | jobs | job/discuss, job/respond, job/comment | staff | Comment on a job |
| aresmush | Admin | jobs | job/cat, job/status, job/title | staff | Change category/status/title |
| aresmush | Admin | jobs | job/addparticipant, job/removeparticipant | staff | Manage job participants |
| aresmush | Admin | jobs | job/mail, job/merge, job/filter, job/search | staff | Mail/merge/filter/search jobs |
| aresmush | Admin | jobs | job/subscribe, job/scan, job/unread, job/catchup | staff | Subscription and read tracking |
| aresmush | Admin | jobs | job/createcategory, job/deletecategory, job/renamecategory | admin | Manage job categories |
| aresmush | Admin | jobs | job/categoryroles, job/categorycolor, job/categorytemplate | admin | Configure category settings |
| aresmush | Admin | jobs | job/purge, job/backup | admin | Purge/backup jobs |
| aresmush | Player | bbs | forum (index), forum <cat>/<post> | any | Read forum categories/posts |
| aresmush | Player | bbs | forum/post, forum/reply, forum/editreply | any | Post/reply on forum |
| aresmush | Player | bbs | forum/scan, forum/catchup | any | Scan unread / mark caught up |
| aresmush | Player | bbs | forum/mute, forum/unmute | any | Mute a forum category |
| aresmush | Admin | bbs | forum/createcat, forum/deletecat, forum/rename | staff | Manage forum categories |
| aresmush | Admin | bbs | forum/edit, forum/delete, forum/move, forum/pin | staff | Moderate/organize posts |
| aresmush | Admin | bbs | forum/hide, forum/show, forum/archive, forum/order | staff | Visibility/archive/ordering |
| aresmush | Admin | bbs | forum/readroles, forum/writeroles | admin | Restrict forum access by role |
| aresmush | Player | mail | mail (inbox), mail <id> | any | View mailbox / read message |
| aresmush | Player | mail | mail/send, mail/start, mail/new | any | Compose and send mail |
| aresmush | Player | mail | mail/reply, mail/replyall, mail/fwd | any | Reply/forward mail |
| aresmush | Player | mail | mail/delete, mail/undelete, mail/emptytrash | any | Trash management |
| aresmush | Player | mail | mail/tag, mail/untag, mail/tags, mail/filter | any | Organize with tags/filters |
| aresmush | Player | mail | mail/archive, mail/scan, mail/unsend, mail/sentmail | any | Archive/scan/unsend/sent view |
| aresmush | Player | mail | mail/proof, mail/toss, -<text> (append) | any | Draft proofing and appending |
| aresmush | Admin | mail | mail/report, mail/review, mail/job | staff | Report/review mail; mail-to-job |
| aresmush | Player | chargen | app (view), app/submit, app/unsubmit | any | View/submit character app |
| aresmush | Player | chargen | bg (view), bg/set, bg/edit | any | Manage background text |
| aresmush | Player | chargen | cg/start, cg/next, cg/prev | any | Step through chargen |
| aresmush | Player | chargen | hook (view), hook/set, hook/edit | any | Manage RP hooks |
| aresmush | Admin | chargen | app/approve, app/reject, app/override | staff | Approve/reject/override app |
| aresmush | Admin | chargen | app/unapprove, app/review | staff | Unapprove / review app |
| aresmush | Player | chargen | sheet | any | View character sheet |
| aresmush | Player | chargen | abilities, roll <ability>, roll X vs Y | any | View abilities / dice rolls |
| aresmush | Player | chargen | specialty/add, specialty/remove | any | Manage ability specialties |
| aresmush | Player | chargen | learn <ability> | any | Learn a new ability |
| aresmush | Player | chargen | raise <ability>, lower <ability> | any | Raise/lower ability with XP |
| aresmush | Admin | chargen | ability <char>=<val>, renameability, wipeability | staff | Staff-set/rename/wipe abilities |
| aresmush | Admin | chargen | xp/award, xp/remove, xp/undo, xp (view) | staff | Manage character XP |
| aresmush | Admin | chargen | luck/award, luck/spend, reset | staff | Manage luck / reset sheet |
| aresmush | Admin | chargen | skill/scan | staff | Scan skills across roster |
| aresmush | Player | info | help <topic>, help/quick, beginner | any | Help system and quickref |
| aresmush | Player | info | who, where, whois | any | Online list, locations, whois |
| aresmush | Admin | info | hide, unhide | staff | Hide/show self on who |
| aresmush | Player | info | time, timezone, ictime | any | OOC time, timezone, IC time |
| aresmush | Player | info | census, census/types, demographic, group | any | Demographic stats and groups |
| aresmush | Player | info | age, birthdate | any | View/set character age/birthdate |
| aresmush | Player | info | ranks (list) | any | View rank structure |
| aresmush | Player | info | achievements, achievement <name> | any | View achievements |
| aresmush | Admin | info | achievement/add, achievement/remove, achievement/all | staff | Grant/revoke achievements |
| aresmush | Player | info | friend (list), friend/add, /remove, /note | any | Manage friends list |
| aresmush | Player | info | events (list), event <id>, event/upcoming | any | View scheduled events |
| aresmush | Player | info | event/signup, event/cancel | any | Sign up / cancel for event |
| aresmush | Admin | info | event/create, event/edit, event/delete, event/scene | staff | Manage events |
| aresmush | Player | describe | look, glance, describe, shortdesc | any | Look/describe self and room |
| aresmush | Player | describe | describe/edit, shortdesc/edit, describe/notify | any | Edit descriptions |
| aresmush | Player | describe | detail/set, detail/edit, detail/delete | any | Manage look-details |
| aresmush | Player | describe | vista/set, vista/edit, vista/delete, vista (list) | any | Manage room vistas |
| aresmush | Player | describe | outfit (list/view), outfit/set, /edit, /delete | any | Manage saved outfits |
| aresmush | Player | describe | wear <outfit> | any | Wear a saved outfit |
| aresmush | Builder | building | build <room> | builder | Create a new room |
| aresmush | Builder | building | open <exit>, link, unlink | builder | Create/link/unlink exits |
| aresmush | Builder | building | teleport <target>=<dest> | builder | Teleport to/move objects |
| aresmush | Builder | building | go <exit>, out, home, home/set | any | Movement between rooms |
| aresmush | Builder | building | lock, unlock, lockhere, unlockhere | builder | Lock/unlock rooms/exits |
| aresmush | Builder | building | roomtype, room/icon, room (list) | builder | Room type/icon settings |
| aresmush | Builder | building | area (view), area/create, /update, /delete, /edit | builder | Manage areas |
| aresmush | Builder | building | area/set, area/parent, area/rename, areas (list) | builder | Assign/organize areas |
| aresmush | Builder | building | owner/set, owner/list, work, work/set | builder | Room ownership / work rooms |
| aresmush | Builder | building | exits, grid, foyer, icstart | any | View exits/grid; set entry rooms |
| aresmush | Player | building | meetme, meetme/join, meetme/bring | any | Request/join meetup teleport |
| aresmush | Admin | admin | admin (list), admin/position | admin | Staff roster / position |
| aresmush | Admin | admin | role/assign, role/remove, role/create, role/delete | admin | Manage roles |
| aresmush | Admin | admin | role/addpermission, role/removepermission, role/info | admin | Manage role permissions |
| aresmush | Admin | admin | roles (list), role/all, permissions | admin | List roles/permissions |
| aresmush | Admin | admin | rank/set | admin | Set a character's rank |
| aresmush | Admin | admin | ban, ban/add, ban/remove, ban/list | admin | Manage site/player bans |
| aresmush | Admin | admin | boot | admin | Disconnect a player |
| aresmush | Admin | admin | motd, motd/set, onconnect, onconnect/edit | admin | Message of the day / connect msg |
| aresmush | Admin | admin | notices, notices/catchup, activity, last, watch | staff | Notices, activity, connection logs |
| aresmush | Admin | admin | announce | admin | Global game announcement |
| aresmush | Admin | admin | npc, playerbit, duty, statue, unstatue | staff | NPC control / player flags / freeze |
| aresmush | Admin | admin | idle/set, idle/queue, idle/execute, idle/preview | staff | Idle-sweep (auto-away) management |
| aresmush | Admin | admin | idle/action, idle/gone, idle/dead, idle/reset, lastwill | staff | Idle actions and last-will |
| aresmush | Admin | admin | sweep, sweep/kick | staff | Sweep idle players from room |
| aresmush | Player | status | afk, offstage, onstage | any | Set AFK / on-off stage status |
| aresmush | Admin | admin | examine <obj>, find, findsite, rename | admin | Inspect/find/rename DB objects |
| aresmush | Admin | admin | destroy, destroy/confirm | admin | Destroy a DB object |
| aresmush | Admin | admin | ruby <code> | admin | Execute arbitrary Ruby (superadmin) |
| aresmush | Admin | admin | config (list/view), config/check, config/cron, config/restore | admin | View/manage game config |
| aresmush | Admin | admin | load, load config/locale/all/styles, reload plugin | admin | Reload config/plugins/locales |
| aresmush | Admin | admin | plugin/install, plugins (list), theme, migrate | admin | Install plugins/themes; migrations |
| aresmush | Admin | admin | git, git/load, upgrade, upgrade/finish | admin | Git pull / version upgrade |
| aresmush | Admin | admin | db/backup, db/save, debuglog, server, version | admin | Backups, debug log, server info |
| aresmush | Admin | admin | shutdown, block, block/add, block/remove | admin | Shutdown; block sites |
| aresmush | Player | login | connect <name>, create <name>=<pw>, quit | guest | Connect, create account, disconnect |
| aresmush | Player | login | create/reserve, tos, tos/agree, tos/reset | any | Reserve name; terms-of-service |
| aresmush | Player | login | password/set, password/reset, email, email/set | any | Manage password/email |
| aresmush | Player | login | keepalive, alias, tour | any | Session keepalive; command aliases |
| aresmush | Player | utils | dice, math, color, colors, ascii, emoji, beep | any | Utility/formatting helpers |
| aresmush | Player | utils | notes, note/set, note/edit, save, recall | any | Personal notes; save; recall output |
| aresmush | Player | utils | screenreader, echo, shortcuts, shortcut/add, /delete | any | Accessibility; command shortcuts |
| aresmush | Player | utils | tinker | any | FS3 crafting/tinker interface |
| aresmush | Admin | admin | website, website/deploy, website/export | admin | Manage/deploy game website |
| evennia | Builder | building | `@dig roomname;alias = exit,exit` | builder | Create a new room plus optional two-way exits |
| evennia | Builder | building | `@tunnel n = room` (`@tun`) | builder | Dig a room in a cardinal/compass direction |
| evennia | Builder | building | `@open exit = room` | builder | Create an exit from current room to a destination |
| evennia | Builder | building | `@link exit = dest` | builder | Link/relink an exit or object's destination |
| evennia | Builder | building | `unlink exit` | builder | Remove an exit's destination link |
| evennia | Builder | building | `@sethome obj = room` | builder | Set an object's home location |
| evennia | Builder | object | `@create name:typeclass` | builder | Create a new object in inventory |
| evennia | Builder | object | `@copy obj = newname` | builder | Duplicate an existing object |
| evennia | Builder | object | `@cpattr obj/attr = obj/attr` | builder | Copy an attribute between objects |
| evennia | Builder | object | `@mvattr obj/attr = obj/attr` | builder | Move (copy+delete) an attribute |
| evennia | Builder | object | `@desc [obj =] text` | builder | Set an object's description |
| evennia | Builder | object | `@destroy obj` (`@del`) | builder | Permanently delete object(s) |
| evennia | Builder | object | `@name obj = newname` (`@rename`) | builder | Rename an object and set aliases |
| evennia | Builder | object | `@alias obj = a,b` | builder | Manage an object's aliases |
| evennia | Builder | object | `@set obj/attr = value` | builder | Set/delete an attribute on an object |
| evennia | Builder | object | `@lock obj = lockstring` (`@locks`) | builder | View or set access locks on an object |
| evennia | Builder | object | `@wipe obj[/attr]` | builder | Clear all or named attributes |
| evennia | Builder | object | `@typeclass obj = path` (`@type/@swap/@update`) | builder | Change or reload an object's typeclass |
| evennia | Builder | object | `@cmdsets obj` | builder | List cmdsets active on an object |
| evennia | Builder | object | `@tag obj = tag[:category]` (`@tags`) | builder | Add/list/remove object tags |
| evennia | OLC | building | `@spawn prototype` (`@olc`) | builder | Spawn object from prototype / open OLC menu |
| evennia | Builder | info | `@examine obj` (`@ex/@exam`) | builder | Inspect object attrs, locks, cmdsets |
| evennia | Builder | info | `@find name/#dbref` (`@search/@locate`) | builder | Search objects by name or dbref range |
| evennia | Builder | info | `@objects` | builder | Show object DB stats and type counts |
| evennia | Builder | info | `@scripts [obj]` (`@script`) | builder | List/stop/start scripts |
| evennia | Builder | building | `@teleport obj = dest` (`@tel`) | builder | Move object to another location |
| evennia | Player | general | `home` | any | Teleport self to home location |
| evennia | Player | info | `look [obj]` (`l`, `ls`) | any | Look at room or an object |
| evennia | Player | general | `nick pattern = replace` (`nicks`) | any | Personal input/alias substitutions |
| evennia | Player | object | `inventory` (`inv`, `i`) | any | List carried items |
| evennia | Player | object | `get obj` (`grab`) | any | Pick up an object |
| evennia | Player | object | `drop obj` | any | Drop a carried object |
| evennia | Player | object | `give obj = target` | any | Give a carried object to someone |
| evennia | Player | general | `setdesc text` | any | Set your own character description |
| evennia | Player | comm | `say text` (`"`, `'`) | any | Speak aloud in the room |
| evennia | Player | comm | `whisper target = text` | any | Whisper privately to someone in room |
| evennia | Player | comm | `pose text` (`:`, `emote`) | any | Emote an action to the room |
| evennia | Player | info | `access` (`groups`, `hierarchy`) | any | Show your permission groups/hierarchy |
| evennia | Player | channel | `@channel[/switch] name = msg` (`@chan`) | any | Use/create/admin/sub channels (many switches) |
| evennia | Player | comm | `page target = msg` (`tell`) | any | Send private cross-room message |
| evennia | Admin | channel | `irc2chan chan = irc` | admin/developer | Bridge a channel to IRC |
| evennia | Admin | channel | `ircstatus` | admin/developer | Show/manage IRC bridge connections |
| evennia | Admin | channel | `rss2chan chan = url` | admin/developer | Bridge an RSS feed to a channel |
| evennia | Admin | channel | `grapevine2chan chan = ch` | admin/developer | Bridge channel to Grapevine network |
| evennia | Admin | channel | `discord2chan` (`discord`) | admin/developer | Bridge a channel to Discord |
| evennia | Player | account | `look` (OOC) (`l`, `ls`) | any | OOC look at account/character menu |
| evennia | Player | account | `charcreate name = desc` | any | Create a new playable character |
| evennia | Player | account | `chardelete name` | any | Delete one of your characters |
| evennia | Player | account | `ic [char]` (`puppet`) | any | Puppet/go in-character as a character |
| evennia | Player | account | `ooc` (`unpuppet`) | any | Return to OOC account menu |
| evennia | Player | account | `sessions` | any | List your active connected sessions |
| evennia | Player | info | `who` (`doing`) | any | List online players (admins see more) |
| evennia | Player | account | `option [name = val]` (`options`) | any | View/set session client options |
| evennia | Player | account | `password old = new` | any | Change your account password |
| evennia | Player | account | `quit` | any | Disconnect this or all sessions |
| evennia | Player | account | `color [ansi/xterm]` | any | Show ANSI/xterm color test tables |
| evennia | Player | account | `quell` (`unquell`) | any | Suppress account perms to char perms |
| evennia | Player | account | `style [name = val]` | any | View/set per-account display styling |
| evennia | Admin | admin | `boot account` | admin/developer | Disconnect a player/session |
| evennia | Admin | admin | `ban [name/ip]` (`bans`) | admin/developer | Ban a name or IP; list bans |
| evennia | Admin | admin | `unban entry` | admin/developer | Remove a ban by id |
| evennia | Admin | admin | `emit text` (`pemit/remit`) | admin/developer | Broadcast raw text to room/object |
| evennia | Admin | admin | `userpassword account = pw` | admin/developer | Set another account's password |
| evennia | Admin | admin | `perm obj = perm` (`setperm`) | admin/developer | Grant/revoke permissions on account/obj |
| evennia | Admin | admin | `wall msg` | admin/developer | Announce message to all players |
| evennia | Admin | admin | `force obj = command` | admin/developer | Force an object to execute a command |
| evennia | Admin | system | `@reload` (`@restart`) | admin/developer | Warm-reload the server, keep sessions |
| evennia | Admin | system | `@reset` | admin/developer | Reload with cold-boot hooks fired |
| evennia | Admin | system | `@shutdown` | admin/developer | Stop the entire server |
| evennia | Admin | system | `@py code` (`@!`) | admin/developer | Execute arbitrary Python (superuser) |
| evennia | Admin | system | `@accounts` (`@account`) | admin/developer | List/manage account database |
| evennia | Admin | system | `@service [start/stop]` (`@services`) | admin/developer | Control Twisted services |
| evennia | Admin | system | `@about` (`@version`) | admin/developer | Show server version/credits |
| evennia | Admin | system | `@time` (`@uptime`) | admin/developer | Show server time and uptime |
| evennia | Admin | system | `@server` (`@serverload`) | admin/developer | Show server load/memory stats |
| evennia | Admin | system | `@tickers` | admin/developer | List active TickerHandler subscriptions |
| evennia | Admin | system | `@tasks` (`@delays/@task`) | admin/developer | List/manage scheduled delay tasks |
| evennia | Admin | system | `batchcommands file` (`batchcmd`) | admin/developer | Run a batch command build file |
| evennia | Admin | system | `batchcode file` | admin/developer | Run a batch Python build file |
| evennia | Softcode-fn | funcparser | `$eval(expr)` | any | Safe-eval arithmetic/string expression |
| evennia | Softcode-fn | funcparser | `$add/$sub/$mult/$div(a,b)` | any | Arithmetic on two operands |
| evennia | Softcode-fn | funcparser | `$round(n,dec)` | any | Round a number |
| evennia | Softcode-fn | funcparser | `$toint(n)` | any | Truncate/convert value to integer |
| evennia | Softcode-fn | funcparser | `$int2str(n)` | any | Spell small integers as words |
| evennia | Softcode-fn | funcparser | `$an(word)` | any | Prefix a/an per following word |
| evennia | Softcode-fn | funcparser | `$random([min,max])` | any | Random int or float |
| evennia | Softcode-fn | funcparser | `$randint(min,max)` | any | Random integer in range |
| evennia | Softcode-fn | funcparser | `$choice(a,b,c)` | any | Pick a random argument |
| evennia | Softcode-fn | funcparser | `$pad(text,width,align,fill)` | any | Pad text to width |
| evennia | Softcode-fn | funcparser | `$crop(text,width)` | any | Crop text with ellipsis |
| evennia | Softcode-fn | funcparser | `$just/$ljust/$rjust/$cjust(text,w)` | any | Justify text (left/right/center) |
| evennia | Softcode-fn | funcparser | `$space(n)` | any | Insert n spaces |
| evennia | Softcode-fn | funcparser | `$clr(col,text)` | any | Wrap text in a color code |
| evennia | Softcode-fn | funcparser | `$pluralize(word,n,plural)` | any | Pluralize word by count |
| evennia | Softcode-fn | funcparser | `$search(query)` (`$obj`,`$dbref`) | builder | Search/resolve an object (needs caller) |
| evennia | Softcode-fn | funcparser | `$objlist(query)` | builder | Search returning a list of objects |
| evennia | Softcode-fn | funcparser | `$you([key])` (`$You`,`$obj`) | any | Actor-stance "you"/name substitution |
| evennia | Softcode-fn | funcparser | `$your([key])` (`$Your`) | any | Actor-stance possessive substitution |
| evennia | Softcode-fn | funcparser | `$conj(verb)` | any | Conjugate verb for actor vs observer |
| evennia | Softcode-fn | funcparser | `$pconj(verb)` | any | Conjugate verb agreeing with pronoun |
| evennia | Softcode-fn | funcparser | `$pron(pronoun[,opts])` (`$Pron`) | any | Map/render a pronoun by viewer |
| coffeemud | OLC | building | `CREATE <type> ...` | builder | Master builder verb; type = ROOM/MOB/ITEM/EXIT/AREA/RACE/CLASS/ABILITY/ACHIEVEMENT/CRON/RECIPE/HELP |
| coffeemud | OLC | building | `MODIFY|MOD <type> <name>` | builder | Opens genEd prompt editor for any created type's stats |
| coffeemud | OLC | building | `DESTROY|JUNK|TEAR <type> <name>` | builder | Permanently remove room/mob/item/exit/area/etc |
| coffeemud | OLC | room | `CREATE ROOM <dir> <id>` | builder | Make a new room and link an exit in a direction |
| coffeemud | OLC | room | `MODIFY ROOM` | builder | Edit title, desc, climate, terrain, affects, behaviors, scripts |
| coffeemud | OLC | room | `DIG <dir> <roomID> [dir back]` | builder | Create room + two-way exit in one step |
| coffeemud | OLC | room | `LINK <dir>=<roomID>` / `UNLINK <dir>` | builder | Attach or detach an exit's destination |
| coffeemud | OLC | room | `RESET ROOM|AREA` | builder | Force area/room re-population from blueprint |
| coffeemud | OLC | mobile | `CREATE MOB <name>` / `MODIFY MOB` | builder | Make/edit an NPC; set stats, class, race, level, behaviors, scripts, shop |
| coffeemud | OLC | object | `CREATE ITEM <name>` / `MODIFY ITEM` | builder | Make/edit item; type, material, wear, affects, spell props, enchant |
| coffeemud | OLC | object | `RESTRING <item> <name>=<desc>` | builder | Rename/redescribe an existing item instance |
| coffeemud | OLC | object | `COPY <object>` | builder | Duplicate a room/mob/item to inventory or here |
| coffeemud | OLC | area | `CREATE AREA <name>` / `MODIFY AREA` | builder | Make/edit an area; author, climate, theme, blurbs, subops |
| coffeemud | OLC | area | `EXPORT <area> [file]` / `IMPORT <file>` | archon/admin | Dump/load area as CoffeeMud XML |
| coffeemud | OLC | area | `PACKAGE <area>` | archon/admin | Bundle area + resources into distributable file |
| coffeemud | OLC | area | `GENERATE <spec>` | builder | Procedurally generate rooms/mobs/items from a def file |
| coffeemud | OLC | area | `TEMPLATE <type>` | builder | Manage reusable object templates |
| coffeemud | OLC | building | `XML <object>` | builder | View/edit raw XML representation of an object |
| coffeemud | OLC | building | `MERGE` | builder | Merge duplicate/room data |
| coffeemud | Builder | room | `GOTO <room|mob|player>` | builder | Teleport self to a room, mob, or player |
| coffeemud | Builder | room | `AT <place> <cmd>` | builder | Execute a command as if standing in another location |
| coffeemud | Builder | mobile | `TRANSFER <who> [to]` | builder | Move mob/player to you or a target room |
| coffeemud | Builder | mobile | `POSSESS <mob>` | archon/admin | Take direct control of an NPC body |
| coffeemud | Builder | mobile | `SWITCH <mob>` | archon/admin | Become/puppet a mob temporarily |
| coffeemud | Builder | mobile | `AS <who> <cmd>` | archon/admin | Force-run a command in another's context |
| coffeemud | Builder | building | `SET <field> ...` | archon/admin | Set player/account/room/global data fields |
| coffeemud | Builder | info | `STAT <object>` | builder | Dump internal stats/variables of any object |
| coffeemud | Builder | building | `LOAD <class|resource>` / `UNLOAD` | archon/admin | Load/unload Java classes, INI, resources at runtime |
| coffeemud | Builder | building | `SAVE` | builder | Persist current room/area/object changes |
| coffeemud | Builder | mobile | `PURGE <mob>` / `NOPURGE` | builder | Delete NPCs in room; flag player against purge |
| coffeemud | Builder | building | `POOF <in>=<out>` | builder | Set custom teleport entry/exit messages |
| coffeemud | Builder | building | `AFTER <t> <cmd>` / `EVERY <t> <cmd>` / `PAUSE` | builder | Deferred / repeating command scheduling |
| coffeemud | Builder | building | `RESET` / `EXPIRE` | builder | Reset or expire timed content |
| coffeemud | Builder | scripting | `MPRUN <script>` | builder | Run a raw MOBprog script line immediately |
| coffeemud | Builder | scripting | `MPCOMMAND <fn>(...)` | builder | Invoke a single scriptable command/function directly |
| coffeemud | Builder | scripting | `GENCOMMAND <spec>` | builder | Define/run a generic scriptable command |
| coffeemud | Builder | scripting | `GMODIFY` / `GCONSIDER` | builder | Bulk-modify / evaluate objects by mask query |
| coffeemud | Admin | admin | `SHUTDOWN` / `REBOOT`-via-config | archon/admin | Stop or restart the MUD |
| coffeemud | Admin | admin | `BOOT <player>` / `BAN <who>` | archon/admin | Disconnect / ban a player or host |
| coffeemud | Admin | admin | `ANNOUNCE <msg>` / `SYSMSGS` | archon/admin | Broadcast; toggle system message feed |
| coffeemud | Admin | admin | `CONFIG <flag>` | archon/admin | View/set runtime config and security flags |
| coffeemud | Admin | admin | `SNOOP <player>` | archon/admin | Watch another player's I/O stream |
| coffeemud | Admin | admin | `WIZLIST` / `WIZINV` / `WIZEMOTE` | archon/admin | Staff roster; invisibility; staff-only emote |
| coffeemud | Admin | admin | `PROXYCTL` | archon/admin | Manage proxy/bot player connections |
| coffeemud | Admin | admin | `TICKTOCK` / `POLLCMD` / `DEFER` | archon/admin | Inspect tick engine; polls; deferred command queue |
| coffeemud | Admin | admin | `CATALOG <obj>` | builder | Manage the shared prototype catalog of mobs/items |
| coffeemud | Admin | admin | `COMMANDJOURNAL` / `TEST` / `TYPECMD` | archon/admin | Command-journal boards; run tests; type registry |
| coffeemud | Admin | admin | `JCONSOLE` / `JRUN` / `SHELL` / `LLM` | archon/admin | JavaScript console; OS shell; LLM integration |
| coffeemud | Admin | admin | `MOTD` / `RULES` / `AHELP` | archon/admin | Edit message-of-day, rules, archon help |
| coffeemud | Player | comm | `SAY` / `TELL` / `REPLY` / `WHISPER` / `YELL` / `SHOUT` | any | Local, private, room and area speech |
| coffeemud | Player | comm | `EMOTE` / `POSE` / `<social>` | any | Freeform emote; socials via SocialsCmd table |
| coffeemud | Player | comm | `CHANNEL` / `CHANNELS` / `NOCHANNEL` / `CHANWHO` | any | Speak on / list / mute / list-listeners of chat channels |
| coffeemud | Player | comm | `GROUP` / `GTELL` / `ORDER` / `FOLLOW` | any | Party management, group chat, order followers |
| coffeemud | Player | comm | `EMAIL` / `HISTORY` / `REPLAY` / `SUBSCRIBE` | any | Player mail; channel history/replay; mailing lists |
| coffeemud | Player | comm | `GRAPEVINE` / `I3CMD` / `IMC2` | any | Inter-MUD chat networks (representative) |
| coffeemud | Player | comm | `CLAN*` (`CLANCREATE`,`CLANWHO`,`CLANTAX`,...) | any | ~40 clan/guild governance verbs (represented as a group) |
| coffeemud | Player | info | `LOOK` / `EXAMINE` / `EXITS` / `READ` | any | Inspect room, object detail, exits, writing |
| coffeemud | Player | info | `SCORE` / `INVENTORY` / `EQUIPMENT` / `WEALTH` | any | Character sheet, carried items, worn gear, money |
| coffeemud | Player | info | `WHO` / `WHOIS` / `WHERE` / `FRIENDS` | any | Online list, player profile, locate, friend list |
| coffeemud | Player | info | `AREAS` / `WEATHER` / `TIME` / `CALENDAR` | any | World gazetteer, weather, game clock/calendar |
| coffeemud | Player | info | `CONSIDER` / `COMPARE` / `VALUE` / `WORTH` | any | Assess foe difficulty; compare items; appraise value |
| coffeemud | Player | info | `HELP` / `TOPICS` / `COMMANDS` / `CREDITS` | any | Help system, topic index, command list |
| coffeemud | Player | info | `EXPERIENCE` / `ACHIEVEMENTS` / `DEITIES` / `FACTIONLIST` | any | XP detail, achievements, gods, faction standings |
| coffeemud | Player | object | `GET` / `DROP` / `PUT` / `GIVE` / `TAKE` | any | Move items between room, container, inventory, others |
| coffeemud | Player | object | `WEAR` / `WIELD` / `HOLD` / `REMOVE` / `SHEATH` / `DRAW` | any | Equip/unequip items and weapons to slots |
| coffeemud | Player | object | `OPEN` / `CLOSE` / `LOCK` / `UNLOCK` / `KNOCK` | any | Operate doors, containers, locks |
| coffeemud | Player | object | `FILL` / `EMPTY` / `POUR` / `EAT` / `DRINK` / `FEED` | any | Liquid containers, consumption |
| coffeemud | Player | object | `DRESS` / `UNDRESS` / `OUTFIT` / `CLOAK` | any | Bulk equip helpers; conceal worn items |
| coffeemud | Player | economy | `BUY` / `SELL` / `LIST` / `BORROW` / `PAY` | any | Shopkeeper trade and services |
| coffeemud | Player | economy | `AUCTION` / `BID` | any | Player auction house |
| coffeemud | Player | economy | `DEPOSIT` / `WITHDRAW` / `SPLIT` / `HIRE` | any | Banking, share coins, hire NPCs |
| coffeemud | Player | ability | `SKILLS` / `ABILITIES` / `SPELLS` / `PRAYERS` / `SONGS` / `CHANTS` / `POWERS` | any | List known abilities by category (generic view commands) |
| coffeemud | Player | ability | `<ability command word> [targets]` | any | Abilities self-register verbs (e.g. cast, backstab); ~500 abilities, invoked directly |
| coffeemud | Player | ability | `PRACTICE` / `LEARN` / `TRAIN` / `GAIN` / `TEACH` | any | Improve proficiency, learn skills, spend train/prac points |
| coffeemud | Player | ability | `QUALIFY` / `WILLQUALIFY` / `EXPERTISES` / `REMORT` / `RETIRE` | any | Check/advance class progression, expertises, remort |
| coffeemud | Player | ability | `ACTIVATE` / `DEACTIVATE` / `AUTOINVOKE` | any | Toggle sustained/auto abilities |
| coffeemud | Player | ability | `KILL` / `ASSIST` / `FLEE` / `WIMPY` / `DUEL` / `PLAYERKILL` | any | Initiate combat, help ally, retreat, PvP (combat represented generically) |
| coffeemud | Player | info | `TITLE` / `DESCRIPTION` / `MOOD` / `PASSWORD` | any | Set own title, self-desc, mood, password |
| coffeemud | Player | info | `BRIEF` / `PROMPT` / `ANSI` / `COLORSET` / `AFK` / `ALIAS` | any | Client/display preferences and command aliases |
| coffeemud | Player | info | `AUTO*` (`AUTOLOOT`,`AUTOEXITS`,`AUTOATTACK`,...) | any | ~30 per-player automation toggles (grouped) |
| coffeemud | Player | comm | `QUIT` / `LOGOFF` / `SAVE` / `IGNORE` / `QUIET` | any | Session control and filtering |
| coffeemud | Player | mobile | movement (`N/S/E/W/U/D`, `ENTER`,`LEAVE`,`CLIMB`,`CRAWL`,`GO`,`FLEE`) | any | Per-direction movement (compressed) |
| coffeemud | Player | mobile | `SIT` / `STAND` / `SLEEP` / `WAKE` / `MOUNT` / `DISMOUNT` / `FORMATION` | any | Posture, rest, riding, party formation |
| coffeemud | Softcode-fn | scripting | trigger `*_PROG` (61) | script | Event triggers on scripted mob/item/room; see grouped rows below |
| coffeemud | Softcode-fn | scripting | `GREET_PROG` / `ALL_GREET_PROG` / `GROUP_GREET_PROG` / `ENTRY_PROG` / `EXIT_PROG` / `ARRIVE_PROG` | script | Fire on mobs entering/leaving/being greeted |
| coffeemud | Softcode-fn | scripting | `SPEECH_PROG` / `SPEAK_PROG` / `SOCIAL_PROG` / `CHANNEL_PROG` | script | Fire on speech, matched keywords, socials, channels |
| coffeemud | Softcode-fn | scripting | `FIGHT_PROG` / `HITPRCNT_PROG` / `DEATH_PROG` / `KILL_PROG` / `DAMAGE_PROG` | script | Combat lifecycle triggers |
| coffeemud | Softcode-fn | scripting | `GIVE_PROG` / `GET_PROG` / `DROP_PROG` / `PUT_PROG` / `BUY_PROG` / `SELL_PROG` / `BRIBE_PROG` | script | Item transfer & shop triggers |
| coffeemud | Softcode-fn | scripting | `WEAR_PROG` / `REMOVE_PROG` / `CONSUME_PROG` / `OPEN_PROG` / `CLOSE_PROG` / `LOCK_PROG` / `UNLOCK_PROG` | script | Item/portal usage triggers |
| coffeemud | Softcode-fn | scripting | `RAND_PROG` / `ONCE_PROG` / `DELAY_PROG` / `TIME_PROG` / `DAY_PROG` / `AGE_PROG` / `QUEST_TIME_PROG` | script | Random/timed/scheduled triggers |
| coffeemud | Softcode-fn | scripting | `LOGIN_PROG` / `LOGOFF_PROG` / `LEVEL_PROG` / `CAST_PROG` / `LOOK_PROG` / `MASK_PROG` / `FUNCTION_PROG` | script | Player-state, casting, look, mask-gated, callable-fn triggers |
| coffeemud | Softcode-fn | scripting | function `RAND(n)`,`ISODD`,`NUMBER`,`RANDNUM`,`MATH`,`EVAL` | script | Numeric/logic condition functions |
| coffeemud | Softcode-fn | scripting | `ISNPC`,`ISPC`,`ISGOOD`,`ISEVIL`,`ISFIGHT`,`ISIMMORT`,`ISCHARMED`,`ISALIVE`,`ISPKILL` | script | Actor boolean checks |
| coffeemud | Softcode-fn | scripting | `HAS`,`WORN`,`WORNON`,`AFFECTED`,`ISABLE`,`ISBEHAVE`,`HASTITLE`,`HASTATTOO`,`HASTAG`,`EXPERTISE` | script | Possession/state/capability checks |
| coffeemud | Softcode-fn | scripting | `STAT`,`GSTAT`,`LEVEL`,`SEX`,`CLASS`,`BASECLASS`,`RACE`,`RACECAT`,`POSITION`,`MOOD`,`DEITY` | script | Read actor attributes |
| coffeemud | Softcode-fn | scripting | `VAR`,`QVAR`,`GSTAT`,`CLANDATA`,`FACTION`,`EXP`,`GOLDAMT`,`QUESTPOINTS`,`TRAINS`,`PRACS` | script | Read script/quest/economy variables |
| coffeemud | Softcode-fn | scripting | `INROOM`,`ISHERE`,`INAREA`,`INLOCALE`,`INCONTAINER`,`CANSEE`,`CANHEAR`,`ISRECALL`,`EXPLORED` | script | Location & perception checks |
| coffeemud | Softcode-fn | scripting | `NUMMOBS*`,`NUMITEMS*`,`NUMPCS*`,`NUMRACES*`,`ROOMMOB`,`ROOMITEM`,`SHOPITEM`,`ITEMCOUNT` | script | Population/inventory counting & selection |
| coffeemud | Softcode-fn | scripting | `ISTIME`,`ISDAY`,`ISSEASON`,`ISWEATHER`,`ISMOON`,`ISHOUR`,`ISMONTH`,`ISYEAR`,`ISRL*`,`DATETIME` | script | Game/real time & environment checks |
| coffeemud | Softcode-fn | scripting | `QUEST*` (`QUESTWINNER`,`QUESTMOB`,`QUESTOBJ`,`QUESTROOM`,`QUESTAREA`,`ISQUESTMOBALIVE`) | script | Quest state functions |
| coffeemud | Softcode-fn | scripting | `NAME`,`STRIN`,`STRCONTAINS`,`ISLIKE`,`CALLFUNC`,`VALUE`,`CURRENCY`,`IPADDRESS` | script | String/util/misc functions |
| coffeemud | Softcode-fn | scripting | command `IF`/`ELSE`/`ENDIF`, `WHILE`, `FOR`/`NEXT`, `SWITCH`/`CASE`/`DEFAULT`, `BREAK`, `RETURN` | script | Control-flow statements |
| coffeemud | Softcode-fn | scripting | `MPSETVAR`/`MPGSET`/`MPQSET`/`MPARGSET`/`MPSAVEVAR`/`MPLOADVAR`/`MPSETINTERNAL` | script | Set/persist script, global, quest, arg variables |
| coffeemud | Softcode-fn | scripting | `MPECHO`/`MPECHOAT`/`MPECHOAROUND`/`MPASOUND`/`MPSPEAK`/`MPPROMPT`/`MPCONFIRM`/`MPCHOOSE`/`MPLOG` | script | Output text to actors/rooms; prompt input; log |
| coffeemud | Softcode-fn | scripting | `MPMLOAD`/`MPOLOAD`/`MPOLOADROOM`/`MPOLOADSHOP`/`MPMLOADSHOP`/`MPRLOAD`/`MPRESET`/`MPPURGE`/`MPJUNK` | script | Spawn mobs/items/rooms; reset; destroy |
| coffeemud | Softcode-fn | scripting | `MPKILL`/`MPHIT`/`MPHEAL`/`MPDAMAGE`/`MPSLAY`/`MPCAST`/`MPCASTEXT`/`MPREJUV`/`MPACCUSE` | script | Combat/heal/cast script actions |
| coffeemud | Softcode-fn | scripting | `MPGOTO`/`MPAT`/`MPTRANSFER`/`MPWALKTO`/`MPTRACKTO`/`MPFORCE`/`MPPOSSESS`/`MPHIDE`/`MPUNHIDE` | script | Movement, remote-exec, force commands |
| coffeemud | Softcode-fn | scripting | `MPSET`/`MPTITLE`/`MPTATTOO`/`MPACCTATTOO`/`MPAFFECT`/`MPUNAFFECT`/`MPBEHAVE`/`MPUNBEHAVE`/`MPEXP`/`MPRPEXP`/`MPTRAINS`/`MPPRACS` | script | Modify actor stats, tattoos, affects, behaviors, progression |
| coffeemud | Softcode-fn | scripting | `MPSTARTQUEST`/`MPENDQUEST`/`MPSTEPQUEST`/`MPQUESTWIN`/`MPQUESTPOINTS`/`MPLOADQUESTOBJ` | script | Quest lifecycle control |
| coffeemud | Softcode-fn | scripting | `MPOPEN`/`MPCLOSE`/`MPLOCK`/`MPUNLOCK`/`MPLINK`/`MPUNLINK`/`MPPUT` | script | Manipulate doors/exits/containers |
| coffeemud | Softcode-fn | scripting | `MPFACTION`/`MPSETCLAN`/`MPSETCLANDATA`/`MPMONEY`/`MPCHANNEL`/`MPACHIEVE`/`MPPLAYERCLASS` | script | Faction, clan, economy, channel, achievement, class actions |
| coffeemud | Softcode-fn | scripting | `MPALARM`/`MPBEACON`/`MPNOTRIGGER`/`MPSTOP`/`MPENABLE`/`MPDISABLE`/`MPSCRIPT`/`MPUNLOADSCRIPT`/`MPCALLFUNC`/`<SCRIPT>...` | script | Scheduling, trigger control, embed JavaScript, call sub-fns |
| coffeemud | Softcode-fn | scripting | vars `$i/$I` self, `$n/$N` source, `$t/$T` target, `$o/$O`,`$p/$P` items, `$q/$Q` scripted | script | Actor/item name & display substitutions |
| coffeemud | Softcode-fn | scripting | vars `$e/$s/$m/$k` pronouns, `$r/$R`,`$c/$C` random PC/anyone, `$a/$b`,`$d/$D` area/room, `$x/$X` exits | script | Pronoun, random-actor, location, direction substitutions |
| coffeemud | Softcode-fn | scripting | vars `$<obj var>`, `$[n quest]` item, `${n quest}` mob, `$%func%`, `$0-$9` args, `$@x` arg-item | script | Named vars, quest-item/mob refs, inline function eval, positional args |
| smaug | OLC | room | `redit <field>` | builder | Room editor; dispatches to sub-fields below |
| smaug | OLC | room | `redit name <text>` | builder | Set room title |
| smaug | OLC | room | `redit desc` | builder | Enter room description editor |
| smaug | OLC | room | `redit exit <dir> [vnum]` | builder | Create/edit an exit |
| smaug | OLC | room | `redit bexit <dir>` | builder | Create bidirectional exit |
| smaug | OLC | room | `redit exname/exdesc/exkey/exflags` | builder | Exit keyword, desc, key vnum, flags |
| smaug | OLC | room | `redit exdistance` | builder | Overland exit distance |
| smaug | OLC | room | `redit flags <bits>` | builder | Toggle room flags |
| smaug | OLC | room | `redit sector <type>` | builder | Set terrain sector type |
| smaug | OLC | room | `redit tunnel <n>` | builder | Max occupants allowed |
| smaug | OLC | room | `redit teledelay/televnum` | builder | Teleport delay and target vnum |
| smaug | OLC | room | `redit pull/push/pulltype/pushtype` | builder | Current/drift movement effects |
| smaug | OLC | room | `redit maxweight <n>` | builder | Room weight capacity |
| smaug | OLC | room | `redit affect/permaffect/indexaffect` | builder | Add room stat affects |
| smaug | OLC | room | `redit ed <kw>` | builder | Add extra (look) description |
| smaug | OLC | room | `redit rmaffect/rmed/rmindexaffect/off` | builder | Remove affects/edesc/exit |
| smaug | OLC | room | `rset <field> <val>` | builder | Set room field non-interactively |
| smaug | OLC | room | `rdig <dir> <vnum>` | builder | Create and link a new room |
| smaug | Builder | room | `rlist [range]` | builder | List room vnums in area |
| smaug | Builder | room | `rstat` | builder | Show room internals/flags |
| smaug | OLC | mobile | `mset <mob> <field> <v>` | builder | Mob editor (fields below) |
| smaug | OLC | mobile | `mset ... level/str..wis/hp/mana/move` | builder | Core stats and attributes |
| smaug | OLC | mobile | `mset ... race/class/sex/pos/defpos` | builder | Race, class, sex, positions |
| smaug | OLC | mobile | `mset ... align/gold/practice/qp` | builder | Alignment, gold, prac, quest pts |
| smaug | OLC | mobile | `mset ... hitroll/damroll/damdie/hitdie` | builder | Attack/damage dice and rolls |
| smaug | OLC | mobile | `mset ... armor/numattacks/attack/defense` | builder | AC, attack count, special attks |
| smaug | OLC | mobile | `mset ... flags/affected/immune/resistant/susceptible` | builder | Act/affect/RIS bitvectors |
| smaug | OLC | mobile | `mset ... part/sav1..5/spec_fun` | builder | Body parts, saves, special program |
| smaug | OLC | mobile | `mset ... name/short/long/description` | builder | Keywords and descriptions |
| smaug | OLC | mobile | `mset ... speaking/speaks/spec/rank` | builder | Languages, spec, rank |
| smaug | OLC | mobile | `mcreate <vnum> <name>` | builder | Create new mob prototype |
| smaug | OLC | mobile | `mdelete <vnum>` | builder | Delete mob prototype |
| smaug | Builder | mobile | `mlist [range]` | builder | List mob vnums in area |
| smaug | Builder | mobile | `mstat <mob>` | builder | Show mob internals |
| smaug | Builder | mobile | `mfind <name>` | builder | Search mob prototypes |
| smaug | OLC | object | `oset <obj> <field> <v>` | builder | Object editor (fields below) |
| smaug | OLC | object | `oset ... type/wear/flags/cflags` | builder | Item type, wear loc, extra/cont flags |
| smaug | OLC | object | `oset ... value0..5 (v0..v5)` | builder | Type-specific value slots |
| smaug | OLC | object | `oset ... weight/cost/level/rent/condition` | builder | Physical/economic attributes |
| smaug | OLC | object | `oset ... affect/apply/ac/layers` | builder | Stat affects, armor, layering |
| smaug | OLC | object | `oset ... spell1..3/charges/maxcharges/slevel` | builder | Wand/staff spells and charges |
| smaug | OLC | object | `oset ... doses/timer/delay/weapontype` | builder | Pill doses, decay timer, weapon type |
| smaug | OLC | object | `oset ... trapflags/tflags/key` | builder | Trap flags, container key |
| smaug | OLC | object | `oset ... name/short/long/actiondesc/ed` | builder | Keywords, descriptions, edesc |
| smaug | OLC | object | `ocreate <vnum> <name>` | builder | Create new object prototype |
| smaug | OLC | object | `odelete <vnum>` | builder | Delete object prototype |
| smaug | Builder | object | `olist [range]` | builder | List object vnums in area |
| smaug | Builder | object | `ostat <obj>` | builder | Show object internals |
| smaug | Builder | object | `ofind <name>` / `vsearch` | builder | Search object prototypes |
| smaug | OLC | area | `aset <area> <field> <v>` | builder | Area editor (fields below) |
| smaug | OLC | area | `aset ... name/author/filename/credits` | builder | Area identity fields |
| smaug | OLC | area | `aset ... flags/resetfreq/resetmsg` | builder | Area flags and reset behavior |
| smaug | OLC | area | `aset ... low/hi mob/obj/room/soft/hard` | builder | Vnum ranges and level ranges |
| smaug | OLC | area | `aset ... low_economy/high_economy` | builder | Area gold economy caps |
| smaug | OLC | area | `aset ... weatherx/weathery` | builder | Weather grid coordinates |
| smaug | OLC | area | `foldarea` / `savearea <file>` | builder | Write area to disk |
| smaug | OLC | area | `loadarea/installarea/unfoldarea/loadup` | immortal | Load/install area files |
| smaug | Builder | area | `areas` / `zones` / `newzones` | any/builder | List areas / zones |
| smaug | OLC | area | `instazone/instaroom/rgrid` | builder | Auto-generate zone/room grids |
| smaug | Builder | area | `check_vnums` / `vnums` / `renumber` | builder | Validate and renumber vnums |
| smaug | OLC | shop | `sedit <field>` | builder | Shop editor |
| smaug | OLC | shop | `makeshop <mob>` / `shopset` | builder | Create/configure shopkeeper |
| smaug | OLC | shop | `makerepair` / `repairset` | builder | Create/configure repair shop |
| smaug | Builder | shop | `shopstat/repairstat/shops/repairshops` | builder | Inspect/list shops |
| smaug | OLC | mobprog | `mpedit <mob> <trigger>` | builder | Edit mob programs on a mob |
| smaug | OLC | mobprog | `opedit/opcopy/opstat` | builder | Edit/copy/show object programs |
| smaug | OLC | mobprog | `rpedit/rpcopy/rpstat` | builder | Edit/copy/show room programs |
| smaug | OLC | mobprog | `mpapply/mpapplyb/mpstat` | builder | Attach/inspect mob programs |
| smaug | OLC | info | `hedit <topic>` | immortal | Help file editor |
| smaug | OLC | info | `hintedit` / `editnews` | immortal | Edit login hints / news |
| smaug | OLC | immortal | `cedit <cmd>` | admin | Command table editor (add/edit cmds) |
| smaug | OLC | immortal | `cmdtable` / `commands` | any | Show command table / list |
| smaug | Builder | immortal | `goto <loc>` | immortal | Teleport self to room/mob/obj |
| smaug | Builder | immortal | `at <loc> <cmd>` | immortal | Run a command at another location |
| smaug | Admin | immortal | `transfer <who> [loc]` | immortal | Teleport a character to you/loc |
| smaug | Admin | immortal | `retran` / `regoto` | immortal | Repeat last transfer/goto |
| smaug | Builder | immortal | `oinvoke <vnum>` | builder | Load an object instance |
| smaug | Builder | immortal | `minvoke <vnum>` | builder | Load a mob instance |
| smaug | Admin | immortal | `purge [target]` / `low_purge` | immortal | Purge mobs/objects in room |
| smaug | Admin | immortal | `restore [who]` | immortal | Restore hp/mana/move fully |
| smaug | Admin | immortal | `force <who> <cmd>` | immortal | Force target to run a command |
| smaug | Builder | immortal | `stat/vstat <vnum>` | builder | Inspect prototype by vnum |
| smaug | Admin | immortal | `slay <who>` | immortal | Kill a character instantly |
| smaug | Admin | immortal | `advance <who> <lvl>` | admin | Set a player's level |
| smaug | Admin | immortal | `trust <who> <lvl>` | admin | Set command trust level |
| smaug | Admin | immortal | `bestow <who> <cmds>` / `bestowarea` | admin | Grant specific commands/area |
| smaug | Admin | immortal | `freeze <who>` | immortal | Prevent target from acting |
| smaug | Admin | immortal | `hell/unhell <who>` | immortal | Jail/release a player |
| smaug | Admin | immortal | `deny <who>` / `pardon` | immortal | Ban account / clear flags |
| smaug | Admin | immortal | `ban/allow <site>` | admin | Site ban management |
| smaug | Admin | immortal | `restrict` / `wizlock` | admin | Restrict logins / lock game |
| smaug | Admin | immortal | `snoop <who>` | immortal | Watch a player's I/O |
| smaug | Admin | immortal | `switch <mob>` | immortal | Possess a mobile |
| smaug | Admin | immortal | `return` | immortal | Return to own body |
| smaug | Admin | immortal | `invis [lvl]` / `holylight` | immortal | Wizinvis / see-all toggle |
| smaug | Admin | immortal | `echo` / `recho` / `aecho` | immortal | Global/room/area broadcast |
| smaug | Admin | immortal | `reboot` / `shutdown` / `hotboot` | admin | Server restart/shutdown |
| smaug | Admin | immortal | `log <cmd>` | admin | Toggle logging of a command |
| smaug | Admin | immortal | `users` / `disconnect <desc>` | immortal | List/kill connections |
| smaug | Admin | immortal | `pcrename` / `immortalize` / `mortalize` | admin | Rename/promote/demote player |
| smaug | Admin | immortal | `pset/mset qp` / `qpset` | immortal | Set player/quest points |
| smaug | Admin | immortal | `config` / `cset` / `sset` | admin | Server/skill config |
| smaug | Player | comm | `say <msg>` / `say_to` | any | Speak to the room |
| smaug | Player | comm | `tell <who> <msg>` / `reply` / `retell` | any | Private message |
| smaug | Player | comm | `shout` / `yell` / `whisper` | any | Broadcast / local speech |
| smaug | Player | comm | `emote` / `think` | any | Freeform action / thought |
| smaug | Player | comm | `chat` / `newbiechat` / `immtalk` | any/imm | Global OOC channels |
| smaug | Player | comm | `clantalk/counciltalk/racetalk/guildtalk` | any | Group channels |
| smaug | Player | comm | `gtell` / `group` | any | Group communication |
| smaug | Player | comm | `channels` / `afk` / `dnd` / `ignore` | any | Channel and presence toggles |
| smaug | Player | comm | `board` / `note` / `boards` | any | Message board reading/posting |
| smaug | Player | info | `look` / `glance` / `examine` / `scan` | any | Observe surroundings/items |
| smaug | Player | info | `exits` / `findexit` / `compass` | any | Show room exits |
| smaug | Player | info | `score` / `worth` / `report` / `bio` | any | Character sheet and status |
| smaug | Player | info | `who` / `whois` / `users` | any | Online player lists |
| smaug | Player | info | `inventory` / `equipment` | any | Carried and worn items |
| smaug | Player | info | `help` / `wizhelp` / `commands` | any | Help system |
| smaug | Player | info | `areas` / `time` / `weather` / `holidays` | any | World info |
| smaug | Player | info | `consider` / `affected` / `where` | any | Assess target/effects/location |
| smaug | Player | info | `skills` (slist) / `spells` / `practice` | any | Ability lists and training |
| smaug | Player | inventory | `get` / `drop` / `put` / `give` | any | Item transfer |
| smaug | Player | inventory | `wear` / `remove` / `hold` / `wield` | any | Equip/unequip |
| smaug | Player | inventory | `quaff` / `eat` / `drink` / `recite` | any | Consume potions/food/scrolls |
| smaug | Player | inventory | `buy` / `sell` / `list` / `value` | any | Shop transactions |
| smaug | Player | inventory | `get all` / `sacrifice` / `junk` | any | Bulk / disposal |
| smaug | Player | social | `socials` | any | List social emotes |
| smaug | Player | social | `beckon` / `bow` (etc., data-driven) | any | Predefined social emotes |
| smaug | Player | combat | `kill` / `murder` | any | Initiate combat |
| smaug | Player | combat | `flee` / `rescue` / `wimpy` | any | Combat survival (representative) |
| smaug | Player | combat | `kick` / `bash` / `backstab` / `disarm` | any | Combat skills (representative) |
| smaug | Player | combat | `cast <spell>` / `brandish` / `zap` | any | Spellcasting (representative) |
| smaug | Player | move | `north` (and dirs) / `enter` / `recall` | any | Movement (compressed) |
| smaug | Player | move | `sit`/`rest`/`sleep`/`wake`/`stand` | any | Position changes |
| smaug | Player | clan | `clans` / `showclan` | any | View clan info |
| smaug | Admin | clan | `makeclan` / `setclan` | admin | Create/configure clan |
| smaug | Player | clan | `induct` / `outcast` / `setrank` | leader | Manage clan membership |
| smaug | Player | deity | `deities` / `showdeity` | any | View deity info |
| smaug | Admin | deity | `makedeity` / `setdeity` | admin | Create/configure deity |
| smaug | Player | deity | `devote` / `supplicate` / `favor` | any | Worship and petition deity |
| smaug | Player | council | `councils` / `induct` (council) | member | Council membership/info |
| smaug | Softcode-fn | mobprog | `mpecho <msg>` | mobprog | Echo to room from mob |
| smaug | Softcode-fn | mobprog | `mpechoat <vict> <msg>` | mobprog | Echo to one character |
| smaug | Softcode-fn | mobprog | `mpechoaround <vict> <msg>` | mobprog | Echo to room except victim |
| smaug | Softcode-fn | mobprog | `mpechozone <msg>` | mobprog | Echo to entire area/zone |
| smaug | Softcode-fn | mobprog | `mpat <loc> <cmd>` | mobprog | Run mob command at location |
| smaug | Softcode-fn | mobprog | `mpgoto <loc>` | mobprog | Move mob to room |
| smaug | Softcode-fn | mobprog | `mptransfer <who> <loc>` | mobprog | Teleport a character |
| smaug | Softcode-fn | mobprog | `mpforce <who> <cmd>` | mobprog | Force character to run command |
| smaug | Softcode-fn | mobprog | `mpmload <vnum>` | mobprog | Load a mob into room |
| smaug | Softcode-fn | mobprog | `mpoload <vnum> [lvl]` | mobprog | Load an object |
| smaug | Softcode-fn | mobprog | `mppurge [target]` | mobprog | Purge mob/object |
| smaug | Softcode-fn | mobprog | `mpjunk <item>` / `mpstrew` / `mpscatter` | mobprog | Destroy/scatter items |
| smaug | Softcode-fn | mobprog | `mpkill <who>` / `mp_slay` / `mp_damage` | mobprog | Attack/kill/damage target |
| smaug | Softcode-fn | mobprog | `mppeace` / `mppardon` / `mp_restore` | mobprog | Stop fight / pardon / heal |
| smaug | Softcode-fn | mobprog | `mpapply/mpapplyb/mpasupress` | mobprog | Apply/suppress affects |
| smaug | Softcode-fn | mobprog | `mpmset/mposet/mppkset/mpflag/mprmflag` | mobprog | Set mob/obj/pk fields and flags |
| smaug | Softcode-fn | mobprog | `mpmorph/mpunmorph/mpmorphset` | mobprog | Change/restore mob morph |
| smaug | Softcode-fn | mobprog | `mpinvis/mpvisible` | mobprog | Toggle mob visibility |
| smaug | Softcode-fn | mobprog | `mpdelay <n>` / `mpnothing` | mobprog | Schedule delayed trigger / no-op |
| smaug | Softcode-fn | mobprog | `mphunt/mphate/mpfear/mpbeckon` | mobprog | AI targeting behaviors |
| smaug | Softcode-fn | mobprog | `mp_open_passage/mp_close_passage` | mobprog | Create/remove temporary exit |
| smaug | Softcode-fn | mobprog | `mp_fill_in` / `mppromote` | mobprog | Terrain/state manipulation |
| smaug | Softcode-fn | mobprog | `mpsound/mpsoundat/mpmusic...` | mobprog | Sound/music messages |
| smaug | Softcode-fn | mobprog | `mpdream/mpasound/mpasupress` | mobprog | Sleep/area messages |
| smaug | Softcode-fn | mobprog | `mp_deposit/mp_withdraw/mpfavor/mpqpset` | mobprog | Bank, favor, quest-point ops |
| smaug | Softcode-fn | mobprog | `mp_log/mp_practice/mpadvance` | mobprog | Log, teach, advance target |
| smaug | Softcode-fn | mobprog | `mptag/mprmtag/mpcopy/mpplace` | mobprog | Object tagging/placement |
| smaug | Softcode-fn | mobprog | `mpnuisance/mpunnuisance` | mobprog | Manage nuisance flags |
| smaug | Softcode-fn | mobprog | trigger types: `>greet_prog` etc. | mobprog | act/speech/greet/entry/rand/fight/death/give/... |
| smaug | Softcode-fn | mobprog | `$n/$N` | mobprog | Actor name / name+title (or short) |
| smaug | Softcode-fn | mobprog | `$t/$T` | mobprog | Victim name / short-desc |
| smaug | Softcode-fn | mobprog | `$r` | mobprog | Random visible character name |
| smaug | Softcode-fn | mobprog | `$e/$m/$s` | mobprog | Actor he/him/his pronouns |
| smaug | Softcode-fn | mobprog | `$j/$k/$l` | mobprog | Victim/self pronoun variants |
| smaug | Softcode-fn | mobprog | `$o/$p` | mobprog | Object short / seen-object name |
| smaug | Softcode-fn | mobprog | `if rand(N)` | mobprog | Ifcheck: random percentage gate |
| smaug | Softcode-fn | mobprog | `if isnpc($n)` / `ispc` | mobprog | Ifcheck: actor is NPC/PC |
| smaug | Softcode-fn | mobprog | `if level($n) > N` | mobprog | Ifcheck: compare level |
| smaug | Softcode-fn | mobprog | `if hitprcnt($n) < N` | mobprog | Ifcheck: hp percentage |
| smaug | Softcode-fn | mobprog | `if ispkill/ischarmed/isimmort/isfollow` | mobprog | Ifcheck: character state |
| smaug | Softcode-fn | mobprog | `if wearing/wearingvnum/name/sex($n)` | mobprog | Ifcheck: equipment/identity |
| smaug | Softcode-fn | mobprog | `if race/class/clan/deity/guild($n)` | mobprog | Ifcheck: affiliation |
| smaug | Softcode-fn | mobprog | `if mobinroom/mobinarea/mobinworld(vnum)` | mobprog | Ifcheck: count mobs present |
| smaug | Softcode-fn | mobprog | `if numfighting/mortcount/timeskilled` | mobprog | Ifcheck: combat/kill counters |
| tbamud | OLC | building | redit `<vnum>` | builder | Full-screen room editor (name/desc/exits/flags/sector/extradescs). |
| tbamud | OLC | building | medit `<vnum>` | builder | Mobile editor (keywords/stats/flags/affects/position/attack). |
| tbamud | OLC | building | oedit `<vnum>` | builder | Object editor (type/values/wear/extra/affect flags/extradescs). |
| tbamud | OLC | building | zedit `<vnum>` | builder | Zone editor: reset command list + zone flags/lifespan. |
| tbamud | OLC | building | sedit `<vnum>` | builder | Shop editor (keeper/items/buy-sell rates/rooms/trade flags). |
| tbamud | OLC | trigger | trigedit `<vnum>` | builder | DG trigger editor (type/args/numeric arg/script body). |
| tbamud | OLC | building | qedit `<vnum>` | builder | Quest editor (giver/target/rewards/prereqs). |
| tbamud | OLC | building | aedit `<social>` | immortal/god | Social (act) editor: messages for social commands. |
| tbamud | OLC | building | hedit `<kw>` | immortal/god | Help entry editor. |
| tbamud | OLC | building | cedit | immortal/god | In-game game config (campaign/rent/rules) editor. |
| tbamud | OLC | building | msgedit | immortal/god | Combat damage-message editor. |
| tbamud | OLC | building | tedit `<file>` | immortal/god | Text-file editor (motd/news/credits/etc). |
| tbamud | OLC | building | prefedit | any | Personal preference/toggle editor. |
| tbamud | OLC | building | olc | builder | Show pending OLC save list (unsaved changes). |
| tbamud | OLC | building | saveall | builder | Save all modified OLC zones to disk. |
| tbamud | OLC | zone | zedit M/O `<vnum>` | builder | Reset: load Mobile / Object into room. |
| tbamud | OLC | zone | zedit G/E `<vnum>` | builder | Reset: Give obj to / Equip obj on last mob. |
| tbamud | OLC | zone | zedit P `<vnum>` | builder | Reset: Put object inside another object. |
| tbamud | OLC | zone | zedit D `<dir> <state>` | builder | Reset: set Door open/closed/locked. |
| tbamud | OLC | zone | zedit R `<vnum>` | builder | Reset: Remove object from room. |
| tbamud | OLC | zone | zedit T/V | builder | Reset: attach Trigger / set script Variable. |
| tbamud | OLC | building | rlist/mlist/olist | builder | List room/mob/obj vnums in a range. |
| tbamud | OLC | building | zlist/slist/tlist/qlist | builder | List zone/shop/trigger/quest entries. |
| tbamud | OLC | building | rcopy/mcopy/ocopy `<from> <to>` | god | Copy a room/mob/obj prototype to new vnum. |
| tbamud | OLC | building | scopy/tcopy `<from> <to>` | god | Copy a shop/trigger prototype. |
| tbamud | OLC | object | oset `<obj> <field> <val>` | builder | Set field on object prototype directly. |
| tbamud | OLC | building | dig `<dir> <vnum>` | builder | Create room and link exit in one step. |
| tbamud | OLC | building | buildwalk | builder | Toggle: auto-create rooms as you walk. |
| tbamud | Builder | building | vnum `<obj|mob> <name>` | immortal/god | Search prototypes by keyword; show vnums. |
| tbamud | Builder | building | vstat `<type> <vnum>` | immortal/god | Stat a prototype (not an instance). |
| tbamud | Builder | building | vdelete `<type> <vnum>` | builder | Delete a prototype from a zone. |
| tbamud | Builder | zone | zreset `<zone>` | builder | Force a zone reset now. |
| tbamud | Builder | zone | zcheck/zpurge `<zone>` | builder | Audit zone for errors / purge zone contents. |
| tbamud | Builder | zone | zlock/zunlock `<zone>` | god | Lock/unlock a zone against editing. |
| tbamud | Builder | trigger | attach/detach `<trig> <target>` | builder | Attach/detach a DG trigger to a live entity. |
| tbamud | Builder | trigger | tstat `<vnum>` | builder | Show trigger prototype details. |
| tbamud | Builder | mobile | load mob/obj `<vnum>` | builder | Spawn a mob or object instance here. |
| tbamud | Builder | room | purge `[target]` | builder | Remove mob/obj (or all) from room. |
| tbamud | Builder | room | teleport `<target> <room>` | builder | Move a target to a room. |
| tbamud | Admin | immortal | goto `<room|target>` | immortal/god | Teleport self to room/player/vnum. |
| tbamud | Admin | immortal | at `<loc> <cmd>` | immortal/god | Execute a command at a remote location. |
| tbamud | Admin | immortal | transfer `<player>` | god | Bring player(s) to you. |
| tbamud | Admin | immortal | force `<who> <cmd>` | god | Force a char (or all) to run a command. |
| tbamud | Admin | immortal | set `<who> <field> <val>` | immortal/god | Set stat/flag on live player or mob. |
| tbamud | Admin | info | stat `<target>` | immortal/god | Detailed stat of live room/mob/obj/player. |
| tbamud | Admin | immortal | restore `<target>` | god | Full heal/restore a target. |
| tbamud | Admin | immortal | advance `<pl> <lvl>` | god | Set a player's level. |
| tbamud | Admin | immortal | switch `<mob>` | god | Possess/control a mobile. |
| tbamud | Admin | immortal | snoop `<player>` | god | Watch another player's I/O. |
| tbamud | Admin | immortal | invis / holylight / nohassle | immortal/god | Wizinvis level; see-all; mobs ignore you. |
| tbamud | Admin | comm | echo/gecho/send | immortal/god | Room echo / global echo / send text to target. |
| tbamud | Admin | immortal | freeze/thaw/mute `<pl>` | god | Freeze player, silence channels. |
| tbamud | Admin | immortal | ban/unban `<site>` | god | Site ban management. |
| tbamud | Admin | immortal | wizlock / shutdown / reboot | impl | Lock logins; stop/restart server. |
| tbamud | Admin | immortal | copyover / export | god | Hot-reboot keeping players; export zone to file. |
| tbamud | Admin | immortal | skillset `<pl> <sk> <n>` | god | Set a player's skill/spell percent. |
| tbamud | Admin | info | users / last / links | god | Connection list; last logins; link status. |
| tbamud | Admin | comm | wiznet `;<msg>` | immortal/god | Immortal-only chat channel. |
| tbamud | Softcode-fn | mobile | mecho `<msg>` | script | Echo message to mob's room. |
| tbamud | Softcode-fn | mobile | mechoaround `<t> <msg>` | script | Echo to room except target. |
| tbamud | Softcode-fn | mobile | msend `<t> <msg>` | script | Send message to one target. |
| tbamud | Softcode-fn | mobile | mrecho `<msg>` | script | Echo to a range/list of rooms. |
| tbamud | Softcode-fn | mobile | mzoneecho `<zone> <msg>` | script | Echo message to whole zone. |
| tbamud | Softcode-fn | mobile | masound `<msg>` | script | Sound message to adjacent rooms. |
| tbamud | Softcode-fn | mobile | mload mob/obj `<vnum>` | script | Load a mob/object at the mob. |
| tbamud | Softcode-fn | mobile | mpurge `[target]` | script | Purge a target (or room contents). |
| tbamud | Softcode-fn | mobile | mgoto `<room>` | script | Move mob to a room. |
| tbamud | Softcode-fn | mobile | mat `<room> <cmd>` | script | Run a mob command at another room. |
| tbamud | Softcode-fn | mobile | mteleport `<t> <room>` | script | Teleport a target to a room. |
| tbamud | Softcode-fn | mobile | mforce `<who> <cmd>` | script | Force target(s) to run a command. |
| tbamud | Softcode-fn | mobile | mkill `<target>` | script | Make mob attack a target. |
| tbamud | Softcode-fn | mobile | mdamage `<t> <amt>` | script | Deal (unattributed) damage to target. |
| tbamud | Softcode-fn | mobile | mjunk `<obj>` | script | Destroy an object mob carries. |
| tbamud | Softcode-fn | mobile | mdoor `<dir> <field> <val>` | script | Edit/create/remove a room exit. |
| tbamud | Softcode-fn | mobile | mhunt `<target>` | script | Set mob to hunt/track a target. |
| tbamud | Softcode-fn | mobile | mremember/mforget `<t>` | script | Store/clear a remembered target on mob. |
| tbamud | Softcode-fn | mobile | mfollow `<target>` | script | Make mob follow a target. |
| tbamud | Softcode-fn | mobile | mtransform `<vnum>` | script | Morph mob into another mob prototype. |
| tbamud | Softcode-fn | mobile | mlog `<msg>` | script | Write to the mud script log. |
| tbamud | Softcode-fn | object | oecho / oechoaround / osend | script | Room echo / echo-except-target / send from object. |
| tbamud | Softcode-fn | object | orecho / ozoneecho / oasound | script | Range echo / zone echo / adjacent-room sound. |
| tbamud | Softcode-fn | object | oload mob/obj `<vnum>` | script | Load a mob/object at the object. |
| tbamud | Softcode-fn | object | opurge `[target]` | script | Purge a target near the object. |
| tbamud | Softcode-fn | object | oforce `<who> <cmd>` | script | Force target(s) to run a command. |
| tbamud | Softcode-fn | object | oteleport `<t> <room>` | script | Teleport target to a room. |
| tbamud | Softcode-fn | object | oat `<room> <cmd>` | script | Run object command at another room. |
| tbamud | Softcode-fn | object | omove `<dir>` | script | Move the object's carrier a direction. |
| tbamud | Softcode-fn | object | odoor `<dir> <field> <val>` | script | Edit exit of the object's room. |
| tbamud | Softcode-fn | object | odamage `<t> <amt>` | script | Damage a target. |
| tbamud | Softcode-fn | object | osetval `<pos> <val>` | script | Set the object's own value slot. |
| tbamud | Softcode-fn | object | otimer `<n>` | script | Set the object's decay timer. |
| tbamud | Softcode-fn | object | otransform `<vnum>` | script | Morph object into another prototype. |
| tbamud | Softcode-fn | object | olog `<msg>` | script | Write to script log. |
| tbamud | Softcode-fn | room | wecho / wechoaround / wsend | script | Room echo / echo-except / send from room. |
| tbamud | Softcode-fn | room | wrecho / wzoneecho / wasound | script | Range echo / zone echo / adjacent-room sound. |
| tbamud | Softcode-fn | room | wload mob/obj `<vnum>` | script | Load mob/object in the room. |
| tbamud | Softcode-fn | room | wpurge `[target]` | script | Purge target in the room. |
| tbamud | Softcode-fn | room | wforce `<who> <cmd>` | script | Force target(s) to run a command. |
| tbamud | Softcode-fn | room | wteleport `<t> <room>` | script | Teleport target to a room. |
| tbamud | Softcode-fn | room | wat `<room> <cmd>` | script | Run room command at another room. |
| tbamud | Softcode-fn | room | wmove `<dir>` | script | Move room occupants a direction. |
| tbamud | Softcode-fn | room | wdoor `<dir> <field> <val>` | script | Edit an exit of the room. |
| tbamud | Softcode-fn | room | wdamage `<t> <amt>` | script | Damage a target in the room. |
| tbamud | Softcode-fn | room | wlog `<msg>` | script | Write to script log. |
| tbamud | Softcode-fn | trigger | if / elseif / else / end | script | Conditional control flow. |
| tbamud | Softcode-fn | trigger | while ... done | script | Loop while condition true (loop-guarded). |
| tbamud | Softcode-fn | trigger | switch/case/default/break | script | Multi-branch dispatch on a value. |
| tbamud | Softcode-fn | trigger | set `<var> <val>` | script | Assign a local trigger variable. |
| tbamud | Softcode-fn | trigger | eval `<var> <expr>` | script | Evaluate arithmetic/string expression into var. |
| tbamud | Softcode-fn | trigger | unset `<var>` | script | Delete a variable. |
| tbamud | Softcode-fn | trigger | global `<var>` | script | Promote a var to script-global scope. |
| tbamud | Softcode-fn | trigger | context `<n>` | script | Set variable namespace/context id. |
| tbamud | Softcode-fn | trigger | remote `<var> <uid>` | script | Copy variable onto another entity's globals. |
| tbamud | Softcode-fn | trigger | rdelete `<var> <uid>` | script | Delete a remote variable. |
| tbamud | Softcode-fn | trigger | wait `<n>` / wait until `<t>` | script | Pause execution for ticks/time. |
| tbamud | Softcode-fn | trigger | halt / return `<0|1>` | script | Stop script / set return value (block cmd). |
| tbamud | Softcode-fn | trigger | nop `<x>` | script | No-op (force a var substitution eval). |
| tbamud | Softcode-fn | trigger | extract `<var> <n> <list>` | script | Pull nth word from a string list. |
| tbamud | Softcode-fn | trigger | makeuid `<var> <id>` | script | Build a UID reference variable from an id. |
| tbamud | Softcode-fn | trigger | attach/detach `<trig> <id>` | script | Attach/detach a trigger at runtime. |
| tbamud | Softcode-fn | trigger | dg_cast '`<spell>`' | script | Cast a spell from within a script. |
| tbamud | Softcode-fn | trigger | dg_affect `<t> <flag> <n> <dur>` | script | Apply an affect/flag to a target. |
| tbamud | Softcode-fn | scripting | %actor.field% | script | Actor accessor: name/id/vnum/level/sex/etc. |
| tbamud | Softcode-fn | scripting | %actor.hitp% .maxhitp .move | script | Actor HP/move/mana stat fields. |
| tbamud | Softcode-fn | scripting | %actor.str% .dex .int (etc) | script | Actor ability-score fields. |
| tbamud | Softcode-fn | scripting | %actor.is_pc% .is_killer .align | script | Actor boolean/class/alignment fields. |
| tbamud | Softcode-fn | scripting | %actor.inventory% .eq[pos] | script | Actor inventory / equipment accessors. |
| tbamud | Softcode-fn | scripting | %actor.varexists(x)% | script | Test whether a remote var exists on actor. |
| tbamud | Softcode-fn | scripting | %obj.val0-3% .type .timer .weight | script | Object value slots and attributes. |
| tbamud | Softcode-fn | scripting | %obj.carried_by% .worn_by .contents | script | Object location/containment accessors. |
| tbamud | Softcode-fn | scripting | %room.vnum% .name .sector .people | script | Room identity/occupant accessors. |
| tbamud | Softcode-fn | scripting | %room.north.vnum% (exits) | script | Directional-exit target/flag accessors. |
| tbamud | Softcode-fn | scripting | %room.weather% .zonenumber | script | Room weather and owning-zone fields. |
| tbamud | Softcode-fn | scripting | %random.N% / %random.char% | script | Random 1..N / random visible char in room. |
| tbamud | Softcode-fn | scripting | %self% %people[room]% %time.hour% | script | Self ref / room population / game time. |
| tbamud | Softcode-fn | scripting | .toupper .trim .contains(x) | script | String function fields on a variable. |
| tbamud | Softcode-fn | scripting | .car .cdr .charat(n) .mudcommand | script | List head/tail, char-at, command-match ops. |
| tbamud | Softcode-fn | scripting | operators == != < > <= >= | script | Comparison ops (numeric or string). |
| tbamud | Softcode-fn | scripting | operators && \|\| /= | script | Logical AND/OR and substring-contains. |
| tbamud | Softcode-fn | scripting | operators + - * / | script | Integer arithmetic in eval expressions. |
| tbamud | Player | comm | say / ' `<msg>` | any | Speak to the room. |
| tbamud | Player | comm | tell `<who> <msg>` / reply | any | Private message; reply to last teller. |
| tbamud | Player | comm | gossip / auction / shout | any | Global chat channels. |
| tbamud | Player | comm | whisper / ask `<who> <msg>` | any | Quiet directed speech. |
| tbamud | Player | comm | emote / : `<action>` | any | Free-form action emote. |
| tbamud | Player | comm | gsay / gtell `<msg>` | any | Talk to your group. |
| tbamud | Player | comm | page / write / mail | any | Notify a player; note-writing; send mail. |
| tbamud | Player | info | look / examine / read | any | View room, object, or writing. |
| tbamud | Player | info | exits / scan / map | any | Show exits; peek adjacent rooms; ASCII map. |
| tbamud | Player | info | score / whoami / attributes | any | Show your character sheet. |
| tbamud | Player | info | who / whois / where / users | any | Who's online; locate players. |
| tbamud | Player | info | inventory / equipment | any | List carried and worn items. |
| tbamud | Player | info | consider / diagnose | any | Compare foe strength; assess wounds. |
| tbamud | Player | info | help / hindex / commands / socials | any | Help system; command and social lists. |
| tbamud | Player | info | time / weather / areas / levels | any | Game clock, weather, zone list, level table. |
| tbamud | Player | object | get / drop / put / give | any | Basic item manipulation. |
| tbamud | Player | object | wear / wield / hold / remove | any | Equip and unequip items. |
| tbamud | Player | object | quaff / recite / use / drink / eat | any | Consume potions/scrolls/wands/food. |
| tbamud | Player | object | buy / sell / list / value | any | Shop interaction. |
| tbamud | Player | object | get/deposit/withdraw (bank) | any | Coin banking; split gold with group. |
| tbamud | Player | mobile | kill / hit / flee / assist | any | Core combat commands. |
| tbamud | Player | mobile | kick / bash / rescue / backstab | any | Representative skill attacks. |
| tbamud | Player | mobile | cast '`<spell>`' `<target>` | any | Cast a memorized/known spell. |
| tbamud | Player | mobile | practice / steal / hide / sneak | any | Train skills; thief/stealth actions. |
| tbamud | Player | info | consider / group / follow | any | Party management commands. |
| tbamud | Player | building | alias `<name> <cmd>` | any | Define command aliases. |
| tbamud | Player | building | toggle / prompt / display / title | any | Personal display/preference settings. |
| tbamud | Player | building | quest / house / bug / idea / typo | any | Quest engine, player housing, feedback reports. |
| tbamud | Player | building | save / quit / rent | any | Save char; log out; rent items. |
| awakemud | Player | matrix | jack <deck> / unjack | decker | Jack cyberdeck into/out of a jackpoint. |
| awakemud | Player | matrix | connect / logon [host] | decker | Log the persona onto a matrix host. |
| awakemud | Player | matrix | logoff / logout / disconnect / quit | decker | Jack out; disconnect from the matrix. |
| awakemud | Player | matrix | look | decker | View current host, its icons and subsystems. |
| awakemud | Player | matrix | scan | decker | Scan/map adjacent hosts and datastore contents. |
| awakemud | Player | matrix | locate <target> | decker | Locate access node, file, decker, or paydata. |
| awakemud | Player | matrix | analyze <target> | decker | Analyze host/icon/security for ratings. |
| awakemud | Player | matrix | run <program> | decker | Run a utility against a subsystem (attack/decrypt/etc). |
| awakemud | Player | matrix | load / unload / upload / swap <prog> | decker | Load programs from deck memory into active memory. |
| awakemud | Player | matrix | download <file> | decker | Download paydata/file to deck storage. |
| awakemud | Player | matrix | decrypt <subsystem> | decker | Decrypt an encrypted file or subsystem. |
| awakemud | Player | matrix | disarm | decker | Disarm a data bomb on a file. |
| awakemud | Player | matrix | crash <deck> | decker | Crash a target's deck (matrix attack). |
| awakemud | Player | matrix | evade | decker | Evade/shake an active trace. |
| awakemud | Player | matrix | parry | decker | Defend against IC in matrix combat. |
| awakemud | Player | matrix | abort | decker | Abort the current matrix operation. |
| awakemud | Player | matrix | redirect | decker | Redirect the datatrail to slow trace. |
| awakemud | Player | matrix | trace <target> | decker | Trace another icon's origin. |
| awakemud | Player | matrix | tap <target> | decker | Tap a line/comm for surveillance. |
| awakemud | Player | matrix | restrict | decker | Restrict/lock down a host subsystem (control). |
| awakemud | Player | matrix | reveal | decker | Reveal hidden icons in the host. |
| awakemud | Player | matrix | max | decker | Show deck's max/active memory usage. |
| awakemud | Player | matrix | score / position | decker | Persona/deck status while decking. |
| awakemud | Player | matrix | asist | decker | Toggle ASIST/hitcher perception link. |
| awakemud | Player | matrix | software | decker | List programs stored on the deck. |
| awakemud | Player | matrix | talk / call / answer / hangup | decker | Comcall (in-matrix phone/comms). |
| awakemud | Player | matrix | selffry | immortal | Debug: fry own persona (test command). |
| awakemud | Player | vehicle | drive [dir] | rigger | Drive a vehicle manually one direction. |
| awakemud | Player | vehicle | rig <vehicle> | rigger | Jack into vehicle control rig (VCR) to pilot. |
| awakemud | Player | vehicle | control | rigger | Enter remote-control/drone rigging deck. |
| awakemud | Player | vehicle | speed <n> | rigger | Set the vehicle's cruising speed. |
| awakemud | Player | vehicle | chase <target> | rigger | Pursue another vehicle/target. |
| awakemud | Player | vehicle | flyto / land | rigger | Fly aircraft to a destination / land it. |
| awakemud | Player | vehicle | gridguide <dest> | rigger | Autonav via GridGuide to a saved destination. |
| awakemud | Player | vehicle | ram <target> | rigger | Ram another vehicle or obstacle. |
| awakemud | Player | vehicle | driveby | rigger | Perform a drive-by attack while moving. |
| awakemud | Player | vehicle | target <mount> | rigger | Acquire target for a vehicle-mounted weapon. |
| awakemud | Player | vehicle | man <mount> | any | Man a mounted weapon/turret. |
| awakemud | Player | vehicle | mount <weapon> | rigger | Install a weapon onto a vehicle mount. |
| awakemud | Player | vehicle | upgrade <vehicle> | rigger | Install/modify vehicle mods (workshop). |
| awakemud | Player | vehicle | switch | any | Switch between front/back seats of a vehicle. |
| awakemud | Player | vehicle | pop | any | Pop trunk/hood/hidden compartment. |
| awakemud | Player | vehicle | tow <vehicle> | rigger | Tow another vehicle. |
| awakemud | Player | vehicle | push | any | Push a disabled vehicle. |
| awakemud | Player | vehicle | transfer | any | Transfer occupants/gear between vehicles. |
| awakemud | Player | vehicle | repair / fix | any | Repair vehicle/rig damage. |
| awakemud | Player | vehicle | subscribe / unsubscribe | rigger | Manage rigger's subscribed drone list. |
| awakemud | Player | vehicle | watch <vehicle> | any | Watch a vehicle's occupants/actions. |
| awakemud | Player | vehicle | vemote / osay | rigger | Emote/speak as/from the vehicle. |
| awakemud | Player | vehicle | wheresmycar | any | Locate your owned/garaged vehicle. |
| awakemud | Player | magic | cast <spell> [target] | mage | Cast a sorcery spell. |
| awakemud | Player | magic | ritualcast <spell> | mage | Perform a ritual sorcery casting. |
| awakemud | Player | magic | spells | mage | List known spells / spellbook. |
| awakemud | Player | magic | dispell <spell> | mage | Dispel a sustained/active spell. |
| awakemud | Player | magic | conjure <type> <force> | mage | Conjure an elemental/nature spirit. |
| awakemud | Player | magic | spirits / elementals | mage | List bound spirits and elementals. |
| awakemud | Player | magic | banish <spirit> | mage | Banish a hostile/enemy spirit. |
| awakemud | Player | magic | domain | mage | Show/set the mage's spirit domain. |
| awakemud | Player | magic | manifest | mage | Manifest an astral form to the physical. |
| awakemud | Player | magic | project | mage | Astrally project from the body. |
| awakemud | Player | magic | perceive | mage | Enter/leave astral perception. |
| awakemud | Player | magic | assense <target> | mage | Astrally assense an aura for info. |
| awakemud | Player | magic | focus <item> | mage | Activate/deactivate a magical focus. |
| awakemud | Player | magic | bond / unbond <focus> | mage | Bond a focus/weapon foci to the mage. |
| awakemud | Player | magic | powerdown | mage | Drop all sustained spells/foci. |
| awakemud | Player | magic | cleanse | mage | Cleanse background/astral taint. |
| awakemud | Player | magic | metamagic | mage | View/manage learned metamagic techniques. |
| awakemud | Player | magic | initiate | mage | Undergo initiation to raise grade. |
| awakemud | Player | magic | addpoint | mage | Spend karma as a power point (non-initiate). |
| awakemud | Player | magic | submerse | decker | Otaku equivalent of initiation (resonance). |
| awakemud | Player | magic | heal / treat | mage | Magically heal / first-aid treat wounds. |
| awakemud | Player | magic | design <spell> | mage | Design a new spell formula (workshop). |
| awakemud | Player | cyberware | cyberware | any | List installed cyberware. |
| awakemud | Player | cyberware | bioware | any | List installed bioware. |
| awakemud | Player | cyberware | activate / deactivate <ware> | any | Toggle cyberware (e.g. spurs, smartlink). |
| awakemud | Player | cyberware | boost | any | Trigger boosted reflexes / wired reflexes. |
| awakemud | Player | cyberware | reflex | any | Set wired-reflex activation level. |
| awakemud | Player | cyberware | download / upload <ware> | any | Move data to/from headware memory. |
| awakemud | Player | cyberware | chipload / load <chip> | any | Load a skillsoft/activesoft into a chipjack. |
| awakemud | Player | cyberware | drugs | any | List active drugs and addiction status. |
| awakemud | Player | cyberware | patch | any | Apply a stim/trauma/slap patch. |
| awakemud | Player | object | build <parts> | decker | Build a cyberdeck from component parts. |
| awakemud | Player | object | cook <chip> | any | Burn/cook an optical chip (softs). |
| awakemud | Player | object | program <target> | decker | Program matrix software / persona programs. |
| awakemud | Player | object | design <part> | any | Design deck part / program / spell (crafting). |
| awakemud | Player | object | attach / unattach <item> | any | Attach accessory (scope, silencer) to gear. |
| awakemud | Player | object | install / uninstall | any | Install/remove modular components. |
| awakemud | Player | object | packup / unpack | any | Pack/unpack a workshop or facility. |
| awakemud | Player | object | repair / fix <item> | any | Repair damaged equipment. |
| awakemud | Player | object | restring <item> <desc> | any | Rename/redescribe owned gear (cosmetic). |
| awakemud | Player | object | ammo / reload / draw / holster | any | Manage firearm ammo, reload, draw, holster. |
| awakemud | Player | object | get/drop/give/put/wear/remove/wield | any | Standard Diku object handling (representative). |
| awakemud | Player | comm | say / ' / sayto / osay | any | Local room speech (incl. one-way osay). |
| awakemud | Player | comm | tell / reply | any | Private cross-game tells. |
| awakemud | Player | comm | ooc / question / ht / rt / shout | any | OOC, newbie-question, hired, RPE, shout channels. |
| awakemud | Player | comm | phone / call / answer / hangup | any | In-world phone system. |
| awakemud | Player | comm | radio | any | Squad radio (frequency-based). |
| awakemud | Player | comm | broadcast / , | any | Broadcast to nearby radios. |
| awakemud | Player | comm | emote / : / vemote | any | Freeform / vehicle emotes. |
| awakemud | Player | comm | ignore / block | any | Ignore/block another player. |
| awakemud | Player | comm | history / says / oocs / tells | any | Recall channel message history. |
| awakemud | Player | comm | pgroup | any | Player-group (runner-team) management. |
| awakemud | Player | info | score / status / affects | any | Character sheet, condition, active effects. |
| awakemud | Player | info | skills / abilities / powers | any | List skills, active/adept abilities. |
| awakemud | Player | info | pools / cpool | any | Show dice pools (combat/spell/etc). |
| awakemud | Player | info | penalties | any | Show current wound/situational penalties. |
| awakemud | Player | info | inventory / equipment / pockets | any | List carried/worn gear. |
| awakemud | Player | info | tke / karma | any | Show total karma earned (TKE). |
| awakemud | Player | info | networth / balance / gold | any | Show nuyen and net worth. |
| awakemud | Player | info | memory / remember / forget | any | Remember/forget introduced names. |
| awakemud | Player | info | who / quickwho / where | any | Who-list and player locations. |
| awakemud | Player | info | recap / jobs / quests / progress | any | Runs/jobs log and advancement progress. |
| awakemud | Player | info | leaderboards | any | View leaderboards. |
| awakemud | Player | info | look / examine / probe / scan | any | Look, examine, probe, scan surroundings. |
| awakemud | Player | info | map / survey / exits | any | Room map, area survey, exit list. |
| awakemud | Player | info | consider / diagnose / assense | any | Assess target's toughness/wounds/aura. |
| awakemud | Player | info | train / practice / learn / teach | any | Improve/learn skills at a trainer. |
| awakemud | Player | info | customize / toggle / configure / display | any | Player preferences, prompt, toggles. |
| awakemud | Player | info | banish (mob) / hail / consent | any | Social-flow and consent controls. |
| awakemud | OLC | building | redit | builder | Room editor (OLC). |
| awakemud | OLC | building | medit | builder | Mobile (NPC) editor (OLC). |
| awakemud | OLC | building | iedit | builder | Object/item editor (OLC). |
| awakemud | OLC | building | vedit | builder | Vehicle editor (OLC). |
| awakemud | OLC | building | icedit | builder | IC (intrusion countermeasures/matrix ICE) editor. |
| awakemud | OLC | building | sedit | builder | Shop editor (OLC). |
| awakemud | OLC | building | zedit | builder | Zone/reset editor (OLC). |
| awakemud | OLC | building | qedit | builder | Quest editor (OLC). |
| awakemud | OLC | building | hedit / helpedit | builder | Help-file editor (OLC). |
| awakemud | OLC | building | houseedit | builder | Apartment/house/complex editor. |
| awakemud | Builder | building | dig / oneway / undig <dir> | builder | Create/remove exits and linked rooms. |
| awakemud | Builder | building | *list (rlist/mlist/ilist/vlist/…) | builder | List protos by type in a zone. |
| awakemud | Builder | building | *clone (rclone/mclone/iclone/vclone/…) | builder | Clone a prototype. |
| awakemud | Builder | building | *delete (rdelete/mdelete/…) | immortal | Delete a prototype/zone. |
| awakemud | Builder | building | *find (vfind/setfind/shopfind) | builder | Search protos/sets/shops. |
| awakemud | Builder | building | vnum / vstat / stat / vteleport | builder | Inspect vnums, stat objects, teleport by vnum. |
| awakemud | Builder | building | iload / wizload | builder | Load an item/mob prototype into the world. |
| awakemud | Builder | building | zreset / zone / zswitch / zdelete | builder | Zone reset and management. |
| awakemud | Builder | building | goto / at / teleport / vteleport | builder | Move to/act at a location. |
| awakemud | Builder | building | redesc / exdescs / tempdesc | builder | Edit room/extra/temporary descriptions. |
| awakemud | Builder | building | phonelist / hlist / iclist / slist | builder | List phones/helps/ICE/spells protos. |
| awakemud | Admin | immortal | advance / self_advance | immortal | Set a player's level. |
| awakemud | Admin | immortal | set / valset / vset / pgset | immortal | Edit player/obj/vehicle values and pgroups. |
| awakemud | Admin | immortal | skillset / spellset / abilityset | immortal | Grant/set a player's skills/spells/abilities. |
| awakemud | Admin | immortal | award / deduct / charge / payout / garnish | immortal | Adjust karma/nuyen; economy admin. |
| awakemud | Admin | immortal | force / forceget / forceput | immortal | Force a character to act. |
| awakemud | Admin | immortal | switch / possess / return | immortal | Puppet/possess an NPC. |
| awakemud | Admin | immortal | snoop / send / restore | immortal | Snoop a session, message, full-heal. |
| awakemud | Admin | immortal | purge / destroy / load | immortal | Purge/destroy/load entities. |
| awakemud | Admin | immortal | invis / incognito / visible / poofin/poofout | immortal | Wizinvis and entrance/exit messages. |
| awakemud | Admin | immortal | freeze / thaw / mute / notitle / squelch | immortal | Player disciplinary controls. |
| awakemud | Admin | immortal | ban / unban / banvpn / authorize | immortal | Site bans and account authorization. |
| awakemud | Admin | immortal | echo / aecho / gecho / zecho / vteleport | immortal | Echo text to room/area/game/zone. |
| awakemud | Admin | immortal | wizhelp / wwho / wtell / wf | immortal | Immortal help, who, wiztell, wizfeel. |
| awakemud | Admin | immortal | hcontrol / houseedit | immortal | Housing (player apartment) admin. |
| awakemud | Admin | immortal | copyover / reboot / shutdown / crashmud | immortal | Server lifecycle control. |
| awakemud | Admin | immortal | cheatlog / cheatmark / logwatch / tridlog | immortal | Audit/anti-cheat logging. |
| awakemud | Admin | immortal | perfmon / metrics / users / fuckups | immortal | Performance, metrics, connected users, error log. |
| awakemud | Admin | immortal | olc / debug / settime / wizlock / slowns | immortal | OLC toggle and low-level dev tools. |
| dikumud3 | Player | info | look `[target]` | any | Show room, unit, or object description. |
| dikumud3 | Player | info | examine `<obj>` | any | Detailed look at object/container/unit. |
| dikumud3 | Player | info | exits / doors / directions | any | List visible room exits. |
| dikumud3 | Player | info | score | any | Show own stats, HP/mana, level, gold. |
| dikumud3 | Player | info | inventory / equipment | any | List carried / worn items. |
| dikumud3 | Player | info | skills / spells | any | List known skills / spells and levels. |
| dikumud3 | Player | info | who / wizlist | any | List online players / immortals. |
| dikumud3 | Player | info | help / wizhelp `<topic>` | any | Help database lookup. |
| dikumud3 | Player | info | commands / socials | any | List available commands / social emotes. |
| dikumud3 | Player | info | areas / news / motd / credits / info | any | Zone list, news, message-of-day, credits. |
| dikumud3 | Player | info | time / weather | any | Show MUD time / weather. |
| dikumud3 | Player | info | quests | any | Show quest progress. |
| dikumud3 | Player | comm | say `<msg>` | any | Speak to room. |
| dikumud3 | Player | comm | tell `<who> <msg>` | any | Private message to player. |
| dikumud3 | Player | comm | shout / broadcast | any | Global/zone-wide message. |
| dikumud3 | Player | comm | whisper / ask `<who> <msg>` | any | Quiet in-room message. |
| dikumud3 | Player | comm | emote / :  `<action>` | any | Freeform action to room. |
| dikumud3 | Player | comm | mail `<who>` | any | Send in-game mail. |
| dikumud3 | Player | comm | noshout / afk / ignore | any | Toggle channel/away/ignore state. |
| dikumud3 | Player | comm | socials (~200: hug, bow, grin, wave…) | any | Predefined emote table (compressed). |
| dikumud3 | Player | object | get / take / drop / put `<obj>` | any | Move objects to/from inventory/ground. |
| dikumud3 | Player | object | give `<obj> <who>` | any | Transfer object to another unit. |
| dikumud3 | Player | object | wear / wield / hold / remove | any | Equip / unequip items. |
| dikumud3 | Player | object | open / close / lock / unlock / knock | any | Operate doors and containers. |
| dikumud3 | Player | object | buy / sell / list / value | any | Shop interaction. |
| dikumud3 | Player | object | donate / drag / split (coins) | any | Misc object/coin handling. |
| dikumud3 | Player | mobile | rest / sit / stand / sleep / wake | any | Change body position. |
| dikumud3 | Player | mobile | mount / dismount / ride | any | Mount handling. |
| dikumud3 | Player | mobile | follow / group | any | Follow leader / manage party. |
| dikumud3 | Player | mobile | enter / leave / sail | any | Enter portals/vehicles (movement compressed). |
| dikumud3 | Player | combat | kill / hit / cast / flee | any | Initiate/resolve combat, spellcast (compressed). |
| dikumud3 | Player | info | prompt / alias / color / change | any | Configure prompt, aliases, ANSI, who-status. |
| dikumud3 | Player | info | trigger / variable / piset / pilist | any | Player-side triggers and stored variables. |
| dikumud3 | Player | info | quit / save / delete / account / reroll | any | Session/character management. |
| dikumud3 | Admin | wizard | goto `<room/who>` | wizard/god | Teleport self to room or unit. |
| dikumud3 | Admin | wizard | at `<loc> <cmd>` | wizard/god | Run a command at a remote location. |
| dikumud3 | Admin | wizard | transfer `<who>` | wizard/god | Summon a player to self. |
| dikumud3 | Admin | wizard | load `<mob/obj vnum>` | wizard/god | Instantiate mobile/object from template. |
| dikumud3 | Admin | wizard | purge `[target]` | wizard/god | Destroy mobs/objects in room (or target). |
| dikumud3 | Admin | wizard | set / nset `<field> <val>` | wizard/god | Set unit fields/flags (nset = extended). |
| dikumud3 | Admin | wizard | restore `<who>` | wizard/god | Full-heal a unit. |
| dikumud3 | Admin | wizard | force `<who> <cmd>` | wizard/god | Force a unit to run a command. |
| dikumud3 | Admin | wizard | snoop / switch `<who>` | wizard/god | Spy on / possess a unit's I/O. |
| dikumud3 | Admin | wizard | stat / wstat / cstat / jstat | wizard/god | Inspect internal unit/DIL/JSON data. |
| dikumud3 | Admin | wizard | wizinv / where / users / corpses | wizard/god | Invisibility, locate units, session list. |
| dikumud3 | Admin | wizard | freeze / petrify / zap / mash | wizard/god | Punitive controls on a player. |
| dikumud3 | Admin | wizard | echo / message / broadcast | wizard/god | Inject server text to players. |
| dikumud3 | Admin | wizard | ban / wizlock / badnames | wizard/god | Site/name ban and login lock. |
| dikumud3 | Admin | wizard | advance / setskill / makemoney | wizard/god | Grant levels/skills/currency. |
| dikumud3 | Admin | wizard | copy / dig | wizard/god | Duplicate unit / create room-link. |
| dikumud3 | Admin | wizard | reset / zonereset | wizard/god | Force zone reset. |
| dikumud3 | Admin | wizard | wpath / plog / boards | wizard/god | Path trace, player log, immortal boards. |
| dikumud3 | Admin | wizard | shutdown / reboot / crash / execute / timewarp | god/ultimate | Server lifecycle and shell exec. |
| dikumud3 | Builder | building | wedit `<unit>` | wizard/god | Online unit editor (beginedit/killedit driven). |
| dikumud3 | Builder | building | .zon zone source (vmc compiler) | builder | Zones authored as DIL-embedded source, compiled offline. |
| dikumud3 | Builder | building | %rooms / %mobiles / %objects / %zone / %dil | builder | Zone-file section directives for unit/DIL definitions. |
| dikumud3 | Builder | building | reset RESET_* / load / dilcopy (in .zon) | builder | Zone reset commands: spawn units, attach DIL. |
| dikumud3 | Softcode-fn | dil | dilbegin … code { } dilend | dil-script | Define a DIL program/function body. |
| dikumud3 | Softcode-fn | dil | var / external / recurse sections | dil-script | Declare locals, external symbols, recursion depth. |
| dikumud3 | Softcode-fn | dil | dilcopy `(name,u)` | dil-script | Attach a named DIL template to a unit. |
| dikumud3 | Softcode-fn | dil | dilcall `(fn(args))` | dil-script | Call another DIL program as a function. |
| dikumud3 | Softcode-fn | dil | dildestroy `(name,u)` | dil-script | Detach/remove a DIL program from a unit. |
| dikumud3 | Softcode-fn | dil | dilfind `(name,u)` | dil-script | Test whether a unit has a named DIL program. |
| dikumud3 | Softcode-fn | dil | hasfunc `(u,name)` | dil-script | Check unit for a DIL function symbol. |
| dikumud3 | Softcode-fn | dil | if / else | dil-script | Conditional branch. |
| dikumud3 | Softcode-fn | dil | while | dil-script | Loop while expression true. |
| dikumud3 | Softcode-fn | dil | foreach `(kind,u)` | dil-script | Iterate local/contained units (auto-secured). |
| dikumud3 | Softcode-fn | dil | break / continue | dil-script | Exit / restart current loop. |
| dikumud3 | Softcode-fn | dil | goto `:label:` | dil-script | Unconditional jump to label. |
| dikumud3 | Softcode-fn | dil | return `[expr]` / quit | dil-script | Return from function / terminate whole program. |
| dikumud3 | Softcode-fn | dil | wait `(flags,expr)` | dil-script | Suspend until matching SFB_* message + condition. |
| dikumud3 | Softcode-fn | dil | waitnoop | dil-script | Yield one pulse without consuming a message. |
| dikumud3 | Softcode-fn | dil | pause | dil-script | Deactivate program until externally resumed. |
| dikumud3 | Softcode-fn | dil | heartbeat := `<pulses>` | dil-script | Set SFB_TICK rate (units of PULSE_SEC/4s). |
| dikumud3 | Softcode-fn | dil | interrupt `(flags,expr,label)` | dil-script | Register message-class interrupt handler. |
| dikumud3 | Softcode-fn | dil | on_activation `(expr,label)` | dil-script | Interrupt run before every activation. |
| dikumud3 | Softcode-fn | dil | on_goto `(...)` | dil-script | Interrupt on unit movement. |
| dikumud3 | Softcode-fn | dil | priority / nopriority | dil-script | Suppress/restore lower special procs. |
| dikumud3 | Softcode-fn | dil | block | dil-script | Cancel the player command being processed. |
| dikumud3 | Softcode-fn | dil | secure `(u,label)` / unsecure `(u)` | dil-script | Protect unitptr; jump to label if unit leaves. |
| dikumud3 | Softcode-fn | dil | exec `(cmd,u)` | dil-script | Make unit perform a command string. |
| dikumud3 | Softcode-fn | dil | act `(msg,vis,ch,med,vict,to)` | dil-script | Send visibility-filtered message to room. |
| dikumud3 | Softcode-fn | dil | sendto `(s,u)` / send `(s)` | dil-script | Send text to a unit / current activator. |
| dikumud3 | Softcode-fn | dil | sendtext `(s,u)` | dil-script | Send raw text (web/markup) to a unit. |
| dikumud3 | Softcode-fn | dil | sendtoall / sendtoalldil | dil-script | Broadcast text to all players / all DIL. |
| dikumud3 | Softcode-fn | dil | send_pre / send_done | dil-script | Emit before/after standard action messages. |
| dikumud3 | Softcode-fn | dil | log `(s)` / flog `(f,s)` / logcrime | dil-script | Write debug log / file log / crime log. |
| dikumud3 | Softcode-fn | dil | link `(u,t)` | dil-script | Move unit into another unit's hierarchy. |
| dikumud3 | Softcode-fn | dil | destroy `(u)` / delunit `(u)` | dil-script | Remove a unit from the game. |
| dikumud3 | Softcode-fn | dil | set `(u,flag)` / unset `(u,flag)` / setbright | dil-script | Set/clear unit flags. |
| dikumud3 | Softcode-fn | object | addequip / equip / unequip | dil-script | Equip/unequip an object on a unit. |
| dikumud3 | Softcode-fn | dil | addaff / subaff | dil-script | Add/remove an affect (buff/debuff). |
| dikumud3 | Softcode-fn | dil | addextra / subextra `(exd,name,val)` | dil-script | Add/remove extra-descr or key/value on unit. |
| dikumud3 | Softcode-fn | dil | addstring / delstr / insert / remove / clear | dil-script | Manipulate DIL string/integer lists. |
| dikumud3 | Softcode-fn | comm | addcolor / delcolor / changecolor / getcolor | dil-script | Manage a unit's color config. |
| dikumud3 | Softcode-fn | dil | store `(u,file,cont)` / load templates | dil-script | Persist a unit tree to a rent/file. |
| dikumud3 | Softcode-fn | dil | savestr / loadstr | dil-script | Save/load a string to persistent extra data. |
| dikumud3 | Softcode-fn | dil | dispatch | dil-script | Re-dispatch current message to special procs. |
| dikumud3 | Softcode-fn | building | beginedit / killedit / pagestring | dil-script | Enter/exit string editor; paged output. |
| dikumud3 | Softcode-fn | room | setroomexit `(...)` | dil-script | Create/modify a room exit at runtime. |
| dikumud3 | Softcode-fn | mobile | follow `(u,t)` | dil-script | Make a unit follow another. |
| dikumud3 | Softcode-fn | mobile | set_fighting / stop_fighting | dil-script | Start/stop combat between units. |
| dikumud3 | Softcode-fn | mobile | cast_spell / attack_spell `(...)` | dil-script | Cast a spell / spell attack from script. |
| dikumud3 | Softcode-fn | mobile | position_update `(u)` | dil-script | Recompute a unit's position after HP change. |
| dikumud3 | Softcode-fn | dil | acc_modify / transfermoney / paycheck | dil-script | Adjust account balance / move currency. |
| dikumud3 | Softcode-fn | admin | set_password / check_password / delete_player | dil-script | Player account credential/removal ops. |
| dikumud3 | Softcode-fn | admin | reboot / gamestate | dil-script | Trigger reboot / read-set server run state. |
| dikumud3 | Softcode-fn | dil | reset_level / reset_race / reset_vlevel | dil-script | Recompute derived unit stats. |
| dikumud3 | Softcode-fn | dil | findroom `(sym)` | dil-script | Find room by symbolic name -> unitptr. |
| dikumud3 | Softcode-fn | dil | findunit `(u,name,pos,from)` | dil-script | Locate a unit by name in a scope. |
| dikumud3 | Softcode-fn | dil | findsymbolic `(zone,name)` | dil-script | Resolve a symbolic zone#name reference. |
| dikumud3 | Softcode-fn | dil | findrndunit / findzone `(...)` | dil-script | Random matching unit / zone lookup. |
| dikumud3 | Softcode-fn | dil | clone `(u)` | dil-script | Duplicate a unit and its contents. |
| dikumud3 | Softcode-fn | dil | rnd `(a,b)` / openroll | dil-script | Random int in range / open-ended dice roll. |
| dikumud3 | Softcode-fn | dil | itoa / atoi | dil-script | Integer<->string conversion. |
| dikumud3 | Softcode-fn | dil | getword `(var s)` / getwords | dil-script | Pop first word / split words from string. |
| dikumud3 | Softcode-fn | dil | left / right / mid / substring / length | dil-script | String slicing and length. |
| dikumud3 | Softcode-fn | dil | toupper / tolower / replace / split | dil-script | Case, substitution, tokenization. |
| dikumud3 | Softcode-fn | dil | strcmp / strncmp | dil-script | Compare strings (also `$=`, `#=` operators). |
| dikumud3 | Softcode-fn | dil | textformat / moneystring / asctime | dil-script | Word-wrap, coin string, time formatting. |
| dikumud3 | Softcode-fn | dil | isname (`in` operator) / isset | dil-script | Name-in-list match / flag test. |
| dikumud3 | Softcode-fn | dil | isaff / islight / isplayer / visible / fits | dil-script | Predicate tests on units/objects. |
| dikumud3 | Softcode-fn | dil | can_carry `(u,obj)` | dil-script | Test if unit may carry object (weight/count). |
| dikumud3 | Softcode-fn | dil | pathto / unitdir / strdir | dil-script | Pathfinding direction / direction<->name. |
| dikumud3 | Softcode-fn | dil | ghead / zhead / chead / rhead / ohead / phead / nhead | dil-script | Global/zone/char/room/obj/pc/npc list heads. |
| dikumud3 | Softcode-fn | dil | gnext / next / gprevious | dil-script | Iterate global or contents linked lists. |
| dikumud3 | Softcode-fn | dil | getcmd / cmdstr / cmdptr / excmdstr / command_head | dil-script | Inspect/parse the current command being run. |
| dikumud3 | Softcode-fn | dil | getaffects / getfollower / getopponent / getinteger | dil-script | Query affects, followers, opponents, ints. |
| dikumud3 | Softcode-fn | mobile | opponent / opponentcount / follower / followercount / master | dil-script | Combat/follow relationship accessors. |
| dikumud3 | Softcode-fn | dil | spellindex / spellinfo / skill_name / weapon_name / weapon_info | dil-script | Look up spell/skill/weapon metadata. |
| dikumud3 | Softcode-fn | dil | symname / nameidx / idx | dil-script | Symbolic name and name-list index helpers. |
| dikumud3 | Softcode-fn | dil | realtime / mudday / mudhour / mudmonth / mudyear / weather | dil-script | Real and MUD time/weather values. |
| dikumud3 | Softcode-fn | dil | self / argument / activator / target / medium / power | dil-script | Reserved runtime pointers/vars in a program. |
| dikumud3 | Softcode-fn | dil | unit fields: `.name .names .type .position .level .exp` | dil-script | Read/write core unit identity/state fields. |
| dikumud3 | Softcode-fn | mobile | char fields: `.hp .max_hp .mana .endurance .sex .race .profession` | dil-script | Char point/vital field accessors. |
| dikumud3 | Softcode-fn | mobile | ability fields: `.skills .spells .abilities .weapons .exp .vlevel` | dil-script | Skill/spell/ability list accessors. |
| dikumud3 | Softcode-fn | object | obj fields: `.value .cost .rent .weight .objecttype .equip` | dil-script | Object economic/type field accessors. |
| dikumud3 | Softcode-fn | room | room fields: `.exits .outside .inside .mapx .mapy .roomflags` | dil-script | Room geometry/exit field accessors. |
| dikumud3 | Softcode-fn | dil | flag fields: `.flags .charflags .npcflags .pcflags .objectflags .openflags` | dil-script | Bitvector flag-set accessors. |
| dikumud3 | Softcode-fn | dil | container fields: `.extra .info .purse .quests .master .fighting` | dil-script | Extra-data, purse, quest, relation accessors. |
| dikumud3 | Softcode-fn | dil | SFB_TICK / SFB_CMD / SFB_COM / SFB_MSG / SFB_PRE / SFB_DONE / SFB_DEAD | dil-script | Message-class bits for wait/interrupt triggers. |
| swr | Player | piloting | board <ship> | any | Enter a ship/vehicle via its hatch. |
| swr | Player | piloting | leaveship | pilot | Exit ship to the room/space outside. |
| swr | Player | piloting | launch | pilot | Take off from ground/dock into space (cockpit). |
| swr | Player | piloting | land [target] | pilot | Land on planet or dock at a bay. |
| swr | Player | piloting | drive <dir> | pilot | Pilot a land speeder/vehicle one direction. |
| swr | Player | piloting | fly | pilot | Atmospheric-flight stub (unimplemented). |
| swr | Player | piloting | accelerate/speed/velocity <n> | pilot | Set sublight speed. |
| swr | Player | piloting | trajectory/course/vector <x y z> | pilot | Set heading toward coordinates. |
| swr | Player | piloting | calculate <system> | pilot | Compute hyperspace jump coordinates. |
| swr | Player | piloting | hyperspace/lightspeed | pilot | Jump to hyperspace toward calculated system. |
| swr | Player | piloting | jumpvector/entryvector <x y z> | pilot | Set hyperspace entry/exit vector. |
| swr | Player | piloting | autopilot | pilot | Toggle automated navigation. |
| swr | Player | piloting | autotrack | pilot | Auto-follow the current target. |
| swr | Player | piloting | refuel | pilot | Refuel ship (at fuel source). |
| swr | Player | piloting | openhatch / closehatch | pilot | Open/close ship boarding hatch. |
| swr | Player | piloting | openbay / closebay | pilot | Open/close carrier launch bay doors. |
| swr | Player | combat-space | target <ship> | pilot | Acquire a target ship in the system. |
| swr | Player | combat-space | fire [weapon] | pilot | Fire lasers/turbolasers at target. |
| swr | Player | combat-space | bomb | pilot | Drop bomb / proton ordnance. |
| swr | Player | combat-space | reload | pilot | Reload torpedoes/missiles. |
| swr | Player | combat-space | chaff | pilot | Launch countermeasures vs incoming missiles. |
| swr | Player | combat-space | recharge / autorecharge (shields) | pilot | Recharge shields; toggle auto-recharge. |
| swr | Player | combat-space | tractorbeam <ship> | pilot | Capture/hold another ship with tractor beam. |
| swr | Player | info | status | pilot | Show ship status (hull/shields/energy/speed). |
| swr | Player | info | radar | pilot | Scan nearby ships/objects in the starsystem. |
| swr | Player | info | info | pilot | Show current ship's stats/details. |
| swr | Player | info | ships | any | List ships (in shipyard/area you can access). |
| swr | Player | info | speeders | any | List land vehicles present. |
| swr | Player | info | starsystems | any | List known star systems. |
| swr | Player | info | planets | any | List planets. |
| swr | Player | ship | buyship <type> | any | Buy a ship at a shipyard. |
| swr | Player | ship | sellship <ship> | any | Sell a ship back at a shipyard. |
| swr | Player | ship | clanbuyship <type> | any | Buy a ship using clan funds. |
| swr | Player | ship | repairship / repair | pilot | Repair ship at a repair shop. |
| swr | Player | ship | addpilot <name> | pilot | Authorize another pilot for the ship. |
| swr | Player | ship | rempilot <name> | pilot | Revoke a ship pilot's authorization. |
| swr | Player | comm | spacetalk <msg> | pilot | Radio comm to ships in the same system. |
| swr | Player | comm | clantalk <msg> | any | Clan/faction private channel. |
| swr | Player | clan | clans | any | List clans/factions. |
| swr | Player | clan | newclan | any | Petition/create a new clan (application). |
| swr | Player | clan | induct <player> | any | Induct a player into your clan (leader). |
| swr | Player | clan | outcast <player> | any | Remove a member from your clan (leader). |
| swr | Player | clan | donate <amount> | any | Deposit credits to clan treasury. |
| swr | Player | clan | withdraw <amount> | any | Withdraw credits from clan treasury. |
| swr | OLC | ship | makeship <name> | immortal | Create a new ship prototype (lvl 105). |
| swr | OLC | ship | setship <field> <val> | immortal | Edit ship fields: shipyard/type/class/hyperspeed/maxspeed/etc (lvl 103). |
| swr | OLC | ship | showship <ship> | immortal | View a ship's full data (lvl 102). |
| swr | OLC | ship | copyship <src> <dst> | immortal | Clone a ship prototype (lvl 105). |
| swr | OLC | ship | resetship <ship> | immortal | Reset ship to spawn/prototype state (lvl 103). |
| swr | OLC | ship | allships / allspeeders | immortal | List every ship/vehicle in game. |
| swr | OLC | planet | makestarsystem <name> | immortal | Create a star system (lvl 103). |
| swr | OLC | planet | setstarsystem <field> <val> | immortal | Edit star system data (lvl 103). |
| swr | OLC | planet | showstarsystem <name> | immortal | View star system data (lvl 102). |
| swr | OLC | planet | makeplanet <name> | immortal | Create a planet in a system (lvl 105). |
| swr | OLC | planet | setplanet <field> <val> | immortal | Edit planet data (lvl 105). |
| swr | OLC | building | makerepair / repairset / repairstat / repairshops | immortal | Create/edit repair shops (shipyards) (lvl 102). |
| swr | OLC | building | makeshop / shopset / shopstat / shops | immortal | Create/edit vendor shops (inherited from SMAUG, extended). |
| swr | OLC | building | instaroom | immortal | Quick-create a room (lvl 102). |
| swr | Admin | clan | makeclan / setclan / showclan | immortal | Create/edit/view clan records (lvl 102-103). |
| swr | OLC | building | redit / rset / oset / mset / mpedit | builder | Room/object/mob/mobprog editing (inherited from SMAUG). |
| swr | Admin | building | aset / sset / slookup / foldarea | immortal | Area/skill/save admin (inherited from SMAUG). |
| swr | Player | comm | say / tell / channels | any | Standard chat (inherited from SMAUG/Diku). |
| swr | Player | info | look / score / who / where | any | Standard info (inherited from SMAUG/Diku). |
| swfote | Player | force | `lightning`/`force_lightning <victim>` | force-user (Sith) | Force lightning damage attack |
| swfote | Player | force | `slash <victim>` | force-user | Lightsaber slash strike |
| swfote | Player | force | `whirlwind` | force-user | Spinning saber hits all foes in room |
| swfote | Player | force | `squeeze`/`choke <victim>` | force-user (Sith) | Force grip/choke, ongoing damage |
| swfote | Player | force | `strike <victim>` | force-user | Telekinetic force strike |
| swfote | Player | force | `heal` | force-user (Jedi) | Force-heal self hp/wounds |
| swfote | Player | force | `protect <target>` | force-user | Grant force protection to ally |
| swfote | Player | force | `shield`/`fshield` | force-user | Raise defensive force shield |
| swfote | Player | force | `refresh` | force-user | Restore movement/energy via Force |
| swfote | Player | force | `awareness` | force-user | Force danger-sense / perception buff |
| swfote | Player | force | `sense` | force-user | Sense beings/force presence |
| swfote | Player | force | `meditate` | force-user | Meditate to regain force/mana |
| swfote | Player | force | `identify` | force-user | Force-identify an object |
| swfote | Player | force | `fdisguise` | force-user | Cloak identity via the Force |
| swfote | Player | force | `finish <victim>` | force-user | Finishing blow on downed foe |
| swfote | Player | force | `parry` | force-user (passive) | Auto lightsaber parry in melee |
| swfote | Player | force | `reflect` | force-user (passive) | Deflect blaster bolts with saber |
| swfote | Player | force | `finfo [power]` | force-user | Show force skills/level/alignment status |
| swfote | Player | force | `fhelp [topic]` | force-user | Force-specific help system |
| swfote | Player | force | `makelightsaber` | force-user | Craft a lightsaber |
| swfote | Player | force | `makedualsaber`/`dwieldsaber` | force-user | Craft/dual-wield double saber |
| swfote | Player | force | `train <stat>` | any/force-user | Train stats/force level at trainer |
| swfote | Player | force | `teach <skill>` | force-user | Teach a skill to another player |
| swfote | Player | force | `student`/`convert <name>` | force-user (master) | Take/convert a player as apprentice |
| swfote | Player | force | `promote <name>` | force-user (master) | Advance apprentice's force rank |
| swfote | Player | force | `master <name>` | force-user (master) | Mastery-train an apprentice |
| swfote | Player | force | `instruct <name>` | force-user (master) | Instruct student in a force skill |
| swfote | Builder | force | `fstat <power>` | immortal | View force-power definition (level/type/cost) |
| swfote | OLC | force | `fset <power> <field>` | immortal | Edit force-power data (Jedi/Sith/general, cost, effects) |
| swfote | Builder | force | `fhstat <topic>` | immortal | View force-help entry |
| swfote | OLC | force | `fhset <topic> <field>` | immortal | Edit force-help entries |
| swfote | Admin | force | `setforcer <victim> <lvl> [jedi/sith/neutral] <status> <pct>` | immortal | Set player force level/alignment/skill |
| swfote | Admin | force | `make_master`/`makemaster` | immortal | Grant force-master status |
| swfote | Builder | alignment | `mset <mob> align <n>` | immortal | Set alignment (light/dark side axis) |
| swfote | Player | empire | `clans` | any | List clans/factions/empires |
| swfote | Player | empire | `showclan <clan>` | any | Show clan detail |
| swfote | Player | empire | `clanstat <clan>` | member | Clan status/treasury/troops |
| swfote | Player | empire | `members` | member | List clan members |
| swfote | Player | empire | `clantalk`/`;` | member | Clan communication channel |
| swfote | Player | empire | `wartalk` | member | Wartime clan channel |
| swfote | Player | empire | `enlist` | any | Enlist/apply to a clan |
| swfote | Player | empire | `induct <name>` | leader | Induct a player into clan |
| swfote | Player | empire | `outcast <name>` | leader | Expel a clan member |
| swfote | Player | empire | `empower <name>` | leader | Grant leadership/deputy powers |
| swfote | Player | empire | `resign` | member | Resign from clan |
| swfote | Player | empire | `outlaw`/`unoutlaw <name>` | leader | Manage clan outlaw list |
| swfote | Player | empire | `war <clan>`/`checkwar` | leader | Declare/check inter-clan war |
| swfote | Player | empire | `buytroops`/`clanbuytroops` | leader | Purchase clan military troops |
| swfote | Player | empire | `setwage <n>` | leader | Set member wage payout |
| swfote | Player | empire | `donate`/`withdraw` | member/leader | Clan bank deposit/withdraw |
| swfote | Player | empire | `senate` | senator | Galactic senate assembly |
| swfote | Admin | empire | `addsenator`/`remsenator <name>` | immortal | Manage senate membership |
| swfote | Admin | empire | `makeclan`/`newclan`/`remclan` | immortal | Create/remove clan/empire |
| swfote | Builder | empire | `setclan <field>` | immortal | Edit clan properties |
| swfote | Player | planet | `planets` | any | List planets |
| swfote | Player | planet | `showplanet <planet>` | any | Show planet detail/owner |
| swfote | Player | planet | `capture` | member | Capture planet for your clan/empire |
| swfote | Admin | planet | `makeplanet <name>` | immortal | Create a planet |
| swfote | Builder | planet | `setplanet <field>` | immortal | Edit planet (owner, taxes, resources) |
| swfote | Player | space | `starsystems` | any | List star systems |
| swfote | Player | space | `showstarsystem <sys>` | any | Show star system detail |
| swfote | Admin | space | `makestarsystem <name>` | immortal | Create star system (SWR lineage) |
| swfote | Builder | space | `setstarsystem <field>` | immortal | Edit star system |
| swfote | Player | ship | `board`/`launch`/`land` | pilot | Enter/launch/land a ship |
| swfote | Player | ship | `leaveship` | any | Exit a docked ship |
| swfote | Player | ship | `fly`/`drive <dir>` | pilot | Pilot ship/vehicle |
| swfote | Player | ship | `accelerate <speed>` | pilot | Set ship speed |
| swfote | Player | ship | `trajectory`/`jumpvector`/`calculate` | pilot | Plot/hyperspace course |
| swfote | Player | ship | `hyperspace` | pilot | Enter hyperspace |
| swfote | Player | ship | `radar`/`status`/`info`/`target` | pilot | Ship sensors/status/targeting |
| swfote | Player | ship | `fire`/`reload`/`bomb` | pilot | Ship weapons fire/reload/bombing |
| swfote | Player | ship | `tractorbeam`/`chaff` | pilot | Tractor capture / countermeasures |
| swfote | Player | ship | `autopilot`/`autotrack`/`autorecharge` | pilot | Ship automation toggles |
| swfote | Player | ship | `refuel`/`recharge`/`shiprepair` | pilot | Ship maintenance |
| swfote | Player | ship | `openhatch`/`closehatch`/`openbay`/`closebay`/`shiplock` | pilot | Ship access control |
| swfote | Player | ship | `addpilot`/`rempilot` | owner | Manage authorized pilots |
| swfote | Player | ship | `buyship`/`sellship`/`ordership` | any | Purchase/sell/order ships |
| swfote | Player | ship | `clanbuyship`/`clangiveship`/`clansalvage`/`orderclanship` | member | Clan/empire ship logistics |
| swfote | Player | ship | `ships`/`allships`/`shiplist`/`showship`/`shipstat` | any | List/inspect ships |
| swfote | Player | ship | `speeders`/`allspeeders` | any | List ground speeders |
| swfote | Admin | ship | `makeship`/`setship`/`removeship`/`copyship`/`freeship` | immortal | Build/edit ship prototypes |
| swfote | Admin | ship | `makesimulator`/`endsimulator` | immortal | Ship combat training simulator |
| swfote | Player | ship | `bounty`/`addbounty`/`rembounty` | any/immortal | Bounty-hunting board |
| swfote | OLC | building | `redit` | immortal | Room editor (inherited from SMAUG) |
| swfote | OLC | building | `sedit` | immortal | Skill editor (inherited from SMAUG) |
| swfote | OLC | building | `hedit` | immortal | Help editor (inherited from SMAUG) |
| swfote | OLC | building | `cedit` | immortal | Command-table editor (inherited from SMAUG) |
| swfote | OLC | building | `mpedit`/`opedit`/`rpedit` | immortal | Mob/obj/room prog editors (inherited) |
| swfote | Builder | building | `oset`/`mset`/`rset`/`sset` | immortal | Set obj/mob/room/skill fields (inherited) |
| swfote | Builder | building | `reset` | immortal | Room reset editor (inherited from SMAUG) |
| swfote | Admin | info | `goto`/`transfer`/`mwhere`/`memory`/`purge`/`slay`/`restore` | immortal | Standard SMAUG wiz commands (inherited) |
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
| gomud | Player | comm | `say <text>` | any | Speak aloud to everyone in the room |
| gomud | Player | comm | `whisper <who> <text>` | any | Private message to one player |
| gomud | Player | comm | `shout <text>` | any | Shout to room and adjacent rooms |
| gomud | Player | comm | `broadcast <text>` | any | Message everyone connected |
| gomud | Player | comm | `emote <action>` | any | Custom roleplay emote |
| gomud | Player | comm | `ask <mob> <topic>` | any | Ask an NPC a question |
| gomud | Player | comm | `show <item> <who>` | any | Show an item to another player/mob |
| gomud | Player | comm | `whisper`/`say` history | any | `history` lists logged character events |
| gomud | Player | info | `look [target]` | any | Look at room, things, or nouns |
| gomud | Player | info | `exits` | any | List known exits in the room |
| gomud | Player | info | `map` | any | Area map centered on character |
| gomud | Player | info | `who` | any | Who is in the room with you |
| gomud | Player | info | `online` | any | Who is currently connected |
| gomud | Player | info | `inventory` | any | Summary of equipment and backpack |
| gomud | Player | info | `status` | any | Character summary/stats |
| gomud | Player | info | `experience` | any | Level and XP progress |
| gomud | Player | info | `skills` | any | List known skills |
| gomud | Player | info | `spells` | any | List learned spells |
| gomud | Player | info | `quests` | any | Current/completed quests |
| gomud | Player | info | `jobs` | any | Suggested jobs and progress |
| gomud | Player | info | `killstats` | any | Kill stats by mob type |
| gomud | Player | info | `consider <target>` | any | Gauge if an enemy is beatable |
| gomud | Player | info | `appraise <item>` | any | Pay merchant to identify an item |
| gomud | Player | info | `conditions` / `cooldowns` | any | Show active conditions / cooldowns |
| gomud | Player | info | `biome` | any | Info about current biome |
| gomud | Player | info | `keyring` | any | Track keys and picked locks |
| gomud | Player | info | `help [topic]` | any | Look up command/topic guidance |
| gomud | Player | info | `macros` | any | List/define multi-command macros |
| gomud | Player | info | `motd` / `print` | any | Message of the day / print text |
| gomud | Player | object | `get <item>` | any | Pick up item from ground |
| gomud | Player | object | `drop <item>` | any | Drop item onto the ground |
| gomud | Player | object | `give <item> <who>` | any | Give item to player/mob |
| gomud | Player | object | `put <item> <container>` | any | Put item into a container |
| gomud | Player | object | `equip <item>` | any | Wield/wear item from backpack |
| gomud | Player | object | `remove <item>` | any | Unequip item back to backpack |
| gomud | Player | object | `gearup` | any | Auto-equip best available gear |
| gomud | Player | object | `use <item>` | any | Use a usable item |
| gomud | Player | object | `drink` / `eat <item>` | any | Consume drinkable/edible item |
| gomud | Player | object | `read <item>` | any | Read notes and maps |
| gomud | Player | object | `stash <item>` | any | Hide an item in the room |
| gomud | Player | object | `storage` | any | Store/unstore items at storage |
| gomud | Player | object | `lock`/`unlock`/`picklock` | any | Lock, unlock, or pick exits/containers |
| gomud | Player | object | `buy`/`sell`/`list`/`offer` | any | Merchant trade commands |
| gomud | Player | object | `bank` | any | Deposit/withdraw at a bank |
| gomud | Player | object | `share` | any | Share wealth with party |
| gomud | Player | mobile | `go <area>` | any | Travel between areas (compresses dirs) |
| gomud | Player | mobile | `flee` | any | Attempt to run from combat |
| gomud | Player | mobile | `pet` / `pets` | any | Manage familiars that assist you |
| gomud | Player | mobile | `tame <creature>` | any | Tame a creature temporarily |
| gomud | Player | mobile | `train` / `stat-train` | any | Spend TP / stat points at guilds |
| gomud | Player | combat | `attack <target>` | any | Engage combat (also shoot/break) |
| gomud | Player | combat | `cast <spell>` | any | Cast a learned spell |
| gomud | Player | combat | skill.* verbs | any | Skill actions: backstab, disarm, sneak, portal, etc. |
| gomud | Player | party | `party` | any | Manage player parties/groups |
| gomud | Player | party | `pvp` | any | Toggle/participate in player-vs-player |
| gomud | Player | admin | `set <opt> <val>` | any | Configure account (prompt, wimpy, description, etc.) |
| gomud | Player | admin | `alias` | any | List/set command aliases |
| gomud | Player | admin | `password` | any | Change account password |
| gomud | Player | admin | `save` / `quit` | any | Save character / meditate-quit |
| gomud | Player | admin | `start` / `suicide` | any | Begin play / delete character |
| gomud | Player | comm | `inbox` / `mudmail` | any | Check in-game mail inbox |
| gomud | OLC | building | `build zone <name>` | builder | Create a new zone |
| gomud | OLC | building | `build room <exit>` | builder | Dig a new room via an exit |
| gomud | OLC | room | `room info\|set\|copy` | builder | Inspect/edit room properties |
| gomud | OLC | room | `room noun <name> <desc>` | builder | Add lookable descriptive nouns |
| gomud | OLC | room | `room exit <dir> <id>` | builder | Link/rename exits between rooms |
| gomud | OLC | room | `room secretexit <dir>` | builder | Make an exit hidden |
| gomud | OLC | room | `room edit containers\|exits\|mutators` | builder | Edit room sub-collections |
| gomud | OLC | mobile | `mob create` | builder | Create a new mob definition |
| gomud | OLC | mobile | `mob spawn <id/name>` | builder | Spawn a mob instance in room |
| gomud | OLC | mobile | `mob list [name]` | builder | List/search mob definitions |
| gomud | OLC | object | `item create` | builder | Create a new item definition |
| gomud | OLC | object | `item spawn <id/name>` | builder | Spawn an item instance |
| gomud | OLC | object | `item list [name]` | builder | List/search item definitions |
| gomud | OLC | building | `zone set autoscale <lo> <hi>` | builder | Set zone level autoscaling |
| gomud | OLC | building | `zone edit` | builder | Edit zone settings |
| gomud | Builder | object | `redescribe <item> "<desc>"` | builder | Rewrite an item's description |
| gomud | Builder | object | `rename <item> "<name>"` | builder | Rename an item, optional display name |
| gomud | Builder | mobile | `spawn gold <amt>` | builder | Spawn gold into the room |
| gomud | Builder | building | `prepare all` | builder | Load all rooms and spawn their mobs |
| gomud | Builder | mobile | `locate <name>` | builder | Find room of a player/mob (wildcards) |
| gomud | Admin | admin | `teleport <id/dir/name>` | admin | Teleport to room, direction, or player |
| gomud | Admin | admin | `grant [target] <amt> experience` | admin | Grant XP to self or a user |
| gomud | Admin | admin | `buff <target> <buffid>` | admin | Apply a buff to a target |
| gomud | Admin | admin | `spell <target> <spell>` | admin | Force-apply a spell |
| gomud | Admin | admin | `skillset <skill> <lvl>` | admin | Set skill levels (or `all`) |
| gomud | Admin | admin | `modify role <user> <role>` | admin | Change a user's role |
| gomud | Admin | admin | `command <user/mob> <action>` | admin | Force a user/mob to run a command |
| gomud | Admin | admin | `paz` / `zap [target]` | admin | Full-heal self / drop target to 1hp |
| gomud | Admin | admin | `questtoken <name>` | admin | Grant/list quest tokens |
| gomud | Admin | admin | `reload <items\|translations\|...>` | admin | Hot-reload data files |
| gomud | Admin | admin | `server` | admin | Server management/info actions |
| gomud | Admin | admin | `syslogs` | admin | Watch live server logs |
| gomud | Admin | admin | `mute`/`unmute`/`deafen`/`undeafen` | admin | Silence/deafen players (child safety) |
| gomud | Admin | admin | `badcommands` | admin | Review unrecognized command attempts |
| gomud | Softcode-fn | scripting | `onCommand(cmd,...)` | script | Handler: intercept a command on room/mob/item |
| gomud | Softcode-fn | scripting | `onCommand_<cmd>(...)` | script | Handler: intercept one specific command |
| gomud | Softcode-fn | scripting | `onEnter(actor,room)` | script | Handler: actor enters room |
| gomud | Softcode-fn | scripting | `onLoad()` | script | Handler: script/entity load init |
| gomud | Softcode-fn | scripting | `onIdle()` | script | Handler: mob idle tick |
| gomud | Softcode-fn | scripting | `onDie()` / `onPlayerDowned()` | script | Handler: death / player downed |
| gomud | Softcode-fn | scripting | `onGive` / `onAsk` / `onShow` | script | Handlers: give, ask, show interactions |
| gomud | Softcode-fn | scripting | `onCast`/`onMagic`/`onFail` | script | Handlers: spell cast/effect/failure |
| gomud | Softcode-fn | scripting | `onWait`/`onPath`/`onLost`/`onLoad` | script | Handlers: wait, pathing, path-lost, load |
| gomud | Softcode-fn | scripting | `GetUser(id)` / `GetMob(id)` | script | Fetch a user/mob actor object |
| gomud | Softcode-fn | scripting | `GetRoom(id)` / `GetMap()` | script | Fetch a room object / area map |
| gomud | Softcode-fn | scripting | `ActorNames(...)` | script | List actor names for matching |
| gomud | Softcode-fn | scripting | `CreateItem(id)` | script | Create an item instance |
| gomud | Softcode-fn | scripting | `CreateEmptyRoomInstances(n)` | script | Instance empty rooms |
| gomud | Softcode-fn | scripting | `CreateInstancesFromRoomIds\|Zone(...)` | script | Instance rooms from ids/zone |
| gomud | Softcode-fn | scripting | `SendUserMessage(id,txt)` | script | Send text to one user |
| gomud | Softcode-fn | scripting | `SendRoomMessage(id,txt)` | script | Send text to a room |
| gomud | Softcode-fn | scripting | `SendRoomExitsMessage(...)` | script | Send text to adjacent rooms via exits |
| gomud | Softcode-fn | scripting | `SendBroadcast(txt)` | script | Broadcast to all players |
| gomud | Softcode-fn | scripting | `RaiseEvent(evt)` / `EventFlags()` | script | Emit an engine event / flags |
| gomud | Softcode-fn | scripting | `ExpandCommand(cmd)` | script | Expand/queue a command string |
| gomud | Softcode-fn | scripting | `UtilDiceRoll(spec)` | script | Roll dice from a spec string |
| gomud | Softcode-fn | scripting | `UtilGetRoundNumber()` | script | Current game round number |
| gomud | Softcode-fn | scripting | `UtilGetSeconds/MinutesToRounds\|Turns` | script | Convert real time to rounds/turns |
| gomud | Softcode-fn | scripting | `UtilGetTime\|SetTime\|IsDay\|SetTimeDay/Night` | script | Read/set game clock and day/night |
| gomud | Softcode-fn | scripting | `UtilGetTimeString()` | script | Formatted game time string |
| gomud | Softcode-fn | scripting | `UtilLocateUser(name)` | script | Find a user's location |
| gomud | Softcode-fn | scripting | `UtilFindMatchIn(...)` / `UtilStripPrepositions` | script | Fuzzy match / clean input text |
| gomud | Softcode-fn | scripting | `UtilApplyColorPattern` / `ColorWrap` | script | Apply color patterns to text |
| gomud | Softcode-fn | scripting | `UtilGetConfig(key)` | script | Read a server config value |
| gomud | Softcode-fn | scripting | `console.log(...)` | script | Debug logging to console |
| gomud | Softcode-fn | scripting | `modules.<ns>.<fn>` | script | Call module-registered custom functions |
| gomud | Softcode-fn | scripting | actor.Get* (Health/Mana/Stat/Level/Race...) | script | Actor read API: stats, hp/mp, level, party, pet |
| gomud | Softcode-fn | scripting | actor.Set*/Add* (Health/Mana/Gold/Alignment) | script | Actor mutate API: hp/mp/gold/alignment |
| gomud | Softcode-fn | scripting | actor.GiveItem/TakeItem/HasItemId/UpdateItem | script | Actor inventory manipulation |
| gomud | Softcode-fn | scripting | actor.GiveBuff/RemoveBuff/HasBuff/CancelBuffWithFlag | script | Actor buff management |
| gomud | Softcode-fn | scripting | actor.LearnSpell/HasSpell/TrainSkill/GetSkillLevel | script | Actor spell/skill management |
| gomud | Softcode-fn | scripting | actor.GiveQuest/HasQuest/GrantXP | script | Actor quest and XP grants |
| gomud | Softcode-fn | scripting | actor.MoveRoom/Command/CommandFlagged/Pathing | script | Move actor, force commands, set pathing |
| gomud | Softcode-fn | scripting | actor.Charm*/Uncurse/Tame/GiveExtraLife | script | Charm, curse, tame, life mechanics |
| gomud | Softcode-fn | scripting | actor.TimerSet/TimerExists/TimerExpired | script | Per-actor script timers |
| gomud | Softcode-fn | scripting | actor.Get/SetTempData / Misc/PermData | script | Actor temp & persistent script storage |
| gomud | Softcode-fn | scripting | room.GetPlayers/GetMobs/GetItems/GetContainers | script | Room contents queries |
| gomud | Softcode-fn | scripting | room.SpawnMob/SpawnItem/RepeatSpawnItem/DestroyItem | script | Room spawning and item removal |
| gomud | Softcode-fn | scripting | room.GetExits/AddTemporaryExit/RemoveTemporaryExit | script | Room exit inspection and temp exits |
| gomud | Softcode-fn | scripting | room.SetLocked/IsLocked/SendText/SendTextToExits | script | Room lock state and messaging |
| gomud | Softcode-fn | scripting | room.AddMutator/HasMutator/RemoveMutator | script | Room mutator (dynamic state) control |
| gomud | Softcode-fn | scripting | room.Has/MissingQuest / Get/SetTemp\|PermData | script | Room quest checks and script storage |
| gomud | Softcode-fn | scripting | item.Name*/Rename/Redescribe/ItemId | script | Item identity and description API |
| gomud | Softcode-fn | scripting | item.GetUsesLeft/SetUsesLeft/AddUsesLeft/MarkLastUsed | script | Item charges/uses tracking |
| gomud | Softcode-fn | scripting | party.GetMembers/SendText/GiveBuff/GrantXP/MoveRoom | script | Party-wide actions mirroring actor API |

*Status: raw reference catalog, no decisions taken. Analysis: [reference-synthesis.md](reference-synthesis.md).*
