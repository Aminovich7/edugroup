"""Student darsni ko'rilgan deb belgilaydi, teacher buni progress jadvalida ko'radi."""

from app.enrollments.models import EnrollmentStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_lesson,
    create_student,
    create_teacher,
)


async def test_student_marks_lesson_watched_and_teacher_sees_it(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    first_lesson = await create_lesson(session, group, title="1-dars", order_index=1)
    await create_lesson(session, group, title="2-dars", order_index=2)

    student = await create_student(session, full_name="Ali Valiyev")
    await create_enrollment(session, student, group, status=EnrollmentStatus.active)

    mark_response = await client.post(
        f"/api/lessons/{first_lesson.id}/progress", headers=auth_headers(student)
    )
    assert mark_response.status_code == 201
    assert mark_response.json()["watched"] is True

    progress_response = await client.get(
        f"/api/groups/{group.id}/progress", headers=auth_headers(teacher)
    )
    assert progress_response.status_code == 200
    rows = progress_response.json()
    assert rows[0]["student_name"] == "Ali Valiyev"
    assert rows[0]["watched_lessons"] == 1
    assert rows[0]["total_lessons"] == 2


async def test_marking_twice_keeps_single_record(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    lesson = await create_lesson(session, group)
    student = await create_student(session)
    await create_enrollment(session, student, group, status=EnrollmentStatus.active)

    await client.post(f"/api/lessons/{lesson.id}/progress", headers=auth_headers(student))
    second = await client.post(
        f"/api/lessons/{lesson.id}/progress", headers=auth_headers(student)
    )

    assert second.status_code == 201

    progress = await client.get(
        f"/api/groups/{group.id}/progress", headers=auth_headers(teacher)
    )
    assert progress.json()[0]["watched_lessons"] == 1


async def test_student_without_active_enrollment_cannot_mark_progress(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    lesson = await create_lesson(session, group)
    student = await create_student(session)

    response = await client.post(
        f"/api/lessons/{lesson.id}/progress", headers=auth_headers(student)
    )

    assert response.status_code == 403


async def test_other_teacher_cannot_view_group_progress(client, session):
    teacher = await create_teacher(session)
    stranger = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)

    response = await client.get(
        f"/api/groups/{group.id}/progress", headers=auth_headers(stranger)
    )

    assert response.status_code == 403
