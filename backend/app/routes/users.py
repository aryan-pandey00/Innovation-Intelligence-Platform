from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_role, is_super_admin
from app.models.user import User, UserRole
from app.schemas.user import UserResponse, RoleUpdate, UserUpdate

router = APIRouter(prefix="/api/users", tags=["Users"])

@router.get("/profile", response_model=UserResponse)
def my_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/all", response_model=list[UserResponse])
def list_all_users(
    db: Session = Depends(get_db),
    _user: User = Depends(require_role(UserRole.ADMIN, UserRole.INNOVATION_MANAGER)),
):
    return db.query(User).all()

@router.patch("/me", response_model=UserResponse)
def update_my_account(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update the signed-in user's own account details. Email and role are
    intentionally not editable here: email is the JWT subject, and roles are
    assigned by an administrator."""
    current_user.full_name = data.full_name
    db.commit()
    db.refresh(current_user)
    return current_user

@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.delete(current_user)
    db.commit()

@router.get("/researcher-only")
def researcher_dashboard(
    current_user: User = Depends(require_role(UserRole.RESEARCHER, UserRole.ADMIN)),
):
    return {"message": f"Welcome researcher {current_user.full_name}"}

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

    user.role = data.role
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

    db.delete(user)
    db.commit()
