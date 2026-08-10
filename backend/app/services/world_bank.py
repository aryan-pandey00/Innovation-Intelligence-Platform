import html
import httpx

PROJECTS_URL = "https://search.worldbank.org/api/v2/projects"


def _map_project(p: dict) -> dict:
    pid = p.get("id")
    country = p.get("countryshortname") or "multiple regions"
    countries = p.get("countryname") or ([country] if country else [])
    return {
        "id": f"wb-{pid}",
        "title": html.unescape((p.get("project_name") or "Untitled project").strip()),
        "agency": "World Bank",
        "source_type": "international_agency",
        "description": f"World Bank development project — {country}",
        "amount_min": None,
        "amount_max": None,
        "currency": "USD",
        "deadline": None,
        "countries": countries if isinstance(countries, list) else [countries],
        "url": p.get("url") or f"https://projects.worldbank.org/en/projects-operations/project-detail/{pid}",
        "live": True,
        "source_label": "World Bank",
        "awarded": True,
    }


async def search_live(keyword: str = "", rows: int = 10) -> list[dict]:
    params = {"format": "json", "rows": rows, "qterm": keyword.strip() or "innovation"}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(PROJECTS_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        projects = (data.get("projects") or {}).values()
        return [_map_project(p) for p in projects if p.get("id")]
    except (httpx.HTTPError, ValueError, KeyError, AttributeError):
        return []
