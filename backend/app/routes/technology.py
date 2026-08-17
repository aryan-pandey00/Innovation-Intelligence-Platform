from fastapi import APIRouter, Depends, HTTPException, Query, status
import httpx
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.research_profile import ResearchProfile
from app.services import notifications, tech_intelligence, trends, profile_utils
from app.schemas.common import MAX_QUERY_LENGTH

router = APIRouter(prefix="/api/technology", tags=["Technology Intelligence"])


@router.get("/intelligence")
async def technology_intelligence(
    query: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH, description="Technology / topic / keyword"),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        result = await tech_intelligence.analyze_technology(query)
    except trends.ResearchQuotaExceeded as exc:
        raise HTTPException(status_code=503, detail=trends.quota_detail(exc))
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Research data source unavailable")
    notifications.record_reading(db, query, result)
    return result


@router.get("/intelligence/my")
async def my_technology_intelligence(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(ResearchProfile).filter(
        ResearchProfile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create your research profile first to see your technology intelligence.",
        )
    fields, fallback = profile_utils.technology_terms(profile)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add a technology area to your profile to assess its maturity.",
        )
    try:
        result = await tech_intelligence.analyze_technology(fields[0])
    except trends.ResearchQuotaExceeded as exc:
        raise HTTPException(status_code=503, detail=trends.quota_detail(exc))
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Research data source unavailable")
    notifications.record_reading(db, fields[0], result)
    result["from_profile"] = True
    result["profile_fields"] = fields
    result["fields_are_fallback"] = fallback
    return result
