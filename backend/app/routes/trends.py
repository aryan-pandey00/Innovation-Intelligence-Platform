from fastapi import APIRouter, Depends, HTTPException, Query, status
import httpx
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.research_profile import ResearchProfile
from app.services import trends, profile_utils
from app.schemas.common import MAX_QUERY_LENGTH

router = APIRouter(prefix="/api/trends", tags=["Research Trends"])


@router.get("")
async def trend_analysis(
    query: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH, description="Topic / domain / keyword"),
    _user: User = Depends(get_current_user),
):
    try:
        return await trends.get_trends(query)
    except trends.ResearchQuotaExceeded as exc:
        raise HTTPException(status_code=503, detail=trends.quota_detail(exc))
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Research data source unavailable")


@router.get("/my")
async def my_domain_trends(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(ResearchProfile).filter(
        ResearchProfile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create your research profile first to see trends for your field.",
        )
    fields = profile_utils.research_terms(profile)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add research domains or keywords to your profile to see trends.",
        )
    try:
        result = await trends.get_trends(fields[0])
    except trends.ResearchQuotaExceeded as exc:
        raise HTTPException(status_code=503, detail=trends.quota_detail(exc))
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Research data source unavailable")
    result["from_profile"] = True
    result["profile_fields"] = fields
    return result
