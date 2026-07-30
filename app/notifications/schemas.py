"""Bildirishnoma sxemalari."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.notifications.models import NotificationType


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    title: str
    message: str
    is_read: bool
    related_entity_type: str | None
    related_entity_id: uuid.UUID | None
    created_at: datetime
