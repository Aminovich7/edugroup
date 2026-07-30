"""Kurs sxemalari."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.courses.models import CourseStatus


class CourseCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    subject: str = Field(min_length=2, max_length=100)
    price: Decimal = Field(ge=0, decimal_places=2)


class CourseUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    subject: str | None = Field(default=None, min_length=2, max_length=100)
    price: Decimal | None = Field(default=None, ge=0, decimal_places=2)
    status: CourseStatus | None = None


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    teacher_id: uuid.UUID
    title: str
    description: str | None
    subject: str
    price: Decimal
    status: CourseStatus
    deleted_at: datetime | None
    created_at: datetime
