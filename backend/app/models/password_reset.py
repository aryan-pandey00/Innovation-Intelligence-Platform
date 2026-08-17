"""Getting back into an account when there is nowhere to send anything."""
from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class SecurityAnswer(Base):
    """One of the two questions an account holder set for identifying themselves."""
    __tablename__ = "security_answers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    position = Column(Integer, nullable=False)

    question = Column(String, nullable=False)
    answer_hash = Column(String, nullable=False)

    set_at = Column(DateTime(timezone=True), server_default=func.now(),
                    onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "position", name="uq_security_answer_slot"),
    )


class PasswordResetRequest(Base):
    __tablename__ = "password_reset_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)

    requested_at = Column(DateTime(timezone=True), server_default=func.now(),
                          index=True)
    claim_hash = Column(String, nullable=True, index=True)

    answered_at = Column(DateTime(timezone=True), nullable=True)
    answer_summary = Column(Text, nullable=True)
    answers_matched = Column(Integer, nullable=True)
    had_questions = Column(Boolean, nullable=False, server_default="false")

    appeal_message = Column(Text, nullable=True)

    approved_at = Column(DateTime(timezone=True), nullable=True)
    issued_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"),
                          nullable=True)
    issued_by_email = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    consumed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", foreign_keys=[user_id])

    __table_args__ = (
        Index("ix_password_resets_user_time", "user_id", "requested_at"),
    )

    @property
    def is_cancelled(self) -> bool:
        return self.cancelled_at is not None

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_approved(self) -> bool:
        return self.approved_at is not None
