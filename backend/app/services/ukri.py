import html
import httpx

GTR_URL = "https://gtr.ukri.org/api/projects"


def _clip(text: str | None, limit: int = 220) -> str:
    if not text:
        return "UK research council funded project."
    text = html.unescape(text.strip())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"


def _map_project(p: dict) -> dict:
    ref = p.get("grantReference") or p.get("id")
    fund = p.get("fund") or {}
    funder = (fund.get("funder") or {}).get("name") or "UK Research and Innovation"
    amount = fund.get("valuePounds")
    return {
        "id": f"ukri-{ref}",
        "title": html.unescape((p.get("title") or "Untitled").strip()),
        "agency": funder,
        "source_type": "research_council",
        "description": _clip(p.get("abstractText")),
        "amount_min": None,
        "amount_max": amount if isinstance(amount, (int, float)) and amount > 0 else None,
        "currency": "GBP",
        "deadline": None,
        "countries": ["United Kingdom"],
        "url": f"https://gtr.ukri.org/projects?ref={ref}",
        "live": True,
        "source_label": "UKRI",
        "awarded": True,
    }


async def search_live(keyword: str = "", rows: int = 10) -> list[dict]:
    params = {"q": keyword.strip() or "innovation", "s": rows}
    try:
        async with httpx.AsyncClient(timeout=15, headers={"Accept": "application/json"}) as client:
            resp = await client.get(GTR_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        projects = (data.get("projectsBean") or {}).get("projects") or []
        return [_map_project(p) for p in projects if p.get("grantReference") or p.get("id")]
    except (httpx.HTTPError, ValueError, KeyError, AttributeError):
        return []
