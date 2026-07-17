# 249. Writing a contrib

> Checklist item 249 — [now] — *package a build as a reusable, configurable pack: content + docs + config knobs*

**What you'll build:** a self-contained "suggestion box" feature — built
in-game, made *configurable* with a plain data knob, exported to a
versioned file, and wrapped as a pack any other REALM game can install.
This is the arc's payoff: everything you've learned, shipped as a module.

**Concepts:** authoring a contrib entirely in softcode + data,
**configuration knobs** as ordinary attributes, `@export` to a versioned
worldio file, the `pack.json` manifest, and portability (import into a
fresh world).

## How it works

A "contrib" — a reusable add-on, in the Evennia sense — is, in REALM,
just **content plus a manifest**. Because a feature is softcode and data
(items 240–243), packaging one requires no code at all: you build it,
export it, and describe it. Three ingredients:

1. **The build** — objects carrying `cmd_*`/`on_*`/`[[…]]` behaviour,
   authored live. (Here: a box with a `$suggest` verb that logs a line.)
2. **Config knobs** — the settings you *want* installers to change, held
   as plain attributes with a `config_` prefix by convention. A knob is
   data, so an installer overrides it with one `@set` — no forking your
   softcode. (Here: `config_thanks`, the reply text.)
3. **The manifest** — a `pack.json` naming the files, a version, and a
   description. Drop it beside the exported `.realm` file and the pack
   system ([235](235_content_packs.md)) does the rest.

The discipline that makes a contrib *good* is the same as any library:
read config, don't hardcode; document the knobs; version the format.

## Build it

Build the feature in its own zone. The verb logs each suggestion to a
data attribute and thanks the sender using the **config knob**, never a
hardcoded string:

```text
@zone here = suggestbox
@create suggestion box
drop suggestion box
@set suggestion box/config_thanks = Thanks - the crew will read it.
@set suggestion box/cmd_suggest = $suggest *:set_attr(me, 'log', V('log', []) + [arg0]); pemit(enactor, V('config_thanks', 'Noted.'))
```

Capture it as a versioned file:

```text
@export suggestbox
```

`Exported 2 objects to areas/suggestbox.realm.` That file carries the
`realm_format` stamp and every attribute — the verb *and* the knob.

Now package it. Beside `suggestbox.realm`, write a `pack.json` manifest
and a short README of the knobs — this directory *is* the contrib:

```json
{
  "name": "suggestbox",
  "version": "1.0",
  "description": "A crew suggestion box. Config: config_thanks (reply text).",
  "files": ["suggestbox.realm"]
}
```

Any REALM game drops that folder into `realm/packs/` (or points at it)
and installs the whole feature with `@pack suggestbox` — or imports the
file à la carte with `@import`.

## Try it

The feature works, and its knob is live data — override it and the
behaviour changes with no edit to the softcode:

```text
> suggest add more benches
Thanks - the crew will read it.
```

An installer retunes the reply for their game:

```text
@set suggestion box/config_thanks = Logged. Command will review.
```

```text
> suggest fix the airlock
Logged. Command will review.
```

Same verb, same logged list, a different voice — because the message was
never in the code. That is the contract a good contrib offers: behaviour
you don't touch, settings you do.

## Going further

- **More knobs:** a `config_public` flag the verb reads to decide between
  `pemit` (private) and `remit` (public); a `config_max_log` cap. Every
  knob is one attribute and one `get_attr`.
- **Ship several areas:** list multiple `.realm` files in the manifest —
  a contrib can be a whole quarter, not just one gadget.
- **Definitions travel too:** a contrib can carry `class_def`/`skill_def`
  objects (the `gurps-scifi` pack does); re-importing skips duplicates,
  so upgrades are safe (item [235](235_content_packs.md)).
- **Version your knobs:** when a knob's meaning changes, bump the
  manifest `version` and note the migration in your README — the
  `realm_format` guard protects the *file* shape; your version protects
  the *content* contract.
- **Test before you ship:** item [247](247_testing_your_game.md)'s
  Simulator imports your file into a fresh world and asserts the feature
  works — a contrib's regression suite.
