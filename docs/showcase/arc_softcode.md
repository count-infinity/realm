# Arc: Softcode for builders

**REALM's native extension model, from one verb to player-authored
content.**

Every MU* lineage answers the same question — how do people extend the
game *without* touching source? PennMUSH answered with softcode on
objects, DikuMUD with MOBprogs, LPMud with a whole in-game language.
REALM's answer is the subject of this arc: a sandboxed, Turing-complete
scripting layer that lives in ordinary attributes, runs under one
authority model, and is safe enough to hand to players. Five tutorials
walk it end to end; by the capstone you have toured the engine's entire
extension surface without writing a line of Python outside the game.

This arc has a mirror. The Solar Frontiers showcase covers the same five
item numbers on Evennia — and there, each one had to be **built**:
per-object cmdsets coded in Python, a custom action language written and
interpreted, a YAML-to-trigger compiler, FuncParser callables registered
by hand, a bespoke six-layer gadget sandbox. On REALM the same arc is a
**tour, not a construction project**: `$`-verbs, `ON_<EVENT>` hooks,
exportable trigger data, `[[...]]` inline blocks, and the player-grade
sandbox are all engine-native. The five tutorials contain in-game
command transcripts and nothing else — which is itself the demonstration.

Tests: `pytest tests/showcase/test_softcode.py` (drives every Build-it
transcript through a real in-process world).

## The tutorials, in order

1. **[243. Object-verb pattern](243_object_verbs.md)** — attach bespoke
   commands to a single object: a jukebox that understands `play` and
   `tracks`. The `$pattern:code` trigger, wildcard captures, the `use`
   lock — and the boundary that builtins always dispatch first, so
   softcode extends the vocabulary but can never hijack `say`.
2. **[240. Builder trigger system](240_builder_triggers.md)** — the
   world acts back: `ON_ENTER`/`ON_GET` lifecycle hooks, `^listen`
   speech patterns, `on_tick` heartbeats, `@tr` test-firing, the `halt`
   kill-switch, and the full standard-event table.
3. **[241. Response scripting in data](241_yaml_responses.md)** —
   because triggers are attributes, they are *data*: an NPC's
   conversation repertoire round-trips through `@export`, a text editor,
   and `@import`'s Terraform-style plan/apply — and ships as `@pack`
   bundles.
4. **[242. Inline functions in text](242_inline_functions.md)** — the
   same sandbox at render time: `[[...]]` blocks in descriptions,
   evaluated per viewer, with skills, randomness, and state — text that
   computes and remembers.
5. **[250. Restricted player scripting](250_player_scripting.md)** — the
   thesis item. A player programs her own gadget in full softcode, and
   the tutorial attacks every wall that makes that safe: AST validation,
   time/call/recursion/output budgets, `controls()` owner authority,
   locks, relocation consent, and `@chown`'s halt-on-transfer.

## The through-line

Read in order, the arc teaches one design stance: **there is no
"builder language" and "player language" — there is one softcode engine
built to be handed to adversaries.** The verb you attach in 243 and the
program a player stores in 250 run through the same sandbox, the same
`controls()` predicate, the same lock engine (`realm.core.safe_eval`
validates scripts, locks, and inline blocks alike). Safety is granted by
construction, not by review queue: reads are open, mutations require
control, escape hatches are unparseable, and budgets bound every run.
That is why the escalation from "a builder's jukebox" to "a player's
programmable gadget" costs the game nothing new — by item 250 the only
thing that changes is who owns the object.

The mechanisms also compose literally: the capstone cube is *programmed*
through a 243-style `$`-verb, *fires* through a 240-style `ON_USE` hook,
could *ship* in a 241 area file, and may carry 242 inline blocks in its
description — one model, five views of it.
