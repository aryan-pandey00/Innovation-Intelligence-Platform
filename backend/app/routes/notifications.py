"""Module 10 — the notification and alert surface."""
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role
from app.models.user import User, UserRole
from app.schemas.notification import (
    BroadcastCreate, NotificationFeed, NotificationResponse,
)
from app.services import notifications

router = APIRouter(prefix="/api/notifications", tags=["Notifications & Alerts"])


@router.get("", response_model=NotificationFeed)
def feed(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    generated = notifications.generate_for(db, current_user)
    return NotificationFeed(
        unread=notifications.unread_count(db, current_user.id),
        generated=generated,
        items=notifications.list_for(db, current_user.id,
                                     unread_only=unread_only, limit=limit),
    )


@router.get("/unread-count")
def unread(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Just the badge."""
    notifications.generate_for(db, current_user)
    return {"unread": notifications.unread_count(db, current_user.id)}


@router.get("/announcements")
def announcements(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """What has already been broadcast."""
    return {"announcements": notifications.sent_announcements(db, limit=limit)}


"""Editing and withdrawing what has been said.

Both are keyed on the `dedupe_key` that every copy of one announcement shares, which
is what makes the announcement — rather than one person's row — the thing being
operated on. Both are declared *above* `/{notification_id}`: that path converts to an
int, so a route registered after it would never be reached, "announcements" would fail
the conversion, and the caller would get a 422 about an integer they never sent.
"""


@router.patch("/announcements/{key}")
def edit_announcement(
    key: str,
    data: BroadcastCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Correct a sent announcement in every feed it reached."""
    changed = notifications.update_announcement(
        db, key, title=data.title, body=data.body, link=data.link)
    if changed == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"updated": changed, "key": key}


@router.delete("/announcements/{key}")
def withdraw_announcement(
    key: str,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Remove a sent announcement from every feed it reached."""
    removed = notifications.delete_announcement(db, key)
    if removed == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return {"removed": removed, "key": key}


@router.put("/{notification_id}/read", response_model=NotificationResponse)
def mark_read(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = notifications.mark_read(db, current_user.id, notification_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    return row


@router.post("/read-all")
def mark_all_read(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return {"marked": notifications.mark_all_read(db, current_user.id)}


@router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss(
    notification_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not notifications.dismiss(db, current_user.id, notification_id):
        raise HTTPException(status_code=404, detail="Notification not found")


@router.post("/broadcast")
def broadcast(
    data: BroadcastCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """A platform notification, from an administrator to everyone or to roles."""
    digest = hashlib.sha1(f"{data.title}\n{data.body}".encode()).hexdigest()[:12]
    key = f"{admin.id}:{digest}"
    sent = notifications.broadcast(
        db, data.title, data.body,
        roles=data.roles or None, link=data.link, key=key)
    return {"sent": sent, "key": key}
