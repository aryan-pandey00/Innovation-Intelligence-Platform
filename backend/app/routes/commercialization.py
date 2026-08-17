"""Commercialization recommendations for a technology."""
from fastapi import APIRouter, Depends, Query
import httpx
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services import assessment, trends
from app.schemas.common import MAX_QUERY_LENGTH

router = APIRouter(prefix="/api/commercialization",
                   tags=["Commercialization Recommendations"])


def _payload(score: dict) -> dict:
    comm = score["commercialization"]
    return {
        "query": score["query"],
        "pathway": comm["pathway"],
        "recommendations": comm["recommendations"],
        "innovation_score": score["innovation_score"],
        "rating": score["rating"],
        "stage": score["signals"]["stage"],
    }


@router.get("")
async def recommend_for_technology(
    query: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH, description="Technology / topic / keyword"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = assessment.profile_for(db, current_user.id)
    try:
        score = await assessment.build(query, db, profile=profile,
                                       user_role=current_user.role.value)
    except (trends.ResearchQuotaExceeded, httpx.HTTPError) as exc:
        raise assessment.source_error(exc)
    return _payload(score)


@router.get("/my")
async def my_recommendations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = assessment.profile_for(db, current_user.id)
    fields, fallback = assessment.technology_focus(
        profile, "commercialization recommendations")
    try:
        score = await assessment.build(fields[0], db, profile=profile,
                                       user_role=current_user.role.value)
    except (trends.ResearchQuotaExceeded, httpx.HTTPError) as exc:
        raise assessment.source_error(exc)
    return {**_payload(score), "from_profile": True,
            "profile_fields": fields, "fields_are_fallback": fallback}
