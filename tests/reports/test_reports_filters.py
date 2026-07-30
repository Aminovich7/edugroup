"""Hisobotlar: umumiy statistika, daromad filtrlari va ruxsatlar."""

from decimal import Decimal

from app.enrollments.models import EnrollmentStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_lesson,
    create_manager,
    create_student,
    create_superadmin,
    create_teacher,
)

COURSE_PRICE = Decimal("500000.00")


async def _confirmed_payment(client, session, manager, student, enrollment):
    payment = await client.post(
        "/api/payments",
        json={"enrollment_id": str(enrollment.id), "amount": str(COURSE_PRICE)},
        headers=auth_headers(student),
    )
    await client.post(
        f"/api/payments/{payment.json()['id']}/confirm", headers=auth_headers(manager)
    )


async def test_overview_counts_users_and_revenue(client, session):
    superadmin = await create_superadmin(session)
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)
    await _confirmed_payment(client, session, manager, student, enrollment)

    response = await client.get("/api/reports/overview", headers=auth_headers(superadmin))

    assert response.status_code == 200
    body = response.json()
    assert body["total_students"] == 1
    assert body["total_teachers"] == 1
    assert body["total_managers"] == 1
    assert body["active_groups"] == 1
    assert body["active_enrollments"] == 1
    assert Decimal(body["total_revenue"]) == COURSE_PRICE


async def test_manager_cannot_read_global_overview(client, session):
    manager = await create_manager(session)

    response = await client.get("/api/reports/overview", headers=auth_headers(manager))

    assert response.status_code == 403


async def test_revenue_report_groups_by_group(client, session):
    superadmin = await create_superadmin(session)
    manager = await create_manager(session)
    teacher = await create_teacher(session, full_name="Dilnoza Karimova")
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher, name="Guruh A")
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)
    await _confirmed_payment(client, session, manager, student, enrollment)

    response = await client.get("/api/reports/revenue", headers=auth_headers(superadmin))

    assert response.status_code == 200
    rows = response.json()["rows"]
    assert len(rows) == 1
    assert rows[0]["group_name"] == "Guruh A"
    assert rows[0]["teacher_name"] == "Dilnoza Karimova"
    assert rows[0]["payments_count"] == 1


async def test_revenue_filter_by_teacher_excludes_others(client, session):
    superadmin = await create_superadmin(session)
    manager = await create_manager(session)

    first_teacher = await create_teacher(session)
    first_course = await create_course(session, first_teacher, price=COURSE_PRICE)
    first_group = await create_group(session, first_course, first_teacher)
    first_student = await create_student(session)
    first_enrollment = await create_enrollment(session, first_student, first_group)
    await _confirmed_payment(client, session, manager, first_student, first_enrollment)

    second_teacher = await create_teacher(session)
    second_course = await create_course(session, second_teacher, price=COURSE_PRICE)
    second_group = await create_group(session, second_course, second_teacher)
    second_student = await create_student(session)
    second_enrollment = await create_enrollment(session, second_student, second_group)
    await _confirmed_payment(client, session, manager, second_student, second_enrollment)

    response = await client.get(
        f"/api/reports/revenue?teacher_id={first_teacher.id}",
        headers=auth_headers(superadmin),
    )

    rows = response.json()["rows"]
    assert len(rows) == 1
    assert Decimal(response.json()["total_amount"]) == COURSE_PRICE


async def test_group_report_shows_students_and_lessons(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher, capacity=3)
    await create_lesson(session, group)

    active_student = await create_student(session)
    waiting_student = await create_student(session)
    await create_enrollment(session, active_student, group, status=EnrollmentStatus.active)
    await create_enrollment(
        session, waiting_student, group, status=EnrollmentStatus.waitlisted, waitlist_position=1
    )

    response = await client.get(
        f"/api/reports/groups/{group.id}", headers=auth_headers(manager)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["active_students"] == 1
    assert body["waitlisted_students"] == 1
    assert body["lessons_count"] == 1
    assert body["capacity"] == 3


async def test_teacher_sees_own_group_report_but_not_others(client, session):
    owner = await create_teacher(session)
    stranger = await create_teacher(session)
    course = await create_course(session, owner)
    group = await create_group(session, course, owner)

    allowed = await client.get(
        f"/api/reports/groups/{group.id}", headers=auth_headers(owner)
    )
    forbidden = await client.get(
        f"/api/reports/groups/{group.id}", headers=auth_headers(stranger)
    )

    assert allowed.status_code == 200
    assert forbidden.status_code == 403


async def test_teacher_report_aggregates_groups_and_revenue(client, session):
    superadmin = await create_superadmin(session)
    manager = await create_manager(session)
    teacher = await create_teacher(session, full_name="Dilnoza")
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    await create_lesson(session, group)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)
    await _confirmed_payment(client, session, manager, student, enrollment)

    response = await client.get(
        f"/api/reports/teachers/{teacher.id}", headers=auth_headers(superadmin)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["teacher_name"] == "Dilnoza"
    assert body["groups_count"] == 1
    assert body["active_students"] == 1
    assert body["lessons_count"] == 1
    assert Decimal(body["total_revenue"]) == COURSE_PRICE


async def test_student_cannot_read_teacher_report(client, session):
    student = await create_student(session)
    teacher = await create_teacher(session)

    response = await client.get(
        f"/api/reports/teachers/{teacher.id}", headers=auth_headers(student)
    )

    assert response.status_code == 403


async def test_payments_list_filters_and_totals(client, session):
    superadmin = await create_superadmin(session)
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher, price=COURSE_PRICE)
    group = await create_group(session, course, teacher)
    student = await create_student(session)
    enrollment = await create_enrollment(session, student, group)
    await _confirmed_payment(client, session, manager, student, enrollment)

    response = await client.get(
        "/api/payments?status=confirmed", headers=auth_headers(superadmin)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 1
    assert Decimal(body["total_amount"]) == COURSE_PRICE
