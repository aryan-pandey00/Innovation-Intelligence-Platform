"""Module 10 — alerts, generated from what the platform already knows."""
from __future__ import annotations

import datetime as dt

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, selectinload

from app.models.funding import FundingOpportunity
from app.core.dependencies import count_super_admins
from app.models.notification import (
    COMMERCIALIZATION, CONTEXT, FUNDING_DEADLINE, FUNDING_NEW, NOW,
    PATENT_ACTIVITY, PIPELINE, PLATFORM, PLATFORM_HEALTH, RESEARCH_TREND,
    TECHNOLOGY_EMERGING, Notification, TopicReading,
)
from app.models.research_profile import ResearchProfile
from app.models.user import User, UserRole
from app.services import funding_reco, platform_analytics, profile_utils

OWNER_ROLES = (UserRole.RESEARCHER, UserRole.STARTUP_FOUNDER)

_MATCH_FLOOR = platform_analytics.STRONG_MATCH
_NEW_GRANT_DAYS = 14
_DEADLINE_DAYS = 30

_PATENT_MOVE = 0.05
_RESEARCH_MOVE = 10.0

_MAX_PER_USER = 200


def _today() -> dt.date:
    return dt.date.today()


def normalise_topic(topic: str) -> str:
    return " ".join((topic or "").strip().lower().split())


def emit(db: Session, user_id: int, kind: str, title: str, body: str, *,
         dedupe_key: str, link: str | None = None,
         priority: str = CONTEXT, occurred_at: dt.datetime | None = None) -> bool:
    """Insert one notification unless this user already has that exact key."""
    stmt = (pg_insert(Notification.__table__)
            .values(user_id=user_id, kind=kind, priority=priority, title=title,
                    body=body, link=link, dedupe_key=dedupe_key,
                    occurred_at=occurred_at)
            .on_conflict_do_nothing(constraint="uq_notification_user_key")
            .returning(Notification.__table__.c.id))
    return db.execute(stmt).first() is not None


def broadcast(db: Session, title: str, body: str, *,
              roles: list[UserRole] | None = None,
              link: str | None = None, key: str) -> int:
    """An administrator's message to everyone, or to chosen roles."""
    q = db.query(User.id)
    if roles:
        q = q.filter(User.role.in_(roles))
    sent = 0
    for (user_id,) in q.all():
        if emit(db, user_id, PLATFORM, title, body,
                dedupe_key=f"{PLATFORM}:{key}", link=link, priority=CONTEXT):
            sent += 1
    db.commit()
    return sent


def _live(q):
    """Everything except the tombstones a dismissal leaves behind."""
    return q.filter(Notification.dismissed_at.is_(None))


def _room(db: Session, user_id: int) -> bool:
    """Whether this account is below the per-user ceiling."""
    return _live(db.query(Notification)
                   .filter(Notification.user_id == user_id)).count() < _MAX_PER_USER


def _funding_alerts(db: Session, user: User, profile: ResearchProfile,
                    opportunities: list[FundingOpportunity]) -> None:
    """New and closing grants, scored exactly as the funding page scores them."""
    ranked = funding_reco.rank_opportunities(
        profile=profile,
        publications=list(profile.publications),
        user_role=user.role.value,
        user_country=profile.country,
        opportunities=opportunities,
    )
    today = _today()
    fresh_from = today - dt.timedelta(days=_NEW_GRANT_DAYS)
    closing_by = today + dt.timedelta(days=_DEADLINE_DAYS)

    for row in ranked:
        if row["relevance_score"] < _MATCH_FLOOR:
            continue
        if row["eligibility"] == funding_reco.INELIGIBLE:
            continue
        opp = row["opportunity"]
        score = round(row["relevance_score"])

        added = opp.created_at.date() if opp.created_at else None
        if added and added >= fresh_from:
            emit(db, user.id, FUNDING_NEW,
                 f"New grant matching your profile: {opp.title}",
                 f"{opp.agency} · {score}% match.",
                 dedupe_key=f"{FUNDING_NEW}:{opp.id}",
                 link="/funding", priority=CONTEXT,
                 occurred_at=opp.created_at)

        if opp.deadline and today <= opp.deadline <= closing_by:
            days = (opp.deadline - today).days
            emit(db, user.id, FUNDING_DEADLINE,
                 f"Closing in {days} day{'' if days == 1 else 's'}: {opp.title}",
                 f"{opp.agency} · {score}% match. Deadline "
                 f"{opp.deadline.strftime('%d %b %Y')}.",
                 dedupe_key=f"{FUNDING_DEADLINE}:{opp.id}:{opp.deadline.isoformat()}",
                 link="/funding", priority=NOW)


def _commercialization_alerts(db: Session, user: User,
                             profile: ResearchProfile) -> None:
    """The one commercialisation risk that needs no external call."""
    pubs = list(profile.publications)
    if not pubs or list(profile.patents):
        return
    fields, _ = profile_utils.technology_terms(profile)
    field = fields[0] if fields else None
    emit(db, user.id, COMMERCIALIZATION,
         "You publish, but hold no patents",
         (f"Your portfolio has {len(pubs)} publication"
          f"{'' if len(pubs) == 1 else 's'} and no filings"
          + (f" in {field}" if field else "")
          + ". Publishing before filing can count as prior art against your own "
            "application."),
         dedupe_key=f"{COMMERCIALIZATION}:prior-art:{len(pubs)}",
         link="/commercialization", priority=NOW)


def _names(people: list[User], limit: int = 5) -> str:
    """A readable list of who an alert is about, ending as a sentence does."""
    shown = ", ".join(p.full_name or p.email for p in people[:limit])
    return f"{shown} and {len(people) - limit} more." if len(people) > limit else f"{shown}."


def _manager_alerts(db: Session, user: User) -> None:
    """Pipeline triage: who cannot be helped yet."""
    owners = db.query(User).filter(User.role.in_(OWNER_ROLES)).all()
    profiles = {p.user_id: p for p in db.query(ResearchProfile).all()}

    no_portfolio = [o for o in owners if o.id not in profiles]
    if no_portfolio:
        emit(db, user.id, PIPELINE,
             f"{len(no_portfolio)} innovator"
             f"{'' if len(no_portfolio) == 1 else 's'} have no portfolio",
             "Nothing can be matched or assessed for them until a portfolio "
             "exists: " + _names(no_portfolio),
             dedupe_key=f"pipeline:no-portfolio:{len(no_portfolio)}",
             link="/dashboard", priority=NOW)

    no_focus = [o for o in owners if o.id in profiles
                and not profile_utils.technology_terms(profiles[o.id])[0]]
    if no_focus:
        emit(db, user.id, PIPELINE,
             f"{len(no_focus)} portfolio"
             f"{'' if len(no_focus) == 1 else 's'} name no technology area",
             "A technology area is what the patent and maturity analysis is run "
             "against, so these accounts cannot be assessed: " + _names(no_focus),
             dedupe_key=f"pipeline:no-focus:{len(no_focus)}",
             link="/dashboard", priority=CONTEXT)


def _admin_alerts(db: Session, user: User) -> None:
    """Platform problems an administrator can act on, in three cheap queries."""
    if count_super_admins(db) == 1:
        sole = (db.query(User).filter(User.is_superuser.is_(True)).first())
        if sole is not None:
            emit(db, user.id, PLATFORM_HEALTH,
                 "Only one account can manage administrators",
                 f"{sole.full_name or sole.email} is the only super-admin, and that "
                 f"account cannot be deleted or stepped down while it stays the only "
                 f"one. Grant super-admin to a second administrator so the platform "
                 f"survives losing it.",
                 dedupe_key=f"admin:single-super:{sole.id}",
                 link="/admin", priority=NOW)

    today = _today()

    untagged = (db.query(FundingOpportunity.id, FundingOpportunity.title)
                  .filter(func.jsonb_array_length(FundingOpportunity.domains) == 0,
                          func.jsonb_array_length(FundingOpportunity.keywords) == 0)
                  .all())
    if untagged:
        names = ", ".join(t for _, t in untagged[:3])
        emit(db, user.id, PLATFORM_HEALTH,
             f"{len(untagged)} grant{'' if len(untagged) == 1 else 's'} can never "
             f"reach anyone",
             f"With no domains and no keywords, matching falls back to description "
             f"text alone, which caps the score at {_MATCH_FLOOR}% — the exact floor a "
             f"match has to clear. {names}"
             f"{'…' if len(untagged) > 3 else ''}.",
             dedupe_key=f"admin:untagged-grants:{len(untagged)}",
             link="/admin/funding", priority=NOW)

    closed = (db.query(FundingOpportunity.id)
                .filter(FundingOpportunity.deadline.isnot(None),
                        FundingOpportunity.deadline < today)
                .count())
    if closed:
        emit(db, user.id, PLATFORM_HEALTH,
             f"{closed} grant{'' if closed == 1 else 's'} past their deadline",
             "A closed grant is ineligible for everyone, so it takes up room in the "
             "catalogue without ever being an opportunity. Update the deadline or "
             "remove it.",
             dedupe_key=f"admin:closed-grants:{closed}",
             link="/admin/funding", priority=CONTEXT)


def generate_for(db: Session, user: User) -> int:
    """Bring this user's notifications up to date."""
    if not _room(db, user.id):
        return 0

    before = db.query(Notification).filter(Notification.user_id == user.id).count()
    try:
        if user.role in OWNER_ROLES:
            profile = (db.query(ResearchProfile)
                         .options(selectinload(ResearchProfile.publications),
                                  selectinload(ResearchProfile.patents))
                         .filter(ResearchProfile.user_id == user.id).first())
            if profile is not None:
                opportunities = db.query(FundingOpportunity).all()
                _funding_alerts(db, user, profile, opportunities)
                _commercialization_alerts(db, user, profile)
        elif user.role == UserRole.INNOVATION_MANAGER:
            _manager_alerts(db, user)
        elif user.role == UserRole.ADMIN:
            _admin_alerts(db, user)
        db.commit()
    except Exception:
        db.rollback()
        return 0
    after = db.query(Notification).filter(Notification.user_id == user.id).count()
    return after - before


def _affected_owners(db: Session, topic: str) -> list[User]:
    """Owners whose portfolio names this topic."""
    wanted = normalise_topic(topic)
    if not wanted:
        return []
    out = []
    rows = (db.query(User, ResearchProfile)
              .join(ResearchProfile, ResearchProfile.user_id == User.id)
              .filter(User.role.in_(OWNER_ROLES)).all())
    for user, profile in rows:
        terms = ((profile.technology_areas or []) + (profile.research_domains or [])
                 + (profile.keywords or []))
        if any(normalise_topic(t) == wanted for t in terms):
            out.append(user)
    return out


def record_reading(db: Session, topic: str, signals: dict) -> int:
    """Store what a technology reads as now, and alert on what moved."""
    key = normalise_topic(topic)
    if not key:
        return 0
    try:
        stage = signals.get("stage")
        research_total = signals.get("research_total")
        research_growth = signals.get("research_growth")
        patent_total = signals.get("patent_total")
        patent_growth = signals.get("patent_growth")
        reliable = bool(signals.get("patent_history_reliable"))

        prior = db.query(TopicReading).filter(TopicReading.topic == key).first()
        created = 0

        if prior is not None:
            created += _topic_alerts(db, key, prior, stage, research_growth,
                                     patent_total, reliable)

        if prior is None:
            prior = TopicReading(topic=key)
            db.add(prior)
        prior.stage = stage
        prior.research_total = research_total
        prior.research_growth = research_growth
        prior.patent_total = patent_total
        prior.patent_growth = patent_growth
        if reliable or prior.patent_history_reliable is None:
            prior.patent_history_reliable = reliable
        db.commit()
        return created
    except Exception:
        db.rollback()
        return 0


def _topic_alerts(db: Session, key: str, prior: TopicReading, stage,
                  research_growth, patent_total, reliable: bool) -> int:
    created = 0
    recipients = _affected_owners(db, key)
    if not recipients:
        return 0
    label = key.title()

    if stage and prior.stage and stage != prior.stage:
        for user in recipients:
            if emit(db, user.id, TECHNOLOGY_EMERGING,
                    f"{label} is now {stage}",
                    f"It read as {prior.stage} when this field was last measured. "
                    f"The recommended route to market follows the stage, so it may "
                    f"have changed too.",
                    dedupe_key=f"{TECHNOLOGY_EMERGING}:{key}:{prior.stage}->{stage}",
                    link="/technology", priority=NOW):
                created += 1

    if (reliable and prior.patent_history_reliable and patent_total
            and prior.patent_total):
        change = (patent_total - prior.patent_total) / prior.patent_total
        if abs(change) >= _PATENT_MOVE:
            direction = "grown" if change > 0 else "shrunk"
            for user in recipients:
                if emit(db, user.id, PATENT_ACTIVITY,
                        f"Patent activity in {label} has {direction}",
                        f"{prior.patent_total:,} filings when last measured, "
                        f"{patent_total:,} now — {abs(change) * 100:.0f}% "
                        f"{direction}.",
                        dedupe_key=(f"{PATENT_ACTIVITY}:{key}:"
                                    f"{prior.patent_total}->{patent_total}"),
                        link="/patents", priority=CONTEXT):
                    created += 1

    if research_growth is not None and prior.research_growth is not None:
        move = research_growth - prior.research_growth
        if abs(move) >= _RESEARCH_MOVE:
            direction = "accelerating" if move > 0 else "slowing"
            for user in recipients:
                if emit(db, user.id, RESEARCH_TREND,
                        f"Research in {label} is {direction}",
                        f"Publication growth moved from "
                        f"{prior.research_growth:+.0f}% to "
                        f"{research_growth:+.0f}% since this field was last read.",
                        dedupe_key=(f"{RESEARCH_TREND}:{key}:"
                                    f"{prior.research_growth:.0f}->"
                                    f"{research_growth:.0f}"),
                        link="/trends", priority=CONTEXT):
                    created += 1
    return created


def list_for(db: Session, user_id: int, *, unread_only: bool = False,
             limit: int = 50) -> list[Notification]:
    q = _live(db.query(Notification).filter(Notification.user_id == user_id))
    if unread_only:
        q = q.filter(Notification.read_at.is_(None))
    return (q.order_by(Notification.read_at.isnot(None),
                       func.coalesce(Notification.occurred_at,
                                     Notification.created_at).desc())
             .limit(limit).all())


def sent_announcements(db: Session, limit: int = 20) -> list[dict]:
    """What has been broadcast, grouped by the key every copy of it shares."""
    rows = (db.query(Notification.dedupe_key.label("key"),
                     func.min(Notification.title).label("title"),
                     func.min(Notification.body).label("body"),
                     func.min(Notification.link).label("link"),
                     func.min(Notification.created_at).label("sent_at"),
                     func.count().label("delivered"),
                     func.count(Notification.read_at).label("read"),
                     func.count(Notification.dismissed_at).label("dismissed"))
             .filter(Notification.kind == PLATFORM)
             .group_by(Notification.dedupe_key)
             .order_by(func.min(Notification.created_at).desc())
             .limit(limit).all())
    return [{"key": r.key, "title": r.title, "body": r.body, "link": r.link,
             "sent_at": r.sent_at.isoformat() if r.sent_at else None,
             "delivered": r.delivered, "read": r.read, "dismissed": r.dismissed}
            for r in rows]


def update_announcement(db: Session, key: str, *, title: str, body: str,
                        link: str | None) -> int:
    """Correct an announcement everywhere it landed."""
    n = (db.query(Notification)
           .filter(Notification.kind == PLATFORM,
                   Notification.dedupe_key == key)
           .update({Notification.title: title, Notification.body: body,
                    Notification.link: link}, synchronize_session=False))
    db.commit()
    return n


def delete_announcement(db: Session, key: str) -> int:
    """Withdraw an announcement from every feed it reached."""
    n = (db.query(Notification)
           .filter(Notification.kind == PLATFORM,
                   Notification.dedupe_key == key)
           .delete(synchronize_session=False))
    db.commit()
    return n


def unread_count(db: Session, user_id: int) -> int:
    return _live(db.query(Notification)
                   .filter(Notification.user_id == user_id,
                           Notification.read_at.is_(None))).count()


def mark_read(db: Session, user_id: int, notification_id: int) -> Notification | None:
    row = _live(db.query(Notification)
                  .filter(Notification.id == notification_id,
                          Notification.user_id == user_id)).first()
    if row is None:
        return None
    if row.read_at is None:
        row.read_at = dt.datetime.now(dt.timezone.utc)
        db.commit()
        db.refresh(row)
    return row


def mark_all_read(db: Session, user_id: int) -> int:
    now = dt.datetime.now(dt.timezone.utc)
    n = (db.query(Notification)
           .filter(Notification.user_id == user_id,
                   Notification.read_at.is_(None))
           .update({Notification.read_at: now}, synchronize_session=False))
    db.commit()
    return n


def dismiss(db: Session, user_id: int, notification_id: int) -> bool:
    """Close an alert for good."""
    row = _live(db.query(Notification)
                  .filter(Notification.id == notification_id,
                          Notification.user_id == user_id)).first()
    if row is None:
        return False
    row.dismissed_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    return True
