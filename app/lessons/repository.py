"""Darslar va progress uchun DB so'rovlari."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lessons.models import Lesson, LessonProgress


async def get_by_id(session: AsyncSession, lesson_id: uuid.UUID) -> Lesson | None:
    return await session.get(Lesson, lesson_id)


async def list_for_group(
    session: AsyncSession, group_id: uuid.UUID, include_deleted: bool = False
) -> list[Lesson]:
    query = select(Lesson).where(Lesson.group_id == group_id).order_by(Lesson.order_index)
    if not include_deleted:
        query = query.where(Lesson.deleted_at.is_(None))
    return list(await session.scalars(query))


async def get_progress(
    session: AsyncSession, student_id: uuid.UUID, lesson_id: uuid.UUID
) -> LessonProgress | None:
    query = select(LessonProgress).where(
        LessonProgress.student_id == student_id,
        LessonProgress.lesson_id == lesson_id,
    )
    return await session.scalar(query)


async def list_progress_for_lessons(
    session: AsyncSession, lesson_ids: list[uuid.UUID]
) -> list[LessonProgress]:
    if not lesson_ids:
        return []
    query = select(LessonProgress).where(
        LessonProgress.lesson_id.in_(lesson_ids), LessonProgress.watched.is_(True)
    )
    return list(await session.scalars(query))


async def list_progress_for_student(
    session: AsyncSession, student_id: uuid.UUID
) -> list[LessonProgress]:
    query = select(LessonProgress).where(LessonProgress.student_id == student_id)
    return list(await session.scalars(query))
