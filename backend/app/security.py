
from datetime import datetime, timedelta, timezone

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import User


password_hasher = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login"
)


# --------------------------------------------------
# PASSWORD HASHING
# --------------------------------------------------

def hash_password(password: str) -> str:
    """Hash a password using Argon2."""
    return password_hasher.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """Verify a password against its stored hash."""
    return password_hasher.verify(
        plain_password,
        hashed_password,
    )


# --------------------------------------------------
# JWT TOKEN GENERATION
# --------------------------------------------------

def create_access_token(user_id: int) -> str:
    """Create a signed JWT access token."""

    if len(settings.jwt_secret_key) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must contain at least 32 characters"
        )

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(
            minutes=settings.access_token_expire_minutes
        ),
        "type": "access",
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


# --------------------------------------------------
# JWT TOKEN VALIDATION
# --------------------------------------------------

def decode_access_token(token: str) -> int | None:
    """Validate JWT signature and return its user ID."""

    if len(settings.jwt_secret_key) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must contain at least 32 characters"
        )

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            options={
                "require": ["sub", "iat", "nbf", "exp", "type"]
            },
        )

        if payload.get("type") != "access":
            return None

        subject = payload.get("sub")

        if not isinstance(subject, str):
            return None

        user_id = int(subject)

        return user_id if user_id > 0 else None

    except (InvalidTokenError, ValueError, TypeError):
        return None


# --------------------------------------------------
# AUTHENTICATION - CURRENT USER
# --------------------------------------------------

def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate the JWT and retrieve the active user."""

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = decode_access_token(token)

    if user_id is None:
        raise credentials_exception

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if user is None or not user.is_active:
        raise credentials_exception

    return user


# --------------------------------------------------
# AUTHORIZATION - ROLE BASED ACCESS CONTROL
# --------------------------------------------------

def require_roles(*allowed_roles: str):
    """Create a dependency that restricts access by user role."""

    valid_roles = {"Admin", "Agent", "Viewer"}

    if not allowed_roles or not set(allowed_roles).issubset(valid_roles):
        raise ValueError("Invalid or missing allowed roles")

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )

        return current_user

    return role_checker
