from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _issued_before_password_change(payload: dict, user: User) -> bool:
    """Was this token minted before the account's password last changed?"""
    changed_at = user.password_changed_at
    if changed_at is None:
        return False
    issued = payload.get("iat")
    if issued is None:
        return True
    if changed_at.tzinfo is None:
        changed_at = changed_at.replace(tzinfo=timezone.utc)

    issued_at = datetime.fromtimestamp(issued, tz=timezone.utc)
    return issued_at < changed_at


def get_current_user(request: Request, token: str = Depends(oauth2_scheme),
                     db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_token(token)
    if payload is None:
        raise credentials_exception
    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
    if _issued_before_password_change(payload, user):
        raise credentials_exception
    if user.is_demo and request.method not in _READ_METHODS:
        # The credentials are published, so the first visitor could otherwise change
        # this account's password or delete it and take the demo down with it.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This is a read-only demo account. Register your own to make changes.")
    return user


def is_super_admin(user: User) -> bool:
    """Authority to manage other administrators."""
    return bool(user.is_superuser)


def count_super_admins(db: Session) -> int:
    return db.query(User).filter(User.is_superuser.is_(True)).count()


def count_admins(db: Session) -> int:
    return db.query(User).filter(User.role == UserRole.ADMIN).count()


def self_delete_block(db: Session, user: User) -> str | None:
    """Why this account may not delete itself, or None if it may."""
    if user.is_demo:
        return "This is the public demo account, so it cannot be deleted."
    if is_super_admin(user) and count_super_admins(db) == 1:
        return ("You are the only super-admin. Grant super-admin to another "
                "administrator before deleting this account.")
    if user.role == UserRole.ADMIN and count_admins(db) == 1:
        return ("You are the only administrator. Promote another account "
                "before deleting this one.")
    return None


def require_role(*allowed_roles: UserRole):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of these roles: {[r.value for r in allowed_roles]}"
            )
        return current_user
    return role_checker


def require_super_admin():
    def checker(current_user: User = Depends(get_current_user)) -> User:
        if not is_super_admin(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the super-admin can perform this action.",
            )
        return current_user
    return checker
