"""Audit log biznes-logikasi.

Audit yozuvi ham bildirishnoma kabi SINXRON yoziladi va o'zgarish bilan
bir xil tranzaksiyada saqlanadi — aks holda o'zgarish saqlanib, audit yozuvi
yo'qolib qolishi mumkin edi va tarix ishonchsiz bo'lardi.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.models import AuditAction, AuditEntityType, AuditLog


async def log_change(
    session: AsyncSession,
    entity_type: AuditEntityType,
    entity_id: uuid.UUID,
    action: AuditAction,
    actor_id: uuid.UUID,
    changes: dict[str, Any] | None = None,
) -> AuditLog:
    log_entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=actor_id,
        changes=changes,
    )
    session.add(log_entry)
    await session.flush()
    return log_entry


async def list_logs(
    session: AsyncSession,
    entity_type: AuditEntityType | None = None,
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditLog], int]:
    """Filtrlangan audit yozuvlari va ularning umumiy sonini qaytaradi."""
    filters = []
    if entity_type is not None:
        filters.append(AuditLog.entity_type == entity_type)
    if entity_id is not None:
        filters.append(AuditLog.entity_id == entity_id)
    if actor_id is not None:
        filters.append(AuditLog.actor_id == actor_id)
    if date_from is not None:
        filters.append(AuditLog.created_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to is not None:
        filters.append(AuditLog.created_at <= datetime.combine(date_to, datetime.max.time()))

    items_query = (
        select(AuditLog)
        .where(*filters)
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    count_query = select(func.count()).select_from(AuditLog).where(*filters)

    items = list(await session.scalars(items_query))
    total_count = await session.scalar(count_query) or 0
    return items, total_count


def build_changes(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Ikki holat orasidagi farqni {"maydon": {"old": ..., "new": ...}} shaklida qaytaradi."""
    changes: dict[str, Any] = {}
    for field, new_value in after.items():
        old_value = before.get(field)
        if old_value != new_value:
            changes[field] = {"old": _to_json_value(old_value), "new": _to_json_value(new_value)}
    return changes


def _to_json_value(value: Any) -> Any:
    """JSONB'ga yozib bo'ladigan oddiy turga o'giradi."""
    if isinstance(value, (uuid.UUID, datetime, date)):
        return str(value)
    if hasattr(value, "value"):  # Enum
        return value.value
    if isinstance(value, (int, float, str, bool)) or value is None:
        return value
    return str(value)
