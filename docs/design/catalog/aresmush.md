# AresMUSH Command Surface Catalog (player/builder/admin commands; no in-world softcode)

| Codebase | Type | Group | Name | Scope | Description |
|----------|------|-------|------|-------|-------------|
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

*Note: AresMUSH has NO in-world softcode/user functions (it replaces MUSHcode with server-side Ruby plugins), so there are zero Softcode-fn rows. OLC is also absent as a distinct mode; building is done via plain builder commands (`build`, `open`, `area/*`).*
