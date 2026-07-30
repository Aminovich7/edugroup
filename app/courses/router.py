"""JSON API: /courses."""

import uuid

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, SessionDep, SuperadminUser, TeacherUser
from app.courses import service
from app.courses.schemas import CourseCreateRequest, CourseResponse, CourseUpdateRequest

router = APIRouter(prefix="/courses", tags=["courses"])


@router.post("", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(data: CourseCreateRequest, session: SessionDep, teacher: TeacherUser):
    return await service.create_course(session, data, teacher)


@router.get("", response_model=list[CourseResponse])
async def list_courses(
    session: SessionDep,
    subject: str | None = None,
    teacher_id: uuid.UUID | None = None,
):
    """Ommaviy katalog — faqat active kurslar."""
    return await service.list_active(session, subject=subject, teacher_id=teacher_id)


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: uuid.UUID, session: SessionDep):
    return await service.get_course(session, course_id)


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: uuid.UUID,
    data: CourseUpdateRequest,
    session: SessionDep,
    current_user: CurrentUser,
):
    return await service.update_course(session, course_id, data, current_user)


@router.delete("/{course_id}", response_model=CourseResponse)
async def delete_course(course_id: uuid.UUID, session: SessionDep, current_user: CurrentUser):
    """Soft delete — yozuv bazada qoladi, deleted_at to'ldiriladi."""
    return await service.soft_delete_course(session, course_id, current_user)


@router.post("/{course_id}/restore", response_model=CourseResponse)
async def restore_course(
    course_id: uuid.UUID, session: SessionDep, superadmin: SuperadminUser
):
    return await service.restore_course(session, course_id, superadmin)
