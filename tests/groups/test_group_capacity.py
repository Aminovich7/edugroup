"""Guruh sig'imi qoidalari: band joylarni hisoblash va sig'imni kamaytirish cheklovi."""

from app.enrollments.models import EnrollmentStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_manager,
    create_student,
    create_teacher,
)


async def test_awaiting_payment_counts_as_occupied_seat(client, session):
    """To'lov kutayotgan joy ham band hisoblanadi — bu overselling'ning oldini oladi."""
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=3)

    student_awaiting = await create_student(session)
    student_active = await create_student(session)
    student_waiting = await create_student(session)

    await create_enrollment(
        session, student_awaiting, group, status=EnrollmentStatus.awaiting_payment
    )
    await create_enrollment(session, student_active, group, status=EnrollmentStatus.active)
    await create_enrollment(
        session, student_waiting, group, status=EnrollmentStatus.waitlisted, waitlist_position=1
    )

    response = await client.get(f"/api/groups/{group.id}")

    body = response.json()
    assert body["occupied_seats"] == 2   # waitlisted joy band qilmaydi
    assert body["free_seats"] == 1
    assert body["waitlist_count"] == 1


async def test_capacity_cannot_drop_below_existing_students(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=5)

    for _ in range(3):
        student = await create_student(session)
        await create_enrollment(session, student, group, status=EnrollmentStatus.active)

    response = await client.patch(
        f"/api/groups/{group.id}", json={"capacity": 2}, headers=auth_headers(manager)
    )

    assert response.status_code == 422


async def test_capacity_can_be_increased(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=5)

    response = await client.patch(
        f"/api/groups/{group.id}", json={"capacity": 20}, headers=auth_headers(manager)
    )

    assert response.status_code == 200
    assert response.json()["capacity"] == 20
