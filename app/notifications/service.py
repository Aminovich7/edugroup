"""Bildirishnoma biznes-logikasi.

Bildirishnomalar ATAYLAB sinxron yaratiladi — ular oddiy DB yozuvi bo'lib,
hech qanday tashqi I/O (email/SMS) qilmaydi. Ularni Celery navbatiga qo'yish
faqat "to'lov tasdiqlandi, lekin bildirishnoma hali yo'q" kabi vaqtinchalik
nomuvofiqlikni keltirib chiqarardi. Shuning uchun ular chaqiruvchi
service funksiyasi bilan bir xil tranzaksiyada yoziladi (TZ 8.2).
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.notifications import repository
from app.notifications.models import Notification, NotificationType
from app.users.models import User


async def create_notification(
    session: AsyncSession,
    user_id: uuid.UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    related_entity_type: str | None = None,
    related_entity_id: uuid.UUID | None = None,
) -> Notification:
    """Boshqa modullarning service qatlami shu funksiyani chaqiradi."""
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    )
    session.add(notification)
    await session.flush()
    return notification


def create_notification_sync(
    session: Session,
    user_id: uuid.UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    related_entity_type: str | None = None,
    related_entity_id: uuid.UUID | None = None,
) -> Notification:
    """Yuqoridagi funksiyaning Celery task'lari uchun sinxron varianti."""
    notification = Notification(
        user_id=user_id,
        type=notification_type,
        title=title,
        message=message,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
    )
    session.add(notification)
    session.flush()
    return notification


async def list_my_notifications(
    session: AsyncSession, current_user: User, is_read: bool | None = None
) -> list[Notification]:
    return await repository.list_for_user(session, current_user.id, is_read)


async def count_unread(session: AsyncSession, current_user: User) -> int:
    return await repository.count_unread(session, current_user.id)


async def mark_as_read(
    session: AsyncSession, notification_id: uuid.UUID, current_user: User
) -> Notification:
    notification = await repository.get_by_id(session, notification_id)
    if notification is None:
        raise NotFoundError("Bildirishnoma topilmadi")
    if notification.user_id != current_user.id:
        raise PermissionDeniedError("Bu bildirishnoma sizga tegishli emas")

    notification.is_read = True
    await session.commit()
    await session.refresh(notification)
    return notification


async def mark_all_as_read(session: AsyncSession, current_user: User) -> int:
    """Barcha o'qilmagan bildirishnomalarni o'qilgan deb belgilaydi."""
    updated_count = await repository.mark_all_read(session, current_user.id)
    await session.commit()
    return updated_count
