"""Bo'lib to'lash: birinchi bo'lak enrollment'ni faollashtiradi,
oxirgi bo'lak rejani completed qiladi."""

from decimal import Decimal

from app.enrollments.models import EnrollmentStatus
from app.payments.models import InstallmentStatus, PaymentPlan, PaymentPlanStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_manager,
    create_student,
    create_teacher,
)

COURSE_PRICE = Decimal("600000.00")


async def _setup(session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)
    return manager, student, enrollment


async def test_plan_splits_price_into_equal_installments(client, session):
    _, student, enrollment = await _setup(session)

    response = await client.post(
        f"/api/enrollments/{enrollment.id}/payment-plan",
        json={"installments_count": 3},
        headers=auth_headers(student),
    )

    assert response.status_code == 201
    body = response.json()
    assert len(body["installments"]) == 3
    total = sum(Decimal(item["amount_due"]) for item in body["installments"])
    # Bo'laklar yig'indisi aynan kurs narxiga teng bo'lishi shart.
    assert total == COURSE_PRICE


async def test_uneven_price_puts_remainder_into_last_installment(client, session):
    """500 000 ni 3 ga bo'lganda tiyin qolmaydi: 166 666 + 166 666 + 166 668."""
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=Decimal("500000.00"))
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)

    response = await client.post(
        f"/api/enrollments/{enrollment.id}/payment-plan",
        json={"installments_count": 3},
        headers=auth_headers(student),
    )

    amounts = [Decimal(item["amount_due"]) for item in response.json()["installments"]]
    assert amounts == [Decimal("166666"), Decimal("166666"), Decimal("166668")]
    assert sum(amounts) == Decimal("500000")
    # Hech bir bo'lakda tiyin qolmaydi.
    assert all(amount == amount.to_integral_value() for amount in amounts)


async def test_first_confirmed_installment_activates_enrollment(client, session):
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
        f"/api/payments/{payment.json()['id']}/confirm", headers=auth_headers(manager)
    )

    await session.refresh(enrollment)
    assert enrollment.status == EnrollmentStatus.active


async def test_last_installment_completes_the_plan(client, session):
    manager, student, enrollment = await _setup(session)

    plan_response = await client.post(
        f"/api/enrollments/{enrollment.id}/payment-plan",
        json={"installments_count": 2},
        headers=auth_headers(student),
    )
    plan_id = plan_response.json()["id"]

    for installment in plan_response.json()["installments"]:
        payment = await client.post(
            "/api/payments",
            json={"installment_id": installment["id"], "amount": installment["amount_due"]},
            headers=auth_headers(student),
        )
        await client.post(
            f"/api/payments/{payment.json()['id']}/confirm", headers=auth_headers(manager)
        )

    plan = await session.get(PaymentPlan, plan_id)
    await session.refresh(plan)
    assert plan.status == PaymentPlanStatus.completed
    assert all(item.status == InstallmentStatus.paid for item in plan.installments)


async def test_second_plan_for_same_enrollment_returns_400(client, session):
    _, student, enrollment = await _setup(session)

    await client.post(
        f"/api/enrollments/{enrollment.id}/payment-plan",
        json={"installments_count": 2},
        headers=auth_headers(student),
    )
    second = await client.post(
        f"/api/enrollments/{enrollment.id}/payment-plan",
        json={"installments_count": 3},
        headers=auth_headers(student),
    )

    assert second.status_code == 400


async def test_installments_count_outside_range_returns_422(client, session):
    _, student, enrollment = await _setup(session)

    response = await client.post(
        f"/api/enrollments/{enrollment.id}/payment-plan",
        json={"installments_count": 5},
        headers=auth_headers(student),
    )

    assert response.status_code == 422


async def test_full_payment_is_rejected_when_plan_exists(client, session):
    """Reja bor bo'lsa, to'liq summani bir yo'la to'lash mumkin emas — bo'lak tanlanadi."""
    _, student, enrollment = await _setup(session)

    await client.post(
        f"/api/enrollments/{enrollment.id}/payment-plan",
        json={"installments_count": 2},
        headers=auth_headers(student),
    )

    response = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )

    assert response.status_code == 400
