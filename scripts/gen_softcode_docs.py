#!/usr/bin/env python
# ruff: noqa: E501  (markdown table rows in the template)
"""Regenerate docs/reference/softcode.md from the live ScriptFunctions API.

Run after adding/changing softcode functions:  python scripts/gen_softcode_docs.py
"""
import inspect
import pathlib

from realm.scripting.functions import ScriptFunctions
from realm.scripting.triggers import STANDARD_EVENTS

HEADER = """# Softcode Reference

Auto-generated from the live API (`python scripts/gen_softcode_docs.py`
regenerates). Scripts are sandboxed Python: loops, comprehensions,
function defs — under time/call/output limits.

## Context names

| Name | Meaning |
|---|---|
| `me` / `executor` | the scripted object (scripts run AS it, with its owner's authority) |
| `enactor` | who triggered the script (`%#` in simple scripts) |
| `here` / `location` | where it happened |
| `viewer` | the looker (inline `[[...]]` blocks and @detail conditions) |
| `arg0..argN` / `%0..%9` | wildcard captures |
| `result` | what an inline `[[...]]` block substitutes |

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

### `ON_<EVENT>` lifecycle hooks

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
    lines = [HEADER]
    for name, desc in STANDARD_EVENTS.items():
        lines.append(f"| `ON_{name}` | {desc} |")
    lines.append("\n## Functions\n")
    lines.append("| Function | Signature | Notes | Example |")
    lines.append("|---|---|---|---|")
    for name in sorted(d):
        fn = d[name]
        if not callable(fn):
            continue
        try:
            sig = str(inspect.signature(fn))
        except (ValueError, TypeError):
            sig = "(...)"
        full = inspect.getdoc(fn) or ""
        doc = full.split("\n")[0].strip()
        example = ""
        for line in full.split("\n"):
            if line.strip().startswith("Example:"):
                example = line.strip()[len("Example:"):].strip()
                break
        def esc(t: str) -> str:
            return t.replace("|", chr(92) + "|")
        lines.append(f"| `{name}` | `{esc(sig)}` | {esc(doc)} "
                     f"| {('`' + esc(example) + '`') if example else ''} |")
    lines.append(FOOTER)
    out = pathlib.Path(__file__).parent.parent / "docs/reference/softcode.md"
    out.write_text("\n".join(lines))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
