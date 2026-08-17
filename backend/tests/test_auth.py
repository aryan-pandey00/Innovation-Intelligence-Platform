"""Registration, login, and what a token is and is not good for."""
from app.core.security import create_access_token
from app.models.user import User, UserRole
from tests.conftest import auth_header, make_user, registration

REGISTRATION = registration(email="new.researcher@example.org",
                            full_name="New Researcher",
                            organization="Example University")


def test_a_researcher_can_register_and_the_token_works(client, db):
    response = client.post("/api/auth/register",
                           json={**REGISTRATION, "role": "researcher"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["user"]["role"] == "researcher"
    assert body["user"]["original_role"] == "researcher"
    assert body["user"]["is_superuser"] is False

    me = client.get("/api/auth/me",
                    headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == REGISTRATION["email"]


def test_a_founder_can_register(client, db):
    response = client.post("/api/auth/register",
                           json={**REGISTRATION, "role": "startup_founder"})
    assert response.status_code == 201
    assert response.json()["user"]["role"] == "startup_founder"


def test_a_password_is_never_stored_or_returned(client, db):
    client.post("/api/auth/register", json={**REGISTRATION, "role": "researcher"})
    assert REGISTRATION["password"] not in client.post(
        "/api/auth/login", data={"username": REGISTRATION["email"],
                                 "password": REGISTRATION["password"]}).text

    stored = db.query(User).filter(User.email == REGISTRATION["email"]).one()
    assert stored.hashed_password != REGISTRATION["password"]
    assert stored.hashed_password.startswith("$2")


def test_elevated_roles_cannot_be_self_registered(client, db):
    """The rule that keeps the platform's staff roles assigned rather than claimed."""
    for role in ("admin", "innovation_manager"):
        response = client.post("/api/auth/register",
                               json={**REGISTRATION, "role": role})
        assert response.status_code == 403, role
        assert "cannot be self-registered" in response.json()["detail"]
    assert db.query(User).count() == 0, "a refused registration must create nothing"


def test_a_duplicate_email_is_refused(client, db):
    client.post("/api/auth/register", json={**REGISTRATION, "role": "researcher"})
    again = client.post("/api/auth/register", json={**REGISTRATION, "role": "researcher"})
    assert again.status_code == 400
    assert db.query(User).count() == 1


def test_login_rejects_a_wrong_password_without_saying_which_half_was_wrong(client, db):
    make_user(db, "someone@example.org")
    response = client.post("/api/auth/login",
                           data={"username": "someone@example.org", "password": "wrong"})
    assert response.status_code == 401
    detail = response.json()["detail"]
    assert detail == "Incorrect email or password"

    unknown = client.post("/api/auth/login",
                          data={"username": "nobody@example.org", "password": "wrong"})
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == detail


def test_an_unsigned_or_malformed_token_is_rejected(client, db):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me",
                      headers={"Authorization": "Bearer not-a-token"}).status_code == 401


def test_a_token_signed_with_another_key_is_rejected(client, db, monkeypatch):
    """The reason SECRET_KEY must not be the value committed to the repository."""
    make_user(db, "victim@example.org", UserRole.ADMIN)

    import jwt
    forged = jwt.encode({"sub": "victim@example.org", "role": "admin"},
                        "a-different-signing-key", algorithm="HS256")
    response = client.get("/api/auth/me",
                          headers={"Authorization": f"Bearer {forged}"})
    assert response.status_code == 401


def test_a_token_for_a_deleted_account_stops_working(client, db):
    """Tokens are stateless, so the user lookup is the only revocation there is."""
    user = make_user(db, "transient@example.org")
    headers = auth_header(client, "transient@example.org")
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    db.delete(user)
    db.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_an_expired_token_is_rejected(client, db, monkeypatch):
    make_user(db, "expiring@example.org")
    monkeypatch.setattr("app.core.security.settings.ACCESS_TOKEN_EXPIRE_MINUTES", -1)
    stale = create_access_token({"sub": "expiring@example.org", "role": "researcher"})
    assert client.get("/api/auth/me",
                      headers={"Authorization": f"Bearer {stale}"}).status_code == 401
