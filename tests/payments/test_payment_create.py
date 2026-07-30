"""To'lov yaratish: summa kurs narxiga teng bo'lishi va ruxsat qoidalari."""

from decimal import Decimal

from app.payments.models import PaymentStatus
from app.users.models import UserStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_student,
    create_teacher,
)

COURSE_PRICE = Decimal("500000.00")


async def _setup_enrollment(session, student_status=UserStatus.approved):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    student = await create_student(session, status=student_status)
    enrollment = await create_enrollment(session, student, group)
    return student, enrollment


async def test_student_creates_full_payment(client, session):
    student, enrollment = await _setup_enrollment(session)

    response = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == PaymentStatus.pending.value
    assert body["method"] == "manual"


async def test_payment_amount_must_match_course_price(client, session):
    student, enrollment = await _setup_enrollment(session)

    response = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": "100000.00"},
        headers=auth_headers(student),
    )

    assert response.status_code == 422


async def test_pending_student_cannot_pay(client, session):
    student, enrollment = await _setup_enrollment(session, student_status=UserStatus.pending)

    response = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )

    assert response.status_code == 403


async def test_student_cannot_pay_for_other_enrollment(client, session):
    _, enrollment = await _setup_enrollment(session)
    stranger = await create_student(session)

    response = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(stranger),
    )

    assert response.status_code == 403


async def test_payment_without_target_returns_422(client, session):
    student, _ = await _setup_enrollment(session)

    response = await client.post(
        "/api/payments", json={"amount": str(COURSE_PRICE)}, headers=auth_headers(student)
    )

    assert response.status_code == 422


async def test_student_sees_own_payments(client, session):
    student, enrollment = await _setup_enrollment(session)
    await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )

    response = await client.get("/api/payments/me", headers=auth_headers(student))

    assert response.status_code == 200
    assert len(response.json()) == 1
