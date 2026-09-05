"""Mark an account as the public read-only demo, or clear the mark."""
import sys

from app.core.database import SessionLocal, engine
from app.core.schema import ensure_schema
from app.models.user import User, UserRole


def main():
    ensure_schema(engine)

    args = [a for a in sys.argv[1:] if a != "--off"]
    turn_off = "--off" in sys.argv[1:]
    email = args[0] if args else input("Account email: ").strip()

    if not email:
        print("An email is required.")
        sys.exit(1)

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if user is None:
            print(f"No account with email {email}.")
            sys.exit(1)

        # Staff can read every account and the audit log, so their credentials are
        # never publishable however read-only the session is.
        if not turn_off and user.role in (UserRole.ADMIN, UserRole.INNOVATION_MANAGER):
            print(f"Refusing: {email} is {user.role.value}. Only a researcher or "
                  "startup founder may be the public demo.")
            sys.exit(1)

        user.is_demo = not turn_off
        db.commit()
        state = "cleared" if turn_off else "set"
        print(f"Demo flag {state} for {email} ({user.role.value}).")
        if not turn_off:
            print("This account can now only answer GET requests.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
