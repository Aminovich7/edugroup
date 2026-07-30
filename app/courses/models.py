"""Kurs modeli."""

import enum
import uuid
from decimal import Decimal

from sqlalchemy import Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import SoftDeleteMixin, TimestampMixin, UuidPrimaryKeyMixin
from app.users.models import User


class CourseStatus(str, enum.Enum):
    draft = "draft"          # teacher yaratdi, hali katalogda ko'rinmaydi
    active = "active"        # katalogda ko'rinadi
    archived = "archived"    # yopilgan


class Course(Base, UuidPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "courses"

    teacher_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str] = mapped_column(String(100), index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[CourseStatus] = mapped_column(
        Enum(CourseStatus, name="course_status"), default=CourseStatus.draft
    )

    teacher: Mapped[User] = relationship(lazy="selectin")
