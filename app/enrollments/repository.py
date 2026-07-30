"""Yozilishlar uchun DB so'rovlari."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.enrollments.models import (
    NON_TERMINAL_STATUSES,
    OCCUPYING_STATUSES,
    Enrollment,
    EnrollmentStatus,
)


async def get_by_id(session: AsyncSession, enrollment_id: uuid.UUID) -> Enrollment | None:
    return await session.get(Enrollment, enrollment_id)


async def get_open_enrollment(
    session: AsyncSession, student_id: uuid.UUID, group_id: uuid.UUID
) -> Enrollment | None:
    """Student shu guruhda hali yakunlanmagan yozuvga egami — shuni qaytaradi."""
    query = select(Enrollment).where(
        Enrollment.student_id == student_id,
        Enrollment.group_id == group_id,
        Enrollment.status.in_(NON_TERMINAL_STATUSES),
    )
    return await session.scalar(query)


async def count_occupied_seats(session: AsyncSession, group_id: uuid.UUID) -> int:
    """Guruhda band bo'lgan joylar soni: awaiting_payment + active."""
    query = (
        select(func.count())
        .select_from(Enrollment)
        .where(
            Enrollment.group_id == group_id,
            Enrollment.status.in_(OCCUPYING_STATUSES),
        )
    )
    return await session.scalar(query) or 0


async def list_for_group(
    session: AsyncSession,
    group_id: uuid.UUID,
    statuses: tuple[EnrollmentStatus, ...] | None = None,
) -> list[Enrollment]:
    query = (
        select(Enrollment)
        .where(Enrollment.group_id == group_id)
        .order_by(Enrollment.requested_at)
    )
    if statuses is not None:
        query = query.where(Enrollment.status.in_(statuses))
    return list(await session.scalars(query))


async def list_waitlist(session: AsyncSession, group_id: uuid.UUID) -> list[Enrollment]:
    """Navbatdagi studentlar — pozitsiya bo'yicha tartiblangan."""
    query = (
        select(Enrollment)
        .where(
            Enrollment.group_id == group_id,
            Enrollment.status == EnrollmentStatus.waitlisted,
        )
        .order_by(Enrollment.waitlist_position)
    )
    return list(await session.scalars(query))


async def list_for_student(session: AsyncSession, student_id: uuid.UUID) -> list[Enrollment]:
    query = (
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .order_by(Enrollment.requested_at.desc())
    )
    return list(await session.scalars(query))


async def list_all(
    session: AsyncSession,
    group_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    status: EnrollmentStatus | None = None,
) -> list[Enrollment]:
    query = select(Enrollment).order_by(Enrollment.requested_at.desc())
    if group_id is not None:
        query = query.where(Enrollment.group_id == group_id)
    if student_id is not None:
        query = query.where(Enrollment.student_id == student_id)
    if status is not None:
        query = query.where(Enrollment.status == status)
    return list(await session.scalars(query))
