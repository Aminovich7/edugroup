"""Audit log sxemalari."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.audit.models import AuditAction, AuditEntityType


class AuditLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    entity_type: AuditEntityType
    entity_id: uuid.UUID
    action: AuditAction
    actor_id: uuid.UUID
    changes: dict[str, Any] | None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogResponse]
    total_count: int
