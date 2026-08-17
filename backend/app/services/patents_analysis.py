import asyncio
import hashlib
import html
import json
import os
import re
from collections import Counter
from datetime import date

import httpx
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer

from app.services import ipc_names

from app.services import epo_ops

GOOGLE_PATENTS_URL = "https://patents.google.com/xhr/query"
_TAG_RE = re.compile(r"<[^>]+>")
_RETRIES = 2
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "patents")


def _clean(text: str | None) -> str | None:
    if not text:
        return text
    return html.unescape(_TAG_RE.sub("", text)).strip()


_SLUG_MAX = 60


def _slug(query: str) -> str:
    """A filesystem-safe name for one query, unique to that query."""
    flat = re.sub(r"[^a-z0-9]+", "-", query.strip().lower()).strip("-")
    if not flat:
        return "query"
    if len(flat) <= _SLUG_MAX:
        return flat
    digest = hashlib.sha1(flat.encode()).hexdigest()[:8]
    head = flat[:_SLUG_MAX - len(digest) - 1].rstrip("-")
    return f"{head}-{digest}"


def _cache_path(query: str) -> str:
    return os.path.join(_CACHE_DIR, f"{_slug(query)}.json")


_CACHE_VERSION = 2
_SERIES_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "patent_series")


def _series_path(query: str) -> str:
    return os.path.join(_SERIES_DIR, f"{_slug(query)}.json")


def _load_series(query: str) -> dict | None:
    path = _series_path(query)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("by_year"), list):
        return None
    return data


def save_series(query: str, series: dict) -> None:
    try:
        os.makedirs(_SERIES_DIR, exist_ok=True)
        with open(_series_path(query), "w", encoding="utf-8") as fh:
            json.dump(series, fh)
    except OSError:
        pass


_SAMPLE_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "patent_samples")
_ABSTRACT_CACHE_CHARS = 600


def _sample_path(query: str) -> str:
    return os.path.join(_SAMPLE_DIR, f"{_slug(query)}.json")


def _load_sample(query: str) -> dict | None:
    path = _sample_path(query)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        return None
    return data


def save_sample(query: str, sample: dict) -> None:
    trimmed = dict(sample)
    trimmed["records"] = [
        {**r, "abstract": (r["abstract"] or "")[:_ABSTRACT_CACHE_CHARS] or None}
        for r in sample["records"]
    ]
    try:
        os.makedirs(_SAMPLE_DIR, exist_ok=True)
        with open(_sample_path(query), "w", encoding="utf-8") as fh:
            json.dump(trimmed, fh)
    except OSError:
        pass


_DERIVED_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "patent_derived")
_DERIVED_VERSION = 8


def _derived_path(query: str) -> str:
    return os.path.join(_DERIVED_DIR, f"{_slug(query)}.json")


def _fingerprint(patents: list[dict], query: str,
                 corpus_counts: dict[str, int] | None = None,
                 corpus_total: int | None = None,
                 tested: int | None = None) -> str:
    """Identifies the exact input `_derive` ran on."""
    h = hashlib.sha1(f"{_DERIVED_VERSION}|{_slug(query)}|{len(patents)}"
                     f"|{corpus_total}|{tested}".encode())
    for p in patents:
        h.update((p.get("patent_number") or p.get("title") or "").encode())
        h.update(b"\x00")
    for name in sorted(corpus_counts or {}):
        h.update(f"{name}={corpus_counts[name]}\x00".encode())
    return h.hexdigest()


def _derive(patents: list[dict], query: str,
            corpus_counts: dict[str, int] | None = None,
            corpus_total: int | None = None,
            tested: int | None = None) -> dict:
    return {
        "top_assignees": _top_assignees(patents, corpus_counts=corpus_counts,
                                        corpus_total=corpus_total, tested=tested),
        "ownership": _ownership(patents, corpus_counts=corpus_counts,
                               corpus_total=corpus_total, tested=tested),
        "clusters": _cluster(patents, query=query),
        "top_patents": _recent_distinct(patents, limit=5),
    }


def _load_derived(query: str, fingerprint: str) -> dict | None:
    path = _derived_path(query)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (ValueError, OSError):
        return None
    if not isinstance(data, dict) or data.get("fingerprint") != fingerprint:
        return None
    derived = data.get("derived")
    return derived if isinstance(derived, dict) else None


def build_derived(query: str, patents: list[dict],
                  corpus_counts: dict[str, int] | None = None,
                  corpus_total: int | None = None,
                  tested: int | None = None) -> dict:
    """Derive and persist."""
    derived = _derive(patents, query, corpus_counts, corpus_total, tested)
    try:
        os.makedirs(_DERIVED_DIR, exist_ok=True)
        with open(_derived_path(query), "w", encoding="utf-8") as fh:
            json.dump({"fingerprint": _fingerprint(patents, query, corpus_counts,
                                                   corpus_total, tested),
                       "derived": derived}, fh)
    except OSError:
        pass
    return derived


def _load_cache(query: str) -> dict | None:
    """Returns {"patents": [...], "corpus_total": int | None}."""
    path = _cache_path(query)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
    except (ValueError, OSError):
        return None

    if isinstance(raw, list):
        return {"patents": raw, "corpus_total": None}
    if isinstance(raw, dict) and isinstance(raw.get("patents"), list):
        return {"patents": raw["patents"], "corpus_total": raw.get("corpus_total")}
    return None


def _save_cache(query: str, patents: list[dict], corpus_total: int | None) -> None:
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        with open(_cache_path(query), "w", encoding="utf-8") as fh:
            json.dump({"version": _CACHE_VERSION, "corpus_total": corpus_total,
                       "patents": patents}, fh)
    except OSError:
        pass


async def _fetch_google_patents(query: str, num: int) -> dict:
    params = {"url": f"q={query}&num={num}", "exp": ""}
    last_error: Exception | None = None
    for attempt in range(_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=25, headers={"User-Agent": "Mozilla/5.0"}) as client:
                resp = await client.get(GOOGLE_PATENTS_URL, params=params)
                resp.raise_for_status()
                data = resp.json()
            break
        except httpx.HTTPError as exc:
            last_error = exc
            if attempt < _RETRIES:
                await asyncio.sleep(1.5 * (attempt + 1))
    else:
        raise last_error

    results = data.get("results") or {}
    corpus_total = results.get("total_num_results")
    if not isinstance(corpus_total, int) or corpus_total < 0:
        corpus_total = None

    patents = []
    clusters = results.get("cluster") or []
    for cluster in clusters:
        for item in cluster.get("result", []):
            p = item.get("patent") or {}
            number = p.get("publication_number")
            patents.append({
                "title": _clean(p.get("title")) or "Untitled",
                "assignee": (p.get("assignee") or "").strip() or None,
                "patent_number": number,
                "filing_date": p.get("filing_date") or None,
                "classification": None,
                "citation_count": None,
                "abstract": _clean(p.get("snippet")),
                "url": f"https://patents.google.com/patent/{number}/en" if number else None,
            })
    if corpus_total is not None and corpus_total < len(patents):
        corpus_total = len(patents)
    return {"patents": patents, "corpus_total": corpus_total}


async def _fetch_patents(query: str, num: int = 100) -> dict:
    return await _fetch_google_patents(query, num)


def _record_date(patent: dict) -> str | None:
    """The date on a sampled record, whichever kind the source provided."""
    return patent.get("publication_date") or patent.get("filing_date")


def _record_date_kind(patents: list[dict]) -> str:
    if any(p.get("publication_date") for p in patents):
        return "publication"
    return "filing"


def _filings_by_year(patents: list[dict], span: int = 12) -> list[dict]:
    """Filing counts for the years the sample actually covers."""
    current = date.today().year
    counts: Counter = Counter()
    for p in patents:
        fd = _record_date(p) or ""
        try:
            year = int(fd[:4])
        except (ValueError, TypeError):
            continue
        if current - span < year <= current:
            counts[year] += 1
    if not counts:
        return []
    return [{"year": y, "count": counts.get(y, 0)}
            for y in range(min(counts), max(counts) + 1)]


def trusted_corpus_count(name: str, appearances: int,
                         corpus_counts: dict[str, int] | None) -> int | None:
    """A field count is only usable if it is at least the sample count."""
    real = (corpus_counts or {}).get(name)
    if not isinstance(real, int) or real < appearances:
        return None
    return real


_MIN_CANDIDATE_APPEARANCES = 3
_MAX_CANDIDATES = 40


def _display_to_raw(patents: list[dict]) -> dict[str, str]:
    """The EPO spelling behind each cleaned display name, most common form wins."""
    raws: dict[str, Counter] = {}
    for p in patents:
        raw = (p.get("assignee") or "").strip()
        name = split_assignee(raw)["name"]
        if name:
            raws.setdefault(name, Counter())[raw] += 1
    return {name: c.most_common(1)[0][0] for name, c in raws.items()}


def count_candidates(patents: list[dict]) -> list[tuple[str, str]]:
    """(display name, EPO's own name) for applicants worth a count query."""
    counts: Counter = Counter()
    for p in patents:
        name = split_assignee(p.get("assignee"))["name"]
        if name:
            counts[name] += 1
    raws = _display_to_raw(patents)
    return [(name, raws[name])
            for name, n in counts.most_common(_MAX_CANDIDATES)
            if n >= _MIN_CANDIDATE_APPEARANCES]


_NAME_TAG = re.compile(r"\s*\[[A-Z]{2}\]\s*$")


def _name_tokens(raw: str) -> tuple[str, ...]:
    cleaned = re.sub(r"[^A-Z0-9 ]", " ", _NAME_TAG.sub("", raw or "").upper())
    return tuple(cleaned.split())


def _drop_nested(resolved: list[tuple], raws: dict[str, str]) -> list[tuple]:
    """Collapse names whose EPO matches contain one another."""
    tokens = {name: _name_tokens(raws.get(name) or name) for name, _, _ in resolved}
    drop: set[str] = set()
    for a_name, _, a_real in resolved:
        for b_name, _, b_real in resolved:
            ta, tb = tokens[a_name], tokens[b_name]
            if a_name == b_name or len(ta) >= len(tb) or tb[:len(ta)] != ta:
                continue
            drop.add(b_name if a_real >= b_real else a_name)
    return [r for r in resolved if r[0] not in drop]


_MIN_RANKABLE = 3


def _top_assignees(patents: list[dict], limit: int = 10,
                   corpus_counts: dict[str, int] | None = None,
                   corpus_total: int | None = None,
                   tested: int | None = None) -> list[dict]:
    """The largest holders in the field, by real patent counts where those exist."""
    counts: Counter = Counter()
    meta: dict[str, dict] = {}
    for p in patents:
        parts = split_assignee(p.get("assignee"))
        display = parts["name"]
        if display:
            counts[display] += 1
            meta.setdefault(display, parts)

    def row(name: str, n: int) -> dict:
        return {"assignee": name, "count": n,
                "country": meta[name]["country"], "kind": meta[name]["kind"]}

    resolved = [(name, n, real) for name, n in counts.items()
                if (real := trusted_corpus_count(name, n, corpus_counts)) is not None]
    resolved = _drop_nested(resolved, _display_to_raw(patents))
    asked = tested if tested is not None else sum(
        1 for name in (corpus_counts or {}) if name in counts)

    if len(resolved) >= _MIN_RANKABLE:
        resolved.sort(key=lambda t: -t[2])
        rows = []
        for name, n, real in resolved[:limit]:
            r = row(name, n)
            r["corpus_count"] = real
            if corpus_total:
                r["corpus_share"] = round(100 * real / corpus_total, 2)
            rows.append(r)
        basis, key = "corpus", "corpus_count"
    else:
        rows = [row(name, n) for name, n in counts.most_common(limit)]
        basis, key = "sample", "count"

    decisive = len(rows) > 1 and rows[0][key] >= rows[1][key] * 2
    for r in rows:
        r["decisive"] = decisive
        r["basis"] = basis
        r["holders_tested"] = asked
        r["holders_resolved"] = len(resolved)
    return rows


_CONCENTRATION_WINDOW = 440


def _concentration_verdict(distinct_share: float) -> str:
    if distinct_share < 60:
        return "concentrated"
    if distinct_share > 85:
        return "fragmented"
    return "mixed"


def _ownership(patents: list[dict],
               corpus_counts: dict[str, int] | None = None,
               corpus_total: int | None = None,
               tested: int | None = None) -> dict:
    """How ownership of a field is spread, and what kind of bodies hold it."""
    counts: Counter = Counter()
    kinds: Counter = Counter()
    seen: set[str] = set()
    for p in patents:
        parts = split_assignee(p.get("assignee"))
        name = parts["name"]
        if not name:
            continue
        counts[name] += 1
        if name not in seen:
            seen.add(name)
            if parts["kind"]:
                kinds[parts["kind"]] += 1

    total = sum(counts.values())
    if not total:
        return {"records": 0, "organisations": 0, "top_share": None,
                "top_holder": None, "top_count": None, "verdict": None, "mix": []}

    distinct = len(counts)
    window = [p for p in patents if split_assignee(p.get("assignee"))["name"]]
    window = window[:_CONCENTRATION_WINDOW]
    window_names = {split_assignee(p["assignee"])["name"] for p in window}
    distinct_share = 100 * len(window_names) / len(window) if window else 0.0

    top_share = top_holder = top_count = None
    known: dict[str, int] = {}
    if corpus_counts and corpus_total:
        trusted = [(n, counts[n], c) for n in corpus_counts
                   if n in counts
                   and (c := trusted_corpus_count(n, counts[n], corpus_counts)) is not None]
        known = {n: c for n, _, c in _drop_nested(trusted, _display_to_raw(patents))}
        if known:
            top_holder, top_count = max(known.items(), key=lambda kv: kv[1])
            top_share = round(100 * top_count / corpus_total, 2)

    return {
        "records": total,
        "organisations": distinct,
        "distinct_share": round(distinct_share, 1),
        "top_share": top_share,
        "top_holder": top_holder,
        "top_count": top_count,
        "holders_tested": tested if tested is not None else sum(
            1 for n in (corpus_counts or {}) if n in counts),
        "holders_resolved": len(known),
        "corpus_total": corpus_total,
        "verdict": _concentration_verdict(distinct_share),
        "mix": _percent_mix(kinds),
    }


_TITLE_FILLER = frozenset("""
and for the with thereof therefor said based device devices system systems
method methods apparatus material materials preparation process use using
""".split())


def _title_word_list(title: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9\-]{4,}", (title or "").lower())
            if w not in _TITLE_FILLER]


def _title_words(title: str) -> set[str]:
    return set(_title_word_list(title))


_FAMILY_LEAD = 4


def _same_family(a: str, b: str) -> bool:
    """Do two titles from one applicant describe the same invention?"""
    wa, wb = _title_words(a), _title_words(b)
    if not wa or not wb:
        return False
    lead_a = _title_word_list(a)[:_FAMILY_LEAD]
    if len(lead_a) == _FAMILY_LEAD and lead_a == _title_word_list(b)[:_FAMILY_LEAD]:
        return True
    shared = len(wa & wb)
    smaller = min(len(wa), len(wb))
    if smaller >= 2 and shared == smaller:
        return True
    return shared / len(wa | wb) >= 0.6


def _recent_distinct(patents: list[dict], limit: int = 5) -> list[dict]:
    """The most recent filings, one per family, titles and names cleaned."""
    ordered = sorted(patents, key=lambda p: _record_date(p) or "", reverse=True)
    out: list[dict] = []
    for p in ordered:
        title = clean_title(p.get("title"))
        if title == "Untitled":
            continue
        assignee = clean_assignee(p.get("assignee"))
        if any(kept.get("assignee") == assignee
               and _same_family(title, kept["title"]) for kept in out):
            continue
        out.append({**p, "title": title, "assignee": assignee})
        if len(out) >= limit:
            break
    return out


def shares_of_total(counts: list[int]) -> list[int]:
    """Whole-number shares that add up to exactly 100."""
    total = sum(counts)
    if not total:
        return [0] * len(counts)
    exact = [100 * c / total for c in counts]
    out = [int(e) for e in exact]
    leftover = 100 - sum(out)
    by_remainder = sorted(range(len(counts)), key=lambda i: -(exact[i] - out[i]))
    for i in by_remainder[:leftover]:
        out[i] += 1
    return out


def _percent_mix(kinds: Counter) -> list[dict]:
    ordered = kinds.most_common()
    if not ordered:
        return []
    shares = shares_of_total([n for _, n in ordered])
    return [{"kind": kind, "count": n, "share": share}
            for (kind, n), share in zip(ordered, shares)]


_PATENT_STOPWORDS = frozenset("""
according accordingly apparatus arranged arrangement assembly based claim claims
comprises comprising configured connected corresponding described describes
device devices disclosed disclosure drawing embodiment embodiments example
figure first further having herein includes including invention least means
member method methods module paragraph paragraphs particular plurality preferably
present provide provided provides relates relating respective respectively said
second set side suitable system systems therefore thereof thereto thus unit use
used using various whereby wherein which
""".split())

_FOREIGN_STOPWORDS = frozenset("""
aus auf bei dabei damit dann das dass dem den der des die diese dieser durch
ein eine einem einen einer eines erste ersten fuer für hat ist jeweils kann mit
nach nicht oder sich sie sind sowie und une von vor werden wird wobei zum zur
zwei zwischen
la le les des du dans par pour avec sur est sont une deux qui que ne pas plus
au aux ce cette il elle son sa ses dont ainsi
el los las una uno con para por como pero mas muy este esta del al se lo
""".split())


def _distinct_terms(words: list[str], limit: int = 3) -> list[str]:

    kept: list[str] = []
    for word in words:
        low = word.lower()
        if any(low in k or k in low for k in kept):
            continue
        kept.append(low)
        if len(kept) >= limit:
            break
    return [w.title() for w in kept]


_MIN_FEATURES = 12
_MIN_DOC_CHARS = 20

_TITLE_SUFFIXES = re.compile(
    r"\s*[-–—]\s*(patent\s+application|patent|google\s+patents)\s*$", re.I)
_LEADING_JUNK = re.compile(r"^[\s.,;:…-]+")


def clean_title(title: str | None) -> str:

    if not title:
        return "Untitled"
    text = _TITLE_SUFFIXES.sub("", title.strip())
    text = _LEADING_JUNK.sub("", text)
    text = re.sub(r"\s*…\s*$", "", text).strip(" .,;:-")

    parts = [p.strip() for p in text.split(",")]
    if len(parts) > 2:
        seen, kept = set(), []
        for part in parts:
            key = part.lower()
            if key and key not in seen:
                seen.add(key)
                kept.append(part)
        deduped = [p for i, p in enumerate(kept)
                   if not any(p.lower() in q.lower() for q in kept[:i])]
        text = ", ".join(deduped)

    text = _drop_restated_clause(text)

    letters = [c for c in text if c.isalpha()]
    if letters and sum(c.isupper() for c in letters) / len(letters) > 0.7:
        text = text.capitalize()
    return text or "Untitled"


_RESTATED = re.compile(
    r"\s*,?\s+and\s+(?:a\s+)?"
    r"(preparation|manufacturing|production|processing|fabrication|synthesis|"
    r"forming|making|assembly|control|application|use)\s+"
    r"(method|process|technique|technology)\s+(?:thereof|of|for|therefor)\b.*$",
    re.IGNORECASE)


def _drop_restated_clause(text: str) -> str:
    """Cut a trailing "and preparation method of <the title again>" clause."""
    match = _RESTATED.search(text)
    if not match:
        return text
    head = text[:match.start()].strip(" ,;:-")
    tail = match.group(0)
    if len(head.split()) < 4:
        return text

    stop = {"of", "for", "the", "a", "an", "and", "with", "based", "method",
            "preparation", "thereof", "system", "device", "material"}
    head_words = {w for w in re.findall(r"[a-z\-]{4,}", head.lower()) if w not in stop}
    tail_words = {w for w in re.findall(r"[a-z\-]{4,}", tail.lower()) if w not in stop}
    if not head_words:
        return text
    overlap = len(head_words & tail_words) / len(head_words)
    return f"{head}, and how to make it" if overlap >= 0.4 else text


_LEGAL_SUFFIXES = {
    "llc": "LLC", "inc": "Inc.", "ltd": "Ltd", "plc": "PLC", "gmbh": "GmbH",
    "co": "Co.", "corp": "Corp.", "sa": "SA", "ag": "AG", "bv": "BV",
    "nv": "NV", "kk": "KK", "spa": "SpA", "as": "AS", "ab": "AB", "oy": "Oy",
    "lp": "LP", "pte": "Pte", "lt": "Ltd", "sas": "SAS", "srl": "Srl",
    "aps": "ApS", "pty": "Pty", "kgaa": "KGaA", "mbh": "mbH",
    "se": "SE",
}

_ABBREVIATIONS = {
    "int": "International", "intl": "International",
    "ind": "Industries", "inds": "Industries",
    "res": "Research", "sci": "Science", "scient": "Scientific",
    "eng": "Engineering", "tech": "Technology", "technol": "Technology",
    "mfg": "Manufacturing", "elec": "Electric", "electr": "Electronics",
    "ges": "Gesellschaft", "forschung": "Forschung",
    "found": "Foundation", "inst": "Institute", "lab": "Laboratory",
    "labs": "Laboratories", "dev": "Development", "syst": "Systems",
    "equip": "Equipment", "mach": "Machinery", "mat": "Materials",
    "chem": "Chemical", "pharm": "Pharmaceutical", "med": "Medical",
    "natl": "National", "nat": "National", "univ": "University",
    "acad": "Academy", "hosp": "Hospital", "telecomm": "Telecommunications",
    "mgmt": "Management", "grp": "Group", "hldgs": "Holdings",
    "automot": "Automotive", "aerosp": "Aerospace", "constr": "Construction",
    "adv": "Advanced", "str": "Structure", "prod": "Production",
    "appl": "Applied", "environ": "Environmental", "agric": "Agricultural",
    "commun": "Communications", "instr": "Instruments", "prec": "Precision",
}

_FUNCTION_WORDS = {"of", "and", "for", "the", "on", "in", "at", "to", "de",
                   "du", "des", "der", "die", "das", "und", "van", "von",
                   "la", "le", "el", "y", "e", "a"}

_INITIALISMS = {
    "gs", "lg", "sk", "kt", "bt", "ge", "ibm", "abb", "basf", "byd", "catl",
    "cas", "cnrs", "csic", "eth", "kaist", "mit", "nasa", "nec", "nxp", "tdk",
    "tsmc", "smic", "zte", "cnpc", "sinopec", "cnooc", "clc", "das", "amd",
    "arm", "bmw", "dsm", "ntt", "kddi", "epfl", "cea", "jfe", "nsk", "ntn",
    "skf", "trw", "zf", "3m", "usa", "uk", "eu", "us", "cn", "jp", "kr",
}

_ORG_NOUNS = {"foundation", "institute", "research", "hospital", "center",
              "centre", "laboratory", "laboratories", "academy", "college",
              "school", "trust", "council", "association"}

_EPO_NAME_LIMIT = 50


def _cased_token(word: str, shouting: bool, first: bool) -> str:
    bare = word.strip(".,()").lower()
    if bare in _LEGAL_SUFFIXES:
        return _LEGAL_SUFFIXES[bare]
    if bare in _INITIALISMS:
        return bare.upper()
    if bare in _FUNCTION_WORDS and not first:
        return bare
    if bare in _ABBREVIATIONS:
        return _ABBREVIATIONS[bare]
    if word in {"&", "-", "+"}:
        return word
    if shouting:
        return word if len(bare) <= 2 else word.capitalize()
    return word


def split_assignee(name: str | None) -> dict:

    if not name or not name.strip():
        return {"name": None, "country": None, "kind": None}

    text = name.strip()
    raw_upper = text.upper()

    country = None
    tag = re.search(r"\s*\[([A-Z]{2})\]\s*$", text)
    if tag:
        country = tag.group(1)
        text = text[:tag.start()].strip()

    kind = classify_organisation(raw_upper)
    truncated = len(text) >= _EPO_NAME_LIMIT

    latin = [c for c in text if c.isalpha() and ord(c) < 0x250]
    if not latin:
        return {"name": text, "country": country, "kind": kind}

    shouting = sum(c.isupper() for c in latin) / len(latin) > 0.7
    raw_words = text.split()
    words = [_cased_token(w, shouting, i == 0) for i, w in enumerate(raw_words)]

    if words and words[0] == "University":
        rest = words[1:]
        if (1 <= len(rest) <= 3
                and not any(w.lower() in _ORG_NOUNS for w in rest)
                and not any(w.lower() in _INITIALISMS for w in rest)):
            words = rest + ["University"]

    for i, w in enumerate(words):
        if w in {"Institute", "University"} and i + 1 < len(words) \
                and words[i + 1] not in {"of", "&"} \
                and words[i + 1].lower() not in _INITIALISMS:
            words.insert(i + 1, "of")
            break

    cleaned = " ".join(words).strip(" ,")
    if truncated:
        cleaned = f"{cleaned}…"
    return {"name": cleaned or None, "country": country, "kind": kind}


def clean_assignee(name: str | None) -> str | None:
    """Display name only, without the country tag."""
    return split_assignee(name)["name"]


COMPANY = "Company"
ACADEMIC = "Academic / research"
STATE = "State / utility"
INDIVIDUAL = "Individual inventor"
OTHER = "Organisation"

_COMMERCIAL_NOUNS = {
    "technology", "technologies", "tech", "design", "designs", "energy",
    "energies", "systems", "system", "solutions", "industries", "industry",
    "electric", "electronics", "electrical", "works", "group", "partners",
    "labs", "laboratory", "laboratories", "materials", "power", "motors",
    "motor", "products", "product", "services", "engineering", "manufacturing",
    "batteries", "battery", "solar", "photovoltaic", "semiconductor", "devices",
    "device", "equipment", "machinery", "chemical", "chemicals", "pharma",
    "medical", "software", "digital", "networks", "network", "communications",
    "holdings", "ventures", "capital", "trading", "international", "global",
    "headquters", "headquarters", "fund", "enterprise", "enterprises",
}

_ACADEMIC_PREFIXES = ("univ", "universit", "inst", "acad", "polytech", "ecole",
                      "hochschule", "fachhochschule")
_ACADEMIC_TOKENS = {"college", "school", "cnrs", "cas", "csic", "eth", "kaist",
                    "fraunhofer", "helmholtz", "riken", "cnr", "inra", "csiro"}
_STATE_PHRASES = ("state grid", "power grid", "national lab", "natl lab",
                  "ministry", "municipal", "administration", "bureau",
                  "atomic energy", "energie atomique", "commissariat",
                  "national research council")
_STATE_TOKENS = {"agency", "commission", "authority", "govt", "government"}


def _looks_like_a_person(tokens: set[str], raw: str) -> bool:
    parts = [t for t in re.split(r"[\s]+", raw.strip()) if t]
    if not 2 <= len(parts) <= 4:
        return False
    if any(not re.fullmatch(r"[A-Za-z][A-Za-z'\-\.]*", p) for p in parts):
        return False
    return not (tokens & _COMMERCIAL_NOUNS)


def classify_organisation(raw: str | None) -> str | None:

    if not raw:
        return None
    upper = raw.upper()
    lower = raw.lower()
    tokens = {t.strip(".,()[]").lower() for t in re.split(r"[\s/]+", raw) if t}

    if any(t.startswith(_ACADEMIC_PREFIXES) for t in tokens) \
            or tokens & _ACADEMIC_TOKENS \
            or "max planck" in lower:
        return ACADEMIC
    if any(p in lower for p in _STATE_PHRASES) or tokens & _STATE_TOKENS:
        return STATE
    if tokens & set(_LEGAL_SUFFIXES) or "kabushiki" in lower:
        return COMPANY
    if any(marker in upper for marker in ("有限公司", "株式会社", "株式會社", "주식회사")):
        return COMPANY
    if tokens & _COMMERCIAL_NOUNS:
        return COMPANY
    stripped = re.sub(r"\s*\[[A-Z]{2}\]\s*$", "", raw).strip()
    if _looks_like_a_person(tokens, stripped):
        return INDIVIDUAL
    return OTHER


_GENERIC_LABELS = frozenset("""
application applications approach approaches area areas aspect assembly body
case cases circuit component components condition conditions configuration
constraint control data design detection device devices element elements
equipment example factor feature field function group information item items
layer level line material mechanism method model models module object operation
parameter part performance point position power problem process product property
range rate region requirement result results scheme section set signal solution
state step structure surface system systems target task technique technology
temperature test time type unit use value variable
""".split())


def _is_weak_label(candidate: str, query_stems: set[str]) -> bool:
    """Reject a generic noun, and the query echoed back at the reader."""
    parts = [w for w in re.split(r"[^a-z0-9]+", candidate.lower()) if w]
    if not parts:
        return True
    if all(p in _GENERIC_LABELS for p in parts):
        return True
    return any(p[:5] in query_stems for p in parts)


def _cluster_label(members: list[dict], words: list[str], used: set[str],
                   query: str = "") -> tuple[str, str]:
    """Name a cluster by the classification its members share."""
    codes = Counter()
    for p in members:
        for code in (p.get("classifications") or ([p["classification"]]
                                                  if p.get("classification") else [])):
            if code:
                codes[code] += 1

    query_stems = {w[:5] for w in re.split(r"[^a-z0-9]+", query.lower())
                   if len(w) >= 4}
    bigrams = [w for w in words if " " in w]
    candidates = bigrams + words
    strong_terms = [c for c in candidates if not _is_weak_label(c, query_stems)]

    for threshold in (0.25, 0.10):
        for code, count in codes.most_common(6):
            if count / len(members) < threshold:
                break
            label = ipc_names.describe(code)
            if label and label.lower() not in used:
                return label, "classification"

    for code, count in codes.most_common(6):
        if count / len(members) < 0.10:
            break
        label = ipc_names.describe(code)
        if not label:
            continue
        base_words = set(re.findall(r"[a-z0-9]+", label.lower()))
        for term in (strong_terms or candidates):
            if set(re.findall(r"[a-z0-9]+", term.lower())) <= base_words:
                continue
            combined = f"{label} — {term.title()}"
            if combined.lower() not in used:
                return combined, "classification"

    for candidate in strong_terms:
        label = candidate.title()
        if label.lower() not in used:
            return label, "terms"

    for candidate in candidates:
        label = candidate.title()
        if label.lower() not in used:
            return label, "terms"
    return "Other filings", "terms"


def _looks_english(doc: str) -> bool:
    """Cheap language check by English function-word density."""
    words = re.findall(r"[a-z]+", doc.lower())
    if len(words) < 8:
        return True
    hits = sum(1 for w in words if w in ENGLISH_STOP_WORDS)
    return hits / len(words) >= 0.08


def _cluster_stopwords(query: str) -> list[str]:

    query_words = {w for w in re.split(r"[^a-z0-9]+", query.lower()) if w}
    return sorted(ENGLISH_STOP_WORDS | _PATENT_STOPWORDS | _FOREIGN_STOPWORDS | query_words)


def _vectorize(docs: list[str], stopwords: list[str]):
    vectorizer = TfidfVectorizer(stop_words=stopwords, max_features=400,
                                 min_df=2, ngram_range=(1, 2),
                                 token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z0-9\-]+\b")
    try:
        matrix = vectorizer.fit_transform(docs)
    except ValueError:
        return None, None
    return vectorizer, matrix


def _cluster(patents: list[dict], query: str = "", max_clusters: int = 5) -> list[dict]:
    pairs = []
    for p in patents:
        title = "" if p["title"] == "Untitled" else p["title"]
        doc = f"{title} {p.get('abstract') or ''}".strip()
        if len(doc) >= _MIN_DOC_CHARS and _looks_english(doc):
            pairs.append((p, doc))
    if len(pairs) < 6:
        return []
    docs = [d for _, d in pairs]

    vectorizer, matrix = _vectorize(docs, _cluster_stopwords(query))
    if matrix is None or matrix.shape[1] < _MIN_FEATURES:
        vectorizer, matrix = _vectorize(docs, sorted(ENGLISH_STOP_WORDS | _PATENT_STOPWORDS | _FOREIGN_STOPWORDS))
    if matrix is None or matrix.shape[1] == 0:
        return []

    k = min(max_clusters, len(docs))
    model = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = model.fit_predict(matrix)

    terms = vectorizer.get_feature_names_out()
    centers = model.cluster_centers_

    groups = []
    for cid in range(k):
        members = [p for (p, _), lab in zip(pairs, labels) if lab == cid]
        if not members:
            continue
        top_idx = centers[cid].argsort()[::-1][:4]
        groups.append((members, [terms[i] for i in top_idx if centers[cid][i] > 0]))
    groups.sort(key=lambda g: len(g[0]), reverse=True)

    out = []
    used_labels: set[str] = set()
    for members, words in groups:
        label, basis = _cluster_label(members, words, used_labels, query=query)
        used_labels.add(label.lower())
        code = None
        match = re.search(r"\s*\(([A-H]\d{2}[A-Z])\)", label)
        if match:
            code = match.group(1)
            label = (label[:match.start()] + label[match.end():]).strip()
        out.append({
            "label": label,
            "code": code,
            "label_basis": basis,
            "terms": _distinct_terms(words),
            "size": len(members),
            "samples": [clean_title(p["title"]) for p in members[:2]],
        })

    shares = shares_of_total([c["size"] for c in out])
    clustered = sum(c["size"] for c in out)
    for cluster, share in zip(out, shares):
        cluster["share"] = share
        cluster["of_records"] = clustered
    return out


async def analyze_landscape(query: str, sample_size: int = 100) -> dict:
    series = _load_series(query)

    ops_sample = _load_sample(query)
    if ops_sample is not None:
        patents = ops_sample["records"]
        result = {"patents": patents, "corpus_total": None}
        cached = True
        sample_source = "epo_ops"
        sample_balanced = True
    else:
        result = _load_cache(query)
        cached = result is not None
        if result is None:
            try:
                result = await _fetch_patents(query, num=sample_size)
                _save_cache(query, result["patents"], result["corpus_total"])
            except Exception:
                if series is None:
                    raise
                result = {"patents": [], "corpus_total": None}
        patents = result["patents"]
        sample_source = "google_sample" if patents else None
        sample_balanced = False

    corpus_counts = (ops_sample or {}).get("applicant_counts") or None
    tested = (ops_sample or {}).get("candidates_tested")

    if series is not None:
        filings = series["by_year"]
        corpus_total = series["total"]
        counts_source = series.get("source", "epo_ops")
        date_basis = series.get("date_basis", "publication")
        stored_basis = series.get("query_basis") or "phrase"
        stale = stored_basis == "phrase" and epo_ops.cpc_for(query) is not None
        query_basis = stored_basis
        low_confidence = stale or (
            stored_basis == "phrase"
            and (corpus_total or 0) < epo_ops.LOW_CONFIDENCE_TOTAL
        )
        sampled = False
    else:
        filings = _filings_by_year(patents)
        corpus_total = result["corpus_total"]
        counts_source = "google_sample"
        date_basis = "filing"
        query_basis = "fulltext"
        low_confidence = False
        sampled = True

    derived = _load_derived(query, _fingerprint(patents, query, corpus_counts,
                                                corpus_total, tested))
    if derived is None:
        derived = build_derived(query, patents, corpus_counts, corpus_total, tested)

    return {
        "query": query,
        "corpus_total": corpus_total,
        "sample_size": len(patents),
        "sample_source": sample_source,
        "sample_date_kind": _record_date_kind(patents),
        "sample_balanced": sample_balanced,
        "filings_sampled": sampled,
        "counts_source": counts_source,
        "date_basis": date_basis,
        "query_basis": query_basis,
        "low_confidence": low_confidence,
        "filings_by_year": filings,
        "sampled_years": [f["year"] for f in filings],
        "top_assignees": derived["top_assignees"],
        "ownership": derived["ownership"],
        "clusters": derived["clusters"],
        "top_patents": derived["top_patents"],
        "cached": cached,
    }
