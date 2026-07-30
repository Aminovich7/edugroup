"""Foydalanuvchi va refresh token uchun DB so'rovlari."""

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.users.models import RefreshToken, StudentProfile, TeacherProfile, User, UserRole, UserStatus


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_email(session: AsyncSession, email: str) -> User | None:
    query = select(User).where(User.email == email)
    return await session.scalar(query)


async def list_users(
    session: AsyncSession,
    role: UserRole | None = None,
    status: UserStatus | None = None,
) -> list[User]:
    query = select(User).order_by(User.created_at.desc())
    if role is not None:
        query = query.where(User.role == role)
    if status is not None:
        query = query.where(User.status == status)
    return list(await session.scalars(query))


async def get_teacher_profile(session: AsyncSession, user_id: uuid.UUID) -> TeacherProfile | None:
    query = select(TeacherProfile).where(TeacherProfile.user_id == user_id)
    return await session.scalar(query)


async def get_student_profile(session: AsyncSession, user_id: uuid.UUID) -> StudentProfile | None:
    query = select(StudentProfile).where(StudentProfile.user_id == user_id)
    return await session.scalar(query)


async def get_refresh_token(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    query = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    return await session.scalar(query)


async def revoke_all_refresh_tokens(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Reuse aniqlanganda yoki blokirovkada foydalanuvchining barcha sessiyalarini yopadi."""
    statement = (
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
        .values(revoked=True)
    )
    await session.execute(statement)
