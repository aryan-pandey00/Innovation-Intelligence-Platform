from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services import assessment, trends

router = APIRouter(prefix="/api/innovation", tags=["Innovation Scoring"])


@router.get("/assessment")
async def score_technology(
    query: str = Query(..., min_length=2, description="Technology / topic / keyword"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # The profile must be loaded here too. Without it, searching a technology
    # swapped the scoring *method* rather than the term, so the same user got two
    # different scores for one technology depending on how they arrived.
    profile = assessment.profile_for(db, current_user.id)
    try:
        return await assessment.build(query, db, profile=profile,
                                      user_role=current_user.role.value)
    except (trends.ResearchQuotaExceeded, httpx.HTTPError) as exc:
        raise assessment.source_error(exc)


@router.get("/assessment/my")
async def my_assessment(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = assessment.profile_for(db, current_user.id)
    # Innovation is assessed for a technology, not a discipline.
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
