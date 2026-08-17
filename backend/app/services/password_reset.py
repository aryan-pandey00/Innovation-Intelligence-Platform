"""Asking for a reset, proving who you are, and an administrator deciding."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import secrets

from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.password_reset import PasswordResetRequest, SecurityAnswer
from app.models.user import User, UserRole

SUGGESTED_QUESTIONS = [
    "What was the name of your first school?",
    "In what town or city were you born?",
    "What was the name of your first pet?",
    "What is your oldest cousin's first name?",
    "What was the make of your first phone?",
    "What street did you live on as a child?",
    "What was the title of your first published paper?",
    "Who was your favourite teacher at school?",
]

QUESTION_SLOTS = (1, 2)
APPROVAL_TTL_MINUTES = 30


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _aware(value: dt.datetime | None) -> dt.datetime | None:
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=dt.timezone.utc)
    return value


def normalise_answer(answer: str) -> str:
    """Fold away the differences that are not differences."""
    lowered = (answer or "").strip().lower()
    kept = [c for c in lowered if c.isalnum() or c.isspace()]
    return " ".join("".join(kept).split())


def set_questions(db: Session, user: User,
                  pairs: list[tuple[str, str]]) -> list[SecurityAnswer]:
    """Replace this account's questions."""
    db.query(SecurityAnswer).filter(SecurityAnswer.user_id == user.id).delete()
    rows = []
    for position, (question, answer) in zip(QUESTION_SLOTS, pairs):
        row = SecurityAnswer(
            user_id=user.id,
            position=position,
            question=question.strip(),
            answer_hash=hash_password(normalise_answer(answer)),
        )
        db.add(row)
        rows.append(row)
    return rows


def questions_of(db: Session, user_id: int) -> list[SecurityAnswer]:
    return (db.query(SecurityAnswer)
            .filter(SecurityAnswer.user_id == user_id)
            .order_by(SecurityAnswer.position)
            .all())


def _decoy_questions(email: str) -> list[str]:
    """Two questions for an address with no account behind it.

    Stable per address, so retrying is not itself the tell.
    """
    digest = hashlib.sha256((email or "").strip().lower().encode()).digest()
    first = digest[0] % len(SUGGESTED_QUESTIONS)
    second = (first + 1 + digest[1] % (len(SUGGESTED_QUESTIONS) - 1)) \
        % len(SUGGESTED_QUESTIONS)
    return [SUGGESTED_QUESTIONS[first], SUGGESTED_QUESTIONS[second]]


ASK_QUESTIONS = "questions"
ASK_APPEAL = "appeal"


def questions_for(db: Session, email: str) -> tuple[str, list[str]]:
    """What to ask this address: `(ASK_QUESTIONS, [q1, q2])` or `(ASK_APPEAL, [])`."""
    user = (db.query(User)
            .filter(User.email == (email or "").strip().lower())
            .first())
    if user is None:
        return ASK_QUESTIONS, _decoy_questions(email)
    rows = questions_of(db, user.id)
    if len(rows) == len(QUESTION_SLOTS):
        return ASK_QUESTIONS, [r.question for r in rows]
    return ASK_APPEAL, []


def generate_claim() -> str:
    return secrets.token_urlsafe(32)


def hash_claim(claim: str) -> str:
    return hashlib.sha256((claim or "").strip().encode("utf-8")).hexdigest()


def by_claim(db: Session, claim: str) -> PasswordResetRequest | None:
    """The request a browser is holding, whatever state it reached."""
    if not claim:
        return None
    return (db.query(PasswordResetRequest)
            .filter(PasswordResetRequest.claim_hash == hash_claim(claim))
            .order_by(PasswordResetRequest.requested_at.desc())
            .first())


def live_request_for(db: Session, user_id: int) -> PasswordResetRequest | None:
    return (db.query(PasswordResetRequest)
            .filter(PasswordResetRequest.user_id == user_id,
                    PasswordResetRequest.consumed_at.is_(None),
                    PasswordResetRequest.cancelled_at.is_(None))
            .order_by(PasswordResetRequest.requested_at.desc())
            .first())


def open_request(db: Session, email: str, claim: str, *,
                 message: str | None = None) -> PasswordResetRequest | None:
    """Record a submitted request and bind it to the browser."""
    user = (db.query(User)
            .filter(User.email == (email or "").strip().lower())
            .first())
    if user is None:
        return None

    existing = live_request_for(db, user.id)
    if existing is not None:
        existing.claim_hash = hash_claim(claim)
        if message is not None and not existing.is_approved:
            existing.appeal_message = message
        return existing

    row = PasswordResetRequest(user_id=user.id, claim_hash=hash_claim(claim),
                               appeal_message=message,
                               had_questions=bool(questions_of(db, user.id)))
    db.add(row)
    db.flush()
    return row


def record_answers(db: Session, row: PasswordResetRequest,
                   answers: list[str]) -> None:
    """Check the answers and write down how it went."""
    stored = questions_of(db, row.user_id)
    summary, matched = [], 0

    if not stored:
        summary = [{"question": None, "matched": None, "typed": None}]
        row.had_questions = False
    else:
        row.had_questions = True
        for index, question in enumerate(stored):
            given = answers[index] if index < len(answers) else ""
            ok = verify_password(normalise_answer(given), question.answer_hash)
            matched += 1 if ok else 0
            summary.append({
                "question": question.question,
                "matched": ok,
                "typed": (given or "").strip()[:80],
            })

    row.answer_summary = json.dumps(summary)
    row.answers_matched = matched
    row.answered_at = _now()


def evidence_summary(row: PasswordResetRequest) -> str:
    """What a decision on this request rests on, in one phrase.

    Written into audit_events and kept, so every field combination gets a true answer.
    """
    if row.had_questions:
        if row.answers_matched is not None:
            return f"{row.answers_matched} of 2 security answers matched"
        # Not the "no questions" wording below: that invites a lenient decision, and
        # this account has two.
        return ("security questions were set but not answered"
                + (" — a written appeal instead" if row.appeal_message else ""))
    if row.appeal_message:
        return "no security questions — a written appeal"
    return "no security questions were set"


def read_answers(row: PasswordResetRequest) -> list[dict]:
    if not row.answer_summary:
        return []
    try:
        return json.loads(row.answer_summary)
    except ValueError:
        return []


def approve(db: Session, row: PasswordResetRequest, admin: User) -> bool:
    """Let this request through."""
    if row.is_cancelled or row.is_consumed or row.is_approved:
        return False
    row.approved_at = _now()
    row.issued_by_id = admin.id
    row.issued_by_email = admin.email
    row.expires_at = _now() + dt.timedelta(minutes=APPROVAL_TTL_MINUTES)
    return True


def is_expired(row: PasswordResetRequest) -> bool:
    expires = _aware(row.expires_at)
    return expires is not None and expires <= _now()


def state_of(row: PasswordResetRequest | None) -> str:
    """What the waiting browser is told."""
    if row is None:
        # "waiting", not "expired": an invented address writes no row, so anything
        # else here announces that the address does not exist.
        return "waiting"
    if row.is_cancelled:
        return "declined"
    if row.is_consumed:
        return "used"
    if row.is_approved:
        return "expired" if is_expired(row) else "approved"
    return "waiting"


def claim_ready(db: Session, claim: str) -> PasswordResetRequest | None:
    """The request this claim may set a password against, or None."""
    row = by_claim(db, claim)
    if (row is None or not row.is_approved or row.is_cancelled
            or row.is_consumed or is_expired(row)):
        return None
    return row


def consume(row: PasswordResetRequest) -> None:
    """Mark it used."""
    row.consumed_at = _now()


def cancel(row: PasswordResetRequest) -> None:
    """Decline it — and **keep the claim**, unlike `consume`."""
    row.cancelled_at = _now()


def pending(db: Session, limit: int = 50) -> list[PasswordResetRequest]:
    """Requests that still need a decision."""
    return (db.query(PasswordResetRequest)
            .filter(PasswordResetRequest.approved_at.is_(None),
                    PasswordResetRequest.consumed_at.is_(None),
                    PasswordResetRequest.cancelled_at.is_(None))
            .order_by(PasswordResetRequest.requested_at.asc())
            .limit(limit)
            .all())


def is_live_approval(row: PasswordResetRequest) -> bool:
    """Approved, unspent, and still inside its window — the only undoable state."""
    return (row.is_approved and not row.is_consumed and not row.is_cancelled
            and not is_expired(row))


def decided(db: Session, limit: int = 60) -> list[PasswordResetRequest]:
    """Everything no longer awaiting a decision, newest first."""
    return (db.query(PasswordResetRequest)
            .filter((PasswordResetRequest.approved_at.isnot(None))
                    | (PasswordResetRequest.consumed_at.isnot(None))
                    | (PasswordResetRequest.cancelled_at.isnot(None)))
            .order_by(PasswordResetRequest.requested_at.desc())
            .limit(limit)
            .all())


def administrators(db: Session) -> list[User]:
    """Who to notify."""
    return db.query(User).filter(User.role == UserRole.ADMIN).all()
