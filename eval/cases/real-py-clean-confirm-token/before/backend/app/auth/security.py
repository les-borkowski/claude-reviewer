import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import bcrypt
import jwt
from fastapi import HTTPException

from app.core.config import settings
from app.db.base import RoleEnum

if TYPE_CHECKING:
    from app.db.models.api_key import APIKey


# --- Password hashing ---


def hash_password(plain: str) -> str:
    """Hash a plain-text password using bcrypt."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# --- JWT tokens ---


def create_access_token(user_id: uuid.UUID, role: RoleEnum) -> str:
    """Create a short-lived JWT access token."""
    payload = {
        "sub": str(user_id),
        "role": role.value,
        "type": "access",
        "exp": datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def create_refresh_token(user_id: uuid.UUID) -> str:
    """Create a long-lived JWT refresh token."""
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises HTTPException on failure."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def create_password_reset_token(user_id: uuid.UUID) -> str:
    """Create a short-lived JWT token for password reset (1 hour expiry)."""
    payload = {
        "sub": str(user_id),
        "type": "password_reset",
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


def verify_password_reset_token(token: str) -> uuid.UUID:
    """Verify a password reset token and return the user ID."""
    payload = decode_token(token)
    if payload.get("type") != "password_reset":
        raise HTTPException(status_code=400, detail="Invalid token type")
    try:
        return uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid token payload") from exc


# --- API key generation ---


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key. Returns (raw_key, key_hash)."""
    raw_key = secrets.token_urlsafe(32)
    key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt(rounds=12)).decode()
    return raw_key, key_hash


# --- Scope checking ---

SCOPE_HIERARCHY: dict[str, set[str]] = {
    "write:projects": {"read:projects"},
    "write:stories": {"read:stories"},
    "write:tasks": {"read:tasks"},
    "write:comments": {"read:comments"},
    "admin": {
        "admin",  # admin implies itself
        "read:projects",
        "write:projects",
        "read:stories",
        "write:stories",
        "read:tasks",
        "write:tasks",
        "read:comments",
        "write:comments",
    },
}


def check_scope(api_key: "APIKey", required_scope: str) -> bool:
    """Check if an API key has the required scope (considering scope hierarchy)."""
    if api_key.revoked_at is not None:
        return False

    expanded: set[str] = set()
    for scope in api_key.scopes:
        expanded.add(scope)
        expanded.update(SCOPE_HIERARCHY.get(scope, set()))

    return required_scope in expanded
