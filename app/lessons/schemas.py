"""Dars sxemalari."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

MIN_DURATION_SECONDS = 300   # 5 daqiqa
MAX_DURATION_SECONDS = 600   # 10 daqiqa
KINESCOPE_DOMAIN = "kinescope.io"


class LessonCreateRequest(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    kinescope_video_id: str = Field(min_length=3, max_length=100)
    kinescope_url: str = Field(max_length=500)
    duration_seconds: int = Field(ge=MIN_DURATION_SECONDS, le=MAX_DURATION_SECONDS)
    order_index: int = Field(default=1, ge=1)

    @field_validator("kinescope_url")
    @classmethod
    def check_kinescope_url(cls, value: str) -> str:
        return _validate_kinescope_url(value)


class LessonUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = None
    kinescope_video_id: str | None = Field(default=None, min_length=3, max_length=100)
    kinescope_url: str | None = Field(default=None, max_length=500)
    duration_seconds: int | None = Field(
        default=None, ge=MIN_DURATION_SECONDS, le=MAX_DURATION_SECONDS
    )
    order_index: int | None = Field(default=None, ge=1)

    @field_validator("kinescope_url")
    @classmethod
    def check_kinescope_url(cls, value: str | None) -> str | None:
        return _validate_kinescope_url(value) if value is not None else None


class LessonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    group_id: uuid.UUID
    title: str
    description: str | None
    kinescope_video_id: str
    kinescope_url: str
    duration_seconds: int
    order_index: int
    deleted_at: datetime | None
    created_at: datetime


class LessonProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    lesson_id: uuid.UUID
    student_id: uuid.UUID
    watched: bool
    watched_at: datetime | None


class StudentProgressRow(BaseModel):
    """Teacher dashboard'idagi progress jadvalining bir qatori."""

    student_id: uuid.UUID
    student_name: str
    watched_lessons: int
    total_lessons: int


def _validate_kinescope_url(value: str) -> str:
    if not value.startswith(("http://", "https://")):
        raise ValueError("Video havolasi http:// yoki https:// bilan boshlanishi kerak")
    if KINESCOPE_DOMAIN not in value:
        raise ValueError(f"Video havolasi {KINESCOPE_DOMAIN} domenida bo'lishi kerak")
    return value
