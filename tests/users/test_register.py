"""Ro'yxatdan o'tish: muvaffaqiyatli holat va takrorlangan email."""

from app.users.models import UserRole, UserStatus
from tests.factories import create_student


async def test_student_register_creates_pending_user(client):
    response = await client.post(
        "/api/auth/register/student",
        json={"full_name": "Ali Valiyev", "email": "ali@test.uz", "password": "parol12345"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == UserRole.student.value
    assert body["status"] == UserStatus.pending.value


async def test_teacher_register_creates_pending_user(client):
    response = await client.post(
        "/api/auth/register/teacher",
        json={
            "full_name": "Dilnoza Karimova",
            "email": "dilnoza@test.uz",
            "password": "parol12345",
            "specialization": "IELTS",
            "experience_years": 5,
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == UserRole.teacher.value


async def test_register_with_existing_email_returns_400(client, session):
    await create_student(session, email="band@test.uz")

    response = await client.post(
        "/api/auth/register/student",
        json={"full_name": "Boshqa Odam", "email": "band@test.uz", "password": "parol12345"},
    )

    assert response.status_code == 400


async def test_register_with_short_password_returns_422(client):
    response = await client.post(
        "/api/auth/register/student",
        json={"full_name": "Ali Valiyev", "email": "qisqa@test.uz", "password": "123"},
    )

    assert response.status_code == 422
