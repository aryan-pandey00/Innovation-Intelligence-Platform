from fastapi import APIRouter, Depends, HTTPException, Query, status
import httpx
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.research_profile import ResearchProfile
from app.services import patents_analysis, profile_utils

router = APIRouter(prefix="/api/patents", tags=["Patent Landscape"])


@router.get("/landscape")
async def landscape(
    query: str = Query(..., min_length=2, description="Technology / topic / keyword"),
    _user: User = Depends(get_current_user),
):
    try:
        return await patents_analysis.analyze_landscape(query)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Patent data source unavailable")


@router.get("/landscape/my")
async def my_landscape(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.query(ResearchProfile).filter(
        ResearchProfile.user_id == current_user.id).first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Create your research profile first to see your patent landscape.",
        )
    # Patents are indexed by technology, so this reads technology areas. Research
    # domains only stand in when the user has none, and we say so.
    fields, fallback = profile_utils.technology_terms(profile)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Add a technology area to your profile to see your patent landscape.",
        )
    try:
        result = await patents_analysis.analyze_landscape(fields[0])
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Patent data source unavailable")
    result["from_profile"] = True
    result["profile_fields"] = fields
    result["fields_are_fallback"] = fallback
    return result
