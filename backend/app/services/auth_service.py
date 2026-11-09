
from sqlalchemy.orm import Session

from app.config import settings
from app.models import User
from app.security import hash_password


def bootstrap_admin(db: Session) -> User:
    """
    Create the initial Admin account from environment credentials.

    This function is idempotent:
    - Existing Admin with the configured email is preserved.
    - Existing non-Admin account is never promoted automatically.
    - A different existing Admin prevents accidental duplicate bootstrap.
    """

    email = settings.admin_email.strip().lower()
    password = settings.admin_password
    full_name = settings.admin_full_name.strip()

    if not email or not password or not full_name:
        raise RuntimeError(
            "ADMIN_EMAIL, ADMIN_PASSWORD and ADMIN_FULL_NAME must be configured"
        )

    if len(password) < 12:
        raise RuntimeError(
            "ADMIN_PASSWORD must contain at least 12 characters"
        )

    existing_user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if existing_user:
        if existing_user.role != "Admin":
            raise RuntimeError(
                "Configured admin email already belongs to a non-Admin account"
            )

        return existing_user

    existing_admin = (
        db.query(User)
        .filter(User.role == "Admin")
        .first()
    )

    if existing_admin:
        raise RuntimeError(
            "An Admin account already exists with a different email. "
            "Verify ADMIN_EMAIL configuration."
        )

    admin = User(
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        role="Admin",
        is_active=True,
    )

    try:
        db.add(admin)
        db.commit()
        db.refresh(admin)
        return admin

    except Exception:
        db.rollback()
        raise
