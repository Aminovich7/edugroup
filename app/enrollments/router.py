"""JSON API: /enrollments."""

import uuid

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, ManagerOrSuperadmin, SessionDep, StudentUser
from app.enrollments import service
from app.enrollments.models import EnrollmentStatus
from app.enrollments.schemas import (
    EnrollmentCancelRequest,
    EnrollmentCreateRequest,
    EnrollmentResponse,
)

router = APIRouter(prefix="/enrollments", tags=["enrollments"])


@router.post("", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def create_enrollment(
    data: EnrollmentCreateRequest, session: SessionDep, student: StudentUser
):
    """Guruhga yozilish so'rovi. Guruh to'la bo'lsa — navbatga qo'yiladi."""
    return await service.request_enrollment(session, data.group_id, student)


@router.get("/me", response_model=list[EnrollmentResponse])
async def list_my_enrollments(session: SessionDep, student: StudentUser):
    return await service.list_my_enrollments(session, student)


@router.get("", response_model=list[EnrollmentResponse])
async def list_all_enrollments(
    session: SessionDep,
    staff: ManagerOrSuperadmin,
    group_id: uuid.UUID | None = None,
    student_id: uuid.UUID | None = None,
    status: EnrollmentStatus | None = None,
):
    return await service.list_all_enrollments(
        session, group_id=group_id, student_id=student_id, status=status
    )


@router.delete("/{enrollment_id}", response_model=EnrollmentResponse)
async def cancel_enrollment(
    enrollment_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    data: EnrollmentCancelRequest | None = None,
):
    """Yozilishni bekor qiladi va navbatdagi keyingi studentni ko'taradi."""
    return await service.cancel_enrollment(
        session, enrollment_id, current_user, reason=data.reason if data else None
    )
