import html
import re
import httpx

from app.services.patents_analysis import clean_assignee, clean_title

OPENALEX_URL = "https://api.openalex.org/works"
GOOGLE_PATENTS_URL = "https://patents.google.com/xhr/query"
CONTACT_EMAIL = "innovation-platform@example.com"
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str | None) -> str | None:
    if not text:
        return text
    return html.unescape(_TAG_RE.sub("", text)).strip()


async def search_publications(query: str, limit: int = 10) -> list[dict]:
    params = {"search": query, "per-page": min(limit, 25), "mailto": CONTACT_EMAIL}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(OPENALEX_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for w in data.get("results", []):
        loc = w.get("primary_location") or {}
        source = loc.get("source") or {}
        authors = [a["author"]["display_name"]
                   for a in w.get("authorships", []) if a.get("author")]
        doi = w.get("doi")
        results.append({
            "title": w.get("title") or "Untitled",
            "authors": authors[:20],
            "venue": source.get("display_name"),
            "year": w.get("publication_year"),
            "doi": doi.replace("https://doi.org/", "") if doi else None,
            "url": loc.get("landing_page_url") or doi,
            "citation_count": w.get("cited_by_count") or 0,
            "abstract": None,
        })
    return results


async def search_patents(query: str, limit: int = 10) -> list[dict]:
    params = {"url": f"q={query}", "exp": ""}
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as client:
        resp = await client.get(GOOGLE_PATENTS_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

    results = []
    clusters = (data.get("results") or {}).get("cluster") or []
    for cluster in clusters:
        for item in cluster.get("result", []):
            p = item.get("patent") or {}
            if len(results) >= limit:
                break
            number = p.get("publication_number")
            results.append({
                "title": clean_title(_clean(p.get("title"))),
                "assignee": clean_assignee(p.get("assignee")),
                "patent_number": number,
                "filing_date": p.get("filing_date") or None,
                "classification": None,
                "technology_domain": None,
                "citation_count": 0,
                "url": f"https://patents.google.com/patent/{number}/en" if number else None,
                "abstract": _clean(p.get("snippet")),
            })
    return results[:limit]
