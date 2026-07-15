# CoffeeMud Command, Builder (OLC) & Scriptable (MOBprog) Surface

| Codebase | Type | Group | Name | Scope | Description |
|----------|------|-------|------|-------|-------------|
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
