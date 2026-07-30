"""JSON API: /superadmin — manager yaratish va foydalanuvchilarni bloklash (TZ 6.11).

Manager akkaunti o'z-o'zidan ro'yxatdan o'ta olmaydi — uni faqat superadmin
shu yerdan yaratadi.
"""

import uuid

from fastapi import APIRouter, status

from app.core.dependencies import SessionDep, SuperadminUser
from app.users import service as users_service
from app.users.schemas import ManagerCreateRequest, UserResponse

router = APIRouter(prefix="/superadmin", tags=["superadmin"])


@router.post("/managers", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_manager(
    data: ManagerCreateRequest, session: SessionDep, superadmin: SuperadminUser
):
    """Yangi manager akkaunti — moderatsiyasiz, darhol faol."""
    return await users_service.create_manager(session, data)


@router.get("/managers", response_model=list[UserResponse])
async def list_managers(session: SessionDep, superadmin: SuperadminUser):
    return await users_service.list_managers(session)


@router.post("/users/{user_id}/block", response_model=UserResponse)
async def block_user(user_id: uuid.UUID, session: SessionDep, superadmin: SuperadminUser):
    """Foydalanuvchini bloklaydi — login va refresh darhol 403 qaytaradi."""
    return await users_service.block_user(session, user_id, superadmin)


@router.post("/users/{user_id}/unblock", response_model=UserResponse)
async def unblock_user(user_id: uuid.UUID, session: SessionDep, superadmin: SuperadminUser):
    return await users_service.unblock_user(session, user_id)
