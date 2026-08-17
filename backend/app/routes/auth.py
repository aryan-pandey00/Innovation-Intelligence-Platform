import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.ratelimit import (
    guard_login, guard_password_change, guard_registration, guard_reset_answers,
    guard_reset_lookup, guard_reset_redeem, guard_reset_request, guard_reset_status,
    note_login_failure, note_login_success, note_password_change_failure,
    note_password_change_success, note_registration, note_reset_answer_attempt,
    note_reset_failure, note_reset_lookup, note_reset_request, note_reset_status,
    note_reset_success,
)
from app.core.security import (
    create_access_token, hash_password, verify_password,
    verify_password_or_dummy,
)
from app.core.dependencies import get_current_user, self_delete_block
from app.models.user import User, UserRole
from app.services import audit, notifications, password_reset
from app.schemas.user import (
    AccountResponse, ForgotPasswordRequest, PasswordChange, PasswordResetAppeal,
    PasswordResetSubmit, SecurityAnswersSubmit, SecurityQuestionsUpdate, Token,
    UserCreate, validate_new_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

SELF_REGISTERABLE_ROLES = {UserRole.RESEARCHER, UserRole.STARTUP_FOUNDER}


def account_for(db: Session, user: User) -> AccountResponse:
    """The caller's own record, with the delete answer already attached."""
    account = AccountResponse.model_validate(user)
    blocked = self_delete_block(db, user)
    account.deletable = blocked is None
    account.delete_block = blocked
    return account


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(request: Request, user_data: UserCreate, db: Session = Depends(get_db)):
    guard_registration(request)
    if user_data.role not in SELF_REGISTERABLE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This role cannot be self-registered. It must be assigned by an administrator.",
        )
    existing = db.query(User).filter(User.email == user_data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
        original_role=user_data.role,
        organization=user_data.organization,
    )
    db.add(new_user)
    db.flush()
    password_reset.set_questions(
        db, new_user,
        [(p.question, p.answer) for p in user_data.security_questions])
    db.commit()
    db.refresh(new_user)
    note_registration(request)

    token = create_access_token({"sub": new_user.email, "role": new_user.role.value})
    return {"access_token": token, "token_type": "bearer",
            "user": account_for(db, new_user)}


@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(),
          db: Session = Depends(get_db)):
    """Sign in, at a rate somebody has to be able to afford."""
    guard_login(request, form_data.username)

    user = db.query(User).filter(User.email == form_data.username).first()
    if not verify_password_or_dummy(
            form_data.password, user.hashed_password if user else None):
        note_login_failure(request, form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    note_login_success(request, form_data.username)
    token = create_access_token({"sub": user.email, "role": user.role.value})
    return {"access_token": token, "token_type": "bearer",
            "user": account_for(db, user)}


@router.get("/me", response_model=AccountResponse)
def get_me(current_user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """The signed-in account, plus whether it may delete itself."""
    return account_for(db, current_user)


def _apply_new_password(user: User, new_password: str) -> None:
    """Set a password and end every session that predates it."""
    user.hashed_password = hash_password(new_password)
    user.password_changed_at = dt.datetime.now(dt.timezone.utc)


def _validated(new_password: str, user: User) -> None:
    """Run the shared password rules, reporting failures as 400 rather than 500."""
    try:
        validate_new_password(new_password, email=user.email,
                              full_name=user.full_name)
    except (ValueError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_my_password(request: Request, data: PasswordChange,
                       current_user: User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """Change your own password."""
    guard_password_change(current_user.id)

    if not verify_password(data.current_password, current_user.hashed_password):
        note_password_change_failure(current_user.id)
        raise HTTPException(status_code=400,
                            detail="Your current password is not correct.")
    if data.new_password == data.current_password:
        raise HTTPException(
            status_code=400,
            detail="Your new password must be different from the current one.")

    _validated(data.new_password, current_user)
    _apply_new_password(current_user, data.new_password)
    db.commit()
    note_password_change_success(current_user.id)


FORGOT_ANSWER = ("Answer your security questions below. An administrator will check "
                 "them and let you through — this platform does not send email, so "
                 "nothing will arrive in your inbox. Keep this page open.")
SUBMITTED_ANSWER = ("Thank you. An administrator will review this shortly. "
                    "Keep this page open — it will update on its own.")


def _notify_administrators(db: Session, row) -> None:
    """Tell everyone who can approve."""
    for admin in password_reset.administrators(db):
        notifications.emit(
            db, admin.id, notifications.PLATFORM_HEALTH,
            "Password reset requested",
            f"{row.user.full_name} ({row.user.email}) cannot sign in. Check "
            "their security answers in the admin panel and approve if you are "
            "satisfied it is really them.",
            dedupe_key=f"password:request:{row.id}",
            link="/resets",
            priority=notifications.NOW,
        )


def _submitted(db: Session, email: str, *, message: str | None = None,
               answers: list[str] | None = None) -> dict:
    """Create the request, bind it to this browser, tell the administrators.

    One function for both submit routes: an unknown address must answer identically.
    """
    # Minted here, never read from the body — a caller-chosen claim would be pollable.
    claim = password_reset.generate_claim()
    row = password_reset.open_request(db, email, claim, message=message)
    if row is not None:
        # Never rewrite evidence an administrator has already acted on.
        if not row.is_approved:
            if answers is not None:
                password_reset.record_answers(db, row, answers)
            _notify_administrators(db, row)
        db.commit()
    return {"claim": claim, "detail": SUBMITTED_ANSWER}


@router.post("/password/forgot")
def forgot_password(request: Request, data: ForgotPasswordRequest,
                    db: Session = Depends(get_db)):
    """What should this person be asked?"""
    guard_reset_lookup(request)
    note_reset_lookup(request)

    mode, questions = password_reset.questions_for(db, data.email)
    return {"mode": mode, "questions": questions, "detail": FORGOT_ANSWER}


@router.post("/password/answers")
def submit_security_answers(request: Request, data: SecurityAnswersSubmit,
                            db: Session = Depends(get_db)):
    """Record the answers for an administrator to weigh."""
    guard_reset_answers(request)
    guard_reset_request(request)
    note_reset_answer_attempt(request)
    note_reset_request(request)

    return _submitted(db, data.email, answers=data.answers, message=data.message)


@router.post("/password/appeal")
def appeal_for_reset(request: Request, data: PasswordResetAppeal,
                     db: Session = Depends(get_db)):
    """Ask an administrator directly, for an account with no questions to ask about."""
    guard_reset_request(request)
    note_reset_request(request)

    # The browser picks the door; the server checks this account has it. Skipping the
    # questions once produced a queue entry the audit log described as having none.
    mode, _ = password_reset.questions_for(db, data.email)
    if mode != password_reset.ASK_APPEAL:
        # Answered exactly like an address with no account: a claim, nothing written.
        return {"claim": password_reset.generate_claim(), "detail": SUBMITTED_ANSWER}

    return _submitted(db, data.email, message=data.message)


@router.get("/password/status")
def reset_status(request: Request, claim: str = Query(..., min_length=8,
                                                      max_length=128),
                 db: Session = Depends(get_db)):
    """What the waiting browser is told: four words and nothing else.

    An unknown claim reads "waiting" — see `state_of`, where the reason lives.
    """
    guard_reset_status(request)
    note_reset_status(request)
    return {"state": password_reset.state_of(password_reset.by_claim(db, claim))}


@router.post("/password/reset")
def reset_password(request: Request, data: PasswordResetSubmit,
                   db: Session = Depends(get_db)):
    """Set a new password, once an administrator has approved this claim."""
    guard_reset_redeem(request)

    row = password_reset.claim_ready(db, data.claim)
    if row is None:
        note_reset_failure(request)
        raise HTTPException(
            status_code=400,
            detail="This reset is no longer valid. It may have been declined, timed "
                   "out, or already been used. Please ask again.")

    user = row.user
    _validated(data.new_password, user)

    _apply_new_password(user, data.new_password)
    password_reset.consume(row)
    audit.record(db, "password_reset_completed", actor=user, target=user,
                 detail=f"approved by {row.issued_by_email or 'an administrator'}")
    notifications.emit(
        db, user.id, notifications.PLATFORM_HEALTH,
        "Your password was reset",
        "Your password was changed after an administrator approved a reset request. "
        "If that was not you, tell an administrator now.",
        dedupe_key=f"password:reset:{row.id}",
        priority=notifications.NOW,
    )
    db.commit()
    note_reset_success(request)
    return {"detail": "Your password has been changed. You have been signed out "
                      "everywhere, so sign in again with the new password."}


@router.get("/security-questions")
def my_security_questions(current_user: User = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """Your two questions, and never your answers."""
    rows = password_reset.questions_of(db, current_user.id)
    return {
        "questions": [{"position": r.position, "question": r.question} for r in rows],
        "configured": len(rows) == len(password_reset.QUESTION_SLOTS),
        "suggestions": password_reset.SUGGESTED_QUESTIONS,
    }


@router.put("/security-questions", status_code=status.HTTP_204_NO_CONTENT)
def set_my_security_questions(data: SecurityQuestionsUpdate,
                              current_user: User = Depends(get_current_user),
                              db: Session = Depends(get_db)):
    """Replace both questions."""
    password_reset.set_questions(
        db, current_user, [(p.question, p.answer) for p in data.pairs])
    db.commit()
