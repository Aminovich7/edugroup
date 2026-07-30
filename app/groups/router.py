"""JSON API: /groups."""

import uuid

from fastapi import APIRouter, status

from app.core.dependencies import CurrentUser, SessionDep, SuperadminUser, TeacherUser
from app.enrollments.schemas import EnrollmentResponse
from app.groups import service
from app.groups.models import Group
from app.groups.schemas import (
    GroupCreateRequest,
    GroupResponse,
    GroupUpdateRequest,
    GroupWithSeatsResponse,
)

router = APIRouter(prefix="/groups", tags=["groups"])


def _with_seats(group: Group, seats: dict[str, int]) -> GroupWithSeatsResponse:
    """Guruh javobiga bo'sh joy va navbat ma'lumotini qo'shadi."""
    return GroupWithSeatsResponse(**GroupResponse.model_validate(group).model_dump(), **seats)


@router.post("", response_model=GroupResponse, status_code=status.HTTP_201_CREATED)
async def create_group(data: GroupCreateRequest, session: SessionDep, teacher: TeacherUser):
    return await service.create_group(session, data, teacher)


@router.get("", response_model=list[GroupWithSeatsResponse])
async def list_groups(
    session: SessionDep,
    subject: str | None = None,
    teacher_id: uuid.UUID | None = None,
    course_id: uuid.UUID | None = None,
):
    """Ommaviy katalog — faqat active guruhlar, bo'sh joy va navbat soni bilan."""
    groups = await service.list_active(
        session, subject=subject, teacher_id=teacher_id, course_id=course_id
    )
    return [
        _with_seats(group, await service.get_seat_info(session, group)) for group in groups
    ]


@router.get("/mine", response_model=list[GroupResponse])
async def list_my_groups(session: SessionDep, teacher: TeacherUser):
    return await service.list_mine(session, teacher)


@router.get("/{group_id}", response_model=GroupWithSeatsResponse)
async def get_group(group_id: uuid.UUID, session: SessionDep):
    group = await service.get_group(session, group_id)
    return _with_seats(group, await service.get_seat_info(session, group))


@router.patch("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: uuid.UUID,
    data: GroupUpdateRequest,
    session: SessionDep,
    current_user: CurrentUser,
):
    return await service.update_group(session, group_id, data, current_user)


@router.delete("/{group_id}", response_model=GroupResponse)
async def delete_group(group_id: uuid.UUID, session: SessionDep, current_user: CurrentUser):
    return await service.soft_delete_group(session, group_id, current_user)


@router.post("/{group_id}/restore", response_model=GroupResponse)
async def restore_group(group_id: uuid.UUID, session: SessionDep, superadmin: SuperadminUser):
    return await service.restore_group(session, group_id, superadmin)


@router.get("/{group_id}/students", response_model=list[EnrollmentResponse])
async def list_group_students(group_id: uuid.UUID, session: SessionDep, viewer: CurrentUser):
    """Guruhdagi o'quvchilar — teacher (o'ziniki), manager, superadmin."""
    return await service.get_students(session, group_id, viewer)


@router.get("/{group_id}/waitlist", response_model=list[EnrollmentResponse])
async def list_group_waitlist(group_id: uuid.UUID, session: SessionDep, viewer: CurrentUser):
    """Guruh navbati — tartib bo'yicha."""
    return await service.get_waitlist(session, group_id, viewer)
