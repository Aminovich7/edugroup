"""Veb-sahifalar uchun autentifikatsiya: token httpOnly cookie'dan o'qiladi.

JSON API'dan farqi shundaki, bu yerda brauzer hech qanday header qo'shmaydi —
token cookie'da keladi va JavaScript unga umuman kira olmaydi.
"""

from typing import Annotated

from fastapi import Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cookies import ACCESS_TOKEN_COOKIE, REFRESH_TOKEN_COOKIE, set_auth_cookies
from app.core.dependencies import load_user_from_access_token
from app.core.exceptions import AppError, NotAuthenticatedError
from app.db.session import get_session
from app.users import service as users_service
from app.users.models import User

WebSession = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user_from_cookie(
    request: Request, response: Response, session: WebSession
) -> User:
    """Joriy foydalanuvchi. Token bo'lmasa yoki yaroqsiz bo'lsa — 401 (login'ga redirect)."""
    user = await _load_user(request, response, session)
    if user is None:
        raise NotAuthenticatedError()
    return user


async def get_optional_user_from_cookie(
    request: Request, response: Response, session: WebSession
) -> User | None:
    """Ommaviy sahifalar uchun: foydalanuvchi bo'lsa qaytaradi, bo'lmasa None."""
    return await _load_user(request, response, session)


CurrentWebUser = Annotated[User, Depends(get_current_user_from_cookie)]
OptionalWebUser = Annotated[User | None, Depends(get_optional_user_from_cookie)]


async def _load_user(
    request: Request, response: Response, session: AsyncSession
) -> User | None:
    """Access token bilan urinadi; u eskirgan bo'lsa refresh token orqali yangilaydi.

    Shu sababli foydalanuvchi 30 daqiqadan keyin ham qayta login qilishi shart emas —
    yangilanish sahifa yuklanayotganda sezilmasdan bajariladi.
    """
    access_token = request.cookies.get(ACCESS_TOKEN_COOKIE)
    if access_token:
        try:
            return await load_user_from_access_token(session, access_token)
        except AppError:
            pass

    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE)
    if not refresh_token:
        return None
    try:
        user, new_access_token, new_refresh_token = await users_service.refresh_token_pair(
            session, refresh_token
        )
    except AppError:
        return None

    set_auth_cookies(response, new_access_token, new_refresh_token)
    return user
