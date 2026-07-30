"""Video havolasini faqat to'lovi tasdiqlangan student ko'ra oladi."""

from app.enrollments.models import EnrollmentStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_enrollment,
    create_group,
    create_lesson,
    create_manager,
    create_student,
    create_teacher,
)


async def _setup_group_with_lesson(session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    lesson = await create_lesson(session, group)
    return teacher, group, lesson


async def test_student_with_active_enrollment_gets_video_url(client, session):
    teacher, group, lesson = await _setup_group_with_lesson(session)
    student = await create_student(session)
    await create_enrollment(session, student, group, status=EnrollmentStatus.active)

    response = await client.get(f"/api/lessons/{lesson.id}", headers=auth_headers(student))

    assert response.status_code == 200
    assert response.json()["kinescope_url"] == lesson.kinescope_url


async def test_student_awaiting_payment_cannot_see_video(client, session):
    teacher, group, lesson = await _setup_group_with_lesson(session)
    student = await create_student(session)
    await create_enrollment(session, student, group, status=EnrollmentStatus.awaiting_payment)

    response = await client.get(f"/api/lessons/{lesson.id}", headers=auth_headers(student))

    assert response.status_code == 403


async def test_student_without_enrollment_cannot_see_video(client, session):
    teacher, group, lesson = await _setup_group_with_lesson(session)
    student = await create_student(session)

    response = await client.get(f"/api/lessons/{lesson.id}", headers=auth_headers(student))

    assert response.status_code == 403


async def test_group_teacher_can_see_video(client, session):
    teacher, group, lesson = await _setup_group_with_lesson(session)

    response = await client.get(f"/api/lessons/{lesson.id}", headers=auth_headers(teacher))

    assert response.status_code == 200


async def test_manager_can_see_video(client, session):
    teacher, group, lesson = await _setup_group_with_lesson(session)
    manager = await create_manager(session)

    response = await client.get(f"/api/lessons/{lesson.id}", headers=auth_headers(manager))

    assert response.status_code == 200


async def test_other_teacher_cannot_see_video(client, session):
    teacher, group, lesson = await _setup_group_with_lesson(session)
    stranger = await create_teacher(session)

    response = await client.get(f"/api/lessons/{lesson.id}", headers=auth_headers(stranger))

    assert response.status_code == 403
