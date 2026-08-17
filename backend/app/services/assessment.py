"""One pass over a user's profile producing the innovation score."""
from fastapi import HTTPException, status
import httpx
from sqlalchemy.orm import Session

from app.models.funding import FundingOpportunity
from app.models.research_profile import ResearchProfile
from app.models.user import User
from app.services import (commercialization, funding_reco, innovation_scoring,
                          notifications, profile_utils, trends)


async def build(query: str, db: Session, patent_query: str | None = None,
                profile: ResearchProfile | None = None,
                user_role: str | None = None) -> dict:
    opportunities = db.query(FundingOpportunity).all()
    publications = list(profile.publications) if profile else []
    patents = list(profile.patents) if profile else []
    topical_pubs = profile_utils.publications_for(publications, query)
    topical_pats = profile_utils.patents_for(patents, query)

    if profile is not None:
        funding_recs = funding_reco.rank_opportunities(
            profile=profile,
            publications=publications,
            user_role=user_role or "researcher",
            user_country=profile.country,
            opportunities=opportunities,
            focus=query,
        )
    else:
        funding_recs = funding_reco.rank_by_query(query, opportunities)
    score = await innovation_scoring.analyze(
        query, funding_recs, patent_query=patent_query,
        publications=topical_pubs, patents=topical_pats,
        portfolio_publications=len(publications), portfolio_patents=len(patents))
    score["commercialization"] = commercialization.recommend(
        score, funding_recs, publications=topical_pubs, patents=topical_pats,
        user_role=user_role)
    notifications.record_reading(db, query, score["signals"])
    return score


def profile_for(db: Session, user_id: int) -> ResearchProfile | None:
    return db.query(ResearchProfile).filter(
        ResearchProfile.user_id == user_id).first()


async def for_user(db: Session, user_id: int) -> dict:
    """Assess one innovator's technology using *their* portfolio."""
    subject = db.query(User).filter(User.id == user_id).first()
    if subject is None:
        raise HTTPException(status_code=404, detail="User not found")
    profile = profile_for(db, user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{subject.full_name} has not built a portfolio yet.",
        )
    fields, fallback = technology_focus(
        profile, f"an assessment of {subject.full_name}")
    try:
        result = await build(fields[0], db, profile=profile,
                             user_role=subject.role.value)
    except (trends.ResearchQuotaExceeded, httpx.HTTPError) as exc:
        raise source_error(exc)
    result["for_user"] = {"id": subject.id, "name": subject.full_name,
                          "email": subject.email, "role": subject.role.value}
    result["profile_fields"] = fields
    result["fields_are_fallback"] = fallback
    return result


def technology_focus(profile: ResearchProfile | None, module: str) -> tuple[list[str], bool]:
    """The profile's technology terms, or a 400 saying which step is missing."""
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Create your research profile first to see your {module}.")
    fields, fallback = profile_utils.technology_terms(profile)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Add a technology area to your profile to see your {module}.")
    return fields, fallback


def source_error(exc: Exception) -> HTTPException:
    """A spent daily quota is not an outage; say which it is and when it clears."""
    if isinstance(exc, trends.ResearchQuotaExceeded):
        return HTTPException(status_code=503, detail=trends.quota_detail(exc))
    return HTTPException(status_code=502, detail="Research data source unavailable")
