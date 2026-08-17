from sqlalchemy import Boolean, Column, Integer, String, Enum, DateTime
from sqlalchemy.sql import func
import enum
from app.core.database import Base


class UserRole(str, enum.Enum):
    RESEARCHER = "researcher"
    STARTUP_FOUNDER = "startup_founder"
    INNOVATION_MANAGER = "innovation_manager"
    ADMIN = "admin"


ROLE_LABELS = {
    UserRole.RESEARCHER: "Researcher",
    UserRole.STARTUP_FOUNDER: "Startup Founder",
    UserRole.INNOVATION_MANAGER: "Innovation Manager",
    UserRole.ADMIN: "Administrator",
}


def role_label(role) -> str:
    """The display name for a role, given the enum or its stored string value."""
    if isinstance(role, str) and not isinstance(role, UserRole):
        try:
            role = UserRole(role)
        except ValueError:
            return role.replace("_", " ").title()
    return ROLE_LABELS.get(role, str(role))


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.RESEARCHER, nullable=False)
    original_role = Column(Enum(UserRole), default=UserRole.RESEARCHER, nullable=False)
    is_superuser = Column(Boolean, nullable=False, server_default="false",
                          default=False)
    organization = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    password_changed_at = Column(DateTime(timezone=True), nullable=True)
