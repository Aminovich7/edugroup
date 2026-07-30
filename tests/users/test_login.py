"""Login: to'g'ri parol, noto'g'ri parol va bloklangan akkaunt."""

from app.users.models import UserStatus
from tests.factories import DEFAULT_PASSWORD, create_student


async def test_login_returns_token_pair(client, session):
    student = await create_student(session, email="login@test.uz")

    response = await client.post(
        "/api/auth/login", json={"email": student.email, "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]


async def test_login_with_wrong_password_returns_401(client, session):
    student = await create_student(session, email="xato@test.uz")

    response = await client.post(
        "/api/auth/login", json={"email": student.email, "password": "notogriparol"}
    )

    assert response.status_code == 401


async def test_blocked_user_cannot_login(client, session):
    student = await create_student(
        session, email="blok@test.uz", status=UserStatus.blocked, is_active=False
    )

    response = await client.post(
        "/api/auth/login", json={"email": student.email, "password": DEFAULT_PASSWORD}
    )

    assert response.status_code == 403


async def test_logout_revokes_refresh_token(client, session):
    student = await create_student(session, email="chiqish@test.uz")
    login = await client.post(
        "/api/auth/login", json={"email": student.email, "password": DEFAULT_PASSWORD}
    )
    refresh_token = login.json()["refresh_token"]

    logout = await client.post(
        "/api/auth/logout",
        json={"refresh_token": refresh_token},
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert logout.status_code == 204

    # Bekor qilingan token bilan yangilash mumkin emas.
    refresh = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh.status_code == 401
