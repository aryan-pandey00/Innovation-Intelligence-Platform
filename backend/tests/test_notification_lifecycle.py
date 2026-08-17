"""What happens to a notification *after* it is delivered."""
import datetime as dt

from app.models.notification import CONTEXT, FUNDING_NEW, Notification, PLATFORM
from app.models.user import UserRole
from app.routes.notifications import router as notifications_router
from app.services import notifications
from tests.conftest import auth_header, make_opportunity, make_profile, make_user


def _owner_with_matching_grant(db):
    user = make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_profile(db, user, domains=["energy"], keywords=["battery", "storage"],
                 technology_areas=["energy storage"])
    make_opportunity(
        db, title="Battery Storage Award", domains=["energy"],
        keywords=["battery", "storage"],
        created_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=1),
    )
    return user


def test_a_dismissed_alert_does_not_come_back(db):
    """The regression, stated as the thing a reader would actually experience."""
    user = _owner_with_matching_grant(db)
    notifications.generate_for(db, user)
    live = notifications.list_for(db, user.id)
    assert live, "nothing to dismiss — this test would otherwise pass vacuously"
    target, key = live[0], live[0].dedupe_key

    assert notifications.dismiss(db, user.id, target.id) is True

    for _ in range(3):
        notifications.generate_for(db, user)

    assert key not in {n.dedupe_key for n in notifications.list_for(db, user.id)}, \
        "it came back"
    assert db.query(Notification).filter_by(id=target.id).count() == 1, \
        "the surviving row is what keeps it away — delete it and the alert re-arms"


def test_a_dismissed_alert_is_not_counted_by_the_badge(db):
    user = _owner_with_matching_grant(db)
    notifications.generate_for(db, user)
    before = notifications.unread_count(db, user.id)
    assert before >= 1
    notifications.dismiss(db, user.id, notifications.list_for(db, user.id)[0].id)
    notifications.generate_for(db, user)
    assert notifications.unread_count(db, user.id) == before - 1, \
        "a badge counting rows the feed will not show can never be cleared"


def test_a_dismissed_alert_is_gone_from_its_owner_too(client, db):
    """The surviving row is ours."""
    _owner_with_matching_grant(db)
    headers = auth_header(client, "owner@example.org")
    first = client.get("/api/notifications", headers=headers).json()["items"][0]["id"]

    assert client.delete(f"/api/notifications/{first}",
                         headers=headers).status_code == 204
    assert client.delete(f"/api/notifications/{first}",
                         headers=headers).status_code == 404
    assert client.put(f"/api/notifications/{first}/read",
                      headers=headers).status_code == 404


def test_dismissing_does_not_starve_an_account_of_new_alerts(db):
    """The ceiling counts what is in the feed, not what has ever been in it."""
    user = make_user(db, "owner@example.org")
    for i in range(notifications._MAX_PER_USER):
        notifications.emit(db, user.id, FUNDING_NEW, "A thing happened", "Detail.",
                           dedupe_key=f"grant:{i}", priority=CONTEXT)
    db.commit()
    assert notifications._room(db, user.id) is False

    for row in notifications.list_for(db, user.id,
                                      limit=notifications._MAX_PER_USER):
        notifications.dismiss(db, user.id, row.id)
    assert notifications._room(db, user.id) is True


def _announce(client, header, title="Scheduled maintenance",
              body="Sunday, 02:00 to 04:00."):
    res = client.post("/api/notifications/broadcast", headers=header,
                      json={"title": title, "body": body}).json()
    history = client.get("/api/notifications/announcements",
                         headers=header).json()["announcements"]
    return res, next(h for h in history if h["title"] == title)


def test_an_announcement_is_corrected_in_every_feed_it_reached(client, db):
    make_user(db, "a@example.org", UserRole.RESEARCHER)
    make_user(db, "b@example.org", UserRole.RESEARCHER)
    admin = make_user(db, "admin@example.org", UserRole.ADMIN)
    header = auth_header(client, "admin@example.org")
    sent, ann = _announce(client, header)
    assert sent["sent"] == 3

    mine = notifications.list_for(db, admin.id)[0]
    client.put(f"/api/notifications/{mine.id}/read", headers=header)

    res = client.patch(f"/api/notifications/announcements/{ann['key']}",
                       headers=header,
                       json={"title": "Scheduled maintenance",
                             "body": "Sunday, 02:00 to 05:00.", "link": "/funding"})
    assert res.status_code == 200 and res.json()["updated"] == 3

    rows = db.query(Notification).filter_by(dedupe_key=ann["key"]).all()
    assert {r.body for r in rows} == {"Sunday, 02:00 to 05:00."}
    assert {r.link for r in rows} == {"/funding"}
    assert sum(r.read_at is not None for r in rows) == 1, "an edit is not a re-alert"


def test_an_edit_keeps_the_key_so_the_old_wording_cannot_return(client, db):
    """The key is the announcement's identity once it has been sent."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    header = auth_header(client, "admin@example.org")
    _, ann = _announce(client, header)
    client.patch(f"/api/notifications/announcements/{ann['key']}", headers=header,
                 json={"title": "Scheduled maintenance",
                       "body": "Now 02:00 to 05:00."})

    again = client.post("/api/notifications/broadcast", headers=header, json={
        "title": "Scheduled maintenance", "body": "Sunday, 02:00 to 04:00."}).json()
    assert again["sent"] == 0, "the original text is still the same announcement"
    assert db.query(Notification).filter_by(kind=PLATFORM).count() == 1


def test_withdrawing_clears_every_feed_and_frees_the_key(client, db):
    """A real delete, unlike a dismissal, and the difference is the whole point."""
    make_user(db, "a@example.org", UserRole.RESEARCHER)
    make_user(db, "admin@example.org", UserRole.ADMIN)
    header = auth_header(client, "admin@example.org")
    _, ann = _announce(client, header)

    res = client.delete(f"/api/notifications/announcements/{ann['key']}",
                        headers=header)
    assert res.status_code == 200 and res.json()["removed"] == 2
    assert db.query(Notification).filter_by(kind=PLATFORM).count() == 0
    assert client.get("/api/notifications/announcements",
                      headers=header).json()["announcements"] == []

    resent = client.post("/api/notifications/broadcast", headers=header, json={
        "title": "Scheduled maintenance", "body": "Sunday, 02:00 to 04:00."}).json()
    assert resent["sent"] == 2, "withdrawn has to mean re-sendable"


def test_an_unknown_announcement_key_is_a_404_not_a_silent_success(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    header = auth_header(client, "admin@example.org")
    assert client.delete("/api/notifications/announcements/platform:nope",
                         headers=header).status_code == 404
    assert client.patch("/api/notifications/announcements/platform:nope",
                        headers=header,
                        json={"title": "Anything", "body": "At all."}
                        ).status_code == 404


def test_only_an_administrator_may_edit_or_withdraw_an_announcement(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_user(db, "manager@example.org", UserRole.INNOVATION_MANAGER)
    _, ann = _announce(client, auth_header(client, "admin@example.org"))

    for email in ("owner@example.org", "manager@example.org"):
        header = auth_header(client, email)
        assert client.patch(f"/api/notifications/announcements/{ann['key']}",
                            headers=header,
                            json={"title": "Hijacked", "body": "By anyone."}
                            ).status_code == 403
        assert client.delete(f"/api/notifications/announcements/{ann['key']}",
                             headers=header).status_code == 403


def test_the_announcement_routes_are_not_shadowed_by_the_id_route():
    """Declaration order is load-bearing here, so it is asserted rather than assumed."""
    order = [r.path for r in notifications_router.routes]
    assert (order.index("/api/notifications/announcements/{key}")
            < order.index("/api/notifications/{notification_id}"))
