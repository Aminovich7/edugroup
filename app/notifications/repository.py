"""Bildirishnomalar uchun DB so'rovlari."""

import uuid

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import Notification


async def get_by_id(session: AsyncSession, notification_id: uuid.UUID) -> Notification | None:
    return await session.get(Notification, notification_id)


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, is_read: bool | None = None
) -> list[Notification]:
    query = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
    )
    if is_read is not None:
        query = query.where(Notification.is_read.is_(is_read))
    return list(await session.scalars(query))


async def count_unread(session: AsyncSession, user_id: uuid.UUID) -> int:
    query = (
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
    )
    return await session.scalar(query) or 0


async def mark_all_read(session: AsyncSession, user_id: uuid.UUID) -> int:
    statement = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True)
    )
    result = await session.execute(statement)
    return result.rowcount or 0
