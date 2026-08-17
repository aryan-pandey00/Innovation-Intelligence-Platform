"""Password hashing and the signed token that carries a session."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import jwt
from jwt import PyJWTError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


@lru_cache(maxsize=1)
def _absent_account_hash() -> str:
    """A bcrypt hash of a value no account uses, to be compared against and fail."""
    return hash_password("no-account-on-this-platform-has-this-password")


def verify_password_or_dummy(plain_password: str, hashed_password: str | None) -> bool:
    """Check a password, spending the same time whether or not the account exists."""
    if hashed_password is None:
        verify_password(plain_password, _absent_account_hash())
        return False
    return verify_password(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """Sign a session token, stamped with when it was issued."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update({
        "iat": now.timestamp(),
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except PyJWTError:
        return None
