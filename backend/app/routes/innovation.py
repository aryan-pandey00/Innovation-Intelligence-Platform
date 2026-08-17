from fastapi import APIRouter, Depends, Query
import httpx
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User, UserRole
from app.services import assessment, trends
from app.schemas.common import MAX_QUERY_LENGTH

router = APIRouter(prefix="/api/innovation", tags=["Innovation Scoring"])


@router.get("/assessment")
async def score_technology(
    query: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH, description="Technology / topic / keyword"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = assessment.profile_for(db, current_user.id)
    try:
        return await assessment.build(query, db, profile=profile,
                                      user_role=current_user.role.value)
    except (trends.ResearchQuotaExceeded, httpx.HTTPError) as exc:
        raise assessment.source_error(exc)


@router.get("/assessment/user/{user_id}")
async def assessment_for_user(
    user_id: int,
    db: Session = Depends(get_db),
    _staff: User = Depends(require_role(UserRole.ADMIN, UserRole.INNOVATION_MANAGER)),
):
    """Assess an innovator's technology using *their* portfolio."""
    return await assessment.for_user(db, user_id)


@router.get("/assessment/my")
async def my_assessment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = assessment.profile_for(db, current_user.id)
    fields, fallback = assessment.technology_focus(profile, "innovation assessment")
    try:
        result = await assessment.build(fields[0], db, profile=profile,
                                        user_role=current_user.role.value)
    except (trends.ResearchQuotaExceeded, httpx.HTTPError) as exc:
        raise assessment.source_error(exc)
    result["from_profile"] = True
    result["profile_fields"] = fields
    result["fields_are_fallback"] = fallback
    return result
