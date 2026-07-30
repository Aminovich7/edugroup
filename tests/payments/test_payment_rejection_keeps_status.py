"""To'lov rad etilganda yozilish holati o'zgarmaydi va qayta to'lash mumkin."""

from decimal import Decimal

from app.enrollments.models import EnrollmentStatus
from app.payments.models import InstallmentStatus, PaymentStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_manager,
    create_student,
    create_teacher,
)

COURSE_PRICE = Decimal("500000.00")


async def _setup(session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)
    return manager, student, enrollment


async def test_rejected_payment_keeps_enrollment_awaiting(client, session):
    manager, student, enrollment = await _setup(session)

    payment = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )
    reject = await client.post(
        f"/api/payments/{payment.json()['id']}/reject",
        json={"reason": "Chek ko'rinmayapti"},
        headers=auth_headers(manager),
    )

    assert reject.status_code == 200
    assert reject.json()["status"] == PaymentStatus.rejected.value
    assert reject.json()["note"] == "Chek ko'rinmayapti"

    await session.refresh(enrollment)
    assert enrollment.status == EnrollmentStatus.awaiting_payment


async def test_student_can_pay_again_after_rejection(client, session):
    manager, student, enrollment = await _setup(session)

    first_payment = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )
    await client.post(
        f"/api/payments/{first_payment.json()['id']}/reject",
        json={"reason": "Noto'g'ri chek"},
        headers=auth_headers(manager),
    )

    second_payment = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )
    assert second_payment.status_code == 201

    confirm = await client.post(
        f"/api/payments/{second_payment.json()['id']}/confirm", headers=auth_headers(manager)
    )
    assert confirm.status_code == 200

    await session.refresh(enrollment)
    assert enrollment.status == EnrollmentStatus.active


async def test_rejected_installment_payment_keeps_installment_pending(client, session):
    manager, student, enrollment = await _setup(session)

    plan = await client.post(
        f"/api/enrollments/{enrollment.id}/payment-plan",
        json={"installments_count": 2},
        headers=auth_headers(student),
    )
    first_installment = plan.json()["installments"][0]

    payment = await client.post(
        "/api/payments",
        json={
            "installment_id": first_installment["id"],
            "amount": first_installment["amount_due"],
        },
        headers=auth_headers(student),
    )
    await client.post(
        f"/api/payments/{payment.json()['id']}/reject",
        json={"reason": "Summa mos emas"},
        headers=auth_headers(manager),
    )

    plan_after = await client.get(
        f"/api/enrollments/{enrollment.id}/payment-plan", headers=auth_headers(student)
    )
    assert (
        plan_after.json()["installments"][0]["status"] == InstallmentStatus.pending.value
    )


async def test_reject_requires_reason(client, session):
    manager, student, enrollment = await _setup(session)

    payment = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )
    response = await client.post(
        f"/api/payments/{payment.json()['id']}/reject",
        json={},
        headers=auth_headers(manager),
    )

    assert response.status_code == 422
