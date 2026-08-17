import re
from datetime import date
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_STOPWORDS = {
    "all", "disciplines", "research", "science", "sciences", "technology",
    "tech", "innovation", "development", "fundamental", "basic", "general",
    "program", "programs", "fund", "funding", "grant", "grants", "project",
    "and", "the", "for", "of", "in", "to",
}


def _term_words(term: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", term.lower())
            if len(w) >= 2 and w not in _STOPWORDS}


def build_profile_text(profile, publications) -> str:
    parts = []
    if profile is not None:
        parts += profile.research_domains or []
        parts += profile.keywords or []
        parts += profile.technology_areas or []
        if profile.headline:
            parts.append(profile.headline)
        if profile.bio:
            parts.append(profile.bio)
    parts += [p.title for p in (publications or []) if p.title]
    return " ".join(parts).strip()


def profile_terms(profile) -> set[str]:
    if profile is None:
        return set()
    terms = (profile.research_domains or []) + (profile.keywords or []) + \
            (profile.technology_areas or [])
    return {t.strip().lower() for t in terms if t.strip()}


def _opportunity_text(opp) -> str:
    return " ".join([
        opp.title or "", opp.description or "",
        " ".join(opp.domains or []), " ".join(opp.keywords or []),
    ]).strip()


ELIGIBLE = "eligible"
UNCONFIRMED = "unconfirmed"
INELIGIBLE = "ineligible"


def recommendation_order(row: dict) -> tuple:
    """Sort key for the order a person is shown their matches in."""
    return (not row["eligible"], -row["relevance_score"])


def check_eligibility(opp, user_role: str, user_country: str | None,
                      today: date) -> tuple[str, list[str]]:
    """Returns (status, reasons) where status is one of the three above."""
    status = ELIGIBLE
    reasons = []

    roles = opp.eligible_roles or []
    if roles and user_role not in roles:
        status = INELIGIBLE
        reasons.append(f"Open only to: {', '.join(roles)}")
    else:
        reasons.append("Open to your role")

    countries = [c.lower() for c in (opp.countries or [])]
    if countries and "any" not in countries:
        if user_country and user_country.strip().lower() in countries:
            reasons.append(f"Available in {user_country}")
        elif user_country:
            status = INELIGIBLE
            reasons.append(f"Open only in: {', '.join(opp.countries)}")
        else:
            if status == ELIGIBLE:
                status = UNCONFIRMED
            reasons.append(f"Limited to {', '.join(opp.countries)} — add your country to check")
    else:
        reasons.append("Open in any country")

    if opp.deadline and opp.deadline < today:
        status = INELIGIBLE
        reasons.append(f"Closed on {opp.deadline.isoformat()}")
    elif opp.deadline:
        reasons.append(f"Closes {opp.deadline.isoformat()}")

    return status, reasons


def _live_eligibility(opp: dict, user_country: str | None) -> tuple[str, list[str]]:
    countries = [c.lower() for c in (opp.get("countries") or [])]
    if not countries or "any" in countries:
        return ELIGIBLE, ["Open in any country"]
    if user_country and user_country.strip().lower() in countries:
        return ELIGIBLE, [f"Available in {user_country}"]
    if user_country:
        return INELIGIBLE, [f"Open only in: {', '.join(opp.get('countries'))}"]
    return UNCONFIRMED, [f"Limited to {', '.join(opp.get('countries'))} — add your country to check"]


def score_live_for_profile(profile, publications, user_country, live_opps) -> list[dict]:
    if not live_opps:
        return []
    ptext = build_profile_text(profile, publications)
    pwords = set()
    for t in profile_terms(profile):
        pwords |= _term_words(t)

    texts = [f"{o.get('title', '')} {o.get('description', '')}".strip() for o in live_opps]
    cosines = [0.0] * len(live_opps)
    if ptext:
        try:
            matrix = TfidfVectorizer(stop_words="english").fit_transform([ptext] + texts)
            cosines = list(cosine_similarity(matrix[0:1], matrix[1:]).flatten())
        except ValueError:
            pass

    results = []
    for opp, cos in zip(live_opps, cosines):
        text_sim = min(1.0, float(cos) * 4)
        owords = _term_words(f"{opp.get('title', '')} {opp.get('description', '')}")
        matched_all = [w for w in pwords if w in owords]
        overlap = len(matched_all) / max(1, len(pwords))
        relevance = round(100 * (0.6 * overlap + 0.4 * text_sim), 1)
        matched = sorted(matched_all)[:6]
        status, reasons = _live_eligibility(opp, user_country)
        results.append({
            "opportunity": opp,
            "relevance_score": relevance,
            "eligibility": status,
            "eligible": status != INELIGIBLE,
            "matched_terms": matched,
            "reasons": reasons,
        })
    return results


def rank_by_query(query: str, opportunities) -> list[dict]:
    if not opportunities or not query.strip():
        return []
    qwords = _term_words(query)
    opp_texts = [_opportunity_text(o) for o in opportunities]

    cosines = [0.0] * len(opportunities)
    try:
        matrix = TfidfVectorizer(stop_words="english").fit_transform([query] + opp_texts)
        cosines = list(cosine_similarity(matrix[0:1], matrix[1:]).flatten())
    except ValueError:
        pass

    results = []
    for opp, cos in zip(opportunities, cosines):
        opp_terms = {t.strip().lower() for t in
                     (opp.domains or []) + (opp.keywords or []) if t.strip()}
        matched = sorted(t for t in opp_terms if _term_words(t) & qwords)
        tag_ratio = len(matched) / max(1, len(opp_terms))
        text_sim = min(1.0, float(cos) * 4)
        relevance = round(100 * (0.6 * tag_ratio + 0.4 * text_sim), 1)
        results.append({"opportunity": opp, "relevance_score": relevance})

    results.sort(key=lambda r: -r["relevance_score"])
    return results


def rank_opportunities(profile, publications, user_role, user_country,
                       opportunities, today=None, focus: str | None = None) -> list[dict]:
    """`focus` narrows the ranking to one technology without dropping the profile."""
    if today is None:
        today = date.today()
    if not opportunities:
        return []

    ptext = build_profile_text(profile, publications)
    pterms = profile_terms(profile)
    focus_key = (focus or "").strip().lower()
    if focus_key and focus_key not in pterms:
        pterms = pterms | {focus_key}
        ptext = f"{ptext} {focus}".strip()
    pwords = set()
    for t in pterms:
        pwords |= _term_words(t)
    opp_texts = [_opportunity_text(o) for o in opportunities]

    cosines = [0.0] * len(opportunities)
    if ptext:
        try:
            matrix = TfidfVectorizer(stop_words="english").fit_transform([ptext] + opp_texts)
            cosines = list(cosine_similarity(matrix[0:1], matrix[1:]).flatten())
        except ValueError:
            pass

    results = []
    for opp, cos in zip(opportunities, cosines):
        status, reasons = check_eligibility(opp, user_role, user_country, today)
        opp_terms = {t.strip().lower() for t in
                     (opp.domains or []) + (opp.keywords or []) if t.strip()}
        matched = sorted(t for t in opp_terms if _term_words(t) & pwords)

        tag_ratio = len(matched) / max(1, len(opp_terms))
        text_sim = min(1.0, float(cos) * 4)
        relevance = round(100 * (0.6 * tag_ratio + 0.4 * text_sim), 1)

        results.append({
            "opportunity": opp,
            "relevance_score": relevance,
            "eligibility": status,
            "eligible": status != INELIGIBLE,
            "matched_terms": matched,
            "reasons": reasons,
        })

    results.sort(key=lambda r: (
        {ELIGIBLE: 0, UNCONFIRMED: 1, INELIGIBLE: 2}[r["eligibility"]],
        -r["relevance_score"],
        r["opportunity"].deadline or date.max,
    ))
    return results
