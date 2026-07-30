"""Guruh modeli — kurs ichidagi aniq jadvalga ega o'quv guruhi."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.courses.models import Course
from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin, UuidPrimaryKeyMixin
from app.users.models import User


class GroupStatus(str, enum.Enum):
    draft = "draft"          # teacher yaratdi, manager tasdig'ini kutmoqda
    active = "active"        # katalogda ko'rinadi, yozilish ochiq
    closed = "closed"        # yangi yozilish yo'q, mavjud studentlar davom etadi
    archived = "archived"    # katalogdan butunlay yashirilgan


class Group(Base, UuidPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "groups"

    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("courses.id"))
    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(200))
    capacity: Mapped[int] = mapped_column(Integer)
    schedule: Mapped[str] = mapped_column(String(200))
    status: Mapped[GroupStatus] = mapped_column(
        Enum(GroupStatus, name="group_status"), default=GroupStatus.draft
    )
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    course: Mapped[Course] = relationship(lazy="selectin")
    teacher: Mapped[User] = relationship(lazy="selectin", foreign_keys=[teacher_id])
