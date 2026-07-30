"""To'lov va reja faqat awaiting_payment holatidagi yozilish uchun ruxsat etiladi."""

from decimal import Decimal

import pytest

from app.enrollments.models import EnrollmentStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_student,
    create_teacher,
)

COURSE_PRICE = Decimal("500000.00")

BLOCKED_STATUSES = [
    EnrollmentStatus.waitlisted,
    EnrollmentStatus.active,
    EnrollmentStatus.expired,
    EnrollmentStatus.cancelled,
]


async def _setup(session, status: EnrollmentStatus):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group, status=status)
    return student, enrollment


@pytest.mark.parametrize("status", BLOCKED_STATUSES)
async def test_payment_plan_requires_awaiting_payment(client, session, status):
    student, enrollment = await _setup(session, status)

    response = await client.post(
        f"/api/enrollments/{enrollment.id}/payment-plan",
        json={"installments_count": 2},
        headers=auth_headers(student),
    )

    assert response.status_code == 400


@pytest.mark.parametrize("status", BLOCKED_STATUSES)
async def test_payment_requires_awaiting_payment(client, session, status):
    student, enrollment = await _setup(session, status)

    response = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )

    assert response.status_code == 400


async def test_awaiting_payment_enrollment_is_allowed(client, session):
    student, enrollment = await _setup(session, EnrollmentStatus.awaiting_payment)

    response = await client.post(
        f"/api/enrollments/{enrollment.id}/payment-plan",
        json={"installments_count": 2},
        headers=auth_headers(student),
    )

    assert response.status_code == 201
