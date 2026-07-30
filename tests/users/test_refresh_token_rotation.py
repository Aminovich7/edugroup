"""Refresh token rotatsiyasi va qayta ishlatishni aniqlash (reuse detection)."""

from tests.factories import DEFAULT_PASSWORD, create_student


async def _login(client, student):
    response = await client.post(
        "/api/auth/login", json={"email": student.email, "password": DEFAULT_PASSWORD}
    )
    return response.json()["refresh_token"]


async def test_refresh_returns_new_tokens(client, session):
    student = await create_student(session, email="rotatsiya@test.uz")
    old_refresh_token = await _login(client, student)

    response = await client.post(
        "/api/auth/refresh", json={"refresh_token": old_refresh_token}
    )

    assert response.status_code == 200
    assert response.json()["refresh_token"] != old_refresh_token


async def test_reused_refresh_token_revokes_all_sessions(client, session):
    """Eski token qayta ishlatilsa — o'g'irlangan deb hisoblanadi, hamma token bekor bo'ladi."""
    student = await create_student(session, email="reuse@test.uz")
    first_refresh_token = await _login(client, student)

    rotated = await client.post(
        "/api/auth/refresh", json={"refresh_token": first_refresh_token}
    )
    new_refresh_token = rotated.json()["refresh_token"]

    # Eskisini qayta ishlatishga urinish.
    replay = await client.post(
        "/api/auth/refresh", json={"refresh_token": first_refresh_token}
    )
    assert replay.status_code == 401

    # Yangi token ham endi ishlamaydi — barcha sessiyalar yopilgan.
    after_replay = await client.post(
        "/api/auth/refresh", json={"refresh_token": new_refresh_token}
    )
    assert after_replay.status_code == 401


async def test_refresh_without_token_returns_401(client):
    response = await client.post("/api/auth/refresh", json={})
    assert response.status_code == 401
