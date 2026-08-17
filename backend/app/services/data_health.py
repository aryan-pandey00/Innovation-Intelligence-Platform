"""What the analysis pages have to work with, and what is missing."""
import json
import os

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.research_profile import ResearchProfile
from app.models.user import User
from app.services import patents_analysis, platform_analytics, profile_utils

_DATA = os.path.join(os.path.dirname(__file__), "..", "data")
_DIRS = {
    "series": os.path.join(_DATA, "patent_series"),
    "sample": os.path.join(_DATA, "patent_samples"),
    "derived": os.path.join(_DATA, "patent_derived"),
    "raw": os.path.join(_DATA, "patents"),
}

_SOURCES = [
    ("epo_ops", "EPO OPS", "Patent Landscape, Technology Intelligence",
     "Seeds the patent corpus. Never called while serving a request — the cached "
     "samples below are what the pages read."),
    ("openalex", "OpenAlex", "Research Trends, Technology Intelligence, Innovation",
     "Read live on every assessment, and the one source with no cache behind it."),
    ("google_patents", "Google Patents", "Patent Landscape",
     "Fallback for topics with no seeded sample."),
    ("grants_gov", "Grants.gov", "Funding Discovery",
     "Live grant listings, merged only when explicitly requested."),
    ("world_bank", "World Bank", "Funding Discovery", "Live grant listings."),
    ("ukri", "UKRI", "Funding Discovery", "Live grant listings."),
]


def _slugs(kind: str) -> dict[str, int]:
    """Slug -> file size, for one cache directory."""
    path = _DIRS[kind]
    if not os.path.isdir(path):
        return {}
    out = {}
    for name in os.listdir(path):
        if name.endswith(".json"):
            out[name[:-5]] = os.path.getsize(os.path.join(path, name))
    return out


def _read(kind: str, slug: str) -> dict | None:
    try:
        with open(os.path.join(_DIRS[kind], f"{slug}.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _sources() -> list[dict]:
    configured = {
        "epo_ops": bool(settings.OPS_CONSUMER_KEY and settings.OPS_CONSUMER_SECRET),
    }
    return [
        {
            "key": key,
            "name": name,
            "used_by": used_by,
            "detail": detail,
            "needs_key": key in configured,
            "configured": configured.get(key, True),
        }
        for key, name, used_by, detail in _SOURCES
    ]


def _topics() -> list[dict]:
    series, samples = _slugs("series"), _slugs("sample")
    derived, raw = _slugs("derived"), _slugs("raw")
    rows = []
    for slug in sorted(set(series) | set(samples) | set(derived) | set(raw)):
        s = _read("series", slug) or {}
        d = _read("derived", slug) or {}
        leaders = (d.get("derived") or {}).get("top_assignees") or []
        rows.append({
            "slug": slug,
            "has_series": slug in series,
            "has_sample": slug in samples,
            "has_derived": slug in derived,
            "has_raw": slug in raw,
            "corpus_total": s.get("total"),
            "years": len(s.get("by_year") or []),
            "query_basis": s.get("query_basis"),
            "low_confidence": s.get("low_confidence"),
            "date_basis": s.get("date_basis"),
            "sample_bytes": samples.get(slug),
            "holder_basis": (leaders[0].get("basis") if leaders else None),
        })
    return rows


_DERIVED_VERSION = patents_analysis._DERIVED_VERSION   # noqa: SLF001


def data_health(db: Session) -> dict:
    """Cache coverage, source configuration, and the gaps that have a user behind them."""
    topics = _topics()
    analysable = {t["slug"] for t in topics if t["has_sample"] or t["has_raw"]}

    owner_ids = {u.id for u in db.query(User)
                 .filter(User.role.in_(platform_analytics.OWNER_ROLES)).all()}
    wanted: dict[str, int] = {}
    for profile in db.query(ResearchProfile).all():
        if profile.user_id not in owner_ids:
            continue
        for term in profile_utils.technology_terms(profile)[0]:
            slug = patents_analysis._slug(term)          # noqa: SLF001
            wanted[slug] = wanted.get(slug, 0) + 1

    gaps = [{"slug": slug, "portfolios": n}
            for slug, n in sorted(wanted.items()) if slug not in analysable]

    return {
        "sources": _sources(),
        "topics": topics,
        "cached": {
            "total": len(topics),
            "with_corpus": sum(1 for t in topics if t["has_series"]),
            "sample_only": sum(1 for t in topics
                               if t["has_sample"] and not t["has_series"]),
            "fallback_only": sum(1 for t in topics
                                 if t["has_raw"] and not t["has_sample"]),
            "series_without_sample": sum(1 for t in topics if t["has_series"]
                                         and t["has_raw"] and not t["has_sample"]),
            "low_confidence": sum(1 for t in topics if t["low_confidence"]),
            "named_by_a_portfolio": len(wanted),
            "unseeded_but_named": len(gaps),
        },
        "gaps": gaps,
        "derived_version": _DERIVED_VERSION,
        "live_state_available": False,
    }
