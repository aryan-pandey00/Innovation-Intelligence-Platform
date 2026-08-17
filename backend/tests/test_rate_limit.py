"""What stops someone guessing passwords all day, and what it must not break."""
import time

import pytest

from app.core import ratelimit
from app.core.config import settings
from app.core.security import verify_password_or_dummy
from app.models.user import User, UserRole
from tests.conftest import BACKEND_ROOT, SECURITY_QUESTIONS, make_user

GOOD_PASSWORD = "test-password-123"
LIMIT = settings.LOGIN_MAX_ATTEMPTS


def _login(client, email, password, **kw):
    return client.post("/api/auth/login",
                       data={"username": email, "password": password}, **kw)


def _from(address: str) -> dict:
    """Headers that make a request look like it came from `address`."""
    return {"X-Forwarded-For": address}


@pytest.fixture
def behind_proxy(monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)


def test_wrong_passwords_are_refused_once_the_limit_is_reached(client, db):
    make_user(db, "target@example.org")

    for attempt in range(LIMIT):
        assert _login(client, "target@example.org", "wrong").status_code == 401, (
            f"attempt {attempt + 1} should still be answered normally")

    blocked = _login(client, "target@example.org", "wrong")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_the_refusal_does_not_say_which_limit_was_hit(client, db):
    """Otherwise the error text leaks what the response timing no longer does."""
    make_user(db, "real@example.org")
    for _ in range(LIMIT + 1):
        _login(client, "real@example.org", "wrong")
    on_real = _login(client, "real@example.org", "wrong")

    ratelimit.reset_all()
    for _ in range(LIMIT + 1):
        _login(client, "ghost@example.org", "wrong")
    on_ghost = _login(client, "ghost@example.org", "wrong")

    assert on_real.status_code == on_ghost.status_code == 429
    assert on_real.json()["detail"] == on_ghost.json()["detail"]


def test_the_limit_is_checked_before_the_password_is_verified(client, db, monkeypatch):
    """Ordering, not politeness."""
    make_user(db, "target@example.org")
    for _ in range(LIMIT):
        _login(client, "target@example.org", "wrong")

    calls = []
    monkeypatch.setattr("app.routes.auth.verify_password_or_dummy",
                        lambda *a, **k: calls.append(1) or False)
    assert _login(client, "target@example.org", "wrong").status_code == 429
    assert calls == [], "the password was hashed on a request that was refused anyway"


def test_registration_is_limited_too(client, db):
    """Each signup costs a bcrypt hash and a permanent row."""
    for i in range(settings.REGISTER_MAX_ATTEMPTS):
        response = client.post("/api/auth/register", json={
            "security_questions": SECURITY_QUESTIONS,
            "email": f"joiner{i}@example.org", "full_name": f"Joiner {i}",
            "password": GOOD_PASSWORD, "role": "researcher"})
        assert response.status_code == 201, response.text

    blocked = client.post("/api/auth/register", json={
        "security_questions": SECURITY_QUESTIONS,
        "email": "one.too.many@example.org", "full_name": "One Too Many",
        "password": GOOD_PASSWORD, "role": "researcher"})
    assert blocked.status_code == 429
    assert db.query(User).filter(
        User.email == "one.too.many@example.org").first() is None


def test_a_rejected_signup_does_not_consume_the_allowance(client, db):
    """A duplicate email costs nothing, so it should not spend a shared address's quota."""
    make_user(db, "taken@example.org")
    for _ in range(settings.REGISTER_MAX_ATTEMPTS + 3):
        assert client.post("/api/auth/register", json={
            "security_questions": SECURITY_QUESTIONS,
            "email": "taken@example.org", "full_name": "Duplicate",
            "password": GOOD_PASSWORD, "role": "researcher"}).status_code == 400

    assert client.post("/api/auth/register", json={
        "security_questions": SECURITY_QUESTIONS,
        "email": "genuinely.new@example.org", "full_name": "Genuinely New",
        "password": GOOD_PASSWORD, "role": "researcher"}).status_code == 201


def test_the_right_password_still_works_after_several_wrong_ones(client, db):
    make_user(db, "forgetful@example.org", password=GOOD_PASSWORD)
    for _ in range(LIMIT - 1):
        assert _login(client, "forgetful@example.org", "wrong").status_code == 401
    assert _login(client, "forgetful@example.org", GOOD_PASSWORD).status_code == 200


def test_a_successful_sign_in_clears_the_count(client, db):
    """This is what keeps the account limit from being a lockout weapon."""
    make_user(db, "owner@example.org", password=GOOD_PASSWORD)
    for _ in range(LIMIT - 1):
        _login(client, "owner@example.org", "wrong")
    assert _login(client, "owner@example.org", GOOD_PASSWORD).status_code == 200

    for _ in range(LIMIT - 1):
        assert _login(client, "owner@example.org", "wrong").status_code == 401, (
            "the counter did not reset on a correct password")


def test_one_address_being_blocked_does_not_block_another(client, db, behind_proxy):
    """A shared network is not a reason to take the whole platform down."""
    make_user(db, "shared@example.org", password=GOOD_PASSWORD)
    for _ in range(LIMIT + 1):
        _login(client, "shared@example.org", "wrong", headers=_from("203.0.113.7"))
    assert _login(client, "shared@example.org", "wrong",
                  headers=_from("203.0.113.7")).status_code == 429

    assert _login(client, "shared@example.org", GOOD_PASSWORD,
                  headers=_from("198.51.100.4")).status_code == 200


def test_a_blocked_address_can_still_be_signed_in_from_after_the_window(client, db,
                                                                       monkeypatch):
    """The block expires on its own."""
    make_user(db, "waiting@example.org", password=GOOD_PASSWORD)
    for _ in range(LIMIT + 1):
        _login(client, "waiting@example.org", "wrong")
    assert _login(client, "waiting@example.org", GOOD_PASSWORD).status_code == 429

    real_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic",
                        lambda: real_monotonic() + settings.LOGIN_WINDOW_SECONDS * 4)
    assert _login(client, "waiting@example.org", GOOD_PASSWORD).status_code == 200


def test_the_deployment_tells_the_limiter_how_many_proxies_are_in_front():
    """The one part of this that a request-level test cannot reach."""
    compose = (BACKEND_ROOT.parent / "docker-compose.yml").read_text(encoding="utf-8")
    assert "TRUSTED_PROXY_HOPS" in compose, (
        "compose puts nginx in front of the API but never tells it so, which leaves "
        "every rate limit keyed on a header the caller controls")
    assert ":-0}" not in compose.split("TRUSTED_PROXY_HOPS")[1].split("\n")[0]


def test_a_forged_forwarded_header_cannot_buy_a_fresh_quota(client, db):
    """With no proxy configured, the header is ignored — which is the safe default."""
    assert settings.TRUSTED_PROXY_HOPS == 0
    make_user(db, "victim@example.org")

    for i in range(LIMIT):
        assert _login(client, "victim@example.org", "wrong",
                      headers=_from(f"10.0.0.{i}")).status_code == 401
    assert _login(client, "victim@example.org", "wrong",
                  headers=_from("10.0.0.250")).status_code == 429


def test_the_trusted_hop_is_read_from_the_right(client, db, monkeypatch):
    """Each proxy appends the peer it saw, so the rightmost entries are the trustworthy ones."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    make_user(db, "hops@example.org")

    for _ in range(LIMIT):
        _login(client, "hops@example.org", "wrong",
               headers=_from("1.2.3.4, 203.0.113.9"))
    assert _login(client, "hops@example.org", "wrong",
                  headers=_from("1.2.3.4, 203.0.113.9")).status_code == 429

    assert _login(client, "hops@example.org", "wrong",
                  headers=_from("9.9.9.9, 203.0.113.9")).status_code == 429


def test_the_counter_map_stays_bounded():
    """A dict keyed on caller address and never pruned is an attacker-controlled leak."""
    limiter = ratelimit.AttemptLimiter(limit=3, window_seconds=300, max_keys=64)
    for i in range(5_000):
        limiter.record_failure(f"10.1.{i // 256}.{i % 256}")
    assert limiter.tracked_keys() <= 64


def test_expired_entries_are_dropped_rather_than_accumulated(monkeypatch):
    limiter = ratelimit.AttemptLimiter(limit=3, window_seconds=60)
    for i in range(100):
        limiter.record_failure(f"host-{i}")
    assert limiter.tracked_keys() == 100

    real_monotonic = time.monotonic
    monkeypatch.setattr(time, "monotonic", lambda: real_monotonic() + 600)
    for i in range(100):
        assert limiter.retry_after(f"host-{i}") is None
    assert limiter.tracked_keys() == 0


def test_an_unknown_account_still_pays_for_a_password_check(monkeypatch):
    """The measured gap was 199ms against 3ms."""
    calls = []
    monkeypatch.setattr("app.core.security.verify_password",
                        lambda plain, hashed: calls.append(hashed) or False)

    verify_password_or_dummy("guess", "$2b$12$aRealStoredHashWouldGoHere")
    verify_password_or_dummy("guess", None)

    assert len(calls) == 2, "the missing-account path skipped the password check"
    assert calls[0] != calls[1]


def test_both_login_failures_are_reported_identically(client, db):
    make_user(db, "exists@example.org", password=GOOD_PASSWORD)
    known = _login(client, "exists@example.org", "wrong")
    unknown = _login(client, "nobody@example.org", "wrong")
    assert known.status_code == unknown.status_code == 401
    assert known.json()["detail"] == unknown.json()["detail"]


@pytest.mark.parametrize("password,label", [
    ("", "an empty string"),
    ("a", "one character"),
    ("1", "one digit"),
    ("short12", "seven characters"),
])

def test_a_password_below_the_floor_is_refused(client, db, password, label):
    """All four of these were accepted by the running server before this."""
    response = client.post("/api/auth/register", json={
        "security_questions": SECURITY_QUESTIONS,
        "email": "weak@example.org", "full_name": "Weak", "password": password,
        "role": "researcher"})
    assert response.status_code == 422, f"{label} was accepted"
    assert db.query(User).filter(User.email == "weak@example.org").first() is None


def test_a_password_longer_than_the_hash_reads_is_refused_not_crashed(client, db):
    """100,000 characters produced a 500 — an unhandled `PasswordSizeError`."""
    for length in (73, 4_097, 100_000):
        response = client.post("/api/auth/register", json={
            "security_questions": SECURITY_QUESTIONS,
            "email": "long@example.org", "full_name": "Long",
            "password": "B" * length, "role": "researcher"})
        assert response.status_code == 422, f"{length} characters -> {response.status_code}"


def test_a_password_at_the_boundary_is_accepted(client, db):
    """The limit is bytes, and the error message says bytes, so 72 must work."""
    assert client.post("/api/auth/register", json={
        "security_questions": SECURITY_QUESTIONS,
        "email": "boundary@example.org", "full_name": "Boundary",
        "password": "C" * 72, "role": "researcher"}).status_code == 201


def test_the_byte_limit_is_counted_in_bytes_not_characters(client, db):
    """bcrypt truncates at 72 bytes."""
    assert client.post("/api/auth/register", json={
        "security_questions": SECURITY_QUESTIONS,
        "email": "emoji@example.org", "full_name": "Emoji",
        "password": "🔒" * 40, "role": "researcher"}).status_code == 422


@pytest.mark.parametrize("password", [
    "password", "Password", "PASSWORD", "password123", "qwerty123", "iloveyou",
    "letmein", "welcome1", "abc123456", "12345678", "trustno1", "admin123",
])

def test_a_password_from_the_top_of_every_breach_list_is_refused(client, db, password):
    """Length alone let `password` through, and it is guess number one everywhere."""
    response = client.post("/api/auth/register", json={
        "security_questions": SECURITY_QUESTIONS,
        "email": "common@example.org", "full_name": "Common", "password": password,
        "role": "researcher"})
    assert response.status_code == 422, f"{password!r} was accepted"


def test_a_password_made_of_the_users_own_name_is_refused(client, db):
    """Their email and display name are shown to every administrator on the platform."""
    for password in ("alice2024", "Alice!!!", "lovelace1", "alice.lovelace"):
        response = client.post("/api/auth/register", json={
            "security_questions": SECURITY_QUESTIONS,
            "email": "alice.lovelace@example.org", "full_name": "Alice Lovelace",
            "password": password, "role": "researcher"})
        assert response.status_code == 422, f"{password!r} was accepted"


def test_an_ordinary_password_is_not_caught_by_either_rule(client, db):
    """The deny-list must not be so eager that real passwords are rejected."""
    for password in ("correct-horse-battery", "Tr0ub4dor&3", "my quiet blue kettle",
                     "aardvark-telescope-9"):
        db.query(User).filter(User.email == "ordinary@example.org").delete()
        db.commit()
        response = client.post("/api/auth/register", json={
            "security_questions": SECURITY_QUESTIONS,
            "email": "ordinary@example.org", "full_name": "Ordinary Person",
            "password": password, "role": "researcher"})
        assert response.status_code == 201, f"{password!r} was refused: {response.text}"


def test_the_signup_form_states_the_rule_the_server_enforces():
    """The form and the API have to agree, and they have drifted once already."""
    import re

    from app.schemas.user import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH

    source = (BACKEND_ROOT.parent / "frontend" / "src" / "pages"
              / "Register.jsx").read_text(encoding="utf-8")
    field = re.search(r'name="password"[\s\S]{0,400}?/>', source)
    assert field, "could not find the password input in Register.jsx"
    block = field.group(0)

    minimum = re.search(r"minLength=\{(\d+)\}", block)
    maximum = re.search(r"maxLength=\{(\d+)\}", block)
    assert minimum and int(minimum.group(1)) == MIN_PASSWORD_LENGTH, (
        f"the form asks for {minimum.group(1) if minimum else 'no'} characters, "
        f"the server requires {MIN_PASSWORD_LENGTH}")
    assert maximum and int(maximum.group(1)) == MAX_PASSWORD_BYTES

    assert f"At least {MIN_PASSWORD_LENGTH} characters" in source


def test_create_admin_refuses_a_weak_password(python_subprocess):
    """The script that makes the most privileged account on the platform is not an."""
    result = python_subprocess(
        "import sys; sys.argv = ['create_admin', 'root@example.org', 'Root', 'abc']\n"
        "from scripts.create_admin import main\n"
        "try:\n"
        "    main()\n"
        "except SystemExit as e:\n"
        "    print('EXIT', e.code)\n")
    assert "EXIT 1" in result.stdout, result.stdout + result.stderr
    assert "at least 8" in result.stdout


def test_registration_and_update_agree_about_how_long_a_name_may_be(client, db):
    """They did not."""
    from app.schemas.user import MAX_NAME_LENGTH

    over = client.post("/api/auth/register", json={
        "security_questions": SECURITY_QUESTIONS,
        "email": "verbose@example.org", "full_name": "A" * (MAX_NAME_LENGTH + 1),
        "password": GOOD_PASSWORD, "role": "researcher"})
    assert over.status_code == 422

    ok = client.post("/api/auth/register", json={
        "security_questions": SECURITY_QUESTIONS,
        "email": "verbose@example.org", "full_name": "A" * MAX_NAME_LENGTH,
        "password": GOOD_PASSWORD, "role": "researcher"})
    assert ok.status_code == 201
    token = ok.json()["access_token"]
    assert client.patch("/api/users/me", json={"full_name": "A" * MAX_NAME_LENGTH},
                        headers={"Authorization": f"Bearer {token}"}
                        ).status_code == 200


def test_registration_collapses_whitespace_in_a_name_the_way_update_does(client, db):
    response = client.post("/api/auth/register", json={
        "security_questions": SECURITY_QUESTIONS,
        "email": "spaced@example.org", "full_name": "  Ada   Lovelace  ",
        "password": GOOD_PASSWORD, "role": "researcher"})
    assert response.status_code == 201
    assert response.json()["user"]["full_name"] == "Ada Lovelace"


def test_every_free_text_query_has_a_ceiling():
    """A census over the real routes, not a list of paths I remembered to write down."""
    from annotated_types import MaxLen, MinLen

    from tests.conftest import api_routes

    uncapped = []
    checked = 0
    for route in api_routes():
        for field in route.dependant.query_params:
            metadata = list(getattr(field.field_info, "metadata", []) or [])
            if not any(isinstance(m, MinLen) for m in metadata):
                continue
            checked += 1
            if not any(isinstance(m, MaxLen) for m in metadata):
                uncapped.append(f"{route.path} ?{field.name}")

    assert checked >= 9, (f"only {checked} free-text params found — the census is "
                          "not reading the application's real routes")
    assert not uncapped, ("these accept unbounded free text:\n  "
                          + "\n  ".join(uncapped))


def test_every_search_box_caps_at_the_length_the_route_accepts():
    """Same rule, stated on both sides — otherwise the page produces a bare 422."""
    import re

    from app.schemas.common import MAX_QUERY_LENGTH

    pages = BACKEND_ROOT.parent / "frontend" / "src" / "pages"
    searching = re.compile(
        r'placeholder=[{"]?[^>]{0,120}?'
        r'(?:a technology|a research topic|Search grants|use your own field)')

    uncapped = []
    checked = 0
    for page in sorted(pages.glob("*.jsx")):
        source = page.read_text(encoding="utf-8")
        for match in re.finditer(r"<input\b", source):
            tag = source[match.start():match.start() + 400]
            tag = tag[:tag.find("/>") + 2] if "/>" in tag else tag
            if not searching.search(tag):
                continue
            checked += 1
            if f"maxLength={{{MAX_QUERY_LENGTH}}}" not in tag:
                uncapped.append(f"{page.name}: {tag[:70]}…")

    assert checked >= 6, (f"only {checked} search inputs found — the census is not "
                          "reading the pages")
    assert not uncapped, "these search boxes accept more than the route will:\n  " \
                         + "\n  ".join(uncapped)


def test_an_oversized_query_is_refused_over_http(client, db):
    """The census above is static; this proves the constraint is actually enforced."""
    from app.schemas.common import MAX_QUERY_LENGTH
    from tests.conftest import auth_header

    make_user(db, "searcher@example.org", UserRole.RESEARCHER)
    headers = auth_header(client, "searcher@example.org")
    response = client.get("/api/trends",
                          params={"query": "x" * (MAX_QUERY_LENGTH + 1)},
                          headers=headers)
    assert response.status_code == 422
