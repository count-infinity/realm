# GoMud command & scripting surface catalog

| Codebase | Type | Group | Name | Scope | Description |
|---|---|---|---|---|---|
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
