from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import (
    count_super_admins, get_current_user, is_super_admin, require_role,
    require_super_admin, self_delete_block,
)
from app.models import audit as audit_model
from app.models.user import User, UserRole
from app.schemas.user import (
    AuditEventResponse, RoleUpdate, SuperuserUpdate, UserResponse, UserUpdate,
)
from app.services import audit, platform_analytics

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/all", response_model=list[UserResponse])
def list_all_users(
    db: Session = Depends(get_db),
    _user: User = Depends(require_role(UserRole.ADMIN, UserRole.INNOVATION_MANAGER)),
):
    return db.query(User).all()


@router.get("/analytics/recommendations")
def recommendation_monitoring(
    db: Session = Depends(get_db),
    _user: User = Depends(require_role(UserRole.ADMIN)),
):
    """How well the recommendation engine is reaching the platform's users."""
    return platform_analytics.recommendation_stats(db)


@router.get("/analytics/pipeline")
def pipeline_monitoring(
    db: Session = Depends(get_db),
    _user: User = Depends(require_role(UserRole.ADMIN, UserRole.INNOVATION_MANAGER)),
):
    """What the monitored innovators work on, and the funding open to them."""
    return platform_analytics.pipeline_stats(db)


@router.patch("/me", response_model=UserResponse)
def update_my_account(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the signed-in user's own account details."""
    current_user.full_name = data.full_name
    db.commit()
    db.refresh(current_user)
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Self-service deletion, except where it would leave nobody in charge."""
    blocked = self_delete_block(db, current_user)
    if blocked:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=blocked)
    audit.record(db, audit_model.DELETE_SELF, current_user, current_user,
                 detail=current_user.role.value)
    db.delete(current_user)
    db.commit()


@router.get("/audit", response_model=list[AuditEventResponse])
def audit_log(
    limit: int = 20,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role(UserRole.ADMIN)),
):
    """Who changed whose access, and when."""
    return audit.recent(db, limit=min(max(limit, 1), 100))


@router.put("/{user_id}/role", response_model=UserResponse)
def change_user_role(
    user_id: int,
    data: RoleUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own role.",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not is_super_admin(admin) and user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the super-admin can modify other administrator accounts.",
        )

    if not is_super_admin(admin) and data.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the super-admin can promote users to Administrator.",
        )

    if user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Remove super-admin from this account before changing its role.",
        )

    base_roles = {UserRole.RESEARCHER, UserRole.STARTUP_FOUNDER}
    effective_orig_role = user.original_role or user.role
    if (
        data.role in base_roles
        and effective_orig_role in base_roles
        and data.role != effective_orig_role
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot change a user's role between Researcher and Startup Founder. They can only promote them to Innovation Manager or Admin, or demote them back to their original registered role.",
        )

    was = user.role.value
    user.role = data.role
    audit.record(db, audit_model.ROLE_CHANGE, admin, user,
                 detail=f"{was} -> {data.role.value}")
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}/superuser", response_model=UserResponse)
def set_superuser(
    user_id: int,
    data: SuperuserUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_super_admin()),
):
    """Grant or withdraw the authority to manage other administrators."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if data.is_superuser and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only an administrator can be made super-admin. Promote this "
                   "account to Administrator first.",
        )
    if not data.is_superuser and user.is_superuser and count_super_admins(db) == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This is the only super-admin. Grant it to another "
                   "administrator before removing it here.",
        )

    if user.is_superuser != data.is_superuser:
        user.is_superuser = data.is_superuser
        audit.record(db, audit_model.GRANT_SUPER if data.is_superuser
                     else audit_model.REVOKE_SUPER, admin, user)
        db.commit()
        db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role(UserRole.ADMIN)),
):
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account from here. Use 'Delete my account' instead.",
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not is_super_admin(admin) and user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the super-admin can delete other administrator accounts.",
        )

    audit.record(db, audit_model.DELETE_USER, admin, user, detail=user.role.value)
    db.delete(user)
    db.commit()
