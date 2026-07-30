"""JSON API: /payments va /enrollments/{id}/payment-plan."""

import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.core.dependencies import (
    CurrentUser,
    ManagerOrSuperadmin,
    SessionDep,
    StudentUser,
    SuperadminUser,
)
from app.payments import service
from app.payments.models import PaymentStatus
from app.payments.schemas import (
    PaymentCreateRequest,
    PaymentListResponse,
    PaymentPlanCreateRequest,
    PaymentPlanResponse,
    PaymentRejectRequest,
    PaymentResponse,
)

router = APIRouter(prefix="/payments", tags=["payments"])
plan_router = APIRouter(prefix="/enrollments", tags=["payments"])


@plan_router.post(
    "/{enrollment_id}/payment-plan",
    response_model=PaymentPlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment_plan(
    enrollment_id: uuid.UUID,
    data: PaymentPlanCreateRequest,
    session: SessionDep,
    student: StudentUser,
):
    """Kurs narxini 2–4 bo'lakka bo'lib to'lash rejasini yaratadi."""
    return await service.create_payment_plan(
        session, enrollment_id, data.installments_count, student
    )


@plan_router.get("/{enrollment_id}/payment-plan", response_model=PaymentPlanResponse)
async def get_payment_plan(
    enrollment_id: uuid.UUID, session: SessionDep, viewer: CurrentUser
):
    return await service.get_payment_plan(session, enrollment_id, viewer)


@router.post("", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
async def create_payment(
    data: PaymentCreateRequest, session: SessionDep, student: StudentUser
):
    return await service.create_payment(session, data, student)


@router.get("/me", response_model=list[PaymentResponse])
async def list_my_payments(session: SessionDep, student: StudentUser):
    return await service.list_my_payments(session, student)


@router.get("", response_model=PaymentListResponse)
async def list_payments(
    session: SessionDep,
    superadmin: SuperadminUser,
    status: PaymentStatus | None = None,
    group_id: uuid.UUID | None = None,
    teacher_id: uuid.UUID | None = None,
    subject: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Barcha to'lovlar — filtrlar va jami summa bilan (faqat superadmin)."""
    items, total_count, total_amount = await service.list_payments(
        session,
        status=status,
        group_id=group_id,
        teacher_id=teacher_id,
        subject=subject,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return PaymentListResponse(
        items=items, total_count=total_count, total_amount=total_amount
    )


@router.post("/{payment_id}/confirm", response_model=PaymentResponse)
async def confirm_payment(
    payment_id: uuid.UUID, session: SessionDep, moderator: ManagerOrSuperadmin
):
    """To'lovni tasdiqlaydi — birinchi tasdiq yozilishni faollashtiradi."""
    return await service.confirm_payment(session, payment_id, moderator)


@router.post("/{payment_id}/reject", response_model=PaymentResponse)
async def reject_payment(
    payment_id: uuid.UUID,
    data: PaymentRejectRequest,
    session: SessionDep,
    moderator: ManagerOrSuperadmin,
):
    """To'lovni rad etadi — yozilish statusi o'zgarmaydi."""
    return await service.reject_payment(session, payment_id, moderator, data.reason)
