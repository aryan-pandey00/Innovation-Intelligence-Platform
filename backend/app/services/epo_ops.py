"""EPO Open Patent Services (OPS) client — real patent counts and year series."""
import asyncio
import base64
import random
import re
import time
from datetime import date

import httpx

from app.core.config import settings

_AUTH_URL = "https://ops.epo.org/3.2/auth/accesstoken"
_SEARCH_URL = "https://ops.epo.org/3.2/rest-services/published-data/search"
_BIBLIO_URL = _SEARCH_URL + "/biblio"
_MAX_RANGE = 2000
_PAGE = 100

_TOKEN_SAFETY_MARGIN = 60

_MIN_GAP = 12.0
_JITTER = 3.0
_DEFAULT_SEARCH_QUOTA = 5

_TOTAL_RE = re.compile(r'total-result-count="(\d+)"')
_QUOTA_RE = re.compile(r"search=(\w+):(\d+)")
_FAULT_RE = re.compile(r"<code>([^<]+)</code>")


def _pace(quota: int) -> float:
    """Seconds to wait before the next search."""
    return max(_MIN_GAP, 60.0 / max(1, quota)) + random.uniform(0, _JITTER)


class OPSUnavailable(RuntimeError):
    """OPS is not configured, refused us, or failed."""

    def __init__(self, message: str, *, retry_after: float | None = None,
                 blocked: bool = False) -> None:
        super().__init__(message)
        self.retry_after = retry_after
        self.blocked = blocked


def is_configured() -> bool:
    return bool(settings.OPS_CONSUMER_KEY and settings.OPS_CONSUMER_SECRET)


class _TokenCache:
    def __init__(self) -> None:
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()

    async def get(self, client: httpx.AsyncClient) -> str:
        async with self._lock:
            if self._token and time.monotonic() < self._expires_at:
                return self._token

            creds = f"{settings.OPS_CONSUMER_KEY}:{settings.OPS_CONSUMER_SECRET}"
            basic = base64.b64encode(creds.encode()).decode()
            try:
                resp = await client.post(
                    _AUTH_URL,
                    data={"grant_type": "client_credentials"},
                    headers={"Authorization": f"Basic {basic}",
                             "Content-Type": "application/x-www-form-urlencoded"},
                )
                resp.raise_for_status()
                payload = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise OPSUnavailable(f"OPS authentication failed: {exc}") from exc

            token = payload.get("access_token")
            if not token:
                raise OPSUnavailable("OPS returned no access token")

            lifetime = int(payload.get("expires_in") or 1200)
            self._token = token
            self._expires_at = time.monotonic() + max(30, lifetime - _TOKEN_SAFETY_MARGIN)
            return token


_tokens = _TokenCache()

_TERM_CPC: dict[str, str] = {
    "cybersecurity": "G06F21 or H04L63",
    "cyber security": "G06F21 or H04L63",
    "grid technology": "H02J or Y04S",
    "smart grid": "Y04S",
    "robotics": "B25J",
    "nanotechnology": "B82Y",
    "clean energy": "Y02E",
    "renewable energy": "Y02E10",
    "photovoltaics": "H01L31 or H02S",
    "quantum computing": "G06N10",
    "hydrogen fuel": "C01B3 or H01M8",
    "gene editing": "C12N15",
    "autonomous vehicles": "G05D1 or B60W60",
    "wireless communication": "H04W",
    "medical devices": "A61B",
    "drug discovery": "G16C20 or C40B",
}

LOW_CONFIDENCE_TOTAL = 500


def cpc_for(term: str) -> str | None:
    return _TERM_CPC.get(" ".join(term.lower().split()))


def _cql_cpc(expression: str) -> str:
    """A CPC expression as CQL, e.g."""
    codes = [c.strip() for c in expression.split(" or ") if c.strip()]
    return "(" + " or ".join(f"cpc={c}" for c in codes) + ")"


def base_query(term: str) -> tuple[str, str]:
    """The CQL for a term, plus how it was derived ('cpc' or 'phrase')."""
    cpc = cpc_for(term)
    if cpc:
        return _cql_cpc(cpc), "cpc"
    return _cql_phrase(term), "phrase"


def _cql_phrase(term: str) -> str:
    """A term as a quoted CQL phrase matched against title and abstract."""
    cleaned = " ".join(term.replace('"', " ").split())
    if not cleaned:
        raise OPSUnavailable("empty search term")
    return f'ti,ab="{cleaned}"'


def _parse_count(resp: httpx.Response) -> int:
    """Read total-result-count from either the JSON or XML representation."""
    try:
        node = resp.json()["ops:world-patent-data"]["ops:biblio-search"]
        return int(node["@total-result-count"])
    except (ValueError, KeyError, TypeError):
        match = _TOTAL_RE.search(resp.text)
        if match:
            return int(match.group(1))
    raise OPSUnavailable("could not read result count from OPS response")


def _search_quota(resp: httpx.Response) -> int:
    """Searches-per-minute OPS says we may make right now."""
    match = _QUOTA_RE.search(resp.headers.get("X-Throttling-Control", ""))
    if not match:
        return _DEFAULT_SEARCH_QUOTA
    colour, allowed = match.group(1), int(match.group(2))
    if colour == "black" or allowed <= 0:
        return 0
    if colour in ("red", "yellow"):
        return 1
    return max(1, allowed)


def _refusal(resp: httpx.Response) -> OPSUnavailable:
    """Turn an OPS refusal into something a human can act on."""
    fault = _FAULT_RE.search(resp.text)
    code = fault.group(1) if fault else f"HTTP {resp.status_code}"
    reason = resp.headers.get("X-Rejection-Reason", "")
    throttle = resp.headers.get("X-Throttling-Control", "")

    retry_after: float | None = None
    raw = resp.headers.get("Retry-After")
    if raw and raw.strip().isdigit():
        retry_after = float(raw.strip())

    detail = f"OPS refused the request: {code}"
    if reason:
        detail += f" (rejection reason: {reason})"
    if retry_after is not None:
        detail += f", Retry-After={raw}"
    if throttle:
        detail += f" [{throttle}]"

    blocked = code == "CLIENT.RobotDetected" or "black:0" in throttle
    if blocked:
        detail += (
            "\n    The search service is currently closed to us. This is a rate/"
            "pattern block, not a data-quota problem — check "
            "X-IndividualQuotaPerHour-Used if unsure."
        )
    return OPSUnavailable(detail, retry_after=retry_after, blocked=blocked)


async def _count(client: httpx.AsyncClient, cql: str) -> tuple[int, int]:
    """Returns (matching patents, searches-per-minute we may currently make)."""
    token = await _tokens.get(client)
    try:
        resp = await client.get(
            _SEARCH_URL,
            params={"q": cql, "Range": "1-1"},
            headers={"Authorization": f"Bearer {token}",
                     "Accept": "application/json"},
        )
    except httpx.HTTPError as exc:
        raise OPSUnavailable(f"OPS request failed: {exc}") from exc

    if resp.status_code == 404:
        return 0, _search_quota(resp)
    if resp.status_code in (403, 429, 503):
        raise _refusal(resp)
    if resp.status_code != 200:
        raise OPSUnavailable(f"OPS returned HTTP {resp.status_code}")

    return _parse_count(resp), _search_quota(resp)


def _as_list(value) -> list:
    """OPS emits a bare object where a single-element list would be expected."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _text(node) -> str | None:
    """Pull the text out of an OPS `{"$": "..."}` wrapper."""
    if isinstance(node, dict):
        val = node.get("$")
        return val.strip() if isinstance(val, str) and val.strip() else None
    if isinstance(node, str) and node.strip():
        return node.strip()
    return None


def _applicants(biblio: dict) -> list[str]:
    """Applicant names, preferring EPO's standardised ('epodoc') spelling."""
    parties = biblio.get("parties") or {}
    entries = _as_list((parties.get("applicants") or {}).get("applicant"))

    preferred, fallback = [], []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        name = _text((entry.get("applicant-name") or {}).get("name"))
        if not name:
            continue
        if entry.get("@data-format") == "epodoc":
            preferred.append(name)
        else:
            fallback.append(name)

    chosen = preferred or fallback
    return list(dict.fromkeys(chosen))


def _classifications(biblio: dict) -> list[str]:
    """IPC codes normalised to subclass level (e.g."""
    node = biblio.get("classifications-ipcr") or {}
    codes: list[str] = []
    for entry in _as_list(node.get("classification-ipcr")):
        if not isinstance(entry, dict):
            continue
        raw = _text(entry.get("text"))
        if not raw:
            continue
        compact = raw.replace(" ", "")
        if len(compact) >= 4 and compact[0].isalpha() and compact[1:3].isdigit():
            subclass = compact[:4].upper()
            if subclass not in codes:
                codes.append(subclass)
    return codes


def _record(document: dict) -> dict | None:
    biblio = document.get("bibliographic-data") or {}

    title = None
    for candidate in _as_list(biblio.get("invention-title")):
        if isinstance(candidate, dict) and candidate.get("@lang") not in (None, "en"):
            continue
        title = _text(candidate)
        if title:
            break

    abstract_parts = []
    for abstract in _as_list(document.get("abstract")):
        if not isinstance(abstract, dict):
            continue
        if abstract.get("@lang") not in (None, "en"):
            continue
        for para in _as_list(abstract.get("p")):
            text = _text(para)
            if text:
                abstract_parts.append(text)

    pub = (biblio.get("publication-reference") or {})
    doc_id = next((d for d in _as_list(pub.get("document-id"))
                   if isinstance(d, dict) and d.get("@document-id-type") == "docdb"),
                  None) or (_as_list(pub.get("document-id")) or [{}])[0]
    country = _text((doc_id or {}).get("country")) or ""
    number = _text((doc_id or {}).get("doc-number")) or ""
    kind = _text((doc_id or {}).get("kind")) or ""
    date = _text((doc_id or {}).get("date"))

    names = _applicants(biblio)
    if not title and not names:
        return None

    codes = _classifications(biblio)
    publication_number = f"{country}{number}{kind}" if number else None
    return {
        "title": title or "Untitled",
        "assignee": names[0] if names else None,
        "all_assignees": names,
        "patent_number": publication_number,
        "publication_date": f"{date[:4]}-{date[4:6]}-{date[6:8]}" if date and len(date) >= 8 else None,
        "classification": codes[0] if codes else None,
        "classifications": codes,
        "citation_count": None,
        "abstract": " ".join(abstract_parts) or None,
        "url": (f"https://worldwide.espacenet.com/patent/search?q={publication_number}"
                if publication_number else None),
    }


def year_window(span: int = 12) -> list[int]:
    """Years to chart: the same window the research series uses."""
    current = date.today().year
    return list(range(current - span + 1, current))


async def _biblio_page(client: httpx.AsyncClient, cql: str,
                       start: int, count: int) -> tuple[list[dict], int]:
    token = await _tokens.get(client)
    end = min(start + count - 1, _MAX_RANGE)
    try:
        resp = await client.get(
            _BIBLIO_URL,
            params={"q": cql, "Range": f"{start}-{end}"},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
    except httpx.HTTPError as exc:
        raise OPSUnavailable(f"OPS biblio request failed: {exc}") from exc

    if resp.status_code == 404:
        return [], _search_quota(resp)
    if resp.status_code in (403, 429, 503):
        raise _refusal(resp)
    if resp.status_code != 200:
        raise OPSUnavailable(f"OPS biblio returned HTTP {resp.status_code}")

    try:
        result = (resp.json()["ops:world-patent-data"]["ops:biblio-search"]
                  ["ops:search-result"])
    except (ValueError, KeyError, TypeError):
        return [], _search_quota(resp)

    records = []
    for wrapper in _as_list(result.get("exchange-documents")):
        if not isinstance(wrapper, dict):
            continue
        for document in _as_list(wrapper.get("exchange-document")):
            if isinstance(document, dict):
                parsed = _record(document)
                if parsed:
                    records.append(parsed)
    return records, _search_quota(resp)


async def sample_records(term: str, by_year: list[dict],
                         per_year: int = 40) -> dict:
    """A date-balanced sample of real records for a term."""
    if not is_configured():
        raise OPSUnavailable("OPS credentials are not configured")

    base, basis = base_query(term)
    records: list[dict] = []
    years_covered: list[int] = []

    async with httpx.AsyncClient(timeout=60) as client:
        quota = _DEFAULT_SEARCH_QUOTA
        for row in by_year:
            year, available = row["year"], row["count"]
            if available <= 0:
                continue
            wanted = min(per_year, available, _PAGE)
            await asyncio.sleep(_pace(quota))
            page, quota = await _biblio_page(
                client,
                f'{base} and pd within "{year}0101 {year}1231"',
                1, wanted,
            )
            if page:
                records.extend(page)
                years_covered.append(year)

    return {
        "term": term,
        "query_basis": basis,
        "per_year": per_year,
        "records": records,
        "years_covered": sorted(years_covered),
        "source": "epo_ops",
    }


_MIN_APPLICANT_CHARS = 3
_COUNTRY_TAG = re.compile(r"\s*\[[A-Z]{2}\]\s*$")


def countable_applicant(raw: str | None) -> bool:
    """`raw` is EPO's spelling of the name, never our display form."""
    return len(re.sub(r"[^A-Za-z0-9]", "", raw or "")) >= _MIN_APPLICANT_CHARS


async def applicant_counts(term: str, names: list[tuple[str, str]],
                           ceiling: int | None = None,
                           counts: dict[str, int] | None = None,
                           done: set[str] | None = None) -> dict[str, int]:
    """True field counts for `(display, raw)` applicants, keyed by display name."""
    if not is_configured():
        raise OPSUnavailable("OPS credentials are not configured")

    base, _basis = base_query(term)
    counts = {} if counts is None else counts
    done = set() if done is None else done
    async with httpx.AsyncClient(timeout=60) as client:
        quota = _DEFAULT_SEARCH_QUOTA
        for display, raw in names:
            if display in done or not countable_applicant(raw):
                continue
            safe = _COUNTRY_TAG.sub("", raw).replace('"', " ").strip()
            await asyncio.sleep(_pace(quota))
            count, quota = await _count(client, f'{base} and pa="{safe}"')
            done.add(display)
            if ceiling is None or count <= ceiling:
                counts[display] = count
    return counts


async def publication_counts(term: str, span: int = 12) -> dict:
    """Corpus total plus a real publications-per-year series for `term`."""
    if not is_configured():
        raise OPSUnavailable("OPS credentials are not configured")

    base, basis = base_query(term)
    years = year_window(span)
    by_year: list[dict] = []

    async with httpx.AsyncClient(timeout=40) as client:
        total, quota = await _count(client, base)
        if quota == 0:
            raise OPSUnavailable("OPS search budget is exhausted — try later",
                                 blocked=True)

        for year in years:
            await asyncio.sleep(_pace(quota))
            count, quota = await _count(
                client, f'{base} and pd within "{year}0101 {year}1231"')
            by_year.append({"year": year, "count": count})

    return {
        "term": term,
        "cql": base,
        "query_basis": basis,
        "total": total,
        "low_confidence": basis == "phrase" and total < LOW_CONFIDENCE_TOTAL,
        "by_year": by_year,
        "date_basis": "publication",
    }
