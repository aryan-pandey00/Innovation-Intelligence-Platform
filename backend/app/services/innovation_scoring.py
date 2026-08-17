"""Innovation scoring."""
import math
from datetime import date

from app.services import tech_intelligence

WEIGHTS = {
    "research_novelty": 0.30,
    "patent_strength": 0.20,
    "technology_maturity": 0.15,
    "market_potential": 0.20,
    "funding_relevance": 0.15,
}

LABELS = {
    "research_novelty": "Research Novelty",
    "patent_strength": "Patent Strength",
    "technology_maturity": "Technology Maturity",
    "market_potential": "Market Potential",
    "funding_relevance": "Funding Relevance",
}

DESCRIPTIONS = {
    "research_novelty":
        "70% how fast publishing in this field is growing, 30% the portfolio's own "
        "papers on this technology — how many, how recent, and how cited. Papers in "
        "the portfolio that never mention this technology are not counted here.",
    "patent_strength":
        "50% how much patenting the field sees, on a log scale so a 6,000-patent "
        "field and an 800,000-patent one do not both read as full. 50% the patents "
        "the portfolio holds in this technology.",
    "technology_maturity":
        "Where the field sits in its lifecycle. Half from how settled its research "
        "growth is — a field still doubling is earlier than one that has levelled "
        "off — and half from how large its literature and patent base have grown.",
    "market_potential":
        "60% the size of the patent base, 40% whether filing is still rising. It "
        "reads the field as a market and takes nothing from the portfolio.",
    "funding_relevance":
        "70% the best-matching funding programme, 30% how many programmes match at "
        "all. Matched on the portfolio and this technology together, with "
        "eligibility checked against the applicant's role and country.",
}

_MATURITY_BAND = {
    "Developing": (25, 45),
    "Emerging": (30, 60),
    "Growing": (50, 85),
    "Mature": (75, 95),
}

_REFERENCE_CORPUS = 1_000_000
_REFERENCE_PUB_CITATIONS = 10_000
_REFERENCE_PATENT_CITATIONS = 500


def _clamp(v: float) -> int:
    return max(0, min(100, round(v)))


def _volume_score(total: int | None, reference: int = _REFERENCE_CORPUS) -> int:
    """Corpus size on a log scale, so 100 and 876,522 do not both read as 100."""
    if not total or total <= 0:
        return 0
    return _clamp(100 * math.log10(1 + total) / math.log10(1 + reference))


def _growth_score(ratio: float) -> int:
    """Growth through tanh, so strong growth never pins at 100."""
    return _clamp(50 + 50 * math.tanh(ratio))


def _maturity_score(stage: str, research_growth: float, research_total: int,
                    patent_total: int) -> int:
    """Continuous within the band its stage sets."""
    lo, hi = _MATURITY_BAND.get(stage, (40, 70))
    settled = 100 * (1 - math.tanh(max(0.0, research_growth)))
    scale = (_volume_score(research_total) + _volume_score(patent_total)) / 2
    return _clamp(lo + (hi - lo) * (0.5 * settled + 0.5 * scale) / 100)


def _publication_score(publications, today: date) -> int:
    """The user's own publishing: volume, recency and citation impact."""
    if not publications:
        return 0
    n = len(publications)
    years = [p.year for p in publications if p.year]
    recent = sum(1 for y in years if y >= today.year - 5)
    citations = sum(p.citation_count or 0 for p in publications)

    volume = min(100, n * 12)
    recency = 100 * recent / len(years) if years else 50
    impact = _volume_score(citations, _REFERENCE_PUB_CITATIONS)
    return _clamp(0.4 * volume + 0.3 * recency + 0.3 * impact)


def _patent_score(patents) -> int:
    """The user's own IP position."""
    if not patents:
        return 0
    n = len(patents)
    citations = sum(p.citation_count or 0 for p in patents)
    volume = min(100, n * 25)
    impact = _volume_score(citations, _REFERENCE_PATENT_CITATIONS)
    return _clamp(0.7 * volume + 0.3 * impact)


async def analyze(query: str, funding_recs: list[dict], patent_query: str | None = None,
                  publications=None, patents=None, today: date | None = None,
                  portfolio_publications: int | None = None,
                  portfolio_patents: int | None = None) -> dict:
    """`publications` / `patents` are the records about *this* technology."""
    if today is None:
        today = date.today()
    tech = await tech_intelligence.analyze_technology(query, patent_query=patent_query)

    research_growth = tech["research_growth"] / 100
    patent_growth = tech["patent_growth"] / 100
    patent_total = tech["patent_total"]
    research_total = tech["research_total"]
    history_reliable = tech.get("patent_history_reliable", False)

    own_publications = _publication_score(publications, today)
    own_patents = _patent_score(patents)

    patent_momentum = _growth_score(patent_growth) if history_reliable else 50

    components = {
        "research_novelty": _clamp(0.70 * _growth_score(research_growth)
                                   + 0.30 * own_publications),
        "patent_strength": _clamp(0.50 * _volume_score(patent_total)
                                  + 0.50 * own_patents),
        "technology_maturity": _maturity_score(tech["stage"], research_growth,
                                               research_total, patent_total),
        "market_potential": _clamp(0.60 * _volume_score(patent_total)
                                   + 0.40 * patent_momentum),
        "funding_relevance": _clamp(
            0.70 * max((r["relevance_score"] for r in funding_recs), default=0)
            + 0.30 * min(100, sum(1 for r in funding_recs
                                  if r["relevance_score"] >= 40) * 10)),
    }

    total = round(sum(components[k] * WEIGHTS[k] for k in WEIGHTS))
    rating = "High" if total >= 70 else "Moderate" if total >= 45 else "Early-stage"

    top_match = max((r["relevance_score"] for r in funding_recs), default=0)
    strong = sum(1 for r in funding_recs if r["relevance_score"] >= 40)

    return {
        "query": query,
        "innovation_score": total,
        "rating": rating,
        "components": [
            {
                "key": k,
                "label": LABELS[k],
                "description": DESCRIPTIONS[k],
                "score": components[k],
                "weight": round(WEIGHTS[k] * 100),
                "contribution": round(components[k] * WEIGHTS[k], 1),
            }
            for k in WEIGHTS
        ],
        "signals": {
            "stage": tech["stage"],
            "opportunity_level": tech["opportunity_level"],
            "patent_total": patent_total,
            "research_total": research_total,
            "patent_growth": tech["patent_growth"],
            "research_growth": tech["research_growth"],
            "patent_history_reliable": history_reliable,
            "top_assignees": tech["top_assignees"],
            "patent_sample_size": tech.get("patent_sample_size"),
            "patents_available": tech["patents_available"],
            "own_publications": len(publications or []),
            "own_patents": len(patents or []),
            "portfolio_publications": (portfolio_publications
                                       if portfolio_publications is not None
                                       else len(publications or [])),
            "portfolio_patents": (portfolio_patents if portfolio_patents is not None
                                  else len(patents or [])),
            "busiest_year": max(tech["activity_trend"],
                                key=lambda r: r["patents"] or 0,
                                default={}).get("year") if tech["activity_trend"] else None,
        },
        "funding": {"top_match": round(top_match), "strong_matches": strong},
    }
