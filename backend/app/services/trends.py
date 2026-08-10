import asyncio
import re
from datetime import date
import httpx

OPENALEX = "https://api.openalex.org/works"
CONTACT_EMAIL = "innovation-platform@example.com"
_RETRIES = 2


def _topic_filter(query: str) -> str:
    """An OpenAlex filter matching the query as a phrase in title or abstract.

    Not `search=`: that is a loose match across full text too, so "energy
    storage" returned 2.5M works led by "Global cancer statistics". This gives
    350,252, and it mirrors the EPO query so both sides count comparable things.
    """
    cleaned = " ".join((query or "").replace('"', " ").split())
    return f'title_and_abstract.search:"{cleaned}"'


def _with_filter(query: str, *extra: str) -> str:
    """Combine the topic filter with any additional filters.

    OpenAlex takes them comma-separated in one `filter` parameter; a second
    `filter` key would silently replace the topic and widen the query.
    """
    return ",".join([_topic_filter(query), *[e for e in extra if e]])


class ResearchQuotaExceeded(Exception):
    """OpenAlex refused the call because the day's request budget is spent.

    Not a transient failure: `retryAfter` counts seconds to midnight UTC, so a
    retry cannot help and the user needs to be told when it comes back.
    """

    def __init__(self, retry_after: int | None = None):
        self.retry_after = retry_after
        super().__init__("OpenAlex daily request budget exhausted")


def quota_detail(exc: ResearchQuotaExceeded) -> str:
    """User-facing text for a spent daily budget: whose limit it is, and when it
    clears. "Data source unavailable" reads as someone else's fault."""
    hours = round((exc.retry_after or 0) / 3600)
    when = f"in about {hours} hour{'s' if hours != 1 else ''}" if hours >= 1 else "shortly"
    return ("The research data source has reached its daily request limit. "
            f"It resets at midnight UTC, {when}. Patent figures are unaffected.")


def _quota_error(exc: httpx.HTTPError) -> ResearchQuotaExceeded | None:
    resp = getattr(exc, "response", None)
    if resp is None or resp.status_code != 429:
        return None
    try:
        retry_after = resp.json().get("retryAfter")
    except ValueError:
        retry_after = None
    return ResearchQuotaExceeded(retry_after)


async def _get(client: httpx.AsyncClient, params: dict) -> dict:
    params = {**params, "mailto": CONTACT_EMAIL}
    last_error: httpx.HTTPError | None = None
    for attempt in range(_RETRIES + 1):
        try:
            resp = await client.get(OPENALEX, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as exc:
            # a spent daily budget does not recover in 4.5s; retrying just burns
            # two more calls against the cap
            quota = _quota_error(exc)
            if quota is not None:
                raise quota from exc
            last_error = exc
            if attempt < _RETRIES:
                await asyncio.sleep(1.5 * (attempt + 1))
    raise last_error


def _year_window(rows: list[dict], span: int = 12) -> list[dict]:
    current = date.today().year
    cleaned = []
    for r in rows:
        try:
            y = int(r["key"])
        except (ValueError, TypeError):
            continue
        if current - span < y < current:
            cleaned.append({"year": y, "count": r["count"]})
    return sorted(cleaned, key=lambda x: x["year"])


_TOPIC_NOISE = frozenset("""
advanced advancements advances and applications for in of research studies
technologies technology the their
""".split())


def _topic_key(name: str) -> str:
    """A comparison key that treats restatements of one topic as the same topic.

    Four of ten hotspots were once the same subject under different spellings.
    Lowercase, drop filler words, sort the remainder.
    """
    words = sorted(w for w in re.split(r"[^a-z0-9]+", (name or "").lower())
                   if w and w not in _TOPIC_NOISE)
    return " ".join(words)


def merge_topics(rows: list[dict], limit: int | None = None) -> list[dict]:
    """Sum counts across restatements of the same topic, keeping the longest
    name as the label (it is usually the most descriptive)."""
    merged: dict[str, dict] = {}
    for row in rows:
        name = row.get("topic") or row.get("key_display_name") or ""
        if not name:
            continue
        key = _topic_key(name) or name.lower()
        entry = merged.get(key)
        if entry is None:
            merged[key] = {"topic": name, "count": row.get("count", 0)}
        else:
            entry["count"] += row.get("count", 0)
            if len(name) > len(entry["topic"]):
                entry["topic"] = name
    out = list(merged.values())
    out.sort(key=lambda r: -r["count"])
    return out[:limit] if limit else out


def _emerging(earlier_topics: list[dict], recent_topics: list[dict],
              total_earlier: int, total_recent: int, limit: int = 6) -> list[dict]:
    """Topics whose share of publications has risen between two windows.

    The windows must not overlap: an all-time baseline contains the recent window
    and damps every change toward zero.

    A share is the topic count over the *work* count — the fraction of
    publications touching the topic. Not over the sum of topic counts: OpenAlex
    assigns ~2 topics per work, so that would silently measure something else.
    """
    if not total_earlier or not total_recent:
        return []
    # merge first, or one topic split across three spellings reads as three risers
    baseline = {_topic_key(t["topic"]): t["count"] / total_earlier
                for t in merge_topics([{"topic": t["key_display_name"],
                                        "count": t["count"]} for t in earlier_topics])}
    out = []
    for t in merge_topics([{"topic": r["key_display_name"], "count": r["count"]}
                           for r in recent_topics]):
        recent_share = t["count"] / total_recent
        earlier_share = baseline.get(_topic_key(t["topic"]), 0.0)
        growth = recent_share - earlier_share
        if growth > 0:
            out.append({
                "topic": t["topic"],
                # both ends: "3.1% → 6.3%" reads as a doubling where "+3.2%" does not
                "earlier_share": round(earlier_share * 100, 1),
                "recent_share": round(recent_share * 100, 1),
                "growth": round(growth * 100, 1),
            })
    out.sort(key=lambda x: x["growth"], reverse=True)
    return out[:limit]


async def get_research_signal(query: str) -> dict:
    async with httpx.AsyncClient(timeout=25) as client:
        data = await _get(client, {"filter": _topic_filter(query),
                                   "group_by": "publication_year"})
    return {
        "total": data["meta"]["count"],
        "by_year": _year_window(data["group_by"]),
    }


# Two non-overlapping windows: the last three years against the seven before them.
_RECENT_YEARS = 2          # current year minus this starts the recent window
_EARLIER_START = 11
_EARLIER_END = 5


async def get_trends(query: str, topic_limit: int = 10, paper_limit: int = 5) -> dict:
    year = date.today().year
    recent_from = f"{year - _RECENT_YEARS}-01-01"
    earlier_from = f"{year - _EARLIER_START}-01-01"
    earlier_to = f"{year - _EARLIER_END}-12-31"

    async with httpx.AsyncClient(timeout=25) as client:
        by_year, all_topics, recent_topics, earlier_topics, top_papers = await asyncio.gather(
            _get(client, {"filter": _topic_filter(query),
                          "group_by": "publication_year"}),
            _get(client, {"filter": _topic_filter(query), "group_by": "topics.id"}),
            _get(client, {"filter": _with_filter(query, f"from_publication_date:{recent_from}"),
                          "group_by": "topics.id"}),
            _get(client, {"filter": _with_filter(query, f"from_publication_date:{earlier_from}",
                                                 f"to_publication_date:{earlier_to}"),
                          "group_by": "topics.id"}),
            _get(client, {"filter": _topic_filter(query),
                          "sort": "cited_by_count:desc", "per-page": paper_limit}),
        )

    total_works = top_papers["meta"]["count"]
    total_recent = recent_topics["meta"]["count"]
    total_earlier = earlier_topics["meta"]["count"]

    all_rows = [{"topic": t["key_display_name"], "count": t["count"]}
                for t in all_topics["group_by"]]
    merged = merge_topics(all_rows)
    hotspots = merged[:topic_limit]
    # share of publications, so the bar means something absolute
    for row in hotspots:
        row["share"] = (round(100 * row["count"] / total_works, 1)
                        if total_works else None)

    emerging = _emerging(earlier_topics["group_by"], recent_topics["group_by"],
                         total_earlier, total_recent)

    papers = []
    for w in top_papers["results"]:
        loc = w.get("primary_location") or {}
        papers.append({
            "title": w.get("title") or "Untitled",
            "year": w.get("publication_year"),
            "cited_by_count": w.get("cited_by_count") or 0,
            "venue": (loc.get("source") or {}).get("display_name"),
            "url": loc.get("landing_page_url") or w.get("doi"),
        })

    return {
        "query": query,
        "total_works": total_works,
        "works_by_year": _year_window(by_year["group_by"]),
        "hotspots": hotspots,
        "topics_shown": len(hotspots),
        # `topics_total` was removed, not relabelled: OpenAlex caps `group_by` at
        # 200 rows and does not paginate, so it read 197-198 for every query. This
        # replaces it — how much of the literature arrived in the recent window.
        "recent_works": total_recent,
        "recent_share": (round(100 * total_recent / total_works)
                         if total_works else None),
        "recent_from_year": year - _RECENT_YEARS,
        "emerging_topics": emerging,
        "emerging_window": {"recent_from": year - _RECENT_YEARS,
                            "earlier_from": year - _EARLIER_START,
                            "earlier_to": year - _EARLIER_END},
        "top_papers": papers,
    }
