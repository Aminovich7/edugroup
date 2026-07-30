"""Hisobot uchun agregatsiya so'rovlari.

Bu modulda o'zgartiruvchi amal yo'q — faqat sanash va yig'indi hisoblash.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.courses.models import Course, CourseStatus
from app.enrollments.models import Enrollment, EnrollmentStatus
from app.groups.models import Group, GroupStatus
from app.lessons.models import Lesson
from app.payments.models import Payment, PaymentStatus
from app.reports.schemas import (
    GroupReportResponse,
    OverviewResponse,
    RevenueReportResponse,
    RevenueRow,
    TeacherReportResponse,
)
from app.users.models import User, UserRole


async def get_overview(session: AsyncSession) -> OverviewResponse:
    """Tizim bo'yicha umumiy statistika (faqat superadmin uchun)."""
    return OverviewResponse(
        total_users=await _count(session, User),
        total_students=await _count(session, User, User.role == UserRole.student),
        total_teachers=await _count(session, User, User.role == UserRole.teacher),
        total_managers=await _count(session, User, User.role == UserRole.manager),
        active_courses=await _count(
            session, Course, Course.status == CourseStatus.active, Course.deleted_at.is_(None)
        ),
        active_groups=await _count(
            session, Group, Group.status == GroupStatus.active, Group.deleted_at.is_(None)
        ),
        active_enrollments=await _count(
            session, Enrollment, Enrollment.status == EnrollmentStatus.active
        ),
        waitlisted_enrollments=await _count(
            session, Enrollment, Enrollment.status == EnrollmentStatus.waitlisted
        ),
        total_revenue=await _confirmed_revenue(session),
    )


async def get_revenue_report(
    session: AsyncSession,
    date_from: date | None = None,
    date_to: date | None = None,
    group_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
) -> RevenueReportResponse:
    """Tasdiqlangan to'lovlar bo'yicha daromad — guruhlar kesimida."""
    query = (
        select(
            Group.id,
            Group.name,
            User.full_name,
            func.count(Payment.id),
            func.coalesce(func.sum(Payment.amount), 0),
        )
        .join(Enrollment, Enrollment.id == Payment.enrollment_id)
        .join(Group, Group.id == Enrollment.group_id)
        .join(User, User.id == Group.teacher_id)
        .where(Payment.status == PaymentStatus.confirmed)
        .group_by(Group.id, Group.name, User.full_name)
        .order_by(func.sum(Payment.amount).desc())
    )
    if date_from is not None:
        query = query.where(Payment.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        query = query.where(Payment.created_at <= datetime.combine(date_to, datetime.max.time()))
    if group_id is not None:
        query = query.where(Group.id == group_id)
    if teacher_id is not None:
        query = query.where(Group.teacher_id == teacher_id)

    rows = [
        RevenueRow(
            group_id=row[0],
            group_name=row[1],
            teacher_name=row[2],
            payments_count=row[3],
            amount=Decimal(row[4]),
        )
        for row in (await session.execute(query)).all()
    ]
    return RevenueReportResponse(
        rows=rows,
        total_amount=sum((row.amount for row in rows), Decimal("0")),
        total_count=sum(row.payments_count for row in rows),
    )


async def get_group_report(
    session: AsyncSession, group_id: uuid.UUID, viewer: User
) -> GroupReportResponse:
    """Bitta guruh bo'yicha to'liq hisobot."""
    group = await session.get(Group, group_id)
    if group is None or group.is_deleted:
        raise NotFoundError("Guruh topilmadi")
    _ensure_can_view_group_report(group, viewer)

    course = await session.get(Course, group.course_id)
    teacher = await session.get(User, group.teacher_id)

    return GroupReportResponse(
        group_id=group.id,
        group_name=group.name,
        course_title=course.title if course else "—",
        teacher_name=teacher.full_name if teacher else "—",
        capacity=group.capacity,
        active_students=await _count_enrollments(session, group_id, EnrollmentStatus.active),
        awaiting_payment_students=await _count_enrollments(
            session, group_id, EnrollmentStatus.awaiting_payment
        ),
        waitlisted_students=await _count_enrollments(
            session, group_id, EnrollmentStatus.waitlisted
        ),
        lessons_count=await _count(
            session, Lesson, Lesson.group_id == group_id, Lesson.deleted_at.is_(None)
        ),
        total_revenue=await _confirmed_revenue(session, group_id=group_id),
    )


async def get_teacher_report(
    session: AsyncSession, teacher_id: uuid.UUID
) -> TeacherReportResponse:
    """Bitta teacher bo'yicha statistika (manager va superadmin ko'radi)."""
    teacher = await session.get(User, teacher_id)
    if teacher is None or teacher.role != UserRole.teacher:
        raise NotFoundError("Teacher topilmadi")

    group_ids = list(
        await session.scalars(
            select(Group.id).where(Group.teacher_id == teacher_id, Group.deleted_at.is_(None))
        )
    )

    active_students = 0
    lessons_count = 0
    if group_ids:
        active_students = await _count(
            session,
            Enrollment,
            Enrollment.group_id.in_(group_ids),
            Enrollment.status == EnrollmentStatus.active,
        )
        lessons_count = await _count(
            session, Lesson, Lesson.group_id.in_(group_ids), Lesson.deleted_at.is_(None)
        )

    return TeacherReportResponse(
        teacher_id=teacher.id,
        teacher_name=teacher.full_name,
        groups_count=len(group_ids),
        active_students=active_students,
        lessons_count=lessons_count,
        total_revenue=await _confirmed_revenue(session, teacher_id=teacher_id),
    )


# --- Ichki yordamchi funksiyalar --------------------------------------------


def _ensure_can_view_group_report(group: Group, viewer: User) -> None:
    if viewer.role in (UserRole.manager, UserRole.superadmin):
        return
    if viewer.role == UserRole.teacher and group.teacher_id == viewer.id:
        return
    raise PermissionDeniedError("Bu hisobotni ko'rish huquqingiz yo'q")


async def _count(session: AsyncSession, model, *filters) -> int:
    query = select(func.count()).select_from(model)
    if filters:
        query = query.where(*filters)
    return await session.scalar(query) or 0


async def _count_enrollments(
    session: AsyncSession, group_id: uuid.UUID, status: EnrollmentStatus
) -> int:
    return await _count(
        session, Enrollment, Enrollment.group_id == group_id, Enrollment.status == status
    )


async def _confirmed_revenue(
    session: AsyncSession,
    group_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
) -> Decimal:
    """Faqat tasdiqlangan to'lovlar summasi."""
    query = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.status == PaymentStatus.confirmed
    )
    if group_id is not None or teacher_id is not None:
        query = query.join(Enrollment, Enrollment.id == Payment.enrollment_id).join(
            Group, Group.id == Enrollment.group_id
        )
        if group_id is not None:
            query = query.where(Group.id == group_id)
        if teacher_id is not None:
            query = query.where(Group.teacher_id == teacher_id)
    return Decimal(await session.scalar(query) or 0)
