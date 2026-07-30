"""Dars va dars progressi modellari.

Video fayl hech qachon serverga yuklanmaydi — faqat Kinescope havolasi saqlanadi.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin, UuidPrimaryKeyMixin


class Lesson(Base, UuidPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "lessons"

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    kinescope_video_id: Mapped[str] = mapped_column(String(100))
    kinescope_url: Mapped[str] = mapped_column(String(500))
    duration_seconds: Mapped[int] = mapped_column(Integer)  # 300–600 (5–10 daqiqa)
    order_index: Mapped[int] = mapped_column(Integer, default=1)


class LessonProgress(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Student darsni ko'rganini belgilaydi — teacher shu orqali progressni kuzatadi."""

    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("student_id", "lesson_id"),)

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    lesson_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    watched: Mapped[bool] = mapped_column(Boolean, default=False)
    watched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
