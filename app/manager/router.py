"""JSON API: /manager — moderatsiya va biriktirish endpointlari.

Bu modulda alohida biznes-logika yo'q: u faqat mavjud domain service'larini
manager uchun qulay bitta manzil ostida jamlaydi.
"""

import uuid

from fastapi import APIRouter

from app.core.dependencies import ManagerOrSuperadmin, SessionDep
from app.groups import service as groups_service
from app.groups.models import GroupStatus
from app.groups.schemas import AssignTeacherRequest, GroupResponse
from app.payments import service as payments_service
from app.payments.schemas import PaymentResponse
from app.users import service as users_service
from app.users.models import UserRole, UserStatus
from app.users.schemas import RejectRequest, UserResponse

router = APIRouter(prefix="/manager", tags=["manager"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    session: SessionDep,
    moderator: ManagerOrSuperadmin,
    role: UserRole | None = None,
    status: UserStatus | None = None,
):
    """Moderatsiya navbati — masalan ?status=pending&role=teacher."""
    return await users_service.list_users(session, role=role, status=status)


@router.post("/users/{user_id}/approve", response_model=UserResponse)
async def approve_user(
    user_id: uuid.UUID, session: SessionDep, moderator: ManagerOrSuperadmin
):
    return await users_service.approve_user(session, user_id, moderator)


@router.post("/users/{user_id}/reject", response_model=UserResponse)
async def reject_user(
    user_id: uuid.UUID,
    data: RejectRequest,
    session: SessionDep,
    moderator: ManagerOrSuperadmin,
):
    return await users_service.reject_user(session, user_id, moderator, data.reason)


@router.post("/groups/{group_id}/assign-teacher", response_model=GroupResponse)
async def assign_teacher(
    group_id: uuid.UUID,
    data: AssignTeacherRequest,
    session: SessionDep,
    moderator: ManagerOrSuperadmin,
):
    """Guruhni tasdiqlaydi (draft -> active) va kerak bo'lsa teacher'ni almashtiradi."""
    return await groups_service.assign_teacher(
        session, group_id, moderator, teacher_id=data.teacher_id
    )


@router.get("/groups", response_model=list[GroupResponse])
async def list_groups(
    session: SessionDep,
    moderator: ManagerOrSuperadmin,
    status: GroupStatus | None = None,
    teacher_id: uuid.UUID | None = None,
):
    return await groups_service.list_groups(session, status=status, teacher_id=teacher_id)


@router.get("/payments", response_model=list[PaymentResponse])
async def list_pending_payments(session: SessionDep, moderator: ManagerOrSuperadmin):
    """Tasdiqlanishi kerak bo'lgan to'lovlar."""
    return await payments_service.list_pending_payments(session)
