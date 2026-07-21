# REALM Command & Softcode Surface Catalog (baseline)

| Codebase | Type | Group | Name | Scope | Description |
|---|---|---|---|---|---|
| realm | Player | perception | look (l) | any | Look at surroundings or an object |
| realm | Player | perception | examine (ex/exam) | any | Examine an object in detail |
| realm | Player | perception | search | any | Search room/container for hidden things |
| realm | Player | movement | go <dir> | any | Move in a direction |
| realm | Player | movement | <direction> (n/s/e/w/u/d...) | any | Directional movement shortcuts |
| realm | Player | movement | in / out | any | Enter or exit |
| realm | Player | movement | recall | any | Return to your home |
| realm | Player | object | inventory (i/inv) | any | Show your inventory |
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
