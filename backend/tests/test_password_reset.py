"""Changing a password, and getting back in after forgetting one."""
import datetime as dt

import pytest

from app.core.security import create_access_token, verify_password
from app.models.password_reset import PasswordResetRequest, SecurityAnswer
from app.models.user import User, UserRole
from app.services import password_reset
from tests.conftest import BACKEND_ROOT, auth_header, make_user

GOOD = "test-password-123"
NEW = "a-quiet-blue-kettle-42"

Q1 = "What was the name of your first school?"
A1 = "St Xavier"
Q2 = "In what town or city were you born?"
A2 = "Delhi"


def _set_questions(client, email, password=GOOD):
    """Give an account two questions, through the route a person would use."""
    response = client.put("/api/auth/security-questions",
                          headers=auth_header(client, email, password=password),
                          json={"pairs": [{"question": Q1, "answer": A1},
                                          {"question": Q2, "answer": A2}]})
    assert response.status_code == 204, response.text


def _forgot(client, email):
    """Ask what this address should be shown."""
    return client.post("/api/auth/password/forgot", json={"email": email})


def _answer(client, email, answers, message=None):
    body = {"email": email, "answers": answers}
    if message is not None:
        body["message"] = message
    return client.post("/api/auth/password/answers", json=body)


def _appeal(client, email, message="I sit in the Materials lab, ask Dr Menon."):
    return client.post("/api/auth/password/appeal",
                       json={"email": email, "message": message})


def _submit(client, email, answers=("something", "anything")):
    """Make the request the way a person does, and hold the claim it returns."""
    response = _answer(client, email, list(answers))
    assert response.status_code == 200, response.text
    return response.json()["claim"]


def _status(client, claim):
    return client.get("/api/auth/password/status", params={"claim": claim})


def _queue(client, admin_email="admin@example.org"):
    return client.get("/api/admin/password-resets",
                      headers=auth_header(client, admin_email)).json()


def _approve(client, request_id, admin_email="admin@example.org"):
    return client.post(f"/api/admin/password-resets/{request_id}/approve",
                       headers=auth_header(client, admin_email))


def _session_opened_minutes_ago(email, role="researcher", minutes=5):
    """A token for a session that began before whatever the test is about to do."""
    import jwt as pyjwt

    from app.core.config import settings

    now = dt.datetime.now(dt.timezone.utc)
    token = pyjwt.encode(
        {"sub": email, "role": role,
         "iat": (now - dt.timedelta(minutes=minutes)).timestamp(),
         "exp": now + dt.timedelta(minutes=30)},
        settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return {"Authorization": f"Bearer {token}"}


def test_an_invented_address_is_answered_like_a_configured_account(client, db):
    """The property that matters: probing cannot confirm an address is registered."""
    make_user(db, "hasq@example.org")
    _set_questions(client, "hasq@example.org")

    real = _forgot(client, "hasq@example.org")
    invented = _forgot(client, "nobody@example.org")

    for response in (real, invented):
        assert response.status_code == 200
        body = response.json()
        assert body["mode"] == "questions"
        assert len(body["questions"]) == 2
        assert body["detail"] == real.json()["detail"]
    assert sorted(real.json()) == sorted(invented.json())


def test_an_account_with_no_questions_is_told_so_rather_than_asked_invented_ones(
        client, db):
    """The one case that *is* distinguishable, and the reason it is worth it."""
    make_user(db, "noq@example.org")

    body = _forgot(client, "noq@example.org").json()
    assert body["mode"] == "appeal"
    assert body["questions"] == []


def test_the_questions_for_an_unknown_address_do_not_change_between_tries(client, db):
    """Otherwise retrying is the oracle."""
    first = _forgot(client, "nobody@example.org").json()["questions"]
    second = _forgot(client, "nobody@example.org").json()["questions"]
    assert first == second
    other = _forgot(client, "someone.else@example.org").json()["questions"]
    assert other != first


def test_asking_creates_nothing_and_tells_nobody(client, db):
    """Typing an address into the first box is not a request."""
    admin = make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "real@example.org")
    _set_questions(client, "real@example.org")
    before = client.get("/api/notifications",
                        headers=auth_header(client, "admin@example.org")).json()

    for _ in range(3):
        assert _forgot(client, "real@example.org").status_code == 200
        assert _forgot(client, "nobody@example.org").status_code == 200

    assert db.query(PasswordResetRequest).count() == 0
    after = client.get("/api/notifications",
                       headers=auth_header(client, "admin@example.org")).json()
    assert len(after["items"]) == len(before["items"])
    assert admin.id is not None


def test_a_request_is_only_recorded_for_a_real_account(client, db):
    make_user(db, "real@example.org")
    _submit(client, "real@example.org")
    _submit(client, "nobody@example.org")
    assert db.query(PasswordResetRequest).count() == 1


def test_the_claim_is_minted_by_the_server_not_chosen_by_the_caller(client, db):
    """There is no field to put one in, and two submissions never share one."""
    make_user(db, "real@example.org")
    first = _submit(client, "real@example.org")
    second = _submit(client, "real@example.org")

    assert first != second
    assert len(first) > 30
    planted = client.post("/api/auth/password/answers",
                          json={"email": "real@example.org", "answers": ["a", "b"],
                                "claim": "aaaa"}).json()["claim"]
    assert planted not in ("aaaa", first, second)


def test_submitting_twice_rebinds_rather_than_queueing_twice(client, db):
    """A second tab should be able to finish, and an admin should still see one job."""
    make_user(db, "real@example.org")
    first = _submit(client, "real@example.org")
    second = _submit(client, "real@example.org")

    assert first != second
    assert db.query(PasswordResetRequest).count() == 1
    assert _status(client, second).json()["state"] == "waiting"
    assert _status(client, first).json()["state"] == "waiting"


def test_answering_both_questions_correctly_approves_nothing(client, db):
    """The centre of the whole design."""
    make_user(db, "stuck@example.org")
    _set_questions(client, "stuck@example.org")
    claim = _submit(client, "stuck@example.org", [A1, A2])

    assert _status(client, claim).json()["state"] == "waiting"
    assert client.post("/api/auth/password/reset", json={
        "claim": claim, "new_password": NEW}).status_code == 400


def test_the_answer_endpoint_does_not_report_the_score(client, db):
    """Otherwise it is an oracle for guessing them one attempt at a time."""
    make_user(db, "stuck@example.org")
    _set_questions(client, "stuck@example.org")

    right = _answer(client, "stuck@example.org", [A1, A2])
    wrong = _answer(client, "stuck@example.org", ["nope", "also nope"])

    assert right.status_code == wrong.status_code == 200
    assert (right.json().keys() == wrong.json().keys()
            and right.json()["detail"] == wrong.json()["detail"])


def test_answers_are_rate_limited(client, db):
    make_user(db, "stuck@example.org")
    _set_questions(client, "stuck@example.org")
    codes = [_answer(client, "stuck@example.org", ["guess", "guess"]).status_code
             for _ in range(15)]
    assert 429 in codes


def test_a_correct_answer_does_not_refill_the_allowance(client, db):
    """Login clears its counter on success because success ends the attempt."""
    from app.core import ratelimit

    make_user(db, "stuck@example.org")
    _set_questions(client, "stuck@example.org")

    _answer(client, "stuck@example.org", ["wrong", "wrong"])
    before = ratelimit.reset_answers_by_address.tracked_keys()
    _answer(client, "stuck@example.org", [A1, A2])
    assert ratelimit.reset_answers_by_address.tracked_keys() >= before


def test_only_a_hash_of_each_answer_is_stored(client, db):
    make_user(db, "stuck@example.org")
    _set_questions(client, "stuck@example.org")

    rows = db.query(SecurityAnswer).all()
    assert len(rows) == 2
    for row in rows:
        assert A1 not in row.answer_hash and A2 not in row.answer_hash
        assert row.answer_hash.startswith("$2")


def test_the_account_holder_cannot_read_their_own_answers_back(client, db):
    make_user(db, "stuck@example.org")
    _set_questions(client, "stuck@example.org")

    body = client.get("/api/auth/security-questions",
                      headers=auth_header(client, "stuck@example.org")).json()
    assert [q["question"] for q in body["questions"]] == [Q1, Q2]
    assert body["configured"] is True
    assert A1 not in str(body) and A2 not in str(body)


@pytest.mark.parametrize("given", ["Delhi", "delhi", "  DELHI  ", "Delhi.", "de lhi"])
def test_an_answer_is_matched_after_normalising(client, db, given):
    """The commonest way an honest person fails their own question is capitalisation."""
    assert (password_reset.normalise_answer(given)
            == password_reset.normalise_answer("Delhi")) is (given != "de lhi")


def test_the_administrator_sees_both_answers_and_both_verdicts(client, db):
    """Judging somebody on half the evidence is not judging."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "stuck@example.org")
    _set_questions(client, "stuck@example.org")
    claim = _submit(client, "stuck@example.org", [A1, "New Delhi"])

    row = next(r for r in _queue(client)["waiting"]
               if r["email"] == "stuck@example.org")
    matched, missed = row["answers"]

    assert matched["matched"] is True and matched["typed"] == A1
    assert missed["matched"] is False and missed["typed"] == "New Delhi"
    assert row["answers_matched"] == 1


def test_the_stored_answer_is_never_exposed_however_it_is_asked_for(client, db):
    """The hash is the thing that must not travel — not the attempt."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "stuck@example.org")
    _set_questions(client, "stuck@example.org")
    claim = _submit(client, "stuck@example.org", [A1, A2])

    payload = str(_queue(client))
    assert "answer_hash" not in payload and "$2b$" not in payload
    own = client.get("/api/auth/security-questions",
                     headers=auth_header(client, "stuck@example.org")).text
    assert A1 not in own and A2 not in own and "$2b$" not in own


def test_an_account_with_no_questions_is_distinguishable_from_a_wrong_answer(client, db):
    """Two failures and never-configured are different situations for the admin."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "bare@example.org")
    _submit(client, "bare@example.org", ["something", "anything"])

    row = next(r for r in _queue(client)["waiting"] if r["email"] == "bare@example.org")
    assert row["had_questions"] is False
    assert row["answers_matched"] == 0


def test_an_appeal_reaches_the_queue_carrying_what_was_written(client, db):
    """The only thing an administrator has to go on here, so it has to arrive."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "bare@example.org")

    said = "I run the Tuesday seminar; Dr Menon in room 304 knows me."
    claim = _appeal(client, "bare@example.org", said).json()["claim"]

    row = next(r for r in _queue(client)["waiting"] if r["email"] == "bare@example.org")
    assert row["appeal_message"] == said
    assert row["had_questions"] is False
    assert row["state"] == "waiting"
    assert _status(client, claim).json()["state"] == "waiting"
    assert client.post("/api/auth/password/reset", json={
        "claim": claim, "new_password": NEW}).status_code == 400


def test_an_appeal_for_an_invented_address_answers_the_same_and_writes_nothing(
        client, db):
    """`/forgot` distinguishes the no-questions account; this must not do it twice."""
    make_user(db, "bare@example.org")

    real = _appeal(client, "bare@example.org")
    phantom = _appeal(client, "nobody@example.org")

    assert real.status_code == phantom.status_code == 200
    assert real.json()["detail"] == phantom.json()["detail"]
    assert sorted(real.json()) == sorted(phantom.json())
    assert real.json()["claim"] != phantom.json()["claim"]
    assert db.query(PasswordResetRequest).count() == 1


def test_an_appeal_that_is_only_whitespace_is_refused(client, db):
    """`min_length` counts spaces."""
    make_user(db, "bare@example.org")
    assert _appeal(client, "bare@example.org", "   \n  ").status_code == 422
    assert db.query(PasswordResetRequest).count() == 0


def test_an_appeal_is_bounded(client, db):
    make_user(db, "bare@example.org")
    assert _appeal(client, "bare@example.org", "x" * 501).status_code == 422
    assert _appeal(client, "bare@example.org", "x" * 500).status_code == 200


def test_an_appeal_cannot_rewrite_evidence_an_administrator_already_acted_on(
        client, db):
    """Approval is recorded against what was in front of the administrator."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "bare@example.org")
    _appeal(client, "bare@example.org", "The first thing I said.")
    row_id = next(r["id"] for r in _queue(client)["waiting"])
    _approve(client, row_id)

    moved = _appeal(client, "bare@example.org", "Something else entirely.")

    row = db.get(PasswordResetRequest, row_id)
    db.refresh(row)
    assert row.appeal_message == "The first thing I said."
    assert _status(client, moved.json()["claim"]).json()["state"] == "approved"


def test_approval_lets_the_claim_holder_set_a_password(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    user = make_user(db, "stuck@example.org", password=GOOD)
    _set_questions(client, "stuck@example.org")
    claim = _submit(client, "stuck@example.org", [A1, A2])

    row_id = next(r["id"] for r in _queue(client)["waiting"])
    assert _approve(client, row_id).status_code == 200
    assert _status(client, claim).json()["state"] == "approved"

    done = client.post("/api/auth/password/reset",
                       json={"claim": claim, "new_password": NEW})
    assert done.status_code == 200, done.text
    db.refresh(user)
    assert verify_password(NEW, user.hashed_password)
    assert client.post("/api/auth/login", data={
        "username": "stuck@example.org", "password": NEW}).status_code == 200


def test_a_declined_request_cannot_set_a_password(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "stuck@example.org")
    claim = _submit(client, "stuck@example.org")
    row_id = next(r["id"] for r in _queue(client)["waiting"])

    assert client.post(f"/api/admin/password-resets/{row_id}/cancel",
                       headers=auth_header(client, "admin@example.org")
                       ).status_code == 200
    assert _status(client, claim).json()["state"] == "declined"
    assert client.post("/api/auth/password/reset", json={
        "claim": claim, "new_password": NEW}).status_code == 400


def test_an_administrator_cannot_start_a_reset_nobody_asked_for(client, db):
    """No route takes a user id."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    victim = make_user(db, "victim@example.org")
    headers = auth_header(client, "admin@example.org")

    assert client.post(f"/api/admin/password-resets/{victim.id}/approve",
                       headers=headers).status_code == 404

    row = PasswordResetRequest(user_id=victim.id,
                               cancelled_at=dt.datetime.now(dt.timezone.utc))
    db.add(row)
    db.commit()
    assert client.post(f"/api/admin/password-resets/{row.id}/approve",
                       headers=headers).status_code == 400


def test_a_claim_cannot_finish_somebody_elses_request(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "alice@example.org")
    make_user(db, "bob@example.org")
    alice_claim = _submit(client, "alice@example.org")
    _submit(client, "bob@example.org")

    bob_row = next(r["id"] for r in _queue(client)["waiting"]
                   if r["email"] == "bob@example.org")
    _approve(client, bob_row)

    assert client.post("/api/auth/password/reset", json={
        "claim": alice_claim, "new_password": NEW}).status_code == 400


def test_a_claim_works_once(client, db):
    """And single use now rests entirely on `claim_ready` checking `is_consumed`."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "stuck@example.org")
    claim = _submit(client, "stuck@example.org")
    _approve(client, next(r["id"] for r in _queue(client)["waiting"]))

    assert client.post("/api/auth/password/reset", json={
        "claim": claim, "new_password": NEW}).status_code == 200
    assert client.post("/api/auth/password/reset", json={
        "claim": claim, "new_password": "another-one-entirely-77"}).status_code == 400
    assert _status(client, claim).json()["state"] == "used"


def test_a_decided_request_leaves_the_queue_of_decisions(client, db):
    """Three lists, and a request is in exactly one of them at a time."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "stuck@example.org")
    _submit(client, "stuck@example.org")

    row_id = next(r["id"] for r in _queue(client)["waiting"])
    _approve(client, row_id)

    q = _queue(client)
    assert [r["id"] for r in q["waiting"]] == []
    assert [r["id"] for r in q["approved"]] == [row_id]
    assert [r["id"] for r in q["recent"]] == []

    row = db.get(PasswordResetRequest, row_id)
    row.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    db.commit()

    q = _queue(client)
    assert [r["id"] for r in q["waiting"]] == []
    assert [r["id"] for r in q["approved"]] == []
    assert [(r["id"], r["state"]) for r in q["recent"]] == [(row_id, "expired")]


def test_a_completed_or_declined_request_is_only_in_recent(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "used@example.org")
    make_user(db, "said.no@example.org")

    claim = _submit(client, "used@example.org")
    _approve(client, next(r["id"] for r in _queue(client)["waiting"]))
    client.post("/api/auth/password/reset",
                json={"claim": claim, "new_password": NEW})

    _submit(client, "said.no@example.org")
    refused = next(r["id"] for r in _queue(client)["waiting"])
    client.post(f"/api/admin/password-resets/{refused}/cancel",
                headers=auth_header(client, "admin@example.org"))

    q = _queue(client)
    assert q["waiting"] == [] and q["approved"] == []
    assert {r["state"] for r in q["recent"]} == {"completed", "cancelled"}


def test_an_expired_approval_cannot_be_used(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "stuck@example.org")
    claim = _submit(client, "stuck@example.org")
    row_id = next(r["id"] for r in _queue(client)["waiting"])
    _approve(client, row_id)

    row = db.get(PasswordResetRequest, row_id)
    row.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
    db.commit()

    assert _status(client, claim).json()["state"] == "expired"
    assert client.post("/api/auth/password/reset", json={
        "claim": claim, "new_password": NEW}).status_code == 400


def test_an_unknown_claim_reads_as_waiting(client, db):
    """The last place the flow gave away who exists, and it gave away everything."""
    make_user(db, "real@example.org")
    real = _submit(client, "real@example.org")
    phantom = _submit(client, "nobody@example.org")

    assert _status(client, "nothing-like-a-real-claim").json()["state"] == "waiting"
    assert _status(client, phantom).json() == _status(client, real).json()


def test_the_new_password_obeys_the_same_rules_as_registration(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "stuck@example.org")
    claim = _submit(client, "stuck@example.org")
    _approve(client, next(r["id"] for r in _queue(client)["waiting"]))

    for bad in ("short", "password", "stuck2024"):
        assert client.post("/api/auth/password/reset", json={
            "claim": claim, "new_password": bad}).status_code in (400, 422), bad


@pytest.mark.parametrize("role", [UserRole.RESEARCHER, UserRole.STARTUP_FOUNDER,
                                  UserRole.INNOVATION_MANAGER])

def test_the_reset_queue_is_for_administrators_only(client, db, role):
    make_user(db, "caller@example.org", role)
    headers = auth_header(client, "caller@example.org")
    assert client.get("/api/admin/password-resets",
                      headers=headers).status_code == 403
    assert client.get("/api/admin/password-resets/waiting",
                      headers=headers).status_code == 403
    assert client.post("/api/admin/password-resets/1/approve",
                       headers=headers).status_code == 403
    assert client.post("/api/admin/password-resets/1/cancel",
                       headers=headers).status_code == 403


def test_the_badge_count_agrees_with_the_queue_it_stands_for(client, db):
    """The sidebar badge is a separate, cheaper endpoint, so it can disagree."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "one@example.org")
    make_user(db, "two@example.org")

    def badge():
        return client.get("/api/admin/password-resets/waiting",
                          headers=auth_header(client, "admin@example.org")
                          ).json()["waiting"]

    assert badge() == 0
    _submit(client, "one@example.org")
    _submit(client, "two@example.org")
    assert badge() == len(_queue(client)["waiting"]) == 2

    _approve(client, next(r["id"] for r in _queue(client)["waiting"]))
    assert badge() == len(_queue(client)["waiting"]) == 1


def test_the_appeal_route_refuses_an_account_that_has_questions(client, db):
    """Which door an account may use is decided on the server, not in the browser."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "guarded@example.org")
    _set_questions(client, "guarded@example.org")

    assert _forgot(client, "guarded@example.org").json()["mode"] == "questions"

    response = _appeal(client, "guarded@example.org", "Please just let me in.")
    assert response.status_code == 200, response.text

    assert db.query(PasswordResetRequest).count() == 0
    assert _queue(client)["waiting"] == []

    invented = _appeal(client, "nobody-at-all@example.org", "Please just let me in.")
    assert invented.status_code == response.status_code
    assert invented.json()["detail"] == response.json()["detail"]
    assert invented.json()["claim"] != response.json()["claim"]
    for claim in (response.json()["claim"], invented.json()["claim"]):
        assert _status(client, claim).json()["state"] == "waiting"

    db.query(SecurityAnswer).filter(
        SecurityAnswer.user_id == db.query(User).filter(
            User.email == "guarded@example.org").first().id).delete()
    db.commit()
    assert _forgot(client, "guarded@example.org").json()["mode"] == "appeal"
    assert _appeal(client, "guarded@example.org", "Ask Dr Menon.").status_code == 200
    assert db.query(PasswordResetRequest).count() == 1


def test_a_note_can_travel_with_the_answers_without_changing_the_verdict(client, db):
    """Somebody who set questions and cannot recall the answers can now say so."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "forgetful@example.org")
    _set_questions(client, "forgetful@example.org")

    response = _answer(client, "forgetful@example.org", ["nope", "also nope"],
                       message="I am in the Materials lab, ask Dr Menon.")
    assert response.status_code == 200, response.text

    row = db.query(PasswordResetRequest).one()
    assert row.appeal_message == "I am in the Materials lab, ask Dr Menon."
    assert row.had_questions is True
    assert row.answers_matched == 0
    assert password_reset.evidence_summary(row) == "0 of 2 security answers matched"

    waiting = _queue(client)["waiting"][0]
    assert waiting["appeal_message"] == "I am in the Materials lab, ask Dr Menon."


@pytest.mark.parametrize("sent", [None, "", "   "])
def test_an_untouched_note_box_is_stored_as_nothing(client, db, sent):
    """Blank means nothing was said, not that an empty thing was said."""
    make_user(db, "quiet@example.org")
    _set_questions(client, "quiet@example.org")

    payload = {"email": "quiet@example.org", "answers": [A1, A2]}
    if sent is not None:
        payload["message"] = sent
    assert client.post("/api/auth/password/answers",
                       json=payload).status_code == 200

    assert db.query(PasswordResetRequest).one().appeal_message is None


def test_the_recorded_basis_is_never_false_about_the_questions(db):
    """`evidence_summary` answers every combination, not only the reachable ones."""
    user = make_user(db, "basis@example.org")
    row = PasswordResetRequest(user_id=user.id, claim_hash="x" * 64)

    for had, matched, message, must_not_say, should_say in [
        (True,  2,    None,     "no security questions", "2 of 2"),
        (True,  0,    None,     "no security questions", "0 of 2"),
        (True,  None, None,     "no security questions", "not answered"),
        (True,  None, "let me in", "no security questions", "not answered"),
        (False, None, "let me in", None,                 "written appeal"),
        (False, None, None,     None,                    "no security questions"),
    ]:
        row.had_questions, row.answers_matched, row.appeal_message = had, matched, message
        basis = password_reset.evidence_summary(row)
        assert should_say in basis, (had, matched, message, basis)
        if must_not_say:
            assert must_not_say not in basis, (
                f"a row whose account HAS questions is described as {basis!r}")


def test_the_reset_page_is_reachable_by_its_own_route():
    """It left the Admin Panel, so the sidebar, the router and the notification that."""
    registry = _jsx("components", "modules.jsx")
    assert "'/resets'" in registry and "key: 'resets'" in registry

    app = _jsx("App.jsx")
    assert 'path="/resets"' in app
    assert 'path="/admin/resets"' in app and "Navigate to=\"/resets\"" in app

    routes = (BACKEND_ROOT / "app" / "routes" / "auth.py").read_text(encoding="utf-8")
    assert 'link="/resets"' in routes


def test_registration_requires_two_security_questions(client, db):
    """Required at signup, not offered on the profile page afterwards."""
    from tests.conftest import registration

    for missing in ({}, {"security_questions": []},
                    {"security_questions": [{"question": Q1, "answer": A1}]}):
        payload = registration(email="joiner@example.org")
        payload.pop("security_questions", None)
        payload.update(missing)
        assert client.post("/api/auth/register",
                           json=payload).status_code == 422, missing
    assert db.query(User).filter(User.email == "joiner@example.org").first() is None


def test_a_registered_account_can_be_recovered_from_the_moment_it_exists(client, db):
    """The questions are written in the same transaction as the account."""
    from tests.conftest import registration

    response = client.post("/api/auth/register",
                           json=registration(email="joiner@example.org"))
    assert response.status_code == 201, response.text

    user = db.query(User).filter(User.email == "joiner@example.org").one()
    stored = db.query(SecurityAnswer).filter(
        SecurityAnswer.user_id == user.id).order_by(SecurityAnswer.position).all()
    assert [s.position for s in stored] == [1, 2]
    assert _forgot(client, "joiner@example.org").json()["questions"] == [
        s.question for s in stored]


def test_registration_refuses_two_identical_questions(client, db):
    """Two identical questions are one question asked twice, counted as two pieces of evidence."""
    from tests.conftest import registration

    assert client.post("/api/auth/register", json=registration(
        email="joiner@example.org",
        security_questions=[{"question": Q1, "answer": "a"},
                            {"question": Q1, "answer": "b"}])).status_code == 422


def _jsx(*parts):
    return (BACKEND_ROOT.parent / "frontend" / "src"
            ).joinpath(*parts).read_text(encoding="utf-8")


def test_the_signup_form_asks_for_them_too():
    """The server requiring something the form never collects is a signup that."""
    source = _jsx("pages", "Register.jsx")
    assert "security_questions" in source, "the form does not send them"
    assert "SecurityQuestionFields" in source, "the form renders no question inputs"
    assert "No email is sent" in source


def test_both_pages_that_set_questions_use_the_one_component():
    """They were built twice and drifted."""
    component = _jsx("components", "SecurityQuestionFields.jsx")
    assert "Write my own" in component and "<select" in component

    for page in (("pages", "Register.jsx"), ("pages", "Profile.jsx")):
        source = _jsx(*page)
        assert "SecurityQuestionFields" in source, f"{page[-1]} bypasses it"
        assert "datalist" not in source, f"{page[-1]} still hand-rolls the control"
        assert "suggestions" not in source or page[-1] == "Profile.jsx"


def test_setting_security_questions_needs_your_own_token(client, db):
    """No administrator route writes these."""
    assert client.put("/api/auth/security-questions", json={
        "pairs": [{"question": Q1, "answer": A1},
                  {"question": Q2, "answer": A2}]}).status_code == 401


def test_two_questions_must_differ(client, db):
    make_user(db, "stuck@example.org")
    assert client.put("/api/auth/security-questions",
                      headers=auth_header(client, "stuck@example.org"),
                      json={"pairs": [{"question": Q1, "answer": "a"},
                                      {"question": Q1, "answer": "b"}]}
                      ).status_code == 422


def test_administrators_are_told_when_somebody_is_locked_out(client, db):
    """On submit — see `test_asking_creates_nothing_and_tells_nobody` for the half."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "stuck@example.org")
    _submit(client, "stuck@example.org")

    feed = client.get("/api/notifications",
                      headers=auth_header(client, "admin@example.org")).json()
    assert "Password reset requested" in [n["title"] for n in feed["items"]]


def test_an_appeal_notifies_administrators_too(client, db):
    """The other door into the same queue."""
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "bare@example.org")
    _appeal(client, "bare@example.org")

    feed = client.get("/api/notifications",
                      headers=auth_header(client, "admin@example.org")).json()
    assert "Password reset requested" in [n["title"] for n in feed["items"]]


def test_the_audit_log_records_the_approval_and_the_reset(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "stuck@example.org")
    claim = _submit(client, "stuck@example.org")
    _approve(client, next(r["id"] for r in _queue(client)["waiting"]))
    client.post("/api/auth/password/reset",
                json={"claim": claim, "new_password": NEW})

    actions = [e["action"] for e in client.get(
        "/api/users/audit", headers=auth_header(client, "admin@example.org")).json()]
    assert "password_reset_approved" in actions
    assert "password_reset_completed" in actions


def test_a_reset_ends_the_sessions_that_predate_it(client, db):
    make_user(db, "admin@example.org", UserRole.ADMIN)
    make_user(db, "stuck@example.org", password=GOOD)
    stolen = _session_opened_minutes_ago("stuck@example.org")
    claim = _submit(client, "stuck@example.org")
    _approve(client, next(r["id"] for r in _queue(client)["waiting"]))

    assert client.post("/api/auth/password/reset", json={
        "claim": claim, "new_password": NEW}).status_code == 200
    assert client.get("/api/auth/me", headers=stolen).status_code == 401


def test_a_session_opened_moments_before_a_change_still_dies(client, db):
    """No sleep, no backdating — the tight case, which was briefly broken."""
    make_user(db, "quick@example.org", password=GOOD)
    token = auth_header(client, "quick@example.org")
    assert client.get("/api/auth/me", headers=token).status_code == 200

    assert client.post("/api/auth/password", headers=token, json={
        "current_password": GOOD, "new_password": NEW}).status_code == 204
    assert client.get("/api/auth/me", headers=token).status_code == 401


def test_a_token_with_no_issued_at_is_refused_only_after_a_change(client, db):
    """Tokens predating the `iat` claim cannot be dated."""
    user = make_user(db, "legacy@example.org")
    import jwt as pyjwt

    from app.core.config import settings
    ancient = pyjwt.encode({"sub": "legacy@example.org", "role": "researcher",
                            "exp": dt.datetime.now(dt.timezone.utc)
                            + dt.timedelta(minutes=30)},
                           settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    headers = {"Authorization": f"Bearer {ancient}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200

    user.password_changed_at = dt.datetime.now(dt.timezone.utc)
    db.commit()
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_changing_a_password_requires_the_current_one(client, db):
    """A stolen token expires in an hour."""
    make_user(db, "owner@example.org", password=GOOD)
    headers = auth_header(client, "owner@example.org")
    assert client.post("/api/auth/password", headers=headers, json={
        "current_password": "not-the-password", "new_password": NEW
    }).status_code == 400


def test_the_new_password_must_differ_from_the_old_one(client, db):
    make_user(db, "owner@example.org", password=GOOD)
    headers = auth_header(client, "owner@example.org")
    assert client.post("/api/auth/password", headers=headers, json={
        "current_password": GOOD, "new_password": GOOD}).status_code == 400


@pytest.mark.parametrize("bad", ["short", "password", "owner2024", "a" * 80])
def test_changing_to_a_bad_password_is_refused(client, db, bad):
    make_user(db, "owner@example.org", password=GOOD)
    headers = auth_header(client, "owner@example.org")
    assert client.post("/api/auth/password", headers=headers, json={
        "current_password": GOOD, "new_password": bad}).status_code in (400, 422)


def test_changing_a_password_is_rate_limited(client, db):
    make_user(db, "owner@example.org", password=GOOD)
    headers = auth_header(client, "owner@example.org")
    codes = [client.post("/api/auth/password", headers=headers, json={
        "current_password": f"guess-{i}", "new_password": NEW}).status_code
        for i in range(15)]
    assert 429 in codes


def test_signing_in_again_immediately_after_a_change_works(client, db):
    """The other direction, and just as important."""
    make_user(db, "owner@example.org", password=GOOD)
    assert client.post("/api/auth/password",
                       headers=auth_header(client, "owner@example.org"),
                       json={"current_password": GOOD,
                             "new_password": NEW}).status_code == 204
    fresh = auth_header(client, "owner@example.org", password=NEW)
    assert client.get("/api/auth/me", headers=fresh).status_code == 200


def test_the_signup_form_states_the_rule_the_server_enforces():
    """The form and the API have drifted once already."""
    import re

    from app.schemas.user import MAX_PASSWORD_BYTES, MIN_PASSWORD_LENGTH

    source = (BACKEND_ROOT.parent / "frontend" / "src" / "pages"
              / "Register.jsx").read_text(encoding="utf-8")
    field = re.search(r'name="password"[\s\S]{0,400}?/>', source)
    assert field, "could not find the password input in Register.jsx"

    minimum = re.search(r"minLength=\{(\d+)\}", field.group(0))
    maximum = re.search(r"maxLength=\{(\d+)\}", field.group(0))
    assert minimum and int(minimum.group(1)) == MIN_PASSWORD_LENGTH
    assert maximum and int(maximum.group(1)) == MAX_PASSWORD_BYTES
    assert f"At least {MIN_PASSWORD_LENGTH} characters" in source


def test_create_admin_can_reset_a_password_and_nothing_else(python_subprocess, db):
    """The last resort behind the last resort: every administrator locked out at once."""
    from tests.conftest import _test_database_url

    make_user(db, "locked@example.org", UserRole.ADMIN, superuser=True,
              password=GOOD)
    result = python_subprocess(
        "import sys; sys.argv = ['create_admin', 'locked@example.org', "
        f"'{NEW}', '--reset-password']\n"
        "from scripts.create_admin import main\n"
        "main()\n",
        env_extra={"DATABASE_URL": _test_database_url()})
    assert "Password reset for" in result.stdout, result.stdout + result.stderr

    db.expire_all()
    refreshed = db.query(User).filter(User.email == "locked@example.org").first()
    assert verify_password(NEW, refreshed.hashed_password)
    assert refreshed.role == UserRole.ADMIN and refreshed.is_superuser is True
    assert refreshed.password_changed_at is not None


def test_create_admin_reset_obeys_the_password_rules(python_subprocess, db):
    from tests.conftest import _test_database_url

    make_user(db, "locked@example.org", UserRole.ADMIN)
    result = python_subprocess(
        "import sys; sys.argv = ['create_admin', 'locked@example.org', 'abc', "
        "'--reset-password']\n"
        "from scripts.create_admin import main\n"
        "try:\n"
        "    main()\n"
        "except SystemExit as e:\n"
        "    print('EXIT', e.code)\n",
        env_extra={"DATABASE_URL": _test_database_url()})
    assert "EXIT 1" in result.stdout, result.stdout + result.stderr
