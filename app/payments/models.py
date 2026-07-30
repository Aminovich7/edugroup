"""To'lov, to'lov rejasi va bo'lib to'lash modellari."""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPrimaryKeyMixin


class PaymentMethod(str, enum.Enum):
    # Real to'lov tizimlari (Payme/Click) integratsiyasi TZ doirasidan tashqarida —
    # to'lov faqat qo'lda kiritiladi va manager tomonidan tasdiqlanadi.
    manual = "manual"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    rejected = "rejected"


class PaymentPlanStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class InstallmentStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    overdue = "overdue"


class PaymentPlan(Base, UuidPrimaryKeyMixin, TimestampMixin):
    """Bo'lib to'lash rejasi — bitta yozilishga bitta reja."""

    __tablename__ = "payment_plans"

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE"), unique=True
    )
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    installments_count: Mapped[int] = mapped_column(Integer)
    status: Mapped[PaymentPlanStatus] = mapped_column(
        Enum(PaymentPlanStatus, name="payment_plan_status"), default=PaymentPlanStatus.active
    )

    installments: Mapped[list["Installment"]] = relationship(
        back_populates="payment_plan", lazy="selectin", order_by="Installment.sequence_number"
    )


class Installment(Base, UuidPrimaryKeyMixin):
    """Rejadagi bitta bo'lak."""

    __tablename__ = "installments"
    __table_args__ = (UniqueConstraint("payment_plan_id", "sequence_number"),)

    payment_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("payment_plans.id", ondelete="CASCADE")
    )
    sequence_number: Mapped[int] = mapped_column(Integer)
    amount_due: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[InstallmentStatus] = mapped_column(
        Enum(InstallmentStatus, name="installment_status"), default=InstallmentStatus.pending
    )

    payment_plan: Mapped[PaymentPlan] = relationship(back_populates="installments")


class Payment(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "payments"

    enrollment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("enrollments.id", ondelete="CASCADE")
    )
    student_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    # Bo'lib to'lashda to'lov aynan qaysi bo'lakka tegishli ekanini ko'rsatadi.
    installment_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("installments.id"), nullable=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method"), default=PaymentMethod.manual
    )
    status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status"), default=PaymentStatus.pending
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
