"""Hisobot sxemalari."""

import uuid
from decimal import Decimal

from pydantic import BaseModel


class OverviewResponse(BaseModel):
    """Superadmin bosh sahifasidagi umumiy raqamlar."""

    total_users: int
    total_students: int
    total_teachers: int
    total_managers: int
    active_courses: int
    active_groups: int
    active_enrollments: int
    waitlisted_enrollments: int
    total_revenue: Decimal


class RevenueRow(BaseModel):
    """Daromad hisobotining bir qatori — guruh kesimida."""

    group_id: uuid.UUID
    group_name: str
    teacher_name: str
    payments_count: int
    amount: Decimal


class RevenueReportResponse(BaseModel):
    rows: list[RevenueRow]
    total_amount: Decimal
    total_count: int


class GroupReportResponse(BaseModel):
    group_id: uuid.UUID
    group_name: str
    course_title: str
    teacher_name: str
    capacity: int
    active_students: int
    awaiting_payment_students: int
    waitlisted_students: int
    lessons_count: int
    total_revenue: Decimal


class TeacherReportResponse(BaseModel):
    teacher_id: uuid.UUID
    teacher_name: str
    groups_count: int
    active_students: int
    lessons_count: int
    total_revenue: Decimal
