import getpass

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import hash_password
from app.utils.enums import UserRole


def create_admin():
    db: Session = SessionLocal()

    try:
        email = input("Admin email: ").strip().lower()
        full_name = input("Admin full name: ").strip()
        password = getpass.getpass("Admin password: ")

        if len(password) < 8:
            print("Password must contain at least 8 characters.")
            return

        existing = db.query(User).filter(
            User.email == email
        ).first()

        if existing:
            print("An account with this email already exists.")
            return

        admin = User(
            full_name=full_name,
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            is_verified=True,
        )

        db.add(admin)
        db.commit()

        print("Super Admin created successfully.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    create_admin()
