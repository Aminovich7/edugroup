"""Modellar uchun umumiy ustunlar — takrorlanmasligi uchun mixin ko'rinishida."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column


class UuidPrimaryKeyMixin:
    """Har bir jadvalning birlamchi kaliti — UUID."""

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )


class TimestampMixin:
    """Yozuv qachon yaratilgani va oxirgi marta qachon o'zgargani."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SoftDeleteMixin:
    """Yozuv jismonan o'chirilmaydi — faqat deleted_at to'ldiriladi.

    deleted_at to'ldirilgan yozuv oddiy ro'yxatlarda ko'rinmaydi,
    lekin superadmin uni qayta tiklashi (restore) mumkin.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
