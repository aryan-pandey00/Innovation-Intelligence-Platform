from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_role
from app.models.password_reset import PasswordResetRequest
from app.models.user import User, UserRole
from app.services import audit, data_health, notifications, password_reset

router = APIRouter(prefix="/api/admin", tags=["Administration"])


@router.get("/data-health")
def platform_data_health(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """What the analysis pages have cached, and which named fields have nothing."""
    return data_health.data_health(db)


def _row(db: Session, request_id: int) -> PasswordResetRequest:
    row = db.get(PasswordResetRequest, request_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such reset request.")
    return row


def _as_json(row: PasswordResetRequest) -> dict:
    """What the queue shows."""
    state = ("cancelled" if row.is_cancelled else
             "completed" if row.is_consumed else
             "expired" if row.is_approved and password_reset.is_expired(row) else
             "approved" if row.is_approved else "waiting")
    return {
        "id": row.id,
        "state": state,
        "user_id": row.user_id,
        "email": row.user.email if row.user else None,
        "full_name": row.user.full_name if row.user else None,
        "role": row.user.role.value if row.user else None,
        "requested_at": row.requested_at,
        "answered_at": row.answered_at,
        "answers": password_reset.read_answers(row),
        "answers_matched": row.answers_matched,
        "had_questions": row.had_questions,
        "basis": password_reset.evidence_summary(row),
        "appeal_message": row.appeal_message,
        "approved_at": row.approved_at,
        "approved_by": row.issued_by_email,
        "expires_at": row.expires_at,
        "consumed_at": row.consumed_at,
        "cancelled_at": row.cancelled_at,
    }


@router.get("/password-resets")
def list_password_resets(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Three lists, because a request is in one of three situations."""
    settled = password_reset.decided(db)
    live = [r for r in settled if password_reset.is_live_approval(r)]
    finished = [r for r in settled if not password_reset.is_live_approval(r)]
    return {
        "waiting": [_as_json(r) for r in password_reset.pending(db)],
        "approved": [_as_json(r) for r in live],
        "recent": [_as_json(r) for r in finished[:20]],
        "ttl_minutes": password_reset.APPROVAL_TTL_MINUTES,
    }


@router.get("/password-resets/waiting")
def count_waiting_resets(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Just the number, for the sidebar badge."""
    return {"waiting": len(password_reset.pending(db))}


@router.post("/password-resets/{request_id}/approve")
def approve_password_reset(
    request_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Let a request through, so the browser that made it can set a new password."""
    row = _row(db, request_id)
    if not password_reset.approve(db, row, admin):
        raise HTTPException(
            status_code=400,
            detail="That request cannot be approved — it has already been "
                   "completed, cancelled, or approved.")

    audit.record(db, "password_reset_approved", actor=admin, target=row.user,
                 detail=password_reset.evidence_summary(row))
    notifications.emit(
        db, row.user_id, notifications.PLATFORM_HEALTH,
        "Password reset approved",
        "An administrator approved your password reset. Return to the page you "
        f"asked from within {password_reset.APPROVAL_TTL_MINUTES} minutes to set a "
        "new password.",
        dedupe_key=f"password:approved:{row.id}",
        priority=notifications.NOW,
    )
    db.commit()
    return _as_json(row)


@router.post("/password-resets/{request_id}/cancel")
def cancel_password_reset(
    request_id: int = Path(..., ge=1),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Refuse a request, or withdraw an approval given to the wrong person."""
    row = _row(db, request_id)
    if row.is_consumed:
        raise HTTPException(status_code=400,
                            detail="That reset has already been completed.")
    password_reset.cancel(row)
    audit.record(db, "password_reset_cancelled", actor=admin, target=row.user,
                 detail=password_reset.evidence_summary(row))
    notifications.emit(
        db, row.user_id, notifications.PLATFORM_HEALTH,
        "Password reset declined",
        "An administrator declined your password reset request. Speak to them if "
        "you still cannot sign in.",
        dedupe_key=f"password:cancelled:{row.id}",
        priority=notifications.NOW,
    )
    db.commit()
    return _as_json(row)
