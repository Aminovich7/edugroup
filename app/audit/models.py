"""Course/Group/Lesson ustidagi o'zgarishlar tarixi."""

import enum
import uuid
from typing import Any

from sqlalchemy import Enum, ForeignKey, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPrimaryKeyMixin


class AuditEntityType(str, enum.Enum):
    course = "course"
    group = "group"
    lesson = "lesson"


class AuditAction(str, enum.Enum):
    create = "create"
    update = "update"
    delete = "delete"
    restore = "restore"


class AuditLog(Base, UuidPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "audit_logs"

    entity_type: Mapped[AuditEntityType] = mapped_column(
        Enum(AuditEntityType, name="audit_entity_type")
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    action: Mapped[AuditAction] = mapped_column(Enum(AuditAction, name="audit_action"))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    # {"field": {"old": ..., "new": ...}} ko'rinishidagi diff
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
