"""Platform-wide analytics for the manager and admin dashboards."""
from collections import Counter
from datetime import date
from typing import NamedTuple

from sqlalchemy.orm import Session, selectinload

from app.models.funding import FundingOpportunity
from app.models.research_profile import ResearchProfile
from app.models.user import User, UserRole
from app.services import funding_reco, profile_utils

STRONG_MATCH = 40
_MAX_PROFILES = 200
_AGENCY_REPEATS = 3

OWNER_ROLES = (UserRole.RESEARCHER, UserRole.STARTUP_FOUNDER)


class _Scored(NamedTuple):
    """One scoring pass, read three different ways."""
    best: dict[int, dict]
    reach: Counter
    eligibility: Counter
    unmatched: set[int]


def _profiles(db: Session) -> list[ResearchProfile]:
    return (db.query(ResearchProfile)
            .options(selectinload(ResearchProfile.publications))
            .order_by(ResearchProfile.id.desc())
            .limit(_MAX_PROFILES)
            .all())


def _owners(db: Session) -> list[User]:
    return db.query(User).filter(User.role.in_(OWNER_ROLES)).all()


def _score_owners(profiles: list[ResearchProfile], users_by_id: dict[int, User],
                  opportunities: list[FundingOpportunity]) -> _Scored:
    best: dict[int, dict] = {}
    reach: Counter = Counter()
    eligibility: Counter = Counter()
    unmatched: set[int] = set()

    for profile in profiles:
        user = users_by_id.get(profile.user_id)
        if user is None:
            continue
        ranked = funding_reco.rank_opportunities(
            profile=profile,
            publications=list(profile.publications),
            user_role=user.role.value,
            user_country=profile.country,
            opportunities=opportunities,
        )
        top = min(ranked, key=funding_reco.recommendation_order) if ranked else None
        if top is None or top["relevance_score"] <= 0:
            unmatched.add(user.id)
            continue
        best[user.id] = {
            "score": round(top["relevance_score"], 1),
            "title": top["opportunity"].title,
            "agency": top["opportunity"].agency,
            "eligibility": top["eligibility"],
        }
        for row in ranked:
            if row["relevance_score"] >= STRONG_MATCH:
                reach[row["opportunity"].id] += 1
                eligibility[row["eligibility"]] += 1

    return _Scored(best=best, reach=reach, eligibility=eligibility,
                   unmatched=unmatched)


def recommendation_stats(db: Session) -> dict:
    """Is the recommendation engine actually reaching the people it is for?"""
    accounts = db.query(User).all()
    owners = [u for u in accounts if u.role in OWNER_ROLES]
    owner_ids = {u.id for u in owners}
    opportunities = db.query(FundingOpportunity).all()

    profiles = [p for p in _profiles(db) if p.user_id in owner_ids]
    scored = _score_owners(profiles, {u.id: u for u in owners}, opportunities)

    strong = sum(1 for m in scored.best.values() if m["score"] >= STRONG_MATCH)
    weak = len(scored.best) - strong
    ranked_scores = sorted(m["score"] for m in scored.best.values())
    median = round(ranked_scores[len(ranked_scores) // 2], 1) if ranked_scores else None
    with_technology = sum(1 for p in profiles if profile_utils.technology_terms(p)[0])

    return {
        "accounts": {
            "total": len(accounts),
            "owners": len(owners),
            "staff": len(accounts) - len(owners),
        },
        "population": {
            "label": "portfolio owners",
            "total": len(owners),
            "with_profile": len(profiles),
            "without_profile": len(owners) - len(profiles),
            "with_technology_area": with_technology,
        },
        "matching": {
            "strong": strong,
            "weak_only": weak,
            "none": len(scored.unmatched),
            "median_best_match": median,
            "median_population": len(ranked_scores),
            "threshold": STRONG_MATCH,
        },
        "opportunities": {
            "total": len(opportunities),
            "reachable": len(scored.reach),
            "unreachable": len(opportunities) - len(scored.reach),
        },
        "reach": [{"id": o.id, "owners": scored.reach.get(o.id, 0)}
                  for o in opportunities],
        "eligibility": [{"status": k, "count": v}
                        for k, v in scored.eligibility.most_common()],
        "profiles_sampled": len(profiles) if len(profiles) == _MAX_PROFILES else None,
    }


def pipeline_stats(db: Session) -> dict:
    """What the monitored innovators work on, and what funding is open to them."""
    monitored = _owners(db)
    ids = {u.id for u in monitored}
    profiles = [p for p in _profiles(db) if p.user_id in ids]
    opportunities = db.query(FundingOpportunity).all()
    scored = _score_owners(profiles, {u.id: u for u in monitored}, opportunities)

    technologies: Counter = Counter()
    roster: list[dict] = []
    for profile in profiles:
        focus = sorted({t.strip() for t in (profile.technology_areas or []) if t.strip()})
        for term in {t.title() for t in focus}:
            technologies[term] += 1
        roster.append({
            "user_id": profile.user_id,
            "focus": focus,
            "best_match": scored.best.get(profile.user_id),
        })
    listed = {r["user_id"] for r in roster if r["focus"]}

    today = date.today()
    open_grants = [o for o in opportunities
                   if o.deadline is None or o.deadline >= today]

    agencies: Counter = Counter(o.agency for o in open_grants if o.agency)
    funded = [o for o in open_grants if o.amount_max]
    total_available = int(sum(o.amount_max for o in funded)) if funded else 0

    return {
        "innovators": len(monitored),
        "with_profile": len(profiles),
        "portfolios_with_focus": len(listed),
        "attention": {
            "no_portfolio": len(monitored) - len(profiles),
            "no_focus": len(profiles) - len(listed),
            "no_strong_match": sum(
                1 for r in roster
                if not r["best_match"] or r["best_match"]["score"] < STRONG_MATCH),
            "threshold": STRONG_MATCH,
        },
        "technologies": [{"name": n, "users": c} for n, c in technologies.most_common(8)],
        "roster": roster,
        "funding": {
            "opportunities": len(open_grants),
            "closed": len(opportunities) - len(open_grants),
            "agencies": len(agencies),
            "top_agencies": ([{"name": n, "count": c} for n, c in agencies.most_common(5)]
                             if agencies and agencies.most_common(1)[0][1] >= _AGENCY_REPEATS
                             else []),
            "total_available": total_available,
            "priced": len(funded),
        },
    }
