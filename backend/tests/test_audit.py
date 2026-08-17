"""The audit trail, and the one property its unusual shape exists to provide."""
from app.models.audit import AuditEvent
from app.models.user import UserRole
from tests.conftest import auth_header, make_user


def test_a_role_change_records_who_did_it_to_whom(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN, full_name="The Admin")
    target = make_user(db, "target@example.org", UserRole.RESEARCHER)

    response = client.put(f"/api/users/{target.id}/role",
                          json={"role": "innovation_manager"},
                          headers=auth_header(client, "admin@example.org"))
    assert response.status_code == 200

    events = db.query(AuditEvent).all()
    assert len(events) == 1, "exactly one row per privileged action"
    event = events[0]
    assert event.action == "role_change"
    assert event.actor_email == "admin@example.org"
    assert event.target_email == "target@example.org"
    assert event.detail == "researcher -> innovation_manager"
    assert event.at is not None


def test_the_record_outlives_the_user_it_describes(client, db):
    """Why there is no ForeignKey."""
    make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    target = make_user(db, "doomed@example.org", UserRole.RESEARCHER)
    headers = auth_header(client, "root@example.org")

    client.put(f"/api/users/{target.id}/role", json={"role": "innovation_manager"},
               headers=headers)
    assert client.delete(f"/api/users/{target.id}", headers=headers).status_code == 204

    events = {e.action: e for e in db.query(AuditEvent).all()}
    assert set(events) == {"role_change", "delete_user"}
    assert events["role_change"].target_email == "doomed@example.org"
    assert events["delete_user"].target_email == "doomed@example.org"
    assert events["delete_user"].detail == "innovation_manager"


def test_granting_and_revoking_super_admin_are_both_recorded(client, db):
    make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    peer = make_user(db, "peer@example.org", UserRole.ADMIN)
    headers = auth_header(client, "root@example.org")

    client.put(f"/api/users/{peer.id}/superuser", json={"is_superuser": True},
               headers=headers)
    client.put(f"/api/users/{peer.id}/superuser", json={"is_superuser": False},
               headers=headers)

    actions = [e.action for e in db.query(AuditEvent).order_by(AuditEvent.id).all()]
    assert actions == ["grant_super", "revoke_super"]


def test_a_change_that_changes_nothing_is_not_recorded(client, db):
    """Otherwise a re-submitted form fills the log with events that never happened."""
    make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    peer = make_user(db, "peer@example.org", UserRole.ADMIN, superuser=True)
    response = client.put(f"/api/users/{peer.id}/superuser",
                          json={"is_superuser": True},
                          headers=auth_header(client, "root@example.org"))
    assert response.status_code == 200
    assert db.query(AuditEvent).count() == 0


def test_self_deletion_is_recorded_too(client, db):
    make_user(db, "leaving@example.org", UserRole.RESEARCHER)
    assert client.delete("/api/users/me",
                         headers=auth_header(client, "leaving@example.org")
                         ).status_code == 204
    event = db.query(AuditEvent).one()
    assert event.action == "delete_self"
    assert event.actor_email == event.target_email == "leaving@example.org"


def test_the_audit_log_is_readable_by_administrators_only(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "manager@example.org", UserRole.INNOVATION_MANAGER)
    make_user(db, "owner@example.org", UserRole.RESEARCHER)

    assert client.get("/api/users/audit",
                      headers=auth_header(client, "admin@example.org")
                      ).status_code == 200
    for who in ("manager@example.org", "owner@example.org"):
        assert client.get("/api/users/audit",
                          headers=auth_header(client, who)).status_code == 403


def test_the_audit_log_reads_newest_first_and_caps_its_own_page_size(client, db):
    make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    headers = auth_header(client, "root@example.org")
    for i in range(3):
        target = make_user(db, f"user{i}@example.org", UserRole.RESEARCHER)
        client.put(f"/api/users/{target.id}/role",
                   json={"role": "innovation_manager"}, headers=headers)

    rows = client.get("/api/users/audit?limit=1000", headers=headers).json()
    assert len(rows) == 3
    assert rows[0]["target_email"] == "user2@example.org"

    assert len(client.get("/api/users/audit?limit=1", headers=headers).json()) == 1
