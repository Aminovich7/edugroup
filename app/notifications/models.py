"""In-app bildirishnoma modeli."""

import enum
import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPrimaryKeyMixin


class NotificationType(str, enum.Enum):
    profile_approved = "profile_approved"
    profile_rejected = "profile_rejected"
    payment_confirmed = "payment_confirmed"
    payment_rejected = "payment_rejected"
    enrollment_activated = "enrollment_activated"
    waitlist_promoted = "waitlist_promoted"
    group_assigned = "group_assigned"
    lesson_added = "lesson_added"
    installment_overdue = "installment_overdue"
    enrollment_expired = "enrollment_expired"
    account_blocked = "account_blocked"
    account_unblocked = "account_unblocked"


class Notification(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(
        Enum(NotificationType, name="notification_type")
    )
    title: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    related_entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    related_entity_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
