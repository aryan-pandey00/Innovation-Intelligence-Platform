import asyncio
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User, UserRole
from app.models.funding import FundingOpportunity
from app.models.research_profile import ResearchProfile
from app.schemas.funding import (
    FundingOpportunityCreate, FundingOpportunityResponse, FundingRecommendation,
    LiveOpportunity, RankedOpportunity,
)
from app.services import funding_reco, grants_gov, world_bank, ukri
from app.schemas.common import MAX_QUERY_LENGTH

router = APIRouter(prefix="/api/funding", tags=["Funding Discovery"])


@router.get("", response_model=list[FundingOpportunityResponse])
def list_opportunities(
    source_type: str | None = Query(None, description="Filter by funding category"),
    country: str | None = Query(None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    query = db.query(FundingOpportunity)
    if source_type:
        query = query.filter(FundingOpportunity.source_type == source_type)
    opportunities = query.order_by(FundingOpportunity.deadline.asc().nullslast()).all()
    if country:
        c = country.strip().lower()
        opportunities = [
            o for o in opportunities
            if not o.countries
            or "any" in [x.lower() for x in o.countries]
            or c in [x.lower() for x in o.countries]
        ]
    return opportunities


@router.get("/search", response_model=list[FundingOpportunityResponse])
def search_opportunities(
    q: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH, description="Search text"),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    like = f"%{q}%"
    return (db.query(FundingOpportunity)
            .filter(or_(
                FundingOpportunity.title.ilike(like),
                FundingOpportunity.agency.ilike(like),
                FundingOpportunity.description.ilike(like),
            ))
            .all())


def _serialize_curated(item: dict) -> dict:
    opp = FundingOpportunityResponse.model_validate(item["opportunity"]).model_dump(mode="json")
    opp["live"] = False
    return {**item, "opportunity": opp}


@router.get("/recommendations", response_model=list[RankedOpportunity])
async def recommendations(
    limit: int = Query(10, ge=1, le=50),
    eligible_only: bool = Query(False),
    include_live: bool = Query(False, description="Also score live external sources"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(ResearchProfile).filter(
        ResearchProfile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create your research profile first to get funding recommendations.",
        )
    opportunities = db.query(FundingOpportunity).all()
    ranked = funding_reco.rank_opportunities(
        profile=profile,
        publications=profile.publications,
        user_role=current_user.role.value,
        user_country=profile.country,
        opportunities=opportunities,
    )
    items = [_serialize_curated(r) for r in ranked]

    if include_live:
        terms = ((profile.research_domains or []) + (profile.keywords or [])
                 + (profile.technology_areas or []))
        keyword = " ".join(terms[:3])
        live_lists = await asyncio.gather(
            grants_gov.search_live(keyword=keyword),
            world_bank.search_live(keyword=keyword),
            ukri.search_live(keyword=keyword),
        )
        live_opps = [o for source in live_lists for o in source]
        items += funding_reco.score_live_for_profile(
            profile, profile.publications, profile.country, live_opps)

    if eligible_only:
        items = [r for r in items if r["eligible"]]
    items.sort(key=funding_reco.recommendation_order)
    return items[:limit]


@router.get("/live", response_model=list[LiveOpportunity])
async def live_opportunities(
    q: str = Query("", description="Keyword to search live funding sources"),
    _user: User = Depends(get_current_user),
):
    results = await asyncio.gather(
        grants_gov.search_live(keyword=q),
        world_bank.search_live(keyword=q),
        ukri.search_live(keyword=q),
    )
    return [item for source in results for item in source]


@router.get("/{opp_id}", response_model=FundingOpportunityResponse)
def get_opportunity(opp_id: int, db: Session = Depends(get_db),
                    _user: User = Depends(get_current_user)):
    opp = db.query(FundingOpportunity).filter(FundingOpportunity.id == opp_id).first()
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return opp


def _check_amounts(data: FundingOpportunityCreate) -> None:
    """A reversed range renders as "USD 500K–100K" and scores as if it were real."""
    if (data.amount_min is not None and data.amount_max is not None
            and data.amount_min > data.amount_max):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The minimum amount cannot be greater than the maximum.",
        )


@router.post("", response_model=FundingOpportunityResponse,
             status_code=status.HTTP_201_CREATED)

def create_opportunity(
    data: FundingOpportunityCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    _check_amounts(data)
    opp = FundingOpportunity(**data.model_dump())
    db.add(opp)
    db.commit()
    db.refresh(opp)
    return opp


@router.put("/{opp_id}", response_model=FundingOpportunityResponse)
def update_opportunity(
    opp_id: int,
    data: FundingOpportunityCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Full replace, not a patch."""
    opp = db.query(FundingOpportunity).filter(FundingOpportunity.id == opp_id).first()
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    _check_amounts(data)
    for field, value in data.model_dump().items():
        setattr(opp, field, value)
    db.commit()
    db.refresh(opp)
    return opp


@router.delete("/{opp_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_opportunity(
    opp_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    opp = db.query(FundingOpportunity).filter(FundingOpportunity.id == opp_id).first()
    if opp is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    db.delete(opp)
    db.commit()
