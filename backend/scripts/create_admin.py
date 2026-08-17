"""Create or promote an administrator, and recover one who is locked out."""
import datetime as dt
import sys

from app.core.database import SessionLocal, engine
from app.core.schema import ensure_schema
from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import validate_new_password

_FLAGS = {"--super", "--reset-password"}


def main():
    ensure_schema(engine)

    args = [a for a in sys.argv[1:] if a not in _FLAGS]
    make_super = "--super" in sys.argv[1:]
    reset_only = "--reset-password" in sys.argv[1:]

    if len(args) >= 3:
        email, full_name, password = args[0], args[1], args[2]
    elif reset_only and len(args) == 2:
        email, full_name, password = args[0], "", args[1]
    else:
        email = input("Admin email: ").strip()
        full_name = "" if reset_only else input("Full name: ").strip()
        password = input("Password: ").strip()

    if not email or not password:
        print("Email and password are required.")
        sys.exit(1)

    try:
        validate_new_password(password, email=email, full_name=full_name or None)
    except ValueError as exc:
        print(str(exc))
        sys.exit(1)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()

        if reset_only:
            if user is None:
                print(f"No account with email '{email}'. Nothing to reset.")
                sys.exit(1)
            user.hashed_password = hash_password(password)
            user.password_changed_at = dt.datetime.now(dt.timezone.utc)
            db.commit()
            print(f"Password reset for '{email}' ({user.role.value}). "
                  "Any existing sessions for that account are now invalid.")
            print("Role and super-admin status were left unchanged.")
            return

        if user:
            was = user.role.value
            user.role = UserRole.ADMIN
            if make_super:
                user.is_superuser = True
            db.commit()
            print(f"Existing user '{email}' ({was}) promoted to ADMIN"
                  + (" and SUPER-ADMIN." if make_super else "."))
            print("Their password was NOT changed. Use --reset-password for that.")
        else:
            user = User(
                email=email,
                full_name=full_name or "Administrator",
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
                original_role=UserRole.ADMIN,
                is_superuser=make_super,
            )
            db.add(user)
            db.commit()
            print(f"{'Super-admin' if make_super else 'Admin'} account created: {email}")

        supers = db.query(User).filter(User.is_superuser.is_(True)).count()
        if supers == 0:
            print("WARNING: no super-admin exists. Nobody can manage administrator "
                  "accounts until one is granted with --super.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
