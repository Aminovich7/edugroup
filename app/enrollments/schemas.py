"""Yozilish sxemalari."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.enrollments.models import EnrollmentStatus


class EnrollmentCreateRequest(BaseModel):
    group_id: uuid.UUID


class EnrollmentCancelRequest(BaseModel):
    """Manager/superadmin bekor qilganda sabab majburiy (service tekshiradi)."""

    reason: str | None = Field(default=None, max_length=500)


class EnrollmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: uuid.UUID
    group_id: uuid.UUID
    status: EnrollmentStatus
    requested_at: datetime
    activated_at: datetime | None
    cancelled_at: datetime | None
    cancel_reason: str | None
    waitlist_position: int | None
