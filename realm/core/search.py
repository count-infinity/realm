"""
Name matching for object targeting.

One matcher for everything a player names: items, players, exits, rooms,
global builder targets. Tiered so the intuitive thing happens:

1. **exact** — case-insensitive full match on name or alias. Always wins;
   typing the full name can never be ambushed by a partial collision.
2. **word-prefix (scored)** — every word of the query must prefix-match a
   word of the candidate's name/alias, consumed left-to-right; candidates
   matching more query words outrank the rest and only the top bucket is
   returned. ``prom`` matches "Station Promenade"; ``big sw`` prefers
   "Big Sword" over anything that only matched "big".
   (Algorithm follows Evennia's ``string_partial_matching``.)
3. **substring** — anywhere in the name, as a last forgiving resort.

Typo correction (edit distance) is deliberately NOT a targeting tier —
guessing wrong on "swrod" and attacking the wrong thing is worse than a
"not found". That belongs in a did-you-mean suggestion, not the match.

Disambiguation: a trailing ``-N`` picks the Nth match of the bare name
(``box-2`` = second box), mirroring the multimatch listing shown when a
query stays ambiguous.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from realm.core.objects import GameObject

# "box-2" → name "box", pick match #2 (1-based).
_MULTIMATCH_RE = re.compile(r"^(?P<name>.+?)-(?P<number>\d+)$")


class AmbiguousMatchError(Exception):
    """
    A query matched several objects equally well.

    Command helpers raise this instead of guessing; the dispatcher turns
    it into a "which one did you mean?" listing with name-N choices.
    """

    def __init__(self, query: str, matches: list[GameObject]):
        self.query = query
        self.matches = matches
        super().__init__(f"'{query}' matches {len(matches)} objects")


@dataclass
class MatchResult:
    """Outcome of a match: the winners of the best tier that hit."""

    query: str
    matches: list[GameObject] = field(default_factory=list)
    tier: str = "none"  # 'exact' | 'word_prefix' | 'substring' | 'none'

    @property
    def obj(self) -> GameObject | None:
        """The single match, or None if there were zero or several."""
        return self.matches[0] if len(self.matches) == 1 else None


def _search_names(obj: GameObject) -> list[str]:
    """The lowercased names an object answers to: name + aliases."""
    names = [obj.name.lower()]
    for alias in obj.db.get('aliases', []) or []:
        names.append(str(alias).lower())
    # Computed plural, so "get apples" targets an apple with nothing
    # stored (unlike Evennia's persisted plural_key aliases).
    from realm.core.language import plural_name
    plural = plural_name(obj).lower()
    if plural not in names:
        names.append(plural)
    return names


def _dedupe(objs: list[GameObject]) -> list[GameObject]:
    seen: set[str] = set()
    result = []
    for obj in objs:
        if obj.id not in seen:
            seen.add(obj.id)
            result.append(obj)
    return result


def _exact_matches(query: str, candidates: list[GameObject]) -> list[GameObject]:
    return [obj for obj in candidates if query in _search_names(obj)]


def _word_prefix_score(query_words: list[str], name: str) -> int:
    """
    Score a single name against the query words.

    Every query word must prefix-match a name word, consumed left to
    right (a name word can't satisfy two query words). Returns the number
    of matched words, or 0 if any query word failed to match.
    """
    name_words = name.split()
    next_index = 0
    score = 0
    for query_word in query_words:
        found = -1
        for i in range(next_index, len(name_words)):
            if name_words[i].startswith(query_word):
                found = i
                break
        if found < 0:
            return 0
        next_index = found + 1
        score += 1
    return score


def _word_prefix_matches(query: str, candidates: list[GameObject]) -> list[GameObject]:
    """Top-scoring bucket of word-prefix matches (see module docstring)."""
    query_words = query.split()
    if not query_words:
        return []

    best_score = 0
    buckets: dict[int, list[GameObject]] = {}
    for obj in candidates:
        score = max(
            (_word_prefix_score(query_words, name) for name in _search_names(obj)),
            default=0,
        )
        if score > 0:
            buckets.setdefault(score, []).append(obj)
            best_score = max(best_score, score)

    return buckets.get(best_score, [])


def _substring_matches(query: str, candidates: list[GameObject]) -> list[GameObject]:
    return [
        obj for obj in candidates
        if any(query in name for name in _search_names(obj))
    ]


_ARTICLES = ("a ", "an ", "the ", "some ")


def _strip_article(query: str) -> str:
    """'an apple' → 'apple' (lowercased queries only)."""
    for art in _ARTICLES:
        if query.startswith(art) and len(query) > len(art):
            return query[len(art):].strip()
    return query


def match_objects(
    query: str,
    candidates: list[GameObject],
    *,
    allow_substring: bool = True,
) -> MatchResult:
    """
    Match a player-typed query against candidate objects.

    Runs the tiers in order and returns the winners of the first tier
    that matches anything. A trailing ``-N`` on the query picks the Nth
    match of the bare name. Candidate order is preserved (and determines
    the N numbering), duplicates are removed.

    Args:
        query: What the player typed ("gem", "prom", "box-2").
        candidates: Objects to consider, in a stable order.
        allow_substring: Include the forgiving substring tier. Turn off
            where accidental matches are costly.
    """
    query = query.strip().lower()
    candidates = _dedupe(list(candidates))
    if not query or not candidates:
        return MatchResult(query=query)

    pick_number: int | None = None
    number_match = _MULTIMATCH_RE.match(query)

    def run_tiers(q: str) -> MatchResult:
        exact = _exact_matches(q, candidates)
        if exact:
            return MatchResult(query=q, matches=exact, tier="exact")
        partial = _word_prefix_matches(q, candidates)
        if partial:
            return MatchResult(query=q, matches=partial, tier="word_prefix")
        if allow_substring:
            sub = _substring_matches(q, candidates)
            if sub:
                return MatchResult(query=q, matches=sub, tier="substring")
        return MatchResult(query=q)

    result = run_tiers(query)

    # No hit? Players naturally type articles ("get an apple") — retry
    # without a leading article before giving up.
    if not result.matches:
        stripped = _strip_article(query)
        if stripped != query:
            result = run_tiers(stripped)

    # Still nothing? The query may carry a -N disambiguator: "box-2".
    if not result.matches and number_match:
        pick_number = int(number_match.group("number"))
        result = run_tiers(number_match.group("name").strip())

    if pick_number is not None and result.matches:
        index = pick_number - 1
        if 0 <= index < len(result.matches):
            result = MatchResult(
                query=result.query,
                matches=[result.matches[index]],
                tier=result.tier,
            )
        else:
            result = MatchResult(query=result.query)

    return result


def match_one(
    query: str,
    candidates: list[GameObject],
    *,
    allow_substring: bool = True,
) -> GameObject | None:
    """
    Match exactly one object or raise AmbiguousMatchError.

    The standard resolver for commands: None means "not found", an
    AmbiguousMatchError means "be more specific" (the dispatcher renders it).
    """
    result = match_objects(query, candidates, allow_substring=allow_substring)
    if not result.matches:
        return None
    if len(result.matches) > 1:
        # Twins: when every match is visually identical (same name, the
        # display-grouping key), prompting "apple-1 or apple-2?" is
        # noise — take the first. name-N still picks a specific one.
        names = {obj.name.lower() for obj in result.matches}
        if len(names) == 1:
            return result.matches[0]
        raise AmbiguousMatchError(result.query, result.matches)
    return result.matches[0]


def describe_match(obj: GameObject, looker: GameObject | None = None) -> str:
    """
    Short context shown next to a name in a multimatch listing —
    why this candidate is different from its twins.
    """
    if obj.has_tag('exit'):
        return "(exit)"
    if looker is not None:
        if obj.location is looker:
            return "(carried)"
        if looker.location is not None and obj.location is looker.location:
            return "(here)"
    if obj.location is not None:
        return f"(in {obj.location.name})"
    return "(nowhere)"


def format_ambiguous(error: AmbiguousMatchError, looker: GameObject | None = None) -> str:
    """
    Render an AmbiguousMatchError as a player-facing "narrow it down" prompt
    with name-N picks.
    """
    lines = [f"Which '{error.query}' do you mean?"]
    for i, obj in enumerate(error.matches[:10], start=1):
        lines.append(f"  {obj.name}-{i} {describe_match(obj, looker)}")
    if len(error.matches) > 10:
        lines.append(f"  ... and {len(error.matches) - 10} more")
    lines.append(f"(Use e.g. '{error.query}-1' to pick one.)")
    return "\n".join(lines)


__all__ = [
    "AmbiguousMatchError",
    "MatchResult",
    "match_objects",
    "match_one",
    "describe_match",
    "format_ambiguous",
]
