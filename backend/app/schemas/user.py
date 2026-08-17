import re

from pydantic import (
    BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator,
)
from datetime import datetime
from app.models.user import UserRole

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 72

MAX_NAME_LENGTH = 120
MAX_ORGANIZATION_LENGTH = 200

_COMMON_PASSWORDS = frozenset("""
password password1 password123 passw0rd p@ssword p@ssw0rd passwords
123456 1234567 12345678 123456789 1234567890 12345 87654321 987654321
qwerty qwerty123 qwertyui qwertyuiop 1q2w3e4r 1qaz2wsx qazwsx zaq12wsx
abc123 abc12345 abc123456 abcd1234 abcdefg abcdefgh a1b2c3d4 aaaaaaaa
11111111 00000000 22222222 99999999 asdfghjk 1234abcd
iloveyou letmein welcome welcome1 welcome123 admin admin123 administrator
root root123 toor guest default changeme change123 secret secret123
login login123 access access123 master master123 superman batman
football baseball basketball dragon monkey sunshine princess flower
shadow michael jennifer jordan harley ranger hunter buster
trustno1 whatever starwars pokemon computer internet samsung google
freedom killer summer winter spring autumn january october
asdfghjkl asdfasdf zxcvbnm zxcvbnm123 poiuytrewa 147258369
loveme hello123 test1234 testing123 temp1234 pass1234 mypassword
qwerty12 asdf1234 987654321 121212 123123123 654321 55555555
""".split())


def _normalise_password(v: str) -> str:
    """Lowercased with trailing digits and punctuation kept — see `_reject_common`."""
    return v.strip().lower()


def _reject_common(password: str, email: str | None, full_name: str | None) -> None:
    """Refuse the values an attacker's first few hundred guesses are made of."""
    lowered = _normalise_password(password)
    if lowered in _COMMON_PASSWORDS:
        raise ValueError(
            "That password appears on every list of the most common ones, so it "
            "would be among the first tried. Please choose something else."
        )

    letters_only = lambda s: re.sub(r"[^a-z]", "", s.lower())  # noqa: E731
    personal = set()
    if email:
        local = email.split("@")[0].lower()
        personal.update(letters_only(p) for p in re.split(r"[._\-+]", local)
                        if len(p) >= 4)
        personal.add(letters_only(local))
    if full_name:
        personal.update(letters_only(p) for p in full_name.split() if len(p) >= 4)
        personal.add(letters_only(full_name))
    personal.discard("")

    stem = letters_only(lowered)
    if stem and stem in personal:
        raise ValueError(
            "That password is your own name or email address with a little added. "
            "Anyone who can see your account can see those, so please choose "
            "something unrelated to them."
        )


def _collapse_name(v: str) -> str:
    """The one name rule, shared by the two routes that accept a name."""
    v = " ".join(v.split())
    if len(v) < 2:
        raise ValueError("Full name must be at least 2 characters.")
    return v


def validate_new_password(password: str, *, email: str | None,
                          full_name: str | None) -> str:
    """Every rule a password must pass, wherever it is being set."""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(
            f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes. Anything longer "
            "is silently truncated by the password hash, so the extra characters "
            "would not protect the account."
        )
    _reject_common(password, email, full_name)
    return password


MAX_ANSWER_LENGTH = 120
MAX_QUESTION_LENGTH = 160
MAX_APPEAL_LENGTH = 500


class SecurityQuestionPair(BaseModel):
    question: str = Field(min_length=8, max_length=MAX_QUESTION_LENGTH)
    answer: str = Field(min_length=1, max_length=MAX_ANSWER_LENGTH)


def _two_distinct_questions(pairs: list[SecurityQuestionPair]) -> None:
    """One rule, both doors — registration and the profile page."""
    a, b = pairs
    if a.question.strip().lower() == b.question.strip().lower():
        raise ValueError("Please choose two different questions.")


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=MAX_NAME_LENGTH)
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    role: UserRole = UserRole.RESEARCHER
    organization: str | None = Field(default=None, max_length=MAX_ORGANIZATION_LENGTH)
    security_questions: list[SecurityQuestionPair] = Field(min_length=2,
                                                           max_length=2)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, v: str) -> str:
        return _collapse_name(v)

    @model_validator(mode="after")
    def password_is_acceptable(self) -> "UserCreate":
        """A model validator, because the rule needs the email and name too."""
        validate_new_password(self.password, email=self.email,
                              full_name=self.full_name)
        _two_distinct_questions(self.security_questions)
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class PasswordChange(BaseModel):
    """Changing your own password while signed in."""
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class SecurityAnswersSubmit(BaseModel):
    """The answers a locked-out person types."""
    email: EmailStr
    answers: list[str] = Field(min_length=1, max_length=2)
    message: str | None = Field(default=None, max_length=MAX_APPEAL_LENGTH)

    @field_validator("answers")
    @classmethod
    def bounded(cls, v: list[str]) -> list[str]:
        if any(len(a) > MAX_ANSWER_LENGTH for a in v):
            raise ValueError(
                f"An answer must be at most {MAX_ANSWER_LENGTH} characters.")
        return v

    @field_validator("message")
    @classmethod
    def blank_is_absent(cls, v: str | None) -> str | None:
        """`""` and `" "` mean the box was left alone, not that nothing was said."""
        cleaned = (v or "").strip()
        return cleaned or None


class PasswordResetAppeal(BaseModel):
    """The other way to ask, for an account with no questions to be asked about."""
    email: EmailStr
    message: str = Field(min_length=1, max_length=MAX_APPEAL_LENGTH)

    @field_validator("message")
    @classmethod
    def not_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Please write something an administrator can check.")
        return cleaned


class SecurityQuestionsUpdate(BaseModel):
    """Both slots at once."""
    pairs: list[SecurityQuestionPair] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def two_different_questions(self) -> "SecurityQuestionsUpdate":
        _two_distinct_questions(self.pairs)
        return self


class PasswordResetSubmit(BaseModel):
    """No email and no code — the claim identifies the request, and the request identifies the account."""
    claim: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH)


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    original_role: UserRole
    is_superuser: bool = False
    organization: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountResponse(UserResponse):
    """The caller's own record — returned by login, register and `GET /api/auth/me`."""
    deletable: bool = True
    delete_block: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AccountResponse


class RoleUpdate(BaseModel):
    role: UserRole


class SuperuserUpdate(BaseModel):
    is_superuser: bool


class AuditEventResponse(BaseModel):
    id: int
    at: datetime
    action: str
    actor_email: str
    target_email: str
    detail: str | None

    model_config = ConfigDict(from_attributes=True)


class UserUpdate(BaseModel):
    """Self-service edits a user may make to their own account record."""
    full_name: str = Field(min_length=2, max_length=MAX_NAME_LENGTH)

    @field_validator("full_name")
    @classmethod
    def strip_and_require_text(cls, v: str) -> str:
        return _collapse_name(v)
