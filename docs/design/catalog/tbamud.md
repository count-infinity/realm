# tbaMUD (CircleMUD/OasisOLC/DG Scripts) Command & Function Surface Catalog

| Codebase | Type | Group | Name | Scope | Description |
|----------|------|-------|------|-------|-------------|
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
