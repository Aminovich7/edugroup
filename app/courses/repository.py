"""Kurslar uchun DB so'rovlari."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.courses.models import Course, CourseStatus


async def get_by_id(session: AsyncSession, course_id: uuid.UUID) -> Course | None:
    return await session.get(Course, course_id)


async def list_courses(
    session: AsyncSession,
    subject: str | None = None,
    teacher_id: uuid.UUID | None = None,
    status: CourseStatus | None = None,
    include_deleted: bool = False,
) -> list[Course]:
    query = select(Course).order_by(Course.created_at.desc())
    if not include_deleted:
        query = query.where(Course.deleted_at.is_(None))
    if subject is not None:
        query = query.where(Course.subject.ilike(f"%{subject}%"))
    if teacher_id is not None:
        query = query.where(Course.teacher_id == teacher_id)
    if status is not None:
        query = query.where(Course.status == status)
    return list(await session.scalars(query))
