"""Guruh sxemalari."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.groups.models import GroupStatus


class GroupCreateRequest(BaseModel):
    course_id: uuid.UUID
    name: str = Field(min_length=3, max_length=200)
    capacity: int = Field(ge=1, le=200)
    schedule: str = Field(min_length=3, max_length=200)


class GroupUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=200)
    capacity: int | None = Field(default=None, ge=1, le=200)
    schedule: str | None = Field(default=None, min_length=3, max_length=200)
    status: GroupStatus | None = None


class AssignTeacherRequest(BaseModel):
    """Manager guruhni tasdiqlaydi; xohlasa boshqa teacher biriktiradi."""

    teacher_id: uuid.UUID | None = None


class GroupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    course_id: uuid.UUID
    teacher_id: uuid.UUID
    name: str
    capacity: int
    schedule: str
    status: GroupStatus
    approved_by: uuid.UUID | None
    approved_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime


class GroupWithSeatsResponse(GroupResponse):
    """Katalog uchun — bo'sh joy va navbat uzunligi bilan."""

    occupied_seats: int
    free_seats: int
    waitlist_count: int
