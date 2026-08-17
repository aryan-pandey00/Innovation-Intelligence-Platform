"""Module 11 — reports, in one shape that every format renders."""
from __future__ import annotations

import datetime as dt

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import audit as audit_model
from app.models.funding import FundingOpportunity
from app.models.research_profile import ResearchProfile
from app.models.user import User, UserRole, role_label
from app.services import (
    assessment, audit, data_health, funding_reco, patents_analysis,
    platform_analytics, profile_utils, trends,
)

OWNERS = (UserRole.RESEARCHER, UserRole.STARTUP_FOUNDER)
_MANAGERS = OWNERS + (UserRole.INNOVATION_MANAGER,)
_STAFF_MANAGER = (UserRole.INNOVATION_MANAGER,)

_ROLE_RANK = {
    UserRole.ADMIN: 0,
    UserRole.INNOVATION_MANAGER: 1,
    UserRole.RESEARCHER: 2,
    UserRole.STARTUP_FOUNDER: 3,
}

CATALOGUE = {
    "funding": {
        "title": "Funding Report",
        "summary": "Every catalogue grant ranked against your profile, with the "
                   "eligibility checks behind each one.",
        "roles": OWNERS,
        "needs_query": False,
        "needs_subject": False,
        "live": False,
    },
    "patents": {
        "title": "Patent Report",
        "summary": "Field size, filing history, who holds the IP and the themes "
                   "running through it.",
        "roles": _MANAGERS,
        "needs_query": True,
        "needs_subject": False,
        "live": True,
    },
    "trends": {
        "title": "Research Trend Report",
        "summary": "Publication volume over time, the busiest sub-fields, what is "
                   "rising, and the most cited work.",
        "roles": OWNERS,
        "needs_query": True,
        "needs_subject": False,
        "live": True,
    },
    "innovation": {
        "title": "Innovation Intelligence Report",
        "summary": "The innovation score and what each of the five weighted "
                   "factors contributed to it.",
        "roles": OWNERS,
        "needs_query": True,
        "needs_subject": False,
        "live": True,
    },
    "commercialization": {
        "title": "Commercialization Report",
        "summary": "The recommended route to market, and what to do first.",
        "roles": OWNERS,
        "needs_query": True,
        "needs_subject": False,
        "live": True,
    },
    "pipeline": {
        "title": "Innovation Pipeline Report",
        "summary": "Every monitored innovator, what they work on, the best funding "
                   "match open to each, and where the pipeline needs attention.",
        "roles": _STAFF_MANAGER,
        "needs_query": False,
        "needs_subject": False,
        "live": False,
    },
    "innovator": {
        "title": "Innovator Report",
        "summary": "One innovator's technology scored with their own portfolio, and "
                   "the route to market it implies.",
        "roles": _STAFF_MANAGER,
        "needs_query": False,
        "needs_subject": True,
        "live": True,
    },
    "system": {
        "title": "System Report",
        "summary": "Accounts, the reach of the recommendation engine, the funding "
                   "catalogue and the state of the cached data.",
        "roles": (UserRole.ADMIN,),
        "needs_query": False,
        "needs_subject": False,
        "live": False,
    },
    "accounts": {
        "title": "Accounts & Audit Report",
        "summary": "Every account with its role and whether a portfolio exists, plus "
                   "the record of who changed whose access.",
        "roles": (UserRole.ADMIN,),
        "needs_query": False,
        "needs_subject": False,
        "live": False,
    },
}


def available_for(role: UserRole) -> list[dict]:
    return [{"kind": k, "title": v["title"], "summary": v["summary"],
             "needs_query": v["needs_query"],
             "needs_subject": v["needs_subject"], "live": v["live"]}
            for k, v in CATALOGUE.items() if role in v["roles"]]


def _dash(v) -> str:
    return "—" if v is None or v == "" else str(v)


def _num(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float) and not v.is_integer():
        return f"{v:,.1f}"
    return f"{int(v):,}"


def _pct(v, sign: bool = False) -> str:
    if v is None:
        return "—"
    return f"{'+' if sign and v > 0 else ''}{round(float(v), 1)}%"


def _default_field_note(db: Session, subject: str) -> str | None:
    """Why this report covers the field it does, when nobody named one."""
    try:
        fields = [t["name"] for t in platform_analytics.pipeline_stats(db)["technologies"]]
    except Exception:
        return None
    if len(fields) <= 1:
        return f"No topic was given, so this covers {subject}, the one field named."
    others = [f for f in fields if f.casefold() != subject.casefold()]
    if not others:
        return None
    return (f"No topic was given, so this covers {subject} — one of "
            f"{len(fields)} technology areas your innovators name. Run it again with a "
            f"topic for {', '.join(others[:3])}"
            f"{'…' if len(others) > 3 else ''}.")


def _growth_pct(v) -> str:
    """Growth as a whole-number percentage, matching how the pathway signals render it."""
    if v is None:
        return "—"
    rounded = round(float(v))
    return f"{'+' if rounded > 0 else ''}{rounded}%"


def _tie_note(rows: list[dict], key: str = "users") -> str | None:
    """Say so when a ranked-looking table is actually a tie."""
    counts = [r.get(key) for r in rows]
    if len(counts) < 2 or len(set(counts)) != 1:
        return None
    return (f"All {len(counts)} are named by {counts[0]} "
            f"{'portfolio' if counts[0] == 1 else 'portfolios'} each, so the order is "
            f"not a ranking.")


def _empty_audit_note(moved: list) -> str:
    """What an empty audit log means, rather than what it looks like."""
    base = ("The log holds role changes, super-admin grants and deletions from the "
            "point auditing was added, so any change made before that leaves no entry "
            "here")
    if not moved:
        return base + "."
    n = len(moved)
    return (f"{base} — {n} account{'' if n == 1 else 's'} above "
            f"{'holds' if n == 1 else 'hold'} a role other than the one "
            f"{'it' if n == 1 else 'they'} registered with.")


def _median_note(matching: dict, population: dict) -> str | None:
    """What the median best match was actually taken over."""
    if matching.get("median_best_match") is None:
        return "Nobody with a portfolio has matched a grant yet."
    n = matching.get("median_population")
    if n is None:
        return None
    if n == 1:
        return ("The median is one owner: only one of the "
                f"{_num(population.get('with_profile'))} with a portfolio matched a "
                "grant at all.")
    return (f"The median is taken over the {_num(n)} owners that matched a grant at "
            f"all, not over the {_num(population.get('with_profile'))} with a "
            f"portfolio.")


def _date(v) -> str:
    """One date format across every report."""
    if not v:
        return "—"
    if isinstance(v, str):
        try:
            v = dt.date.fromisoformat(v[:10])
        except ValueError:
            return v
    try:
        return v.strftime("%d %b %Y")
    except AttributeError:
        return str(v)


def _clip(text: str | None, limit: int) -> str:
    """Shorten on a word boundary, and say that it was shortened."""
    text = (text or "").strip()
    if len(text) <= limit:
        return text or "—"
    cut = text[:limit].rsplit(" ", 1)[0].rstrip(",;:-")
    return f"{cut or text[:limit]}…"


def _section(heading, *, note=None, facts=None, columns=None, rows=None) -> dict:
    return {"heading": heading, "note": note, "facts": facts or [],
            "columns": columns or [], "rows": rows or []}


def _profile(db: Session, user: User) -> ResearchProfile:
    profile = (db.query(ResearchProfile)
                 .filter(ResearchProfile.user_id == user.id).first())
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create your research profile first to generate this report.")
    return profile


def _funding(db: Session, user: User, query: str | None,
             subject_id: int | None) -> tuple[str, list[dict]]:
    profile = _profile(db, user)
    opportunities = db.query(FundingOpportunity).all()
    ranked = funding_reco.rank_opportunities(
        profile=profile,
        publications=list(profile.publications),
        user_role=user.role.value,
        user_country=profile.country,
        opportunities=opportunities,
    )
    ranked.sort(key=funding_reco.recommendation_order)

    eligible = [r for r in ranked if r["eligibility"] == funding_reco.ELIGIBLE]
    unconfirmed = [r for r in ranked if r["eligibility"] == funding_reco.UNCONFIRMED]
    ruled_out = [r for r in ranked if r["eligibility"] == funding_reco.INELIGIBLE]
    strong = [r for r in ranked
              if r["eligibility"] != funding_reco.INELIGIBLE
              and r["relevance_score"] >= platform_analytics.STRONG_MATCH]

    def table(rows):
        return [[r["opportunity"].title, r["opportunity"].agency,
                 f"{round(r['relevance_score'])}%",
                 _date(r["opportunity"].deadline),
                 ", ".join(r["matched_terms"][:6]) or "—"] for r in rows]

    cols = ["Grant", "Agency", "Match", "Deadline", "Matched terms"]
    sections = [
        _section(
            "Summary",
            note=("Ranked on domain and keyword overlap plus text similarity, with "
                  f"eligibility checked against your role and country. A match of "
                  f"{platform_analytics.STRONG_MATCH}% or more is one the platform "
                  f"treats as worth acting on."),
            facts=[
                {"label": "Grants in the catalogue", "value": _num(len(ranked))},
                {"label": "Eligible for you", "value": _num(len(eligible))},
                {"label": "Unconfirmed (no country set)", "value": _num(len(unconfirmed))},
                {"label": "Ruled out", "value": _num(len(ruled_out))},
                {"label": f"Strong matches (≥{platform_analytics.STRONG_MATCH}%)",
                 "value": _num(len(strong))},
                {"label": "Best match",
                 "value": f"{round(ranked[0]['relevance_score'])}%" if ranked else "—"},
                {"label": "Best match grant",
                 "value": _clip(ranked[0]["opportunity"].title, 44) if ranked else "—"},
            ]),
        _section("Eligible grants", columns=cols, rows=table(eligible),
                 note="Your role and country both satisfied."),
    ]
    if unconfirmed:
        sections.append(_section(
            "Unconfirmed eligibility", columns=cols, rows=table(unconfirmed),
            note="Open to your role, but restricted by country and no country is "
                 "set on your profile. Adding one resolves these either way."))
    if ruled_out:
        sections.append(_section(
            "Ruled out", columns=cols, rows=table(ruled_out),
            note="Closed to your role, restricted to a country that is not yours, "
                 "or past its deadline."))
    return "Your profile", sections


async def _patents(db: Session, user: User, query: str | None,
                   subject_id: int | None) -> tuple[str, list[dict]]:
    subject = query or _own_field(db, user, technology=True)
    data = await patents_analysis.analyze_landscape(subject)
    defaulted = None if query else _default_field_note(db, subject)

    corpus = data.get("corpus_total")
    sample = data.get("sample_size") or 0
    own = data.get("ownership") or {}
    sampled_counts = data.get("filings_sampled") is not False
    basis = (f"Counts come from a sample of {_num(sample)} records."
             if sampled_counts else
             "Counts cover every matching patent, not a sample.")

    sections = [
        _section(
            "Field size and sampling",
            note=" ".join(filter(None, [
                defaulted,
                f"{basis} Anything reading the text inside a "
                f"patent — themes, assignee names — uses the "
                f"{_num(sample)}-record sample, which is date-balanced so no one "
                f"year dominates.",
            ])),
            facts=[
                {"label": "Patents in the field", "value": _num(corpus or sample)},
                {"label": "Records read", "value": _num(sample)},
                {"label": "Date basis", "value": _dash(data.get("date_basis"))},
                {"label": "Query basis", "value": _dash(data.get("query_basis"))},
                {"label": "Count confidence",
                 "value": "low — few records matched"
                          if data.get("low_confidence") else "normal"},
            ]),
        _section(
            "Filings by year",
            columns=["Year", "Filings"],
            rows=[[r["year"], _num(r.get("count"))]
                  for r in (data.get("filings_by_year") or [])],
            note=None if data.get("filings_sampled") is False else
                 "Sampled years: a relevance-ranked sample shows the shape of "
                 "filing activity, not true year-on-year volume."),
        _section(
            "Who holds the IP",
            columns=["Organisation", "Patents in field", "Share", "Type", "Country"],
            rows=[[a.get("assignee"), _num(a.get("corpus_count") or a.get("count")),
                   _pct(a.get("corpus_share")), _dash(a.get("kind")),
                   _dash(a.get("country"))]
                  for a in (data.get("top_assignees") or [])],
            facts=[
                {"label": f"Organisations in the {_num(own.get('records') or sample)}"
                          f"-record sample",
                 "value": _num(own.get("organisations"))},
                {"label": "Largest holder", "value": _dash(own.get("top_holder"))},
                {"label": "Their share of the whole field",
                 "value": _pct(own.get("top_share"))},
                {"label": "Concentration", "value": _dash(own.get("verdict"))},
            ],
            note="The table's counts are each applicant's true total across the whole "
                 "field, queried per applicant, not their share of the sample. The "
                 "organisation count above is the opposite: it is how many distinct "
                 "names appear in the sample that was read."),
        _section(
            "Innovation map",
            columns=["Theme", "Classification", "Patents", "Leading terms"],
            rows=[[c.get("label"), _dash(c.get("code")), _num(c.get("size")),
                   _clip(", ".join(c.get("terms") or []), 80)]
                  for c in (data.get("clusters") or [])],
            note="Themes are TF-IDF and K-means clusters over the sample, named by "
                 "the classification code their patents share."),
        _section(
            "Recent patents",
            columns=["Title", "Assignee", "Number", "Published"],
            rows=[[_clip(p.get("title"), 110), _dash(p.get("assignee")),
                   _dash(p.get("patent_number")), _date(p.get("publication_date"))]
                  for p in (data.get("top_patents") or [])[:15]],
            note="The most recently published, one per patent family. Several often "
                 "share the latest publication date, so the order within a date is "
                 "not a ranking."),
    ]
    return subject, sections


async def _trends(db: Session, user: User, query: str | None,
                  subject_id: int | None) -> tuple[str, list[dict]]:
    subject = query or _own_field(db, user, technology=False)
    data = await trends.get_trends(subject)
    window = data.get("emerging_window") or {}

    sections = [
        _section(
            "Summary",
            facts=[
                {"label": "Publications matched", "value": _num(data.get("total_works"))},
                {"label": f"Published since {_dash(data.get('recent_from_year'))}",
                 "value": _num(data.get("recent_works"))},
                {"label": "Share that is recent", "value": _pct(data.get("recent_share"))},
                {"label": "Sub-fields shown", "value": _num(data.get("topics_shown"))},
            ],
            note="Publication counts come from OpenAlex for this query."),
        _section(
            "Publications by year",
            columns=["Year", "Publications"],
            rows=[[r["year"], _num(r.get("count"))]
                  for r in (data.get("works_by_year") or [])]),
        _section(
            "Busiest sub-fields",
            columns=["Sub-field", "Publications", "Share"],
            rows=[[h.get("topic"), _num(h.get("count")), _pct(h.get("share"))]
                  for h in (data.get("hotspots") or [])]),
        _section(
            "Rising topics",
            columns=["Topic", "Earlier share", "Recent share", "Change"],
            rows=[[e.get("topic"), _pct(e.get("earlier_share")),
                   _pct(e.get("recent_share")), _pct(e.get("growth"), sign=True)]
                  for e in (data.get("emerging_topics") or [])],
            note=(f"Share of output in {_dash(window.get('recent_from'))} onwards "
                  f"against {_dash(window.get('earlier_from'))}–"
                  f"{_dash(window.get('earlier_to'))}. A rising share means the "
                  f"topic is taking a larger part of the field, not simply that "
                  f"more was published.")),
        _section(
            "Most cited work",
            columns=["Title", "Year", "Citations", "Venue"],
            rows=[[_clip(p.get("title"), 110), _dash(p.get("year")),
                   _num(p.get("cited_by_count")), _dash(p.get("venue"))]
                  for p in (data.get("top_papers") or [])[:15]]),
    ]
    return subject, sections


async def _innovation(db: Session, user: User, query: str | None,
                      subject_id: int | None) -> tuple[str, list[dict]]:
    profile = _profile(db, user)
    subject = query or _own_field(db, user, technology=True)
    score = await assessment.build(subject, db, profile=profile,
                                   user_role=user.role.value)
    s = score.get("signals") or {}

    sections = [
        _section(
            "Innovation score",
            facts=[
                {"label": "Score (out of 100)",
                 "value": _num(score.get("innovation_score"))},
                {"label": "Rating", "value": _dash(score.get("rating"))},
                {"label": "Lifecycle stage", "value": _dash(s.get("stage"))},
                {"label": "Opportunity", "value": _dash(s.get("opportunity_level"))},
            ],
            note="Five weighted factors, per the project specification. Corpus "
                 "sizes are normalised on a log scale and growth through tanh, so "
                 "no factor saturates into a constant."),
        _section(
            "What each factor contributed",
            columns=["Factor", "Weight", "Score", "Contribution", "What it measures"],
            rows=[[c.get("label"), f"{c.get('weight')}%", _num(c.get("score")),
                   _num(c.get("contribution")), c.get("description")]
                  for c in (score.get("components") or [])],
            note="Contribution is the factor's score times its weight — what it "
                 "actually added to the headline number."),
        _section(
            "The readings behind it",
            columns=["Signal", "Value"],
            rows=[
                ["Publications in this field", _num(s.get("research_total"))],
                ["Research growth", _growth_pct(s.get("research_growth"))],
                ["Patents in this field", _num(s.get("patent_total"))],
                ["Patent growth",
                 _growth_pct(s.get("patent_growth"))
                 if s.get("patent_history_reliable") else "not measurable"],
                ["Your publications on this technology", _num(s.get("own_publications"))],
                ["Your patents on this technology", _num(s.get("own_patents"))],
                ["Your whole portfolio",
                 f"{_num(s.get('portfolio_publications'))} publications, "
                 f"{_num(s.get('portfolio_patents'))} patents"],
            ],
            note="Only work matching this technology counts toward the score; the "
                 "portfolio totals are shown so 'none about this' can be told "
                 "apart from 'none at all'."),
    ]
    return subject, sections


async def _commercialization(db: Session, user: User, query: str | None,
                             subject_id: int | None) -> tuple[str, list[dict]]:
    profile = _profile(db, user)
    subject = query or _own_field(db, user, technology=True)
    score = await assessment.build(subject, db, profile=profile,
                                   user_role=user.role.value)
    comm = score.get("commercialization") or {}
    pathway = comm.get("pathway") or {}
    recs = comm.get("recommendations") or []
    now = [r for r in recs if r.get("priority") == "now"]
    context = [r for r in recs if r.get("priority") != "now"]

    def table(rows):
        return [[r.get("title"),
                 f"{(r.get('stat') or {}).get('value', '')} "
                 f"{(r.get('stat') or {}).get('label', '')}".strip(),
                 r.get("reading"), _dash(r.get("action"))] for r in rows]

    cols = ["Finding", "Figure", "Reading", "Action"]
    sections = [
        _section(
            "Recommended route",
            facts=[
                {"label": "Pathway", "value": _dash(pathway.get("title"))},
                *[{"label": sig["label"], "value": sig["value"]}
                  for sig in (pathway.get("signals") or [])],
            ],
            note=(pathway.get("detail") or "") +
                 " The route follows the field's lifecycle stage and your role: an "
                 "academic files through an institution that owns the result, a "
                 "founder for a company that already exists."),
        _section("Do next", columns=cols, rows=table(now),
                 note="Each carries a deadline or a risk."),
    ]
    if context:
        sections.append(_section("Worth knowing", columns=cols, rows=table(context),
                                 note="Context rather than an action."))
    return subject, sections


def _pipeline(db: Session, user: User, query: str | None,
              subject_id: int | None) -> tuple[str, list[dict]]:
    """The manager's dashboard, written down."""
    stats = platform_analytics.pipeline_stats(db)
    roster = stats.get("roster") or []
    attention = stats.get("attention") or {}
    funding = stats.get("funding") or {}

    ids = [r["user_id"] for r in roster]
    people = {u.id: u for u in db.query(User).filter(User.id.in_(ids)).all()} if ids else {}

    ordered = sorted(roster, key=lambda r: -((r.get("best_match") or {}).get("score") or -1))

    def row(r):
        u = people.get(r["user_id"])
        best = r.get("best_match")
        return [
            u.full_name if u else f"account {r['user_id']}",
            u.email if u else "—",
            (role_label(u.role) if u else "—"),
            ", ".join(r.get("focus") or []) or "no technology area",
            f"{round(best['score'])}%" if best else "—",
            best["agency"] if best else "nothing matched",
            best["eligibility"] if best else "—",
        ]

    sections = [
        _section(
            "Summary",
            facts=[
                {"label": "Monitored innovators", "value": _num(stats.get("innovators"))},
                {"label": "With a portfolio", "value": _num(stats.get("with_profile"))},
                {"label": "Ready to analyse",
                 "value": _num(stats.get("portfolios_with_focus"))},
                {"label": "Not set up yet", "value": _num(attention.get("no_portfolio"))},
                {"label": "Portfolio but no technology area",
                 "value": _num(attention.get("no_focus"))},
                {"label": f"No match at or above "
                          f"{_num(attention.get('threshold'))}%",
                 "value": _num(attention.get("no_strong_match"))},
            ],
            note="\"Monitored\" is every researcher and founder on the platform: there "
                 "is no manager-to-innovator assignment in the schema, so the "
                 "population is stated rather than implied. Ready to analyse means a "
                 "technology area is set, which is what the patent and innovation "
                 "modules run on."),
        _section(
            "Roster",
            columns=["Name", "Email", "Type", "Working on", "Best match", "Agency",
                     "Eligibility"],
            rows=[row(r) for r in ordered],
            note=f"The {_num(stats.get('with_profile'))} innovators who have built a "
                 f"portfolio; the other "
                 f"{_num((stats.get('innovators') or 0) - (stats.get('with_profile') or 0))} "
                 f"have nothing to score yet. Strongest funding match first, and each "
                 f"match is the row that innovator is shown first on their own "
                 f"dashboard, from the same scoring pass, so this report and their "
                 f"screen cannot disagree about a grant."),
        _section(
            "Technology focus",
            columns=["Technology area", "Portfolios naming it"],
            rows=[[t["name"], _num(t["users"])]
                  for t in (stats.get("technologies") or [])],
            note=" ".join(filter(None, [
                (f"Counted per innovator, not per mention, out of "
                 f"{_num(stats.get('portfolios_with_focus'))} "
                 + ("portfolio that names" if stats.get("portfolios_with_focus") == 1
                    else "portfolios that name")
                 + " any technology area at all."),
                _tie_note(stats.get("technologies") or []),
            ]))),
        _section(
            "Funding available",
            facts=[
                {"label": "Open opportunities", "value": _num(funding.get("opportunities"))},
                {"label": "Funding agencies", "value": _num(funding.get("agencies"))},
                {"label": "Total on offer",
                 "value": f"USD {_num(funding.get('total_available'))}"},
                {"label": "Awards stating a ceiling", "value": _num(funding.get("priced"))},
            ],
            note=" ".join(filter(None, [
                (f"Grants still open only; {_num(funding.get('closed'))} past their "
                 f"deadline are left out, being open to nobody."
                 if funding.get("closed") else None),
                "The total covers only awards that state an upper bound; a range with "
                "no ceiling is not a zero, and summing it would understate every one "
                "of them.",
            ]))),
    ]
    return "The innovation pipeline", sections


async def _innovator(db: Session, user: User, query: str | None,
                     subject_id: int | None) -> tuple[str, list[dict]]:
    """One innovator, scored with their own portfolio."""
    data = await assessment.for_user(db, subject_id)
    who = data.get("for_user") or {}
    s = data.get("signals") or {}
    comm = data.get("commercialization") or {}
    pathway = comm.get("pathway") or {}
    now = [r for r in (comm.get("recommendations") or []) if r.get("priority") == "now"]

    sections = [
        _section(
            "Innovator",
            facts=[
                {"label": "Name", "value": _dash(who.get("name"))},
                {"label": "Email", "value": _dash(who.get("email"))},
                {"label": "Type",
                 "value": _dash(role_label(who["role"]) if who.get("role") else None)},
                {"label": "Technology assessed", "value": _dash(data.get("query"))},
                {"label": "Their technology areas",
                 "value": ", ".join(data.get("profile_fields") or []) or "—"},
            ],
            note="Scored with this innovator's own portfolio. The same technology "
                 "scored from another account reads the own-work factors as zero, "
                 "which is why this report exists rather than a search for the field."
                 + (" Their profile names no technology area, so the field came from "
                    "their research domains." if data.get("fields_are_fallback") else "")),
        _section(
            "Innovation score",
            facts=[
                {"label": "Score (out of 100)",
                 "value": _num(data.get("innovation_score"))},
                {"label": "Rating", "value": _dash(data.get("rating"))},
                {"label": "Lifecycle stage", "value": _dash(s.get("stage"))},
                {"label": "Opportunity", "value": _dash(s.get("opportunity_level"))},
            ],
            note="Rating is the band the score falls in. Opportunity describes the "
                 "field rather than this innovator — it weighs how fast research is "
                 "growing against how fast patenting is, so a field where filing "
                 "outpaces publishing reads Low however strong a portfolio in it "
                 "may be."),
        _section(
            "What each factor contributed",
            columns=["Factor", "Weight", "Score", "Contribution", "What it measures"],
            rows=[[c.get("label"), f"{c.get('weight')}%", _num(c.get("score")),
                   _num(c.get("contribution")), c.get("description")]
                  for c in sorted(data.get("components") or [],
                                  key=lambda c: (-(c.get("weight") or 0),
                                                 -(c.get("score") or 0)))],
            note="Heaviest factor first. Contribution is the factor's score times its "
                 "weight — what it actually added to the headline number."),
        _section(
            "The readings behind it",
            columns=["Signal", "Value"],
            rows=[
                ["Publications in this field", _num(s.get("research_total"))],
                ["Research growth", _growth_pct(s.get("research_growth"))],
                ["Patents in this field", _num(s.get("patent_total"))],
                ["Patent growth",
                 _growth_pct(s.get("patent_growth"))
                 if s.get("patent_history_reliable") else "not measurable"],
                ["Their publications on this technology", _num(s.get("own_publications"))],
                ["Their patents on this technology", _num(s.get("own_patents"))],
                ["Their whole portfolio",
                 f"{_num(s.get('portfolio_publications'))} publications, "
                 f"{_num(s.get('portfolio_patents'))} patents"],
            ],
            note="Only work matching this technology counts toward the score; the "
                 "portfolio totals are shown so 'none about this' can be told apart "
                 "from 'none at all'."),
        _section(
            "Route to market",
            facts=[
                {"label": "Pathway", "value": _dash(pathway.get("title"))},
                *[{"label": sig["label"], "value": sig["value"]}
                  for sig in (pathway.get("signals") or [])],
                {"label": "Steps outstanding", "value": _num(len(now))},
            ],
            columns=["Step"],
            rows=[[r.get("title")] for r in now],
            note="The pathway follows the field's lifecycle stage and this innovator's "
                 "role. The detail behind each step is written to them directly, so "
                 "only the headings travel here."),
    ]
    return who.get("name") or f"account {subject_id}", sections


def _system(db: Session, user: User, query: str | None,
            subject_id: int | None) -> tuple[str, list[dict]]:
    reco = platform_analytics.recommendation_stats(db)
    pipeline = platform_analytics.pipeline_stats(db)
    health = data_health.data_health(db)

    accounts = reco.get("accounts") or {}
    population = reco.get("population") or {}
    matching = reco.get("matching") or {}
    opportunities = reco.get("opportunities") or {}
    cached = health.get("cached") or {}

    roster = sorted(pipeline.get("roster") or [],
                    key=lambda r: -((r.get("best_match") or {}).get("score") or -1))
    people = ({u.id: u for u in db.query(User)
                                 .filter(User.id.in_([r["user_id"] for r in roster])).all()}
              if roster else {})

    sections = [
        _section(
            "Accounts",
            facts=[
                {"label": "Total accounts", "value": _num(accounts.get("total"))},
                {"label": "Portfolio owners", "value": _num(accounts.get("owners"))},
                {"label": "Staff", "value": _num(accounts.get("staff"))},
            ],
            note="Staff run the platform and own no portfolio, so they are counted "
                 "here but never form the denominator of a reach figure."),
        _section(
            f"Reach across {_dash(population.get('label'))}",
            facts=[
                {"label": "Population", "value": _num(population.get("total"))},
                {"label": "With a portfolio", "value": _num(population.get("with_profile"))},
                {"label": "Without one", "value": _num(population.get("without_profile"))},
                {"label": "With a technology area",
                 "value": _num(population.get("with_technology_area"))},
                {"label": f"Strong match "
                          f"(≥{_num(matching.get('threshold'))}%)",
                 "value": _num(matching.get("strong"))},
                {"label": "Weak matches only", "value": _num(matching.get("weak_only"))},
                {"label": "Nothing matched", "value": _num(matching.get("none"))},
                {"label": "Median best match",
                 "value": _pct(matching.get("median_best_match"))},
            ],
            note=" ".join(filter(None, [
                _median_note(matching, population),
                (f"Measured over {_num(reco.get('profiles_sampled'))} profiles."
                 if reco.get("profiles_sampled") else None),
            ])) or None),
        _section(
            "Funding catalogue",
            facts=[
                {"label": "Grants", "value": _num(opportunities.get("total"))},
                {"label": "Reaching at least one owner",
                 "value": _num(opportunities.get("reachable"))},
                {"label": "Reaching nobody",
                 "value": _num(opportunities.get("unreachable"))},
            ],
            note="A grant reaches nobody when no portfolio on the platform matches "
                 "it. With few portfolios that is arithmetic rather than a fault."),
        _section(
            "Pipeline",
            columns=["Account", "Email", "Working on", "Best funding match"],
            rows=[[(people[r["user_id"]].full_name if r["user_id"] in people
                    else f"account {r['user_id']}"),
                   people[r["user_id"]].email if r["user_id"] in people else "—",
                   ", ".join(r.get("focus") or []) or "no technology area",
                   f"{round(r['best_match']['score'])}% — {r['best_match']['title']}"
                   if r.get("best_match") else "nothing matched"]
                  for r in roster],
            note=f"The {_num(population.get('with_profile'))} owners who have built a "
                 f"portfolio; the other {_num(population.get('without_profile'))} have "
                 f"nothing to score. Strongest match first, from the same scoring pass "
                 f"as the figures above and as each innovator's own dashboard."),
        _section(
            "Cached data",
            facts=[
                {"label": "Topics cached", "value": _num(cached.get("total"))},
                {"label": "With a full corpus", "value": _num(cached.get("with_corpus"))},
                {"label": "Sample only", "value": _num(cached.get("sample_only"))},
                {"label": "Fallback only", "value": _num(cached.get("fallback_only"))},
                {"label": "Field size is a floor",
                 "value": _num(cached.get("low_confidence"))},
                {"label": "Named by a portfolio",
                 "value": _num(cached.get("named_by_a_portfolio"))},
            ],
            note=" ".join(filter(None, [
                (f"{_num(cached.get('series_without_sample'))} topics are counted in "
                 f"both of the first two figures — their field size is known but "
                 f"there is no sample to read inside it — so those two do not sum to "
                 f"{_num(cached.get('total'))}."
                 if cached.get("series_without_sample") else None),
                "Read from disk and configuration only. Whether a source is throttled "
                "right now is not knowable without calling it, and this report never "
                "does.",
            ]))),
        _section(
            "Gaps",
            columns=["Technology named by a portfolio", "State"],
            rows=[[g.get("topic") if isinstance(g, dict) else str(g),
                   g.get("state", "no cached corpus") if isinstance(g, dict)
                   else "no cached corpus"]
                  for g in (health.get("gaps") or [])],
            note="Fields someone has put in a portfolio that have nothing cached "
                 "behind them — the answer to why a page came back empty."),
    ]
    return "This platform", sections


def _accounts(db: Session, user: User, query: str | None,
              subject_id: int | None) -> tuple[str, list[dict]]:
    """Who holds what access, and the record of it changing."""
    accounts = sorted(db.query(User).all(),
                      key=lambda u: (_ROLE_RANK.get(u.role, len(_ROLE_RANK)),
                                     (u.full_name or u.email).casefold()))
    owner_ids = {p.user_id for p in db.query(ResearchProfile.user_id).all()}
    events = audit.recent(db, limit=100)
    moved = [u for u in accounts if u.original_role and u.original_role != u.role]

    by_role: dict[str, int] = {}
    for u in accounts:
        by_role[u.role.value] = by_role.get(u.role.value, 0) + 1

    owners = [u for u in accounts if u.role in OWNERS]
    without = [u for u in owners if u.id not in owner_ids]

    def portfolio_state(u: User) -> str:
        if u.role not in OWNERS:
            return "not applicable — staff"
        return "yes" if u.id in owner_ids else "none built"

    sections = [
        _section(
            "Summary",
            facts=[
                {"label": "Accounts", "value": _num(len(accounts))},
                *[{"label": f"{role_label(role)}s", "value": _num(n)}
                  for role, n in sorted(by_role.items())],
                {"label": "Super-admins",
                 "value": _num(sum(1 for u in accounts if u.is_superuser))},
                {"label": "Portfolio owners without a portfolio", "value": _num(len(without))},
            ],
            note="The four role counts sum to the total. The last two do not add to "
                 "it: super-admins are a subset of the administrators above, and only "
                 "researchers and founders are counted in the final figure, since "
                 "administrators and innovation managers own no portfolio by design."),
        _section(
            "Accounts",
            columns=["Name", "Email", "Role", "Super-admin", "Portfolio",
                     "Registered as"],
            rows=[[u.full_name or "—", u.email,
                   role_label(u.role),
                   "yes" if u.is_superuser else "—",
                   portfolio_state(u),
                   (role_label(u.original_role) if u.original_role else "—")]
                  for u in accounts],
            note="Grouped by role, most privileged first, then by name. \"Registered "
                 "as\" is the role the account signed up with. Only researcher and "
                 "founder can be self-registered, and an administrator cannot move an "
                 "account between those two — the original is kept so a demotion has "
                 "somewhere to go back to."),
        _section(
            "Recent access changes",
            columns=["When", "Who", "Did what", "To whom", "Detail"],
            rows=[[_date(e.at), e.actor_email,
                   audit_model.ACTION_LABELS.get(e.action, e.action),
                   ("themselves" if e.action == audit_model.DELETE_SELF
                    else e.target_email),
                   _dash(e.detail)]
                  for e in events],
            note="Role changes, super-admin grants and account deletions. Both "
                 "identities are stored as text rather than as references, so a record "
                 "still names an account that has since been deleted — which is most "
                 "of the point of keeping it."
                 if events else _empty_audit_note(moved)),
    ]
    return "This platform", sections


def _pipeline_field(db: Session) -> str:
    """The field most of a manager's innovators work in."""
    technologies = platform_analytics.pipeline_stats(db)["technologies"]
    if not technologies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No innovator on the platform has named a technology area yet, so "
                   "there is no field to report on. Name one above to run this report.")
    return technologies[0]["name"]


def _own_field(db: Session, user: User, *, technology: bool) -> str:
    """The subject to report on when none was given."""
    if user.role not in OWNERS:
        return _pipeline_field(db)

    profile = _profile(db, user)
    if technology:
        fields, _ = profile_utils.technology_terms(profile)
        missing = "Add a technology area to your profile, or name one to report on."
    else:
        fields = profile_utils.research_terms(profile)
        missing = ("Add research domains or keywords to your profile, or name a "
                   "topic to report on.")
    if not fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=missing)
    return fields[0]


_BUILDERS = {
    "funding": _funding,
    "patents": _patents,
    "trends": _trends,
    "innovation": _innovation,
    "commercialization": _commercialization,
    "pipeline": _pipeline,
    "innovator": _innovator,
    "system": _system,
    "accounts": _accounts,
}

assert set(_BUILDERS) == set(CATALOGUE), (
    f"report catalogue and builders disagree: "
    f"{set(CATALOGUE) ^ set(_BUILDERS)}")


async def build(kind: str, db: Session, user: User, query: str | None = None,
                subject_id: int | None = None) -> dict:
    spec = CATALOGUE.get(kind)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"No such report: {kind}")
    if user.role not in spec["roles"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"The {spec['title'].lower()} is not available to your role.")
    if spec["needs_subject"] and subject_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The {spec['title'].lower()} is about one innovator. "
                   f"Choose which from the list.")

    builder = _BUILDERS[kind]
    try:
        result = builder(db, user, query, subject_id)
        subject, sections = await result if spec["live"] else result
    except trends.ResearchQuotaExceeded as exc:
        raise HTTPException(status_code=503, detail=trends.quota_detail(exc))

    return {
        "kind": kind,
        "title": spec["title"],
        "subject": subject,
        "summary": spec["summary"],
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "meta": [
            {"label": "Prepared for", "value": user.full_name or user.email},
            {"label": "Role", "value": role_label(user.role)},
            {"label": "Subject", "value": subject},
            {"label": "Generated", "value": dt.datetime.now().strftime("%d %b %Y, %H:%M")},
        ],
        "sections": sections,
    }


def filename(report: dict, extension: str) -> str:
    """A name that says what it is and when, safe on every filesystem."""
    stamp = dt.date.today().isoformat()
    subject = "".join(ch if ch.isalnum() else "-"
                      for ch in (report.get("subject") or "")).strip("-").lower()
    subject = "-".join(p for p in subject.split("-") if p)[:40]
    parts = [report["kind"], subject, stamp] if subject else [report["kind"], stamp]
    return f"{'-'.join(parts)}.{extension}"
