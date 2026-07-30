"""Manager guruhga teacher biriktiradi va guruhni faollashtiradi."""

from app.groups.models import GroupStatus
from app.users.models import UserStatus
from tests.conftest import auth_headers
from tests.factories import create_course, create_group, create_manager, create_teacher


async def test_assign_teacher_activates_draft_group(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, status=GroupStatus.draft)

    response = await client.post(
        f"/api/manager/groups/{group.id}/assign-teacher",
        json={},
        headers=auth_headers(manager),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == GroupStatus.active.value
    assert body["approved_by"] == str(manager.id)


async def test_assign_teacher_can_replace_teacher(client, session):
    manager = await create_manager(session)
    first_teacher = await create_teacher(session)
    second_teacher = await create_teacher(session)
    course = await create_course(session, first_teacher)
    group = await create_group(session, course, first_teacher, status=GroupStatus.draft)

    response = await client.post(
        f"/api/manager/groups/{group.id}/assign-teacher",
        json={"teacher_id": str(second_teacher.id)},
        headers=auth_headers(manager),
    )

    assert response.status_code == 200
    assert response.json()["teacher_id"] == str(second_teacher.id)


async def test_cannot_assign_unapproved_teacher(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session)
    pending_teacher = await create_teacher(session, status=UserStatus.pending)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, status=GroupStatus.draft)

    response = await client.post(
        f"/api/manager/groups/{group.id}/assign-teacher",
        json={"teacher_id": str(pending_teacher.id)},
        headers=auth_headers(manager),
    )

    assert response.status_code == 400


async def test_teacher_cannot_assign_teacher(client, session):
    teacher = await create_teacher(session)
    course = await create_course(session, teacher)
    group = await create_group(session, course, teacher, status=GroupStatus.draft)

    response = await client.post(
        f"/api/manager/groups/{group.id}/assign-teacher",
        json={},
        headers=auth_headers(teacher),
    )

    assert response.status_code == 403
