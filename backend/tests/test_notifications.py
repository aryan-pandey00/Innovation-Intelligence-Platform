"""Alerts: de-duplication, the match floor, and honest change detection."""
import datetime as dt
import subprocess
import sys

from app.models.notification import (
    CONTEXT, FUNDING_DEADLINE, FUNDING_NEW, NOW, PLATFORM_HEALTH, Notification,
    TopicReading,
)
from app.models.user import UserRole
from app.services import notifications, platform_analytics
from tests.conftest import auth_header, make_opportunity, make_profile, make_user


def _emit(db, user, key, title="A thing happened"):
    return notifications.emit(db, user.id, FUNDING_NEW, title, "Some detail.",
                              dedupe_key=key, priority=CONTEXT)


def test_the_same_alert_is_only_delivered_once(db):
    user = make_user(db, "owner@example.org")
    assert _emit(db, user, "grant:1") is True
    assert _emit(db, user, "grant:1") is False
    db.commit()
    assert db.query(Notification).count() == 1


def test_a_duplicate_does_not_poison_the_session(db):
    """The regression."""
    user = make_user(db, "owner@example.org")
    assert _emit(db, user, "grant:1") is True
    assert _emit(db, user, "grant:1") is False
    assert _emit(db, user, "grant:2") is True, (
        "the alert after a duplicate was lost — the session was left needing a "
        "rollback, which is how a whole generation pass used to disappear"
    )
    assert _emit(db, user, "grant:3") is True
    db.commit()
    assert db.query(Notification).count() == 3


def test_deduplication_is_per_user_not_global(db):
    """The key identifies the *thing*; two people are both entitled to hear it."""
    first = make_user(db, "one@example.org")
    second = make_user(db, "two@example.org")
    assert _emit(db, first, "grant:1") is True
    assert _emit(db, second, "grant:1") is True
    db.commit()
    assert db.query(Notification).count() == 2


def test_deleting_a_user_takes_their_alerts_with_them(db):
    """The opposite of the audit table."""
    user = make_user(db, "leaving@example.org")
    _emit(db, user, "grant:1")
    db.commit()
    db.delete(user)
    db.commit()
    assert db.query(Notification).count() == 0


def _owner_with_matching_grant(db, *, deadline=None, added_days_ago=1):
    user = make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_profile(db, user, domains=["energy"], keywords=["battery", "storage"],
                 technology_areas=["energy storage"])
    opp = make_opportunity(
        db, title="Battery Storage Award", domains=["energy"],
        keywords=["battery", "storage"], deadline=deadline,
        created_at=dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=added_days_ago),
    )
    return user, opp


def test_a_new_matching_grant_produces_an_alert(db):
    user, opp = _owner_with_matching_grant(db)
    assert notifications.generate_for(db, user) >= 1
    kinds = {n.kind for n in db.query(Notification).all()}
    assert FUNDING_NEW in kinds


def test_generation_is_idempotent(db):
    """It runs on every read of the feed, so calling it twice has to be free."""
    user, _ = _owner_with_matching_grant(db)
    first = notifications.generate_for(db, user)
    assert first >= 1
    assert notifications.generate_for(db, user) == 0


def test_a_weak_match_is_not_announced(db):
    """A 27% match was once announced in the same words as an 85% one."""
    assert notifications._MATCH_FLOOR == platform_analytics.STRONG_MATCH

    user = make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_profile(db, user, domains=["marine biology"], keywords=["coral"])
    make_opportunity(db, title="Astronomy Fund", domains=["astronomy"],
                     keywords=["telescope", "spectroscopy"],
                     created_at=dt.datetime.now(dt.timezone.utc))

    notifications.generate_for(db, user)
    assert db.query(Notification).filter(Notification.kind == FUNDING_NEW).count() == 0


def test_an_ineligible_grant_is_not_an_opportunity(db):
    user = make_user(db, "founder@example.org", UserRole.STARTUP_FOUNDER)
    make_profile(db, user, domains=["energy"], keywords=["battery", "storage"])
    make_opportunity(db, title="Academics Only Award", domains=["energy"],
                     keywords=["battery", "storage"], eligible_roles=["researcher"],
                     created_at=dt.datetime.now(dt.timezone.utc))
    notifications.generate_for(db, user)
    assert db.query(Notification).filter(Notification.kind == FUNDING_NEW).count() == 0


def test_an_alert_is_dated_when_the_thing_happened(db):
    """Read-time generation would otherwise stamp every alert with when you looked."""
    user, opp = _owner_with_matching_grant(db, added_days_ago=9)
    notifications.generate_for(db, user)
    row = db.query(Notification).filter(Notification.kind == FUNDING_NEW).one()
    assert row.occurred_at is not None
    assert row.occurred_at.date() == opp.created_at.date()
    assert row.occurred_at.date() != dt.date.today()
    assert "Added" not in row.body


def test_a_closing_deadline_is_flagged_as_needing_attention(db):
    user, _ = _owner_with_matching_grant(
        db, deadline=dt.date.today() + dt.timedelta(days=5))
    notifications.generate_for(db, user)
    row = db.query(Notification).filter(
        Notification.kind == FUNDING_DEADLINE).one()
    assert row.priority == "now"
    assert "Closing in 5 days" in row.title


def test_the_feed_reads_by_when_things_happened(db):
    """Ordering is on `COALESCE(occurred_at."""
    user = make_user(db, "owner@example.org")
    now = dt.datetime.now(dt.timezone.utc)
    notifications.emit(db, user.id, FUNDING_NEW, "Older", "b", dedupe_key="a",
                       occurred_at=now - dt.timedelta(days=7))
    notifications.emit(db, user.id, FUNDING_NEW, "Newer", "b", dedupe_key="b",
                       occurred_at=now - dt.timedelta(hours=1))
    db.commit()
    titles = [n.title for n in notifications.list_for(db, user.id)]
    assert titles == ["Newer", "Older"]


def test_the_feed_read_and_dismiss_cycle(client, db):
    user, _ = _owner_with_matching_grant(db)
    headers = auth_header(client, "owner@example.org")

    feed = client.get("/api/notifications", headers=headers).json()
    assert feed["generated"] >= 1
    assert feed["unread"] == len(feed["items"])
    first = feed["items"][0]["id"]

    assert client.put(f"/api/notifications/{first}/read",
                      headers=headers).status_code == 200
    assert client.get("/api/notifications/unread-count",
                      headers=headers).json()["unread"] == feed["unread"] - 1

    marked = client.post("/api/notifications/read-all", headers=headers).json()
    assert marked["marked"] == feed["unread"] - 1
    assert client.get("/api/notifications/unread-count",
                      headers=headers).json()["unread"] == 0

    assert client.delete(f"/api/notifications/{first}",
                         headers=headers).status_code == 204
    assert client.delete(f"/api/notifications/{first}",
                         headers=headers).status_code == 404


def test_one_user_cannot_read_or_dismiss_another_user_alerts(client, db):
    owner, _ = _owner_with_matching_grant(db)
    notifications.generate_for(db, owner)
    theirs = db.query(Notification).first().id

    make_user(db, "stranger@example.org", UserRole.RESEARCHER)
    headers = auth_header(client, "stranger@example.org")
    assert client.put(f"/api/notifications/{theirs}/read",
                      headers=headers).status_code == 404
    assert client.delete(f"/api/notifications/{theirs}",
                         headers=headers).status_code == 404


def _admin_with_problems(db):
    """A platform with all three structural faults present at once."""
    admin = make_user(db, "sole@example.org", UserRole.ADMIN)
    admin.is_superuser = True
    db.commit()
    make_opportunity(db, title="Untagged Fund", domains=[], keywords=[])
    make_opportunity(db, title="Expired Fund", domains=["energy"],
                     keywords=["battery"],
                     deadline=dt.date.today() - dt.timedelta(days=3))
    return admin


def test_an_administrator_gets_the_three_structural_alerts(db):
    admin = _admin_with_problems(db)
    assert notifications.generate_for(db, admin) == 3

    rows = db.query(Notification).filter(
        Notification.user_id == admin.id,
        Notification.kind == PLATFORM_HEALTH).all()
    keys = {r.dedupe_key.split(":")[1] for r in rows}
    assert keys == {"single-super", "untagged-grants", "closed-grants"}
    backup = next(r for r in rows if "single-super" in r.dedupe_key)
    assert backup.priority == NOW


def test_the_admin_feed_says_nothing_new_on_a_second_pass(db):
    admin = _admin_with_problems(db)
    assert notifications.generate_for(db, admin) == 3
    assert notifications.generate_for(db, admin) == 0


def test_a_second_super_admin_settles_the_backup_alert(db):
    admin = _admin_with_problems(db)
    notifications.generate_for(db, admin)
    before = db.query(Notification).filter(Notification.user_id == admin.id).count()

    second = make_user(db, "backup@example.org", UserRole.ADMIN)
    second.is_superuser = True
    db.commit()
    notifications.generate_for(db, admin)
    assert db.query(Notification).filter(
        Notification.user_id == admin.id).count() == before, (
        "the condition is false now, so nothing should be added")

    make_opportunity(db, title="Another Expired Fund", domains=["energy"],
                     keywords=["battery"],
                     deadline=dt.date.today() - dt.timedelta(days=1))
    assert notifications.generate_for(db, admin) == 1


def test_generating_an_admin_feed_stays_cheap_enough_for_every_navigation(db):
    """This runs on `/notifications` *and* on `/notifications/unread-count`."""
    import time
    admin = _admin_with_problems(db)
    notifications.generate_for(db, admin)
    start = time.perf_counter()
    notifications.generate_for(db, admin)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < 400, f"{elapsed_ms:.0f} ms on every navigation"


def test_the_announcement_history_groups_by_announcement_not_recipient(client, db):
    """`broadcast` writes one row per account and gives them all one key."""
    make_user(db, "a@example.org", UserRole.RESEARCHER)
    make_user(db, "b@example.org", UserRole.RESEARCHER)
    admin = make_user(db, "admin@example.org", UserRole.ADMIN)

    header = auth_header(client, "admin@example.org")
    sent = client.post("/api/notifications/broadcast", headers=header, json={
        "title": "Scheduled maintenance", "body": "Sunday, 02:00 to 04:00."}).json()
    assert sent["sent"] == 3

    history = client.get("/api/notifications/announcements",
                         headers=header).json()["announcements"]
    assert len(history) == 1, "three recipients are one announcement"
    assert history[0]["title"] == "Scheduled maintenance"
    assert history[0]["delivered"] == 3
    assert (history[0]["read"], history[0]["dismissed"]) == (0, 0)

    mine = notifications.list_for(db, admin.id)[0]
    client.put(f"/api/notifications/{mine.id}/read", headers=header)
    after = client.get("/api/notifications/announcements",
                       headers=header).json()["announcements"][0]
    assert (after["delivered"], after["read"]) == (3, 1)

    client.delete(f"/api/notifications/{mine.id}", headers=header)
    tidied = client.get("/api/notifications/announcements",
                        headers=header).json()["announcements"][0]
    assert (tidied["delivered"], tidied["read"], tidied["dismissed"]) == (3, 1, 1)


def test_only_an_administrator_may_read_the_announcement_history(client, db):
    make_user(db, "owner@example.org", UserRole.RESEARCHER)
    assert client.get("/api/notifications/announcements",
                      headers=auth_header(client, "owner@example.org")
                      ).status_code == 403


def test_a_broadcast_reaches_everyone_once(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "a@example.org", UserRole.RESEARCHER)
    make_user(db, "b@example.org", UserRole.STARTUP_FOUNDER)
    headers = auth_header(client, "admin@example.org")
    message = {"title": "Scheduled maintenance", "body": "Sunday, 02:00 UTC."}

    first = client.post("/api/notifications/broadcast", json=message, headers=headers)
    assert first.status_code == 200
    assert first.json()["sent"] == 3

    again = client.post("/api/notifications/broadcast", json=message, headers=headers)
    assert again.json()["sent"] == 0
    assert again.json()["key"] == first.json()["key"]

    make_user(db, "latecomer@example.org", UserRole.RESEARCHER)
    third = client.post("/api/notifications/broadcast", json=message, headers=headers)
    assert third.json()["sent"] == 1, "a re-send exists to catch up new accounts"


def test_a_broadcast_key_is_stable_across_processes(python_subprocess):
    """`hash()` is randomised per interpreter, so it would re-deliver after a restart."""
    snippet = ("import hashlib;"
               "print(hashlib.sha1(b'Scheduled maintenance\\nSunday.').hexdigest()[:12])")
    first = python_subprocess(snippet).stdout.strip()
    second = python_subprocess(snippet).stdout.strip()
    assert first and first == second

    unstable = {subprocess.run([sys.executable, "-c", "print(hash('x'))"],
                               capture_output=True, text=True).stdout.strip()
                for _ in range(4)}
    assert len(unstable) > 1, "hash() was expected to vary between processes"


def test_a_broadcast_can_be_limited_to_roles(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "researcher@example.org", UserRole.RESEARCHER)
    make_user(db, "founder@example.org", UserRole.STARTUP_FOUNDER)
    sent = client.post("/api/notifications/broadcast",
                       json={"title": "For founders", "body": "Demo day.",
                             "roles": ["startup_founder"]},
                       headers=auth_header(client, "admin@example.org")).json()
    assert sent["sent"] == 1


def test_only_an_administrator_may_broadcast(client, db):
    make_user(db, "manager@example.org", UserRole.INNOVATION_MANAGER)
    assert client.post("/api/notifications/broadcast",
                       json={"title": "Hello", "body": "Everyone."},
                       headers=auth_header(client, "manager@example.org")
                       ).status_code == 403


def test_the_first_reading_of_a_topic_alerts_nobody(db):
    """There is nothing to compare it against, so a first reading is not news."""
    user = make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_profile(db, user, technology_areas=["energy storage"])

    created = notifications.record_reading(db, "energy storage", {
        "stage": "Growing", "research_total": 1000, "research_growth": 20.0,
        "patent_total": 5000, "patent_growth": 10.0, "patent_history_reliable": True,
    })
    assert created == 0
    assert db.query(Notification).count() == 0
    assert db.query(TopicReading).count() == 1, "but the baseline is remembered"


def test_an_unchanged_reading_says_nothing(db):
    user = make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_profile(db, user, technology_areas=["energy storage"])
    signals = {"stage": "Growing", "research_total": 1000, "research_growth": 20.0,
               "patent_total": 5000, "patent_growth": 10.0,
               "patent_history_reliable": True}
    notifications.record_reading(db, "energy storage", signals)
    assert notifications.record_reading(db, "energy storage", dict(signals)) == 0
    assert db.query(Notification).count() == 0


def test_a_material_move_reaches_the_owners_who_named_that_field(db):
    interested = make_user(db, "interested@example.org", UserRole.RESEARCHER)
    make_profile(db, interested, technology_areas=["energy storage"])
    uninterested = make_user(db, "elsewhere@example.org", UserRole.RESEARCHER)
    make_profile(db, uninterested, technology_areas=["quantum sensing"],
                 domains=["physics"], keywords=["qubit"])

    base = {"stage": "Growing", "research_total": 1000, "research_growth": 20.0,
            "patent_total": 5000, "patent_growth": 10.0,
            "patent_history_reliable": True}
    notifications.record_reading(db, "energy storage", base)
    moved = {**base, "patent_total": 7000}
    assert notifications.record_reading(db, "energy storage", moved) >= 1

    recipients = {n.user_id for n in db.query(Notification).all()}
    assert recipients == {interested.id}, "nobody is told about a field they never claimed"


def test_an_unreliable_series_never_becomes_a_baseline(db):
    """Patent history derived from a sample is not a measurement of the field."""
    user = make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_profile(db, user, technology_areas=["energy storage"])
    signals = {"stage": "Growing", "research_total": 1000, "research_growth": 20.0,
               "patent_total": 5000, "patent_growth": 10.0,
               "patent_history_reliable": False}
    notifications.record_reading(db, "energy storage", signals)
    reading = db.query(TopicReading).one()
    assert reading.patent_history_reliable is False
    assert notifications.record_reading(
        db, "energy storage", {**signals, "patent_growth": 90.0}) == 0
