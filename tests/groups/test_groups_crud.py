"""Guruh CRUD va holat o'tishlari."""

from app.groups.models import GroupStatus
from tests.conftest import auth_headers
from tests.factories import (
    create_course,
    create_group,
    create_manager,
    create_student,
    create_teacher,
)


async def test_teacher_creates_draft_group(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)

    response = await client.post(
        "/api/groups",
        json={
            "course_id": str(course.id),
            "name": "Guruh B",
            "capacity": 8,
            "schedule": "Sesh, Pay 19:00",
        },
        headers=auth_headers(teacher),
    )

    assert response.status_code == 201
    assert response.json()["status"] == GroupStatus.draft.value


async def test_teacher_cannot_create_group_in_other_course(client, session):
    owner = await create_teacher(session)
    stranger = await create_teacher(session)
    course = await create_course(session, owner)

    response = await client.post(
        "/api/groups",
        json={
            "course_id": str(course.id),
            "name": "Guruh",
            "capacity": 8,
            "schedule": "Dush 10:00",
        },
        headers=auth_headers(stranger),
    )

    assert response.status_code == 403


async def test_public_list_shows_only_active_groups(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    await create_group(session, course, teacher, name="Faol", status=GroupStatus.active)
    await create_group(session, course, teacher, name="Qoralama", status=GroupStatus.draft)
    await create_group(session, course, teacher, name="Yopilgan", status=GroupStatus.closed)

    response = await client.get("/api/groups")

    assert response.status_code == 200
    names = [group["name"] for group in response.json()]
    assert names == ["Faol"]


async def test_group_response_contains_seat_info(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, capacity=5)

    response = await client.get(f"/api/groups/{group.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["free_seats"] == 5
    assert body["occupied_seats"] == 0
    assert body["waitlist_count"] == 0


async def test_manager_closes_active_group(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, status=GroupStatus.active)

    response = await client.patch(
        f"/api/groups/{group.id}",
        json={"status": GroupStatus.closed.value},
        headers=auth_headers(manager),
    )

    assert response.status_code == 200
    assert response.json()["status"] == GroupStatus.closed.value


async def test_teacher_cannot_change_group_status(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, status=GroupStatus.active)

    response = await client.patch(
        f"/api/groups/{group.id}",
        json={"status": GroupStatus.closed.value},
        headers=auth_headers(teacher),
    )

    assert response.status_code == 403


async def test_invalid_status_transition_is_rejected(client, session):
    """draft -> closed o'tishi mumkin emas: guruh avval assign-teacher orqali faollashadi."""
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, status=GroupStatus.draft)

    response = await client.patch(
        f"/api/groups/{group.id}",
        json={"status": GroupStatus.closed.value},
        headers=auth_headers(manager),
    )

    assert response.status_code == 400


async def test_student_cannot_view_group_students(client, session):
    student = await create_student(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher)

    response = await client.get(
        f"/api/groups/{group.id}/students", headers=auth_headers(student)
    )

    assert response.status_code == 403
