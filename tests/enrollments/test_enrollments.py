"""Guruhga yozilish: asosiy holatlar va cheklovlar."""

from app.enrollments.models import EnrollmentStatus
from app.groups.models import GroupStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_manager,
    create_student,
    create_teacher,
)


async def test_student_enrolls_into_free_group(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=5)
    student = await create_student(session)

    response = await client.post(
        "/api/enrollments", json={"group_id": str(group.id)}, headers=auth_headers(student)
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == EnrollmentStatus.awaiting_payment.value
    assert body["waitlist_position"] is None


async def test_double_enrollment_returns_400(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=5)
    student = await create_student(session)
    await create_enrollment(session, student, group)

    response = await client.post(
        "/api/enrollments", json={"group_id": str(group.id)}, headers=auth_headers(student)
    )

    assert response.status_code == 400


async def test_cannot_enroll_into_closed_group(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, status=GroupStatus.closed)
    student = await create_student(session)

    response = await client.post(
        "/api/enrollments", json={"group_id": str(group.id)}, headers=auth_headers(student)
    )

    assert response.status_code == 400


async def test_teacher_cannot_enroll(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)

    response = await client.post(
        "/api/enrollments", json={"group_id": str(group.id)}, headers=auth_headers(teacher)
    )

    assert response.status_code == 403


async def test_student_sees_own_enrollments(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    other_student = await create_student(session)
    await create_enrollment(session, student, group)
    await create_enrollment(session, other_student, group)

    response = await client.get("/api/enrollments/me", headers=auth_headers(student))

    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_manager_sees_all_enrollments_with_filter(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)

    first_student = await create_student(session)
    second_student = await create_student(session)
    await create_enrollment(session, first_student, group, status=EnrollmentStatus.active)
    await create_enrollment(
        session, second_student, group, status=EnrollmentStatus.awaiting_payment
    )

    all_response = await client.get("/api/enrollments", headers=auth_headers(manager))
    assert len(all_response.json()) == 2

    filtered = await client.get(
        "/api/enrollments?status=active", headers=auth_headers(manager)
    )
    assert len(filtered.json()) == 1


async def test_student_cannot_list_all_enrollments(client, session):
    student = await create_student(session)

    response = await client.get("/api/enrollments", headers=auth_headers(student))

    assert response.status_code == 403


async def test_student_cancels_own_enrollment(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)

    response = await client.request(
        "DELETE", f"/api/enrollments/{enrollment.id}", headers=auth_headers(student)
    )

    assert response.status_code == 200
    assert response.json()["status"] == EnrollmentStatus.cancelled.value


async def test_manager_must_give_reason_when_cancelling(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)

    without_reason = await client.request(
        "DELETE", f"/api/enrollments/{enrollment.id}", headers=auth_headers(manager)
    )
    assert without_reason.status_code == 400

    with_reason = await client.request(
        "DELETE",
        f"/api/enrollments/{enrollment.id}",
        json={"reason": "Guruh qayta tuzildi"},
        headers=auth_headers(manager),
    )
    assert with_reason.status_code == 200
    assert with_reason.json()["cancel_reason"] == "Guruh qayta tuzildi"


async def test_other_student_cannot_cancel_enrollment(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    stranger = await create_student(session)
    enrollment = await create_enrollment(session, student, group)

    response = await client.request(
        "DELETE", f"/api/enrollments/{enrollment.id}", headers=auth_headers(stranger)
    )

    assert response.status_code == 403
