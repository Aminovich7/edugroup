"""Manager profillarni tasdiqlaydi va rad etadi."""

from app.users.models import UserStatus
from tests.conftest import auth_headers
from tests.factories import create_manager, create_student, create_teacher


async def test_manager_approves_teacher(client, session):
    manager = await create_manager(session)
    teacher = await create_teacher(session, status=UserStatus.pending)

    response = await client.post(
        f"/api/manager/users/{teacher.id}/approve", headers=auth_headers(manager)
    )

    assert response.status_code == 200
    assert response.json()["status"] == UserStatus.approved.value


async def test_manager_rejects_student_with_reason(client, session):
    manager = await create_manager(session)
    student = await create_student(session, status=UserStatus.pending)

    response = await client.post(
        f"/api/manager/users/{student.id}/reject",
        json={"reason": "Ma'lumotlar to'liq emas"},
        headers=auth_headers(manager),
    )

    assert response.status_code == 200
    assert response.json()["status"] == UserStatus.rejected.value


async def test_student_cannot_approve_users(client, session):
    student = await create_student(session)
    other_student = await create_student(session, status=UserStatus.pending)

    response = await client.post(
        f"/api/manager/users/{other_student.id}/approve", headers=auth_headers(student)
    )

    assert response.status_code == 403


async def test_manager_cannot_approve_another_manager(client, session):
    manager = await create_manager(session)
    other_manager = await create_manager(session)

    response = await client.post(
        f"/api/manager/users/{other_manager.id}/approve", headers=auth_headers(manager)
    )

    assert response.status_code == 400


async def test_pending_users_list_is_filtered(client, session):
    manager = await create_manager(session)
    await create_teacher(session, status=UserStatus.pending)
    await create_teacher(session, status=UserStatus.approved)

    response = await client.get(
        "/api/manager/users?status=pending&role=teacher", headers=auth_headers(manager)
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
