# PennMUSH Softcode Inventory vs REALM

A survey of **PennMUSH**'s builder-facing surface — its **531 softcode
functions** and its **standard attributes**, with emphasis on the
**action-attribute** family (`@afail`, `@aenter`, `@asuccess`, …) — mapped
onto what REALM has, is missing, or covers differently. Pulled from the
`~/pennmush` source (`src/function.c` for the function table; `did_it()` /
`real_did_it()` call sites in `src/{move,look,rob,set,create,destroy}.c` for
the action-attribute hooks).

The headline framing, before the detail: **most of Penn's 531 functions
exist because MUSHcode has no native data structures.** REALM's softcode is
a Python subset, so strings, lists, maps, and math are the *language*, not a
library — roughly half of Penn's function count evaporates. What's left, and
what actually matters for parity, is the **MU\*-domain** surface: object/db
access, attributes, communication, authority-carrying evaluation,
connection introspection — plus the **action-attribute hooks**, which is
where the real gaps live.

---

## Part 1 — Action attributes (the `@afail` / `@aenter` family)

### Penn's model: the message triple

Every interaction in Penn fires a **triple** through `did_it()`:

| slot | attribute | who sees it |
|---|---|---|
| message | `@success` | the enactor |
| omessage | `@osuccess` | everyone else in the room |
| **action** | **`@asuccess`** | **softcode run as the object** |

So `@asuccess exit = @tel me=#123` runs when someone traverses the exit;
`@ofail exit = tries the door, but it's locked.` shows the room a failure.
This (`msg` / `omsg` / `a`-action) pattern repeats across every built-in
event.

### The built-in hooks, and REALM's equivalent

Authoritative list from the `did_it` call sites plus the connect/listen
paths:

| Penn event (attr triple) | Fires when | REALM equivalent | Status |
|---|---|---|---|
| `@success`/`@osuccess`/`@asuccess` | look/get/traverse succeeds | `event:look`/`event:get` + `add_message` + `ON_<EVENT>` trigger | ◑ partial |
| **`@failure`/`@ofail`/`@afail`** | **an action is blocked / an exit is a dead-end** | **`event:on_fail` → `ON_FAIL` trigger** (shipped 2026-07-12) | ● have |
| `@enter`/`@oenter`/`@aenter` | something enters a room/object | `event:on_enter` → `ON_ENTER` trigger | ● have |
| `@leave`/`@oleave`/`@aleave` | something leaves | `event:on_leave` → `ON_LEAVE` | ● have |
| `@zenter`/`@zleave` (`AZENTER`) | zone-level enter/leave | zone-master witnesses room events (Penn ZMR parity) | ● have |
| `@drop`/`@odrop`/`@adrop` | object dropped | `drop` verb core (event) | ◑ partial |
| `@move`/`@amove` | object moved | covered by on_enter/on_leave | ◑ partial |
| `@use`/`@ouse`/`@ause` (+`RUNOUT`) | `use`d, with charge depletion | `use` command; no charge/`RUNOUT` convention | ◑ partial |
| `@give`/`@agive`, `@receive`/`@areceive` | give/receive an object | `give` verb; no receive hook | ◑ partial |
| `@aconnect` / `@adisconnect` | player connects / disconnects | `event:connect` / `event:disconnect` → `ON_CONNECT` | ● have |
| **`@startup`** | **server (re)boot** | **— Python `init_world` only, no softcode hook —** | ✗ **gap** |
| `@listen` + `@ahear`/`@amhear`/`@aahear` | overheard text matches a pattern | **`^listen`** (pattern → action on overheard) | ● have (a strength) |
| `@apayment`/`@abuy` | paid / bought | `event:payment` → `ON_PAYMENT` | ● have (payment) |
| `@afollow`/`@aunfollow` | follow / unfollow | follow/party system (no fire-hook) | ◑ partial |
| `@atport` | teleported | no teleport event | ✗ gap |
| `@adescribe`/`@aidescribe` | looked at | `event:look` | ◑ partial |
| `@away` / `IDLE` | idle / away messaging | — | ✗ gap (minor) |
| `@aclone`, `@adestroy`, `@amail` | cloned / destroyed / mailed | — (destroy is Python-side) | ✗ gap (minor) |

### What this tells us

1. **REALM already has Penn's action-attribute mechanism** — it's
   `ON_<EVENT>` triggers plus `^listen`, riding the propagation stream.
   Enter/leave/connect/disconnect/speech/payment are all covered, and
   `^listen` (pattern-matched reactions to overheard text) is *cleaner* than
   Penn overloading `@listen`/`@ahear`.

2. **The failure hook — `@afail` — is now built** (`event:on_fail`,
   2026-07-12). `move_through_exit` fires it on every blocked return
   (locked / closed / skill-fail / enter-lock / on_leave-veto), and the two
   dead-end (no-destination) sites fire it too. `ON_FAIL` softcode on the
   exit or room reacts, post-hoc like Penn's `@afail`. The dead-end case
   originally doubled as the **wilderness/portal** primitive (an `ON_FAIL`
   that materializes the room beyond and moves the walker in — still
   supported as the legacy pattern), but formula-resolved exit destinations
   have since shipped as their own primitive: a deferred-destination
   resolver registry (`register_dest_resolver`,
   `db.dest_resolver = "wilderness" | "instance"` —
   `realm/core/movement.py`, `realm/core/wilderness.py`,
   `realm/core/instances.py`). `move_through_exit` materializes the room
   after the origin-side gates pass, and the traversal proceeds like any
   door. `ON_FAIL` remains the post-hoc failure hook, Penn-`@afail` style.
   (`enter_instance` gained an
   enactor-consent rule so a portal exit — which doesn't *control* the
   walker — may still send the walker who triggered it, gated by the
   template's ENTER lock.)

3. **Message-triple authoring** (`@success`/`@osuccess` uniformly on every
   object) is a builder convenience REALM only half-has (per-command
   `add_message` + triggers). A uniform `succ`/`osucc`/`afail` attribute
   convention on any object would close it — cheap, and very Penn-familiar.

4. **`@startup`** (softcode that runs at boot) has no REALM analog; a
   `startup`-tagged trigger fired after world-load would match it.

**Done (2026-07-12):** **`event:on_fail`** is fired by `move_through_exit`
(every blocked return, plus its own dead-end branch when a deferred
resolver yields nothing) and the two entry-point dead-end sites, carrying
the exit + reason; `ON_FAIL` / `@afail` softcode reacts, and an authored
`@afail` may still materialize-and-move (the legacy portal pattern).
`realm/core/movement.py:fire_exit_fail`, `tests/test_fail_event.py`. The
wilderness feature (ephemeral Stage 2) has since shipped on the separate
deferred-destination resolver (`realm/core/wilderness.py`), not on this
trigger.

---

## Part 2 — The 531 functions

### Category A — subsumed by Python (REALM needs ~none of these)

Because REALM softcode is Python, these Penn categories are native language
operators/methods, not functions to port:

- **Strings** (~70): `CAPSTR CENTER LJUST RJUST MID LEFT RIGHT STRLEN
  STRREPLACE EDIT TRIM SQUISH SPACE POS BEFORE AFTER REST FIRST WORDS
  WORDPOS REVWORDS SCRAMBLE REPEAT …` → Python `str` methods, slicing,
  f-strings.
- **Lists/sets** (~50): `FILTER FOLD MAP MIX MUNGE SORT SORTBY SETUNION
  SETINTER SETDIFF SPLICE ITER STEP EXTRACT REMOVE LDELETE LINSERT MEMBER
  SHUFFLE UNIQUE ELEMENTS …` → Python lists, comprehensions,
  `sorted`/`filter`/`map`, `set` ops.
- **Math** (~40): `ADD SUB MUL DIV ABS SQRT SIN COS TAN LOG POWER BOUND MAX
  MIN MEAN MEDIAN STDDEV MODULO SIGN ROUND FLOOR CEIL …` → Python operators
  + a small math surface.
- **Bit ops**: `BAND BOR BXOR BNOT SHL SHR` → Python `& | ^ ~ << >>`.
- **Control-as-function**: `IF IFELSE SWITCH CASE COND AND OR NOT` → Python
  `if`/`match`/boolean operators.

That's **~200+ functions REALM gets for free** by being Python. This is the
core payoff of REALM's language choice and worth stating plainly: Penn needs
a function library to have data structures; REALM has a language. (REALM
does expose a small Penn-named convenience subset anyway — `capstr`, `mid`,
`trim`, `first`, `words`, `setunion`, etc. in
`realm/scripting/functions.py` — as sugar, not necessity.)

### Category B — MU\*-domain functions (where parity actually lives)

| Group | Representative Penn fns | REALM today | Verdict |
|---|---|---|---|
| Object access | `GET SET NAME LOC LOCATE PMATCH NUM OWNER PARENT CHILDREN CON EXIT NEXT LCON LEXITS RLOC HOME` | `get`/`set_attr`/`name`/`loc`/`owner`/`contents`/`exits`/`search_world` | ● most covered |
| Object creation | `CREATE DIG OPEN CLONE LINK` | `create_obj` (+ OLC `@dig`/`@open`) | ● covered (softcode `dig/open` thinner) |
| Attributes | `GET XGET LATTR HASATTR NATTR XATTR GREP REGRAB WIPE ATTRIB_SET LFLAGS` | `get_attr`/`has_attr`/`del_attr`/`tags` | ◑ covered; no `lattr`-glob / `grep`-over-attrs |
| Eval w/ authority | `U ULOCAL ULAMBDA PFUN ZFUN FN OBJEVAL GET_EVAL S R SETQ SETR LETQ LOCALIZE` | `eval_attr` (a *subroutine* call, NOT `u()`), Python locals for registers | ◑ **no true `u()`**: Penn's `u()` swaps the executor to the attribute's object (`call_ufun_int` → `process_expression(..., ufun->thing, caller, ...)`); `eval_attr` keeps the caller as executor, so it cannot escalate but `me` inside it is the caller. The `u()`-semantics library call is the `@function` entry in BACKLOG. Also: no `ulambda` anon-fn, no Q-register sugar (Python vars instead) |
| Communication | `PEMIT REMIT OEMIT EMIT LEMIT ZEMIT PROMPT MESSAGE SPEAK` + `NS*` no-spoof | `pemit`/`remit`/`oemit`/`prompt` + `act` (multiroom) | ● covered; no `@message`/`speak` formatter, no explicit no-spoof variants |
| Matching | `LOCATE PMATCH NAMEGRAB MATCH STRMATCH WILDGREP` | `search_world` + name matcher | ◑ have core; no Penn match-flag vocabulary |
| Locks | `LOCK ELOCK TESTLOCK LOCKFILTER LOCKFLAGS ANDLPOWERS` | `set_lock`/`test_lock`/`clear_lock` | ● covered |
| Connection/player | `CONN IDLE DOING POLL WHO LWHO MWHO XWHO HIDDEN IPADDR HOST TERMINFO SSL PORTS` | limited (`@stats`, session data) | ✗ mostly missing from softcode |
| Time | `TIME SECS CONVTIME CONVSECS TIMEFMT STRINGSECS ETIME UPTIME STARTTIME` | `now()` | ✗ thin — no `timefmt`/`convtime` |
| JSON | `JSON JSON_QUERY JSON_MOD ISJSON WSJSON` | — (Python `json` exists but unexposed) | ✗ gap (useful for OOB/client) |
| SQL | `SQL MAPSQL SQLESCAPE` | — (SQLite is the backend) | ✗ gap (deliberate?) |
| Crypto/encode | `DIGEST ENCRYPT DECRYPT ENCODE64 DECODE64 CHECKPASS HMAC SHA0 URLENCODE` | native auth (scrypt) | ◑ internal only |
| **Vectors** | **`VADD VSUB VDOT VCROSS VMAG VUNIT VDIM VMAX VMIN`** | **—** | ✗ **gap — directly relevant to the 3D spatial primitive** |
| Markup/ANSI | `ANSI ANSIGEN COLORS HTML TAG TAGWRAP RENDER STRIPANSI PUEBLO BEEP` | `ansi`/`escape` + pipe-markup at the edge | ● covered (REALM's model is cleaner) |
| Channels/mail | `CEMIT CHANNELS CWHO CMSGS MAIL MAILSEND MALIAS` | structured log channels; no player chat/mail | ✗ gap (no comms system yet) |

### Function steal-list (ranked)

1. **Vector math** (`VADD/VDOT/VCROSS/VMAG/VUNIT`) — not for MUSH nostalgia,
   but because they're the exact primitives the **3D spatial sidecar** (free
   flight / space combat) needs. If/when that gets built, ship these as
   softcode bindings.
2. **JSON functions** (`json`, `json_query`, `json_mod`) — high value for
   OOB/GMCP client payloads and structured data; thin `@softcode_function`
   wrappers over Python `json`.
3. **`lattr`/`grep`-over-attributes + match-flags** — iterate/glob an
   object's attributes and Penn-style flexible object matching; useful for
   generic tools.
4. **Time formatting** (`timefmt`, `convtime`, `stringsecs`) — cheap, and
   builders reach for it constantly.
5. **`ulambda`** (anonymous softcode function value) — REALM has `u()`
   (`eval_attr`); an inline lambda you can pass to a map/filter would round
   out the functional style.
6. **Connection introspection** (`conn`, `idle`, `doing`, `who`) — expose
   read-only session data to softcode for social/status tooling.

---

## Verdict

- **Language primitives:** REALM wins by construction — Python subsumes
  ~200 of Penn's functions. Don't port them.
- **Action attributes:** REALM has the full mechanism (`ON_<EVENT>` +
  `^listen`); the failure hook (`@afail` = `event:on_fail`) shipped
  2026-07-12. Formula-resolved exit destinations shipped separately as the
  deferred-destination resolver (`db.dest_resolver`), so the
  wilderness/portal primitive no longer lives in the failure hook.
- **Domain functions:** core covered (object/attr/comm/lock/eval/markup);
  worthwhile targets are **vectors** (for future space), **JSON** (for
  clients), attribute-globbing, and time formatting.
- **Whole subsystems Penn has that REALM doesn't:** player **channels &
  mail** (a comms system), and **connection introspection** — separate
  features, not function ports.

*Status: reference survey, no decisions taken — captured for evaluation.
See also [LambdaMOO Comparison](moo-comparison.md) and the
[Features Roadmap](features-roadmap.md).*
