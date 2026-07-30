"""Dars CRUD: qo'shish, tahrirlash, soft delete va tiklash."""

from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_group,
    create_lesson,
    create_superadmin,
    create_teacher,
)

VALID_LESSON = {
    "title": "1-dars: Kirish",
    "kinescope_video_id": "abc123",
    "kinescope_url": "https://kinescope.io/abc123",
    "duration_seconds": 420,
    "order_index": 1,
}


async def test_teacher_adds_lesson_to_own_group(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)

    response = await client.post(
        f"/api/groups/{group.id}/lessons", json=VALID_LESSON, headers=auth_headers(teacher)
    )

    assert response.status_code == 201
    assert response.json()["kinescope_url"] == VALID_LESSON["kinescope_url"]


async def test_teacher_cannot_add_lesson_to_other_group(client, session):
    owner = await create_teacher(session)
    stranger = await create_teacher(session)
    course = await create_course(session, owner)
    group = await create_group(session, course, owner)

    response = await client.post(
        f"/api/groups/{group.id}/lessons", json=VALID_LESSON, headers=auth_headers(stranger)
    )

    assert response.status_code == 403


async def test_teacher_updates_own_lesson(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    lesson = await create_lesson(session, group)

    response = await client.patch(
        f"/api/lessons/{lesson.id}",
        json={"title": "Yangilangan dars"},
        headers=auth_headers(teacher),
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Yangilangan dars"


async def test_lesson_delete_is_soft_and_restore_works(client, session):
    teacher = await create_teacher(session)
    superadmin = await create_superadmin(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)
    lesson = await create_lesson(session, group)

    delete_response = await client.delete(
        f"/api/lessons/{lesson.id}", headers=auth_headers(teacher)
    )
    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_at"] is not None

    restore_response = await client.post(
        f"/api/lessons/{lesson.id}/restore", headers=auth_headers(superadmin)
    )
    assert restore_response.status_code == 200
    assert restore_response.json()["deleted_at"] is None
