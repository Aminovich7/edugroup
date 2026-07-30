"""To'lovlar uchun DB so'rovlari."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.courses.models import Course
from app.enrollments.models import Enrollment
from app.groups.models import Group
from app.payments.models import Installment, Payment, PaymentPlan, PaymentStatus


async def get_payment(session: AsyncSession, payment_id: uuid.UUID) -> Payment | None:
    return await session.get(Payment, payment_id)


async def get_installment(
    session: AsyncSession, installment_id: uuid.UUID
) -> Installment | None:
    return await session.get(Installment, installment_id)


async def get_plan_by_enrollment(
    session: AsyncSession, enrollment_id: uuid.UUID
) -> PaymentPlan | None:
    query = select(PaymentPlan).where(PaymentPlan.enrollment_id == enrollment_id)
    return await session.scalar(query)


async def list_for_student(session: AsyncSession, student_id: uuid.UUID) -> list[Payment]:
    query = (
        select(Payment)
        .where(Payment.student_id == student_id)
        .order_by(Payment.created_at.desc())
    )
    return list(await session.scalars(query))


async def has_confirmed_payment(session: AsyncSession, enrollment_id: uuid.UUID) -> bool:
    query = select(Payment.id).where(
        Payment.enrollment_id == enrollment_id,
        Payment.status == PaymentStatus.confirmed,
    )
    return await session.scalar(query) is not None


async def list_payments(
    session: AsyncSession,
    status: PaymentStatus | None = None,
    group_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    subject: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Payment], int, Decimal]:
    """Filtrlangan to'lovlar, ularning soni va umumiy summasini qaytaradi."""
    filters = []
    if status is not None:
        filters.append(Payment.status == status)
    if date_from is not None:
        filters.append(Payment.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        filters.append(Payment.created_at <= datetime.combine(date_to, datetime.max.time()))

    needs_group_join = group_id is not None or teacher_id is not None or subject is not None

    def apply_filters(query):
        if needs_group_join:
            query = (
                query.join(Enrollment, Enrollment.id == Payment.enrollment_id)
                .join(Group, Group.id == Enrollment.group_id)
                .join(Course, Course.id == Group.course_id)
            )
            if group_id is not None:
                query = query.where(Group.id == group_id)
            if teacher_id is not None:
                query = query.where(Group.teacher_id == teacher_id)
            if subject is not None:
                query = query.where(Course.subject.ilike(f"%{subject}%"))
        return query.where(*filters)

    items_query = apply_filters(select(Payment)).order_by(Payment.created_at.desc())
    items = list(await session.scalars(items_query.limit(limit).offset(offset)))

    total_count = await session.scalar(
        apply_filters(select(func.count()).select_from(Payment))
    ) or 0
    total_amount = await session.scalar(
        apply_filters(select(func.coalesce(func.sum(Payment.amount), 0)).select_from(Payment))
    ) or Decimal("0")

    return items, total_count, Decimal(total_amount)
