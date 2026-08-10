import asyncio
import math

from app.services import trends, patents_analysis


def _growth(series: list[dict]) -> float:
    counts = [s["count"] for s in series]
    n = len(counts)
    if n < 2:
        return 0.0
    half = n // 2 or 1
    early = sum(counts[:half]) / half
    recent = sum(counts[half:]) / (n - half)
    if early == 0:
        return 1.0 if recent > 0 else 0.0
    return round((recent - early) / early, 3)


def _has_patents(patent_total: int, patents_ok: bool) -> bool:
    return patents_ok and patent_total > 0


# A relevance-ranked sample shows the shape of recent filings, never real
# year-on-year volume, so growth maths on it produces confident nonsense.
def _history_reliable(patents_ok: bool, sampled: bool, series: list[dict]) -> bool:
    return patents_ok and not sampled and len(series) >= 4


_EMERGING_MIN_GROWTH = 1.0
_EMERGING_MAX_VOLUME = 300000


def _stage(research_growth: float, patent_total: int,
           patents_ok: bool, research_total: int) -> tuple[str, str]:
    """Where a field sits in its lifecycle, from its research alone.

    Patents only gate the answer: with none we cannot judge and say so. Past that it
    is research growth and research volume, and the card's subtitle must say so.
    """
    if not _has_patents(patent_total, patents_ok):
        return "Developing", "No patent data available for this query, so maturity can't be fully assessed — confirm what has already been filed before choosing a path."
    if research_growth <= 0.05:
        return "Mature", "Research output has plateaued while patenting stays active — an established, largely commercialised field."
    if research_growth >= _EMERGING_MIN_GROWTH and research_total < _EMERGING_MAX_VOLUME:
        return "Emerging", "Explosively growing research with a still-modest base — a hot, early-stage field."
    return "Growing", "A large, active research base with ongoing patenting — an expanding field moving toward maturity."


# Fitted to the spread the measure below actually produces across the seeded
# fields (18..92, median 55). The old thresholds were fitted to a formula that
# subtracted percentages, and left only three fields above "Medium".
_OPPORTUNITY_HIGH = 62
_OPPORTUNITY_MEDIUM = 42
# A field that lost everything gives a multiplier of 0, and log(0) is undefined.
_MIN_MULTIPLIER = 0.01


def _multiplier(growth: float) -> float:
    """Growth as a multiplier: +89% becomes 1.89, so two rates can be divided."""
    return max(_MIN_MULTIPLIER, 1 + growth)


def _log_multiplier(growth: float) -> float:
    """Growth as a log multiplier, so two rates can be divided rather than subtracted."""
    return math.log(_multiplier(growth))


# Where "one side is genuinely ahead" begins. Inside this band the two are moving
# together and the card says so rather than naming a leader on a rounding error.
_RESEARCH_AHEAD = 1.25
_PATENTS_AHEAD = 0.80


def _balance(research_growth: float, patent_growth: float) -> dict:
    """Which side is growing faster, and by how much.

    Shown on the card instead of the 0-100 score, which is a balance centred on 50
    and so read as a failing mark whenever a field grew evenly. "1.3x faster" needs
    no scale. The score stays in the payload for the innovation model.
    """
    ratio = _multiplier(research_growth) / _multiplier(patent_growth)
    if ratio >= _RESEARCH_AHEAD:
        return {"lead": "research", "factor": round(ratio, 1)}
    if ratio <= _PATENTS_AHEAD:
        return {"lead": "patents", "factor": round(1 / ratio, 1)}
    return {"lead": "even", "factor": round(max(ratio, 1 / ratio), 1)}


def _opportunity(research_growth: float, patent_growth: float, patent_total: int,
                 patents_ok: bool, history_reliable: bool) -> tuple[int | None, str, str]:
    """How much open ground the research leaves relative to the patenting.

    A *ratio of multipliers*, not a difference of percentages: subtracting them scored
    artificial intelligence 6/100 for two near-identical growth rates. tanh keeps the
    extremes off the rails.
    """
    if not _has_patents(patent_total, patents_ok):
        return None, "Unknown", "No patent data available for this query."
    if not history_reliable:
        return None, "Unknown", (
            "Patent filing history for this query comes from a relevance-ranked "
            "sample, which cannot support a year-on-year growth comparison. "
            "Connect a full patent source to score this."
        )
    score = max(0, min(100, round(50 + 50 * math.tanh(
        _log_multiplier(research_growth) - _log_multiplier(patent_growth)))))
    level = ("High" if score >= _OPPORTUNITY_HIGH
             else "Medium" if score >= _OPPORTUNITY_MEDIUM else "Low")
    return score, level, "Research growth measured against patent growth."


def _combined_trend(r_by_year: list[dict], p_by_year: list[dict]) -> list[dict]:
    """Both series indexed to their own peak, with the real counts alongside.

    Indexed because hundreds of papers against tens of thousands of patents on one
    axis draws the research line flat along the floor. The raw counts travel with
    them for the tooltip and labels: the shape needs the index, the numbers do not.
    A year the patent sample says nothing about yields None, never 0.
    """
    r_max = max((s["count"] for s in r_by_year), default=0) or 1
    p_max = max((s["count"] for s in p_by_year), default=0) or 1
    r_map = {s["year"]: s["count"] for s in r_by_year}
    p_map = {s["year"]: s["count"] for s in p_by_year}
    years = sorted(set(r_map) | set(p_map))
    return [{
        "year": y,
        "research": round(100 * r_map[y] / r_max) if y in r_map else None,
        "patents": round(100 * p_map[y] / p_max) if y in p_map else None,
        "research_count": r_map.get(y),
        "patent_count": p_map.get(y),
    } for y in years]


async def analyze_technology(query: str, patent_query: str | None = None) -> dict:
    research, patents = await asyncio.gather(
        trends.get_research_signal(query),
        patents_analysis.analyze_landscape(patent_query or query),
        return_exceptions=True,
    )
    if isinstance(research, Exception):
        raise research

    patents_ok = not isinstance(patents, Exception)
    r_by_year = research["by_year"]
    p_by_year = patents["filings_by_year"] if patents_ok else []
    top_assignees = patents["top_assignees"] if patents_ok else []
    ownership = patents.get("ownership") if patents_ok else None
    sample_size = patents["sample_size"] if patents_ok else 0
    filings_sampled = patents["filings_sampled"] if patents_ok else True
    counts_source = patents["counts_source"] if patents_ok else None
    date_basis = patents["date_basis"] if patents_ok else None
    query_basis = patents["query_basis"] if patents_ok else None
    low_confidence = bool(patents["low_confidence"]) if patents_ok else False

    # falls back to the sample only when the source never gave a corpus total
    corpus_total = patents["corpus_total"] if patents_ok else None
    patent_total = corpus_total if corpus_total is not None else sample_size

    history_reliable = _history_reliable(patents_ok, filings_sampled, p_by_year)

    research_growth = _growth(r_by_year)
    patent_growth = _growth(p_by_year)
    stage, stage_reason = _stage(research_growth, patent_total,
                                 patents_ok, research["total"])
    opportunity_score, opportunity_level, opportunity_reason = _opportunity(
        research_growth, patent_growth, patent_total, patents_ok, history_reliable)

    return {
        "query": query,
        "stage": stage,
        "stage_reason": stage_reason,
        "opportunity_score": opportunity_score,
        "opportunity_level": opportunity_level,
        # what the card shows: the score's own scale misleads, see _balance
        "opportunity_balance": (_balance(research_growth, patent_growth)
                                if opportunity_score is not None else None),
        "opportunity_reason": opportunity_reason,
        "research_total": research["total"],
        "patent_total": patent_total,
        "patent_total_exact": corpus_total is not None,
        "patent_sample_size": sample_size,
        # `research_per_patent` was removed rather than relabelled: its denominator
        # comes from three different query bases while the numerator is always a
        # phrase match, so two names for one technology differ 50x. It measured our
        # query strategy, not the world.
        "patents_available": patents_ok,
        "patent_history_reliable": history_reliable,
        "patent_counts_source": counts_source,
        "patent_date_basis": date_basis,
        "patent_query_basis": query_basis,
        "patent_count_low_confidence": low_confidence,
        "research_growth": round(research_growth * 100, 1),
        # sample-derived while patent_history_reliable is False: not a measured rate
        "patent_growth": round(patent_growth * 100, 1),
        "activity_trend": _combined_trend(r_by_year, p_by_year),
        "top_assignees": top_assignees,
        "ownership": ownership,
    }
