"""JSON API: /lessons va /groups/{id}/lessons."""

import uuid

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, SessionDep, StudentUser, SuperadminUser, TeacherUser
from app.lessons import service
from app.lessons.schemas import (
    LessonCreateRequest,
    LessonProgressResponse,
    LessonResponse,
    LessonUpdateRequest,
    StudentProgressRow,
)

router = APIRouter(prefix="/lessons", tags=["lessons"])
group_lessons_router = APIRouter(prefix="/groups", tags=["lessons"])


@group_lessons_router.post(
    "/{group_id}/lessons", response_model=LessonResponse, status_code=status.HTTP_201_CREATED
)
async def create_lesson(
    group_id: uuid.UUID,
    data: LessonCreateRequest,
    session: SessionDep,
    teacher: TeacherUser,
):
    return await service.create_lesson(session, group_id, data, teacher)


@group_lessons_router.get("/{group_id}/lessons", response_model=list[LessonResponse])
async def list_group_lessons(group_id: uuid.UUID, session: SessionDep, viewer: CurrentUser):
    """Guruh darslari — faqat active yozilishi bor student, teacher yoki staff ko'radi."""
    return await service.list_for_group(session, group_id, viewer)


@group_lessons_router.get("/{group_id}/progress", response_model=list[StudentProgressRow])
async def get_group_progress(group_id: uuid.UUID, session: SessionDep, viewer: CurrentUser):
    """Guruhdagi o'quvchilarning progress jadvali."""
    return await service.get_group_progress(session, group_id, viewer)


@router.get("/{lesson_id}", response_model=LessonResponse)
async def get_lesson(lesson_id: uuid.UUID, session: SessionDep, viewer: CurrentUser):
    """Dars tafsilotlari va Kinescope havolasi."""
    return await service.get_lesson(session, lesson_id, viewer)


@router.patch("/{lesson_id}", response_model=LessonResponse)
async def update_lesson(
    lesson_id: uuid.UUID,
    data: LessonUpdateRequest,
    session: SessionDep,
    current_user: CurrentUser,
):
    return await service.update_lesson(session, lesson_id, data, current_user)


@router.delete("/{lesson_id}", response_model=LessonResponse)
async def delete_lesson(lesson_id: uuid.UUID, session: SessionDep, current_user: CurrentUser):
    return await service.soft_delete_lesson(session, lesson_id, current_user)


@router.post("/{lesson_id}/restore", response_model=LessonResponse)
async def restore_lesson(lesson_id: uuid.UUID, session: SessionDep, superadmin: SuperadminUser):
    return await service.restore_lesson(session, lesson_id, superadmin)


@router.post(
    "/{lesson_id}/progress",
    response_model=LessonProgressResponse,
    status_code=status.HTTP_201_CREATED,
)
async def mark_lesson_watched(lesson_id: uuid.UUID, session: SessionDep, student: StudentUser):
    """Darsni "tomosha qilindi" deb belgilaydi."""
    return await service.mark_watched(session, lesson_id, student)
