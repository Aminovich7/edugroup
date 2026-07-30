"""Superadmin manager akkaunti yaratadi (TZ 6.11)."""

from app.users.models import UserRole, UserStatus
from tests.conftest import auth_headers
from tests.factories import create_manager, create_superadmin, create_teacher


async def test_superadmin_creates_active_manager(client, session):
    superadmin = await create_superadmin(session)

    response = await client.post(
        "/api/superadmin/managers",
        json={
            "full_name": "Yangi Manager",
            "email": "manager@test.uz",
            "password": "parol12345",
        },
        headers=auth_headers(superadmin),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == UserRole.manager.value
    # Manager moderatsiyasiz, darhol faol bo'ladi.
    assert body["status"] == UserStatus.approved.value
    assert body["is_active"] is True


async def test_manager_cannot_create_manager(client, session):
    manager = await create_manager(session)

    response = await client.post(
        "/api/superadmin/managers",
        json={"full_name": "Boshqa", "email": "boshqa@test.uz", "password": "parol12345"},
        headers=auth_headers(manager),
    )

    assert response.status_code == 403


async def test_teacher_cannot_list_managers(client, session):
    teacher = await create_teacher(session)

    response = await client.get("/api/superadmin/managers", headers=auth_headers(teacher))

    assert response.status_code == 403


async def test_superadmin_lists_managers(client, session):
    superadmin = await create_superadmin(session)
    await create_manager(session)
    await create_manager(session)

    response = await client.get("/api/superadmin/managers", headers=auth_headers(superadmin))

    assert response.status_code == 200
    assert len(response.json()) == 2
