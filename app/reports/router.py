"""JSON API: /reports."""

import uuid
from datetime import date

from fastapi import APIRouter

from app.core.dependencies import (
    CurrentUser,
    ManagerOrSuperadmin,
    SessionDep,
    SuperadminUser,
)
from app.reports import service
from app.reports.schemas import (
    GroupReportResponse,
    OverviewResponse,
    RevenueReportResponse,
    TeacherReportResponse,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(session: SessionDep, superadmin: SuperadminUser):
    return await service.get_overview(session)


@router.get("/revenue", response_model=RevenueReportResponse)
async def get_revenue(
    session: SessionDep,
    superadmin: SuperadminUser,
    date_from: date | None = None,
    date_to: date | None = None,
    group_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
):
    return await service.get_revenue_report(
        session,
        date_from=date_from,
        date_to=date_to,
        group_id=group_id,
        teacher_id=teacher_id,
    )


@router.get("/groups/{group_id}", response_model=GroupReportResponse)
async def get_group_report(group_id: uuid.UUID, session: SessionDep, viewer: CurrentUser):
    """Guruh hisoboti — teacher (o'ziniki), manager yoki superadmin."""
    return await service.get_group_report(session, group_id, viewer)


@router.get("/teachers/{teacher_id}", response_model=TeacherReportResponse)
async def get_teacher_report(
    teacher_id: uuid.UUID, session: SessionDep, staff: ManagerOrSuperadmin
):
    return await service.get_teacher_report(session, teacher_id)
