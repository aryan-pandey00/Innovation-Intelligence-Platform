"""Role gates, the privilege ladder, and the guards that keep someone in charge."""
import pytest

from app.models.research_profile import ResearchProfile
from app.models.user import User, UserRole
from tests.conftest import auth_header, make_profile, make_user, registration

PROFILE_BODY = {
    "headline": "Testing",
    "research_domains": ["energy"],
    "keywords": ["battery"],
    "technology_areas": ["energy storage"],
    "country": "United States",
}


@pytest.mark.parametrize("role,expected", [
    (UserRole.RESEARCHER, 403),
    (UserRole.STARTUP_FOUNDER, 403),
    (UserRole.INNOVATION_MANAGER, 200),
    (UserRole.ADMIN, 200),
])

def test_the_user_list_is_staff_only(client, db, role, expected):
    make_user(db, "caller@example.org", role)
    response = client.get("/api/users/all",
                          headers=auth_header(client, "caller@example.org"))
    assert response.status_code == expected


@pytest.mark.parametrize("path,manager_expected", [
    ("/api/users/analytics/recommendations", 403),
    ("/api/users/analytics/pipeline", 200),
])

def test_the_analytics_endpoints_split_admin_from_manager(client, db, path,
                                                          manager_expected):
    make_user(db, "manager@example.org", UserRole.INNOVATION_MANAGER)
    make_user(db, "admin@example.org", UserRole.ADMIN)
    assert client.get(path, headers=auth_header(client, "manager@example.org")
                      ).status_code == manager_expected
    assert client.get(path, headers=auth_header(client, "admin@example.org")
                      ).status_code == 200


@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.INNOVATION_MANAGER])
def test_staff_cannot_create_a_research_profile(client, db, role):
    """Staff run the platform and are never scored."""
    make_user(db, "staff@example.org", role)
    response = client.post("/api/profiles/me", json=PROFILE_BODY,
                           headers=auth_header(client, "staff@example.org"))
    assert response.status_code == 403
    assert db.query(ResearchProfile).count() == 0


@pytest.mark.parametrize("role", [UserRole.RESEARCHER, UserRole.STARTUP_FOUNDER])
def test_owners_can_create_a_research_profile(client, db, role):
    make_user(db, "owner@example.org", role)
    response = client.post("/api/profiles/me", json=PROFILE_BODY,
                           headers=auth_header(client, "owner@example.org"))
    assert response.status_code == 201, response.text
    assert db.query(ResearchProfile).count() == 1


def test_a_promoted_researcher_keeps_an_editable_profile(client, db):
    """Only *creation* is gated."""
    user = make_user(db, "promoted@example.org", UserRole.RESEARCHER)
    make_profile(db, user)
    headers = auth_header(client, "promoted@example.org")

    user.role = UserRole.INNOVATION_MANAGER
    db.commit()

    assert client.get("/api/profiles/me", headers=headers).status_code == 200
    assert client.put("/api/profiles/me", json={"headline": "Still mine"},
                      headers=headers).status_code == 200


def test_an_administrator_cannot_change_their_own_role(client, db):
    admin = make_user(db, "admin@example.org", UserRole.ADMIN)
    response = client.put(f"/api/users/{admin.id}/role", json={"role": "researcher"},
                          headers=auth_header(client, "admin@example.org"))
    assert response.status_code == 400
    assert "your own role" in response.json()["detail"]


def test_a_plain_admin_cannot_create_another_admin(client, db):
    """Admin → admin is reserved to the tier above, the standard owner/admin split."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    target = make_user(db, "hopeful@example.org", UserRole.RESEARCHER)
    response = client.put(f"/api/users/{target.id}/role", json={"role": "admin"},
                          headers=auth_header(client, "admin@example.org"))
    assert response.status_code == 403


def test_a_plain_admin_cannot_touch_another_administrator(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    peer = make_user(db, "peer@example.org", UserRole.ADMIN)
    headers = auth_header(client, "admin@example.org")
    assert client.put(f"/api/users/{peer.id}/role", json={"role": "researcher"},
                      headers=headers).status_code == 403
    assert client.delete(f"/api/users/{peer.id}", headers=headers).status_code == 403


def test_a_plain_admin_may_promote_someone_to_innovation_manager(client, db):
    """A manager's permissions are a strict subset of an admin's."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    target = make_user(db, "rising@example.org", UserRole.RESEARCHER)
    response = client.put(f"/api/users/{target.id}/role",
                          json={"role": "innovation_manager"},
                          headers=auth_header(client, "admin@example.org"))
    assert response.status_code == 200
    assert response.json()["role"] == "innovation_manager"
    assert response.json()["original_role"] == "researcher"


def test_a_manager_can_be_demoted_to_their_original_role(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    target = make_user(db, "returning@example.org", UserRole.RESEARCHER)
    headers = auth_header(client, "admin@example.org")
    client.put(f"/api/users/{target.id}/role", json={"role": "innovation_manager"},
               headers=headers)
    back = client.put(f"/api/users/{target.id}/role", json={"role": "researcher"},
                      headers=headers)
    assert back.status_code == 200
    assert back.json()["role"] == "researcher"


def test_an_admin_cannot_swap_a_user_between_the_two_owner_roles(client, db):
    """Researcher and founder are what the person said they were, not a setting."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    target = make_user(db, "owner@example.org", UserRole.RESEARCHER)
    response = client.put(f"/api/users/{target.id}/role",
                          json={"role": "startup_founder"},
                          headers=auth_header(client, "admin@example.org"))
    assert response.status_code == 400


def test_a_superuser_role_cannot_be_changed_while_the_flag_is_set(client, db):
    """Refused, not silently cleared."""
    make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    peer = make_user(db, "peer@example.org", UserRole.ADMIN, superuser=True)
    response = client.put(f"/api/users/{peer.id}/role", json={"role": "researcher"},
                          headers=auth_header(client, "root@example.org"))
    assert response.status_code == 400
    assert "Remove super-admin" in response.json()["detail"]


def test_changing_the_role_of_an_absent_user_is_a_404(client, db):
    make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    response = client.put("/api/users/99999/role", json={"role": "researcher"},
                          headers=auth_header(client, "root@example.org"))
    assert response.status_code == 404


def test_only_a_super_admin_may_grant_super_admin(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    target = make_user(db, "peer@example.org", UserRole.ADMIN)
    response = client.put(f"/api/users/{target.id}/superuser",
                          json={"is_superuser": True},
                          headers=auth_header(client, "admin@example.org"))
    assert response.status_code == 403


def test_the_administrator_tier_cannot_be_skipped(client, db):
    make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    target = make_user(db, "researcher@example.org", UserRole.RESEARCHER)
    response = client.put(f"/api/users/{target.id}/superuser",
                          json={"is_superuser": True},
                          headers=auth_header(client, "root@example.org"))
    assert response.status_code == 400
    assert "Only an administrator" in response.json()["detail"]


def test_super_admin_can_be_granted_to_another_administrator(client, db):
    make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    target = make_user(db, "peer@example.org", UserRole.ADMIN)
    response = client.put(f"/api/users/{target.id}/superuser",
                          json={"is_superuser": True},
                          headers=auth_header(client, "root@example.org"))
    assert response.status_code == 200
    assert response.json()["is_superuser"] is True


def test_the_last_super_admin_cannot_be_removed(client, db):
    """Including by themselves — otherwise stepping down locks the platform."""
    root = make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    headers = auth_header(client, "root@example.org")
    response = client.put(f"/api/users/{root.id}/superuser",
                          json={"is_superuser": False}, headers=headers)
    assert response.status_code == 400
    assert "only super-admin" in response.json()["detail"]


def test_stepping_down_works_once_someone_else_holds_it(client, db):
    root = make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    successor = make_user(db, "successor@example.org", UserRole.ADMIN)
    headers = auth_header(client, "root@example.org")

    assert client.put(f"/api/users/{successor.id}/superuser",
                      json={"is_superuser": True}, headers=headers).status_code == 200
    stepping_down = client.put(f"/api/users/{root.id}/superuser",
                               json={"is_superuser": False}, headers=headers)
    assert stepping_down.status_code == 200
    assert stepping_down.json()["is_superuser"] is False


def test_the_only_super_admin_cannot_delete_their_own_account(client, db):
    make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    make_user(db, "peer@example.org", UserRole.ADMIN)
    response = client.delete("/api/users/me",
                             headers=auth_header(client, "root@example.org"))
    assert response.status_code == 400
    assert "only super-admin" in response.json()["detail"]
    assert db.query(User).filter(User.email == "root@example.org").count() == 1


def test_the_only_administrator_cannot_delete_their_own_account(client, db):
    """Neither staff role is self-registerable."""
    make_user(db, "solo@example.org", UserRole.ADMIN)
    response = client.delete("/api/users/me",
                             headers=auth_header(client, "solo@example.org"))
    assert response.status_code == 400
    assert "only administrator" in response.json()["detail"]


def test_an_owner_can_delete_their_own_account(client, db):
    make_user(db, "leaving@example.org", UserRole.RESEARCHER)
    response = client.delete("/api/users/me",
                             headers=auth_header(client, "leaving@example.org"))
    assert response.status_code == 204
    assert db.query(User).count() == 0


@pytest.mark.parametrize("setup, deletable", [
    ((("root@example.org", UserRole.ADMIN, True),
      ("peer@example.org", UserRole.ADMIN, False)), False),
    ((("solo@example.org", UserRole.ADMIN, False),), False),
    ((("owner@example.org", UserRole.RESEARCHER, False),), True),
    ((("manager@example.org", UserRole.INNOVATION_MANAGER, False),), True),
])

def test_the_delete_flag_agrees_with_the_route_it_describes(client, db, setup,
                                                            deletable):
    """One rule, two readers — and a test that reads them apart is the only thing."""
    for email, role, superuser in setup:
        make_user(db, email, role, superuser=superuser)
    email = setup[0][0]
    headers = auth_header(client, email)

    me = client.get("/api/auth/me", headers=headers).json()
    assert me["deletable"] is deletable
    assert (me["delete_block"] is None) is deletable

    response = client.delete("/api/users/me", headers=headers)
    if deletable:
        assert response.status_code == 204
    else:
        assert response.status_code == 400
        assert response.json()["detail"] == me["delete_block"]


@pytest.mark.parametrize("route, payload", [
    ("/api/auth/login", None),
    ("/api/auth/register", registration(email="joining@example.org",
                                        full_name="Joining")),
])

def test_every_route_that_returns_your_own_account_answers_the_delete_question(
        client, db, route, payload):
    """The three routes that hand back "you" must hand back the same record."""
    make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    make_user(db, "peer@example.org", UserRole.ADMIN)

    if payload is None:
        response = client.post("/api/auth/login",
                               data={"username": "root@example.org",
                                     "password": "test-password-123"})
        expected = {"deletable": False}
    else:
        response = client.post(route, json=payload)
        expected = {"deletable": True}
    assert response.status_code in (200, 201), response.text

    account = response.json()["user"]
    assert account["deletable"] is expected["deletable"]
    assert (account["delete_block"] is None) is expected["deletable"]

    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = client.get("/api/auth/me", headers=headers).json()
    assert me == account


def test_deleting_a_profile_owner_takes_the_profile_with_them(client, db):
    """The cascade is declared on the foreign key; this is the proof it is in force."""
    user = make_user(db, "owner@example.org", UserRole.RESEARCHER)
    make_profile(db, user)
    assert client.delete("/api/users/me",
                         headers=auth_header(client, "owner@example.org")
                         ).status_code == 204
    assert db.query(ResearchProfile).count() == 0


def test_an_admin_cannot_delete_themselves_through_the_admin_route(client, db):
    admin = make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "peer@example.org", UserRole.ADMIN)
    response = client.delete(f"/api/users/{admin.id}",
                             headers=auth_header(client, "admin@example.org"))
    assert response.status_code == 400


def test_a_super_admin_may_delete_another_administrator(client, db):
    make_user(db, "root@example.org", UserRole.ADMIN, superuser=True)
    peer = make_user(db, "peer@example.org", UserRole.ADMIN)
    assert client.delete(f"/api/users/{peer.id}",
                         headers=auth_header(client, "root@example.org")
                         ).status_code == 204
