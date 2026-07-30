"""JSON API uchun autentifikatsiya va rol tekshiruvi dependency'lari.

Bu qatlam tokenni `Authorization: Bearer ...` header'idan oladi (tashqi/mobil
klientlar va testlar uchun). Web sahifalar tokenni cookie'dan oladi —
app/web/dependencies.py ga qarang.
"""

import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotAuthenticatedError, PermissionDeniedError
from app.core.security import ACCESS_TOKEN_TYPE, decode_token
from app.db.session import get_session
from app.users import repository as users_repository
from app.users.models import User, UserRole

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(request: Request, session: SessionDep) -> User:
    """Bearer token orqali joriy foydalanuvchini qaytaradi."""
    token = _read_bearer_token(request)
    if token is None:
        raise NotAuthenticatedError()
    return await load_user_from_access_token(session, token)


async def load_user_from_access_token(session: AsyncSession, token: str) -> User:
    """Access tokenni tekshirib, mos foydalanuvchini bazadan oladi.

    Web qatlami ham xuddi shu funksiyani ishlatadi — farq faqat tokenni
    qayerdan olishda (header yoki cookie).
    """
    payload = decode_token(token, ACCESS_TOKEN_TYPE)
    if payload is None:
        raise NotAuthenticatedError("Token yaroqsiz yoki muddati o'tgan")

    user = await users_repository.get_by_id(session, uuid.UUID(payload["sub"]))
    if user is None:
        raise NotAuthenticatedError("Foydalanuvchi topilmadi")
    if not user.is_active:
        raise PermissionDeniedError("Akkaunt bloklangan")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed_roles: UserRole):
    """Faqat ko'rsatilgan rollarga ruxsat beruvchi dependency yaratadi."""

    async def check_role(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise PermissionDeniedError()
        return current_user

    return check_role


# Routerlarda to'g'ridan-to'g'ri ishlatiladigan tayyor rol-dependency'lar.
StudentUser = Annotated[User, Depends(require_roles(UserRole.student))]
TeacherUser = Annotated[User, Depends(require_roles(UserRole.teacher))]
ManagerOrSuperadmin = Annotated[
    User, Depends(require_roles(UserRole.manager, UserRole.superadmin))
]
SuperadminUser = Annotated[User, Depends(require_roles(UserRole.superadmin))]


def _read_bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    prefix = "Bearer "
    if not header.startswith(prefix):
        return None
    return header[len(prefix):]
