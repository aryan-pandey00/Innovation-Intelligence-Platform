from fastapi import APIRouter, Depends, HTTPException, Query
import httpx
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services import datasets
from app.schemas.common import MAX_QUERY_LENGTH

router = APIRouter(prefix="/api/datasets", tags=["Dataset Integration"])


@router.get("/publications/search")
async def search_publications(
    q: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH, description="Search text"),
    limit: int = Query(10, ge=1, le=25),
    _user: User = Depends(get_current_user),
):
    try:
        results = await datasets.search_publications(q, limit)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Publication data source unavailable")
    return {"source": "OpenAlex", "count": len(results), "results": results}


@router.get("/patents/search")
async def search_patents(
    q: str = Query(..., min_length=2, max_length=MAX_QUERY_LENGTH, description="Search text"),
    limit: int = Query(10, ge=1, le=25),
    _user: User = Depends(get_current_user),
):
    try:
        results = await datasets.search_patents(q, limit)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Patent data source unavailable")
    return {"source": "Google Patents", "count": len(results), "results": results}
