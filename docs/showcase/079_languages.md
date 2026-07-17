# 79. Languages

> Checklist item 79 — [small] — *per-listener speech; an unknown tongue garbles through a speech renderer*

**What you'll build:** a trade port where a single `say` reaches two
listeners as two different lines — one who shares your tongue reads your
words, one who doesn't hears only `<something in Trade>`. The words
garble; the name over them does not.

**Concepts:** the **speech-renderer seam** (`register_speech_renderer`) —
one short native binding a game registers at deploy time — plus an in-game
`$speak <tongue>` command and per-character `speaking` / `languages`
attributes. Like [short-descs](133_short_descs.md), the policy half —
*what a stranger to the tongue actually hears* — is the game's own, so it
lives in setup Python, not in softcode a player could rewrite.

## How it works

Speech leaves a speaker as one `event:speech` action, but its body — the
`{speech}` token — is resolved **once per listener** (see
[action propagation](../architecture/events.md)). That is the seam
languages need: one `say`, a different body for each set of ears.

A **speech renderer** is the hook. It sees `(body, action, looker)` and
returns the body that particular looker should read. Ours is nine lines. A
speaker carries `db.speaking` (the tongue on their lips right now); a
listener carries `db.languages` (the tongues they know). If the looker
lacks the speaker's tongue they get a placeholder; everyone else — and the
speaker's own ear — reads it plain:

```python
# In your game's setup (config.py's on_start, or a bindings module):
from realm.core.propagation import register_speech_renderer

def garble_unknown_tongue(body, action, looker):
    if action.action_type != "event:speech":
        return body                      # only spoken words garble
    tongue = action.actor.db.get("speaking")
    if not tongue or looker is None or looker is action.actor:
        return body                      # plain speech, or the speaker's own ear
    if tongue in (looker.db.get("languages") or []):
        return body                      # this listener shares the tongue
    return f"<something in {tongue.title()}>"

register_speech_renderer(garble_unknown_tongue)
```

**The renderer touches the body, never the name.** It rewrites only
`{speech}`; the `{actor}` around it still resolves through
`get_display_name`, so both listeners read *"Vex says,"* — attribution is
untouched, only the words differ. A listener knows *who* spoke and *that*
it was a tongue they don't have, which is exactly right.

**Choosing a tongue is an admin-owned command.** `$speak trade` writes the
speaker's own `speaking` attribute — a write to a player's sheet, which
softcode may do only through an admin-owned object's authority (the same
rule the [introductions steward](133_short_descs.md) runs on). So the
lectern that carries the verb is `@create`d by an admin.

**Only `say`, for now.** The renderer keys on `event:speech`, so a whisper
or a shout arrives ungarbled. Widening that guard to the whole
speech-family is a one-line change — see *Going further*.

## Build it

The port, and an admin-owned lectern whose `$speak` verb sets the tongue
you are currently speaking:

```text
@dig The Trade Moot
@teleport The Trade Moot
@create polyglot lectern
drop polyglot lectern
@desc polyglot lectern = A brass lectern stacked with shifting dictionaries. SPEAK <tongue> to choose the language on your lips; SPEAK common to drop back to plain speech.
@set polyglot lectern/cmd_speak = $speak *: lang = trim(arg0).lower(); (set_attr(enactor, 'speaking', None), pemit(enactor, 'You drop back into the common tongue; everyone here will follow you.')) if lang in ('common', 'plain', 'plainly', '') else (pemit(enactor, 'You know no such tongue -- your mouth just makes noise.') if lang not in get_attr(enactor, 'languages', []) else (set_attr(enactor, 'speaking', lang), pemit(enactor, 'You shift into ' + ucfirst(lang) + '. Only those who share it will understand you.')))
```

The lectern needs no tag: the dispatcher matches its `$speak` verb for
anyone in the room, and its authority to write a speaker's `speaking`
comes from its admin owner.

## Try it

Give three people their tongues (a builder does this here; chargen would
normally). Vex and Mara share Trade; Bran does not:

```text
@set Vex/languages = ["trade"]
@set Mara/languages = ["trade"]
@set Bran/languages = []
```

Vex chooses to speak Trade, then says one line:

```text
(Vex)   speak trade
    You shift into Trade. Only those who share it will understand you.
(Vex)   say the cargo lands at dawn
```

That one `say` reaches the room as two different lines. Mara shares the
tongue and reads it; Bran hears only that a tongue was spoken:

```text
(Mara hears)  Vex says, "the cargo lands at dawn"
(Bran hears)  Vex says, "<something in Trade>"
```

The attribution is identical — *Vex says,* to both. Only the words inside
the quotes changed, and Vex, speaking a tongue she knows, always reads her
own words plain. Drop back to common and the wall falls:

```text
(Vex)   speak common
    You drop back into the common tongue; everyone here will follow you.
(Vex)   say and the manifest is clean
(Bran hears)  Vex says, "and the manifest is clean"
```

## Going further

- **Cover whisper and shout.** Change the guard `action.action_type !=
  "event:speech"` to `action.action_type not in ("event:speech",
  "event:whisper", "event:shout")` and a muttered aside garbles too — the
  seam already runs for every speech-family action.
- **A deterministic scramble, not a placeholder.** Return a per-word
  gibberish seeded by `(tongue, word)` so the same word always garbles the
  same way — players learn vocabulary by exposure, hearing `"khazur"`
  whenever smugglers mention the docks. The drunk
  [slur](139_intoxication.md) is a worked deterministic transform to copy.
- **Degrees of fluency.** Store `languages` as `{"trade": "broken"}` and
  garble only every third word for a partial speaker — comprehension as a
  spectrum, not a switch.
- **Compose with intoxication.** Register the drunk slur too; renderers run
  in registration order, so a tipsy smuggler in a foreign tongue both
  garbles (to those without it) *and* slurs (to everyone). See
  [139](139_intoxication.md).
