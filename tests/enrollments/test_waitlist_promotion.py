"""Navbat (waitlist): to'la guruhga yozilish va joy bo'shaganda avtomatik ko'tarilish."""

from app.enrollments.models import EnrollmentStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_student,
    create_teacher,
)


async def test_enrollment_into_full_group_goes_to_waitlist(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=1)

    seated_student = await create_student(session)
    await create_enrollment(session, seated_student, group, status=EnrollmentStatus.active)

    waiting_student = await create_student(session)
    response = await client.post(
        "/api/enrollments",
        json={"group_id": str(group.id)},
        headers=auth_headers(waiting_student),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == EnrollmentStatus.waitlisted.value
    assert body["waitlist_position"] == 1


async def test_waitlist_positions_are_sequential(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=1)

    seated_student = await create_student(session)
    await create_enrollment(session, seated_student, group, status=EnrollmentStatus.active)

    positions = []
    for _ in range(3):
        student = await create_student(session)
        response = await client.post(
            "/api/enrollments",
            json={"group_id": str(group.id)},
            headers=auth_headers(student),
        )
        positions.append(response.json()["waitlist_position"])

    assert positions == [1, 2, 3]


async def test_cancelling_active_enrollment_promotes_next_student(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=1)

    seated_student = await create_student(session)
    seated_enrollment = await create_enrollment(
        session, seated_student, group, status=EnrollmentStatus.active
    )

    first_waiting = await create_student(session)
    second_waiting = await create_student(session)
    first_enrollment = await create_enrollment(
        session, first_waiting, group, status=EnrollmentStatus.waitlisted, waitlist_position=1
    )
    second_enrollment = await create_enrollment(
        session, second_waiting, group, status=EnrollmentStatus.waitlisted, waitlist_position=2
    )

    await client.request(
        "DELETE", f"/api/enrollments/{seated_enrollment.id}", headers=auth_headers(seated_student)
    )

    await session.refresh(first_enrollment)
    await session.refresh(second_enrollment)

    # Birinchi navbatdagi to'lov kutish holatiga ko'tariladi.
    assert first_enrollment.status == EnrollmentStatus.awaiting_payment
    assert first_enrollment.waitlist_position is None
    # Qolganlarning pozitsiyasi qayta hisoblanadi.
    assert second_enrollment.status == EnrollmentStatus.waitlisted
    assert second_enrollment.waitlist_position == 1


async def test_cancelling_waitlisted_enrollment_reindexes_queue(client, session):
    """Navbatdagi student chiqib ketsa — joy bo'shamaydi, faqat navbat qayta raqamlanadi."""
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=1)

    seated_student = await create_student(session)
    await create_enrollment(session, seated_student, group, status=EnrollmentStatus.active)

    first_waiting = await create_student(session)
    second_waiting = await create_student(session)
    first_enrollment = await create_enrollment(
        session, first_waiting, group, status=EnrollmentStatus.waitlisted, waitlist_position=1
    )
    second_enrollment = await create_enrollment(
        session, second_waiting, group, status=EnrollmentStatus.waitlisted, waitlist_position=2
    )

    await client.request(
        "DELETE", f"/api/enrollments/{first_enrollment.id}", headers=auth_headers(first_waiting)
    )

    await session.refresh(second_enrollment)
    assert second_enrollment.status == EnrollmentStatus.waitlisted
    assert second_enrollment.waitlist_position == 1


async def test_teacher_sees_group_waitlist(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=1)

    seated_student = await create_student(session)
    await create_enrollment(session, seated_student, group, status=EnrollmentStatus.active)
    waiting_student = await create_student(session)
    await create_enrollment(
        session, waiting_student, group, status=EnrollmentStatus.waitlisted, waitlist_position=1
    )

    response = await client.get(
        f"/api/groups/{group.id}/waitlist", headers=auth_headers(teacher)
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["waitlist_position"] == 1


async def test_student_cannot_see_full_waitlist(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    student = await create_student(session)

    response = await client.get(
        f"/api/groups/{group.id}/waitlist", headers=auth_headers(student)
    )

    assert response.status_code == 403
