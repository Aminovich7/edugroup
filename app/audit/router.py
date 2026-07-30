"""JSON API: /audit-logs — faqat superadmin uchun."""

import uuid
from datetime import date

from fastapi import APIRouter, Query

from app.audit import service
from app.audit.models import AuditEntityType
from app.audit.schemas import AuditLogListResponse
from app.core.dependencies import SessionDep, SuperadminUser

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=AuditLogListResponse)
async def list_audit_logs(
    session: SessionDep,
    superadmin: SuperadminUser,
    entity_type: AuditEntityType | None = None,
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items, total_count = await service.list_logs(
        session,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(items=items, total_count=total_count)
