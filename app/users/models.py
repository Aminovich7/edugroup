"""Foydalanuvchi, profil va refresh token modellari."""

import enum
import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPrimaryKeyMixin


class UserRole(str, enum.Enum):
    student = "student"
    teacher = "teacher"
    manager = "manager"
    superadmin = "superadmin"


class UserStatus(str, enum.Enum):
    pending = "pending"      # ro'yxatdan o'tdi, manager tasdig'ini kutmoqda
    approved = "approved"    # tasdiqlangan, to'liq ishlay oladi
    rejected = "rejected"    # manager rad etdi
    blocked = "blocked"      # superadmin blokladi


class User(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(150), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), unique=True, nullable=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.pending
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    teacher_profile: Mapped["TeacherProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        lazy="selectin",
        foreign_keys="TeacherProfile.user_id",
    )
    student_profile: Mapped["StudentProfile | None"] = relationship(
        back_populates="user",
        uselist=False,
        lazy="selectin",
        foreign_keys="StudentProfile.user_id",
    )


class TeacherProfile(Base, UuidPrimaryKeyMixin):
    __tablename__ = "teacher_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    specialization: Mapped[str | None] = mapped_column(String(100), nullable=True)
    experience_years: Mapped[int] = mapped_column(Integer, default=0)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="teacher_profile", foreign_keys=[user_id])


class StudentProfile(Base, UuidPrimaryKeyMixin):
    __tablename__ = "student_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="student_profile", foreign_keys=[user_id])


class RefreshToken(Base, UuidPrimaryKeyMixin):
    """Refresh tokenlarning rotatsiya zanjiri va bekor qilish ro'yxati.

    Tokenning o'zi hech qachon saqlanmaydi — faqat SHA-256 hash'i.
    """

    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    replaced_by_token_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
