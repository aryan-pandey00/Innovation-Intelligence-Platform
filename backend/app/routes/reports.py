"""Module 11 — reports and export."""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services import report_formats, reports
from app.schemas.common import MAX_QUERY_LENGTH

router = APIRouter(prefix="/api/reports", tags=["Reports & Export"])

_MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
}


@router.get("")
def catalogue(current_user: User = Depends(get_current_user)):
    """The reports this role may run."""
    return {"reports": reports.available_for(current_user.role)}


@router.get("/{kind}")
async def report(
    kind: str,
    query: str | None = Query(None, min_length=2, max_length=MAX_QUERY_LENGTH,
                              description="Topic to report on; defaults to your own field"),
    subject_id: int | None = Query(None, ge=1,
                                   description="Account to report on, for reports about "
                                               "one innovator"),
    format: str = Query("json", pattern="^(json|xlsx|pdf)$"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        built = await reports.build(kind, db, current_user, query,
                                    subject_id=subject_id)
    except httpx.HTTPError:
        raise HTTPException(status_code=502,
                            detail="A data source this report needs is unavailable.")

    if format == "json":
        return built

    body = (report_formats.to_xlsx(built) if format == "xlsx"
            else report_formats.to_pdf(built))
    name = reports.filename(built, format)
    return Response(
        content=body,
        media_type=_MEDIA[format],
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )
