"""Parol hashlash va JWT token bilan ishlash (python-jose, HS256)."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


def hash_password(plain_password: str) -> str:
    return password_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_context.verify(plain_password, hashed_password)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    """30 daqiqalik access token — foydalanuvchini aniqlash uchun."""
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    return _encode_token(
        {
            "sub": str(user_id),
            "role": role,
            "type": ACCESS_TOKEN_TYPE,
            "exp": expires_at,
        }
    )


def create_refresh_token(user_id: uuid.UUID) -> tuple[str, datetime]:
    """7 kunlik refresh token va uning tugash vaqtini qaytaradi.

    Har bir token noyob bo'lishi uchun ichiga tasodifiy `jti` qo'yiladi —
    aks holda bir xil sekundda yaratilgan ikki token bir xil bo'lib qolardi
    va bazadagi token_hash unique cheklovini buzardi.
    """
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    token = _encode_token(
        {
            "sub": str(user_id),
            "jti": str(uuid.uuid4()),
            "type": REFRESH_TOKEN_TYPE,
            "exp": expires_at,
        }
    )
    return token, expires_at


def decode_token(token: str, expected_type: str) -> dict[str, Any] | None:
    """Tokenni tekshiradi. Yaroqsiz, muddati o'tgan yoki turi mos kelmasa — None."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
    if payload.get("type") != expected_type:
        return None
    return payload


def hash_refresh_token(token: str) -> str:
    """Bazada tokenning o'zi emas, faqat SHA-256 hash'i saqlanadi."""
    return hashlib.sha256(token.encode()).hexdigest()


def _encode_token(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
