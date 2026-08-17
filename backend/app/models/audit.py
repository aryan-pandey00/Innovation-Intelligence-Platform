"""A record of who changed whose access, and when."""
from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base

ROLE_CHANGE = "role_change"
GRANT_SUPER = "grant_super"
REVOKE_SUPER = "revoke_super"
DELETE_USER = "delete_user"
DELETE_SELF = "delete_self"

ACTION_LABELS = {
    ROLE_CHANGE: "changed the role of",
    GRANT_SUPER: "made super-admin",
    REVOKE_SUPER: "removed super-admin from",
    DELETE_USER: "deleted the account of",
    DELETE_SELF: "deleted their own account",
}


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    action = Column(String, nullable=False, index=True)

    actor_id = Column(Integer, nullable=True)
    actor_email = Column(String, nullable=False)
    target_id = Column(Integer, nullable=True)
    target_email = Column(String, nullable=False)

    detail = Column(String, nullable=True)
