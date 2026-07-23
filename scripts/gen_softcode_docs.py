#!/usr/bin/env python
# ruff: noqa: E501  (markdown table rows in the template)
"""Regenerate docs/reference/softcode.md from the live ScriptFunctions API.

Run after adding/changing softcode functions:  python scripts/gen_softcode_docs.py
"""
import inspect
import pathlib
import re
import textwrap

from realm.scripting.functions import ScriptFunctions
from realm.scripting.triggers import STANDARD_EVENTS

#: Function -> section. Every softcode function must appear exactly once;
#: main() raises if this map and the live API drift apart, so adding a
#: function without filing it here fails the build rather than silently
#: dropping it into an "Other" bucket nobody reads.
CATEGORIES: dict[str, list[str]] = {
    "Objects & attributes": [
        "get", "get_attr", "set_attr", "has_attr", "del_attr", "V",
        "incr", "decr", "name", "loc", "owner", "contents", "exits",
        "create_obj", "destroy_obj", "teleport_obj", "controls",
        "eval_attr", "call", "search_world",
    ],
    "Tags & zones": [
        "add_tag", "remove_tag", "has_tag", "tags", "tag_value",
        "tag_values", "zones_of", "zone_rooms",
    ],
    "Locks & permissions": [
        "set_lock", "clear_lock", "test_lock", "has_entitlement",
    ],
    "Money": ["credits", "adjust_credits", "transfer_credits"],
    "Messaging & prompts": [
        "pemit", "oemit", "remit", "oob", "ansi", "escape", "prompt",
    ],
    "Dice & skill checks": [
        "rand", "dice", "roll", "skill_check", "check_roll", "contest",
        "band", "highest", "margin_over", "margin_under", "net_successes",
    ],
    "Combat & effects": [
        "damage", "heal", "apply_effect", "remove_effect", "start_combat",
        "cast",
    ],
    "NPCs & behaviors": [
        "disposition", "adjust_disposition", "reaction_roll", "force",
        "behaviors", "attach_behavior", "detach_behavior",
    ],
    "Movement & travel": ["move_to", "enter_instance", "enter_wilderness"],
    "Firing your own events": ["act"],
    "Time & scheduling": ["now", "wait", "cancel_wait", "expire"],
    "Text": [
        "capstr", "lcfirst", "ucfirst", "left", "right", "mid", "strlen",
        "repeat", "replace", "trim", "words", "extract", "first", "last",
        "rest", "member", "setdiff", "setinter", "setunion",
    ],
    "Math & logic": ["ceil", "floor", "clamp", "if_else", "switch"],
}


def anchor(name: str) -> str:
    """The stable HTML id for a function's reference block."""
    return f"fn-{name.lower()}"


def rst_to_md(text: str) -> str:
    """``literal`` (RST, as written in docstrings) -> `literal` (markdown)."""
    return text.replace("``", "`")


def clean_sig(sig: str) -> str:
    """Unquote stringified annotations.

    ``from __future__ import annotations`` makes every annotation a string
    literal, so a raw signature reads ``obj: 'GameObject | None'``. Strip
    the quotes from annotations and return types only — a *default* like
    ``targeting: str = 'remote'`` must keep its quotes to stay honest.
    """
    return re.sub(r"(:\s*|->\s*)'([^']*)'", r"\1\2", sig)


def split_doc(doc: str) -> tuple[str, str]:
    """Split a docstring into (prose, example).

    An example block starts at the first line beginning with ``Example``
    that carries a colon — both ``Example: code`` and ``Example:`` with
    the code indented underneath, and prose variants like
    ``Example — a scry: code``. Everything from that line to the end of
    the docstring is the example; everything before it is prose.
    """
    lines = doc.split("\n")
    for i, line in enumerate(lines):
        if line.strip().startswith("Example") and ":" in line:
            prose = "\n".join(lines[:i]).strip()
            head = line.split(":", 1)[1].strip()
            tail = textwrap.dedent("\n".join(lines[i + 1:])).strip("\n")
            example = f"{head}\n{tail}".strip() if tail else head
            return prose, example
    return doc.strip(), ""


def summarize(prose: str) -> str:
    """One-line summary for the index table: the first sentence."""
    flat = " ".join(prose.split())
    match = re.match(r"(.+?[.!?])(?:\s|$)", flat)
    return rst_to_md(match.group(1) if match else flat)

HEADER = """# Softcode Reference

Auto-generated from the live API (`python scripts/gen_softcode_docs.py`
regenerates). Scripts are sandboxed Python: loops, comprehensions,
generator expressions, lambdas, function defs, and **f-strings** — under
time/call/output limits. A script runs in one namespace, like module scope,
so nested scopes read the variables you just assigned:
`rows = V('scores', {}); result = sorted(rows, key=lambda r: rows[r])`.
Prefer f-strings for readable output:
`say(f"{name(enactor)} owes {V('debt',0)} cr")` reads better than string
concatenation.

## Context names

| Name | Meaning |
|---|---|
| `me` / `executor` | the scripted object (scripts run AS it, with its owner's authority) |
| `enactor` | who triggered the script (`%#` in simple scripts) |
| `here` / `location` | where it happened |
| `viewer` | the looker (inline `[[...]]` blocks and @detail conditions) |
| `arg0..argN` / `%0..%9` | wildcard captures |
| `result` | what an inline `[[...]]` block substitutes |

## Substitutions (`%` tokens)

Text-substituted into the script *before* it compiles, so a token must
land where its value is valid (usually inside a string). The namespace
variables above (`enactor`, `me`, …) are usually clearer; `%` tokens are
the terse PennMUSH-style shorthand.

| Token | Expands to |
|---|---|
| `%#` | enactor id (`enactor.id`) |
| `%!` | executor id (`me.id`) |
| `%n` | enactor name |
| `%l` | location id (`here.id`) |
| `%0`..`%9` | wildcard captures (same as `arg0..arg9`) |

## Readability helpers

| Instead of | Write |
|---|---|
| `get_attr(me, 'cost', 10)` | `V('cost', 10)` |
| `set_attr(me, k, get_attr(me, k, 0) + 1)` | `incr(k)` (returns the new value; `incr(k, n)` / `decr(k)` too) |

## Event data namespace {#event-data-namespace}

**The event data namespace** is the set of names REALM binds inside a
script that is reacting to an action, describing *what happened* rather
than merely who ran the script. It is bound whenever there is an action
behind the script — every `ON_<EVENT>` hook, every `^listen`, and every
`on_check` ward. A `$`-command or a `@trigger` has no action behind it,
so these names are unbound there.

The action being described is an `Action` — one object carrying the
actor, the target, a type string, a payload, and a set of category tags.
For what an `Action` is and how it reaches your object, see
[Action Propagation](../architecture/events.md); for a guided tour with
worked examples, see
[Event bus tour](../showcase/245_event_bus_tour.md).

| Name | Meaning |
|---|---|
| `atype` | the action type (`item:on_get`, `event:payment`, `combat:on_damage`, …) |
| `actor` | who is acting (same object as `enactor`) |
| `target` | what/who the action targets |
| `adata(key, default)` | the action's payload |
| `has_atag(tag)` | orthogonal action tags (`hostile`, `sound`, …) |

### Guard on `target` — events are heard by the whole room {#guard-on-target}

**This is the one that bites.** An `ON_<EVENT>` hook fires on *every*
object in the room, not only the one the action was aimed at. So `target`
is not a nicety — it is how a witness tells **"this happened to me"** from
**"this happened near me"**:

```
@set pump/on_payment = paid = adata('amount', 0) if target is me else 0; ...
@set golem/on_receive = it = adata('item') if target is me else None; ...
```

Without the guard, paying the *vending machine* standing next to your fuel
pump runs the pump's hook with the machine's `amount`, and it cheerfully
dispenses free fuel. Anything that reacts to `ON_PAYMENT`, `ON_RECEIVE`,
`ON_GET`, `ON_DAMAGE` — any event with a target — wants this check unless
it genuinely means to react to the whole room's traffic.

Payloads carried today (read with `adata`):

| Action | Keys |
|---|---|
| `event:payment` | `amount` |
| `item:on_get` / `on_drop` / `on_wield` / `on_unwield` | *(none — the item IS `target`)* |
| `item:on_give` | `item` (`target` is the recipient; the item also arrives as `tool`) |
| `item:on_put` | `item` (`target` is the container) |
| `event:on_receive` | `item`, `giver` |
| `event:on_leave` | `exit`, `direction`, `destination` |
| `event:on_fail` | `reason` (`'skill'`, `'closed'`, `'locked'`, …), `exit`, `direction`, `destination` |
| `event:on_enter` / `pre_enter` / `on_look` / `on_expire` / `on_reset` | *(none — the subject is `target`)* |
| `event:on_hitprcnt` | `percent`, `threshold` |
| `event:on_cast` | `ability`, `caster` |
| `event:connect` | `returning` |
| `combat:on_damage` | `damage`, `damage_types` |
| `combat:on_attack` | `weapon`, `attacker_hp`, `defender_hp` |
| `combat:on_death` | `killer` (a name; the killer *object* is `actor`), `fatal` |
| `event:speech` / `shout` / `ooc` / `emit` / `whisper` | `message` |
| `event:emote` / `semipose` | `pose` |

```
@set ogre/ON_PAYMENT = pose pockets [[adata('amount')]] and steps aside.
@set anvil/ON_GET = set_attr(me, 'last_taker', name(actor))
```

`on_check` wards get all of the above **plus** the decision verbs —
`block(reason)`, `mod(n)`, `is_blocked()`, `set_adata(k, v)`. Observers do
not: by the time an `ON_<EVENT>` runs the decision is already made, so the
apply pass is read-only.

### When a ward breaks

A ward that errors **fails closed if it could have denied** — it blocks the
action and messages the object's owner. "The ward is broken" must never look
the same to the world as "the ward allowed it", or a typo silently unlocks
your vault:

| Ward | On error |
|---|---|
| calls `block(...)` | **blocks** — it guards something |
| calls an unknown name (`blok(...)`, a typo) | **blocks** — intent unclear |
| doesn't parse | **blocks** — can't tell what it guards |
| only `mod()` / `set_adata()` (armour, resistance) | **allows**, loudly — a failed soak must not veto the swing |

`@set` also warns at the prompt when a script attribute won't parse, so a
dead ward announces itself when you type it rather than months later.

## Script commands (simple scripts / `cmd()` / `output()` lines)

`say`, `pose`/`:`, `emit`/`@emit`, `whisper x = msg`, `move <exit>`,
`get`/`take`, `drop`, `give x = y`, `open`, `close`,
`trigger [obj/]attr`, `wait <sec> <command>`.

## Triggers (attributes on objects)

| Form | Fires |
|---|---|
| `$pattern:code` (attr `cmd_*`) | player input matching the pattern (gated by the `use` lock) |
| `^pattern:code` (attr `listen_*`) | overheard speech (gated by the `listen` lock) |
| `on_tick` attr | via the `script_ticker` behavior |
| `ON_<EVENT>` attr | a lifecycle event (below); matched by suffix, so any `ON_<name>` works |

## Configurable surface syntax

The sigils and delimiters above are game settings in `config.py`; this
reference (and every example in the docs) uses the defaults.

| Setting | Default | Governs |
|---|---|---|
| `COMMAND_SIGIL` | `$` | the `$pattern:code` command-trigger prefix (any length 1-16) |
| `LISTEN_SIGIL` | `^` | the `^pattern:code` listen-trigger prefix (any length 1-16) |
| `INLINE_OPEN` / `INLINE_CLOSE` | `[[` / `]]` | inline description blocks — the code inside nests freely (`fn1(fn2(x))`, `words[idx[0]]`, quoted closers); pick a bracket-final closer (`}`, `]`, `)`) so nesting tracking applies |
| `MARKUP_MARKER` | `\\|` | color markup (`\\|r`, `\\|n`, …) — remap it (`~`, `%%`, any length 1-16) to keep literal pipes in prose; the doubled-marker escape follows it |
| `EMOTE_SIGIL` | `/` | rich-emote reference prefix — `pose waves at /Bob` names Bob per viewer (each reader sees the name they know; Bob reads "you"). An unmatched `/word` stays literal |

Sigils and the marker take any non-alphanumeric, non-space characters;
sigils additionally exclude `:` (the pattern:action separator). A bad
value raises at boot, never mid-render.

### `ON_<EVENT>` lifecycle hooks {#lifecycle-hooks}

An `ON_<NAME>` attribute fires when that event reaches the object (zone
masters also hear their member rooms). Gated hooks let an `on_check` ward
veto (a cursed item refusing removal).

| Hook attr | Fires when |
|---|---|"""

FOOTER = """
Authority in one line: **reads are open** (except `password` and
`secret`-flagged attributes), **mutations require `controls()`**
(self, owned, delegated), **combat/effects use proximity** (same
room), `wait`/`force`/`start_combat` are queued and run after the
script.
"""


def main() -> None:
    d = ScriptFunctions().to_dict()
    live = {n for n, fn in d.items() if callable(fn)}
    filed = {n for names in CATEGORIES.values() for n in names}
    if live != filed:
        missing = ", ".join(sorted(live - filed)) or "none"
        stale = ", ".join(sorted(filed - live)) or "none"
        raise SystemExit(
            "CATEGORIES is out of sync with the live API.\n"
            f"  unfiled functions: {missing}\n"
            f"  filed but gone:    {stale}\n"
            "Add each new function to a section in CATEGORIES."
        )

    lines = [HEADER]
    for name, desc in STANDARD_EVENTS.items():
        lines.append(f"| `ON_{name}` | {desc} |")

    def esc(t: str) -> str:
        return t.replace("|", chr(92) + "|")

    lines.append("""
## Functions

Every function below is listed in the index, then documented in full
under its section. Each entry links to its own anchor, so you can point
a tutorial straight at one function (`reference/softcode.md#fn-pemit`).

### Index
""")
    lines.append("| Function | What it does | Section |")
    lines.append("|---|---|---|")
    section_of = {n: sec for sec, names in CATEGORIES.items() for n in names}
    for name in sorted(live, key=str.lower):
        prose, _ = split_doc(inspect.getdoc(d[name]) or "")
        sec = section_of[name]
        lines.append(f"| [`{name}`](#{anchor(name)}) "
                     f"| {esc(summarize(prose))} "
                     f"| [{sec}](#{sec.lower().replace(' & ', '-').replace(' ', '-')}) |")

    for section, names in CATEGORIES.items():
        lines.append(f"\n## {section}\n")
        for name in sorted(names, key=str.lower):
            fn = d[name]
            try:
                sig = str(inspect.signature(fn))
            except (ValueError, TypeError):
                sig = "(...)"
            prose, example = split_doc(inspect.getdoc(fn) or "")
            lines.append(f"### `{name}` {{#{anchor(name)}}}\n")
            lines.append(f"```text\n{name}{clean_sig(sig)}\n```\n")
            lines.append(rst_to_md(prose) + "\n")
            if example:
                lines.append("**Example**\n")
                lines.append(f"```text\n{rst_to_md(example)}\n```\n")

    lines.append(FOOTER)
    out = pathlib.Path(__file__).parent.parent / "docs/reference/softcode.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out} ({len(live)} functions)")


if __name__ == "__main__":
    main()
