"""Which profile fields answer which question.

Patent databases index technology; academic databases index disciplines. The
three field types are not interchangeable — using profile terms as patent
queries returned `fusion` -> 20,762 patents and `resources` -> 10,002.

  research_terms    -> Trends (OpenAlex: disciplines and subjects)
  technology_terms  -> Patents, Technology, Innovation, Commercialisation
  all_terms         -> Funding, a deliberately broad relevance match

`publications_for` / `patents_for` answer a different question: which of the
user's own records are about the technology being assessed. Work in one field is
not evidence of a position in another.
"""
import re

# Words that must never be the reason a record matches. Nearly every patent title
# contains "system", "method" or "device", which would match everything to
# everything — the failure this filter exists to stop, by another door.
_MATCH_STOPWORDS = {
    "and", "the", "for", "of", "in", "to", "a", "an", "with", "from", "by", "on",
    "its", "use", "using", "used", "based", "new", "novel", "improved", "kind",
    "type", "same", "system", "systems", "method", "methods", "device", "devices",
    "apparatus", "process", "processes", "material", "materials", "technology",
    "technologies", "application", "applications", "data", "control", "general",
    "introduction", "study", "review", "analysis", "research", "development",
}


def _stem(word: str) -> str:
    """Enough to make batteries/battery the same word. The length guards keep
    `gas` from becoming `ga`."""
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _significant_words(*texts: str | None) -> set[str]:
    words: set[str] = set()
    for text in texts:
        for raw in re.split(r"[^a-z0-9]+", (text or "").lower()):
            if len(raw) >= 3 and raw not in _MATCH_STOPWORDS:
                words.add(_stem(raw))
    return words


def matches_topic(query: str, *texts: str | None) -> bool:
    """One shared meaningful word is enough.

    Requiring every word would read "Energy Storage" against "The irreversible
    momentum of clean energy" as no match. The looser rule errs by under-crediting
    an unusual title rather than crediting a paper to an unrelated field.
    """
    qwords = _significant_words(query)
    if not qwords:
        return False
    return bool(qwords & _significant_words(*texts))


def publications_for(publications, query: str) -> list:
    """The user's papers that are about this technology."""
    return [p for p in (publications or [])
            if matches_topic(query, p.title, p.abstract, p.venue)]


def patents_for(patents, query: str) -> list:
    """The user's patents that are about this technology."""
    return [p for p in (patents or [])
            if matches_topic(query, p.title, p.abstract,
                             p.classification, p.technology_domain)]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in values:
        term = (raw or "").strip()
        if term and term.lower() not in seen:
            seen.add(term.lower())
            out.append(term)
    return out


def research_terms(profile) -> list[str]:
    """Academic vocabulary: broad disciplines first, then specific subjects."""
    if profile is None:
        return []
    return _dedupe((profile.research_domains or []) + (profile.keywords or []))


def technology_terms(profile) -> tuple[list[str], bool]:
    """Applied technologies, plus whether this is a fallback.

    Research domains stand in for a user with no technology areas, but the caller
    must be able to say so: a discipline is a weaker patent query.
    """
    if profile is None:
        return [], False
    areas = _dedupe(profile.technology_areas or [])
    if areas:
        return areas, False
    return _dedupe(profile.research_domains or []), True


def all_terms(profile) -> list[str]:
    """Every field, for funding's deliberately broad relevance matching."""
    if profile is None:
        return []
    return _dedupe((profile.technology_areas or [])
                   + (profile.research_domains or [])
                   + (profile.keywords or []))
