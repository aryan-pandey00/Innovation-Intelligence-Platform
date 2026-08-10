import html
from datetime import datetime
import httpx

SEARCH2_URL = "https://api.grants.gov/v1/api/search2"


def _iso_date(value: str) -> str | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%m/%d/%Y").date().isoformat()
    except (ValueError, TypeError):
        return None


def _map_hit(hit: dict) -> dict:
    opp_id = hit.get("id")
    number = hit.get("number") or ""
    return {
        "id": f"live-{opp_id}",
        "title": html.unescape((hit.get("title") or "Untitled").strip()),
        "agency": (hit.get("agency") or "").strip() or "Federal Agency",
        "source_type": "government_grant",
        "description": f"Live federal grant opportunity · #{number}".strip(" ·"),
        "amount_min": None,
        "amount_max": None,
        "currency": "USD",
        "deadline": _iso_date(hit.get("closeDate")),
        "countries": ["United States"],
        "url": f"https://www.grants.gov/search-results-detail/{opp_id}",
        "live": True,
        "source_label": "Grants.gov",
        "awarded": False,
    }


async def search_live(keyword: str = "", rows: int = 10) -> list[dict]:
    payload = {"keyword": keyword.strip(), "oppStatuses": "posted", "rows": rows}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(SEARCH2_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
        if data.get("errorcode") != 0:
            return []
        hits = data.get("data", {}).get("oppHits", []) or []
        return [_map_hit(h) for h in hits if h.get("id")]
    except (httpx.HTTPError, ValueError, KeyError):
        return []
