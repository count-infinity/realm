"""
Action category tags — REALM's flag-mask vocabulary.

Every propagated ``Action`` carries a set of *category* tags. A ward blocks
by CATEGORY, never by enumerating specific action types:

    @set here/on_check = block('The binding holds you.') if has_atag('movement') else None

That one line stops walking, fleeing, following, *and* a cast-teleport —
none of which the ward names. This is CoffeeMUD's ``CMMsg`` flag-mask model
(``MASK_MOVE``, ``MASK_MAGIC``…) in REALM's string-tag form.

These are the categories the **kernel guarantees** on the events it fires —
a stable vocabulary wards can rely on. A game is free to add its own domain
categories (``fire``, ``holy``, ``poison``…); ``has_atag()`` reads them all
the same. Keep THIS set small and universal — resist adding game-specific
categories here; that belongs in a content pack.

Distinct from **object** tags (``room`` / ``exit`` / ``player`` / ``dark``):
same ``has_tag`` plumbing, different vocabulary. Object tags say *what a
thing is*; these say *what an action is*.

Sub-kinds are read from ``adata``, not multiplied into tags — e.g. a
movement action with an ``exit`` in its ``adata`` is a **traversal** (a
walk); its absence means **direct placement** (a teleport/summon/knockback).
So "block teleports but allow walking" is
``has_atag('movement') and not adata('exit')`` — no separate tag needed.
"""

from __future__ import annotations

#: Any relocation of a body — walk, flee, follow, teleport, summon, knockback.
MOVEMENT = "movement"

#: An aggressive act — drives auto-combat; a peace ward blocks it.
HOSTILE = "hostile"

#: Perceived by sight — gated by blindness / darkness.
VISUAL = "visual"

#: Perceived by hearing — gated by silence / deafness.
SOUND = "sound"

#: Originated from softcode (loop/depth accounting), not a player command.
SCRIPTED = "scripted"

#: A thwarted attempt — paired with its base category (e.g. movement+failure).
FAILURE = "failure"

#: The kernel-guaranteed category set — every one of these IS emitted by
#: engine-fired events, so a ward can rely on them. Kernel code that fires
#: an action in one of these categories MUST tag it.
CORE_CATEGORIES = frozenset({
    MOVEMENT, HOSTILE, VISUAL, SOUND, SCRIPTED, FAILURE,
})

# --- Reserved (game-layer) categories -------------------------------------
# Conventional names for tags GAMES emit — the kernel itself never fires
# them (a hard-SF game has no "magic"; that's genre, not engine). They live
# here only so packs converge on the same spelling; has_atag() reads any
# string either way.

#: Magical / supernatural causation — the anti-magic-ward category.
MAGIC = "magic"

#: Against the target's will — knockback, compel, forced march.
FORCED = "forced"

RESERVED_CATEGORIES = frozenset({MAGIC, FORCED})

__all__ = [
    "MOVEMENT", "HOSTILE", "VISUAL", "SOUND", "SCRIPTED", "FAILURE",
    "MAGIC", "FORCED", "CORE_CATEGORIES", "RESERVED_CATEGORIES",
]
