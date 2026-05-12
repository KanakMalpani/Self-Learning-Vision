from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt
from passlib.context import CryptContext

from app.core.config import settings


def _assert_bcrypt_compatibility() -> None:
    """Fail fast with a clear error when bcrypt is incompatible with passlib 1.7.x."""
    version = getattr(bcrypt, "__version__", "")
    major_str = str(version).split(".", 1)[0]
    try:
        major = int(major_str)
    except ValueError:
        return

    if major >= 5:
        raise RuntimeError(
            "Unsupported bcrypt version detected. "
            "This project requires bcrypt<5 for passlib[bcrypt]==1.7.4 compatibility. "
            "Reinstall with: pip install -r requirements.txt -c constraints.txt"
        )


_assert_bcrypt_compatibility()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TokenError(Exception):
    pass


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(*, subject: str, expires_minutes: int | None = None) -> str:
    minutes = expires_minutes or settings.jwt_access_token_expires_minutes
    expire_at = datetime.now(UTC) + timedelta(minutes=minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire_at,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired token") from exc

    if payload.get("type") != "access" or not payload.get("sub"):
        raise TokenError("Invalid token payload")
    return payload

