"""Notifications, and the baseline that makes "this changed" answerable."""
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from app.core.database import Base

FUNDING_NEW = "funding_new"
FUNDING_DEADLINE = "funding_deadline"
PATENT_ACTIVITY = "patent_activity"
TECHNOLOGY_EMERGING = "technology_emerging"
RESEARCH_TREND = "research_trend"
COMMERCIALIZATION = "commercialization"
PLATFORM = "platform"
PLATFORM_HEALTH = "platform_health"
PIPELINE = "pipeline"

CONTEXT = "context"
NOW = "now"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)

    kind = Column(String, nullable=False, index=True)
    priority = Column(String, nullable=False, server_default=CONTEXT)

    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    link = Column(String, nullable=True)

    dedupe_key = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(),
                        index=True)
    occurred_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    dismissed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key", name="uq_notification_user_key"),
        Index("ix_notifications_user_unread", "user_id", "read_at"),
    )


class TopicReading(Base):
    __tablename__ = "topic_readings"

    id = Column(Integer, primary_key=True, index=True)
    topic = Column(String, nullable=False, unique=True, index=True)

    stage = Column(String, nullable=True)
    research_total = Column(Integer, nullable=True)
    research_growth = Column(Float, nullable=True)
    patent_total = Column(Integer, nullable=True)
    patent_growth = Column(Float, nullable=True)
    patent_history_reliable = Column(Boolean, nullable=False,
                                     server_default="false")

    captured_at = Column(DateTime(timezone=True), server_default=func.now(),
                         onupdate=func.now())
