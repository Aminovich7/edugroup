"""To'lov sxemalari."""

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.payments.models import InstallmentStatus, PaymentMethod, PaymentPlanStatus, PaymentStatus


class PaymentPlanCreateRequest(BaseModel):
    """Bo'lib to'lash 2 dan 4 gacha bo'lakka bo'linishi mumkin."""

    installments_count: int = Field(ge=2, le=4)


class PaymentCreateRequest(BaseModel):
    """To'liq to'lov uchun enrollment_id, bo'lak uchun installment_id yuboriladi."""

    enrollment_id: uuid.UUID | None = None
    installment_id: uuid.UUID | None = None
    amount: Decimal = Field(gt=0, decimal_places=2)

    @model_validator(mode="after")
    def check_target_is_given(self) -> "PaymentCreateRequest":
        if self.enrollment_id is None and self.installment_id is None:
            raise ValueError("enrollment_id yoki installment_id yuborilishi kerak")
        return self


class PaymentRejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class InstallmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sequence_number: int
    amount_due: Decimal
    due_date: date | None
    status: InstallmentStatus


class PaymentPlanResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    enrollment_id: uuid.UUID
    total_amount: Decimal
    installments_count: int
    status: PaymentPlanStatus
    installments: list[InstallmentResponse]


class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    enrollment_id: uuid.UUID
    student_id: uuid.UUID
    installment_id: uuid.UUID | None
    amount: Decimal
    method: PaymentMethod
    status: PaymentStatus
    confirmed_by: uuid.UUID | None
    confirmed_at: datetime | None
    note: str | None
    created_at: datetime


class PaymentListResponse(BaseModel):
    """Hisobot uchun — sahifalangan ro'yxat va jami summalar."""

    items: list[PaymentResponse]
    total_count: int
    total_amount: Decimal
