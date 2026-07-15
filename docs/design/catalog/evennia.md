# Evennia Command & Inline-Function Surface (default cmdsets + FuncParser)

| Codebase | Type | Group | Name | Scope | Description |
|----------|------|-------|------|-------|-------------|
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

_Note: Evennia has no in-world softcode language. Player/builder-authored dynamic text is limited to the `$func` FuncParser callables above (used in prototypes, msg templates, room/emote text), while arbitrary logic requires `@py` / batch-code — Python at the developer/superuser level, not an in-game scripting DSL._
