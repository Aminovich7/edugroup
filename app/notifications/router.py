"""JSON API: /notifications."""

import uuid

from fastapi import APIRouter

from app.core.dependencies import CurrentUser, SessionDep
from app.notifications import service
from app.notifications.schemas import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_my_notifications(
    session: SessionDep, current_user: CurrentUser, is_read: bool | None = None
):
    return await service.list_my_notifications(session, current_user, is_read)


@router.post("/read-all", response_model=dict[str, int])
async def mark_all_read(session: SessionDep, current_user: CurrentUser):
    """Barcha o'qilmagan bildirishnomalarni o'qilgan deb belgilaydi."""
    updated_count = await service.mark_all_as_read(session, current_user)
    return {"updated_count": updated_count}


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
):
    return await service.mark_as_read(session, notification_id, current_user)
