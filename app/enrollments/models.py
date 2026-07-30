"""Student va guruh o'rtasidagi yozilish (enrollment) modeli."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPrimaryKeyMixin


class EnrollmentStatus(str, enum.Enum):
    awaiting_payment = "awaiting_payment"  # joy band qilindi, to'lov kutilmoqda
    waitlisted = "waitlisted"              # guruh to'la, navbatda
    active = "active"                      # to'lov tasdiqlandi, videolar ochiq
    expired = "expired"                    # muddat ichida to'lanmadi
    cancelled = "cancelled"                # student yoki manager bekor qildi


# Yakunlanmagan (non-terminal) statuslar — joy bandligi shular bo'yicha hisoblanadi.
NON_TERMINAL_STATUSES = (
    EnrollmentStatus.awaiting_payment,
    EnrollmentStatus.waitlisted,
    EnrollmentStatus.active,
)

# Guruh "to'la" ekanligini aniqlaydigan statuslar: to'lov kutayotgan joy ham band
# hisoblanadi, aks holda bir joy ikki studentga sotilib ketishi mumkin edi.
OCCUPYING_STATUSES = (EnrollmentStatus.awaiting_payment, EnrollmentStatus.active)


class Enrollment(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "enrollments"
    __table_args__ = (
        # PARTIAL unique index — oddiy unique_constraint(student_id, group_id) EMAS.
        # Oddiy cheklov bo'lganda bekor qilingan yozuv (student, group) juftligini
        # abadiy band qilib qo'yardi va student o'sha guruhga qayta yozila olmasdi.
        # Bu yerda cheklov faqat yakunlanmagan statuslarga tegishli.
        Index(
            "uq_enrollment_active_per_group",
            "student_id",
            "group_id",
            unique=True,
            postgresql_where=text(
                "status IN ('awaiting_payment', 'waitlisted', 'active')"
            ),
        ),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    status: Mapped[EnrollmentStatus] = mapped_column(
        Enum(EnrollmentStatus, name="enrollment_status")
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Faqat status=waitlisted bo'lganda to'ldiriladi: 1 — navbatdagi birinchi.
    waitlist_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
