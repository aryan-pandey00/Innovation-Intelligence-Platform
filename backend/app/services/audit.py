"""Writing and reading the record of privileged actions."""
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.user import User


def record(db: Session, action: str, actor: User, target: User,
           detail: str | None = None) -> AuditEvent:
    event = AuditEvent(
        action=action,
        actor_id=actor.id,
        actor_email=actor.email,
        target_id=target.id,
        target_email=target.email,
        detail=detail,
    )
    db.add(event)
    return event


def recent(db: Session, limit: int = 20) -> list[AuditEvent]:
    return (db.query(AuditEvent)
            .order_by(AuditEvent.at.desc(), AuditEvent.id.desc())
            .limit(limit)
            .all())
