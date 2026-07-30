"""Yozilish biznes-logikasi: guruhga yozilish, navbat (waitlist) va bekor qilish.

Asosiy qoidalar:
- Guruh "to'la" hisoblanadi, agar awaiting_payment + active yozilishlar soni
  capacity'ga yetsa. To'lov kutayotgan joy ham band hisoblanadi, aks holda
  bitta joy bir necha studentga va'da qilinib qolardi.
- Guruh to'la bo'lsa so'rov rad etilmaydi — student navbatga (waitlisted) qo'yiladi.
- Joy bo'shaganda (bekor qilish yoki muddat tugashi) navbatdagi birinchi student
  avtomatik awaiting_payment holatiga ko'tariladi.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.enrollments import repository
from app.enrollments.models import Enrollment, EnrollmentStatus
from app.groups import repository as groups_repository
from app.groups.models import Group, GroupStatus
from app.notifications import service as notifications_service
from app.notifications.models import NotificationType
from app.users.models import User, UserRole

CANCELLABLE_STATUSES = (
    EnrollmentStatus.awaiting_payment,
    EnrollmentStatus.waitlisted,
    EnrollmentStatus.active,
)


async def request_enrollment(
    session: AsyncSession, group_id: uuid.UUID, student: User
) -> Enrollment:
    """Student guruhga yozilish so'rovini yuboradi.

    Guruhda joy bo'lsa — awaiting_payment, to'la bo'lsa — waitlisted.
    """
    group = await groups_repository.get_by_id(session, group_id)
    if group is None or group.is_deleted:
        raise NotFoundError("Guruh topilmadi")
    if group.status != GroupStatus.active:
        raise BusinessRuleError("Bu guruhga hozir yozilish mumkin emas")

    existing = await repository.get_open_enrollment(session, student.id, group_id)
    if existing is not None:
        raise BusinessRuleError("Siz bu guruhga allaqachon yozilgansiz")

    occupied_seats = await repository.count_occupied_seats(session, group_id)
    is_group_full = occupied_seats >= group.capacity

    if is_group_full:
        waitlist = await repository.list_waitlist(session, group_id)
        status = EnrollmentStatus.waitlisted
        waitlist_position = len(waitlist) + 1
    else:
        status = EnrollmentStatus.awaiting_payment
        waitlist_position = None

    enrollment = Enrollment(
        student_id=student.id,
        group_id=group_id,
        status=status,
        requested_at=datetime.now(UTC),
        waitlist_position=waitlist_position,
    )
    session.add(enrollment)
    await session.commit()
    await session.refresh(enrollment)
    return enrollment


async def cancel_enrollment(
    session: AsyncSession,
    enrollment_id: uuid.UUID,
    current_user: User,
    reason: str | None = None,
) -> Enrollment:
    """Yozilishni bekor qiladi va bo'shagan joyga navbatdagi studentni ko'taradi.

    Student o'z yozilishini istalgan holatda bekor qila oladi; manager/superadmin
    esa istalgan studentniki uchun, lekin majburiy sabab bilan.
    """
    enrollment = await repository.get_by_id(session, enrollment_id)
    if enrollment is None:
        raise NotFoundError("Yozilish topilmadi")

    is_owner = enrollment.student_id == current_user.id
    is_staff = current_user.role in (UserRole.manager, UserRole.superadmin)
    if not is_owner and not is_staff:
        raise PermissionDeniedError("Bu yozilishni bekor qilish huquqingiz yo'q")
    if is_staff and not is_owner and not reason:
        raise BusinessRuleError("Bekor qilish sababini ko'rsating")
    if enrollment.status not in CANCELLABLE_STATUSES:
        raise BusinessRuleError("Bu yozilish allaqachon yakunlangan")

    was_occupying_seat = enrollment.status in (
        EnrollmentStatus.awaiting_payment,
        EnrollmentStatus.active,
    )

    enrollment.status = EnrollmentStatus.cancelled
    enrollment.cancelled_at = datetime.now(UTC)
    enrollment.cancel_reason = reason
    enrollment.waitlist_position = None
    await session.flush()

    if was_occupying_seat:
        await promote_next_waitlisted(session, enrollment.group_id)
    else:
        await _reindex_waitlist(session, enrollment.group_id)

    await session.commit()
    await session.refresh(enrollment)
    return enrollment


async def promote_next_waitlisted(
    session: AsyncSession, group_id: uuid.UUID
) -> Enrollment | None:
    """Navbatdagi birinchi studentni bo'shagan joyga ko'taradi.

    Bekor qilish, majburiy bekor qilish va muddat tugashi — uchala holatda ham
    shu funksiya chaqiriladi.
    """
    group = await groups_repository.get_by_id(session, group_id)
    if group is None:
        return None

    occupied_seats = await repository.count_occupied_seats(session, group_id)
    if occupied_seats >= group.capacity:
        return None

    waitlist = await repository.list_waitlist(session, group_id)
    if not waitlist:
        return None

    promoted = waitlist[0]
    promoted.status = EnrollmentStatus.awaiting_payment
    promoted.waitlist_position = None
    await session.flush()

    await notifications_service.create_notification(
        session,
        user_id=promoted.student_id,
        notification_type=NotificationType.waitlist_promoted,
        title="Guruhda joy bo'shadi",
        message=f"'{group.name}' guruhida joy bo'shadi. To'lovni amalga oshiring.",
        related_entity_type="enrollment",
        related_entity_id=promoted.id,
    )
    await _reindex_waitlist(session, group_id)
    return promoted


async def list_my_enrollments(session: AsyncSession, student: User) -> list[Enrollment]:
    return await repository.list_for_student(session, student.id)


async def list_all_enrollments(
    session: AsyncSession,
    group_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    status: EnrollmentStatus | None = None,
) -> list[Enrollment]:
    """Manager/superadmin uchun — barcha yozilishlar, filtrlar bilan."""
    return await repository.list_all(
        session, group_id=group_id, student_id=student_id, status=status
    )


async def get_active_enrollment(
    session: AsyncSession, student_id: uuid.UUID, group_id: uuid.UUID
) -> Enrollment | None:
    """Studentning shu guruhdagi active yozilishi (video ochish tekshiruvi uchun)."""
    query = select(Enrollment).where(
        Enrollment.student_id == student_id,
        Enrollment.group_id == group_id,
        Enrollment.status == EnrollmentStatus.active,
    )
    return await session.scalar(query)


# --- Celery task uchun sinxron variant ---------------------------------------


def expire_stale_enrollments_sync(session: Session, expiry_hours: int) -> int:
    """Muddati o'tgan yozilishlarni expired qiladi va navbatni ko'taradi.

    Bu funksiya Celery task'i tomonidan sinxron sessiya bilan chaqiriladi —
    shuning uchun yuqoridagi async funksiyalardan alohida yozilgan.
    Nechta yozilish expired bo'lganini qaytaradi.
    """
    deadline = datetime.now(UTC) - timedelta(hours=expiry_hours)
    stale_query = select(Enrollment).where(
        Enrollment.status.in_(
            (EnrollmentStatus.awaiting_payment, EnrollmentStatus.waitlisted)
        ),
        Enrollment.requested_at < deadline,
    )
    stale_enrollments = list(session.scalars(stale_query))

    for enrollment in stale_enrollments:
        freed_a_seat = enrollment.status == EnrollmentStatus.awaiting_payment
        group_id = enrollment.group_id

        enrollment.status = EnrollmentStatus.expired
        enrollment.waitlist_position = None
        session.flush()

        notifications_service.create_notification_sync(
            session,
            user_id=enrollment.student_id,
            notification_type=NotificationType.enrollment_expired,
            title="Yozilish muddati tugadi",
            message="To'lov belgilangan muddatda amalga oshirilmagani uchun so'rov bekor qilindi.",
            related_entity_type="enrollment",
            related_entity_id=enrollment.id,
        )

        if freed_a_seat:
            _promote_next_waitlisted_sync(session, group_id)
        else:
            _reindex_waitlist_sync(session, group_id)

    session.commit()
    return len(stale_enrollments)


# --- Ichki yordamchi funksiyalar --------------------------------------------


async def _reindex_waitlist(session: AsyncSession, group_id: uuid.UUID) -> None:
    """Navbat pozitsiyalarini 1, 2, 3 ... qilib qayta raqamlaydi."""
    waitlist = await repository.list_waitlist(session, group_id)
    for position, enrollment in enumerate(waitlist, start=1):
        enrollment.waitlist_position = position
    await session.flush()


def _promote_next_waitlisted_sync(session: Session, group_id: uuid.UUID) -> None:
    """promote_next_waitlisted() ning Celery uchun sinxron nusxasi."""
    group = session.get(Group, group_id)
    if group is None:
        return

    occupied_seats = _count_occupied_seats_sync(session, group_id)
    if occupied_seats >= group.capacity:
        return

    waitlist = _list_waitlist_sync(session, group_id)
    if not waitlist:
        return

    promoted = waitlist[0]
    promoted.status = EnrollmentStatus.awaiting_payment
    promoted.waitlist_position = None
    session.flush()

    notifications_service.create_notification_sync(
        session,
        user_id=promoted.student_id,
        notification_type=NotificationType.waitlist_promoted,
        title="Guruhda joy bo'shadi",
        message=f"'{group.name}' guruhida joy bo'shadi. To'lovni amalga oshiring.",
        related_entity_type="enrollment",
        related_entity_id=promoted.id,
    )
    _reindex_waitlist_sync(session, group_id)


def _reindex_waitlist_sync(session: Session, group_id: uuid.UUID) -> None:
    for position, enrollment in enumerate(_list_waitlist_sync(session, group_id), start=1):
        enrollment.waitlist_position = position
    session.flush()


def _list_waitlist_sync(session: Session, group_id: uuid.UUID) -> list[Enrollment]:
    query = (
        select(Enrollment)
        .where(
            Enrollment.group_id == group_id,
            Enrollment.status == EnrollmentStatus.waitlisted,
        )
        .order_by(Enrollment.waitlist_position)
    )
    return list(session.scalars(query))


def _count_occupied_seats_sync(session: Session, group_id: uuid.UUID) -> int:
    query = select(Enrollment).where(
        Enrollment.group_id == group_id,
        Enrollment.status.in_(
            (EnrollmentStatus.awaiting_payment, EnrollmentStatus.active)
        ),
    )
    return len(list(session.scalars(query)))
