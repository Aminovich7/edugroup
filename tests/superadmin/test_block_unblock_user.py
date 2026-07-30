"""Bloklangan foydalanuvchi login va refresh qila olmaydi (TZ 6.11)."""

from app.users.models import UserStatus
from tests.conftest import auth_headers
from tests.factories import DEFAULT_PASSWORD, create_manager, create_student, create_superadmin


async def test_blocked_user_cannot_login_and_can_after_unblock(client, session):
    superadmin = await create_superadmin(session)
    student = await create_student(session, email="blok-oqim@test.uz")

    block = await client.post(
        f"/api/superadmin/users/{student.id}/block", headers=auth_headers(superadmin)
    )
    assert block.status_code == 200
    assert block.json()["status"] == UserStatus.blocked.value

    login_while_blocked = await client.post(
        "/api/auth/login", json={"email": student.email, "password": DEFAULT_PASSWORD}
    )
    assert login_while_blocked.status_code == 403

    unblock = await client.post(
        f"/api/superadmin/users/{student.id}/unblock", headers=auth_headers(superadmin)
    )
    assert unblock.status_code == 200

    login_after_unblock = await client.post(
        "/api/auth/login", json={"email": student.email, "password": DEFAULT_PASSWORD}
    )
    assert login_after_unblock.status_code == 200


async def test_block_revokes_existing_refresh_tokens(client, session):
    superadmin = await create_superadmin(session)
    student = await create_student(session, email="token-blok@test.uz")

    login = await client.post(
        "/api/auth/login", json={"email": student.email, "password": DEFAULT_PASSWORD}
    )
    refresh_token = login.json()["refresh_token"]

    await client.post(
        f"/api/superadmin/users/{student.id}/block", headers=auth_headers(superadmin)
    )

    response = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 401


async def test_manager_cannot_block_user(client, session):
    manager = await create_manager(session)
    student = await create_student(session)

    response = await client.post(
        f"/api/superadmin/users/{student.id}/block", headers=auth_headers(manager)
    )

    assert response.status_code == 403


async def test_superadmin_cannot_block_self(client, session):
    superadmin = await create_superadmin(session)

    response = await client.post(
        f"/api/superadmin/users/{superadmin.id}/block", headers=auth_headers(superadmin)
    )

    assert response.status_code == 400
