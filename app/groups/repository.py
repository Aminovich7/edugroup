"""Guruhlar uchun DB so'rovlari."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.courses.models import Course
from app.groups.models import Group, GroupStatus


async def get_by_id(session: AsyncSession, group_id: uuid.UUID) -> Group | None:
    return await session.get(Group, group_id)


async def list_groups(
    session: AsyncSession,
    course_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    status: GroupStatus | None = None,
    subject: str | None = None,
    include_deleted: bool = False,
) -> list[Group]:
    query = select(Group).order_by(Group.created_at.desc())
    if not include_deleted:
        query = query.where(Group.deleted_at.is_(None))
    if course_id is not None:
        query = query.where(Group.course_id == course_id)
    if teacher_id is not None:
        query = query.where(Group.teacher_id == teacher_id)
    if status is not None:
        query = query.where(Group.status == status)
    if subject is not None:
        query = query.join(Course, Course.id == Group.course_id).where(
            Course.subject.ilike(f"%{subject}%")
        )
    return list(await session.scalars(query))
