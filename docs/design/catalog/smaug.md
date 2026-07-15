# SmaugFUSS Command Surface Catalog (player, builder, immortal, MOBprog)

| Codebase | Type | Group | Name | Scope | Description |
|----------|------|-------|------|-------|-------------|
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
