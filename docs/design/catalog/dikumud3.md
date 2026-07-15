# DikuMUD3 (Valhalla / VME) Command & DIL Scripting Surface Catalog

| Codebase | Type | Group | Name | Scope | Description |
|----------|------|-------|------|-------|-------------|
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
