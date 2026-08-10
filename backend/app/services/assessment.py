"""One pass over a user's profile producing the innovation score, the funding
ranking behind it and the commercialization advice drawn from both.

Module 7 (scoring) and module 8 (commercialization) share this because they share
their inputs: the advice quotes the same filtered records and the same funding
match the score was computed from, so deriving them separately would let the two
pages disagree about the same user.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.funding import FundingOpportunity
from app.models.research_profile import ResearchProfile
from app.services import (commercialization, funding_reco, innovation_scoring,
                          profile_utils, trends)


async def build(query: str, db: Session, patent_query: str | None = None,
                profile: ResearchProfile | None = None,
                user_role: str | None = None) -> dict:
    opportunities = db.query(FundingOpportunity).all()
    publications = list(profile.publications) if profile else []
    patents = list(profile.patents) if profile else []
    # Only work about this technology counts toward the score. Funding keeps the
    # whole portfolio: a grant match asks about the person, not one field.
    topical_pubs = profile_utils.publications_for(publications, query)
    topical_pats = profile_utils.patents_for(patents, query)

    # Profile *and* technology together. The bare term threw away the role and
    # country checks and disagreed with the dashboard on the same grant; the
    # profile alone made Funding Relevance identical for every technology.
    # `rank_by_query` survives only for a user with no profile at all.
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
    # advice must agree with the score, so it sees the same filtered records
    score["commercialization"] = commercialization.recommend(
        score, funding_recs, publications=topical_pubs, patents=topical_pats)
    return score


def profile_for(db: Session, user_id: int) -> ResearchProfile | None:
    return db.query(ResearchProfile).filter(
        ResearchProfile.user_id == user_id).first()


def technology_focus(profile: ResearchProfile | None, module: str) -> tuple[list[str], bool]:
    """The profile's technology terms, or a 400 saying which step is missing.

    Both entry points need the same two checks and the same two messages; `module`
    only names what the reader was trying to open.
    """
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
