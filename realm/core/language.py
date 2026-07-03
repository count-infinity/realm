"""
Display-time English: articles and plurals, computed, never stored.

The design rule (deliberately unlike Evennia, which saves "an apple" /
"three foos" into database aliases from its display path): an object's
``name`` is the bare noun — "apple", "rusty sword", "Zeke the Bartender".
Articles and plurals are derived at render time from three layers:

1. Convention: a capitalized name is a proper noun — no article.
2. Heuristic: vowel-start → "an", else "a"; plurals via standard
   s/es/ies rules plus an irregulars table.
3. Override attributes for English's exceptions: ``db.article``
   ("an" for hour, "some" for sand, "" to force none) and ``db.plural``
   ("staves", "fish").

Nothing here touches persistence; overrides are ordinary attributes a
builder sets only when the heuristic is wrong.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

_VOWELS = set("aeiou")

# Last-word irregulars. Extend freely; db.plural overrides per object.
IRREGULAR_PLURALS = {
    "child": "children",
    "deer": "deer",
    "die": "dice",
    "fish": "fish",
    "foot": "feet",
    "goose": "geese",
    "man": "men",
    "mouse": "mice",
    "person": "people",
    "sheep": "sheep",
    "staff": "staves",
    "tooth": "teeth",
    "woman": "women",
}


def is_proper_noun(name: str) -> bool:
    """Capitalized names are treated as proper nouns (no article)."""
    return bool(name) and name[0].isupper()


def article_for(name: str) -> str:
    """
    The indefinite article for a bare noun — "" for proper nouns.

    Pure heuristic; callers should prefer ``singular_name(obj)`` which
    honors the ``db.article`` override.
    """
    if not name or is_proper_noun(name):
        return ""
    return "an" if name[0].lower() in _VOWELS else "a"


def pluralize(name: str) -> str:
    """
    Pluralize a bare noun phrase by its last word.

    "energy cell" → "energy cells", "staff" → "staves". Heuristic only;
    callers should prefer ``plural_name(obj)`` which honors ``db.plural``.
    """
    if not name:
        return name
    head, _, last = name.rpartition(" ")
    prefix = f"{head} " if head else ""
    lower = last.lower()

    if lower in IRREGULAR_PLURALS:
        result = IRREGULAR_PLURALS[lower]
        if last[0].isupper():
            result = result[0].upper() + result[1:]
        return prefix + result
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return f"{prefix}{last}es"
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in _VOWELS:
        return f"{prefix}{last[:-1]}ies"
    if lower.endswith("fe"):
        return f"{prefix}{last[:-2]}ves"
    if lower.endswith("f") and not lower.endswith("ff"):
        return f"{prefix}{last[:-1]}ves"
    return f"{prefix}{last}s"


def singular_name(obj: GameObject) -> str:
    """
    The display form of one of this object: "an apple", "Zeke the
    Bartender", "some sand" (via ``db.article``).
    """
    override = obj.db.get('article')
    if override is not None:
        return f"{override} {obj.name}" if override else obj.name
    art = article_for(obj.name)
    return f"{art} {obj.name}" if art else obj.name


def plural_name(obj: GameObject) -> str:
    """The plural display form: "apples", honoring ``db.plural``."""
    override = obj.db.get('plural')
    if override:
        return str(override)
    return pluralize(obj.name)


def definite_name(obj: GameObject) -> str:
    """
    The definite display form: "the apple"; proper nouns unchanged
    ("Zeke the Bartender", never "the Zeke the Bartender").
    """
    if is_proper_noun(obj.name):
        return obj.name
    return f"the {obj.name}"


def numbered_name(obj: GameObject, count: int) -> str:
    """
    How ``count`` of this object read in a list: "an apple" / "3 apples".
    """
    if count <= 1:
        return singular_name(obj)
    return f"{count} {plural_name(obj)}"


__all__ = [
    "IRREGULAR_PLURALS",
    "is_proper_noun",
    "article_for",
    "pluralize",
    "singular_name",
    "plural_name",
    "definite_name",
    "numbered_name",
]
